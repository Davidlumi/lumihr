#!/usr/bin/env bash
# lumi off-box backup (R1e, Gate 1) — the copy you actually restore DATA from.
# Runs on the deployed instance (cron/systemd-timer, daily). Copies the TWO
# DATABASES ONLY — never logs (PH-LOG-1 containment, A4), never the checkout.
#
# FAIL-CLOSED TRAP GUARD (R5 / backup_policy.md 2026-08-08 amendment): a
# versioned bucket retains deleted/overwritten objects as NONCURRENT versions
# unless noncurrent-version expiration is ALSO configured. Both rules —
# current-version expiry AND noncurrent-version expiry — must equal the 35-day
# ceiling, or this script would silently defeat ceiling-binds and falsify the
# member-facing retention disclosure. So the script ASSERTS both rules exist
# before every upload and refuses to copy if either is missing.
set -euo pipefail

BUCKET="${LUMI_BACKUP_BUCKET:?set LUMI_BACKUP_BUCKET}"          # e.g. lumi-backups-eu-west-2
DATA="${LUMI_DATA_DIR:-/srv/lumi/data}"
CEILING_DAYS=35
STAMP="$(date -u +%Y%m%d_%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
umask 077

# --- trap guard: both lifecycle rules present and equal to the ceiling ---------
LC="$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" 2>/dev/null || true)"
if [[ -z "$LC" ]]; then
  echo "FATAL: bucket $BUCKET has NO lifecycle configuration — refusing to upload." >&2
  exit 2
fi
echo "$LC" | python3 -c "
import json, sys
rules = json.load(sys.stdin).get('Rules', [])
cur = any(r.get('Status') == 'Enabled' and r.get('Expiration', {}).get('Days') == $CEILING_DAYS for r in rules)
non = any(r.get('Status') == 'Enabled' and r.get('NoncurrentVersionExpiration', {}).get('NoncurrentDays') == $CEILING_DAYS for r in rules)
if not (cur and non):
    sys.exit('FATAL: lifecycle must carry BOTH Expiration.Days=$CEILING_DAYS AND '
             'NoncurrentVersionExpiration.NoncurrentDays=$CEILING_DAYS (found: current=%s, noncurrent=%s) '
             '— a versioned bucket without noncurrent expiry defeats ceiling-binds. Refusing.' % (cur, non))
print('lifecycle guard: both rules present at $CEILING_DAYS days')
"

# --- consistent copies: checkpoint, then the SQLite backup API (never cp) ------
for db in lumi.db identity.db; do
  python3 - "$DATA/$db" "$WORK/$db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()
n = src.execute("SELECT (SELECT COUNT(*) FROM sqlite_master)").fetchone()[0]
src.close()
c = sqlite3.connect("file:%s?mode=ro" % sys.argv[2], uri=True)
assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity check failed"
c.close()
print("copied + integrity ok:", sys.argv[2])
PY
done

# --- upload: SSE, bucket must block public access (asserted) -------------------
PAB="$(aws s3api get-public-access-block --bucket "$BUCKET" --query 'PublicAccessBlockConfiguration' 2>/dev/null || true)"
echo "$PAB" | grep -q '"BlockPublicAcls": true' \
  || { echo "FATAL: bucket does not block public access — refusing." >&2; exit 2; }

for db in lumi.db identity.db; do
  aws s3 cp "$WORK/$db" "s3://$BUCKET/db/$db.$STAMP" --sse AES256 --only-show-errors
done
echo "off-box backup complete: s3://$BUCKET/db/{lumi,identity}.db.$STAMP (ceiling ${CEILING_DAYS}d, both expiry rules asserted)"
