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
CREATE TABLE IF NOT EXISTS pinned_views (
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    user_id TEXT NOT NULL DEFAULT '',
    layout_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (org_id, user_id)
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
                "ALTER TABLE questions ADD COLUMN module TEXT"):
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
