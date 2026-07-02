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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import auth as auth_lib
import hashlib

import claude_api
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
DOMAIN_MIN_POLARISED = int(os.environ.get("LUMI_DOMAIN_MIN_POLARISED", "5"))
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
AI_CONSENT_MODE = os.environ.get("LUMI_AI_CONSENT_MODE", "opt_out").lower()
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
    completion = completion_pct(conn, org)
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
        "pending_changes": pending_changes,
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


def require_platform_admin(request):
    """lumi-staff tier (back office, D2). ABOVE the org roles: a cross-tenant
    privilege, so it deliberately returns NO org — every /api/admin/* route
    reads across tenants explicitly and must never scope to one org. The flag
    rides on request.state.user (get_session_user does SELECT u.*), so it is
    checked on every request like any other session fact."""
    if request.state.user is None:
        raise HTTPException(401, "Not signed in")
    if not request.state.user.get("platform_admin"):
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


def assemble_card(q, p, org, org_answers, cut, twin_blocks_by_q, entitled, market_band=None, prevalence_band=None):
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
        # firewall-reviewed market position (below/at/above), from the SAME Substance pool
        # the competitiveness gauge/donut counts (positions.pool_market_bands). null when
        # the metric isn't a positioned market rate (Approach / neutral / lower_is_better /
        # non-competitive / unclassified). Passed in per-request so a card's band can never
        # disagree with the donut count it sums into (Pass 2a, 2026-06-27).
        "market_band": market_band,
        # practice-prevalence band (match / common_alt / rarer) from the SAME prevalence_items
        # pool the §1 prevalence donut counts; null when not a prevalence-rated practice. Drives
        # the second (prevalence) chip dimension (prevalence-filtering Pass A, 2026-06-28).
        "prevalence_band": prevalence_band,
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
    # AI Insights consent — UNBUNDLED from the platform terms (a separate, unticked-by-default
    # acknowledgment). opt_in: record only if the member explicitly ticked it; opt_out: no
    # record needed (absence of a withdrawal = active under legitimate interest). Never blocks
    # account creation — a member can decline AI and still use lumi.
    if AI_CONSENT_MODE == "opt_in" and body.get("accept_ai_insights") is True:
        record_ai_consent(conn, org_id, uid)
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
    # AI features are now EFFECTIVE flags: master gate AND the member's consent AND the
    # per-feature kill-switch. So every existing client gate (me.features.X) automatically
    # respects the master switch + consent with no client change. ai_insights carries the
    # gate state for the settings toggle + the consent prompt.
    _aig = ai_gate(conn, user)
    return {
        "contribution": contrib,
        "features": {"commentary": ai_feature_on(_aig, AI_COMMENTARY), "analyst": ai_feature_on(_aig, AI_ANALYST),
                     "boardpack": ai_feature_on(_aig, AI_BOARDPACK), "pulse_ai": ai_feature_on(_aig, AI_PULSE),
                     "domain_summary": ai_feature_on(_aig, AI_DOMAIN_SUMMARY)},
        "ai_insights": _aig,
        # the market band the engine uses (LUMI_MARKET_BAND) so the client colours
        # cards on the SAME line as the tiles + signals — single source of truth.
        "config": {"market_band": [MARKET_BAND_LOW, MARKET_BAND_HIGH]},
        "scope": {"superpowers": ACTIVE_SUPERPOWERS or sorted({q.superpower for q in vis.values()}),
                  "focused": bool(ACTIVE_SUPERPOWERS),
                  "question_count": len(vis)},
        "user": {"email": user["email"], "role": user["role"], "display_name": user["display_name"],
                 "platform_admin": bool(user.get("platform_admin"))},
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
    # the report: give-to-get scoped to THIS pulse — participants only, PLUS the
    # sponsor that launched it (a paying self-service owner always sees its
    # results). Below the floor, the honest holding state is shown (never blank).
    view["is_owner"] = bool(p["owner_org_id"] and p["owner_org_id"] == org["org_id"])
    if view["participated"] or view["is_owner"]:
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
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_PULSE)
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
    # AI Insights consent is PER-USER (not inherited from the org) — each joiner decides for
    # themselves via the same unbundled, unticked acknowledgment (opt_in mode).
    if AI_CONSENT_MODE == "opt_in" and body.get("accept_ai_insights") is True:
        record_ai_consent(conn, row["org_id"], uid)
    conn.execute("UPDATE invites SET used_at=datetime('now') WHERE token=?", (row["token"],))
    conn.commit()
    token = auth_lib.create_session(uid)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(auth_lib.COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=auth_lib.SESSION_TTL_DAYS * 86400)
    return resp


@app.post("/api/ai-consent")
async def ai_consent(request: Request):
    """Member-level AI Insights consent toggle — the Settings switch AND the consent gate.
    Records a consent or a withdrawal event in the immutable terms_acceptances audit log;
    the gate re-reads the latest event next request, so withdrawal closes the gate at once.
    Per-user (each member decides for themselves), versioned (pins AI_TERMS_VERSION)."""
    user, org = require_user(request)
    body = await request.json()
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
                "n": (p.get("all") or {}).get("n", 0), "reduced": True,
            })
            continue
        cards.append(assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None,
                                   entitled, market_band=band_map.get(qid),
                                   prevalence_band=prev_band_map.get(qid)))
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
    # "Apply my strategy" toggle (?strategy=off): read the dashboard WITHOUT the stance
    # lens — absolute RAG colours, impact-ordered signals, plain verdict (no aim/target).
    # Reuses the engine's strategy=None degrade path (§5.5); the org's strategy still
    # EXISTS (strategy_complete stays true) — it's simply not applied this request.
    apply_strategy = request.query_params.get("strategy") != "off"
    _strategy = _strategy_full if apply_strategy else None   # None → legacy hero + legacy signal order
    summary = pos.overview_summary(items, mp_config=mp_cfg, practice_items=prac_items,
                                   band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH)
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
    _statuses = {r["question_id"]: r["status"] for r in conn.execute(
        "SELECT question_id, status FROM signal_actions WHERE org_id=? AND user_id=?",
        (org["org_id"], user["user_id"]))}
    # step-3 layer 4: per-domain alignment map from the layer-3 hero output (the SINGLE
    # source of truth — alignment is NOT recomputed in signals.py, which has no domain
    # aggregate verdict). {domain: alignment} over competitive domains that carry a target;
    # strategy-off → every target None → empty map → nothing confirms → the signal set
    # degrades byte-identical. Drives confirm-suppression inside build_signals.
    _dom_align = {d["name"]: (d.get("target") or {}).get("alignment")
                  for d in hero["domains"] if d.get("target")}
    sigs = signals_mod.build_signals(items, money, _visq, _get_block, _answers,
                                     conn=conn, org_id=org["org_id"], statuses=_statuses,
                                     strategy=_strategy, domain_alignment=_dom_align)
    # full uncapped set for the dedicated Signals explore page (home stays capped)
    sigs_all = signals_mod.build_signals(items, money, _visq, _get_block, _answers,
                                         conn=conn, org_id=org["org_id"], cap=False, statuses=_statuses,
                                         strategy=_strategy, domain_alignment=_dom_align)
    # new-since-last-seen: a signal is NEW until the user has viewed it on the
    # Signals page. Annotate both sets + count the un-dismissed new ones.
    _seen = {r["sig_id"] for r in conn.execute(
        "SELECT sig_id FROM signal_seen WHERE org_id=? AND user_id=?",
        (org["org_id"], user["user_id"]))}
    for s in sigs_all:
        s["new"] = (s.get("sig_id") or s["question_id"]) not in _seen
    _new_ids = {(s.get("sig_id") or s["question_id"]) for s in sigs_all}  # current sig_ids
    for s in sigs:
        s["new"] = (s.get("sig_id") or s["question_id"]) not in _seen
    signals_new = sum(1 for s in sigs_all if s["new"] and s.get("status") != "dismissed")
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
        "org": {"name": org["name"], "industry": org["industry"], "fte_band": org["fte_band"],
                "hq_region": org["hq_region"], "classified": bool(org["classified"])},
        "cut": cut,
        "peer_pool": pool,
        "snapshot": {"date": snap["snapshot_date"], "window": snap["collection_window"]},
        "headline": summary,
        "contribution": contrib,
        "hero": hero,
        "signals": sigs,
        "signals_all": sigs_all,
        "signals_new": signals_new,
        # reward strategy completion — drives the dashboard nudge for Admins who
        # haven't set their stance yet (the engines read None = legacy until then)
        "strategy_complete": bool(conn.execute(
            "SELECT 1 FROM org_strategy WHERE org_id=? AND completed_at IS NOT NULL",
            (org["org_id"],)).fetchone()),
        # whether the stance lens is APPLIED on this request (the "Apply my strategy"
        # toggle) — distinct from strategy_complete (does one EXIST). False = absolute view.
        "strategy_applied": bool(_strategy),
        "strategy_can_edit": user["role"] == "admin",
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
    on_plan = [d["name"] for d in domains if d.get("competitive", True)
               and d["name"] in strategy_diag._COMPETITIVE and d["verdict"] and d["name"] not in flagged]
    obj_label = OBJECTIVE_LABELS.get(strat.get("primary_objective")) if (
        (strat.get("provenance") or {}).get("primary_objective") != "skipped") else None
    payload = strategy_diag.build_diagnosis_payload(
        strat, findings, (hero.get("market") or {}).get("target"), obj_label, on_plan,
        bool(get_meta("synthetic_pool", False)))
    res = claude_api.generate_strategy_diagnosis(payload)
    # Signpost: attach each finding's domain so the Signals page can deep-link the
    # narrative to the matching signal group. The validator guarantees the narrated
    # findings match the computed `findings` 1:1 and in order, so a positional zip is
    # safe; the on-plan affirmation has no computed findings, so it carries no domain.
    parts = res["parts"]
    nf = parts.get("findings") or []
    if len(nf) == len(findings):
        for narrated, computed in zip(nf, findings):
            narrated["area"] = computed.get("area")
    return {"ok": True, "parts": parts, "source": res["source"],
            # on_plan = competitive domains tracking with intent (engine-derived, not
            # model output) — the frontend renders them as a quiet "on plan" line that
            # can still signpost to each domain's signals.
            "on_plan": on_plan,
            "caveats": {"illustrative": payload["illustrative_sample_data"]}}


# ============================================================ NOTIFICATIONS ==

def org_signals(conn, org):
    """The org's full (uncapped) signal set on the default all-peers cut, built
    request-free for the nightly sweep — the same machinery /api/overview uses,
    minus the per-user triage status (identity/value don't depend on it).
    STRATEGY-AWARE (step-3 notification coherence, ruling C): threads the org's strategy +
    per-domain alignment exactly as /api/overview does, so confirm-suppression fires HERE too —
    confirming non-risk signals carry s["confirm"] (the event layer quiets them; risk_framed stays
    exempt by the same not-risk_framed gate). The peer cut stays the canonical all-peers frame
    (RULED). strategy None / no override → empty alignment map → no confirm flags → byte-identical
    to the pre-coherence (strategy-blind) sweep (degrade)."""
    cut = {"dim": "all", "value": None}
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
    for row in conn.execute("SELECT * FROM orgs"):
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
            if not seen_before:
                notifications.record_baseline(conn, oid, fresh)   # silent: establish baseline
                swept += 1
                continue
            events = notifications.diff_and_record(conn, oid, fresh)
            if events:
                notifications.fan_out(conn, oid, events)
            swept += 1
            total_events += len(events)
        except Exception as e:
            print("[lumi] signal sweep failed for org %s: %s" % (org.get("org_id"), e))
    if verbose:
        print("Signal sweep: %d unlocked orgs, %d change events recorded" % (swept, total_events))
    return swept, total_events


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


@app.get("/api/data-overview")
async def data_overview(request: Request):
    """Completion-first view of the org's own data: overall + per-domain
    progress and, per domain, every question with its answered status and the
    submitted value. Drives the Your-data landing + per-domain drill-down."""
    user, org = require_user(request)
    conn = get_conn()
    answers = org_answers_for(org)                       # {(qid,row): value}
    questions = org_visible_questions(org)
    by_q = {}
    for (qid, row_id), value in answers.items():
        by_q.setdefault(qid, []).append((row_id, value))
    basis = {q.id for q in completion_basis_questions()}
    domains = {}
    for qid, q in questions.items():
        sec = q.sub_power or "General"
        d = domains.setdefault(sec, {"name": sec, "order": 999, "questions": []})
        d["order"] = min(d["order"], q.sub_power_order or 999)
        ans = by_q.get(qid)
        rowdefs = dict(q.matrix_row_defs()) if q.type == "matrix" else {}
        item = {"question_id": qid, "title": q.display_title, "question": q.text,
                "type": q.type, "unit": q.unit_block(), "answered": bool(ans),
                "required": qid in basis, "value": None, "rows": None}
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
        d["questions"].sort(key=lambda x: (not x["answered"], x["title"]))
        tot = len(d["questions"]); ansd = sum(1 for x in d["questions"] if x["answered"])
        d["total"] = tot; d["answered"] = ansd
        d["pct"] = round(100.0 * ansd / tot) if tot else 0
        out.append(d)
    out.sort(key=lambda d: d["order"])
    tot = sum(d["total"] for d in out); ansd = sum(d["answered"] for d in out)
    return {
        "contribution": contribution_state(conn, org),
        "total": tot, "answered": ansd,
        "pct": round(100.0 * ansd / tot) if tot else 0,
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


def _dash_meta(row, vis):
    return {"id": row["dashboard_id"], "name": row["name"], "position": row["position"],
            "count": len(_dash_visible_layout(row, vis)), "updated_at": row["updated_at"]}


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
                   "position": active["position"], "layout": _dash_visible_layout(active, vis)},
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
            "layout": _dash_visible_layout(row, vis)}


@app.post("/api/dashboards")
async def create_dashboard(request: Request):
    user, org = require_user(request)
    body = await request.json()
    conn = get_conn()
    _ensure_dashboards(request, org, user, conn)
    name = (body.get("name") or "New dashboard").strip()[:60] or "New dashboard"
    layout = []
    clone = body.get("clone_from")
    if clone:
        src = _own_dashboard(conn, clone, org, user)
        if src:
            layout = uj(src["layout_json"], [])
    # create-with-a-card (the "+ New dashboard" option in the card picker)
    with_card = body.get("with_card")
    if with_card and not any(s.get("question_id") == with_card for s in layout):
        layout = layout + [{"question_id": with_card, "size": 1}]
    pos = conn.execute("SELECT COALESCE(MAX(position),-1)+1 p FROM dashboards WHERE org_id=? AND user_id=?",
                       (org["org_id"], user["user_id"])).fetchone()["p"]
    did = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO dashboards(dashboard_id, org_id, user_id, name, layout_json, position) VALUES (?,?,?,?,?,?)",
        (did, org["org_id"], user["user_id"], name, j(layout), pos))
    conn.execute("UPDATE users SET active_dashboard_id=? WHERE user_id=?", (did, user["user_id"]))
    conn.commit()
    return {"id": did, "name": name, "position": pos, "layout": layout}


@app.put("/api/dashboards/{did}")
async def update_dashboard(did: str, request: Request):
    user, org = require_user(request)
    body = await request.json()
    conn = get_conn()
    row = _own_dashboard(conn, did, org, user)
    if row is None:
        raise HTTPException(404, "No such dashboard.")
    name = row["name"]
    if body.get("name") is not None:
        name = (body.get("name") or "").strip()[:60] or row["name"]
    layout_json = row["layout_json"]
    if body.get("layout") is not None:
        layout_json = j(body.get("layout") or [])
    conn.execute("UPDATE dashboards SET name=?, layout_json=?, updated_at=datetime('now') WHERE dashboard_id=?",
                 (name, layout_json, did))
    conn.commit()
    return {"ok": True, "name": name}


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
    body = await request.json()
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
    body = await request.json()
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
    body = await request.json()
    qid = (body.get("question_id") or "").strip()
    status = body.get("status")
    if not qid:
        raise HTTPException(400, "question_id required")
    conn = get_conn()
    if status in (None, "", "active", "new"):
        conn.execute("DELETE FROM signal_actions WHERE org_id=? AND user_id=? AND question_id=?",
                     (org["org_id"], user["user_id"], qid))
        status = None
    elif status in ("priority", "saved", "dismissed"):
        conn.execute(
            "INSERT INTO signal_actions(org_id, user_id, question_id, status, updated_at) "
            "VALUES (?,?,?,?,datetime('now')) "
            "ON CONFLICT(org_id, user_id, question_id) DO UPDATE SET status=excluded.status, updated_at=datetime('now')",
            (org["org_id"], user["user_id"], qid, status))
    else:
        raise HTTPException(400, "bad status")
    conn.commit()
    return {"ok": True, "question_id": qid, "status": status}


@app.post("/api/signals/seen")
async def signals_seen(request: Request):
    """Mark signals as seen for this user (clears their NEW state). The client
    posts the sig_ids it is currently showing — called when the Signals page is
    viewed. Idempotent."""
    user, org = require_user(request)
    body = await request.json()
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
    body = await request.json()
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
    body = await request.json()
    p = body.get("prefs") or {}
    clean = {
        "inbox_enabled": bool(p.get("inbox_enabled", True)),
        "email_frequency": p.get("email_frequency") if p.get("email_frequency") in ("off", "daily", "weekly") else "weekly",
        "lenses": [l for l in (p.get("lenses") or []) if l in notifications.ALL_LENSES] or notifications.ALL_LENSES,
        "events": [e for e in (p.get("events") or []) if e in notifications.ALL_EVENTS],
        "min_money_gbp": max(0, int(p.get("min_money_gbp") or 0)),
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
    """Manual trigger for the nightly sweep (no cron in this environment).
    Platform-admin only — recomputes change events and fans out notifications
    for EVERY org (a cross-tenant write), so it carries no org scope and must
    not be reachable by an ordinary org admin."""
    require_platform_admin(request)
    swept, events = run_signal_sweep(get_conn(), verbose=False)
    return {"ok": True, "orgs_swept": swept, "events": events}


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


# ============================================================== BENCHMARK CSV ==

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
    w.writerow(["question_id", "title", "subpower", "your_value",
                "p10", "p25", "p50", "p75", "p90", "n", "cut_label", "suppressed"])

    rows = []
    for qid, q in org_visible_questions(org).items():
        p = payloads().get(qid)
        if p is None:
            continue
        card = assemble_card(q, p, org, answers, cut, {qid: tb.get(qid)} if tb else None, entitled)
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

        rows.append([qid, q.display_title, q.sub_power, your_value,
                     *stats, card.get("n", 0), cut_label,
                     "true" if suppressed else "false"])

    rows.sort(key=lambda r: (r[2] or "", r[1] or ""))
    for r in rows:
        w.writerow(r)

    fname = "lumi-benchmark-%s.csv" % (cut.get("dim") or "all")
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % fname})


# ================================================================== ANALYST ==

@app.post("/api/analyst")
async def analyst(request: Request):
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_ANALYST)
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    conn = get_conn()
    vis = org_visible_questions(org)

    # Intent routing: finding a metric, explaining a term, or how-to guidance go
    # to the GUIDE path (no peer data → can't cite a figure). Anything else is a
    # benchmark question and falls through to the strict, cited analyst below.
    intent, extra = guide.classify(question)
    if intent != "benchmark":
        return _guide_response(question, intent, extra, org, vis)

    contrib = contribution_state(conn, org)
    if contrib["reduced"]:
        return {"answer": "Your full benchmark is paused until your reward data is complete — "
                          "finish your submission and I'll have every comparison ready for you again.",
                "chips": [], "matched": [], "reduced": True}
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


def _depluralise(question):
    """Best-effort singularise each word so a plural find-query ('pensions',
    'allowances', 'bonuses') still matches the singular library term — the
    retrieval tokenizer doesn't stem. English plural rules, not naive 's'-strip
    (which mangles 'allowances'→'allowanc')."""
    def one(w):
        if len(w) > 4 and re.search(r"(?:ses|xes|zes|ches|shes)$", w):
            return w[:-2]                                  # bonuses->bonus, boxes->box
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]                                  # pensions->pension, allowances->allowance
        return w
    return " ".join(one(t) for t in question.lower().split())


def _guide_response(question, intent, extra, org, vis):
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
                "chips": [], "matched": [], "no_metric": True, "topic": question, "kind": "find"}

    links = guide.links_for(intent, extra)
    ctx = {"intent": intent, "question": question, "glossary": guide.GLOSSARY,
           "features": [{"answer": f["answer"], "route": f["route"], "cta": f["cta"]} for f in guide.FEATURES],
           "metrics": metas, "term": extra if intent == "term" else None,
           "organisation": {"name": org["name"]}}
    res = claude_api.guide_answer(ctx) if AI_ANALYST else {"ok": False}
    if res.get("ok"):
        answer = res["answer"]
        if res.get("links"):
            links = res["links"]
    else:
        answer = guide.deterministic_answer(intent, extra, question, bool(metas))
    return {"answer": answer, "chips": chips, "links": links, "matched": qids, "kind": intent}


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
    gaps = pos.top_gaps(items, 4)
    # mix: a couple of benchmark questions from the org's biggest gaps, plus
    # guide examples so members discover that Ask lumi also finds metrics,
    # explains terms and helps with the platform.
    starters = []
    for g in gaps[:3]:
        starters.append("How does our %s compare with similar organisations?" % pos._lower_first(g["label"]))
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
    return {"starters": starters[:6]}


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
        "cut": {"dim": cut["dim"], "value": cut.get("value")},   # for one-click regenerate
        "cut_criteria": cut.get("criteria"),                     # saved-group construction, printed on the methodology page
        "band": {"low": MARKET_BAND_LOW, "high": MARKET_BAND_HIGH},   # the on-market band (scale zones + callout)
        "methodology_version": 1,
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
             "peer_adoption_pct": r["peer_adoption_pct"], "n": r["n"]}
            for r in reg["rows"] if not r["suppressed"] and r["gap"] is not None and r["gap"] > 0
        ][:10],
        "maturity": reg["maturity"],
        # Tier 2 sections — every consumer (render + narrative) treats these as optional
        "by_section": {k: {"available": v["available"], "above": v["above"],
                           "below": v["below"], "inline": v["inline"]}
                       for k, v in (summary.get("by_section") or {}).items()},
        "signals": [{"name": s.get("name") or s.get("label_short"), "domain": s.get("domain"),
                     "stand": s.get("stand"), "tag": s.get("tag"),
                     "risk": bool(s.get("risk_framed")), "bucket": s.get("bucket")}
                    for s in _pack_sigs[:5]],
        "strategy": {"complete": _strat_done,
                     "objective": OBJECTIVE_LABELS.get(_strat.get("primary_objective")) if (
                         _strat and (_strat.get("provenance") or {}).get("primary_objective") != "skipped") else None},
        "movement": ("First benchmark period — movement appears from your next data cycle."
                     if _snap_count <= 1 else None),
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
            "percentile": int(round(i["percentile"])), "n": n, "cut_label": i["cut_label"],
            "p50_display": i["p50_display"], "superpower": i["superpower"],
            "polarity": i.get("polarity"), "favourable": i.get("favourable"),
            "p25_display": i.get("p25_display") if q_ok else None,
            "p75_display": i.get("p75_display") if q_ok else None,
            "p10_display": i.get("p10_display") if t_ok else None,
            "p90_display": i.get("p90_display") if t_ok else None}


@app.post("/api/boardpack/generate")
async def boardpack_generate(request: Request):
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_BOARDPACK)
    contrib = contribution_state(get_conn(), org)
    if not contrib["insights_unlocked"]:
        raise HTTPException(403, "Your board pack unlocks once you've answered %d%% of your key reward questions." % int(TARGET_PCT))
    body = await request.json()
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
    return {"pack_id": pack_id, "payload": uj(row["payload_json"]),
            "narrative": uj(row["narrative_json"]), "created_at": row["created_at"],
            "current_collection_window": snap["collection_window"] if snap else None,
            "previous": prev_summary}


@app.get("/api/boardpacks")
async def boardpacks_list(request: Request):
    user, org = require_user(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT b.pack_id, b.created_at, b.payload_json, b.narrative_json, u.display_name "
        "FROM board_packs b LEFT JOIN users u ON u.user_id = b.created_by "
        "WHERE b.org_id=? ORDER BY b.created_at DESC LIMIT 50",
        (org["org_id"],)).fetchall()
    packs = []
    for r in rows:
        p = uj(r["payload_json"], {})
        n = uj(r["narrative_json"], {})
        packs.append({"pack_id": r["pack_id"], "created_at": r["created_at"],
                      "cut_label": p.get("cut_label"), "collection_window": p.get("collection_window"),
                      "ai": not n.get("_fallback"), "created_by": r["display_name"]})
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


def strategy_state(conn, org):
    """The org's stored B/C strategy + provenance + Plane-A facts, shaped for the API."""
    r = conn.execute("SELECT * FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    row = dict(r) if r else {}
    strat = {f: row.get(f) for f in STRATEGY_ENUMS}
    strat["benefits_lead"] = uj(row.get("benefits_lead"), []) or []
    strat["domain_targets"] = uj(row.get("domain_targets"), {}) or {}   # step-3 layer 1 round-trip (no consumer yet)
    # competitive domains for the per-domain override UI (step-3 layer 2) — derived from the
    # SAME config source the save-route validation uses (_domains where competitive), so the
    # UI list and the validation can't drift. Governance (competitiveness=False) falls out.
    _mpc = pos.market_position_config()
    comp_domains = [d for d in (_mpc.get("_domains") or {}) if pos._mp_competitive(_mpc, d)]
    return {
        "strategy": strat,
        "provenance": uj(row.get("field_provenance"), {}) or {},
        "completed_at": row.get("completed_at"),
        "plane_a": _strategy_plane_a(org),
        "required": list(STRATEGY_REQUIRED),
        "benefits_options": STRATEGY_BENEFITS,
        "competitive_domains": comp_domains,
    }


@app.get("/api/strategy")
async def get_strategy(request: Request):
    user, org = require_user(request)
    out = strategy_state(get_conn(), org)
    out["can_edit"] = user["role"] == "admin"
    return out


@app.get("/api/strategy/suggestions")
async def get_strategy_suggestions(request: Request):
    """Reserved (spec §2.1/§3). v1 emits NO demographic suggestions — there is no
    life-stage signal to derive from, and a manufactured default would make the
    engines confidently wrong. The 'suggested' provenance value stays reserved."""
    require_user(request)
    return {"suggestions": {}}


@app.put("/api/strategy")
async def put_strategy(request: Request):
    """Admin-only upsert. Every field validated against its enum (400 on unknown,
    never silent coerce). completed_at is set server-side only when all three
    required dials are non-null — the gate is not UI-only."""
    user, org = require_admin(request)
    body = await request.json()
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
    _doms = _mpc.get("_domains", {})              # the canonical domain set (config = single source of truth)
    for dom, stance in dt.items():
        if stance not in STRATEGY_ENUMS["market_position"]:
            raise HTTPException(400, "'%s' isn't a valid market position for %s — use lag, match or lead." % (stance, dom))
        # reject UNKNOWN domains (absent from _domains — _mp_competitive defaults True for those)
        # AND non-competitive ones (Governance: present but competitiveness=False) — one gate, derived.
        if dom not in _doms or not pos._mp_competitive(_mpc, dom):
            raise HTTPException(400, "'%s' isn't a competitive reward domain that can carry a market-position target." % dom)
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
    prev = conn.execute("SELECT completed_at FROM org_strategy WHERE org_id=?", (org["org_id"],)).fetchone()
    complete = all(vals.get(f) for f in STRATEGY_REQUIRED)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    completed_at = (prev["completed_at"] if prev and prev["completed_at"] else None) or (now if complete else None)
    cols = list(STRATEGY_ENUMS) + ["benefits_lead", "domain_targets", "field_provenance", "updated_at", "completed_at"]
    row_vals = [vals[f] for f in STRATEGY_ENUMS] + [vals["benefits_lead"], vals["domain_targets"], json.dumps(prov), now, completed_at]
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
    out["domain_targets"] = uj(row.get("domain_targets"), {}) or {}   # step-3 layer 3: per-domain aims for the engine (null col → {} → every domain reads global)
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
    _gs = lambda i: {"metric": _gname(i), "adj_pctl": round(50.0 + i["distance"]), "n": i["n"]}  # integer percentile (no false precision)
    gaps = [_gs(i) for i in pos.top_gaps(dom_pool, 3)]
    strengths = [_gs(i) for i in pos.top_strengths(dom_pool, 3)]
    prev = d.get("prevalence") or {}
    appr = d.get("approach") or {}
    # alignment in DISPLAY vocabulary, present only strategy-on AND when a target exists
    # (target is None strategy-off by construction). on_target -> "on strategy" (D3).
    _ALIGN = {"behind": "behind strategy", "on_target": "on strategy", "ahead": "ahead of strategy"}
    tgt = d.get("target")
    alignment = _ALIGN.get((tgt or {}).get("alignment")) if (tgt and apply_strategy) else None
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
        "n": card["n"],
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
    body = await request.json()
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
                    "generated_at": row["created_at"], "caveats": caveats}
    res = claude_api.generate_metric_commentary(payload)
    conn.execute(
        "INSERT OR REPLACE INTO metric_commentary(org_id, question_id, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], qid, cut_key, phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False, "caveats": caveats}


@app.post("/api/domain-summary")
async def domain_summary(request: Request):
    """AI per-DOMAIN describe-only summary for one domain on one cut + strategy state:
    grounded ONLY in the metric-level figures the domain page shows (Pass 2a), validated
    post-generation, cached per org+domain+cut+strategy until the underlying numbers change.
    Mirrors /api/metric-commentary. Never errors on model failure — generate_domain_summary
    always returns the validated deterministic floor when the model is down or rejected."""
    user, org = require_user(request)
    require_ai(get_conn(), user, AI_DOMAIN_SUMMARY)
    body = await request.json()
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

    cut_key = dim + "::" + (value or "") + "::" + ("strat" if apply_strategy else "abs")
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
    res = claude_api.generate_domain_summary(payload)
    conn.execute(
        "INSERT OR REPLACE INTO domain_summary(org_id, domain, cut_key, payload_hash, text, source) "
        "VALUES (?,?,?,?,?,?)",
        (org["org_id"], name, cut_key, phash, j(res["parts"]), res["source"]))
    conn.commit()
    return {"parts": res["parts"], "source": res["source"], "cached": False, "caveats": caveats}


# ============================================================ METRIC REQUESTS ==

NOTIFY_EMAIL = os.environ.get("LUMI_NOTIFY_EMAIL", "david@lumi.example")


def send_notification(subject, body, to=None):
    """Best-effort email. SMTP isn't configured in this environment, so this
    logs to console like every other outbound mail; when LUMI_SMTP_HOST is set
    it sends for real with no other changes. Never raises — the stored row is
    the source of truth. `to` defaults to the ops inbox (NOTIFY_EMAIL) for
    internal alerts; member digests pass the member's address."""
    recipient = to or NOTIFY_EMAIL
    host = os.environ.get("LUMI_SMTP_HOST")
    if host:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = os.environ.get("LUMI_SMTP_FROM", "noreply@lumi.example")
            msg["To"] = recipient
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
    print("\n[lumi] EMAIL (not configured — logged only) to %s\n  Subject: %s\n%s\n" % (recipient, subject, body))
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
    body = await request.json()
    name = (body.get("metric_name") or "").strip()
    measures = (body.get("what_it_measures") or "").strip()
    matters = (body.get("why_it_matters") or "").strip()
    category = (body.get("suggested_category") or "").strip() or None
    missing = [lbl for v, lbl in ((name, "metric name"), (measures, "what it measures"),
                                  (matters, "why it matters")) if not v]
    if missing:
        raise HTTPException(400, "Required: " + ", ".join(missing) + ".")
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
        "org_name": org["name"]})
    return {"status": "ok", "id": cur.lastrowid}


# =============================================================== BACK OFFICE ==
# lumi-staff console (closes D2). EVERY route's first line is
# require_platform_admin — a cross-tenant privilege, so there is NO org scope and
# NEVER a client-supplied org_id. The console authors definitions/metadata only;
# it never writes answer data (answers / pulse_responses), so the integrity
# firewall holds. New core metrics are always unscored + optional.

ADMIN_SUB_POWERS = ["Pay", "Incentives", "Benefits", "Time Off", "Wellbeing",
                    "Recognition", "Governance"]
ADMIN_SUB_POWER_ORDER = {name: i + 1 for i, name in enumerate(ADMIN_SUB_POWERS)}
SUGGESTION_STATUSES = ("new", "reviewed", "accepted", "rejected")
ADMIN_METRIC_TYPES = ("numeric", "single_select", "yes_no", "multi_select")


def _admin_slug_code(label):
    s = re.sub(r"[^A-Za-z0-9]+", "_", label.strip().upper()).strip("_")
    return s or "OPT"


# ----- module 1: cross-tenant orgs overview (read-only) ----------------------
@app.get("/api/admin/orgs")
async def admin_orgs(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT o.*, (SELECT COUNT(*) FROM users u WHERE u.org_id=o.org_id) AS n_users "
        "FROM orgs o ORDER BY o.name").fetchall()
    out = []
    for r in rows:
        o = dict(r)
        out.append({
            "org_id": o["org_id"], "name": o["name"], "industry": o["industry"],
            "fte_band": o["fte_band"], "classified": bool(o["classified"]),
            "source": o["source"], "submission_complete": bool(o["submission_complete"]),
            "n_users": o["n_users"],
            # read-only unlock state (the stored stamp) — no side-effecting stamp
            # from a staff list view, unlike org_unlocked().
            "unlocked": bool(o["insights_unlocked_at"]) or bool(o["submission_complete"]),
        })
    return {"orgs": out, "total": len(out)}


# ----- module 2: metric-suggestions triage ----------------------------------
@app.get("/api/admin/suggestions")
async def admin_suggestions(request: Request):
    require_platform_admin(request)
    conn = get_conn()
    rows = conn.execute(
        "SELECT s.*, o.name AS org_name FROM metric_suggestions s "
        "LEFT JOIN orgs o ON o.org_id = s.org_id ORDER BY s.created_at DESC, s.id DESC").fetchall()
    return {"suggestions": [dict(r) for r in rows], "statuses": list(SUGGESTION_STATUSES)}


@app.put("/api/admin/suggestions/{sid}")
async def admin_suggestion_update(sid: int, request: Request):
    user = require_platform_admin(request)
    body = await request.json()
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
    require_platform_admin(request)
    body = await request.json()
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
    return {"ok": True, "pulse_id": pid}


def _pulse_lifecycle(fn, pid):
    try:
        fn(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/admin/pulses/{pid}/open")
async def admin_pulse_open(pid: str, request: Request):
    require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.open_pulse, pid)


@app.post("/api/admin/pulses/{pid}/close")
async def admin_pulse_close(pid: str, request: Request):
    require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.close_pulse, pid)


@app.post("/api/admin/pulses/{pid}/archive")
async def admin_pulse_archive(pid: str, request: Request):
    require_platform_admin(request)
    return _pulse_lifecycle(pulses_mod.archive_pulse, pid)


@app.post("/api/admin/pulses/{pid}/extend")
async def admin_pulse_extend(pid: str, request: Request):
    require_platform_admin(request)
    body = await request.json()
    new_close = (body.get("closes_at") or "").strip()
    if not new_close:
        raise HTTPException(400, "Provide a new close date/time (YYYY-MM-DD HH:MM:SS).")
    try:
        pulses_mod.extend_close(pid, new_close)
    except ValueError as e:
        raise HTTPException(400, str(e))
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
# lumi review, and once approved pays a launch fee (Stripe) that opens it to the
# whole community. Ownership + the review/billing gate live on pulses.* ; payment
# ONLY gates draft->open and never touches give-to-get or the core firewall.

def _base_url():
    return os.environ.get("LUMI_BASE_URL", "http://localhost:8060").rstrip("/")


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
    qids = body.get("question_ids") or []
    new_qs = body.get("new_questions") or []
    if not qids and not new_qs:
        raise HTTPException(400, "Add at least one question.")
    for nq in new_qs:
        if nq.get("type") not in pulses_mod.PULSE_NEW_TYPES:
            raise HTTPException(400, "Each new question needs a supported type (%s)."
                                % ", ".join(pulses_mod.PULSE_NEW_TYPES))
        if not (nq.get("text") or "").strip():
            raise HTTPException(400, "Each new question needs text.")
    return name, (body.get("description") or "").strip(), qids, new_qs, (body.get("closes_at") or None)


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
    name, desc, qids, new_qs, closes_at = _parse_pulse_body(await request.json())
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
    name, desc, qids, new_qs, closes_at = _parse_pulse_body(await request.json())
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
    """Approved -> pay. Records a launch order; when Stripe is configured returns
    a Checkout Session URL. When it isn't, returns the order 'unconfigured' so a
    lumi admin can confirm the launch (invoiced / pre-keys)."""
    user, org = require_admin(request)
    conn = get_conn()
    p = _owned_pulse(conn, pid, org)
    if p["launch_status"] != "approved":
        raise HTTPException(400, "This pulse isn't approved for launch yet.")
    fee = p["launch_fee_pence"] or PULSE_LAUNCH_FEE_PENCE
    oid = pulses_mod.create_launch_order(pid, org["org_id"], fee, created_by=user["user_id"], conn=conn)
    if not payments_mod.is_configured():
        return {"ok": True, "mode": "unconfigured", "order_id": oid, "amount_pence": fee,
                "message": "Card payments aren't switched on yet — a lumi admin can confirm this launch."}
    base = _base_url()
    try:
        session_id, url = payments_mod.create_checkout_session(
            amount_pence=fee, currency="gbp",
            product_name="lumi pulse launch — %s" % p["name"],
            success_url=base + "/app#/run-a-pulse/%s?paid=1" % pid,
            cancel_url=base + "/app#/run-a-pulse/%s?cancelled=1" % pid,
            client_reference_id=oid,
            metadata={"order_id": oid, "pulse_id": pid, "org_id": org["org_id"]})
    except Exception as e:                       # Stripe/network error -> surface, change nothing
        raise HTTPException(502, "Couldn't start checkout: %s" % e)
    pulses_mod.set_order_session(oid, session_id, conn)
    return {"ok": True, "mode": "stripe", "order_id": oid, "checkout_url": url}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe -> us (public, signature-verified). On checkout.session.completed
    the launch order is marked paid, which opens the pulse. Idempotent."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = payments_mod.verify_webhook(payload, sig)
    except ValueError as e:
        raise HTTPException(400, "Webhook verification failed: %s" % e)
    if event.get("type") == "checkout.session.completed":
        sess = (event.get("data") or {}).get("object") or {}
        oid = sess.get("client_reference_id") or (sess.get("metadata") or {}).get("order_id")
        pi = sess.get("payment_intent")
        if oid:
            try:
                pulses_mod.mark_order_paid(oid, payment_intent=pi)
            except ValueError:
                pass    # unknown/duplicate — acknowledge so Stripe stops retrying
    return {"received": True}


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
    body = await request.json()
    decision = body.get("decision")
    notes = (body.get("notes") or "").strip()
    fee = body.get("fee_pence")
    if decision == "approve" and not fee:
        fee = PULSE_LAUNCH_FEE_PENCE
    try:
        pulses_mod.review_pulse(pid, decision, staff["user_id"], notes=notes, fee_pence=fee, conn=get_conn())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/admin/pulses/{pid}/confirm-launch")
async def admin_pulse_confirm_launch(pid: str, request: Request):
    """Staff confirm a launch WITHOUT Stripe — an invoiced/hand-negotiated deal,
    or local testing before keys exist. Opens the pulse exactly as a real card
    payment would (marks the latest pending order paid, or records one)."""
    staff = require_platform_admin(request)
    conn = get_conn()
    try:
        p = pulses_mod.get_pulse(pid, conn)
    except ValueError:
        raise HTTPException(404, "Unknown pulse")
    if not p["owner_org_id"] or p["launch_status"] not in ("approved", "paid"):
        raise HTTPException(400, "Only an approved self-service pulse can be confirmed.")
    fee = p["launch_fee_pence"] or PULSE_LAUNCH_FEE_PENCE
    o = pulses_mod.latest_order(pid, conn)
    oid = (o["order_id"] if (o and o["status"] != "paid")
           else pulses_mod.create_launch_order(pid, p["owner_org_id"], fee, created_by=staff["user_id"], conn=conn))
    pulses_mod.mark_order_paid(oid, payment_intent="staff-confirmed", conn=conn)
    return {"ok": True, "pulse_id": pid}


# ----- module 4: create metric (author -> backlog -> publish live) -----------
def _validate_metric_def(body):
    text = (body.get("text") or "").strip()
    sub_power = (body.get("sub_power") or "").strip()
    qtype = (body.get("type") or "").strip()
    polarity = (body.get("polarity") or "neutral").strip()
    if not text:
        raise HTTPException(400, "The metric needs a question text.")
    if sub_power not in ADMIN_SUB_POWER_ORDER:
        raise HTTPException(400, "Category must be one of: " + ", ".join(ADMIN_SUB_POWERS))
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
        "sub_power": m["sub_power"], "sub_power_order": ADMIN_SUB_POWER_ORDER[m["sub_power"]],
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
    require_platform_admin(request)
    body = await request.json()
    metric = _validate_metric_def(body)
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO core_backlog(title, detail, source, status) VALUES (?,?,'admin_console','queued')",
        (metric["text"][:120], j(metric)))
    conn.commit()
    return {"ok": True, "backlog_id": cur.lastrowid}


@app.post("/api/admin/metrics/{backlog_id}/publish")
async def admin_metric_publish(backlog_id: int, request: Request):
    require_platform_admin(request)
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
    return {"ok": True, "question_id": qid}


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
    # headline scoped to the Substance pool (Provision presence included) so the
    # public share link agrees with the dashboard gauge
    prac_items = pos.practice_position_items(org["org_id"], cut, org_visible_questions(org), payloads(), answers, entitled, None)
    summary = pos.overview_summary(items, mp_config=pos.market_position_config(), practice_items=prac_items,
                                   band_low=MARKET_BAND_LOW, band_high=MARKET_BAND_HIGH)
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
    # public marketing front door; the app lives at /app (its "Log in" target).
    # marketing.html bounces any incoming app-route hash (/#/reset/… etc.) to /app.
    return FileResponse(os.path.join(WEB_DIR, "marketing.html"))


@app.get("/app")
async def app_shell():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


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
