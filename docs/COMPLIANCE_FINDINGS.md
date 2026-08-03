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
