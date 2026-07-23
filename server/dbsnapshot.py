"""
gate-safety-2 — whole-DB standing assertion.

Snapshots EVERY table (derived from the schema at runtime — never a hardcoded list, so a table added
later is covered automatically) as (row_count, content_hash), compares two snapshots, and NAMES what
moved, filtered by declared expected deltas. This is the structural DETECTION that matches gate-safety-1's
structural PREVENTION: the coverage gap (40/42 tables carried no standing assertion) is why qa_phase2's
DELETE FROM drafts went unnoticed, and why every gate-safety-1 leak was caught only by hand-comparing all
42 counts.

CONTENT hash (not count-only): the qa_release case (UPDATE questions SET is_required/version) changes NO
row count, so a count-only check would pass it. We hash the rows too.

DETERMINISM: rows are ordered by the table's PRIMARY KEY (from PRAGMA table_info); tables without a PK are
ordered by all columns. Both are stable across runs and independent of physical row order / VACUUM.

EXPECTED vs UNEXPECTED: compare(before, after, expected=...) treats every table not in `expected` as
must-not-change. A migration declares the tables it legitimately writes; a gate/run_gates cycle declares
nothing (or only the inherently-volatile allowlist), so any other movement fires.

CLI (for wrapping a bare run or a manual audit — the leaks came from bare gate runs, not run_gates):
    python dbsnapshot.py save  <snap.json> [--db PATH]
    python dbsnapshot.py check <snap.json> [--db PATH] [--expect t1,t2] [--allow-volatile]
`check` exits non-zero and names the tables that moved if any UNDECLARED table changed.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys

# Inherently-volatile tables: written by normal server operation (logins, notifications, AI logs),
# not by data edits. A run_gates / bare-gate live check allows these via --allow-volatile so the
# assertion doesn't cry wolf on an ambient login. Kept SMALL and justified; a leak into any OTHER
# table still fires. (sessions churns on every login; the rest are append-on-use server logs.)
VOLATILE = {"sessions", "notification_events", "notification_reads", "analyst_log", "share_audit"}


def tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")]


def _order_by(conn, t):
    info = list(conn.execute('PRAGMA table_info("%s")' % t))          # (cid, name, type, notnull, dflt, pk)
    pk = [r[1] for r in sorted((r for r in info if r[5]), key=lambda r: r[5])]
    return pk if pk else [r[1] for r in info]                          # PK order, else all columns


def table_fingerprint(conn, t):
    cols = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % t)]
    order = _order_by(conn, t)
    sql = 'SELECT %s FROM "%s" ORDER BY %s' % (
        ",".join('"%s"' % c for c in cols), t, ",".join('"%s"' % c for c in order))
    h = hashlib.sha256()
    n = 0
    for row in conn.execute(sql):
        h.update(("\x1f".join("\x00" if v is None else str(v) for v in row) + "\x1e")
                 .encode("utf-8", "surrogatepass"))
        n += 1
    return n, h.hexdigest()


def snapshot(conn):
    return {t: {"count": c, "hash": hsh} for t in tables(conn) for c, hsh in [table_fingerprint(conn, t)]}


def compare(before, after, expected=(), allow_volatile=False):
    """Return {table: reason} for every table that changed and was NOT declared expected."""
    exp = set(expected) | (VOLATILE if allow_volatile else set())
    diffs = {}
    for t in sorted(set(before) | set(after)):
        b, a = before.get(t), after.get(t)
        if b == a or t in exp:
            continue
        if b is None:
            diffs[t] = "table ADDED (%d rows)" % a["count"]
        elif a is None:
            diffs[t] = "table DROPPED (was %d rows)" % b["count"]
        elif b["count"] != a["count"]:
            diffs[t] = "count %+d (%d -> %d)" % (a["count"] - b["count"], b["count"], a["count"])
        else:
            diffs[t] = "content changed, same count %d (a value was UPDATED)" % a["count"]
    return diffs


def _conn(db):
    return sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db), uri=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["save", "check"])
    ap.add_argument("snap")
    ap.add_argument("--db", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lumi.db"))
    ap.add_argument("--expect", default="", help="comma-separated tables allowed to change")
    ap.add_argument("--allow-volatile", action="store_true", help="also allow %s" % ",".join(sorted(VOLATILE)))
    a = ap.parse_args()
    conn = _conn(a.db)
    snap = snapshot(conn)
    conn.close()
    if a.action == "save":
        json.dump(snap, open(a.snap, "w"), indent=0)
        print("saved snapshot of %d tables -> %s" % (len(snap), a.snap))
        return 0
    before = json.load(open(a.snap))
    expected = [x.strip() for x in a.expect.split(",") if x.strip()]
    diffs = compare(before, snap, expected=expected, allow_volatile=a.allow_volatile)
    if not diffs:
        print("OK — no undeclared table changed (%d tables checked%s%s)"
              % (len(snap), ("; expected: " + ",".join(expected)) if expected else "",
                 "; volatile allowed" if a.allow_volatile else ""))
        return 0
    print("CHANGED — %d undeclared table(s) moved:" % len(diffs))
    for t, why in diffs.items():
        print("  %-22s %s" % (t, why))
    return 1


if __name__ == "__main__":
    sys.exit(main())
