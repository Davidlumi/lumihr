# -*- coding: utf-8 -*-
"""migrate_r3s2_maturity_pilot.py — seed benchmarking through the maturity gradient.

Pilot of the r3s2 mechanism: PROP_fe1a29ec re-seeded per-org on HR_Maturity via
reseed_engine.maturity_assign (the SAME implementation future engine reseeds use).
Anchors from generated_marginals.json maturity_gradients (generator-emitted from
structured_bases). Replaces the Diff-15 flat 60/30/10 cohort-centre placeholder.
Dry-run default; --write requires --confirmed-by-david. Emits r3s2_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import maturity_assign, latent  # shared mechanism + spine

QID = "PROP_fe1a29ec"
ENTRY = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["maturity_gradients"][QID]
STAMP = "2026-07-18 r3s2 maturity pilot"

PROF = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    d = json.load(open(os.path.join(ROOT, p)))
    PROF.update({k: v for k, v in d.items() if isinstance(v, dict)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()

    rows = [(o, v) for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (QID,))]
    ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                        WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (QID,)).fetchone()[0]
    assert ns == 0, "non-seed answers present — ABORT"
    lat = {o: latent(o, PROF) for o, _ in rows}
    newmap = maturity_assign(QID, ENTRY, rows, PROF, lat)
    assert set(newmap) == {o for o, _ in rows}, "no sector gate on the pilot: full coverage expected"

    def band(o): return (PROF.get(o) or {}).get("HR_Maturity") or "?"
    per_band = {}
    for o, lbl in newmap.items():
        b = band(o); t, p = per_band.get(b, (0, 0))
        per_band[b] = (t + 1, p + (1 if lbl == ENTRY["positive_option"] else 0))
    before = Counter(v for _, v in rows); after = Counter(newmap.values())
    pos_share = sum(1 for v in newmap.values() if v == ENTRY["positive_option"]) / len(newmap)
    print("%s: n=%d | before %s" % ("APPLY" if a.write else "dry-run", len(rows), dict(before)))
    print("  after  %s | cohort formal %.1f%%" % (dict(after), pos_share * 100))
    for b in ("Basic", "Developing", "Advanced"):
        t, p = per_band.get(b, (0, 0))
        print("  %-10s n=%3d formal=%3d (%.1f%% vs anchor %d%%)" % (b, t, p, (p / t * 100 if t else 0), ENTRY["anchors"][b]))
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, QID))
    for o, lbl in newmap.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (lbl, QID, o))
    c.commit()
    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    got = dict(cur.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (QID,)))
    assert got == dict(after), (got, dict(after))
    with open(os.path.join(ROOT, "r3s2_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after", "per_band"])
        w.writeheader()
        w.writerow({"metric_id": QID, "action": "maturity-gradient pilot",
                    "before": json.dumps(dict(before)), "after": json.dumps(dict(after)),
                    "per_band": json.dumps({b: {"n": t, "formal": p} for b, (t, p) in per_band.items()})})
    print(json.dumps({"applied": True, "history_rows": len(rows), "non_target_book": "hash-identical",
                      "per_band_exact": "asserted", "manifest": "r3s2_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
