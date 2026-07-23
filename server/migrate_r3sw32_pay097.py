"""
r3sw32 — PAY_097 (pay differentiated by performance): clear the 16 definitively-impossible answers.

REW_PAY_097 was seeded loosely coupled to its mechanism in BOTH directions. Ruled (David), a narrow honest fix:
  FIX (only)  CLEAR the 16 IMPOSSIBLE: orgs answering "Yes - strongly" (10) or "Yes - moderately" (6) with
              NEITHER a performance rating (PERF_03 = some/all) NOR a merit matrix (REW263_PAY_MERITMATRIX =
              Performance only / Full merit matrix) -> "Not applicable". They claim differentiation-BY-RATING
              with no mechanism to differentiate by. Child-impossible.
  PRESERVE    the 6 "No - flat or near-flat" no-mechanism answers (DELIBERATE ruling, not arithmetic): a no-
              mechanism org answering "we don't differentiate" is an honest substantive answer; the standing
              rule protects it. Clearing all 22 over-answers would have destroyed these 6 (the Option-2 trap).
  LEAVE       the 42 reverse-N/A (applicable orgs who self-declared N/A) UNTOUCHED, logged as a known base gap:
              filling fabricates (no independent evidence to falsify a fill — the unfalsifiable class); the
              union base (PERF_03 ∪ MERITMATRIX = 195) needs a multi-signal parent engine change, declined.
              The metric still UNDER-REPORTS by 42 after this diff — deliberate, recorded open.
NO condition on the 195 union (multi-signal parent, declined). NO coherence pair, NO applicable_bases change --
DATA-ONLY (the N/A bar still renders; this diff does NOT claim to clear it). VERDICT-NEUTRAL: PAY_097 is
class=Practice + neutral -> double-excluded at positions.py:778 (score_direction=-1 is a red herring; the
membership gate is the authority). Prior ruling (PRACTICE, philosophy fork) constrains classification/direction
only -- untouched here. 8 frozen asserted byte-identical. Dual-guard; dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD, NA = "REW_PAY_097", "Not applicable"
FLAT = "No – flat or near-flat"
YES = {"Yes – strongly differentiated", "Yes – moderately differentiated"}
PERF, MM = "PERF_03", "REW263_PAY_MERITMATRIX"
MM_USE = ("Performance only", "Full merit matrix")
TOUCHED = [CHILD]
STAMP = "2026-07-23"
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]


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
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == os.path.join(ROOT, "lumi.db")
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert not any(q in ft for q in (CHILD, PERF, MM)), "a target metric is unexpectedly frozen"
    def val(q): return {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))}
    p97, perf, mm = val(CHILD), val(PERF), val(MM)
    mech = {o for o, v in perf.items() if v.startswith("Yes")} | {o for o, v in mm.items() if v in MM_USE}

    clear = sorted(o for o, v in p97.items() if v in YES and o not in mech)
    flat_nomech = sorted(o for o, v in p97.items() if v == FLAT and o not in mech)
    rev_na = sorted(o for o, v in p97.items() if v == NA and o in mech)
    # --- HARD ASSERTS (derive-don't-hardcode) ---
    assert len(clear) == 16, "COHORT MOVED: clear set %d != 16 — HARD ABORT (ruling doesn't cover it)" % len(clear)
    strong = sum(1 for o in clear if p97[o] == "Yes – strongly differentiated")
    mod = sum(1 for o in clear if p97[o] == "Yes – moderately differentiated")
    assert strong == 10 and mod == 6, (strong, mod)
    assert len(flat_nomech) == 6 and not (set(clear) & set(flat_nomech)), "STANDING-RULE GUARD: 6 honest No-flat not intact/disjoint"
    assert len(rev_na) == 42, "reverse-N/A != 42 (%d)" % len(rev_na)
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)" % ",".join("?" * len(clear)), clear)}
    assert src <= {"seed"}, "non-seed org in clear set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)
    flat_pre = {o: p97[o] for o in flat_nomech}; rev_pre = {o: p97[o] for o in rev_na}

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  CLEAR 16 impossible -> N/A (10 strongly + 6 moderately, no rating AND no merit matrix)")
    print("  PRESERVE 6 honest No-flat (standing rule) ; LEAVE 42 reverse-N/A (known gap, still under-reports)")
    print("  DATA-ONLY: no config, no pair; N/A bar STILL renders (45 -> 61); base(render) stays 220")
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david (live) or --write (throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for o in clear:
        cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw32 pre-clear", CHILD, o))
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NA, CHILD, o) for o in clear])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    assert frozen_snap(c) == frozen_pre, "A FROZEN TARGET MOVED — HARD ABORT"
    now = val(CHILD)
    assert all(now[o] == NA for o in clear), "a cleared org is not NA"
    assert all(now[o] == flat_pre[o] for o in flat_nomech), "STANDING-RULE GUARD TRIPPED — a preserved No-flat moved"
    assert all(now[o] == rev_pre[o] for o in rev_na), "a reverse-N/A org moved"
    c.commit()

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw32_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([CHILD, "clear 16 impossible -> N/A", "10 strongly + 6 moderately; 6 No-flat preserved; 42 reverse-N/A left (gap)"])
    print(json.dumps({"applied": True, "cleared": len(clear), "split": {"strongly": strong, "moderately": mod},
                      "preserved_noflat": len(flat_nomech), "left_reverse_na": len(rev_na), "frozen8": "byte-identical",
                      "row_count": "%d (unchanged)" % n_before, "config": "unchanged (data-only)", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
