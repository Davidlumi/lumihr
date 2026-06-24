# -*- coding: utf-8 -*-
"""NOTIFICATIONS QA — signal change alerts.

Hermetic: drives notifications.py against an in-memory DB seeded with explicit
before/after signal sets, so diff correctness, bucket discipline, guardrails,
prefs and the email rate cap are all checked with zero UI and no network.

Run after any change to the alert logic or the `alert` block in
signal_lenses.json.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notifications as N

# qa_hero owns the canonical banned-directive list; copied (not imported —
# importing qa_hero would execute its suite). Keep in sync.
DIRECTIVE = ("should", "must", "we recommend", "you need to", "increase your", "reduce your")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print("  %s %-66s %s" % ("PASS" if ok else "FAIL", name[:66], ("| " + str(detail)[:80]) if detail and not ok else ""))


def fresh_db():
    """Minimal schema the notifications layer touches."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE orgs(org_id TEXT PRIMARY KEY, name TEXT);
      CREATE TABLE users(user_id TEXT PRIMARY KEY, org_id TEXT, email TEXT, notify_prefs_json TEXT NOT NULL DEFAULT '{}');
      CREATE TABLE signal_state(org_id TEXT, signal_key TEXT, lens TEXT, kind TEXT, question_id TEXT,
        value_display TEXT, bucket TEXT NOT NULL, detail TEXT NOT NULL,
        first_seen TEXT DEFAULT (datetime('now')), last_seen TEXT DEFAULT (datetime('now')),
        PRIMARY KEY(org_id, signal_key));
      CREATE TABLE notification_events(id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT, event_kind TEXT,
        signal_key TEXT, lens TEXT, question_id TEXT, payload_json TEXT, detected_at TEXT DEFAULT (datetime('now')));
      CREATE TABLE notification_reads(user_id TEXT, event_id INTEGER, read_at TEXT, emailed_at TEXT,
        suppressed_reason TEXT, PRIMARY KEY(user_id, event_id));
    """)
    conn.execute("INSERT INTO orgs VALUES('o1','Test Org')")
    conn.commit()
    return conn


def sig(lens, kind, qid, vd, detail, worth=True, row=""):
    sid = qid + ("::" + row if row else "")
    return {"lens": lens, "kind": kind, "question_id": qid, "sig_id": sid,
            "value_display": vd, "detail": detail, "name": qid, "tag": "X", "worth": worth}


# stub the cleared-message label lookup (avoids loading the question library)
N._LABELS["cache"] = {"Q_behind": "Flexible allowance", "Q_money": "Bonus", "Q_prev": "Pay in adverts"}


# ---- 1. diff correctness: appeared / moved / cleared ------------------------
conn = fresh_db()
a = sig("save", "behind", "Q_behind", "P30", "You sit at P30 on flexible allowance.")
ev = N.diff_and_record(conn, "o1", [a])
check("appeared: first sighting fires one 'appeared'", len(ev) == 1 and ev[0]["event_kind"] == "appeared", ev)
check("appeared: signal_state now holds the signal",
      conn.execute("SELECT COUNT(*) c FROM signal_state WHERE org_id='o1'").fetchone()["c"] == 1)

a2 = sig("save", "behind", "Q_behind", "P5", "You sit at P5 on flexible allowance.")
ev = N.diff_and_record(conn, "o1", [a2])   # P30 (b2) -> P5 (b0): crosses
check("moved: a bucket-crossing move fires one 'moved'", len(ev) == 1 and ev[0]["event_kind"] == "moved", ev)
check("moved: payload carries the previous value",
      ev and N.render_event(ev[0])["body"].endswith("(was P30)"), ev and N.render_event(ev[0])["body"])

ev = N.diff_and_record(conn, "o1", [])     # gone
check("cleared: a vanished signal fires one 'cleared'", len(ev) == 1 and ev[0]["event_kind"] == "cleared", ev)
check("cleared: signal_state row removed",
      conn.execute("SELECT COUNT(*) c FROM signal_state WHERE org_id='o1'").fetchone()["c"] == 0)


# ---- 2. bucket discipline: sub-bucket wobble is silent ----------------------
conn = fresh_db()
N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P30", "d")])  # b2 (>25)
ev = N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P28", "d")])  # still b2
check("bucket: same-bucket wobble (P30->P28) produces no event", len(ev) == 0, ev)
check("bucket: value_display still updated silently",
      conn.execute("SELECT value_display FROM signal_state WHERE org_id='o1'").fetchone()["value_display"] == "P28")

conn = fresh_db()
N.diff_and_record(conn, "o1", [sig("save", "money", "Q_money", "£60k", "d")])   # b1 (>=50k)
ev = N.diff_and_record(conn, "o1", [sig("save", "money", "Q_money", "£64k", "d")])  # still b1; <10k change
check("bucket: money sub-bucket + <£10k change is silent", len(ev) == 0, ev)
ev = N.diff_and_record(conn, "o1", [sig("save", "money", "Q_money", "£120k", "d")])  # b2, >£10k
check("bucket: money crossing £100k with >£10k change fires", len(ev) == 1 and ev[0]["event_kind"] == "moved", ev)


# ---- 3. fan-out + content prefs (lens / event / £ floor) --------------------
def seed_user(conn, uid, prefs_json="{}"):
    conn.execute("INSERT INTO users VALUES(?,?,?,?)", (uid, "o1", uid + "@x.com", prefs_json))
    conn.commit()

import json
conn = fresh_db()
seed_user(conn, "u_all")                                   # defaults: inbox on, all lenses/events
seed_user(conn, "u_attract", json.dumps({"lenses": ["attract"]}))   # only attract
seed_user(conn, "u_noclear", json.dumps({"events": ["appeared", "moved"]}))  # mutes good news
ev = N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P30", "d")])
N.fan_out(conn, "o1", ev)
check("fan-out: default user gets a row",
      conn.execute("SELECT COUNT(*) c FROM notification_reads WHERE user_id='u_all'").fetchone()["c"] == 1)
check("prefs: muted lens (attract-only) gets NO row for a save event",
      conn.execute("SELECT COUNT(*) c FROM notification_reads WHERE user_id='u_attract'").fetchone()["c"] == 0)

ev = N.diff_and_record(conn, "o1", [])   # cleared
N.fan_out(conn, "o1", ev)
check("prefs: cleared on by default reaches the default user",
      conn.execute("SELECT COUNT(*) c FROM notification_reads r JOIN notification_events e ON e.id=r.event_id "
                   "WHERE r.user_id='u_all' AND e.event_kind='cleared'").fetchone()["c"] == 1)
check("prefs: a user who muted good news gets NO cleared row",
      conn.execute("SELECT COUNT(*) c FROM notification_reads r JOIN notification_events e ON e.id=r.event_id "
                   "WHERE r.user_id='u_noclear' AND e.event_kind='cleared'").fetchone()["c"] == 0)

conn = fresh_db()
seed_user(conn, "u_bigfloor", json.dumps({"min_money_gbp": 200000}))
ev = N.diff_and_record(conn, "o1", [sig("save", "money", "Q_money", "£60k", "d")])
N.fan_out(conn, "o1", ev)
check("prefs: £ below the user's personal floor gets no row",
      conn.execute("SELECT COUNT(*) c FROM notification_reads WHERE user_id='u_bigfloor'").fetchone()["c"] == 0)


# ---- 4. email: default off, rate cap, inbox uncapped ------------------------
conn = fresh_db()
seed_user(conn, "u_default")                          # default prefs -> weekly digest (opt-out)
seed_user(conn, "u_off", json.dumps({"email_frequency": "off"}))   # explicitly opted out
ev = N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P30", "d")])
N.fan_out(conn, "o1", ev)
# stub send to count, not actually send
sent_log = []
import app
_real_send = app.send_notification
app.send_notification = lambda subj, body, to=None: sent_log.append(to)
N.run_email_digest(conn)
check("email: default user (weekly) receives a digest", "u_default@x.com" in sent_log, sent_log)
check("email: explicitly opted-out user receives no digest", "u_off@x.com" not in sent_log, sent_log)
check("inbox-vs-email: the bell row exists for the off user regardless of email",
      conn.execute("SELECT COUNT(*) c FROM notification_reads WHERE user_id='u_off'").fetchone()["c"] == 1)

# rate cap: 3 digests already this week -> a 4th is blocked, rows stay unemailed
conn = fresh_db()
seed_user(conn, "u_cap", json.dumps({"email_frequency": "daily"}))
ev = N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P30", "d")])
N.fan_out(conn, "o1", ev)
eid = conn.execute("SELECT event_id FROM notification_reads WHERE user_id='u_cap'").fetchone()["event_id"]
for t in ("-1 days", "-2 days", "-3 days"):   # 3 distinct prior digests this week
    conn.execute("INSERT INTO notification_reads(user_id,event_id,emailed_at) VALUES('u_cap',?,datetime('now',?))", (90000 + hash(t) % 1000, t))
conn.commit()
sent_log = []
N.run_email_digest(conn)
check("rate cap: a 4th email in the week is blocked", "u_cap@x.com" not in sent_log, sent_log)
check("rate cap: the blocked event stays unemailed (rolls forward), still in the bell",
      conn.execute("SELECT emailed_at FROM notification_reads WHERE user_id='u_cap' AND event_id=?", (eid,)).fetchone()["emailed_at"] is None)
app.send_notification = _real_send


# ---- 5. wording: never a directive --------------------------------------
conn = fresh_db()
evs = N.diff_and_record(conn, "o1", [sig("save", "behind", "Q_behind", "P30", "You sit at P30 on flexible allowance."),
                                     sig("retain", "money", "Q_money", "£60k", "£60k gap to the peer median.")])
evs += N.diff_and_record(conn, "o1", [])   # clear them -> cleared messages too
texts = []
for e in conn.execute("SELECT * FROM notification_events WHERE org_id='o1'"):
    r = N.render_event(dict(e))
    texts += [r["title"], r["body"]]
bad = [t for t in texts if any(d in (t or "").lower() for d in DIRECTIVE)]
check("wording: no directive verb in any rendered alert (title or body)", not bad, bad)

# ---- 6. unsubscribe semantics (email off, inbox intact) ---------------------
p = N.user_prefs(json.dumps({"email_frequency": "weekly", "inbox_enabled": True}))
p_unsub = N.user_prefs(json.dumps({"email_frequency": "off", "inbox_enabled": True}))
check("unsubscribe: flipping email to off leaves the inbox enabled",
      p_unsub["email_frequency"] == "off" and p_unsub["inbox_enabled"] is True)


print()
fails = len(RESULTS) - sum(RESULTS)
print("RESULTS: %d checks, %d passed, %d failed" % (len(RESULTS), sum(RESULTS), fails))
sys.exit(1 if fails else 0)
