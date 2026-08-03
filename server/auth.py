"""Authentication & tenancy.

bcrypt password hashing, server-side sessions in httpOnly SameSite cookies,
rate-limited login, tokenised reset/invite links (console-logged in this
environment instead of email). Org scoping is enforced by middleware in
app.py: every request's org_id comes from the session, never from the client.
"""
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

import bcrypt

from db import get_conn
import identity

SESSION_TTL_DAYS = 14
INVITE_TTL_DAYS = 7
RESET_TTL_HOURS = 2
COOKIE_NAME = "lumi_session"


def hash_password(pw):
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(pw, pw_hash):
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("ascii"))
    except ValueError:
        return False


# --------------------------------------------------------- rate limiting ---

_attempts = defaultdict(list)  # key -> [timestamps]
RATE_MAX = 5        # per email — strict
RATE_MAX_IP = 30    # per IP — generous (whole offices share NAT egress IPs)
RATE_WINDOW = 300   # seconds


def rate_limited(key):
    now = time.time()
    limit = RATE_MAX_IP if "-ip:" in key else RATE_MAX  # any per-IP key gets the generous NAT-friendly tier
    _attempts[key] = [t for t in _attempts[key] if now - t < RATE_WINDOW]
    if len(_attempts[key]) >= limit:
        return True
    _attempts[key].append(now)
    return False


# -------------------------------------------------------------- sessions ---

def create_session(user_id):
    """Seam-B: sessions live in identity.db. Token and TTL are minted here (policy);
    identity.py stores them. Hard cutover — nothing is written reward-side."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    identity.create_session(token, user_id, expires)
    return token


def get_session_user(token):
    """Seam-B: a cross-store composition. The token is validated identity-side (same
    join, same expiry rule); reward-side account state is layered on top. The result
    carries the SAME keys the pre-split "SELECT u.* + expires_at" did, so every caller
    and request.state.user are unchanged in shape."""
    if not token:
        return None
    ident = identity.session_user_identity(token)
    if ident is None:
        return None
    acct = get_conn().execute(
        "SELECT role, chart_prefs_json, preview_as_core, created_at, notify_prefs_json, "
        "platform_admin, active_dashboard_id, disabled_at FROM users WHERE user_id=?",
        (ident["user_id"],)).fetchone()
    if acct is None:
        return None          # no reward-side account row: the same 401 the old join gave
    if acct["disabled_at"]:
        return None          # soft-deactivated: every session dies here, even a live one
    out = dict(acct)
    out.update(ident)
    return out


def destroy_session(token):
    identity.delete_session(token)


# ----------------------------------------------------------------- users ---

def create_user(org_id, email, password, role, display_name=None):
    conn = get_conn()
    uid = str(uuid.uuid4())
    em = email.lower().strip()
    ph = hash_password(password)
    conn.execute(                       # step 5: email/pw_hash/display_name identity-side only
        "INSERT INTO users(user_id, org_id, role) VALUES (?,?,?)",
        (uid, org_id, role))
    conn.commit()
    identity.shadow(identity.register_user, uid, org_id, em, ph, display_name)
    return uid


def find_user(email):
    """The row for one email — identity store only (P1; D6: identity through
    identity.py). Returns identity.users' five columns as a dict, or None on a
    miss, exactly as the reward-side SELECT returned a row or None.
    A straight swap, not a Seam-B composition: a repo-wide census of all six
    callers found none reads a reward-side column (role, platform_admin, prefs)
    off this result — only pw_hash, user_id, and truthiness."""
    return identity.lookup_user_by_email(email.lower().strip())


# ----------------------------------------------------- invites & resets ---

def create_invite(org_id, email, role, created_by):
    conn = get_conn()
    token = secrets.token_urlsafe(24)
    expires = (datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    em = email.lower().strip()
    conn.execute(                       # step 5: invites.email identity-side only
        "INSERT INTO invites(token, org_id, role, created_by, expires_at) VALUES (?,?,?,?,?)",
        (token, org_id, role, created_by, expires))
    conn.commit()
    identity.shadow(identity.record_invite, token, org_id, em, role, created_by, expires)
    return token


def get_valid_invite(token):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM invites WHERE token=? AND used_at IS NULL AND expires_at > datetime('now')",
        (token,)).fetchone()


def create_reset(user_id):
    conn = get_conn()
    token = secrets.token_urlsafe(24)
    expires = (datetime.utcnow() + timedelta(hours=RESET_TTL_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO password_resets(token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.commit()
    identity.shadow(identity.record_password_reset, token, user_id, expires)
    return token


def get_valid_reset(token):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM password_resets WHERE token=? AND used_at IS NULL AND expires_at > datetime('now')",
        (token,)).fetchone()
