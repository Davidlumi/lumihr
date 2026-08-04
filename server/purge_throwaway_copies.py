#!/usr/bin/env python3
"""PH-BAK-1 §3.2/§4: destroy Groups B and C — every gate-throwaway and scratchpad
database copy, identity-bearing or not ("a rule that says 'delete the dirty ones'
invites a judgement call that will eventually be got wrong" — David's ruling,
2026-08-03).

Scope, exactly:
  B: /tmp/lumi_gates.*/            *.db, *.db-wal, *.db-shm
  C: the Claude session scratchpads under /private/tmp/claude-*/
     -Applications-Lumi-Project/*/scratchpad/ (recursive), same patterns.

GROUP A IS NEVER TOUCHED: any candidate resolving inside the project tree is a
FATAL error, not a skip — this script must be structurally unable to delete the
governed .bak ritual set or the live stores.

Dry-run by default; deletion requires BOTH --write AND --confirmed-by-david
(house double-guard). Logs and non-DB files in the same directories are left
alone (PH-LOG-1 governs logs; the verbatim-tally convention keeps them).

HONEST about what deletion achieves (ruled §4): on APFS, rm UNLINKS — it does
not overwrite, and overwrite tooling on SSDs is largely theatre. The meaningful
controls are: the file is gone from the live filesystem, and backup media is
addressed separately (Time Machine's /private/tmp coverage is David's GUI
question, still open from PH-LOG-1).
"""
import argparse
import glob
import os
import re
import sqlite3
import sys

PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DB_PATTERN = re.compile(r"\.db(-wal|-shm)?$")

ROOTS = ["/tmp/lumi_gates.*"]
SCRATCH_GLOB = "/private/tmp/claude-*/-Applications-Lumi-Project/*/scratchpad"


def candidates():
    """(real_files, symlinks). SYMLINKS ARE NOT COPIES — prior sessions built
    scratch mirror-trees of the repo root out of symlinks, so a db-named link
    points AT the live store. Links are skipped and reported, never unlinked:
    this script deletes data copies, and a link holds none."""
    real, links = [], []
    def add(p):
        (links if os.path.islink(p) else real).append(p)
    for pat in ROOTS:
        for d in glob.glob(pat):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if DB_PATTERN.search(f) and (os.path.isfile(p) or os.path.islink(p)):
                    add(p)
    for d in glob.glob(SCRATCH_GLOB):
        for dirpath, _dirnames, filenames in os.walk(d):
            for f in sorted(filenames):
                if DB_PATTERN.search(f):
                    add(os.path.join(dirpath, f))
    return real, links


def describe(p):
    """Best-effort exposure note for the report; never blocks deletion."""
    if p.endswith(("-wal", "-shm")):
        return "sidecar"
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "org_register" in tables:
            n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return "IDENTITY store (%d user rows — full PII by design)" % n
        if "orgs" in tables and "answers" in tables:
            pop = conn.execute(
                "SELECT SUM(name IS NOT NULL AND name != '') FROM orgs").fetchone()[0] or 0
            return ("REWARD store, PRE-split (%d org names populated)" % pop) if pop \
                else "REWARD store, post-split (six identity columns empty)"
        return "sqlite (unrecognised schema)"
    except Exception as e:
        return "unreadable (%s)" % e
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    args = ap.parse_args()
    live = args.write and args.confirmed_by_david

    targets, links = candidates()
    if links:
        print("SKIPPED %d symlink(s) — a link is not a copy and is never unlinked "
              "through (prior sessions' mirror-trees point at the LIVE stores):" % len(links))
        for p in links:
            print("   %s -> %s" % (p, os.readlink(p)))
        print()
    # Group-A guard on REAL files: FATAL, not skip.
    inside = [p for p in targets if os.path.realpath(p).startswith(PROJECT_ROOT + os.sep)]
    if inside:
        print("FATAL: real file(s) resolve inside the project tree — Group A / live "
              "stores are NEVER in this script's scope:")
        for p in inside:
            print("  ", p)
        sys.exit(2)

    total = 0
    print("%s — %d candidate file(s):\n" % ("PURGING" if live else "DRY-RUN (no deletion)", len(targets)))
    for p in targets:
        sz = os.path.getsize(p)
        total += sz
        print("  %-95s %10.1f KB  %s" % (p, sz / 1024, describe(p)))
        if live:
            os.unlink(p)
    print("\n%s %d file(s), %.2f GB." % ("Deleted" if live else "Would delete", len(targets), total / 1073741824))
    if live:
        survivors, _ = candidates()
        print("post-purge survivor count in scope: %d %s"
              % (len(survivors), "✓" if not survivors else "— NOT CLEAN: %s" % survivors))
        print("NOTE (APFS): rm unlinks; it does not overwrite. Gone from the live "
              "filesystem; backup media is a separate control (TM /private/tmp "
              "question remains David's GUI check).")
        sys.exit(0 if not survivors else 1)
    else:
        print("Run with --write --confirmed-by-david to execute.")


if __name__ == "__main__":
    main()
