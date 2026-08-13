# Launch dress rehearsal — 2026-08-13

Full fresh-org journey executed on a prod-like throwaway rig (MFA enforced, link minting on,
backup-API copies of both stores), plus static audits of the email transport and the production
env posture. **Verdict: the product path is GO; four David-actions gate the ops path.**

## 1 · The fresh-customer journey — PASSED end-to-end

| Step | Result |
|---|---|
| Staff provisioning (`POST /api/admin/orgs`) | ✅ org + founding-admin invite in one transaction; firmographics validated; invite link minted via LUMI_BASE_URL |
| Invite page (logged out) | ✅ pre-filled locked email, password policy, platform-terms tick, AI disclosure |
| Accept invite | ✅ account + session created (link = trust anchor; MFA correctly reserved for logins) |
| First-run funnel | ✅ 4-step WelcomeHero: profile ✓ → data terms → 77 key questions (~50 min) → invite team; "your 30 days only start once your Admin accepts the data terms" |
| Data terms | ✅ accepted; clock started only then |
| **MFA login** | ✅ password → challenge → emailed code → verify → session (code read from the no-SMTP console fallback) |
| Data entry | ✅ 77 key questions drafted through the UI's own endpoints; zero validation errors; core 90.9% |
| **Submit** | ✅ 118 answer rows; full pool re-aggregate in **1.2 s**; `benchmark_unlocked: true` |
| Post-unlock | ✅ live donut, domain positions, 10 signals, Confidence 10/10 · 221 peers (org joined the pool), board-pack + share live, strategy + default-peer-group prompts queued |

One copy nit found (not fixed — needs a one-line ruling): the invite page tells the **founding
admin** "Your Admin accepts the Data Contribution Terms — nothing is needed from you", but this
invitee IS that admin and the terms gate greets them on arrival. Suggest role-aware copy:
admins see "As the Admin, you'll review the Data Contribution Terms after joining."

## 2 · Hardening shipped from rehearsal findings (this commit)

- **MFA/resend sends are honest and off the event loop** — a failed send now returns 503
  ("couldn't send your code") instead of stranding the user at a code screen with a 200 and a
  dead challenge; a hung relay no longer freezes every other request.
- **Bearer leak closed at the choke point** — a production SMTP outage used to print live reset
  links and MFA codes into the server log; the failure path now withholds bodies (log.error,
  alertable), while the dev no-SMTP console path still prints codes for QA.
- **Verified STARTTLS** — Python 3.9 smtplib doesn't verify the relay cert by default; it does now.
- **Digest truth** — a failed digest no longer stamps `emailed_at` (events retried next sweep).
- **Boot refusals extended** — `LUMI_QA_SEAMS` (fault-injection) and `LUMI_OPEN_REGISTRATION`
  now refuse to boot in production posture (negative-tested).
- Reset + member-invite sends threaded (reset keeps its generic 200 — no account oracle).

## 3 · David-actions before go-live (the ops gate)

1. **SES/SMTP** — create the SES domain identity (DKIM/SPF for lumihr.co.uk), get out of
   sandbox, set the SMTP env block (in `deploy` runbook + the agent runbook below). Boot
   refuses MFA-without-SMTP, so this physically gates launch. Then run the 8-step
   day-one email test (reset → MFA → invite → digest → ops mail → deliverability headers).
2. **Restore drill from S3** — never performed; your own GO_LIVE_CHECKLIST Gate 1 says not done
   until one real restore lands on a scratch instance. Known weakness to watch: `restore.sh`
   resolves the two stores independently by LastModified — verify both restored files carry the
   SAME backup date (torn-pair risk; candidate script fix if you want it).
3. **Rotate the ANTHROPIC_API_KEY** that has lived in `server/.env.local` (DECISIONS 2026-08-10
   already rules it compromised) and confirm `.env.local` never deploys.
4. **Env file** — paste the runbook block (agents' full versions in
   `tasks/w4vua2blp.output`); prove the absent-list clean:
   `grep -E 'SEED_DEMO|QA_SEAMS|OPEN_REGISTRATION|ALLOW_NO_MFA|EXIT_DELETION|ALLOW_LIVE|WEB_CONCURRENCY' lumi.env`
   must return nothing. Engine tunables stay unset (code defaults are the ratified values).

## 4 · Accepted-as-is (conscious, documented)

- Invite-accept mints a session without MFA (possession of the link is the factor; industry standard).
- Single worker is pinned in `deploy/lumi.service`; the WEB_CONCURRENCY warning can't see
  `uvicorn --workers` — the systemd unit is the control.
- No-SMTP dev fallback prints OTP codes to stdout — required for QA; unreachable in prod
  posture (boot guard).
