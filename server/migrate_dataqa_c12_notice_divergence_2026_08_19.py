#!/usr/bin/env python3
"""Data QA class 12 — let employer and employee notice diverge at senior levels
(2026-08-19, David's ruling: "differentiate — employer notice rises faster").

The two notice matrices were reported as "seeded with identical values at every level". That
overstated it. Measured cell by cell across all 1,890 pairs, they agree 81.9% of the time:

    board / executive        73% identical
    director                 67%
    head of                  72%
    senior manager           74%
    manager                  94%
    supervisor               95%
    frontline                97%

The junior end is right and is left alone — a frontline contract genuinely does mirror notice
both ways, and 97% is a fair picture of that. The senior end is the problem. A board contract
that requires the same notice from the employer as from the employee is the exception in UK
practice, not the rule at ~7 in 10: employers routinely give six months at that level while
requiring three.

So only the four senior rows move, and only the EMPLOYEE matrix is touched — the employer
distribution is left byte-identical, so nothing that reads employer notice shifts at all.
Where a pair currently matches, a share of employees are stepped DOWN one notice band:

    board / executive     73% identical -> 35%
    director              67%           -> 42%
    head of               72%           -> 52%
    senior manager        74%           -> 62%

Stepping down one band never produces a value outside the existing scale, and an employee
notice below one week is floored rather than created.

Deterministic, history-appending. Run aggregate.run_snapshot(1) afterwards.
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

EMPLOYER = "REW_Q524161"
EMPLOYEE = "b1785613-96ed-4a64-9fd7-762d0ac65f19"

# ascending notice scale; stepping "down" means one position left
BANDS = ["1 week", "2 weeks", "4 weeks", "8 weeks", "12 weeks", "16 weeks", "More than 16 weeks"]

# level -> target share of pairs that still match
TARGET_IDENTICAL = {
    "board_executive": 0.35,
    "director": 0.42,
    "head_of": 0.52,
    "senior_manager": 0.62,
}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)
    idx = {b: i for i, b in enumerate(BANDS)}
    moved = 0

    for lvl, want in TARGET_IDENTICAL.items():
        emp = {r["org_id"]: r["value"] for r in conn.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
            "AND matrix_row_id=?", (EMPLOYER, lvl))}
        eee = {r["org_id"]: r["value"] for r in conn.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
            "AND matrix_row_id=?", (EMPLOYEE, lvl))}
        orgs = sorted(set(emp) & set(eee))
        matching = [o for o in orgs if emp[o] == eee[o]]
        target_n = int(round(want * len(orgs)))
        k = len(matching) - target_n
        print("   %-22s identical %d/%d (%.0f%%) -> %d (%.0f%%)"
              % (lvl, len(matching), len(orgs), 100.0 * len(matching) / len(orgs),
                 target_n, 100.0 * target_n / len(orgs)))
        if k <= 0:
            print("      already at or below target — nothing moved")
            continue
        # only step down pairs that CAN step down (employee not already on the lowest band)
        eligible = [o for o in matching if idx.get(eee[o], 0) > 0]
        if len(eligible) < k:
            print("      REFUSE — need %d steppable, only %d are above the lowest band"
                  % (k, len(eligible)))
            continue
        for org in rnd.sample(eligible, k):
            new = BANDS[idx[eee[org]] - 1]
            moved += 1
            if WRITE:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=?",
                             (new, org, EMPLOYEE, lvl))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,?,?,datetime('now'))",
                             (org, EMPLOYEE, lvl, new))

    print("\n%d employee-notice cells %s (employer matrix untouched)"
          % (moved, "moved" if WRITE else "would move"))
    if WRITE:
        conn.commit()
        print("committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
