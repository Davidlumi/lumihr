#!/usr/bin/env python3
"""Seed-realism B9 — Tier-3: DC pension ladder recentre + diversity (2026-08-10).

Two defects in REW_BEN_112 (typical employer pension contribution, by level):
  1. MAGNITUDE — DC employer contributions sat at ~10% median (board ~18%) vs a UK
     norm of ~5-6% (only ~25% of cells in the 3-6% band vs ~68% market). David ruled
     RECENTRE TO MARKET.
  2. TEXTURE — one rigid by-level template was stamped on all 220 orgs (fixed offsets,
     zero flat schemes) — a generator fingerprint. Most UK DC employers run a single
     rate; the rest a light 2-3 tier.
Fix: regenerate each DC org's ladder from a deterministic shape mixture (~55% flat,
~25% 2-tier, ~20% 3-tier) with a heaped base rate in 3-6% and a small senior uplift,
monotonic by construction. PENSION_TYPE='DB' and 'Hybrid' orgs are LEFT UNTOUCHED
(DB was set to flat 15-28% in B4). REW_BEN_112 is not frozen/marginal and numeric
matrices are skipped by qa_plausibility CHECK A, so this is gate-safe; the value we
protect is realism (monotonicity, market magnitude). Deterministic sha256; DRY-RUN
unless --write --confirmed-by-david.

    python3 server/migrate_seedreal_b9_pension_ladders_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b9_pension_ladders_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW_BEN_112"
# senior -> junior
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]
SENIOR3 = {"board_executive", "director", "head_of"}
MID = {"senior_manager", "manager"}
BASES = [3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 7, 8]   # heaped; ~17% generous (7-8) to match the ~32% market tail above 6%


def u(tag, org):
    return int(hashlib.sha256(("%s|%s" % (tag, org)).encode()).hexdigest()[:8], 16) / 0x100000000


def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def median(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ptype = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW26_BEN_PENSION_TYPE' AND matrix_row_id='' AND snapshot_id=1")}
    # present levels per org (only rewrite rows that exist)
    present = defaultdict(set)
    for a in c.execute("SELECT org_id,matrix_row_id FROM answers WHERE question_id=? AND snapshot_id=1", (Q,)):
        present[a["org_id"]].add(a["matrix_row_id"])
    changes = 0; touched = 0

    def ladder(org):
        base = BASES[int(u("PEN_BASE", org) * len(BASES))]
        s = u("PEN_SHAPE", org)
        upl = [2, 3, 4][int(u("PEN_UPL", org) * 3)]
        val = {}
        for lvl in LEVELS:
            if s < 0.55:                        # FLAT
                val[lvl] = base
            elif s < 0.80:                      # 2-TIER: seniors +uplift
                val[lvl] = base + upl if lvl in SENIOR3 else base
            else:                               # 3-TIER
                val[lvl] = base + upl if lvl in SENIOR3 else (base + max(1, upl // 2) if lvl in MID else base)
        return val

    for org, lvls in present.items():
        if ptype.get(org) != "DC":              # leave DB / Hybrid ladders alone
            continue
        touched += 1
        lad = ladder(org)
        # monotonic by construction (senior>=junior); write only existing rows
        for lvl in LEVELS:
            if lvl not in lvls:
                continue
            newv = str(lad[lvl])
            cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                            (org, Q, lvl)).fetchone()
            if cur is not None and (cur["value"] or "") != newv:
                changes += 1
                if WRITE:
                    c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                              (newv, org, Q, lvl))
    if WRITE:
        c.commit()

    # ---- verify ----
    cells = [num(a["value"]) for a in c.execute(
        "SELECT value FROM answers WHERE question_id=? AND snapshot_id=1 AND value!=''", (Q,))]
    cells = [v for v in cells if v is not None]
    dc_cells = []
    permo = 0; nmo = 0
    for org, lvls in present.items():
        seq = []
        for lvl in LEVELS:
            r = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                          (org, Q, lvl)).fetchone()
            if r and num(r["value"]) is not None:
                seq.append(num(r["value"]))
        if seq:
            nmo += 1
            if all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1)):
                permo += 1
        if ptype.get(org) == "DC":
            dc_cells += [x for x in seq]
    in36 = sum(1 for v in dc_cells if 3 <= v <= 6)
    # shape diversity among DC
    shapes = set()
    for org in present:
        if ptype.get(org) == "DC":
            shapes.add(tuple(num(c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                       (org, Q, lvl)).fetchone()["value"]) for lvl in LEVELS if lvl in present[org]))
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d DC orgs re-laddered, %d cells changed" % (touched, changes))
    print("  DC pooled median: %.1f (was ~10) | DC cells in 3-6%%: %d/%d = %.0f%% (target ~68)" %
          (median(dc_cells) if dc_cells else 0, in36, len(dc_cells), 100 * in36 / len(dc_cells) if dc_cells else 0))
    print("  distinct DC ladder shapes: %d (was 1 template) | monotonic orgs: %d/%d" % (len(shapes), permo, nmo))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
