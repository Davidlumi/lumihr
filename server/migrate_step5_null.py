#!/usr/bin/env python3
"""STEP 5 — the migration (commits 5+6). THE IRREVERSIBLE COMMIT.

Two phases, in C.3's forced order. A writer of a NOT NULL column cannot be
stripped (the INSERT fails), and five of the six columns are NOT NULL, so
"strip then null" is impossible:

    --phase=rebuild : marker -> in_progress, then rebuild orgs/users/invites
                      relaxing NOT NULL on the six. Columns still POPULATED.
    <the eight writer strips land between the phases — a code change>
    --phase=null    : NULL the six, then marker -> complete.

Between the strips and the NULL the columns are PARTIAL — the state P2 made
fatal. The marker's 'in_progress' is what makes that window legible rather than
alarming (C.4), which is why phase 1 writes it before touching the reward store.

Rollback: re-copy from identity.db by single-key join (D.1 — all six columns are
reconstructible from it and nothing else), then the pre-diff backup, then the pin.
"""
import json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identity

DB = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))
COLUMNS = ["orgs.name", "orgs.normalized_name", "users.email", "users.pw_hash",
           "users.display_name", "invites.email"]
RELAX = {  # table -> the NOT NULL fragments to relax, verbatim from the live DDL
    "orgs":    (("name TEXT NOT NULL", "name TEXT"),
                ("normalized_name TEXT NOT NULL", "normalized_name TEXT")),
    "users":   (("email TEXT NOT NULL UNIQUE", "email TEXT UNIQUE"),
                ("pw_hash TEXT NOT NULL", "pw_hash TEXT")),
    "invites": (("email TEXT NOT NULL", "email TEXT"),),
}

def rebuild(conn, t):
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()[0]
    idx = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (t,))]
    cols = [x[1] for x in conn.execute("PRAGMA table_info(%s)" % t)]
    before = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    new = ddl
    for a, b in RELAX[t]:
        assert a in new, "%s: DDL fragment not found: %r" % (t, a)
        new = new.replace(a, b, 1)
    new = new.replace("CREATE TABLE %s" % t, "CREATE TABLE %s_s5new" % t, 1)
    new = new.replace('CREATE TABLE "%s"' % t, "CREATE TABLE %s_s5new" % t, 1)
    conn.execute("BEGIN")
    conn.execute(new)
    conn.execute("INSERT INTO %s_s5new(%s) SELECT %s FROM %s" % (t, ",".join(cols), ",".join(cols), t))
    conn.execute("DROP TABLE %s" % t)
    conn.execute("ALTER TABLE %s_s5new RENAME TO %s" % (t, t))
    for i in idx:
        conn.execute(i)                     # idx_orgs_norm is recreated HERE, inside the txn
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    assert before == after, (t, before, after)
    print("    %-9s rebuilt: %d rows preserved, %d index(es) recreated" % (t, after, len(idx)))

def main():
    phase = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--phase=")), None)
    write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
    assert phase in ("rebuild", "null"), "--phase=rebuild|null required"
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA legacy_alter_table=ON")
    state = {c: conn.execute("SELECT COUNT(*) FROM %s WHERE %s IS NOT NULL" % tuple(c.split("."))).fetchone()[0]
             for c in COLUMNS}
    print("[step5:%s] non-null before: %s" % (phase, state))
    if not write:
        print("[step5:%s] DRY RUN — no write." % phase); return 0
    if phase == "rebuild":
        identity.set_step5_marker("in_progress", COLUMNS)
        print("  marker -> in_progress (before any reward-side change)")
        for t in ("orgs", "users", "invites"):
            rebuild(conn, t)
        print("  integrity: %s | foreign_key_check: %s"
              % (conn.execute("PRAGMA integrity_check").fetchone()[0],
                 conn.execute("PRAGMA foreign_key_check").fetchall() or "clean"))
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_orgs_norm'").fetchone(), \
            "idx_orgs_norm LOST"
        print("  idx_orgs_norm: present")
    else:
        for c in COLUMNS:
            t, col = c.split(".")
            conn.execute("UPDATE %s SET %s=NULL" % (t, col))
        conn.commit()
        post = {c: conn.execute("SELECT COUNT(*) FROM %s WHERE %s IS NOT NULL" % tuple(c.split("."))).fetchone()[0]
                for c in COLUMNS}
        print("  non-null after: %s" % post)
        assert all(v == 0 for v in post.values()), post
        ts = identity.set_step5_marker("complete", COLUMNS)
        print("  marker -> complete at %s (mechanism NULL, %d columns)" % (ts, len(COLUMNS)))
    print("[step5:%s] PASS" % phase)
    return 0

if __name__ == "__main__":
    sys.exit(main())
