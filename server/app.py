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
import claude_api
import retrieval
from db import get_conn, init_schema, j, uj, get_meta, set_meta
from library import load_questions, slugify
import positions as pos
import peer_twin
from aggregate import run_snapshot, coerce_number, SUPPRESSION_FLOOR

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
CURRENT_SNAPSHOT = 1
CORE_COMPLETION_THRESHOLD = 0.90

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


def effective_tier(user, org):
    if org["tier_entitlement"] == "full" and not user.get("preview_as_core"):
        return "full"
    return "core"


def make_entitled(user, org):
    tier = effective_tier(user, org)
    if tier == "full":
        return lambda q: True
    return lambda q: q.lumi_tier == "Core"


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
    if dim not in ("all", "industry", "fte_band", "twin"):
        dim = "all"
    cut = {"dim": dim, "value": value}
    if dim == "industry" and not value:
        cut["value"] = org.get("industry")
    if dim == "fte_band" and not value:
        cut["value"] = org.get("fte_band")
    return cut


def twin_blocks_if_needed(conn, org, cut):
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
        "tier": q.lumi_tier,
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
                    "polarity": (q.scoring_config or {}).get("polarity", "neutral"),
                }

    elif q.type == "matrix":
        rows = []
        for row in p.get("matrix_rows", []):
            rblk, _ = pos.matrix_row_block_for(row, cut, tb)
            v = coerce_number(org_answers.get((q.id, row["row_id"])))
            r_out = {
                "row_id": row["row_id"], "label": row["label"],
                "suppressed": bool(pos.is_suppressed(rblk)),
                "block": None if pos.is_suppressed(rblk) else strip_internal(rblk),
            }
            if v is not None:
                r_out["you"] = {"value": v, "display": pos.fmt_value(v, q.unit_block())}
                if not pos.is_suppressed(rblk):
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
    conn = get_conn()
    nn = re.sub(r"[^a-z0-9]", "", body["org_name"].lower())
    if conn.execute("SELECT 1 FROM orgs WHERE normalized_name=?", (nn,)).fetchone():
        raise HTTPException(400, "An organisation with that name already exists — ask your admin for an invite.")
    if auth_lib.find_user(body["email"]):
        raise HTTPException(400, "That email already has an account.")
    org_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO orgs(org_id, name, normalized_name, source, tier_entitlement, classified) "
        "VALUES (?,?,?,'signup','core',0)", (org_id, body["org_name"].strip(), nn))
    conn.commit()
    uid = auth_lib.create_user(org_id, body["email"], body["password"], "admin",
                               body.get("display_name"))
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
    completion = core_completion(conn, org)
    snaps = [dict(r) for r in conn.execute("SELECT snapshot_id, snapshot_date, collection_window, status FROM snapshots ORDER BY snapshot_id")]
    return {
        "user": {"email": user["email"], "role": user["role"], "display_name": user["display_name"],
                 "preview_as_core": bool(user["preview_as_core"])},
        "org": {"name": org["name"], "industry": org["industry"], "subsector": org["subsector"],
                "fte_band": org["fte_band"], "hq_region": org["hq_region"],
                "ownership_type": org["ownership_type"], "classified": bool(org["classified"]),
                "tier_entitlement": org["tier_entitlement"], "source": org["source"],
                "submission_complete": bool(org["submission_complete"])},
        "effective_tier": effective_tier(user, org),
        "core_completion_pct": completion,
        "benchmark_unlocked": bool(org["submission_complete"]) or completion >= CORE_COMPLETION_THRESHOLD * 100,
        "peer_pool": get_meta("peer_pool", {}),
        "snapshots": snaps,
    }


@app.post("/api/me/preview-core")
async def preview_core(request: Request):
    user, org = require_admin(request)
    if org["tier_entitlement"] != "full":
        raise HTTPException(400, "Preview is only available to full-tier organisations.")
    body = await request.json()
    conn = get_conn()
    conn.execute("UPDATE users SET preview_as_core=? WHERE user_id=?",
                 (1 if body.get("on") else 0, user["user_id"]))
    conn.commit()
    return {"ok": True}


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
    role = body.get("role") if body.get("role") in ("admin", "viewer") else "viewer"
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    if auth_lib.find_user(email):
        raise HTTPException(400, "That email already has a lumi account.")
    token = auth_lib.create_invite(org["org_id"], email, role, user["user_id"])
    link = "http://localhost:8060/#/invite/%s" % token
    print("\n[lumi] TEAM INVITE for %s (%s at %s):\n       %s\n" % (email, role, org["name"], link))
    return {"ok": True, "link": link, "expires_days": auth_lib.INVITE_TTL_DAYS}


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
    conn = get_conn()
    uid = auth_lib.create_user(row["org_id"], row["email"], body["password"], row["role"],
                               body.get("display_name"))
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
    for qid, q in load_questions().items():
        p = payloads().get(qid, {})
        out.append({
            "id": qid, "title": q.display_title, "superpower": q.superpower,
            "subpower": q.sub_power, "sub_power_order": q.sub_power_order,
            "type": q.type, "category": q.category, "tier": q.lumi_tier,
            "locked": not entitled(q), "answered": qid in answered_q,
            "n": (p.get("all") or {}).get("n", 0),
        })
    return {"questions": out}


@app.get("/api/benchmarks/{superpower}")
async def benchmarks_for_superpower(superpower: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    entitled = make_entitled(user, org)
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    answers = org_answers_for(org)
    cards = []
    for qid, q in load_questions().items():
        if q.superpower != superpower:
            continue
        p = payloads().get(qid)
        if p is None:
            continue
        cards.append(assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None, entitled))
    cards.sort(key=lambda c: (c["sub_power_order"] or 999, c["title"]))
    return {"superpower": superpower, "cut": cut, "cards": cards}


@app.get("/api/benchmark/{qid}")
async def single_benchmark(qid: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    q = load_questions().get(qid)
    p = payloads().get(qid)
    if q is None or p is None:
        raise HTTPException(404, "Unknown metric")
    entitled = make_entitled(user, org)
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    card = assemble_card(q, p, org, org_answers_for(org), cut,
                         {qid: tb.get(qid)} if tb else None, entitled)
    # opportunity panel for £-model metrics
    mm = next((m for m in pos.MONEY_METRICS if m["question_id"] == qid), None)
    if mm and not card["locked"] and q.polarity != "neutral":
        money = pos.money_opportunities(conn, org, load_questions(), payloads(),
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
    return {
        "industries": pool.get("industries", {}),
        "fte_bands": pool.get("fte_bands", {}),
        "twin_available": twin is not None,
        "org_industry": org["industry"], "org_fte_band": org["fte_band"],
    }


# ================================================================= OVERVIEW ==

def build_items(request, org, user, cut):
    conn = get_conn()
    entitled = make_entitled(user, org)
    tb = twin_blocks_if_needed(conn, org, cut) if cut.get("dim") == "twin" else None
    return pos.position_items(org["org_id"], cut, load_questions(), payloads(),
                              org_answers_for(org), entitled, tb), tb


@app.get("/api/overview")
async def overview(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    cut = parse_cut(request, org)
    items, tb = build_items(request, org, user, cut)
    summary = pos.overview_summary(items)
    co = pos.callouts(items, load_questions(), k=3)
    money = pos.money_opportunities(conn, org, load_questions(), payloads(),
                                    org_answers_for(org), cut, tb)
    pool = get_meta("peer_pool", {})
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    return {
        "org": {"name": org["name"], "industry": org["industry"], "fte_band": org["fte_band"],
                "hq_region": org["hq_region"], "classified": bool(org["classified"])},
        "cut": cut,
        "peer_pool": pool,
        "snapshot": {"date": snap["snapshot_date"], "window": snap["collection_window"]},
        "headline": summary,
        "callouts": {"strengths": [c["text"] for c in co["strengths"]],
                     "gaps": [c["text"] for c in co["gaps"]],
                     "strength_items": [c["item"] for c in co["strengths"]],
                     "gap_items": [c["item"] for c in co["gaps"]]},
        "opportunity": {
            "total_savings_to_p50_gbp": money["total_savings_to_p50_gbp"],
            "total_investment_to_p50_gbp": money["total_investment_to_p50_gbp"],
            "items": [{"label": i["label"], "direction": i["direction"],
                       "to_p50_gbp": i["to_p50_gbp"], "question_id": i["question_id"]}
                      for i in money["items"]],
            "fte_known": money["fte_known"], "indicative": True,
        },
        "movement": {"available": False,
                     "message": "First benchmark — movement appears from your next cycle."},
    }


# ================================================================== MY DATA ==

@app.get("/api/my-data")
async def my_data(request: Request):
    user, org = require_user(request)
    answers = org_answers_for(org)
    questions = load_questions()
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
                     "unit": q.unit_block(), "tier": q.lumi_tier})
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
    return {
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
    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=?",
                       (org["org_id"], user["user_id"])).fetchone()
    if row:
        return {"layout": uj(row["layout_json"], []), "source": "user"}
    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=''",
                       (org["org_id"],)).fetchone()
    if row:
        return {"layout": uj(row["layout_json"], []), "source": "org_default"}
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
    tb = twin_blocks_if_needed(conn, org, cut) if cut.get("dim") == "twin" else None
    sector_cut = {"dim": "industry", "value": org["industry"]} if org["industry"] else None
    return pos.gap_register(conn, org, load_questions(), payloads(), org_answers_for(org),
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
    w.writerow(["Superpower", "Sub-power", "Category", "Practice / policy", "Tier",
                "Your status", "In place", "Peer adoption %", "Sector adoption %", "Gap", "n"])
    for r in reg["rows"]:
        w.writerow([r["superpower"], r["subpower"], r["category"], r["name"], r["tier"],
                    r["org_status"], "" if r["in_place"] is None else ("Yes" if r["in_place"] else "No"),
                    "suppressed" if r["suppressed"] else r["peer_adoption_pct"],
                    r["sector_adoption_pct"] if r["sector_adoption_pct"] is not None else "",
                    r["gap"] if r["gap"] is not None else "", r["n"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=lumi-gap-register.csv"})


# ================================================================== ANALYST ==

@app.post("/api/analyst")
async def analyst(request: Request):
    user, org = require_user(request)
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    conn = get_conn()
    qids = retrieval.search_questions(question, limit=6)
    if not qids:
        return {"answer": "I couldn't match that to anything in the lumi benchmark set. "
                          "Try naming the metric, practice or benefit you're interested in.",
                "chips": [], "matched": []}
    answers = org_answers_for(org)
    entitled = make_entitled(user, org)
    questions = load_questions()
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
            "How common is a formal flexible working policy?",
            "What does the peer median look like for regretted attrition?",
            "Which benefits are most commonly offered by organisations our size?",
            "How does our agency usage compare with our sector?",
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
    money = pos.money_opportunities(conn, org, load_questions(), payloads(),
                                    org_answers_for(org), cut, tb)
    reg = build_gap_register(request, user, org, cut)
    pool = get_meta("peer_pool", {})
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    cut_label = "All peers" if cut["dim"] == "all" else (
        cut.get("value") if cut["dim"] == "industry" else
        "%s FTE" % cut.get("value") if cut["dim"] == "fte_band" else "Organisations like you")
    if cut["dim"] == "industry":
        cut_n = pool.get("industries", {}).get(cut.get("value"), 0)
    elif cut["dim"] == "fte_band":
        cut_n = pool.get("fte_bands", {}).get(cut.get("value"), 0)
    elif cut["dim"] == "twin":
        twin = peer_twin.compute_twin(conn, org["org_id"])
        cut_n = len(twin["peer_org_ids"]) if twin else 0
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


def core_completion(conn, org):
    """% of Core-tier questions with an answer (matrix counts if any row answered)."""
    questions = load_questions()
    core_q = [q for q in questions.values() if q.lumi_tier == "Core"]
    if not core_q:
        return 100.0
    answered = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=?",
        (org["org_id"], CURRENT_SNAPSHOT))}
    drafted = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
        (org["org_id"],))}
    have = answered | drafted
    return round(100.0 * sum(1 for q in core_q if q.id in have) / len(core_q), 1)


@app.get("/api/submission/state")
async def submission_state(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    questions = load_questions()
    answered = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=?",
        (org["org_id"], CURRENT_SNAPSHOT))}
    drafted = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
        (org["org_id"],))}
    have = answered | drafted
    sections = []
    sp_order = []
    for q in questions.values():
        if q.superpower not in sp_order:
            sp_order.append(q.superpower)
    for sp in sp_order:
        qs = [q for q in questions.values() if q.superpower == sp]
        sections.append({
            "superpower": sp, "questions": len(qs),
            "answered": sum(1 for q in qs if q.id in have),
            "core_questions": sum(1 for q in qs if q.lumi_tier == "Core"),
            "core_answered": sum(1 for q in qs if q.lumi_tier == "Core" and q.id in have),
        })
    firmographics_done = all(org.get(f) for f in ("industry", "fte_band", "hq_region", "ownership_type"))
    return {
        "firmographics_done": firmographics_done,
        "firmographics": {f: org.get(f) for f in FIRMOGRAPHIC_FIELDS},
        "choices": {"industries": INDUSTRIES, "fte_bands": FTE_BANDS,
                    "regions": REGIONS, "ownership_types": OWNERSHIP},
        "sections": sections,
        "core_completion_pct": core_completion(conn, org),
        "threshold_pct": CORE_COMPLETION_THRESHOLD * 100,
        "submission_complete": bool(org["submission_complete"]),
        "is_admin": user["role"] == "admin",
    }


@app.put("/api/submission/firmographics")
async def put_firmographics(request: Request):
    user, org = require_admin(request)
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
            "Ownership_Type": org.get("ownership_type")}
    for attr, values in [(a, space["cat_values"][a]) for a in (
            "Industry", "FTE_Band", "Ownership_Type", "Archetype", "Turnover_Band",
            "Avg_Tenure_Band", "HR_Maturity", "Operating_Model", "Business_Maturity")]:
        mine = decl.get(attr)
        vec += [1.0 if mine == v else 0.0 for v in values]
    for a in ("Workforce_Frontline_%", "Workforce_Shift_%", "Workforce_Unionised_%"):
        vec.append(0.5)
    conn.execute("UPDATE orgs SET similarity_vector_json=? WHERE org_id=?", (j(vec), org["org_id"]))
    conn.execute("DELETE FROM peer_twin_cache WHERE org_id=?", (org["org_id"],))


@app.get("/api/submission/section/{superpower}")
async def submission_section(superpower: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    questions = load_questions()
    answers = org_answers_for(org)
    drafts = {}
    for r in conn.execute("SELECT * FROM drafts WHERE org_id=?", (org["org_id"],)):
        drafts[(r["question_id"], r["matrix_row_id"] or "")] = r["value"]
    out = []
    for qid, q in questions.items():
        if q.superpower != superpower:
            continue
        entry = {
            "id": qid, "text": q.text, "title": q.display_title, "help_text": q.help_text,
            "subpower": q.sub_power, "sub_power_order": q.sub_power_order,
            "type": q.type, "category": q.category, "tier": q.lumi_tier,
            "options": [{"code": o["code"], "label": o["label"], "is_na": bool(o.get("is_na"))}
                        for o in sorted(q.options or [], key=lambda o: o.get("order", 0))],
            "unit_display_name": q.unit_display_name,
            "unit": q.unit_block(),
            "validation": q.validation, "tolerance": q.tolerance,
            "is_required": q.is_required,
            "matrix": q.matrix if q.type == "matrix" else None,
            "matrix_rows": [{"row_id": rid, "label": lbl} for rid, lbl in q.matrix_row_defs()],
        }
        if q.type == "matrix":
            entry["current"] = {rid: (drafts.get((qid, rid)) if (qid, rid) in drafts else answers.get((qid, rid)))
                                for rid, _l in q.matrix_row_defs()}
        else:
            entry["current"] = drafts.get((qid, "")) if (qid, "") in drafts else answers.get((qid, ""))
        out.append(entry)
    out.sort(key=lambda e: (e["sub_power_order"] or 999, e["title"]))
    return {"superpower": superpower, "questions": out}


def validate_answer(q, value, row_id=""):
    """Validation comes from the library, not invented. Returns (errors, warnings)."""
    errors, warnings = [], []
    v = (value or "").strip()
    if v == "":
        return errors, warnings
    val = q.validation or {}
    tol = q.tolerance or {}
    if val.get("max_length") and len(v) > int(val["max_length"]):
        errors.append("Answer is too long (max %s characters)." % val["max_length"])
    if val.get("pattern"):
        try:
            if not re.match(val["pattern"], v):
                errors.append("Answer doesn't match the expected format.")
        except re.error:
            pass
    if q.type in ("numeric", "matrix"):
        f = coerce_number(v)
        if f is None:
            errors.append("Please enter a number.")
            return errors, warnings
        if val.get("integer_only") and f != int(f):
            errors.append("Please enter a whole number.")
        if val.get("max_decimals") is not None:
            parts = v.replace(",", "").split(".")
            if len(parts) == 2 and len(parts[1]) > int(val["max_decimals"]):
                warnings.append("We'll round this to %s decimal places." % val["max_decimals"])
        hard_min, hard_max = tol.get("hard_min"), tol.get("hard_max")
        soft_min, soft_max = tol.get("soft_min"), tol.get("soft_max")
        if hard_min is not None and f < hard_min:
            errors.append("Must be at least %s." % pos.fmt_value(hard_min, q.unit_block()))
        if hard_max is not None and f > hard_max:
            errors.append("Must be no more than %s." % pos.fmt_value(hard_max, q.unit_block()))
        if not errors:
            if soft_min is not None and f < soft_min:
                warnings.append("This is below the typical range (%s+) — please confirm it's right."
                                % pos.fmt_value(soft_min, q.unit_block()))
            if soft_max is not None and f > soft_max:
                warnings.append("This is above the typical range (up to %s) — please confirm it's right."
                                % pos.fmt_value(soft_max, q.unit_block()))
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


@app.put("/api/submission/draft")
async def save_draft(request: Request):
    user, org = require_admin(request)
    body = await request.json()
    qid = body.get("question_id")
    row_id = body.get("matrix_row_id") or ""
    q = load_questions().get(qid)
    if q is None:
        raise HTTPException(404, "Unknown question")
    value = body.get("value")
    errors, warnings = validate_answer(q, value if value is not None else "", row_id)
    conn = get_conn()
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    conn.execute(
        "INSERT INTO drafts(org_id, question_id, matrix_row_id, value, updated_at) "
        "VALUES (?,?,?,?,datetime('now')) "
        "ON CONFLICT(org_id, question_id, matrix_row_id) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
        (org["org_id"], qid, row_id, value))
    conn.commit()
    return {"ok": True, "errors": [], "warnings": warnings}


@app.post("/api/submission/validate")
async def validate_all(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    questions = load_questions()
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
                                        "superpower": q.superpower})
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
    user, org = require_admin(request)
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
    completion = core_completion(conn, dict(org))
    if completion >= CORE_COMPLETION_THRESHOLD * 100:
        conn.execute("UPDATE orgs SET submission_complete=1 WHERE org_id=?", (org["org_id"],))
        conn.commit()
    # aggregates refresh synchronously (≈2s); peer group size updates live
    run_snapshot(CURRENT_SNAPSHOT, verbose=False)
    invalidate_payloads()
    return {"ok": True, "answers_saved": now_rows,
            "core_completion_pct": completion,
            "benchmark_unlocked": completion >= CORE_COMPLETION_THRESHOLD * 100}


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
    pseudo_user = {"role": "viewer", "preview_as_core": 0}
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
    if cut.get("dim") == "twin":
        cut = {"dim": "all"}  # twin never exposed on anonymous links
    answers = pos.get_org_answers(conn, org["org_id"], CURRENT_SNAPSHOT)
    items = pos.position_items(org["org_id"], cut, load_questions(), payloads(), answers, entitled, None)
    summary = pos.overview_summary(items)
    co = pos.callouts(items, load_questions(), k=3)
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
        q = load_questions().get(qid)
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


@app.on_event("startup")
def startup():
    init_schema()
    conn = get_conn()
    global INDUSTRIES
    pool = get_meta("peer_pool", {})
    INDUSTRIES = sorted(pool.get("industries", {}).keys())
    # demo accounts attached to a registry-matched seed org
    demo_org = conn.execute(
        "SELECT * FROM orgs WHERE classified=1 AND normalized_name LIKE 'thornbridgeretail%'").fetchone()
    if demo_org is None:
        demo_org = conn.execute("SELECT * FROM orgs WHERE classified=1 LIMIT 1").fetchone()
    if demo_org is not None:
        for (email, pw), role in ((DEMO_ADMIN, "admin"), (DEMO_VIEWER, "viewer")):
            if not auth_lib.find_user(email):
                auth_lib.create_user(demo_org["org_id"], email, pw, role,
                                     "Demo %s" % role.title())
        print("\n[lumi] Demo accounts on org '%s':" % demo_org["name"])
        print("       Admin : %s / %s" % DEMO_ADMIN)
        print("       Viewer: %s / %s\n" % DEMO_VIEWER)
