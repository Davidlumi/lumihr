#!/usr/bin/env python3
"""THROWAWAY-ONLY scaffolding: give seed organisations a signed-in Admin so the
self-service pulse journey can be exercised end to end (2026-08-19).

The 270 seed organisations have benchmark answers but no user accounts, so nothing can log
in as them and nothing can walk the pulse journey the way a member does. This mints one
Admin per named organisation with a known password.

REFUSES TO RUN AGAINST THE LIVE STORE. It creates credentials, so a mistyped LUMI_DB would
be a real security event, not an inconvenience: the path must live under a scratchpad or
tmp directory and must not be the repo's lumi.db.

    LUMI_DB=<throwaway> LUMI_IDENTITY_DB=<throwaway> python3 qa_scaffold_pulse_orgs.py --count 4
"""
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, ".."))
DB = os.environ.get("LUMI_DB", "")
IDB = os.environ.get("LUMI_IDENTITY_DB", "")

PASSWORD = "pulse-agent-2026!"          # throwaway fixture credential, never a real secret


def _refuse_if_live():
    live = os.path.abspath(os.path.join(ROOT, "lumi.db"))
    live_id = os.path.abspath(os.path.join(ROOT, "identity.db"))
    for label, path in (("LUMI_DB", DB), ("LUMI_IDENTITY_DB", IDB)):
        if not path:
            sys.exit("REFUSING: %s is unset. This script mints credentials and must only "
                     "ever run against an explicit throwaway." % label)
        ap = os.path.abspath(path)
        if ap in (live, live_id):
            sys.exit("REFUSING: %s points at the LIVE store (%s)." % (label, ap))
        if not ("/scratchpad" in ap or ap.startswith("/tmp") or ap.startswith("/private/tmp")):
            sys.exit("REFUSING: %s (%s) is not under a scratchpad or tmp directory." % (label, ap))


def main():
    _refuse_if_live()
    import auth as auth_lib
    import identity
    from db import get_conn

    count = 4
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    conn = get_conn()
    # organisations with benchmark data but no account, largest first so the pulse
    # authors look like plausible employers rather than the tail of the seed
    rows = conn.execute(
        "SELECT o.org_id, o.industry, o.fte_band FROM orgs o "
        "WHERE o.source='seed' AND NOT EXISTS (SELECT 1 FROM users u WHERE u.org_id=o.org_id) "
        "ORDER BY o.org_id LIMIT ?", (count,)).fetchall()

    made = []
    for i, r in enumerate(rows, 1):
        org_id = r["org_id"]
        ident = identity.org_display(org_id)
        org_name = (ident or {}).get("name") or ("Seed org %s" % org_id[:8])
        email = "pulse-agent-%d@example.com" % i
        if identity.lookup_user_by_email(email):
            print("   %-42s %s (already exists)" % (org_name[:42], email))
            made.append((org_name, email, org_id))
            continue
        uid = str(uuid.uuid4())
        pw_hash = auth_lib.hash_password(PASSWORD)
        conn.execute("INSERT INTO users(user_id, org_id, role, platform_admin) VALUES (?,?,?,0)",
                     (uid, org_id, "admin"))
        identity.register_user(uid, org_id, email, pw_hash, "Pulse Agent %d" % i)
        conn.commit()
        print("   %-42s %-28s %s" % (org_name[:42], email, r["industry"] or "—"))
        made.append((org_name, email, org_id))

    print("\n%d admin account(s) ready. Password for all: %s" % (len(made), PASSWORD))
    print("Base URL: http://localhost:8069/app")
    return made


if __name__ == "__main__":
    main()
