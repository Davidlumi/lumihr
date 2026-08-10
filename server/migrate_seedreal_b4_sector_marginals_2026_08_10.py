#!/usr/bin/env python3
"""Seed-realism B4 — Tier-2 sector/size fingerprints, marginal-conserving (2026-08-10).

Three sector/size corrections that each CONSERVE their register/frozen/ruled global
distribution (reallocation only — permitted for anchored metrics). LUMI_DB-aware;
DRY-RUN unless --write --confirmed-by-david.

- OT_04_b14623a6 (register marginal, global ~0.63 Yes): unsocial-hours premium was
  inverted — office sectors ~90-100% (Tech 8/8), shift sectors low (Hospitality
  4/15). Reset per-sector Yes-counts to a shift-operating profile that holds the
  classified Yes-total (~107) so the global marginal is conserved.
- REW26_BEN_PENSION_TYPE (FROZEN 21 DB / 195 DC / 4 Hybrid): Education showed 0/10 DB
  despite statutory TPS/LGPS/USS membership, while stray DB sat in non-public sectors.
  SWAP 3 Education DC orgs -> DB with 3 non-public DB orgs -> DC (frozen global
  conserved exactly); set the new Education-DB orgs' REW_BEN_112 to TPS/LGPS-level
  flat rates and drop the de-DB'd orgs to a DC ladder.
- REW264_HLT_VIRTUALGP (RULED 99 all / 29 some / 24 via-PMI / 68 no): 'Yes all
  employees' saturated the top bands (100% at 10,000+, 92% at 5,000-9,999) vs the
  register's own ~54% large-firm anchor, while SMEs undershot. PERMUTE: swap top-band
  'Yes all' answers with SME non-'Yes-all' answers (ruled option counts conserved
  exactly), lowering top-band saturation and lifting the SME bands.

    python3 server/migrate_seedreal_b4_sector_marginals_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b4_sector_marginals_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict, Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]

OT = "OT_04_b14623a6"
# target Yes-count per classified sector (sums to ~107 = current classified Yes -> global held)
OT_TARGET = {
    "Construction & Infrastructure": 14, "Logistics, Transport & Distribution": 14,
    "Manufacturing & Engineering": 13, "Retail & Consumer Goods": 14,
    "Hospitality, Leisure & Travel": 13, "Public Sector & Government": 11,
    "Healthcare & Life Sciences": 4, "Energy, Utilities & Environmental Services": 6,
    "Technology, Software & Digital": 2, "Financial Services": 3,
    "Professional Services": 3, "Media, Communications & Creative Industries": 3,
    "Education (Public & Private)": 5, "Charity, Non-Profit & Social Enterprise": 2,
}
N_EDU_DB = 3
N_VGP_SWAP = 12


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = defaultdict(int)
    # The demo fixture org is what several gates pin their examples to (qa_commentary
    # hardcodes it being 'behind' on OT_04). It is a fixture, not a real benchmark
    # participant, so exclude it from the OT_04 sector reallocation to keep that stable.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from demo_org import demo_row
        DEMO_ID = dict(demo_row(c))["org_id"]
    except Exception:
        DEMO_ID = None

    def rows(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, row, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, q, row)).fetchone()
        if cur is None or (cur["value"] or "") == new:
            return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (new, org, q, row))

    # ---- OT_04 shift premium: per-sector Yes-count reset (global conserved) ----
    ot = rows(OT)
    bysec = defaultdict(list)
    for o in sorted(ot):
        if o in ind:
            bysec[ind[o]].append(o)
    for sec, orgs in bysec.items():
        tgt = OT_TARGET.get(sec)
        if tgt is None:
            continue
        orgs = [o for o in orgs if o != DEMO_ID]   # leave the demo fixture's OT_04 untouched
        # keep current Yes-holders first so churn is minimal, then set first `tgt` = Yes
        orgs = sorted(orgs, key=lambda o: (0 if str(ot[o]).strip() == "Yes" else 1, o))
        for i, o in enumerate(orgs):
            setv(OT, o, "", "Yes" if i < tgt else "No")

    # ---- PENSION_TYPE: swap Education<->non-public DB (frozen conserved) ----
    pt = rows("REW26_BEN_PENSION_TYPE")
    edu_dc = sorted(o for o, v in pt.items() if v == "DC" and "Education" in str(ind.get(o, "")))
    # de-DB donors: DB orgs NOT in public sector / education (the audit's "stray DB")
    stray_db = sorted(o for o, v in pt.items()
                      if v == "DB" and not any(s in str(ind.get(o, "")) for s in ("Public Sector", "Education")))
    k = min(N_EDU_DB, len(edu_dc), len(stray_db))
    for i in range(k):
        e, d = edu_dc[i], stray_db[i]
        setv("REW26_BEN_PENSION_TYPE", e, "", "DB")     # Education -> DB (TPS/LGPS/USS)
        setv("REW26_BEN_PENSION_TYPE", d, "", "DC")     # stray private DB -> DC
        # DB has no member fund choice -> clear the DC-only pension children (coherence
        # pairs: substantive AEDEFAULT/GREENDEFAULT require parent != DB)
        setv("REW264_PEN_AEDEFAULT", e, "", "Not applicable (no DC scheme)")
        setv("REW264_PEN_GREENDEFAULT", e, "", "Not applicable (no DC default fund)")
        for lvl in LEVELS:                               # Education DB gets TPS/LGPS flat rate
            setv("REW_BEN_112", e, lvl, "23")
        # de-DB'd org drops to a modest DC ladder (was set to a DB rate by M1)
        for lvl, r in zip(LEVELS, ["8", "7", "6", "5", "5", "4", "4"]):
            setv("REW_BEN_112", d, lvl, r)

    # ---- VIRTUALGP: permute top-band 'Yes all' with SME non-'Yes-all' (ruled conserved) ----
    vg = rows("REW264_HLT_VIRTUALGP")
    top = sorted(o for o in vg if fte.get(o) in ("5,000-9,999", "10,000+") and vg[o] == "Yes all employees")
    sme = sorted(o for o in vg if fte.get(o) in ("50-249", "250-999") and vg[o] != "Yes all employees")
    k2 = min(N_VGP_SWAP, len(top), len(sme))
    for i in range(k2):
        t, s = top[i], sme[i]
        setv("REW264_HLT_VIRTUALGP", t, "", vg[s])   # top band gets the SME's (lower) value
        setv("REW264_HLT_VIRTUALGP", s, "", "Yes all employees")

    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  OT_04 global (conserve ~135 Yes):", dict(Counter(rows(OT).values())))
    print("  PENSION_TYPE global (conserve 21DB/195DC/4H):", dict(Counter(rows("REW26_BEN_PENSION_TYPE").values())))
    print("  VIRTUALGP global (conserve 99/29/24/68):", dict(Counter(rows("REW264_HLT_VIRTUALGP").values())))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
