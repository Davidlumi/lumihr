# -*- coding: utf-8 -*-
"""Core question-set versioning & governance (2026-06-12).

A RELEASE is a named, dated version of the core question set. The live core
== the current release; prior releases reconstruct exactly from their stored
snapshots. Reproducing a benchmark needs BOTH dimensions: the question set
as-of a release AND the data period (snapshots.collection_window) — a trend
is the same question version across data periods.

Rules encoded here:
- Retire, never delete: leaving questions get status='retired' +
  release_retired; they vanish from the live member experience but stay in
  the questions table and in every release snapshot that contained them, so
  historical benchmarks still resolve. Retiring a required question simply
  shrinks the required set (the gate can only get easier).
- Change log: written by the RELEASE DIFF (added/retired/reworded vs the
  previous release), one source of truth. The emergency lane is the only
  path that logs between releases.
- Emergency lane: for questions that became FACTUALLY WRONG due to an
  external change (statutory baseline moved, etc.) — requires an explicit
  external trigger AND sign-off; routine additions wait for a release.
- Backlog: a real stored queue (core_backlog) feeding releases; items are
  never auto-applied to the live core.
- Comparability breaks: 'break@<release_id>' markers appended to the
  library's historical_comparability field (alongside its high/medium/low
  rating); the trend layer must never draw a continuous line across one.

This module changes NO metric computation — versioning plumbing only.
"""
import csv
import json
import os
import re

from db import get_conn, j, uj

BASELINE_ID = "2025-baseline"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                        "lumi_questions.csv")

_GOV_COLS = ("question_version", "historical_comparability", "status", "replaced_by")


def current_release(conn=None):
    conn = conn or get_conn()
    return conn.execute("SELECT * FROM core_releases WHERE status='current' "
                        "ORDER BY released_at DESC LIMIT 1").fetchone()


def _question_row(conn, qid):
    return conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()


def _live_core(conn):
    """The live core = active (non-retired) questions in the active scope.
    Scope mirrors the launch focus (Reward) without importing app config."""
    sps = [s.strip() for s in os.environ.get("LUMI_ACTIVE_SUPERPOWERS", "Reward").split(",") if s.strip()]
    qmarks = ",".join("?" * len(sps))
    return conn.execute(
        "SELECT * FROM questions WHERE superpower IN (%s) AND status != 'retired' "
        "ORDER BY question_order" % qmarks, sps).fetchall()


def ensure_governance_backfill(conn=None):
    """One-time: copy the governance fields from the library CSV into the
    questions table (they were never imported), and normalise the LIVE core's
    stale 'proposed' statuses to 'active' — those questions are demonstrably
    live (seeded, aggregated, served). Idempotent."""
    conn = conn or get_conn()
    if conn.execute("SELECT COUNT(*) FROM questions WHERE question_version IS NOT NULL").fetchone()[0]:
        return 0
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = {r["id"]: r for r in csv.DictReader(f)}
    n = 0
    for qid, r in rows.items():
        conn.execute(
            "UPDATE questions SET question_version=?, historical_comparability=?, "
            "status=?, replaced_by=? WHERE id=?",
            (r.get("question_version") or None, r.get("historical_comparability") or None,
             (r.get("status") or "active").strip() or "active", r.get("replaced_by") or None, qid))
        n += 1
    # live-core normalisation: 27 Reward questions carry stale 'proposed' in
    # the CSV but are live in fact (seeded + aggregated + member-visible)
    normalised = conn.execute(
        "UPDATE questions SET status='active' WHERE superpower='Reward' AND status='proposed'").rowcount
    conn.commit()
    return n + normalised


def ensure_baseline(conn=None):
    """Snapshot the current live core as the baseline release — the 'before'
    everything downstream diffs against. Idempotent."""
    conn = conn or get_conn()
    if conn.execute("SELECT COUNT(*) FROM core_releases").fetchone()[0]:
        return None
    live = _live_core(conn)
    conn.execute(
        "INSERT INTO core_releases(release_id, name, notes, status) VALUES (?,?,?,'current')",
        (BASELINE_ID, "2025 baseline core",
         "Snapshot of the live core question set at versioning go-live "
         "(%d questions). 27 live questions carried stale 'proposed' status in "
         "the library CSV and were normalised to 'active' — they were already "
         "seeded, aggregated and member-visible." % len(live)))
    for r in live:
        conn.execute(
            "INSERT INTO release_questions(release_id, question_id, question_version, "
            "is_required, status, snapshot_json) VALUES (?,?,?,?,?,?)",
            (BASELINE_ID, r["id"], r["question_version"], r["is_required"],
             r["status"] or "active", j({k: r[k] for k in r.keys()})))
    conn.execute("UPDATE questions SET release_entered=? WHERE release_entered IS NULL "
                 "AND id IN (%s)" % ",".join("?" * len(live)),
                 [BASELINE_ID] + [r["id"] for r in live])
    conn.execute(
        "INSERT INTO core_changelog(release_id, lane, change_type, detail) VALUES (?,?,?,?)",
        (BASELINE_ID, "release", "baseline",
         "Baseline release captured: %d live core questions snapshotted." % len(live)))
    # the existing data period was aggregated under this question set
    conn.execute("UPDATE snapshots SET release_id=? WHERE release_id IS NULL", (BASELINE_ID,))
    conn.commit()
    return BASELINE_ID


def question_set(release_id, conn=None):
    """Reconstruct a release's exact question set ({qid: full row dict})."""
    conn = conn or get_conn()
    out = {}
    for r in conn.execute("SELECT * FROM release_questions WHERE release_id=?", (release_id,)):
        out[r["question_id"]] = uj(r["snapshot_json"], {})
    return out


def retire_question(qid, replaced_by=None, conn=None):
    """Stage a retirement: marked, never deleted. Takes effect in the live
    member experience immediately; the release it left is stamped when the
    next release is cut (release_retired + change log come from the diff)."""
    conn = conn or get_conn()
    r = _question_row(conn, qid)
    if r is None:
        raise ValueError("unknown question %s" % qid)
    conn.execute("UPDATE questions SET status='retired', replaced_by=? WHERE id=?",
                 (replaced_by, qid))
    conn.commit()


def mark_comparability_break(qid, release_id, conn=None):
    """Append a break marker to historical_comparability (keeps the
    high/medium/low rating: 'medium; break@2026.1')."""
    conn = conn or get_conn()
    r = _question_row(conn, qid)
    cur = (r["historical_comparability"] or "").strip()
    marker = "break@%s" % release_id
    if marker in cur:
        return
    conn.execute("UPDATE questions SET historical_comparability=? WHERE id=?",
                 ((cur + "; " if cur else "") + marker, qid))
    conn.commit()


def comparability_breaks(q_hist):
    """Parse 'break@<release>' markers out of a historical_comparability value."""
    return re.findall(r"break@([\w.\-]+)", q_hist or "")


def create_release(release_id, notes="", signed_off_by=None, conn=None):
    """Cut a release: snapshot the live core, DIFF against the previous
    release, and write the change log from the diff (added / retired /
    reworded). The previous release is superseded, never altered."""
    conn = conn or get_conn()
    if conn.execute("SELECT 1 FROM core_releases WHERE release_id=?", (release_id,)).fetchone():
        raise ValueError("release %s already exists" % release_id)
    prev = current_release(conn)
    prev_set = question_set(prev["release_id"], conn) if prev else {}
    live = {r["id"]: r for r in _live_core(conn)}

    changes = []
    for qid, r in live.items():
        if qid not in prev_set:
            changes.append(("added", qid, "Added in %s (version %s)." % (release_id, r["question_version"] or "v1")))
            conn.execute("UPDATE questions SET release_entered=? WHERE id=? AND "
                         "(release_entered IS NULL OR release_entered='')", (release_id, qid))
        elif (r["question_version"] or "") != (prev_set[qid].get("question_version") or ""):
            brk = "break@%s" % release_id in (r["historical_comparability"] or "")
            changes.append(("reworded", qid, "Version %s -> %s.%s" % (
                prev_set[qid].get("question_version"), r["question_version"],
                " COMPARABILITY BREAK — trends reset at this release." if brk else "")))
        elif (r["sub_power"] or "") != (prev_set[qid].get("sub_power") or ""):
            # re-filing only: wording unchanged, trends remain comparable —
            # NEVER a comparability break, never a retirement
            changes.append(("recategorised", qid, "Moved %s -> %s (re-filed; wording unchanged, "
                            "trends remain comparable)." % (prev_set[qid].get("sub_power"), r["sub_power"])))
    for qid, snap in prev_set.items():
        if qid not in live:
            conn.execute("UPDATE questions SET release_retired=? WHERE id=?", (release_id, qid))
            changes.append(("retired", qid, "Retired in %s%s. History retained; prior "
                            "benchmarks still resolve." % (
                                release_id,
                                "" if not _question_row(conn, qid)["replaced_by"]
                                else " (replaced by %s)" % _question_row(conn, qid)["replaced_by"])))

    conn.execute("UPDATE core_releases SET status='superseded' WHERE status='current'")
    conn.execute("INSERT INTO core_releases(release_id, name, notes, status, signed_off_by) "
                 "VALUES (?,?,?,'current',?)", (release_id, release_id, notes, signed_off_by))
    for r in live.values():
        conn.execute(
            "INSERT INTO release_questions(release_id, question_id, question_version, "
            "is_required, status, snapshot_json) VALUES (?,?,?,?,?,?)",
            (release_id, r["id"], r["question_version"], r["is_required"],
             r["status"] or "active", j({k: r[k] for k in r.keys()})))
    for ctype, qid, detail in changes:
        conn.execute("INSERT INTO core_changelog(release_id, lane, change_type, question_id, "
                     "detail, signed_off_by) VALUES (?,?,?,?,?,?)",
                     (release_id, "release", ctype, qid, detail, signed_off_by))
    if not changes:
        conn.execute("INSERT INTO core_changelog(release_id, lane, change_type, detail, signed_off_by) "
                     "VALUES (?,?,?,?,?)", (release_id, "release", "baseline",
                                            "No membership/version changes.", signed_off_by))
    conn.commit()
    return changes


def emergency_change(qid, new_version, external_trigger, signed_off_by,
                     comparability_break=False, conn=None):
    """The ONLY between-release change path. Gate: the live question must have
    become FACTUALLY WRONG because of an external change (e.g. a statutory
    baseline moved) — never 'we want to add something'; routine changes queue
    in the backlog for the next release. Requires the external trigger AND an
    explicit sign-off, and is logged in the change log."""
    conn = conn or get_conn()
    if not (external_trigger or "").strip():
        raise ValueError("Emergency lane refused: state the EXTERNAL change that made "
                         "the live question factually wrong. Routine additions go to the backlog.")
    if not (signed_off_by or "").strip():
        raise ValueError("Emergency lane refused: explicit sign-off is required.")
    r = _question_row(conn, qid)
    if r is None:
        raise ValueError("unknown question %s" % qid)
    cur = current_release(conn)
    conn.execute("UPDATE questions SET question_version=? WHERE id=?", (new_version, qid))
    if comparability_break:
        mark_comparability_break(qid, "%s+emergency" % (cur["release_id"] if cur else "live"), conn)
    conn.execute(
        "INSERT INTO core_changelog(release_id, lane, change_type, question_id, detail, signed_off_by) "
        "VALUES (?,?,?,?,?,?)",
        (cur["release_id"] if cur else None, "emergency", "emergency_correction", qid,
         "EMERGENCY (between releases): %s Version -> %s.%s" % (
             external_trigger.strip(), new_version,
             " Comparability break marked." if comparability_break else ""),
         signed_off_by.strip()))
    conn.commit()


def add_backlog(title, detail="", source="manual", source_ref=None, conn=None):
    conn = conn or get_conn()
    if source_ref and conn.execute("SELECT 1 FROM core_backlog WHERE source=? AND source_ref=?",
                                   (source, str(source_ref))).fetchone():
        return False
    conn.execute("INSERT INTO core_backlog(title, detail, source, source_ref) VALUES (?,?,?,?)",
                 (title, detail, source, str(source_ref) if source_ref is not None else None))
    conn.commit()
    return True


def ingest_metric_requests(conn=None):
    """Pull member request-a-metric submissions into the backlog (idempotent;
    queued for a release, never auto-applied)."""
    conn = conn or get_conn()
    n = 0
    for r in conn.execute("SELECT * FROM metric_requests ORDER BY created_at"):
        if add_backlog(r["requested_text"], r["notes"] or "", "request-a-metric", r["id"], conn):
            n += 1
    return n
