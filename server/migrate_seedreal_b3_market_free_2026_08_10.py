#!/usr/bin/env python3
"""Seed-realism B3 — market calibration: free single/multi-selects (2026-08-10).

Tier-2 batch, part 2 — four chain-free, free-metric corrections. LUMI_DB-aware;
DRY-RUN unless --write --confirmed-by-david.

- REW264_BEN_EVSALSAC: the 2024-26 salary-sacrifice car market is EV-driven (2-3%
  BiK); a fuel-neutral-dominated book is dated. Flip most Fuel-neutral -> EV-led/
  EV-only (keep ~15% fuel-neutral). Also trim SME over-prevalence: 50-249 was ~50%
  with a scheme vs a ~20-25% market -> move the excess to 'Not applicable'.
- REW_PAY_007 (benchmark sources): 61% single-source, recruiter intel at 8% (norm
  ~35%). Add a second source to single-pick orgs (modal 2), lifting recruiter
  intelligence and live tools toward market.
- REW264_HLT_CASHPLAN: employer-paid cash plans were overcooked at 5,000+ (~55%,
  double medical provision alongside ~90% PMI) and near-absent in the SME bands
  (where cash plans actually live). Reallocate: large bands down to ~25%, small
  bands up to ~17%.
- REW_BEN_038 'Retail discounts': staff discount is the signature retail/hospitality
  benefit but was seeded lowest there. Add it to more Retail (8->~13/15) and
  Hospitality (4->~11/15) orgs. (Not one of the 6 checklist flags rederived in B4,
  so this persists.)

    python3 server/migrate_seedreal_b3_market_free_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b3_market_free_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict, Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
ORDER = ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = defaultdict(int)

    def rows(q):
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

    def sep(v):
        return "; " if "; " in v else ";"

    def add_token(q, org, val, token):
        parts = [p.strip() for p in str(val).split(";") if p.strip()]
        if token in parts:
            return
        parts.append(token)
        setv(q, org, "; ".join(parts))

    # ---- EVSALSAC ----
    ev = rows("REW264_BEN_EVSALSAC")
    # (a) SME trim: 50-249 substantive down to ~25%
    sme = sorted(o for o in ev if fte.get(o) == "50-249" and ev[o] in ("Fuel-neutral", "EV-only", "EV-led (EV prioritised)"))
    keep = round(0.25 * sum(1 for o in ev if fte.get(o) == "50-249"))
    # keep EV-typed first, drop fuel-neutral to NA beyond the target
    sme.sort(key=lambda o: (0 if "EV" in ev[o] else 1, o))
    for o in sme[keep:]:
        if ev[o] == "Fuel-neutral":
            setv("REW264_BEN_EVSALSAC", o, "Not applicable")
            ev[o] = "Not applicable"
    # (b) flip remaining Fuel-neutral -> EV (keep ~1 in 7 fuel-neutral)
    fn = sorted(o for o, v in ev.items() if v == "Fuel-neutral")
    for i, o in enumerate(fn):
        if i % 7 == 6:
            continue  # keep a residual fuel-neutral tail
        setv("REW264_BEN_EVSALSAC", o, "EV-only" if i % 5 == 0 else "EV-led (EV prioritised)")

    # ---- REW_PAY_007 benchmark sources: add a second source to single-pick orgs ----
    RECR = "Recruiter market intelligence"; LIVE = "Live market benchmarking tools (e.g., HR DataHub)"
    PEER = "Peer network / informal comparisons"
    src = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_PAY_007' AND matrix_row_id='' AND snapshot_id=1")}
    singles = sorted(o for o, v in src.items() if len([p for p in str(v).split(";") if p.strip()]) == 1)
    for i, o in enumerate(singles):
        r = i % 5
        tok = RECR if r in (0, 1, 2) else (LIVE if r == 3 else PEER)  # ~60% recruiter, 20% live, 20% peer
        add_token("REW_PAY_007", o, src[o], tok)

    # ---- REW264_HLT_CASHPLAN reallocation by band ----
    cp = rows("REW264_HLT_CASHPLAN")
    EMP = ("Employer-paid all", "Employer-paid some")
    byband = defaultdict(list)
    for o in sorted(cp):
        if o in fte:
            byband[fte[o]].append(o)
    # large bands: employer-paid down to ~25%
    for band in ("5,000-9,999", "10,000+"):
        orgs = byband[band]; tgt = round(0.25 * len(orgs))
        emp = [o for o in orgs if cp[o] in EMP]
        for i, o in enumerate(emp[tgt:]):
            setv("REW264_HLT_CASHPLAN", o, "Voluntary only" if i % 2 == 0 else "No")
    # small bands: any-provision up to ~17%
    for band in ("50-249", "250-999"):
        orgs = byband[band]; tgt = round(0.17 * len(orgs))
        any_prov = [o for o in orgs if cp[o] != "No"]
        no = [o for o in orgs if cp[o] == "No"]
        need = max(0, tgt - len(any_prov))
        for o in no[:need]:
            setv("REW264_HLT_CASHPLAN", o, "Voluntary only")

    # ---- REW_BEN_038 staff discount for Retail & Hospitality ----
    b038 = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND matrix_row_id='' AND snapshot_id=1")}
    for secmatch, tgt in (("Retail", 13), ("Hospitality", 11)):
        orgs = sorted(o for o in b038 if secmatch in str(ind.get(o, "")))
        have = [o for o in orgs if "Retail discounts" in str(b038[o])]
        havent = [o for o in orgs if "Retail discounts" not in str(b038[o])]
        for o in havent[:max(0, tgt - len(have))]:
            add_token("REW_BEN_038", o, b038[o], "Retail discounts")

    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
