#!/usr/bin/env python3
"""Seed-realism correction (reward-persona sense-check, 2026-08-10).

Three plausibility defects flagged by a reward-professional review of the seeded
benchmark; none are frozen-anchored (frozen_targets.json holds only 8 wellbeing/
pension metrics), so these are safe to correct. Honours LUMI_DB so it can run
against a throwaway; DRY-RUN unless BOTH --write and --confirmed-by-david are given.

FIX A — Company car (CAR_STATUS_01) sector inversion. The status-car benefit was
  distributed backwards: car-light sectors (Tech 88%, Media 78%) highest, car/van +
  sales sectors (Construction/Logistics 7%) lowest. CAR_STATUS_01 is a Tier-2 GLOBAL
  marginal (target 35% ±5pp, base_type all_only) — NOT sector-conditioned — so we
  rebalance WHICH sectors hold the 'Yes' answers to a real-world-plausible spread,
  keeping the global count on 35% (54/154). CAR has no hard coherence pair; the only
  dependant is the soft CAR_COST_02 lean (No when no status car), which we align.

FIX B — Education operating LTIP/equity plans. 5 Education orgs answered
  REW_INC_131='Yes' (RSUs/options/performance shares) — schools/colleges have no
  equity to grant. Set INC_131='No' and cascade the hard coherence chain:
  INC_132='Not applicable', INC_133 all levels 'No' (INC_131=Yes ⟺ INC_133 has an
  eligible level; INC_132-substantive ⊆ INC_131=Yes).

FIX C — 'Grants equity but has no shares' contradiction. Orgs with an equity-typed
  LTIP (RSUs/options/perf-shares) that also answered the all-employee share-plan
  question 'Not applicable (no shares)'. For the sector-plausible ones (Tech/FS/
  Manufacturing/Energy/Logistics) keep the LTIP but switch INC_132 to 'Cash LTIP'
  so 'no shares' is consistent — no share-plan child chain touched. (Any Education
  org here is already resolved by Fix B.)

FIX D — One Healthcare org's bonus gradient inverted (Manager > Senior Manager).
  Raise Senior Manager to at least Manager to restore monotonicity.

    python3 server/migrate_seedreal_car_ltip_2026_08_10.py                       # dry run
    python3 server/migrate_seedreal_car_ltip_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, re

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
SNAP = 1
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

CAR = "CAR_STATUS_01"; COST = "CAR_COST_02"
INC131, INC132, INC133 = "REW_INC_131", "REW_INC_132", "REW_INC_133"
SHARE = "REW264_INC_SHAREPLAN"; BONUS = "323ffcf1-749b-43f3-bf34-1de6b8b1ca67"

# Real-world-plausible status-car 'Yes' counts per sector (senior grade-based cars).
# Sums to 54 = 35% of the 154 orgs that answer CAR_STATUS_01 (the Tier-2 marginal).
CAR_TARGET = {
    "Financial Services": 5, "Professional Services": 5, "Manufacturing & Engineering": 6,
    "Energy, Utilities & Environmental Services": 5, "Construction & Infrastructure": 7,
    "Logistics, Transport & Distribution": 7, "Healthcare & Life Sciences": 3,
    "Retail & Consumer Goods": 6, "Hospitality, Leisure & Travel": 4,
    "Technology, Software & Digital": 1, "Media, Communications & Creative Industries": 2,
    "Public Sector & Government": 1, "Charity, Non-Profit & Social Enterprise": 1,
    "Education (Public & Private)": 1,
}
EQUITY = ("RSU", "Share option", "Performance share")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    def get(q): return {(a["org_id"], a["matrix_row_id"]): a["value"] for a in c.execute(
        "SELECT org_id,matrix_row_id,value FROM answers WHERE question_id=? AND snapshot_id=?", (q, SNAP))}
    changes = []  # (qid, org, row, old, new)
    def setv(q, org, row, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=?",
                        (org, q, row, SNAP)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes.append((q, org, row, cur["value"], new))
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=?",
                      (new, org, q, row, SNAP))

    # ---- FIX A: CAR_STATUS_01 sector rebalance (global-conserving) ----
    car = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (CAR, SNAP))}
    cost_rows = {a["org_id"] for a in c.execute(
        "SELECT org_id FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (COST, SNAP))}
    from collections import defaultdict
    bysec = defaultdict(list)
    for oid in sorted(car):                       # deterministic (org_id sort)
        if oid in ind: bysec[ind[oid]].append(oid)
    for sec, orgs in bysec.items():
        tgt = CAR_TARGET.get(sec)
        if tgt is None: continue
        for i, oid in enumerate(orgs):
            want = "Yes" if i < tgt else "No"
            setv(CAR, oid, "", want)
            if want == "No" and oid in cost_rows:  # align the soft lean (no status car -> no EV mandate)
                setv(COST, oid, "", "No")

    # ---- FIX B: Education LTIP off + cascade ----
    inc131 = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (INC131, SNAP))}
    edu = [o for o, v in inc131.items() if str(v).startswith("Yes") and "Education" in str(ind.get(o, ""))]
    inc133_rows = [r["matrix_row_id"] for r in c.execute(
        "SELECT DISTINCT matrix_row_id FROM answers WHERE question_id=? AND snapshot_id=?", (INC133, SNAP))]
    for o in edu:
        setv(INC131, o, "", "No")
        setv(INC132, o, "", "Not applicable")
        for row in inc133_rows:
            setv(INC133, o, row, "No")

    # ---- FIX C: equity LTIP + 'no shares' -> Cash LTIP (non-education, sector-plausible) ----
    typ = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (INC132, SNAP))}
    share = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (SHARE, SNAP))}
    for o, v in inc131.items():
        if o in edu: continue
        if str(v).startswith("Yes") and any(e in str(typ.get(o, "")) for e in EQUITY) \
           and "no shares" in str(share.get(o, "")).lower():
            setv(INC132, o, "", "Cash LTIP")

    # ---- FIX D: bonus gradient — raise Senior Manager to >= Manager where inverted ----
    bon = get(BONUS)
    orgs_bon = {k[0] for k in bon}
    for o in orgs_bon:
        sm = bon.get((o, "senior_manager")); mg = bon.get((o, "manager"))
        def n(x):
            try: return float(re.sub(r"[^0-9.]", "", str(x)))
            except: return None
        if n(sm) is not None and n(mg) is not None and n(sm) < n(mg):
            setv(BONUS, o, "senior_manager", str(int(n(mg))))

    if WRITE: c.commit()
    # ---- report ----
    from collections import Counter
    byq = Counter(ch[0] for ch in changes)
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d cell changes  %s" % (len(changes), dict(byq)))
    # new CAR global share
    newcar = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=?", (CAR, SNAP))}
    y = sum(1 for v in newcar.values() if v == "Yes"); t = len(newcar)
    print("  CAR_STATUS_01 global 'Yes': %d/%d = %.1f%% (target 35%% ±5pp)" % (y, t, 100*y/t))
    for ch in changes[:8]:
        print("   ", ch)
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
