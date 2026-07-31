#!/usr/bin/env python3
"""S6 step 3 commit 1b (S4.2 amendment, ruled 2026-07-30): reshape identity.users
from 12 columns to the 5-column identity set — user_id, org_id (deliberate
duplicate, drift-checked), email, pw_hash, display_name.

The 7 dropped columns (role, chart_prefs_json, preview_as_core, created_at,
notify_prefs_json, platform_admin, active_dashboard_id) are account state that
stays reward-side permanently; their identity-side copies are discarded, and the
reward-side originals are untouched by this script (it never opens the reward store).

SQLite >= 3.35 path: ALTER TABLE DROP COLUMN x7 (live library 3.51.0). Preserves
the user_id PRIMARY KEY and the inline email UNIQUE constraint (neither is touched).
Proof: the 5-column content hash is taken before and asserted equal after.

Guarded: rehearses unless BOTH --write AND --confirmed-by-david are passed.
Targets the identity store via identity.py's resolver (LUMI_IDENTITY_DB honoured).
"""
import hashlib, os, sys

_here = os.path.dirname(os.path.abspath(__file__))
for _cand in (_here, os.path.join(os.getcwd(), "server")):
    if os.path.isfile(os.path.join(_cand, "identity.py")):
        sys.path.insert(0, _cand)
        break
import identity

DROP = ["role", "chart_prefs_json", "preview_as_core", "created_at",
        "notify_prefs_json", "platform_admin", "active_dashboard_id"]
KEEP = ["user_id", "org_id", "email", "pw_hash", "display_name"]
write_mode = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

conn = identity.get_conn()
cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
assert set(DROP) <= set(cols), "drop-set column missing: already reshaped? cols=%s" % cols


def keep_hash():
    h = hashlib.sha256()
    for r in conn.execute("SELECT %s FROM users ORDER BY user_id" % ", ".join(KEEP)):
        h.update(("|".join("" if v is None else str(v) for v in r)).encode())
    return h.hexdigest()[:16]


before = keep_hash()
n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
print("[reshape] pre: %d cols, %d rows, kept-5 hash %s" % (len(cols), n, before))

if not write_mode:
    print("[reshape] DRY RUN — would ALTER TABLE users DROP COLUMN x7: %s" % ", ".join(DROP))
    sys.exit(0)

for col in DROP:
    conn.execute("ALTER TABLE users DROP COLUMN %s" % col)
conn.commit()

cols_after = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
after = keep_hash()
n2 = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
print("[reshape] post: %d cols (%s), %d rows, kept-5 hash %s, integrity %s"
      % (len(cols_after), ", ".join(cols_after), n2, after, ic))
assert cols_after == KEEP, "column set/order unexpected: %s" % cols_after
assert after == before, "kept-column content moved during reshape"
assert n2 == n and ic == "ok"
print("[reshape] PASS — 5-column identity.users, content preserved")
