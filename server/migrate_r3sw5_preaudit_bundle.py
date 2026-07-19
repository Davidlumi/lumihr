# -*- coding: utf-8 -*-
"""migrate_r3sw5_preaudit_bundle.py — pre-audit close-out, three independent parts.

A. NULL-industry populate: orgs.industry (+subsector where empty) from the
   Step-1-verified PROFILE sector for every NULL seed org (staff/signup excluded).
   Cascade: the enlarged hospitality set gets ADDITIVE tips/tronc-chain seeds
   (r3sw1 ratios, existing orgs' answers preserved byte-identically).
B. Clawback conditioning (REW_INC_071 — CONTEXT metric, premise corrected: NOT a
   marginal): bonus-less orgs (INC_103='None') read 'Not applicable'; per-org
   coherence hard assert — zero clawback-Yes without a bonus scheme.
C. DK strip, ruled scope: HOL_001's 5 standard-side Don't-knows -> deleted
   (n-excluded, never redistributed) + the DK option leaves the bank. The
   60-metric DK inventory is REPORTED for a separate blanket ruling, not acted on.
Each part has its own asserts and prints independently. Dry-run default;
--write requires --confirmed-by-david. Emits r3sw5_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import canon_industry, CFG

R3SW1 = json.load(open(os.path.join(ROOT, "r3sw1_derivation_rules.json")))
TIPS_QID = "REW_PAY_TIPS_EXIST_7c80c508"
TIPS_YES = "Yes – tips/service charges are received"
TIPS_NO = "No – tips/service charges not received"
HOL, CLAW, BONUS = "REW_BEN_HOL_001", "REW_INC_071", "REW_INC_103"
STAMP = "2026-07-18 r3sw5 pre-audit bundle"
LONG = {v: k for k, v in (CFG.get("industry_canon") or {}).items()}   # short -> long

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, _p))).items() if isinstance(v, dict)})


def lr_alloc(ratio, orgs):
    tot = float(sum(ratio.values()))
    raw = {l: w * len(orgs) / tot for l, w in ratio.items()}
    fl = {l: int(raw[l]) for l in raw}
    for l in sorted(raw, key=lambda l: (-(raw[l] - fl[l]), l))[: len(orgs) - sum(fl.values())]:
        fl[l] += 1
    out, i = {}, 0
    for l in ratio:
        for _ in range(fl[l]):
            out[orgs[i]] = l; i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()
    manifest = []

    # ================= PART A — NULL-industry populate + scoped-seed cascade =================
    nulls = [(o, n, s or "") for o, n, s in cur.execute(
        "SELECT org_id, name, source FROM orgs WHERE industry IS NULL OR industry=''")]
    plan_a = []
    for o, name, src in nulls:
        p = PROF.get(o)
        if src != "seed" or not p:
            continue                      # staff/signup or profile-less: not ours to tag
        short = p.get("Industry") or ""
        long_lbl = LONG.get(short, short)  # pass-throughs and 'Other' stay as-is
        plan_a.append((o, name, long_lbl, p.get("Subsector") or ""))
    mix = Counter(l for _, _, l, _ in plan_a)
    print("A: populate %d NULL seed orgs (excluded: %d non-seed/profile-less) | sectors: %s"
          % (len(plan_a), len(nulls) - len(plan_a), dict(mix.most_common())))
    new_hosp = sorted(o for o, _, l, _ in plan_a if l == "Hospitality, Leisure & Travel")
    # additive tips seed for the newly-scoped hospitality orgs (existing preserved)
    tips_new = lr_alloc({TIPS_YES: 4, TIPS_NO: 1}, sorted(
        new_hosp, key=lambda o: hashlib.sha256((TIPS_QID + "|" + o).encode()).hexdigest()))
    new_tips_yes = sorted(o for o, v in tips_new.items() if v == TIPS_YES)
    chain = {}
    for m in R3SW1["metrics"]:
        qid = m["qid"]
        if m.get("ratio"):
            cond = new_tips_yes if m["condition"] == "tips" else chain.get("_tronc_yes", [])
            ranked = sorted(cond, key=lambda o: hashlib.sha256((qid + "|" + o).encode()).hexdigest())
            chain[qid] = lr_alloc(m["ratio"], ranked)
            if qid == "REW_PAY_TRONC_6db81475":
                chain["_tronc_yes"] = sorted(o for o, v in chain[qid].items() if v == "Yes")
        else:
            from reseed_engine import latent
            cond = chain.get("_tronc_yes", [])
            lranked = sorted(cond, key=lambda o: (-latent(o, PROF),
                             hashlib.sha256((qid + "|" + o).encode()).hexdigest()))
            rows = {}
            for slug, pct in m["matrix_levels"].items():
                k = int(round(pct / 100.0 * len(lranked)))
                for i, o in enumerate(lranked):
                    rows[(o, slug)] = m["options"][0] if i < k else m["options"][1]
            chain[qid] = rows
    print("   cascade: +%d hospitality -> tips +%d (%dY/%dN) -> tronc-chain adds: %s"
          % (len(new_hosp), len(tips_new), len(new_tips_yes), len(tips_new) - len(new_tips_yes),
             {q[:24]: (len(v) if isinstance(v, dict) else 0) for q, v in chain.items() if not q.startswith("_")}))

    # ================= PART B — clawback conditioning (context metric) =================
    bonus_none = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id=? AND value='None'", (BONUS,))}
    claw = {o: v for o, v in cur.execute("SELECT org_id, value FROM answers WHERE question_id=?", (CLAW,))}
    flip_b = {o: "Not applicable" for o, v in claw.items() if o in bonus_none and v != "Not applicable"}
    before_b = Counter(claw.values())
    after_b = Counter(dict(claw, **flip_b).values())
    print("B: clawback conditioning — %d bonus-less orgs flip to 'Not applicable' (%d were incoherent Yes) | %s -> %s"
          % (len(flip_b), sum(1 for o in flip_b if claw[o] == "Yes"), dict(before_b), dict(after_b)))

    # ================= PART C — HOL_001 DK strip (ruled scope) =================
    dk_hol = [o for o, v in cur.execute("SELECT org_id, value FROM answers WHERE question_id=?", (HOL,)) if v == "Don't know"]
    print("C: HOL_001 DK strip — %d answers -> deleted (n-excluded); DK option leaves the bank" % len(dk_hol))

    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    TOUCHED_Q = [TIPS_QID, CLAW, HOL] + [m["qid"] for m in R3SW1["metrics"]]
    ph = ",".join("?" * len(TOUCHED_Q))
    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, TOUCHED_Q))).hexdigest()

    # A: orgs table
    for o, _, l, sub in plan_a:
        cur.execute("UPDATE orgs SET industry=?, subsector=COALESCE(NULLIF(subsector,''),?) WHERE org_id=?", (l, sub, o))
    # A: additive scoped seeds (INSERT only — existing rows never touched)
    for o, v in tips_new.items():
        cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,'',?,?)",
                    (o, TIPS_QID, v, STAMP))
    for qid, data in chain.items():
        if qid.startswith("_"): continue
        if all(isinstance(k, str) for k in data):
            for o, v in data.items():
                cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,'',?,?)",
                            (o, qid, v, STAMP))
        else:
            for (o, slug), v in data.items():
                cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,?,?,?)",
                            (o, qid, slug, v, STAMP))
    # B: clawback flips (history first)
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, CLAW))
    for o, v in flip_b.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (v, CLAW, o))
    # C: HOL DK deletions + option strip
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND value=?""",
                (STAMP, HOL, "Don't know"))
    cur.execute("DELETE FROM answers WHERE question_id=? AND value=?", (HOL, "Don't know"))
    opts = json.loads(cur.execute("SELECT options_json FROM questions WHERE id=?", (HOL,)).fetchone()[0])
    cur.execute("UPDATE questions SET options_json=? WHERE id=?",
                (json.dumps([o for o in opts if "don't know" not in o["label"].lower()]), HOL))
    c.commit()

    # ---- independent asserts ----
    left = cur.execute("""SELECT COUNT(*) FROM orgs o JOIN (SELECT DISTINCT org_id FROM answers) a ON a.org_id=o.org_id
                          WHERE (o.industry IS NULL OR o.industry='') AND COALESCE(o.source,'')='seed'""").fetchone()[0]
    assert left == 0, "PART A: seed orgs still NULL: %d" % left
    hosp_n = cur.execute("""SELECT COUNT(DISTINCT a.org_id) FROM answers a JOIN orgs o ON o.org_id=a.org_id
                            WHERE a.question_id=? AND o.industry='Hospitality, Leisure & Travel'""", (TIPS_QID,)).fetchone()[0]
    stray = cur.execute("""SELECT COUNT(*) FROM answers a JOIN orgs o ON o.org_id=a.org_id
                           WHERE a.question_id=? AND COALESCE(o.industry,'')!='Hospitality, Leisure & Travel'""", (TIPS_QID,)).fetchone()[0]
    assert stray == 0, "PART A: out-of-scope tips answers: %d" % stray
    db_bonus_none = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id=? AND value='None'", (BONUS,))}
    bad_b = [o for (o, v) in cur.execute("SELECT org_id, value FROM answers WHERE question_id=?", (CLAW,))
             if v == "Yes" and o in db_bonus_none]
    assert not bad_b, "PART B: clawback-Yes without bonus: %d" % len(bad_b)
    dk_left = cur.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (HOL, "Don't know")).fetchone()[0]
    assert dk_left == 0, "PART C: HOL DKs remain"
    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, TOUCHED_Q))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    manifest += [
        {"metric_id": "orgs.industry", "action": "A: NULL populate", "detail": json.dumps(dict(mix))},
        {"metric_id": TIPS_QID, "action": "A: additive scope seed", "detail": "n=%d (stray=0)" % hosp_n},
        {"metric_id": CLAW, "action": "B: bonus conditioning", "detail": json.dumps(dict(after_b))},
        {"metric_id": HOL, "action": "C: DK strip", "detail": "%d deleted, option removed" % len(dk_hol)},
    ]
    with open(os.path.join(ROOT, "r3sw5_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "detail"])
        w.writeheader(); w.writerows(manifest)
    print(json.dumps({"applied": True, "A_null_left": 0, "A_tips_n": hosp_n, "A_stray": 0,
                      "B_incoherent_left": 0, "C_dk_left": 0,
                      "non_target_book": "hash-identical", "manifest": "r3sw5_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
