# -*- coding: utf-8 -*-
"""PULSE GATE (standing, 2026-06-12) — hard separation + lifecycle + engine
parity for the Tier-2 pulse surface. Self-cleaning fixtures; exit != 0 on
failure. DB-level (no HTTP needed) so it runs anywhere the DB lives.

THE INVARIANTS THIS GATE PROTECTS:
1. HARD SEPARATION: a pulse response never pools into a core aggregate and
   vice versa — even for the same org answering the same question.
2. ONE ENGINE: pulse aggregation == the core engine path (same n>=5 floor,
   same calculation, matrix + multi-select included).
3. Lifecycle: draft invisible / open accepts / closed read-only / archived
   keeps its report; no reopen.
4. Give-to-get independence: pulse participation never moves core unlock.
5. Graduation carries the DEFINITION only — zero responses copied.
6. Archived reports stay as-asked after later core rewords.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from db import get_conn, uj
import pulses
import app as appmod

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append((name, detail))


def ref_pctl(vals, p):
    v = sorted(vals)
    k = (len(v) - 1) * p / 100.0
    f, c = int(math.floor(k)), int(math.ceil(k))
    return float(v[f]) if f == c else float(v[f] * (c - k) + v[c] * (k - f))


conn = get_conn()
QID = "PROP_9e4ad87f"   # a core numeric that also appears in pulse fixtures

core_before = json.loads(conn.execute(
    "SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (QID,)).fetchone()[0])
orgs = [r["org_id"] for r in conn.execute(
    "SELECT org_id FROM orgs WHERE source='seed' AND classified=1 ORDER BY org_id DESC LIMIT 6")]
demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]
unlock_before = conn.execute("SELECT insights_unlocked_at FROM orgs WHERE org_id=?", (demo,)).fetchone()[0]

print("== fixture pulse: lifecycle + engine parity ==")
pid = pulses.create_pulse("qa-pulse-fixture", "gate fixture",
                          question_ids=[QID, "ALLOW_01", "REW_BEN_112"], conn=conn)
p = pulses.get_pulse(pid, conn)
check("draft pulse exists with status draft", p["status"] == "draft")
try:
    pulses.join_pulse(pid, orgs[0], conn)
    check("draft refuses joins", False)
except ValueError:
    check("draft refuses joins", True)

pulses.open_pulse(pid, conn)
check("open snapshots its questions as-asked",
      QID in uj(pulses.get_pulse(pid, conn)["question_snapshot_json"], {}))

# 4 participants -> below floor; engine must serve NOTHING
for i, oid in enumerate(orgs[:4]):
    pulses.join_pulse(pid, oid, conn)
    pulses.save_response(pid, oid, QID, "", str(100 + i), conn)          # absurd sentinel values
    pulses.save_response(pid, oid, "ALLOW_01", "", "Car allowance; Meal allowance", conn)
    pulses.save_response(pid, oid, "REW_BEN_112", "board_executive", str(20 + i), conn)
    pulses.submit_pulse(pid, oid, conn)
rep4 = pulses.pulse_report(pid, conn)
check("4 participants -> below_floor flagged", rep4["below_floor"] and rep4["participants"] == 4)
served = [q for q in rep4["questions"] if q["block"] and not q["block"].get("suppressed")
          and any(k in q["block"] for k in ("p50", "options"))]
check("4 participants -> every question suppressed (no values anywhere)", not served,
      [q["question_id"] for q in served])

# 5th participant -> exactly at floor, serves; engine parity vs fresh recompute
pulses.join_pulse(pid, orgs[4], conn)
pulses.save_response(pid, orgs[4], QID, "", "104", conn)
pulses.save_response(pid, orgs[4], "ALLOW_01", "", "Shift allowance", conn)
pulses.save_response(pid, orgs[4], "REW_BEN_112", "board_executive", "24", conn)
pulses.submit_pulse(pid, orgs[4], conn)
rep5 = pulses.pulse_report(pid, conn)
num = next(q for q in rep5["questions"] if q["question_id"] == QID)
check("exactly 5 -> numeric serves", num["block"].get("n") == 5)
check("pulse numeric p50 == independent recompute",
      abs(num["block"]["p50"] - ref_pctl([100, 101, 102, 103, 104], 50)) < 1e-9,
      (num["block"]["p50"], ref_pctl([100, 101, 102, 103, 104], 50)))
multi = next(q for q in rep5["questions"] if q["question_id"] == "ALLOW_01")
car = next((o for o in (multi["block"].get("options") or []) if o["label"] == "Car allowance"), None)
check("pulse multi-select splits (Car 4/5 = 80%)", car and car["count"] == 4 and abs(car["pct"] - 80.0) < 0.1,
      car)
mat = next(q for q in rep5["questions"] if q["question_id"] == "REW_BEN_112")
row = next((r for r in (mat.get("matrix_rows") or []) if r["row_id"] == "board_executive"), None)
check("pulse matrix row aggregates (n=5, p50=22)",
      row and row["block"].get("n") == 5 and abs(row["block"]["p50"] - 22.0) < 1e-9,
      row and row["block"])

print("== HARD SEPARATION (the cardinal rule) ==")
core_after = json.loads(conn.execute(
    "SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (QID,)).fetchone()[0])
check("core payload byte-identical despite absurd pulse sentinels (100-104)",
      json.dumps(core_after, sort_keys=True) == json.dumps(core_before, sort_keys=True))
in_answers = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND TRIM(value) IN ('100','101','102','103','104')",
                          (QID,)).fetchone()[0]
check("no pulse sentinel value present in the core answers store", in_answers == 0, in_answers)
# reverse direction: the pulse aggregate is cohort-only, never the core pool
check("pulse n is the cohort (5), never the core pool (%s)" % core_before["all"].get("n"),
      num["block"]["n"] == 5)
# re-run the CORE aggregation with pulse data present — output must not move
from aggregate import run_snapshot
run_snapshot(1, verbose=False)
core_rerun = json.loads(get_conn().execute(
    "SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (QID,)).fetchone()[0])
check("full core re-aggregation ignores pulse_responses structurally",
      json.dumps(core_rerun, sort_keys=True) == json.dumps(core_before, sort_keys=True))

print("== give-to-get independence ==")
unlock_after = conn.execute("SELECT insights_unlocked_at FROM orgs WHERE org_id=?", (demo,)).fetchone()[0]
check("core unlock stamp untouched by pulse activity", unlock_after == unlock_before)
basis = len(appmod.completion_basis_questions())
check("core unlock denominator unchanged (82)", basis == 82, basis)
# a core-locked org can still participate (no core gate on the pulse path)
conn.execute("INSERT OR REPLACE INTO orgs(org_id, name, normalized_name, source, classified, submission_complete, tier_entitlement) "
             "VALUES ('qa-pulse-locked','QA Locked','qapulselocked','signup',0,0,'full')")
conn.commit()
try:
    pulses.join_pulse(pid, "qa-pulse-locked", conn)
    pulses.save_response(pid, "qa-pulse-locked", QID, "", "102.5", conn)
    pulses.submit_pulse(pid, "qa-pulse-locked", conn)
    check("a core-LOCKED org joins, answers and participates in a pulse", True)
except ValueError as e:
    check("a core-LOCKED org joins, answers and participates in a pulse", False, e)

print("== lifecycle: closed read-only, archived keeps report, no reopen ==")
pulses.close_pulse(pid, conn)
try:
    pulses.save_response(pid, orgs[0], QID, "", "999", conn)
    check("closed pulse refuses responses", False)
except ValueError:
    check("closed pulse refuses responses", True)
try:
    pulses.extend_close(pid, "2099-01-01", conn)
    check("closed pulse refuses window extension (no reopen in v1)", False)
except ValueError:
    check("closed pulse refuses window extension (no reopen in v1)", True)
pulses.archive_pulse(pid, conn)
rep_arch = pulses.pulse_report(pid, conn)
check("archived pulse still reports (final)", rep_arch["participants"] == 6 and
      next(q for q in rep_arch["questions"] if q["question_id"] == QID)["block"]["n"] == 6)

print("== as-asked reproducibility after a core reword ==")
orig_text = conn.execute("SELECT text FROM questions WHERE id=?", (QID,)).fetchone()[0]
conn.execute("UPDATE questions SET text='REWORDED FIXTURE TEXT' WHERE id=?", (QID,))
conn.commit()
appmod.load_questions.cache_clear()
qs_asked = pulses.pulse_questions(pulses.get_pulse(pid, conn))
check("archived pulse renders the question AS-ASKED, not the reworded core text",
      qs_asked[QID].text == orig_text, qs_asked[QID].text[:40])
conn.execute("UPDATE questions SET text=? WHERE id=?", (orig_text, QID))
conn.commit()
appmod.load_questions.cache_clear()

print("== graduation: definition only, zero responses ==")
gqid = "PULSE_QA_GRAD_FIXTURE"
conn.execute("DELETE FROM questions WHERE id=?", (gqid,))
conn.commit()
pid2 = pulses.create_pulse("qa-grad-fixture", "x", question_ids=[], new_questions=[{
    "id": gqid, "title": "Grad fixture", "text": "Grad fixture?",
    "type": "yes_no", "polarity": "neutral",
    "options": [{"code": "YES", "label": "Yes", "order": 1, "is_na": False},
                {"code": "NO", "label": "No", "order": 2, "is_na": False}]}], conn=conn)
pulses.open_pulse(pid2, conn)
pulses.join_pulse(pid2, orgs[0], conn)
pulses.save_response(pid2, orgs[0], gqid, "", "Yes", conn)
pulses.submit_pulse(pid2, orgs[0], conn)
check("pulse-origin question invisible to the core scope",
      gqid not in appmod.visible_questions())
n_core = pulses.graduate_question(gqid, "Governance", conn=conn)
check("graduated question enters the live core with ZERO core responses",
      gqid in appmod.visible_questions() and n_core == 0)
check("the pulse's responses were NOT copied into the core store",
      conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (gqid,)).fetchone()[0] == 0)
check("pulse responses retained in their own store",
      conn.execute("SELECT COUNT(*) FROM pulse_responses WHERE question_id=?", (gqid,)).fetchone()[0] == 1)

# ------------------------------------------------------------- CLEANUP -----
print("== fixture cleanup ==")
for fpid in (pid, pid2):
    conn.execute("DELETE FROM pulse_responses WHERE pulse_id=?", (fpid,))
    conn.execute("DELETE FROM pulse_participants WHERE pulse_id=?", (fpid,))
    conn.execute("DELETE FROM pulses WHERE pulse_id=?", (fpid,))
conn.execute("DELETE FROM questions WHERE id=?", (gqid,))
conn.execute("DELETE FROM orgs WHERE org_id='qa-pulse-locked'")
conn.commit()
appmod.load_questions.cache_clear()
left = conn.execute("SELECT COUNT(*) FROM pulses WHERE name LIKE 'qa-%'").fetchone()[0]
check("fixtures removed", left == 0, left)

print("\nNOTE: this gate clears the app's question cache in ITS process only —")
print("restart the app after running it (same convention as qa_release).")
print("\nRESULTS: %d failures" % len(FAILS))
for n, d in FAILS:
    print("  FAIL:", n, d)
sys.exit(1 if FAILS else 0)
