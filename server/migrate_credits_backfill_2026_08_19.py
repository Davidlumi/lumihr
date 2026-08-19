#!/usr/bin/env python3
"""Pulse credits — open the ledger for organisations that already exist (2026-08-19).

New organisations get their joining credit inside _insert_member_org, so they can never
exist without an opening ledger line. Everyone who joined before credits existed needs the
same line written retrospectively, or their balance reads 0 and they cannot launch the
pulse they were always entitled to.

Grants SIGNUP_GRANT (1) to every organisation with no signup_grant entry. Idempotent — the
grant helper refuses a second one — so re-running changes nothing.

Seed organisations are included deliberately. They are what the demo and the gate fixtures
run against, and a seed org with no credits would make the pulse journey untestable for the
wrong reason.

Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import credits as credits_mod          # noqa: E402

ROOT = os.path.join(HERE, "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))

    have = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name='credit_ledger'").fetchone()
    if not have:
        print("credit_ledger does not exist here — run the app once so init_schema creates it.")
        return

    orgs = [r["org_id"] for r in conn.execute("SELECT org_id FROM orgs ORDER BY org_id")]
    already = {r["org_id"] for r in conn.execute(
        "SELECT DISTINCT org_id FROM credit_ledger WHERE kind='signup_grant'")}
    todo = [o for o in orgs if o not in already]

    by_source = {}
    for r in conn.execute("SELECT source, COUNT(*) c FROM orgs GROUP BY source"):
        by_source[r["source"]] = r["c"]
    print("   organisations: %d  (%s)" % (len(orgs),
          " · ".join("%s %d" % (k or "?", v) for k, v in sorted(by_source.items()))))
    print("   already granted: %d" % len(already))
    print("   to grant %d credit each: %d" % (credits_mod.SIGNUP_GRANT, len(todo)))

    if WRITE:
        for org in todo:
            credits_mod.grant_signup(org, conn)
        conn.commit()
        total = conn.execute("SELECT COALESCE(SUM(delta),0) FROM credit_ledger").fetchone()[0]
        print("\n   granted. Ledger now totals %d credits across %d organisations."
              % (total, len(orgs)))
    else:
        print("\nRe-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
