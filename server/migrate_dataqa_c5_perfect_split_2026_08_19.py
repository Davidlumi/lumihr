#!/usr/bin/env python3
"""Data QA class 5 — the perfect 50/50 (2026-08-19, David: "Odd perfect 50%").

A bank-wide sweep for implausible distribution shapes — identical whole-number percentages,
near-perfect two-way splits, three-or-more options within a point of each other, and single
options above 92% — returned exactly one artefact:

  REW_BEN_058  "In the last 12 months, have you enhanced benefits in response to
                cost-of-living or labour market pressures?"
                Yes 135 · No 135 · n=270 · 50.0% / 50.0%

135 and 135 is not a survey result, it is a coin flip written down. Real yes/no questions
land on untidy numbers, and a reader who notices the symmetry stops trusting the rest of
the card — which is what happened.

Reseeded to 57.0% / 43.0% (154 / 116). The direction is deliberate: this asks whether an
employer enhanced benefits under cost-of-living and labour-market pressure over the last
year, and a small majority having done SOMETHING is the honest reading of that market. The
figure is modelled, like the rest of this seeded bank.

The seven other sweep hits were left alone and are listed here so nobody re-raises them:
AI-skills premium 7.5% yes, four-day week 93.7% no, EOT 94% no, grandparental leave 94% no,
leave donation 94.4% no, unlimited annual leave 94% no. Each is a genuinely rare practice
and a low yes is the correct answer, not a seeding failure.

Deterministic, count-conserving (n stays 270), history-appending.
Run aggregate.run_snapshot(1) afterwards.

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

QID = "REW_BEN_058"
SRC, DST = "No", "Yes"
TARGET_YES = 0.570


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))

    counts = {r["value"]: r["c"] for r in conn.execute(
        "SELECT value, COUNT(*) c FROM answers WHERE question_id=? AND snapshot_id=1 "
        "AND matrix_row_id='' GROUP BY value", (QID,))}
    n = sum(counts.values())
    yes = counts.get(DST, 0)
    want = int(round(TARGET_YES * n))
    move = want - yes
    print("   before: Yes %d · No %d · n=%d  (%.1f%% / %.1f%%)"
          % (yes, counts.get(SRC, 0), n, 100.0 * yes / n, 100.0 * counts.get(SRC, 0) / n))
    if move <= 0:
        print("\n   nothing to do — already at or above the target.")
        conn.close()
        return

    rows = conn.execute("SELECT org_id FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' AND value=? ORDER BY org_id", (QID, SRC)).fetchall()
    pool = [r["org_id"] for r in rows]
    if len(pool) < move:
        print("   REFUSE — %r has only %d, need %d" % (SRC, len(pool), move))
        conn.close()
        return
    pick = random.Random(SEED).sample(pool, move)
    print("   move %d from %r to %r" % (move, SRC, DST))
    print("   after : Yes %d · No %d · n=%d  (%.1f%% / %.1f%%)"
          % (yes + move, len(pool) - move, n,
             100.0 * (yes + move) / n, 100.0 * (len(pool) - move) / n))

    if WRITE:
        for org in pick:
            conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (DST, org, QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                         (org, QID, DST))
        conn.commit()
        print("\n   WROTE %d answers. Now rebuild: "
              "python3 -c \"import aggregate; aggregate.run_snapshot(1)\"" % move)
    else:
        print("\n   Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
