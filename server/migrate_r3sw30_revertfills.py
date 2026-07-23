"""
r3sw30 — revert 17 Diff-7 fabrications on the pension-SS NIC-cap children (STANDING-RULE RESTORATION).

Option 2 (tighten the NIC-cap children to the 131 default-pension-SS cohort) was REJECTED: REW26_BEN_SALSAC
='Yes' means pension offered via salary sacrifice BY DEFAULT, not has-pension-SS. 43 of the 66 SALSAC=No
substantive answerers carry the WEL pension-SS tick (opt-in pension SS) and ARE subject to the £2,000 cap;
their answers are real. Diff 7's any-salsac base of 197 STANDS.

This diff is NOT a base tightening. It reverts a specific FABRICATION: Diff 7's false-NA correction (14 July)
RNG-overwrote a genuine "Not applicable" to a substantive answer for 17 orgs that had NO pension-SS evidence
at all (neither SALSAC=Yes nor the WEL pension tick) — manufacturing an answer for an org that had answered
honestly. Reverting restores their pre-Diff-7 state. Base moves 197 -> 180 as a CONSEQUENCE, not a goal.

DERIVE-DON'T-HARDCODE: the 17 are derived from answers_history (pre-14-July value == the NA option on the
child, Diff-7-overwritten to substantive) AND carry no pension-SS signal. If the derived N != 17 the cohort
has moved and the ruling doesn't cover it -> HARD ABORT. Each org is restored to the EXACT NA label it held
pre-Diff-7 (read from history, not assumed). The 6 genuine no-signal floor answers and the 43 opt-in orgs are
asserted UNTOUCHED (the standing-rule guard). Data-only (existing answerer_only decl drops the NA); NO config
change. Dual-guard; dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMP, RESP = "REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE"
NA = "Not applicable (no sal-sac)"
CHILDREN = [IMP, RESP]
TOUCHED = CHILDREN
WELTOK = "Salary Sacrifice for Pension Contributions"
STAMP = "2026-07-23"
BASE_AFTER = 180
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]


def toks(v): return [t.strip() for t in (v or "").split(";") if t.strip()]


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def frozen_snap(c):
    return {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8}


def earliest_hist(c, qid, o):
    r = c.execute("SELECT value FROM answers_history WHERE question_id=? AND org_id=? ORDER BY recorded_at LIMIT 1", (qid, o)).fetchone()
    return r[0] if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == os.path.join(ROOT, "lumi.db")
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert all(q in ft for q in FROZEN8), "a frozen target is missing"
    def val(q): return {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))}
    sal = val("REW26_BEN_SALSAC"); yes = {o for o, v in sal.items() if v == "Yes"}
    wel = val("WEL_BMAP_FIN_SALARY_SACRIFICE_001")
    welp = {o for o, v in wel.items() if WELTOK in toks(v)}
    haspens = yes | welp
    imp, resp = val(IMP), val(RESP)

    # --- DERIVE the 17 from provenance ---
    the66 = {o for o, v in imp.items() if v and v != NA} - yes            # SALSAC=No substantive
    no_signal = the66 - welp                                             # + no WEL tick -> no pension SS at all
    the17 = sorted(o for o in no_signal if earliest_hist(c, IMP, o) == NA)  # + Diff-7 overwrote a pre-NA
    genuine6 = sorted(no_signal - set(the17))
    optin43 = sorted(the66 & welp)
    assert len(the17) == 17, "COHORT MOVED: derived N=%d != 17 — HARD ABORT (ruling doesn't cover it)" % len(the17)
    assert all(earliest_hist(c, IMP, o) == NA and earliest_hist(c, RESP, o) == NA for o in the17), "an org lacks pre-Diff-7 NA on a child"
    assert all(o not in haspens for o in the17), "a to-revert org has a pension-SS signal"
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)" % ",".join("?" * len(the17)), the17)}
    assert src <= {"seed"}, "non-seed org in the 17: %s" % src

    # per-org, per-child restore target = the exact pre-Diff-7 label from history
    restore = {q: {o: earliest_hist(c, q, o) for o in the17} for q in CHILDREN}
    assert all(restore[q][o] == NA for q in CHILDREN for o in the17), "a restore target is not the NA option"
    guard_pre = {q: {o: val(q)[o] for o in optin43 + genuine6} for q in CHILDREN}   # standing-rule guard snapshot
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  derived 17 fabrications (pre-Diff-7 NA + Diff-7-filled + no pension-SS signal) — HARD-ASSERTED ==17")
    print("  revert both children -> pre-Diff-7 NA label; per-child edits: IMPACT %d, RESPONSE %d (=%d)" % (len(the17), len(the17), 2 * len(the17)))
    print("  UNTOUCHED (standing-rule guard): 43 opt-in-pension-SS orgs + 6 genuine no-signal floor answers")
    print("  base 197 -> %d (consequence); NO config change (existing answerer_only decl drops the NA)" % BASE_AFTER)
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david (live) or --write (throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for q in CHILDREN:
        for o in the17:
            cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                           SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                           WHERE question_id=? AND org_id=?""", (STAMP + " r3sw30 pre-revert", q, o))
        cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(restore[q][o], q, o) for o in the17])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    assert frozen_snap(c) == frozen_pre, "A FROZEN TARGET MOVED — HARD ABORT"
    for q in CHILDREN:
        now = val(q)
        assert all(now[o] == NA for o in the17), "%s: a reverted org is not NA" % q
        assert all(now[o] == guard_pre[q][o] for o in optin43 + genuine6), "%s: STANDING-RULE GUARD TRIPPED — a protected answer moved" % q
        base = len({o for o, v in now.items() if v and v != NA})
        assert base == BASE_AFTER, "%s base %d != %d" % (q, base, BASE_AFTER)
    c.commit()

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw30_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        for q in CHILDREN:
            w.writerow([q, "revert 17 Diff-7 fabrications -> pre-Diff-7 NA", "base 197->180 (consequence)"])
    print(json.dumps({"applied": True, "reverted": len(the17), "edits": 2 * len(the17), "base": BASE_AFTER,
                      "guard": "43 opt-in + 6 genuine UNTOUCHED (asserted)", "frozen8": "byte-identical",
                      "row_count": "%d (unchanged)" % n_before, "config": "unchanged (no write)", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
