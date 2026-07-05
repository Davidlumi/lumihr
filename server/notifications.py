# -*- coding: utf-8 -*-
"""Signal change alerts (notifications) — pure data + config layer.

Signals are computed live and not persisted, so there is nothing to diff
against. This module gives them a stored history (signal_state), detects the
three change events (appeared / cleared / moved), records them to a single
event log (notification_events), fans them out per-user honouring prefs +
guardrails (notification_reads), and renders the in-app inbox + email digest.

The cardinal stance carries over from signals: an alert states a fact and says
"worth a look" — never what to do. The inbox and email reuse the signal
`detail` strings verbatim (they already pass qa_hero's directive gate), so a
directive can't sneak in via the notification layer. Templates add neutral
framing only.

Materiality buckets live in signal_lenses.json under `alert` (David owns the
thresholds, consistent with the rest of that file). A `moved` event fires only
when a figure crosses a bucket boundary, so peer jitter stays silent.
"""
import json
import re
from datetime import datetime

from signals import lens_config, signal_key

# kinds that carry a numeric we can bucket for "moved" events. Everything else
# (ahead / outlier / depth / rare) only ever fires appeared / cleared.
_BUCKET_KIND = {"behind": "behind", "save": "save", "prevalence": "prevalence", "money": "money"}

_DEFAULT_ALERT = {
    "buckets": {"behind": [10, 25], "save": [85, 95], "prevalence": [50, 75, 90],
                "money": [10000, 50000, 100000]},
    "min_money_change_gbp": 10000,
    "max_emails_per_org_per_week": 3,
    "min_hours_between_emails": 24,
    "email_digest_default": "weekly",
}


def alert_cfg():
    """The `alert` block from signal_lenses.json, merged over safe defaults.
    Inherits the file's keep-last-good behaviour on a malformed config."""
    cfg = (lens_config() or {}).get("alert") or {}
    out = dict(_DEFAULT_ALERT)
    out.update({k: v for k, v in cfg.items() if not str(k).startswith("_")})
    if not isinstance(out.get("buckets"), dict):
        out["buckets"] = _DEFAULT_ALERT["buckets"]
    return out


# --------------------------------------------------------------- bucketing ---
def materiality(kind, value_display):
    """The raw number we bucket, parsed from the figure shown on the signal.
    Percentiles ('P5'), shares ('56%') and money ('£75k/yr', '£1.2m') all read
    back cleanly enough for boundaries at P10/P25, 50/75/90%, £10k/50k/100k."""
    s = str(value_display or "")
    if kind == "money":
        m = re.search(r"£\s*([\d,.]+)\s*([km]?)", s, re.I)
        if not m:
            return None
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            return None
        suf = (m.group(2) or "").lower()
        return n * (1000 if suf == "k" else 1_000_000 if suf == "m" else 1)
    m = re.search(r"P(\d+)", s)            # percentile
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)\s*%", s)      # share
    if m:
        return float(m.group(1))
    return None


def bucket_of(kind, value_display, alert):
    """A materiality step label. Same label across sub-bucket drift (so jitter
    is silent); changes only when a boundary is crossed. Kinds without a bucket
    config collapse to a single 'present' step (appeared/cleared only)."""
    key = _BUCKET_KIND.get(kind)
    bounds = (alert.get("buckets") or {}).get(key) if key else None
    v = materiality(kind, value_display)
    if not bounds or v is None:
        return "present"
    return "b%d" % sum(1 for b in bounds if v >= b)


def _kind_of(signal_key_str):
    parts = (signal_key_str or "").split(":")
    return parts[1] if len(parts) > 1 else ""


# ---------------------------------------------------------------- labels ------
_LABELS = {"cache": None}


def _label(question_id):
    """Human metric label for a cleared message (the cleared event has no live
    signal to borrow `name` from). Metadata only — not firewall data."""
    if _LABELS["cache"] is None:
        try:
            from library import load_questions
            _LABELS["cache"] = {qid: (q.display_title or q.text) for qid, q in load_questions().items()}
        except Exception:
            _LABELS["cache"] = {}
    return _LABELS["cache"].get(question_id, "this metric")


# ----------------------------------------------------------- diff + record ----
def record_baseline(conn, org_id, fresh_signals):
    """First time we ever see an org: store its signal set WITHOUT firing
    'appeared' for every existing flag (that would flood the bell on day one).
    Alerts are about CHANGES from this baseline."""
    alert = alert_cfg()
    for s in fresh_signals:
        k = signal_key(s)
        kind = s.get("kind", "")
        vd = s.get("value_display")
        conn.execute(
            "INSERT OR REPLACE INTO signal_state(org_id, signal_key, lens, kind, question_id, value_display, bucket, detail) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (org_id, k, s.get("lens", ""), kind, s.get("question_id", ""), vd,
             bucket_of(kind, vd, alert), s.get("detail") or s.get("stand") or ""))
    conn.commit()
    return []


def rebaseline(conn, org_id, fresh_signals):
    """Silent RE-baseline (step-3 notification coherence): fully replace the org's signal_state
    with a fresh set, firing NO events. Used when the org's OWN deliberate act — a strategy change
    — re-sorts what's worth flagging: that must quietly re-baseline the bell, never storm it (the
    inverse of the cut-drift stable ruling; parallel to the transparency reconfirm gate). DELETE
    first so a strategy effect that REMOVES signals (e.g. location-agnostic) can't leave stale rows
    the next sweep would 'clear'."""
    conn.execute("DELETE FROM signal_state WHERE org_id=?", (org_id,))
    return record_baseline(conn, org_id, fresh_signals)


def event_is_confirm(event):
    """True iff this event confirms the org's strategy aim (payload.confirm) — quiet, never leads
    the bell and never emailed. Accepts a DB row (payload_json) or an in-flight event dict."""
    event = dict(event)                    # sqlite3.Row has no .get — same normalise as render_event
    p = event.get("payload") if isinstance(event.get("payload"), dict) else None
    if p is None:
        try:
            p = json.loads(event.get("payload_json") or "{}")
        except (ValueError, TypeError):
            p = {}
    return bool(p.get("confirm"))


def diff_and_record(conn, org_id, fresh_signals):
    """Diff stored signal_state vs a freshly-built signal set for one org.
    Writes appeared/cleared/moved rows to notification_events and updates
    signal_state. Returns the event rows (with their new ids) for fan-out.

    Self-caused vs market-caused is intentionally NOT distinguished — a self
    edit that flips a flag is useful confirmation it landed."""
    alert = alert_cfg()
    stored = {r["signal_key"]: dict(r) for r in conn.execute(
        "SELECT * FROM signal_state WHERE org_id=?", (org_id,))}
    fresh = {}
    for s in fresh_signals:
        fresh[signal_key(s)] = s
    events = []

    for k, s in fresh.items():
        kind = s.get("kind", "")
        vd = s.get("value_display")
        detail = s.get("detail") or s.get("stand") or ""
        bucket = bucket_of(kind, vd, alert)
        if k not in stored:
            events.append({"event_kind": "appeared", "signal_key": k, "lens": s.get("lens", ""),
                           "question_id": s.get("question_id", ""),
                           "payload": {"kind": kind, "name": s.get("name"), "tag": s.get("tag"),
                                       "detail": detail, "value_display": vd,
                                       "prev_value": None, "worth": bool(s.get("worth")),
                                       "confirm": bool(s.get("confirm"))}})
            conn.execute(
                "INSERT INTO signal_state(org_id, signal_key, lens, kind, question_id, value_display, bucket, detail) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (org_id, k, s.get("lens", ""), kind, s.get("question_id", ""), vd, bucket, detail))
        else:
            prev = stored[k]
            crossed = prev["bucket"] != bucket
            if crossed and kind == "money":
                pv, nv = materiality("money", prev["value_display"]), materiality("money", vd)
                if pv is not None and nv is not None and abs(nv - pv) < alert.get("min_money_change_gbp", 10000):
                    crossed = False
            if crossed:
                events.append({"event_kind": "moved", "signal_key": k, "lens": s.get("lens", ""),
                               "question_id": s.get("question_id", ""),
                               "payload": {"kind": kind, "name": s.get("name"), "tag": s.get("tag"),
                                           "detail": detail, "value_display": vd,
                                           "prev_value": prev["value_display"], "worth": bool(s.get("worth")),
                                           "confirm": bool(s.get("confirm"))}})
            conn.execute(
                "UPDATE signal_state SET lens=?, kind=?, value_display=?, bucket=?, detail=?, last_seen=datetime('now') "
                "WHERE org_id=? AND signal_key=?",
                (s.get("lens", ""), kind, vd, bucket, detail, org_id, k))

    for k, prev in stored.items():
        if k not in fresh:
            events.append({"event_kind": "cleared", "signal_key": k, "lens": prev["lens"],
                           "question_id": prev["question_id"],
                           "payload": {"kind": prev["kind"], "name": _label(prev["question_id"]),
                                       "tag": "CLEARED",
                                       "detail": "%s no longer flags against your peers." % _label(prev["question_id"]),
                                       "value_display": None, "prev_value": prev["value_display"], "worth": False}})
            conn.execute("DELETE FROM signal_state WHERE org_id=? AND signal_key=?", (org_id, k))

    for e in events:
        cur = conn.execute(
            "INSERT INTO notification_events(org_id, event_kind, signal_key, lens, question_id, payload_json) "
            "VALUES (?,?,?,?,?,?)",
            (org_id, e["event_kind"], e["signal_key"], e["lens"], e["question_id"], json.dumps(e["payload"])))
        e["id"] = cur.lastrowid
    conn.commit()
    return events


# ------------------------------------------------------------ user prefs ------
ALL_LENSES = ["save", "attract", "retain", "engage"]
ALL_EVENTS = ["appeared", "moved", "cleared"]


def user_prefs(notify_prefs_json, alert=None):
    """Per-user notification prefs merged over defaults: inbox on, email a
    WEEKLY digest by default (opt-out — switch to Daily or Off any time), all
    lenses, all events (cleared = good news, on by default), and David's £ floor
    (the personal floor can be stricter, never looser)."""
    alert = alert or alert_cfg()
    try:
        p = json.loads(notify_prefs_json or "{}") or {}
    except (ValueError, TypeError):
        p = {}
    floor = max(int(p.get("min_money_gbp") or 0), int(alert.get("min_money_change_gbp", 10000)))
    return {
        "inbox_enabled": p.get("inbox_enabled", True),
        "email_frequency": p.get("email_frequency", alert.get("email_digest_default", "weekly")),  # off | daily | weekly
        "lenses": list(p.get("lenses") or ALL_LENSES),
        "events": list(p.get("events") or ALL_EVENTS),
        "min_money_gbp": floor,
    }


def _content_ok(event, prefs):
    """Does this event pass the user's CONTENT filters (lens / event-type /
    £ floor)? Drops here mean no inbox row at all for that user."""
    if event["lens"] not in prefs["lenses"]:
        return False
    if event["event_kind"] not in prefs["events"]:
        return False
    payload = event.get("payload") or {}
    if (payload.get("kind") or _kind_of(event["signal_key"])) == "money":
        v = materiality("money", payload.get("value_display") or payload.get("prev_value"))
        if v is not None and v < prefs["min_money_gbp"]:
            return False
    return True


def fan_out(conn, org_id, events):
    """Create a notification_reads row for every (user, event) the user's
    content prefs admit. The bell + digest apply the inbox/email toggles at
    read time, so flipping them never needs a re-fan."""
    if not events:
        return 0
    users = conn.execute("SELECT user_id, notify_prefs_json FROM users WHERE org_id=?", (org_id,)).fetchall()
    n = 0
    for u in users:
        prefs = user_prefs(u["notify_prefs_json"])
        for e in events:
            if not _content_ok(e, prefs):
                continue
            conn.execute("INSERT OR IGNORE INTO notification_reads(user_id, event_id) VALUES (?,?)",
                         (u["user_id"], e["id"]))
            n += 1
    conn.commit()
    return n


# --------------------------------------------------------------- rendering ----
def render_event(event):
    """Inbox-ready view of one event, assembled only from the stored factual
    strings (templates add neutral framing only — never a directive)."""
    event = dict(event)                    # accept a DB row or an in-flight event dict
    payload = event["payload"] if isinstance(event.get("payload"), dict) else json.loads(event["payload_json"])
    kind = event["event_kind"]
    name = payload.get("name") or _label(event["question_id"])
    # COMPLETE SENTENCES ONLY: the prevalence signal's stored detail ("of peers X —
    # you don't yet") is written to sit AFTER the value the Signals page renders
    # beside it. A notification (and the email digest) has no such neighbour, so
    # compose the value back in at read time — heals already-stored events too.
    if (payload.get("detail") or "").startswith("of peers") and payload.get("value_display"):
        payload = dict(payload, detail="%s %s" % (payload["value_display"], payload["detail"]))
    if kind == "cleared":
        title = "Cleared"
        body = payload.get("detail") or ("%s no longer flags against your peers." % name)
    elif kind == "moved":
        title = "Worth a look" if payload.get("worth") else "Update"
        body = payload.get("detail") or ""
        if payload.get("prev_value"):
            body = "%s (was %s)" % (body, payload["prev_value"])
    else:  # appeared
        title = "Worth a look" if payload.get("worth") else "New"
        body = payload.get("detail") or ""
    # notification coherence (step-3, ruling C): a change that CONFIRMS the org's strategy aim is
    # quiet — "On plan", never "Worth a look". Mirrors L4 demoting a confirming signal off the home
    # briefing while keeping it findable (cleared stays as-is — an absence has no confirm sense).
    confirm = bool(payload.get("confirm")) and kind != "cleared"
    if confirm:
        title = "On plan"
    return {"id": event.get("id"), "event_kind": kind, "lens": event["lens"],
            "question_id": event["question_id"], "title": title, "body": body, "confirm": confirm,
            "tag": payload.get("tag"), "name": name, "detected_at": event.get("detected_at")}


# ----------------------------------------------------------- email digest -----
def _live_at_send(conn, event):
    """Suppression re-check at send time: an appeared/moved figure must still be
    a live (non-suppressed) signal. If a cut fell below the n>=5 floor between
    detection and the digest, the last sweep removed it from signal_state — so
    we never email a peer figure that wouldn't render in-app. Cleared (an
    absence) is always safe to send."""
    if event["event_kind"] == "cleared":
        return True
    return conn.execute("SELECT 1 FROM signal_state WHERE org_id=? AND signal_key=?",
                        (event["org_id"], event["signal_key"])).fetchone() is not None


def _email_allowed(conn, user_id, alert):
    """Rate cap: max emails/week + min gap. A digest is one email regardless of
    how many changes it carries (distinct emailed_at = one digest)."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT emailed_at) c, MAX(emailed_at) last FROM notification_reads "
        "WHERE user_id=? AND emailed_at IS NOT NULL AND emailed_at >= datetime('now','-7 days')",
        (user_id,)).fetchone()
    if (row["c"] or 0) >= alert.get("max_emails_per_org_per_week", 3):
        return False
    if row["last"]:
        too_soon = conn.execute(
            "SELECT ? >= datetime('now', ?) AS x",
            (row["last"], "-%d hours" % int(alert.get("min_hours_between_emails", 24)))).fetchone()["x"]
        if too_soon:
            return False
    return True


def _digest_subject(n, freq):
    word = {"daily": "today", "weekly": "this week"}.get(freq, "recently")
    return "lumi: %d thing%s moved against your peers %s" % (n, "" if n == 1 else "s", word)


def _digest_body(org_name, events, settings_link, overview_link):
    """Plain text, clock-reminder voice. Worth-a-look + good-news sections, both
    built from stored detail strings. Never a metric name in the subject."""
    worth = [render_event(e) for e in events if e["event_kind"] != "cleared"]
    good = [render_event(e) for e in events if e["event_kind"] == "cleared"]
    lines = ["Hello %s," % org_name, "",
             "Since we last wrote, here's what changed in how you sit against your peers.",
             "These are pointers, not advice — open lumi to see the full picture.", ""]
    if worth:
        lines.append("WORTH A LOOK")
        lines += ["- %s" % w["body"] for w in worth]
        lines.append("")
    if good:
        lines.append("GOOD NEWS")
        lines += ["- %s" % g["body"] for g in good]
        lines.append("")
    lines += ["See these in context: %s" % overview_link,
              "Change how often you hear from us: %s" % settings_link,
              "", "— lumi"]
    return "\n".join(lines)


def run_email_digest(conn, base_url="", frequencies=("daily", "weekly")):
    """Send digests to opted-in users with not-yet-emailed admitted events.
    Groups by user, re-checks suppression + rate cap, sends one email, stamps
    emailed_at. Excess (over the cap) stays unemailed and rolls to next time —
    it is never dropped and the bell still shows it. send_notification is
    imported lazily to avoid an import cycle with app.py."""
    from app import send_notification  # lazy: app imports this module
    alert = alert_cfg()
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM notification_reads WHERE emailed_at IS NULL AND suppressed_reason IS NULL").fetchall()
    sent = 0
    for ur in rows:
        uid = ur["user_id"]
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if not user:
            continue
        prefs = user_prefs(user["notify_prefs_json"], alert)
        if prefs["email_frequency"] not in frequencies:
            continue
        if not _email_allowed(conn, uid, alert):
            continue
        pending = conn.execute(
            "SELECT e.* FROM notification_reads r JOIN notification_events e ON e.id=r.event_id "
            "WHERE r.user_id=? AND r.emailed_at IS NULL AND r.suppressed_reason IS NULL "
            "ORDER BY e.detected_at",
            (uid,)).fetchall()
        # notification coherence (step-3, ruling C): a confirm-flagged change is on-plan — it stays
        # in the in-app inbox (quiet) but is NEVER pushed in the email digest (the push channel is
        # the "briefing"; confirm is demoted off it, exactly as L4 demotes it off the home briefing).
        # It stays emailed_at NULL = inert in the email path; an org with ONLY confirm changes mails nothing.
        live = [e for e in pending if _live_at_send(conn, e) and not event_is_confirm(e)]
        if not live:
            continue
        org = conn.execute("SELECT name FROM orgs WHERE org_id=?", (user["org_id"],)).fetchone()
        subj = _digest_subject(len(live), prefs["email_frequency"])
        body = _digest_body(org["name"] if org else "there", live,
                            base_url + "/#/settings", base_url + "/#/overview")
        send_notification(subj, body, to=user["email"])
        ids = [e["id"] for e in live]
        conn.executemany("UPDATE notification_reads SET emailed_at=datetime('now') WHERE user_id=? AND event_id=?",
                         [(uid, i) for i in ids])
        conn.commit()
        sent += 1
    return sent
