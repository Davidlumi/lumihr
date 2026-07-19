# -*- coding: utf-8 -*-
"""migrate_r3sw2_sector_gradient.py — sector-keyed gradient build (r3sw2, ruled).

  A. BACKCOMPAT PROOF: the generalised maturity_assign must reproduce the LIVE
     state of the three maturity metrics byte-identically (no-key entries take
     the old code path). Hard abort on any deviation.
  B. Stale-trust cleanup (re-tag regression, one-time): Brightstone + Severnbourne
     lose their Diff-13 bonus ladders (rows deleted on REW_INC_111/323ffcf1) and
     flip to all-level No on REW_INC_133 (the non-runner representation).
  C. REW_INC_103 re-seeded via the generalised gradient (sector-keyed,
     band_distributions, latent-within-band).
  D. REW_INC_131 DERIVED per-org: Yes := exactly the orgs with any REW_INC_133
     eligibility-Yes (post-cleanup); everyone else No. Four-way pair coherence.
Dry-run default; --write requires --confirmed-by-david. Emits r3sw2_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import maturity_assign, latent

GEN = json.load(open(os.path.join(ROOT, "generated_marginals.json")))
MGRAD = GEN["maturity_gradients"]
STALE_TRUSTS = ["Brightstone Trust", "Severnbourne Trust"]
BONUS_MATRICES = ["REW_INC_111", "323ffcf1-749b-43f3-bf34-1de6b8b1ca67"]
LTI_ELIG = "REW_INC_133"
INC_103, INC_131 = "REW_INC_103", "REW_INC_131"
TOUCHED = BONUS_MATRICES + [LTI_ELIG, INC_103, INC_131]
STAMP = "2026-07-18 r3sw2 sector gradient"

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, _p))).items() if isinstance(v, dict)})
NAME2ID = {p.get("Company_Name"): o for o, p in PROF.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()

    for qid in TOUCHED:
        ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                            WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (qid,)).fetchone()[0]
        assert ns == 0, "non-seed answers on %s — ABORT" % qid

    # ---- A. backcompat proof: generalised code reproduces live maturity state ----
    mismatches = []
    for qid in ("PROP_fe1a29ec", "REW_FAI_128", "REW_PAY_001"):
        rows = [(o, v) for o, v in cur.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (qid,))]
        lat = {o: latent(o, PROF) for o, _ in rows}
        new = maturity_assign(qid, MGRAD[qid], rows, PROF, lat)
        cur_map = dict(rows)
        diff = [o for o in new if new[o] != cur_map.get(o)] + [o for o in cur_map if o not in new]
        if diff:
            mismatches.append((qid, len(diff)))
    print("BACKCOMPAT: generalised maturity_assign vs live maturity metrics — mismatches: %s"
          % (mismatches or "NONE (byte-identical)"))
    assert not mismatches, "GENERALISATION CHANGED THE MATURITY FAMILY — ABORT"

    trust_ids = [NAME2ID[n] for n in STALE_TRUSTS]
    # ---- plan C: INC_103 via the gradient ----
    rows103 = [(o, v) for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (INC_103,))]
    lat103 = {o: latent(o, PROF) for o, _ in rows103}
    map103 = maturity_assign(INC_103, MGRAD[INC_103], rows103, PROF, lat103)
    before103 = Counter(v for _, v in rows103)
    # ---- plan D: INC_131 derived from post-cleanup 133 eligibility ----
    elig = {o for (o,) in cur.execute(
        "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value='Yes'", (LTI_ELIG,))}
    elig -= set(trust_ids)                       # part B flips them to No
    rows131 = [o for (o,) in cur.execute(
        "SELECT org_id FROM answers WHERE question_id=? AND matrix_row_id=''", (INC_131,))]
    map131 = {o: ("Yes" if o in elig else "No") for o in rows131}
    before131 = Counter(v for (v,) in cur.execute(
        "SELECT value FROM answers WHERE question_id=? AND value!=''", (INC_131,)))
    def band103(o):
        from reseed_engine import canon_industry
        return canon_industry((PROF.get(o) or {}).get("Industry") or "")
    per_band = Counter()
    for o, v in map103.items():
        if v != "None": per_band[band103(o)] += 1
    stale_rows = {q: cur.execute(
        "SELECT COUNT(*) FROM answers WHERE question_id=? AND org_id IN (?,?)", [q] + trust_ids).fetchone()[0]
        for q in BONUS_MATRICES + [LTI_ELIG]}
    print("%s:" % ("APPLY" if a.write else "dry-run"))
    print("  B stale trusts: bonus-matrix rows to delete %s | 133 rows to flip->No: %d"
          % ({q[:12]: n for q, n in stale_rows.items() if q in BONUS_MATRICES}, stale_rows[LTI_ELIG]))
    print("  C INC_103: %s -> %s" % (dict(before103), dict(Counter(map103.values()))))
    print("     bonus-havers by canon sector: %s" % dict(per_band.most_common(6)))
    print("  D INC_131: %s -> Yes=%d No=%d (derived := 133 eligibility-holders post-cleanup)"
          % (dict(before131), len([v for v in map131.values() if v == "Yes"]),
             len([v for v in map131.values() if v == "No"])))
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    ph = ",".join("?" * len(TOUCHED))
    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, TOUCHED))).hexdigest()
    for qid in TOUCHED:
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, qid))
    for q in BONUS_MATRICES:
        cur.execute("DELETE FROM answers WHERE question_id=? AND org_id IN (?,?)", [q] + trust_ids)
    cur.execute("UPDATE answers SET value='No' WHERE question_id=? AND org_id IN (?,?)", [LTI_ELIG] + trust_ids)
    for o, lbl in map103.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (lbl, INC_103, o))
    for o, lbl in map131.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (lbl, INC_131, o))
    c.commit()

    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, TOUCHED))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    got103 = dict(cur.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (INC_103,)))
    assert got103 == dict(Counter(map103.values())), got103
    db_yes131 = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id=? AND value='Yes'", (INC_131,))}
    db_elig = {o for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value='Yes'", (LTI_ELIG,))}
    assert db_yes131 == db_elig, "PAIR INCOHERENCE: %d misaligned" % len(db_yes131 ^ db_elig)
    for q in BONUS_MATRICES:
        left = cur.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND org_id IN (?,?)", [q] + trust_ids).fetchone()[0]
        assert left == 0, (q, left)
    with open(os.path.join(ROOT, "r3sw2_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader()
        w.writerow({"metric_id": INC_103, "action": "sector-keyed gradient reseed",
                    "before": json.dumps(dict(before103)), "after": json.dumps(dict(Counter(map103.values())))})
        w.writerow({"metric_id": INC_131, "action": "derived := 133 eligibility-holders",
                    "before": json.dumps(dict(before131)),
                    "after": json.dumps(dict(Counter(map131.values())))})
        for q in BONUS_MATRICES:
            w.writerow({"metric_id": q, "action": "stale-trust rows deleted", "before": stale_rows[q], "after": 0})
        w.writerow({"metric_id": LTI_ELIG, "action": "stale trusts flipped to all-level No",
                    "before": stale_rows[LTI_ELIG], "after": "No rows retained"})
    print(json.dumps({"applied": True, "backcompat": "byte-identical", "pair_coherence": "exact",
                      "yes131": len(db_yes131), "non_target_book": "hash-identical",
                      "manifest": "r3sw2_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
