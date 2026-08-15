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
import functools
import hashlib
import io
import json
import logging
import os
import re
import urllib.parse
import secrets
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Structured-ish logging to stdout (journald/CloudWatch capture it in production).
# Failure paths log at WARNING/ERROR so an operator can alert on severity, not grep prints.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [lumi] %(message)s")
log = logging.getLogger("lumi")


def _load_local_env():
    """Load server/.env.local (git-ignored) into the environment at startup, so
    local secrets like ANTHROPIC_API_KEY are present however the server is launched
    — terminal, the preview runner, a process manager — without exporting them by
    hand each time. A real environment variable always wins (the file only fills
    gaps), and a missing or malformed file never blocks startup."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        pass
    except Exception as e:                       # never let a bad env file crash boot
        print("[lumi] .env.local present but could not be read: %s" % e)


_load_local_env()

from anyio import to_thread
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import auth as auth_lib
import hashlib
import refresh_policy

import claude_api
import identity
import strategy_align
import strategy_diag
import pulses as pulses_mod
import payments as payments_mod
import releases
import retrieval
import guide
import signals as signals_mod
import notifications
from db import get_conn, init_schema, j, uj, get_meta, set_meta
from library import load_questions, slugify
import positions as pos
import practice_axis
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
# percentile bounds on the favourable-adjusted scale. 35-65 (David, 2026-06-14):
# below P35 = below market, P35-65 = on market, above P65 = above market. Kept in
# sync with cardPosition (card colour) and thresholds.behind_percentile so the
# card colour, the tile verdict and the signal all agree. Tune via env.
_band = os.environ.get("LUMI_MARKET_BAND", "35-65").split("-")
MARKET_BAND_LOW, MARKET_BAND_HIGH = float(_band[0]), float(_band[1])
# 3 RATIFIED (fix class D, David 2026-07-11): the effective live floor was always 3 — the
# mp_config defaults block silently overrode this env value (positions.py, hero classified
# path) until that override was removed. The old "5" here was never a considered decision;
# env is now the single authority. Domain floor (polarised-question count) is orthogonal to
# the n<5 suppression floor (peer count).
DOMAIN_MIN_POLARISED = int(os.environ.get("LUMI_DOMAIN_MIN_POLARISED", "3"))
# Board-pack graduated DISPLAY thresholds (Sprint 2 ruling, 2026-07-02 — the Mercer
# convention): the n<5 anonymity floor stays absolute everywhere; above it, quartiles
# show at n>=7 and the P10/P90 tails at n>=10, masked cells rendering as '—'. Display
# policy only — engine suppression untouched. David-tunable.
PACK_QUARTILE_MIN_N = int(os.environ.get("LUMI_PACK_QUARTILE_MIN_N", "7"))
PACK_TAIL_MIN_N = int(os.environ.get("LUMI_PACK_TAIL_MIN_N", "10"))
# minimum distinct positioned questions for a tile's INDICATIVE verdict when
# the strict floor isn't met (David-tunable; evidence counts ship to the UI)
TILE_MIN_POSITIONED = int(os.environ.get("LUMI_TILE_MIN_POSITIONED", "1"))
# Self-service pulse launch fee (2026-06-22): the DEFAULT fee a member pays to
# launch their own pulse to the community, in whole GBP (staff can override per
# pulse at approval). Stored/charged in pence. David-tunable.
PULSE_LAUNCH_FEE_PENCE = int(os.environ.get("LUMI_PULSE_LAUNCH_FEE_GBP", "750")) * 100
# Hero verdict (2026-06-13, David): the headline reads where the centre of
# gravity sits — net lean = (above-below)/pool. The verdict is "on market"
# unless that net lean clears this threshold either way. ONE value drives both
# the verdict word and the gauge needle, so they can never disagree (the
# original two-measures-in-one-component defect). 0.25 (wider than the old
# 0.15) lets a near-even split like 34/46/14 read "On market". Env-tunable.
VERDICT_NET_LEAN = float(os.environ.get("LUMI_VERDICT_NET_LEAN",
                                        os.environ.get("LUMI_VERDICT_MARGIN", "0.25")))
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
AI_STRATEGY = os.environ.get("LUMI_AI_STRATEGY", "on").lower() == "on"
# Per-domain AI summary (Pass 3) — its OWN kill switch. Default OFF: go-live to ALL members
# is RESERVED for David and gated on the compliance track (DPA / privacy notice / sub-processor
# review — this ships AI-generated, member-facing content derived from member data). The
# adversarial gate (qa_domain_summary.py) is green and the voice is signed off, so it's enabled
# per-environment with LUMI_AI_DOMAIN_SUMMARY=on (demo / preview) until David explicitly
# authorizes launch. (The 2026-06-28 default-on flip was unauthorized and reverted.)
AI_DOMAIN_SUMMARY = os.environ.get("LUMI_AI_DOMAIN_SUMMARY", "off").lower() == "on"

# Per-org cap on paid AI GENERATIONS (pre-prod audit 2026-08-12: most AI endpoints had
# no rate limit — one scripted member could burn unbounded spend). Generous by design:
# peeks/cache hits never count, only true generation calls. Complements (never replaces)
# the per-surface kill switches and the board-pack cap.
_ai_gen_calls = defaultdict(list)   # org_id -> [timestamps]
AI_GEN_MAX_PER_HOUR = int(os.environ.get("LUMI_AI_GEN_MAX_PER_HOUR", "60"))

def _ai_generation_or_429(org):
    now = time.time()
    key = org["org_id"]
    _ai_gen_calls[key] = [t for t in _ai_gen_calls[key] if now - t < 3600]
    if len(_ai_gen_calls[key]) >= AI_GEN_MAX_PER_HOUR:
        raise HTTPException(429, "This hour's AI writing budget is used up — cached readings still open instantly; try again shortly.")
    _ai_gen_calls[key].append(now)

# ===================================================================== AI INSIGHTS GATE ==
# The MASTER switch for ALL member-facing AI insight features (commentary, analyst, board
# pack, pulse, strategy diagnosis, domain summary). Default OFF — this holds production dark
# regardless of the per-feature flags above (five of which still default on), so AI-generated,
# member-facing content derived from member data ships to NOBODY until the prod env flip.
# Solicitor sign-off was RECEIVED on 2026-06-28 (legitimate-interest/opt-out basis, legal text
# finalised, Anthropic named as sub-processor). The code default stays OFF as a backstop: the
# go-live is the single deploy-env action LUMI_AI_INSIGHTS_ENABLED=on, which is David's to make.
# Every AI feature renders iff:  AI_INSIGHTS_ENABLED on  AND  its own flag on  AND  the member
# has consented (per AI_CONSENT_MODE). Demo/review runs the COMPLETE flow on test data via
# LUMI_AI_INSIGHTS_ENABLED=on; real members see nothing while it's off. See GO_LIVE_CHECKLIST.md.
AI_INSIGHTS_ENABLED = os.environ.get("LUMI_AI_INSIGHTS_ENABLED", "off").lower() == "on"
# Lawful-basis switch — the solicitor RULED legitimate interest (opt-out) on 2026-06-28, with a
# documented LIA on file. AI Insights are on by default and a member can disable them in Settings
# (records a withdrawal). Built to support EITHER basis without a code change.
#   opt_out (default, legitimate interest): AI on unless the member withdraws.
#   opt_in  (consent):                      no AI for a member until they explicitly consent.
# Accept BOTH env names so neither silently no-ops: the go-live checklist historically
# named this AI_CONSENT_MODE, the codebase convention is LUMI_AI_CONSENT_MODE. Canonical
# (LUMI_-prefixed, like every other switch) wins; the un-prefixed alias is honoured too.
AI_CONSENT_MODE = (os.environ.get("LUMI_AI_CONSENT_MODE")
                   or os.environ.get("AI_CONSENT_MODE") or "opt_out").lower()
# The AI-Insights terms version the consent/withdrawal record pins. Finalised to "1.0" on solicitor
# sign-off (2026-06-28); a future material change bumps this and can force re-consent.
AI_TERMS_VERSION = "1.0"
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
    answered_ct, basis_ct = completion_counts(conn, org)
    completion = 100.0 if not basis_ct else round(100.0 * answered_ct / basis_ct, 1)
    unlocked = org_unlocked(conn, org, completion)
    terms = org_data_terms(conn, org["org_id"])
    clock_start = org["clock_start"]
    # Drafts are autosaved but only committed to the benchmark on submit (which
    # clears them). A non-empty drafts table therefore means "saved, but not yet
    # submitted" — the cue for the unsubmitted-changes reminder.
    pending_changes = conn.execute(
        "SELECT COUNT(*) c FROM drafts WHERE org_id=?", (org["org_id"],)).fetchone()["c"]
    days_left = None
    if clock_start and not unlocked:
        try:
            started = datetime.strptime(clock_start[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            started = datetime.utcnow()
        # PH-PAY-2 R3: suspension pauses the clock. clock_start is IMMUTABLE
        # (the original moment of data-terms acceptance is a fact worth
        # keeping); the pause is an ACCUMULATED suspended_seconds counter
        # incremented at each reactivation — a single delta from
        # deactivated_at would be right once and wrong on the second
        # suspension. While CURRENTLY suspended the clock is frozen at the
        # suspension moment (elapsed stops accruing).
        _o = org if isinstance(org, dict) else dict(org)   # sqlite Row has no .get
        now = datetime.utcnow()
        if _o.get("deactivated_at"):
            try:
                now = min(now, datetime.strptime(_o["deactivated_at"][:19], "%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError):
                pass
        elapsed = now - started - timedelta(seconds=_o.get("suspended_seconds") or 0)
        days_left = max(0, CLOCK_DAYS - elapsed.days)
    # team invited = any pending invite OR any member beyond the founding Admin —
    # the "invite your team" setup step's done-state (persistent onboarding checklist)
    team_invited = bool(conn.execute(
        "SELECT 1 FROM invites WHERE org_id=? LIMIT 1", (org["org_id"],)).fetchone()
        or conn.execute("SELECT 1 FROM users WHERE org_id=? AND role!='admin' LIMIT 1",
                        (org["org_id"],)).fetchone())
    return {
        "core_pct": completion,
        "target_pct": TARGET_PCT,
        "basis_total": basis_ct,          # the ~82 key questions the gate measures (for honest effort copy)
        "basis_answered": answered_ct,    # exact count answered — drives "N key questions to unlock" proximity copy
        "insights_unlocked": unlocked,
        "terms_accepted": terms is not None,
        "team_invited": team_invited,
        "clock_started": bool(clock_start),
        "clock_start": clock_start,
        "days_left": days_left,
        "reduced": bool(clock_start) and (not unlocked) and days_left <= 0,
        "pending_changes": pending_changes,
    }


def maybe_send_clock_reminder(conn, org, state):
    """Gentle reminders at 7 and 1 days left. Triggers are stored so email
    fires automatically once SMTP is configured; in-app banners are driven
    by days_left regardless."""
    if state["insights_unlocked"] or state["days_left"] is None:
        return
    # PH-PAY-2 R3a: no clock nagging while suspended — and the guard sits BEFORE
    # reminders_json is marked, so the reminder is HELD (fires after
    # reactivation if still due), never silently consumed.
    _o = org if isinstance(org, dict) else dict(org)
    if _o.get("deactivated_at"):
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
    admins = [r["user_id"] for r in conn.execute(
        "SELECT user_id FROM users WHERE org_id=? AND role='admin'", (org["org_id"],))]
    org_name = (identity.org_display(org["org_id"]) or {}).get("name")
    # addressed to each Admin (defaulting to the ops inbox meant members never
    # actually received the 7-day/1-day warnings once SMTP went live)
    for uid in admins:
        addr = identity.user_email(uid)
        if not addr:
            print("[identity-routing] ANOMALY: no identity-side email for an existing admin "
                  "(present reward-side) — clock reminder SKIPPED for that recipient; run "
                  "identity_recon: dual-write integrity is in question.")
            continue
        send_notification(
            "lumi: %s left to unlock your insights" % ("7 days" if due == "7d" else "1 day"),
            "Hello %s,\n\nYour reward benchmark is waiting — you're %s%% of the way to unlocking "
            "your insights (£ opportunities, board pack and biggest gaps). Complete your reward "
            "questions in the next %s to unlock them.\n\n— lumi · UK reward benchmarking"
            % (org_name if org_name else "(org name unavailable — identity record missing)",
               state["core_pct"], "7 days" if due == "7d" else "day"),
            to=addr)


TRONC_SECTORS = {"Hospitality, Leisure & Travel", "Retail & Consumer Goods"}


def org_visible_questions(org):
    """The member-facing question set for ONE organisation: the live core
    minus sector-module metrics the org isn't eligible for. 2026.1: the 5
    tronc/tips metrics are a hospitality module — shown to hospitality/retail
    organisations, hidden otherwise. Module questions are never is_required
    (invariant, asserted by qa_release) so the unlock gate is org-independent.

    r3s4 (ruled 2026-07-18): SECTOR-SCOPE layer on top — data/sector_scopes.json
    declares per-metric sector lists; outside the scope the metric is FULLY
    hidden (entry, chart, signals, peer base). Declaration-driven, no bespoke
    per-metric code; narrows the module where both apply (tips: hospitality
    only, though the module also shows to retail)."""
    qs = visible_questions()
    ind = org["industry"] if org is not None else None
    if ind not in TRONC_SECTORS:
        qs = {qid: q for qid, q in qs.items() if not q.module}
    scopes = sector_scopes().get("scopes") or {}
    if scopes:
        qs = {qid: q for qid, q in qs.items()
              if qid not in scopes or ind in (scopes[qid].get("sectors") or [])}
    return qs


_SECTOR_SCOPES_CACHE = {"mtime": None, "data": {}}


def sector_scopes():
    """data/sector_scopes.json, mtime-cached (hot-reload like the lens map)."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "sector_scopes.json")
    try:
        mt = os.path.getmtime(path)
        if _SECTOR_SCOPES_CACHE["mtime"] != mt:
            with open(path, encoding="utf-8") as f:
                _SECTOR_SCOPES_CACHE["data"] = json.load(f)
            _SECTOR_SCOPES_CACHE["mtime"] = mt
    except OSError:
        _SECTOR_SCOPES_CACHE["data"] = {}
    return _SECTOR_SCOPES_CACHE["data"]


_AB_CACHE = {"mtime": None, "data": {}}


def applicable_bases():
    """data/applicable_bases.json metrics map, mtime-cached (r3sw9 N/A-not-on-graph
    mechanism). LUMI_AB_CONFIG overrides the path so gate servers and staged runs
    never read the served copy (r3sw7 doctrine)."""
    path = os.environ.get("LUMI_AB_CONFIG") or os.path.join(
        os.path.dirname(__file__), "..", "data", "applicable_bases.json")
    try:
        mt = os.path.getmtime(path)
        if _AB_CACHE["mtime"] != mt:
            with open(path, encoding="utf-8") as f:
                _AB_CACHE["data"] = json.load(f).get("metrics") or {}
            _AB_CACHE["mtime"] = mt
    except OSError:
        _AB_CACHE["data"] = {}
    return _AB_CACHE["data"]


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
                # SEAM (S3 path 20): the request context carries REWARD columns only —
                # name/normalized_name never enter it. similarity_vector_json, created_at
                # and unlocked_release are dropped too: unread from this row (peer_twin
                # queries its own; created_at reads are other tables'; unlocked_release is
                # write-only). Identity for display is fetched via identity.py per path.
                org = conn.execute(
                    "SELECT org_id, source, tier_entitlement, classified, industry, subsector, "
                    "fte_band, hq_region, ownership_type, registry_json, submission_complete, "
                    "clock_start, insights_unlocked_at, reminders_json, unionised_level, "
                    "hr_maturity, business_maturity, operating_model, default_cut, deactivated_at, "
                    "suspended_seconds "
                    "FROM orgs WHERE org_id=?", (user["org_id"],)).fetchone()
                # soft-deactivated org: its members carry no request context at all —
                # every authed route sees the same 401 a signed-out user gets.
                if org is not None and org["deactivated_at"]:
                    return await call_next(request)
                request.state.user = dict(user)
                request.state.org = dict(org) if org else None
        return await call_next(request)


app.add_middleware(SessionMiddleware)


class TxnHygieneMiddleware(BaseHTTPMiddleware):
    """End-of-request transaction discipline: whatever a handler wanted to keep, it
    committed — anything still pending on the shared thread-local connections is
    rolled back so it can never bleed into the NEXT request's commit. Closes the
    HTTPException-after-partial-write residue the 500-handler rollback (pre-prod
    audit loop 1) couldn't reach: FastAPI converts HTTPExceptions to responses
    before that handler fires. No-ops (cheaply) when nothing is pending."""

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        finally:
            for _rb in (get_conn, identity.get_conn):
                try:
                    c = _rb()
                    if c.in_transaction:
                        c.rollback()
                except Exception:
                    pass


app.add_middleware(TxnHygieneMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Secure-configuration hardening for the hosted service (Cyber Essentials
    'Secure Configuration'). Sets defence-in-depth response headers on every
    response. HSTS is emitted only on an https deployment (never on localhost dev,
    where it would pin the browser to https and break http). CSP is deliberately
    conservative: the app uses inline style attributes throughout (htm/React), so
    style-src allows 'unsafe-inline'; scripts are same-origin vendored files only."""
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'")
        if (os.environ.get("LUMI_BASE_URL") or "").strip().lower().startswith("https://"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp


app.add_middleware(SecurityHeadersMiddleware)
# Compress everything over 1KB — the benchmark JSON, app.css and the vendored
# JS all shipped raw before this; one line is a 5-10× transfer cut on cold load.
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402 (grouped with its consumer)
app.add_middleware(GZipMiddleware, minimum_size=1024)


async def _json(request):
    """Parse the request body as JSON, returning a clean 400 instead of a raw 500 on
    malformed input (§4.7). Every handler immediately calls .get() on the result, so a
    valid-JSON-but-not-an-object body ([] or "x") must 400 here too, not AttributeError
    into the 500 handler (pre-prod audit 2026-08-12)."""
    try:
        out = await request.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON.")
    if not isinstance(out, dict):
        raise HTTPException(400, "Request body must be a JSON object.")
    return out


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


# The super-admin allowlist (2026-08-03, David's ruling: "the super admin will be
# david@lumihr.co.uk only"). Belt-and-braces OVER the platform_admin flag: even if
# a stray UPDATE ever flips the flag on another account, the gate still refuses it.
# Deliberately an env override (LUMI_SUPER_ADMINS, comma-separated) rather than a
# hard-coded literal, so adding staff later is a config decision, not a code edit.
SUPER_ADMIN_EMAILS = frozenset(
    e.strip().lower() for e in
    os.environ.get("LUMI_SUPER_ADMINS", "david@lumihr.co.uk").split(",") if e.strip())


def require_platform_admin(request):
    """lumi-staff tier (back office, D2). ABOVE the org roles: a cross-tenant
    privilege, so it deliberately returns NO org — every /api/admin/* route
    reads across tenants explicitly and must never scope to one org. The flag
    rides on request.state.user (get_session_user does SELECT u.*), so it is
    checked on every request like any other session fact. Two conditions, both
    required: the platform_admin flag AND membership of the pinned allowlist."""
    if request.state.user is None:
        raise HTTPException(401, "Not signed in")
    if not request.state.user.get("platform_admin"):
        raise HTTPException(403, "Staff access only")
    if (request.state.user.get("email") or "").lower() not in SUPER_ADMIN_EMAILS:
        raise HTTPException(403, "Staff access only")
    return request.state.user


# ----------------------------------------------------------- layered terms --
PLATFORM_TERMS_VERSION = "1.0"
DATA_TERMS_VERSION = "1.0"
LEGAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "legal")
LEGAL_FILES = {
    "platform": "platform-terms-v1.0.md",
    "data_contribution": "data-contribution-terms-v1.0.md",
    "dpa": "data-sharing-agreement-dpa-v1.0.md",
    "privacy": "privacy-notice-v1.0.md",
    "cookies": "cookie-policy-v1.0-draft.md",
    "subprocessors": "sub-processors-v1.0.md",
    "ai_insights": "ai-insights-terms-v1.0.md",
}

# The Legal index (chrome spec section 4.3): each document is its own page;
# the "How lumi works" hub is the index. Public read access — these must be
# reachable from the auth screens (the enforceability footer) before any
# account exists. Each entry's `draft` flag reflects its own review status:
# platform terms, data-contribution terms, the DPA, the privacy notice, the
# sub-processor list and the AI Insights terms are final v1.0 (privacy + sub-
# processors finalised 2026-06-28: real rights contact + named AWS/SES). Only the
# cookie policy remains in draft pending its analytics description.
LEGAL_INDEX = [
    {"key": "platform", "title": "Terms of Use", "draft": False},
    {"key": "privacy", "title": "Privacy Notice", "draft": False},
    {"key": "cookies", "title": "Cookie Policy", "draft": True},
    {"key": "data_contribution", "title": "Data Contribution Terms", "draft": False},
    {"key": "dpa", "title": "Data Sharing Agreement (DPA)", "draft": False},
    {"key": "subprocessors", "title": "Sub-processor List", "draft": False},
    {"key": "ai_insights", "title": "AI Insights Terms", "draft": False},
]


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
        "SELECT t.* FROM terms_acceptances t "
        "WHERE t.org_id=? AND t.kind='data_contribution' ORDER BY t.accepted_at DESC, t.id DESC LIMIT 1",
        (org_id,)).fetchone()


def require_data_terms(conn, org):
    """Submission routes are blocked until the org's Admin has accepted the
    Data Contribution Terms. Seed orgs never hit this (no users)."""
    if org_data_terms(conn, org["org_id"]) is None:
        raise HTTPException(403, "Review and accept the Data Contribution Terms to begin — "
                                 "your organisation's Admin accepts them once, on the Submit data page.")


# --------------------------------------------------- AI Insights consent (per user) --
# Consent is recorded in the SAME terms_acceptances audit log (kind="ai_insights"), and
# withdrawal as kind="ai_insights_withdrawn" — an immutable, versioned, per-user event
# trail (Article 30). The CURRENT state is the member's latest ai_insights-family event.
def record_ai_consent(conn, org_id, user_id, version=None):
    record_acceptance(conn, org_id, user_id, "ai_insights", version or AI_TERMS_VERSION)


def record_ai_withdrawal(conn, org_id, user_id, version=None):
    record_acceptance(conn, org_id, user_id, "ai_insights_withdrawn", version or AI_TERMS_VERSION)


def purge_ai_cache(conn, org_id):
    """Data-minimisation on opt-out (C3): when a member turns AI Insights off, delete the org's
    cached AI-generated summaries so no derived AI output persists — not merely gated from display.
    The two on-demand caches are cleared (they regenerate lawfully only if a still-consented member
    next views the page; under opt_out a withdrawn member's routes 403 before any regeneration).
    Board packs are member-INITIATED saved exports (created_by, a deliberate document), handled
    under the normal erasure/retention process, not this automatic cache purge."""
    conn.execute("DELETE FROM domain_summary WHERE org_id=?", (org_id,))
    conn.execute("DELETE FROM metric_commentary WHERE org_id=?", (org_id,))
    conn.execute("DELETE FROM analyst_log WHERE org_id=?", (org_id,))
    conn.commit()


def ai_consent_state(conn, user_id):
    """The member's latest AI-consent event → {event, version, at}. event is
    'ai_insights' (granted), 'ai_insights_withdrawn', or None (never decided)."""
    row = conn.execute(
        "SELECT kind, version, accepted_at FROM terms_acceptances "
        "WHERE user_id=? AND kind IN ('ai_insights','ai_insights_withdrawn') "
        "ORDER BY accepted_at DESC, id DESC LIMIT 1", (user_id,)).fetchone()
    if row is None:
        return {"event": None, "version": None, "at": None}
    return {"event": row["kind"], "version": row["version"], "at": row["accepted_at"]}


def is_ai_consented(state, mode=None):
    """Resolve the consent EVENT into an effective yes/no under the lawful basis.
    opt_out: active unless explicitly withdrawn. opt_in: active only if explicitly granted."""
    mode = mode or AI_CONSENT_MODE
    if mode == "opt_out":
        return state["event"] != "ai_insights_withdrawn"
    return state["event"] == "ai_insights"


def ai_gate(conn, user):
    """The single source of truth for whether a member may see AI insights. Returns the
    full state so /api/me can expose it and the AI routes can enforce it identically."""
    state = ai_consent_state(conn, user["user_id"])
    consented = is_ai_consented(state)
    return {
        "master": AI_INSIGHTS_ENABLED,          # the global switch (David flips post-solicitor)
        "mode": AI_CONSENT_MODE,                # opt_in | opt_out
        "consent_event": state["event"],        # ai_insights | ai_insights_withdrawn | None
        "consented": consented,                 # effective yes/no under the mode
        "consented_at": state["at"],
        "version": state["version"],
        "terms_version": AI_TERMS_VERSION,
        # needs_decision: opt_in member who has never decided → show the consent gate (item 6)
        "needs_decision": (AI_CONSENT_MODE == "opt_in" and state["event"] is None),
        "active": AI_INSIGHTS_ENABLED and consented,   # master AND consent (per-feature flag still ANDs on top)
    }


def ai_feature_on(gate, feature_flag):
    """A specific AI feature renders iff the master gate is on, the member consents, AND the
    feature's own kill-switch is on. This is what /api/me publishes and the routes enforce."""
    return bool(gate["active"] and feature_flag)


def require_ai(conn, user, feature_flag):
    """Server-side enforcement for an AI route — defence in depth behind the features map."""
    gate = ai_gate(conn, user)
    if not ai_feature_on(gate, feature_flag):
        raise HTTPException(403, "AI Insights aren't enabled for you. They may be switched off "
                                 "for the platform, or awaiting your consent in Settings.")


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
    # custom-group blocks memoise per (snapshot, criteria) and were never cleared —
    # after a submit, group cuts (including the org-default landing group) served
    # pre-submit numbers for the life of the process (pre-prod audit 2026-08-12)
    peer_twin.invalidate_group_caches()


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
    # unknown vocabulary never echoes into a LABEL: cut_value=-999999 used to render
    # "-999999 FTE" on the card (P3 sweep 2026-08-13). Same fallback the group path
    # takes: an unrecognised value resolves to All peers.
    if dim == "industry" and cut.get("value"):
        known = {r[0] for r in get_conn().execute("SELECT DISTINCT industry FROM orgs WHERE industry IS NOT NULL")}
        if cut["value"] not in known:
            return {"dim": "all", "value": None}
    if dim == "fte_band" and cut.get("value"):
        known = {r[0] for r in get_conn().execute("SELECT DISTINCT fte_band FROM orgs WHERE fte_band IS NOT NULL")}
        if cut["value"] not in known:
            return {"dim": "all", "value": None}
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


def assemble_card(q, p, org, org_answers, cut, twin_blocks_by_q, entitled, market_band=None, prevalence_band=None):
    """Everything one benchmark card needs, fully sanitised."""
    locked = not entitled(q)
    tb = (twin_blocks_by_q or {}).get(q.id)
    blk, cut_label = pos.block_for(p, cut, tb)
    _mp_ent = pos.market_position_config().get("metrics", {}).get(q.id) or {}
    # Diff 14: unbenchmarked = the seeded distribution carries no ruled authority
    # (not marginal/settled/floor). The distribution still renders, but NO peer
    # comparison does: no verdict, no "X in 10" lead, no percentile readouts.
    _unbench = bool(_mp_ent.get("unbenchmarked"))
    _ab = applicable_bases().get(q.id)
    base = {
        "id": q.id,
        "title": q.display_title,
        # r3sw9: declared applicable base — the chart + n cover only orgs where the
        # metric applies (data/applicable_bases.json; None for undeclared metrics)
        "base": ({"label": _ab.get("base_label") or "organisations where this applies",
                  "mode": _ab.get("mode"),
                  "excluded": (blk or {}).get("excluded_na", 0)} if _ab else None),
        "question_text": q.text,
        "help_text": q.help_text,
        "definition": q.definition,
        "superpower": q.superpower,
        "subpower": q.sub_power,
        "sub_power_order": q.sub_power_order,
        "type": q.type,
        "category": q.category,
        # key = one of the is_required questions the unlock gate measures; lets the
        # benchmark card flag its own relevance to the org's insight unlock (empty-state review)
        "is_required": q.is_required,
        "locked": locked,
        "chart_default": q.default_chart_type,
        "unit": q.unit_block(),
        "polarity": q.polarity,
        "cut": {"dim": cut["dim"], "value": cut.get("value"), "label": cut_label},
        "n": (blk or {}).get("n", 0), "n_real": (blk or {}).get("n_real", 0),
        "suppressed": bool(pos.is_suppressed(blk)),
        "movement": None,  # vs-last-period slot: populated once a second snapshot exists
        # firewall-reviewed market position (below/at/above), from the SAME Substance pool
        # the competitiveness gauge/donut counts (positions.pool_market_bands). null when
        # the metric isn't a positioned market rate (Approach / neutral / lower_is_better /
        # non-competitive / unclassified). Passed in per-request so a card's band can never
        # disagree with the donut count it sums into (Pass 2a, 2026-06-27).
        # Diff-14 disclosure layer: an unbenchmarked metric stays IN the donut pool (ruled
        # architecture) but its CARD must carry no market claim — the band is withheld here
        # like the readout/percentiles (pre-prod audit 2026-08-12: five unbenchmarked cards
        # leaked verdict text through the meaning line).
        "market_band": None if _unbench else market_band,
        # practice-prevalence band (match / common_alt / rarer) from the SAME prevalence_items
        # pool the §1 prevalence donut counts; null when not a prevalence-rated practice. Drives
        # the second (prevalence) chip dimension (prevalence-filtering Pass A, 2026-06-28).
        "prevalence_band": prevalence_band,
        # practice-class flag (Diff 4, 2026-07-14): computed HERE from the cached config so
        # every card path carries it (one implementation). Drives the "A practice choice"
        # chip + position-pill suppression; distinct from prevalence_band, which is null
        # for suppressed pools (that's the "low peer data" render state).
        "practice": (_mp_ent.get("class") in ("Practice", "Design")) and q.id not in pos.STRATEGY_CONFIG_IDS,
        "unbenchmarked": _unbench,
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
            if not base["suppressed"] and not _unbench:
                # unbenchmarked: the percentile/readout IS the numeric form of the
                # "X in 10 peers" claim — suppressed with the verdict (Diff 14)
                r = pos.percentile_rank(blk["_values"], v)
                you["percentile"] = round(r, 1)
                _th = pos.tie_halfwidth(blk["_values"], v)
                if _th:
                    you["tie_half"] = round(_th, 1)   # median-tie ⇒ at-market rule (client mirror)
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
            # the org's answer IS an N/A route (na_codes) — the metric can rank other orgs,
            # but no rank applies to THIS answer. Surfaced so the UI says "doesn't apply"
            # honestly instead of "not yet rated" (labelling doctrine 2026-08-12).
            if q.type != "multi_select":
                from aggregate import _norm_label as _nl
                _na = set((q.scoring_config or {}).get("na_codes") or [])
                if _na:
                    _code = {_nl(o["label"]): o["code"] for o in (q.options or [])}.get(_nl(raw))
                    if _code is not None and _code in _na:
                        base["you_na"] = True
        if q.type == "multi_select":
            base["readout"] = pos.SUPPRESSED_COPY if base["suppressed"] else None
        elif _unbench:
            base["readout"] = None   # Diff 14: no peer-comparison sentence on unbenchmarked
        else:
            base["readout"] = pos.readout_select(q, raw, blk, cut_label)
        sc_blk, _ = pos.score_block_for(p, cut, tb)
        if q.is_scored and raw is not None and not pos.is_suppressed(sc_blk):
            s = pos.score_answer_safe(q, raw)
            if s is not None:
                base["score"] = {
                    "you": round(s, 1),
                    "polarity": score_polarity(q),
                }
                if not _unbench:  # score percentile vs peers = the same claim class (Diff 14)
                    base["score"]["percentile"] = round(pos.percentile_rank(sc_blk["_scores"], s), 1)
                    _th = pos.tie_halfwidth(sc_blk["_scores"], s)
                    if _th:
                        base["score"]["tie_half"] = round(_th, 1)   # median-tie ⇒ at-market rule (client mirror)
                    base["score"]["peer_p50"] = sc_blk.get("p50")

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
                _row_est = row["row_id"] in pos.unbenchmarked_rows(q.id)
                if _row_est:
                    r_out["unbenchmarked"] = True   # r3sw6 split verdict: EST tier
                if not pos.is_suppressed(rblk) and "_values" in rblk and not _row_est:
                    r_out["you"]["percentile"] = round(pos.percentile_rank(rblk["_values"], v), 1)
                    _rth = pos.tie_halfwidth(rblk["_values"], v)
                    if _rth:
                        r_out["you"]["tie_half"] = round(_rth, 1)
            rows.append(r_out)
        base["matrix_rows"] = rows
        vis = [r for r in rows if not r["suppressed"]]
        if vis:
            you_rows = [r for r in vis if "you" in r and "percentile" in r["you"]]
            if you_rows:
                avg = sum(r["you"]["percentile"] for r in you_rows) / len(you_rows)
                base["readout"] = ("Across the %d comparable levels, your typical position is P%d."
                                   % (len(you_rows), int(round(avg))))
        if base["suppressed"]:
            base["readout"] = pos.SUPPRESSED_COPY
    return base


from aggregate import score_answer as _score_answer  # noqa: E402
pos.score_answer_safe = _score_answer


# ================================================================== AUTH ====

# Session cookie is marked Secure whenever the deployment is HTTPS (production is
# always https — base_url() rejects a non-localhost non-https LUMI_BASE_URL), so
# the token is never sent in cleartext; localhost dev (http) stays cookie-friendly.
def _cookie_secure():
    return (os.environ.get("LUMI_BASE_URL") or "").strip().lower().startswith("https://")


def _set_session_cookie(resp, token):
    resp.set_cookie(auth_lib.COOKIE_NAME, token, httponly=True, samesite="lax",
                    secure=_cookie_secure(), max_age=auth_lib.SESSION_TTL_DAYS * 86400)


def _clear_session_cookie(resp):
    # attributes must match the set-cookie for the browser to clear it
    resp.delete_cookie(auth_lib.COOKIE_NAME, samesite="lax", secure=_cookie_secure())


# A fixed bcrypt hash so a login attempt on an UNKNOWN email still runs a full
# verify — equal work on both branches closes the timing side-channel that would
# otherwise reveal which emails are registered (feeds enumeration + lockout DoS).
_DUMMY_PW_HASH = auth_lib.hash_password("lumi-timing-equaliser-not-a-real-password")


# MFA (email one-time code). Enforced in production to satisfy Cyber Essentials
# A7.16/A7.17 (MFA on every cloud-service account). Env-gated so dev/QA/gates run
# password-only (they can't read an emailed code); production sets LUMI_MFA=on.
def _mfa_enforced():
    return os.environ.get("LUMI_MFA", "").lower() in ("on", "1", "true", "yes")


def _send_mfa_code(email, code):
    # Delivered via send_notification, which console-logs until SMTP is live. NOTE:
    # enforced email-OTP in production REQUIRES a configured SMTP (LUMI_SMTP_HOST),
    # otherwise codes never reach users. The code itself is never logged elsewhere.
    # Returns the transport result ("sent"/"failed"/"logged") — the login and resend
    # endpoints refuse honestly on "failed" instead of stranding the user.
    return send_notification(
        "Your lumi sign-in code",
        "Hello,\n\nYour lumi sign-in code is:\n\n    %s\n\nEnter it to finish signing in. "
        "It expires in %d minutes. If you didn't try to sign in, you can ignore this email "
        "and consider changing your password.\n\n— lumi · UK reward benchmarking"
        % (code, auth_lib.MFA_TTL_MINUTES),
        to=email)


def _account_active_or_403(conn, user_id):
    """Shared post-auth gate: refuse a deactivated user or a deactivated org before a
    session is minted (used by both the direct-login and the MFA-verify paths)."""
    acct = conn.execute("SELECT disabled_at, org_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if acct and acct["disabled_at"]:
        raise HTTPException(403, "This account has been deactivated. Contact hello@lumihr.co.uk "
                                 "if you think this is a mistake.")
    if acct and conn.execute("SELECT 1 FROM orgs WHERE org_id=? AND deactivated_at IS NOT NULL",
                             (acct["org_id"],)).fetchone():
        raise HTTPException(403, "Your organisation's lumi membership is deactivated. "
                                 "Contact hello@lumihr.co.uk to reactivate it.")


@app.post("/api/auth/login")
async def login(request: Request):
    body = await _json(request)
    email = (body.get("email") or "").lower().strip()
    ip = request.client.host if request.client else "?"
    # Evaluate BOTH tiers (no `or` short-circuit) so the per-IP budget always
    # increments; key the strict tier per (email, IP) not bare email, so a remote
    # attacker can't lock a victim out of their own account by burning the email key.
    ip_hit = auth_lib.rate_limited("login-ip:%s" % ip)
    em_hit = auth_lib.rate_limited("login:%s|%s" % (email, ip))
    if ip_hit or em_hit:
        raise HTTPException(429, "Too many attempts — please wait a few minutes and try again.")
    user = auth_lib.find_user(email)
    # constant-ish work whether or not the email exists (timing equaliser)
    if not auth_lib.verify_password(body.get("password") or "", user["pw_hash"] if user else _DUMMY_PW_HASH) or not user:
        raise HTTPException(401, "That email and password don't match our records.")
    # soft-deactivate gates (back office, 2026-08-03): a correct password on a
    # deactivated account gets the honest message, not the credentials one.
    conn = get_conn()
    _account_active_or_403(conn, user["user_id"])
    # a CORRECT password releases this user's slice of the rate budget — the caps slow
    # guessing, they must not lock a NAT-shared office out through normal sign-ins
    auth_lib.rate_clear("login:%s|%s" % (email, ip))
    auth_lib.rate_clear("login-ip:%s" % ip)
    # MFA step-up (Cyber Essentials A7.16/A7.17): when enforced, a correct password
    # does NOT create a session — it mints a challenge and emails a one-time code;
    # the session is created only after /api/auth/mfa/verify.
    if _mfa_enforced():
        challenge, code = auth_lib.create_mfa_challenge(user["user_id"])
        # off the event loop (a hung relay froze EVERY request for the socket timeout)
        # and HONEST on failure: a 200 with a dead challenge stranded the user at the
        # code screen with no code coming (launch rehearsal 2026-08-13). Password is
        # already verified here, so a 503 leaks nothing.
        sent = await to_thread.run_sync(_send_mfa_code, email, code)
        if sent == "failed":
            raise HTTPException(503, "We couldn't send your sign-in code just now — "
                                     "please try again in a moment.")
        return JSONResponse({"ok": True, "mfa_required": True, "challenge": challenge})
    token = auth_lib.create_session(user["user_id"])
    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, token)
    return resp


@app.post("/api/auth/mfa/verify")
async def mfa_verify(request: Request):
    body = await _json(request)
    ip = request.client.host if request.client else "?"
    # brute-force guard on the 6-digit code endpoint (per-challenge attempt cap is in
    # verify_mfa_challenge; this bounds attempts across challenges from one IP too)
    if auth_lib.rate_limited("mfa-ip:%s" % ip):
        raise HTTPException(429, "Too many attempts — please wait a few minutes and try again.")
    uid = auth_lib.verify_mfa_challenge(body.get("challenge") or "", (body.get("code") or "").strip())
    if not uid:
        raise HTTPException(400, "That code is wrong or has expired. Request a new one.")
    conn = get_conn()
    _account_active_or_403(conn, uid)   # re-check active between password step and session
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, token)
    return resp


@app.post("/api/auth/mfa/resend")
async def mfa_resend(request: Request):
    body = await _json(request)
    ip = request.client.host if request.client else "?"
    if auth_lib.rate_limited("mfa-resend-ip:%s" % ip):
        raise HTTPException(429, "Too many requests — please wait a few minutes and try again.")
    uid = auth_lib.mfa_challenge_user(body.get("challenge") or "")
    if not uid:
        raise HTTPException(400, "Your sign-in attempt has expired — please sign in again.")
    challenge, code = auth_lib.create_mfa_challenge(uid)   # invalidates the old code
    _addr = identity.user_email(uid)
    if not _addr:
        # identity row missing its email = a recon anomaly; without this check the
        # sign-in code fell through send_notification's default recipient — the OPS
        # INBOX (P3 sweep 2026-08-13). Refuse loudly instead of misdelivering a bearer.
        log.error("mfa_resend: no identity email for user %s — recon anomaly", uid)
        raise HTTPException(500, "We couldn't send your code — please contact hello@lumihr.co.uk.")
    sent = await to_thread.run_sync(_send_mfa_code, _addr, code)
    if sent == "failed":
        raise HTTPException(503, "We couldn't send your sign-in code just now — "
                                 "please try again in a moment.")
    return {"ok": True, "challenge": challenge}


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(auth_lib.COOKIE_NAME)
    if token:
        auth_lib.destroy_session(token)
    resp = JSONResponse({"ok": True})
    _clear_session_cookie(resp)
    return resp


def _open_registration():
    """PH-PROV-1 §2.3: self-serve registration is CLOSED by default — membership is
    staff-provisioned. LUMI_OPEN_REGISTRATION=on reopens it (read per request so a
    gate server can grant it by env without code paths diverging). The route is
    retained, not deleted."""
    return os.environ.get("LUMI_OPEN_REGISTRATION", "").lower() in ("on", "true", "1")


@app.get("/api/auth/registration")
async def registration_posture():
    """Public, unauthenticated: is self-serve registration open? The register
    FORM reads this so a closed door is shown as a door, not discovered as a
    403 after the prospect has filled in the whole form (review #1)."""
    return {"open": _open_registration()}


@app.post("/api/auth/register")
async def register(request: Request):
    """New member organisation sign-up (tier: core)."""
    if not _open_registration():
        raise HTTPException(403, "lumi membership is set up for you by our team at the moment, "
                                 "rather than self-service. Email hello@lumihr.co.uk and we'll "
                                 "get your organisation started.")
    ip = request.client.host if request.client else "?"
    # per-IP throttle — mass-signup abuse guard (login and reset already rate-limit; §4.7)
    if auth_lib.rate_limited("register-ip:%s" % ip):
        raise HTTPException(429, "Too many sign-up attempts — please wait a few minutes and try again.")
    body = await _json(request)
    for f in ("org_name", "email", "password"):
        if not body.get(f):
            raise HTTPException(400, "Missing %s" % f)
    _pwerr = auth_lib.validate_password(body["password"], email=body.get("email"), org_name=body.get("org_name"))
    if _pwerr:
        raise HTTPException(400, _pwerr)
    if body.get("accept_platform_terms") is not True:
        raise HTTPException(400, "Please accept the Platform Terms of Use to create your account.")
    conn = get_conn()
    nn = re.sub(r"[^a-z0-9]", "", body["org_name"].lower())
    if identity.org_lookup_by_normalized(nn):
        raise HTTPException(400, "An organisation with that name already exists — ask your admin for an invite.")
    if auth_lib.find_user(body["email"]):
        raise HTTPException(400, "That email already has an account.")
    org_id = str(uuid.uuid4())
    # founding members: first year free with full access — the contribution
    # clock is about data, never payment (day-one experience brief).
    # clock_start stays NULL until the Admin accepts the Data Contribution
    # Terms — setup time must not eat into the 30 days.
    _insert_member_org(conn, org_id)   # shared with staff provisioning (PH-PROV-1 §2.1);
    conn.commit()                      # identity columns never written — org_register carries the name
    identity.shadow(identity.register_org_identity, org_id, body["org_name"].strip(), nn)
    uid = auth_lib.create_user(org_id, body["email"], body["password"], "admin",
                               body.get("display_name"))
    record_acceptance(conn, org_id, uid, "platform", PLATFORM_TERMS_VERSION)
    # AI Insights consent — UNBUNDLED from the platform terms (a separate, unticked-by-default
    # acknowledgment). opt_in: record only if the member explicitly ticked it; opt_out: no
    # record needed (absence of a withdrawal = active under legitimate interest). Never blocks
    # account creation — a member can decline AI and still use lumi.
    if AI_CONSENT_MODE == "opt_in" and body.get("accept_ai_insights") is True:
        record_ai_consent(conn, org_id, uid)
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, token)
    return resp


@app.post("/api/auth/request-reset")
async def request_reset(request: Request):
    body = await _json(request)
    email = (body.get("email") or "").strip()
    ip = request.client.host if request.client else "?"
    # key the strict tier per (email, IP) so an attacker can't stop a victim
    # receiving reset mail by burning the email key from elsewhere; IP tier bounds abuse
    if auth_lib.rate_limited("reset-ip:%s" % ip) or auth_lib.rate_limited("reset:%s|%s" % (email.lower(), ip)):
        raise HTTPException(429, "Too many attempts — please wait a few minutes.")
    user = auth_lib.find_user(email)
    if user:
        token = auth_lib.create_reset(user["user_id"])
        # a real member-facing email (send_notification console-logs it, link
        # included, until SMTP is configured — same dev flow, no dev-copy leak)
        # PH-PAY-2 R3b CARVE-OUT — DO NOT gate this on suspension: reset mail
        # STILL SENDS for a suspended org's members (sole-admin recovery is
        # exactly the case that needs it; the login gate, not the mail gate,
        # is what suspension means here). Only digest/signal mail is gated.
        # off the event loop (a hung relay froze every request); the failure path in
        # send_notification withholds bodies by default now, so the reset link can't
        # land in a production log — while the dev no-SMTP console path still prints
        # it for QA. The response stays the generic 200 either way — a transport 5xx
        # here would be an account-existence oracle.
        await to_thread.run_sync(
            functools.partial(
                send_notification,
                "Reset your lumi password",
                "Hello,\n\nSomeone asked to reset the lumi password for this address. If that was "
                "you, choose a new password here:\n\n%s/app#/reset/%s\n\nThe link expires in 2 hours. "
                "If you didn't ask for this, you can safely ignore this email — your password is "
                "unchanged.\n\n— lumi · UK reward benchmarking" % (base_url(minting=True), token),
                to=email))
    return {"ok": True, "message": "If that email has an account, we've sent a reset link to it. "
                                   "The link expires in 2 hours."}


@app.post("/api/auth/reset")
async def do_reset(request: Request):
    body = await _json(request)
    row = auth_lib.get_valid_reset(body.get("token") or "")
    if not row:
        raise HTTPException(400, "That reset link has expired or already been used.")
    conn = get_conn()
    # an individually-deactivated user can't set a new password (login stays blocked
    # regardless; refusing here avoids a pointless credential change). The suspended-
    # ORG sole-admin recovery carve-out is preserved — only per-USER disable is checked.
    _acct = conn.execute("SELECT disabled_at FROM users WHERE user_id=?", (row["user_id"],)).fetchone()
    if _acct and _acct["disabled_at"]:
        raise HTTPException(403, "This account has been deactivated. Contact hello@lumihr.co.uk.")
    _pwerr = auth_lib.validate_password(body.get("password") or "",
                                       email=identity.user_email(row["user_id"]))
    if _pwerr:
        raise HTTPException(400, _pwerr)
    ph = auth_lib.hash_password(body["password"])
    # step 5: pw_hash is identity-side only; identity.update_pw_hash below is the write.
    conn.execute("UPDATE password_resets SET used_at=datetime('now') WHERE token=?", (row["token"],))
    conn.commit()
    identity.shadow(identity.update_pw_hash, row["user_id"], ph)
    identity.shadow(identity.consume_password_reset, row["token"])
    # SECURITY: a password reset is the canonical post-compromise recovery — revoke
    # every existing session so a stolen/old cookie can't survive the reset. The user
    # is not auto-logged-in; they re-authenticate with the new password.
    identity.delete_sessions_for_user(row["user_id"])
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
    # AI features are now EFFECTIVE flags: master gate AND the member's consent AND the
    # per-feature kill-switch. So every existing client gate (me.features.X) automatically
    # respects the master switch + consent with no client change. ai_insights carries the
    # gate state for the settings toggle + the consent prompt.
    _aig = ai_gate(conn, user)
    _sp_cut, _sp_label, _sp_crit = _default_cut_info(conn, org)   # org default peer group for the client
    return {
        "contribution": contrib,
        "features": {"commentary": ai_feature_on(_aig, AI_COMMENTARY), "analyst": ai_feature_on(_aig, AI_ANALYST),
                     "boardpack": ai_feature_on(_aig, AI_BOARDPACK), "pulse_ai": ai_feature_on(_aig, AI_PULSE),
                     "domain_summary": ai_feature_on(_aig, AI_DOMAIN_SUMMARY)},
        "ai_insights": _aig,
        # the market band the engine uses (LUMI_MARKET_BAND) so the client colours
        # cards on the SAME line as the tiles + signals — single source of truth.
        "config": {"market_band": [MARKET_BAND_LOW, MARKET_BAND_HIGH],
                   # the pulse launch fee, so the price is visible BEFORE a member
                   # builds a survey (it used to appear only after review approval)
                   "pulse_launch_fee_pence": PULSE_LAUNCH_FEE_PENCE},
        "scope": {"superpowers": ACTIVE_SUPERPOWERS or sorted({q.superpower for q in vis.values()}),
                  "focused": bool(ACTIVE_SUPERPOWERS),
                  "question_count": len(vis)},
        "user": (lambda d: {"email": d.get("email"), "role": user["role"],
                            "display_name": d.get("display_name"),
                            "platform_admin": bool(user.get("platform_admin"))})(
                    identity.user_display(user["user_id"]) or {}),
        "org": {"name": (identity.org_display(org["org_id"]) or {}).get("name"),
                "industry": org["industry"], "subsector": org["subsector"],
                "fte_band": org["fte_band"], "hq_region": org["hq_region"],
                # the org's DEFAULT peer group (drives signals, alerts + everyone's landing view).
                # signal_peer_cut = raw (all/industry::X/fte_band::Y/group::gid); label + criteria
                # let the client name it and pre-fill the Settings multi-select. NULL = all-peers.
                "signal_peer_cut": org.get("default_cut"),
                "signal_peer_label": _sp_label,
                "signal_peer_criteria": _sp_crit,
                "ownership_type": org["ownership_type"], "classified": bool(org["classified"]),
                "profile_rich_complete": all(org.get(f) for f in PROFILE_RICH),
                "tier_entitlement": org["tier_entitlement"], "source": org["source"],
                "submission_complete": bool(org["submission_complete"]),
                "data_terms": (lambda t: {
                    "accepted": t is not None,
                    "accepted_by": t and (lambda d: (d or {}).get("display_name") or (d or {}).get("email")
                                          or "a former Admin")(identity.user_display(t["user_id"])),
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
    # P5-live: email and display_name come from the identity store (D6). The SELECT * stays
    # as it is — narrowing it is C6's separate fix class. Misses render unnamed, no fallback.
    _urows = list(conn.execute("SELECT * FROM users WHERE org_id=? ORDER BY created_at",
                               (org["org_id"],)))
    _uid = identity.user_display_batch([r["user_id"] for r in _urows])
    users = [{"email": (_uid.get(r["user_id"]) or {}).get("email"), "role": r["role"],
              "display_name": (_uid.get(r["user_id"]) or {}).get("display_name"),
              "created_at": r["created_at"]}
             for r in _urows]
    _irows = list(conn.execute(
        "SELECT * FROM invites WHERE org_id=? AND used_at IS NULL AND expires_at > datetime('now')",
        (org["org_id"],)))
    _iem = identity.invite_email_batch([r["token"] for r in _irows])
    invites = [{"email": _iem.get(r["token"]), "role": r["role"], "expires_at": r["expires_at"],
                "token": r["token"], "used": r["used_at"] is not None}
               for r in _irows]
    return {"users": users, "invites": invites if user["role"] == "admin" else []}


ROLE_LABELS = {"admin": "Admin", "contributor": "Contributor", "viewer": "Viewer"}


@app.post("/api/team/invite")
async def invite(request: Request):
    user, org = require_admin(request)
    body = await _json(request)
    email = (body.get("email") or "").strip()
    # PH-PROV-1b (2026-08-08): "Admins are made by promotion, never by invite"
    # is now an EXPLICIT refusal, not a silent downgrade — the inviter must
    # learn the rule, not discover a viewer where they expected an admin.
    # (The staff provisioning path keeps its founding-admin carve-out.)
    if body.get("role") == "admin":
        raise HTTPException(400, "Admins are made by promotion after joining, never by "
                                 "invite. Invite them as a contributor, then promote "
                                 "them from the Team page once they've joined.")
    role = body.get("role") if body.get("role") in ("contributor", "viewer") else "viewer"
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    # Email is globally unique, so an existing account genuinely can't accept a new
    # invite — but don't turn that into a cross-tenant membership oracle for an org
    # admin. Same-org: say so plainly (the admin sees their own team anyway).
    # Otherwise: a non-confirmatory refusal that doesn't reveal membership elsewhere.
    # (The staff provisioning routes keep the plain message — staff read cross-tenant by design.)
    _existing = auth_lib.find_user(email)
    if _existing:
        if str(_existing.get("org_id") or "") == org["org_id"]:
            raise HTTPException(400, "That person is already on your team.")
        raise HTTPException(400, "We couldn't send an invite to that address. If it already "
                                 "has a lumi account, that person should sign in with it.")
    # PH-PAY-2 R3b CARVE-OUT: invite mail is AUTH mail — where invite CREATION
    # is permitted, the mail always sends regardless of suspension state.
    # (Creation into an org-suspended tenant is separately refused by the F12
    # design — that is a creation rule, not a mail gate, and it does not touch
    # the sole-admin-recovery path, which suspends a USER, not the org.)
    token = auth_lib.create_invite(org["org_id"], email, role, user["user_id"])
    link = "%s/app#/invite/%s" % (base_url(minting=True), token)
    inviter = user["display_name"] or user["email"]
    org_name = (identity.org_display(org["org_id"]) or {}).get("name")
    # off the event loop; self-recovering on failure — the link also returns in the
    # API response, and send_notification's failure path withholds the bearer
    await to_thread.run_sync(
        functools.partial(
            send_notification,
            "%s has invited you to lumi" % org_name,
            "Hello,\n\n%s has invited you to join %s on lumi — the UK reward benchmarking "
            "co-operative — as a %s.\n\nAccept your invite here:\n\n%s\n\nThe link expires in "
            "%d days. If you weren't expecting this, you can ignore this email.\n\n"
            "— lumi · UK reward benchmarking" % (inviter, org_name, ROLE_LABELS.get(role, role),
                                                 link, auth_lib.INVITE_TTL_DAYS),
            to=email))
    return {"ok": True, "link": link, "expires_days": auth_lib.INVITE_TTL_DAYS}


@app.put("/api/team/role")
async def change_role(request: Request):
    """Admin promotes/demotes a member. An org can never be left without an
    Admin: demoting the sole Admin is blocked with a clear message."""
    user, org = require_admin(request)
    body = await _json(request)
    email = (body.get("email") or "").strip().lower()
    role = body.get("role")
    if role not in ("admin", "contributor", "viewer"):
        raise HTTPException(400, "Role must be admin, contributor or viewer.")
    conn = get_conn()
    # P1: email resolves identity-side; org scoping stays REWARD-side, where
    # org_id is authoritative and survives step 5. Identity is used for the
    # email -> user_id resolution only, never for the org membership test.
    ident = identity.lookup_user_by_email(email)
    target = conn.execute("SELECT * FROM users WHERE user_id=? AND org_id=?",
                          (ident["user_id"], org["org_id"])).fetchone() if ident else None
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
    return {"ok": True, "email": ident["email"], "role": role}


@app.delete("/api/team/member")
async def remove_member(request: Request):
    user, org = require_admin(request)
    body = await _json(request)
    email = (body.get("email") or "").strip().lower()
    conn = get_conn()
    # P1: email resolves identity-side; org scoping stays REWARD-side, where
    # org_id is authoritative and survives step 5. Identity is used for the
    # email -> user_id resolution only, never for the org membership test.
    ident = identity.lookup_user_by_email(email)
    target = conn.execute("SELECT * FROM users WHERE user_id=? AND org_id=?",
                          (ident["user_id"], org["org_id"])).fetchone() if ident else None
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
        conn.execute("UPDATE metric_suggestions SET user_id=? WHERE user_id=?",
                     (user["user_id"], target["user_id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (target["user_id"],))
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (target["user_id"],))
        conn.execute("DELETE FROM notification_reads WHERE user_id=?", (target["user_id"],))
        conn.execute("DELETE FROM pinned_views WHERE org_id=? AND user_id=?",
                     (org["org_id"], target["user_id"]))
        conn.execute("DELETE FROM users WHERE user_id=?", (target["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    identity.shadow(identity.remove_user_identity, target["user_id"], user["user_id"])
    return {"ok": True, "removed": ident["email"]}


@app.delete("/api/team/invite/{token}")
async def revoke_invite(token: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    cur = conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=? AND org_id=?",
                       (token, org["org_id"]))
    conn.commit()
    if cur.rowcount != 1:
        # the identity shadow marks by TOKEN ALONE — firing it when the org-scoped
        # reward update matched nothing would let one org's admin burn another org's
        # invite by guessing/pasting its token (P3 sweep 2026-08-13)
        raise HTTPException(404, "That invite isn't one of yours, or it's already used.")
    identity.shadow(identity.mark_invite_used, token)
    return {"ok": True}


# ============================================================ LAYERED TERMS ==

# ======================================================== PULSES (Tier 2) ==
# A separate surface riding the SAME engine. Pulse data never pools with core
# data (structural separation — see pulses.py docstring). Fully independent
# of the core unlock gate in both directions.

def _pulse_member_view(conn, p, org, with_teaser=False):
    part = pulses_mod.participant(p["pulse_id"], org["org_id"], conn)
    n_q = len(uj(p["question_ids_json"], []))
    # PULSE-1: a real member's participant count reads the REAL subset — the
    # floor gate must agree with the report the same viewer will see.
    if org["source"] not in ("seed", "staff", "demo"):
        n_parts = conn.execute(
            "SELECT COUNT(*) FROM pulse_participants pp JOIN orgs o ON o.org_id=pp.org_id "
            "WHERE pp.pulse_id=? AND pp.submission_complete=1 "
            "AND o.source NOT IN ('seed','staff','demo')", (p["pulse_id"],)).fetchone()[0]
    else:
        n_parts = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=? AND submission_complete=1",
                               (p["pulse_id"],)).fetchone()[0]
    topic, icon = pulses_mod.topic_for(p["name"], p["description"])
    view = {
        "pulse_id": p["pulse_id"], "name": p["name"], "description": p["description"],
        "status": p["status"], "opens_at": p["opens_at"], "closes_at": p["closes_at"],
        "accepting": pulses_mod.is_accepting(p), "questions": n_q,
        "participants": n_parts, "floor": SUPPRESSION_FLOOR,
        "joined": part is not None, "participated": bool(part and part["submission_complete"]),
        "topic": topic, "icon": icon,
    }
    # a compact report teaser for the Explore card — only for a participant whose report
    # has actually unlocked, and only when the caller asks (the list view), so the detail
    # page (which builds the full report anyway) never double-pays for the aggregation.
    if with_teaser and view["participated"] and n_parts >= SUPPRESSION_FLOOR:
        try:
            rep = pulses_mod.pulse_report(
                p["pulse_id"], conn,
                real_viewer=org["source"] not in ("seed", "staff", "demo"))
            teaser = pulses_mod.pulse_teaser(rep)
            if teaser:
                view["teaser"] = teaser
        except Exception:
            pass
    return view


@app.get("/api/pulses")
async def list_pulses(request: Request):
    """The member Pulses surface: open (joinable), joined, and closed/archived
    pulses. Draft pulses are INVISIBLE to members."""
    user, org = require_user(request)
    conn = get_conn()
    out = []
    for p in conn.execute("SELECT * FROM pulses WHERE status != 'draft' ORDER BY created_at DESC"):
        out.append(_pulse_member_view(conn, p, org, with_teaser=True))
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
    # the report: give-to-get scoped to THIS pulse — participants only, PLUS the
    # sponsor that launched it (a paying self-service owner always sees its
    # results). Below the floor, the honest holding state is shown (never blank).
    view["is_owner"] = bool(p["owner_org_id"] and p["owner_org_id"] == org["org_id"])
    if view["participated"] or view["is_owner"]:
        rep = strip_internal(pulses_mod.pulse_report(pid, conn, real_viewer=org["source"] not in ("seed", "staff", "demo")))
        # thread the org's OWN answer into each report question so the report can
        # mark "you" against the cohort — a benchmark that never shows 'you' isn't one.
        # Values store as the display label (selects), "; "-joined labels (multi), or
        # a number (numeric/matrix); the client resolves the marker from `you`.
        for rq in rep.get("questions", []):
            qid = rq["question_id"]
            if rq.get("matrix_rows"):
                for mrow in rq["matrix_rows"]:
                    v = mine.get((qid, mrow["row_id"]))
                    if v not in (None, ""):
                        mrow["you"] = v
            else:
                v = mine.get((qid, ""))
                if v not in (None, ""):
                    rq["you"] = v
        # illustrative flag: a keyless/synthetic pool must never present seeded
        # numbers as real, in the report the same as in the commentary caveat
        rep["illustrative"] = bool(get_meta("synthetic_pool", False))
        view["report"] = rep
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
    body = await _json(request)
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
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_PULSE)
    body = await _json(request)
    qid = body.get("question_id")
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    part = pulses_mod.participant(pid, org["org_id"], conn)
    if not (part and part["submission_complete"]):
        raise HTTPException(403, "Participate in this pulse to see its commentary.")
    rep = pulses_mod.pulse_report(pid, conn, real_viewer=org["source"] not in ("seed", "staff", "demo"))
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
        "n": blk.get("n"), "n_real": blk.get("n_real", 0), "suppressed": bool(blk.get("suppressed")),
        "polarity": q.polarity, "you": mine and mine[0], "percentile": None,
        "stance": None,
        "illustrative_sample_data": bool(get_meta("synthetic_pool", False)),
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
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_metric_commentary, payload)
    return {"parts": res["parts"], "source": res["source"], "cached": False,
            "caveats": {"illustrative": payload["illustrative_sample_data"]}}


@app.post("/api/pulses/{pid}/narrative")
async def pulse_narrative(pid: str, request: Request):
    """AI-enhanced report-level narrative (summary + key findings). Keyless it
    returns the deterministic floor already in the report; live it upgrades to a
    grounded, validated model narrative. Same gates as commentary."""
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_PULSE)
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    part = pulses_mod.participant(pid, org["org_id"], conn)
    is_owner = bool(p["owner_org_id"] and p["owner_org_id"] == org["org_id"])
    if not ((part and part["submission_complete"]) or is_owner):
        raise HTTPException(403, "Participate in this pulse to see its report.")
    # SAME cohort flag as the report the member reads (pre-prod audit 2026-08-12: the
    # narrative was written over the default cohort while the visible report used the
    # real_viewer cohort — the AI could cite figures the page never showed)
    rep = strip_internal(pulses_mod.pulse_report(pid, conn, real_viewer=org["source"] not in ("seed", "staff", "demo")))
    if rep.get("below_floor"):
        raise HTTPException(400, "Report not available below the suppression floor.")
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_pulse_narrative, rep)
    return {"narrative": res["narrative"], "source": res["source"]}


# ============================================ CORE-SET GOVERNANCE / TRENDS ==

@app.get("/api/governance")
async def governance(request: Request):
    """Releases, change log and backlog — read surface for the admin page."""
    user = require_platform_admin(request)
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
    user = require_platform_admin(request)
    body = await _json(request)
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "A title is needed.")
    releases.add_backlog(title, (body.get("detail") or "").strip(),
                         body.get("source") or "manual", body.get("source_ref"))
    return {"ok": True}


@app.post("/api/governance/ingest-requests")
async def governance_ingest(request: Request):
    user = require_platform_admin(request)
    n = releases.ingest_metric_requests(get_conn())
    return {"ok": True, "ingested": n}


@app.post("/api/governance/emergency")
async def governance_emergency(request: Request):
    """The between-release lane. High bar by design: refused without BOTH the
    external trigger that made the question factually wrong AND a sign-off."""
    user = require_platform_admin(request)
    body = await _json(request)
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
              "release_id": s["release_id"], "n": blk.get("n"), "n_real": blk.get("n_real", 0)}
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
    exists. Both documents are the lawyer-approved final v1.0 versions."""
    return {
        "platform": {"version": PLATFORM_TERMS_VERSION, "text": legal_text("platform")},
        "data_contribution": {"version": DATA_TERMS_VERSION, "text": legal_text("data_contribution")},
        "dpa_available": True,
    }


@app.get("/api/terms/dpa")
async def terms_dpa():
    return Response(legal_text("dpa"), media_type="text/markdown",
                    headers={"Content-Disposition": 'attachment; filename="lumi-data-sharing-agreement.md"'})


@app.get("/api/legal")
async def legal_index():
    """Public: the index behind the "How lumi works -> Legal" section and the
    auth-screen footer. Lists every legal document; the text is fetched per
    document below."""
    return {"documents": LEGAL_INDEX}


@app.get("/api/legal/{key}")
async def legal_doc(key: str):
    """Public: one legal document's text (read-only). 404 for unknown keys."""
    meta = next((d for d in LEGAL_INDEX if d["key"] == key), None)
    if meta is None or key not in LEGAL_FILES:
        raise HTTPException(404, "Unknown legal document")
    return {"key": key, "title": meta["title"], "draft": meta["draft"], "text": legal_text(key)}


def _md_to_html(text):
    """Minimal, safe markdown→HTML for the legal docs (headings, bullets, bold) —
    mirrors the client TermsText renderer so public pages read the same."""
    import html as _html
    out = []
    for line in (text or "").split("\n"):
        esc = _html.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        if esc.startswith("# "):
            out.append("<h1>%s</h1>" % esc[2:])
        elif esc.startswith("## "):
            out.append("<h2>%s</h2>" % esc[3:])
        elif esc.startswith("- "):
            out.append("<p class='li'>• %s</p>" % esc[2:])
        elif esc.strip():
            out.append("<p>%s</p>" % esc)
    return "\n".join(out)


@app.get("/legal/{key}")
async def legal_page(key: str):
    """Public HTML render of a legal document — procurement and prospects must be
    able to read Terms/Privacy from the marketing footer WITHOUT an account."""
    meta = next((d for d in LEGAL_INDEX if d["key"] == key), None)
    if meta is None or key not in LEGAL_FILES:
        raise HTTPException(404, "Unknown legal document")
    draft_note = ("<p style='background:#FBEFD9;padding:12px 16px;border-radius:10px'>"
                  "This document is <b>DRAFT — pending legal review</b>.</p>") if meta["draft"] else ""
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>%s · lumi</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:Inter,system-ui,sans-serif;background:#FBF9F6;color:#211B26;margin:0}
.wrap{max-width:720px;margin:0 auto;padding:48px 24px}
.logo{font-weight:700;font-size:20px;color:#2048B0;text-decoration:none}.logo span{color:#F08C6E}
h1{font-size:26px;line-height:1.25}h2{font-size:18px;margin-top:28px}
p{color:#3d3745;line-height:1.6}p.li{margin:4px 0 4px 12px}
a{color:#2E62D9}footer{margin-top:48px;padding-top:16px;border-top:1px solid #EAE5DE;
color:#6E6874;font-size:13px}</style></head>
<body><div class="wrap"><a class="logo" href="/">lumi<span>.</span></a>
%s%s
<footer>© 2026 lumi · UK reward benchmarking · <a href="/">lumihr.co.uk</a> · questions: hello@lumihr.co.uk</footer>
</div></body></html>""" % (meta["title"], draft_note, _md_to_html(legal_text(key))))


@app.post("/api/terms/accept-data")
async def accept_data_terms(request: Request):
    """The Admin accepts the Data Contribution Terms on behalf of the
    organisation — once. This logged acceptance IS the organisational
    agreement, and it starts the 30-day contribution clock."""
    user, org = require_admin(request)
    body = await _json(request)
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
    # P1b: the org name comes from the identity store (D6). Display-shaped and
    # no-fallback, like every other read switch — a miss renders unnamed rather
    # than reaching back into the reward store, which would mask a broken split.
    _terms = org_data_terms(get_conn(), row["org_id"]) is not None
    return {"email": identity.invite_email(token), "role": row["role"],
            "org_name": (identity.org_display(row["org_id"]) or {}).get("name"),
            "data_terms_accepted": _terms}


@app.post("/api/auth/accept-invite")
async def accept_invite(request: Request):
    body = await _json(request)
    row = auth_lib.get_valid_invite(body.get("token") or "")
    if not row:
        raise HTTPException(400, "This invite link has expired or already been used.")
    if get_conn().execute("SELECT 1 FROM orgs WHERE org_id=? AND deactivated_at IS NOT NULL",
                          (row["org_id"],)).fetchone():
        raise HTTPException(400, "This organisation's lumi membership is deactivated — "
                                 "the invite can't be completed.")
    if body.get("accept_platform_terms") is not True:
        raise HTTPException(400, "Please accept the Platform Terms of Use to join.")
    conn = get_conn()
    # P5-live: the invited address lives identity-side. NOT display-shaped — resolve it
    # BEFORE any write and fail legibly, rather than letting a None reach create_user where
    # `email.lower()` raises AttributeError before the INSERT is ever attempted.
    _email = identity.invite_email(row["token"])
    if not _email:
        raise HTTPException(500, "This invite can't be completed — its record is incomplete. "
                                 "Please ask your Admin to send a new one.")
    _pwerr = auth_lib.validate_password(body.get("password") or "", email=_email)
    if _pwerr:
        raise HTTPException(400, _pwerr)
    uid = auth_lib.create_user(row["org_id"], _email, body["password"], row["role"],
                               body.get("display_name"))
    # Joiners accept the Platform Terms only — the org's Data Contribution
    # agreement was made once by the Admin and is inherited, never re-accepted.
    record_acceptance(conn, row["org_id"], uid, "platform", PLATFORM_TERMS_VERSION)
    # AI Insights consent is PER-USER (not inherited from the org) — each joiner decides for
    # themselves via the same unbundled, unticked acknowledgment (opt_in mode).
    if AI_CONSENT_MODE == "opt_in" and body.get("accept_ai_insights") is True:
        record_ai_consent(conn, row["org_id"], uid)
    conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=?", (row["token"],))
    conn.commit()
    identity.shadow(identity.mark_invite_used, row["token"])
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    _set_session_cookie(resp, token)
    return resp


@app.post("/api/ai-consent")
async def ai_consent(request: Request):
    """Member-level AI Insights consent toggle — the Settings switch AND the consent gate.
    Records a consent or a withdrawal event in the immutable terms_acceptances audit log;
    the gate re-reads the latest event next request, so withdrawal closes the gate at once.
    Per-user (each member decides for themselves), versioned (pins AI_TERMS_VERSION)."""
    user, org = require_user(request)
    body = await _json(request)
    conn = get_conn()
    if body.get("consent") is True:
        record_ai_consent(conn, org["org_id"], user["user_id"])
    else:
        record_ai_withdrawal(conn, org["org_id"], user["user_id"])
        purge_ai_cache(conn, org["org_id"])     # C3: erase derived AI summaries on opt-out
    return {"ok": True, "ai_insights": ai_gate(conn, user)}


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
            "n": (p.get("all") or {}).get("n", 0), "n_real": (p.get("all") or {}).get("n_real", 0),
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
    # firewall-reviewed per-card market position (Pass 2a): build the SAME Substance pool
    # the overview's gauge/donut counts (build_items + practice_position_items, identical
    # args to /api/overview) and classify it once, so each card's market_band agrees with
    # the §1 donut count it sums into. Strategy-invariant (the position chips don't move).
    _bi_items, _bi_tb = build_items(request, org, user, cut)
    _bi_prac = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                           payloads(), answers, entitled, _bi_tb)
    band_map = pos.pool_market_bands(_bi_items, _bi_prac, pos.market_position_config(),
                                     MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN)
    # second chip dimension (prevalence-filtering Pass A): the per-card prevalence band from the
    # SAME prevalence_items pool the §1 prevalence donut counts, so a card's band === the donut.
    _bi_prev = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org),
                                    payloads(), answers, entitled, _bi_tb)
    prev_band_map = pos.pool_prevalence_bands(_bi_prev, UNCOMMON_PCT)
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
                "n": (p.get("all") or {}).get("n", 0), "n_real": (p.get("all") or {}).get("n_real", 0), "reduced": True,
            })
            continue
        cards.append(assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None,
                                   entitled, market_band=band_map.get(qid),
                                   prevalence_band=prev_band_map.get(qid)))
    # strategy glyph on EVERY grid card (2026-08-13, David: "every metric should show the icon
    # below/on/above strategy"): attach the domain stance so the client's metricAim reads the
    # per-card alignment from the card's own market_band — same gate as assemble_card's block
    # (completed strategy + competitive domain), so the grid matches the detail card + overview.
    _sg_strat = strategy_for_engine(conn, org["org_id"])
    if _sg_strat and conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                                  (org["org_id"],)).fetchone():
        _sg_dt = _sg_strat.get("domain_targets") or {}
        _sg_global = _sg_strat.get("market_position")
        _sg_doms = (pos.market_position_config().get("_domains") or {})
        for c in cards:
            if c.get("reduced") or c.get("domain_aim"):
                continue
            sp = c.get("subpower")
            stance = _sg_dt.get(sp) or _sg_global
            if stance and _sg_doms.get(sp, {}).get("competitiveness", True):
                c["domain_aim"] = {"domain": sp, "stance": stance}
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
                "n": (p.get("all") or {}).get("n", 0), "n_real": (p.get("all") or {}).get("n_real", 0), "reduced": True}
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    # the SAME firewall-reviewed per-card market position the grid + donut use
    # (pool_market_bands) — the expanded page's verdict can never disagree with
    # the card the member clicked or the §1 donut it sums into (audit 2026-08-12:
    # this endpoint previously passed market_band=None, so the hero page lacked
    # the ruled verdict entirely).
    _bi_items, _bi_tb = build_items(request, org, user, cut)
    _bi_prac = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                           payloads(), org_answers_for(org), entitled, _bi_tb)
    _band_map = pos.pool_market_bands(_bi_items, _bi_prac, pos.market_position_config(),
                                      MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN)
    # …and the practice-prevalence band (common / alternative / rare — Diff-4 ruled
    # vocabulary), same pool as the §1 prevalence donut (labelling doctrine 2026-08-12:
    # every metric marked market OR practice on every surface)
    _prev_items = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org),
                                       payloads(), org_answers_for(org), entitled, _bi_tb)
    _prev_map = pos.pool_prevalence_bands(_prev_items, UNCOMMON_PCT)
    card = assemble_card(q, p, org, org_answers_for(org), cut,
                         {qid: tb.get(qid)} if tb else None, entitled,
                         market_band=_band_map.get(qid), prevalence_band=_prev_map.get(qid))
    # opportunity panel for £-model metrics
    mm = next((m for m in pos.MONEY_METRICS if m["question_id"] == qid), None)
    if mm and not card["locked"] and q.polarity != "neutral":
        money = pos.money_opportunities(conn, org, org_visible_questions(org), payloads(),
                                        org_answers_for(org), cut, {qid: tb.get(qid)} if tb else None)
        card["opportunity"] = next((i for i in money["items"] if i["question_id"] == qid), None)
        card["assumptions"] = money["assumptions"]
    # classification (analyst/detailed view): the engine's internal class/register —
    # surfaced here only, never on the default chip rows (spec §6.3)
    _mp = pos.market_position_config()
    _m = (_mp.get("metrics") or {}).get(qid)
    if _m:
        _cls = _m.get("class")
        _reg = "Substance" if _cls in ("Level", "Provision") else "Approach" if _cls in ("Practice", "Design") else None
        _comp = (_mp.get("_domains") or {}).get(q.sub_power, {}).get("competitiveness", True)
        card["classification"] = {
            "cls": _cls, "register": _reg, "direction": _m.get("direction"),
            "weight": _m.get("weight", 1), "competitive_domain": bool(_comp),
            "feeds_gauge": bool(_reg == "Substance" and _m.get("direction") == "higher_is_better" and _comp),
        }
    # STRATEGY READ-THROUGH (2026-07-06): carry the org's DECLARED aim for this
    # metric's domain so the detail page reads against it — the same "against your
    # aim" language the hero, signals and board pack speak (until now the funnel's
    # destination dropped the stance entirely). Fact only — the per-metric alignment
    # vs this aim is computed client-side from the card's own position, reusing the
    # SAME below/at/above vs lag/match/lead compare as pos._market_target, so the
    # vocabulary matches everywhere. Gated on a COMPLETED strategy AND a competitive
    # domain (no aim on a no-market-rate area like Governance).
    _strat = strategy_for_engine(conn, org["org_id"])
    if _strat and conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                               (org["org_id"],)).fetchone():
        _stance = (_strat.get("domain_targets") or {}).get(q.sub_power) or _strat.get("market_position")
        _comp_dom = (_mp.get("_domains") or {}).get(q.sub_power, {}).get("competitiveness", True)
        if _stance and _comp_dom:
            card["domain_aim"] = {"domain": q.sub_power, "stance": _stance}
    return card


@app.get("/api/benchmark-batch")
async def benchmark_batch(request: Request):
    """Several cards in one round-trip — the dashboards page was issuing one GET
    per pinned card (20 pins = 20 requests). Same assembly, same suppression,
    same reduced handling as the single route; no £ panel (dashboards never
    render it)."""
    user, org = require_user(request)
    ids = [x for x in (request.query_params.get("ids") or "").split(",") if x][:60]
    conn = get_conn()
    vis = org_visible_questions(org)
    entitled = make_entitled(user, org)
    contrib = contribution_state(conn, org)
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    answers = org_answers_for(org)
    # same ruled per-card market position as the grid + single routes (audit 2026-08-12) —
    # one pool build per request, so pinned dashboard cards agree with the donut too
    _bi_items, _bi_tb = build_items(request, org, user, cut)
    _bi_prac = pos.practice_position_items(org["org_id"], cut, vis, payloads(), answers, entitled, _bi_tb)
    _band_map = pos.pool_market_bands(_bi_items, _bi_prac, pos.market_position_config(),
                                      MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN)
    _prev_items = pos.prevalence_items(org["org_id"], cut, vis, payloads(), answers, entitled, _bi_tb)
    _prev_map = pos.pool_prevalence_bands(_prev_items, UNCOMMON_PCT)
    cards = {}
    for qid in ids:
        q = vis.get(qid)
        p = payloads().get(qid)
        if q is None or p is None:
            continue
        if contrib["reduced"] and qid not in reduced_sample_ids():
            cards[qid] = {"id": qid, "title": q.display_title, "question_text": q.text,
                          "superpower": q.superpower, "subpower": q.sub_power,
                          "sub_power_order": q.sub_power_order, "type": q.type,
                          "category": q.category,
                          "cut": {"dim": "all", "value": None, "label": "All peers"},
                          "n": (p.get("all") or {}).get("n", 0), "n_real": (p.get("all") or {}).get("n_real", 0), "reduced": True}
            continue
        cards[qid] = assemble_card(q, p, org, answers, cut,
                                   {qid: tb.get(qid)} if tb else None, entitled,
                                   market_band=_band_map.get(qid), prevalence_band=_prev_map.get(qid))
    return {"cards": cards}


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
        "twin_n": len(twin["peer_org_ids"]) if twin else None,
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
    prev_items = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org), payloads(),
                                      org_answers_for(org), make_entitled(user, org), tb)
    sec_order = []
    for q in org_visible_questions(org).values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in org_visible_questions(org).values() if q.sub_power == x))
    # direction-bearing practice evidence (unscored additions): Provision presence
    # feeds the gauge + headline; the rest is tile-rollup only
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                             payloads(), org_answers_for(org),
                                             make_entitled(user, org), tb)
    # headline counts the SAME Substance pool the gauge does (board pack / share /
    # dashboard never disagree about the same org)
    mp_cfg = pos.market_position_config()
    _strategy_full = strategy_for_engine(conn, org["org_id"])   # the org's declared strategy (None if unset)
    # ONE definition of "has a strategy" platform-wide: a strategy applies only once
    # COMPLETED (same gate as metric cards / pack / strategy check) — a half-saved
    # capture must not lens one page while every other surface says "no strategy yet".
    if _strategy_full and not conn.execute(
            "SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
            (org["org_id"],)).fetchone():
        _strategy_full = None
    # "Apply my strategy" toggle (?strategy=off): read the dashboard WITHOUT the stance
    # lens — absolute RAG colours, impact-ordered signals, plain verdict (no aim/target).
    # Reuses the engine's strategy=None degrade path (§5.5); the org's strategy still
    # EXISTS (strategy_complete stays true) — it's simply not applied this request.
    apply_strategy = request.query_params.get("strategy") != "off"
    _strategy = _strategy_full if apply_strategy else None   # None → legacy hero + legacy signal order
    # Diff 16 (N/A-disclosure): gauge-eligible metrics legitimately not applicable to this org
    # stay in the positioned pool as a DISCLOSED absence, never a silent drop. Derived structurally
    # (positions.disclosed_absent) and passed as a separate list — it enters no verdict denominator.
    _positioned_qids = set(pos.pool_market_bands(items, prac_items, mp_cfg,
                                                 MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN).keys())
    _absent = pos.disclosed_absent(org["org_id"], cut, org_visible_questions(org), payloads(),
                                   org_answers_for(org), make_entitled(user, org), mp_cfg,
                                   _positioned_qids, tb)
    summary = pos.overview_summary(items, mp_config=mp_cfg, practice_items=prac_items,
                                   band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH,
                                   absent_items=_absent)
    summary["absent_disclosed_metrics"] = _absent
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=mp_cfg, strategy=_strategy)
    # Practice Alignment: attach the member-facing title/states/verdict ALONGSIDE the frozen
    # engine keys on each domain's prevalence object, so the frontend reads them instead of
    # hardcoding. UNCONDITIONAL + None-safe (Pass 2 / Option A): every domain carries title +
    # states even with no practice questions (verdict null then), so the frontend never needs a
    # hardcoded fallback. with_display spreads the original dict — engine keys untouched. This is
    # the browser object only; the model payload (build_domain_summary_payload) is built separately
    # and never gains these display fields.
    for _d in hero.get("domains", []):
        _d["prevalence"] = practice_axis.with_display(_d.get("prevalence"))
    reg_rows = build_gap_register(request, user, org, cut).get("rows", [])
    hero["action_gaps"] = sum(1 for r in reg_rows
                              if r.get("org_answered") and r.get("in_place") is False and (r.get("gap") or 0) > 0)
    co = pos.callouts(items, org_visible_questions(org), k=3)
    money = pos.money_opportunities(conn, org, org_visible_questions(org), payloads(),
                                    org_answers_for(org), cut, tb)
    # signals (2026-06-12): outcome-lens flags from the SAME computed data —
    # lens mapping + thresholds are David's (data/signal_lenses.json)
    _visq = org_visible_questions(org)
    _answers = org_answers_for(org)
    _get_block = lambda qid: pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0] if payloads().get(qid) else None
    # Signals snooze auto-return: a snoozed row whose window has passed is cleared
    # here (lazily, on read), so the signal drops back to the inbox as if never
    # snoozed. datetime('now') is UTC, same clock the snooze_until was written on.
    conn.execute(
        "DELETE FROM signal_actions WHERE org_id=? AND user_id=? AND status='snoozed' "
        "AND snooze_until IS NOT NULL AND snooze_until <= datetime('now')",
        (org["org_id"], user["user_id"]))
    conn.commit()
    _statuses, _snooze_until = {}, {}
    for r in conn.execute(
            "SELECT question_id, status, snooze_until FROM signal_actions WHERE org_id=? AND user_id=?",
            (org["org_id"], user["user_id"])):
        _statuses[r["question_id"]] = r["status"]
        if r["status"] == "snoozed":
            _snooze_until[r["question_id"]] = r["snooze_until"]
    # step-3 layer 4: per-domain alignment map from the layer-3 hero output (the SINGLE
    # source of truth — alignment is NOT recomputed in signals.py, which has no domain
    # aggregate verdict). {domain: alignment} over competitive domains that carry a target;
    # strategy-off → every target None → empty map → nothing confirms → the signal set
    # degrades byte-identical. Drives confirm-suppression inside build_signals.
    _dom_align = {d["name"]: (d.get("target") or {}).get("alignment")
                  for d in hero["domains"] if d.get("target")}
    # SIGNALS ANCHORED TO THE ORG DEFAULT PEER GROUP (David 2026-08-11): on-screen signals must
    # match the nightly alert sweep (org_signals → _org_sweep_cut) and never drift as the user
    # browses other cuts — otherwise the page and the emails flag different things. Position /
    # hero / bars keep the REQUESTED cut; only the signal build re-points to the default. When the
    # requested cut IS the default (the common case, and every gate's frame), this is a no-op alias
    # — byte-identical to before. The default is a firmographic cut (industry/fte_band) or all.
    sig_cut = _org_sweep_cut(conn, org)
    if sig_cut.get("dim") == cut.get("dim") and sig_cut.get("value") == cut.get("value"):
        sig_items, sig_money, sig_get_block, sig_align = items, money, _get_block, _dom_align
    else:
        sig_items, sig_tb = build_items(request, org, user, sig_cut)
        sig_money = pos.money_opportunities(conn, org, _visq, payloads(), _answers, sig_cut, sig_tb)
        sig_get_block = lambda qid: pos.block_for(payloads().get(qid) or {}, sig_cut, (sig_tb or {}).get(qid))[0] if payloads().get(qid) else None
        sig_align = {}
        if _strategy:   # confirm-suppression alignment only bites with a strategy applied
            _sig_ent = make_entitled(user, org)
            _sig_prev = pos.prevalence_items(org["org_id"], sig_cut, _visq, payloads(), _answers, _sig_ent, sig_tb)
            _sig_prac = pos.practice_position_items(org["org_id"], sig_cut, _visq, payloads(), _answers, _sig_ent, sig_tb)
            _sig_hero = pos.hero_signals(sig_items, _sig_prev, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                                         DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                                         practice_items=_sig_prac, tile_min=TILE_MIN_POSITIONED,
                                         mp_config=mp_cfg, strategy=_strategy)
            sig_align = {d["name"]: (d.get("target") or {}).get("alignment")
                         for d in _sig_hero["domains"] if d.get("target")}
    _sigs_brief = signals_mod.build_signals(sig_items, sig_money, _visq, sig_get_block, _answers,
                                            conn=conn, org_id=org["org_id"], statuses=_statuses,
                                            strategy=_strategy, domain_alignment=sig_align)
    # per-view briefings (signals.py caps each position pool separately):
    # `signals` KEEPS its meaning — the market-view balanced briefing (qa_hero
    # asserts its caps) — while the practice-view briefing rides alongside.
    sigs = [s for s in _sigs_brief if s.get("position") in ("below", "on", "above")]
    sigs_practice = [s for s in _sigs_brief if s.get("position") not in ("below", "on", "above")]
    # full uncapped set for the dedicated Signals explore page (home stays capped)
    sigs_all = signals_mod.build_signals(sig_items, sig_money, _visq, sig_get_block, _answers,
                                         conn=conn, org_id=org["org_id"], cap=False, statuses=_statuses,
                                         strategy=_strategy, domain_alignment=sig_align)
    # new-since-last-seen: a signal is NEW until the user has viewed it on the
    # Signals page. Annotate both sets + count the un-dismissed new ones.
    _seen = {r["sig_id"] for r in conn.execute(
        "SELECT sig_id FROM signal_seen WHERE org_id=? AND user_id=?",
        (org["org_id"], user["user_id"]))}
    for s in sigs_all:
        s["new"] = (s.get("sig_id") or s["question_id"]) not in _seen
        s["snooze_until"] = _snooze_until.get(s.get("sig_id") or s["question_id"])
    _new_ids = {(s.get("sig_id") or s["question_id"]) for s in sigs_all}  # current sig_ids
    for s in sigs + sigs_practice:
        s["new"] = (s.get("sig_id") or s["question_id"]) not in _seen
        s["snooze_until"] = _snooze_until.get(s.get("sig_id") or s["question_id"])
    signals_new = sum(1 for s in sigs_all if s["new"] and s.get("status") not in ("dismissed", "snoozed"))
    dots = signals_mod.domain_dots(items)
    prac_dots = signals_mod.domain_dots(prac_items)
    sig_by_cat = {}
    for sg in sigs:
        q = org_visible_questions(org).get(sg["question_id"])
        if q:
            sig_by_cat.setdefault(q.sub_power, []).append(sg["lens"])
    for d in hero["domains"]:
        # polarised dot when the domain has one; practice evidence fills in
        # only where the score/value pool says nothing (Wellbeing today)
        d["dot"] = dots.get(d["name"]) if dots.get(d["name"]) is not None else prac_dots.get(d["name"])
        d["signal_lenses"] = sig_by_cat.get(d["name"], [])
    pool = get_meta("peer_pool", {})
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    return {
        "org": {"name": (identity.org_display(org["org_id"]) or {}).get("name"), "industry": org["industry"], "fte_band": org["fte_band"],
                "hq_region": org["hq_region"], "classified": bool(org["classified"])},
        "cut": cut,
        "peer_pool": pool,
        "snapshot": {"date": snap["snapshot_date"], "window": snap["collection_window"]},
        "headline": summary,
        "contribution": contrib,
        "hero": hero,
        # the single-bucket practice read (Diff 4, 2026-07-14) — aggregated from the SAME
        # prev_items the lens renders (one implementation); strategy-config rows are
        # excluded at the engine boundary (positions.STRATEGY_CONFIG_IDS)
        "practice_bucket": pos.practice_bucket(org_visible_questions(org),
                                               pos.market_position_config(), prev_items,
                                               org_answers_for(org), UNCOMMON_PCT),
        "signals": sigs,
        "signals_practice": sigs_practice,
        "signals_all": sigs_all,
        "signals_new": signals_new,
        # the peer group the signals above were computed against — the org default (2026-08-11),
        # so the page + emails agree; the client shows it and anchors the Signals page to it.
        "signal_cut": sig_cut,
        # reward strategy completion — drives the dashboard nudge for Admins who
        # haven't set their stance yet (the engines read None = legacy until then)
        "strategy_complete": bool(conn.execute(
            "SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
            (org["org_id"],)).fetchone()),
        # whether the stance lens is APPLIED on this request (the "Apply my strategy"
        # toggle) — distinct from strategy_complete (does one EXIST). False = absolute view.
        "strategy_applied": bool(_strategy),
        "strategy_can_edit": user["role"] in ("admin", "contributor"),
        # the objective the Signals order is read through (None when unset/skipped) —
        # drives the modest "ordered for your strategy" indicator on the Signals page
        "strategy_objective": OBJECTIVE_LABELS.get(
            _strategy.get("primary_objective")) if (_strategy and
            (_strategy.get("provenance") or {}).get("primary_objective") != "skipped") else None,
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


@app.post("/api/strategy-diagnosis")
async def strategy_diagnosis(request: Request):
    """Strategy-execution check: where the org's declared reward strategy and its
    actual market position diverge. Findings computed deterministically (firewall),
    narrated by the model with the same trust gate as commentary."""
    user, org = require_user(request)
    conn = get_conn()
    require_ai(conn, user, AI_STRATEGY)
    strat = strategy_for_engine(conn, org["org_id"])
    complete = conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                            (org["org_id"],)).fetchone()
    if not strat or not complete:
        return {"ok": False, "reason": "no_strategy"}
    contrib = contribution_state(conn, org)
    if not contrib["insights_unlocked"]:
        return {"ok": False, "reason": "locked", "days_left": contrib["days_left"]}
    # build the same hero domains + £ opportunities the overview does, on All peers
    cut = parse_cut(request, org)
    items, tb = build_items(request, org, user, cut)
    prev_items = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org), payloads(),
                                      org_answers_for(org), make_entitled(user, org), tb)
    sec_order = []
    for q in org_visible_questions(org).values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                             payloads(), org_answers_for(org), make_entitled(user, org), tb)
    mp_cfg = pos.market_position_config()
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=mp_cfg, strategy=strat)
    money = pos.money_opportunities(conn, org, org_visible_questions(org), payloads(),
                                    org_answers_for(org), cut, tb)
    # per-domain verdict + £ opportunity rolled up by domain (q.sub_power)
    domains = []
    for d in hero["domains"]:
        p = d.get("position") or d.get("market") or {}
        domains.append({"name": d["name"], "verdict": p.get("verdict"),
                        "below": p.get("below"), "at": p.get("at"), "above": p.get("above"),
                        "pool": p.get("pool"), "competitive": d.get("competitiveness", True)})
    vq = org_visible_questions(org)
    opp_by_domain = {}
    for it in money["items"]:
        q = vq.get(it["question_id"])
        dom = q.sub_power if q else None
        gbp = it.get("to_p50_gbp") or 0
        if not dom or not gbp:
            continue
        e = opp_by_domain.setdefault(dom, {"gbp": 0, "direction": it["direction"], "top_label": it["label"], "top_gbp": 0})
        e["gbp"] += gbp
        if gbp >= (e["top_gbp"] or 0):
            e["top_gbp"], e["top_label"], e["direction"] = gbp, it["label"], it["direction"]
    findings = strategy_diag.compute_findings(strat, domains, opp_by_domain)
    flagged = {f["area"] for f in findings}
    # derived, never literal (Diff 1 doctrine): competitive = the payload's own flag —
    # the old strategy_diag._COMPETITIVE six-name filter dropped every renamed domain
    on_plan = [d["name"] for d in domains if d.get("competitive", True)
               and d["verdict"] and d["name"] not in flagged]
    obj_label = OBJECTIVE_LABELS.get(strat.get("primary_objective")) if (
        (strat.get("provenance") or {}).get("primary_objective") != "skipped") else None
    payload = strategy_diag.build_diagnosis_payload(
        strat, findings, (hero.get("market") or {}).get("target"), obj_label, on_plan,
        bool(get_meta("synthetic_pool", False)))
    # Cached on the payload hash, same store and contract as the strategy commentary
    # (2026-08-16). This used to regenerate on EVERY call, which was affordable when
    # only the Overview's collapsible opened it — the Reward Plan report reads it on
    # every open, and a document people re-read must not bill a model call each time.
    # `force` re-generates; the hash means a changed position invalidates by itself.
    _dhash = hashlib.sha256(
        (j(payload) + "|" + claude_api.DIAGNOSIS_VERSION).encode()).hexdigest()[:16]
    _body = await _json(request)
    if not _body.get("force"):
        _row = conn.execute(
            "SELECT * FROM metric_commentary WHERE org_id=? AND question_id=? AND cut_key=? AND payload_hash=?",
            (org["org_id"], "__diagnosis__", "strategy", _dhash)).fetchone()
        if _row:
            _p = uj(_row["text"], {})
            return {"ok": True, "parts": _p, "source": _row["source"], "cached": True,
                    "generated_at": _row["created_at"], "on_plan": on_plan,
                    "caveats": {"illustrative": payload["illustrative_sample_data"]}}
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_strategy_diagnosis, payload)
    # Signpost: attach each finding's domain so the Signals page can deep-link the
    # narrative to the matching signal group. The validator guarantees the narrated
    # findings match the computed `findings` 1:1 and in order, so a positional zip is
    # safe; the on-plan affirmation has no computed findings, so it carries no domain.
    parts = res["parts"]
    nf = parts.get("findings") or []
    if len(nf) == len(findings):
        for narrated, computed in zip(nf, findings):
            narrated["area"] = computed.get("area")
    # store the NARRATED parts (areas already attached) so a cache hit is byte-identical
    # to a fresh generation — a reader must never see the document change on reload
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], "__diagnosis__", "strategy", _dhash, j(parts), res["source"]))
    conn.commit()
    return {"ok": True, "parts": parts, "source": res["source"], "cached": False,
            # on_plan = competitive domains tracking with intent (engine-derived, not
            # model output) — the frontend renders them as a quiet "on plan" line that
            # can still signpost to each domain's signals.
            "on_plan": on_plan,
            "caveats": {"illustrative": payload["illustrative_sample_data"]}}


# ============================================================ NOTIFICATIONS ==

# cuts a nightly, request-free sweep can safely build: the firmographic peer sets (their
# blocks are pre-aggregated), never twin (needs the org's similarity vector) or group
# (needs membership). Anything else → all-peers.
SWEEP_CUT_DIMS = ("industry", "fte_band")

def _org_sweep_cut(conn, org):
    """The org's default_cut as a cut dict for signals/alerts. A single firmographic value
    (industry::X / fte_band::Y) resolves inline; a COMPANY-DEFAULT GROUP (group::gid) loads its
    criteria — a multi sector × size intersection computed via peer_twin.group_blocks, which is
    request-free (conn + criteria only), so the nightly sweep can build it too. A deleted group or
    NULL / unsupported value → all-peers."""
    raw = (org.get("default_cut") or "").strip()
    if raw.startswith("group::"):
        gid = raw.split("::", 1)[1]
        row = conn.execute("SELECT criteria_json FROM peer_groups WHERE group_id=? AND org_id=?",
                           (gid, org["org_id"])).fetchone()
        if row:
            return {"dim": "group", "value": gid, "criteria": uj(row["criteria_json"], {}) or {}}
        return {"dim": "all", "value": None}
    if "::" in raw:
        dim, val = raw.split("::", 1)
        if dim in SWEEP_CUT_DIMS and val:
            return {"dim": dim, "value": val}
    return {"dim": "all", "value": None}


def _default_cut_info(conn, org):
    """(raw_cut, label, criteria) describing the org default, for the client — the criteria
    pre-fills the Settings multi-select (checked sectors/sizes) and the label names the group on
    the Signals page. NULL / missing → all peers."""
    raw = (org.get("default_cut") or "").strip()
    if raw.startswith("group::"):
        gid = raw.split("::", 1)[1]
        row = conn.execute("SELECT name, criteria_json FROM peer_groups WHERE group_id=? AND org_id=?",
                           (gid, org["org_id"])).fetchone()
        if row:
            return raw, row["name"], (uj(row["criteria_json"], {}) or {})
        return None, "All peers", {}
    if "::" in raw:
        dim, val = raw.split("::", 1)
        if dim == "industry":
            return raw, val, {"industry": [val]}
        if dim == "fte_band":
            return raw, val + " FTE", {"fte_band": [val]}
    return None, "All peers", {}


def _default_group_name(criteria):
    """Readable name for the auto company-default group, from its firmographic criteria."""
    parts = []
    inds, ftes = criteria.get("industry") or [], criteria.get("fte_band") or []
    if inds:
        parts.append(", ".join(inds) if len(inds) <= 2 else ("%d sectors" % len(inds)))
    if ftes:
        parts.append((", ".join(ftes) if len(ftes) <= 2 else ("%d sizes" % len(ftes))) + " FTE")
    return " · ".join(parts) or "Company default"


@app.put("/api/org/signal-peers")
async def set_org_signal_peers(request: Request):
    """Editor-only: set the ORG DEFAULT peer group (drives signals, alerts AND everyone's landing
    view — David 2026-08-11). Accepts a firmographic CRITERIA with MULTIPLE sectors and/or size
    bands: nothing selected → all peers; a single firmographic value → the trusted pre-aggregated
    single cut; a genuine combination → a company-default peer GROUP (criteria resolved dynamically
    via group_blocks, request-free so the nightly sweep can build it). A group default can ONLY come
    from this flow (the old control + sweep never allowed groups), so `cur_gid` is always the auto
    group — safe to reuse/replace. Legacy {cut:"industry::X"} body still accepted."""
    user, org = require_editor(request)
    body = await _json(request)
    conn = get_conn()
    cur = (org.get("default_cut") or "")
    cur_gid = cur.split("::", 1)[1] if cur.startswith("group::") else None
    def _drop_auto_group():
        if cur_gid:
            # R2 guard (2026-08-14): if the reward strategy declared this auto group as its
            # comparator, the group is no longer disposable — leave it in place (it simply
            # stops being the org default) rather than dangling the strategy.
            if conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND comparator_cut=?",
                            (org["org_id"], "group::" + cur_gid)).fetchone():
                return
            conn.execute("DELETE FROM peer_groups WHERE group_id=? AND org_id=?", (cur_gid, org["org_id"]))
    # legacy single-cut body (back-compat)
    if "criteria" not in body and body.get("cut") is not None:
        raw = (body.get("cut") or "all").strip()
        if raw != "all" and raw.split("::", 1)[0] not in SWEEP_CUT_DIMS:
            return JSONResponse({"error": "Only industry or size peer groups are allowed."}, status_code=400)
        _drop_auto_group()
        conn.execute("UPDATE orgs SET default_cut=? WHERE org_id=?", (None if raw == "all" else raw, org["org_id"]))
        conn.commit()
        return {"ok": True, "signal_peer_cut": None if raw == "all" else raw}
    # criteria body: multiple sectors / size bands
    ci = body.get("criteria") or {}
    crit = {}
    for f in ("industry", "fte_band"):
        vals = [v for v in (ci.get(f) or []) if isinstance(v, str) and v]
        if vals:
            crit[f] = vals
    if not crit:                                       # nothing selected → all peers
        _drop_auto_group()
        conn.execute("UPDATE orgs SET default_cut=NULL WHERE org_id=?", (org["org_id"],))
        conn.commit()
        return {"ok": True, "signal_peer_cut": None}
    criteria = validate_group_criteria(crit)           # validates against profile_choices
    # a single firmographic value → use the trusted pre-aggregated single cut (exact + fast)
    if len(criteria) == 1 and len(next(iter(criteria.values()))) == 1:
        field = next(iter(criteria)); value = criteria[field][0]
        _drop_auto_group()
        conn.execute("UPDATE orgs SET default_cut=? WHERE org_id=?", (field + "::" + value, org["org_id"]))
        conn.commit()
        return {"ok": True, "signal_peer_cut": field + "::" + value}
    # a genuine combination → the company-default GROUP (find-or-create, then point the default at it)
    name = _default_group_name(criteria)
    if cur_gid and conn.execute("SELECT 1 FROM peer_groups WHERE group_id=? AND org_id=?",
                                (cur_gid, org["org_id"])).fetchone():
        conn.execute("UPDATE peer_groups SET name=?, criteria_json=?, updated_at=datetime('now') WHERE group_id=?",
                     (name, j(criteria), cur_gid))
        gid = cur_gid
    else:
        gid = str(uuid.uuid4())
        conn.execute("INSERT INTO peer_groups(group_id, org_id, name, criteria_json, created_by) VALUES (?,?,?,?,?)",
                     (gid, org["org_id"], name, j(criteria), user["user_id"]))
    conn.execute("UPDATE orgs SET default_cut=? WHERE org_id=?", ("group::" + gid, org["org_id"]))
    conn.commit()
    return {"ok": True, "signal_peer_cut": "group::" + gid,
            "match_count": len(peer_twin.group_org_ids(conn, criteria))}


def org_signals(conn, org):
    """The org's full (uncapped) signal set on the default all-peers cut, built
    request-free for the nightly sweep — the same machinery /api/overview uses,
    minus the per-user triage status (identity/value don't depend on it).
    STRATEGY-AWARE (step-3 notification coherence, ruling C): threads the org's strategy +
    per-domain alignment exactly as /api/overview does, so confirm-suppression fires HERE too —
    confirming non-risk signals carry s["confirm"] (the event layer quiets them; risk_framed stays
    exempt by the same not-risk_framed gate). The peer cut stays the canonical all-peers frame
    (RULED). strategy None / no override → empty alignment map → no confirm flags → byte-identical
    to the pre-coherence (strategy-blind) sweep (degrade).

    PEER GROUP (2026-07-10, David: "for this default power notifications"): the org's
    default_cut drives the sweep now — the emails flag against the peers the org actually
    cares about, not always all-peers (the old RULED frame). Restricted to the stable
    firmographic cuts (industry/fte_band) so a nightly, request-free build never depends on
    twin vectors / group membership; NULL or anything else → all-peers (byte-identical)."""
    cut = _org_sweep_cut(conn, org)
    items, tb = build_items(None, org, None, cut)
    visq = org_visible_questions(org)
    answers = org_answers_for(org)
    money = pos.money_opportunities(conn, org, visq, payloads(), answers, cut, tb)
    get_block = lambda qid: pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0] if payloads().get(qid) else None
    # parity with /api/overview: build the hero (request-free; all entitled — the sweep only runs
    # for UNLOCKED orgs) to derive the {domain: alignment} map, then thread strategy + the map into
    # build_signals. Single source of truth — the same per-domain target L3/L4/recolour read.
    strat = strategy_for_engine(conn, org["org_id"])
    ent = lambda q: True
    prev_items = pos.prevalence_items(org["org_id"], cut, visq, payloads(), answers, ent, tb)
    prac_items = pos.practice_position_items(org["org_id"], cut, visq, payloads(), answers, ent, tb)
    sec_order = []
    for q in visq.values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in visq.values() if q.sub_power == x))
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=pos.market_position_config(), strategy=strat)
    dom_align = {d["name"]: (d.get("target") or {}).get("alignment")
                 for d in hero["domains"] if d.get("target")}
    return signals_mod.build_signals(items, money, visq, get_block, answers,
                                     conn=conn, org_id=org["org_id"], cap=False, statuses=None,
                                     strategy=strat, domain_alignment=dom_align)


def run_signal_sweep(conn=None, verbose=True):
    """Nightly: after run_snapshot recomputes the benchmark, diff each unlocked
    org's signal set against signal_state, record change events and fan them
    out per-user. Locked orgs get nothing (no insights → no signals → no
    events), checked here. Returns (orgs_swept, events_written)."""
    conn = conn or get_conn()
    swept, total_events = 0, 0
    # PH-PAY-2 R3a: suspended orgs are OUT of the sweep — no signal events accrue
    # for members who cannot see them, and no downstream mail path receives them.
    for row in conn.execute(
            "SELECT org_id, industry, fte_band, insights_unlocked_at, "
            "submission_complete, default_cut FROM orgs WHERE deactivated_at IS NULL"):
        org = dict(row)
        try:
            if not org_unlocked(conn, org):
                continue
            fresh = org_signals(conn, org)
            oid = org["org_id"]
            seen_before = conn.execute(
                "SELECT (EXISTS(SELECT 1 FROM signal_state WHERE org_id=?) "
                "     OR EXISTS(SELECT 1 FROM notification_events WHERE org_id=?)) e",
                (oid, oid)).fetchone()["e"]
            # P1-F (R-P6 seam): if the pool-composition epoch moved since this
            # org's baseline, REBASELINE silently instead of diffing — taper-
            # driven movement is excluded from signal detection by rule. A
            # MISSING epoch row is treated as the CURRENT epoch (stamped lazily
            # below): treating it as "different" would silently rebaseline every
            # pre-P1F org on the first sweep and eat genuinely pending changes.
            cur_epoch = str(get_meta("composition_epoch", "0"))
            ep_row = conn.execute("SELECT epoch FROM org_signal_epoch WHERE org_id=?",
                                  (oid,)).fetchone()
            if not seen_before:
                notifications.record_baseline(conn, oid, fresh)   # silent: establish baseline
                conn.execute("INSERT OR REPLACE INTO org_signal_epoch VALUES (?,?)",
                             (oid, cur_epoch))
                conn.commit()
                swept += 1
                continue
            if ep_row is not None and ep_row["epoch"] != cur_epoch:
                # FULL replace (rebaseline = DELETE first), not INSERT OR
                # REPLACE: an epoch change must also clear rows whose signal
                # keys are absent from the fresh set — otherwise stale rows
                # (old vocabulary, dead signals) survive the rebaseline
                # (SIG-1 stored-row finding, 2026-08-08).
                notifications.rebaseline(conn, oid, fresh)        # composition moved: no events
                conn.execute("INSERT OR REPLACE INTO org_signal_epoch VALUES (?,?)",
                             (oid, cur_epoch))
                conn.commit()
                swept += 1
                continue
            events = notifications.diff_and_record(conn, oid, fresh)
            conn.execute("INSERT OR REPLACE INTO org_signal_epoch VALUES (?,?)",
                         (oid, cur_epoch))
            conn.commit()
            if events:
                notifications.fan_out(conn, oid, events)
            swept += 1
            total_events += len(events)
        except Exception as e:
            print("[lumi] signal sweep failed for org %s: %s" % (org.get("org_id"), e))
    if verbose:
        print("Signal sweep: %d unlocked orgs, %d change events recorded" % (swept, total_events))
    return swept, total_events


def _signal_scheduler():
    """Daemon loop: once a day at LUMI_SWEEP_HOUR (UTC, default 07) run the signal
    sweep, then the email digest — so members are proactively emailed when their
    position moves. Weekly-digest users are included one weekday a week
    (LUMI_WEEKLY_DAY, Mon=0). Uses a thread-local connection (db.get_conn is
    thread-local, so this thread gets its own). ENV-GATED off by default — dev,
    tests and the QA suite never start it. Assumes a SINGLE app instance; with
    multiple workers, leave this OFF and drive POST /api/notifications/run-sweep
    ?digest=daily,weekly from one external cron instead (each worker would
    otherwise sweep in parallel). Emails only actually leave once LUMI_SMTP_HOST
    is set; otherwise send_notification console-logs them."""
    import time as _time
    while True:
        try:
            hour = int(os.environ.get("LUMI_SWEEP_HOUR", "7")) % 24
            weekly_day = int(os.environ.get("LUMI_WEEKLY_DAY", "0"))
            now = datetime.utcnow()
            nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            _time.sleep(max(30.0, (nxt - now).total_seconds()))
            conn = get_conn()
            swept, events = run_signal_sweep(conn, verbose=False)
            freqs = ["daily"] + (["weekly"] if datetime.utcnow().weekday() == weekly_day else [])
            sent = notifications.run_email_digest(
                conn, base_url=base_url() or "", frequencies=tuple(freqs))
            print("[lumi] signal scheduler: swept %d orgs, %d change events, %d digests sent (%s)"
                  % (swept, events, sent, ",".join(freqs)), flush=True)
        except Exception as e:
            print("[lumi] signal scheduler error (retrying in 1h): %s" % e, flush=True)
            _time.sleep(3600)


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


@app.get("/api/account/personal-data")
async def account_personal_data(request: Request):
    """Subject-access export (UK GDPR Art. 15): the personal data lumi holds about
    the REQUESTING USER — their account identity, role, consent/withdrawal history and
    active-session metadata. This is distinct from /api/my-data, which is the
    ORGANISATION's contributed reward answers (org-level, not personal). No tokens or
    other members' data are ever included; a user can only export their own record."""
    user, org = require_user(request)
    conn = get_conn()
    disp = identity.user_display(user["user_id"]) or {}
    acct = conn.execute("SELECT role, created_at FROM users WHERE user_id=?",
                        (user["user_id"],)).fetchone()
    consents = [dict(r) for r in conn.execute(
        "SELECT kind, version, accepted_at FROM terms_acceptances WHERE user_id=? "
        "ORDER BY accepted_at", (user["user_id"],))]
    org_name = (identity.org_display(org["org_id"]) or {}).get("name")
    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " UTC",
        "account": {
            "user_id": user["user_id"],
            "email": disp.get("email"),
            "display_name": disp.get("display_name"),
            "role": acct["role"] if acct else user.get("role"),
            "created_at": acct["created_at"] if acct else None,
            "organisation": org_name,
            "organisation_id": org["org_id"],
        },
        # the immutable consent/terms audit trail for this user (platform terms,
        # AI-insights consent + any withdrawal, etc.)
        "consents": consents,
        # active sessions — metadata only; session tokens are NEVER exported
        "active_sessions": identity.sessions_for_user(user["user_id"]),
        "notes": "Your organisation's contributed reward data is available separately via "
                 "the 'Your data' export (/api/my-data). This export is the personal data "
                 "lumi holds about you as an individual.",
    }


@app.get("/api/data-overview")
async def data_overview(request: Request):
    """Completion-first view of the org's own data: overall + per-domain
    progress and, per domain, every question with its answered status and the
    submitted value. Drives the Your-data landing + per-domain drill-down."""
    user, org = require_user(request)
    conn = get_conn()
    # DRAFT-INCLUSIVE (empty-state review 2026-08-09): autosaved drafts count
    # toward the unlock gate (completion_counts unions answers|drafts), so the
    # Your-data view must show them too — otherwise a company that has drafted 40
    # answers but not yet hit Submit sees "0 answered" here while the Overview
    # says "N from unlocking", and the "autosaved as you go" promise reads false.
    # Committed answers first, then drafts win per cell (the latest edit); an
    # explicit blank draft clears the cell. Refresh-due stays answers-only below
    # (a draft is not aged submitted data).
    answers = org_answers_for(org)                       # {(qid,row): value} — committed
    merged = dict(answers)
    for r in conn.execute("SELECT question_id, matrix_row_id, value FROM drafts WHERE org_id=?",
                          (org["org_id"],)):
        key = (r["question_id"], r["matrix_row_id"] or "")
        v = (r["value"] or "").strip()
        if v == "":
            merged.pop(key, None)
        else:
            merged[key] = r["value"]
    questions = org_visible_questions(org)
    by_q = {}
    for (qid, row_id), value in merged.items():
        if value is None or (isinstance(value, str) and value.strip() == ""):
            continue
        by_q.setdefault(qid, []).append((row_id, value))
    basis = {q.id for q in completion_basis_questions()}
    # refresh-cadence flags (data/metric_refresh_register.json): an answered
    # question is due when its oldest row predates its ruled cadence. Nudge
    # only — never gates completion, access or aggregation.
    rstate = refresh_policy.refresh_state(conn, org["org_id"], CURRENT_SNAPSHOT, questions)
    domains = {}
    for qid, q in questions.items():
        sec = q.sub_power or "General"
        d = domains.setdefault(sec, {"name": sec, "order": 999, "questions": []})
        d["order"] = min(d["order"], q.sub_power_order or 999)
        ans = by_q.get(qid)
        rowdefs = dict(q.matrix_row_defs()) if q.type == "matrix" else {}
        rs = rstate.get(qid) or {}
        item = {"question_id": qid, "title": q.display_title, "question": q.text,
                "type": q.type, "unit": q.unit_block(), "answered": bool(ans),
                "required": qid in basis, "value": None, "rows": None,
                "last_updated": rs.get("last"),
                "needs_refresh": bool(ans) and bool(rs.get("due")),
                "refresh_months": rs.get("months")}
        if ans:
            if q.type == "matrix":
                item["rows"] = [{"row": rowdefs.get(r, r) or "—", "value": v}
                                for r, v in sorted(ans, key=lambda x: x[0] or "")]
                item["value"] = "%d level%s" % (len(ans), "" if len(ans) == 1 else "s")
            else:
                item["value"] = ans[0][1]
        d["questions"].append(item)
    out = []
    for sec, d in domains.items():
        # answered first (refresh-due at the top of those), then unanswered
        d["questions"].sort(key=lambda x: (not x["answered"], not x["needs_refresh"], x["title"]))
        tot = len(d["questions"]); ansd = sum(1 for x in d["questions"] if x["answered"])
        d["total"] = tot; d["answered"] = ansd
        d["pct"] = round(100.0 * ansd / tot) if tot else 0
        d["to_refresh"] = sum(1 for x in d["questions"] if x["needs_refresh"])
        out.append(d)
    out.sort(key=lambda d: d["order"])
    tot = sum(d["total"] for d in out); ansd = sum(d["answered"] for d in out)
    return {
        "contribution": contribution_state(conn, org),
        "total": tot, "answered": ansd,
        "pct": round(100.0 * ansd / tot) if tot else 0,
        "to_refresh": sum(d["to_refresh"] for d in out),
        "domains": out,
    }


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
        # the SAME version the board pack stamps (assemble_pack_payload) — the page
        # header and the pack footer can never claim different methodologies
        "methodology_version": 2 if pos.MS_PREVALENCE else 1,
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
    body = await _json(request)
    conn = get_conn()
    conn.execute(
        "INSERT INTO pinned_views(org_id, user_id, layout_json, updated_at) VALUES (?,?,?,datetime('now')) "
        "ON CONFLICT(org_id, user_id) DO UPDATE SET layout_json=excluded.layout_json, updated_at=datetime('now')",
        (org["org_id"], user["user_id"], j(_norm_layout(body.get("layout")))))
    conn.commit()
    return {"ok": True}


@app.post("/api/myview/save-default")
async def save_default_view(request: Request):
    user, org = require_admin(request)
    body = await _json(request)
    conn = get_conn()
    conn.execute(
        "INSERT INTO pinned_views(org_id, user_id, layout_json, updated_at) VALUES (?,'',?,datetime('now')) "
        "ON CONFLICT(org_id, user_id) DO UPDATE SET layout_json=excluded.layout_json, updated_at=datetime('now')",
        (org["org_id"], j(_norm_layout(body.get("layout")))))
    conn.commit()
    return {"ok": True}


# ============================================================== DASHBOARDS ==
# "My dashboards" — multiple named, saveable layouts per user. Slot shape is the
# same as the old single "My view". A user's FIRST dashboard is lazily migrated
# from their old pinned_views row, so nobody loses their existing view.

def _dash_seed_layout(request, org, user, conn):
    """Layout for a user's first-ever dashboard: their old personal pinned view
    if present, else the org default, else the computed starter (8 gaps + 4
    strengths) — the exact cascade the old /api/myview used."""
    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=?",
                       (org["org_id"], user["user_id"])).fetchone()
    if row:
        return uj(row["layout_json"], [])
    row = conn.execute("SELECT layout_json FROM pinned_views WHERE org_id=? AND user_id=''",
                       (org["org_id"],)).fetchone()
    if row:
        return uj(row["layout_json"], [])
    return starter_layout(request, org, user)


def _dash_rows(conn, org, user):
    return conn.execute(
        "SELECT * FROM dashboards WHERE org_id=? AND user_id=? ORDER BY position, created_at",
        (org["org_id"], user["user_id"])).fetchall()


def _ensure_dashboards(request, org, user, conn):
    """Every user always has >=1 dashboard — bootstrap (seeded from the old view)
    on first visit or after the last one is deleted."""
    rows = _dash_rows(conn, org, user)
    if rows:
        return rows
    did = str(uuid.uuid4())
    # idempotent seed — the WHERE NOT EXISTS guards the check-then-insert race when
    # two first-visit requests land together (the app shell + the page both GET
    # /api/dashboards), so a brand-new user can't end up with two "My dashboard"
    # rows. The active pointer is left to _resolve_active, which repairs it.
    conn.execute(
        "INSERT INTO dashboards(dashboard_id, org_id, user_id, name, layout_json, position) "
        "SELECT ?,?,?,?,?,0 WHERE NOT EXISTS(SELECT 1 FROM dashboards WHERE org_id=? AND user_id=?)",
        (did, org["org_id"], user["user_id"], "My dashboard",
         j(_dash_seed_layout(request, org, user, conn)), org["org_id"], user["user_id"]))
    conn.commit()
    return _dash_rows(conn, org, user)


def _resolve_active(request, org, user, conn):
    """(active_id, rows) — validates users.active_dashboard_id and repairs a
    missing/stale pointer to the first dashboard."""
    rows = _ensure_dashboards(request, org, user, conn)
    ids = [r["dashboard_id"] for r in rows]
    cur = conn.execute("SELECT active_dashboard_id FROM users WHERE user_id=?",
                       (user["user_id"],)).fetchone()
    aid = cur["active_dashboard_id"] if cur else None
    if aid not in ids:
        aid = ids[0]
        conn.execute("UPDATE users SET active_dashboard_id=? WHERE user_id=?", (aid, user["user_id"]))
        conn.commit()
    return aid, rows


def _dash_visible_layout(row, vis):
    return [s for s in uj(row["layout_json"], []) if s.get("question_id") in vis]


# Per-dashboard peer sample (2026-08-11). Stored as a {dim,value} cut in cut_json;
# NULL / "all" means the full peer pool. Only these dims are honoured; anything else
# normalises to all-peers so a stale/hand-crafted body can't smuggle an odd filter.
_DASH_CUT_DIMS = {"industry", "fte_band", "group"}


def _dash_cut(row):
    """The dashboard's stored cut as {dim,value}, or None (= all peers)."""
    raw = row["cut_json"] if "cut_json" in row.keys() else None
    if not raw:
        return None
    c = uj(raw, None)
    if not isinstance(c, dict):
        return None
    dim = c.get("dim")
    if dim == "twin":
        return {"dim": "twin", "value": None}
    if dim in _DASH_CUT_DIMS and c.get("value"):
        return {"dim": dim, "value": str(c.get("value"))}
    return None


def _norm_layout(raw):
    """Stored layouts are user-shaped JSON that later request paths TRUST (the CSV
    exporter aggregates per slot) — validate the shape and cap the count on the way
    in (P3 sweep 2026-08-13). Unknown keys are dropped; junk slots are skipped."""
    out = []
    for slot in (raw if isinstance(raw, list) else [])[:60]:
        if not isinstance(slot, dict):
            continue
        qid = slot.get("question_id")
        if not isinstance(qid, str) or not qid or len(qid) > 80:
            continue
        clean = {"question_id": qid}
        rid = slot.get("row_id")
        if isinstance(rid, str) and rid and len(rid) <= 80:
            clean["row_id"] = rid
        clean["size"] = 2 if slot.get("size") == 2 else 1
        cut = _norm_dash_cut(slot.get("cut"))
        if cut:
            clean["cut"] = cut
        out.append(clean)
    return out


def _norm_dash_cut(c):
    """A request-body cut → the value to store (None = all peers, else {dim,value})."""
    if not isinstance(c, dict):
        return None
    dim = c.get("dim")
    if dim == "twin":
        return {"dim": "twin", "value": None}
    if dim in _DASH_CUT_DIMS and c.get("value"):
        return {"dim": dim, "value": str(c.get("value"))[:120]}
    return None


def _dash_meta(row, vis):
    return {"id": row["dashboard_id"], "name": row["name"], "position": row["position"],
            "count": len(_dash_visible_layout(row, vis)), "cut": _dash_cut(row),
            "updated_at": row["updated_at"]}


def _own_dashboard(conn, did, org, user):
    return conn.execute(
        "SELECT * FROM dashboards WHERE dashboard_id=? AND org_id=? AND user_id=?",
        (did, org["org_id"], user["user_id"])).fetchone()


@app.get("/api/dashboards")
async def list_dashboards(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    vis = org_visible_questions(org)
    aid, rows = _resolve_active(request, org, user, conn)
    active = next(r for r in rows if r["dashboard_id"] == aid)
    # ?card=<qid> annotates each dashboard with whether it already holds that
    # metric — powers the card's "Add to dashboard" picker.
    card = request.query_params.get("card")
    metas = []
    for r in rows:
        m = _dash_meta(r, vis)
        if card:
            m["has_card"] = any(s.get("question_id") == card for s in uj(r["layout_json"], []))
        metas.append(m)
    return {
        "dashboards": metas,
        "active_id": aid,
        "active": {"id": active["dashboard_id"], "name": active["name"],
                   "position": active["position"], "layout": _dash_visible_layout(active, vis),
                   "cut": _dash_cut(active)},
    }


@app.get("/api/dashboards/{did}")
async def get_dashboard(did: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    vis = org_visible_questions(org)
    return {"id": row["dashboard_id"], "name": row["name"], "position": row["position"],
            "layout": _dash_visible_layout(row, vis), "cut": _dash_cut(row)}


@app.post("/api/dashboards")
async def create_dashboard(request: Request):
    user, org = require_user(request)
    body = await _json(request)
    conn = get_conn()
    _ensure_dashboards(request, org, user, conn)
    name = (body.get("name") or "New dashboard").strip()[:60] or "New dashboard"
    layout = []
    cut = None
    clone = body.get("clone_from")
    if clone:
        src = _own_dashboard(conn, clone, org, user)
        if src:
            layout = uj(src["layout_json"], [])
            cut = _dash_cut(src)          # a duplicate inherits the source's sample
    if "cut" in body:                     # explicit sample on create wins over the clone's
        cut = _norm_dash_cut(body.get("cut"))
    # create-with-a-card (the "+ New dashboard" option in the card picker)
    with_card = body.get("with_card")
    if with_card and not any(s.get("question_id") == with_card for s in layout):
        layout = layout + [{"question_id": with_card, "size": 1}]
    pos = conn.execute("SELECT COALESCE(MAX(position),-1)+1 p FROM dashboards WHERE org_id=? AND user_id=?",
                       (org["org_id"], user["user_id"])).fetchone()["p"]
    did = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO dashboards(dashboard_id, org_id, user_id, name, layout_json, cut_json, position) VALUES (?,?,?,?,?,?,?)",
        (did, org["org_id"], user["user_id"], name, j(layout), (j(cut) if cut else None), pos))
    conn.execute("UPDATE users SET active_dashboard_id=? WHERE user_id=?", (did, user["user_id"]))
    conn.commit()
    return {"id": did, "name": name, "position": pos, "layout": layout, "cut": cut}


@app.put("/api/dashboards/{did}")
async def update_dashboard(did: str, request: Request):
    user, org = require_user(request)
    body = await _json(request)
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    name = row["name"]
    if body.get("name") is not None:
        name = (body.get("name") or "").strip()[:60] or row["name"]
    layout_json = row["layout_json"]
    if body.get("layout") is not None:
        layout_json = j(_norm_layout(body.get("layout")))
    # cut is set only when the key is present, so a layout/name PUT never clobbers the
    # sample. cut:null (or "all") explicitly clears it back to all-peers.
    cut_json = row["cut_json"] if "cut_json" in row.keys() else None
    cut_out = _dash_cut(row)
    if "cut" in body:
        cut_out = _norm_dash_cut(body.get("cut"))
        cut_json = j(cut_out) if cut_out else None
    conn.execute("UPDATE dashboards SET name=?, layout_json=?, cut_json=?, updated_at=datetime('now') WHERE dashboard_id=?",
                 (name, layout_json, cut_json, did))
    conn.commit()
    return {"ok": True, "name": name, "cut": cut_out}


@app.delete("/api/dashboards/{did}")
async def delete_dashboard(did: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    conn.execute("DELETE FROM dashboards WHERE dashboard_id=?", (did,))
    conn.commit()
    # never leave the user with zero — _resolve_active re-bootstraps if needed
    aid, rows = _resolve_active(request, org, user, conn)
    vis = org_visible_questions(org)
    return {"ok": True, "active_id": aid, "dashboards": [_dash_meta(r, vis) for r in rows]}


@app.post("/api/dashboards/{did}/activate")
async def activate_dashboard(did: str, request: Request):
    user, org = require_user(request)
    conn = get_conn()
    if _own_dashboard(conn, did, org, user) is None:
        raise HTTPException(404, "No such dashboard.")
    conn.execute("UPDATE users SET active_dashboard_id=? WHERE user_id=?", (did, user["user_id"]))
    conn.commit()
    return {"ok": True}


def _toggle_card_layout(layout, qid, row_id=None):
    """Add the card if absent, remove it if present. Returns (layout, now_on)."""
    if any(s.get("question_id") == qid for s in layout):
        return [s for s in layout if s.get("question_id") != qid], False
    slot = {"question_id": qid, "size": 1}
    if row_id:
        slot["row_id"] = row_id
    return layout + [slot], True


@app.post("/api/dashboards/pin")
async def pin_to_dashboard(request: Request):
    """Toggle a metric on the user's ACTIVE dashboard — the target the global
    pin-star points at from anywhere in the app."""
    user, org = require_user(request)
    body = await _json(request)
    qid = body.get("question_id")
    if not qid:
        raise HTTPException(400, "question_id required")
    conn = get_conn()
    aid, rows = _resolve_active(request, org, user, conn)
    active = next(r for r in rows if r["dashboard_id"] == aid)
    layout, _on = _toggle_card_layout(uj(active["layout_json"], []), qid, body.get("row_id"))
    conn.execute("UPDATE dashboards SET layout_json=?, updated_at=datetime('now') WHERE dashboard_id=?",
                 (j(layout), aid))
    conn.commit()
    vis = org_visible_questions(org)
    pinned = [s.get("question_id") for s in layout if s.get("question_id") in vis]
    return {"pinned_ids": pinned, "active_id": aid, "dashboard_name": active["name"]}


@app.post("/api/dashboards/{did}/toggle-card")
async def toggle_card_on_dashboard(did: str, request: Request):
    """Add/remove a metric on a SPECIFIC dashboard — the card's picker target."""
    user, org = require_user(request)
    body = await _json(request)
    qid = body.get("question_id")
    if not qid:
        raise HTTPException(400, "question_id required")
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    layout, now_on = _toggle_card_layout(uj(row["layout_json"], []), qid, body.get("row_id"))
    conn.execute("UPDATE dashboards SET layout_json=?, updated_at=datetime('now') WHERE dashboard_id=?",
                 (j(layout), did))
    conn.commit()
    vis = org_visible_questions(org)
    return {"on": now_on, "count": len([s for s in layout if s.get("question_id") in vis])}


@app.post("/api/signals/action")
async def signal_action(request: Request):
    """Per-user Signals triage: set one status (priority | saved | dismissed) on
    a signal, or clear it (status=active/None). Keyed by question_id — the per-
    metric cap means one signal per metric."""
    user, org = require_user(request)
    body = await _json(request)
    qid = (body.get("question_id") or "").strip()
    status = body.get("status")
    if not qid:
        raise HTTPException(400, "question_id required")
    conn = get_conn()
    if status in (None, "", "active", "new"):
        conn.execute("DELETE FROM signal_actions WHERE org_id=? AND user_id=? AND question_id=?",
                     (org["org_id"], user["user_id"], qid))
        status = None
    elif status == "snoozed":
        # "real, but not this cycle": hide until snooze_until, then auto-return (read path).
        # Clamp the requested window to a sane range; default ~6 weeks ("next cycle").
        try:
            days = int(body.get("snooze_days") or 42)
        except (TypeError, ValueError):
            days = 42
        days = max(1, min(days, 365))
        conn.execute(
            "INSERT INTO signal_actions(org_id, user_id, question_id, status, snooze_until, updated_at) "
            "VALUES (?,?,?,?,datetime('now', ?),datetime('now')) "
            "ON CONFLICT(org_id, user_id, question_id) DO UPDATE SET status=excluded.status, "
            "snooze_until=excluded.snooze_until, updated_at=datetime('now')",
            (org["org_id"], user["user_id"], qid, status, "+%d days" % days))
    elif status in ("priority", "saved", "dismissed"):
        conn.execute(
            "INSERT INTO signal_actions(org_id, user_id, question_id, status, snooze_until, updated_at) "
            "VALUES (?,?,?,?,NULL,datetime('now')) "
            "ON CONFLICT(org_id, user_id, question_id) DO UPDATE SET status=excluded.status, "
            "snooze_until=NULL, updated_at=datetime('now')",
            (org["org_id"], user["user_id"], qid, status))
    else:
        raise HTTPException(400, "bad status")
    conn.commit()
    return {"ok": True, "question_id": qid, "status": status}


@app.post("/api/signals/action-bulk")
async def signal_action_bulk(request: Request):
    """Batch triage: set ONE status on many signals at once ("dismiss all in this
    view", and the Undo that restores them). Atomic. Snooze is excluded — it needs
    a per-signal duration, so it stays on the single-action route."""
    user, org = require_user(request)
    body = await _json(request)
    qids = [str(q).strip() for q in (body.get("question_ids") or []) if str(q).strip()][:500]
    status = body.get("status")
    if not qids:
        return {"ok": True, "count": 0, "status": status}
    conn = get_conn()
    if status in (None, "", "active", "new"):
        conn.executemany("DELETE FROM signal_actions WHERE org_id=? AND user_id=? AND question_id=?",
                         [(org["org_id"], user["user_id"], q) for q in qids])
        status = None
    elif status in ("priority", "saved", "dismissed"):
        conn.executemany(
            "INSERT INTO signal_actions(org_id, user_id, question_id, status, snooze_until, updated_at) "
            "VALUES (?,?,?,?,NULL,datetime('now')) "
            "ON CONFLICT(org_id, user_id, question_id) DO UPDATE SET status=excluded.status, "
            "snooze_until=NULL, updated_at=datetime('now')",
            [(org["org_id"], user["user_id"], q, status) for q in qids])
    else:
        raise HTTPException(400, "bad status")
    conn.commit()
    return {"ok": True, "count": len(qids), "status": status}


@app.post("/api/signals/seen")
async def signals_seen(request: Request):
    """Mark signals as seen for this user (clears their NEW state). The client
    posts the sig_ids it is currently showing — called when the Signals page is
    viewed. Idempotent."""
    user, org = require_user(request)
    body = await _json(request)
    ids = [str(s) for s in (body.get("sig_ids") or []) if s][:2000]
    if ids:
        conn = get_conn()
        conn.executemany(
            "INSERT OR IGNORE INTO signal_seen(org_id, user_id, sig_id) VALUES (?,?,?)",
            [(org["org_id"], user["user_id"], sid) for sid in ids])
        conn.commit()
    return {"ok": True, "seen": len(ids)}


# ----------------------------------------------------------- notifications ----
@app.get("/api/notifications")
async def list_notifications(request: Request):
    """The bell: this user's admitted change events (newest first) + unread
    count. Org-scoped via the session, like everywhere. Inbox-off → empty."""
    user, org = require_user(request)
    conn = get_conn()
    urow = conn.execute("SELECT notify_prefs_json FROM users WHERE user_id=?", (user["user_id"],)).fetchone()
    prefs = notifications.user_prefs(urow["notify_prefs_json"] if urow else "{}")
    if not prefs["inbox_enabled"]:
        return {"unread": 0, "events": [], "inbox_enabled": False}
    rows = conn.execute(
        "SELECT e.*, r.read_at FROM notification_reads r JOIN notification_events e ON e.id=r.event_id "
        "WHERE r.user_id=? AND r.suppressed_reason IS NULL AND e.org_id=? "
        "ORDER BY e.detected_at DESC, e.id DESC LIMIT 100",
        (user["user_id"], org["org_id"])).fetchall()
    out = []
    for r in rows:
        ev = notifications.render_event(dict(r))
        ev["read"] = r["read_at"] is not None
        out.append(ev)
    # notification coherence (step-3, ruling C): a confirm-flagged change confirms the org's
    # strategy aim — it stays in the inbox (nothing dropped) but NEVER leads. Tension + risk lead
    # the list and the unread badge; confirm sorts to the bottom and is excluded from the badge —
    # mirroring L4 demoting a confirming signal off the home briefing while keeping it findable.
    out.sort(key=lambda e: bool(e.get("confirm")))   # stable → confirm to the bottom, order otherwise kept
    unread = sum(1 for e in out if not e["read"] and not e.get("confirm"))
    return {"unread": unread, "events": out, "inbox_enabled": True}


@app.post("/api/notifications/read")
async def mark_notifications_read(request: Request):
    user, org = require_user(request)
    body = await _json(request)
    conn = get_conn()
    if body.get("all"):
        conn.execute("UPDATE notification_reads SET read_at=datetime('now') WHERE user_id=? AND read_at IS NULL",
                     (user["user_id"],))
    else:
        ids = [int(i) for i in (body.get("event_ids") or []) if str(i).isdigit()][:500]
        if ids:
            conn.executemany("UPDATE notification_reads SET read_at=datetime('now') WHERE user_id=? AND event_id=?",
                             [(user["user_id"], i) for i in ids])
    conn.commit()
    return {"ok": True}


@app.get("/api/notify-prefs")
async def get_notify_prefs(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    urow = conn.execute("SELECT notify_prefs_json FROM users WHERE user_id=?", (user["user_id"],)).fetchone()
    return {"prefs": notifications.user_prefs(urow["notify_prefs_json"] if urow else "{}"),
            "min_money_floor": notifications.alert_cfg().get("min_money_change_gbp", 10000)}


@app.put("/api/notify-prefs")
async def put_notify_prefs(request: Request):
    user, org = require_user(request)
    body = await _json(request)
    p = body.get("prefs") or {}
    if not isinstance(p, dict):
        raise HTTPException(400, "prefs must be an object.")
    try:
        _min_money = max(0, int(p.get("min_money_gbp") or 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "min_money_gbp must be a number.")
    clean = {
        "inbox_enabled": bool(p.get("inbox_enabled", True)),
        "email_frequency": p.get("email_frequency") if p.get("email_frequency") in ("off", "daily", "weekly") else "weekly",
        "lenses": [l for l in (p.get("lenses") or []) if l in notifications.ALL_LENSES] or notifications.ALL_LENSES,
        "events": [e for e in (p.get("events") or []) if e in notifications.ALL_EVENTS],
        "min_money_gbp": _min_money,
    }
    conn = get_conn()
    conn.execute("UPDATE users SET notify_prefs_json=? WHERE user_id=?", (j(clean), user["user_id"]))
    conn.commit()
    return {"ok": True, "prefs": notifications.user_prefs(j(clean))}


@app.post("/api/notify-prefs/unsubscribe")
async def unsubscribe_email(request: Request):
    """One-click email opt-out — flips the master email toggle to off, honoured
    before any other pref. The in-app inbox is unaffected."""
    user, org = require_user(request)
    conn = get_conn()
    urow = conn.execute("SELECT notify_prefs_json FROM users WHERE user_id=?", (user["user_id"],)).fetchone()
    p = uj(urow["notify_prefs_json"] if urow else "{}", {})
    p["email_frequency"] = "off"
    conn.execute("UPDATE users SET notify_prefs_json=? WHERE user_id=?", (j(p), user["user_id"]))
    conn.commit()
    return {"ok": True}


@app.post("/api/notifications/run-sweep")
async def trigger_sweep(request: Request):
    """Manual trigger for the nightly pipeline (the in-process scheduler is env-
    gated by LUMI_SIGNAL_SWEEP; this runs it on demand). Platform-admin only —
    recomputes change events and fans out notifications for EVERY org (a cross-
    tenant write), so it carries no org scope. Pass ?digest=daily,weekly to ALSO
    send the email digest (real emails when LUMI_SMTP_HOST is set, else console-
    logged) — used to smoke-test the full pipeline at go-live."""
    user = require_platform_admin(request)
    conn = get_conn()
    swept, events = run_signal_sweep(conn, verbose=False)
    out = {"ok": True, "orgs_swept": swept, "events": events}
    dig = (request.query_params.get("digest") or "").strip()
    if dig:
        freqs = tuple(f for f in (x.strip() for x in dig.split(",")) if f in ("daily", "weekly"))
        if freqs:
            out["digests_sent"] = notifications.run_email_digest(
                conn, base_url=base_url() or "", frequencies=freqs)
            out["digest_frequencies"] = list(freqs)
    _audit(user, "platform.run_sweep", "platform", None,
           {"orgs_swept": swept, "events": events, "digest": dig or None})
    return out


# ==================================================================== PREFS ==

@app.get("/api/prefs")
async def get_prefs(request: Request):
    user, org = require_user(request)
    return {"prefs": uj(user["chart_prefs_json"], {})}


@app.put("/api/prefs")
async def put_prefs(request: Request):
    user, org = require_user(request)
    body = await _json(request)
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
    body = await _json(request)
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


def cut_label_of(cut):
    if not cut or cut.get("dim") in (None, "all"): return "All peers"
    if cut.get("dim") == "twin": return "Organisations like you"
    if cut.get("dim") == "group": return cut.get("label") or "Custom group"
    return str(cut.get("value") or cut.get("dim"))


def csv_cell(v):
    """Excel formula-injection guard for USER-AUTHORED strings that land in CSV cells
    (peer-group names, option labels the org typed): a leading = + - @ makes Excel
    execute the cell. Prefix with a quote — visually harmless, defuses execution.
    Apply to user-supplied text cells only, never to numbers (P3 sweep 2026-08-13)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _csv_response(buf, org, artefact, cut_label):
    """World-class export discipline (2026-08-09): BOM for Excel £/dash safety, and a
    filename that files itself — lumi — <org> — <artefact> — <cut> — <date>.csv."""
    import datetime as _dt
    safe = lambda s: re.sub(r"[^A-Za-z0-9&+ '-]+", "", s or "").strip()
    # display names live in the identity store (D6) — the middleware org carries none
    _name = (identity.org_display(org["org_id"]) or {}).get("name") if org else None
    fname = "lumi — %s — %s — %s — %s.csv" % (
        safe(_name or "organisation"), safe(artefact) or "benchmark", safe(cut_label or "All peers"),
        _dt.date.today().isoformat())
    ascii_fn = re.sub(r"[^A-Za-z0-9 .-]", "", fname.replace("—", "-"))
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''%s; filename=\"%s\"" % (
                        urllib.parse.quote(fname), ascii_fn)})


@app.get("/api/gap-register.csv")
async def gap_register_csv(request: Request):
    user, org = require_admin(request)
    cut = parse_cut(request, org)
    reg = build_gap_register(request, user, org, cut)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Benchmark", "Category", "Type", "Practice / policy", "Tier",
                "Your status", "In place", "Peer adoption %", "Sector adoption %", "Sector n", "Gap", "n"])
    for r in reg["rows"]:
        w.writerow([r["superpower"], r["subpower"], r["category"], r["name"], r["tier"],
                    csv_cell(r["org_status"]),
                    {"in_place": "In place", "partial": "Partially", "not_in_place": "Not in place"}.get(r.get("status"), "Not assessable"),
                    "suppressed" if r["suppressed"] else r["peer_adoption_pct"],
                    r["sector_adoption_pct"] if r["sector_adoption_pct"] is not None else "",
                    r.get("sector_n") if r.get("sector_n") is not None else "",
                    r["gap"] if r["gap"] is not None else "", r["n"]])
    w.writerow([])
    w.writerow(["# Comparison pool: %d UK organisation profiles. See lumihr.co.uk methodology for sources." % (get_meta("peer_pool", {}).get("responding_orgs") or 0)])
    return _csv_response(buf, org, "gap register", cut_label_of(cut))


# ============================================================== BENCHMARK CSV ==

# quantitative CSV shape shared by the whole-benchmark export and the per-dashboard
# export — one row per metric, numbers matching the cards exactly (same assemble_card
# path), suppressed cells blank + suppressed=true so a small-cell distribution never leaks.
BENCH_CSV_HEADER = ["question_id", "title", "subpower", "your_value", "unit",
                    "p10", "p25", "p50", "p75", "p90", "n", "cut_label", "window", "suppressed"]


def _bench_csv_row(qid, q, card, window=""):
    suppressed = bool(card.get("suppressed"))
    cut_label = (card.get("cut") or {}).get("label", "")
    # your_value: numeric value, else the selected label (multi_select joined)
    you = card.get("you") or {}
    if "value" in you:
        your_value = you["value"]
    elif you.get("labels"):
        your_value = "; ".join(you["labels"])
    elif "label" in you:
        your_value = you["label"]
    else:
        your_value = ""
    # percentiles only exist for numeric distributions; suppressed cells stay blank
    blk = card.get("block") if not suppressed else None
    if blk and q.type == "numeric":
        stats = [blk.get("p10", ""), blk.get("p25", ""), blk.get("p50", ""),
                 blk.get("p75", ""), blk.get("p90", "")]
    else:
        stats = ["", "", "", "", ""]
    _ub = q.unit_block() or {}
    _ut = _ub.get("type")
    _unit = _ub.get("symbol") or ("" if _ut in (None, "none") else _ut)   # "none" is not a unit
    # csv_cell on the USER-AUTHORED strings (your_value carries typed option labels,
    # cut_label carries peer-group names) — Excel formula-injection guard
    return [qid, q.display_title, q.sub_power, csv_cell(your_value), _unit,
            *stats, card.get("n", 0), csv_cell(cut_label), window,
            "true" if suppressed else "false"]


@app.get("/api/benchmark.csv")
async def benchmark_csv(request: Request):
    """Quantitative export: one row per org-visible metric, numbers matching the
    benchmark cards exactly (same assemble_card path). Suppressed cells ship
    blank stats + suppressed=true — a small-cell distribution never leaks."""
    user, org = require_user(request)
    conn = get_conn()
    entitled = make_entitled(user, org)
    cut = parse_cut(request, org)
    tb = twin_blocks_if_needed(conn, org, cut)
    answers = org_answers_for(org)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(BENCH_CSV_HEADER)

    _sp = request.query_params.get("sp")   # optional domain scope (category-page export)
    _visq = org_visible_questions(org)
    if _sp and not any(q.sub_power == _sp for q in _visq.values()):
        raise HTTPException(404, "No such area for this organisation.")
    _snap = conn.execute("SELECT collection_window FROM snapshots WHERE snapshot_id=?",
                         (CURRENT_SNAPSHOT,)).fetchone()
    _win = (_snap and _snap["collection_window"]) or ""    # fetched ONCE, not per row
    rows = []
    for qid, q in _visq.items():
        if _sp and q.sub_power != _sp:
            continue
        p = payloads().get(qid)
        if p is None:
            continue
        card = assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None, entitled)
        rows.append(_bench_csv_row(qid, q, card, _win))

    rows.sort(key=lambda r: (r[2] or "", r[1] or ""))
    for r in rows:
        w.writerow(r)

    w.writerow([])
    w.writerow(["# Comparison pool: %d UK organisation profiles. See lumihr.co.uk methodology for sources." % (get_meta("peer_pool", {}).get("responding_orgs") or 0)])
    return _csv_response(buf, org, (_sp + " benchmarks") if _sp else "benchmark", cut_label_of(cut))


@app.get("/api/dashboards/{did}/export.csv")
async def dashboard_csv(did: str, request: Request):
    """The numbers behind one saved dashboard — one row per pinned card, in the
    dashboard's own order, with the same stats/suppression as the benchmark
    export. Honours a slot's own peer cut where set, else the page cut."""
    user, org = require_user(request)
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    vis = org_visible_questions(org)
    entitled = make_entitled(user, org)
    req_cut = parse_cut(request, org)
    answers = org_answers_for(org)

    _snap = conn.execute("SELECT collection_window FROM snapshots WHERE snapshot_id=?",
                         (CURRENT_SNAPSHOT,)).fetchone()
    _win = (_snap and _snap["collection_window"]) or ""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(BENCH_CSV_HEADER)
    seen = set()
    for slot in _dash_visible_layout(row, vis):
        qid = slot.get("question_id")
        if not qid or qid in seen:
            continue
        seen.add(qid)
        q = vis.get(qid)
        p = payloads().get(qid)
        if q is None or p is None:
            continue
        # stored layout JSON is user-shaped — normalise the per-slot cut like the
        # dashboard-level cut; junk falls back to the request cut instead of a 500
        _slot_cut = _norm_dash_cut(slot.get("cut"))
        eff_cut = _slot_cut or req_cut
        if _slot_cut and _slot_cut.get("dim") == "group":
            _row = conn.execute("SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
                                (_slot_cut.get("value") or "", org["org_id"])).fetchone()
            if _row is None:
                eff_cut = req_cut
            else:
                eff_cut = {"dim": "group", "value": _row["group_id"], "label": _row["name"],
                           "criteria": uj(_row["criteria_json"], {})}
        tb = twin_blocks_if_needed(conn, org, eff_cut)
        card = assemble_card(q, p, org, answers, eff_cut, {qid: tb.get(qid)} if tb else None, entitled)
        w.writerow(_bench_csv_row(qid, q, card, _win))

    return _csv_response(buf, org, "dashboard — " + (row["name"] or "view"), cut_label_of(req_cut))


# ================================================================== ANALYST ==

# Per-org budget guard: every benchmark question is potentially an uncached
# model call, so cap the hourly rate (generous — a member reads answers far
# slower than this) and the question length (retrieval + prompt weight).
ANALYST_RATE_PER_HOUR = int(os.environ.get("LUMI_ANALYST_RATE_PER_HOUR", "40"))
ANALYST_MAX_QUESTION_CHARS = int(os.environ.get("LUMI_ANALYST_MAX_QUESTION_CHARS", "500"))
_analyst_asks = defaultdict(list)


def _analyst_rate_limited(org_id):
    import time as _t
    now = _t.time()
    _analyst_asks[org_id] = [t for t in _analyst_asks[org_id] if now - t < 3600]
    if len(_analyst_asks[org_id]) >= ANALYST_RATE_PER_HOUR:
        return True
    _analyst_asks[org_id].append(now)
    return False


# Board-pack generation fires a large (max_tokens=8000, high-effort) Claude call.
# Cap it per org per day so a member can't rack up spend by regenerating; the
# deterministic pack floor is never capped (only the paid AI call is).
BOARDPACK_PER_DAY = int(os.environ.get("LUMI_BOARDPACK_PER_DAY", "20"))
_boardpack_gen = defaultdict(list)


def _boardpack_rate_limited(org_id):
    import time as _t
    now = _t.time()
    _boardpack_gen[org_id] = [t for t in _boardpack_gen[org_id] if now - t < 86400]
    if len(_boardpack_gen[org_id]) >= BOARDPACK_PER_DAY:
        return True
    _boardpack_gen[org_id].append(now)
    return False


ANALYST_LOG_RETENTION_DAYS = int(os.environ.get("LUMI_ANALYST_LOG_RETENTION_DAYS", "180"))


def _analyst_log(conn, org, user, question, intent, matched, source, answer):
    """Audit trail for the chat surface — the sibling AI surfaces persist their
    output; until now Ask lumi answers vanished on response. Reviewable when a
    member reports a bad answer; purged with the AI caches on consent withdrawal
    (purge_ai_cache). Retention: rows older than LUMI_ANALYST_LOG_RETENTION_DAYS
    (default 180) are pruned opportunistically on write (data-minimisation — the
    log is an operational audit trail, not a permanent record). Logging must
    never break the answer path."""
    try:
        conn.execute("INSERT INTO analyst_log (org_id, user_id, question, intent, matched_json, source, answer) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (org["org_id"], user["user_id"], question, intent, j(matched or []), source, answer))
        conn.execute("DELETE FROM analyst_log WHERE created_at < datetime('now', ?)",
                     ("-%d days" % ANALYST_LOG_RETENTION_DAYS,))
        conn.commit()
    except Exception:
        pass


@app.post("/api/analyst")
async def analyst(request: Request):
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_ANALYST)
    body = await _json(request)
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    if len(question) > ANALYST_MAX_QUESTION_CHARS:
        raise HTTPException(400, "That's a long one — keep questions under %d characters."
                            % ANALYST_MAX_QUESTION_CHARS)
    if _analyst_rate_limited(org["org_id"]):
        raise HTTPException(429, "You've asked a lot in the last hour — give it a little "
                                 "while and try again.")
    conn = get_conn()
    vis = org_visible_questions(org)

    # Intent routing: finding a metric, explaining a term, or how-to guidance go
    # to the GUIDE path (no peer data → can't cite a figure). Anything else is a
    # benchmark question and falls through to the strict, cited analyst below.
    intent, extra = guide.classify(question)
    if intent != "benchmark":
        res = await _guide_response(question, intent, extra, org, vis)
        _analyst_log(conn, org, user, question, intent, res.get("matched"),
                     "guide-" + res.get("source", "deterministic"), res.get("answer", ""))
        return res

    contrib = contribution_state(conn, org)
    if contrib["reduced"]:
        resp = {"answer": "Your full benchmark is paused until your reward data is complete — "
                          "finish your submission and I'll have every comparison ready for you again.",
                "chips": [], "matched": [], "reduced": True}
        _analyst_log(conn, org, user, question, intent, [], "reduced", resp["answer"])
        return resp

    if retrieval.is_vague(question):
        # nothing topic-shaped to match ("how much do peers usually offer?") —
        # the capabilities nudge beats three readouts of whatever fuzzy-scored
        resp = {"answer": guide.CAPABILITIES, "chips": [],
                "links": [{"label": "How lumi works", "route": "/how-lumi-works"}],
                "matched": [], "kind": "help"}
        _analyst_log(conn, org, user, question, intent, [], "vague", resp["answer"])
        return resp

    def _bench_matches(q):
        hits = [x for x in retrieval.search_questions(q, limit=12) if x in vis][:6]
        if hits and retrieval.distinctive_coverage(q, hits) < 0.34:
            return []   # fuzzy noise, not real coverage — offer the request path
        return hits
    qids = _bench_matches(question)
    if not qids:
        # the retrieval tokenizer doesn't stem, so "how do our pensions compare?"
        # misses the singular library term — retry singularised before we ever
        # tell a member lumi doesn't benchmark something it does
        alt = _depluralise(question)
        if alt != question.lower():
            qids = _bench_matches(alt)
    if not qids:
        resp = {"answer": "lumi doesn't benchmark that yet, so I won't guess at a figure. "
                          "If it would be useful, request it — member requests shape "
                          "what lumi measures next.",
                "chips": [], "matched": [], "no_metric": True, "topic": question}
        _analyst_log(conn, org, user, question, intent, [], "no_metric", resp["answer"])
        return resp
    answers = org_answers_for(org)
    entitled = make_entitled(user, org)
    questions = vis
    data = {"organisation": {"name": (identity.org_display(org["org_id"]) or {}).get("name"),
                             "industry": org["industry"],
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

    # the SDK call is synchronous — run it off the event loop so one member's
    # question can never stall every other request on this single-loop server
    res = await to_thread.run_sync(claude_api.analyst_answer, question, data)
    if not res["ok"]:
        # deterministic fallback: cite the closest matches' readouts, most
        # on-topic first, each named — a member must be able to tell which
        # metric every line describes
        order = {qid: i for i, qid in
                 enumerate(retrieval.topic_rank(question, [m["question_id"] for m in data["metrics"]]))}
        ranked = sorted(data["metrics"], key=lambda m: order.get(m["question_id"], len(order)))
        lines = []
        chips = []
        for m in ranked[:3]:
            blk = m["all_peers"]
            if blk.get("readout"):
                lines.append("%s — %s" % (m["metric"], blk["readout"]))
            if blk.get("you_display") and blk.get("you_percentile") is not None:
                chips.append({"label": m["metric"], "value": blk["you_display"],
                              "sub": "P%d · All peers · n=%d" % (round(blk["you_percentile"]), blk.get("n", 0)),
                              "question_id": m["question_id"]})
        if not lines:
            resp = {"answer": "The closest matches don't have enough peer data to show safely "
                              "yet — try a broader question, or open the metric itself for the "
                              "full picture.",
                    "chips": chips, "matched": qids, "fallback": True}
        else:
            resp = {"answer": "Here's where you stand on the closest matches to your question:\n\n"
                              + "\n\n".join(lines),
                    "chips": chips, "matched": qids, "fallback": True}
        _analyst_log(conn, org, user, question, intent, qids, "fallback", resp["answer"])
        return resp
    _analyst_log(conn, org, user, question, intent, qids, "model", res["answer"])
    return {"answer": res["answer"], "chips": res["chips"], "matched": qids}


def _depluralise(question):
    """Best-effort singularise each word so a plural query ('pensions',
    'allowances', 'EAPs') still matches the singular library term — the
    retrieval tokenizer doesn't stem. Words are extracted with the same regex
    the tokenizer uses (so trailing punctuation — 'pensions?' — can't defeat
    it), and each candidate is vocabulary-checked against the library
    (retrieval.singularise), so 'bonus' can never mangle to 'bonu'."""
    words = re.findall(r"[a-z0-9%£]+", question.lower())
    return " ".join(retrieval.singularise(w) for w in words)


async def _guide_response(question, intent, extra, org, vis):
    """Ask lumi's non-benchmark side: find a metric · explain a term · how-to.
    Assembles the metric CATALOGUE (names/areas only — never values), the
    glossary and the feature guide, lets Claude phrase it warmly, and falls back
    to the deterministic glossary/feature copy when the model is unavailable."""
    answers = org_answers_for(org)
    answered_q = {k[0] for k in answers}

    def _matches(q):
        """Catalogue hits with real topic coverage — the same distinctive gate
        the benchmark path uses, so a topic lumi doesn't cover ("submarines")
        returns nothing rather than fuzzy noise."""
        hits = [x for x in retrieval.search_questions(q, limit=10) if x in vis]
        return hits if (hits and retrieval.distinctive_coverage(q, hits) >= 0.34) else []

    # Only "find" needs the catalogue (its chips). Term/how-to questions never
    # show metric chips, so we skip the (full-catalogue) retrieval scan entirely.
    if intent == "find" and retrieval.is_vague(question):
        # "what metrics do you have?" — no topic to match; the capabilities
        # blurb answers this shape properly, the request-a-metric refusal doesn't
        return {"answer": guide.CAPABILITIES, "chips": [],
                "links": [{"label": "How lumi works", "route": "/how-lumi-works"}],
                "matched": [], "kind": "help", "source": "deterministic"}
    qids = []
    if intent == "find":
        qids = _matches(question)
        if not qids:
            # the retrieval tokenizer doesn't stem, so a plural ("pensions") misses
            # the singular library term. Retry singularised before we ever tell a
            # member lumi doesn't cover something it does.
            alt = _depluralise(question)
            if alt != question.lower():
                qids = _matches(alt)
    metas = []
    for qid in qids:
        q = vis[qid]
        metas.append({"question_id": qid, "name": q.display_title,
                      "area": q.sub_power or q.category or q.superpower,
                      "in_your_data": qid in answered_q})
    # chips are the clickable metric list — only meaningful for "find" (for term
    # and how-to questions the retrieval matches are noise, so we don't show them)
    chips = []
    if intent == "find":
        chips = [{"label": m["name"], "value": "in your data" if m["in_your_data"] else "add data",
                  "sub": m["area"], "question_id": m["question_id"]} for m in metas[:8]]

    # nothing in the catalogue for a "find" → offer the request path, no chips
    if intent == "find" and not metas:
        return {"answer": guide.deterministic_answer("find", None, question, False),
                "chips": [], "matched": [], "no_metric": True, "topic": question,
                "kind": "find", "source": "deterministic"}

    links = guide.links_for(intent, extra)
    ctx = {"intent": intent, "question": question, "glossary": guide.GLOSSARY,
           "features": [{"answer": f["answer"], "route": f["route"], "cta": f["cta"]} for f in guide.FEATURES],
           "metrics": metas, "term": extra if intent == "term" else None,
           "organisation": {"name": (identity.org_display(org["org_id"]) or {}).get("name")}}
    res = (await to_thread.run_sync(claude_api.guide_answer, ctx)) if AI_ANALYST else {"ok": False}
    if res.get("ok"):
        answer = res["answer"]
        if res.get("links"):
            links = res["links"]
    else:
        answer = guide.deterministic_answer(intent, extra, question, bool(metas))
    return {"answer": answer, "chips": chips, "links": links, "matched": qids, "kind": intent,
            "source": "model" if res.get("ok") else "deterministic"}


def _analyst_block(card):
    out = {"suppressed": card.get("suppressed"), "n": card.get("n"), "n_real": card.get("n_real", 0),
           "cut_label": card["cut"]["label"], "readout": card.get("readout")}
    if card.get("block"):
        b = dict(card["block"])
        b.pop("options", None)
        out["aggregates"] = b
        if card.get("type") in ("single_select", "yes_no", "multi_select"):
            out["distribution"] = [{"label": o["label"], "pct": o["pct"]}
                                   for o in card["block"].get("options", [])]
            if card.get("type") == "multi_select":
                # organisations pick several options, so the shares legitimately
                # sum past 100 — spelled out so the model can't misread the split
                out["distribution_semantics"] = ("multi-select: each pct is the share of "
                                                 "organisations selecting that option; "
                                                 "shares can sum past 100")
    if card.get("matrix_rows"):
        out["rows"] = [{"label": r["label"],
                        "suppressed": r["suppressed"],
                        "aggregates": r.get("block"),
                        "you": (r.get("you") or {}).get("value"),
                        "you_percentile": (r.get("you") or {}).get("percentile")}
                       for r in card["matrix_rows"]]
    you = card.get("you") or {}
    # explicit None-checks: `or` would drop a legitimate 0 answer (0 days, 0%)
    out["you_value"] = you["value"] if you.get("value") is not None else you.get("label")
    out["you_display"] = you.get("display") if you.get("display") is not None else you.get("label")
    out["you_percentile"] = you.get("percentile")
    return out


_starters_cache = {}                 # org_id → (monotonic ts, starters)
_STARTERS_TTL = 600                  # the gap list moves when answers do — 10 min is plenty


@app.get("/api/analyst/starters")
async def analyst_starters(request: Request):
    import time as _t
    user, org = require_user(request)
    cached = _starters_cache.get(org["org_id"])
    if cached and _t.monotonic() - cached[0] < _STARTERS_TTL:
        return {"starters": cached[1]}
    items, _ = build_items(request, org, user, {"dim": "all"})
    gaps = pos.top_gaps(items, 6)
    # mix: a couple of benchmark questions from the org's biggest gaps, plus
    # guide examples so members discover that Ask lumi also finds metrics,
    # explains terms and helps with the platform.
    starters = []
    seen_q = set()
    for g in gaps:
        # one starter per question family — two rows of the same matrix read
        # as near-duplicates — and the label goes in quotes, because display
        # titles jammed into a sentence produce broken grammar
        if g.get("question_id") in seen_q:
            continue
        seen_q.add(g.get("question_id"))
        starters.append("How do we compare on ‘%s’?" % g["label"])
        if len(starters) == 3:
            break
    bench_fallback = [
        "Where do we sit on employer pension contributions?",
        "How common are holiday purchase schemes?",
        "How does our annual leave entitlement compare?",
    ]
    while len(starters) < 3:
        starters.append(bench_fallback[len(starters)])
    starters += ["Do you have any metrics on parental leave?",
                 "What does ‘percentile’ mean?",
                 "How do I add my data?"]
    starters = starters[:6]
    _starters_cache[org["org_id"]] = (_t.monotonic(), starters)
    return {"starters": starters}


# ---------------------------------------------------- strategy commentary ----
def _strategy_commentary_payload(request, user, org):
    """Grounded payload for the strategy reading: the declared dials plus the SAME
    per-domain aim-vs-position rows the board pack computes (hero path, all peers)."""
    conn = get_conn()
    cut = {"dim": "all"}
    items, tb = build_items(request, org, user, cut)
    _visq = org_visible_questions(org)
    _answers = org_answers_for(org)
    _mp_cfg = pos.market_position_config()
    strat = strategy_for_engine(conn, org["org_id"])
    done = bool(conn.execute(
        "SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
        (org["org_id"],)).fetchone())
    if not (strat and done):
        return None
    _prev = pos.prevalence_items(org["org_id"], cut, _visq, payloads(), _answers, make_entitled(user, org), tb)
    _prac = pos.practice_position_items(org["org_id"], cut, _visq, payloads(), _answers, make_entitled(user, org), tb)
    _sec_order = []
    for _q in _visq.values():
        if _q.sub_power and _q.sub_power not in _sec_order:
            _sec_order.append(_q.sub_power)
    _sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in _visq.values() if q.sub_power == x))
    hero = pos.hero_signals(items, _prev, _sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=_prac, tile_min=TILE_MIN_POSITIONED,
                            mp_config=_mp_cfg, strategy=strat)
    stance_word = {"lag": "below market", "match": "on market", "lead": "above market"}
    rows = []
    for d in hero.get("domains", []):
        t = d.get("target")
        if not t:
            continue
        rows.append({"area": d["name"], "aim": stance_word.get(t.get("stance")),
                     "position": (d.get("position") or {}).get("verdict"),
                     "alignment": t.get("alignment"),
                     "aim_is_override": d["name"] in (strat.get("domain_targets") or {})})
    return {
        "org_name": (identity.org_display(org["org_id"]) or {}).get("name"),   # reward-side name is NULLed (Phase-1 split)
        "stance": dict(
            {k: strat.get(k) for k in ("market_position", "reward_mix", "pay_for_performance",
                                       "location_approach", "family_position", "primary_objective")},
            **({"transparency": strat.get("transparency")}
               if (strat.get("provenance") or {}).get("transparency") == "live" else {})),
        "objective_label": OBJECTIVE_LABELS.get(strat.get("primary_objective")),
        "areas": rows,
        "off_aim": [r["area"] for r in rows if r["alignment"] and r["alignment"] != "on_target"],
    }


@app.post("/api/strategy/commentary")
async def strategy_commentary(request: Request):
    """AI reading of the declared strategy against the live position — grounded ONLY in
    the dials + the pack's aim-vs-position rows, validated post-generation, cached until
    the underlying read changes (metric_commentary table, question_id '__strategy__')."""
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_COMMENTARY)
    body = await _json(request)
    conn = get_conn()
    payload = _strategy_commentary_payload(request, user, org)
    if payload is None:
        raise HTTPException(404, "No completed strategy to read.")
    phash = hashlib.sha256(
        (j(payload) + "|" + claude_api.STRATEGY_COMMENTARY_VERSION).encode()).hexdigest()[:16]
    if not body.get("force"):
        row = conn.execute(
            "SELECT * FROM metric_commentary WHERE org_id=? AND question_id=? AND cut_key=? AND payload_hash=?",
            (org["org_id"], "__strategy__", "strategy", phash)).fetchone()
        if row:
            return {"parts": uj(row["text"], {}), "source": row["source"], "cached": True,
                    "generated_at": row["created_at"]}
    if body.get("peek"):
        return {"parts": None, "source": None, "cached": False}
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_strategy_commentary, payload)
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], "__strategy__", "strategy", phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False}


# ================================================================ BOARD PACK ==

def assemble_pack_payload(request, user, org, cut):
    conn = get_conn()
    items, tb = build_items(request, org, user, cut)
    # headline scoped to the Substance pool (Provision presence included) so the
    # board pack agrees with the dashboard gauge — same definition, same numbers
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                             payloads(), org_answers_for(org),
                                             make_entitled(user, org), tb)
    summary = pos.overview_summary(items, mp_config=pos.market_position_config(),
                                   practice_items=prac_items,
                                   band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH)
    # PACK-LAYER selection integrity (2026-07-02): the pack must agree with the app's
    # market-position rulings, so (1) CONTEXT metrics (mp_config direction=neutral —
    # e.g. workforce cost) are never verdicted in the app and cannot appear as board
    # "strengths"/"gaps"; (2) one matrix question must not consume the whole table —
    # keep the best/worst ROW per question, fill from the next distinct question.
    # top_strengths/top_gaps themselves are untouched (other callers keep raw order);
    # we over-fetch and filter here, at the pack layer only.
    _mp_cfg = pos.market_position_config()
    _mp_metrics = _mp_cfg.get("metrics", {})
    # the same QA-hardened verdict the dashboard gauge shows — THE competitiveness
    # feed (substance_pool) through _pool_verdict, word/needle agreeing by
    # construction. NOT in overview_summary (that returns counts only).
    _gauge_pool = pos.substance_pool(items, prac_items, _mp_cfg)
    _market = pos._pool_verdict(_gauge_pool, MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN) or {}
    def _pack_rows(ranked, k=5):
        out, seen = [], set()
        for i in ranked:
            if (_mp_metrics.get(i["question_id"]) or {}).get("direction") == "neutral":
                continue                    # context, not a verdict — the engine's own ruling
            if i["question_id"] in seen:
                continue                    # one row per matrix question family
            seen.add(i["question_id"])
            out.append(i)
            if len(out) == k:
                break
        return out
    strengths = _pack_rows(pos.top_strengths(items, 12))
    gaps = _pack_rows(pos.top_gaps(items, 12))
    money = pos.money_opportunities(conn, org, visible_questions(), payloads(),
                                    org_answers_for(org), cut, tb)
    reg = build_gap_register(request, user, org, cut)
    # Tier 2 (2026-07-02): the pack carries the app's richest insight surfaces.
    # Signals = the SAME balanced top-5 briefing the home page shows, in the ABSOLUTE
    # view (no per-user triage, no strategy lens — a board pack is org-level evidence).
    _visq = org_visible_questions(org)
    _answers = org_answers_for(org)
    _get_block = lambda qid: pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0] if payloads().get(qid) else None
    _pack_sigs = signals_mod.build_signals(items, money, _visq, _get_block, _answers,
                                           conn=conn, org_id=org["org_id"])
    _strat = strategy_for_engine(conn, org["org_id"])
    _strat_done = bool(conn.execute(
        "SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
        (org["org_id"],)).fetchone())
    _snap_count = conn.execute("SELECT count(*) FROM snapshots").fetchone()[0]
    # STRATEGY ALIGNMENT page (2026-07-03, David's ruling): the declared strategy plus
    # the engine's own per-domain read against it — computed via the SAME hero path the
    # dashboard uses (hero_signals with strategy applied), stances translated to member
    # words (lag/match/lead never renders — the standing vocabulary rule).
    # hero hoisted OUT of the strategy gate (pack-methodology incorporation, David 2026-07-12):
    # every pack now carries per-domain depth_pctl + the practice prevalence read, strategy or
    # not (hero_signals degrades with strategy=None). The strategy-alignment page stays gated.
    _prev_items = pos.prevalence_items(org["org_id"], cut, _visq, payloads(),
                                       _answers, make_entitled(user, org), tb)
    _sec_order = []
    for _q in _visq.values():
        if _q.sub_power and _q.sub_power not in _sec_order:
            _sec_order.append(_q.sub_power)
    _sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in _visq.values() if q.sub_power == x))
    _hero_s = pos.hero_signals(items, _prev_items, _sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                               DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                               practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                               mp_config=_mp_cfg, strategy=_strat if (_strat and _strat_done) else None)
    # per-domain typical-metric depth + basis, for the pack's Position-by-area table (the
    # dashboard's Position view read); keyed by domain name to merge onto by_section.
    _dom_depth = {d["name"]: {"depth_pctl": (d.get("position") or {}).get("depth_pctl"),
                              "basis": d.get("position_basis")}
                  for d in _hero_s.get("domains", []) if d.get("position")}
    # the org-level practice prevalence read (common/alternative/rare) — replaces the retired
    # maturity 0-100 language in the pack (the app removed maturity scores 2026-06-11).
    _prev_sum = _hero_s.get("prevalence") or {}
    _practice_prev = ({"common": _prev_sum.get("with_majority"), "alternative": _prev_sum.get("established"),
                       "rare": _prev_sum.get("less_common"), "pool": _prev_sum.get("pool")}
                      if _prev_sum.get("pool") else None)
    _strat_align = None
    if _strat and _strat_done:
        _stance_word = {"lag": "below market", "match": "on market", "lead": "above market"}
        _overall_t = (_hero_s.get("market") or {}).get("target")
        _dom_rows = []
        for _d in _hero_s.get("domains", []):
            _t = _d.get("target")
            if not _t:
                continue
            _pos_v = (_d.get("position") or {}).get("verdict")
            _dom_rows.append({"name": _d["name"],
                              "aim": _stance_word.get(_t.get("stance")),
                              "aim_is_override": _d["name"] in (_strat.get("domain_targets") or {}),
                              "position": _pos_v,
                              "alignment": _t.get("alignment")})
        _strat_align = {
            "objective": OBJECTIVE_LABELS.get(_strat.get("primary_objective")) if (
                (_strat.get("provenance") or {}).get("primary_objective") != "skipped") else None,
            "overall_aim": _stance_word.get(_strat.get("market_position")),
            "overall_alignment": _overall_t.get("alignment") if _overall_t else None,
            "domains": _dom_rows,
        }
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
    # ---- Reward Strategy Review (2026-08-14, Artefact B) — SAME payload path, no
    # parallel assembly. Present only with a completed strategy; every string is
    # deterministic (strategy_align — DIRECTIVE_RE-clean by construction); the AI
    # narrative contract is untouched (it may read these figures, never invent them).
    _strat_review = None
    if _strat and _strat_done:
        _st_state = strategy_state(conn, org)
        _own = {k[0]: v for k, v in (org_answers_for(org) or {}).items()
                if (k[1] or "") == "" and isinstance(v, str)}
        _al = strategy_align.evaluate(
            strategy_align.load_rules(), _strat, _st_state.get("document") or {}, _own,
            _hero_s.get("domains") or [], STRATEGY_POSITION_EXCLUDE,
            visible_qids=set(_visq), cut_label=cut_label)
        _ver = conn.execute("SELECT version, approved_at, approved_by, approver_body, approval_date, "
                            "effective_date, next_review FROM strategy_versions "
                            "WHERE org_id=? AND status='approved' ORDER BY version DESC LIMIT 1",
                            (org["org_id"],)).fetchone()
        _strat_review = {
            "version": dict(_ver) if _ver else None,       # Artefact B always cites a version (or says draft)
            "principles": (_st_state.get("document") or {}).get("principles") or [],
            "population_targets": (_st_state.get("document") or {}).get("population_targets") or [],
            "comparator_label": (_st_state.get("document") or {}).get("comparator_label"),
            "alignment_counts": _al["counts"],
            "commitments": _al["commitments"],
            "options": strategy_align.options_for(_al["commitments"], visible_qids=set(_visq)),
            "action_plan": (_st_state.get("document") or {}).get("action_plan"),
        }
    return {
        "cut_n": cut_n,
        "cut": {"dim": cut["dim"], "value": cut.get("value")},   # for one-click regenerate
        "cut_criteria": cut.get("criteria"),                     # saved-group construction, printed on the methodology page
        "band": {"low": MARKET_BAND_LOW, "high": MARKET_BAND_HIGH},   # the on-market band (scale zones + callout)
        # v2 = multi-select prevalence on (core-coverage read admits ~16 more practices to
        # the pool; decision paper 2026-07-13) — a visible, dated methodology change, so
        # stored v1 packs stay honestly labelled with the maths they were built under.
        "methodology_version": 2 if pos.MS_PREVALENCE else 1,
        "organisation": {"name": (identity.org_display(org["org_id"]) or {}).get("name"),
                         "industry": org["industry"],
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
            # the QA-hardened verdict the dashboard gauge shows (word + needle agree
            # by construction) — the pack's headline must not diverge from it
            "market": {"verdict": _market.get("verdict"),
                       "lean": _market.get("lean"),
                       "depth_pctl": _market.get("depth_pctl")},
        },
        "strengths": [_pack_item(i) for i in strengths],
        "gaps": [_pack_item(i) for i in gaps],
        "opportunities": [{"label": i["label"], "direction": i["direction"],
                           "to_p50_gbp": i["to_p50_gbp"], "to_p75_gbp": i["to_p75_gbp"],
                           "formula": i["formula"], "cut_label": i["cut_label"]}
                          for i in money["items"]],
        "opportunity_totals": {"savings_to_p50_gbp": money.get("total_savings_to_p50_gbp"),
                               "investment_to_p50_gbp": money.get("total_investment_to_p50_gbp"),
                               "fte_known": money.get("fte_known")},
        "opportunity_assumptions": {k: v for k, v in money["assumptions"].items()
                                    if k in ("median_salary_gbp", "cost_per_leaver_pct_salary",
                                             "agency_premium_pct", "fte_band_midpoints")},
        "gap_register_top": [
            {"name": r["name"], "superpower": r["superpower"], "your_status": r["org_status"],
             "peer_adoption_pct": r["peer_adoption_pct"], "n": r["n"], "n_real": r.get("n_real", 0)}
            for r in reg["rows"] if not r["suppressed"] and r["gap"] is not None and r["gap"] > 0
        ][:10],
        "maturity": reg["maturity"],   # legacy field kept for STORED-pack renders; new packs read practice_prevalence
        # the dashboard's practice read (common/alternative/rare, prevalence — never a 0-100
        # score, which the app retired 2026-06-11); pack-methodology incorporation 2026-07-12
        "practice_prevalence": _practice_prev,
        # the single-bucket practice read (Diff 4) — the SAME helper the dashboard card
        # uses, over the SAME _prev_items; render treats it as optional (stored packs)
        "practice_bucket": pos.practice_bucket(_visq, pos.market_position_config(),
                                               _prev_items, org_answers_for(org), UNCOMMON_PCT),
        # Tier 2 sections — every consumer (render + narrative) treats these as optional.
        # depth_pctl/basis merged per domain (the Position view's typical-metric read).
        "by_section": {k: {"available": v["available"], "above": v["above"],
                           "below": v["below"], "inline": v["inline"],
                           "depth_pctl": _dom_depth.get(k, {}).get("depth_pctl"),
                           "basis": _dom_depth.get(k, {}).get("basis")}
                       for k, v in (summary.get("by_section") or {}).items()},
        # CONTEXT signals excluded (2026-07-09 ship review, Pack 3.2): context-bucket
        # metrics (mp_config direction=neutral — e.g. workforce cost per FTE) are
        # facts the engine deliberately refuses to verdict, so they must not ship in
        # the pack's "What to watch" indistinguishable from genuine gaps (the live
        # repro read as a £16.5k underpayment). Mirrors _pack_rows' context filter
        # above — the pack layer only; the in-app signals surface keeps them with
        # its own context labelling.
        "signals": [{"name": s.get("name") or s.get("label_short"), "domain": s.get("domain"),
                     "stand": s.get("stand"), "tag": s.get("tag"),
                     "risk": bool(s.get("risk_framed")), "bucket": s.get("bucket")}
                    for s in [x for x in _pack_sigs if x.get("bucket") != "context"][:5]],
        "strategy": {"complete": _strat_done,
                     "objective": OBJECTIVE_LABELS.get(_strat.get("primary_objective")) if (
                         _strat and (_strat.get("provenance") or {}).get("primary_objective") != "skipped") else None},
        "movement": ("First benchmark period — movement appears from your next data cycle."
                     if _snap_count <= 1 else None),
        "strategy_alignment": _strat_align,
        "strategy_review": _strat_review,
        # the ruled one-line provenance footer (R-P2 amendment 2026-08-08) — the pack
        # was the one durable artefact the implementing commit missed
        "pool_footer": "Comparison pool: %d UK organisation profiles. See lumihr.co.uk methodology for sources."
                       % (pool.get("responding_orgs") or 0),
    }


def _pack_item(i):
    # percentiles rounded here so the narrative can only cite figures that
    # appear verbatim in its input payload. polarity/favourable ship so the
    # RENDER and the narrative colour by direction (a low pay gap is favourable;
    # the pre-fix render coloured by table membership alone).
    # graduated display (Sprint 2): the stored payload IS the graduated truth, so the
    # narrative's number-grounding can never cite a masked statistic either
    n = i["n"]
    q_ok = n >= PACK_QUARTILE_MIN_N
    t_ok = n >= PACK_TAIL_MIN_N
    return {"label": i["label"], "value_display": i["value_display"],
            "percentile": int(round(i["percentile"])), "n": n, "n_real": i.get("n_real", 0), "cut_label": i["cut_label"],
            "p50_display": i["p50_display"], "superpower": i["superpower"],
            "polarity": i.get("polarity"), "favourable": i.get("favourable"),
            "p25_display": i.get("p25_display") if q_ok else None,
            "p75_display": i.get("p75_display") if q_ok else None,
            "p10_display": i.get("p10_display") if t_ok else None,
            "p90_display": i.get("p90_display") if t_ok else None}


@app.post("/api/boardpack/generate")
async def boardpack_generate(request: Request):
    user, org = require_user(request)
    # Deep-QA ruling 2026-07-13: generation is editor+ (it writes an org artefact and can
    # spend an AI call); READING packs stays any-user — a Viewer's whole job is consuming them.
    # Not require_editor(): its message talks about submitting data, wrong for this refusal.
    if user["role"] not in ("admin", "contributor"):
        raise HTTPException(403, "Generating a board pack is for Admins and Contributors — "
                                 "Viewers can open any pack the team has already produced.")
    # §4.3 medium (surfaced by David 2026-07-11, "the board pack has disappeared"): the pack has a
    # complete deterministic narrative floor, so GENERATION must not hide behind the AI gate — a
    # keyless/AI-off/unconsented member still gets the full pack, honestly labelled "composed
    # directly from the figures". Only the CLAUDE CALL is AI; the gate now scopes to it alone.
    _ai_ok = ai_feature_on(ai_gate(get_conn(), user), AI_BOARDPACK)
    contrib = contribution_state(get_conn(), org)
    if not contrib["insights_unlocked"]:
        raise HTTPException(403, "Your board pack unlocks once you've answered %d%% of your key reward questions." % int(TARGET_PCT))
    body = await _json(request)
    cut = {"dim": body.get("cut", "all"), "value": body.get("cut_value")}
    if cut["dim"] not in ("all", "industry", "fte_band", "twin", "group"):
        cut["dim"] = "all"
    if cut["dim"] == "group":
        # mirror parse_cut (:555-563): resolve the saved group's label + criteria; a
        # stale or foreign group id falls back to all-peers rather than shipping a
        # null label and empty criteria into a board document (the pre-fix bug).
        row = get_conn().execute(
            "SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
            (cut["value"] or "", org["org_id"])).fetchone()
        if row is None:
            cut = {"dim": "all", "value": None}
        else:
            cut["label"] = row["name"]
            cut["criteria"] = uj(row["criteria_json"], {})
    if cut["dim"] == "industry" and not cut["value"]:
        cut["value"] = org["industry"]
    if cut["dim"] == "fte_band" and not cut["value"]:
        cut["value"] = org["fte_band"]
    # cap only the paid AI call — the deterministic pack floor is always available
    if _ai_ok and _boardpack_rate_limited(org["org_id"]):
        raise HTTPException(429, "You've generated a lot of board packs today — please try again "
                                 "tomorrow. Packs you've already produced are still available.")
    if _ai_ok:
        _ai_generation_or_429(org)
    payload = assemble_pack_payload(request, user, org, cut)
    result = (await to_thread.run_sync(claude_api.generate_board_pack_narrative, payload)) if _ai_ok \
        else {"ok": False, "error": "AI narrative not enabled for this member",
              "narrative": claude_api._deterministic_pack(payload)}
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
    # staleness signal: the CURRENT collection window, so the client can flag a pack
    # generated from an older snapshot. previous: the prior pack's headline, for the
    # "since your last pack" line. Both additive — old clients ignore them.
    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (CURRENT_SNAPSHOT,)).fetchone()
    prev = conn.execute(
        "SELECT payload_json, created_at FROM board_packs WHERE org_id=? AND created_at < ? "
        "ORDER BY created_at DESC LIMIT 1", (org["org_id"], row["created_at"])).fetchone()
    prev_summary = None
    if prev:
        _pp = uj(prev["payload_json"], {})
        _ph = _pp.get("headline") or {}
        prev_summary = {"generated_date": _pp.get("generated_date"), "created_at": prev["created_at"],
                        "comparable_metrics": _ph.get("comparable_metrics"),
                        "above_median": _ph.get("above_median"), "below_median": _ph.get("below_median"),
                        "broadly_in_line": _ph.get("broadly_in_line"),
                        "verdict": (_ph.get("market") or {}).get("verdict")}
    payload = uj(row["payload_json"])
    # LIVE-DRIFT check (2026-07-09 ship review, Pack 3.1): the window-only stale
    # check misses drift WITHIN a collection window — a stored pack can say
    # "behind aim"/1-of-91 while the live dashboard says "on aim"/3-of-93, with no
    # banner. Recompute the headline through the SAME engine path generation used,
    # under the pack's own stored cut, and ship it additively so the client can
    # banner the divergence (old clients ignore the field). Best-effort: a failure
    # here must never block serving the stored pack.
    live_headline = None
    try:
        _cut = dict(payload.get("cut") or {"dim": "all"})
        if payload.get("cut_criteria"):
            _cut["criteria"] = payload["cut_criteria"]
        _tb = twin_blocks_if_needed(conn, org, _cut) if _cut.get("dim") in ("twin", "group") else None
        _qs = org_visible_questions(org)
        _ent = make_entitled(user, org)
        _ans = org_answers_for(org)
        _items = pos.position_items(org["org_id"], _cut, _qs, payloads(), _ans, _ent, _tb)
        _prac = pos.practice_position_items(org["org_id"], _cut, _qs, payloads(), _ans, _ent, _tb)
        _mp_cfg = pos.market_position_config()
        _s = pos.overview_summary(_items, mp_config=_mp_cfg, practice_items=_prac,
                                  band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH)
        _mkt = pos._pool_verdict(pos.substance_pool(_items, _prac, _mp_cfg),
                                 MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN) or {}
        _ph = payload.get("headline") or {}
        live_headline = {
            "comparable_metrics": _s["comparable_metrics"], "above_median": _s["above_median"],
            "below_median": _s["below_median"], "broadly_in_line": _s["broadly_in_line"],
            "verdict": _mkt.get("verdict"),
            "drifted": bool(_ph) and (
                _s["comparable_metrics"] != _ph.get("comparable_metrics")
                or _s["above_median"] != _ph.get("above_median")
                or _s["below_median"] != _ph.get("below_median")
                or _s["broadly_in_line"] != _ph.get("broadly_in_line")
                or _mkt.get("verdict") != (_ph.get("market") or {}).get("verdict")),
        }
    except Exception:
        live_headline = None
    return {"pack_id": pack_id, "payload": payload,
            "narrative": uj(row["narrative_json"]), "created_at": row["created_at"],
            "current_collection_window": snap["collection_window"] if snap else None,
            "previous": prev_summary,
            "live_headline": live_headline}


@app.get("/api/boardpacks")
async def boardpacks_list(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT b.pack_id, b.created_at, b.payload_json, b.narrative_json, b.created_by "
        "FROM board_packs b WHERE b.org_id=? ORDER BY b.created_at DESC LIMIT 50",
        (org["org_id"],)).fetchall()
    creators = identity.user_display_batch([r["created_by"] for r in rows])
    packs = []
    for r in rows:
        p = uj(r["payload_json"], {})
        n = uj(r["narrative_json"], {})
        packs.append({"pack_id": r["pack_id"], "created_at": r["created_at"],
                      "cut_label": p.get("cut_label"), "collection_window": p.get("collection_window"),
                      "ai": not n.get("_fallback"),
                      "created_by": (creators.get(r["created_by"]) or {}).get("display_name")})
    return {"packs": packs}


@app.delete("/api/boardpack/{pack_id}")
async def boardpack_delete(pack_id: str, request: Request):
    """Admin-only, org-scoped. Deleting a pack also strands any share links minted
    for it (they 404 on open) — the confirm dialog says so."""
    user, org = require_admin(request)
    conn = get_conn()
    r = conn.execute("DELETE FROM board_packs WHERE pack_id=? AND org_id=?",
                     (pack_id, org["org_id"]))
    conn.commit()
    if r.rowcount == 0:
        raise HTTPException(404, "Board pack not found")
    return {"ok": True}


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


def completion_counts(conn, org):
    """(answered, total) over the BASIS (key-question) set. N/A and Don't-know
    selections are stored values, so they count as answered — only skipped
    questions don't. Single source for both the % and the exact 'N key
    questions left to unlock' effort copy the funnel leans on."""
    basis = completion_basis_questions()
    if not basis:
        return 0, 0
    answered = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=?",
        (org["org_id"], CURRENT_SNAPSHOT))}
    drafted = {r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
        (org["org_id"],))}
    have = answered | drafted
    return sum(1 for q in basis if q.id in have), len(basis)


def completion_pct(conn, org):
    """% of the BASIS set answered."""
    a, t = completion_counts(conn, org)
    return 100.0 if not t else round(100.0 * a / t, 1)


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
    body = await _json(request)
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
    user, org = require_editor(request)   # peer groups are org-shared config — editors only
    body = await _json(request)
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
    user, org = require_editor(request)   # org-shared config — editors only
    conn = get_conn()
    row = conn.execute("SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
                       (gid, org["org_id"])).fetchone()
    if row is None:
        raise HTTPException(404, "No such peer group.")
    body = await _json(request)
    name = (body.get("name") or row["name"]).strip()[:60] or row["name"]
    criteria = validate_group_criteria(body["criteria"]) if body.get("criteria") else uj(row["criteria_json"], {})
    conn.execute("UPDATE peer_groups SET name=?, criteria_json=?, updated_at=datetime('now') WHERE group_id=?",
                 (name, j(criteria), gid))
    conn.commit()
    return group_row_out(conn, conn.execute("SELECT * FROM peer_groups WHERE group_id=?", (gid,)).fetchone())


@app.delete("/api/peer-groups/{gid}")
async def peer_groups_delete(gid: str, request: Request):
    user, org = require_editor(request)   # org-shared config — editors only
    conn = get_conn()
    # R2 delete guard (2026-08-14): a group that is the reward strategy's declared
    # comparator can't be silently deleted out from under the strategy — the strategy
    # would dangle and its review would lose its peer frame. Change the strategy first.
    if conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND comparator_cut=?",
                    (org["org_id"], "group::" + gid)).fetchone():
        raise HTTPException(409, "This peer group is your reward strategy's comparator — "
                                 "change the strategy's comparator before deleting it.")
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


def _classified_from(row):
    """THE rule for orgs.classified (PH-PROV-1 ruling §2): 1 iff every PROFILE_CORE
    field is populated. The two profile writers and the provisioning route all
    derive through here — derive, never hardcode."""
    return 1 if all(row.get(f) for f in PROFILE_CORE) else 0


def _insert_member_org(conn, org_id, firmographics=None):
    """THE org-creating INSERT for a real member organisation — self-serve register
    (when open) and staff provisioning both call this one helper so the column set
    cannot drift between paths (PH-PROV-1 §2.1/§3). Reward store only; the six
    identity columns are never written — orgs.name / orgs.normalized_name stay
    empty (identity's org_register carries them; the step-5 split). source='signup'
    is the ruled value: legacy name, means "real member organisation". No commit —
    the caller owns the transaction (provisioning pairs this with the first admin
    invite atomically)."""
    firmo = {f: firmographics[f] for f in PROFILE_CORE if firmographics and firmographics.get(f)}
    cols = {"org_id": org_id, "source": "signup", "tier_entitlement": "full",
            "classified": _classified_from(firmo)}
    cols.update(firmo)
    conn.execute("INSERT INTO orgs(%s) VALUES (%s)" % (
        ",".join(cols), ",".join("?" * len(cols))), list(cols.values()))


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
    body = await _json(request)
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
    classified = _classified_from(row)
    conn.execute("UPDATE orgs SET classified=? WHERE org_id=?", (classified, org["org_id"]))
    if classified:
        _encode_signup_vector(conn, row)
    conn.commit()
    invalidate_payloads()
    return {"ok": True, "core_complete": bool(classified),
            "rich_complete": all(row.get(f) for f in PROFILE_RICH)}


# ===================== Reward strategy capture (2026-06-16) =====================
# Org-level reward stance — Plane B (philosophy) + Plane C (posture) dials. Plane A
# (your business) is read from the existing registry record, not duplicated here.
# Three required dials flip a signal's direction; the rest default neutral. See
# DECISIONS.md "Reward strategy capture".
STRATEGY_ENUMS = {
    "market_position":     ["lag", "match", "lead"],
    "reward_mix":          ["cash", "balanced", "benefits"],
    "pay_for_performance": ["egal", "moderate", "strong"],
    "transparency":        ["closed", "ranges", "open"],
    "location_approach":   ["local", "national", "agnostic"],
    "family_position":     ["statutory", "market", "over"],
    "primary_objective":   ["attract", "retain", "cost", "compliance", "hold"],
    "budget_direction":    ["investing", "flat", "pressure"],
    "acute_pressure":      ["bau", "scaling", "shock"],
    "risk_appetite":       ["early", "follow", "wait"],
}
STRATEGY_BENEFITS = ["physical", "mental", "financial", "worklife"]   # multi-select
STRATEGY_REQUIRED = ("market_position", "reward_mix", "primary_objective")
OBJECTIVE_LABELS = {"attract": "Attract", "retain": "Retain", "cost": "Control cost",
                    "compliance": "Get it right", "hold": "Hold steady"}
STRATEGY_PLANE_A_KEYS = {"lifecycle": "Business_Maturity", "talent": "Talent_Competition",
                         "workforce": "Workforce_Shape", "footprint": "International_Footprint"}

# ---- Total Reward Strategy document capture (2026-08-14, brief v2 + Phase-0 rulings R1-R13) ----
# R3b (David 2026-08-14): position commitments are capturable in the SIX substance-dense
# categories only. Wellbeing carries a PROVISION commitment ("what we will offer");
# Governance & Transparency a PRACTICE commitment ("how we operate"). This is a PRODUCT
# ruling, not an engine constraint — post-Diff-2 the engine can verdict all eight; the
# document stays honest by register. A ruled pin, not a derivable list.
STRATEGY_POSITION_EXCLUDE = ("Wellbeing", "Governance & Transparency")
STRATEGY_CONSTRAINTS = ["affordability", "collective_bargaining", "statutory_pressure",
                        "headcount_change", "system_change", "other"]
STRATEGY_CADENCES = ["annual", "twice_yearly", "quarterly", "ad_hoc"]
STRATEGY_HORIZONS = ["this_cycle", "next_cycle", "multi_cycle"]
# capture is RESUMABLE (2026-06-16 deviation stands): caps are hard 400s, minimums are
# document-honesty concerns (the artefact renders "not yet stated"), never save blocks.
STRATEGY_MAX_PRINCIPLES, STRATEGY_PRINCIPLE_CHARS = 6, 140
STRATEGY_MAX_SEGMENTS, STRATEGY_SEGMENT_CHARS = 6, 60
STRATEGY_MAX_MEASURES = 8            # R4: 5-8; the >=5 half is advisory (resumability)
STRATEGY_MAX_ROADMAP, STRATEGY_ROADMAP_CHARS = 6, 120
STRATEGY_GOV_CHARS = 80
STRATEGY_STATEMENT_CHARS = 240
# population positions (2026-08-15, reward-director review): exec vs all-employee is
# the primary axis of a listed company's reward strategy — but lumi holds NO executive
# pay data, so these are DOCUMENT statements only and are never fed to the engine.
# the SEVEN matrix row labels, verbatim (18 matrix questions share them) — a position
# set here can be read directly against any by-level matrix metric.
STRATEGY_POPULATIONS = ["Board / Executive", "Director", "Head of", "Senior Manager",
                        "Manager", "Supervisor / Team Leader", "Frontline / Individual Contributor"]
STRATEGY_MAX_POPULATIONS = 7
# primary objective is now a RATED allocation with a hard budget, so a member must
# trade off rather than tick everything. The engine still reads one primary_objective:
# it is derived server-side as the highest-rated (ties -> the existing stored value).
STRATEGY_OBJECTIVE_BUDGET = 10
STRATEGY_MEASURE_TEXT = 80


def _validate_comparator(conn, org, raw):
    """R2: the strategy binds to a declared comparator using the SAME cut grammar as
    orgs.default_cut ('all'/None | industry::X | fte_band::Y | group::<gid>), so
    _org_sweep_cut-style resolution is reused verbatim. 400 on anything unresolvable —
    a strategy must never point at a comparator that can't be evidenced."""
    if raw in (None, "", "all"):
        return None                                   # None = the org default / All peers
    if not isinstance(raw, str) or "::" not in raw:
        raise HTTPException(400, "comparator must be 'all', 'industry::X', 'fte_band::Y' or 'group::<id>'.")
    dim, val = raw.split("::", 1)
    if dim in ("industry", "fte_band"):
        choices = profile_choices().get(dim) or []
        if val not in choices:
            raise HTTPException(400, "'%s' isn't a recognised %s." % (val, dim.replace("_", " ")))
        return raw
    if dim == "group":
        if not conn.execute("SELECT 1 FROM peer_groups WHERE group_id=? AND org_id=?",
                            (val, org["org_id"])).fetchone():
            raise HTTPException(400, "That saved peer group no longer exists.")
        return raw
    raise HTTPException(400, "'%s' isn't a comparator dimension." % dim)


def _comparator_label(conn, org, raw):
    """Human words for the comparator. Deliberately the SAME helper the benchmark,
    Signals and Settings name the peer group with — the strategy must never describe
    a different market from the one the numbers come from."""
    if not raw:
        return "All peers"
    _raw, label, _crit = _default_cut_info(conn, dict(org, default_cut=raw))
    return label


def strategy_measure_options(conn, org, comparator_cut):
    """R4/§10 eligibility, computed live for the measures picker AND re-checked at PUT:
    a measure must be visible to the org and carry a usable read. n/suppression under the
    declared comparator is REPORTED here (the UI greys sub-floor picks) but enforced at
    REPORT time, not capture time — eligibility is cut-dependent and the report is the
    honest place (a metric can clear the floor in one cut and not the next). Group
    comparators fall back to the all-peers read for the advisory n (group blocks are
    request-time machinery; the report resolves them properly)."""
    mpc = pos.market_position_config()
    metrics = mpc.get("metrics") or {}
    cut = {"dim": "all", "value": None}
    if comparator_cut and comparator_cut.split("::", 1)[0] in ("industry", "fte_band"):
        d, v = comparator_cut.split("::", 1)
        cut = {"dim": d, "value": v}
    out = []
    pl = payloads()
    for qid, q in org_visible_questions(org).items():
        p = pl.get(qid)
        if p is None:
            continue
        m = metrics.get(qid) or {}
        blk, _lbl = pos.block_for(p, cut)
        n = (blk or {}).get("n", 0)
        out.append({
            "id": qid, "title": q.display_title, "category": q.sub_power,
            "direction": m.get("direction"), "cls": m.get("class"),
            "context": m.get("direction") == "neutral",     # tracked as a LEVEL, never progress (§10.3)
            "n": n, "suppressed": bool(pos.is_suppressed(blk)),
        })
    out.sort(key=lambda o: (o["category"], o["title"]))
    return out


def _workforce_shape(reg):
    """Derived, not stored (spec §4): Workforce_Frontline_% banded <33 / 33-66 / >66."""
    try:
        f = float(reg.get("Workforce_Frontline_%"))
    except (TypeError, ValueError):
        return None
    return "Salaried" if f < 33 else ("Frontline / shift" if f > 66 else "Mixed")


def _strategy_plane_a(org):
    """The 4 Plane-A confirm facts, read from the registry record (read-only
    pre-fill; an Admin override persists back into registry_json on PUT)."""
    reg = uj(org.get("registry_json"), {}) or {}
    cv = (get_meta("sim_feature_space") or {}).get("cat_values", {})
    shape_override = reg.get("Workforce_Shape")
    return [
        {"key": "lifecycle", "label": "Lifecycle stage", "value": reg.get("Business_Maturity"),
         "options": cv.get("Business_Maturity") or [],
         "why": "Sets your default posture — a scale-up leads on equity; a mature firm on retention."},
        {"key": "talent", "label": "Talent model", "value": reg.get("Talent_Competition"),
         "options": cv.get("Talent_Competition") or ["Low", "Medium", "High"],
         "why": "Scarce, business-critical skills justify paying a premium — we read high pay as strategy, not overspend."},
        {"key": "workforce", "label": "Workforce shape", "value": shape_override or _workforce_shape(reg),
         "options": ["Salaried", "Mixed", "Frontline / shift"], "derived": not shape_override,
         "why": "Decides which questions apply to you — frontline and shift workforces route differently."},
        {"key": "footprint", "label": "Geographic footprint", "value": reg.get("International_Footprint"),
         "options": cv.get("International_Footprint") or ["UK Only", "UK + Europe", "UK + Global"],
         "why": "Decides whether local-market pay reads matter, or a single national view is the right one."},
    ]


def _canon_domain_targets(dt, mpc=None):
    """Heal legacy short domain keys ('Time Off', pre-canonicalisation rows) to the
    canonical sub_power names ('Time Off & Family') the engine and the validator both
    speak. Exact keys pass through; a UNIQUE prefix match rewrites; anything else is
    left for validation to reject. Root cause 2026-08-08 deep QA: a stored short key
    made every strategy save 400 AND the engine silently ignored the member's aim."""
    if not dt:
        return dt or {}
    mpc = mpc or pos.market_position_config()
    doms = list(mpc.get("_domains", {}))
    out = {}
    for k, v in dt.items():
        if k in doms:
            out[k] = v
            continue
        hits = [d for d in doms if d.startswith(k)]
        out[hits[0] if len(hits) == 1 else k] = v
    return out


def strategy_state(conn, org):
    """The org's stored B/C strategy + provenance + Plane-A facts, shaped for the API."""
    r = conn.execute("SELECT * FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    row = dict(r) if r else {}
    strat = {f: row.get(f) for f in STRATEGY_ENUMS}
    strat["benefits_lead"] = uj(row.get("benefits_lead"), []) or []
    # legacy keys healed on read; keys no canonicalisation can place are DROPPED here
    # (they are inert in the engine and would 400 every save — unusable garbage config)
    _dt = _canon_domain_targets(uj(row.get("domain_targets"), {}) or {})
    _known = set(pos.market_position_config().get("_domains", {}))
    strat["domain_targets"] = {k: v for k, v in _dt.items() if k in _known}
    strat["objective_weights"] = uj(row.get("objective_weights"), {}) or {}
    # competitive domains for the per-domain override UI (step-3 layer 2) — derived from the
    # SAME config source the save-route validation uses (_domains where competitive), so the
    # UI list and the validation can't drift. Governance (competitiveness=False) falls out.
    _mpc = pos.market_position_config()
    comp_domains = [d for d in (_mpc.get("_domains") or {}) if pos._mp_competitive(_mpc, d)]
    # Total Reward Strategy document fields (2026-08-14). Parsed here so the client
    # never touches raw JSON columns; absent = "not yet stated", never fabricated.
    doc = {
        "comparator_cut": row.get("comparator_cut"),
        "principles": uj(row.get("principles_json"), []) or [],
        "constraints": uj(row.get("constraints_json"), {}) or {},

        "population_targets": uj(row.get("population_targets_json"), []) or [],
        "roadmap": uj(row.get("roadmap_json"), []) or [],
        "action_plan": uj(row.get("action_plan_json"), None),
        # author edits to the GENERATED PROSE only — see PUT /api/strategy/narrative
        "narrative_overrides": uj(row.get("narrative_overrides_json"), {}) or {},
    }
    # ONE peer group (2026-08-15, David: "compare against contradicts the default
    # benchmark sample group — the two need to be aligned"). orgs.default_cut is the
    # single source of truth: it already anchors the benchmark, Signals and alerts,
    # so the strategy states THAT market, never a second one.
    doc["comparator_cut"] = (org.get("default_cut") or None)
    doc["comparator_label"] = _comparator_label(conn, org, doc["comparator_cut"])
    doc["comparator_is_default"] = True
    # Artefact A versioning (2026-08-14): the live row is the working draft; the
    # latest approved snapshot names the version the review cites. dirty = edits
    # since approval (the view says so honestly rather than pretending currency).
    ver = conn.execute("SELECT * FROM strategy_versions WHERE org_id=? AND status='approved' "
                       "ORDER BY version DESC LIMIT 1", (org["org_id"],)).fetchone()
    version = (dict(dict(ver), **{"dirty": bool(row.get("updated_at") and row["updated_at"] > ver["approved_at"]),
                                  "unstated": uj(ver["unstated_json"], []) or []})
               if ver else None)
    if version:
        version.pop("snapshot_json", None)
    # R3b: the position-dial category list = competitive MINUS the ruled exclusion;
    # Wellbeing/Governance carry provision/practice commitments instead.
    position_domains = [d for d in comp_domains if d not in STRATEGY_POSITION_EXCLUDE]
    _dr = uj(row.get("draft_json"), None)
    draft = ({"saved_at": row.get("draft_saved_at"), "by": row.get("draft_by"),
              "step": (_dr or {}).get("step")} if _dr else None)
    submitted = ({"at": row.get("submitted_at"), "by": row.get("submitted_by")}
                 if row.get("submitted_at") else None)
    return {
        "strategy": strat,
        "provenance": uj(row.get("field_provenance"), {}) or {},
        "completed_at": row.get("completed_at"),
        "draft": draft,
        "submitted": submitted,
        "populations": STRATEGY_POPULATIONS,
        "plane_a": _strategy_plane_a(org),
        "required": list(STRATEGY_REQUIRED),
        "benefits_options": STRATEGY_BENEFITS,
        "competitive_domains": comp_domains,
        "document": doc,
        "version": version,
        "position_domains": position_domains,
        "commitment_domains": list(STRATEGY_POSITION_EXCLUDE),
        "constraint_options": STRATEGY_CONSTRAINTS,
        "cadence_options": STRATEGY_CADENCES,
        "horizon_options": STRATEGY_HORIZONS,
    }


@app.get("/api/strategy")
async def get_strategy(request: Request):
    user, org = require_user(request)
    out = strategy_state(get_conn(), org)
    out["can_edit"] = user["role"] in ("admin", "contributor")
    out["can_approve"] = user["role"] == "admin"
    return out


@app.get("/api/strategy/suggestions")
async def get_strategy_suggestions(request: Request):
    """Reserved (spec §2.1/§3). v1 emits NO demographic suggestions — there is no
    life-stage signal to derive from, and a manufactured default would make the
    engines confidently wrong. The 'suggested' provenance value stays reserved."""
    require_user(request)
    return {"suggestions": {}}


@app.get("/api/strategy/measure-options")
async def get_strategy_measure_options(request: Request):
    """R4/§10: the eligible-measures list for the capture picker — visible metrics with
    their class/direction and an ADVISORY n/suppression read under the declared
    comparator. Floor enforcement is report-time (the honest place for a cut-dependent
    fact); context (~) metrics are flagged so the UI can say 'tracked as a level'."""
    user, org = require_user(request)
    conn = get_conn()
    r = conn.execute("SELECT comparator_cut FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    comp = r["comparator_cut"] if r else None
    return {"options": strategy_measure_options(conn, org, comp),
            "floor": SUPPRESSION_FLOOR, "max": STRATEGY_MAX_MEASURES, "min_advisory": 5}


def _unstated_sections(st):
    """Which parts of the document are empty right now — recorded on approval so a
    version can never quietly imply more than it contains."""
    d = st.get("document") or {}
    checks = [
        ("Principles", bool([p for p in (d.get("principles") or []) if str(p).strip()])),
        ("Peer group", d.get("comparator_cut") is not None),
        ("Constraints", bool((d.get("constraints") or {}).get("selected") or (d.get("constraints") or {}).get("notes"))),
        ("Position by level", bool(d.get("population_targets"))),
        ("Action plan", bool(d.get("action_plan"))),
    ]
    return [name for name, ok in checks if not ok]


@app.post("/api/strategy/plan")
async def build_action_plan(request: Request):
    """The reward action plan (2026-08-15, David): built AFTER the strategy is stated
    and the data is in. The CANDIDATES are assembled deterministically — every gap the
    alignment engine found, matched to the levers David owns, carrying the indicative £
    the money model already computed. The model only sequences and explains them; it
    can never invent an action or a number (validate_plan enforces both)."""
    user, org = require_editor(request)
    conn = get_conn()
    require_ai(conn, user, AI_STRATEGY)
    strat = strategy_for_engine(conn, org["org_id"])
    if not strat or not conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                                     (org["org_id"],)).fetchone():
        return {"ok": False, "reason": "no_strategy"}
    contrib = contribution_state(conn, org)
    if not contrib["insights_unlocked"]:
        return {"ok": False, "reason": "locked", "days_left": contrib["days_left"]}
    st = strategy_state(conn, org)
    cut = parse_cut(request, org)
    items, tb = build_items(request, org, user, cut)
    _vis = org_visible_questions(org)
    prev_items = pos.prevalence_items(org["org_id"], cut, _vis, payloads(), org_answers_for(org),
                                      make_entitled(user, org), tb)
    prac_items = pos.practice_position_items(org["org_id"], cut, _vis, payloads(), org_answers_for(org),
                                             make_entitled(user, org), tb)
    sec_order = []
    for q in _vis.values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=pos.market_position_config(), strategy=strat)
    own = {k[0]: v for k, v in (org_answers_for(org) or {}).items()
           if (k[1] or "") == "" and isinstance(v, str)}
    cut_label = "All peers" if cut["dim"] == "all" else (cut.get("label") or cut.get("value") or "your peer group")
    al = strategy_align.evaluate(strategy_align.load_rules(), strat, st.get("document") or {}, own,
                                 hero.get("domains") or [], STRATEGY_POSITION_EXCLUDE,
                                 visible_qids=set(_vis), cut_label=cut_label)
    opts = strategy_align.options_for(al["commitments"], visible_qids=set(_vis))
    money = pos.money_opportunities(conn, org, _vis, payloads(), org_answers_for(org), cut, tb)
    # £ by category, so a lever in that area can carry the figure the engine computed
    gbp_by_cat = {}
    for it in money.get("items", []):
        q = _vis.get(it["question_id"])
        if q and q.sub_power and (it.get("to_p50_gbp") or 0):
            e = gbp_by_cat.setdefault(q.sub_power, {"gbp": 0, "direction": it["direction"], "label": it["label"]})
            e["gbp"] += it["to_p50_gbp"]
    # the candidate set: one per lever offered against a real gap, deduped, £-carrying
    cands, seen = [], set()
    for ob in opts:
        cat = ob.get("category")
        for lev in ob.get("levers", []):
            key = (cat, lev.get("lever_id"))
            if key in seen:
                continue
            seen.add(key)
            m = gbp_by_cat.get(cat)
            roi = (("Indicative £%s a year to reach the peer median on %s, on lumi's stated assumptions."
                    % ("{:,}".format(int(m["gbp"])), m["label"]))
                   if m and m.get("gbp") else
                   ("Cost-saving where it lands." if lev.get("cost_character") == "cost-saving"
                    else "No indicative figure — the effect is on retention, fairness and how the package reads."))
            cands.append({
                "title": lev.get("name"), "category": cat, "lever_id": lev.get("lever_id"),
                "why": (ob.get("statement") or "") + " " + (lev.get("what_it_is") or ""),
                "horizon": lev.get("speed") or "this cycle",
                "cost_character": lev.get("cost_character"), "trade_off": lev.get("trade_off"),
                "roi": roi,
            })
    payload = {"objective": OBJECTIVE_LABELS.get(strat.get("primary_objective")),
               "objective_weights": (st.get("strategy") or {}).get("objective_weights") or {},
               "cut_label": cut_label, "candidates": cands[:10],
               "counts": al["counts"]}
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_action_plan, payload)
    plan = dict(res["parts"], source=res.get("source"),
                built_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                basis="Built from the gaps between your stated strategy and your own data, on %s. "
                      "Indicative figures come from lumi's £ model with its published assumptions." % cut_label)
    conn.execute("UPDATE org_strategy SET action_plan_json=? WHERE org_id=?",
                 (json.dumps(plan), org["org_id"]))
    conn.commit()
    return {"ok": True, "plan": plan}


# The document sections whose PROSE an author may replace. Deliberately a closed list:
# everything else on the page is a computed figure, a position, a count or a stated
# dial, and letting an author retype those would turn a benchmark into an assertion.
# Edit those at source — the wizard for what you stated, the data for what you are.
NARRATIVE_KEYS = ("exec_summary", "intent", "tensions", "watch", "findings_intro",
                  "gaps_intro", "plan_summary", "method")
NARRATIVE_MAX = 4000


@app.put("/api/strategy/narrative")
async def put_strategy_narrative(request: Request):
    """Replace one section's generated prose with the author's own wording (2026-08-16,
    David: "build in ways the user can edit and adjust any of the sections").

    Scope is the point: a key here overrides WRITTEN COMMENTARY only. Positions, counts,
    gaps and £ are never writable — they are what the engine found, and a document that
    let you retype them would stop being evidence. Sending an empty string clears the
    override and restores the generated text."""
    user, org = require_editor(request)
    body = await _json(request)
    key = (body.get("key") or "").strip()
    if key not in NARRATIVE_KEYS:
        raise HTTPException(400, "Unknown section '%s' — editable sections are: %s"
                            % (key, ", ".join(NARRATIVE_KEYS)))
    text = body.get("text")
    if text is not None and not isinstance(text, str):
        raise HTTPException(400, "text must be a string")
    text = (text or "").strip()
    if len(text) > NARRATIVE_MAX:
        raise HTTPException(400, "That section is longer than %d characters." % NARRATIVE_MAX)
    conn = get_conn()
    row = conn.execute("SELECT narrative_overrides_json FROM org_strategy WHERE org_id=?",
                       (org["org_id"],)).fetchone()
    if row is None:
        raise HTTPException(404, "No strategy to edit yet.")
    cur = uj(row["narrative_overrides_json"], {}) or {}
    if text:
        cur[key] = text
    else:
        cur.pop(key, None)
    conn.execute("UPDATE org_strategy SET narrative_overrides_json=?, updated_at=? WHERE org_id=?",
                 (json.dumps(cur), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), org["org_id"]))
    conn.commit()
    return {"ok": True, "key": key, "edited": bool(text), "narrative_overrides": cur}


@app.put("/api/strategy/draft")
async def put_strategy_draft(request: Request):
    """Server-side draft (2026-08-15): the in-flight capture, saved on every step.
    Stored as a blob APART from the live columns, so a half-finished capture never
    reaches the engine — nothing changes for anyone else until an explicit save.
    Editor-level: the person doing the work is usually the Contributor."""
    user, org = require_editor(request)
    body = await _json(request)
    payload = body.get("draft")
    if not isinstance(payload, dict):
        raise HTTPException(400, "draft must be an object.")
    blob = json.dumps(payload)
    if len(blob) > 200000:
        raise HTTPException(400, "That draft is too large to store.")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    who = user.get("name") or user.get("email") or "A colleague"
    conn.execute("INSERT INTO org_strategy (org_id, draft_json, draft_saved_at, draft_by) VALUES (?,?,?,?) "
                 "ON CONFLICT(org_id) DO UPDATE SET draft_json=excluded.draft_json, "
                 "draft_saved_at=excluded.draft_saved_at, draft_by=excluded.draft_by",
                 (org["org_id"], blob, now, who))
    conn.commit()
    return {"ok": True, "saved_at": now, "by": who}


@app.get("/api/strategy/draft")
async def get_strategy_draft(request: Request):
    user, org = require_user(request)
    r = get_conn().execute("SELECT draft_json, draft_saved_at, draft_by FROM org_strategy WHERE org_id=?",
                           (org["org_id"],)).fetchone()
    if not r or not r["draft_json"]:
        return {"ok": True, "draft": None}
    return {"ok": True, "draft": uj(r["draft_json"], None),
            "saved_at": r["draft_saved_at"], "by": r["draft_by"]}


@app.delete("/api/strategy/draft")
async def delete_strategy_draft(request: Request):
    user, org = require_editor(request)
    conn = get_conn()
    conn.execute("UPDATE org_strategy SET draft_json=NULL, draft_saved_at=NULL, draft_by=NULL WHERE org_id=?",
                 (org["org_id"],))
    conn.commit()
    return {"ok": True}


@app.post("/api/strategy/submit")
async def submit_strategy(request: Request):
    """Hand the strategy to an Admin for sign-off. Editor-level, because the drafter
    is often not the approver — that separation is the point."""
    user, org = require_editor(request)
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                        (org["org_id"],)).fetchone():
        raise HTTPException(400, "Save the strategy before sending it for approval.")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    who = user.get("name") or user.get("email") or "A colleague"
    conn.execute("UPDATE org_strategy SET submitted_at=?, submitted_by=? WHERE org_id=?",
                 (now, who, org["org_id"]))
    conn.commit()
    return {"ok": True, "submitted_at": now, "submitted_by": who}


@app.post("/api/strategy/withdraw")
async def withdraw_strategy_submission(request: Request):
    user, org = require_editor(request)
    conn = get_conn()
    conn.execute("UPDATE org_strategy SET submitted_at=NULL, submitted_by=NULL WHERE org_id=?", (org["org_id"],))
    conn.commit()
    return {"ok": True}


@app.get("/api/strategy/versions/{version}")
async def get_strategy_version(version: int, request: Request):
    """A single approved snapshot, for "what did we approve last year?"."""
    user, org = require_user(request)
    r = get_conn().execute("SELECT * FROM strategy_versions WHERE org_id=? AND version=?",
                           (org["org_id"], version)).fetchone()
    if not r:
        raise HTTPException(404, "No such version.")
    out = dict(r)
    out["snapshot"] = uj(out.pop("snapshot_json", None), {}) or {}
    out["unstated"] = uj(out.get("unstated_json"), []) or []
    out.pop("unstated_json", None)
    return out


@app.post("/api/strategy/approve")
async def approve_strategy(request: Request):
    """Approval as a governance ACT, not a button press (2026-08-15, all three
    persona reviews): Admin-only, explicitly confirmed, and recorded with WHO
    approved it (the body, which is usually not the account clicking), WHEN they
    approved it, what it is effective from, when it is next reviewed, and which
    sections were empty at the time. Immutable once written; the next approval
    supersedes it."""
    user, org = require_admin(request)
    body = await _json(request)
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                        (org["org_id"],)).fetchone():
        raise HTTPException(400, "Complete the three required positions before approving a version.")
    if not body.get("confirmed"):
        # the client shows what is unstated and asks; the server will not stamp a
        # governance record on an unconfirmed click
        raise HTTPException(400, "Approval must be confirmed.")
    st = strategy_state(conn, org)
    approver_body = str(body.get("approver_body") or "").strip()[:STRATEGY_GOV_CHARS]
    if not approver_body:
        raise HTTPException(400, "Name the person or body approving this version.")
    for k in ("approval_date", "effective_date", "next_review"):
        v = body.get(k)
        if v:
            try:
                datetime.strptime(str(v), "%Y-%m-%d")
            except ValueError:
                raise HTTPException(400, "%s must be YYYY-MM-DD." % k.replace("_", " "))
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute("SELECT submitted_by FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    nxt = (conn.execute("SELECT MAX(version) FROM strategy_versions WHERE org_id=?",
                        (org["org_id"],)).fetchone()[0] or 0) + 1
    conn.execute("UPDATE strategy_versions SET status='superseded' WHERE org_id=? AND status='approved'",
                 (org["org_id"],))
    conn.execute("INSERT INTO strategy_versions(org_id, version, snapshot_json, approved_by, approved_at, "
                 "status, approver_body, approval_date, effective_date, next_review, submitted_by, unstated_json) "
                 "VALUES (?,?,?,?,?,'approved',?,?,?,?,?,?)",
                 (org["org_id"], nxt,
                  json.dumps({"strategy": st["strategy"], "document": st["document"]}),
                  user.get("name") or user.get("email") or "Admin", now,
                  approver_body, body.get("approval_date") or None, body.get("effective_date") or None,
                  body.get("next_review") or None, (row["submitted_by"] if row else None),
                  json.dumps(_unstated_sections(st))))
    # the submission is consumed by the approval
    conn.execute("UPDATE org_strategy SET submitted_at=NULL, submitted_by=NULL WHERE org_id=?", (org["org_id"],))
    conn.commit()
    return {"ok": True, "version": nxt, "approved_at": now,
            "unstated": _unstated_sections(st)}


@app.get("/api/strategy/versions")
async def list_strategy_versions(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    return {"versions": [dict(dict(r), unstated=uj(r["unstated_json"], []) or []) for r in conn.execute(
        "SELECT version, approved_by, approved_at, status, approver_body, approval_date, "
        "effective_date, next_review, submitted_by, unstated_json FROM strategy_versions "
        "WHERE org_id=? ORDER BY version DESC", (org["org_id"],))]}


@app.get("/api/strategy/alignment")
async def get_strategy_alignment(request: Request):
    """The alignment read (2026-08-14, brief v2 §5): every commitment resolved to one
    of four statuses, counted per category — never a score (R5). Deterministic; the
    hero target read is the position evidence (same engine path as the overview)."""
    user, org = require_user(request)
    conn = get_conn()
    strat = strategy_for_engine(conn, org["org_id"])
    complete = conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                            (org["org_id"],)).fetchone()
    if not strat or not complete:
        return {"ok": False, "reason": "no_strategy"}
    st = strategy_state(conn, org)
    cut = parse_cut(request, org)
    items, tb = build_items(request, org, user, cut)
    prev_items = pos.prevalence_items(org["org_id"], cut, org_visible_questions(org), payloads(),
                                      org_answers_for(org), make_entitled(user, org), tb)
    sec_order = []
    for q in org_visible_questions(org).values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org),
                                             payloads(), org_answers_for(org), make_entitled(user, org), tb)
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=pos.market_position_config(), strategy=strat)
    # own-answer evidence: single-value answers only ((qid, "") keys; matrix rows are
    # never rule evidence — the rules speak in whole-question responses)
    answers = {k[0]: v for k, v in (org_answers_for(org) or {}).items()
               if (k[1] or "") == "" and isinstance(v, str)}
    _cut_label = (cut.get("label") or ("All peers" if cut.get("dim") == "all" else cut.get("value") or "your peer group"))
    out = strategy_align.evaluate(
        strategy_align.load_rules(), strat, st.get("document") or {}, answers,
        hero.get("domains") or [], STRATEGY_POSITION_EXCLUDE,
        visible_qids=set(org_visible_questions(org)),
        cut_label=_cut_label)
    # everything the Reward plan page needs, in one call: where you are (the per-category
    # target read), the gaps (commitments), what the market does about them (levers), and
    # the plan itself.
    out["options"] = strategy_align.options_for(out["commitments"], visible_qids=set(org_visible_questions(org)))
    out["domains"] = [{"name": d["name"],
                       "target": d.get("target"),
                       "position": {"verdict": (d.get("position") or {}).get("verdict"),
                                    "depth_pctl": (d.get("position") or {}).get("depth_pctl")} if d.get("position") else None}
                      for d in (hero.get("domains") or []) if d.get("target")]
    out["plan"] = (st.get("document") or {}).get("action_plan")
    out["cut_label"] = _cut_label
    out["objective"] = OBJECTIVE_LABELS.get(strat.get("primary_objective"))
    out["stance"] = strat.get("market_position")
    out["ok"] = True
    return out


@app.put("/api/strategy")
async def put_strategy(request: Request):
    """Editor-level upsert (Admin or Contributor — 2026-08-15: the person who does
    this work is usually the Contributor; APPROVAL stays Admin-only). Every field is
    validated against its enum (400 on unknown, never silent coerce). completed_at is
    set server-side only when all three required dials are non-null."""
    user, org = require_editor(request)
    body = await _json(request)
    incoming = body.get("strategy") or {}
    vals, prov = {}, {}
    for f, allowed in STRATEGY_ENUMS.items():
        v = incoming.get(f)
        if v in (None, ""):
            vals[f] = None
            prov[f] = "skipped"                      # required-empty also reads skipped; gate below catches it
            continue
        if v not in allowed:
            raise HTTPException(400, "'%s' isn't a valid option for %s." % (v, f.replace("_", " ")))
        vals[f] = v
        prov[f] = "set"
    ow = incoming.get("objective_weights")
    if ow is not None:
        if not isinstance(ow, dict):
            raise HTTPException(400, "objective_weights must be an object of {objective: points}.")
        clean = {}
        for k, v in ow.items():
            if k not in STRATEGY_ENUMS["primary_objective"]:
                raise HTTPException(400, "'%s' isn't a reward objective." % k)
            try:
                iv = int(v)
            except (TypeError, ValueError):
                raise HTTPException(400, "Objective ratings must be whole numbers.")
            if iv < 0 or iv > STRATEGY_OBJECTIVE_BUDGET:
                raise HTTPException(400, "Each objective is rated 0-%d." % STRATEGY_OBJECTIVE_BUDGET)
            if iv:
                clean[k] = iv
        if sum(clean.values()) > STRATEGY_OBJECTIVE_BUDGET:
            raise HTTPException(400, "You have %d points to spread across the objectives — that totals %d."
                                % (STRATEGY_OBJECTIVE_BUDGET, sum(clean.values())))
        vals["objective_weights"] = json.dumps(clean) if clean else None
        prov["objective_weights"] = "set" if clean else "skipped"
        # the engine contract is untouched: it still reads ONE primary_objective, which
        # is simply the objective the member rated highest.
        if clean:
            top = sorted(clean.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            vals["primary_objective"] = top
            prov["primary_objective"] = "set"
    else:
        vals["objective_weights"] = None

    bl = incoming.get("benefits_lead") or []
    if not isinstance(bl, list):
        raise HTTPException(400, "benefits_lead must be a list of areas.")
    for x in bl:
        if x not in STRATEGY_BENEFITS:
            raise HTTPException(400, "'%s' isn't a recognised benefits area." % x)
    vals["benefits_lead"] = json.dumps(bl) if bl else None
    prov["benefits_lead"] = "set" if bl else "skipped"
    # per-domain market-position target (step-3 layer 1, 2026-06-24) — STRICT REJECT.
    # A dict {domain: stance}; each stance must be a valid market_position enum, each
    # domain must pass _mp_competitive (the SINGLE source of truth — this rejects unknown
    # domains AND the non-competitive Governance through ONE gate, no special branch).
    # Absent/empty → skipped → null → degrade-to-global. Stored only; NO consumer yet (layer 3).
    dt = incoming.get("domain_targets") or {}
    if not isinstance(dt, dict):
        raise HTTPException(400, "domain_targets must be an object of {domain: stance}.")
    _mpc = pos.market_position_config()
    dt = _canon_domain_targets(dt, _mpc)          # heal legacy short keys before the gate
    _doms = _mpc.get("_domains", {})              # the canonical domain set (config = single source of truth)
    for dom, stance in dt.items():
        if stance not in STRATEGY_ENUMS["market_position"]:
            raise HTTPException(400, "'%s' isn't a valid market position for %s — use lag, match or lead." % (stance, dom))
        # reject UNKNOWN domains (absent from _domains — _mp_competitive defaults True for those)
        # AND non-competitive ones — one gate, derived.
        if dom not in _doms or not pos._mp_competitive(_mpc, dom):
            raise HTTPException(400, "'%s' isn't a competitive reward domain that can carry a market-position target." % dom)
        # R3b (David 2026-08-14): Wellbeing/Governance carry provision/practice commitments,
        # never a position — blocked at capture, honestly, not silently dropped later.
        if dom in STRATEGY_POSITION_EXCLUDE:
            raise HTTPException(400, "%s is measured by what's offered and how you operate, not a market rate — "
                                     "it can't carry a position target." % dom)
    vals["domain_targets"] = json.dumps(dt) if dt else None
    prov["domain_targets"] = "set" if dt else "skipped"
    # transparency RECONFIRM gate (step-3 tagging unit 2, 2026-06-25) — the field was hidden
    # ("coming") and is now live; resolves the L2 stale-value flag. A stored value must be SEEN +
    # reconfirmed in the visible field before it drives surfacing (treat-as-unset-until-reconfirmed).
    # The live field sends transparency_confirmed=true on save → provenance "live"; a pre-wiring value
    # passed through WITHOUT it keeps "set" → the engine (_transparency_mult) treats it as unset.
    # (transparency_confirmed rides the BODY top-level, beside plane_a — not inside `strategy`.)
    if vals.get("transparency") and body.get("transparency_confirmed"):
        prov["transparency"] = "live"

    conn = get_conn()
    # ---- Total Reward Strategy document fields (2026-08-14, rulings R1-R13) ----
    # Every field optional (resumable capture); caps are hard 400s; strings are the
    # member's words — the model never authors a commitment (guardrail 9).
    doc_in = body.get("document") or {}
    docvals = {}

    # the comparator IS the org default peer group — setting it here moves the whole
    # benchmark, so there is only ever one market in play (see strategy_state).
    _comp_in = doc_in.get("comparator_cut")
    docvals["comparator_cut"] = _validate_comparator(conn, org, _comp_in)
    if "comparator_cut" in doc_in and docvals["comparator_cut"] != (org.get("default_cut") or None):
        conn.execute("UPDATE orgs SET default_cut=? WHERE org_id=?",
                     (docvals["comparator_cut"], org["org_id"]))
        invalidate_payloads()
    prov["comparator"] = "set" if docvals["comparator_cut"] is not None else "skipped"

    # segments / "scarce roles" REMOVED 2026-08-15 (David): lumi holds no pay data, so a
    # premium for scarce roles can never be evidenced — capturing it invited a claim we
    # cannot stand behind. Column retained; no longer written.
    docvals["segments_json"] = None
    prov["segments"] = "skipped"

    prin = doc_in.get("principles") or []
    if not isinstance(prin, list):
        raise HTTPException(400, "principles must be a list of statements.")
    prin = [str(p).strip() for p in prin if str(p).strip()]
    if len(prin) > STRATEGY_MAX_PRINCIPLES:
        raise HTTPException(400, "At most %d reward principles." % STRATEGY_MAX_PRINCIPLES)
    if any(len(p) > STRATEGY_PRINCIPLE_CHARS for p in prin):
        raise HTTPException(400, "Each principle is capped at %d characters." % STRATEGY_PRINCIPLE_CHARS)
    docvals["principles_json"] = json.dumps(prin) if prin else None
    prov["principles"] = "set" if prin else "skipped"

    # "How reward is governed" REMOVED 2026-08-15 (David).
    docvals["reward_governance_json"] = None
    prov["reward_governance"] = "skipped"

    cons = doc_in.get("constraints") or {}
    if cons:
        if not isinstance(cons, dict):
            raise HTTPException(400, "constraints must be an object.")
        sel = [c for c in (cons.get("selected") or [])]
        for c in sel:
            if c not in STRATEGY_CONSTRAINTS:
                raise HTTPException(400, "'%s' isn't a constraint option." % c)
        notes = str(cons.get("notes") or "").strip()[:300]
        cons = {"selected": sel, "notes": notes} if (sel or notes) else {}
    docvals["constraints_json"] = json.dumps(cons) if cons else None
    prov["constraints"] = "set" if cons else "skipped"

    # "How we'll know it's working" (measures) REMOVED 2026-08-15 (David) — the metrics
    # already ARE the measures; asking a member to re-pick them was duplicate work.
    docvals["measures_json"] = None
    prov["measures"] = "skipped"
    # the roadmap is no longer typed by hand either: it becomes the AI-built action
    # plan, generated from the gaps once the strategy is set and the data is in.
    docvals["roadmap_json"] = None
    prov["roadmap"] = "skipped"

    pops_in = doc_in.get("population_targets") or []
    if not isinstance(pops_in, list):
        raise HTTPException(400, "population_targets must be a list.")
    pops = []
    for p in pops_in[:STRATEGY_MAX_POPULATIONS + 1]:
        if not isinstance(p, dict):
            raise HTTPException(400, "Each population position must be an object.")
        label = str(p.get("label") or "").strip()
        if not label:
            continue
        if label not in STRATEGY_POPULATIONS:
            raise HTTPException(400, "'%s' isn't a recognised employee population." % label)
        stance = p.get("position")
        if stance and stance not in STRATEGY_ENUMS["market_position"]:
            raise HTTPException(400, "'%s' isn't a valid position — use lag, match or lead." % stance)
        row = {"label": label}
        if stance:
            row["position"] = stance
        note = str(p.get("note") or "").strip()
        if note:
            row["note"] = note[:STRATEGY_STATEMENT_CHARS]
        pops.append(row)
    if len(pops) > STRATEGY_MAX_POPULATIONS:
        raise HTTPException(400, "At most %d employee populations." % STRATEGY_MAX_POPULATIONS)
    if len({p["label"] for p in pops}) != len(pops):
        raise HTTPException(400, "Each population can appear once.")
    docvals["population_targets_json"] = json.dumps(pops) if pops else None
    prov["population_targets"] = "set" if pops else "skipped"

    # "What we offer / how we operate" (commitments) REMOVED 2026-08-15 (David): every
    # one of those provisions is already captured as a metric answer.
    docvals["commitments_json"] = None
    prov["commitments"] = "skipped"

    prev = conn.execute("SELECT completed_at FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    complete = all(vals.get(f) for f in STRATEGY_REQUIRED)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    completed_at = (prev["completed_at"] if prev and prev["completed_at"] else None) or (now if complete else None)
    DOC_COLS = ["comparator_cut", "segments_json", "principles_json", "reward_governance_json",
                "constraints_json", "measures_json", "roadmap_json", "commitments_json",
                "population_targets_json"]
    cols = list(STRATEGY_ENUMS) + ["benefits_lead", "domain_targets", "objective_weights"] + DOC_COLS + ["field_provenance", "updated_at", "completed_at"]
    row_vals = ([vals[f] for f in STRATEGY_ENUMS] + [vals["benefits_lead"], vals["domain_targets"], vals.get("objective_weights")]
                + [docvals[c] for c in DOC_COLS] + [json.dumps(prov), now, completed_at])
    setclause = ", ".join("%s=excluded.%s" % (c, c) for c in cols)
    conn.execute("INSERT INTO org_strategy (org_id, %s) VALUES (%s) ON CONFLICT(org_id) DO UPDATE SET %s"
                 % (", ".join(cols), ", ".join(["?"] * (len(cols) + 1)), setclause),
                 [org["org_id"]] + row_vals)
    # Plane-A overrides persist back into the registry record (small merge)
    pa = body.get("plane_a") or {}
    if pa:
        reg = uj(org.get("registry_json"), {}) or {}
        changed = False
        for k, regkey in STRATEGY_PLANE_A_KEYS.items():
            if pa.get(k) and pa[k] != reg.get(regkey):
                reg[regkey] = pa[k]
                changed = True
        if changed:
            conn.execute("UPDATE orgs SET registry_json=? WHERE org_id=?",
                         (json.dumps(reg), org["org_id"]))
    conn.commit()
    # the saved strategy supersedes any in-flight draft
    conn.execute("UPDATE org_strategy SET draft_json=NULL, draft_saved_at=NULL, draft_by=NULL WHERE org_id=?",
                 (org["org_id"],))
    conn.commit()
    # notification coherence (step-3, ruling C — storm bound): a strategy change is the user's OWN
    # deliberate act, so it re-sorts what's worth flagging — that must QUIETLY re-baseline the bell,
    # never storm it (the inverse of the cut-drift stable ruling; parallel to the transparency
    # reconfirm gate). Recompute the strategy-aware signal set and silently reset signal_state, so
    # the next sweep diffs against the new baseline and a strategy-driven re-sort fires no alerts.
    # Best-effort — never break the save (only unlocked orgs have a baseline to reset).
    try:
        if org_unlocked(conn, org):
            notifications.rebaseline(conn, org["org_id"], org_signals(conn, org))
    except Exception as e:
        print("[lumi] strategy-change rebaseline failed for org %s: %s" % (org.get("org_id"), e))
    return {"ok": True, "completed_at": completed_at,
            "complete": bool(completed_at)}


def strategy_for_engine(conn, org_id):
    """The org's B/C strategy + provenance for the verdict engines, or None when
    unset (→ engines run their legacy path byte-for-byte, §5.5)."""
    r = conn.execute("SELECT * FROM org_strategy WHERE org_id=?", (org_id,)).fetchone()
    if not r:
        return None
    row = dict(r)
    out = {f: row.get(f) for f in STRATEGY_ENUMS}
    out["benefits_lead"] = uj(row.get("benefits_lead"), []) or []
    out["provenance"] = uj(row.get("field_provenance"), {}) or {}
    out["domain_targets"] = _canon_domain_targets(uj(row.get("domain_targets"), {}) or {})   # legacy keys healed — the engine matches sub_power names
    return out


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
    # DEDUPED BY NAME (2026-07-09 ship review, blocker B1): two library rows carry
    # sub_power_order=2 on 'Pay' (the other 58 are order=1), so keying on the full
    # (order, name, superpower) tuple minted a DUPLICATE 'Pay' section and trapped
    # the guided flow in a Pay↔Incentives loop (submission.js walks sections by
    # name via indexOf). Key on the sub-power NAME, keep the minimum (order,
    # superpower) — mirroring the frontend's own sectionList() dedupe
    # (web/js/app.js:775-783). Section names are now unique by construction.
    sections = []
    sub_order = {}
    for q in questions.values():
        sub = q.sub_power or "General"
        key = (q.sub_power_order or 999, q.superpower)
        if sub not in sub_order or key < sub_order[sub]:
            sub_order[sub] = key
    for sub, (_o, sp) in sorted(sub_order.items(), key=lambda kv: (kv[1][0], kv[0], kv[1][1])):
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
    body = await _json(request)
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
    classified = _classified_from(dict(row))
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
    rstate = refresh_policy.refresh_state(conn, org["org_id"], CURRENT_SNAPSHOT, questions)
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
            "needs_refresh": bool((rstate.get(qid) or {}).get("due")),
            "last_updated": (rstate.get(qid) or {}).get("last"),
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
    body = await _json(request)
    qid = body.get("question_id")
    row_id = body.get("matrix_row_id") or ""
    # resolve against the org's VISIBLE set, not the full library: the full-library
    # lookup accepted drafts for retired / sector-scoped / out-of-module questions,
    # which validate_all never checks (it iterates visible only) yet submit() commits —
    # a bypass of the r3s4 sector-scope rule (pre-prod audit 2026-08-12)
    q = org_visible_questions(org).get(qid)
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
    body = await _json(request)
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
    return {"problems": problems, "unanswered_required": unanswered_required,
          "pending_changes": len(drafts)}


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
    # belt to save_draft's visible-set gate: a stale draft for a question that has since
    # been retired or scoped away must not slip into the answers book un-validated
    _visible = org_visible_questions(org)
    _skipped = [d["question_id"] for d in drafts if d["question_id"] not in _visible]
    if _skipped:
        log.warning("submit: dropping %d out-of-scope draft(s) for org %s: %s",
                    len(_skipped), org["org_id"], ", ".join(sorted(set(_skipped))[:8]))
        conn.executemany("DELETE FROM drafts WHERE org_id=? AND question_id=?",
                         [(org["org_id"], qid) for qid in set(_skipped)])
        drafts = [d for d in drafts if d["question_id"] in _visible]
        if not drafts:
            conn.commit()
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
    basis_answered, basis_total = completion_counts(conn, dict(org))
    completion = 100.0 if not basis_total else round(100.0 * basis_answered / basis_total, 1)
    if completion >= TARGET_PCT:
        conn.execute("UPDATE orgs SET submission_complete=1 WHERE org_id=?", (org["org_id"],))
        conn.commit()
    # aggregates refresh (~2s, full-pool recompute holding the SQLite write lock).
    # Offloaded to a worker thread so the submit doesn't freeze the whole event loop
    # for every other concurrent request; run_snapshot uses its own thread-local
    # connection and commits independently.
    await to_thread.run_sync(run_snapshot, CURRENT_SNAPSHOT, False)
    invalidate_payloads()
    return {"ok": True, "answers_saved": now_rows,
            "completion_pct": completion,
            # exact key-question counts so the post-submit screen can say "just N more"
            "basis_answered": basis_answered, "basis_total": basis_total,
            "threshold_pct": TARGET_PCT,
            "benchmark_unlocked": completion >= TARGET_PCT}


# ========================================================== METRIC COMMENTARY ==

def _commentary_stance(percentile, polarity):
    """Same thresholds and polarity adjustment as the card pill."""
    if percentile is None or polarity in (None, "neutral"):
        return None
    adj = 100 - percentile if polarity == "lower_is_better" else percentile
    return "ahead" if adj > 55 else "behind" if adj < 45 else "in line"


def _cut_peer_n(conn, org, cut):
    """The nominal peer-group size for a cut — the SAME number the page header + the small-
    sample caveat show (mirrors the client cutSize and the board-pack cut_n at app.py ~2583).
    Used for the domain-summary provenance so 'compared with N peers' matches the header's
    'peer group (n=N)', not the whole-pool nominal (D4 reversal, counts-reconciliation
    ruling 2026-06-28)."""
    pool = get_meta("peer_pool", {}) or {}
    dim = cut.get("dim")
    if dim == "industry":
        return pool.get("industries", {}).get(cut.get("value") or org.get("industry"), 0)
    if dim == "fte_band":
        return pool.get("fte_bands", {}).get(cut.get("value") or org.get("fte_band"), 0)
    if dim == "twin":
        twin = peer_twin.compute_twin(conn, org["org_id"])
        return len(twin["peer_org_ids"]) if twin else 0
    if dim == "group":
        return len(peer_twin.group_org_ids(conn, cut.get("criteria") or {}))
    return pool.get("responding_orgs", 0)


def build_domain_summary_payload(conn, org, user, name, cut, apply_strategy=True):
    """The grounded per-DOMAIN payload: exactly the metric-level figures the domain page
    shows (Pass 2a position_metrics, prevalence, approach, the widest gaps/strengths,
    provenance) — and ONLY those numeric DATA fields (never metric definitions, so the
    validator's allowlist stays tight, D2). Built from the SAME engine the overview/§1
    donut uses, so the summary can never disagree with the page. Shared by the endpoint
    and the qa_domain_summary harness so the harness attacks the real path. apply_strategy
    drives the alignment field (present only strategy-on); the position counts are
    strategy-invariant either way (Pass 2a)."""
    qs = org_visible_questions(org)
    if not any(q.sub_power == name for q in qs.values()):
        return None
    entitled = make_entitled(user, org)
    answers = org_answers_for(org)
    tb = twin_blocks_if_needed(conn, org, cut) if cut.get("dim") in ("twin", "group") else None
    items = pos.position_items(org["org_id"], cut, qs, payloads(), answers, entitled, tb)
    prev_items = pos.prevalence_items(org["org_id"], cut, qs, payloads(), answers, entitled, tb)
    prac_items = pos.practice_position_items(org["org_id"], cut, qs, payloads(), answers, entitled, tb)
    mp_cfg = pos.market_position_config()
    strat = strategy_for_engine(conn, org["org_id"]) if apply_strategy else None
    sec_order = []
    for q in qs.values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    hero = pos.hero_signals(items, prev_items, sec_order, MARKET_BAND_LOW, MARKET_BAND_HIGH,
                            DOMAIN_MIN_POLARISED, VERDICT_NET_LEAN, UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=TILE_MIN_POSITIONED,
                            mp_config=mp_cfg, strategy=strat)
    d = next((x for x in hero["domains"] if x["name"] == name), None)
    if d is None:
        return None
    pm = d.get("position_metrics")
    has_pos = bool(d.get("competitiveness")) and pm is not None
    # widest gaps / strengths from the SAME Substance pool the counts use, with the
    # favourability-ADJUSTED percentile (50 + distance) so a quoted "P9" always reads
    # low = gap regardless of polarity (D1). Metric-level labels (matrix rows carry their
    # row label, e.g. "Pay by band — Senior").
    dom_pool = [i for i in pos.substance_pool(items, prac_items, mp_cfg) if i.get("subpower") == name]
    # Concise metric name: q.short_description (a clean label) + the matrix row, NOT the full
    # display_title — whose benchmark_display can embed an explanatory sentence with stray
    # numbers ("(where market is 100%) so 110%…") that would clutter the summary and mislead.
    def _gname(i):
        q = qs.get(i["question_id"])
        base = q.short_description if (q and q.short_description) else i["label"]
        base = re.sub(r"\s*\([^)]*\d[^)]*\)", "", base)   # drop only digit-bearing parens (noise, not "(PMI)")
        base = base.split("?")[0]                          # drop any trailing post-question explainer
        base = re.sub(r"\s+", " ", base).strip().rstrip(".,;:")
        if len(base) > 78:
            base = base[:77].rstrip() + "…"
        if i.get("row_id") and " — " in i["label"]:
            base = base + " — " + i["label"].rsplit(" — ", 1)[-1]
        return base
    _gs = lambda i: {"metric": _gname(i), "adj_pctl": round(50.0 + i["distance"]), "n": i["n"], "n_real": i.get("n_real", 0)}  # integer percentile (no false precision)
    gaps = [_gs(i) for i in pos.top_gaps(dom_pool, 3)]
    strengths = [_gs(i) for i in pos.top_strengths(dom_pool, 3)]
    prev = d.get("prevalence") or {}
    appr = d.get("approach") or {}
    # alignment in DISPLAY vocabulary, present only strategy-on AND when a target exists
    # (target is None strategy-off by construction). on_target -> "on strategy" (D3).
    _ALIGN = {"behind": "behind strategy", "on_target": "on strategy", "ahead": "ahead of strategy"}
    tgt = d.get("target")
    alignment = _ALIGN.get((tgt or {}).get("alignment")) if (tgt and apply_strategy) else None
    # the AIM itself travels with the alignment (David 2026-07-13, "the narrative needs to
    # directly relate to the strategy") — the summary can then say WHAT the strategy wants
    # here, not just how the domain scores against it. Display vocabulary; strategy-on only.
    _AIM = {"lag": "sit deliberately below the market", "match": "match the market",
            "lead": "lead the market"}
    strategy_aim = _AIM.get((tgt or {}).get("stance")) if (tgt and apply_strategy) else None
    mix_note = d.get("mix_note") if apply_strategy else None
    # provenance (counts-reconciliation fix, 2026-06-28): the ACTUAL number of metrics in this
    # domain the org has ANSWERED (matches the header's "N benchmarks", ~58 — NOT the positioned
    # subset of 13, which mislabelled positioned as answered and collided with the header), and
    # the CUT's peer count (the header's n=15 — NOT the whole-pool nominal of 220; D4 reversed).
    answered_count = sum(1 for qid, q in qs.items()
                         if (q.sub_power or "General") == name and entitled(q)
                         and any(k[0] == qid for k in answers))
    peer_pool_size = _cut_peer_n(conn, org, cut)
    small_sample = bool(peer_pool_size and peer_pool_size < 20)   # <20 thin cut — read directionally
    return {
        "domain": name,
        "has_position": has_pos,
        "position_basis": d.get("position_basis"),
        "position": ({"below": pm.get("below"), "at": pm.get("at"),
                      "above": pm.get("above"), "pool": pm.get("pool")} if has_pos else None),
        "gaps": gaps,
        "strengths": strengths,
        "prevalence": ({"match_market_majority": prev.get("with_majority"),
                        "established_alternative": prev.get("established"),
                        "less_common": prev.get("less_common"),
                        "pool": prev.get("pool")} if prev.get("pool") else None),
        # the "differ from market" approach register is the NON-competitive companion to the
        # market position (Governance) — for a competitive domain it's near-redundant beside
        # prevalence, so it's dropped (describe-only discipline; ruling 2026-06-28).
        "approach": ({"differ": appr.get("differ"), "in_line": appr.get("in_line"),
                      "pool": appr.get("pool")} if (not has_pos and appr.get("pool")) else None),
        "alignment": alignment,
        "strategy_aim": strategy_aim,
        "mix_note": mix_note,
        "provenance": {"answered_count": answered_count, "peer_pool_size": peer_pool_size},
        "small_sample": small_sample,
        "illustrative_sample_data": bool(get_meta("synthetic_pool", False)),
    }


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
    # the engine's market-position classification (same source the metric page's
    # "How lumi reads this" note uses) — lets the narrative frame a no-direction
    # measure by prevalence rather than a false above/below verdict.
    _mc = (pos.market_position_config().get("metrics") or {}).get(qid) or {}
    # stance is read from the firewall-reviewed market-position direction — the SAME
    # source the metric page's "How lumi reads this" note, pill and gauge use — never
    # the legacy DB polarity, which can disagree. This guarantees the narrative can't
    # contradict how the rest of the page reads the metric.
    _dir = _mc.get("direction")
    if _dir == "neutral" or _mc.get("class") in ("Practice", "Design"):
        _stance = None                                  # no inherent better/worse → prevalence
    elif _dir in ("higher_is_better", "lower_is_better"):
        _stance = _commentary_stance(pctl, _dir)
    else:
        _stance = _commentary_stance(pctl, pol)         # unclassified → fall back to engine polarity
    payload = {
        "metric": card["title"],
        "definition": card.get("definition") or "",
        "cut_label": card["cut"]["label"],
        "n": card["n"], "n_real": card.get("n_real", 0),
        "suppressed": bool(card.get("suppressed")),
        "polarity": _dir or pol,
        "you": you.get("display") or you.get("label"),
        "percentile": pctl,
        "stance": _stance,
        # richer signal for the narrative: how lumi classifies the metric, which
        # domain it sits in, and how it's expressed
        "cls": _mc.get("class"),
        "direction": _mc.get("direction"),
        "category": q.sub_power or q.category or q.superpower,
        "metric_type": q.type,
        "illustrative_sample_data": bool(get_meta("synthetic_pool", False)),
    }
    # the declared aim rides along (identical gate to the card's domain_aim) so the
    # model can never contradict the aim chip rendered beside it
    _cstrat = strategy_for_engine(conn, org["org_id"])
    if _cstrat and conn.execute("SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
                                (org["org_id"],)).fetchone():
        _cstance = (_cstrat.get("domain_targets") or {}).get(q.sub_power) or _cstrat.get("market_position")
        if _cstance and (pos.market_position_config().get("_domains") or {}).get(q.sub_power, {}).get("competitiveness", True):
            payload["declared_aim"] = {"lag": "below market", "match": "on market", "lead": "above market"}.get(_cstance)
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
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_COMMENTARY)
    body = await _json(request)
    qid = body.get("question_id")
    conn = get_conn()
    dim = body.get("cut") if body.get("cut") in ("all", "industry", "fte_band", "twin", "group") else "all"
    value = body.get("cut_value")
    payload = build_commentary_payload(conn, org, user, qid, dim, value)
    if payload is None:
        raise HTTPException(404, "That metric isn't part of your benchmark.")

    cut_key = dim + "::" + (value or "")
    phash = hashlib.sha256(
        (j(payload) + "|" + claude_api.COMMENTARY_GEN_VERSION).encode()).hexdigest()[:16]
    caveats = {"illustrative": bool(payload["illustrative_sample_data"])}
    if not body.get("force"):
        row = conn.execute(
            "SELECT * FROM metric_commentary WHERE org_id=? AND question_id=? AND cut_key=? AND payload_hash=?",
            (org["org_id"], qid, cut_key, phash)).fetchone()
        if row:
            return {"parts": uj(row["text"], {}), "source": row["source"], "cached": True,
                    "generated_at": row["created_at"], "caveats": caveats,
                    "edited_by": row["edited_by"], "edited_at": row["edited_at"]}
    # PEEK (2026-07-07): hydrate an existing (AI or edited) commentary on page load
    # WITHOUT spending a generation — nothing cached for this hash → return empty, and
    # the page shows the Generate prompt. Keeps a saved EDIT visible on return (and
    # stops the CTA overwriting it).
    if body.get("peek"):
        return {"parts": None, "source": None, "cached": False, "caveats": caveats}
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_metric_commentary, payload)
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], qid, cut_key, phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False, "caveats": caveats}


@app.post("/api/metric-commentary/save")
async def metric_commentary_save(request: Request):
    """Save a member-EDITED metric commentary — the org's OWN words (AI-assisted).
    The "edit and make it yours" path (2026-07-07): deliberately NOT run through the
    directive/legal validator that gates AI GENERATION. The member reviews and OWNS
    this note and may phrase it as advice/recommendations — the mirror-vs-consultant
    line stays on lumi's auto-generated text, not on the human's edit. Keyed to the
    current payload_hash so it self-invalidates like the AI cache when the figures
    move. Editor-only: the commentary is org-shared, so an edit changes it for all."""
    user, org = require_editor(request)
    require_ai(get_conn(), user, AI_COMMENTARY)
    body = await _json(request)
    qid = body.get("question_id")
    conn = get_conn()
    dim = body.get("cut") if body.get("cut") in ("all", "industry", "fte_band", "twin", "group") else "all"
    value = body.get("cut_value")
    payload = build_commentary_payload(conn, org, user, qid, dim, value)
    if payload is None:
        raise HTTPException(404, "That metric isn't part of your benchmark.")
    parts_in = body.get("parts") or {}
    parts = {}
    for k in claude_api.COMMENTARY_PARTS:
        v = str(parts_in.get(k) or "")[:2000]
        parts[k] = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", v).strip()   # strip control chars; the member's words otherwise stand
    if not any(parts.values()):
        raise HTTPException(400, "Nothing to save.")
    cut_key = dim + "::" + (value or "")
    phash = hashlib.sha256((j(payload) + "|" + claude_api.COMMENTARY_GEN_VERSION).encode()).hexdigest()[:16]
    who = user["email"]
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source, edited_by, edited_at) "
        "VALUES (?,?,?,?,?,?,?,datetime('now'))",
        (org["org_id"], qid, cut_key, phash, j(parts), "edited", who))
    conn.commit()
    row = conn.execute("SELECT edited_at FROM metric_commentary WHERE org_id=? AND question_id=? AND cut_key=?",
                       (org["org_id"], qid, cut_key)).fetchone()
    return {"parts": parts, "source": "edited", "edited_by": who,
            "edited_at": row["edited_at"] if row else None, "cached": True}


@app.post("/api/domain-summary")
async def domain_summary(request: Request):
    """AI per-DOMAIN describe-only summary for one domain on one cut + strategy state:
    grounded ONLY in the metric-level figures the domain page shows (Pass 2a), validated
    post-generation, cached per org+domain+cut+strategy until the underlying numbers change.
    Mirrors /api/metric-commentary. Never errors on model failure — generate_domain_summary
    always returns the validated deterministic floor when the model is down or rejected."""
    user, org = require_user(request)
    # Gate SPLIT (David's path-(a) ruling, 2026-07-13, briefing build): the deterministic
    # floor is template text composed from the member's own figures — NOT AI-generated
    # content — so it ships ungated (the board-pack §4.3 precedent). Only the CLAUDE call
    # honours the compliance-reserved gate (LUMI_AI_DOMAIN_SUMMARY default-off + consent);
    # that flag's product-wide go-live remains reserved for David, unchanged.
    _ai_ok = ai_feature_on(ai_gate(get_conn(), user), AI_DOMAIN_SUMMARY)
    body = await _json(request)
    name = body.get("domain")
    conn = get_conn()
    dim = body.get("cut") if body.get("cut") in ("all", "industry", "fte_band", "twin", "group") else "all"
    value = body.get("cut_value")
    if dim == "industry" and not value:
        value = org.get("industry")
    if dim == "fte_band" and not value:
        value = org.get("fte_band")
    apply_strategy = body.get("apply_strategy") is not False     # default True
    cut = {"dim": dim, "value": value}
    if dim == "group":
        row = conn.execute("SELECT * FROM peer_groups WHERE group_id=? AND org_id=?",
                           (value or "", org["org_id"])).fetchone()
        if row is None:
            cut, dim, value = {"dim": "all", "value": None}, "all", None   # foreign/stale id → all peers
        else:
            cut["label"] = row["name"]
            cut["criteria"] = uj(row["criteria_json"], {})
    payload = build_domain_summary_payload(conn, org, user, name, cut, apply_strategy=apply_strategy)
    if payload is None:
        raise HTTPException(404, "That domain isn't part of your benchmark.")

    # ai-state folds into the cache key so a deterministic-floor row can never be served
    # to an AI-enabled user (or the reverse) — the two produce different text for one hash
    cut_key = (dim + "::" + (value or "") + "::" + ("strat" if apply_strategy else "abs")
               + "::" + ("ai" if _ai_ok else "det"))
    phash = hashlib.sha256(
        (j(payload) + "|" + claude_api.DOMAIN_SUMMARY_GEN_VERSION).encode()).hexdigest()[:16]
    caveats = {"illustrative": bool(payload["illustrative_sample_data"])}
    if not body.get("force"):
        row = conn.execute(
            "SELECT * FROM domain_summary WHERE org_id=? AND domain=? AND cut_key=? AND payload_hash=?",
            (org["org_id"], name, cut_key, phash)).fetchone()
        if row:
            return {"parts": uj(row["text"], {}), "source": row["source"], "cached": True,
                    "generated_at": row["created_at"], "caveats": caveats}
    _ai_generation_or_429(org)
    res = await to_thread.run_sync(claude_api.generate_domain_summary, payload, _ai_ok)
    conn.execute(
        "INSERT OR REPLACE INTO domain_summary(org_id, domain, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], name, cut_key, phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False, "caveats": caveats}


# ============================================================ METRIC REQUESTS ==

NOTIFY_EMAIL = os.environ.get("LUMI_NOTIFY_EMAIL", "hello@lumihr.co.uk")
# Public origin for links inside outbound email (reset/invite). Localhost is the
# PH-CFG-1 Branch A (2026-08-08): THE one base-URL accessor. The old module
# global (import-time read, localhost fallback) let three divergent readers
# drift — one with a "" fallback that mailed RELATIVE dead links in digests.
# Rules, per the ruled Branch-A shape:
#   * read per call (setting the env needs a restart of nothing but the env);
#   * trailing slash normalised;
#   * minting=True (creating an invite/reset link): UNSET refuses THE ACTION
#     with the exact fix — never the boot; an explicit localhost value is a
#     legitimate dry-run configuration (gates set http://localhost:8060);
#   * non-localhost values must be https — an emailed link never downgrades a
#     member to plain http;
#   * minting=False (display/digest): unset returns None, callers omit links.
def base_url(minting=False):
    raw = (os.environ.get("LUMI_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        if minting:
            raise HTTPException(503, "LUMI_BASE_URL is not configured, so this link would "
                                     "be dead on arrival — refusing to mint it. Set "
                                     "LUMI_BASE_URL (production: https://your-domain; "
                                     "local dry-run: http://localhost:8060) and restart.")
        return None
    if minting:
        host = (urllib.parse.urlsplit(raw).hostname or "").lower()
        local = host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")
        if not raw.startswith(("http://", "https://")):
            raise HTTPException(503, "LUMI_BASE_URL must start http:// or https:// "
                                     "(currently %r)." % raw)
        if not local and not raw.startswith("https://"):
            raise HTTPException(503, "A non-localhost LUMI_BASE_URL must be https — "
                                     "emailed links must not downgrade members to plain http.")
    return raw


def composition_label(n, n_real):
    """P1-C (R-P1/R-P2): the ruled chip progression, server-rendered twin of
    web compositionLabel — shared artefacts (pack subs, CSV, digests) carry the
    same composition language as the live surfaces."""
    if n is None:
        return ""
    if not n_real or n_real <= 0:
        return "%s \u00b7 reference panel" % n
    if n_real >= n:
        return "%s members" % n
    return "%s \u00b7 %d member%s + panel" % (n, n_real, "" if n_real == 1 else "s")


def send_notification(subject, body, to=None, log_body=None):
    """Best-effort email. SMTP isn't configured in this environment, so this
    logs to console like every other outbound mail; when LUMI_SMTP_HOST is set
    it sends for real with no other changes. Never raises — the stored row is
    the source of truth. `to` defaults to the ops inbox (NOTIFY_EMAIL) for
    internal alerts; member digests pass the member's address.

    PH-PROV-1f: `log_body` is the REDACTED body for every console/log path
    (SMTP-unset fallback AND the send-failure print). A caller whose body
    carries a bearer (invite/reset link) passes a digest-bearing log_body so
    the bearer never lands in a log; the real body still goes to SMTP."""
    recipient = to or NOTIFY_EMAIL
    host = os.environ.get("LUMI_SMTP_HOST")
    if host:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = os.environ.get("LUMI_SMTP_FROM", "lumi <noreply@lumihr.co.uk>")
            msg["To"] = recipient
            msg["Subject"] = subject
            # deliverability + PECR courtesy on every outbound mail
            msg["List-Unsubscribe"] = os.environ.get(
                "LUMI_LIST_UNSUBSCRIBE", "<mailto:unsubscribe@lumihr.co.uk>")
            msg.set_content(body)
            with smtplib.SMTP(host, int(os.environ.get("LUMI_SMTP_PORT", "587")), timeout=10) as smtp:
                if os.environ.get("LUMI_SMTP_USER"):
                    # verified STARTTLS: Python 3.9's default context does NOT verify the
                    # relay certificate without this — a MITM'd relay would read every
                    # OTP and reset link (launch rehearsal 2026-08-13)
                    import ssl
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(os.environ["LUMI_SMTP_USER"], os.environ.get("LUMI_SMTP_PASS", ""))
                smtp.send_message(msg)
            return "sent"
        except Exception as e:
            # NEVER the raw body here: a production SMTP outage was writing live reset
            # links and MFA codes into the server log (launch rehearsal 2026-08-13 —
            # the PH-PROV-1d defect class, now closed at the choke point). log.error so
            # ops can alert on it; the redacted log_body still names what was lost.
            log.error("EMAIL SEND FAILED (%s) to %s — subject: %s%s", e, recipient, subject,
                      ("\n" + log_body) if log_body is not None else " (body withheld — carries user content)")
            return "failed"
    print("\n[lumi] EMAIL (not configured — logged only) to %s\n  Subject: %s\n%s\n"
          % (recipient, subject, log_body if log_body is not None else body))
    return "logged"


@app.post("/api/metric-requests")
async def create_metric_request(request: Request):
    user, org = require_user(request)
    body = await _json(request)
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
    requester = identity.user_display(user["user_id"]) or {}
    org_name = (identity.org_display(org["org_id"]) or {}).get("name")
    status = send_notification(
        "lumi metric request: %s" % text[:80],
        "Requested metric: %s\nNotes: %s\nFrom: %s (%s, %s)\nSource: %s\nWhen: %s\nRequest id: %d"
        % (text, notes or "—", requester.get("display_name") or requester.get("email"), requester.get("email"),
           org_name, source, datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), cur.lastrowid))
    return {"ok": True, "id": cur.lastrowid, "notification": status}


# ======================================================== METRIC SUGGESTIONS ==

def notify_suggestion_team(s):
    """Email the ops inbox about a new metric suggestion via the existing
    best-effort notification service (send_notification). The stored row is the
    source of truth; email is best-effort and never raises."""
    body = ("New metric suggestion #%d\n\n"
            "Metric name: %s\nWhat it measures: %s\nWhy it matters: %s\nSuggested category: %s\n\n"
            "From: %s (%s)\nOrganisation: %s\nWhen: %s\n"
            % (s["id"], s["metric_name"], s["what_it_measures"], s["why_it_matters"],
               s["suggested_category"] or "—", s["user_name"], s["user_email"], s["org_name"],
               datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")))
    return send_notification("New metric suggestion: %s" % s["metric_name"][:80], body)


@app.post("/api/suggestions")
async def create_suggestion(request: Request):
    user, org = require_user(request)               # 401 if session invalid
    body = await _json(request)
    name = (body.get("metric_name") or "").strip()
    measures = (body.get("what_it_measures") or "").strip()
    matters = (body.get("why_it_matters") or "").strip()
    category = (body.get("suggested_category") or "").strip() or None
    missing = [lbl for v, lbl in ((name, "metric name"), (measures, "what it measures"),
                                  (matters, "why it matters")) if not v]
    if missing:
        raise HTTPException(400, "Required: " + ", ".join(missing) + ".")
    # length caps mirror create_metric_request — unbounded fields were stored AND
    # emailed to the ops inbox verbatim (P3 sweep 2026-08-13)
    if len(name) > 120 or len(measures) > 2000 or len(matters) > 2000 or len(category or "") > 120:
        raise HTTPException(400, "That's a little long — a sentence or two per field is perfect.")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO metric_suggestions(org_id, user_id, user_email, metric_name, what_it_measures,"
        " why_it_matters, suggested_category) VALUES (?,?,?,?,?,?,?)",
        (org["org_id"], user["user_id"], user["email"], name, measures, matters, category))
    conn.commit()
    notify_suggestion_team({
        "id": cur.lastrowid, "metric_name": name, "what_it_measures": measures,
        "why_it_matters": matters, "suggested_category": category,
        "user_name": user["display_name"] or user["email"], "user_email": user["email"],
        "org_name": (identity.org_display(org["org_id"]) or {}).get("name")})
    return {"status": "ok", "id": cur.lastrowid}


# =============================================================== BACK OFFICE ==
# lumi-staff console (closes D2). EVERY route's first line is
# require_platform_admin — a cross-tenant privilege, so there is NO org scope and
# NEVER a client-supplied org_id. The console authors definitions/metadata only;
# it never writes answer data (answers / pulse_responses), so the integrity
# firewall holds. New core metrics are always unscored + optional.

def admin_sub_powers():
    """Live category -> sub_power_order map, DERIVED from the question bank (Diff 1
    doctrine: never a literal taxonomy). The old hardcoded seven-name list predated
    the 7->8 remap and silently blocked authoring into six of the eight live
    categories. Order is each category's live block rank (identical across its
    questions), sorted for a stable display list."""
    order = {}
    for q in visible_questions().values():
        if q.sub_power:
            o = q.sub_power_order or 0
            order[q.sub_power] = min(order.get(q.sub_power, o), o)
    return dict(sorted(order.items(), key=lambda kv: (kv[1], kv[0])))
SUGGESTION_STATUSES = ("new", "reviewed", "accepted", "rejected")
ADMIN_METRIC_TYPES = ("numeric", "single_select", "yes_no", "multi_select")


def _admin_slug_code(label):
    s = re.sub(r"[^A-Za-z0-9]+", "_", label.strip().upper()).strip("_")
    return s or "OPT"


def _audit(user, action, target_kind=None, target_id=None, detail=None):
    """Append one row to the back-office audit trail (admin_audit_log). Call it
    AFTER the action's own commit, so a failed action never logs as done. Actor
    is the user_id only — emails stay identity-side (Phase-1 split) and are
    resolved at read time. Never raises: an audit failure must not fail the
    staff action it describes (it logs loudly instead, like identity.shadow)."""
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO admin_audit_log(actor_user_id, action, target_kind, target_id, detail_json) "
            "VALUES (?,?,?,?,?)",
            (user["user_id"], action, target_kind,
             str(target_id) if target_id is not None else None,
             j(detail) if detail else None))
        conn.commit()
    except Exception as e:
        # security-relevant: a destructive console action completed but its audit row
        # didn't land. Log at ERROR so monitoring alerts rather than it scrolling past.
        log.error("admin-audit WRITE FAILED (%s): %s", action, e)


def _org_lifecycle(conn, o):
    """PH-PROV-2b §1: THE lifecycle derivation — one helper, one place, DERIVED
    never stored, reward store only (every signal is reward-side per 2a's P6).
    Seed and staff orgs are NOT in the member lifecycle (§1.2): they return None
    and render as provenance, not state. Deactivation is an OVERLAY the caller
    reads from orgs.deactivated_at — never a fifth state here (§1.4).
    Precedence: complete > contributing > activated > provisioned; 'activated'
    is the existence of any users row, which holds because provisioning creates
    only the org + invite and the user row is minted at invite-accept."""
    if o["source"] != "signup":
        return None
    if o["submission_complete"]:
        return {"state": "complete"}
    if o["clock_start"]:
        return {"state": "contributing"}
    if conn.execute("SELECT 1 FROM users WHERE org_id=? LIMIT 1",
                    (o["org_id"],)).fetchone():
        return {"state": "activated"}
    inv = conn.execute(
        "SELECT expires_at FROM invites WHERE org_id=? AND role='admin' "
        "AND used_at IS NULL AND expires_at > datetime('now') "
        "ORDER BY expires_at DESC LIMIT 1", (o["org_id"],)).fetchone()
    # §1.3: the sub-state that needs action — no live invite is the org that
    # goes unnoticed (provisioned weeks ago, never activated).
    return {"state": "provisioned", "invite_live": bool(inv),
            "invite_expires_at": inv["expires_at"] if inv else None}


# ----- module 1: cross-tenant orgs overview (read-only) ----------------------
@app.get("/api/admin/orgs")
async def admin_orgs(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT o.*, (SELECT COUNT(*) FROM users u WHERE u.org_id=o.org_id) AS n_users "
        "FROM orgs o").fetchall()
    names = identity.org_display_batch([r["org_id"] for r in rows])
    out = []
    for r in rows:
        o = dict(r)
        out.append({
            "org_id": o["org_id"], "name": names.get(o["org_id"]), "industry": o["industry"],
            "fte_band": o["fte_band"], "classified": bool(o["classified"]),
            "source": o["source"], "submission_complete": bool(o["submission_complete"]),
            "n_users": o["n_users"],
            # read-only unlock state (the stored stamp) — no side-effecting stamp
            # from a staff list view, unlike org_unlocked().
            "unlocked": bool(o["insights_unlocked_at"]) or bool(o["submission_complete"]),
            "deactivated": bool(o["deactivated_at"]),
            "deactivated_reason": o["deactivated_reason"],
            "lifecycle": _org_lifecycle(conn, o),
        })
    # sort by the RESOLVED identity name — orgs.name is NULLed by the Phase-1 split,
    # so the old ORDER BY o.name was insertion order in disguise (P3 sweep 2026-08-13)
    out.sort(key=lambda x: (x["name"] or "").lower())
    return {"orgs": out, "total": len(out)}


# ----- module 2: metric-suggestions triage ----------------------------------
@app.get("/api/admin/suggestions")
async def admin_suggestions(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT s.* FROM metric_suggestions s "
        "ORDER BY s.created_at DESC, s.id DESC").fetchall()
    names = identity.org_display_batch([r["org_id"] for r in rows])
    out = []
    for r in rows:
        d = dict(r)
        d["org_name"] = names.get(r["org_id"])
        out.append(d)
    return {"suggestions": out, "statuses": list(SUGGESTION_STATUSES)}


@app.put("/api/admin/suggestions/{sid}")
async def admin_suggestion_update(sid: int, request: Request):
    user = require_platform_admin(request)
    body = await _json(request)
    status = body.get("status")
    if status not in SUGGESTION_STATUSES:
        raise HTTPException(400, "status must be one of: " + ", ".join(SUGGESTION_STATUSES))
    notes = (body.get("review_notes") or "").strip() or None
    conn = get_conn()
    row = conn.execute("SELECT * FROM metric_suggestions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown suggestion")
    conn.execute("UPDATE metric_suggestions SET status=?, review_notes=?, reviewed_by=?, "
                 "reviewed_at=datetime('now') WHERE id=?", (status, notes, user["email"], sid))
    conn.commit()
    # accepting promotes it into the governed backlog (dedup by source_ref).
    promoted = False
    if status == "accepted":
        promoted = releases.add_backlog(
            row["metric_name"],
            (row["what_it_measures"] or "") + " — " + (row["why_it_matters"] or ""),
            "request-a-metric", "sugg-%d" % sid)
    _audit(user, "suggestion.update", "suggestion", sid,
           {"status": status, "promoted_to_backlog": promoted})
    return {"ok": True, "promoted_to_backlog": promoted}


# ----- module 3: pulse builder + management ----------------------------------
@app.get("/api/admin/pulses")
async def admin_pulses(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    out = []
    for p in conn.execute("SELECT * FROM pulses ORDER BY created_at DESC"):
        n_parts = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=?",
                               (p["pulse_id"],)).fetchone()[0]
        n_done = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=? AND submission_complete=1",
                              (p["pulse_id"],)).fetchone()[0]
        out.append({
            "pulse_id": p["pulse_id"], "name": p["name"], "description": p["description"],
            "status": p["status"], "opens_at": p["opens_at"], "closes_at": p["closes_at"],
            "n_questions": len(uj(p["question_ids_json"], [])),
            "n_participants": n_parts, "n_submitted": n_done})
    return {"pulses": out}


@app.post("/api/admin/pulses")
async def admin_pulse_create(request: Request):
    user = require_platform_admin(request)
    body = await _json(request)
    name = (body.get("name") or "").strip()
    desc = (body.get("description") or "").strip()
    if not name:
        raise HTTPException(400, "A pulse needs a name.")
    qids = body.get("question_ids") or []
    new_qs = body.get("new_questions") or []
    if not qids and not new_qs:
        raise HTTPException(400, "Add at least one question — from the library or a new one.")
    for nq in new_qs:                      # console v1 authors non-matrix only
        if nq.get("type") == "matrix":
            raise HTTPException(400, "Matrix questions are authored via script in v1, not the console.")
        if not (nq.get("text") or "").strip() or not nq.get("type"):
            raise HTTPException(400, "Each new question needs text and a type.")
    try:
        pid = pulses_mod.create_pulse(name, desc, qids, new_qs, body.get("closes_at") or None)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, "Couldn't create the pulse: %s" % e)
    _audit(user, "pulse.create", "pulse", pid, {"name": name})
    return {"ok": True, "pulse_id": pid}


def _pulse_lifecycle(fn, pid, user, verb):
    try:
        fn(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(user, "pulse." + verb, "pulse", pid)
    return {"ok": True}


@app.post("/api/admin/pulses/{pid}/open")
async def admin_pulse_open(pid: str, request: Request):
    user = require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.open_pulse, pid, user, "open")


@app.post("/api/admin/pulses/{pid}/close")
async def admin_pulse_close(pid: str, request: Request):
    user = require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.close_pulse, pid, user, "close")


@app.post("/api/admin/pulses/{pid}/archive")
async def admin_pulse_archive(pid: str, request: Request):
    user = require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.archive_pulse, pid, user, "archive")


@app.post("/api/admin/pulses/{pid}/extend")
async def admin_pulse_extend(pid: str, request: Request):
    user = require_platform_admin(request)
    body = await _json(request)
    new_close = (body.get("closes_at") or "").strip()
    if not new_close:
        raise HTTPException(400, "Provide a new close date/time (YYYY-MM-DD HH:MM:SS).")
    try:
        pulses_mod.extend_close(pid, new_close)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(user, "pulse.extend", "pulse", pid, {"closes_at": new_close})
    return {"ok": True}


@app.get("/api/admin/pulses/{pid}/report")
async def admin_pulse_report(pid: str, request: Request):
    require_platform_admin(request)
    try:
        rep = pulses_mod.pulse_report(pid, get_conn())
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    return strip_internal(rep)


# ============== SELF-SERVICE PULSE BUILDER + PAID LAUNCH (2026-06-22) =========
# An org Admin authors a pulse (its own firewall-safe questions), submits it for
# lumi review, and once approved is INVOICED the launch fee (PH-PAY-1: all
# payments by invoice); staff Confirm-launch opens it to the whole community.
# Ownership + the review/billing gate live on pulses.* ; payment ONLY gates
# draft->open and never touches give-to-get or the core firewall.

def _owned_pulse(conn, pid, org):
    """Fetch a pulse and assert this org owns it — 404 (not 403) for anything
    else so we never reveal another org's pulse ids."""
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    if not p["owner_org_id"] or p["owner_org_id"] != org["org_id"]:
        raise HTTPException(404, "Unknown pulse")
    return p


def _org_pulse_detail(conn, p):
    """Owner-facing detail incl. the authored questions (live library while a
    draft; the as-asked snapshot once opened) — feeds the builder + status view."""
    qs = pulses_mod.pulse_questions(p)
    qlist = []
    for qid, q in qs.items():
        qlist.append({"id": qid, "text": q.text, "title": q.display_title, "type": q.type,
                      "polarity": q.polarity,
                      "options": [{"code": o["code"], "label": o["label"]} for o in (q.options or [])],
                      "authored": str(qid).startswith("PULSE_")})
    d = pulses_mod._pulse_summary(p, conn)
    d["question_list"] = qlist
    d["payments_enabled"] = payments_mod.is_configured()
    d["payments_mode"] = payments_mod.mode()
    d["default_fee_pence"] = PULSE_LAUNCH_FEE_PENCE
    return d


def _parse_pulse_body(body):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Your pulse needs a name.")
    if len(name) > 120:
        raise HTTPException(400, "Keep the survey name under 120 characters.")
    description = (body.get("description") or "").strip()
    if len(description) > 280:
        raise HTTPException(400, "Keep the description under 280 characters.")
    qids = body.get("question_ids") or []
    new_qs = body.get("new_questions") or []
    if not qids and not new_qs:
        raise HTTPException(400, "Add at least one question.")
    # the full new-question validation (types, options, lengths) lives in
    # pulses._assemble_questions and runs at create/update — surface its message
    try:
        pulses_mod.validate_new_questions(new_qs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    closes_at = (body.get("closes_at") or "").strip() or None
    if closes_at is not None:
        parsed, date_only = None, False
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(closes_at, fmt)
                date_only = (fmt == "%Y-%m-%d")
                break
            except ValueError:
                continue
        if parsed is None:
            raise HTTPException(400, "Close date must look like YYYY-MM-DD or YYYY-MM-DD HH:MM.")
        if date_only:
            parsed = parsed.replace(hour=23, minute=59, second=59)   # a date closes at end of day
        if parsed <= datetime.utcnow():
            raise HTTPException(400, "The close date needs to be in the future.")
        closes_at = parsed.strftime("%Y-%m-%d %H:%M:%S")   # store ISO, never free text
    return name, description, qids, new_qs, closes_at


@app.get("/api/org/pulses")
async def org_pulses_list(request: Request):
    user, org = require_admin(request)
    return {"pulses": pulses_mod.org_pulses(org["org_id"], get_conn()),
            "payments_enabled": payments_mod.is_configured(),
            "payments_mode": payments_mod.mode(),
            "default_fee_pence": PULSE_LAUNCH_FEE_PENCE}


@app.get("/api/org/pulses/{pid}")
async def org_pulse_detail(pid: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    return _org_pulse_detail(conn, _owned_pulse(conn, pid, org))


@app.post("/api/org/pulses")
async def org_pulse_create(request: Request):
    user, org = require_admin(request)
    name, desc, qids, new_qs, closes_at = _parse_pulse_body(await _json(request))
    try:
        pid = pulses_mod.create_pulse(name, desc, qids, new_qs, closes_at,
                                      owner_org_id=org["org_id"], created_by=user["user_id"])
    except (ValueError, KeyError) as e:
        raise HTTPException(400, "Couldn't create the pulse: %s" % e)
    return {"ok": True, "pulse_id": pid}


@app.put("/api/org/pulses/{pid}")
async def org_pulse_update(pid: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    _owned_pulse(conn, pid, org)
    name, desc, qids, new_qs, closes_at = _parse_pulse_body(await _json(request))
    try:
        pulses_mod.update_pulse_draft(pid, org["org_id"], name, desc, qids, new_qs, closes_at, conn)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.delete("/api/org/pulses/{pid}")
async def org_pulse_discard(pid: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    _owned_pulse(conn, pid, org)
    try:
        pulses_mod.discard_pulse(pid, org["org_id"], conn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/org/pulses/{pid}/submit-for-review")
async def org_pulse_submit_review(pid: str, request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    _owned_pulse(conn, pid, org)
    try:
        pulses_mod.submit_for_review(pid, org["org_id"], conn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/org/pulses/{pid}/checkout")
async def org_pulse_checkout(pid: str, request: Request):
    """Approved -> launch requested. ALL PAYMENTS BY INVOICE (David's ruling,
    2026-08-04, PH-PAY-1): this records the launch ORDER — the invoice ledger
    entry — and a platform admin confirms the launch once the invoice is
    settled (the existing Confirm-launch path). The Stripe checkout, redirect
    reconcile, and webhook that used to live here were removed under the same
    ruling; card payment may return later, and payments.mode() is the seam it
    would return through. Endpoint path kept for client compatibility."""
    user, org = require_admin(request)
    conn = get_conn()
    p = _owned_pulse(conn, pid, org)
    if p["launch_status"] != "approved":
        raise HTTPException(400, "This pulse isn't approved for launch yet.")
    # explicit 0 = staff-waived fee; only an UNSET fee falls back to the default
    fee = p["launch_fee_pence"] if p["launch_fee_pence"] is not None else PULSE_LAUNCH_FEE_PENCE
    oid = pulses_mod.create_launch_order(pid, org["org_id"], fee, created_by=user["user_id"], conn=conn)
    return {"ok": True, "mode": "invoice", "order_id": oid, "amount_pence": fee,
            "message": "Launch requested — lumi will invoice you, and your pulse opens "
                       "to the community as soon as it's confirmed."}


# ----- staff: review + confirm self-service launches -------------------------
@app.get("/api/admin/pulse-reviews")
async def admin_pulse_reviews(request: Request):
    require_platform_admin(request)
    return {"pulses": pulses_mod.review_queue(get_conn()),
            "payments_mode": payments_mod.mode(),
            "default_fee_pence": PULSE_LAUNCH_FEE_PENCE}


@app.post("/api/admin/pulses/{pid}/review")
async def admin_pulse_review(pid: str, request: Request):
    staff = require_platform_admin(request)
    body = await _json(request)
    decision = body.get("decision")
    notes = (body.get("notes") or "").strip()
    fee = body.get("fee_pence")
    if fee in (None, ""):
        fee = PULSE_LAUNCH_FEE_PENCE if decision == "approve" else None
    elif decision == "approve":
        try:
            fee = int(fee)
        except (TypeError, ValueError):
            raise HTTPException(400, "fee_pence must be a whole number of pence")
        if fee < 0:
            raise HTTPException(400, "fee_pence cannot be negative")
    try:
        pulses_mod.review_pulse(pid, decision, staff["user_id"], notes=notes, fee_pence=fee, conn=get_conn())
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(staff, "pulse.review", "pulse", pid,
           {"decision": decision, "fee_pence": fee if decision == "approve" else None})
    return {"ok": True}


@app.post("/api/admin/pulses/{pid}/confirm-launch")
async def admin_pulse_confirm_launch(pid: str, request: Request):
    """Staff confirm a launch once the invoice is settled — THE payment path
    (PH-PAY-1: all payments by invoice). Marks the latest pending order paid,
    or records one, which opens the pulse."""
    staff = require_platform_admin(request)
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    if not p["owner_org_id"] or p["launch_status"] not in ("approved", "paid"):
        raise HTTPException(400, "Only an approved self-service pulse can be confirmed.")
    # explicit 0 = staff-waived fee; only an UNSET fee falls back to the default
    fee = p["launch_fee_pence"] if p["launch_fee_pence"] is not None else PULSE_LAUNCH_FEE_PENCE
    o = pulses_mod.latest_order(pid, conn)
    oid = (o["order_id"] if (o and o["status"] != "paid")
           else pulses_mod.create_launch_order(pid, p["owner_org_id"], fee, created_by=staff["user_id"], conn=conn))
    pulses_mod.mark_order_paid(oid, payment_intent="staff-confirmed", conn=conn)
    # the £-consequential staff action: confirming the invoice as settled.
    _audit(staff, "pulse.confirm_launch", "pulse", pid,
           {"order_id": oid, "fee_pence": fee})
    return {"ok": True, "pulse_id": pid}


# ----- module 4: create metric (author -> backlog -> publish live) -----------
def _validate_metric_def(body):
    text = (body.get("text") or "").strip()
    sub_power = (body.get("sub_power") or "").strip()
    qtype = (body.get("type") or "").strip()
    polarity = (body.get("polarity") or "neutral").strip()
    if not text:
        raise HTTPException(400, "The metric needs a question text.")
    if sub_power not in admin_sub_powers():
        raise HTTPException(400, "Category must be one of: " + ", ".join(admin_sub_powers()))
    if qtype not in ADMIN_METRIC_TYPES:
        raise HTTPException(400, "Type must be numeric, single_select, yes_no or multi_select "
                                 "(matrix is script-only in v1).")
    if polarity not in ("higher_is_better", "lower_is_better", "neutral"):
        raise HTTPException(400, "Polarity must be higher_is_better, lower_is_better or neutral.")
    options = []
    if qtype in ("single_select", "yes_no", "multi_select"):
        labels = [str(l).strip() for l in (body.get("options") or []) if str(l).strip()]
        if qtype == "yes_no" and not labels:
            labels = ["Yes", "No"]
        if len(labels) < 2:
            raise HTTPException(400, "Select questions need at least two options.")
        for l in labels:
            if ";" in l or "," in l:
                raise HTTPException(400, "Option labels can't contain ';' or ',' (delimiter-safe storage).")
        options = labels
    return {
        "text": text, "short_description": (body.get("short_description") or text[:80]).strip(),
        "help_text": (body.get("help_text") or "").strip() or None,
        "definition": (body.get("definition") or "").strip() or None,
        "sub_power": sub_power, "type": qtype, "polarity": polarity, "options": options,
        "unit": (body.get("unit") or "").strip() or None,
        "unit_display_name": (body.get("unit_display_name") or "").strip() or None,
        "unit_type": (body.get("unit_type") or "none").strip() or "none",
    }


def _publish_metric(conn, m):
    """Governed insert of a NEW core metric — mirrors apply_release_2026_2.py.
    ALWAYS is_scored=0 + is_required=0 (never re-locks the 82-question unlock
    gate, never needs seeded answers — the firewall holds). Stamped to the
    current release; no per-metric release cut (the next annual diff logs it as
    'added'). Caller commits + marks the backlog row applied."""
    qid = "ADM_" + uuid.uuid4().hex[:10].upper()
    if conn.execute("SELECT 1 FROM questions WHERE id=?", (qid,)).fetchone():
        raise ValueError("id collision — please retry")
    order = (conn.execute("SELECT MAX(question_order) FROM questions "
                          "WHERE question_order < 90000").fetchone()[0] or 0) + 1
    is_select = m["type"] in ("single_select", "yes_no", "multi_select")
    opts = j([{"code": _admin_slug_code(l), "label": l, "order": i + 1, "is_na": False}
              for i, l in enumerate(m["options"])]) if is_select else None
    unit_type = m["unit_type"] if m["type"] == "numeric" else "none"
    rel = releases.current_release(conn)
    cols = {
        "id": qid, "text": m["text"], "short_description": m["short_description"],
        "help_text": m["help_text"], "definition": m["definition"], "superpower": "Reward",
        "sub_power": m["sub_power"], "sub_power_order": admin_sub_powers()[m["sub_power"]],
        "type": m["type"], "category": "practice", "options_json": opts,
        "default_chart_type": "quartile_band" if m["type"] == "numeric" else "bar",
        "data_display_type": "mean" if m["type"] == "numeric" else "percentage_distribution",
        "polarity": m["polarity"],
        "unit": m["unit"] if m["type"] == "numeric" else None,
        "unit_display_name": m["unit_display_name"] if m["type"] == "numeric" else None,
        "unit_type": unit_type, "currency_code": "GBP" if unit_type == "currency" else None,
        "lumi_tier": "Core",
        "na_handling_json": j({"exclude_from_scoring": True, "exclude_from_benchmarking": False}),
        "benchmark_display": m["short_description"], "is_scored": 0, "is_required": 0,
        "search_description": ((m["help_text"] or "") + " " + m["text"]).strip(),
        "question_order": order, "question_version": "v1.0",
        "historical_comparability": "high", "status": "active",
        "release_entered": rel["release_id"] if rel else None,
    }
    conn.execute("INSERT INTO questions(%s) VALUES (%s)" % (
        ",".join(cols), ",".join("?" * len(cols))), list(cols.values()))
    load_questions.cache_clear()
    invalidate_payloads()
    return qid


@app.get("/api/admin/backlog")
async def admin_backlog(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute("SELECT * FROM core_backlog ORDER BY created_at DESC, id DESC").fetchall()
    return {"backlog": [dict(r) for r in rows]}


@app.post("/api/admin/metrics/draft")
async def admin_metric_draft(request: Request):
    user = require_platform_admin(request)
    body = await _json(request)
    metric = _validate_metric_def(body)
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO core_backlog(title, detail, source, status) VALUES (?,?,'admin_console','queued')",
        (metric["text"][:120], j(metric)))
    conn.commit()
    _audit(user, "metric.draft", "metric", cur.lastrowid, {"title": metric["text"][:120]})
    return {"ok": True, "backlog_id": cur.lastrowid}


@app.post("/api/admin/metrics/{backlog_id}/publish")
async def admin_metric_publish(backlog_id: int, request: Request):
    user = require_platform_admin(request)
    conn = get_conn()
    row = conn.execute("SELECT * FROM core_backlog WHERE id=?", (backlog_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown backlog item")
    if row["source"] != "admin_console":
        raise HTTPException(400, "Only console-authored drafts can be published here.")
    if row["status"] == "applied":
        raise HTTPException(400, "This draft has already been published.")
    metric = uj(row["detail"], None)
    if not metric:
        raise HTTPException(400, "This backlog item has no metric definition to publish.")
    try:
        qid = _publish_metric(conn, metric)
    except ValueError as e:
        conn.rollback()
        raise HTTPException(400, "Couldn't publish: %s" % e)
    conn.execute("UPDATE core_backlog SET status='applied' WHERE id=?", (backlog_id,))
    conn.commit()
    _audit(user, "metric.publish", "metric", qid, {"backlog_id": backlog_id})
    return {"ok": True, "question_id": qid}


# ===== BACK OFFICE v2 (2026-08-03): org drill-down, user support, ops, ======
# ===== billing, compliance, audit. Same doctrine: cross-tenant, no client ====
# ===== org_id, definitions/metadata only — NEVER answer data. Identity reads =
# ===== honour the no-bulk-export contract: emails surface only org-scoped ====
# ===== (user_display_batch, capped) or single-key (exact-email lookup). ======

_BOOT_TIME = datetime.utcnow()
_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# ----- provisioning: create an org + its founding-admin invite (PH-PROV-1) ---
@app.post("/api/admin/orgs")
async def admin_org_create(request: Request):
    """Staff-provisioned membership (PH-PROV-1 §2.1 as amended by the ruling
    addendum). Contract: org_name, admin_email, and ALL FOUR PROFILE_CORE
    firmographics — industry, fte_band, hq_region (the spec's 'region' IS
    hq_region; stated here so the mapping cannot drift), ownership_type — each
    validated against profile_choices(), the same accessor the member profile
    form uses. Creates the orgs row AND the founding-admin invite in ONE reward
    transaction (ruling §3); role='admin' is permitted here and on the reissue
    route only — the tenant /api/team/invite path keeps its own independent
    guard, deliberately unshared. classified is DERIVED via _classified_from,
    never hardcoded. No email is sent: the link is returned for staff to pass
    on. Identity attachments (org name, invite email) follow the reward commit
    as shadows, the house order. The six identity columns in the reward store
    are never written."""
    staff = require_platform_admin(request)
    body = await _json(request)
    name = (body.get("org_name") or "").strip()
    if not name:
        raise HTTPException(400, "Give the organisation a name (org_name).")
    nn = re.sub(r"[^a-z0-9]", "", name.lower())
    if not nn:
        raise HTTPException(400, "The name needs at least one letter or number.")
    email = (body.get("admin_email") or "").strip()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid admin email address (admin_email).")
    if auth_lib.find_user(email):
        raise HTTPException(400, "That email already has a lumi account.")
    choices = profile_choices()
    firmo = {}
    for f in PROFILE_CORE:
        v = (body.get(f) or "").strip() if isinstance(body.get(f), str) else body.get(f)
        if not v:
            raise HTTPException(400, "'%s' is required — all four profile fields are "
                                     "provisioned so the member never meets the "
                                     "complete-your-profile prompt." % f)
        if choices.get(f) and v not in choices[f]:
            raise HTTPException(400, "'%s' isn't one of the recognised options for %s."
                                     % (v, f.replace("_", " ")))
        firmo[f] = v
    # collision check with CLASS in the message (ruling §6): the name namespace is
    # identity-side (org_register); the colliding org's reward-side source names it.
    hit = identity.org_lookup_by_normalized(nn)
    if hit:
        conn = get_conn()
        src = conn.execute("SELECT source FROM orgs WHERE org_id=?",
                           (hit["org_id"],)).fetchone()
        cls = {"seed": "a seed benchmark organisation",
               "signup": "an existing member organisation",
               "staff": "the lumi staff organisation"}.get(src["source"] if src else None,
                                                           "an existing organisation")
        raise HTTPException(400, "That name collides with %s already on the platform." % cls)
    conn = get_conn()
    org_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)   # mirrors auth.create_invite's minting exactly;
    expires = (datetime.utcnow()        # inlined so both rows share ONE transaction
               + timedelta(days=auth_lib.INVITE_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        _insert_member_org(conn, org_id, firmo)   # classified derived from the four fields
        # QA seam (default OFF): §7.7 demands proof that a failure between the two
        # inserts leaves no orphan org. Active only when the operator launched the
        # server with LUMI_QA_SEAMS=on — never in normal operation.
        if body.get("_qa_fail_after_org") and os.environ.get("LUMI_QA_SEAMS") == "on":
            raise RuntimeError("qa seam: forced failure after org insert")
        # QA seam (LUMI_QA_SEAMS only): plants the impossible state so the
        # anomaly assertion below is provably live, per PH-PROV-1g §2.3.
        if body.get("_qa_inject_prior_invite") and os.environ.get("LUMI_QA_SEAMS") == "on":
            conn.execute("INSERT INTO invites(token, org_id, role, created_by, expires_at) "
                         "VALUES (?,?,?,?,?)",
                         ("qa-seam-" + org_id[:8], org_id, "admin", staff["user_id"], expires))
        # PH-PROV-1g §2.3 — assert, don't assume: this org_id was minted lines
        # above, so a pre-existing admin invite for it is an anomaly (collision
        # or bug), and the request fails closed rather than proceeding.
        if conn.execute("SELECT 1 FROM invites WHERE org_id=? AND role='admin' LIMIT 1",
                        (org_id,)).fetchone():
            raise RuntimeError("anomaly: a pre-existing admin invite for a just-minted org_id")
        conn.execute(
            "INSERT INTO invites(token, org_id, role, created_by, expires_at) "
            "VALUES (?,?,?,?,?)", (token, org_id, "admin", staff["user_id"], expires))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, "Provisioning failed before completion — nothing was "
                                 "created. (%s)" % e)
    # QA seam, second branch (same LUMI_QA_SEAMS pattern, PH-PROV-1 Stage 3 §1):
    # simulate the post-reward-commit identity failure — both shadows skipped, the
    # response still 200, exactly the silent orphan the real failure mode produces.
    # identity_recon is the net that must catch it; qa_backoffice asserts it does.
    if body.get("_qa_fail_identity") and os.environ.get("LUMI_QA_SEAMS") == "on":
        _audit(staff, "org.create", "org", org_id, {"invite_role": "admin", "classified": 1})
        return {"ok": True, "org_id": org_id, "name": name,
                "invite_link": "%s/app#/invite/%s" % (base_url(minting=True), token),
                "expires_days": auth_lib.INVITE_TTL_DAYS}
    identity.shadow(identity.register_org_identity, org_id, name, nn)
    identity.shadow(identity.record_invite, token, org_id, email.lower(), "admin",
                    staff["user_id"], expires)
    # NO name and NO email in the audit detail: both are identity-side (Phase-1
    # split); the org_id target resolves at read time like every other surface.
    _audit(staff, "org.create", "org", org_id, {"invite_role": "admin", "classified": 1})
    return {"ok": True, "org_id": org_id, "name": name,
            "invite_link": "%s/app#/invite/%s" % (base_url(minting=True), token),
            "expires_days": auth_lib.INVITE_TTL_DAYS}


@app.post("/api/admin/orgs/{org_id}/invite")
async def admin_org_invite(org_id: str, request: Request):
    """Staff invite into ANY org — the provisioning twin of /api/team/invite.
    ONE deliberate difference: staff may invite an ADMIN (a new org needs its
    founding Admin; the tenant path stays promotion-only precisely so a tenant
    admin can't silently mint one). The invitee sets their own password and
    accepts the platform terms on join — the console never handles either."""
    staff = require_platform_admin(request)
    body = await _json(request)
    email = (body.get("email") or "").strip()
    role = body.get("role") if body.get("role") in ("admin", "contributor", "viewer") else "viewer"
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    conn = get_conn()
    orow = conn.execute("SELECT deactivated_at FROM orgs WHERE org_id=?", (org_id,)).fetchone()
    if orow is None:
        raise HTTPException(404, "Unknown organisation")
    if orow["deactivated_at"]:
        raise HTTPException(400, "This organisation is deactivated — reactivate it before inviting.")
    if auth_lib.find_user(email):
        raise HTTPException(400, "That email already has a lumi account.")
    if role == "admin":
        # PH-PROV-1g §2.2 — THE BOUNDARY OF THE 2026-08-03 CARVE-OUT, not a mere
        # validation: the carve-out authorises minting an organisation's FIRST
        # Admin only. Once an Admin exists and is active, another admin invite
        # is lateral admin creation — exactly what "Admins are made by
        # promotion, never by invite" (2026-06-11) exists to prevent.
        if conn.execute("SELECT 1 FROM users WHERE org_id=? AND role='admin' "
                        "AND disabled_at IS NULL LIMIT 1", (org_id,)).fetchone():
            raise HTTPException(400, "This organisation already has an active Admin — "
                                     "Admins are made by promotion (their Team page), "
                                     "never by invite. The provisioning carve-out covers "
                                     "only the founding Admin.")
        # PH-PROV-1g §2.1 — at most ONE live admin invite per org: reissuing
        # supersedes every prior live admin invite, via G1's own mechanism
        # (used_at), in the SAME transaction as the new insert — both or
        # neither. Contributor/viewer invites are untouched by construction.
        prior = [r["token"] for r in conn.execute(
            "SELECT token FROM invites WHERE org_id=? AND role='admin' AND used_at IS NULL",
            (org_id,))]
        token = secrets.token_urlsafe(24)
        expires = (datetime.utcnow()
                   + timedelta(days=auth_lib.INVITE_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            if prior:
                conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token IN (%s)"
                             % ",".join("?" * len(prior)), prior)
            # QA seam (LUMI_QA_SEAMS only): §3.6 — a failure between invalidate
            # and insert must leave the PRIOR invite live and no new row.
            if body.get("_qa_fail_after_invalidate") and os.environ.get("LUMI_QA_SEAMS") == "on":
                raise RuntimeError("qa seam: forced failure between invalidate and insert")
            conn.execute(
                "INSERT INTO invites(token, org_id, role, created_by, expires_at) "
                "VALUES (?,?,?,?,?)", (token, org_id, "admin", staff["user_id"], expires))
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(500, "Reissue failed before completion — nothing changed; "
                                     "any prior invite is still live. (%s)" % e)
        for t in prior:
            identity.shadow(identity.mark_invite_used, t)
        identity.shadow(identity.record_invite, token, org_id, email.lower(), "admin",
                        staff["user_id"], expires)
    else:
        token = auth_lib.create_invite(org_id, email, role, staff["user_id"])
        prior = []
    link = "%s/app#/invite/%s" % (base_url(minting=True), token)
    org_name = (identity.org_display(org_id) or {}).get("name") or "your organisation"
    # PH-PROV-1f: the console/log fallback carries a DIGEST, never the link —
    # the API response below already hands the operator the link directly, so
    # the logged copy served no one and exposed a live bearer (PH-PROV-1d's
    # defect class). The real email body (SMTP path) still carries the link.
    send_notification(
        "You've been invited to lumi",
        "Hello,\n\nThe lumi team has invited you to join %s on lumi — the UK reward "
        "benchmarking co-operative — as a %s.\n\nAccept your invite here:\n\n%s\n\n"
        "The link expires in %d days. If you weren't expecting this, you can ignore "
        "this email.\n\n— lumi · UK reward benchmarking"
        % (org_name, ROLE_LABELS.get(role, role), link, auth_lib.INVITE_TTL_DAYS),
        to=email,
        log_body="[provisioning invite — link withheld from logs (PH-PROV-1f); "
                 "token sha256[:12]=%s; the link was returned to the console operator "
                 "in the API response]" % hashlib.sha256(token.encode()).hexdigest()[:12])
    # the email itself stays out of the reward-store audit row (Phase-1 split);
    # the invite's identity half already records it, org-scoped. Superseded
    # tokens appear as sha256[:12] digests — the PH-PROV-1d convention: the
    # audit names what was invalidated without a bearer ever landing in a log.
    detail = {"role": role}
    if prior:
        detail["superseded_token_sha256_12"] = [
            hashlib.sha256(t.encode()).hexdigest()[:12] for t in prior]
        detail["cause"] = "superseded by reissue"
    _audit(staff, "org.invite", "org", org_id, detail)
    return {"ok": True, "link": link, "expires_days": auth_lib.INVITE_TTL_DAYS}


@app.post("/api/admin/invites/{token}/revoke")
async def admin_invite_revoke(token: str, request: Request):
    staff = require_platform_admin(request)
    conn = get_conn()
    row = conn.execute("SELECT org_id, used_at FROM invites WHERE token=?", (token,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown invite")
    if row["used_at"]:
        raise HTTPException(400, "That invite is already used or revoked.")
    conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=?", (token,))
    conn.commit()
    identity.shadow(identity.mark_invite_used, token)
    _audit(staff, "org.invite_revoke", "org", row["org_id"])
    return {"ok": True}


# ----- soft-deactivate (ACCESS gates only — nothing is deleted, contributed ---
# ----- answers stay in the pool; retire-never-delete) -------------------------
def _suspension_reason(body):
    """PH-PAY-3: every suspension carries WHY — a bare timestamp couldn't tell
    'unpaid' from 'sole-admin recovery in progress', which need opposite
    operator responses. Required, short, and kept out of the identity space
    (name the situation, not a person)."""
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "Give a reason for the suspension — it's what tells the "
                                 "next operator whether this is e.g. 'unpaid invoice' or "
                                 "'sole-admin recovery in progress' (opposite responses).")
    if len(reason) > 200:
        raise HTTPException(400, "Keep the reason under 200 characters — it's a label for "
                                 "the console, not a case file.")
    return reason


@app.post("/api/admin/users/{user_id}/deactivate")
async def admin_user_deactivate(user_id: str, request: Request):
    staff = require_platform_admin(request)
    reason = _suspension_reason(await _json(request))
    conn = get_conn()
    row = conn.execute("SELECT platform_admin, disabled_at FROM users WHERE user_id=?",
                       (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown user")
    if row["platform_admin"]:
        raise HTTPException(400, "Staff accounts can't be deactivated from the console.")
    if row["disabled_at"]:
        raise HTTPException(400, "That account is already deactivated.")
    conn.execute("UPDATE users SET disabled_at=datetime('now'), disabled_reason=? "
                 "WHERE user_id=?", (reason, user_id))
    conn.commit()
    n = identity.delete_sessions_for_user(user_id)
    _audit(staff, "user.deactivate", "user", user_id, {"sessions_revoked": n, "reason": reason})
    return {"ok": True, "sessions_revoked": n}


@app.post("/api/admin/users/{user_id}/reactivate")
async def admin_user_reactivate(user_id: str, request: Request):
    staff = require_platform_admin(request)
    conn = get_conn()
    row = conn.execute("SELECT disabled_at FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown user")
    if not row["disabled_at"]:
        raise HTTPException(400, "That account isn't deactivated.")
    # reason cleared with the state (it describes the CURRENT suspension only;
    # the audit log keeps the history)
    conn.execute("UPDATE users SET disabled_at=NULL, disabled_reason=NULL WHERE user_id=?",
                 (user_id,))
    conn.commit()
    _audit(staff, "user.reactivate", "user", user_id)
    return {"ok": True}


@app.post("/api/admin/orgs/{org_id}/deactivate")
async def admin_org_deactivate(org_id: str, request: Request):
    """Suspend a whole membership: every member loses access (existing sessions
    revoked, new logins refused, pending invites can't complete). The org's rows
    — profile, answers, history — are untouched, and reactivation restores
    access exactly as it was."""
    staff = require_platform_admin(request)
    reason = _suspension_reason(await _json(request))
    conn = get_conn()
    row = conn.execute("SELECT source, deactivated_at FROM orgs WHERE org_id=?",
                       (org_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown organisation")
    if row["source"] == "staff":
        raise HTTPException(400, "The staff org can't be deactivated — that would lock "
                                 "the console out of itself.")
    if row["deactivated_at"]:
        raise HTTPException(400, "That organisation is already deactivated.")
    conn.execute("UPDATE orgs SET deactivated_at=datetime('now'), deactivated_reason=? "
                 "WHERE org_id=?", (reason, org_id))
    conn.commit()
    members = [r["user_id"] for r in
               conn.execute("SELECT user_id FROM users WHERE org_id=?", (org_id,))]
    revoked = sum(identity.delete_sessions_for_user(u) for u in members)
    _audit(staff, "org.deactivate", "org", org_id,
           {"members": len(members), "sessions_revoked": revoked, "reason": reason})
    return {"ok": True, "members": len(members), "sessions_revoked": revoked}


@app.post("/api/admin/orgs/{org_id}/reactivate")
async def admin_org_reactivate(org_id: str, request: Request):
    staff = require_platform_admin(request)
    conn = get_conn()
    row = conn.execute("SELECT deactivated_at FROM orgs WHERE org_id=?", (org_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown organisation")
    if not row["deactivated_at"]:
        raise HTTPException(400, "That organisation isn't deactivated.")
    # PH-PAY-2 R3: bank THIS suspension's elapsed seconds into the accumulator
    # before clearing the state — accumulated, never a single delta, so a
    # second suspension accrues on top of the first. Computed in SQL against
    # the same clock that stamped deactivated_at.
    conn.execute("UPDATE orgs SET "
                 "suspended_seconds = suspended_seconds + "
                 "  MAX(0, strftime('%s','now') - strftime('%s', deactivated_at)), "
                 "deactivated_at=NULL, deactivated_reason=NULL "
                 "WHERE org_id=?", (org_id,))
    conn.commit()
    _audit(staff, "org.reactivate", "org", org_id)
    return {"ok": True}


# ----- org drill-down --------------------------------------------------------
@app.get("/api/admin/orgs/{org_id}")
async def admin_org_detail(org_id: str, request: Request):
    require_platform_admin(request)
    conn = get_conn()
    o = conn.execute("SELECT * FROM orgs WHERE org_id=?", (org_id,)).fetchone()
    if o is None:
        raise HTTPException(404, "Unknown organisation")
    o = dict(o)
    ident = identity.org_display(org_id)
    urows = conn.execute(
        "SELECT user_id, role, platform_admin, created_at, disabled_at, disabled_reason "
        "FROM users WHERE org_id=? ORDER BY created_at", (org_id,)).fetchall()
    # org-scoped identity batch (capped at 200 — the contract's org-sized shape).
    uids = [r["user_id"] for r in urows][:200]
    idents = identity.user_display_batch(uids)
    users = []
    for r in urows:
        d = idents.get(r["user_id"], {})
        users.append({
            "user_id": r["user_id"], "role": r["role"],
            "platform_admin": bool(r["platform_admin"]), "created_at": r["created_at"],
            "email": d.get("email"), "display_name": d.get("display_name"),
            "active_sessions": len(identity.sessions_for_user(r["user_id"])),
            "disabled_at": r["disabled_at"],
            "disabled_reason": r["disabled_reason"],
        })
    terms = []
    for t in conn.execute(
            "SELECT user_id, kind, version, accepted_at FROM terms_acceptances "
            "WHERE org_id=? ORDER BY accepted_at DESC", (org_id,)):
        d = dict(t)
        d["email"] = idents.get(t["user_id"], {}).get("email")
        terms.append(d)
    # PH-PROV-2b §2.4: expired-but-unused invites stay visible — they are the
    # attention state (§1.3) and the thing reissue exists for. Used/revoked stay hidden.
    irows = conn.execute(
        "SELECT token, role, expires_at, expires_at > datetime('now') AS live FROM invites "
        "WHERE org_id=? AND used_at IS NULL "
        "ORDER BY expires_at DESC", (org_id,)).fetchall()
    iem = identity.invite_email_batch([r["token"] for r in irows][:200])
    # a READ view must not 503 on an unset LUMI_BASE_URL (base_url(minting=True)
    # raises by design) — the drill-down was unreadable exactly when config was
    # broken and staff most needed it (P3 sweep 2026-08-13). link=null when unset.
    _base = base_url()
    invites = [{"token": r["token"], "role": r["role"], "expires_at": r["expires_at"],
                "email": iem.get(r["token"]), "expired": not r["live"],
                "link": ("%s/app#/invite/%s" % (_base, r["token"])) if _base else None} for r in irows]
    counts = {
        "answers": conn.execute("SELECT COUNT(*) FROM answers WHERE org_id=?", (org_id,)).fetchone()[0],
        "drafts": conn.execute("SELECT COUNT(*) FROM drafts WHERE org_id=?", (org_id,)).fetchone()[0],
        "peer_groups": conn.execute("SELECT COUNT(*) FROM peer_groups WHERE org_id=?", (org_id,)).fetchone()[0],
        "suggestions": conn.execute("SELECT COUNT(*) FROM metric_suggestions WHERE org_id=?", (org_id,)).fetchone()[0],
    }
    strat = conn.execute("SELECT completed_at, updated_at FROM org_strategy WHERE org_id=?",
                         (org_id,)).fetchone()
    return {
        "org": {
            "org_id": org_id, "name": ident["name"] if ident else None,
            "source": o["source"], "tier_entitlement": o["tier_entitlement"],
            "classified": bool(o["classified"]), "industry": o["industry"],
            "subsector": o["subsector"], "fte_band": o["fte_band"],
            "hq_region": o["hq_region"], "ownership_type": o["ownership_type"],
            "submission_complete": bool(o["submission_complete"]),
            "created_at": o["created_at"], "clock_start": o["clock_start"],
            "insights_unlocked_at": o["insights_unlocked_at"],
            "unlocked_release": o["unlocked_release"], "default_cut": o["default_cut"],
            "deactivated_at": o["deactivated_at"],
            "deactivated_reason": o["deactivated_reason"],
            "lifecycle": _org_lifecycle(conn, o),
        },
        "users": users, "terms": terms, "counts": counts,
        "strategy": dict(strat) if strat else None,
        "invites": invites,
    }


# ----- user support (exact-email lookup + session/reset actions) -------------
@app.get("/api/admin/users/lookup")
async def admin_user_lookup(request: Request):
    """Single-key identity read (S4.3): staff type the EXACT email — there is
    deliberately no wildcard or platform-wide user list."""
    require_platform_admin(request)
    email = (request.query_params.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Provide an email address to look up.")
    ident = identity.lookup_user_by_email(email)
    if ident is None:
        return {"found": False}
    conn = get_conn()
    acct = conn.execute(
        "SELECT role, platform_admin, created_at, disabled_at, disabled_reason "
        "FROM users WHERE user_id=?", (ident["user_id"],)).fetchone()
    org_ident = identity.org_display(ident["org_id"])
    sessions = identity.sessions_for_user(ident["user_id"])
    return {"found": True, "user": {
        "user_id": ident["user_id"], "email": ident["email"],
        "display_name": ident["display_name"], "org_id": ident["org_id"],
        "org_name": org_ident["name"] if org_ident else None,
        "role": acct["role"] if acct else None,
        "platform_admin": bool(acct["platform_admin"]) if acct else False,
        "created_at": acct["created_at"] if acct else None,
        "disabled_at": acct["disabled_at"] if acct else None,
        "disabled_reason": acct["disabled_reason"] if acct else None,
        "active_sessions": len(sessions),
        "sessions": sessions,      # created/expires only — tokens never leave identity.py
    }}


def _refuse_staff_target(user_id):
    """Console credential actions (force-logout, reset-link) must not target a
    platform-staff account — minting a reset link for a super-admin would be an
    account-takeover path. Mirrors the deactivate guard so all three are consistent."""
    r = get_conn().execute("SELECT platform_admin FROM users WHERE user_id=?", (user_id,)).fetchone()
    if r and r["platform_admin"]:
        raise HTTPException(400, "Staff accounts are managed out of band, not from the console.")


@app.post("/api/admin/users/{user_id}/logout")
async def admin_user_logout(user_id: str, request: Request):
    """Force sign-out everywhere — the support action for a lost laptop or a
    suspected compromised session. Revokes identity-side sessions (the only
    store get_session_user reads post-Seam-B)."""
    staff = require_platform_admin(request)
    if identity.user_display(user_id) is None:
        raise HTTPException(404, "Unknown user")
    _refuse_staff_target(user_id)
    n = identity.delete_sessions_for_user(user_id)
    _audit(staff, "user.force_logout", "user", user_id, {"sessions_revoked": n})
    return {"ok": True, "sessions_revoked": n}


@app.post("/api/admin/users/{user_id}/reset-link")
async def admin_user_reset_link(user_id: str, request: Request):
    """Mint a password-reset link for a member (the manual sole-admin-recovery
    process DECISIONS flagged). Uses the exact same token path as the member's
    own 'forgot password' — 2-hour expiry, single use. The link is returned to
    the console for staff to pass on out-of-band; the token itself is never
    written to the audit trail."""
    staff = require_platform_admin(request)
    if identity.user_display(user_id) is None:
        raise HTTPException(404, "Unknown user")
    _refuse_staff_target(user_id)
    token = auth_lib.create_reset(user_id)
    _audit(staff, "user.reset_link", "user", user_id)
    return {"ok": True, "link": "%s/app#/reset/%s" % (base_url(minting=True), token),
            "expires_in_hours": auth_lib.RESET_TTL_HOURS}


# ----- ops: platform health + curated config ---------------------------------
def _db_file_stats(path):
    out = {}
    for suffix, key in (("", "db"), ("-wal", "wal"), ("-shm", "shm")):
        p = path + suffix
        if os.path.exists(p):
            out[key] = os.path.getsize(p)
    return out


@app.get("/api/admin/health")
async def admin_health(request: Request):
    require_platform_admin(request)
    conn = get_conn()

    def one(sql, *args):
        return conn.execute(sql, args).fetchone()[0]

    def by(sql):
        return {r[0] or "—": r[1] for r in conn.execute(sql)}

    backups = []
    try:
        for f in os.listdir(_PROJECT_ROOT):
            if f.startswith("lumi.db.bak_") and not f.endswith(("-wal", "-shm")):
                p = os.path.join(_PROJECT_ROOT, f)
                backups.append({"file": f, "bytes": os.path.getsize(p),
                                "modified": datetime.utcfromtimestamp(
                                    os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")})
        backups.sort(key=lambda b: b["modified"], reverse=True)
    except OSError:
        pass
    rel = releases.current_release(conn)
    _key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    _live = os.environ.get("LUMI_AI_LIVE", "").lower() == "on"
    return {
        "uptime_seconds": int((datetime.utcnow() - _BOOT_TIME).total_seconds()),
        "server_started_utc": _BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        "counts": {
            "orgs_total": one("SELECT COUNT(*) FROM orgs"),
            "orgs_by_source": by("SELECT source, COUNT(*) FROM orgs GROUP BY source"),
            "users": one("SELECT COUNT(*) FROM users"),
            "active_sessions": identity.active_session_count(),
            "answers_rows": one("SELECT COUNT(*) FROM answers"),
            "questions_active": one("SELECT COUNT(*) FROM questions WHERE status='active'"),
            "pulses_by_status": by("SELECT status, COUNT(*) FROM pulses GROUP BY status"),
            "suggestions_by_status": by("SELECT status, COUNT(*) FROM metric_suggestions GROUP BY status"),
            "backlog_queued": one("SELECT COUNT(*) FROM core_backlog WHERE status='queued'"),
            "orders_by_status": by("SELECT status, COUNT(*) FROM pulse_launch_orders GROUP BY status"),
            "terms_acceptances": one("SELECT COUNT(*) FROM terms_acceptances"),
            "audit_rows": one("SELECT COUNT(*) FROM admin_audit_log"),
        },
        "storage": {
            "lumi_db": _db_file_stats(os.path.join(_PROJECT_ROOT, "lumi.db")),
            "identity_db": _db_file_stats(os.path.join(_PROJECT_ROOT, "identity.db")),
            "backups": backups[:5], "backups_total": len(backups),
        },
        "modes": {
            "payments": payments_mod.mode(),
            "ai_master_gate": bool(AI_INSIGHTS_ENABLED),
            "ai_live": _live, "ai_key_present": _key,
            "ai_effective": "live" if (AI_INSIGHTS_ENABLED and _live and _key) else "deterministic",
            "signal_sweep": os.environ.get("LUMI_SIGNAL_SWEEP", "").lower() == "on",
            "sweep_hour_utc": int(os.environ.get("LUMI_SWEEP_HOUR", "7")) % 24,
            "smtp_configured": bool(os.environ.get("LUMI_SMTP_HOST")),
            "base_url": base_url() or "(unset — link minting disabled)",
            "base_url_is_localhost": bool(base_url() and ("localhost" in base_url() or "127.0.0.1" in base_url())),
        },
        "release": {"release_id": rel["release_id"], "name": rel["name"],
                    "released_at": rel["released_at"]} if rel else None,
    }


# Curated config inventory — every operational switch, described, with secrets
# reported as set/unset only (values never leave the server). This is the
# console twin of the boot log: what IS the environment, not what could be.
_CONFIG_INVENTORY = [
    ("LUMI_BASE_URL", "value", "Public origin for emailed invite/reset/share links"),
    ("LUMI_MFA", "value", "Enforce email one-time-code MFA on every login — MUST be 'on' in production (CE A7.16/A7.17)"),
    ("LUMI_SEED_DEMO", "value", "Provision demo accounts with known passwords — dev/QA only, MUST be unset in production (CE A5.2/A5.3)"),
    ("LUMI_STAFF_PASSWORD", "secret", "Initial password for the seeded staff/super-admin account (else strong-random)"),
    ("LUMI_SUPER_ADMINS", "secret", "Back-office allowlist (comma-separated emails)"),
    ("LUMI_OPEN_REGISTRATION", "value", "Self-serve signup — CLOSED unless 'on' (membership is staff-provisioned)"),
    ("LUMI_QA_SEAMS", "value", "Gate-only fault injection in provisioning; default unset = inert. MUST NEVER be set outside gate runs"),
    ("LUMI_AI_INSIGHTS_ENABLED", "value", "AI master gate — all AI features off unless 'on'"),
    ("LUMI_AI_LIVE", "value", "Paid Claude calls — deterministic drafts unless 'on'"),
    ("ANTHROPIC_API_KEY", "secret", "Claude API key (server/.env.local)"),
    ("ANTHROPIC_MODEL", "value", "Model override for AI features"),
    ("LUMI_PULSE_LAUNCH_FEE_GBP", "value", "Default self-service pulse launch fee (£), invoiced — all payments by invoice (PH-PAY-1)"),
    ("LUMI_SIGNAL_SWEEP", "value", "Nightly signal sweep + email digest scheduler"),
    ("LUMI_SWEEP_HOUR", "value", "Sweep hour (UTC, default 7)"),
    ("LUMI_SMTP_HOST", "value", "SMTP relay — emails console-logged when unset"),
    ("LUMI_SMTP_PORT", "value", "SMTP port"),
    ("LUMI_SMTP_USER", "value", "SMTP username"),
    ("LUMI_SMTP_PASS", "secret", "SMTP password"),
    ("LUMI_SMTP_FROM", "value", "From address on outbound email"),
    ("LUMI_COMPLETION_BASIS", "value", "Unlock-gate basis (default: required)"),
    ("LUMI_COMPLETION_THRESHOLD", "value", "Unlock-gate threshold (default 0.90)"),
    ("LUMI_MARKET_BAND", "value", "Hero market-position band width"),
    ("LUMI_ANALYST_RATE_PER_HOUR", "value", "Ask-lumi questions per org-hour cap"),
    ("LUMI_ANALYST_MAX_QUESTION_CHARS", "value", "Ask-lumi question length cap"),
    ("LUMI_AI_TIMEOUT_SECONDS", "value", "AI call timeout"),
]


@app.get("/api/admin/config")
async def admin_config(request: Request):
    require_platform_admin(request)
    out = []
    for name, kind, desc in _CONFIG_INVENTORY:
        raw = os.environ.get(name)
        out.append({
            "name": name, "kind": kind, "description": desc,
            "set": raw is not None and raw != "",
            "value": (raw if kind == "value" else None) if raw else None,
        })
    return {"config": out}


# ----- billing: the pulse-launch order ledger ---------------------------------
@app.get("/api/admin/orders")
async def admin_orders(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT o.*, p.name AS pulse_name FROM pulse_launch_orders o "
        "LEFT JOIN pulses p ON p.pulse_id=o.pulse_id "
        "ORDER BY o.created_at DESC").fetchall()
    names = identity.org_display_batch([r["org_id"] for r in rows])
    out = []
    for r in rows:
        d = dict(r)
        d["org_name"] = names.get(r["org_id"])
        d.pop("stripe_session_id", None)      # internal handles stay server-side
        out.append(d)
    total_paid = sum(r["amount_pence"] for r in rows if r["status"] == "paid")
    return {"orders": out, "total_paid_pence": total_paid,
            "payments_mode": payments_mod.mode()}


# ----- compliance: the terms-acceptance evidence trail ------------------------
@app.get("/api/admin/terms")
async def admin_terms(request: Request):
    """The DPA/consent evidence trail, org-named. Deliberately NO emails at this
    platform-wide scope (the no-bulk contract) — the org drill-down shows who,
    org-scoped. Latest 500."""
    require_platform_admin(request)
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0]
    rows = conn.execute(
        "SELECT org_id, user_id, kind, version, accepted_at FROM terms_acceptances "
        "ORDER BY accepted_at DESC, id DESC LIMIT 500").fetchall()
    names = identity.org_display_batch([r["org_id"] for r in rows])
    out = []
    for r in rows:
        d = dict(r)
        d["org_name"] = names.get(r["org_id"])
        out.append(d)
    return {"acceptances": out, "total": total,
            "versions": {"platform": PLATFORM_TERMS_VERSION, "data_contribution": DATA_TERMS_VERSION}}


# ----- the audit trail itself -------------------------------------------------
@app.get("/api/admin/audit")
async def admin_audit_list(request: Request):
    require_platform_admin(request)
    try:
        limit = max(1, min(int(request.query_params.get("limit", "200")), 1000))
    except ValueError:
        limit = 200
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM admin_audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM admin_audit_log").fetchone()[0]
    actors = identity.user_display_batch(list({r["actor_user_id"] for r in rows})[:200])
    out = []
    for r in rows:
        d = dict(r)
        d["actor_email"] = actors.get(r["actor_user_id"], {}).get("email")
        out.append(d)
    return {"entries": out, "total": total}


# =================================================================== SHARES ==

@app.get("/api/shares")
async def list_shares(request: Request):
    user, org = require_admin(request)
    conn = get_conn()
    shares = []
    share_rows = conn.execute("SELECT * FROM shares WHERE org_id=? ORDER BY created_at DESC",
                              (org["org_id"],)).fetchall()
    audit_rows = {r["token"]: conn.execute(
        "SELECT sa.action, sa.at, sa.user_id FROM share_audit sa "
        "WHERE sa.share_token=? ORDER BY sa.at", (r["token"],)).fetchall() for r in share_rows}
    actors = identity.user_display_batch([a["user_id"] for rows_ in audit_rows.values() for a in rows_])
    for r in share_rows:
        audit = [{"action": a["action"], "at": a["at"],
                  "email": (actors.get(a["user_id"]) or {}).get("email")} for a in audit_rows[r["token"]]]
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
    body = await _json(request)
    kind = body.get("kind")
    if kind not in ("boardpack", "dashboard"):
        raise HTTPException(400, "Unknown share type")
    config = body.get("config") or {}
    if kind == "boardpack":
        conn = get_conn()
        if not conn.execute("SELECT 1 FROM board_packs WHERE pack_id=? AND org_id=?",
                            (config.get("pack_id"), org["org_id"])).fetchone():
            raise HTTPException(404, "Board pack not found")
    if kind == "dashboard":
        # snapshot the shared dashboard's card selection (question_id/row_id/size only —
        # per-slot cuts are dropped so a bespoke peer group is never exposed on a public
        # link). The link then renders THESE cards, not the org's team-default layout.
        lay = config.get("layout")
        clean = []
        if isinstance(lay, list):
            for s in lay[:24]:
                if isinstance(s, dict) and s.get("question_id"):
                    clean.append({"question_id": str(s["question_id"]),
                                  "row_id": s.get("row_id"),
                                  "size": 2 if s.get("size") == 2 else 1})
        if clean:
            config["layout"] = clean
        else:
            config.pop("layout", None)
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
    org_name = (identity.org_display(org["org_id"]) or {}).get("name")
    config = uj(share["config_json"], {})
    pseudo_user = {"role": "viewer"}
    entitled = make_entitled(pseudo_user, org)
    if share["kind"] == "boardpack":
        row = conn.execute("SELECT * FROM board_packs WHERE pack_id=? AND org_id=?",
                           (config.get("pack_id"), org["org_id"])).fetchone()
        if not row:
            raise HTTPException(404, "Board pack not found")
        return {"kind": "boardpack", "org_name": org_name,
                "payload": uj(row["payload_json"]), "narrative": uj(row["narrative_json"]),
                "created_at": row["created_at"]}
    # dashboard share: overview + the org's pinned/starter cards under a fixed cut.
    # The client stores cut as a dim STRING plus a separate cut_value (not a dict), so
    # rebuild the {dim,value} shape the engine expects — a bare string here used to 500.
    raw_cut = config.get("cut")
    cut = raw_cut if isinstance(raw_cut, dict) else {"dim": raw_cut or "all", "value": config.get("cut_value")}
    if cut.get("dim") in ("twin", "group"):
        cut = {"dim": "all"}  # bespoke groups never exposed on anonymous links
    answers = pos.get_org_answers(conn, org["org_id"], CURRENT_SNAPSHOT)
    items = pos.position_items(org["org_id"], cut, org_visible_questions(org), payloads(), answers, entitled, None)
    # headline scoped to the Substance pool (Provision presence included) so the
    # public share link agrees with the dashboard gauge
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org), payloads(), answers, entitled, None)
    summary = pos.overview_summary(items, mp_config=pos.market_position_config(), practice_items=prac_items,
                                   band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH)
    # verdict-source unification reaches the ANONYMOUS link too (pre-prod audit
    # 2026-08-12): without these maps assemble_card fell back to the legacy
    # percentile read, so a shared card could disagree with the member's own view
    # of the same metric. Share cuts are never twin/group (rewritten above), so
    # tb=None makes these maps equal the member dashboard's for the same cut.
    band_map = pos.pool_market_bands(items, prac_items, pos.market_position_config(),
                                     MARKET_BAND_LOW, MARKET_BAND_HIGH, VERDICT_NET_LEAN)
    prev_band_map = pos.pool_prevalence_bands(
        pos.prevalence_items(org["org_id"], cut, org_visible_questions(org), payloads(), answers, entitled, None),
        UNCOMMON_PCT)
    co = pos.callouts(items, org_visible_questions(org), k=3)
    cards = []
    # prefer the dashboard's own snapshot (set at share time) so the link shows the
    # cards the user actually shared; fall back to the org team-default, then to an
    # auto strengths/gaps selection for links created before this field existed.
    cfg_layout = config.get("layout")
    if isinstance(cfg_layout, list) and cfg_layout:
        layout = cfg_layout
    else:
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
        cards.append(assemble_card(q, p, org, answers, cut, None, entitled,
                                   market_band=band_map.get(qid), prevalence_band=prev_band_map.get(qid)))
    return {"kind": "dashboard", "org_name": org_name, "cut": cut,
            "headline": summary,
            "callouts": {"strengths": [c["text"] for c in co["strengths"]],
                         "gaps": [c["text"] for c in co["gaps"]]},
            "cards": cards,
            # CUT-SCOPED peer-group size (2026-07-09 ship review, blocker B5): the
            # share page renders peer_pool.responding_orgs beside the cut label, so
            # serving the global meta made a 15-org sector cut read "(220
            # organisations)" next to callouts citing n=15 on the same page. Serve
            # the SAME number the in-app header shows for this cut (_cut_peer_n,
            # D4 counts-reconciliation ruling); for the all-peers cut _cut_peer_n
            # returns responding_orgs itself. Also stops shipping the full
            # per-industry/per-band pool breakdown on an anonymous public link —
            # the page only ever read this one field.
            # cut_n: the top-level field share.js PREFERS (B5 integration fix — the two
            # halves landed under different names; serving both closes the seam, and old
            # links keep working via the peer_pool fallback on all-peers cuts).
            "cut_n": _cut_peer_n(conn, org, cut),
            "peer_pool": {"responding_orgs": _cut_peer_n(conn, org, cut)}}


# ================================================================== STATIC ===

@app.get("/share/{token}")
async def share_page(token: str):
    return FileResponse(os.path.join(WEB_DIR, "share.html"))


@app.get("/")
async def index():
    # public marketing front door; the app lives at /app (its "Log in" target).
    # marketing.html bounces any incoming app-route hash (/#/reset/… etc.) to /app.
    return FileResponse(os.path.join(WEB_DIR, "marketing.html"))


@app.get("/pricing")
async def pricing_page():
    return FileResponse(os.path.join(WEB_DIR, "pricing.html"))


@app.get("/security")
async def security_page():
    return FileResponse(os.path.join(WEB_DIR, "security.html"))


@app.get("/methodology")
async def methodology_page():
    return FileResponse(os.path.join(WEB_DIR, "methodology.html"))


@app.get("/sample-board-pack")
async def sample_board_pack_page():
    return FileResponse(os.path.join(WEB_DIR, "sample-board-pack.html"))


@app.get("/app")
async def app_shell():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return FileResponse(os.path.join(WEB_DIR, "robots.txt"), media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    return FileResponse(os.path.join(WEB_DIR, "sitemap.xml"), media_type="application/xml")


@app.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    return FileResponse(os.path.join(WEB_DIR, "llms.txt"), media_type="text/plain; charset=utf-8")


@app.get("/llms-full.txt", include_in_schema=False)
async def llms_full_txt():
    return FileResponse(os.path.join(WEB_DIR, "llms-full.txt"), media_type="text/plain; charset=utf-8")


# Brand assets at the document root (browsers request /favicon.ico by default,
# and the lumi_brand_kit head snippet uses root paths). Served from web/.
for _bn, _mt in (("favicon.ico", None), ("lumi_favicon.svg", "image/svg+xml"),
                 ("apple-touch-icon.png", None), ("lumi_app_navy_192.png", None),
                 ("lumi_app_navy_512.png", None),
                 ("manifest.webmanifest", "application/manifest+json")):
    def _brand_asset(name=_bn, media=_mt):
        async def _serve():
            return FileResponse(os.path.join(WEB_DIR, name), media_type=media) if media \
                else FileResponse(os.path.join(WEB_DIR, name))
        return _serve
    app.add_api_route("/" + _bn, _brand_asset(), methods=["GET"], include_in_schema=False)


class _CachedStatic(StaticFiles):
    """§4.10(4): assets are ?v=N-versioned, so a versioned request is immutable — cache it hard
    (a ?v bump busts it). Unversioned requests keep the default (revalidating) behaviour, so a
    stale asset can never be pinned for a year."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if b"v=" in scope.get("query_string", b""):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


app.mount("/static", _CachedStatic(directory=WEB_DIR), name="static")


@app.get("/healthz")
async def healthz():
    """Unauthenticated liveness/readiness probe for the process supervisor, the
    reverse proxy and uptime monitoring. Confirms BOTH datastores answer a trivial
    query; returns nothing else (no counts, paths or config). 200 healthy, 503 not."""
    try:
        get_conn().execute("SELECT 1")
        identity.get_conn().execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        log.error("healthz failed: %s", e)
        return JSONResponse({"status": "error"}, status_code=503)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc):
    """Last-resort handler: log the failure with method+path (and org/user when
    resolved) at ERROR so it can be alerted on, and return a clean response — never
    a stack trace — to the client."""
    who = ""
    try:
        u = getattr(request.state, "user", None)
        if u:
            who = " user=%s org=%s" % (u.get("user_id"), (getattr(request.state, "org", None) or {}).get("org_id"))
    except Exception:
        pass
    log.error("unhandled error %s %s%s: %s", request.method, request.url.path, who, exc, exc_info=True)
    # roll back both stores: routes share thread-local connections with implicit
    # transactions, so a failure mid-way through a multi-statement write otherwise
    # leaves dirty pending rows that the NEXT request's commit would persist
    # (pre-prod audit 2026-08-12)
    for _rb in (get_conn, identity.get_conn):
        try:
            _rb().rollback()
        except Exception:
            pass
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)
    return HTMLResponse(status_code=500, content="<!doctype html><meta charset=utf-8>"
                        "<title>Something went wrong · lumi</title>"
                        "<p style='font-family:system-ui;text-align:center;margin-top:20vh'>"
                        "Something went wrong. Please try again.</p>")


@app.exception_handler(404)
async def not_found(request: Request, exc):
    """A mistyped public URL (a PA re-typing a share link) gets a branded page,
    not raw API JSON. API paths keep their JSON contract."""
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return HTMLResponse(status_code=404, content="""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Page not found · lumi</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:Inter,system-ui,sans-serif;background:#FBF9F6;color:#211B26;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}
.card{background:#fff;border:1px solid #EAE5DE;border-radius:16px;padding:40px 48px;max-width:420px}
.logo{font-weight:700;font-size:22px;color:#2048B0}.logo span{color:#F08C6E}
p{color:#5B5560;line-height:1.5}a{color:#2E62D9}</style></head>
<body><div class="card"><div class="logo">lumi<span>.</span></div>
<h1 style="font-size:20px">That page doesn't exist</h1>
<p>The link may have been mistyped or may have expired. If someone shared a lumi link
with you, ask them to check it — shared links can be revoked or time out.</p>
<p><a href="/">Go to lumi</a></p></div></body></html>""")


# ================================================================== STARTUP ==

# the demo org, by its exact normalized_name (identity-side key). One visible line to
# change if a reseed renames it — a miss no longer silently falls back (ruled 2026-07-30).
DEMO_ORG_NORMALIZED = identity.DEMO_ORG_NORMALIZED   # P3: single definition, identity-side
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


def _validate_prod_config():
    """Boot-time guard against the config mistakes that would silently ship an
    insecure or broken production instance. 'Production posture' is detected by an
    https LUMI_BASE_URL (localhost/dev is http). Fatal misconfigurations REFUSE to
    boot (raise) with the exact fix; softer ones log a prominent warning. Escape
    hatch LUMI_ALLOW_NO_MFA=on exists only for a deliberate, documented exception."""
    base = (os.environ.get("LUMI_BASE_URL") or "").strip().lower()
    prod = base.startswith("https://")
    on = lambda k: os.environ.get(k, "").lower() in ("on", "1", "true", "yes")
    fatal = []
    if prod:
        if on("LUMI_SEED_DEMO"):
            fatal.append("LUMI_SEED_DEMO is on — this would create demo accounts with KNOWN passwords "
                         "in production (Cyber Essentials A5.2/A5.3). Unset it.")
        if not on("LUMI_MFA") and not on("LUMI_ALLOW_NO_MFA"):
            fatal.append("LUMI_MFA is not on — production must enforce MFA (Cyber Essentials A7.16/A7.17). "
                         "Set LUMI_MFA=on (and configure SMTP), or set LUMI_ALLOW_NO_MFA=on to override deliberately.")
        if on("LUMI_MFA") and not os.environ.get("LUMI_SMTP_HOST"):
            fatal.append("LUMI_MFA is on but LUMI_SMTP_HOST is unset — sign-in codes would be console-logged, "
                         "not emailed, locking every user out. Configure SMTP (SES) before enforcing MFA.")
        # dev/QA-only switches that must never survive into production (launch
        # rehearsal 2026-08-13 — the validator was silent on both):
        if on("LUMI_QA_SEAMS"):
            fatal.append("LUMI_QA_SEAMS is on — fault-injection seams let request bodies trigger "
                         "mid-write failures. Gate runs only; unset it.")
        if on("LUMI_OPEN_REGISTRATION"):
            fatal.append("LUMI_OPEN_REGISTRATION is on — membership is staff-provisioned; open "
                         "self-registration must be a deliberate product decision, not an env leftover. Unset it.")
    if fatal:
        raise RuntimeError("Refusing to start — production config errors:\n  - " + "\n  - ".join(fatal))
    # single-instance assumptions: the in-memory rate limiter (auth.py), the signal
    # scheduler thread, and the lru_cache'd question library are per-process. More than
    # one worker silently weakens login throttling and can serve a stale library.
    try:
        wc = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        wc = 1
    if wc > 1:
        print("[lumi] ⚠ WEB_CONCURRENCY=%d — lumi assumes a SINGLE worker. Multiple workers weaken the "
              "in-memory login rate limiter and can serve a stale question library, and would duplicate "
              "the signal digest. Run --workers 1 (behind a reverse proxy) unless these are addressed." % wc,
              flush=True)


@app.on_event("startup")
def startup():
    _validate_prod_config()
    init_schema()
    identity.init_identity_db()   # self-create the identity store like the reward store (was __main__-only)
    # AI go-live status — ONE grep-able line printed on every boot, so a restart
    # confirms at a glance exactly what's live (the go-live switches are env-only by
    # design). "LIVE — paid Claude" needs all three: the master gate, LUMI_AI_LIVE=on,
    # and a key; miss any and members get the deterministic draft.
    _key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    _live = os.environ.get("LUMI_AI_LIVE", "").lower() == "on"
    _feats = [n for n, on in (("commentary", AI_COMMENTARY), ("analyst", AI_ANALYST),
              ("pulse", AI_PULSE), ("boardpack", AI_BOARDPACK), ("strategy", AI_STRATEGY),
              ("domain_summary", AI_DOMAIN_SUMMARY)) if on]
    _real = AI_INSIGHTS_ENABLED and _live and _key
    print("[lumi] AI INSIGHTS: %s | model: %s (LUMI_AI_LIVE=%s, key=%s) | consent=%s | features: %s"
          % ("ON" if AI_INSIGHTS_ENABLED else "OFF (set LUMI_AI_INSIGHTS_ENABLED=on)",
             "LIVE — paid Claude calls" if _real else "deterministic draft (no live model)",
             "on" if _live else "off", "present" if _key else "ABSENT",
             AI_CONSENT_MODE, ", ".join(_feats) or "none"), flush=True)
    conn = get_conn()
    # core-set governance: backfill the library's versioning fields (one-time)
    # and capture the baseline release if none exists. Both idempotent.
    if releases.ensure_governance_backfill(conn):
        load_questions.cache_clear()
    releases.ensure_baseline(conn)
    global INDUSTRIES
    pool = get_meta("peer_pool", {})
    INDUSTRIES = sorted(pool.get("industries", {}).keys())
    # Demo accounts carry KNOWN, printed-at-startup credentials — a convenience for
    # dev/QA only. Auto-creating guessable-password accounts (and logging the
    # passwords) in production would fail Cyber Essentials A5.2 (unnecessary accounts)
    # and A5.3 (default/guessable passwords). So provisioning is gated OFF by default
    # and only happens when LUMI_SEED_DEMO is explicitly set (run_gates.sh sets it;
    # dev sets it). Production leaves the demo accounts unprovisioned.
    if os.environ.get("LUMI_SEED_DEMO", "").lower() not in ("on", "1", "true", "yes"):
        print("[lumi] demo accounts: not provisioned (LUMI_SEED_DEMO off — production default).")
    else:
        # normalized_name is an identity column post-split, so the org is resolved
        # through identity.py; the classified check stays reward-side. NO arbitrary-org
        # fallback: a miss provisions nothing and says so.
        demo_ident = identity.org_lookup_by_normalized(DEMO_ORG_NORMALIZED)
        demo_org = None
        if demo_ident is not None:
            demo_org = conn.execute("SELECT * FROM orgs WHERE org_id=? AND classified=1",
                                    (demo_ident["org_id"],)).fetchone()
        if demo_org is None:
            print("[lumi] demo org %r did not resolve (%s) — demo accounts not provisioned; "
                  "no fallback org used."
                  % (DEMO_ORG_NORMALIZED,
                     "no identity record" if demo_ident is None
                     else "identity record found, but the org is not classified"))
        else:
            for (email, pw), role in ((DEMO_ADMIN, "admin"), (DEMO_VIEWER, "viewer"),
                                      (DEMO_CONTRIBUTOR, "contributor")):
                if not auth_lib.find_user(email):
                    auth_lib.create_user(demo_org["org_id"], email, pw, role,
                                         "Demo %s" % role.title())
            print("\n[lumi] Demo accounts on org '%s':" % demo_ident["name"])
            print("       Admin      : %s / %s" % DEMO_ADMIN)
            print("       Contributor: %s / %s" % DEMO_CONTRIBUTOR)
            print("       Viewer     : %s / %s\n" % DEMO_VIEWER)
    backfill_terms(conn)
    # proactive signal alerts (the marketing "we email you when it moves"): the
    # nightly sweep + email digest. Env-gated OFF by default so dev/tests/QA never
    # start it; set LUMI_SIGNAL_SWEEP=on in production (SINGLE instance) to email
    # members when their position moves. Emails actually leave only once
    # LUMI_SMTP_HOST is set — otherwise they are console-logged.
    if os.environ.get("LUMI_SIGNAL_SWEEP", "").lower() == "on":
        import threading
        threading.Thread(target=_signal_scheduler, name="lumi-signal-sweep", daemon=True).start()
        print("[lumi] SIGNAL SCHEDULER: ON — daily sweep + email digest at %02dh UTC | SMTP: %s"
              % (int(os.environ.get("LUMI_SWEEP_HOUR", "7")) % 24,
                 "configured" if os.environ.get("LUMI_SMTP_HOST") else "NOT set (emails console-logged)"), flush=True)
    else:
        print("[lumi] SIGNAL SCHEDULER: OFF (set LUMI_SIGNAL_SWEEP=on for proactive alerts)", flush=True)
    # PH-CFG-1 Branch A boot log (§4.2 successor): the VALUE is logged at every
    # boot; the boot never refuses. Enforcement lives at the ACTION — base_url(
    # minting=True) refuses to mint links while unset/misconfigured.
    _b = base_url()
    if _b is None:
        print("[lumi] ⚠ LUMI_BASE_URL UNSET — invite/reset link MINTING IS DISABLED "
              "(each attempt gets a 503 naming the fix). Set LUMI_BASE_URL "
              "(production: https://your-domain; dry-run: http://localhost:8060).", flush=True)
    elif "localhost" in _b or "127.0.0.1" in _b:
        print("[lumi] LUMI_BASE_URL = %s (localhost dry-run value — links mint but are "
              "dead for real recipients; fine for gates/dev, not for go-live)." % _b, flush=True)
    else:
        print("[lumi] LUMI_BASE_URL = %s" % _b, flush=True)
