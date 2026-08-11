#!/usr/bin/env python3
"""UX: tag the two pay-multiplier matrices as unit_type='multiplier' (2026-08-10).

REW_Q534581 (hourly-paid pay multipliers by time band) and REW_Q528801 (overtime
multiplier by shift type) held unit_type='none', so their derived signal/median display
rendered a bare number ('you 1, market median 1.25') instead of a multiplier. Tagging
them 'multiplier' lets fmtValue append '×' (web/js/core.js). questions-table only
(not answers) — no answer-book fingerprint / L1 impact. LUMI_DB-aware; DRY-RUN unless
--write --confirmed-by-david.
"""
import os, sys, sqlite3

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
IDS = ("REW_Q534581", "REW_Q528801")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changed = 0
    for qid in IDS:
        r = c.execute("SELECT unit_type FROM questions WHERE id=?", (qid,)).fetchone()
        if r is None:
            print("  MISSING:", qid); continue
        if (r["unit_type"] or "") == "multiplier":
            continue
        changed += 1
        if WRITE:
            c.execute("UPDATE questions SET unit_type='multiplier' WHERE id=?", (qid,))
    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d/%d metrics tagged unit_type='multiplier'" % (changed, len(IDS)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
