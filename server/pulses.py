# -*- coding: utf-8 -*-
"""PULSES — Tier 2 timely topical surveys (2026-06-12).

A pulse is a short, time-boxed deep-dive with its own OPT-IN cohort, its own
window and its own standalone report — free to participants, give-to-get per
pulse, fully independent of the core unlock gate in both directions.

THE CARDINAL RULE — hard data separation: pulse responses are stored in
pulse_responses, never in `answers`. The core aggregation path reads
`answers` only and the pulse path reads `pulse_responses` only — the same
question answered in both places produces TWO independent aggregates from
two different cohorts, and neither can pool into the other even via a
forgotten filter. Graduation (pulse question -> core release) carries the
QUESTION DEFINITION ONLY, never the responses: the graduated core question
starts at zero answers and trends from its entry release.

ONE ENGINE, NOT TWO: pulse aggregation calls the SAME
aggregate.aggregate_question_for_orgs the core uses — identical calculation,
identical n>=5 suppression, matrix/multi-select handling included.

Lifecycle: draft (invisible to members) -> open (join/submit inside the
window) -> closed (read-only, report final) -> archived (retained, report
still viewable). closes_at may be extended while OPEN; reopening a closed
pulse is deliberately out of scope for v1 (its report is final).

Creation is a LUMI action (superadmin), not a member action. v1 affordance:
the seed script (seed_pulse.py) + these module functions — the back-office
console remains unbuilt and flagged (DECISIONS.md D2).
"""
import json
import uuid
from datetime import datetime

from db import get_conn, j, uj
from library import load_questions, _row_to_question
from aggregate import aggregate_question_for_orgs, SUPPRESSION_FLOOR

CATEGORY_PULSE = "Pulse"   # pulse-origin questions: superpower='Pulse' keeps
                           # them out of the core scope filter AND core releases


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------- lifecycle
def create_pulse(name, description, question_ids, new_questions=None,
                 closes_at=None, conn=None):
    """Superadmin: assemble a pulse from existing library questions (by id —
    reuse first) and/or newly authored pulse questions (full standard schema,
    flagged pulse-origin via superpower='Pulse'). Starts as DRAFT."""
    conn = conn or get_conn()
    qids = list(question_ids or [])
    for nq in (new_questions or []):
        qid = nq.get("id") or ("PULSE_" + uuid.uuid4().hex[:10].upper())
        cols = {
            "id": qid, "text": nq["text"], "short_description": nq.get("title"),
            "help_text": nq.get("help_text"), "definition": nq.get("definition"),
            "superpower": CATEGORY_PULSE, "sub_power": CATEGORY_PULSE,
            "sub_power_order": 99, "type": nq["type"], "category": nq.get("category") or "practice",
            "options_json": j(nq.get("options")) if nq.get("options") else None,
            "default_chart_type": "quartile_band" if nq["type"] == "numeric" else "bar",
            "data_display_type": "mean" if nq["type"] == "numeric" else "percentage_distribution",
            "polarity": nq.get("polarity") or "neutral",
            "unit": nq.get("unit"), "unit_display_name": nq.get("unit_display_name"),
            "unit_type": nq.get("unit_type") or "none",
            "currency_code": "GBP" if nq.get("unit_type") == "currency" else None,
            "matrix_json": j(nq["matrix"]) if nq.get("matrix") else None,
            "matrix_rows_json": j(nq["matrix_rows"]) if nq.get("matrix_rows") else None,
            "lumi_tier": "Pulse",
            "na_handling_json": j({"exclude_from_scoring": True, "exclude_from_benchmarking": False}),
            "benchmark_display": nq.get("title"), "is_scored": 0,
            "is_required": 0, "search_description": nq.get("title"),
            "question_order": 90000,
            "question_version": "pulse-v1", "historical_comparability": "high",
            "status": "active",
        }
        conn.execute("INSERT INTO questions(%s) VALUES (%s)" % (
            ",".join(cols), ",".join("?" * len(cols))), list(cols.values()))
        qids.append(qid)
    load_questions.cache_clear()
    lib = load_questions()
    missing = [q for q in qids if q not in lib]
    if missing:
        raise ValueError("unknown question ids: %s" % missing)
    pid = "pulse-" + uuid.uuid4().hex[:8]
    conn.execute("INSERT INTO pulses(pulse_id, name, description, status, closes_at, question_ids_json) "
                 "VALUES (?,?,?,'draft',?,?)", (pid, name, description, closes_at, j(qids)))
    conn.commit()
    return pid


def open_pulse(pulse_id, conn=None):
    """draft -> open. Snapshots every question definition AS-ASKED (the same
    pattern as core release snapshots) so the report stays reproducible
    regardless of later core rewords/retirements."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if p["status"] != "draft":
        raise ValueError("only a draft pulse can open (status=%s)" % p["status"])
    snap = {}
    for qid in uj(p["question_ids_json"], []):
        row = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        snap[qid] = {k: row[k] for k in row.keys()}
    conn.execute("UPDATE pulses SET status='open', opens_at=?, question_snapshot_json=? WHERE pulse_id=?",
                 (_now(), j(snap), pulse_id))
    conn.commit()


def close_pulse(pulse_id, conn=None):
    conn = conn or get_conn()
    if get_pulse(pulse_id, conn)["status"] != "open":
        raise ValueError("only an open pulse can close")
    conn.execute("UPDATE pulses SET status='closed', closes_at=COALESCE(closes_at, ?) WHERE pulse_id=?",
                 (_now(), pulse_id))
    conn.commit()


def archive_pulse(pulse_id, conn=None):
    conn = conn or get_conn()
    if get_pulse(pulse_id, conn)["status"] != "closed":
        raise ValueError("only a closed pulse can archive")
    conn.execute("UPDATE pulses SET status='archived' WHERE pulse_id=?", (pulse_id,))
    conn.commit()


def extend_close(pulse_id, new_closes_at, conn=None):
    """Superadmin may extend the window while OPEN. Reopening a closed pulse
    is out of scope for v1 — its report is final."""
    conn = conn or get_conn()
    if get_pulse(pulse_id, conn)["status"] != "open":
        raise ValueError("only an OPEN pulse's window can be extended (no reopen in v1)")
    conn.execute("UPDATE pulses SET closes_at=? WHERE pulse_id=?", (new_closes_at, pulse_id))
    conn.commit()


def get_pulse(pulse_id, conn=None):
    conn = conn or get_conn()
    p = conn.execute("SELECT * FROM pulses WHERE pulse_id=?", (pulse_id,)).fetchone()
    if p is None:
        raise ValueError("unknown pulse %s" % pulse_id)
    return p


def is_accepting(p):
    """Open AND inside the window (closes_at may be NULL = no deadline yet)."""
    if p["status"] != "open":
        return False
    ca = p["closes_at"]
    return not ca or _now() <= ca


# -------------------------------------------------------------- participation
def join_pulse(pulse_id, org_id, conn=None):
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if not is_accepting(p):
        raise ValueError("This pulse isn't open for new participants.")
    conn.execute("INSERT OR IGNORE INTO pulse_participants(pulse_id, org_id) VALUES (?,?)",
                 (pulse_id, org_id))
    conn.commit()


def pulse_questions(p):
    """Question objects AS-ASKED: from the open-time snapshot (fall back to
    the live library only for a draft that hasn't snapshotted yet)."""
    snap = uj(p["question_snapshot_json"], {})
    if snap:
        return {qid: _row_to_question(_DictRow(row)) for qid, row in snap.items()}
    lib = load_questions()
    return {qid: lib[qid] for qid in uj(p["question_ids_json"], []) if qid in lib}


class _DictRow(dict):
    """sqlite3.Row-alike over a snapshot dict (library loader compatibility)."""
    def keys(self):
        return list(dict.keys(self))


def save_response(pulse_id, org_id, qid, row_id, value, conn=None):
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if not is_accepting(p):
        raise ValueError("This pulse is closed — responses are read-only.")
    if not conn.execute("SELECT 1 FROM pulse_participants WHERE pulse_id=? AND org_id=?",
                        (pulse_id, org_id)).fetchone():
        raise ValueError("Join the pulse before answering.")
    if qid not in pulse_questions(p):
        raise ValueError("That question isn't part of this pulse.")
    if value in (None, ""):
        conn.execute("DELETE FROM pulse_responses WHERE pulse_id=? AND org_id=? AND question_id=? AND matrix_row_id=?",
                     (pulse_id, org_id, qid, row_id or ""))
    else:
        conn.execute(
            "INSERT INTO pulse_responses(pulse_id, org_id, question_id, matrix_row_id, value, updated_at) "
            "VALUES (?,?,?,?,?,datetime('now')) "
            "ON CONFLICT(pulse_id, org_id, question_id, matrix_row_id) "
            "DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (pulse_id, org_id, qid, row_id or "", value))
    conn.commit()


def submit_pulse(pulse_id, org_id, conn=None):
    """Give-to-get, scoped to THIS pulse: submitting reveals this pulse's
    report (and only this pulse's). Partial submissions count — answered
    questions aggregate, skipped ones are excluded (blank != 0)."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if not is_accepting(p):
        raise ValueError("This pulse is closed.")
    n = conn.execute("SELECT COUNT(*) FROM pulse_responses WHERE pulse_id=? AND org_id=? "
                     "AND value IS NOT NULL AND TRIM(value) != ''", (pulse_id, org_id)).fetchone()[0]
    if not n:
        raise ValueError("Answer at least one question to participate.")
    conn.execute("UPDATE pulse_participants SET submission_complete=1 WHERE pulse_id=? AND org_id=?",
                 (pulse_id, org_id))
    conn.commit()


def participant(pulse_id, org_id, conn=None):
    conn = conn or get_conn()
    return conn.execute("SELECT * FROM pulse_participants WHERE pulse_id=? AND org_id=?",
                        (pulse_id, org_id)).fetchone()


# ----------------------------------------------------------------- the report
def pulse_report(pulse_id, conn=None):
    """Aggregate the pulse's questions over ITS cohort only — through the
    SAME engine entry point the core uses (aggregate_question_for_orgs), so
    calculation, suppression (n>=5) and matrix/multi handling are identical
    by construction. Whole-cohort only in v1 (no cuts: opt-in cohorts would
    suppress every cut)."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    qs = pulse_questions(p)
    cohort = {r["org_id"] for r in conn.execute(
        "SELECT org_id FROM pulse_participants WHERE pulse_id=? AND submission_complete=1", (pulse_id,))}
    answers_by_q = {}
    for r in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM pulse_responses WHERE pulse_id=?",
                          (pulse_id,)):
        answers_by_q.setdefault(r["question_id"], {})[(r["org_id"], r["matrix_row_id"] or "")] = r["value"]
    out = []
    for qid, q in qs.items():
        blk, mr, _score, _presence = aggregate_question_for_orgs(q, cohort, answers_by_q.get(qid, {}))
        entry = {"question_id": qid, "title": q.display_title, "text": q.text,
                 "type": q.type, "unit": q.unit_block(), "polarity": q.polarity,
                 "block": blk, "as_asked_version": q.question_version}
        if mr is not None:
            entry["matrix_rows"] = [{"row_id": m["row_id"], "label": m["label"], "block": m["block"]} for m in mr]
        out.append(entry)
    return {"pulse_id": pulse_id, "name": p["name"], "status": p["status"],
            "participants": len(cohort), "floor": SUPPRESSION_FLOOR,
            "below_floor": len(cohort) < SUPPRESSION_FLOOR, "questions": out}


# ----------------------------------------------------------------- graduation
def graduate_question(qid, category, release_note="", conn=None):
    """Promote a pulse-origin question into the CORE at the next release —
    the DEFINITION ONLY. The pulse's responses stay in pulse_responses
    forever; the core question starts at ZERO answers, is answered fresh by
    the whole membership, and trends only from its entry release. Copying
    pulse responses into `answers` is forbidden (different population —
    the cardinal rule's subtlest hole)."""
    conn = conn or get_conn()
    q = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if q is None or q["superpower"] != CATEGORY_PULSE:
        raise ValueError("only a pulse-origin question can graduate")
    order = {"Pay": 1, "Incentives": 2, "Benefits": 3, "Time Off": 4,
             "Wellbeing": 5, "Recognition": 6, "Governance": 7}
    if category not in order:
        raise ValueError("category must be one of the 7")
    conn.execute("UPDATE questions SET superpower='Reward', sub_power=?, sub_power_order=?, "
                 "lumi_tier='Core' WHERE id=?", (category, order[category], qid))
    conn.commit()
    load_questions.cache_clear()
    # the question now appears in the live core; the NEXT release's diff logs
    # it as 'added' and stamps release_entered. Structurally zero responses:
    n = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (qid,)).fetchone()[0]
    assert n == 0, "graduated question must start with zero core responses"
    return n
