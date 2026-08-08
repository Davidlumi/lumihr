#!/usr/bin/env python3
"""Commit C — R4 / R4a / R4b: delete the signup-era artefact orgs, BOTH stores.

Rulings (Master Ruling Transmission 2026-08-08 + R4b amendment):
  R4   HR_DATAHUB_DISPOSITION = DELETE (rationale restated factually, approved)
  R4a  TESTER_DISPOSITION = DELETE + deliberate book re-baseline (89,321 -> 89,320)
  R4b  SIGNUP_ERA_ARTEFACT = DELETE where answer_rows = 0 — the CLASS is ruled,
       so a fourth artefact would be eligible by rule; the ENUMERATED census is
       what David approved, so this script refuses if the live census differs
       from the approved list (derive, don't hardcode — then compare).

Preconditions honoured:
  C-1  full census printed and compared against the APPROVED enumeration below.
  C-2  org-counting surfaces checked at echo time (all gate on
       submission_complete=1; counts printed).
  C-3  one guarded operation, both stores: reward first (per-org transaction,
       namespace census of every org_id-carrying table), then
       identity.remove_org_identity() — a crash between the two leaves an
       identity-only orphan, the NAMED direction identity_recon calls out.
       identity_recon must be clean both directions afterwards (asserted here).

Backups: reward pre-write backup (SQLite backup API, pin-aware retention sweep —
the 2026-08-05 incident guard); identity backup via backup_identity.py, which
carries the policy's integrity + row-count assertions.

Dry-run default. Writing needs BOTH --write AND --confirmed-by-david.
"""
import argparse
import glob
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BASELINE = os.path.join(ROOT, "data", "book_baseline.json")
RETAIN, PINNED = 3, ("presplit",)

# The APPROVED enumeration (C-1, David 2026-08-08). The live census is derived
# fresh and MUST match this set exactly — a new arrival is R4b-ELIGIBLE by rule
# but is NOT approved until David sees it enumerated.
APPROVED = {
    "488e5ed3-18ea-46d8-b727-eed355bd4c28": ("HR Datahub", "R4",  0),
    "74a5739a-dbab-4d66-8657-a23c17b2559f": ("Tester",     "R4a", 1),
    "aa24b6c2-f711-4705-9ff5-5fe48c65c182": ("tester 1",   "R4b", 0),
}
EXPECTED_BOOK_AFTER = 89320   # transmission §4.3 claim — re-derived below


def book_fingerprint(conn):
    """THE canonical recipe — dbsnapshot.table_fingerprint, the exact function
    data/book_baseline.json names. (First draft re-implemented a similar-looking
    serialization and the dry-run's fail-closed baseline check caught the
    mismatch — the reason the recipe is named in the baseline file is exactly
    so this function gets IMPORTED, not imitated.)"""
    sys.path.insert(0, HERE)
    import dbsnapshot
    n, full = dbsnapshot.table_fingerprint(conn, "answers")
    return n, full[:16]


def org_keyed_tables(conn):
    """Census by NAMESPACE, never inventory: every table carrying an org_id column."""
    out = []
    for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % t["name"])]
        if "org_id" in cols:
            out.append(t["name"])
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a = ap.parse_args()
    write = a.write and a.confirmed_by_david
    if a.write and not a.confirmed_by_david:
        sys.exit("REFUSING: --write requires --confirmed-by-david.")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # ---------------- C-1: the census, derived live, compared to approved ----
    print("== C-1 census (live) ==")
    for r in conn.execute("SELECT source, COUNT(*) c FROM orgs GROUP BY source"):
        print("  %-8s %d" % (r["source"], r["c"]))
    live = {}
    for o in conn.execute("SELECT org_id, created_at, classified FROM orgs "
                          "WHERE source='signup' ORDER BY created_at"):
        oid = o["org_id"]
        nu = conn.execute("SELECT COUNT(*) c FROM users WHERE org_id=?", (oid,)).fetchone()["c"]
        na = conn.execute("SELECT COUNT(*) c FROM answers WHERE org_id=?", (oid,)).fetchone()["c"]
        live[oid] = na
        print("  %s created=%s users=%d answers=%d classified=%d"
              % (oid, o["created_at"][:10], nu, na, o["classified"]))
    if set(live) != set(APPROVED):
        sys.exit("FATAL: live signup census differs from the APPROVED enumeration "
                 "(new/missing: %s). R4b makes a new arrival ELIGIBLE, not APPROVED — "
                 "show David the new census first." % (set(live) ^ set(APPROVED)))
    for oid, (name, ruling, exp_answers) in APPROVED.items():
        if live[oid] != exp_answers:
            sys.exit("FATAL: %s (%s) has %d answer rows, approved list says %d — "
                     "the world moved; re-approve." % (name, oid, live[oid], exp_answers))

    # ---------------- C-2: org-counting surfaces, which case obtains ---------
    print("== C-2 org-counting surfaces ==")
    for oid, (name, ruling, _) in APPROVED.items():
        twin = conn.execute("SELECT 1 FROM orgs WHERE org_id=? AND "
                            "similarity_vector_json IS NOT NULL AND submission_complete=1",
                            (oid,)).fetchone()
        comp = conn.execute("SELECT 1 FROM orgs WHERE org_id=? AND classified=1 AND "
                            "submission_complete=1", (oid,)).fetchone()
        grp = conn.execute("SELECT 1 FROM orgs WHERE org_id=? AND submission_complete=1",
                           (oid,)).fetchone()
        print("  %-11s twin-pool=%s composition=%s group-count=%s (all gate on "
              "submission_complete=1)" % (name, bool(twin), bool(comp), bool(grp)))
        if twin or comp or grp:
            sys.exit("FATAL: %s contributes to an org-counting surface — the C-2 "
                     "premise fails; stop and report." % name)
    n_allow = conn.execute("SELECT COUNT(DISTINCT org_id) c FROM answers "
                           "WHERE question_id='ALLOW_02'").fetchone()["c"]
    print("  the ONE moving aggregate: ALLOW_02 pool %d -> %d (Tester's row; floor n>=5 "
          "untouched)" % (n_allow, n_allow - 1))

    # ---------------- expected book, derived then compared -------------------
    n_before, fp_before = book_fingerprint(conn)
    baseline = json.load(open(BASELINE))
    total_del = sum(v for v in live.values())
    print("== book ==")
    print("  live: %d rows / %s | recorded baseline: %d / %s" %
          (n_before, fp_before, baseline["rows"], baseline["hash16"]))
    if (n_before, fp_before) != (baseline["rows"], baseline["hash16"]):
        sys.exit("FATAL: live book does not match the recorded baseline — resolve that "
                 "drift before a deliberate re-baseline.")
    derived_after = n_before - total_del
    print("  derived post-delete: %d (transmission claims %d)" % (derived_after, EXPECTED_BOOK_AFTER))
    if derived_after != EXPECTED_BOOK_AFTER:
        sys.exit("FATAL: derivation disagrees with the transmission's claim — reporting, "
                 "not reconciling silently.")

    # ---------------- per-org reward-store namespace census ------------------
    tables = org_keyed_tables(conn)
    plan = {}
    for oid, (name, ruling, _) in APPROVED.items():
        uids = [r["user_id"] for r in conn.execute(
            "SELECT user_id FROM users WHERE org_id=?", (oid,))]
        rows = {}
        for t in tables:
            c = conn.execute("SELECT COUNT(*) c FROM %s WHERE org_id=?" % t, (oid,)).fetchone()["c"]
            if c:
                rows[t] = c
        urows = {}
        for t in ("password_resets", "sessions", "notification_reads"):
            cols = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % t)]
            if "user_id" in cols and uids:
                c = conn.execute("SELECT COUNT(*) c FROM %s WHERE user_id IN (%s)"
                                 % (t, ",".join("?" * len(uids))), uids).fetchone()["c"]
                if c:
                    urows[t] = c
        plan[oid] = (uids, rows, urows)
        print("  %-11s [%s] org-keyed rows: %s | user-keyed: %s" % (name, ruling, rows or "{}", urows or "{}"))

    if not write:
        print("\nDRY-RUN (no changes). Re-run with --write --confirmed-by-david to apply.")
        return

    # ---------------- backups (both stores, policy-conformant) ---------------
    tag = time.strftime("%Y%m%d_%H%M%S")
    db_abs = os.path.abspath(DB)
    bak = "%s.bak_pre_r4signup_%s" % (db_abs, tag)
    src = sqlite3.connect(DB)
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst = sqlite3.connect(bak)
    src.backup(dst)
    dst.close(); src.close()
    print("reward backup: %s" % os.path.basename(bak))
    baks = [b for b in sorted(glob.glob(db_abs + ".bak_pre_*"), key=os.path.getmtime)
            if not b.endswith(("-shm", "-wal"))]
    pinned = [b for b in baks if any(p in os.path.basename(b) for p in PINNED)]
    for b in baks:
        if b in pinned:
            print("pinned (excluded from rotation): %s" % os.path.basename(b))
    rot = [b for b in baks if b not in pinned]
    for old in rot[:-RETAIN]:
        for f in (old, old + "-shm", old + "-wal"):
            if os.path.exists(f):
                os.unlink(f)
                print("retention (keep last %d): deleted %s" % (RETAIN, os.path.basename(f)))
    # backup_identity.py roots its RETAIN-1 rotation at the REPO unconditionally —
    # so it runs ONLY when the target identity store IS the live one. A rehearsal
    # against a throwaway pair must not mint a repo-root backup of throwaway
    # content, and must not rotate away the real identity backup (the
    # presplit-incident lesson, applied before it repeats).
    idb = os.path.realpath(os.environ.get("LUMI_IDENTITY_DB")
                           or os.path.join(ROOT, "identity.db"))
    if idb == os.path.realpath(os.path.join(ROOT, "identity.db")):
        r = subprocess.run([sys.executable, "backup_identity.py", "--write",
                            "--confirmed-by-david", "--tag=r4signup"],
                           cwd=HERE, env=dict(os.environ), capture_output=True, text=True)
        print(r.stdout.strip()[-400:])
        if r.returncode != 0:
            sys.exit("FATAL: identity backup failed — nothing deleted.\n%s" % r.stderr[-400:])
    else:
        print("REHEARSAL TARGET (identity store is not live): backup_identity SKIPPED — "
              "its retain-1 rotation is repo-rooted and would touch the live backup.")

    # ---------------- the deletion: reward first, then identity --------------
    for oid, (name, ruling, _) in APPROVED.items():
        uids, rows, urows = plan[oid]
        cur = conn.cursor()
        try:
            for t, c in urows.items():
                cur.execute("DELETE FROM %s WHERE user_id IN (%s)"
                            % (t, ",".join("?" * len(uids))), uids)
            order = [t for t in rows if t not in ("users", "orgs")] + \
                    [t for t in ("users", "orgs") if t in rows]
            for t in order:
                cur.execute("DELETE FROM %s WHERE org_id=?" % t, (oid,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            sys.exit("FATAL: reward-store delete failed for %s (%s) — rolled back; "
                     "identity untouched." % (name, e))
        sys.path.insert(0, HERE)
        import identity
        identity.remove_org_identity(oid)
        print("deleted %-11s [%s] both stores (reward rows: %d; identity via "
              "remove_org_identity)" % (name, ruling, sum(rows.values()) + sum(urows.values())))

    # ---------------- verification ------------------------------------------
    n_after, fp_after = book_fingerprint(conn)
    print("book after: %d rows / %s" % (n_after, fp_after))
    if n_after != EXPECTED_BOOK_AFTER:
        sys.exit("FATAL: post-delete book %d != expected %d — restore from %s"
                 % (n_after, EXPECTED_BOOK_AFTER, os.path.basename(bak)))
    left = conn.execute("SELECT COUNT(*) c FROM orgs WHERE source='signup'").fetchone()["c"]
    if left != 0:
        sys.exit("FATAL: %d signup orgs survive." % left)
    # the deliberate re-baseline (R4a) — LIVE RUNS ONLY: the baseline file is a
    # repo artefact describing the LIVE book; the rehearsal caught this script
    # rewriting it from a throwaway run (harness leak, fixed here).
    if os.path.realpath(DB) != os.path.realpath(os.path.join(ROOT, "lumi.db")):
        print("REHEARSAL TARGET: book_baseline.json write SKIPPED (describes the live "
              "book only). Post-delete fingerprint on this copy: %d / %s" % (n_after, fp_after))
        rec = subprocess.run([sys.executable, "identity_recon.py"], cwd=HERE,
                             env=dict(os.environ), capture_output=True, text=True)
        print(rec.stdout.strip().splitlines()[-1])
        if rec.returncode != 0:
            sys.exit("FATAL: identity_recon NOT clean after rehearsal deletion.")
        return
    json.dump({
        "_what": baseline.get("_what"),
        "store": baseline.get("store"), "table": baseline.get("table"),
        "recipe": baseline.get("recipe"),
        "rows": n_after, "hash16": fp_after,
        "recorded": time.strftime("%Y-%m-%d"),
        "supersedes": {
            "rows": baseline["rows"], "hash16": baseline["hash16"],
            "recorded": baseline.get("recorded"),
            "why": "DELIBERATE re-baseline, rulings R4/R4a/R4b (Master Ruling "
                   "Transmission 2026-08-08): three signup-era artefact orgs deleted "
                   "from both stores (HR Datahub 0 answers, Tester 1 answer, "
                   "tester 1 0 answers). The book moved by exactly Tester's one row. "
                   "A moved baseline read without this note is drift; with it, it is "
                   "the ruling executing.",
        },
    }, open(BASELINE, "w"), indent=1)
    print("book_baseline.json re-baselined: %d / %s (reason + ruling ids recorded)"
          % (n_after, fp_after))

    # recon must be clean in both directions (C-3)
    rec = subprocess.run([sys.executable, "identity_recon.py"], cwd=HERE,
                         env=dict(os.environ), capture_output=True, text=True)
    print(rec.stdout.strip().splitlines()[-1])
    if rec.returncode != 0:
        sys.exit("FATAL: identity_recon NOT clean after deletion — investigate now.")
    print("\nWRITTEN. Now: aggregate.run_snapshot(1), plausibility gate, full suite.")


if __name__ == "__main__":
    main()
