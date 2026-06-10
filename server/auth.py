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
    limit = RATE_MAX_IP if key.startswith("login-ip:") else RATE_MAX
    _attempts[key] = [t for t in _attempts[key] if now - t < RATE_WINDOW]
    if len(_attempts[key]) >= limit:
        return True
    _attempts[key].append(now)
    return False


# -------------------------------------------------------------- sessions ---

def create_session(user_id):
    conn = get_conn()
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.commit()
    return token


def get_session_user(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.user_id=s.user_id
           WHERE s.token=? AND s.expires_at > datetime('now')""", (token,)).fetchone()
    return row


def destroy_session(token):
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()


# ----------------------------------------------------------------- users ---

def create_user(org_id, email, password, role, display_name=None):
    conn = get_conn()
    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users(user_id, org_id, email, pw_hash, role, display_name) VALUES (?,?,?,?,?,?)",
        (uid, org_id, email.lower().strip(), hash_password(password), role, display_name))
    conn.commit()
    return uid


def find_user(email):
    conn = get_conn()
    return conn.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()


# ----------------------------------------------------- invites & resets ---

def create_invite(org_id, email, role, created_by):
    conn = get_conn()
    token = secrets.token_urlsafe(24)
    expires = (datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO invites(token, org_id, email, role, created_by, expires_at) VALUES (?,?,?,?,?,?)",
        (token, org_id, email.lower().strip(), role, created_by, expires))
    conn.commit()
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
    return token


def get_valid_reset(token):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM password_resets WHERE token=? AND used_at IS NULL AND expires_at > datetime('now')",
        (token,)).fetchone()
