#!/usr/bin/env python3
"""Seed-realism B10 — Tier-3: target-bonus ladder heaping + uncap (2026-08-10).

REW_INC_111 (target bonus %, by level) was a fixed multiplier chain (board/director
ratio 1.333 sd 0.017, machine-tight), with no round-number heaping and board hard-
capped at 52% in every sector — synthetic, and it understates FS/listed exec
incentive design. Regenerate each responder's ladder: a sector-tilted, HEAPED board
target (FS/Tech uncapped to 60-100%+), then a varied, heaped, monotonic descent to
frontline. Preserves each org's answered LEVEL SET (no rows added/removed, so bonus
breadth / INC_103 coherence is untouched). Free metric, numeric matrix (skipped by
CHECK A), no coherence pair -> gate-safe. Deterministic sha256; DRY-RUN unless
--write --confirmed-by-david.

    python3 server/migrate_seedreal_b10_bonus_ladder_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b10_bonus_ladder_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW_INC_111"
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]
HEAP = [1, 2, 3, 5, 7, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 100]
# sector board-target heap sets (uncapped for HIGH)
HIGH = {"Financial Services", "Technology, Software & Digital"}
MID = {"Professional Services", "Energy, Utilities & Environmental Services",
       "Media, Communications & Creative Industries", "Healthcare & Life Sciences"}
BOARD_HIGH = [50, 60, 75, 100]      # FS/Tech: uncapped exec design
BOARD_MID = [40, 50, 60]            # prof-svcs/energy/media/health
BOARD_STD = [25, 30, 40, 50]        # everyone else: lower sectors ~preserved, small low tail
# factor of board per lower level (base); small per-org jitter applied
FACTOR = {"director": 0.72, "head_of": 0.50, "senior_manager": 0.38,
          "manager": 0.25, "supervisor_team_leader": 0.12, "frontline_individual_contributor": 0.05}


def u(tag, org):
    return int(hashlib.sha256(("%s|%s" % (tag, org)).encode()).hexdigest()[:8], 16) / 0x100000000


def snap_heap(v):
    return min(HEAP, key=lambda h: abs(h - v))


def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    present = defaultdict(set)
    for a in c.execute("SELECT org_id,matrix_row_id FROM answers WHERE question_id=? AND snapshot_id=1 AND value!=''", (Q,)):
        present[a["org_id"]].add(a["matrix_row_id"])
    changes = 0

    def board_set(org):
        s = ind.get(org, "")
        return BOARD_HIGH if s in HIGH else (BOARD_MID if s in MID else BOARD_STD)

    for org, lvls in present.items():
        bs = board_set(org)
        board = bs[int(u("BON_BOARD", org) * len(bs))]
        vals = {"board_executive": board}
        prev = board
        for lvl in LEVELS[1:]:
            f = FACTOR[lvl] * (0.85 + 0.30 * u("BON_" + lvl, org))   # +/-15% jitter
            t = snap_heap(board * f)
            t = min(t, prev)          # enforce non-increasing
            t = max(t, 1)
            vals[lvl] = t
            prev = t
        for lvl in LEVELS:
            if lvl not in lvls:
                continue
            newv = str(int(vals[lvl]))
            cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                            (org, Q, lvl)).fetchone()
            if cur is not None and (cur["value"] or "") != newv:
                changes += 1
                if WRITE:
                    c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                              (newv, org, Q, lvl))
    if WRITE:
        c.commit()

    # verify
    m = defaultdict(dict)
    for a in c.execute("SELECT org_id,matrix_row_id,value FROM answers WHERE question_id=? AND snapshot_id=1 AND value!=''", (Q,)):
        v = num(a["value"])
        if v is not None:
            m[a["org_id"]][a["matrix_row_id"]] = v
    def med(lvl):
        vv = sorted(m[o][lvl] for o in m if lvl in m[o]); return vv[len(vv) // 2] if vv else None
    boards = [m[o]["board_executive"] for o in m if "board_executive" in m[o]]
    heapshare = sum(1 for o in m for l in m[o] if m[o][l] in HEAP) / sum(len(m[o]) for o in m)
    mono = sum(1 for o in m if all(m[o].get(LEVELS[i], 0) >= m[o].get(LEVELS[i + 1], 0)
               for i in range(len(LEVELS) - 1) if LEVELS[i] in m[o] and LEVELS[i + 1] in m[o]))
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d cells changed" % changes)
    print("  board median=%s max=%s (was 40/52) | frontline med=%s" % (med("board_executive"), max(boards), med("frontline_individual_contributor")))
    print("  FS/Tech board max:", max((m[o]["board_executive"] for o in m if ind.get(o) in HIGH and "board_executive" in m[o]), default=None))
    print("  on-heap share: %.0f%% (was ~16) | monotonic orgs: %d/%d" % (100 * heapshare, mono, len(m)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
