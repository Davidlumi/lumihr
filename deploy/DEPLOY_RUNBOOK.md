# lumi deployment runbook (R1 family, 2026-08-08)

**Ruled shape:** EC2 (x86, Ubuntu LTS), eu-west-2, single instance. **Launched 2026-08-20 as `m7i-flex.large` (2 vCPU / 8 GB, Intel Xeon 8488C) — x86 chosen over ARM/t4g deliberately, for per-request speed at launch (David, 2026-08-20).** Caddy terminates
TLS for `app.lumihr.co.uk` (automatic ACME) and proxies to uvicorn on loopback.
**The DB at launch is SQLite on the instance's EBS volume — that is R1d, ruled.
Phase 2 attaches RDS to this same instance and becomes a connection-string change,
without re-platforming. That sentence is the whole reason EC2 won over Lightsail /
containers.** Marketing keeps the apex (`lumihr.co.uk`); only `app.` points here.

**Split of labour:** this runbook and the artefacts beside it are produced from the
repo; DAVID executes every AWS/DNS step against his own account. Nothing here
provisions infrastructure.

---

## 0. Security posture (stated, not implied)

- **Security group:** inbound 443 (TLS) and 80 (ACME challenge + redirect only) from
  anywhere; SSH (22) restricted to David's named source IP/CIDR; **nothing else**.
  No direct 8060 exposure ever — uvicorn binds 127.0.0.1 (enforced in the unit).
- **The app runs as `lumi`, non-root**, with systemd `ProtectSystem=strict`: write
  access ONLY to `/srv/lumi/data` and `/srv/lumi/logs`. Write does not imply delete;
  least-write is the doctrine.
- **Relaunch-from-committed-source discipline:** the service runs from
  `/srv/lumi/app`, a git checkout at a named commit. Deploys are
  `git fetch && git checkout <commit> && systemctl restart lumi` — no long-lived
  process ever runs uncommitted code, and the running commit is always
  `git -C /srv/lumi/app rev-parse HEAD`.
- **Logs (PH-LOG-1 containment, A4):** app output goes to journald with retention
  capped (`SystemMaxUse=200M`, `MaxRetentionSec=35day` in
  `/etc/systemd/journald.conf.d/lumi.conf` — the same 35-day R5 ceiling); journald
  files are root-readable only, outside every web-served path, and **excluded from
  the off-box backup** (deploy/offbox_backup.sh copies databases only, never logs).
  Auth links appear in app logs until D2 lands; **D2 (SES) is a HARD precondition of
  first provisioning** — see §6.

## 1. Instance

1. EC2: Ubuntu LTS x86 (m7i-flex class), eu-west-2. EBS gp3, encrypted-at-rest ON.
2. Tag it; enable termination protection.
3. `apt update && apt install -y python3-venv caddy` (Caddy from its apt repo).
4. Create user + tree:
   ```bash
   sudo adduser --system --group --home /srv/lumi lumi
   sudo -u lumi mkdir -p /srv/lumi/{app,data,logs,env}
   ```
5. Clone the repo at the release commit into `/srv/lumi/app`; venv into
   `/srv/lumi/venv`; `pip install -r requirements.txt` (the ROOT manifest — `server/requirements.txt` is a subset missing pydantic, httpx and anyio pins).
6. Copy the two live stores (SQLite backup API, never cp) into `/srv/lumi/data`;
   point the env at them (below). The stores live OUTSIDE the checkout.

## 2. Environment (`/srv/lumi/env/lumi.env`, mode 0600 root:lumi)

```
LUMI_BASE_URL=https://app.lumihr.co.uk
LUMI_DB=/srv/lumi/data/lumi.db
LUMI_IDENTITY_DB=/srv/lumi/data/identity.db
LUMI_AI_INSIGHTS_ENABLED=on     # R8 OVERRIDDEN by David, 2026-08-20 — see below
LUMI_AI_LIVE=on                 # the paid-API positive switch
ANTHROPIC_API_KEY=<rotated>     # rotate before go-live; any key seen in the tree is compromised
# deliberately ABSENT / off at launch:
#   LUMI_OPEN_REGISTRATION   (unset -> self-serve registration CLOSED)
#   LUMI_QA_SEAMS            (unset -> fault-injection seams inert)
# D2 (before first provisioning): LUMI_SMTP_* for SES SMTP.
```

## 3. Services

1. `deploy/lumi.service` → `/etc/systemd/system/lumi.service`; `systemctl enable --now lumi`.
2. `deploy/Caddyfile` → `/etc/caddy/Caddyfile`; `systemctl reload caddy`.
3. DNS: `app.lumihr.co.uk` A/AAAA → the instance's Elastic IP. Caddy obtains the
   certificate automatically on first request; renewal is Caddy's own loop — no
   cron to silently fail (why nginx+certbot was rejected).

## 4. Boot assertions — run after EVERY start, fail closed

```bash
set -e
J="journalctl -u lumi -b --no-pager"
$J | grep -q "LUMI_BASE_URL = https://app.lumihr.co.uk" \
  || { echo "FATAL: base URL wrong/unset — link minting would refuse or lie"; exit 1; }
# R8 OVERRIDE (David, 2026-08-20): AI ships ON. This assertion was the inverse — it
# required AI dark until provenance surfacing shipped. David ruled to launch with AI
# live, so it now asserts the opposite: that the surfaces are actually reaching the
# model, because the failure mode of this feature is silent (every generator falls back
# to a deterministic floor and returns 200 with plausible prose either way).
#
# THE PRECONDITION THIS REPLACES IS NOT DISCHARGED. Generated content derived from
# member data leaves the instance to reach a model, so the DPA, the privacy notice and
# the sub-processor review must be in place BEFORE the first real customer — not before
# the first deploy. That is a David action, tracked outside this file. If it is not done,
# set LUMI_AI_INSIGHTS_ENABLED=off (env only, no deploy) and take customers without AI.
$J | grep -q "AI INSIGHTS: ON" \
  || { echo "FATAL: AI master gate off — members would silently get composed floors"; exit 1; }
$J | grep -q "model: LIVE" \
  || { echo "FATAL: AI on but not live (key missing or LUMI_AI_LIVE unset) — silent floors"; exit 1; }
curl -s https://app.lumihr.co.uk/api/legal >/dev/null \
  || { echo "FATAL: edge not serving"; exit 1; }
curl -s -X POST https://app.lumihr.co.uk/api/auth/register \
     -H 'Content-Type: application/json' -d '{}' | grep -q "403\|hello@lumihr" \
  || { echo "FATAL: self-serve registration is NOT closed"; exit 1; }
ss -tlnp | grep ':8060' | grep -q '127.0.0.1' \
  || { echo "FATAL: uvicorn not loopback-only"; exit 1; }
echo "boot assertions: all green"
```
(The registration probe asserts the 403 posture; `LUMI_QA_SEAMS` has no boot line by
design — its absence is asserted by the env file review in step 2, which is the
point: it must never be set outside gate runs.)

## 5. Backups — see `data/backup_policy.md` §layers (Commit F + J)

Three layers, three purposes, never conflated: DLM EBS snapshots (machine restore),
on-box rotation (`backup_identity.py`, wal_checkpoint FIRST), off-box S3 copy
(`deploy/offbox_backup.sh` — the copy you actually restore data from; R1e, Gate 1).
Lifecycle **and** noncurrent-version expiry both = 35 days (R5). The script refuses
unless the bucket proves: eu-west-2 (asserted FROM the bucket), default encryption,
versioning Enabled, both lifecycle rules at 35d, public access blocked.

**IAM (Commit J): the uploader is PUT-ONLY.** Attach
`deploy/iam_backup_writer_policy.json` (substitute the real bucket name for
`LUMI_BACKUP_BUCKET`) to the instance role. Lifecycle expiry removes objects; the
instance never can — no DeleteObject / DeleteObjectVersion /
PutLifecycleConfiguration, with an explicit Deny statement so a broader role
attached later cannot quietly re-grant them. A compromised box must not be able to
delete its own off-box copies.

## 6. Hard preconditions of FIRST PROVISIONING (not of deployment)

0. **One-time signal_state rebaseline (P1-C-doc, 2026-08-08).** The database
   carries a ~11,247-event un-swept dev backlog (seed orgs, no recipients —
   nothing would mail, but production must not begin life replaying a dev
   backlog through its first sweep). Run once, before first provisioning:
   **The instruction that used to sit here did not work, and was measured failing
   on 2026-08-20.** It said: bump `composition_epoch` and run one sweep. But the
   sweep treats a MISSING `org_signal_epoch` row as the CURRENT epoch and stamps
   it lazily — deliberately, so a pre-P1F org is not rebaselined into eating
   genuinely pending changes. This database has **0 epoch rows** against 220 orgs
   carrying `signal_state`, so the bump is invisible and every org falls through
   to `diff_and_record`. Run against a copy of the live stores, the literal
   instruction wrote **14,238 notification events**. The corrected sequence wrote
   **0**.

   Every org must therefore be STAMPED with a prior epoch first, so the bump is
   something the sweep can actually see. Use the script, which does this and the
   rest of the first-provisioning cleanup in one pass, dry-run by default:

   ```bash
   python3 server/prepare_production_stores.py \
       --db /srv/lumi/data/lumi.db --identity-db /srv/lumi/data/identity.db
   # read the plan, then add:  --write --confirmed-by-david
   ```

   Then boot once and run a single sweep: it must report **0 events written**.
   If it reports anything else, STOP — the backlog is replaying into what will
   become real member notifications. NOTE: notification_events history (7,407 dev rows, seed orgs,
   never mailed) is the immutable event log and persists — archived history,
   not a served surface; it does not reach production members.

1. **D2 — SES email delivery live** (A4 ruling): domain verified, DKIM, sandbox
   exit, `LUMI_SMTP_*` set, a real invite delivered to a test mailbox. Until D2,
   invite links only exist in API responses and journald — and the journald copy is
   the contained PH-LOG-1 exposure, not a delivery path.
2. Off-box backup (R1e) restored ONCE in anger: prove a restore from S3 to a
   scratch instance before any member data exists worth losing.
3. The §4 STOP (HR Datahub / Tester / "tester 1" dispositions) executed, so the
   first member lands in a clean member namespace.

---

## Backup & restore operations (artefacts landed 2026-08-10)

**Automated off-box backup.** `offbox_backup.sh` is now scheduled — install the timer:

```
sudo cp deploy/lumi-backup.service deploy/lumi-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lumi-backup.timer
systemctl list-timers lumi-backup.timer      # confirm next run
```

The timer runs daily at 02:30 UTC (Persistent=true catches a missed run). Requires
`LUMI_BACKUP_BUCKET` in `/srv/lumi/env/lumi.env` and the instance role with the
PUT-only policy (`iam_backup_writer_policy.json`). The script is fail-closed: it
refuses to upload unless the bucket is eu-west-2 + SSE + versioned + both 35-day
lifecycle rules + public-access-blocked.

**Restore drill (§6.2 precondition — do this ONCE before first provisioning).**

```
sudo systemctl stop lumi
LUMI_BACKUP_BUCKET=<bucket> LUMI_DATA_DIR=/srv/lumi/data ./deploy/restore.sh lumi.db latest
LUMI_BACKUP_BUCKET=<bucket> LUMI_DATA_DIR=/srv/lumi/data ./deploy/restore.sh identity.db latest
sudo systemctl start lumi
curl -fsS http://127.0.0.1:8060/healthz          # expect {"status":"ok"}
```

`restore.sh` refuses to run while `lumi.service` is active, integrity-checks the
pulled copy before touching the live file, and keeps the replaced file as
`<db>.pre_restore_<ts>`. Rehearse on a scratch instance first; only then is
"off-box backup restored ONCE in anger" (Gate 1) satisfied.

**On-box pre-change snapshot** (fast local rollback before a migration; DB class,
retain-3): `python3 server/backup_lumi.py --tag pre_migration --write --confirmed-by-david`.

**Liveness.** `GET /healthz` (unauthenticated) returns `{"status":"ok"}` (200) when
both stores answer, else 503 — use it for the Caddy upstream check and uptime monitoring.

---

## Build notes from the first production build (2026-08-20)

Everything above was executed against the real instance. What follows is what the
runbook did not say, and cost time or would have cost correctness.

**The `model: LIVE` assertion in §4 is weaker than it reads.** The boot line is built
from `_key = bool(os.environ.get("ANTHROPIC_API_KEY"))`, so *any* non-empty string
satisfies it — the literal placeholder `REPLACE_ME` prints
`model: LIVE — paid Claude calls (key=present)`. The assertion proves a key is SET, not
that it WORKS, which is the same silent-fallback class the AI programme exists to fight.
Liveness must be proven with a real call. Add to §4:

```bash
# reads the key from the env file, makes one ~14-token call, prints no secret
sudo -u lumi /srv/lumi/venv/bin/python3 - <<'PY'
key = next(l.split("=",1)[1].strip() for l in open("/srv/lumi/env/lumi.env")
           if l.startswith("ANTHROPIC_API_KEY="))
import anthropic, sys
if not key or key == "REPLACE_ME": sys.exit("FATAL: no usable key")
r = anthropic.Anthropic(api_key=key).messages.create(
    model="claude-haiku-4-5-20251001", max_tokens=8,
    messages=[{"role":"user","content":"Reply with the single word: alive"}])
print("AI LIVE:", r.content[0].text.strip())
PY
```

The same applies to SMTP: `LUMI_SMTP_HOST` being set proves nothing. Authenticate against
the relay (EHLO → STARTTLS → LOGIN → QUIT, sending no message) before trusting that MFA
can deliver. With MFA mandatory, a bad SMTP credential locks everyone out, including you.

**`ubuntu` cannot traverse `/srv/lumi`** (0750 lumi:lumi). Remote `cd /srv/lumi/app`,
shell globs (`chmod 640 /srv/lumi/data/*.bak`) and anything else expanded by the login
shell fail with "Permission denied" or "No such file". Use `sudo` with explicit full
paths, and `git -C /srv/lumi/app` rather than `cd`.

**Never run `caddy validate` under sudo before the first start.** It creates
`/var/log/caddy/<site>.log` owned `root:root`, and caddy — running as `caddy` — then
refuses to start with "permission denied" on its own access log. Fix:
`chown caddy:caddy /var/log/caddy/<site>.log`.

**§6.0 outcome.** `prepare_production_stores.py --write` ran clean. It removes the
rehearsal ORG as well as its user (271 → 270 orgs), and every remaining org received an
epoch row — which is precisely the condition that makes the bump visible. Verified
against a COPY, with SMTP stripped from the environment so nothing could leave even on
failure: **0 events written**. The naive instruction this replaced wrote 14,238.

**The signal sweep is deliberately OFF at launch** (`LUMI_SIGNAL_SWEEP` unset), and this
is not an oversight. Four of the five accounts are `@thornbridge.example`; `.example` is
RFC 2606 reserved and can never receive mail, so every send hard-bounces. An 80% bounce
rate will get a new Postmark sender paused, which would take MFA delivery down with it.
Enable the sweep when the first real customer exists — or give the demo accounts
deliverable addresses first.

**Backups written by the prepare script land 0644.** They contain member data; chmod them
to 0640 (`lumi.db.pre-prod-prep.bak`, `identity.db.pre-prod-prep.bak`).
