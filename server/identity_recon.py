#!/usr/bin/env python3
"""Identity/reward reconciliation (D6's orphan assertion, first standalone form;
joins the gate suite properly at step 7 — deliberately NOT qa_-prefixed until then,
so the gate-roster derivation is unchanged).

Reads both stores read-only. For each dual-written table: rows present reward-side
with no identity counterpart, and the reverse, plus a content-drift count (rows
present both sides whose column tuples differ). Drift is FATAL (nonzero exit) per
the 1a sequencing ruling, whose condition — the 1b mutation mirror and 1c delete
mirror both landed — was met at b8aa490: every column in the compared sets now has
a live mirror, so any drift is a real dual-write defect, not an expected gap.
Sessions excluded by ruling (step 2 skip; clean cutover at the seam).

Counts only — no names, emails, or tokens. Exit 0 iff both orphan directions AND
drift are 0 for every table.
"""
import hashlib, os, sqlite3, sys

REWARD = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identity

r = sqlite3.connect("file:%s?mode=ro" % REWARD, uri=True)
i = sqlite3.connect("file:%s?mode=ro" % identity._resolve_identity_db_path(), uri=True)

PAIRS = [
    # (label, reward SQL, identity SQL, key index)
    ("orgs<->org_register",
     "SELECT org_id, name, normalized_name FROM orgs ORDER BY org_id",
     "SELECT org_id, name, normalized_name FROM org_register ORDER BY org_id", 0),
    ("users (5-col shared set; S4.2 split)",
     "SELECT user_id, org_id, email, pw_hash, display_name FROM users ORDER BY user_id",
     "SELECT user_id, org_id, email, pw_hash, display_name FROM users ORDER BY user_id", 0),
    ("invites",
     "SELECT token, org_id, email, role, created_by, expires_at, used_at FROM invites ORDER BY token",
     "SELECT token, org_id, email, role, created_by, expires_at, used_at FROM invites ORDER BY token", 0),
    ("password_resets",
     "SELECT token, user_id, expires_at, used_at FROM password_resets ORDER BY token",
     "SELECT token, user_id, expires_at, used_at FROM password_resets ORDER BY token", 0),
]

ok = True
for label, rsql, isql, k in PAIRS:
    rrows = {row[k]: row for row in r.execute(rsql)}
    irows = {row[k]: row for row in i.execute(isql)}
    only_reward = len(set(rrows) - set(irows))
    only_identity = len(set(irows) - set(rrows))
    drift = sum(1 for key in set(rrows) & set(irows) if rrows[key] != irows[key])
    print("%s: reward=%d identity=%d | reward-only (identity orphan missing)=%d | "
          "identity-only (reverse orphan)=%d | content-drift=%d"
          % (label, len(rrows), len(irows), only_reward, only_identity, drift))
    ok &= (only_reward == 0 and only_identity == 0 and drift == 0)

print("sessions: EXCLUDED by ruling (step-2 skip; clean cutover at the seam)")
print("RECONCILIATION: %s" % ("PASS — 0 orphans in both directions, 0 drift"
                              if ok else "FAIL — orphans or drift present"))
sys.exit(0 if ok else 2)
