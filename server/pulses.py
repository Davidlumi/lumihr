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
import re
import unicodedata
import uuid
from datetime import datetime

from db import get_conn, j, uj
import identity
from library import load_questions, _row_to_question
from aggregate import aggregate_question_for_orgs, SUPPRESSION_FLOOR

CATEGORY_PULSE = "Pulse"   # pulse-origin questions: superpower='Pulse' keeps
                           # them out of the core scope filter AND core releases


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------- lifecycle
PULSE_NEW_TYPES = ("yes_no", "single_select", "multi_select", "numeric")


# What a number on an authored question MEANS. Without one, a pulse asking "by what
# percentage does headcount rise?" reported a cohort median of "4.8" — 4.8 what? The engine
# already formats by unit_type (_fmt_num); authored questions just never set one (agent QA
# finding, 2026-08-19).
#
# TWO CALLERS, one contract. The builder UI sends the full triple it has always sent
# (unit_type="currency", unit="GBP"); an API author sends a friendly unit ("%", "days") and
# nothing else. Whitelisting only the friendly words would have rejected the builder's own
# "GBP" and every custom label it offers — so unit_type is trusted when given and INFERRED
# when it is not, and the unit string itself is free text with a length bound.
PULSE_UNIT_TYPES = ("percentage", "currency", "none")


def _infer_unit_type(unit):
    u = (unit or "").strip().lower()
    if u in ("%", "percent", "percentage", "pct"):
        return "percentage"
    if u in ("£", "gbp", "gbp£", "pounds"):
        return "currency"
    return "none"


def validate_new_questions(new_questions):
    """Guardrails on authored pulse questions — shared by the API body parse and
    the assembly step so a broken survey (one option, a delimiter-breaking label,
    duplicates, an over-long question) can never reach review or launch. Mirrors
    the core metric validator. Raises ValueError with a member-facing message."""
    seen_text = set()
    for nq in (new_questions or []):
        if nq.get("type") not in PULSE_NEW_TYPES:
            raise ValueError("“%s” isn't a question type we support. Use one of: %s."
                             % (nq.get("type"), ", ".join(PULSE_NEW_TYPES)))
        text = (nq.get("text") or "").strip()
        if not text:
            raise ValueError("Every question needs some text.")
        if len(text) > 200:
            raise ValueError("Keep each question to 200 characters or fewer.")
        # the same question twice splits its own results across two ids and shows
        # respondents a duplicate — it quietly damages the data the member paid for
        if text.lower() in seen_text:
            raise ValueError("“%s” appears twice — every question in a pulse must be "
                             "different." % text[:60])
        seen_text.add(text.lower())
        if nq["type"] == "numeric":
            u = nq.get("unit")
            if isinstance(u, dict):
                u = u.get("symbol") or u.get("display_name") or ""   # the builder's block shape
            if u is not None and not isinstance(u, str):
                raise ValueError("“%s”: the unit must be text, like \"%%\" or \"days\"."
                                 % text[:60])
            if len(((u or "").strip())) > 16:
                raise ValueError("“%s”: keep the unit to 16 characters or fewer." % text[:60])
            ut = (nq.get("unit_type") or "").strip()
            if ut and ut not in PULSE_UNIT_TYPES:
                raise ValueError("“%s”: %r isn't a unit type. Use one of: %s."
                                 % (text[:60], ut, ", ".join(PULSE_UNIT_TYPES)))
        if nq["type"] == "numeric" and (nq.get("options") or []):
            # numeric renders as a number box, so options ride along invisibly. Every
            # other type validates its options strictly; this one used to accept and
            # store whatever it was given (agent QA finding, 2026-08-19).
            raise ValueError("“%s” asks for a number, so it can't have answer options — "
                             "remove them, or change the type." % text[:60])
        if nq["type"] == "yes_no" and not (nq.get("options") or []):
            nq["options"] = ["Yes", "No"]        # they are Yes and No by definition
        if nq["type"] in ("yes_no", "single_select", "multi_select"):
            # options may arrive as dicts ({code,label}, the builder UI's shape) OR bare
            # strings (API authors) — both are valid input; a string must never 500
            # (E2E finding 1, 2026-07-13). Anything else (numbers, null) is not an option.
            # Codes are normalised at assembly.
            labels = [((o.get("label") or "") if isinstance(o, dict) else
                       (o if isinstance(o, str) else "")).strip()
                      for o in (nq.get("options") or [])]
            given = len(nq.get("options") or [])
            labels = [l for l in labels if l]
            # a blank option used to be silently dropped and then reported as "needs at
            # least two options", which sent the member off to ADD one instead of filling
            # in the empty one they had already typed
            if given > len(labels):
                raise ValueError("“%s” has %d blank answer option%s — fill %s in or remove "
                                 "%s." % (text[:60], given - len(labels),
                                          "" if given - len(labels) == 1 else "s",
                                          "it" if given - len(labels) == 1 else "them",
                                          "it" if given - len(labels) == 1 else "them"))
            if len(labels) < 2:
                raise ValueError("“%s” needs at least two answer options." % text[:60])
            if nq["type"] == "yes_no" and len(labels) != 2:
                raise ValueError("“%s” is a Yes/No question, so it needs exactly two "
                                 "options." % text[:60])
            for l in labels:
                if ";" in l or "," in l:
                    raise ValueError("“%s”: answer options can't contain a semicolon or a "
                                     "comma — they separate stored answers." % text[:60])
                if len(l) > 80:
                    raise ValueError("“%s”: keep each answer option to 80 characters or fewer."
                                     % text[:60])
            if len({l.lower() for l in labels}) != len(labels):
                raise ValueError("“%s” has the same answer option twice — each one must be "
                                 "different." % text[:60])


def _norm_options(opts):
    """Normalise authored options to the full {code,label,order,is_na} shape the rest of
    the platform assumes (E2E finding 2, 2026-07-13): validation accepts label-only dicts
    and bare strings, so assembly must guarantee codes — otherwise an accepted pulse
    500s its own page the moment it opens (the worst possible moment, post-launch).
    Codes slug from the label (the builder UI's own convention), deduped defensively."""
    out, seen = [], set()
    for i, o in enumerate(opts or []):
        if not isinstance(o, dict):
            o = {"label": (o if isinstance(o, str) else "").strip()}
        label = (o.get("label") or "").strip()
        if not label:
            continue   # non-option garbage (validation already guaranteed >= 2 real labels)
        code = (o.get("code") or "").strip()
        if not code:
            folded = unicodedata.normalize("NFKD", label.upper())
            folded = "".join(c for c in folded if not unicodedata.combining(c))
            code = re.sub(r"[^A-Z0-9]+", "_", folded).strip("_") or ("OPT%d" % i)
        base, k = code, 2
        while code in seen:
            code, k = "%s_%d" % (base, k), k + 1
        seen.add(code)
        # spread the ORIGINAL dict first — authored extras (is_favourable, help text)
        # must survive normalisation (qa_pulse guards the favourable channel)
        out.append({**o, "code": code, "label": label,
                    "order": o.get("order", i + 1), "is_na": bool(o.get("is_na"))})
    return out


def _u(nq):
    """(unit, display, unit_type). Trusts an explicit unit_type (the builder always sends
    one); infers it from the unit string for an API author who sent only "%" or "£"."""
    u = nq.get("unit")
    if isinstance(u, dict):
        u = u.get("symbol") or u.get("display_name") or ""
    u = (u or "").strip() or None
    ut = (nq.get("unit_type") or "").strip() or _infer_unit_type(u)
    disp = (nq.get("unit_display_name") or "").strip() or u
    return (u, disp, ut)


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
            "options_json": j(_norm_options(nq.get("options"))) if nq.get("options") else None,
            "default_chart_type": "quartile_band" if nq["type"] == "numeric" else "bar",
            "data_display_type": "mean" if nq["type"] == "numeric" else "percentage_distribution",
            "polarity": nq.get("polarity") or "neutral",
            "unit": _u(nq)[0], "unit_display_name": _u(nq)[1],
            "unit_type": _u(nq)[2],
            "currency_code": "GBP" if _u(nq)[2] == "currency" else None,
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


_STATE_WORDS = {
    "building": "still a draft",
    "in_review": "with lumi for review",
    "changes_requested": "waiting on your changes",
    "approved": "approved and ready to launch",
    "paid": "live to the community",
    "rejected": "not approved",
}


def _state_words(ls):
    return _STATE_WORDS.get(ls, ls or "in an unknown state")


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
        raise ValueError("You can't edit this pulse — it's %s. Ask lumi to send it back "
                         "if you need to change something." % _state_words(p["launch_status"]))
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
        raise ValueError("You can't discard this pulse — it's %s. Only your own drafts "
                         "can be discarded." % _state_words(p["launch_status"]))
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
        raise ValueError("This pulse is already %s, so there's nothing to send."
                         % _state_words(p["launch_status"]))
    if not uj(p["question_ids_json"], []):
        raise ValueError("Add at least one question before sending this for review.")
    # A pulse with no close date never closes and never reports. Create-time validation
    # rejected a date in the PAST but never required the field, and a PUT that omitted it
    # used to clear it — so a pulse could reach review with nothing to stop it running for
    # ever (agent QA finding, 2026-08-19).
    if not (p["closes_at"] or "").strip():
        raise ValueError("Set a close date before sending this for review — a pulse with no "
                         "closing date never produces a report.")
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
    if target == "approved" and fee_pence is None:
        raise ValueError("Approval needs a launch fee (0 waives it).")
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
    names = identity.org_display_batch([p["owner_org_id"] for p in rows])
    out = []
    for p in rows:
        s = _pulse_summary(p, conn)
        s["owner_name"] = names.get(p["owner_org_id"])
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
    qs_now = pulse_questions(p)
    if qid not in qs_now:
        raise ValueError("That question isn't part of this pulse.")
    # "None of these" is exclusive. The API path already enforces this in validate_answer
    # (app.py, since 2026-06-11) and returns {"ok": false, errors:[…]}; this is defence in
    # depth for callers that reach save_response directly — a seeder or a future import
    # that skips the endpoint, which is exactly how a self-contradicting cohort ("pays
    # nothing" alongside six premiums) got into a QA fixture on 2026-08-19.
    q_now = qs_now[qid]
    if getattr(q_now, "type", None) == "multi_select" and value:
        picked = [t.strip() for t in str(value).split(";") if t.strip()]
        nones = {(o.get("label") or "") for o in (getattr(q_now, "options", None) or [])
                 if (o.get("label") or "").strip().lower().startswith("none")}
        if len(picked) > 1 and nones.intersection(picked):
            raise ValueError("“%s” can't be chosen alongside another answer — it means none "
                             "of them apply." % sorted(nones.intersection(picked))[0])
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
def report_is_available(p):
    """Results appear only once the pulse has CLOSED — for everyone, the owning
    organisation included (David 2026-08-20).

    While a pulse is open, a live report would let a member read the cohort's answers and
    then choose their own against them, and would let the author — who wrote the questions
    — watch the market answer before committing. Waiting until close removes both, and it
    is one rule with no exceptions to explain."""
    if (p["status"] or "") in ("closed", "archived"):
        return True
    # A pulse whose close date has passed but whose status has not been flipped yet has
    # closed as far as a member is concerned — it stopped accepting answers on that date.
    # Keying only on status left it in limbo: not accepting, and no report either.
    return (p["status"] or "") == "open" and not is_accepting(p)


def report_access(pulse_id, org_id, conn=None):
    """Why this organisation may (or may not) see the report. Returns a reason string:
    'participant' | 'owner' | 'purchased' | None."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    if p["owner_org_id"] and p["owner_org_id"] == org_id:
        return "owner"          # they commissioned it and spent the credit
    part = participant(pulse_id, org_id, conn)
    if part and part["submission_complete"]:
        return "participant"    # give-to-get
    row = conn.execute("SELECT 1 FROM pulse_report_access WHERE pulse_id=? AND org_id=?",
                       (pulse_id, org_id)).fetchone()
    return "purchased" if row else None


def grant_report_access(pulse_id, org_id, granted_by, reason="", amount_pence=None, conn=None):
    conn = conn or get_conn()
    conn.execute(
        "INSERT INTO pulse_report_access(pulse_id, org_id, amount_pence, reason, granted_by) "
        "VALUES (?,?,?,?,?) ON CONFLICT(pulse_id, org_id) DO UPDATE SET "
        "amount_pence=excluded.amount_pence, reason=excluded.reason, granted_by=excluded.granted_by",
        (pulse_id, org_id, amount_pence, (reason or "").strip(), granted_by))
    conn.commit()


def revoke_report_access(pulse_id, org_id, conn=None):
    conn = conn or get_conn()
    conn.execute("DELETE FROM pulse_report_access WHERE pulse_id=? AND org_id=?",
                 (pulse_id, org_id))
    conn.commit()


def report_access_list(pulse_id=None, org_id=None, conn=None):
    conn = conn or get_conn()
    where, args = [], []
    if pulse_id:
        where.append("a.pulse_id=?"); args.append(pulse_id)
    if org_id:
        where.append("a.org_id=?"); args.append(org_id)
    sql = ("SELECT a.*, p.name AS pulse_name, p.status FROM pulse_report_access a "
           "JOIN pulses p ON p.pulse_id=a.pulse_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return [dict(r) for r in conn.execute(sql + " ORDER BY a.granted_at DESC", args)]


def pulse_report(pulse_id, conn=None, real_viewer=False, cut_org_ids=None):
    """Aggregate the pulse's questions over ITS cohort only — through the
    SAME engine entry point the core uses (aggregate_question_for_orgs), so
    calculation, suppression (n>=5) and matrix/multi handling are identical
    by construction.

    cut_org_ids narrows the cohort to a peer cut (the same selector the benchmark uses).
    The v1 note here said whole-cohort only, because an opt-in cohort would suppress every
    cut. Measured on a 120-organisation cohort (2026-08-20) that no longer holds — 34 of 39
    cuts clear the 5-organisation floor — so cuts are served, and any cut that does fall
    under the floor suppresses exactly as it does on the benchmark."""
    conn = conn or get_conn()
    p = get_pulse(pulse_id, conn)
    qs = pulse_questions(p)
    cohort = {r["org_id"] for r in conn.execute(
        "SELECT org_id FROM pulse_participants WHERE pulse_id=? AND submission_complete=1", (pulse_id,))}
    if cut_org_ids is not None:
        cohort &= set(cut_org_ids)
    # PULSE-1 (ruled 2026-08-08): SEEDED_PULSE_VISIBILITY = seed/demo/staff only.
    # A REAL member sees REAL responses only — seeded pulse responses are
    # fabricated answers to a commissioned question, not a market reference; the
    # give-to-get logic that justifies the benchmark panel does not reach them.
    # Below the participant floor the report reads "not yet enough responses".
    # Seed/staff/demo viewers see the full cohort (the demo keeps working —
    # Thornbridge is seed-class). Same source rule as the P1-AB partition.
    if real_viewer:
        real = {r["org_id"] for r in conn.execute(
            "SELECT org_id FROM orgs WHERE source NOT IN ('seed','staff','demo')")}
        cohort &= real
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
    summary += ("Results below are the whole cohort across %d question%s%s. As on the core "
                "benchmark, nothing is shown where fewer than 5 organisations answered." %
                (shown, "" if shown == 1 else "s",
                 "" if shown == total else " of %d" % total))
    # A finding is what the numbers SHOW. Walking the questions in order and appending each
    # one's top answer produced five interchangeable table rows — the shape never came first,
    # and questions 6 and 7 were never reached however striking they were (David 2026-08-20).
    # Score each result for how notable it is, then say what it is.
    scored = []
    for q in qs:
        blk = q.get("block") or {}
        opts = sorted((blk.get("options") or []), key=lambda o: o.get("pct") or 0, reverse=True)
        # Keep the question INTACT and interrogative. Lower-casing it and splicing it into
        # a prepositional phrase produced "divides on at peak season what share…" and
        # "On by what percentage does…" — the questions are full sentences, not noun
        # phrases, so the finding follows the question rather than swallowing it.
        qn = q["title"].strip().rstrip("?") + "?"
        nq = blk.get("n", n)
        if opts:
            top = opts[0]
            tp = top.get("pct") or 0
            second = opts[1] if len(opts) > 1 else None
            sp = (second.get("pct") or 0) if second else 0
            if tp >= 75:
                score = tp
                text = ("%s \u2014 near-unanimous: %s%% answered \u201c%s\u201d (n=%s)."
                        % (qn, tp, top.get("label", ""), nq))
            elif tp >= 55:
                score = tp - 10
                text = ("%s \u2014 a clear majority, %s%%, answered \u201c%s\u201d (n=%s)."
                        % (qn, tp, top.get("label", ""), nq))
            elif second is not None and abs(tp - sp) <= 8:
                score = 70 - abs(tp - sp)
                text = ("%s \u2014 the cohort divides, \u201c%s\u201d %s%% against "
                        "\u201c%s\u201d %s%% (n=%s)."
                        % (qn, top.get("label", ""), tp, second.get("label", ""), sp, nq))
            else:
                score = 45 - tp
                text = ("%s \u2014 no answer dominates; the most common, \u201c%s\u201d, "
                        "reaches only %s%% (n=%s)." % (qn, top.get("label", ""), tp, nq))
        elif blk.get("p50") is not None:
            med = _fmt_num(blk["p50"], q.get("unit"))
            p25, p75 = blk.get("p25"), blk.get("p75")
            if p25 is not None and p75 is not None:
                score = 40
                text = ("%s \u2014 the median is %s, with the middle half of the cohort "
                        "between %s and %s (n=%s)."
                        % (qn, med, _fmt_num(p25, q.get("unit")),
                           _fmt_num(p75, q.get("unit")), nq))
            else:
                score = 30
                text = "%s \u2014 the cohort median is %s (n=%s)." % (qn, med, nq)
        else:
            continue
        scored.append((score, text))
    scored.sort(key=lambda t: -t[0])
    return {"summary": summary, "key_findings": [t[1] for t in scored[:5]],
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


# ------------------------------------------------------ card enrichment (2026-08-11)
# A pulse's topic identity is DERIVED, not stored: a keyword read of name+description
# picks a glyph so the Explore cards look distinct and legible at a glance — no schema
# column, no builder field, no backfill. Every medallion is a single blue tile
# (one-blue law): the topic changes the SHAPE, never the colour. First rule wins, so
# specific subjects are ordered before broad ones; an unmatched pulse falls to "zap".
# (Upgrade path if this ever needs to be exact: a stored `topic` set at lumi review.)
PULSE_TOPIC_RULES = (
    ("wellbeing", "heart",   ("wellbeing", "wellness", "mental health", "burnout", "stress", "resilience")),
    ("working",   "clock",   ("four-day", "4-day", "four day", "hybrid", "remote", "flexible working",
                              "working week", "working hours", "wfh", "return to office", "in-office")),
    ("people",    "users",   ("hiring", "recruit", "retention", "attrition", "turnover", "talent",
                              "headcount", "onboarding", "diversity", "inclusion", "belonging", "dei")),
    ("tech",      "sparkle", ("artificial intelligence", " ai ", "automation", "machine learning", "digital")),
    ("benefits",  "award",   ("pension", "insurance", "healthcare", "medical", "annual leave",
                              "parental leave", "holiday", "perk", "allowance", "benefit")),
    ("pay",       "coins",   ("pay", "salary", "salaries", "wage", "reward", "compensation",
                              "bonus", "transparency", "gender pay", "pay gap")),
    ("policy",    "shield",  ("compliance", "policy", "regulation", "directive", "legislation",
                              "legal", "statutory", "mandate")),
)


def topic_for(name, description):
    """(topic, icon) derived from a pulse's name + description; falls to ('general', 'zap')."""
    hay = " " + ((name or "") + " " + (description or "")).lower() + " "
    for topic, icon, kws in PULSE_TOPIC_RULES:
        if any(k in hay for k in kws):
            return topic, icon
    return "general", "zap"


def pulse_teaser(report):
    """A compact one-line finding for a participated pulse's card — the strongest single
    figure from the FIRST non-suppressed question. Returns {stat, on} or None. Reads a
    report already built by pulse_report(); never touches the core firewall."""
    for q in report.get("questions", []):
        blk = q.get("block") or {}
        if blk.get("suppressed"):
            continue
        opts = blk.get("options") or []
        if opts:
            top = max(opts, key=lambda o: o.get("pct", 0) or 0)
            return {"stat": u"%s%% chose “%s”" % (top.get("pct", 0), top.get("label", "")),
                    "on": q.get("title") or q.get("text") or ""}
        if blk.get("p50") is not None:
            return {"stat": u"Median %s" % _fmt_num(blk["p50"], q.get("unit")),
                    "on": q.get("title") or q.get("text") or ""}
    return None


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
