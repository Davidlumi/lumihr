"""lumi platform server.

Tenancy model: SessionMiddleware resolves the session cookie ONCE per request
and attaches user/org to request.state. No route ever accepts an org_id from
the client; all data access keys off request.state. Share-token requests get a
restricted read-only context bound to the sharing org. Raw answers are only
ever serialised for the owning org; peer data leaves the server only as
suppression-checked aggregates with all internal ("_"-prefixed) keys stripped.

Run:  python3 -m uvicorn app:app --port 8060
"""
import csv
import io
import json
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import auth as auth_lib
import hashlib

import claude_api
import pulses as pulses_mod
import releases
import retrieval
from db import get_conn, init_schema, j, uj, get_meta, set_meta
from library import load_questions, slugify
import positions as pos
import peer_twin
from aggregate import run_snapshot, coerce_number, score_polarity, SUPPRESSION_FLOOR, matrix_value

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
CURRENT_SNAPSHOT = 1

# ------------------------------------------------------- insight-unlock gate
# THE single place to tune the gate. Tiers are gone: every reward question is
# just a question. Completion is measured against the BASIS set:
#   required (default) — the library's is_required questions (82 in reward
#       scope), which by definition apply to every organisation. Safe: a
#       member who answers everything that applies always reaches the gate.
#   all — every visible question (~180). Unsafe with many N/A-able questions;
#       kept only as a tunable option.
# Selecting "Not applicable" / "Don't know" IS answering — it counts. Only
# genuinely skipped questions are incomplete. A matrix counts as ONE question.
COMPLETION_BASIS = os.environ.get("LUMI_COMPLETION_BASIS", "required")  # required | all
# Hero signals (market position + practice prevalence). The at-market band is
# percentile bounds on the favourable-adjusted scale: the default quartile band
# (25-75) is the honest default but reads amber-heavy; tune via env on real
# data (e.g. "40-60" for a sharper hero).
_band = os.environ.get("LUMI_MARKET_BAND", "25-75").split("-")
MARKET_BAND_LOW, MARKET_BAND_HIGH = float(_band[0]), float(_band[1])
DOMAIN_MIN_POLARISED = int(os.environ.get("LUMI_DOMAIN_MIN_POLARISED", "5"))
VERDICT_MARGIN = float(os.environ.get("LUMI_VERDICT_MARGIN", "0.15"))
UNCOMMON_PCT = float(os.environ.get("LUMI_UNCOMMON_PCT", "20"))

# AI metric commentary. Default ON: the adversarial QA gate (qa_commentary.py)
# passed clean on 2026-06-11 (40/40). Set LUMI_AI_COMMENTARY=off to hide it;
# re-run the gate before re-enabling after any change to the generator,
# validator or payload builder — and after configuring ANTHROPIC_API_KEY.
AI_COMMENTARY = os.environ.get("LUMI_AI_COMMENTARY", "on").lower() == "on"
# Per-surface kill switches for the other AI surfaces (delivery-audit D3):
# both ship on (they have grounded prompts + deterministic fallbacks), but can
# be cut off independently without a deploy if a trust issue appears.
AI_ANALYST = os.environ.get("LUMI_AI_ANALYST", "on").lower() == "on"
AI_PULSE = os.environ.get("LUMI_AI_PULSE", "on").lower() == "on"
AI_BOARDPACK = os.environ.get("LUMI_AI_BOARDPACK", "on").lower() == "on"
COMPLETION_THRESHOLD = float(os.environ.get("LUMI_COMPLETION_THRESHOLD", "0.90"))

# ---------------------------------------------------------------- launch focus
# lumi launches as a reward benchmarking product. The other nine areas stay
# fully built (data, aggregation, scoring untouched) and are hidden from every
# user-facing surface by THIS flag alone. Set LUMI_ACTIVE_SUPERPOWERS=all (or a
# comma list) to re-show them — nothing else needs touching.
_asp = os.environ.get("LUMI_ACTIVE_SUPERPOWERS", "Reward").strip()
ACTIVE_SUPERPOWERS = [] if _asp.lower() in ("", "all", "*") else [x.strip() for x in _asp.split(",") if x.strip()]


CLOCK_DAYS = 30
TARGET_PCT = COMPLETION_THRESHOLD * 100

# Reduced (post-deadline) teaser: the first two metrics of each section stay
# fully visible so the member remembers the value; the rest gate behind
# completing their submission. Computed once per process from the library.
_reduced_sample = None


def reduced_sample_ids():
    global _reduced_sample
    if _reduced_sample is None:
        per_section = {}
        ids = set()
        for qid, q in visible_questions().items():
            key = q.sub_power or "general"
            per_section.setdefault(key, 0)
            if per_section[key] < 2:
                per_section[key] += 1
                ids.add(qid)
        _reduced_sample = ids
    return _reduced_sample


def org_unlocked(conn, org, completion=None):
    """STICKY unlock (versioning, 2026-06-12): once a member earns their
    unlock it is stored (insights_unlocked_at + the release they unlocked
    under) and NEVER revoked by a release. A release that adds required
    questions can therefore never re-lock anyone — the new questions surface
    as 'new to complete', access stays. Live completion is only consulted
    until the first unlock, and can only ever ADD the stamp."""
    if org["insights_unlocked_at"]:
        return True
    if completion is None:
        completion = completion_pct(conn, org)
    unlocked = bool(org["submission_complete"]) or completion >= TARGET_PCT
    if unlocked:
        rel = releases.current_release(conn)
        conn.execute("UPDATE orgs SET insights_unlocked_at=datetime('now'), unlocked_release=? "
                     "WHERE org_id=? AND insights_unlocked_at IS NULL",
                     (rel["release_id"] if rel else None, org["org_id"]))
        conn.commit()
    return unlocked


def contribution_state(conn, org):
    """The day-one model: explore freely for CLOCK_DAYS; hitting the
    completion target unlocks insights; past the deadline unmet, the benchmark reduces
    to a teaser until the submission is completed. Co-op contribution, never
    a paywall.

    The clock starts when the Admin accepts the Data Contribution Terms —
    the moment the org can actually contribute — NOT at signup or first
    login, so setup time never eats into the 30 days."""
    completion = completion_pct(conn, org)
    unlocked = org_unlocked(conn, org, completion)
    terms = org_data_terms(conn, org["org_id"])
    clock_start = org["clock_start"]
    days_left = None
    if clock_start and not unlocked:
        try:
            started = datetime.strptime(clock_start[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            started = datetime.utcnow()
        days_left = max(0, CLOCK_DAYS - (datetime.utcnow() - started).days)
    return {
        "core_pct": completion,
        "target_pct": TARGET_PCT,
        "insights_unlocked": unlocked,
        "terms_accepted": terms is not None,
        "clock_started": bool(clock_start),
        "clock_start": clock_start,
        "days_left": days_left,
        "reduced": bool(clock_start) and (not unlocked) and days_left <= 0,
    }


def maybe_send_clock_reminder(conn, org, state):
    """Gentle reminders at 7 and 1 days left. Triggers are stored so email
    fires automatically once SMTP is configured; in-app banners are driven
    by days_left regardless."""
    if state["insights_unlocked"] or state["days_left"] is None:
        return
    due = "7d" if state["days_left"] <= 7 and state["days_left"] > 1 else \
          "1d" if state["days_left"] <= 1 else None
    if not due:
        return
    sent = uj(org["reminders_json"], [])
    if due in sent:
        return
    sent.append(due)
    conn.execute("UPDATE orgs SET reminders_json=? WHERE org_id=?", (j(sent), org["org_id"]))
    conn.commit()
    admins = [r["email"] for r in conn.execute(
        "SELECT email FROM users WHERE org_id=? AND role='admin'", (org["org_id"],))]
    send_notification(
        "lumi: %s left to unlock your insights" % ("7 days" if due == "7d" else "1 day"),
        "Hello %s,\n\nYour reward benchmark is waiting — you're %s%% of the way to unlocking "
        "your insights (£ opportunities, board pack and biggest gaps). Complete your reward "
        "questions in the next %s to unlock them.\n\n— lumi (to: %s)"
        % (org["name"], state["core_pct"], "7 days" if due == "7d" else "day", ", ".join(admins)))


TRONC_SECTORS = {"Hospitality, Leisure & Travel", "Retail & Consumer Goods"}


def org_visible_questions(org):
    """The member-facing question set for ONE organisation: the live core
    minus sector-module metrics the org isn't eligible for. 2026.1: the 5
    tronc/tips metrics are a hospitality module — shown to hospitality/retail
    organisations, hidden otherwise. Module questions are never is_required
    (invariant, asserted by qa_release) so the unlock gate is org-independent."""
    qs = visible_questions()
    ind = org["industry"] if org is not None else None
    if ind in TRONC_SECTORS:
        return qs
    return {qid: q for qid, q in qs.items() if not q.module}


def visible_questions():
    """The question set every user-facing route serves. THE focus filter.
    Retired questions (versioning, 2026-06-12) leave the live member
    experience but stay in the library and in release history — historical
    benchmarks that used them still resolve."""
    qs = load_questions()
    out = {qid: q for qid, q in qs.items()
           if getattr(q, "status", "active") != "retired"}
    if not ACTIVE_SUPERPOWERS:
        return out
    return {qid: q for qid, q in out.items() if q.superpower in ACTIVE_SUPERPOWERS}

app = FastAPI(title="lumi", docs_url=None, redoc_url=None)


# ----------------------------------------------------------- tenancy layer ---

class SessionMiddleware(BaseHTTPMiddleware):
    """Resolves auth once per request. Routes use request.state.{user,org} only."""

    async def dispatch(self, request, call_next):
        request.state.user = None
        request.state.org = None
        token = request.cookies.get(auth_lib.COOKIE_NAME)
        if token:
            user = auth_lib.get_session_user(token)
            if user:
                conn = get_conn()
                org = conn.execute("SELECT * FROM orgs WHERE org_id=?", (user["org_id"],)).fetchone()
                request.state.user = dict(user)
                request.state.org = dict(org) if org else None
        return await call_next(request)


app.add_middleware(SessionMiddleware)


def require_user(request):
    if request.state.user is None or request.state.org is None:
        raise HTTPException(401, "Not signed in")
    return request.state.user, request.state.org


def require_admin(request):
    user, org = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Admin role required")
    return user, org


def require_editor(request):
    """Admin or Contributor — the roles allowed to submit/edit the org's data."""
    user, org = require_user(request)
    if user["role"] not in ("admin", "contributor"):
        raise HTTPException(403, "Your role (Viewer) can see the benchmark but not edit data. "
                                 "Ask your Admin for the Contributor role if you need to submit.")
    return user, org


# ----------------------------------------------------------- layered terms --
PLATFORM_TERMS_VERSION = "1.0-draft"
DATA_TERMS_VERSION = "1.0-draft"
LEGAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "legal")
LEGAL_FILES = {
    "platform": "platform-terms-v1.0.md",
    "data_contribution": "data-contribution-terms-v1.0.md",
    "dpa": "data-sharing-agreement-dpa-v1.0-draft.md",
}


def legal_text(kind):
    with open(os.path.join(LEGAL_DIR, LEGAL_FILES[kind]), encoding="utf-8") as f:
        return f.read()


def record_acceptance(conn, org_id, user_id, kind, version):
    conn.execute("INSERT INTO terms_acceptances(org_id, user_id, kind, version) VALUES (?,?,?,?)",
                 (org_id, user_id, kind, version))
    conn.commit()


def org_data_terms(conn, org_id):
    """The org-level Data Contribution agreement (latest acceptance), or None."""
    return conn.execute(
        "SELECT t.*, u.email AS user_email, u.display_name AS user_name "
        "FROM terms_acceptances t LEFT JOIN users u ON u.user_id = t.user_id "
        "WHERE t.org_id=? AND t.kind='data_contribution' ORDER BY t.accepted_at DESC, t.id DESC LIMIT 1",
        (org_id,)).fetchone()


def require_data_terms(conn, org):
    """Submission routes are blocked until the org's Admin has accepted the
    Data Contribution Terms. Seed orgs never hit this (no users)."""
    if org_data_terms(conn, org["org_id"]) is None:
        raise HTTPException(403, "Review and accept the Data Contribution Terms to begin — "
                                 "your organisation's Admin accepts them once, on the Submit data page.")


def make_entitled(user, org):
    # Tiers are removed: every reward question is available to every member.
    # The lumi_tier library column still exists but is never consulted.
    return lambda q: True


# ------------------------------------------------------------- sanitisation ---

def strip_internal(obj):
    """Recursively remove '_'-prefixed keys (raw peer value lists never ship)."""
    if isinstance(obj, dict):
        return {k: strip_internal(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_internal(x) for x in obj]
    return obj


def histogram(values, bins=12):
    if not values:
        return None
    lo, hi = min(values), max(values)
    if hi == lo:
        return {"min": lo, "max": hi, "bins": [len(values)]}
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    return {"min": lo, "max": hi, "bins": counts}


# ----------------------------------------------------------- data assembly ---

_payload_cache = {"snapshot": None, "data": None}


def payloads():
    if _payload_cache["snapshot"] != CURRENT_SNAPSHOT or _payload_cache["data"] is None:
        _payload_cache["data"] = pos.load_payloads(get_conn(), CURRENT_SNAPSHOT)
        _payload_cache["snapshot"] = CURRENT_SNAPSHOT
    return _payload_cache["data"]


def invalidate_payloads():
    _payload_cache["data"] = None
    peer_twin.invalidate_twin_caches()


def parse_cut(request, org):
    dim = request.query_params.get("cut", "all")
    value = request.query_params.get("cut_value")
    if dim not in ("all", "industry", "fte_band", "twin", "group"):
        dim = "all"
    cut = {"dim": dim, "value": value}
    if dim == "group":
        row = get_conn().execute(
            "SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
            (value or "", org["org_id"])).fetchone()
        if row is None:
            # another org's group id (or a stale one) never resolves — all peers
            return {"dim": "all", "value": None}
        cut["label"] = row["name"]
        cut["criteria"] = uj(row["criteria_json"], {})
    if dim == "industry" and not value:
        cut["value"] = org.get("industry")
    if dim == "fte_band" and not value:
        cut["value"] = org.get("fte_band")
    return cut


def twin_blocks_if_needed(conn, org, cut):
    """Bespoke peer blocks: Peer Twin or a custom group. Both run through the
    identical engine path; a custom group below the suppression floor returns
    None blocks per question (no aggregation ran), so every metric renders the
    suppressed state — never data, never a partial peek."""
    if cut.get("dim") == "group":
        blocks, match = peer_twin.group_blocks(conn, cut.get("criteria") or {}, CURRENT_SNAPSHOT)
        cut["match_count"] = match
        if blocks is None:
            cut["too_small"] = True
            return {}  # every question resolves to a suppressed block
        return blocks
    if cut.get("dim") != "twin":
        return None
    tb = peer_twin.twin_blocks(conn, org["org_id"], CURRENT_SNAPSHOT)
    if tb is None:
        raise HTTPException(400, "Peer Twin isn't available for your organisation yet — it needs your firmographic profile.")
    return tb


def assemble_card(q, p, org, org_answers, cut, twin_blocks_by_q, entitled):
    """Everything one benchmark card needs, fully sanitised."""
    locked = not entitled(q)
    tb = (twin_blocks_by_q or {}).get(q.id)
    blk, cut_label = pos.block_for(p, cut, tb)
    base = {
        "id": q.id,
        "title": q.display_title,
        "question_text": q.text,
        "help_text": q.help_text,
        "definition": q.definition,
        "superpower": q.superpower,
        "subpower": q.sub_power,
        "sub_power_order": q.sub_power_order,
        "type": q.type,
        "category": q.category,
       
        "locked": locked,
        "chart_default": q.default_chart_type,
        "unit": q.unit_block(),
        "polarity": q.polarity,
        "cut": {"dim": cut["dim"], "value": cut.get("value"), "label": cut_label},
        "n": (blk or {}).get("n", 0),
        "suppressed": bool(pos.is_suppressed(blk)),
        "movement": None,  # vs-last-period slot: populated once a second snapshot exists
    }
    if locked:
        return base
    raw = org_answers.get((q.id, ""))
    base["answered"] = any(k[0] == q.id for k in org_answers)

    if q.type in ("numeric",):
        base["block"] = strip_internal(blk) if not base["suppressed"] else None
        if not base["suppressed"]:
            base["histogram"] = histogram(blk.get("_values"))
        v = coerce_number(raw)
        if v is not None:
            you = {"value": v, "display": pos.fmt_value(v, q.unit_block())}
            if not base["suppressed"]:
                r = pos.percentile_rank(blk["_values"], v)
                you["percentile"] = round(r, 1)
                it = pos._item(q, None, v, r, blk, cut_label, "value")
                base["readout"] = pos.readout_numeric(it)
                base["favourable"] = it["favourable"]
            base["you"] = you
        if base["suppressed"]:
            base["readout"] = pos.SUPPRESSED_COPY

    elif q.type in ("single_select", "yes_no", "multi_select"):
        base["block"] = strip_internal(blk) if not base["suppressed"] else None
        if raw is not None:
            base["you"] = {"label": raw,
                           "labels": [t.strip() for t in raw.split(";")] if q.type == "multi_select" else [raw]}
        if q.type == "multi_select":
            base["readout"] = pos.SUPPRESSED_COPY if base["suppressed"] else None
        else:
            base["readout"] = pos.readout_select(q, raw, blk, cut_label)
        sc_blk, _ = pos.score_block_for(p, cut, tb)
        if q.is_scored and raw is not None and not pos.is_suppressed(sc_blk):
            s = pos.score_answer_safe(q, raw)
            if s is not None:
                base["score"] = {
                    "you": round(s, 1),
                    "percentile": round(pos.percentile_rank(sc_blk["_scores"], s), 1),
                    "peer_p50": sc_blk.get("p50"),
                    "polarity": score_polarity(q),
                }

    elif q.type == "matrix":
        rows = []
        for row in p.get("matrix_rows", []):
            rblk, _ = pos.matrix_row_block_for(row, cut, tb)
            raw_v = org_answers.get((q.id, row["row_id"]))
            v = matrix_value(raw_v)   # same tolerant parser as the peer side ("1.5x")
            r_out = {
                "row_id": row["row_id"], "label": row["label"],
                "suppressed": bool(pos.is_suppressed(rblk)),
                "block": None if pos.is_suppressed(rblk) else strip_internal(rblk),
            }
            categorical = bool(rblk) and rblk.get("kind") == "select"
            if categorical and raw_v not in (None, ""):
                you = {"label": str(raw_v).strip(), "display": str(raw_v).strip()}
                if not pos.is_suppressed(rblk):
                    mine = next((o for o in rblk.get("options", []) if o["label"] == you["label"]), None)
                    if mine:
                        you["share_pct"] = mine["pct"]
                r_out["you"] = you
            elif v is not None:
                r_out["you"] = {"value": v, "display": pos.fmt_value(v, q.unit_block())}
                if not pos.is_suppressed(rblk) and "_values" in rblk:
                    r_out["you"]["percentile"] = round(pos.percentile_rank(rblk["_values"], v), 1)
            rows.append(r_out)
        base["matrix_rows"] = rows
        vis = [r for r in rows if not r["suppressed"]]
        if vis:
            you_rows = [r for r in vis if "you" in r and "percentile" in r["you"]]
            if you_rows:
                avg = sum(r["you"]["percentile"] for r in you_rows) / len(you_rows)
                base["readout"] = ("Across the %d comparable levels, your typical position is P%d (%s)."
                                   % (len(you_rows), int(round(avg)), cut_label))
        if base["suppressed"]:
            base["readout"] = pos.SUPPRESSED_COPY
    return base


from aggregate import score_answer as _score_answer  # noqa: E402
pos.score_answer_safe = _score_answer


# ================================================================== AUTH ====

@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    email = (body.get("email") or "").lower().strip()
    ip = request.client.host if request.client else "?"
    if auth_lib.rate_limited("login:%s" % email) or auth_lib.rate_limited("login-ip:%s" % ip):
        raise HTTPException(429, "Too many attempts — please wait a few minutes and try again.")
    user = auth_lib.find_user(email)
    if not user or not auth_lib.verify_password(body.get("password") or "", user["pw_hash"]):
        raise HTTPException(401, "That email and password don't match our records.")
    token = auth_lib.create_session(user["user_id"])
    resp = JSONResponse({"ok": True})
    resp.set_cookie(auth_lib.COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=auth_lib.SESSION_TTL_DAYS * 86400)
    return resp


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(auth_lib.COOKIE_NAME)
    if token:
        auth_lib.destroy_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth_lib.COOKIE_NAME)
    return resp


@app.post("/api/auth/register")
async def register(request: Request):
    """New member organisation sign-up (tier: core)."""
    body = await request.json()
    for f in ("org_name", "email", "password"):
        if not body.get(f):
            raise HTTPException(400, "Missing %s" % f)
    if len(body["password"]) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if body.get("accept_platform_terms") is not True:
        raise HTTPException(400, "Please accept the Platform Terms of Use to create your account.")
    conn = get_conn()
    nn = re.sub(r"[^a-z0-9]", "", body["org_name"].lower())
    if conn.execute("SELECT 1 FROM orgs WHERE normalized_name=?", (nn,)).fetchone():
        raise HTTPException(400, "An organisation with that name already exists — ask your admin for an invite.")
    if auth_lib.find_user(body["email"]):
        raise HTTPException(400, "That email already has an account.")
    org_id = str(uuid.uuid4())
    # founding members: first year free with full access — the contribution
    # clock is about data, never payment (day-one experience brief).
    # clock_start stays NULL until the Admin accepts the Data Contribution
    # Terms — setup time must not eat into the 30 days.
    conn.execute(
        "INSERT INTO orgs(org_id, name, normalized_name, source, tier_entitlement, classified) "
        "VALUES (?,?,?,'signup','full',0)", (org_id, body["org_name"].strip(), nn))
    conn.commit()
    uid = auth_lib.create_user(org_id, body["email"], body["password"], "admin",
                               body.get("display_name"))
    record_acceptance(conn, org_id, uid, "platform", PLATFORM_TERMS_VERSION)
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(auth_lib.COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=auth_lib.SESSION_TTL_DAYS * 86400)
    return resp


@app.post("/api/auth/request-reset")
async def request_reset(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip()
    if auth_lib.rate_limited("reset:%s" % email.lower()):
        raise HTTPException(429, "Too many attempts — please wait a few minutes.")
    user = auth_lib.find_user(email)
    if user:
        token = auth_lib.create_reset(user["user_id"])
        # In production this is an email; here the tokenised link is console-logged.
        print("\n[lumi] PASSWORD RESET LINK for %s:\n       http://localhost:8060/#/reset/%s\n" % (email, token))
    return {"ok": True, "message": "If that email has an account, a reset link has been issued (see server console)."}


@app.post("/api/auth/reset")
async def do_reset(request: Request):
    body = await request.json()
    row = auth_lib.get_valid_reset(body.get("token") or "")
    if not row:
        raise HTTPException(400, "That reset link has expired or already been used.")
    if len(body.get("password") or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    conn = get_conn()
    conn.execute("UPDATE users SET pw_hash=? WHERE user_id=?",
                 (auth_lib.hash_password(body["password"]), row["user_id"]))
    conn.execute("UPDATE password_resets SET used_at=datetime('now') WHERE token=?", (row["token"],))
    conn.commit()
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    completion = completion_pct(conn, org)
    snaps = [dict(r) for r in conn.execute("SELECT snapshot_id, snapshot_date, collection_window, status FROM snapshots ORDER BY snapshot_id")]
    vis = org_visible_questions(org)
    contrib = contribution_state(conn, org)
    # (sticky-unlock stamping now happens centrally in org_unlocked)
    maybe_send_clock_reminder(conn, org, contrib)
    return {
        "contribution": contrib,
        "features": {"commentary": AI_COMMENTARY, "analyst": AI_ANALYST, "boardpack": AI_BOARDPACK, "pulse_ai": AI_PULSE},
        "scope": {"superpowers": ACTIVE_SUPERPOWERS or sorted({q.superpower for q in vis.values()}),
                  "focused": bool(ACTIVE_SUPERPOWERS),
                  "question_count": len(vis)},
        "user": {"email": user["email"], "role": user["role"], "display_name": user["display_name"]},
        "org": {"name": org["name"], "industry": org["industry"], "subsector": org["subsector"],
                "fte_band": org["fte_band"], "hq_region": org["hq_region"],
                "ownership_type": org["ownership_type"], "classified": bool(org["classified"]),
                "profile_rich_complete": all(org.get(f) for f in PROFILE_RICH),
                "tier_entitlement": org["tier_entitlement"], "source": org["source"],
                "submission_complete": bool(org["submission_complete"]),
                "data_terms": (lambda t: {
                    "accepted": t is not None,
                    "accepted_by": t and (t["user_name"] or t["user_email"] or "a former Admin"),
                    "accepted_at": t and t["accepted_at"],
                    "version": t and t["version"],
                })(org_data_terms(conn, org["org_id"]))},
        "completion_pct": completion,
        "benchmark_unlocked": org_unlocked(conn, org, completion),
        "peer_pool": get_meta("peer_pool", {}),
        "snapshots": snaps,
    }




# ==================================================================== TEAM ===

@app.get("/api/team")
async def team(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    users = [{"email": r["email"], "role": r["role"], "display_name": r["display_name"],
              "created_at": r["created_at"]}
             for r in conn.execute("SELECT * FROM users WHERE org_id=? ORDER BY created_at", (org["org_id"],))]
    invites = [{"email": r["email"], "role": r["role"], "expires_at": r["expires_at"],
                "token": r["token"], "used": r["used_at"] is not None}
               for r in conn.execute(
                   "SELECT * FROM invites WHERE org_id=? AND used_at IS NULL AND expires_at > datetime('now')",
                   (org["org_id"],))]
    return {"users": users, "invites": invites if user["role"] == "admin" else []}


@app.post("/api/team/invite")
async def invite(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    email = (body.get("email") or "").strip()
    # Admins are made by promotion after joining, never by invite
    role = body.get("role") if body.get("role") in ("contributor", "viewer") else "viewer"
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    if auth_lib.find_user(email):
        raise HTTPException(400, "That email already has a lumi account.")
    token = auth_lib.create_invite(org["org_id"], email, role, user["user_id"])
    link = "http://localhost:8060/#/invite/%s" % token
    print("\n[lumi] TEAM INVITE for %s (%s at %s):\n       %s\n" % (email, role, org["name"], link))
    return {"ok": True, "link": link, "expires_days": auth_lib.INVITE_TTL_DAYS}


@app.put("/api/team/role")
async def change_role(request: Request):
    """Admin promotes/demotes a member. An org can never be left without an
    Admin: demoting the sole Admin is blocked with a clear message."""
    user, org = require_admin(request)
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    role = body.get("role")
    if role not in ("admin", "contributor", "viewer"):
        raise HTTPException(400, "Role must be admin, contributor or viewer.")
    conn = get_conn()
    target = conn.execute("SELECT * FROM users WHERE org_id=? AND lower(email)=?",
                          (org["org_id"], email)).fetchone()
    if target is None:
        raise HTTPException(404, "No member with that email in your organisation.")
    if target["role"] == "admin" and role != "admin":
        admins = conn.execute("SELECT COUNT(*) c FROM users WHERE org_id=? AND role='admin'",
                              (org["org_id"],)).fetchone()["c"]
        if admins <= 1:
            raise HTTPException(400, "Promote another Admin before removing yourself — "
                                     "your organisation must always have at least one Admin.")
    conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, target["user_id"]))
    conn.commit()
    return {"ok": True, "email": target["email"], "role": role}


@app.delete("/api/team/member")
async def remove_member(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    conn = get_conn()
    target = conn.execute("SELECT * FROM users WHERE org_id=? AND lower(email)=?",
                          (org["org_id"], email)).fetchone()
    if target is None:
        raise HTTPException(404, "No member with that email in your organisation.")
    if target["role"] == "admin":
        admins = conn.execute("SELECT COUNT(*) c FROM users WHERE org_id=? AND role='admin'",
                              (org["org_id"],)).fetchone()["c"]
        if admins <= 1:
            raise HTTPException(400, "Promote another Admin before removing yourself — "
                                     "your organisation must always have at least one Admin.")
    try:
        # org artifacts the member created stay with the org — reassigned to
        # the acting admin so FK constraints hold. The terms-acceptance log is
        # deliberately untouched: the org's agreement survives staff turnover.
        for table in ("invites", "shares", "board_packs"):
            conn.execute("UPDATE %s SET created_by=? WHERE created_by=?" % table,
                         (user["user_id"], target["user_id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (target["user_id"],))
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (target["user_id"],))
        conn.execute("DELETE FROM pinned_views WHERE org_id=? AND user_id=?",
                     (org["org_id"], target["user_id"]))
        conn.execute("DELETE FROM users WHERE user_id=?", (target["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"ok": True, "removed": target["email"]}


@app.delete("/api/team/invite/{token}")
async def revoke_invite(token: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=? AND org_id=?",
                 (token, org["org_id"]))
    conn.commit()
    return {"ok": True}


# ============================================================ LAYERED TERMS ==

# ======================================================== PULSES (Tier 2) ==
# A separate surface riding the SAME engine. Pulse data never pools with core
# data (structural separation — see pulses.py docstring). Fully independent
# of the core unlock gate in both directions.

def _pulse_member_view(conn, p, org):
    part = pulses_mod.participant(p["pulse_id"], org["org_id"], conn)
    n_q = len(uj(p["question_ids_json"], []))
    n_parts = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=? AND submission_complete=1",
                           (p["pulse_id"],)).fetchone()[0]
    return {
        "pulse_id": p["pulse_id"], "name": p["name"], "description": p["description"],
        "status": p["status"], "opens_at": p["opens_at"], "closes_at": p["closes_at"],
        "accepting": pulses_mod.is_accepting(p), "questions": n_q,
        "participants": n_parts, "floor": SUPPRESSION_FLOOR,
        "joined": part is not None, "participated": bool(part and part["submission_complete"]),
    }


@app.get("/api/pulses")
async def list_pulses(request: Request):
    """The member Pulses surface: open (joinable), joined, and closed/archived
    pulses. Draft pulses are INVISIBLE to members."""
    user, org = require_user(request)
    conn = get_conn()
    out = []
    for p in conn.execute("SELECT * FROM pulses WHERE status != 'draft' ORDER BY created_at DESC"):
        out.append(_pulse_member_view(conn, p, org))
    return {"pulses": out}


@app.get("/api/pulses/{pid}")
async def pulse_detail(pid: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    if p["status"] == "draft":
        raise HTTPException(404, "Unknown pulse")   # drafts invisible to members
    view = _pulse_member_view(conn, p, org)
    qs = pulses_mod.pulse_questions(p)
    mine = {}
    for r in conn.execute("SELECT question_id, matrix_row_id, value FROM pulse_responses "
                          "WHERE pulse_id=? AND org_id=?", (pid, org["org_id"])):
        mine[(r["question_id"], r["matrix_row_id"] or "")] = r["value"]
    view["question_list"] = []
    for qid, q in qs.items():
        entry = {"id": qid, "text": q.text, "title": q.display_title,
                 "help_text": q.help_text, "type": q.type,
                 "options": [{"code": o["code"], "label": o["label"]} for o in (q.options or [])],
                 "unit": q.unit_block(), "unit_display_name": q.unit_display_name,
                 "na_allowed": q.type in ("numeric", "matrix"),
                 "matrix": q.matrix if q.type == "matrix" else None,
                 "matrix_rows": [{"row_id": rid, "label": lbl} for rid, lbl in q.matrix_row_defs()],
                 "as_asked_version": q.question_version}
        if q.type == "matrix":
            entry["current"] = {rid: mine.get((qid, rid)) for rid, _l in q.matrix_row_defs()}
        else:
            entry["current"] = mine.get((qid, ""))
        view["question_list"].append(entry)
    # the report: give-to-get scoped to THIS pulse — participants only.
    # Below the floor, participants get the honest holding state (never blank).
    if view["participated"]:
        rep = pulses_mod.pulse_report(pid, conn)
        view["report"] = strip_internal(rep)
    return view


@app.post("/api/pulses/{pid}/join")
async def pulse_join(pid: str, request: Request):
    user, org = require_editor(request)
    try:
        pulses_mod.join_pulse(pid, org["org_id"], get_conn())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.put("/api/pulses/{pid}/response")
async def pulse_response(pid: str, request: Request):
    user, org = require_editor(request)
    body = await request.json()
    qid = body.get("question_id")
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    q = pulses_mod.pulse_questions(p).get(qid)
    if q is None:
        raise HTTPException(404, "That question isn't part of this pulse.")
    value = body.get("value")
    if value is not None and NA_RE.match(str(value).strip() or ""):
        value = NA_CANON
    errors, warnings = validate_answer(q, value if value is not None else "", body.get("matrix_row_id") or "")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    try:
        pulses_mod.save_response(pid, org["org_id"], qid, body.get("matrix_row_id") or "", value, conn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "errors": [], "warnings": warnings}


@app.post("/api/pulses/{pid}/submit")
async def pulse_submit(pid: str, request: Request):
    user, org = require_editor(request)
    try:
        pulses_mod.submit_pulse(pid, org["org_id"], get_conn())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/pulses/{pid}/commentary")
async def pulse_commentary(pid: str, request: Request):
    """Grounded AI commentary on ONE pulse question — same generator, same
    validate_commentary gate as the core, scoped to the pulse cohort.
    LUMI_AI_PULSE kill switch joins the per-surface family."""
    if not AI_PULSE:
        raise HTTPException(403, "AI commentary isn't enabled for pulses.")
    user, org = require_user(request)
    body = await request.json()
    qid = body.get("question_id")
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    part = pulses_mod.participant(pid, org["org_id"], conn)
    if not (part and part["submission_complete"]):
        raise HTTPException(403, "Participate in this pulse to see its commentary.")
    rep = pulses_mod.pulse_report(pid, conn)
    entry = next((x for x in rep["questions"] if x["question_id"] == qid), None)
    if entry is None:
        raise HTTPException(404, "That question isn't part of this pulse.")
    q = pulses_mod.pulse_questions(p).get(qid)
    blk = entry["block"] or {}
    mine = conn.execute("SELECT value FROM pulse_responses WHERE pulse_id=? AND org_id=? AND question_id=? AND matrix_row_id=''",
                        (pid, org["org_id"], qid)).fetchone()
    payload = {
        "metric": entry["title"], "definition": q.definition or "",
        "cut_label": "the %s pulse cohort" % p["name"],
        "n": blk.get("n"), "suppressed": bool(blk.get("suppressed")),
        "polarity": q.polarity, "you": mine and mine[0], "percentile": None,
        "stance": None,
        "illustrative_sample_data": bool(get_meta("synthetic_pool", True)),
    }
    if blk.get("p50") is not None:
        payload["peer_median_display"] = pos.fmt_value(blk["p50"], q.unit_block())
        payload["peer_p25_display"] = pos.fmt_value(blk["p25"], q.unit_block()) if blk.get("p25") is not None else None
        payload["peer_p75_display"] = pos.fmt_value(blk["p75"], q.unit_block()) if blk.get("p75") is not None else None
    if blk.get("options"):
        top = max(blk["options"], key=lambda o: o.get("pct") or 0)
        payload["most_common"] = "\u201c%s\u201d" % top["label"]
        payload["most_common_share"] = top.get("pct")
        if mine and mine[0]:
            m = next((o for o in blk["options"] if o["label"] == mine[0]), None)
            payload["your_answer_peer_share"] = m and m.get("pct")
            payload["you"] = "\u201c%s\u201d" % mine[0]
    res = claude_api.generate_metric_commentary(payload)
    return {"parts": res["parts"], "source": res["source"], "cached": False,
            "caveats": {"illustrative": payload["illustrative_sample_data"]}}


# ============================================ CORE-SET GOVERNANCE / TRENDS ==

@app.get("/api/governance")
async def governance(request: Request):
    """Releases, change log and backlog — read surface for the admin page."""
    user, org = require_admin(request)
    conn = get_conn()
    cur = releases.current_release(conn)
    return {
        "current_release": dict(cur) if cur else None,
        "releases": [dict(r) for r in conn.execute(
            "SELECT * FROM core_releases ORDER BY released_at DESC")],
        "changelog": [dict(r) for r in conn.execute(
            "SELECT * FROM core_changelog ORDER BY id DESC LIMIT 200")],
        "backlog": [dict(r) for r in conn.execute(
            "SELECT * FROM core_backlog ORDER BY id DESC LIMIT 200")],
        "core_size": len(visible_questions()),
        "required_size": len(completion_basis_questions()),
    }


@app.post("/api/governance/backlog")
async def governance_backlog_add(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "A title is needed.")
    releases.add_backlog(title, (body.get("detail") or "").strip(),
                         body.get("source") or "manual", body.get("source_ref"))
    return {"ok": True}


@app.post("/api/governance/ingest-requests")
async def governance_ingest(request: Request):
    user, org = require_admin(request)
    n = releases.ingest_metric_requests(get_conn())
    return {"ok": True, "ingested": n}


@app.post("/api/governance/emergency")
async def governance_emergency(request: Request):
    """The between-release lane. High bar by design: refused without BOTH the
    external trigger that made the question factually wrong AND a sign-off."""
    user, org = require_admin(request)
    body = await request.json()
    try:
        releases.emergency_change(
            body.get("question_id"), body.get("new_version"),
            body.get("external_trigger"), body.get("signed_off_by"),
            bool(body.get("comparability_break")))
    except ValueError as e:
        raise HTTPException(400, str(e))
    load_questions.cache_clear()
    invalidate_payloads()
    return {"ok": True}


@app.get("/api/trend/{qid}")
async def metric_trend(qid: str, request: Request):
    """The metric across data periods — the second reproducibility dimension.
    Comparability breaks are ENFORCED here, not just stored: the series is
    returned as SEGMENTS split at each break, and the client never draws a
    line across a segment boundary."""
    user, org = require_user(request)
    q = org_visible_questions(org).get(qid)
    if q is None:
        raise HTTPException(404, "Unknown metric")
    conn = get_conn()
    rel_order = {r["release_id"]: i for i, r in enumerate(conn.execute(
        "SELECT release_id FROM core_releases ORDER BY released_at"))}
    breaks = releases.comparability_breaks(q.historical_comparability)

    def rel_pos(rid):
        base = (rid or "").replace("+emergency", "")
        pos = rel_order.get(base, -1)
        return pos + (0.5 if rid and rid.endswith("+emergency") else 0)

    points = []
    for s in conn.execute("SELECT * FROM snapshots WHERE status='aggregated' ORDER BY snapshot_id"):
        row = conn.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=? AND question_id=?",
                           (s["snapshot_id"], qid)).fetchone()
        if row is None:
            continue
        p = json.loads(row["payload_json"])
        blk = p.get("all") or {}
        if blk.get("suppressed"):
            continue
        pt = {"snapshot_id": s["snapshot_id"], "period": s["collection_window"],
              "release_id": s["release_id"], "n": blk.get("n")}
        if blk.get("p50") is not None:
            pt["p50"] = blk["p50"]
        elif (p.get("scores") or {}).get("all") and not (p["scores"]["all"] or {}).get("suppressed"):
            pt["p50"] = (p["scores"]["all"] or {}).get("p50")
            pt["kind"] = "score"
        else:
            opts = blk.get("options") or []
            if opts:
                top = max(opts, key=lambda o: o.get("count", 0))
                pt["modal_label"], pt["modal_pct"] = top.get("label"), top.get("pct")
        points.append(pt)

    # split into segments: a break at release R cuts between a period stamped
    # before R and one stamped at/after R — a continuous line across that
    # boundary would splice incomparable data
    segments, cuts = [[]], []
    for i, pt in enumerate(points):
        if i > 0:
            prev_pos, cur_pos = rel_pos(points[i - 1]["release_id"]), rel_pos(pt["release_id"])
            crossing = [b for b in breaks if prev_pos < rel_pos(b) <= cur_pos]
            if crossing:
                cuts.append({"after_period": points[i - 1]["period"], "release_id": crossing[0],
                             "reason": "question changed materially — values either side are not comparable"})
                segments.append([])
        segments[-1].append(pt)
    return {"question_id": qid, "title": q.display_title, "unit": q.unit_block(),
            "question_version": q.question_version,
            "segments": [s for s in segments if s], "breaks": cuts,
            "periods": len(points)}


@app.get("/api/terms")
async def terms_texts():
    """Public: the signup screen shows the Platform Terms before any account
    exists. Both documents are DRAFT — pending legal review."""
    return {
        "platform": {"version": PLATFORM_TERMS_VERSION, "text": legal_text("platform")},
        "data_contribution": {"version": DATA_TERMS_VERSION, "text": legal_text("data_contribution")},
        "dpa_available": True,
    }


@app.get("/api/terms/dpa")
async def terms_dpa():
    return Response(legal_text("dpa"), media_type="text/markdown",
                    headers={"Content-Disposition": 'attachment; filename="lumi-data-sharing-agreement-DRAFT.md"'})


@app.post("/api/terms/accept-data")
async def accept_data_terms(request: Request):
    """The Admin accepts the Data Contribution Terms on behalf of the
    organisation — once. This logged acceptance IS the organisational
    agreement, and it starts the 30-day contribution clock."""
    user, org = require_admin(request)
    body = await request.json()
    if body.get("accept") is not True:
        raise HTTPException(400, "Tick the acceptance box to accept the terms.")
    conn = get_conn()
    if org_data_terms(conn, org["org_id"]) is not None:
        raise HTTPException(400, "Your organisation has already accepted the Data Contribution Terms.")
    record_acceptance(conn, org["org_id"], user["user_id"], "data_contribution", DATA_TERMS_VERSION)
    if not org["clock_start"]:
        conn.execute("UPDATE orgs SET clock_start=datetime('now') WHERE org_id=?", (org["org_id"],))
        conn.commit()
    org = dict(conn.execute("SELECT * FROM orgs WHERE org_id=?", (org["org_id"],)).fetchone())
    return {"ok": True, "contribution": contribution_state(conn, org),
            "version": DATA_TERMS_VERSION}


@app.get("/api/invite/{token}")
async def invite_info(token: str):
    row = auth_lib.get_valid_invite(token)
    if not row:
        raise HTTPException(404, "This invite link has expired or already been used.")
    conn = get_conn()
    org = conn.execute("SELECT name FROM orgs WHERE org_id=?", (row["org_id"],)).fetchone()
    return {"email": row["email"], "role": row["role"], "org_name": org["name"]}


@app.post("/api/auth/accept-invite")
async def accept_invite(request: Request):
    body = await request.json()
    row = auth_lib.get_valid_invite(body.get("token") or "")
    if not row:
        raise HTTPException(400, "This invite link has expired or already been used.")
    if len(body.get("password") or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if body.get("accept_platform_terms") is not True:
        raise HTTPException(400, "Please accept the Platform Terms of Use to join.")
    conn = get_conn()
    uid = auth_lib.create_user(row["org_id"], row["email"], body["password"], row["role"],
                               body.get("display_name"))
    # Joiners accept the Platform Terms only — the org's Data Contribution
    # agreement was made once by the Admin and is inherited, never re-accepted.
    record_acceptance(conn, row["org_id"], uid, "platform", PLATFORM_TERMS_VERSION)
    conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=?", (row["token"],))
    conn.commit()
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(auth_lib.COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=auth_lib.SESSION_TTL_DAYS * 86400)
    return resp


# =============================================================== BENCHMARKS ==

def org_answers_for(org):
    return pos.get_org_answers(get_conn(), org["org_id"], CURRENT_SNAPSHOT)


@app.get("/api/questions")
async def questions_index(request: Request):
    user, org = require_user(request)
    entitled = make_entitled(user, org)
    answers = org_answers_for(org)
    answered_q = {k[0] for k in answers}
    out = []
    for qid, q in org_visible_questions(org).items():
        p = payloads().get(qid, {})
        out.append({
            "id": qid, "title": q.display_title, "superpower": q.superpower,
            "subpower": q.sub_power, "sub_power_order": q.sub_power_order,
            "type": q.type, "category": q.category,
            "locked": not entitled(q), "answered": qid in answered_q,
            "n": (p.get("all") or {}).get("n", 0),
        })
    return {"questions": out}


@app.get("/api/benchmarks/{superpower}")
async def benchmarks_for_superpower(superpower: str, request: Request):
    user, org = require_user(request)
    if ACTIVE_SUPERPOWERS and superpower not in ACTIVE_SUPERPOWERS:
        raise HTTPException(404, "This benchmark area isn't available.")
    conn = get_conn()
    entitled = make_entitled(user, org)
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    answers = org_answers_for(org)
    contrib = contribution_state(conn, org)
    sample = reduced_sample_ids() if contrib["reduced"] else None
    cards = []
    for qid, q in org_visible_questions(org).items():
        if q.superpower != superpower:
            continue
        p = payloads().get(qid)
        if p is None:
            continue
        if sample is not None and qid not in sample:
            cards.append({
                "id": qid, "title": q.display_title, "question_text": q.text,
                "superpower": q.superpower, "subpower": q.sub_power,
                "sub_power_order": q.sub_power_order, "type": q.type,
                "category": q.category,
                "cut": {"dim": cut["dim"], "value": cut.get("value"), "label": "All peers"},
                "n": (p.get("all") or {}).get("n", 0), "reduced": True,
            })
            continue
        cards.append(assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None, entitled))
    cards.sort(key=lambda c: (c["sub_power_order"] or 999, c["title"]))
    return {"superpower": superpower, "cut": cut, "cards": cards, "reduced": contrib["reduced"]}


@app.get("/api/benchmark/{qid}")
async def single_benchmark(qid: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    q = org_visible_questions(org).get(qid)
    p = payloads().get(qid)
    if q is None or p is None:
        raise HTTPException(404, "Unknown metric")
    entitled = make_entitled(user, org)
    contrib = contribution_state(conn, org)
    if contrib["reduced"] and qid not in reduced_sample_ids():
        return {"id": qid, "title": q.display_title, "question_text": q.text,
                "superpower": q.superpower, "subpower": q.sub_power,
                "sub_power_order": q.sub_power_order, "type": q.type,
                "category": q.category,
                "cut": {"dim": "all", "value": None, "label": "All peers"},
                "n": (p.get("all") or {}).get("n", 0), "reduced": True}
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    card = assemble_card(q, p, org, org_answers_for(org), cut,
                         {qid: tb.get(qid)} if tb else None, entitled)
    # opportunity panel for £-model metrics
    mm = next((m for m in pos.MONEY_METRICS if m["question_id"] == qid), None)
    if mm and not card["locked"] and q.polarity != "neutral":
        money = pos.money_opportunities(conn, org, org_visible_questions(org), payloads(),
                                        org_answers_for(org), cut, {qid: tb.get(qid)} if tb else None)
        card["opportunity"] = next((i for i in money["items"] if i["question_id"] == qid), None)
        card["assumptions"] = money["assumptions"]
    return card


@app.get("/api/cuts")
async def cuts_available(request: Request):
    user, org = require_user(request)
    pool = get_meta("peer_pool", {})
    conn = get_conn()
    twin = peer_twin.compute_twin(conn, org["org_id"])
    groups = [group_row_out(conn, r) for r in conn.execute(
        "SELECT * FROM peer_groups WHERE org_id=? ORDER BY created_at", (org["org_id"],))]
    return {
        "industries": pool.get("industries", {}),
        "fte_bands": pool.get("fte_bands", {}),
        "twin_available": twin is not None,
        "org_industry": org["industry"], "org_fte_band": org["fte_band"],
        "groups": groups,
    }


# ================================================================= OVERVIEW ==

def build_items(request, org, user, cut):
    conn = get_conn()
    entitled = make_entitled(user, org)
    tb = twin_blocks_if_needed(conn, org, cut) if cut.get("dim") in ("twin", "group") else None
    return pos.position_items(org["org_id"], cut, org_visible_questions(org), payloads(),
                              org_answers_for(org), entitled, tb), tb


@app.get("/api/overview")
async def overview(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    cut = parse_cut(request, org)
    contrib = contribution_state(conn, org)
    items, tb = build_items(request, org, user, cut)
    summary = pos.overview_summary(items)
    prev_items = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org), payloads(),
                                      org_answers_for(org), make_entitled(user, org), tb)
    sec_order = []
    for q in org_visible_questions(org).values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in org_visible_questions(org).values() if q.sub_power == x))
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_MARGIN, UNCOMMON_PCT)
    reg_rows = build_gap_register(request, user, org, cut).get("rows", [])
    hero["action_gaps"] = sum(1 for r in reg_rows
                              if r.get("org_answered") and r.get("in_place") is False and (r.get("gap") or 0) > 0)
    co = pos.callouts(items, org_visible_questions(org), k=3)
    money = pos.money_opportunities(conn, org, org_visible_questions(org), payloads(),
                                    org_answers_for(org), cut, tb)
    pool = get_meta("peer_pool", {})
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    return {
        "org": {"name": org["name"], "industry": org["industry"], "fte_band": org["fte_band"],
                "hq_region": org["hq_region"], "classified": bool(org["classified"])},
        "cut": cut,
        "peer_pool": pool,
        "synthetic_pool": bool(get_meta("synthetic_seed", False)),
        "snapshot": {"date": snap["snapshot_date"], "window": snap["collection_window"]},
        "headline": summary,
        "contribution": contrib,
        "hero": hero,
        "callouts": {"strengths": [c["text"] for c in co["strengths"]],
                     "gaps": [] if not contrib["insights_unlocked"] else [c["text"] for c in co["gaps"]],
                     "gaps_locked": not contrib["insights_unlocked"],
                     "gaps_available": len(co["gaps"]),
                     "strength_items": [c["item"] for c in co["strengths"]],
                     "gap_items": [] if not contrib["insights_unlocked"] else [c["item"] for c in co["gaps"]]},
        "opportunity": ({
            "locked": True, "days_left": contrib["days_left"],
            "item_count": len(money["items"]), "fte_known": money["fte_known"],
        } if not contrib["insights_unlocked"] else {
            "total_savings_to_p50_gbp": money["total_savings_to_p50_gbp"],
            "total_investment_to_p50_gbp": money["total_investment_to_p50_gbp"],
            "items": [{"label": i["label"], "direction": i["direction"],
                       "to_p50_gbp": i["to_p50_gbp"], "to_p75_gbp": i["to_p75_gbp"],
                       "question_id": i["question_id"], "rows": i.get("rows", [])}
                      for i in money["items"]],
            "fte_known": money["fte_known"], "indicative": True,
        }),
        "movement": {"available": False,
                     "message": "First benchmark — movement appears from your next cycle."},
    }


# ================================================================== MY DATA ==

@app.get("/api/my-data")
async def my_data(request: Request):
    user, org = require_user(request)
    answers = org_answers_for(org)
    questions = org_visible_questions(org)
    rows = []
    for (qid, row_id), value in answers.items():
        q = questions.get(qid)
        if q is None:
            continue
        label = None
        if row_id:
            label = dict(q.matrix_row_defs()).get(row_id, row_id)
        rows.append({"question_id": qid, "question": q.text, "title": q.display_title,
                     "superpower": q.superpower, "subpower": q.sub_power,
                     "matrix_row": label, "value": value, "type": q.type,
                     "unit": q.unit_block()})
    rows.sort(key=lambda r: (r["superpower"], r["subpower"] or "", r["title"], r["matrix_row"] or ""))
    return {"rows": rows}


# ============================================================== METHODOLOGY ==

@app.get("/api/methodology")
async def methodology(request: Request):
    require_user(request)
    conn = get_conn()
    recon = get_meta("reconciliation", {})
    pool = get_meta("peer_pool", {})
    comp = defaultdict(lambda: defaultdict(int))
    for r in conn.execute("SELECT industry, fte_band FROM orgs WHERE classified=1 AND submission_complete=1"):
        comp[r["industry"]][r["fte_band"]] += 1
    uncl = conn.execute("SELECT COUNT(*) c FROM orgs WHERE classified=0 AND source='seed'").fetchone()["c"]
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    assumptions = get_meta("assumptions_defaults", {})
    vis = visible_questions()
    return {
        "scope": {"superpowers": ACTIVE_SUPERPOWERS or sorted({q.superpower for q in vis.values()}),
                  "focused": bool(ACTIVE_SUPERPOWERS), "question_count": len(vis),
                  "sections": sorted({q.sub_power for q in vis.values() if q.sub_power})},
        "synthetic_pool": bool(get_meta("synthetic_seed", False)),
        "composition": {k: dict(v) for k, v in sorted(comp.items())},
        "unclassified_count": uncl,
        "fte_bands": ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"],
        "peer_pool": pool,
        "reconciliation": {k: recon.get(k) for k in (
            "files", "matched_orgs", "file_only_orgs", "registry_only_orgs", "answer_rows")},
        "collection_window": snap["collection_window"],
        "snapshot_date": snap["snapshot_date"],
        "suppression_floor": SUPPRESSION_FLOOR,
        "assumptions": assumptions,
    }


# ================================================================== MY VIEW ==

def starter_layout(request, org, user):
    """8 biggest gaps + 4 biggest strengths — same definition as everywhere."""
    items, _ = build_items(request, org, user, {"dim": "all"})
    cards = []
    for it in pos.top_gaps(items, 8) + pos.top_strengths(items, 4):
        cards.append({"question_id": it["question_id"], "row_id": it["row_id"],
                      "size": 1, "cut": {"dim": "all"}})
    seen, out = set(), []
    for c in cards:
        if c["question_id"] not in seen:
            seen.add(c["question_id"])
            out.append(c)
    return out


@app.get("/api/myview")
async def get_myview(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    vis = org_visible_questions(org)

    def keep(layout):
        return [slot for slot in (layout or []) if slot.get("question_id") in vis]

    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=?",
                       (org["org_id"], user["user_id"])).fetchone()
    if row:
        return {"layout": keep(uj(row["layout_json"], [])), "source": "user"}
    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=''",
                       (org["org_id"],)).fetchone()
    if row:
        return {"layout": keep(uj(row["layout_json"], [])), "source": "org_default"}
    return {"layout": starter_layout(request, org, user), "source": "starter"}


@app.put("/api/myview")
async def put_myview(request: Request):
    user, org = require_user(request)
    body = await request.json()
    conn = get_conn()
    conn.execute(
        "INSERT INTO pinned_views(org_id, user_id, layout_json, updated_at) VALUES (?,?,?,datetime('now')) "
        "ON CONFLICT(org_id, user_id) DO UPDATE SET layout_json=excluded.layout_json, updated_at=datetime('now')",
        (org["org_id"], user["user_id"], j(body.get("layout") or [])))
    conn.commit()
    return {"ok": True}


@app.post("/api/myview/save-default")
async def save_default_view(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    conn = get_conn()
    conn.execute(
        "INSERT INTO pinned_views(org_id, user_id, layout_json, updated_at) VALUES (?,'',?,datetime('now')) "
        "ON CONFLICT(org_id, user_id) DO UPDATE SET layout_json=excluded.layout_json, updated_at=datetime('now')",
        (org["org_id"], j(body.get("layout") or [])))
    conn.commit()
    return {"ok": True}


# ==================================================================== PREFS ==

@app.get("/api/prefs")
async def get_prefs(request: Request):
    user, org = require_user(request)
    return {"prefs": uj(user["chart_prefs_json"], {})}


@app.put("/api/prefs")
async def put_prefs(request: Request):
    user, org = require_user(request)
    body = await request.json()
    conn = get_conn()
    conn.execute("UPDATE users SET chart_prefs_json=? WHERE user_id=?",
                 (j(body.get("prefs") or {}), user["user_id"]))
    conn.commit()
    return {"ok": True}


# ============================================================== ASSUMPTIONS ==

@app.get("/api/assumptions")
async def get_assumptions_route(request: Request):
    user, org = require_user(request)
    return {"assumptions": pos.get_assumptions(get_conn(), org["org_id"]),
            "editable": user["role"] == "admin"}


@app.put("/api/assumptions")
async def put_assumptions(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    allowed = {"median_salary_gbp", "cost_per_leaver_pct_salary", "agency_premium_pct"}
    overrides = {k: v for k, v in (body.get("assumptions") or {}).items() if k in allowed}
    for k, v in overrides.items():
        if not isinstance(v, (int, float)) or v <= 0 or v > 10_000_000:
            raise HTTPException(400, "Invalid value for %s" % k)
    conn = get_conn()
    conn.execute(
        "INSERT INTO org_assumptions(org_id, assumptions_json) VALUES (?,?) "
        "ON CONFLICT(org_id) DO UPDATE SET assumptions_json=excluded.assumptions_json",
        (org["org_id"], j(overrides)))
    conn.commit()
    return {"ok": True}


# ================================================================ PEER TWIN ==

@app.get("/api/peer-twin")
async def peer_twin_route(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    twin = peer_twin.compute_twin(conn, org["org_id"])
    if twin is None:
        return {"available": False,
                "message": "Peer Twin needs your organisation's firmographic profile. Complete the 'About your organisation' step to unlock it."}
    return {"available": True, "rationale": twin["rationale"]}


# ============================================================= GAP REGISTER ==

def build_gap_register(request, user, org, cut):
    conn = get_conn()
    entitled = make_entitled(user, org)
    tb = twin_blocks_if_needed(conn, org, cut) if cut.get("dim") in ("twin", "group") else None
    sector_cut = {"dim": "industry", "value": org["industry"]} if org["industry"] else None
    return pos.gap_register(conn, org, org_visible_questions(org), payloads(), org_answers_for(org),
                            cut, sector_cut, entitled, tb)


@app.get("/api/gap-register")
async def gap_register_route(request: Request):
    user, org = require_user(request)
    cut = parse_cut(request, org)
    return build_gap_register(request, user, org, cut)


@app.get("/api/gap-register.csv")
async def gap_register_csv(request: Request):
    user, org = require_admin(request)
    cut = parse_cut(request, org)
    reg = build_gap_register(request, user, org, cut)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Benchmark", "Category", "Type", "Practice / policy", "Tier",
                "Your status", "In place", "Peer adoption %", "Sector adoption %", "Gap", "n"])
    for r in reg["rows"]:
        w.writerow([r["superpower"], r["subpower"], r["category"], r["name"], r["tier"],
                    r["org_status"],
                    {"in_place": "In place", "partial": "Partially", "not_in_place": "Not in place"}.get(r.get("status"), "Not assessable"),
                    "suppressed" if r["suppressed"] else r["peer_adoption_pct"],
                    r["sector_adoption_pct"] if r["sector_adoption_pct"] is not None else "",
                    r["gap"] if r["gap"] is not None else "", r["n"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=lumi-gap-register.csv"})


# ================================================================== ANALYST ==

@app.post("/api/analyst")
async def analyst(request: Request):
    user, org = require_user(request)
    if not AI_ANALYST:
        raise HTTPException(403, "Ask lumi is switched off at the moment.")
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    conn = get_conn()
    contrib = contribution_state(conn, org)
    if contrib["reduced"]:
        return {"answer": "Your full benchmark is paused until your reward data is complete — "
                          "finish your submission and I'll have every comparison ready for you again.",
                "chips": [], "matched": [], "reduced": True}
    vis = org_visible_questions(org)
    qids = [x for x in retrieval.search_questions(question, limit=12) if x in vis][:6]
    if qids and retrieval.distinctive_coverage(question, qids) < 0.34:
        qids = []   # fuzzy noise, not real coverage — offer the request path
    if not qids:
        return {"answer": "lumi doesn't benchmark that yet, so I won't guess at a figure. "
                          "If it would be useful, ask us to add it — member requests shape "
                          "what lumi measures next.",
                "chips": [], "matched": [], "no_metric": True, "topic": question}
    answers = org_answers_for(org)
    entitled = make_entitled(user, org)
    questions = vis
    data = {"organisation": {"name": org["name"], "industry": org["industry"],
                             "fte_band": org["fte_band"]},
            "metrics": []}
    for qid in qids:
        q = questions[qid]
        if not entitled(q):
            continue
        p = payloads().get(qid)
        if p is None:
            continue
        card_all = assemble_card(q, p, org, answers, {"dim": "all"}, None, entitled)
        entry = {"question_id": qid, "metric": q.display_title, "type": q.type,
                 "unit": q.unit_block(), "polarity": q.polarity,
                 "all_peers": _analyst_block(card_all)}
        if org["industry"]:
            card_sec = assemble_card(q, p, org, answers, {"dim": "industry", "value": org["industry"]}, None, entitled)
            entry["sector_cut"] = _analyst_block(card_sec)
            entry["sector_cut"]["cut_label"] = org["industry"]
        data["metrics"].append(entry)

    res = claude_api.analyst_answer(question, data)
    if not res["ok"]:
        # deterministic fallback: cite the top matches' readouts
        lines = []
        chips = []
        for m in data["metrics"][:3]:
            blk = m["all_peers"]
            if blk.get("readout"):
                lines.append(blk["readout"])
            if blk.get("you_display") and blk.get("you_percentile") is not None:
                chips.append({"label": m["metric"], "value": blk["you_display"],
                              "sub": "P%d · All peers · n=%d" % (round(blk["you_percentile"]), blk.get("n", 0)),
                              "question_id": m["question_id"]})
        prefix = ("(AI analyst is not configured on this server — showing the matching benchmark "
                  "readouts instead.)\n\n")
        return {"answer": prefix + ("\n".join(lines) if lines else "No matching benchmark data found."),
                "chips": chips, "matched": qids, "fallback": True}
    return {"answer": res["answer"], "chips": res["chips"], "matched": qids}


def _analyst_block(card):
    out = {"suppressed": card.get("suppressed"), "n": card.get("n"),
           "cut_label": card["cut"]["label"], "readout": card.get("readout")}
    if card.get("block"):
        b = dict(card["block"])
        b.pop("options", None)
        out["aggregates"] = b
        if card.get("type") in ("single_select", "yes_no", "multi_select"):
            out["distribution"] = [{"label": o["label"], "pct": o["pct"]}
                                   for o in card["block"].get("options", [])]
    if card.get("matrix_rows"):
        out["rows"] = [{"label": r["label"],
                        "suppressed": r["suppressed"],
                        "aggregates": r.get("block"),
                        "you": (r.get("you") or {}).get("value"),
                        "you_percentile": (r.get("you") or {}).get("percentile")}
                       for r in card["matrix_rows"]]
    you = card.get("you") or {}
    out["you_value"] = you.get("value") or you.get("label")
    out["you_display"] = you.get("display") or you.get("label")
    out["you_percentile"] = you.get("percentile")
    return out


@app.get("/api/analyst/starters")
async def analyst_starters(request: Request):
    user, org = require_user(request)
    items, _ = build_items(request, org, user, {"dim": "all"})
    gaps = pos.top_gaps(items, 6)
    starters = []
    for g in gaps:
        starters.append("How does our %s compare with similar organisations?" % pos._lower_first(g["label"]))
    while len(starters) < 6:
        starters.append([
            "Where do we sit on employer pension contributions?",
            "How common are holiday purchase schemes?",
            "What bonus eligibility is typical for organisations like ours?",
            "Which benefits are most commonly offered by organisations our size?",
            "How does our annual leave entitlement compare?",
            "What proportion of peers have a published pay transparency approach?",
        ][len(starters)])
    return {"starters": starters[:6]}


# ================================================================ BOARD PACK ==

def assemble_pack_payload(request, user, org, cut):
    conn = get_conn()
    items, tb = build_items(request, org, user, cut)
    summary = pos.overview_summary(items)
    strengths = pos.top_strengths(items, 5)
    gaps = pos.top_gaps(items, 5)
    money = pos.money_opportunities(conn, org, visible_questions(), payloads(),
                                    org_answers_for(org), cut, tb)
    reg = build_gap_register(request, user, org, cut)
    pool = get_meta("peer_pool", {})
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    cut_label = "All peers" if cut["dim"] == "all" else (
        cut.get("value") if cut["dim"] == "industry" else
        "%s FTE" % cut.get("value") if cut["dim"] == "fte_band" else
        cut.get("label") if cut["dim"] == "group" else "Organisations like you")
    if cut["dim"] == "industry":
        cut_n = pool.get("industries", {}).get(cut.get("value"), 0)
    elif cut["dim"] == "fte_band":
        cut_n = pool.get("fte_bands", {}).get(cut.get("value"), 0)
    elif cut["dim"] == "twin":
        twin = peer_twin.compute_twin(conn, org["org_id"])
        cut_n = len(twin["peer_org_ids"]) if twin else 0
    elif cut["dim"] == "group":
        cut_n = len(peer_twin.group_org_ids(conn, cut.get("criteria") or {}))
    else:
        cut_n = pool.get("responding_orgs", 0)
    return {
        "cut_n": cut_n,
        "organisation": {"name": org["name"], "industry": org["industry"],
                         "fte_band": org["fte_band"], "region": org["hq_region"]},
        "cut_label": cut_label,
        "generated_date": datetime.utcnow().strftime("%d %B %Y"),
        "collection_window": snap["collection_window"],
        "peer_pool": {"total": pool.get("responding_orgs"), "classified": pool.get("classified_orgs")},
        "headline": {
            "comparable_metrics": summary["comparable_metrics"],
            "above_median": summary["above_median"],
            "below_median": summary["below_median"],
            "broadly_in_line": summary["broadly_in_line"],
        },
        "strengths": [_pack_item(i) for i in strengths],
        "gaps": [_pack_item(i) for i in gaps],
        "opportunities": [{"label": i["label"], "direction": i["direction"],
                           "to_p50_gbp": i["to_p50_gbp"], "to_p75_gbp": i["to_p75_gbp"],
                           "formula": i["formula"], "cut_label": i["cut_label"]}
                          for i in money["items"]],
        "opportunity_assumptions": {k: v for k, v in money["assumptions"].items()
                                    if k in ("median_salary_gbp", "cost_per_leaver_pct_salary",
                                             "agency_premium_pct", "fte_band_midpoints")},
        "gap_register_top": [
            {"name": r["name"], "superpower": r["superpower"], "your_status": r["org_status"],
             "peer_adoption_pct": r["peer_adoption_pct"], "n": r["n"]}
            for r in reg["rows"] if not r["suppressed"] and r["gap"] is not None and r["gap"] > 0
        ][:10],
        "maturity": reg["maturity"],
    }


def _pack_item(i):
    # percentiles rounded here so the narrative can only cite figures that
    # appear verbatim in its input payload
    return {"label": i["label"], "value_display": i["value_display"],
            "percentile": int(round(i["percentile"])), "n": i["n"], "cut_label": i["cut_label"],
            "p50_display": i["p50_display"], "superpower": i["superpower"]}


@app.post("/api/boardpack/generate")
async def boardpack_generate(request: Request):
    user, org = require_user(request)
    if not AI_BOARDPACK:
        raise HTTPException(403, "Board pack generation is switched off at the moment.")
    contrib = contribution_state(get_conn(), org)
    if not contrib["insights_unlocked"]:
        raise HTTPException(403, "Your board pack unlocks once you've answered %d%% of your key reward questions." % int(TARGET_PCT))
    body = await request.json()
    cut = {"dim": body.get("cut", "all"), "value": body.get("cut_value")}
    if cut["dim"] == "industry" and not cut["value"]:
        cut["value"] = org["industry"]
    if cut["dim"] == "fte_band" and not cut["value"]:
        cut["value"] = org["fte_band"]
    payload = assemble_pack_payload(request, user, org, cut)
    result = claude_api.generate_board_pack_narrative(payload)
    pack_id = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO board_packs(pack_id, org_id, created_by, payload_json, narrative_json) VALUES (?,?,?,?,?)",
        (pack_id, org["org_id"], user["user_id"], j(payload), j(result["narrative"])))
    conn.commit()
    return {"pack_id": pack_id, "ai": result["ok"]}


@app.get("/api/boardpack/{pack_id}")
async def boardpack_get(pack_id: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    row = conn.execute("SELECT * FROM board_packs WHERE pack_id=? AND org_id=?",
                       (pack_id, org["org_id"])).fetchone()
    if not row:
        raise HTTPException(404, "Board pack not found")
    return {"pack_id": pack_id, "payload": uj(row["payload_json"]),
            "narrative": uj(row["narrative_json"]), "created_at": row["created_at"]}


@app.get("/api/boardpacks")
async def boardpacks_list(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT pack_id, created_at FROM board_packs WHERE org_id=? ORDER BY created_at DESC LIMIT 20",
        (org["org_id"],)).fetchall()
    return {"packs": [dict(r) for r in rows]}


# =============================================================== SUBMISSION ==

FIRMOGRAPHIC_FIELDS = ("industry", "subsector", "fte_band", "hq_region", "ownership_type")
INDUSTRIES = []  # filled at startup from registry meta
FTE_BANDS = ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]
REGIONS = ["London", "South East", "South West", "East of England", "East Midlands",
           "West Midlands", "Yorkshire & Humber", "North East", "North West",
           "Scotland", "Wales", "Northern Ireland"]
OWNERSHIP = ["Private (Founder/Family)", "Private Equity-backed", "Public Listed (PLC)",
             "Public Sector", "Charity / Not-for-profit", "Partnership / LLP",
             "Co-operative / Mutual", "Subsidiary of overseas parent"]


def completion_basis_questions():
    # GLOBAL by design: sector-module questions are never is_required
    # (qa_release asserts it), so the unlock denominator is org-independent.
    questions = visible_questions()
    if COMPLETION_BASIS == "required":
        basis = [q for q in questions.values() if q.is_required]
        if basis:
            return basis
    return list(questions.values())


def completion_pct(conn, org):
    """% of the BASIS set answered. N/A and Don't-know selections are stored
    values, so they count as answered — only skipped questions don't."""
    basis = completion_basis_questions()
    if not basis:
        return 100.0
    answered = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=?",
        (org["org_id"], CURRENT_SNAPSHOT))}
    drafted = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
        (org["org_id"],))}
    have = answered | drafted
    return round(100.0 * sum(1 for q in basis if q.id in have) / len(basis), 1)


# ============================================================== PEER GROUPS ==
# Filter-based custom peer groups, private to the org. The anonymity rules:
# the same n>=5 floor as everything else, enforced in the engine path (a
# below-floor group never aggregates at all); membership is NEVER revealed —
# only counts; criteria fields and values are validated against the curated
# registry sets so hand-built requests can't probe arbitrary columns.

GROUP_FIELD_LABELS = [
    ("industry", "Industry / sector"),
    ("fte_band", "Organisation size (FTE)"),
    ("hq_region", "HQ region"),
    ("ownership_type", "Ownership"),
    ("unionised_level", "Unionised workforce"),
    ("hr_maturity", "HR maturity"),
    ("business_maturity", "Business life stage"),
    ("operating_model", "Operating model"),
]


def validate_group_criteria(criteria):
    if not isinstance(criteria, dict) or not criteria:
        raise HTTPException(400, "Choose at least one criterion for the group.")
    choices = profile_choices()
    clean = {}
    for field, values in criteria.items():
        if field not in peer_twin.GROUP_FIELDS:
            raise HTTPException(400, "'%s' isn't a recognised peer-group criterion." % field)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise HTTPException(400, "Criteria values must be lists of options.")
        values = [v for v in values if v]
        if not values:
            continue
        allowed = set(choices.get(field) or [])
        bad = [v for v in values if v not in allowed]
        if bad:
            raise HTTPException(400, "'%s' isn't a recognised option for %s." % (bad[0], field.replace("_", " ")))
        clean[field] = values
    if not clean:
        raise HTTPException(400, "Choose at least one criterion for the group.")
    return clean


def group_row_out(conn, row):
    criteria = uj(row["criteria_json"], {})
    match = len(peer_twin.group_org_ids(conn, criteria))
    return {"group_id": row["group_id"], "name": row["name"], "criteria": criteria,
            "match_count": match, "min_orgs": SUPPRESSION_FLOOR,
            "too_small": match < SUPPRESSION_FLOOR}


@app.get("/api/peer-groups/options")
async def peer_group_options(request: Request):
    require_user(request)
    choices = profile_choices()
    return {"fields": [{"key": k, "label": lbl, "choices": choices.get(k) or []}
                       for k, lbl in GROUP_FIELD_LABELS],
            "min_orgs": SUPPRESSION_FLOOR}


@app.post("/api/peer-groups/preview")
async def peer_group_preview(request: Request):
    """Live match count while building. Returns ONLY the count — never which
    organisations match."""
    user, org = require_user(request)
    body = await request.json()
    criteria = validate_group_criteria(body.get("criteria") or {})
    match = len(peer_twin.group_org_ids(get_conn(), criteria))
    return {"match_count": match, "min_orgs": SUPPRESSION_FLOOR,
            "too_small": match < SUPPRESSION_FLOOR}


@app.get("/api/peer-groups")
async def peer_groups_list(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    rows = conn.execute("SELECT * FROM peer_groups WHERE org_id=? ORDER BY created_at",
                        (org["org_id"],)).fetchall()
    return {"groups": [group_row_out(conn, r) for r in rows]}


@app.post("/api/peer-groups")
async def peer_groups_create(request: Request):
    user, org = require_user(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name or len(name) > 60:
        raise HTTPException(400, "Give the group a name (up to 60 characters).")
    criteria = validate_group_criteria(body.get("criteria") or {})
    conn = get_conn()
    gid = str(uuid.uuid4())
    conn.execute("INSERT INTO peer_groups(group_id, org_id, name, criteria_json, created_by) VALUES (?,?,?,?,?)",
                 (gid, org["org_id"], name, j(criteria), user["user_id"]))
    conn.commit()
    return group_row_out(conn, conn.execute("SELECT * FROM peer_groups WHERE group_id=?", (gid,)).fetchone())


@app.put("/api/peer-groups/{gid}")
async def peer_groups_update(gid: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    row = conn.execute("SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
                       (gid, org["org_id"])).fetchone()
    if row is None:
        raise HTTPException(404, "No such peer group.")
    body = await request.json()
    name = (body.get("name") or row["name"]).strip()[:60] or row["name"]
    criteria = validate_group_criteria(body["criteria"]) if body.get("criteria") else uj(row["criteria_json"], {})
    conn.execute("UPDATE peer_groups SET name=?, criteria_json=?, updated_at=datetime('now') WHERE group_id=?",
                 (name, j(criteria), gid))
    conn.commit()
    return group_row_out(conn, conn.execute("SELECT * FROM peer_groups WHERE group_id=?", (gid,)).fetchone())


@app.delete("/api/peer-groups/{gid}")
async def peer_groups_delete(gid: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    n = conn.execute("DELETE FROM peer_groups WHERE group_id=? AND org_id=?",
                     (gid, org["org_id"])).rowcount
    conn.commit()
    if not n:
        raise HTTPException(404, "No such peer group.")
    return {"ok": True}


# ============================================================ COMPANY PROFILE ==
# Org-level, captured once by the Admin at first-run, BEFORE the data terms —
# without sector/size there's nothing meaningful to compare against. Choice
# sets come from the seed registry's feature space so real organisations land
# in exactly the same peer cuts and similarity buckets as the seed orgs.

PROFILE_CORE = ("industry", "fte_band", "hq_region", "ownership_type")
PROFILE_RICH = ("unionised_level", "hr_maturity", "business_maturity", "operating_model")
UNION_BANDS = ["None (0%)", "Low (1-25%)", "Medium (26-50%)", "High (over 50%)"]
UNION_MIDPOINTS = {"None (0%)": 0, "Low (1-25%)": 13, "Medium (26-50%)": 38, "High (over 50%)": 65}


def profile_choices():
    space = get_meta("sim_feature_space") or {"cat_values": {}}
    cv = space["cat_values"]
    return {
        "industry": INDUSTRIES,
        "fte_band": FTE_BANDS,
        "hq_region": REGIONS,
        "ownership_type": cv.get("Ownership_Type", OWNERSHIP),
        "unionised_level": UNION_BANDS,
        "hr_maturity": cv.get("HR_Maturity", ["Basic", "Developing", "Advanced"]),
        "business_maturity": cv.get("Business_Maturity", []),
        "operating_model": cv.get("Operating_Model", []),
    }


@app.get("/api/org-profile")
async def get_org_profile(request: Request):
    user, org = require_user(request)
    fields = PROFILE_CORE + PROFILE_RICH
    return {
        "values": {f: org.get(f) for f in fields},
        "choices": profile_choices(),
        "core_complete": bool(org["classified"]),
        "rich_complete": all(org.get(f) for f in PROFILE_RICH),
        "can_edit": user["role"] == "admin",
    }


@app.put("/api/org-profile")
async def put_org_profile(request: Request):
    """Admin-only; deliberately does NOT require the data terms — the profile
    is the step before them in the lifecycle."""
    user, org = require_admin(request)
    body = await request.json()
    choices = profile_choices()
    vals = {}
    for f in PROFILE_CORE + PROFILE_RICH:
        v = body.get(f)
        if v in (None, ""):
            continue
        if choices.get(f) and v not in choices[f]:
            raise HTTPException(400, "'%s' isn't one of the recognised options for %s." % (v, f.replace("_", " ")))
        vals[f] = v
    if not vals:
        raise HTTPException(400, "Nothing to save.")
    conn = get_conn()
    sets = ", ".join("%s=?" % f for f in vals)
    conn.execute("UPDATE orgs SET %s WHERE org_id=?" % sets, list(vals.values()) + [org["org_id"]])
    row = dict(conn.execute("SELECT * FROM orgs WHERE org_id=?", (org["org_id"],)).fetchone())
    classified = 1 if all(row.get(f) for f in PROFILE_CORE) else 0
    conn.execute("UPDATE orgs SET classified=? WHERE org_id=?", (classified, org["org_id"]))
    if classified:
        _encode_signup_vector(conn, row)
    conn.commit()
    invalidate_payloads()
    return {"ok": True, "core_complete": bool(classified),
            "rich_complete": all(row.get(f) for f in PROFILE_RICH)}


@app.get("/api/submission/state")
async def submission_state(request: Request):
    user, org = require_editor(request)
    conn = get_conn()
    questions = org_visible_questions(org)
    answered = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=?",
        (org["org_id"], CURRENT_SNAPSHOT))}
    drafted = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
        (org["org_id"],))}
    have = answered | drafted
    # Sections are SUB-powers (Pay, Benefits, Incentives, Transparency,
    # Progression) — one digestible page each, with progress per section.
    sections = []
    sub_order = []
    for q in questions.values():
        key = (q.sub_power_order or 999, q.sub_power or "General", q.superpower)
        if key not in sub_order:
            sub_order.append(key)
    for _o, sub, sp in sorted(sub_order):
        qs = [q for q in questions.values() if (q.sub_power or "General") == sub]
        sections.append({
            "section": sub, "superpower": sp, "questions": len(qs),
            "answered": sum(1 for q in qs if q.id in have),
            "key_questions": sum(1 for q in qs if q.is_required),
            "key_answered": sum(1 for q in qs if q.is_required and q.id in have),
        })
    firmographics_done = all(org.get(f) for f in ("industry", "fte_band", "hq_region", "ownership_type"))
    return {
        "firmographics_done": firmographics_done,
        "firmographics": {f: org.get(f) for f in FIRMOGRAPHIC_FIELDS},
        "choices": {"industries": INDUSTRIES, "fte_bands": FTE_BANDS,
                    "regions": REGIONS, "ownership_types": OWNERSHIP},
        "sections": sections,
        "completion_pct": completion_pct(conn, org),
        "threshold_pct": TARGET_PCT,
        "basis": COMPLETION_BASIS,
        "basis_total": len(completion_basis_questions()),
        "basis_answered": sum(1 for q in completion_basis_questions() if q.id in have),
        "submission_complete": bool(org["submission_complete"]),
        "is_admin": user["role"] == "admin",
        "is_editor": user["role"] in ("admin", "contributor"),
        "data_terms_accepted": org_data_terms(conn, org["org_id"]) is not None,
    }


@app.put("/api/submission/firmographics")
async def put_firmographics(request: Request):
    user, org = require_editor(request)
    require_data_terms(get_conn(), org)
    body = await request.json()
    vals = {}
    if body.get("industry") and body["industry"] not in INDUSTRIES:
        raise HTTPException(400, "Unknown industry")
    if body.get("fte_band") and body["fte_band"] not in FTE_BANDS:
        raise HTTPException(400, "Unknown FTE band")
    for f in FIRMOGRAPHIC_FIELDS:
        if body.get(f):
            vals[f] = str(body[f]).strip()
    if not vals:
        raise HTTPException(400, "Nothing to save")
    conn = get_conn()
    sets = ", ".join("%s=?" % f for f in vals)
    conn.execute("UPDATE orgs SET %s WHERE org_id=?" % sets, list(vals.values()) + [org["org_id"]])
    row = conn.execute("SELECT * FROM orgs WHERE org_id=?", (org["org_id"],)).fetchone()
    classified = 1 if all(row[f] for f in ("industry", "fte_band", "hq_region", "ownership_type")) else 0
    conn.execute("UPDATE orgs SET classified=? WHERE org_id=?", (classified, org["org_id"]))
    if classified:
        _encode_signup_vector(conn, dict(row))
    conn.commit()
    invalidate_payloads()
    return {"ok": True, "classified": bool(classified)}


def _encode_signup_vector(conn, org):
    """Encode declared firmographics into the registry feature space so new
    orgs participate in Peer Twin (unknown attributes stay neutral)."""
    space = get_meta("sim_feature_space")
    if not space:
        return
    vec = []
    decl = {"Industry": org.get("industry"), "FTE_Band": org.get("fte_band"),
            "Ownership_Type": org.get("ownership_type"),
            "HR_Maturity": org.get("hr_maturity"),
            "Operating_Model": org.get("operating_model"),
            "Business_Maturity": org.get("business_maturity")}
    for attr, values in [(a, space["cat_values"][a]) for a in (
            "Industry", "FTE_Band", "Ownership_Type", "Archetype", "Turnover_Band",
            "Avg_Tenure_Band", "HR_Maturity", "Operating_Model", "Business_Maturity")]:
        mine = decl.get(attr)
        vec += [1.0 if mine == v else 0.0 for v in values]
    for a in ("Workforce_Frontline_%", "Workforce_Shift_%", "Workforce_Unionised_%"):
        if a == "Workforce_Unionised_%" and org.get("unionised_level") in UNION_MIDPOINTS:
            rng = (space.get("num_ranges") or {}).get(a)
            mid = UNION_MIDPOINTS[org["unionised_level"]]
            if rng and rng[1] > rng[0]:
                vec.append(max(0.0, min(1.0, (mid - rng[0]) / float(rng[1] - rng[0]))))
            else:
                vec.append(mid / 100.0)
        else:
            vec.append(0.5)  # undeclared numerics stay neutral
    conn.execute("UPDATE orgs SET similarity_vector_json=? WHERE org_id=?", (j(vec), org["org_id"]))
    conn.execute("DELETE FROM peer_twin_cache WHERE org_id=?", (org["org_id"],))


@app.get("/api/submission/section/{section}")
async def submission_section(section: str, request: Request):
    """One SUB-power per page (Pay, Benefits, …). Each question carries its
    unit symbol, N/A capability and the soft-warn thresholds so the client
    can show the unit inline and explain a warning's range."""
    user, org = require_editor(request)
    questions = org_visible_questions(org)
    known = {(q.sub_power or "General") for q in questions.values()}
    if section not in known:
        raise HTTPException(404, "This section isn't available.")
    conn = get_conn()
    answers = org_answers_for(org)
    drafts = {}
    for r in conn.execute("SELECT * FROM drafts WHERE org_id=?", (org["org_id"],)):
        drafts[(r["question_id"], r["matrix_row_id"] or "")] = r["value"]
    out = []
    for qid, q in questions.items():
        if (q.sub_power or "General") != section:
            continue
        hard_min, soft_min, soft_max = soft_thresholds(q)
        cfg = validation_cfg().get(qid) or {}
        entry = {
            "id": qid, "text": q.text, "title": q.display_title, "help_text": q.help_text,
            "definition": q.definition,
            "subpower": q.sub_power, "sub_power_order": q.sub_power_order,
            "question_order": q.question_order,
            "type": q.type, "category": q.category,
            "options": [{"code": o["code"], "label": o["label"], "is_na": bool(o.get("is_na"))}
                        for o in sorted(q.options or [], key=lambda o: o.get("order", 0))],
            "unit_display_name": q.unit_display_name,
            "unit": q.unit_block(),
            "validation": q.validation,
            "thresholds": {"hard_min": hard_min, "soft_min": soft_min, "soft_max": soft_max},
            "monotonic": cfg.get("monotonic"),
            "na_allowed": q.type in ("numeric", "matrix"),
            "is_required": q.is_required,
            "matrix": q.matrix if q.type == "matrix" else None,
            "matrix_rows": [{"row_id": rid, "label": lbl} for rid, lbl in q.matrix_row_defs()],
        }
        if q.type == "matrix":
            entry["current"] = {rid: (drafts.get((qid, rid)) if (qid, rid) in drafts else answers.get((qid, rid)))
                                for rid, _l in q.matrix_row_defs()}
            # question-level N/A lives at row_id '' (excluded from aggregation by design)
            entry["current_na"] = (drafts.get((qid, "")) if (qid, "") in drafts
                                   else answers.get((qid, ""))) == NA_CANON
        else:
            entry["current"] = drafts.get((qid, "")) if (qid, "") in drafts else answers.get((qid, ""))
        out.append(entry)
    out.sort(key=lambda e: (0 if e["is_required"] else 1, e["question_order"] or 999, e["title"]))
    return {"section": section, "questions": out}


# ======================================================= ENTRY GUARDRAILS ==
# The validation philosophy (2026-06-12): SOFT warnings, never hard
# plausibility blocks. A member must always be able to enter their real
# value, however unusual — a genuine 200% LTI goes through. Three layers:
#   1. hard floor   — malformed input (not a number) or below a true floor
#                     where below is meaningless (negative %/£). The ONLY block.
#   2. soft warn    — crosses David's threshold -> "is that right?" ->
#                     confirmed values save AND are logged, never refused.
#   3. cross-field  — seniority inversions on monotonic metrics, max-below-
#                     target pairs. Warn only.
# Thresholds live in data/validation_thresholds.json (seeded from the library
# by seed_validation_config.py with the too-tight caps widened). David edits
# the file directly; it hot-reloads on change. % CONVENTION: percentages are
# stored as human numbers end-to-end (50 means 50%) — entry, thresholds,
# aggregation and display all share it.

VALIDATION_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "data", "validation_thresholds.json")
_vcfg_cache = {"mtime": None, "cfg": {}}


def validation_cfg():
    """David's editable soft-warn thresholds; hot-reloads on file change.
    A malformed edit keeps the last good config rather than dropping guardrails."""
    try:
        mt = os.path.getmtime(VALIDATION_CFG_PATH)
    except OSError:
        return _vcfg_cache["cfg"]
    if _vcfg_cache["mtime"] != mt:
        try:
            with open(VALIDATION_CFG_PATH) as f:
                _vcfg_cache["cfg"] = json.load(f).get("questions") or {}
            _vcfg_cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _vcfg_cache["cfg"]


NA_RE = re.compile(r"^(not applicable|n/?a)$", re.I)
NA_CANON = "Not applicable"


def soft_thresholds(q):
    """(hard_min, soft_min, soft_max). A config entry wins outright; otherwise
    the library tolerance applies with hard_max DEMOTED to a soft warn — the
    library caps were authored as plausibility, and plausibility never blocks.
    The hard floor survives only at 0 (negative is genuinely impossible)."""
    cfg = validation_cfg().get(q.id)
    tol = q.tolerance or {}
    if cfg is not None:
        return cfg.get("hard_min"), cfg.get("soft_min"), cfg.get("soft_max")
    hard_min = 0 if tol.get("hard_min") == 0 else None
    soft_min = tol.get("soft_min")
    soft_max = tol.get("soft_max") if tol.get("soft_max") is not None else tol.get("hard_max")
    return hard_min, soft_min, soft_max


def _matrix_col(q):
    return ((q.matrix or {}).get("columns") or [{}])[0] if q.type == "matrix" else {}


def _range_text(q, soft_min, soft_max, hard_min):
    u = q.unit_block()
    lo = soft_min if soft_min is not None else hard_min
    if lo is not None and soft_max is not None:
        return "%s–%s" % (pos.fmt_value(lo, u), pos.fmt_value(soft_max, u))
    if soft_max is not None:
        return "up to %s" % pos.fmt_value(soft_max, u)
    return "%s and above" % pos.fmt_value(lo, u)


def validate_answer(q, value, row_id=""):
    """Layers 1-2. Returns (errors, warnings): errors are the malformed/
    impossible blocks; warnings always allow."""
    errors, warnings = [], []
    v = (value or "").strip()
    if v == "":
        return errors, warnings
    val = q.validation or {}
    if val.get("max_length") and len(v) > int(val["max_length"]):
        errors.append("Answer is too long (max %s characters)." % val["max_length"])
    if val.get("pattern"):
        try:
            if not re.match(val["pattern"], v):
                errors.append("Answer doesn't match the expected format.")
        except re.error:
            pass
    if q.type in ("numeric", "matrix"):
        # N/A is a first-class answer everywhere a number is asked for —
        # never faked with 0, never conflated with blank.
        if NA_RE.match(v):
            return errors, warnings
        col = _matrix_col(q)
        if col.get("type") == "select":
            opts = col.get("options") or []
            if opts and v not in opts:
                errors.append("Choose one of the listed options.")
            return errors, warnings
        f = coerce_number(v)
        if f is None and q.type == "matrix":
            f = matrix_value(v)   # tolerate "1.5x" / "12 weeks" style input
        if f is None:
            errors.append("Enter a number — e.g. 7.5. If this doesn't apply to you, use “Not applicable”.")
            return errors, warnings
        if val.get("integer_only") and f != int(f):
            errors.append("Please enter a whole number.")
        if val.get("max_decimals") is not None:
            parts = v.replace(",", "").split(".")
            if len(parts) == 2 and len(parts[1]) > int(val["max_decimals"]):
                warnings.append("We'll round this to %s decimal places." % val["max_decimals"])
        hard_min, soft_min, soft_max = soft_thresholds(q)
        if hard_min is not None and f < hard_min:
            errors.append("This can't be negative." if hard_min == 0 else
                          "Must be at least %s." % pos.fmt_value(hard_min, q.unit_block()))
            return errors, warnings
        if soft_max is not None and f > soft_max:
            warnings.append("That's unusually high — common range is %s. Is that right?"
                            % _range_text(q, soft_min, soft_max, hard_min))
        elif soft_min is not None and f < soft_min:
            warnings.append("That's unusually low — common range is %s. Is that right?"
                            % _range_text(q, soft_min, soft_max, hard_min))
    elif q.type in ("single_select", "yes_no"):
        labels = {o["label"] for o in (q.options or [])}
        if labels and v not in labels:
            errors.append("Please choose one of the listed options.")
    elif q.type == "multi_select":
        labels = {o["label"] for o in (q.options or [])}
        toks = [t.strip() for t in v.split(";") if t.strip()]
        bad = [t for t in toks if labels and t not in labels]
        if bad:
            errors.append("Unrecognised option(s): %s" % ", ".join(bad[:3]))
        none_opts = [o["label"] for o in (q.options or [])
                     if o["label"].lower().startswith("none")]
        if none_opts and any(t in none_opts for t in toks) and len(toks) > 1:
            errors.append("“%s” can't be combined with other options." % none_opts[0])
    return errors, warnings


def _merged_q_values(conn, org, qid):
    """{row_id: raw} this org's current values for one question — drafts over
    submitted answers, blanks dropped."""
    vals = {}
    for r in conn.execute("SELECT matrix_row_id, value FROM answers WHERE org_id=? AND snapshot_id=? AND question_id=?",
                          (org["org_id"], CURRENT_SNAPSHOT, qid)):
        vals[r["matrix_row_id"] or ""] = r["value"]
    for r in conn.execute("SELECT matrix_row_id, value FROM drafts WHERE org_id=? AND question_id=?",
                          (org["org_id"], qid)):
        vals[r["matrix_row_id"] or ""] = r["value"]
    return {k: v for k, v in vals.items() if v not in (None, "")}


def _comparable(q, v):
    """Scalar for cross-field comparison: the number, or a band's index in
    the column's ordered option list ('2 weeks' < '12 weeks'). None if N/A
    or not comparable."""
    if v is None or NA_RE.match(str(v).strip()):
        return None
    f = coerce_number(v)
    if f is None:
        f = matrix_value(v)
    if f is not None and _matrix_col(q).get("type") != "select":
        return f
    opts = _matrix_col(q).get("options") or []
    s = str(v).strip()
    return float(opts.index(s)) if s in opts else None


def cross_field_warnings(conn, org, q, row_id, value):
    """Layer 3 — internal-contradiction soft warns. Seniority inversion fires
    ONLY on metrics configured monotonic 'seniority' (bonus/LTI/pension/notice
    climb with seniority); flat-by-design matrices (pensionability,
    eligibility) never warn — flat is normal there. Equal values never warn."""
    out = []
    cfg = validation_cfg().get(q.id) or {}
    v_now = _comparable(q, value)
    if v_now is None:
        return out
    if cfg.get("monotonic") == "seniority" and q.type == "matrix" and row_id:
        rows = q.matrix_row_defs()          # library order: senior -> junior
        order = [rid for rid, _ in rows]
        labels = dict(rows)
        if row_id in order:
            merged = _merged_q_values(conn, org, q.id)
            merged[row_id] = value
            i_now = order.index(row_id)
            for i_other, rid in enumerate(order):
                if rid == row_id or rid not in merged:
                    continue
                v_other = _comparable(q, merged[rid])
                if v_other is None:
                    continue
                if (i_other < i_now and v_now > v_other) or (i_other > i_now and v_other > v_now):
                    junior, senior = (row_id, rid) if i_other < i_now else (rid, row_id)
                    out.append("%s (%s) is above %s (%s) — this usually climbs with seniority. "
                               "Keep it if that's genuinely how your scheme works."
                               % (labels[junior], merged[junior], labels[senior], merged[senior]))
                    break
    # a "maximum" sitting below its typical/target twin on the same level
    pairs = [(q.id, cfg.get("max_of"))] if cfg.get("max_of") else []
    pairs += [(mqid, q.id) for mqid, e in validation_cfg().items() if e.get("max_of") == q.id]
    for max_qid, typ_qid in pairs:
        if not typ_qid or max_qid == typ_qid:
            continue
        other_qid = typ_qid if max_qid == q.id else max_qid
        other = _merged_q_values(conn, org, other_qid).get(row_id)
        oq = load_questions().get(other_qid)
        v_other = _comparable(oq, other) if (oq and other) else None
        if v_other is None:
            continue
        v_max, v_typ = (v_now, v_other) if max_qid == q.id else (v_other, v_now)
        if v_max < v_typ:
            out.append("The maximum here (%s) sits below the typical/target value (%s) for the same level — "
                       "worth a quick check." % (pos.fmt_value(v_max, q.unit_block()),
                                                 pos.fmt_value(v_typ, q.unit_block())))
            break
    return out


@app.put("/api/submission/draft")
async def save_draft(request: Request):
    user, org = require_editor(request)
    require_data_terms(get_conn(), org)
    body = await request.json()
    qid = body.get("question_id")
    row_id = body.get("matrix_row_id") or ""
    q = load_questions().get(qid)
    if q is None:
        raise HTTPException(404, "Unknown question")
    value = body.get("value")
    if value is not None and NA_RE.match(str(value).strip() or ""):
        value = NA_CANON          # one canonical N/A spelling end-to-end
    errors, warnings = validate_answer(q, value if value is not None else "", row_id)
    conn = get_conn()
    if errors:
        # the ONLY refusals: malformed / impossible input — never plausibility
        return {"ok": False, "errors": errors, "warnings": warnings}
    conn.execute(
        "INSERT INTO drafts(org_id, question_id, matrix_row_id, value, updated_at) "
        "VALUES (?,?,?,?,datetime('now')) "
        "ON CONFLICT(org_id, question_id, matrix_row_id) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
        (org["org_id"], qid, row_id, value))
    conn.commit()
    if value not in (None, ""):
        warnings = warnings + cross_field_warnings(conn, org, q, row_id, value)
    return {"ok": True, "errors": [], "warnings": warnings}


@app.post("/api/submission/confirm-value")
async def confirm_value(request: Request):
    """The user pressed 'yes, that's right' on a soft warning. The value is
    already saved (warnings never gate saving) — this records the override
    quietly (who/field/value/threshold) so David can scan confirmed outliers
    later. Logging only; nothing is ever blocked or altered."""
    user, org = require_editor(request)
    body = await request.json()
    qid = body.get("question_id")
    row_id = body.get("matrix_row_id") or ""
    q = load_questions().get(qid)
    if q is None:
        raise HTTPException(404, "Unknown question")
    value = body.get("value")
    if value is not None and NA_RE.match(str(value).strip() or ""):
        value = NA_CANON
    conn = get_conn()
    _e, warnings = validate_answer(q, value if value is not None else "", row_id)
    warnings += cross_field_warnings(conn, org, q, row_id, value)
    hard_min, soft_min, soft_max = soft_thresholds(q)
    cfg = validation_cfg().get(qid) or {}
    threshold = j({"soft_min": soft_min, "soft_max": soft_max,
                   "monotonic": cfg.get("monotonic"), "max_of": cfg.get("max_of")})
    for w in warnings:
        conn.execute(
            "INSERT INTO validation_overrides(org_id, user_email, question_id, matrix_row_id, value, warning, threshold) "
            "VALUES (?,?,?,?,?,?,?)",
            (org["org_id"], user["email"], qid, row_id, str(value), w, threshold))
    conn.commit()
    return {"ok": True, "logged": len(warnings)}


@app.post("/api/submission/validate")
async def validate_all(request: Request):
    user, org = require_editor(request)
    conn = get_conn()
    questions = org_visible_questions(org)
    drafts = {}
    for r in conn.execute("SELECT * FROM drafts WHERE org_id=?", (org["org_id"],)):
        drafts[(r["question_id"], r["matrix_row_id"] or "")] = r["value"]
    answers = org_answers_for(org)
    merged = dict(answers)
    merged.update({k: v for k, v in drafts.items() if v not in (None, "")})
    problems, unanswered_required = [], []
    for qid, q in questions.items():
        if q.is_required and not any(k[0] == qid and (v or "").strip() for k, v in merged.items()):
            unanswered_required.append({"question_id": qid, "title": q.display_title,
                                        "superpower": q.superpower,
                                        "section": q.sub_power or "General"})
        for (kq, krow), v in merged.items():
            if kq != qid:
                continue
            errs, _w = validate_answer(q, v or "", krow)
            if errs:
                problems.append({"question_id": qid, "title": q.display_title,
                                 "matrix_row_id": krow, "errors": errs})
    return {"problems": problems, "unanswered_required": unanswered_required}


@app.post("/api/submission/submit")
async def submit(request: Request):
    user, org = require_editor(request)
    require_data_terms(get_conn(), org)
    conn = get_conn()
    if org["source"] == "signup" and not org["classified"]:
        raise HTTPException(400, "Complete the 'About your organisation' step before submitting.")
    validation = await validate_all(request)
    if validation["problems"]:
        raise HTTPException(400, "Fix the highlighted answers before submitting.")
    drafts = conn.execute("SELECT * FROM drafts WHERE org_id=?", (org["org_id"],)).fetchall()
    if not drafts:
        raise HTTPException(400, "Nothing new to submit.")
    now_rows = 0
    for d in drafts:
        v = (d["value"] or "").strip()
        # answers are versioned: every accepted value is appended to history
        conn.execute(
            "INSERT INTO answers_history(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,?,?,?,?)",
            (org["org_id"], CURRENT_SNAPSHOT, d["question_id"], d["matrix_row_id"], v or None))
        if v == "":
            conn.execute("DELETE FROM answers WHERE org_id=? AND snapshot_id=? AND question_id=? AND matrix_row_id=?",
                         (org["org_id"], CURRENT_SNAPSHOT, d["question_id"], d["matrix_row_id"]))
        else:
            conn.execute(
                "INSERT OR REPLACE INTO answers(org_id, snapshot_id, question_id, matrix_row_id, value, submitted_at) "
                "VALUES (?,?,?,?,?,datetime('now'))",
                (org["org_id"], CURRENT_SNAPSHOT, d["question_id"], d["matrix_row_id"], v))
            now_rows += 1
    conn.execute("DELETE FROM drafts WHERE org_id=?", (org["org_id"],))
    conn.commit()
    completion = completion_pct(conn, dict(org))
    if completion >= TARGET_PCT:
        conn.execute("UPDATE orgs SET submission_complete=1 WHERE org_id=?", (org["org_id"],))
        conn.commit()
    # aggregates refresh synchronously (≈2s); peer group size updates live
    run_snapshot(CURRENT_SNAPSHOT, verbose=False)
    invalidate_payloads()
    return {"ok": True, "answers_saved": now_rows,
            "completion_pct": completion,
            "benchmark_unlocked": completion >= TARGET_PCT}


# ========================================================== METRIC COMMENTARY ==

def _commentary_stance(percentile, polarity):
    """Same thresholds and polarity adjustment as the card pill."""
    if percentile is None or polarity in (None, "neutral"):
        return None
    adj = 100 - percentile if polarity == "lower_is_better" else percentile
    return "ahead" if adj > 55 else "behind" if adj < 45 else "in line"


def build_commentary_payload(conn, org, user, qid, dim, value):
    """The grounded payload: exactly the figures the metric page shows for
    this cut, nothing else. Shared by the endpoint and the adversarial QA
    harness so the harness attacks the real path."""
    q = org_visible_questions(org).get(qid)
    p = payloads().get(qid)
    if q is None or p is None:
        return None
    if dim == "industry" and not value:
        value = org.get("industry")
    if dim == "fte_band" and not value:
        value = org.get("fte_band")
    cut = {"dim": dim, "value": value}
    if dim == "group":
        row = conn.execute("SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
                           (value or "", org["org_id"])).fetchone()
        if row is None:
            cut = {"dim": "all", "value": None}   # foreign/stale id: never another org's group
        else:
            cut["label"] = row["name"]
            cut["criteria"] = uj(row["criteria_json"], {})
    tb = twin_blocks_if_needed(conn, org, cut) if cut["dim"] in ("twin", "group") else None
    card = assemble_card(q, p, org, org_answers_for(org), cut,
                         {qid: tb.get(qid)} if tb else None, make_entitled(user, org))
    blk = card.get("block") or {}
    you = card.get("you") or {}
    # scored selects carry their direction-corrected percentile in card.score
    # (the same source the pill uses) — without this, an ahead/behind scored
    # metric would read as positionless prevalence (QA phase-6 defect 6-D1)
    pctl = you.get("percentile")
    pol = card.get("polarity")
    sc = card.get("score") or {}
    if pctl is None and (you.get("display") or you.get("label")) and sc.get("percentile") is not None:
        pctl = sc["percentile"]
        pol = sc.get("polarity") or pol
    payload = {
        "metric": card["title"],
        "definition": card.get("definition") or "",
        "cut_label": card["cut"]["label"],
        "n": card["n"],
        "suppressed": bool(card.get("suppressed")),
        "polarity": pol,
        "you": you.get("display") or you.get("label"),
        "percentile": pctl,
        "stance": _commentary_stance(pctl, pol),
        "illustrative_sample_data": bool(get_meta("synthetic_pool", True)),
    }
    if blk.get("p50") is not None:
        payload["peer_median_display"] = pos.fmt_value(blk["p50"], q.unit_block())
        payload["peer_p25_display"] = pos.fmt_value(blk["p25"], q.unit_block()) if blk.get("p25") is not None else None
        payload["peer_p75_display"] = pos.fmt_value(blk["p75"], q.unit_block()) if blk.get("p75") is not None else None
    if blk.get("options"):
        top = max(blk["options"], key=lambda o: o.get("pct") or 0)
        payload["most_common"] = "\u201c%s\u201d" % top["label"]
        payload["most_common_share"] = top.get("pct")
        if you.get("label"):
            mine = next((o for o in blk["options"] if o["label"] == you["label"]), None)
            payload["your_answer_peer_share"] = mine and mine.get("pct")
            payload["you"] = "\u201c%s\u201d" % you["label"]
    return payload


@app.post("/api/metric-commentary")
async def metric_commentary(request: Request):
    """AI commentary for one metric on one cut: grounded ONLY in the figures
    on the page (the same assembled card), validated post-generation, cached
    per org+metric+cut until the underlying numbers change."""
    if not AI_COMMENTARY:
        raise HTTPException(403, "AI commentary isn't enabled yet.")
    user, org = require_user(request)
    body = await request.json()
    qid = body.get("question_id")
    conn = get_conn()
    dim = body.get("cut") if body.get("cut") in ("all", "industry", "fte_band", "twin", "group") else "all"
    value = body.get("cut_value")
    payload = build_commentary_payload(conn, org, user, qid, dim, value)
    if payload is None:
        raise HTTPException(404, "That metric isn't part of your benchmark.")

    cut_key = dim + "::" + (value or "")
    phash = hashlib.sha256(j(payload).encode()).hexdigest()[:16]
    caveats = {"illustrative": bool(payload["illustrative_sample_data"])}
    if not body.get("force"):
        row = conn.execute(
            "SELECT * FROM metric_commentary WHERE org_id=? AND question_id=? AND cut_key=? AND payload_hash=?",
            (org["org_id"], qid, cut_key, phash)).fetchone()
        if row:
            return {"parts": uj(row["text"], {}), "source": row["source"], "cached": True,
                    "generated_at": row["created_at"], "caveats": caveats}
    res = claude_api.generate_metric_commentary(payload)
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], qid, cut_key, phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False, "caveats": caveats}


# ============================================================ METRIC REQUESTS ==

NOTIFY_EMAIL = os.environ.get("LUMI_NOTIFY_EMAIL", "david@lumi.example")


def send_notification(subject, body):
    """Best-effort email. SMTP isn't configured in this environment, so this
    logs to console like every other outbound mail; when LUMI_SMTP_HOST is set
    it sends for real with no other changes. Never raises — the stored row is
    the source of truth."""
    host = os.environ.get("LUMI_SMTP_HOST")
    if host:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = os.environ.get("LUMI_SMTP_FROM", "noreply@lumi.example")
            msg["To"] = NOTIFY_EMAIL
            msg["Subject"] = subject
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("LUMI_SMTP_PORT", "587")), timeout=10) as smtp:
                if os.environ.get("LUMI_SMTP_USER"):
                    smtp.starttls()
                    smtp.login(os.environ["LUMI_SMTP_USER"], os.environ.get("LUMI_SMTP_PASS", ""))
                smtp.send_message(msg)
            return "sent"
        except Exception as e:
            print("[lumi] EMAIL SEND FAILED (%s) — request is stored regardless:\n%s\n%s" % (e, subject, body))
            return "failed"
    print("\n[lumi] EMAIL (not configured — logged only) to %s\n  Subject: %s\n%s\n" % (NOTIFY_EMAIL, subject, body))
    return "logged"


@app.post("/api/metric-requests")
async def create_metric_request(request: Request):
    user, org = require_user(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Tell us what you'd like to benchmark first.")
    if len(text) > 500 or len((body.get("notes") or "")) > 2000:
        raise HTTPException(400, "That's a little long — a sentence or two is perfect.")
    source = body.get("source") if body.get("source") in ("button", "search", "ask-lumi") else "button"
    notes = (body.get("notes") or "").strip() or None
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO metric_requests(org_id, user_id, requested_text, notes, source) VALUES (?,?,?,?,?)",
        (org["org_id"], user["user_id"], text, notes, source))
    conn.commit()
    status = send_notification(
        "lumi metric request: %s" % text[:80],
        "Requested metric: %s\nNotes: %s\nFrom: %s (%s, %s)\nSource: %s\nWhen: %s\nRequest id: %d"
        % (text, notes or "—", user["display_name"] or user["email"], user["email"],
           org["name"], source, datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), cur.lastrowid))
    return {"ok": True, "id": cur.lastrowid, "notification": status}


# =================================================================== SHARES ==

@app.get("/api/shares")
async def list_shares(request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    shares = []
    for r in conn.execute("SELECT * FROM shares WHERE org_id=? ORDER BY created_at DESC", (org["org_id"],)):
        audit = [dict(a) for a in conn.execute(
            "SELECT sa.action, sa.at, u.email FROM share_audit sa LEFT JOIN users u ON u.user_id=sa.user_id "
            "WHERE sa.share_token=? ORDER BY sa.at", (r["token"],))]
        shares.append({
            "token": r["token"], "kind": r["kind"], "config": uj(r["config_json"], {}),
            "created_at": r["created_at"], "expires_at": r["expires_at"],
            "revoked": r["revoked_at"] is not None, "url": "/share/%s" % r["token"],
            "audit": audit,
        })
    return {"shares": shares}


@app.post("/api/shares")
async def create_share(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    kind = body.get("kind")
    if kind not in ("boardpack", "dashboard"):
        raise HTTPException(400, "Unknown share type")
    config = body.get("config") or {}
    if kind == "boardpack":
        conn = get_conn()
        if not conn.execute("SELECT 1 FROM board_packs WHERE pack_id=? AND org_id=?",
                            (config.get("pack_id"), org["org_id"])).fetchone():
            raise HTTPException(404, "Board pack not found")
    expiry_days = body.get("expiry_days")
    expires = None
    if expiry_days in (7, 30, 90):
        expires = (datetime.utcnow() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    import secrets
    token = secrets.token_urlsafe(24)
    conn = get_conn()
    conn.execute(
        "INSERT INTO shares(token, org_id, kind, config_json, created_by, expires_at) VALUES (?,?,?,?,?,?)",
        (token, org["org_id"], kind, j(config), user["user_id"], expires))
    conn.execute("INSERT INTO share_audit(share_token, action, user_id) VALUES (?,?,?)",
                 (token, "created", user["user_id"]))
    conn.commit()
    return {"ok": True, "token": token, "url": "/share/%s" % token}


@app.delete("/api/shares/{token}")
async def revoke_share(token: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    row = conn.execute("SELECT * FROM shares WHERE token=? AND org_id=?", (token, org["org_id"])).fetchone()
    if not row:
        raise HTTPException(404, "Share not found")
    conn.execute("UPDATE shares SET revoked_at=datetime('now') WHERE token=?", (token,))
    conn.execute("INSERT INTO share_audit(share_token, action, user_id) VALUES (?,?,?)",
                 (token, "revoked", user["user_id"]))
    conn.commit()
    return {"ok": True}


def get_live_share(token):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM shares WHERE token=? AND revoked_at IS NULL "
        "AND (expires_at IS NULL OR expires_at > datetime('now'))", (token,)).fetchone()
    return row


@app.get("/api/share/{token}/data")
async def share_data(token: str, request: Request):
    """Read-only data for a share link — same assembly code, suppression and
    entitlement as the owning org's own users. No login required."""
    share = get_live_share(token)
    if not share:
        raise HTTPException(404, "This share link is no longer available.")
    conn = get_conn()
    org = dict(conn.execute("SELECT * FROM orgs WHERE org_id=?", (share["org_id"],)).fetchone())
    config = uj(share["config_json"], {})
    pseudo_user = {"role": "viewer"}
    entitled = make_entitled(pseudo_user, org)
    if share["kind"] == "boardpack":
        row = conn.execute("SELECT * FROM board_packs WHERE pack_id=? AND org_id=?",
                           (config.get("pack_id"), org["org_id"])).fetchone()
        if not row:
            raise HTTPException(404, "Board pack not found")
        return {"kind": "boardpack", "org_name": org["name"],
                "payload": uj(row["payload_json"]), "narrative": uj(row["narrative_json"]),
                "created_at": row["created_at"]}
    # dashboard share: overview + the org's pinned/starter cards under a fixed cut
    cut = config.get("cut") or {"dim": "all"}
    if cut.get("dim") in ("twin", "group"):
        cut = {"dim": "all"}  # bespoke groups never exposed on anonymous links
    answers = pos.get_org_answers(conn, org["org_id"], CURRENT_SNAPSHOT)
    items = pos.position_items(org["org_id"], cut, org_visible_questions(org), payloads(), answers, entitled, None)
    summary = pos.overview_summary(items)
    co = pos.callouts(items, org_visible_questions(org), k=3)
    cards = []
    layout_row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=''",
                              (org["org_id"],)).fetchone()
    layout = uj(layout_row["layout_json"], []) if layout_row else \
        [{"question_id": it["question_id"], "row_id": it["row_id"], "size": 1}
         for it in (pos.top_gaps(items, 8) + pos.top_strengths(items, 4))]
    seen = set()
    for slot in layout[:12]:
        qid = slot.get("question_id")
        if qid in seen:
            continue
        seen.add(qid)
        q = org_visible_questions(org).get(qid)
        p = payloads().get(qid)
        if q is None or p is None or not entitled(q):
            continue
        cards.append(assemble_card(q, p, org, answers, cut, None, entitled))
    return {"kind": "dashboard", "org_name": org["name"], "cut": cut,
            "headline": summary,
            "callouts": {"strengths": [c["text"] for c in co["strengths"]],
                         "gaps": [c["text"] for c in co["gaps"]]},
            "cards": cards,
            "peer_pool": get_meta("peer_pool", {})}


# ================================================================== STATIC ===

@app.get("/share/{token}")
async def share_page(token: str):
    return FileResponse(os.path.join(WEB_DIR, "share.html"))


@app.get("/")
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


# ================================================================== STARTUP ==

DEMO_ADMIN = ("director@thornbridge.example", "lumi-demo-2026")
DEMO_VIEWER = ("ceo@thornbridge.example", "lumi-view-2026")
DEMO_CONTRIBUTOR = ("analyst@thornbridge.example", "lumi-data-2026")


def backfill_terms(conn):
    """Map pre-existing accounts onto the layered-terms model:
    - every existing user is treated as having accepted the Platform Terms;
    - any org with users and contributed data is treated as having accepted
      the Data Contribution Terms (its first admin, so demos aren't blocked)."""
    for u in conn.execute(
            "SELECT user_id, org_id FROM users WHERE user_id NOT IN "
            "(SELECT user_id FROM terms_acceptances WHERE kind='platform')").fetchall():
        conn.execute("INSERT INTO terms_acceptances(org_id, user_id, kind, version) VALUES (?,?,?,?)",
                     (u["org_id"], u["user_id"], "platform", PLATFORM_TERMS_VERSION))
    for o in conn.execute(
            "SELECT o.org_id, o.clock_start FROM orgs o WHERE "
            "EXISTS (SELECT 1 FROM users u WHERE u.org_id=o.org_id) AND "
            "EXISTS (SELECT 1 FROM answers a WHERE a.org_id=o.org_id) AND "
            "NOT EXISTS (SELECT 1 FROM terms_acceptances t WHERE t.org_id=o.org_id "
            "            AND t.kind='data_contribution')").fetchall():
        admin = conn.execute(
            "SELECT user_id FROM users WHERE org_id=? AND role='admin' ORDER BY created_at LIMIT 1",
            (o["org_id"],)).fetchone()
        if admin is None:
            continue
        conn.execute("INSERT INTO terms_acceptances(org_id, user_id, kind, version) VALUES (?,?,?,?)",
                     (o["org_id"], admin["user_id"], "data_contribution", DATA_TERMS_VERSION))
        if not o["clock_start"]:
            conn.execute("UPDATE orgs SET clock_start=datetime('now') WHERE org_id=?", (o["org_id"],))
    conn.commit()


@app.on_event("startup")
def startup():
    init_schema()
    conn = get_conn()
    # core-set governance: backfill the library's versioning fields (one-time)
    # and capture the baseline release if none exists. Both idempotent.
    if releases.ensure_governance_backfill(conn):
        load_questions.cache_clear()
    releases.ensure_baseline(conn)
    global INDUSTRIES
    pool = get_meta("peer_pool", {})
    INDUSTRIES = sorted(pool.get("industries", {}).keys())
    # demo accounts attached to a registry-matched seed org
    demo_org = conn.execute(
        "SELECT * FROM orgs WHERE classified=1 AND normalized_name LIKE 'thornbridgeretail%'").fetchone()
    if demo_org is None:
        demo_org = conn.execute("SELECT * FROM orgs WHERE classified=1 LIMIT 1").fetchone()
    if demo_org is not None:
        for (email, pw), role in ((DEMO_ADMIN, "admin"), (DEMO_VIEWER, "viewer"),
                                  (DEMO_CONTRIBUTOR, "contributor")):
            if not auth_lib.find_user(email):
                auth_lib.create_user(demo_org["org_id"], email, pw, role,
                                     "Demo %s" % role.title())
        print("\n[lumi] Demo accounts on org '%s':" % demo_org["name"])
        print("       Admin      : %s / %s" % DEMO_ADMIN)
        print("       Contributor: %s / %s" % DEMO_CONTRIBUTOR)
        print("       Viewer     : %s / %s\n" % DEMO_VIEWER)
    backfill_terms(conn)
