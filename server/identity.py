"""Identity store access layer (Phase 1 split — S6 step 1; DECISIONS c3df1d3, D6 shape B).

The ONLY module allowed to open identity.db — the Phase-1 boundary gate asserts
exactly that (S4.3). No-bulk-export contract: every read is single-key; nothing
returns all names or all emails; no function accepts an unbounded id list.
ATTACH is banned; no cross-store SQL ever (D6).

org_id is minted reward-side (the D6 atomicity ruling): an org_register row is an
ATTACHMENT to a reward-side org_id, not its parent — an orphan identity row is
inert and deletable; an orphan reward row is a nameless org that renders unnamed.

Schema deliberately mirrors server/db.py's live DDL for the moved tables, with ONE
ruled adaptation: users.org_id and invites.org_id lose REFERENCES orgs(org_id) —
after the split that reference is cross-store, which D6 bans. Intra-store FKs
(sessions/password_resets/invites -> users) follow live verbatim.

At S6 step 1 nothing imports this module and the store is empty. The auth-flow
write surface (sessions/resets/invites/registration) is wired at step 3 with its
call sites — building writers nothing calls invites drift between schema and use.
"""
import os
import re
import sqlite3
import sys

_LIVE_IDENTITY_DB = os.path.join(os.path.dirname(__file__), "..", "identity.db")
# gate-safety-1 twin (mirrors server/db.py:19): a bare qa_*/verify_* process must
# never silently open the live identity store.
_GATE_ARGV_RE = re.compile(r"^(qa_|verify_).*\.py$")

# The demo org's identity-side key. Lives here (P3) because every consumer already
# imports identity to resolve it, gates importing app for a constant would drag
# FastAPI into one-shot tooling, and duplicating it across eighteen sites is how
# seed_import's writer drifted from its readers at step 4.
DEMO_ORG_NORMALIZED = "thornbridgeretailgroupplc"


def _resolve_identity_db_path():
    """Mirror of db.py._resolve_db_path (gate-safety-1), twinned for identity:
      1. LUMI_IDENTITY_DB set            -> use it (throwaway or named store; run_gates.sh will set it).
      2. LUMI_IDENTITY_ALLOW_LIVE == 1   -> the LIVE identity store (explicit opt-in; deliberately a
                                            SEPARATE flag from db.py's LUMI_ALLOW_LIVE — one opt-in
                                            must not open two stores of different sensitivity).
      3. a gate/test process             -> REFUSE (raise) rather than silently touch live.
      4. anything else                   -> the LIVE identity store (server + normal app usage).
    """
    env = os.environ.get("LUMI_IDENTITY_DB")
    if env:
        return env
    if os.environ.get("LUMI_IDENTITY_ALLOW_LIVE") == "1":
        return _LIVE_IDENTITY_DB
    argv0 = os.path.basename(sys.argv[0] or "")
    if _GATE_ARGV_RE.match(argv0):
        raise RuntimeError(
            "identity.get_conn(): REFUSING to open the LIVE identity store from gate/test process %r.\n"
            "  Set LUMI_IDENTITY_DB=<throwaway.db> to run against a copy (what run_gates.sh does),\n"
            "  or LUMI_IDENTITY_ALLOW_LIVE=1 to deliberately target live.\n"
            "  (gate-safety-1 twin: identity.py never silently defaults gates to the live store.)" % argv0)
    return _LIVE_IDENTITY_DB


def get_conn():
    conn = sqlite3.connect(_resolve_identity_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- schema (S6 step 1) ----------------------------------------------------------
# org_register: the identity attachment for orgs. name/normalized_name arrive at
# step 2; company_name/external_registry_id receive registry_json's two identity
# keys (Company_Name / Org_ID) at step 4. Uniqueness mirrors live idx_orgs_norm.
DDL = [
    """CREATE TABLE IF NOT EXISTS org_register (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    company_name TEXT,
    external_registry_id INTEGER
)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_org_register_norm ON org_register(normalized_name)",
    """CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    display_name TEXT
)""",
    """CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
)""",
    """CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT
)""",
    """CREATE TABLE IF NOT EXISTS invites (
    token TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_by TEXT NOT NULL REFERENCES users(user_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT
)""",
    # step 5's restore marker (commit 3; D.2). Typed columns, not key/value: the reward
    # store's meta is a general key/value bag, but this store is the PII concentrate and
    # a bag invites arbitrary future keys into it. One row, one purpose, and a schema that
    # says what it holds. The CHECK makes an unknown state a write error rather than a
    # silently-unclassifiable marker.
    """CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    step5_state TEXT NOT NULL CHECK (step5_state IN ('in_progress', 'complete')),
    step5_completed_at TEXT,
    step5_columns TEXT NOT NULL,
    step5_mechanism TEXT NOT NULL
)""",
]

TABLES = ("org_register", "users", "sessions", "password_resets", "invites")


def init_identity_db(conn=None):
    own = conn is None
    if own:
        conn = get_conn()
    for stmt in DDL:
        conn.execute(stmt)
    conn.commit()
    if own:
        conn.close()


# --- single-key reads (the step-3 wiring surface; no bulk export) -----------------

def step5_marker():
    """The step-5 restore marker, or None if absent. Read-only; the two-phase WRITER
    belongs to step 5's own migration script (commits 5/6) and is deliberately NOT
    built here — the step-1 precedent: writers nothing calls drift from their call
    sites. identity_recon reads the marker through this function (D6)."""
    conn = get_conn()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
            return None
        r = conn.execute("SELECT step5_state, step5_completed_at, step5_columns, "
                         "step5_mechanism FROM meta WHERE id=1").fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def org_display(org_id):
    """{'name': ...} for one org, or None. The render-path lookup (S4.3)."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT name FROM org_register WHERE org_id=?", (org_id,)).fetchone()
        return {"name": r["name"]} if r else None
    finally:
        conn.close()


ORG_BATCH_CAP = 1000   # defence-in-depth over the caller-supplied-ids contract: clears
                       # today's real maximum (223, /api/admin/orgs) with ~4x membership
                       # growth; raising it is a deliberate, reviewed act.


def org_display_batch(org_ids):
    """Bounded batch of org display names for staff/cross-tenant surfaces — the
    no-bulk-export contract (S4.3) made concrete. The caller supplies the explicit
    org_id list it derived from its own reward-side query; there is no zero-argument
    or give-me-everything form. Returns {org_id: name}; misses are OMITTED, so
    .get(org_id) yields the ruled unnamed render. Independent of org_display —
    additive capability, not a refactor of the shipped single-key path."""
    ids = list(dict.fromkeys(org_ids))
    if len(ids) > ORG_BATCH_CAP:
        raise ValueError("org_display_batch: %d ids exceeds the no-bulk cap %d"
                         % (len(ids), ORG_BATCH_CAP))
    out = {}
    conn = get_conn()
    try:
        CHUNK = 500   # stays under SQLite's 999-parameter bound
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            for r in conn.execute(
                    "SELECT org_id, name FROM org_register WHERE org_id IN (%s)"
                    % ",".join("?" * len(chunk)), chunk):
                out[r["org_id"]] = r["name"]
        return out
    finally:
        conn.close()


def org_lookup_by_normalized(normalized_name):
    """{'org_id','name'} for one normalized name, or None (demo-org resolution path)."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT org_id, name FROM org_register WHERE normalized_name=?",
                         (normalized_name,)).fetchone()
        return {"org_id": r["org_id"], "name": r["name"]} if r else None
    finally:
        conn.close()


def user_email(user_id):
    """One user's email, or None."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT email FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r["email"] if r else None
    finally:
        conn.close()


def user_display(user_id):
    """{'email','display_name'} for one user, or None."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT email, display_name FROM users WHERE user_id=?",
                         (user_id,)).fetchone()
        return {"email": r["email"], "display_name": r["display_name"]} if r else None
    finally:
        conn.close()


USER_BATCH_CAP = 200   # org-scoped surfaces only (pack creators, share-audit actors):
                       # covers a 200-member org with slack; the platform-total shape
                       # stays impossible by construction (caller-supplied ids + cap).


def user_display_batch(user_ids):
    """Bounded batch of user display identities — the user-side twin of
    org_display_batch, same contract: explicit caller-supplied ids from the
    caller's own reward-side query, no zero-argument form, misses OMITTED.
    Returns {user_id: {'email', 'display_name'}}, matching user_display's shape."""
    ids = list(dict.fromkeys(user_ids))
    if len(ids) > USER_BATCH_CAP:
        raise ValueError("user_display_batch: %d ids exceeds the no-bulk cap %d"
                         % (len(ids), USER_BATCH_CAP))
    out = {}
    conn = get_conn()
    try:
        for r in conn.execute(
                "SELECT user_id, email, display_name FROM users WHERE user_id IN (%s)"
                % ",".join("?" * len(ids)), ids) if ids else []:
            out[r["user_id"]] = {"email": r["email"], "display_name": r["display_name"]}
        return out
    finally:
        conn.close()


INVITE_BATCH_CAP = 200   # org-scoped: one org's pending-invite list. Same ground as
                         # USER_BATCH_CAP — a platform-total shape stays impossible by
                         # construction (caller-supplied tokens + cap).


def invite_email(token):
    """The invited address for one token, or None. Single-key (S4.3)."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT email FROM invites WHERE token=?", (token,)).fetchone()
        return r["email"] if r else None
    finally:
        conn.close()


def invite_email_batch(tokens):
    """Bounded batch — the invite twin of user_display_batch, same contract: explicit
    caller-supplied tokens from the caller's own reward-side query, no zero-argument
    form, misses OMITTED so .get() yields the unnamed render. Returns {token: email}."""
    ids = list(dict.fromkeys(tokens))
    if len(ids) > INVITE_BATCH_CAP:
        raise ValueError("invite_email_batch: %d tokens exceeds the no-bulk cap %d"
                         % (len(ids), INVITE_BATCH_CAP))
    out = {}
    conn = get_conn()
    try:
        for r in conn.execute("SELECT token, email FROM invites WHERE token IN (%s)"
                              % ",".join("?" * len(ids)), ids) if ids else []:
            out[r["token"]] = r["email"]
        return out
    finally:
        conn.close()


def lookup_user_by_email(email):
    """The login-path row for one email (UNIQUE), or None. pw_hash stays here —
    hashing/verification remains auth.py's job."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


# --- dual-write shadow (S6 step 3 commit 1; DECISIONS c3df1d3, D6) ----------------
# During dual-write the reward store is authoritative for every read; these writers
# keep the identity store in step. A failed shadow write must never fail the user's
# request — it logs loudly and leaves an orphan the reconciliation check surfaces
# (server/identity_recon.py; joins the gate suite at step 7).

def shadow(write_fn, *args):
    """Run one identity shadow-write; never raise. No values are logged — function
    name and DB error text only (constraint messages name columns, not data)."""
    try:
        write_fn(*args)
    except Exception as e:
        print("[identity-shadow] WRITE FAILED (%s): %s — reward store authoritative; "
              "orphan stands until reconciled" % (getattr(write_fn, "__name__", "?"), e))


def register_org_identity(org_id, name, normalized_name):
    """Identity attachment for a reward-minted org (D6: org_id minted reward-side
    first). Idempotent upsert on org_id — a retry rewrites the same attachment."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO org_register(org_id, name, normalized_name) VALUES (?,?,?) "
            "ON CONFLICT(org_id) DO UPDATE SET name=excluded.name, "
            "normalized_name=excluded.normalized_name",
            (org_id, name, normalized_name))
        conn.commit()
    finally:
        conn.close()


def register_user(user_id, org_id, email, pw_hash, display_name):
    """Shadow of auth.create_user — byte-identical values (the caller passes the same
    normalised email and computed hash). Five identity columns only (S4.2 amendment:
    users SPLITS — role and account state stay reward-side). Idempotent upsert on
    user_id; a DIFFERENT user_id reusing an email hits users.email UNIQUE and raises
    (shadow() logs it)."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users(user_id, org_id, email, pw_hash, display_name) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET email=excluded.email, "
            "pw_hash=excluded.pw_hash, display_name=excluded.display_name",
            (user_id, org_id, email, pw_hash, display_name))
        conn.commit()
    finally:
        conn.close()


def remove_user_identity(user_id, reassign_created_by_to):
    """Mirror of remove_member's identity-side removal (1c; D6 order — invoked via
    shadow() AFTER the reward-side commit). One transaction, explicit FK order
    (E8: bare REFERENCES, no ON DELETE): reassign invites.created_by first, then
    delete password_resets, then the users row last. org_register untouched —
    user-level, not org-level. Sessions are deleted here too (Seam-B): once the
    session lifecycle moved identity-side, sessions.user_id's FK would block the
    users delete — the commit that created that hazard closes it, in FK order."""
    conn = get_conn()
    try:
        conn.execute("UPDATE invites SET created_by=? WHERE created_by=?",
                     (reassign_created_by_to, user_id))
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def create_session(token, user_id, expires_at):
    """Store a session identity-side (Seam-B). auth.py mints the token and expiry —
    policy stays there, identity.py stores what it is given, exactly as register_user
    takes a computed pw_hash."""
    conn = get_conn()
    try:
        conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)",
                     (token, user_id, expires_at))
        conn.commit()
    finally:
        conn.close()


def session_user_identity(token):
    """Validate one session token and return the IDENTITY half of the user record,
    or None if the token is unknown or expired. One identity-side query — the same
    sessions-join-users shape and the SAME expiry rule as the pre-split read; the
    reward-side account state is composed on top by auth.get_session_user."""
    conn = get_conn()
    try:
        r = conn.execute(
            "SELECT u.user_id, u.org_id, u.email, u.pw_hash, u.display_name, s.expires_at "
            "FROM sessions s JOIN users u ON u.user_id=s.user_id "
            "WHERE s.token=? AND s.expires_at > datetime('now')", (token,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def delete_session(token):
    """Logout — single token, idempotent."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()


def update_pw_hash(user_id, pw_hash):
    """Mirror of the reward-side password change — the ONE users mutation that
    survives the split (S4.2 amendment). Single-key, idempotent."""
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET pw_hash=? WHERE user_id=?", (pw_hash, user_id))
        conn.commit()
    finally:
        conn.close()


def record_invite(token, org_id, email, role, created_by, expires_at):
    """Shadow of auth.create_invite. ON CONFLICT(token) DO NOTHING — a replay of the
    same token is a no-op; a retry mints a fresh token and lands as its own row."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO invites(token, org_id, email, role, created_by, expires_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(token) DO NOTHING",
            (token, org_id, email, role, created_by, expires_at))
        conn.commit()
    finally:
        conn.close()


def record_password_reset(token, user_id, expires_at):
    """Shadow of auth.create_reset. ON CONFLICT(token) DO NOTHING."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO password_resets(token, user_id, expires_at) VALUES (?,?,?) "
            "ON CONFLICT(token) DO NOTHING",
            (token, user_id, expires_at))
        conn.commit()
    finally:
        conn.close()


def mark_invite_used(token):
    """Shadow of the two reward-side invites.used_at writers (accept + revoke-as-used)."""
    conn = get_conn()
    try:
        conn.execute("UPDATE invites SET used_at=datetime('now') "
                     "WHERE token=? AND used_at IS NULL", (token,))
        conn.commit()
    finally:
        conn.close()


def consume_password_reset(token):
    """Shadow of the reward-side password_resets consume."""
    conn = get_conn()
    try:
        conn.execute("UPDATE password_resets SET used_at=datetime('now') "
                     "WHERE token=? AND used_at IS NULL", (token,))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_identity_db()
    conn = get_conn()
    for t in TABLES:
        print("%s: %d rows" % (t, conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))
    conn.close()
