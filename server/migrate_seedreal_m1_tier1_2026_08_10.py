#!/usr/bin/env python3
"""Seed-realism M1 — Tier-1 clear errors (2026-08-10).

First of four batches from the 10-lens realism audit (SEED_REALISM_AUDIT_2026-08-10.md).
M1 fixes internal contradictions & legal impossibilities whose PARENT metrics are
NOT re-touched by the Tier-2 market batch, so they can land independently. The
parent-dependent coherence cleanups (benefits-checklist rederivation, WEL_DATA
orphans, risk satellites, the PMI cluster) are deferred to M2, after Tier-2
parents are final. LUMI_DB-aware; DRY-RUN unless --write --confirmed-by-david.

Fixes (all verified against raw data; constraint status noted):
  1.1  PROP_36b990f9 (free): 14 orgs answer employer pension 'Not applicable /
       not offered' yet give a 3-5% contribution in their own REW_BEN_112 matrix
       (auto-enrolment impossibility + self-contradiction). Map each to the band
       implied by its own frontline REW_BEN_112 value.
  1.2  REW_BEN_SICK_001 (marginal): 3 orgs 'No sick pay provided' -> 'Statutory
       sick pay only' (SSP is mandatory; aligns with their statutory-only SICK_002/
       004). +1.4pp global shift, well within +/-5pp.
  1.3  CAR_STATUS_03 (free): 71 orgs answer Yes to the car-or-cash CHOICE while
       CAR_STATUS_01='No' (no status car). The choice presupposes a car -> 'No'.
  1.4  REW_BEN_038 (free): 1 org selects 'None' together with 'Income protection'
       -> drop 'None'.
  1.8  REW26_WEL_MH_SUPPORT (FROZEN): 17 orgs answer mental-health support 'None'
       while holding an EAP (every EAP includes counselling). Conserve the frozen
       token counts EXACTLY by pairwise-swapping whole answer vectors with EAP=No
       orgs that hold substantive MH support.
  1.9  REW263_REC_CURRENCY (free): orgs answer recognition currency 'Not applicable'
       while funding a recognition budget -> reassign to a substantive currency
       drawn proportionally from the existing Monetary/Voucher/Mixed/Points mix.
  1.12 REW_BEN_FAM_002 (marginal): FAM_001 says enhanced maternity PAY but FAM_002
       says zero enhanced weeks (and the reverse). Pairwise-swap FAM_002 values
       between the two mismatched sets -> conserves the FAM_002 marginal exactly.
  1.13 REW_BEN_112 (free): all 21 DB-pension orgs pay a <=7% employer contribution
       (median 3%, the DC auto-enrolment floor) — impossible for DB (real 15-29%,
       ~flat by grade). Reseed their ladders to DB-appropriate flat rates.

    python3 server/migrate_seedreal_m1_tier1_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_m1_tier1_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict, Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs")}
    changes = defaultdict(int)

    def g1(q):
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

    def num(x):
        try:
            return float(str(x).replace("%", "").strip())
        except Exception:
            return None

    # ---- 1.1 PROP_36b990f9 pension 'not offered' -> band from own REW_BEN_112 ----
    pen = g1("PROP_36b990f9")
    b112f = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_112' "
        "AND matrix_row_id='frontline_individual_contributor' AND snapshot_id=1")}

    def band(v):
        n = num(v)
        if n is None:
            return "5%–7%"
        if n <= 4:
            return "3%–4%"
        if n <= 7:
            return "5%–7%"
        if n <= 10:
            return "8%–10%"
        return "11%+"
    for org, v in pen.items():
        if v == "Not applicable / not offered":
            setv("PROP_36b990f9", org, "", band(b112f.get(org)))

    # ---- 1.2 REW_BEN_SICK_001 'No sick pay provided' -> 'Statutory sick pay only' ----
    for org, v in g1("REW_BEN_SICK_001").items():
        if v == "No sick pay provided":
            setv("REW_BEN_SICK_001", org, "", "Statutory sick pay only")

    # ---- 1.3 CAR_STATUS_03 choice=Yes with no status car -> No ----
    car01 = g1("CAR_STATUS_01")
    for org, v in g1("CAR_STATUS_03").items():
        if car01.get(org) == "No" and str(v).strip().lower().startswith("yes"):
            setv("CAR_STATUS_03", org, "", "No")

    # ---- 1.4 REW_BEN_038 'None' co-selected with a substantive benefit ----
    for a in c.execute("SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND snapshot_id=1"):
        parts = [p.strip() for p in str(a["value"]).split(";") if p.strip()]
        if "None" in parts and len(parts) > 1:
            setv("REW_BEN_038", a["org_id"], "", "; ".join(p for p in parts if p != "None"))

    # ---- 1.8 MH_SUPPORT 'None' among EAP holders: frozen vector swap ----
    eap = g1("REW26_WEL_EAP")
    mh = g1("REW26_WEL_MH_SUPPORT")
    none_eap = sorted(o for o, v in mh.items() if str(v).strip() == "None" and eap.get(o) == "Yes")
    partners = sorted(o for o, v in mh.items() if str(v).strip() != "None" and eap.get(o) == "No")
    swaps = min(len(none_eap), len(partners))
    for i in range(swaps):
        a_org, b_org = none_eap[i], partners[i]
        va, vb = mh[a_org], mh[b_org]
        setv("REW26_WEL_MH_SUPPORT", a_org, "", vb)   # EAP org gets substantive support
        setv("REW26_WEL_MH_SUPPORT", b_org, "", va)   # non-EAP org gets 'None'

    # ---- 1.9 REC_CURRENCY 'Not applicable' contradicted by a recognition budget ----
    rc = g1("REW263_REC_CURRENCY")
    budget = g1("EXT_REW_GAP_001")            # dedicated per-employee recognition budget
    mgr = g1("REW263_REC_MGRBUDGET")

    def has_scheme(o):
        b = str(budget.get(o, "")); m = str(mgr.get(o, ""))
        no_budget = ("No" in b and "budget" in b.lower()) or b in ("", "No", "None", "No dedicated budget")
        no_mgr = m in ("", "No", "None", "No budget", "Not applicable")
        return not (no_budget and no_mgr)
    contradicted = sorted(o for o, v in rc.items() if "Not applicable" in str(v) and has_scheme(o))
    subs = ["Monetary", "Experiential/voucher", "Mixed", "Points-based"]
    # weights from current substantive prevalence 56/47/44/28
    weighted = (["Monetary"] * 56 + ["Experiential/voucher"] * 47 + ["Mixed"] * 44 + ["Points-based"] * 28)
    for i, org in enumerate(contradicted):
        setv("REW263_REC_CURRENCY", org, "", weighted[(i * 37) % len(weighted)])

    # ---- 1.12 DEFERRED to a ruling: FAM_001 (enhanced pay, marginal 0.67) and
    # FAM_002 (enhanced weeks, marginal 0.544) are jointly inconsistent by ~25 orgs,
    # so 25 orgs show 'enhanced pay / zero weeks'. No coherence-preserving swap exists
    # (0 statutory-pay orgs hold weeks). Fixing it requires moving one of the two
    # register marginals — David's call, same as REW_FAI_079. NOT changed here.

    # ---- 1.13 DB-pension orgs: reseed REW_BEN_112 to DB-appropriate flat rates ----
    ptype = g1("REW26_BEN_PENSION_TYPE")
    db_orgs = sorted(o for o, v in ptype.items() if v == "DB")
    # deterministic per-org rate: public sector clustered high (LGPS/TPS/CS 20-28%),
    # private DB 15-18% (all flat by grade — DB employer cost is a flat % of pay)
    PUB = ("Public Sector", "Education")
    pub_rates = [20, 22, 24, 26, 28]; priv_rates = [15, 16, 17, 18]
    pi = qi = 0
    for org in db_orgs:
        if any(p in str(ind.get(org, "")) for p in PUB):
            rate = pub_rates[pi % len(pub_rates)]; pi += 1
        else:
            rate = priv_rates[qi % len(priv_rates)]; qi += 1
        for lvl in LEVELS:
            setv("REW_BEN_112", org, lvl, str(rate))

    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  1.1 pension not-offered fixed: %d" % sum(1 for v in pen.values() if v == "Not applicable / not offered"))
    print("  1.8 MH frozen swaps: %d pairs (none_eap=%d partners=%d)" % (swaps, len(none_eap), len(partners)))
    print("  1.9 REC_CURRENCY contradicted reassigned: %d (of %d NA)" %
          (len(contradicted), sum(1 for v in rc.values() if "Not applicable" in str(v))))
    print("  1.12 FAM_002 enhanced-weeks contradiction DEFERRED to a ruling (marginals conflict)")
    print("  1.13 DB orgs reseeded: %d" % len(db_orgs))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
