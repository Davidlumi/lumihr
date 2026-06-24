# -*- coding: utf-8 -*-
"""Seed the lumi-staff back-office: an internal staff org + the platform-admin
account that runs the console (closes D2 — see DECISIONS.md).

This provisions ACCOUNT data, not benchmark data — but it still follows the
firewall's double-guard convention (prints intended actions by default; writes
only when BOTH --write and --confirmed-by-david are passed). Idempotent: it
refuses to duplicate the staff org or the staff user, so it is safe to re-run.

    python3 server/seed_staff_admin.py                                  # dry-run
    python3 server/seed_staff_admin.py --write --confirmed-by-david     # apply

The staff org carries NO benchmark data (source='staff', classified=0) so it can
never enter the peer pool or aggregates. The staff user is a normal org 'admin'
of that empty org AND carries platform_admin=1 — the cross-tenant tier the
console gates on. Password defaults to the demo password (override with
LUMI_STAFF_PASSWORD); change it after first login.
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db          # noqa: E402
import auth        # noqa: E402

STAFF_ORG_NAME = "Lumi HR (staff)"
STAFF_EMAIL = "david@lumihr.co.uk"
STAFF_NAME = "David Whitfield"
STAFF_PASSWORD = os.environ.get("LUMI_STAFF_PASSWORD", "lumi-demo-2026")


def main():
    write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
    db.init_schema()                       # ensure platform_admin column exists
    conn = db.get_conn()

    nn = re.sub(r"[^a-z0-9]", "", STAFF_ORG_NAME.lower())
    org = conn.execute("SELECT * FROM orgs WHERE normalized_name=?", (nn,)).fetchone()
    user = auth.find_user(STAFF_EMAIL)

    print("Plan:")
    print("  staff org   '%s' (source=staff): %s" % (
        STAFF_ORG_NAME, "exists — skip" if org else "CREATE"))
    print("  staff user  '%s' (platform_admin=1): %s" % (
        STAFF_EMAIL, "exists — ensure flag" if user else "CREATE"))

    if not write:
        print("\n[dry-run] pass --write --confirmed-by-david to apply.")
        return

    if org is None:
        org_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO orgs(org_id, name, normalized_name, source, tier_entitlement, classified) "
            "VALUES (?,?,?,'staff','core',0)", (org_id, STAFF_ORG_NAME, nn))
        conn.commit()
        print("[applied] staff org created (%s)." % org_id)
    else:
        org_id = org["org_id"]

    if user is None:
        uid = auth.create_user(org_id, STAFF_EMAIL, STAFF_PASSWORD, "admin", STAFF_NAME)
        print("[applied] staff user created (%s)." % uid)
    else:
        uid = user["user_id"]
        print("[applied] staff user already present — leaving password unchanged.")

    conn.execute("UPDATE users SET platform_admin=1 WHERE user_id=?", (uid,))
    conn.commit()
    print("[applied] platform_admin=1 set on %s." % STAFF_EMAIL)
    print("\nStaff login: %s / %s  (change after first sign-in)" % (STAFF_EMAIL, STAFF_PASSWORD))


if __name__ == "__main__":
    main()
