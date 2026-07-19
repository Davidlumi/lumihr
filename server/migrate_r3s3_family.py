# -*- coding: utf-8 -*-
"""migrate_r3s3_family.py — maturity-family expansion + coupled range-max recompute.

Two metrics onto the gradient via reseed_engine.maturity_assign (no new engine code):
  REW_FAI_128  top-performer market pricing   anchors 5/25/70
  REW_PAY_001  formal pay ranges (have-ranges) anchors 5/30/90
COUPLED: REW265_PAY_RANGEMAX derived PER-ORG from REW_PAY_001's strict-Yes set —
members split lump/continue/frozen 40/20/40 (hash-ranked), non-members answer
'No formal ranges'. HARD ASSERT: zero orgs with have-ranges != Yes holding a
policy answer (the pay-structure-family coherence guard). A conflict fails the write.
Dry-run default; --write requires --confirmed-by-david. Emits r3s3_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import maturity_assign, latent

GEN = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["maturity_gradients"]
RM_QID = "REW265_PAY_RANGEMAX"
RM_SPLIT = [("Lump-sum in lieu", 40), ("Continue increases", 20), ("Frozen until range moves", 40)]
RM_NONE = "No formal ranges"
STAMP = "2026-07-18 r3s3 family"
TOUCHED = ["REW_FAI_128", "REW_PAY_001", RM_QID]

PROF = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, p))).items() if isinstance(v, dict)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()

    plans = {}
    for qid in ("REW_FAI_128", "REW_PAY_001"):
        rows = [(o, v) for o, v in cur.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (qid,))]
        ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                            WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (qid,)).fetchone()[0]
        assert ns == 0, "non-seed answers on %s — ABORT" % qid
        lat = {o: latent(o, PROF) for o, _ in rows}
        plans[qid] = {"rows": rows, "newmap": maturity_assign(qid, GEN[qid], rows, PROF, lat)}
    # coupled range-max: members = STRICT Yes on REW_PAY_001's NEW assignment
    yes_set = {o for o, v in plans["REW_PAY_001"]["newmap"].items() if v == "Yes"}
    rm_rows = [(o, v) for o, v in cur.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (RM_QID,))]
    members = sorted((o for o, _ in rm_rows if o in yes_set),
                     key=lambda o: hashlib.sha256((RM_QID + "|" + o).encode()).hexdigest())
    raw = {lbl: pct * len(members) / 100.0 for lbl, pct in RM_SPLIT}
    fl = {lbl: int(raw[lbl]) for lbl in raw}
    for lbl in sorted(raw, key=lambda l: -(raw[l] - fl[l]))[: len(members) - sum(fl.values())]:
        fl[lbl] += 1
    rm_map = {}
    i = 0
    for lbl, _ in RM_SPLIT:
        for _ in range(fl[lbl]):
            rm_map[members[i]] = lbl; i += 1
    for o, _ in rm_rows:
        if o not in rm_map:
            rm_map[o] = RM_NONE
    plans[RM_QID] = {"rows": rm_rows, "newmap": rm_map}

    def band(o): return (PROF.get(o) or {}).get("HR_Maturity") or "?"
    print("%s:" % ("APPLY" if a.write else "dry-run"))
    for qid in TOUCHED:
        p = plans[qid]
        before = Counter(v for _, v in p["rows"]); after = Counter(p["newmap"].values())
        print("  %s: %s\n    -> %s" % (qid, dict(before), dict(after)))
        if qid != RM_QID:
            pos = GEN[qid]["positive_option"]
            for b in ("Basic", "Developing", "Advanced"):
                t = sum(1 for o in p["newmap"] if band(o) == b)
                pn = sum(1 for o, v in p["newmap"].items() if band(o) == b and v == pos)
                print("      %-10s %d/%d (%.1f%% vs anchor %d%%)" % (b, pn, t, pn / t * 100 if t else 0, GEN[qid]["anchors"][b]))
    conflicts = [o for o, v in plans[RM_QID]["newmap"].items()
                 if v != RM_NONE and plans["REW_PAY_001"]["newmap"].get(o) != "Yes"]
    print("  COHERENCE: have-ranges!=Yes holding a policy answer: %d (must be 0)" % len(conflicts))
    assert not conflicts, conflicts[:5]
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (?,?,?) ORDER BY 1,2,3,4",
        TOUCHED))).hexdigest()
    manifest = []
    for qid in TOUCHED:
        p = plans[qid]
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                    (STAMP, qid))
        for o, lbl in p["newmap"].items():
            cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''", (lbl, qid, o))
        manifest.append({"metric_id": qid, "action": "maturity-family r3s3",
                         "before": json.dumps(dict(Counter(v for _, v in p["rows"]))),
                         "after": json.dumps(dict(Counter(p["newmap"].values())))})
    c.commit()

    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (?,?,?) ORDER BY 1,2,3,4",
        TOUCHED))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    for qid in TOUCHED:
        got = dict(cur.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (qid,)))
        assert got == dict(Counter(plans[qid]["newmap"].values())), (qid, got)
    # the coherence guard, re-checked FROM THE DB post-write
    live_yes = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id='REW_PAY_001' AND value='Yes'")}
    bad = [o for (o, v) in cur.execute("SELECT org_id, value FROM answers WHERE question_id=?", (RM_QID,))
           if v != RM_NONE and o not in live_yes]
    assert not bad, "POST-WRITE COHERENCE CONFLICTS: %s" % bad[:5]
    with open(os.path.join(ROOT, "r3s3_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader(); w.writerows(manifest)
    print(json.dumps({"applied": True, "coherence_conflicts": 0, "non_target_book": "hash-identical",
                      "manifest": "r3s3_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
