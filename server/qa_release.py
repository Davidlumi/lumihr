# -*- coding: utf-8 -*-
"""VERSIONING / GOVERNANCE GATE (standing, 2026-06-12).

Exercises the full release lifecycle against the live DB with SELF-CLEANING
fixtures: baseline integrity, release cut + diff changelog, exact prior-set
reconstruction, retire-not-delete, required-set shrink, comparability-break
trend splitting, STICKY unlock across a required-adding release, the
emergency lane's refusal gate, and backlog non-application. Restores every
fixture before exiting. Run with the app DB present; no HTTP needed.
Exit code != 0 on any failure.
"""
import json
import os
import sys
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from db import get_conn
import releases as rel
import app as appmod

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append((name, detail))


conn = get_conn()
TEST_REL = "qa-release-fixture"

# pre-state
pre_core = conn.execute("SELECT COUNT(*) FROM questions WHERE superpower='Reward' AND status!='retired'").fetchone()[0]
pre_req = conn.execute("SELECT COUNT(*) FROM questions WHERE superpower='Reward' AND status!='retired' AND is_required=1").fetchone()[0]
pre_changelog = conn.execute("SELECT COUNT(*) FROM core_changelog").fetchone()[0]
pre_backlog = conn.execute("SELECT COUNT(*) FROM core_backlog").fetchone()[0]

print("== baseline integrity ==")
base = conn.execute("SELECT * FROM core_releases WHERE release_id=?", (rel.BASELINE_ID,)).fetchone()
check("baseline release exists and reconstructs", base is not None)
base_set = rel.question_set(rel.BASELINE_ID, conn)
check("baseline question set reconstructs at full size", len(base_set) >= 180, len(base_set))
stamped = conn.execute("SELECT COUNT(*) FROM questions q JOIN release_questions r ON r.question_id=q.id "
                       "AND r.release_id=? WHERE q.question_version IS NULL OR q.release_entered IS NULL",
                       (rel.BASELINE_ID,)).fetchone()[0]
check("every core question carries version + release_entered", stamped == 0, stamped)
check("data periods carry the release they were aggregated under",
      conn.execute("SELECT COUNT(*) FROM snapshots WHERE release_id IS NULL").fetchone()[0] == 0)

print("== module invariant (2026.1) ==")
bad_mod = conn.execute("SELECT COUNT(*) FROM questions WHERE module IS NOT NULL AND is_required=1").fetchone()[0]
check("sector-module questions are never required (gate stays org-independent)", bad_mod == 0, bad_mod)

print("== fixture release: add required + retire + break ==")
prev_current = rel.current_release(conn)["release_id"]
flip = [r[0] for r in conn.execute("SELECT id FROM questions WHERE superpower='Reward' AND is_required=0 "
                                   "AND status!='retired' ORDER BY question_order LIMIT 3")]
conn.executemany("UPDATE questions SET is_required=1, question_version=question_version||'+qafix' WHERE id=?",
                 [(q,) for q in flip])
RETIRE = conn.execute("SELECT id FROM questions WHERE superpower='Reward' AND is_required=1 AND status!='retired' "
                      "AND id NOT IN (%s) ORDER BY question_order LIMIT 1" % ",".join("?" * len(flip)), flip).fetchone()[0]
rel.retire_question(RETIRE, conn=conn)
rel.mark_comparability_break(flip[0], TEST_REL, conn)
conn.commit()
changes = rel.create_release(TEST_REL, "qa fixture", "qa-gate", conn)
types = sorted({c[0] for c in changes})
check("release diff logs reworded + retired", "retired" in types and "reworded" in types, types)
check("retired question recorded with the release it left",
      conn.execute("SELECT release_retired FROM questions WHERE id=?", (RETIRE,)).fetchone()[0] == TEST_REL)
check("retired question NOT deleted",
      conn.execute("SELECT COUNT(*) FROM questions WHERE id=?", (RETIRE,)).fetchone()[0] == 1)
check("retired question still in the baseline snapshot", RETIRE in base_set)
check("historical payload still resolves for the retired question",
      conn.execute("SELECT COUNT(*) FROM benchmark_snapshots WHERE question_id=?", (RETIRE,)).fetchone()[0] > 0)
check("prior release reconstruction unchanged by the new release",
      len(rel.question_set(rel.BASELINE_ID, conn)) == len(base_set))

print("== live experience: retire excluded, required shrinks-and-grows correctly ==")
appmod.load_questions.cache_clear()
vis = appmod.visible_questions()
check("retired question gone from the live core", RETIRE not in vis)
new_req = len(appmod.completion_basis_questions())
check("required set = pre %d - 1 retired + 3 added" % pre_req, new_req == pre_req - 1 + 3, new_req)

print("== sticky unlock across the required-adding release ==")
conn.execute("""INSERT OR REPLACE INTO orgs(org_id, name, normalized_name, source, classified,
                submission_complete, insights_unlocked_at, unlocked_release, tier_entitlement)
                VALUES ('qa-sticky-org','QA Sticky','qasticky','signup',0,0,datetime('now'),?, 'full')""",
             (prev_current,))
conn.commit()
fx = conn.execute("SELECT * FROM orgs WHERE org_id='qa-sticky-org'").fetchone()
comp = appmod.completion_pct(conn, dict(fx))
check("stamped org at %.0f%% completion STAYS unlocked after the release" % comp,
      appmod.org_unlocked(conn, fx) is True and comp < appmod.TARGET_PCT, comp)

print("== comparability break enforced in the trend layer ==")
conn.execute("INSERT OR REPLACE INTO snapshots(snapshot_id, snapshot_date, collection_window, status, release_id) "
             "VALUES (999, '2099-01-01', 'QA-fixture period', 'aggregated', ?)", (TEST_REL,))
src = conn.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (flip[0],)).fetchone()
if src:
    conn.execute("INSERT OR REPLACE INTO benchmark_snapshots(snapshot_id, question_id, payload_json) VALUES (999, ?, ?)",
                 (flip[0], src[0]))
    conn.commit()
    q = appmod.visible_questions()[flip[0]]
    breaks = rel.comparability_breaks(q.historical_comparability)
    check("break marker stored and parsed", TEST_REL in breaks, breaks)
    rel_order = {r["release_id"]: i for i, r in enumerate(conn.execute(
        "SELECT release_id FROM core_releases ORDER BY released_at"))}
    p1 = rel_order.get(conn.execute("SELECT release_id FROM snapshots WHERE snapshot_id=1").fetchone()[0], -1)
    p2 = rel_order.get(TEST_REL, -1)
    crossing = [b for b in breaks if p1 < rel_order.get(b, -1) <= p2]
    check("trend splits between the two periods (no continuous line)", len(crossing) >= 1, crossing)

print("== emergency lane gate ==")
refused = 0
for args in ((flip[0], "v9", "", "someone"), (flip[0], "v9", "a trigger", "")):
    try:
        rel.emergency_change(*args, conn=conn)
    except ValueError:
        refused += 1
check("refused without trigger AND without sign-off", refused == 2, refused)
rel.emergency_change(flip[1], "v9-qafix", "QA: statutory baseline fixture", "qa-gate", conn=conn)
check("accepted with both; logged in the emergency lane",
      conn.execute("SELECT COUNT(*) FROM core_changelog WHERE lane='emergency' AND question_id=?",
                   (flip[1],)).fetchone()[0] == 1)

print("== backlog queues, never applies ==")
rel.add_backlog("qa fixture item", "x", "manual", "qa-fixture-1", conn)
live_after = conn.execute("SELECT COUNT(*) FROM questions WHERE superpower='Reward' AND status!='retired'").fetchone()[0]
check("backlog add leaves the live core untouched", live_after == pre_core - 1, live_after)

# ------------------------------------------------------------- CLEANUP -----
print("== fixture cleanup ==")
conn.executemany("UPDATE questions SET is_required=0, question_version=REPLACE(question_version,'+qafix','') WHERE id=?",
                 [(q,) for q in flip])
conn.execute("UPDATE questions SET question_version=REPLACE(question_version,'v9-qafix','v9') WHERE id=?", (flip[1],))
# restore versions exactly from the baseline snapshot (source of truth)
for qid in flip + [RETIRE]:
    snap = base_set.get(qid)
    if snap:
        conn.execute("UPDATE questions SET question_version=?, is_required=?, status=?, release_retired=NULL WHERE id=?",
                     (snap["question_version"], snap["is_required"], snap.get("status") or "active", qid))
conn.execute("UPDATE questions SET historical_comparability=REPLACE(REPLACE(historical_comparability, '; break@%s',''),'break@%s','') WHERE id=?" % (TEST_REL, TEST_REL), (flip[0],))
conn.execute("DELETE FROM benchmark_snapshots WHERE snapshot_id=999")
conn.execute("DELETE FROM snapshots WHERE snapshot_id=999")
conn.execute("DELETE FROM release_questions WHERE release_id=?", (TEST_REL,))
conn.execute("DELETE FROM core_releases WHERE release_id=?", (TEST_REL,))
conn.execute("DELETE FROM core_changelog WHERE release_id=? OR (lane='emergency' AND signed_off_by='qa-gate')", (TEST_REL,))
conn.execute("UPDATE core_releases SET status='current' WHERE release_id=?", (prev_current,))
conn.execute("UPDATE questions SET release_entered=? WHERE release_entered=?", (prev_current, TEST_REL))
conn.execute("DELETE FROM core_backlog WHERE source_ref='qa-fixture-1'")
conn.execute("DELETE FROM orgs WHERE org_id='qa-sticky-org'")
conn.commit()
appmod.load_questions.cache_clear()

post_core = conn.execute("SELECT COUNT(*) FROM questions WHERE superpower='Reward' AND status!='retired'").fetchone()[0]
post_req = len(appmod.completion_basis_questions())
post_changelog = conn.execute("SELECT COUNT(*) FROM core_changelog").fetchone()[0]
post_backlog = conn.execute("SELECT COUNT(*) FROM core_backlog").fetchone()[0]
check("cleanup restored core size", post_core == pre_core, (pre_core, post_core))
check("cleanup restored required set", post_req == pre_req, (pre_req, post_req))
check("cleanup restored changelog/backlog", post_changelog == pre_changelog and post_backlog == pre_backlog,
      (pre_changelog, post_changelog, pre_backlog, post_backlog))

print("\nNOTE: this gate mutates and restores the DB; a RUNNING app process still")
print("caches the fixture question set — restart the app after running this gate.")
print("\nRESULTS: %d failures" % len(FAILS))
for n, d in FAILS:
    print("  FAIL:", n, d)
sys.exit(1 if FAILS else 0)
