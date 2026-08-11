#!/usr/bin/env python3
"""Per-dashboard peer sample (2026-08-11, David: "each dashboard should have its own
tied sample filter").

Adds a nullable `cut_json` column to the `dashboards` table so each dashboard can carry
its own {dim,value} peer cut (NULL = all peers). The active dashboard's cut drives every
card on it (web/js/pages.js DashboardsPage). Schema-only, additive, no data rewrite —
existing dashboards get NULL (= all peers), matching their prior behaviour of following
the app-wide selector's default. Idempotent. LUMI_DB-aware; DRY-RUN unless
--write --confirmed-by-david.
"""
import os, sys, sqlite3

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    cols = [r["name"] for r in c.execute("PRAGMA table_info(dashboards)").fetchall()]
    if "cut_json" in cols:
        print("NO-OP — dashboards.cut_json already present")
        c.close()
        return 0
    if WRITE:
        c.execute("ALTER TABLE dashboards ADD COLUMN cut_json TEXT")
        c.commit()
    n = c.execute("SELECT COUNT(*) n FROM dashboards").fetchone()["n"]
    print(("APPLIED" if WRITE else "DRY RUN") +
          " — add dashboards.cut_json (nullable = all peers); %d existing dashboard(s) → NULL" % n)
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
