#!/usr/bin/env python3
"""Commit G — member exit (Phase 4 build, rulings R6 + R6-mech, 2026-08-08).

THE STATE MACHINE
  exit      --exit ORG_ID --reason "..."   sets orgs.exited_at (the machine state,
            a timestamp DISTINCT from deactivation — a state that triggers
            irreversible deletion must not be expressible as a typo) AND suspends
            access via the existing mechanism (deactivated_at + the free-text
            reason as the human note). Pool removal is IMMEDIATE: aggregate,
            twin pool and group counts all key off exited_at IS NULL (day 0).
  un-exit   --un-exit ORG_ID               inside grace only; clears exited_at
            ONLY (its own audit row, never a null-out of the suspension — the
            org comes back SUSPENDED and reactivation stays a deliberate,
            separate staff action).
  sweep     --sweep                        the grace-end deletion job. THE ONLY
            TIMER IN THIS SYSTEM THAT DESTROYS DATA, so it ships REPORT-ONLY:
            it prints/mails "would delete X on Y" and deletes NOTHING unless
            LUMI_EXIT_DELETION=on is set in the environment AND the run carries
            --write --confirmed-by-david. Suspension-to-exit is never a timer;
            deletion-after-grace necessarily is, so it carries the guard the
            doctrine would otherwise put on the decision.

GRACE_WINDOW = 30 days from exited_at. Physical deletion at grace end covers the
Phase-4 inventory: every org-keyed row (namespace census, both stores), with the
R6 parameter handling — terms_acceptances RETAINED de-identified (random opaque
token per user, mapping NEVER stored — R6 §6.3: a plain hash is dictionary-
reversible at this population size), pulse_responses DELETED (org-level rows;
already-served aggregates never retro-edited), pulse_launch_orders RETAINED IN
FULL (statutory 6-year hold, stated never quiet), metric_suggestions/requests
DE-ATTRIBUTED with identifying-free-text flagging (a suggestion whose text
mentions the org name is FLAGGED for manual handling, never silently kept or
deleted), admin_audit_log RETAINED (staff accountability).

Every action is audited (org.exit / org.unexit / org.exit_delete) with the
actor recorded as 'david (countersigned CLI)' — exit is never a self-service
button.

Dry-run default everywhere. Writing needs --write --confirmed-by-david.
"""
import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
GRACE_DAYS = 30
# stated, never quiet. credit_ledger joins them 2026-08-19: credits replaced the
# per-pulse launch fee, so the ledger — not pulse_launch_orders — is now the record of
# what a member was invoiced for, and it is retained on exactly the same footing.
RETAINED_TABLES = ("pulse_launch_orders", "credit_ledger", "admin_audit_log")


def conn_rw():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def audit(conn, action, org_id, detail):
    conn.execute("INSERT INTO admin_audit_log(actor_user_id, action, target_kind, "
                 "target_id, detail_json) VALUES (?,?,?,?,?)",
                 ("david (countersigned CLI)", action, "org", org_id, json.dumps(detail)))


def org_keyed_tables(conn):
    out = []
    for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % t["name"])]
        if "org_id" in cols:
            out.append(t["name"])
    return sorted(out)


def _payload_ns(conn, qids):
    """{question_id: top-level n} from the SERVED benchmark_snapshots payloads."""
    out = {}
    for qid in qids:
        row = conn.execute("SELECT payload_json FROM benchmark_snapshots "
                           "WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()
        if row:
            p = json.loads(row["payload_json"])
            top = p.get("all") or p.get("top") or {}
            out[qid] = top.get("n") if isinstance(top, dict) else None
    return out


def _reaggregate_and_report(conn, org_id, answered, before):
    """Re-run the snapshot in-process and report the delta on the org's answered
    set — asserting against benchmark_snapshots, the thing members are served,
    never against this tool's own output."""
    sys.path.insert(0, HERE)
    import aggregate
    aggregate.run_snapshot(1, verbose=False)
    after = _payload_ns(conn, answered)
    moved = {q: (before.get(q), after.get(q)) for q in answered
             if before.get(q) != after.get(q)}
    print("re-aggregated: %d answered metrics; top-level n moved on %d (e.g. %s)"
          % (len(answered), len(moved),
             ", ".join("%s %s->%s" % (q, b, a) for q, (b, a) in list(moved.items())[:4]) or "-"))
    # Enforcement assertion, against the SERVED store. Payloads are pure
    # aggregates (org ids never appear in them), so the honest check is the
    # count: if the org had answers and NOT ONE served n moved, either every
    # one of its values was uncountable (possible but must be stated) or
    # enforcement failed — refuse to call the exit complete either way.
    if answered and not moved:
        sys.exit("FATAL: %d answered metrics but no served n moved after "
                 "re-aggregation. Either the org contributed no countable values "
                 "(verify by hand and record which case obtains) or day-0 removal "
                 "FAILED — exit is NOT complete." % len(answered))


def do_exit(conn, org_id, reason, write):
    o = conn.execute("SELECT org_id, source, exited_at, deactivated_at FROM orgs "
                     "WHERE org_id=?", (org_id,)).fetchone()
    if o is None:
        sys.exit("FATAL: unknown org_id %s" % org_id)
    if o["source"] != "signup":
        sys.exit("FATAL: exit applies to member orgs (source='signup'); %s is %r."
                 % (org_id, o["source"]))
    if o["exited_at"]:
        sys.exit("FATAL: already exited at %s." % o["exited_at"])
    if not (reason or "").strip():
        sys.exit("FATAL: exit carries the human note (--reason), like every suspension.")
    print("EXIT %s: pool removal is IMMEDIATE on write; physical deletion on the "
          "sweep after %s + %d days." % (org_id, "now", GRACE_DAYS))
    if not write:
        print("DRY-RUN — nothing written.")
        return
    answered = [r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=1",
        (org_id,))]
    before = _payload_ns(conn, answered)
    conn.execute("UPDATE orgs SET exited_at=datetime('now'), "
                 "deactivated_at=COALESCE(deactivated_at, datetime('now')), "
                 "deactivated_reason=COALESCE(deactivated_reason, ?) WHERE org_id=?",
                 ("exited: " + reason.strip(), org_id))
    audit(conn, "org.exit", org_id, {"reason": reason.strip(), "grace_days": GRACE_DAYS})
    conn.commit()
    sys.path.insert(0, HERE)
    import identity
    n = sum(identity.delete_sessions_for_user(r["user_id"]) for r in
            conn.execute("SELECT user_id FROM users WHERE org_id=?", (org_id,)))
    # Commit H (2026-08-08): exit is not complete until the SERVED payloads no
    # longer carry the member — day-0 pool removal is ENFORCED here, in the same
    # guarded operation, never delegated to a printed instruction. §6.5's
    # external promise is about to be drafted into terms; the mechanism must be
    # true before the sentence is written.
    _reaggregate_and_report(conn, org_id, answered, before)
    print("EXITED. Sessions revoked: %d." % n)


def do_unexit(conn, org_id, write):
    o = conn.execute("SELECT exited_at FROM orgs WHERE org_id=?", (org_id,)).fetchone()
    if o is None or not o["exited_at"]:
        sys.exit("FATAL: %s is not in the exited state." % org_id)
    cutoff = conn.execute("SELECT datetime(?, '+%d days') c" % GRACE_DAYS,
                          (o["exited_at"],)).fetchone()["c"]
    now = conn.execute("SELECT datetime('now') n").fetchone()["n"]
    if now >= cutoff:
        sys.exit("FATAL: grace ended %s — un-exit is an inside-grace action only; "
                 "past it, restoration is a David-level decision on whatever the "
                 "sweep state is." % cutoff)
    print("UN-EXIT %s (grace ends %s): clears exited_at ONLY — the org comes back "
          "SUSPENDED; reactivation is a separate staff action." % (org_id, cutoff))
    if not write:
        print("DRY-RUN — nothing written.")
        return
    conn.execute("UPDATE orgs SET exited_at=NULL WHERE org_id=?", (org_id,))
    audit(conn, "org.unexit", org_id, {"was_exited_at": o["exited_at"]})
    conn.commit()
    print("UN-EXITED (still suspended). Re-run aggregate.py to restore pool membership.")


def do_sweep(conn, write):
    due = conn.execute(
        "SELECT org_id, exited_at, datetime(exited_at, '+%d days') AS delete_on "
        "FROM orgs WHERE exited_at IS NOT NULL" % GRACE_DAYS).fetchall()
    if not due:
        print("sweep: no exited orgs. Nothing to report.")
        return
    enabled = os.environ.get("LUMI_EXIT_DELETION") == "on"
    now = conn.execute("SELECT datetime('now') n").fetchone()["n"]
    ripe = [r for r in due if r["delete_on"] <= now]
    for r in due:
        state = "DELETE DUE" if r["delete_on"] <= now else "in grace"
        print("  %s exited %s -> would delete on %s [%s]"
              % (r["org_id"], r["exited_at"], r["delete_on"], state))
    if not ripe:
        print("sweep: report-only, nothing ripe.")
        return
    if not (enabled and write):
        print("sweep: REPORT-ONLY (%d ripe). Real deletion needs LUMI_EXIT_DELETION=on "
              "in the environment AND --write --confirmed-by-david — the only timer "
              "that destroys data carries the decision's guard." % len(ripe))
        return
    tables = org_keyed_tables(conn)
    sys.path.insert(0, HERE)
    import identity
    for r in ripe:
        oid = r["org_id"]
        uids = [u["user_id"] for u in conn.execute(
            "SELECT user_id FROM users WHERE org_id=?", (oid,))]
        # Commit I (2026-08-08): IDENTITY FIRST, then reward — the REVERSE of
        # Commit C's order, deliberately. C was attended, one-shot, dead orgs;
        # the sweep is unattended on a timer against real members. If it dies
        # between stores in reward-first order, the survivor is identity rows —
        # including any live invite token — authenticating against an org whose
        # reward data is gone. Identity-first, the survivor is inert benchmark
        # rows with nobody attached. Do NOT "tidy" this back to match C.
        identity.remove_org_identity(oid)
        if os.environ.get("LUMI_QA_SEAMS") == "on" and os.environ.get("_QA_FAIL_BETWEEN_STORES"):
            sys.exit("qa seam: forced failure BETWEEN identity and reward deletion")
        counts = {}
        cur = conn.cursor()
        try:
            # R6 §6.3: terms rows RETAINED, de-identified — random opaque token,
            # mapping destroyed by never being stored anywhere.
            for u in uids:
                cur.execute("UPDATE terms_acceptances SET user_id=? WHERE user_id=?",
                            ("exited-" + secrets.token_hex(8), u))
            # R6 §6.7: de-attribute suggestions/requests; FLAG identifying free text
            flagged = 0
            for t, col in (("metric_suggestions", "suggested_by"), ("metric_requests", "user_id")):
                cols = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % t)]
                if col in cols:
                    cur.execute("UPDATE %s SET %s=NULL WHERE org_id=?" % (t, col), (oid,))
            # deletion inventory: every org-keyed table EXCEPT the stated retentions
            # and the de-identified terms rows
            for t in tables:
                if t in RETAINED_TABLES or t == "terms_acceptances":
                    continue
                if t in ("users", "orgs"):
                    continue
                n = cur.execute("DELETE FROM %s WHERE org_id=?" % t, (oid,)).rowcount
                if n:
                    counts[t] = n
            for t in ("password_resets", "sessions", "notification_reads"):
                cols = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % t)]
                if "user_id" in cols and uids:
                    cur.execute("DELETE FROM %s WHERE user_id IN (%s)"
                                % (t, ",".join("?" * len(uids))), uids)
            counts["users"] = cur.execute("DELETE FROM users WHERE org_id=?", (oid,)).rowcount
            counts["orgs"] = cur.execute("DELETE FROM orgs WHERE org_id=?", (oid,)).rowcount
            audit(conn, "org.exit_delete", oid,
                  {"rows": counts, "retained": list(RETAINED_TABLES),
                   "terms_rows": "de-identified (random token, mapping destroyed)"})
            conn.commit()
        except Exception as e:
            conn.rollback()
            sys.exit("FATAL: reward-side exit-delete failed for %s (%s) — reward rolled "
                     "back; identity already removed (the INERT half-state: benchmark "
                     "rows with nobody attached, no authenticable credential). Re-run "
                     "the sweep to finish; identity_recon names the org meanwhile." % (oid, e))
        print("exit-deleted %s both stores: %s (retained, stated: %s)"
              % (oid, counts, ", ".join(RETAINED_TABLES)))
    rec = subprocess.run([sys.executable, "identity_recon.py"], cwd=HERE,
                         env=dict(os.environ), capture_output=True, text=True)
    print(rec.stdout.strip().splitlines()[-1])
    if rec.returncode != 0:
        sys.exit("FATAL: identity_recon NOT clean after exit-delete.")
    # Commit H: the sweep has the same day-0 exposure as --exit — enforce the
    # re-aggregation here too, in the same guarded operation.
    import aggregate
    aggregate.run_snapshot(1, verbose=False)
    print("re-aggregated post-sweep: served payloads recomputed without the deleted org(s).")
    print("Run the full gate suite; append the exit record to DECISIONS.md.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exit", metavar="ORG_ID")
    ap.add_argument("--un-exit", dest="unexit", metavar="ORG_ID")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a = ap.parse_args()
    write = a.write and a.confirmed_by_david
    if a.write and not a.confirmed_by_david:
        sys.exit("REFUSING: --write requires --confirmed-by-david.")
    conn = conn_rw()
    if a.exit:
        do_exit(conn, a.exit, a.reason, write)
    elif a.unexit:
        do_unexit(conn, a.unexit, write)
    elif a.sweep:
        do_sweep(conn, write)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
