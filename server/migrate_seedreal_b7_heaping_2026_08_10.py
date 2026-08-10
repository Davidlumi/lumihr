#!/usr/bin/env python3
"""Seed-realism B7 — Tier-3 numeric round-number heaping (2026-08-10).

Real survey £/% answers heap on round numbers; the seed spread them uniformly
(e.g. £113 wellbeing budgets, 2.9% pay budgets). Snap ~70% of values to the natural
heap grid, keep ~30% as off-heap 'actuals'. DETERMINISTIC (sha256 over fixed ids;
no RNG/time). Value-only UPDATE; submitted_at never touched.

GATE SAFETY (verified by the design pass): none of these 7 metrics is in
frozen_targets.json or generated_marginals.json (marginals/ruled/coherence) — they
appear only in the non-binding `context` block. qa_plausibility CHECK A scores only
yes/no eligibility matrices (these are numeric -> skipped); CHECK B/C iterate only
single_select/yes_no/multi_select (numeric/matrix skipped). So the only invariants to
protect are self-imposed: the MEDIAN (feeds the PercentileRuler P50), matrix
MONOTONICITY, and coded-absence. All are preserved:
  - MEDIAN: the central order-statistic(s) are PINNED (never snapped) and a no-cross
    clamp forbids any value crossing the median -> P50 is byte-stable.
  - MONOTONICITY: the car matrix is snapped whole-org then re-sorted DESC by level.
  - CODED ABSENCE: REW26_WEL_BUDGET's 'Not applicable' rows are out of scope.
REW_BEN_FLEX_ALLOW_01 is EXCLUDED — snapping its fine 0.1 seniority ladder collapses
it (destroys more realism than it adds).

    python3 server/migrate_seedreal_b7_heaping_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b7_heaping_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SNAP_PCT = 70   # ~70% snapped, ~30% kept as actuals
CAR_LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
              "supervisor_team_leader", "frontline_individual_contributor"]


def sel(qid, key):
    return int(hashlib.sha256(("%s|%s" % (qid, key)).encode()).hexdigest()[:8], 16) % 100


def snap(v, g):
    return round(v / g) * g


def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changes = defaultdict(int)
    import math

    def write(qid, org, row, newval):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, qid, row)).fetchone()
        if cur is None or (cur["value"] or "") == newval:
            return
        changes[qid] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (newval, org, qid, row))

    def fmt(v, decimals):
        return ("%.1f" % v) if decimals else str(int(round(v)))

    # ---- (A) single-value numerics: snap w/ no-cross-median clamp + central pin ----
    def heap_single(qid, g, decimals):
        rows = [(a["org_id"], num(a["value"])) for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (qid,))]
        rows = [(o, v) for o, v in rows if v is not None]
        if len(rows) < 3:
            return
        M = median([v for _, v in rows])
        ordered = sorted(rows, key=lambda t: (t[1], t[0]))
        n = len(ordered)
        pin = {ordered[n // 2][0]} if n % 2 else {ordered[n // 2 - 1][0], ordered[n // 2][0]}
        lo = math.floor(M / g) * g; hi = math.ceil(M / g) * g
        for o, v in rows:
            if o in pin or sel(qid, o) >= SNAP_PCT:
                continue
            t = snap(v, g)
            if v < M:
                t = min(t, lo)
            elif v > M:
                t = max(t, hi)
            else:
                continue
            write(qid, o, "", fmt(t, decimals))

    heap_single("PROP_9e4ad87f", 0.5, True)                 # salary-increase budget %
    heap_single("REW26_BEN_PENSION_COST_SHARE", 0.5, True)  # pension cost share %
    heap_single("PROP_e63cf45a", 5, False)                  # workforce cost % of revenue
    heap_single("PROP_d16bae79", 1000, False)               # workforce cost per FTE £
    heap_single("REW26_WEL_BUDGET", 25, True)               # wellbeing budget £/head (NA skipped by value parse)

    # ---- (B) car allowance £ by LEVEL: whole-org snap + DESC re-sort (monotone) ----
    CAR = "fa0f46f6-61e3-41d1-a2d1-3e57483bb1cf"
    car = defaultdict(dict)
    for a in c.execute("SELECT org_id,matrix_row_id,value FROM answers WHERE question_id=? AND snapshot_id=1 AND value!=''", (CAR,)):
        v = num(a["value"])
        if v is not None:
            car[a["org_id"]][a["matrix_row_id"]] = v
    for org, cells in car.items():
        if sel(CAR, org) >= SNAP_PCT:
            continue
        present = [l for l in CAR_LEVELS if l in cells]
        snapped = sorted((snap(cells[l], 1000) for l in present), reverse=True)  # DESC = senior first
        for l, val in zip(present, snapped):
            write(CAR, org, l, fmt(val, False))

    # ---- (C) allowances £ by TYPE: per-type median clamp + pin ----
    ALLOW = "a7ed418e-b057-4b70-ab58-31e897b7c1b6"
    bytype = defaultdict(list)
    for a in c.execute("SELECT org_id,matrix_row_id,value FROM answers WHERE question_id=? AND snapshot_id=1 AND value!=''", (ALLOW,)):
        v = num(a["value"])
        if v is not None:
            bytype[a["matrix_row_id"]].append((a["org_id"], v))
    for typ, rows in bytype.items():
        if len(rows) < 3:
            continue
        M = median([v for _, v in rows])
        ordered = sorted(rows, key=lambda t: (t[1], t[0]))
        n = len(ordered)
        pin = {ordered[n // 2][0]} if n % 2 else {ordered[n // 2 - 1][0], ordered[n // 2][0]}
        lo = math.floor(M / 500) * 500; hi = math.ceil(M / 500) * 500
        for o, v in rows:
            if o in pin or sel(ALLOW, o + "|" + typ) >= SNAP_PCT:
                continue
            t = snap(v, 500)
            if v < M:
                t = min(t, lo)
            elif v > M:
                t = max(t, hi)
            else:
                continue
            write(ALLOW, o, typ, fmt(t, False))

    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    # verify medians held
    for qid, g, dec in [("PROP_9e4ad87f", 0.5, True), ("REW26_BEN_PENSION_COST_SHARE", 0.5, True),
                        ("PROP_e63cf45a", 5, False), ("PROP_d16bae79", 1000, False), ("REW26_WEL_BUDGET", 25, True)]:
        vals = [num(a["value"]) for a in c.execute(
            "SELECT value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (qid,))]
        vals = [v for v in vals if v is not None]
        print("  %-30s median=%s" % (qid, median(vals)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
