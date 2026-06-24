"""Database layer for lumi.

SQLite for this build. The schema deliberately sticks to ANSI types
(TEXT/INTEGER/REAL/TIMESTAMP-as-TEXT) and avoids SQLite-only features so a
Postgres migration is a connection-string + driver swap (see DECISIONS.md).
All JSON-shaped values are stored as TEXT and (de)serialised at the edges.
"""
import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(__file__), "..", "lumi.db"))

_local = threading.local()


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    short_description TEXT,
    help_text TEXT,
    definition TEXT,
    superpower TEXT NOT NULL,
    sub_power TEXT,
    sub_power_order INTEGER,
    type TEXT NOT NULL,                -- single_select | multi_select | matrix | yes_no | numeric
    category TEXT,                     -- practice | metric | policy | benefit
    options_json TEXT,                 -- JSON array of {code,label,order,is_na}
    default_chart_type TEXT,
    data_display_type TEXT,
    polarity TEXT,                     -- higher_is_better | lower_is_better | neutral
    unit TEXT,
    unit_display_name TEXT,
    unit_type TEXT,
    currency_code TEXT,
    matrix_json TEXT,                  -- JSON matrix definition
    matrix_rows_json TEXT,             -- JSON array of row labels
    lumi_tier TEXT,                    -- Core | Enhanced | Pulse | Strategic
    na_handling_json TEXT,
    benchmark_display TEXT,
    is_scored INTEGER NOT NULL DEFAULT 0,
    scoring_config_json TEXT,
    score_map_json TEXT,
    validation_json TEXT,
    tolerance_json TEXT,
    is_required INTEGER NOT NULL DEFAULT 0,
    search_description TEXT,
    question_order INTEGER             -- stable order from the library file
);

CREATE TABLE IF NOT EXISTS orgs (
    org_id TEXT PRIMARY KEY,           -- UUID
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed',        -- seed | signup
    tier_entitlement TEXT NOT NULL DEFAULT 'core',  -- core | full
    classified INTEGER NOT NULL DEFAULT 0,      -- 1 if firmographics known
    industry TEXT,
    subsector TEXT,
    fte_band TEXT,
    hq_region TEXT,
    ownership_type TEXT,
    registry_json TEXT,                -- full registry record for matched seed orgs
    similarity_vector_json TEXT,       -- normalised feature vector (registry-matched / declared)
    submission_complete INTEGER NOT NULL DEFAULT 0, -- core-tier >=90% answered
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orgs_norm ON orgs(normalized_name);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY,
    snapshot_date TEXT NOT NULL,
    collection_window TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',  -- open | aggregated
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Raw answers. NEVER served to any client other than the owning org's users.
CREATE TABLE IF NOT EXISTS answers (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    question_id TEXT NOT NULL REFERENCES questions(id),
    matrix_row_id TEXT NOT NULL DEFAULT '',
    value TEXT,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, snapshot_id, question_id, matrix_row_id)
);
CREATE INDEX IF NOT EXISTS idx_answers_q ON answers(snapshot_id, question_id);

-- Aggregates per question per snapshot (the only benchmark data the API serves).
CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    question_id TEXT NOT NULL REFERENCES questions(id),
    payload_json TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_id, question_id)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    email TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin | viewer
    display_name TEXT,
    chart_prefs_json TEXT NOT NULL DEFAULT '{}',
    preview_as_core INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invites (
    token TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT
);

-- "My view" pinned layouts. user_id='' means the org default layout.
-- Retained as the org-default TEMPLATE that seeds a new user's first dashboard
-- (and for backward-compat); per-user working layouts now live in `dashboards`.
CREATE TABLE IF NOT EXISTS pinned_views (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL DEFAULT '',
    layout_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, user_id)
);

-- "My dashboards" — each user can keep several named, saveable dashboards.
-- A dashboard is a layout (same slot shape as pinned_views.layout_json) plus a
-- name + ordering position. The user's first dashboard is lazily migrated from
-- their old pinned_views row (see _ensure_dashboards in app.py). Tenancy + owner
-- are (org_id, user_id); the active one is tracked on users.active_dashboard_id.
CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(org_id),
    user_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    layout_json  TEXT NOT NULL DEFAULT '[]',
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dashboards_owner ON dashboards(org_id, user_id, position);

-- Per-user triage state for Signals (the inbox model): one status per signal
-- (keyed by question_id — the per-metric cap means one signal per metric).
CREATE TABLE IF NOT EXISTS signal_actions (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    status TEXT NOT NULL,                -- priority | saved | dismissed
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, user_id, question_id)
);

-- per-user "seen" set for the new-since-last-seen badge: a signal (by sig_id)
-- is NEW until the user has viewed it on the Signals page.
CREATE TABLE IF NOT EXISTS signal_seen (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL,
    sig_id TEXT NOT NULL,
    seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, user_id, sig_id)
);

-- Notifications (signal change alerts). Signals are computed live and not
-- persisted; signal_state is the nightly snapshot we diff against to detect a
-- flag appearing, clearing, or crossing a materiality bucket.
CREATE TABLE IF NOT EXISTS signal_state (
    org_id        TEXT NOT NULL REFERENCES orgs(org_id),
    signal_key    TEXT NOT NULL,        -- {lens}:{kind}:{question_id}:{matrix_row}
    lens          TEXT NOT NULL,        -- save | attract | retain | engage
    kind          TEXT NOT NULL,        -- behind | save | prevalence | money | ...
    question_id   TEXT NOT NULL,
    value_display TEXT,                 -- the figure shown ("P5", "56%", "£75k/yr")
    bucket        TEXT NOT NULL,        -- materiality step — diffed, not the raw value
    detail        TEXT NOT NULL,        -- factual string, reused in inbox + email verbatim
    first_seen    TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, signal_key)
);

-- One row per detected org-level change. Two consumers: the in-app inbox
-- (every user) and the email digest (opted-in users).
CREATE TABLE IF NOT EXISTS notification_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id       TEXT NOT NULL REFERENCES orgs(org_id),
    event_kind   TEXT NOT NULL,         -- appeared | cleared | moved
    signal_key   TEXT NOT NULL,
    lens         TEXT NOT NULL,
    question_id  TEXT NOT NULL,
    payload_json TEXT NOT NULL,         -- diff row frozen at detection (detail, value, prev)
    detected_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-user read/email state against those events (drives the bell + digest).
CREATE TABLE IF NOT EXISTS notification_reads (
    user_id           TEXT NOT NULL REFERENCES users(user_id),
    event_id          INTEGER NOT NULL REFERENCES notification_events(id),
    read_at           TEXT,             -- NULL = unread in the bell
    emailed_at        TEXT,             -- NULL = not yet in a sent digest
    suppressed_reason TEXT,             -- guardrail/pref drop (audit, not error)
    PRIMARY KEY (user_id, event_id)
);

CREATE TABLE IF NOT EXISTS shares (
    token TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    kind TEXT NOT NULL,                 -- boardpack | dashboard
    config_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,                    -- NULL = no expiry
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS share_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    share_token TEXT NOT NULL,
    action TEXT NOT NULL,               -- created | revoked
    user_id TEXT NOT NULL,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Submission drafts (autosave); promoted into answers on submit.
CREATE TABLE IF NOT EXISTS drafts (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    question_id TEXT NOT NULL,
    matrix_row_id TEXT NOT NULL DEFAULT '',
    value TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, question_id, matrix_row_id)
);

-- Soft-warning overrides: a user confirmed an unusual-but-real value. Kept
-- for optional review (who/field/value/threshold) — never gates anything.
CREATE TABLE IF NOT EXISTS validation_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_email TEXT NOT NULL,
    question_id TEXT NOT NULL,
    matrix_row_id TEXT NOT NULL DEFAULT '',
    value TEXT,
    warning TEXT,
    threshold TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Editable £-model assumptions per org (falls back to engine defaults).
CREATE TABLE IF NOT EXISTS org_assumptions (
    org_id TEXT PRIMARY KEY REFERENCES orgs(org_id),
    assumptions_json TEXT NOT NULL DEFAULT '{}'
);

-- Cached Peer Twin groups per org.
CREATE TABLE IF NOT EXISTS peer_twin_cache (
    org_id TEXT PRIMARY KEY REFERENCES orgs(org_id),
    peer_org_ids_json TEXT NOT NULL,
    rationale_json TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Append-only history of every answer version (movement tracking depends on
-- submissions never overwriting history).
CREATE TABLE IF NOT EXISTS answers_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    matrix_row_id TEXT NOT NULL DEFAULT '',
    value TEXT,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Member requests for metrics lumi doesn't benchmark yet. The durable record
-- (email notification is best-effort); curated by hand — never auto-added.
CREATE TABLE IF NOT EXISTS metric_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    requested_text TEXT NOT NULL,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'button',   -- button | search | ask-lumi
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Structured "Suggest a metric" submissions (name + definition + rationale +
-- optional category) — input to a deliberate research-standards review, never
-- auto-added. status is for future review-state tracking. (Schema change, not
-- data: lives here and auto-applies on restart; see DECISIONS.md.)
CREATE TABLE IF NOT EXISTS metric_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    user_email TEXT,
    metric_name TEXT NOT NULL,
    what_it_measures TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    suggested_category TEXT,
    status TEXT NOT NULL DEFAULT 'new'
);

-- Layered terms acceptance log: who accepted what, for which org, when, and
-- which version. kind='platform' is user-level; kind='data_contribution' is
-- the org-level agreement (accepted once by an Admin on the org's behalf).
CREATE TABLE IF NOT EXISTS terms_acceptances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,                -- platform | data_contribution
    version TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_terms_org ON terms_acceptances(org_id, kind);

-- Custom peer groups: filter-based (NEVER hand-picked orgs), private to the
-- owning org. criteria_json maps curated firmographic fields to accepted
-- value lists. Membership is resolved at query time and never stored or
-- exposed — only counts and suppressed-compliant aggregates leave the server.
CREATE TABLE IF NOT EXISTS peer_groups (
    group_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    name TEXT NOT NULL,
    criteria_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_peer_groups_org ON peer_groups(org_id);

-- AI metric commentary, cached per org+metric+cut until the underlying
-- figures change (payload_hash). Regenerate replaces the row.
CREATE TABLE IF NOT EXISTS metric_commentary (
    org_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    cut_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,              -- model | deterministic
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, question_id, cut_key)
);

-- Generated board packs (narrative cached so the print view is stable).
CREATE TABLE IF NOT EXISTS board_packs (
    pack_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,     -- data passed to the model
    narrative_json TEXT NOT NULL,   -- model output sections
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ===================== CORE QUESTION-SET VERSIONING / GOVERNANCE ===========
-- A release is a named, dated version of the core question set. The live core
-- = the current release. Prior releases are reconstructable forever.
CREATE TABLE IF NOT EXISTS core_releases (
    release_id TEXT PRIMARY KEY,           -- '2025-baseline', '2026.1'
    name TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'current',-- current | superseded
    signed_off_by TEXT,
    released_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Exact per-release membership snapshot: full question row preserved so any
-- prior release's question set reconstructs byte-for-byte.
CREATE TABLE IF NOT EXISTS release_questions (
    release_id TEXT NOT NULL REFERENCES core_releases(release_id),
    question_id TEXT NOT NULL,
    question_version TEXT,
    is_required INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    snapshot_json TEXT NOT NULL,
    PRIMARY KEY (release_id, question_id)
);

-- One change-log line per change. lane='release' rows are generated by the
-- release diff; lane='emergency' is the only path that writes between
-- releases (factually-wrong corrections only, signed off).
CREATE TABLE IF NOT EXISTS core_changelog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id TEXT,
    lane TEXT NOT NULL DEFAULT 'release',  -- release | emergency
    change_type TEXT NOT NULL,             -- baseline | added | retired | reworded | emergency_correction
    question_id TEXT,
    detail TEXT,
    signed_off_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================== PULSES (Tier 2) ============================
-- Time-boxed topical surveys with their own opt-in cohort and window.
-- THE CARDINAL RULE: pulse responses live HERE, never in `answers` — the core
-- aggregation path reads `answers` only, so pulse data cannot pool into a
-- core aggregate even via a forgotten WHERE clause (structural separation).
CREATE TABLE IF NOT EXISTS pulses (
    pulse_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | open | closed | archived
    opens_at TEXT,
    closes_at TEXT,
    question_ids_json TEXT NOT NULL DEFAULT '[]',
    -- the question definitions AS-ASKED (full rows), snapshotted at open:
    -- an archived pulse report stays truthful even if the core later
    -- rewords/retires a referenced question
    question_snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pulse_participants (
    pulse_id TEXT NOT NULL REFERENCES pulses(pulse_id),
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    submission_complete INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pulse_id, org_id)
);

CREATE TABLE IF NOT EXISTS pulse_responses (
    pulse_id TEXT NOT NULL REFERENCES pulses(pulse_id),
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    question_id TEXT NOT NULL,
    matrix_row_id TEXT NOT NULL DEFAULT '',
    value TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (pulse_id, org_id, question_id, matrix_row_id)
);

-- Self-service pulse launches (2026-06-22): an org Admin authors a pulse, it
-- goes through lumi staff review, then a paid Stripe checkout opens it to the
-- community. Ownership + review state + the launch fee ride on `pulses`
-- (owner_org_id, created_by, launch_status, review_*, launch_fee_pence); each
-- checkout attempt is one row HERE — the billing/audit ledger. Payment ONLY
-- gates the draft->open transition; it never touches the give-to-get report
-- gate or the core firewall.
CREATE TABLE IF NOT EXISTS pulse_launch_orders (
    order_id TEXT PRIMARY KEY,
    pulse_id TEXT NOT NULL REFERENCES pulses(pulse_id),
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    amount_pence INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'gbp',
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | paid | failed | refunded
    stripe_session_id TEXT,
    stripe_payment_intent TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at TEXT
);

-- The persisted backlog that FEEDS releases. Items queue here and are never
-- auto-applied to the live core.
CREATE TABLE IF NOT EXISTS core_backlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    detail TEXT,
    source TEXT NOT NULL DEFAULT 'manual', -- request-a-metric | regulatory | pulse-graduation | manual
    source_ref TEXT,                       -- e.g. metric_requests.id (dedup key)
    status TEXT NOT NULL DEFAULT 'queued', -- queued | scheduled | applied | rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reward strategy capture (2026-06-16): org-level reward stance — the Plane B
-- (philosophy) + Plane C (posture) dials that let the engines tell "below market"
-- from "below market, on purpose". Plane A facts are NOT here — they live in the
-- orgs/registry record. One row per org; Admin-set.
CREATE TABLE IF NOT EXISTS org_strategy (
    org_id              TEXT PRIMARY KEY REFERENCES orgs(org_id),
    -- Plane B (philosophy)
    market_position     TEXT,   -- 'lag' | 'match' | 'lead'                       (REQUIRED)
    reward_mix          TEXT,   -- 'cash' | 'balanced' | 'benefits'               (REQUIRED)
    pay_for_performance TEXT,   -- 'egal' | 'moderate' | 'strong'
    transparency        TEXT,   -- 'closed' | 'ranges' | 'open'
    location_approach   TEXT,   -- 'local' | 'national' | 'agnostic'
    benefits_lead       TEXT,   -- JSON array: ['physical','mental','financial','worklife']
    family_position     TEXT,   -- 'statutory' | 'market' | 'over'
    -- Plane C (posture)
    primary_objective   TEXT,   -- 'attract'|'retain'|'cost'|'compliance'|'hold'  (REQUIRED)
    budget_direction    TEXT,   -- 'investing' | 'flat' | 'pressure'
    acute_pressure      TEXT,   -- 'bau' | 'scaling' | 'shock'
    risk_appetite       TEXT,   -- 'early' | 'follow' | 'wait'
    field_provenance    TEXT,   -- JSON {field: 'set'|'suggested'|'skipped'} ('suggested' reserved, unused v1)
    -- per-domain market-position target (step-3 layer 1, 2026-06-24): JSON
    -- {domain: 'lag'|'match'|'lead'} — SAME enum as market_position, only for
    -- COMPETITIVE domains (validated via _mp_competitive). Absent domain / null
    -- column → falls back to the global market_position (degrade-to-global).
    -- Stored only; NO consumer yet (engine reads it in layer 3).
    domain_targets      TEXT,
    completed_at        TEXT,
    updated_at          TEXT
);
"""


def init_schema(conn=None):
    conn = conn or get_conn()
    conn.executescript(SCHEMA)
    # migration-lite for existing databases
    for ddl in ("ALTER TABLE orgs ADD COLUMN clock_start TEXT",
                "ALTER TABLE orgs ADD COLUMN insights_unlocked_at TEXT",
                "ALTER TABLE orgs ADD COLUMN reminders_json TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE orgs ADD COLUMN unionised_level TEXT",
                "ALTER TABLE orgs ADD COLUMN hr_maturity TEXT",
                "ALTER TABLE orgs ADD COLUMN business_maturity TEXT",
                "ALTER TABLE orgs ADD COLUMN operating_model TEXT",
                # core-set versioning (2026-06-12): governance fields from the
                # library + the release each question entered/left under, the
                # sticky-unlock release stamp, and the release a data period
                # was aggregated under (release x period = reproducibility)
                "ALTER TABLE questions ADD COLUMN question_version TEXT",
                "ALTER TABLE questions ADD COLUMN historical_comparability TEXT",
                "ALTER TABLE questions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
                "ALTER TABLE questions ADD COLUMN replaced_by TEXT",
                "ALTER TABLE questions ADD COLUMN release_entered TEXT",
                "ALTER TABLE questions ADD COLUMN release_retired TEXT",
                "ALTER TABLE orgs ADD COLUMN unlocked_release TEXT",
                "ALTER TABLE snapshots ADD COLUMN release_id TEXT",
                # 2026.1 restructure: sector-gated module flag (hospitality tronc/tips)
                "ALTER TABLE questions ADD COLUMN module TEXT",
                # signal change alerts: per-user notification preferences (bell +
                # email opt-in), stored like chart_prefs_json
                "ALTER TABLE users ADD COLUMN notify_prefs_json TEXT NOT NULL DEFAULT '{}'",
                # back-office (D2): platform-admin tier ABOVE the org roles — staff
                # who can cross tenants in the staff console. Defaults to 0 so every
                # existing user stays a normal tenant member.
                "ALTER TABLE users ADD COLUMN platform_admin INTEGER NOT NULL DEFAULT 0",
                # metric-suggestion triage: staff review workflow over the existing
                # write-only suggestions inbox (status new -> reviewed -> accepted|rejected)
                "ALTER TABLE metric_suggestions ADD COLUMN reviewed_by TEXT",
                "ALTER TABLE metric_suggestions ADD COLUMN reviewed_at TEXT",
                "ALTER TABLE metric_suggestions ADD COLUMN review_notes TEXT",
                # "My dashboards" (multi-dashboard): per-user pointer to the
                # dashboard the global pin-star targets and the page opens on.
                "ALTER TABLE users ADD COLUMN active_dashboard_id TEXT",
                # Self-service pulse builder + paid launch (2026-06-22): pulses
                # gain org ownership + a review/billing sub-state that lives
                # ALONGSIDE the engine `status` (draft->open->closed->archived).
                # launch_status is NULL for legacy staff-authored global pulses;
                # for org-authored pulses it tracks building -> in_review ->
                # changes_requested|approved -> paid (then status flips to open).
                "ALTER TABLE pulses ADD COLUMN owner_org_id TEXT",
                "ALTER TABLE pulses ADD COLUMN created_by TEXT",
                "ALTER TABLE pulses ADD COLUMN launch_status TEXT",
                "ALTER TABLE pulses ADD COLUMN review_notes TEXT",
                "ALTER TABLE pulses ADD COLUMN reviewed_by TEXT",
                "ALTER TABLE pulses ADD COLUMN reviewed_at TEXT",
                "ALTER TABLE pulses ADD COLUMN launch_fee_pence INTEGER",
                "ALTER TABLE pulses ADD COLUMN visibility TEXT NOT NULL DEFAULT 'community'",
                # per-domain market-position target (step-3 layer 1, 2026-06-24):
                # nullable JSON {domain: lag|match|lead}; null → global fallback.
                "ALTER TABLE org_strategy ADD COLUMN domain_targets TEXT"):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


def j(value):
    """Serialise to JSON text (None-safe)."""
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def uj(text, default=None):
    """Deserialise JSON text (None/garbage-safe)."""
    if text is None or text == "":
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def set_meta(key, value, conn=None):
    conn = conn or get_conn()
    conn.execute(
        "INSERT INTO meta(key, value_json) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()


def get_meta(key, default=None, conn=None):
    conn = conn or get_conn()
    row = conn.execute("SELECT value_json FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else default
