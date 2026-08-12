"""Authentication & tenancy.

bcrypt password hashing, server-side sessions in httpOnly SameSite cookies,
rate-limited login, tokenised reset/invite links (console-logged in this
environment instead of email). Org scoping is enforced by middleware in
app.py: every request's org_id comes from the session, never from the client.
"""
import base64
import hashlib
import re
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

# ------------------------------------------------------ password policy ---
# NIST 800-63B + Cyber Essentials posture: a real length floor + screening against
# the passwords attackers try first — NOT character-class composition rules, and NO
# maximum length (CE A5.5 requires no max; hash_password pre-hashes so long passphrases
# are safe). The blocklist is the head of every public breach corpus; equality with the
# email local-part or the org name is also refused.
PASSWORD_MIN = 8
_COMMON_PASSWORDS = frozenset("""
password password1 password123 passw0rd 12345678 123456789 1234567890 123123123
qwerty qwertyuiop qwerty123 1q2w3e4r 1qaz2wsx zaq12wsx abc12345 letmein welcome
welcome1 iloveyou admin123 administrator changeme trustno1 sunshine princess
football baseball dragon monkey master shadow superman batman michael jennifer
whatever qazwsxedc 11111111 00000000 aaaaaaaa 88888888 87654321 password!
p@ssword p@ssw0rd secret123 login123 test1234 samsung123 google123 starwars
lovely123 hello123 charlie123 default lumi1234 rewarddata benchmark123
""".split())


def validate_password(pw, *, email=None, org_name=None):
    """Return a human error string if the password is unacceptable, else None.
    One source for register / reset / invite so the rule never drifts."""
    pw = pw or ""
    if len(pw) < PASSWORD_MIN:
        return "Password must be at least %d characters." % PASSWORD_MIN
    low = pw.lower().strip()
    if low in _COMMON_PASSWORDS:
        return "That password is one of the most common — please choose something less guessable."
    if email:
        local = str(email).split("@")[0].lower().strip()
        if local and low == local:
            return "Your password can't be your email address."
    if org_name:
        on = re.sub(r"[^a-z0-9]", "", str(org_name).lower())
        if on and len(on) >= 4 and re.sub(r"[^a-z0-9]", "", low) == on:
            return "Your password can't be your organisation name."
    return None
COOKIE_NAME = "lumi_session"


def _bcrypt_input(pw):
    # SHA-256 -> base64 (~44 bytes) BEFORE bcrypt. bcrypt silently ignores bytes past
    # 72, which both weakens long passphrases and imposes an effective maximum length.
    # Pre-hashing removes both: bcrypt now sees a fixed-size digest, so there is NO
    # maximum password length (Cyber Essentials A5.5 requires "no maximum length") and
    # no truncation/collision for long passphrases.
    return base64.b64encode(hashlib.sha256((pw or "").encode("utf-8")).digest())


def hash_password(pw):
    return bcrypt.hashpw(_bcrypt_input(pw), bcrypt.gensalt()).decode("ascii")


def verify_password(pw, pw_hash):
    try:
        h = pw_hash.encode("ascii")
        if bcrypt.checkpw(_bcrypt_input(pw), h):
            return True
        # Legacy hashes (minted before the 2026-08-10 pre-hash switch) were bcrypt(raw pw).
        # Still accept them so no existing login breaks; they migrate to the pre-hash
        # scheme automatically the next time the password is set (register/reset/invite).
        return bcrypt.checkpw((pw or "").encode("utf-8"), h)
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


def rate_clear(key):
    """Forget a key's attempts after a SUCCESSFUL authentication — the cap exists to
    slow guessing, not to lock out a NAT-shared office where 30 people signing in
    normally within five minutes exhausted the per-IP tier (pre-prod audit 2026-08-12)."""
    _attempts.pop(key, None)


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


# ------------------------------------------- MFA (email one-time code) -----
# A password-verified login mints a short-lived challenge; the real session is
# only created once the emailed 6-digit code is verified. The code is stored
# HASHED (never plaintext), expires quickly, and is capped at a handful of
# attempts. Cyber Essentials A7.16/A7.17 (MFA on cloud-service accounts).
MFA_TTL_MINUTES = 10
MFA_MAX_ATTEMPTS = 5


def create_mfa_challenge(user_id):
    """Mint a challenge + 6-digit code for a user. Returns (challenge_token, code).
    Any earlier unconsumed challenges for the user are invalidated so only the
    latest code works."""
    conn = get_conn()
    conn.execute("UPDATE mfa_challenges SET consumed_at=datetime('now') "
                 "WHERE user_id=? AND consumed_at IS NULL", (user_id,))
    challenge = secrets.token_urlsafe(24)
    code = "%06d" % secrets.randbelow(1_000_000)
    expires = (datetime.utcnow() + timedelta(minutes=MFA_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO mfa_challenges(challenge, user_id, code_hash, expires_at) VALUES (?,?,?,?)",
                 (challenge, user_id, hash_password(code), expires))
    conn.commit()
    return challenge, code


def verify_mfa_challenge(challenge, code):
    """Return the user_id on a correct, unexpired, not-yet-consumed, under-attempt-cap
    challenge (consuming it); else None. Wrong guesses increment the attempt counter."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM mfa_challenges WHERE challenge=? AND consumed_at IS NULL "
        "AND expires_at > datetime('now')", (challenge,)).fetchone()
    if row is None or row["attempts"] >= MFA_MAX_ATTEMPTS:
        return None
    if not verify_password(code or "", row["code_hash"]):
        conn.execute("UPDATE mfa_challenges SET attempts=attempts+1 WHERE challenge=?", (challenge,))
        conn.commit()
        return None
    conn.execute("UPDATE mfa_challenges SET consumed_at=datetime('now') WHERE challenge=?", (challenge,))
    conn.commit()
    return row["user_id"]


def mfa_challenge_user(challenge):
    """The user_id behind a still-valid challenge (for 'resend'), or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id FROM mfa_challenges WHERE challenge=? AND consumed_at IS NULL "
        "AND expires_at > datetime('now')", (challenge,)).fetchone()
    return row["user_id"] if row else None
