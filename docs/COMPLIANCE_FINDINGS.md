# Compliance findings register

First created 2026-08-03 (PH-LOG-1). **Needs reconciling with the governance pack
(DPIA / RoPA / LIA / controller determination) when that work happens** — this file
predates it and must fold in, not fork from it.

Each entry mirrors its DECISIONS.md close condition EXACTLY — the two must not drift.

---

## CF-1 — Credentials in application logs (invite/reset links)

- **Date raised:** 2026-08-03 (PH-PROV-1d census; contained under PH-LOG-1 same day)
- **Description:** `send_notification` writes full invite and password-reset links to the
  server log — the designed SMTP-less email delivery path. Each link is a bearer
  credential; provisioning invites carry `role='admin'`.
- **Affected component:** `server/app.py` `send_notification` (console-logged email);
  any server log capturing stdout.
- **Severity as assessed:** Medium today (all logged links belong to gate-manufactured
  throwaway orgs; logs 0600 in 0700 dirs outside the git tree, /tmp-resident, never
  committed — history verified clean). **High the moment a real founding member is
  provisioned** while SMTP remains unconfigured.
- **Compensating controls:** logs outside the working tree (run_gates refuses an in-tree
  workdir); umask 077 → files 0600, dirs 0700; .gitignore `*.log`/`*.out` as defence in
  depth; git history verified free of logs and link patterns; no Dropbox/iCloud/cron
  coverage of log paths; Time Machine covers the project tree but not /tmp (built-in
  exclusion — GUI confirmation pending, see DECISIONS PH-LOG-1).
- **Close condition:** This exposure is live until real email delivery (D2) lands and
  send_notification no longer writes link bodies to any log; it is reviewed at that point
  and not before.
- **Owner:** David Whitfield (delivery decision is D2; interim controls maintained by the
  gate suite — run_gates.sh enforces both).

---

## CF-2 — Unmanaged database copies outside the governed backup set

- **Date raised:** 2026-08-03 (PH-BAK-1 census, arising from PH-LOG-1's passing finding)
- **Description:** Gate-suite and session tooling created full-database throwaway copies
  outside the ruled backup policy's scope: three pre-split reward copies holding the
  complete identity dataset (223 org names, 8 emails, 8 bcrypt pw_hash each) survived four
  days in /tmp; session scratchpads held identity-store copies. The governed in-tree
  `.bak` ritual was compliant throughout; the policy's scratch-copy carve-out was the gap.
- **Affected component:** `run_gates.sh` teardown (asymmetric deletion, now fixed);
  session rehearsal tooling; `data/backup_policy.md` scope (amended, dated correction).
- **Severity as assessed:** Low as measured (16 distinct addresses — 13 demo/probe, 3
  real-domain; 11 bcrypt cost-12 hashes; git history proven clean at every scope). High
  if unchanged at member scale — fixed during soak precisely because it is cheap now.
- **Compensating controls:** teardown deletes BOTH throwaways on the EXIT-trap path and
  asserts a zero count of surviving copies; `server/purge_throwaway_copies.py` (dry-run
  default, double-guarded, structurally unable to touch Group A) sweeps ad-hoc copies;
  generic `*.db`/`*.sqlite*` gitignore as defence in depth; Group A bounded by rotation
  depth 3 + the named pin's release trigger; 90-day maximum retention ceiling recorded.
- **Close condition:** Closed when (a) the Groups B/C purge has run with zero database
  copies surviving in scope, (b) a full suite run shows the teardown zero-survivors
  assertion green, and (c) David confirms in the Time Machine GUI whether /private/tmp is
  excluded from backups; the Group A position remains accepted-bounded under
  data/backup_policy.md and is not part of this finding.
- **Owner:** David Whitfield (TM GUI confirmation); gate suite enforces the teardown
  assertion from here.
