#!/usr/bin/env python3
"""What the AI surfaces cost, and how often their output survives the gate.

Read this after a week of real use to decide the model question with a table instead of an
opinion: which surface dominates the token bill, which is slow, and which has its output
rejected often enough that the model is doing the work twice.

    python3 ai_cost_report.py [--days 7] [--db path]

Money appears only if LUMI_AI_PRICE_IN_PER_MTOK / LUMI_AI_PRICE_OUT_PER_MTOK are set to
the rates on your bill — no price is baked in, because a wrong constant is worse than none.
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ai_metrics                               # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--db", default=os.environ.get("LUMI_DB")
                    or os.path.join(HERE, "..", "lumi.db"))
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(a.db), uri=True)
    conn.row_factory = sqlite3.Row
    have = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name='ai_calls'").fetchone()
    if not have:
        print("No ai_calls table in %s — start the app once so init_schema creates it."
              % a.db)
        return 1
    print("DB: %s\n" % os.path.abspath(a.db))
    print(ai_metrics.render(conn, a.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
