#!/usr/bin/env python3
"""Turn a COPY of the live stores into the pair production should start life with.

Run this once, against /srv/lumi/data after the runbook's §1.6 copy and BEFORE the
first boot — never against the working tree's stores, which is why there are no default
paths: both must be named explicitly.

    python3 prepare_production_stores.py --db /srv/lumi/data/lumi.db \\
                                         --identity-db /srv/lumi/data/identity.db
    # ...read the plan, then:
    python3 prepare_production_stores.py --db ... --identity-db ... --write --confirmed-by-david

FOUR THINGS, and why each one matters:

1. REMOVE THE REHEARSAL ACCOUNT. director@larkholm.example is a leftover from the August
   launch rehearsal with a working password. Production copies whatever is in these files.

2. ROTATE THE DEMO PASSWORDS. David's ruling (2026-08-20) keeps the Thornbridge demo org
   in production for sales demos. Its passwords are CONSTANTS IN THE SOURCE
   (DEMO_ADMIN/DEMO_VIEWER/DEMO_CONTRIBUTOR in app.py), so anyone with repo access could
   sign in to production as an admin of that org. New passwords are generated here and
   printed ONCE — save them before closing the terminal, they are not stored anywhere
   else. Local development is unaffected: LUMI_SEED_DEMO only creates accounts that do
   not exist, so the dev stores keep the familiar ones.

3. REBASELINE THE SIGNAL STATE. The runbook's precondition 0, and it has a trap. The
   instruction reads "bump composition_epoch and run one sweep", but the sweep treats a
   MISSING org_signal_epoch row as the CURRENT epoch and stamps it lazily — deliberately,
   so a pre-P1F org is not rebaselined into eating genuinely pending changes. This
   database has 0 epoch rows against 220 orgs carrying signal_state, so bumping the epoch
   alone would change nothing and the first production sweep would diff a dev backlog
   into real events. Every org is therefore stamped with a PRIOR epoch first, so the bump
   is actually visible to the sweep and each org rebaselines silently, full-replace.

   notification_events is left alone on purpose: the runbook calls it the immutable event
   log — archived history, not a served surface, and it reaches no member.

4. CLEAR DEV ARTEFACTS. Board packs, generation jobs and AI call metering from months of
   development, sitting in tables production will serve and report from.

Dry-run by default. Both stores are backed up through the SQLite backup API (never a file
copy — a WAL-mode database copied with cp can be torn) before a single write.
"""
import argparse
import json
import os
import secrets
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REHEARSAL_EMAILS = ("director@larkholm.example",)
DEMO_DOMAIN = "@thornbridge.example"
PRIOR_EPOCH = "pre-prod"
PROD_EPOCH = "prod-1"


def backup(path):
    """SQLite backup API, not cp: these run in WAL mode and a file copy can be torn."""
    dest = path + ".pre-prod-prep.bak"
    src = sqlite3.connect(path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="the reward store to prepare")
    ap.add_argument("--identity-db", required=True, help="the identity store to prepare")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a = ap.parse_args()
    write = a.write and a.confirmed_by_david

    for p in (a.db, a.identity_db):
        if not os.path.exists(p):
            sys.exit("no such database: %s" % p)
    repo_live = os.path.abspath(os.path.join(HERE, "..", "lumi.db"))
    if os.path.abspath(a.db) == repo_live:
        sys.exit("REFUSING: that is the working tree's lumi.db. Point this at the COPY "
                 "in /srv/lumi/data — rotating the demo passwords in your dev store would "
                 "break local demos for no reason.")

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    idb = sqlite3.connect(a.identity_db)
    idb.row_factory = sqlite3.Row

    print("reward store   : %s" % os.path.abspath(a.db))
    print("identity store : %s" % os.path.abspath(a.identity_db))
    print("mode           : %s\n" % ("WRITE" if write else "DRY RUN — nothing will change"))

    # ---------------------------------------------------------------- 1. rehearsal --
    rehearsal = []
    for email in REHEARSAL_EMAILS:
        r = idb.execute("SELECT user_id, org_id FROM users WHERE email=?", (email,)).fetchone()
        if r:
            rehearsal.append((email, r["user_id"], r["org_id"]))
    print("1. REHEARSAL ACCOUNTS")
    if not rehearsal:
        print("   none found — already clean")
    for email, uid, oid in rehearsal:
        name = (idb.execute("SELECT name FROM org_register WHERE org_id=?", (oid,)).fetchone()
                or {"name": "(unknown)"})["name"]
        peers = conn.execute("SELECT COUNT(*) c FROM users WHERE org_id=?", (oid,)).fetchone()["c"]
        print("   remove %s  (org %r, %d user(s) in that org)" % (email, name, peers))

    # ------------------------------------------------------------------ 2. demo pw --
    demo = idb.execute("SELECT user_id, email FROM users WHERE email LIKE ?",
                       ("%" + DEMO_DOMAIN,)).fetchall()
    print("\n2. DEMO PASSWORDS (org kept, per David 2026-08-20)")
    if not demo:
        print("   no demo accounts present")
    for d in demo:
        print("   rotate %s" % d["email"])

    # ---------------------------------------------------------------- 3. rebaseline --
    epoch_rows = conn.execute("SELECT COUNT(*) c FROM org_signal_epoch").fetchone()["c"]
    orgs = conn.execute("SELECT COUNT(*) c FROM orgs").fetchone()["c"]
    with_state = conn.execute("SELECT COUNT(DISTINCT org_id) c FROM signal_state").fetchone()["c"]
    # meta stores JSON (db.set_meta json.dumps'es it, db.get_meta json.loads'es it) —
    # writing a bare string here would make get_meta raise on the first sweep
    _m = conn.execute("SELECT value_json FROM meta WHERE key='composition_epoch'").fetchone()
    cur_epoch = json.loads(_m["value_json"]) if _m else "0 (unset)"
    print("\n3. SIGNAL REBASELINE  (runbook precondition 0)")
    print("   orgs %d · carrying signal_state %d · epoch rows %d · composition_epoch %s"
          % (orgs, with_state, epoch_rows, cur_epoch))
    print("   stamp every org with epoch %r, then set composition_epoch=%r" % (PRIOR_EPOCH, PROD_EPOCH))
    print("   -> the first production sweep then rebaselines each org SILENTLY (zero events).")
    if epoch_rows == 0:
        print("   NOTE: with 0 epoch rows, bumping the epoch ALONE would do nothing — a missing")
        print("         row reads as the current epoch. The stamp is what makes the bump bite.")

    # ------------------------------------------------------------------ 4. artefacts --
    print("\n4. DEV ARTEFACTS")
    counts = {}
    for t in ("board_packs", "generation_jobs", "ai_calls", "notification_reads"):
        try:
            counts[t] = conn.execute("SELECT COUNT(*) c FROM %s" % t).fetchone()["c"]
        except sqlite3.OperationalError:
            counts[t] = None
    for t, c in counts.items():
        print("   clear %-20s %s" % (t, "(table absent)" if c is None else "%d row(s)" % c))
    keep = conn.execute("SELECT COUNT(*) c FROM notification_events").fetchone()["c"]
    print("   KEEP  %-20s %d row(s) — immutable event log, reaches no member" % ("notification_events", keep))

    if not write:
        print("\nRe-run with --write --confirmed-by-david to apply.")
        return 0

    # ============================================================== apply ==========
    print("\nbacking up before any write:")
    for p in (a.db, a.identity_db):
        print("   %s" % backup(p))

    for email, uid, oid in rehearsal:
        for c, tables in ((conn, ("users",)), (idb, ("users",))):
            for t in tables:
                c.execute("DELETE FROM %s WHERE user_id=?" % t, (uid,))
        # the org goes too: a rehearsal org in the peer pool would skew real benchmarks
        for t in ("orgs",):
            conn.execute("DELETE FROM %s WHERE org_id=?" % t, (oid,))
        idb.execute("DELETE FROM org_register WHERE org_id=?", (oid,))
        print("   removed %s and its org" % email)

    new_pw = {}
    if demo:
        import auth as auth_lib
        for d in demo:
            pw = "%s-%s" % (secrets.token_urlsafe(9), secrets.token_hex(3))
            idb.execute("UPDATE users SET pw_hash=? WHERE user_id=?",
                        (auth_lib.hash_password(pw), d["user_id"]))
            new_pw[d["email"]] = pw

    conn.executemany("INSERT OR REPLACE INTO org_signal_epoch VALUES (?,?)",
                     [(r["org_id"], PRIOR_EPOCH) for r in conn.execute("SELECT org_id FROM orgs")])
    conn.execute("INSERT INTO meta(key, value_json) VALUES('composition_epoch', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                 (json.dumps(PROD_EPOCH),))

    for t, c in counts.items():
        if c:
            conn.execute("DELETE FROM %s" % t)

    conn.commit()
    idb.commit()
    conn.close()
    idb.close()

    print("\ndone.")
    if new_pw:
        print("\n" + "=" * 66)
        print("DEMO PASSWORDS — shown ONCE, stored nowhere else. Save them now.")
        print("=" * 66)
        for e, pw in new_pw.items():
            print("   %-34s %s" % (e, pw))
        print("=" * 66)
    print("\nNEXT: boot the instance once and run a single signal sweep. Every org")
    print("rebaselines silently; the sweep should report 0 events written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
