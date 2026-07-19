# -*- coding: utf-8 -*-
"""migrate_r3sw7_virtualgp.py — virtual GP re-anchor + verdict re-earn (r3sw7).

ATOMIC config+data (the r3sw6 standing process): the --write path applies the
data reshape AND the mp-config lift (direction restored, unbenchmarked REMOVED)
AND questions.polarity in one execution — no mixed-state window. Dry-run
previews all three. Reshape: ruled dist 45/13/11/31 over the 220 answerers,
largest-remainder, latent-ranked down the ruled provision ladder.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent

QID = "REW264_HLT_VIRTUALGP"
GEN = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["ruled_distributions"][QID]
ORDER = json.load(open(os.path.join(ROOT, "ruled_orderings.json")))["orderings"][QID]["option_order"]
STAMP = "2026-07-18 r3sw7 virtualgp"
PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, _p))).items() if isinstance(v, dict)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()
    ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                        WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (QID,)).fetchone()[0]
    assert ns == 0, "non-seed answers — ABORT"
    rows = [(o, v) for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (QID,))]
    lat = {o: latent(o, PROF) for o, _ in rows}
    ranked = sorted((o for o, _ in rows), key=lambda o: (-lat[o], hashlib.sha256((QID + "|" + o).encode()).hexdigest()))
    n = len(ranked)
    dist = GEN["distribution"]
    raw = {l: dist[l] * n / 100.0 for l in dist}
    fl = {l: int(raw[l]) for l in raw}
    for l in sorted(raw, key=lambda l: (-(raw[l] - fl[l]), l))[: n - sum(fl.values())]:
        fl[l] += 1
    newmap = {}
    i = 0
    for lbl in reversed(ORDER):            # generous pole (Yes all) to top-latent
        for _ in range(fl.get(lbl, 0)):
            newmap[ranked[i]] = lbl; i += 1
    assert i == n
    before = Counter(v for _, v in rows); after = Counter(newmap.values())
    print("%s: n=%d | %s -> %s" % ("APPLY" if a.write else "dry-run", n, dict(before), dict(after)))
    print("  atomic staged: mp direction neutral->higher_is_better, unbenchmarked REMOVED; polarity neutral->higher_is_better")
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, QID))
    for o, v in newmap.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (v, QID, o))
    cur.execute("UPDATE questions SET polarity='higher_is_better' WHERE id=?", (QID,))
    c.commit()
    # atomic config lift (same execution)
    cfgp = os.path.join(ROOT, "data", "market_position_config.json")
    cfg = json.load(open(cfgp))
    e = cfg["metrics"][QID]
    e["direction"] = "higher_is_better"
    e.pop("unbenchmarked", None); e.pop("_diff14", None)
    e["_r3sw7"] = "VERDICT RE-EARNED (first benefits metric via the Diff-14 path): total provision sourced CIPD H&W 2025 grade A/B; split EST-flagged on the register"
    json.dump(cfg, open(cfgp, "w"), indent=2, ensure_ascii=False)
    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    got = dict(cur.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (QID,)))
    assert got == dict(after), (got, dict(after))
    with open(os.path.join(ROOT, "r3sw7_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader()
        w.writerow({"metric_id": QID, "action": "CIPD re-anchor + verdict re-earn (atomic config+data)",
                    "before": json.dumps(dict(before)), "after": json.dumps(dict(after))})
    print(json.dumps({"applied": True, "dist": dict(after), "config_lifted": True,
                      "non_target_book": "hash-identical", "manifest": "r3sw7_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
