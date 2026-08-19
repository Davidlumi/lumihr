#!/usr/bin/env python3
"""Data QA class 3 — card headings that contradict their own options (2026-08-19, David).

The benchmark card shows `short_description`, not the question text. In all three cases the
question itself is fine and the HEADING is what misleads:

  EXT_REW_GAP_009   "Employees expectation to attend a workplace cadence"
                    Ungrammatical, and "cadence" adds nothing — the options ARE a frequency
                    (fully remote / <1 a month / 1-2 days / 3+ days / varies).
                    David: "Reword question makes no sense."

  PROP_fe1a29ec     "External pay/benefits benchmarking cadence"
                    Not a cadence at all. The options are formal / informal only / none —
                    WHETHER and HOW, not how often. David: "Reward question."

  REW_BEN_REM_PAY_001  "Remote working base pay treatment"
                    Noun-stack; says nothing about the move that triggers it. David: "Update
                    question vague." (The unused options on this one are a seed gap, class 2.)

Question text, options, ids and scoring are untouched — this changes the heading only.

Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import os, sqlite3, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

NEW = {
    "EXT_REW_GAP_009":     "How often employees attend a workplace",
    "PROP_fe1a29ec":       "Use of external benchmarking data",
    "REW_BEN_REM_PAY_001": "Base pay when someone moves to remote working",
}


def main():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    print("DB: %s\nMODE: %s\n" % (DB, "WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    n = 0
    for qid, new in NEW.items():
        r = conn.execute("SELECT short_description, text FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            print("  SKIP %s — not in this bank" % qid); continue
        old = r["short_description"] or ""
        if old == new:
            print("  SKIP %s — already reads %r" % (qid, new)); continue
        print("  %s" % qid)
        print("      asks : %s" % r["text"][:88])
        print("      was  : %s" % old)
        print("      now  : %s" % new)
        if WRITE:
            conn.execute("UPDATE questions SET short_description=? WHERE id=?", (new, qid))
        n += 1
    if WRITE and n:
        conn.commit(); print("\ncommitted %d heading(s)." % n)
    else:
        print("\n%d heading(s) would change. Re-run with --write --confirmed-by-david." % n)
    conn.close()


if __name__ == "__main__":
    main()
