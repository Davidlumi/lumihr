#!/usr/bin/env python3
"""Data QA class 2a — the two redundancy questions where every band is empty (2026-08-19).

RED_TERM_02 (max redundancy multiple) and RED_TERM_03 (max weeks' pay) each have 221
respondents and NOT ONE substantive answer. Both remaining options are flagged is_na, so
100% of respondents sit in a non-answer:

    RED_TERM_02   Not applicable 103  +  Varies by grade/tenure 118  = 221
    RED_TERM_03   Not applicable 105  +  Varies by grade/tenure 116  = 221

Two questions answered by 221 organisations that say nothing about redundancy terms.

WHAT THIS DOES. It leaves "Not applicable (statutory only)" alone — roughly half of UK
employers really do pay statutory only, and that half is the honest part of the current
data. It redistributes most of the "Varies by grade/tenure" cohort onto real bands, keeping
a fifth genuinely "varies", because some employers do decide case by case.

WHAT THE SHAPE IS BASED ON. UK enhanced-redundancy practice concentrates at one to two
weeks' pay per year of service, and caps commonly land between six months and a year.
The curves below follow that. THEY ARE MODELLED, NOT MEASURED — this is seeded peer data,
as the whole bank is, and the alternative on the table was leaving 100% of respondents in
a non-answer, which is not more honest, only less useful.

Deterministic: the cohort is sorted by org_id and allocated with a fixed seed, so the same
input always produces the same output and a re-run is a no-op.
Count-conserving: n stays 221 on both; only the split inside the "varies" cohort changes.
History-safe: updates `answers` and APPENDS to `answers_history`; never deletes history.

Run aggregate.run_snapshot(1) afterwards or the API keeps serving the stale payload.

Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import os
import random
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SEED = 20260819

PLAN = {
    "RED_TERM_02": ("Varies by grade/tenure", [
        ("Varies by grade/tenure", 24),   # genuinely case-by-case
        ("Up to 1× weekly pay", 14),
        ("More than 1× to 1.5×", 26),
        ("More than 1.5× to 2×", 30),   # the modal enhanced package
        ("More than 2× to 3×", 16),
        ("More than 3× to 4×", 6),
        ("More than 4×", 2),
    ]),
    "RED_TERM_03": ("Varies by grade/tenure", [
        ("Varies by grade/tenure", 23),
        ("Up to 12 weeks", 12),
        ("13–26 weeks", 30),   # ~2 quarters, the common cap
        ("27–39 weeks", 18),
        ("40–52 weeks", 20),   # a year's pay
        ("53–78 weeks", 8),
        ("79–104 weeks", 4),
        ("More than 104 weeks", 1),
    ]),
}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    for qid, (src, targets) in PLAN.items():
        rows = conn.execute("SELECT org_id FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' AND value=? ORDER BY org_id",
                            (qid, src)).fetchall()
        cohort = [r["org_id"] for r in rows]
        want = sum(n for _, n in targets)
        print("== %s   cohort in %r: %d   plan totals: %d" % (qid, src, len(cohort), want))
        if not cohort:
            print("   SKIP — nothing to redistribute (already applied?)\n")
            continue
        if want != len(cohort):
            print("   REFUSE — plan totals %d but the cohort is %d; that would not conserve n\n"
                  % (want, len(cohort)))
            continue
        rnd = random.Random(SEED)
        order = cohort[:]
        rnd.shuffle(order)
        moves = []
        i = 0
        for label, n in targets:
            for org in order[i:i + n]:
                if label != src:
                    moves.append((org, label))
            i += n
        for label, n in targets:
            print("   %-30s %4d   %5.1f%% of 221" % (label[:30], n, 100.0 * n / 221))
        print("   moves: %d answers · %d stay in %r · 'Not applicable' untouched"
              % (len(moves), dict(targets).get(src, 0), src))
        if WRITE:
            for org, label in moves:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (label, org, qid))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) "
                             "VALUES (?,1,?,'',?,datetime('now'))", (org, qid, label))
            print("   WROTE %d answers (+%d history rows)" % (len(moves), len(moves)))
        print()
    if WRITE:
        conn.commit()
        print("committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
