# -*- coding: utf-8 -*-
"""migrate_r3sw3_pension_carveout.py — PENSION_TYPE public-sector carve-out (TPR A).

Surgical-band contract: the sector-keyed gradient entry declares ONLY the
Public Sector & Government band (no _default) -> maturity_assign returns a
newmap covering the 15 public orgs alone; everyone else is asserted
byte-identical. Tier-1 re-freeze rides in frozen_targets.json (already updated).
Backcompat: the 4 prior gradient metrics must still reproduce live byte-identically.
Dry-run default; --write requires --confirmed-by-david. Emits r3sw3_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import maturity_assign, latent, canon_industry

QID = "REW26_BEN_PENSION_TYPE"
GEN = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["maturity_gradients"]
FROZ = json.load(open(os.path.join(ROOT, "frozen_targets.json")))[QID]["dist"]
STAMP = "2026-07-18 r3sw3 pension carve-out"
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

    # backcompat: prior gradient metrics reproduce live byte-identically
    bad = []
    for q in ("PROP_fe1a29ec", "REW_FAI_128", "REW_PAY_001", "REW_INC_103"):
        rows = [(o, v) for o, v in cur.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (q,))]
        lat = {o: latent(o, PROF) for o, _ in rows}
        if maturity_assign(q, GEN[q], rows, PROF, lat) != dict(rows):
            bad.append(q)
    print("BACKCOMPAT prior gradient metrics:", bad or "byte-identical")
    assert not bad

    rows = [(o, v) for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (QID,))]
    lat = {o: latent(o, PROF) for o, _ in rows}
    newmap = maturity_assign(QID, GEN[QID], rows, PROF, lat)
    pub = {o for o, _ in rows if canon_industry((PROF.get(o) or {}).get("Industry") or "") == "Public Sector & Government"}
    assert set(newmap) == pub, "surgical-band contract breached: newmap must cover ONLY the public band"
    before = Counter(v for _, v in rows)
    changed = {o: (dict(rows)[o], v) for o, v in newmap.items() if dict(rows)[o] != v}
    after = Counter(dict(rows, **newmap).values())
    pubdist = Counter(newmap.values())
    print("%s: public band n=%d -> %s | changed %d orgs | national %s -> %s"
          % ("APPLY" if a.write else "dry-run", len(newmap), dict(pubdist), len(changed), dict(before), dict(after)))
    tgt = {k: round(v * 220) for k, v in FROZ.items()}
    assert dict(after) == tgt, ("national aggregate != frozen target", dict(after), tgt)
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    nonpub_pre = {o: v for o, v in rows if o not in pub}
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, QID))
    for o, v in newmap.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (v, QID, o))
    c.commit()
    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    nonpub_post = {o: v for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (QID,)) if o not in pub}
    assert nonpub_post == nonpub_pre, "COMMERCIAL/CHARITY NOT BYTE-IDENTICAL — ABORT"
    got = Counter(v for (v,) in cur.execute("SELECT value FROM answers WHERE question_id=?", (QID,)))
    assert dict(got) == tgt, (dict(got), tgt)
    with open(os.path.join(ROOT, "r3sw3_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader()
        w.writerow({"metric_id": QID, "action": "public-sector carve-out (TPR A, tier-1 re-freeze)",
                    "before": json.dumps(dict(before)), "after": json.dumps(dict(got))})
    print(json.dumps({"applied": True, "public_band": dict(pubdist), "changed_orgs": len(changed),
                      "nonpublic": "byte-identical", "national": dict(got),
                      "non_target_book": "hash-identical", "manifest": "r3sw3_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
