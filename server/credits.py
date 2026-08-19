# -*- coding: utf-8 -*-
"""Pulse credits — the entitlement to run a pulse (David's ruling, 2026-08-19).

One credit buys one pulse, end to end. Every organisation is granted ONE on creation, so
the first pulse is genuinely free; further credits are bought by contacting lumi and are
invoiced offline, in line with PH-PAY-1 (all payments by invoice). Credits REPLACE the
per-pulse launch fee — there is no second charge at launch.

THE LEDGER IS THE BALANCE. There is no stored balance column, because a stored balance and
an audit trail can disagree and then nobody can say which is right. `balance()` is
SUM(delta) over credit_ledger, so the number on screen is arithmetically the history that
produced it. Every movement carries who, when, how many, why.

WHEN A CREDIT IS SPENT: at LAUNCH, and never refunded (David's ruling). Drafting, editing
and submitting for review are all free, so nobody loses a credit to an abandoned draft or a
rejected review. The balance is checked twice — once when the member requests launch, so
they are told early, and again inside the same transaction that opens the pulse, because
two pulses can be requested against one credit.

Every function takes an open connection; nothing here commits. The caller owns the
transaction, so a spend and the launch it pays for succeed or fail together.
"""
import uuid

SIGNUP_GRANT = 1                 # what a new organisation starts with
LAUNCH_COST = 1                  # what opening one pulse costs

KINDS = ("signup_grant", "purchase", "adjustment", "pulse_launch")


class InsufficientCredits(Exception):
    """Raised instead of returning False so a spend can never be ignored by accident."""

    def __init__(self, balance, needed):
        self.balance = balance
        self.needed = needed
        super().__init__("needs %d credit(s), balance is %d" % (needed, balance))


def balance(org_id, conn):
    r = conn.execute("SELECT COALESCE(SUM(delta), 0) AS b FROM credit_ledger WHERE org_id=?",
                     (org_id,)).fetchone()
    return int(r["b"] if hasattr(r, "keys") else r[0])


def _entry(conn, org_id, delta, kind, reason, actor_user_id=None, pulse_id=None):
    if kind not in KINDS:
        raise ValueError("unknown credit kind: %r" % kind)
    if delta == 0:
        raise ValueError("a zero-delta ledger entry says nothing — refusing")
    eid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO credit_ledger(entry_id, org_id, delta, kind, reason, pulse_id, "
        "actor_user_id) VALUES (?,?,?,?,?,?,?)",
        (eid, org_id, int(delta), kind, (reason or "").strip(), pulse_id, actor_user_id))
    return eid


def grant_signup(org_id, conn, amount=SIGNUP_GRANT):
    """Idempotent: an organisation gets its joining credit exactly once, however many
    times provisioning is retried."""
    seen = conn.execute("SELECT 1 FROM credit_ledger WHERE org_id=? AND kind='signup_grant'",
                        (org_id,)).fetchone()
    if seen or amount <= 0:
        return None
    return _entry(conn, org_id, amount, "signup_grant",
                  "Joining credit — one pulse included")


def adjust(org_id, delta, reason, actor_user_id, conn, kind="adjustment"):
    """Staff grant or deduction. A reason is required: a balance nobody can explain is the
    thing this ledger exists to prevent."""
    delta = int(delta)
    if not (reason or "").strip():
        raise ValueError("Give a reason — it is what makes the ledger worth having.")
    if delta < 0 and balance(org_id, conn) + delta < 0:
        raise InsufficientCredits(balance(org_id, conn), -delta)
    return _entry(conn, org_id, delta, kind, reason, actor_user_id=actor_user_id)


def spend_for_launch(org_id, pulse_id, conn, actor_user_id=None, cost=LAUNCH_COST):
    """Deduct the launch credit. Raises InsufficientCredits rather than opening a pulse
    nobody paid for. Call inside the same transaction that opens the pulse."""
    have = balance(org_id, conn)
    if have < cost:
        raise InsufficientCredits(have, cost)
    return _entry(conn, org_id, -cost, "pulse_launch",
                  "Pulse launched", actor_user_id=actor_user_id, pulse_id=pulse_id)


def ledger(org_id, conn, limit=200):
    """Newest first, each row carrying the balance as it stood after that movement — which
    is what makes a disputed invoice answerable."""
    rows = [dict(r) for r in conn.execute(
        "SELECT entry_id, delta, kind, reason, pulse_id, actor_user_id, created_at "
        "FROM credit_ledger WHERE org_id=? ORDER BY created_at, rowid", (org_id,)).fetchall()]
    running = 0
    for r in rows:
        running += r["delta"]
        r["balance_after"] = running
    rows.reverse()
    return rows[:limit]


def summary(org_id, conn):
    r = conn.execute(
        "SELECT COALESCE(SUM(delta),0) AS bal, "
        "COALESCE(SUM(CASE WHEN delta>0 THEN delta ELSE 0 END),0) AS granted, "
        "COALESCE(SUM(CASE WHEN delta<0 THEN -delta ELSE 0 END),0) AS spent "
        "FROM credit_ledger WHERE org_id=?", (org_id,)).fetchone()
    return {"balance": int(r["bal"]), "granted": int(r["granted"]), "spent": int(r["spent"])}


def balances_batch(org_ids, conn):
    """One query for the whole organisations table rather than N."""
    if not org_ids:
        return {}
    marks = ",".join("?" * len(org_ids))
    rows = conn.execute(
        "SELECT org_id, COALESCE(SUM(delta),0) AS b FROM credit_ledger "
        "WHERE org_id IN (%s) GROUP BY org_id" % marks, list(org_ids)).fetchall()
    out = {o: 0 for o in org_ids}
    for r in rows:
        out[r["org_id"]] = int(r["b"])
    return out
