# Operator dry-run: exercise the provisioning form without touching live

PH-PROV-2a §3.4. This is how you confirm the form works end to end — before a sales
call, after a change, whenever — with the live stores untouched. There is no DOM test
harness (no Node in this environment), so this procedure IS the end-to-end check.

```bash
# 1. WAL-checkpointed copies of BOTH stores (backup API, never cp)
python3 - <<'EOF'
import sqlite3
for src, dst in (("lumi.db", "/tmp/dryrun_lumi.db"), ("identity.db", "/tmp/dryrun_identity.db")):
    s = sqlite3.connect(src); s.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    d = sqlite3.connect(dst); s.backup(d); d.close(); s.close()
    print("copied", src)
EOF

# 2. throwaway server on :8071 (leave your live :8060 alone)
cd server
LUMI_DB=/tmp/dryrun_lumi.db LUMI_IDENTITY_DB=/tmp/dryrun_identity.db \
  ANTHROPIC_API_KEY='' python3 -m uvicorn app:app --port 8071
```

3. Browser → `http://localhost:8071/app` → sign in as the super admin →
   Console → Organisations → **＋ Provision a member**. Everything you do here lands in
   the throwaway. Worth exercising each visit:
   - the happy path: six fields → Provision → copy the invite link → open the link in a
     private window and accept it → the member appears on the org's page;
   - a name collision (try "Thornbridge Retail Group plc" → the message names the class);
   - an existing email (your own) → distinct message pointing at the Users tab;
   - the submit button stays disabled until all six fields are filled.

4. Tear down: Ctrl-C the server, then delete the copies — the startup sweep will nag
   you on the next gate run if you forget:

```bash
rm /tmp/dryrun_lumi.db* /tmp/dryrun_identity.db*
```

## The lifecycle column and invite actions (PH-PROV-2b)

Same throwaway stack as above. Worth exercising each visit:

- **Lifecycle column** (Organisations list): seed and staff rows show a dash — only
  member orgs carry a state. `provisioned · NO LIVE INVITE` in red is the org that
  needs you: provisioned but never activated, and its invite has died.
- **Reissue** (org page → Pending invites): both variants confirm by naming the org and
  saying the previous link stops working — after a reissue, only the NEW link works
  (the old one 404s; try it).
- **The active-Admin refusal**: try issuing an admin invite to an org that already has
  one — you get the sole-admin-recovery pointer (docs/SOLE_ADMIN_RECOVERY.md), not an
  error. Deactivate the Admin in the Members table first and the same issue then succeeds.
