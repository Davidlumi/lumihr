"""
r3sw31 — LTI-types (REW_INC_132): condition on the ruled parent, clear the seed over-answer.

REW_INC_132 "which LTI types offered" was seeded UNCONDITIONED on its parent — 211 substantive answers vs
REW_INC_131=Yes=65 (the r3sw2-ruled exec-LTI operators, coherence-enforced = the INC_133 eligibility-holders,
131<->133 pair-locked). Of the 148 over-answers: 131 have NO LTI/equity signal at all, 17 are secondary-equity-
only (EMICSOP/SHAREPLAN operators — all-employee SAYE/SIP or discretionary EMI/CSOP, which INC_131 deliberately
excludes). Ruled (David): CLEAR all 148 to the existing "Not applicable" is_na option; condition on INC_131=Yes.
Base 211 -> 63. This corrects a ~3x prevalence inflation (offers-an-LTI-type 96% -> 30%) and removes 131 orgs'
fabricated LTI practice (e.g. a charity shown offering performance shares). INC_132 is class=Practice / neutral /
direction=None (score_direction 0) — NO directional verdict moves; the harm is data-correctness, not verdicts.

NO reclassify (parent r3sw2-ruled + 131<->133 pair-locked), NO remap, NO floor-add (no "None" option; N/A is the
honest no-LTI answer; remapping to "Other" (score 100) would fabricate). The 17 cleared alongside the 131; the
INC_131-vs-EMICSOP/SHAREPLAN coherence gap (union 82 vs ruled 65) logged as a KNOWN OUT-OF-SCOPE fork (WEL-vs-
SALSAC treatment). Parent + 131<->133 pair asserted UNTOUCHED. Provenance: INC_132 has zero answers_history
(pure original seed). Subset pair added: INC_132-substantive ⊆ INC_131=Yes (single-value parent_value selector,
NO engine change). Data UPDATE-only. Dual-config atomic (r3sw7); dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD, NA = "REW_INC_132", "Not applicable"
PARENT, PYES = "REW_INC_131", "Yes"
EMI, SP = "REW264_INC_EMICSOP", "REW264_INC_SHAREPLAN"
EMI_OP, SP_OP = ("EMI", "CSOP", "Both"), ("SAYE", "SIP", "Both")
TOUCHED = [CHILD]
STAMP = "2026-07-23"
BASE_AFTER = 63
BASE_LABEL = "organisations that operate long-term incentive plans"
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]
NOTE = ("INC_132-substantive ⊆ INC_131=Yes (r3sw31): LTI-types answerable only by ruled LTI-operators (65, "
        "r3sw2 exec-LTI eligibility, 131<->133 pair-locked); a future reseed that re-over-answers INC_132 fails")


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def frozen_snap(c):
    return {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", dest="cout", default=None)
    ap.add_argument("--sb-out", dest="sbout", default=None)
    ap.add_argument("--gm-out", dest="gmout", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    served_sb = os.path.join(ROOT, "structured_bases.json")
    served_gm = os.path.join(ROOT, "generated_marginals.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if is_live:
            a.cout = a.cout or served_ab; a.sbout = a.sbout or served_sb; a.gmout = a.gmout or served_gm
            if not a.confirmed:
                print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
        else:
            for nm, v in (("--config-out", a.cout), ("--sb-out", a.sbout), ("--gm-out", a.gmout)):
                if v is None:
                    sys.exit("REFUSED: throwaway needs %s (r3sw7)" % nm)
            if os.path.abspath(a.cout) == served_ab or os.path.abspath(a.sbout) == served_sb or os.path.abspath(a.gmout) == served_gm:
                sys.exit("REFUSED: throwaway may not target a served config (r3sw7)")

    c = sqlite3.connect(a.db)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert CHILD not in ft and PARENT not in ft, "a target metric is unexpectedly frozen"
    def val(q): return {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))}
    i132, i131 = val(CHILD), val(PARENT)
    emi, sp = val(EMI), val(SP)
    yes = {o for o, v in i131.items() if v == PYES}
    assert len(yes) == 65, "INC_131=Yes moved from ruled 65: %d" % len(yes)
    sub = {o for o, v in i132.items() if v and v != NA}
    clear = sorted(sub - yes)
    assert len(clear) == 148, "COHORT MOVED: clear set %d != 148 — HARD ABORT" % len(clear)
    emi_op = {o for o, v in emi.items() if v in EMI_OP}; sp_op = {o for o, v in sp.items() if v in SP_OP}
    no_signal = sorted(set(clear) - (emi_op | sp_op)); secondary = sorted(set(clear) & (emi_op | sp_op))
    assert len(no_signal) == 131 and len(secondary) == 17, (len(no_signal), len(secondary))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)" % ",".join("?" * len(clear)), clear)}
    assert src <= {"seed"}, "non-seed org in clear set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  parent INC_131=Yes (ruled, UNTOUCHED) = %d" % len(yes))
    print("  CLEAR %d over-answers -> N/A (%d no-signal + %d secondary-equity-only); base 211 -> %d"
          % (len(clear), len(no_signal), len(secondary), BASE_AFTER))
    print("  subset pair INC_132-substantive ⊆ INC_131=Yes (parent_value selector, no engine change)")
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + staged outs for throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for o in clear:
        cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw31 pre-clear", CHILD, o))
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NA, CHILD, o) for o in clear])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    assert frozen_snap(c) == frozen_pre, "A FROZEN TARGET MOVED — HARD ABORT"
    assert {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (PARENT,)) if v == PYES} == yes, "PARENT MOVED"
    now_sub = {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value!=''", (CHILD,)) if v != NA}
    assert now_sub <= yes and now_sub == (sub & yes) and len(now_sub) == BASE_AFTER, "post substantive != INC_131=Yes answerers"

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab.setdefault("metrics", {})[CHILD] = {"mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
        "_r3sw31": "LTI-types conditioned on INC_131=Yes (65, ruled); 148 seed over-answers cleared (131 no-signal + 17 secondary-equity-only); neutral practice, no verdict move"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    sb = json.load(open(served_sb, encoding="utf-8"))
    pairs = list(sb.get("_coherence_pairs") or [])
    pairs.append({"child": CHILD, "child_value_not": NA, "parent": PARENT, "parent_value": PYES, "relation": "subset_orgs", "note": NOTE})
    sb["_coherence_pairs"] = pairs
    sb_text = json.dumps(sb, indent=1, ensure_ascii=False)
    gm = json.load(open(served_gm, encoding="utf-8")); gm["coherence_pairs"] = pairs
    gm_text = json.dumps(gm, indent=1, ensure_ascii=False)
    c.commit()
    for path, text in ((a.cout, ab_text), (a.sbout, sb_text), (a.gmout, gm_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw31_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([CHILD, "clear 148 over-answers -> N/A + answerer_only + subset pair", "131 no-signal + 17 secondary; base 211->63"])
    print(json.dumps({"applied": True, "cleared": len(clear), "no_signal": len(no_signal), "secondary": len(secondary),
                      "base": BASE_AFTER, "parent": "INC_131=Yes 65 UNTOUCHED", "frozen8": "byte-identical",
                      "row_count": "%d (unchanged)" % n_before, "pair": "INC_132-substantive ⊆ INC_131=Yes", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
