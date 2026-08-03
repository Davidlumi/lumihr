#!/bin/zsh
# run_gates.sh — one-command shipped-state QA (2026-07-14; 12 gates since 2026-08-03 —
# qa_backoffice joined for the staff console; qa_plausibility freeze gate wired 07-14).
# Encodes the gate-run doctrine so it stops being tribal knowledge:
#   1. throwaway DB via the SQLite BACKUP API (never cp — WAL torn-copy)
#   2. :8060 taken over by a PROVABLY fresh server on the throwaway
#      (lsof first, log to file, assert zero "Address already in use", kill by PID)
#   3. all gates run with LUMI_DB=<throwaway> and ANTHROPIC_API_KEY='' (deterministic path)
#   4. server restarted before each HTTP suite (login rate-limiter 429s under load)
#   5. qa_pulse + qa_release run LAST (they exercise lifecycle/release state)
#   6. teardown ALWAYS relaunches the plain dev server on the real DB
# Usage: ./run_gates.sh [workdir]   (workdir defaults to a mktemp dir)
set -u
ROOT="${0:A:h}"
SRV="$ROOT/server"
WORK="${1:-$(mktemp -d /tmp/lumi_gates.XXXXXX)}"
# PH-LOG-1: server logs carry credential-bearing console emails (the SMTP-less
# delivery path, accepted until D2) — so (a) every file this suite writes (logs,
# gate .out, DB copies) lands 0600 via umask, and (b) a workdir inside the git
# tree is refused outright: outside-the-tree is the control, .gitignore is only
# defence in depth. Checked BEFORE anything is touched.
umask 077
case "${WORK:A}/" in
  "${ROOT:A}"/*)
    print "FATAL (PH-LOG-1): workdir '$WORK' resolves inside the git tree ($ROOT)."
    print "Gate logs carry invite/reset links; they must never live in the repo."
    exit 2;;
esac
mkdir -p "$WORK"
DB="$WORK/lumi_qa.db"
IDB="$WORK/identity_qa.db"
PORT=8060
PASS=(); FAIL=()

say() { print -- "\n=== $1 ==="; }

kill_port() {
  local pids; pids=$(lsof -t -iTCP:$PORT -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    print "killing :$PORT listeners: $pids"
    echo "$pids" | xargs kill 2>/dev/null
    for i in {1..20}; do
      lsof -t -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1 || return 0
      sleep 0.25
    done
    echo "$pids" | xargs kill -9 2>/dev/null; sleep 0.5
  fi
}

SERVER_PID=""
start_server() {  # $1 = db path ("" = real DB), $2 = log name, $3 = extra env (optional)
  kill_port
  local log="$WORK/$2.log"
  # PH-PROV-1: self-serve registration is CLOSED by default. Gate servers whose
  # suites self-register probe orgs (qa_strategy) pass LUMI_OPEN_REGISTRATION=on;
  # srv_backoffice runs with the production default so the 403 is verifiable.
  ( cd "$SRV" && env LUMI_DB="${1}" LUMI_IDENTITY_DB="$IDB" ANTHROPIC_API_KEY='' LUMI_AI_LIVE='' ${=3:-} \
      nohup python3 -m uvicorn app:app --port $PORT >"$log" 2>&1 & print $! ) | read SERVER_PID
  for i in {1..40}; do
    curl -s -o /dev/null "http://localhost:$PORT/api/legal" && break
    sleep 0.5
  done
  if grep -q "Address already in use" "$log"; then
    print "FATAL: port collision — see $log"; exit 2
  fi
  print "server up on :$PORT pid=$SERVER_PID db=${1:-REAL} log=$log"
}

run_gate() {  # $1 = script name (in server/), rest = extra env assignments
  local g="$1"
  say "$g"
  ( cd "$SRV" && env LUMI_DB="$DB" LUMI_IDENTITY_DB="$IDB" ANTHROPIC_API_KEY='' LUMI_AI_LIVE='' \
      python3 "$g.py" ) >"$WORK/$g.out" 2>&1
  local rc=$?
  tail -4 "$WORK/$g.out"
  if [[ $rc -eq 0 ]]; then PASS+=("$g"); else FAIL+=("$g (rc=$rc, see $WORK/$g.out)"); fi
}

teardown() {
  say "teardown — restoring dev server on the REAL DB"
  kill_port
  ( cd "$SRV" && nohup python3 -m uvicorn app:app --port $PORT >"$WORK/devserver_restored.log" 2>&1 & print $! ) | read DEVPID
  for i in {1..40}; do curl -s -o /dev/null "http://localhost:$PORT/api/legal" && break; sleep 0.5; done
  print "dev server restored pid=$DEVPID (real lumi.db)"
  # gate-safety-2: assert the suite left the REAL db untouched (volatile server-log tables allowed).
  if [[ -f "$WORK/live_pre.json" ]]; then
    if python3 "$SRV/dbsnapshot.py" check "$WORK/live_pre.json" --db "$ROOT/lumi.db" --allow-volatile >/dev/null 2>&1; then
      print "gate-safety-2: live DB untouched by the suite ✓"
    else
      print "⚠️  gate-safety-2: the SUITE CHANGED THE LIVE DB —"
      python3 "$SRV/dbsnapshot.py" check "$WORK/live_pre.json" --db "$ROOT/lumi.db" --allow-volatile
    fi
  fi
  # D8/backup-policy creation-time doctrine: the identity throwaway is pure PII —
  # delete it at teardown, success or failure. Logs stay (verbatim-tally convention).
  rm -f "$IDB" "$IDB-shm" "$IDB-wal" 2>/dev/null
  if [[ -e "$IDB" ]]; then print "⚠️  identity throwaway NOT deleted: $IDB"
  else print "identity throwaway deleted (logs kept in $WORK)"; fi
}
trap teardown EXIT
trap 'exit 130' INT TERM

say "stopping :$PORT so the two-store copy is one instant (D8)"
kill_port
say "throwaway copies (SQLite backup API, both stores, one instant)"
python3 - "${LUMI_GATES_SRC:-$ROOT/lumi.db}" "$DB" "${LUMI_GATES_IDENTITY_SRC:-$ROOT/identity.db}" "$IDB" <<'EOF'
import sqlite3, sys
for src_p, dst_p in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    src = sqlite3.connect(src_p)
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # D8: checkpoint each store before copy (no-op on non-WAL)
    dst = sqlite3.connect(dst_p)
    src.backup(dst); dst.close(); src.close()
    print("backup complete ->", dst_p)
EOF
[[ -s "$DB" ]] || { print "FATAL: backup produced no file"; exit 2; }
[[ -s "$IDB" ]] || { print "FATAL: identity backup produced no file"; exit 2; }

# gate-safety-2: fingerprint the REAL lumi.db (all 41 tables, count+content) so teardown can prove
# the suite — which runs entirely on the throwaway $DB — left live byte-identical.
python3 "$SRV/dbsnapshot.py" save "$WORK/live_pre.json" --db "$ROOT/lumi.db" >/dev/null 2>&1 \
  && print "gate-safety-2: live fingerprint captured (41 tables)" \
  || print "gate-safety-2: fingerprint skipped (dbsnapshot unavailable)"

# Re-aggregate the throwaway so stored payloads match its answers table exactly —
# answers submitted after the last live aggregate run (e.g. the Tester signup org
# testing the questionnaire) otherwise read as false engine drift in qa_engine_audit.
say "re-aggregate throwaway (answers -> payloads, staleness alignment)"
( cd "$SRV" && LUMI_DB="$DB" LUMI_IDENTITY_DB="$IDB" ANTHROPIC_API_KEY='' python3 aggregate.py ) >"$WORK/aggregate.out" 2>&1 \
  || { print "FATAL: aggregate failed — see $WORK/aggregate.out"; exit 2; }
tail -2 "$WORK/aggregate.out"

# --- HTTP suites (each on a fresh server: rate-limiter + stale-state hygiene) ---
start_server "$DB" srv_hero;    run_gate qa_hero; run_gate qa_focus
start_server "$DB" srv_signals "LUMI_OPEN_REGISTRATION=on"; run_gate qa_signals_system; run_gate qa_strategy
start_server "$DB" srv_engine;  run_gate qa_engine_audit

# --- direct-DB suites (server can stay up; they read LUMI_DB directly) ---
run_gate qa_overview
run_gate qa_domain_summary
run_gate qa_commentary

# --- freeze gate (Diff 12): qa_plausibility Check C, ENFORCING. Root-dir script
#     (not server/); honours LUMI_DB so it validates the suite's throwaway, not live.
say "qa_plausibility"
( cd "$ROOT" && env LUMI_DB="$DB" LUMI_IDENTITY_DB="$IDB" ANTHROPIC_API_KEY='' python3 qa_plausibility.py ) >"$WORK/qa_plausibility.out" 2>&1
PLAUS_RC=$?
tail -4 "$WORK/qa_plausibility.out"
if [[ $PLAUS_RC -eq 0 ]]; then PASS+=(qa_plausibility); else FAIL+=("qa_plausibility (rc=$PLAUS_RC, see $WORK/qa_plausibility.out)"); fi

# --- back office (2026-08-03): mutates console state (probe org/users, soft-
#     deactivate cycles) — own fresh server, and BEFORE the LAST-by-doctrine pair
#     so lifecycle/release gates still see their expected world. Probe orgs carry
#     no answers, so engine/pool gates upstream are unaffected either way.
#     PRODUCTION posture deliberately (no LUMI_QA_SEAMS, registration closed):
#     the gate proves the seam inert by default on THIS server, and spawns its
#     own short-lived :8061 server WITH seams for the fault-injection checks.
start_server "$DB" srv_backoffice; run_gate qa_backoffice

# --- LAST by doctrine ---
run_gate qa_pulse
run_gate qa_release

say "SUMMARY"
print "PASS (${#PASS[@]}): ${(j:, :)PASS}"
if (( ${#FAIL[@]} )); then
  print "FAIL (${#FAIL[@]}):"; for f in "${FAIL[@]}"; do print "  - $f"; done
  exit 1
fi
print "ALL GATES GREEN — throwaway + logs in $WORK"
