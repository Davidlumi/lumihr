# -*- coding: utf-8 -*-
"""Backup migration for the metric_suggestions table.

CANONICAL HOME: this table is defined in db.py's SCHEMA and auto-applies on
restart via init_schema() (see DECISIONS.md — schema changes live in SCHEMA;
data changes use double-guarded scripts). This script is a manual fallback that
mirrors the firewall write-guard convention: it prints the DDL by default and
executes only when BOTH --write and --confirmed-by-david are passed.

    python3 server/migrate_metric_suggestions.py                              # dry-run: print SQL
    python3 server/migrate_metric_suggestions.py --write --confirmed-by-david  # apply to lumi.db
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn  # noqa: E402

DDL = """
CREATE TABLE IF NOT EXISTS metric_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    user_email TEXT,
    metric_name TEXT NOT NULL,
    what_it_measures TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    suggested_category TEXT,
    status TEXT NOT NULL DEFAULT 'new'
);
"""


def main():
    print(DDL)
    if not ("--write" in sys.argv and "--confirmed-by-david" in sys.argv):
        print("[dry-run] pass --write --confirmed-by-david to apply to lumi.db.")
        return
    conn = get_conn()
    conn.executescript(DDL)
    conn.commit()
    print("[applied] metric_suggestions created.")


if __name__ == "__main__":
    main()
