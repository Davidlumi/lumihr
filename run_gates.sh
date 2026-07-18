#!/bin/zsh
# run_gates.sh — one-command shipped-state QA (2026-07-14).
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
mkdir -p "$WORK"
DB="$WORK/lumi_qa.db"
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
start_server() {  # $1 = db path ("" = real DB), $2 = log name
  kill_port
  local log="$WORK/$2.log"
  ( cd "$SRV" && LUMI_DB="${1}" ANTHROPIC_API_KEY='' LUMI_AI_LIVE='' \
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
  ( cd "$SRV" && env LUMI_DB="$DB" ANTHROPIC_API_KEY='' LUMI_AI_LIVE='' \
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
}
trap teardown EXIT

say "throwaway copy (SQLite backup API)"
python3 - "${LUMI_GATES_SRC:-$ROOT/lumi.db}" "$DB" <<'EOF'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
print("backup complete ->", sys.argv[2])
EOF
[[ -s "$DB" ]] || { print "FATAL: backup produced no file"; exit 2; }

# Re-aggregate the throwaway so stored payloads match its answers table exactly —
# answers submitted after the last live aggregate run (e.g. the Tester signup org
# testing the questionnaire) otherwise read as false engine drift in qa_engine_audit.
say "re-aggregate throwaway (answers -> payloads, staleness alignment)"
( cd "$SRV" && LUMI_DB="$DB" ANTHROPIC_API_KEY='' python3 aggregate.py ) >"$WORK/aggregate.out" 2>&1 \
  || { print "FATAL: aggregate failed — see $WORK/aggregate.out"; exit 2; }
tail -2 "$WORK/aggregate.out"

# --- HTTP suites (each on a fresh server: rate-limiter + stale-state hygiene) ---
start_server "$DB" srv_hero;    run_gate qa_hero; run_gate qa_focus
start_server "$DB" srv_signals; run_gate qa_signals_system; run_gate qa_strategy
start_server "$DB" srv_engine;  run_gate qa_engine_audit

# --- direct-DB suites (server can stay up; they read LUMI_DB directly) ---
run_gate qa_overview
run_gate qa_domain_summary
run_gate qa_commentary

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
