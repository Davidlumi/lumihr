#!/usr/bin/env python3
"""Seed-realism corrections #3 (persona sweep across all metrics, 2026-08-10).

Verified data-fixes from the reward-persona sweep (overall/sector/FTE). Each was
confirmed against raw data (several 'high' sweep findings were substrate artefacts
— binary matrices my numeric stats couldn't parse, composite-string parsing — and
are NOT touched here). None of the four metrics below is frozen-anchored or a
register marginal, so these are safe. LUMI_DB-aware; DRY-RUN unless --write
--confirmed-by-david.

A — EMI at >=250 FTE (REW264_INC_EMICSOP). EMI is statutorily restricted to
  companies with <250 employees (ITEPA 2003 Sch 5). 18 orgs in the 250-999 /
  1,000-4,999 / 5,000-9,999 / 10,000+ bands answered 'EMI' (or 'Both'). Change
  those to 'CSOP' (no size cap, the large-firm equivalent). Coherence-safe:
  EMICSOP-substantive still requires share capital, which those orgs have.

B — Enhanced optical (REW264_HLT_OPTICAL) had an INVERSE size gradient (Yes-share
  87% at 50-249 down to 25% at 10,000+) — backwards for a cheap near-universal
  perk. Rebalance to a plausible RISING gradient by size.

C — EOT in Public Sector (REW265_INC_EOT). An Employee Ownership Trust is a
  private-company share structure a public body cannot hold. The 1 'EOT-owned'
  Public Sector org -> 'No'.

D — Earned Wage Access (REW264_WEL_EWA) sector inversion. EWA (Wagestream-type) is
  a frontline/hourly product, but adoption was highest in white-collar sectors
  (Tech/FS/Media 67-75%) and lowest in Retail/Hospitality (27%). Rebalance so
  frontline-heavy sectors lead, keeping the global offer count ~constant. Cascade
  the two coherence children (EWACAP/EWAFEES) so they stay 'Not applicable' iff No.

DEFERRED to a ruling (not fixed here): REW_FAI_079 gender-pay-gap reporting is a
register MARGINAL, so raising 250+ compliance to the statutory level would breach
its target — the marginal must be updated alongside the data (David's call).

    python3 server/migrate_seedreal_persona2_2026_08_10.py                       # dry run
    python3 server/migrate_seedreal_persona2_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG_BANDS = ("250-999", "1,000-4,999", "5,000-9,999", "10,000+")
FTES = ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]
OPTICAL_TARGET = {"50-249": .80, "250-999": .83, "1,000-4,999": .87, "5,000-9,999": .90, "10,000+": .93}
# EWA plausible offer-rates: frontline/hourly sectors lead, white-collar trail
EWA_TARGET = {
    "Retail & Consumer Goods": .67, "Hospitality, Leisure & Travel": .67,
    "Logistics, Transport & Distribution": .60, "Manufacturing & Engineering": .55,
    "Healthcare & Life Sciences": .50, "Construction & Infrastructure": .47,
    "Public Sector & Government": .40, "Charity, Non-Profit & Social Enterprise": .38,
    "Energy, Utilities & Environmental Services": .38, "Financial Services": .33,
    "Education (Public & Private)": .30, "Professional Services": .30,
    "Technology, Software & Digital": .25, "Media, Communications & Creative Industries": .25,
}
EWA_OFFER = ("Yes all eligible", "Yes hourly/frontline only", "Piloting")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = defaultdict(int)

    def get1(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (org, q)).fetchone()
        if cur is None or (cur["value"] or "") == new:
            return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, org, q))

    # A — EMI at >=250 FTE -> CSOP; then seed EMI in a few eligible <250 firms
    emicsop = get1("REW264_INC_EMICSOP")
    shareplan = get1("REW264_INC_SHAREPLAN")
    for org, v in emicsop.items():
        if fte.get(org) in BIG_BANDS and v in ("EMI", "Both"):
            setv("REW264_INC_EMICSOP", org, "CSOP")
    # removing the illegal large-org EMI leaves zero EMI anywhere, which is itself
    # implausible (EMI is the standard <250-FTE scheme). Seed a realistic handful
    # into small firms that legally qualify: 50-249, has share capital, EMI-typical
    # sector. Deterministic pick by (sector rank, org_id).
    EMI_RANK = {"Technology, Software & Digital": 0, "Media, Communications & Creative Industries": 1,
                "Professional Services": 2, "Manufacturing & Engineering": 3,
                "Financial Services": 4, "Energy, Utilities & Environmental Services": 5}
    cands = [o for o, v in emicsop.items()
             if fte.get(o) == "50-249" and v in ("CSOP", "Neither")
             and "no shares" not in str(shareplan.get(o, "")).lower() and shareplan.get(o)
             and ind.get(o) in EMI_RANK]
    for org in sorted(cands, key=lambda o: (EMI_RANK[ind[o]], o))[:4]:
        setv("REW264_INC_EMICSOP", org, "EMI")

    # B — enhanced optical: rising gradient by size
    optical = get1("REW264_HLT_OPTICAL")
    byband = defaultdict(list)
    for org in sorted(optical):
        if org in fte:
            byband[fte[org]].append(org)
    for band, orgs in byband.items():
        tgt = OPTICAL_TARGET.get(band)
        if tgt is None:
            continue
        n_yes = round(tgt * len(orgs))
        for i, org in enumerate(orgs):
            setv("REW264_HLT_OPTICAL", org, "Yes" if i < n_yes else "Statutory DSE only")

    # C — EOT in public sector -> No
    for org, v in get1("REW265_INC_EOT").items():
        if v == "EOT-owned" and "Public Sector" in str(ind.get(org, "")):
            setv("REW265_INC_EOT", org, "No")

    # D — EWA sector rebalance (+ child cascade)
    ewa = get1("REW264_WEL_EWA")
    bysec = defaultdict(list)
    for org in sorted(ewa):
        if org in ind:
            bysec[ind[org]].append(org)
    for sec, orgs in bysec.items():
        tgt = EWA_TARGET.get(sec)
        if tgt is None:
            continue
        n_off = round(tgt * len(orgs))
        # keep current offerers first -> only the net sector delta flips (min churn)
        orgs = sorted(orgs, key=lambda o: (0 if ewa[o] in EWA_OFFER else 1, o))
        for i, org in enumerate(orgs):
            if i < n_off:
                # keep an existing offer kind; otherwise default to hourly/frontline
                if ewa[org] not in EWA_OFFER:
                    setv("REW264_WEL_EWA", org, "Yes hourly/frontline only")
                    # give the children plausible substantive values (coherence: not 'Not applicable')
                    setv("REW264_WEL_EWACAP", org, "Yes <=50%")
                    setv("REW264_WEL_EWAFEES", org, "Employer-funded (free to employee)")
            else:
                if ewa[org] in EWA_OFFER:
                    setv("REW264_WEL_EWA", org, "No")
                    setv("REW264_WEL_EWACAP", org, "Not applicable")
                    setv("REW264_WEL_EWAFEES", org, "Not applicable")

    print(("APPLIED" if WRITE else "DRY RUN") + " — changes: " + str(dict(changes)))
    # echo new EWA global offer count
    e = get1("REW264_WEL_EWA")
    off = sum(1 for v in e.values() if v in EWA_OFFER)
    print("  EWA offer (post): %d/%d" % (off, len(e)))
    c.commit() if WRITE else None
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
