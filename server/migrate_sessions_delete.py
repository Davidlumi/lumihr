#!/usr/bin/env python3
"""Reward-side sessions deletion (PH1-SESSIONS-DELETE). Inert since Seam-B —
the reachability sweep found zero reads, only deletes. The 49 in-window rows
are bearer tokens at rest in the store this phase empties of exactly that.
identity.db sessions (the live store since Seam-B) is untouched.
History note, per the ruling: the retained reward DB-class backups hold these
rows until their own rotation — live-store hygiene, not history rewriting."""
import os, sqlite3, sys
DB = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))
write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
conn = sqlite3.connect(DB)
n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
u = conn.execute("SELECT COUNT(*) FROM sessions WHERE expires_at > datetime('now')").fetchone()[0]
print("[sessdel] reward sessions: %d (unexpired %d)" % (n, u))
if not write:
    print("[sessdel] DRY RUN — would DELETE FROM sessions (%d rows)." % n); sys.exit(0)
cur = conn.cursor()
cur.execute("DELETE FROM sessions")
print("[sessdel] deleted %d row(s)" % cur.rowcount)
assert cur.rowcount == n, (cur.rowcount, n)
conn.commit()
left = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
print("[sessdel] POST: sessions = %d (expect 0)" % left)
assert left == 0
print("[sessdel] PASS")
