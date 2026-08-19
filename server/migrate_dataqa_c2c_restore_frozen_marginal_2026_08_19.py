#!/usr/bin/env python3
"""Data QA class 2c — restore the frozen marginal I broke (2026-08-19).

migrate_dataqa_c2b took 20 respondents OUT of "Base pay is protected" on
REW_BEN_REM_PAY_001 to populate two options that had none. That option is a FROZEN register
marginal: qa_plausibility carries a standing David ruling (Diff 11, 18 Jul 2026) recording
that "the 0.64 target was extracted ON that n=94 base". The move took it to 0.488 and the
freeze gate failed it at 15.2pp drift against a 5pp tolerance. Frozen means frozen.

The two zero options still need populating — that part of 2b was right — so the twenty come
from "Treatment varies by role or case" instead, which carries no frozen target.

    before 2b   protected 80 · varies 43 · over-time  0 · immediately 0
    after  2b   protected 60 · varies 43 · over-time 14 · immediately 6   <- 0.488, FAILS
    after  2c   protected 80 · varies 23 · over-time 14 · immediately 6   <- 0.650, passes

n stays 123 throughout; only the source of the twenty changes.

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

QID = "REW_BEN_REM_PAY_001"
SRC = "Treatment varies by role or case"
DST = "Base pay is protected"
FROZEN_TARGET = 0.640
TOL = 0.05


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))

    counts = {r["value"]: r["c"] for r in conn.execute(
        "SELECT value, COUNT(*) c FROM answers WHERE question_id=? AND snapshot_id=1 "
        "AND matrix_row_id='' GROUP BY value", (QID,))}
    base = sum(v for k, v in counts.items() if k != "Not applicable")
    have = counts.get(DST, 0)
    need = int(round(FROZEN_TARGET * base)) - have
    print("   base (excl. Not applicable): %d" % base)
    print("   %-34s %d  (%.3f)" % (DST, have, have / base if base else 0))
    print("   frozen target %.3f -> need to move %d back from %r" % (FROZEN_TARGET, need, SRC))

    if need <= 0:
        print("\n   nothing to do — already at or above the frozen target.")
        conn.close()
        return

    rows = conn.execute("SELECT org_id FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' AND value=? ORDER BY org_id", (QID, SRC)).fetchall()
    pool = [r["org_id"] for r in rows]
    if len(pool) < need:
        print("   REFUSE — %r has only %d, need %d" % (SRC, len(pool), need))
        conn.close()
        return

    rnd = random.Random(SEED)
    pick = rnd.sample(pool, need)
    after_dst = have + need
    after_src = len(pool) - need
    print("\n   after: %-34s %d  (%.3f)" % (DST, after_dst, after_dst / base))
    print("          %-34s %d" % (SRC, after_src))
    print("          drift vs frozen target: %.2fpp (tolerance %.0fpp)"
          % (abs(after_dst / base - FROZEN_TARGET) * 100, TOL * 100))

    if WRITE:
        for org in pick:
            conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (DST, org, QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                         (org, QID, DST))
        conn.commit()
        print("\n   WROTE %d answers. Now rebuild: "
              "python3 -c \"import aggregate; aggregate.run_snapshot(1)\"" % need)
    else:
        print("\n   Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
