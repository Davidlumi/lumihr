#!/usr/bin/env bash
# lumi restore (R1e) — the other half of a backup: the rehearsed way to bring a
# database back from the off-box S3 copy. "A restore never performed is not a
# backup" (GO_LIVE_CHECKLIST Gate 1). Run this at least ONCE against a scratch
# instance before first provisioning (DEPLOY_RUNBOOK §6.2), and again for real if
# ever needed. Fail-closed: integrity-checks the pulled copy BEFORE it touches the
# live file, and refuses to run while the app is writing.
#
#   sudo systemctl stop lumi
#   LUMI_BACKUP_BUCKET=... LUMI_DATA_DIR=/srv/lumi/data ./restore.sh lumi.db latest
#   sudo systemctl start lumi
set -euo pipefail

BUCKET="${LUMI_BACKUP_BUCKET:?set LUMI_BACKUP_BUCKET}"
DATA="${LUMI_DATA_DIR:-/srv/lumi/data}"
DB="${1:-}"                 # lumi.db | identity.db
KEY="${2:-latest}"          # S3 object key under db/ (e.g. db/lumi.db.20260810_023000) or 'latest'

[[ "$DB" == "lumi.db" || "$DB" == "identity.db" ]] \
  || { echo "usage: restore.sh <lumi.db|identity.db> [<s3-key>|latest]" >&2; exit 2; }

# Never restore under a live writer — a half-written swap corrupts the store.
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet lumi; then
  echo "FATAL: lumi.service is active. Stop it first:  sudo systemctl stop lumi" >&2; exit 2
fi

if [[ "$KEY" == "latest" ]]; then
  KEY="$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "db/$DB." \
         --query 'sort_by(Contents,&LastModified)[-1].Key' --output text)"
  [[ -n "$KEY" && "$KEY" != "None" ]] || { echo "FATAL: no backups found under db/$DB. in s3://$BUCKET" >&2; exit 2; }
fi
echo "restoring $DB from s3://$BUCKET/$KEY"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT; umask 077
aws s3 cp "s3://$BUCKET/$KEY" "$WORK/$DB" --only-show-errors

# integrity-check the PULLED copy before going anywhere near the live file
python3 - "$WORK/$DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
c.close()
assert ok == "ok", "integrity check FAILED on the pulled copy (%s) — refusing to swap it in" % ok
print("pulled copy integrity: ok")
PY

STAMP="$(date -u +%Y%m%d_%H%M%S)"
if [[ -f "$DATA/$DB" ]]; then
  mv "$DATA/$DB" "$DATA/$DB.pre_restore_$STAMP"
  echo "kept the current live file as $DATA/$DB.pre_restore_$STAMP"
fi
rm -f "$DATA/$DB-wal" "$DATA/$DB-shm"    # stale WAL/SHM belonging to the replaced file
cp "$WORK/$DB" "$DATA/$DB"
chown lumi:lumi "$DATA/$DB" 2>/dev/null || true
echo "restored $DB → $DATA/$DB. Start the service:  sudo systemctl start lumi"
echo "if wrong, the previous file is at $DATA/$DB.pre_restore_$STAMP"
