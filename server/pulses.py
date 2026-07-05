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
PULSE_NEW_TYPES = ("yes_no", "single_select", "multi_select", "numeric")


def validate_new_questions(new_questions):
    """Guardrails on authored pulse questions — shared by the API body parse and
    the assembly step so a broken survey (one option, a delimiter-breaking label,
    duplicates, an over-long question) can never reach review or launch. Mirrors
    the core metric validator. Raises ValueError with a member-facing message."""
    for nq in (new_questions or []):
        if nq.get("type") not in PULSE_NEW_TYPES:
            raise ValueError("unsupported question type: %s" % nq.get("type"))
        text = (nq.get("text") or "").strip()
        if not text:
            raise ValueError("every question needs text")
        if len(text) > 200:
            raise ValueError("keep each question under 200 characters")
        if nq["type"] in ("yes_no", "single_select", "multi_select"):
            labels = [(o.get("label") or "").strip() for o in (nq.get("options") or [])]
            labels = [l for l in labels if l]
            if len(labels) < 2:
                raise ValueError("“%s” needs at least two answer options" % text[:40])
            if nq["type"] == "yes_no" and len(labels) != 2:
                raise ValueError("a Yes/No question needs exactly two options")
            for l in labels:
                if ";" in l or "," in l:
                    raise ValueError("answer options can't contain ';' or ',' (delimiter-safe storage)")
                if len(l) > 80:
                    raise ValueError("keep each answer option under 80 characters")
            if len({l.lower() for l in labels}) != len(labels):
                raise ValueError("answer options must be distinct")


def _assemble_questions(question_ids, new_questions, conn):
    """Build the final ordered question-id list for a pulse from reused library
    ids + newly authored pulse questions. Newly authored questions are inserted
    into `questions` flagged pulse-origin (superpower='Pulse') so they can never
    leak into the core scope filter or a core release — the firewall holds for
    self-service authors exactly as it does for staff."""
    validate_new_questions(new_questions)
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
    return qids


def create_pulse(name, description, question_ids, new_questions=None,
                 closes_at=None, conn=None, owner_org_id=None, created_by=None):
    """Assemble a pulse from existing library questions (by id — reuse first)
    and/or newly authored pulse questions. Starts as DRAFT.

    Staff-authored (owner_org_id=None): launch_status stays NULL and the pulse
    is opened directly from the admin console. Org-authored (owner_org_id set):
    launch_status starts 'building' and the pulse only opens via the
    review -> approve -> paid gate (see review_pulse / mark_order_paid)."""
    conn = conn or get_conn()
    qids = _assemble_questions(question_ids, new_questions, conn)
    pid = "pulse-" + uuid.uuid4().hex[:8]
    launch_status = "building" if owner_org_id else None
    conn.execute(
        "INSERT INTO pulses(pulse_id, name, description, status, closes_at, question_ids_json, "
        "owner_org_id, created_by, launch_status) VALUES (?,?,?,'draft',?,?,?,?,?)",
        (pid, name, description, closes_at, j(qids), owner_org_id, created_by, launch_status))
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


# ===================== self-service launch flow (2026-06-22) =================
# An org Admin authors a pulse, submits it for lumi review, and — once approved —
# pays a launch fee that opens it to the whole community. The states below ride
# on pulses.launch_status (NULL for staff-authored pulses); the engine `status`
# stays 'draft' until payment, at which point open_pulse() runs unchanged.
#
#   building -> in_review -> changes_requested -> (back to building)
#                         -> rejected
#                         -> approved -> paid (==> status flips draft->open)
#
# EDITABLE = the author can still change it; LOCKED otherwise.
_EDITABLE = ("building", "changes_requested")


def _require_owner(p, org_id):
    if not p["owner_org_id"]:
        raise ValueError("This isn't a self-service pulse.")
    if org_id is not None and p["owner_org_id"] != org_id:
        raise ValueError("This pulse belongs to another organisation.")


def update_pulse_draft(pulse_id, org_id, name, description, question_ids,
                       new_questions=None, closes_at=None, conn=None):
    """Edit an org-authored draft while it is still EDITABLE (building or
    after staff requested changes). Rebuilds the question set; any previously
    authored pulse questions left unreferenced stay inert (superpower='Pulse',
    invisible to core)."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    _require_owner(p, org_id)
    if p["launch_status"] not in _EDITABLE:
        raise ValueError("This pulse can no longer be edited (it is %s)." % p["launch_status"])
    qids = _assemble_questions(question_ids, new_questions, conn)
    conn.execute("UPDATE pulses SET name=?, description=?, closes_at=?, question_ids_json=? WHERE pulse_id=?",
                 (name, description, closes_at, j(qids), pulse_id))
    conn.commit()
    return qids


def discard_pulse(pulse_id, org_id, conn=None):
    """Delete an org-authored draft that hasn't launched (building or
    changes_requested). Removes the pulse and any orders/participants/responses
    it accrued (a pre-launch draft has none of the latter)."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    _require_owner(p, org_id)
    if p["launch_status"] not in _EDITABLE:
        raise ValueError("Only a draft that hasn't launched can be discarded.")
    conn.execute("DELETE FROM pulse_responses WHERE pulse_id=?", (pulse_id,))
    conn.execute("DELETE FROM pulse_participants WHERE pulse_id=?", (pulse_id,))
    conn.execute("DELETE FROM pulse_launch_orders WHERE pulse_id=?", (pulse_id,))
    conn.execute("DELETE FROM pulses WHERE pulse_id=?", (pulse_id,))
    conn.commit()


def submit_for_review(pulse_id, org_id, conn=None):
    """Author -> lumi: hand an editable draft to staff for the launch review."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    _require_owner(p, org_id)
    if p["launch_status"] not in _EDITABLE:
        raise ValueError("This pulse isn't ready to submit (it is %s)." % p["launch_status"])
    if not uj(p["question_ids_json"], []):
        raise ValueError("Add at least one question before submitting for review.")
    conn.execute("UPDATE pulses SET launch_status='in_review', review_notes=NULL WHERE pulse_id=?", (pulse_id,))
    conn.commit()


def review_pulse(pulse_id, decision, reviewed_by, notes="", fee_pence=None, conn=None):
    """lumi staff decision on a submitted pulse. decision in
    {approve, changes, reject}. Approval REQUIRES a launch fee (pence) and moves
    the pulse to 'approved' — ready for the author to pay. 'changes' returns it
    to the author (editable again) with notes; 'reject' is terminal."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if not p["owner_org_id"]:
        raise ValueError("Only a self-service pulse goes through review.")
    if p["launch_status"] != "in_review":
        raise ValueError("Only a pulse awaiting review can be decided (it is %s)." % p["launch_status"])
    target = {"approve": "approved", "changes": "changes_requested", "reject": "rejected"}.get(decision)
    if not target:
        raise ValueError("decision must be approve | changes | reject")
    if target == "approved" and not fee_pence:
        raise ValueError("Approval needs a launch fee.")
    conn.execute(
        "UPDATE pulses SET launch_status=?, review_notes=?, reviewed_by=?, reviewed_at=?, "
        "launch_fee_pence=COALESCE(?, launch_fee_pence) WHERE pulse_id=?",
        (target, notes or None, reviewed_by, _now(), fee_pence, pulse_id))
    conn.commit()


# --------------------------------------------------------------- launch orders
def create_launch_order(pulse_id, org_id, amount_pence, created_by, currency="gbp", conn=None):
    """One row per checkout attempt — the billing/audit ledger."""
    conn = conn or get_conn()
    oid = "ord-" + uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO pulse_launch_orders(order_id, pulse_id, org_id, amount_pence, currency, created_by) "
        "VALUES (?,?,?,?,?,?)", (oid, pulse_id, org_id, amount_pence, currency, created_by))
    conn.commit()
    return oid


def set_order_session(order_id, session_id, conn=None):
    conn = conn or get_conn()
    conn.execute("UPDATE pulse_launch_orders SET stripe_session_id=? WHERE order_id=?", (session_id, order_id))
    conn.commit()


def get_order(order_id, conn=None):
    conn = conn or get_conn()
    return conn.execute("SELECT * FROM pulse_launch_orders WHERE order_id=?", (order_id,)).fetchone()


def get_order_by_session(session_id, conn=None):
    conn = conn or get_conn()
    return conn.execute("SELECT * FROM pulse_launch_orders WHERE stripe_session_id=?", (session_id,)).fetchone()


def latest_order(pulse_id, conn=None):
    conn = conn or get_conn()
    return conn.execute("SELECT * FROM pulse_launch_orders WHERE pulse_id=? ORDER BY created_at DESC, rowid DESC "
                        "LIMIT 1", (pulse_id,)).fetchone()


def mark_order_paid(order_id, payment_intent=None, conn=None):
    """IDEMPOTENT paid->open gate (webhook and success-redirect may both fire):
    mark the order paid, flip launch_status='paid', and OPEN the pulse (snapshot
    + status='open') if it is still a draft. Returns the pulse_id."""
    conn = conn or get_conn()
    o = get_order(order_id, conn)
    if o is None:
        raise ValueError("unknown launch order")
    if o["status"] != "paid":
        conn.execute(
            "UPDATE pulse_launch_orders SET status='paid', paid_at=?, stripe_payment_intent=? WHERE order_id=?",
            (_now(), payment_intent, order_id))
        conn.commit()
    p = get_pulse(o["pulse_id"], conn)
    if p["launch_status"] != "paid":
        conn.execute("UPDATE pulses SET launch_status='paid' WHERE pulse_id=?", (o["pulse_id"],))
        conn.commit()
    if p["status"] == "draft":
        open_pulse(o["pulse_id"], conn)        # snapshot questions + status='open'
    return o["pulse_id"]


# ------------------------------------------------------------- listing helpers
def _pulse_summary(p, conn):
    """Owner/staff-facing summary row: counts + lifecycle + the latest order."""
    pid = p["pulse_id"]
    n_part = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=?", (pid,)).fetchone()[0]
    n_sub = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=? AND submission_complete=1",
                         (pid,)).fetchone()[0]
    o = latest_order(pid, conn)
    return {
        "pulse_id": pid, "name": p["name"], "description": p["description"],
        "status": p["status"], "launch_status": p["launch_status"],
        "owner_org_id": p["owner_org_id"], "visibility": p["visibility"],
        "n_questions": len(uj(p["question_ids_json"], [])),
        "n_participants": n_part, "n_submitted": n_sub,
        "opens_at": p["opens_at"], "closes_at": p["closes_at"], "created_at": p["created_at"],
        "review_notes": p["review_notes"], "launch_fee_pence": p["launch_fee_pence"],
        "order": ({"order_id": o["order_id"], "status": o["status"], "amount_pence": o["amount_pence"]}
                  if o else None),
    }


def org_pulses(org_id, conn=None):
    """Every pulse this org authored, newest first (owner dashboard)."""
    conn = conn or get_conn()
    rows = conn.execute("SELECT * FROM pulses WHERE owner_org_id=? ORDER BY created_at DESC", (org_id,)).fetchall()
    return [_pulse_summary(r, conn) for r in rows]


def review_queue(conn=None):
    """Staff console: all self-service pulses, those awaiting review first."""
    conn = conn or get_conn()
    rows = conn.execute(
        "SELECT * FROM pulses WHERE owner_org_id IS NOT NULL "
        "ORDER BY (launch_status='in_review') DESC, created_at DESC").fetchall()
    out = []
    for p in rows:
        s = _pulse_summary(p, conn)
        owner = conn.execute("SELECT name FROM orgs WHERE org_id=?", (p["owner_org_id"],)).fetchone()
        s["owner_name"] = owner["name"] if owner else p["owner_org_id"]
        # the actual questions, so staff can review wording for quality / no-PII
        s["questions"] = [{"id": qid, "text": q.text, "type": q.type}
                          for qid, q in pulse_questions(p).items()]
        out.append(s)
    return out


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
        # author-declared favourable option (single-choice only) — surfaced for the
        # render layer straight from the as-asked definition; the core engine's option
        # blocks are untouched, so the benchmark snapshot stays byte-identical.
        if q.type in ("single_select", "yes_no"):
            favlbl = next((o.get("label") for o in (q.options or []) if o.get("is_favourable")), None)
            if favlbl:
                entry["favourable_label"] = favlbl
        if mr is not None:
            entry["matrix_rows"] = [{"row_id": m["row_id"], "label": m["label"], "block": m["block"]} for m in mr]
        out.append(entry)
    report = {"pulse_id": pulse_id, "name": p["name"], "status": p["status"],
              "description": p["description"],
              "participants": len(cohort), "floor": SUPPRESSION_FLOOR,
              "below_floor": len(cohort) < SUPPRESSION_FLOOR, "questions": out,
              "closes_at": p["closes_at"], "generated_at": _now()}
    report["narrative"] = pulse_narrative_deterministic(report)
    return report


def _pct_word(pct):
    if pct >= 75: return "most"
    if pct >= 55: return "over half"
    if pct >= 45: return "nearly half"
    if pct >= 28: return "around a third"
    if pct >= 15: return "a minority"
    return "a few"


def pulse_narrative_deterministic(report):
    """The always-present report headline — an honest read composed straight
    from the cohort figures (no model needed; this is the keyless floor and the
    fallback the AI path validates against). Returns {summary, key_findings}."""
    n = report["participants"]
    qs = [q for q in report["questions"] if not (q.get("block") or {}).get("suppressed")]
    shown = len(qs)
    total = len(report["questions"])
    summary = ("%d organisation%s took part in “%s”. " % (n, "" if n == 1 else "s", report["name"]))
    if shown == 0:
        summary += "Every question is still below the 5-organisation floor, so no figures are shown yet."
        return {"summary": summary, "key_findings": [], "_fallback": True}
    summary += ("Results below are the whole-cohort view across %d question%s%s, each held to the same "
                "5-organisation suppression as the core benchmark." %
                (shown, "" if shown == 1 else "s",
                 "" if shown == total else " of %d" % total))
    findings = []
    for q in qs:
        blk = q.get("block") or {}
        opts = blk.get("options") or []
        if opts:
            top = max(opts, key=lambda o: o.get("pct", 0))
            findings.append("On “%s”, %s of the cohort chose “%s” (%s%%, n=%s)." %
                            (q["title"], _pct_word(top.get("pct", 0)), top.get("label", ""),
                             top.get("pct", 0), blk.get("n", n)))
        elif blk.get("p50") is not None:
            findings.append("On “%s”, the cohort median is %s (n=%s)." %
                            (q["title"], _fmt_num(blk["p50"], q.get("unit")), blk.get("n", n)))
    return {"summary": summary, "key_findings": findings[:5],
            "_fallback": True}


def _fmt_num(v, unit):
    ut = (unit or {}).get("type") if isinstance(unit, dict) else None
    try:
        s = ("%.1f" % float(v)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)
    if ut == "percentage": return s + "%"
    if ut == "currency": return "£" + s
    return s


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
