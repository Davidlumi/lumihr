#!/usr/bin/env python3
"""Seed-realism B11 — Tier-3 panel: timestamp re-stamp (2026-08-10).

answers.submitted_at had only ~30 distinct values across 89,320 rows (build batches;
every org 'answered' the same question in the same second), and 1,739 rows held
BUILD-TAG STRINGS ('2026-07-18 diff15' etc.) where a timestamp belongs. Re-stamp every
row into a plausible per-org collection SESSION model, and stagger the bulk-inserted
org lifecycle dates. VALUE-ONLY on answers (submitted_at) + orgs lifecycle columns —
no answer VALUE is touched, so all frozen/marginal/coherence/monotonicity are
byte-identical.

Window: 2026-05-04 .. 2026-07-17 (~11 weeks). Min refresh cadence is 12 months, so
every stamp (~1-3 months before now) keeps metrics FRESH — refresh-cadence behaviour
is preserved (verified against refresh_policy: due = oldest row < now-cadence). All
stamps canonical 'YYYY-MM-DD HH:MM:SS' (qa_refresh C12). Deterministic sha256; no
RNG/wall-clock. DRY-RUN unless --write --confirmed-by-david.

    python3 server/migrate_seedreal_b11_timestamps_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b11_timestamps_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from datetime import date, datetime, timedelta

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
WIN_START = date(2026, 5, 4)   # Monday
WIN_DAYS = 70                  # -> Fri 2026-07-17


def u(tag, key):
    return int(hashlib.sha256(("%s|%s" % (tag, key)).encode()).hexdigest()[:8], 16) / 0x100000000


def weekday_dt(base_day, hour, minute, second):
    d = base_day
    if d.weekday() >= 5:                       # Sat/Sun -> Monday
        d = d + timedelta(days=7 - d.weekday())
    return datetime(d.year, d.month, d.day, hour, minute, second)


def session_dt(tag, org, seed):
    day_off = int(u(tag + "_DAY", org) * (WIN_DAYS - 5))
    base = WIN_START + timedelta(days=day_off)
    hr = 18 + int(u(tag + "_EVE", org) * 4) if u(tag + "_EVE", org) < 0.15 else 9 + int(u(tag + "_HR", org) * 8)
    return weekday_dt(base, hr, int(u(tag + "_MIN", org) * 60), int(seed % 60))


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    seed_orgs = [r["org_id"] for r in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1")]

    # per-org sessions
    sess = {}
    for org in seed_orgs:
        s1 = session_dt("S1", org, int(u("S1_SEC", org) * 60))
        two = u("NSESS", org) >= 0.55
        s2 = None
        if two:
            gap = 1 + int(u("GAP", org) * 5)
            s2 = weekday_dt((s1 + timedelta(days=gap)).date(),
                            9 + int(u("S2_HR", org) * 8), int(u("S2_MIN", org) * 60), int(u("S2_SEC", org) * 60))
        sess[org] = (s1, s2)

    def stamp_for(org, qid, row):
        s1, s2 = sess[org]
        h = int(hashlib.sha256(("%s|%s" % (qid, row)).encode()).hexdigest()[:6], 16)
        base = s2 if (s2 is not None and h % 2 == 0) else s1
        dt = base + timedelta(minutes=h % 47, seconds=(h // 47) % 60)   # within-session spread
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # ---- answers.submitted_at (all 89,320) ----
    rows = list(c.execute("SELECT org_id,question_id,matrix_row_id FROM answers WHERE snapshot_id=1"))
    updates = [(stamp_for(r["org_id"], r["question_id"], r["matrix_row_id"]),
                r["org_id"], r["question_id"], r["matrix_row_id"]) for r in rows]
    if WRITE:
        c.executemany("UPDATE answers SET submitted_at=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1", updates)

    # ---- orgs lifecycle: created_at (stagger), clock_start & insights_unlocked_at (only where non-null) ----
    orgcols = [r["name"] for r in c.execute("PRAGMA table_info(orgs)")]
    org_upd = 0
    for org in seed_orgs:
        s1 = sess[org][0]
        created = (s1 - timedelta(days=1 + int(u("CRE", org) * 20)))
        created_dt = weekday_dt(created.date(), 9 + int(u("CRE_HR", org) * 8), int(u("CRE_MIN", org) * 60), int(u("CRE_SEC", org) * 60))
        cs = created_dt.strftime("%Y-%m-%d %H:%M:%S")
        cur = c.execute("SELECT created_at, clock_start, insights_unlocked_at FROM orgs WHERE org_id=?", (org,)).fetchone()
        if cur is None:
            continue
        if WRITE:
            c.execute("UPDATE orgs SET created_at=? WHERE org_id=?", (cs, org))
            if cur["clock_start"] is not None:      # preserve NULLs
                c.execute("UPDATE orgs SET clock_start=? WHERE org_id=?", (cs, org))
            if cur["insights_unlocked_at"] is not None:
                iu = (created_dt + timedelta(days=1 + int(u("IU", org) * 10))).strftime("%Y-%m-%d %H:%M:%S")
                c.execute("UPDATE orgs SET insights_unlocked_at=? WHERE org_id=?", (iu, org))
        org_upd += 1
    if WRITE:
        c.commit()

    # report
    distinct = c.execute("SELECT COUNT(DISTINCT submitted_at) d FROM answers WHERE snapshot_id=1").fetchone()["d"]
    noncanon = c.execute("SELECT COUNT(*) n FROM answers WHERE snapshot_id=1 AND submitted_at NOT GLOB "
                         "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'").fetchone()["n"]
    rng = c.execute("SELECT MIN(submitted_at) a, MAX(submitted_at) b FROM answers WHERE snapshot_id=1").fetchone()
    print(("APPLIED" if WRITE else "DRY RUN(read reflects pre-state)") + " — answers re-stamped: %d, orgs updated: %d" % (len(updates), org_upd))
    print("  distinct submitted_at: %d (was 30) | non-canonical: %d (was 1739) | range %s .. %s" % (distinct, noncanon, rng["a"], rng["b"]))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
