# Orphan remediation runbook (PH-PROV-1e, 2026-08-08)

`server/identity_recon.py` audits the Phase-1 split's dual-write integrity: every
org/user/invite/reset must exist in BOTH stores (reward `lumi.db` + identity
`identity.db`) or NEITHER. It exits non-zero on any orphan or field drift, prints the
orphan's LOCATOR (org_id / user_id), and for token-keyed rows prints
`token_sha256[:12]=<digest>` — never the bearer (PH-PROV-1d). It runs at the end of
every `run_gates.sh` suite (auditing the whole run's dual-write hygiene) and is safe
to run by hand at any time: it is READ-ONLY.

```bash
cd server && python3 identity_recon.py            # live stores
LUMI_DB=… LUMI_IDENTITY_DB=… python3 identity_recon.py   # a named pair
```

## Reading the output

Each section reports both directions:

- `reward-only (identity orphan missing)=N` — a row exists reward-side with no
  identity twin. **This is the dangerous direction**: the record works mechanically
  (ids resolve) but has no name/email — a provisioning write that died between the
  reward commit and the identity shadow-writes.
- `identity-only=N` — an identity row with no reward twin. Usually a cleanup that
  removed the reward half first, or a probe org swept from one store only.
- `drift` — both rows exist but a compared field differs (expires_at, used_at, role…).

## Remediation, by direction

**Always diagnose before touching anything.** The locator printed is the query key;
none of the fixes below are scripts to run blind — each is a decision about ONE row.

### 1. Reward-only org (the silent provisioning orphan)

The classic failure: `POST /api/admin/orgs` returned 200, the reward org + invite
exist, but the identity register/invite rows are missing — the invitee's link will
dead-end because the identity store doesn't know the email.

- If the provisioning is WANTED: re-provision from the console (a fresh org +
  invite); then delete the orphan pair reward-side:
  `DELETE FROM invites WHERE org_id='<locator>'; DELETE FROM orgs WHERE org_id='<locator>';`
  on a rehearsed throwaway first, then live, inside one transaction.
- If it was a probe/abandoned attempt: delete the reward rows as above. Answers
  cannot exist for it (no one ever joined), assert first:
  `SELECT COUNT(*) FROM answers WHERE org_id='<locator>'` must be 0.

### 2. Reward-only user

Should not occur (users are created at invite-accept, which writes identity first).
Treat as a bug: capture both stores' rows for the user_id, file the finding in
DECISIONS.md, do not delete until the write path is understood.

### 3. Identity-only rows

An org_register/users/invites row with no reward twin. If the reward half was
deliberately removed (probe cleanup), finish the job identity-side with the matching
delete — identity.py owns the store; use its helpers from a Python shell, never raw
SQL against identity.db from other modules (the module boundary is the split's law).

### 4. Token drift (invites/resets)

The digest names the row: find it by locator
(`SELECT * FROM invites WHERE org_id='<locator>'`), hash candidate tokens with
`hashlib.sha256(tok.encode()).hexdigest()[:12]` to confirm which row the digest
means. Usual cause: an expiry aged in one store only (the qa_backoffice L2 lesson —
fixtures must dual-write). Fix by copying the authoritative value across; the
reward-side row is authoritative for lifecycle fields (used_at), identity-side for
email.

## Conventions that keep this runbook short

- **Rehearse on a throwaway pair first** (SQLite backup API copies — never `cp`), the
  2×2 discipline: prove the fix changes exactly the orphan and nothing else.
- **Backup naming**: reward `lumi.db.bak_pre_<tag>_<YYYYMMDD_HHMMSS>`, identity
  `identity.db.bak_pre_<tag>_<ts>` — the classes and retention live in
  `data/backup_policy.md` (identity class retains 1, conditionally; reward class
  retains 3 with NAMED PINS EXCLUDED FROM THE ROTATION COUNT — the 2026-08-05
  incident is why that sentence is in bold). `server/backup_identity.py` enforces the
  identity-class convention (`BAK_RE`); any new backup-writing script must match it.
- **Never print a bearer.** Recon prints digests; so must any ad-hoc query you paste
  into a session or log (PH-PROV-1d).
