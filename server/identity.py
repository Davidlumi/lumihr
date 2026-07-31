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

def org_display(org_id):
    """{'name': ...} for one org, or None. The render-path lookup (S4.3)."""
    conn = get_conn()
    try:
        r = conn.execute("SELECT name FROM org_register WHERE org_id=?", (org_id,)).fetchone()
        return {"name": r["name"]} if r else None
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
