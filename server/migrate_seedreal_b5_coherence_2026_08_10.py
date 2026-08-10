#!/usr/bin/env python3
"""Seed-realism B5 — coherence rederivation against final parents (2026-08-10).

The Tier-1 coherence cleanups that had to wait until the Tier-2 market batches (B2/B3)
made their parent metrics final. All target metrics are free. LUMI_DB-aware; DRY-RUN
unless --write --confirmed-by-david.

- REW_BEN_038 benefits checklist: 6 mirrored flags were seeded independently of their
  standalone parents (disagreeing 69-141 per flag). Recompute each flag deterministically
  from its parent (as IP/CI/dental already are):
    PMI            <- REW_BEN_100  != 'Not offered'
    Life assurance <- REW_BEN_045  != 'Not offered'
    EAP            <- REW26_WEL_EAP == 'Yes'            (frozen parent)
    Salsac car     <- REW264_BEN_EVSALSAC substantive
    Enh maternity  <- REW_BEN_FAM_001 enhanced-pay      (marginal parent, unchanged)
    Enh paternity  <- REW263_TIME_PATPAY enhanced
  Every other 038 token (income protection, staff discount, cycle-to-work, ...) is left
  exactly as-is.
- REW263_WEL_DATA: drop tracking picks for products the org doesn't hold — 'PMI claims'
  where REW_BEN_100='Not offered', 'EAP utilisation' where REW26_WEL_EAP!='Yes'. Empty
  list -> 'None'.
- Risk-benefit satellites, gated on the core cover actually held:
    REW264_HLT_RISKFLEXUP  'Yes both' needs life (045) AND IP (046!='No'); 'Yes one'
      needs at least one; else downgrade.
    REW264_HLT_GIPREHAB    substantive needs group IP (046 in Long-term only/Both);
      else 'Not applicable'.
    REW264_HLT_SPOUSELIFE  Employer-paid/Voluntary needs life assurance; else 'No'.
  Core metrics (045/046) are NOT modified.

    python3 server/migrate_seedreal_b5_coherence_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b5_coherence_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changes = defaultdict(int)

    def g1(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, new, row=""):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, q, row)).fetchone()
        if cur is None or (cur["value"] or "") == new:
            return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (new, org, q, row))

    # ---- repair orphaned PMI detail (B2 gap): orgs set to 100='Not offered' that
    # nonetheless hold real PMI detail (components/premium/excess) are PMI-havers with a
    # mis-seeded all-No 139 matrix. Give them senior-only eligibility so 100/044/139/038
    # and the PMI child pairs all cohere (rather than discard the detail). ----
    b100_pre = g1("REW_BEN_100")
    comp = g1("REW265_BEN_PMICOMP"); exc = g1("REW263_BEN_PMIEXCESS")
    prem = {a["org_id"] for a in c.execute(
        "SELECT DISTINCT org_id FROM answers WHERE question_id='3faf1f0c-f753-497f-a395-384bba38c5e3' "
        "AND value!='' AND snapshot_id=1")}
    SENIOR = {"board_executive", "director", "head_of", "senior_manager"}
    ALL_LVL = ["board_executive", "director", "head_of", "senior_manager", "manager",
               "supervisor_team_leader", "frontline_individual_contributor"]

    def has_pmi_detail(o):
        return (comp.get(o) not in (None, "", "Not applicable", "None of these — core cover only")) \
            or (o in prem) or (exc.get(o) not in (None, "", "Not applicable"))
    for org, v in b100_pre.items():
        if "Not offered" in str(v) and has_pmi_detail(org):
            for lvl in ALL_LVL:
                setv("REW_BEN_139", org, "Yes" if lvl in SENIOR else "No", row=lvl)
            setv("REW_BEN_100", org, "10–24%")
            setv("REW_BEN_044", org, "Grade/level restricted")

    # ---- REW_BEN_038 checklist rederivation (6 flags) ----
    b100 = g1("REW_BEN_100"); b045 = g1("REW_BEN_045"); eap = g1("REW26_WEL_EAP")
    ev = g1("REW264_BEN_EVSALSAC"); fam = g1("REW_BEN_FAM_001"); pat = g1("REW263_TIME_PATPAY")
    FLAGS = {
        "Private Medical Insurance (PMI)": lambda o: "Not offered" not in str(b100.get(o, "")),
        "Life assurance": lambda o: "Not offered" not in str(b045.get(o, "")),
        "Employee Assistance Programme (EAP)": lambda o: eap.get(o) == "Yes",
        "Salary sacrifice car scheme": lambda o: ev.get(o) not in (None, "", "Not applicable"),
        "Enhanced maternity pay": lambda o: "nhanced pay" in str(fam.get(o, "")) or "Combination" in str(fam.get(o, "")),
        "Enhanced paternity pay": lambda o: "nhanced" in str(pat.get(o, "")),
    }
    b038 = g1("REW_BEN_038")
    for org, val in b038.items():
        parts = [p.strip() for p in str(val).split(";") if p.strip()]
        s = set(parts)
        for tok, pred in FLAGS.items():
            if pred(org):
                s.add(tok)
            else:
                s.discard(tok)
        if s != set(parts):
            # preserve original order for untouched tokens, append any newly-added flags
            new_parts = [p for p in parts if p in s] + [t for t in FLAGS if t in s and t not in parts]
            setv("REW_BEN_038", org, "; ".join(new_parts) if new_parts else "None")

    # ---- REW263_WEL_DATA orphan tracking ----
    weld = g1("REW263_WEL_DATA")
    for org, val in weld.items():
        parts = [p.strip() for p in str(val).split(";") if p.strip()]
        kept = []
        for p in parts:
            if p == "PMI claims" and "Not offered" in str(b100.get(org, "")):
                continue
            if p == "EAP utilisation" and eap.get(org) != "Yes":
                continue
            kept.append(p)
        kept = [p for p in kept if p != "None"]
        new = ";".join(kept) if kept else "None"
        if new != str(val):
            setv("REW263_WEL_DATA", org, new)

    # ---- risk-benefit satellites ----
    b046 = g1("REW_BEN_046")
    has_la = lambda o: "Not offered" not in str(b045.get(o, ""))
    has_ip_any = lambda o: b046.get(o) in ("Short-term only", "Long-term only", "Both")
    has_gip = lambda o: b046.get(o) in ("Long-term only", "Both")

    for org, v in g1("REW264_HLT_RISKFLEXUP").items():
        if v == "Yes both" and not (has_la(org) and has_ip_any(org)):
            setv("REW264_HLT_RISKFLEXUP", org, "Yes one" if (has_la(org) or has_ip_any(org)) else "No")
        elif v == "Yes one" and not (has_la(org) or has_ip_any(org)):
            setv("REW264_HLT_RISKFLEXUP", org, "No")
    for org, v in g1("REW264_HLT_GIPREHAB").items():
        if v in ("Actively used", "Rarely used", "Unaware of services") and not has_gip(org):
            setv("REW264_HLT_GIPREHAB", org, "Not applicable")
    for org, v in g1("REW264_HLT_SPOUSELIFE").items():
        if v in ("Employer-paid", "Voluntary") and not has_la(org):
            setv("REW264_HLT_SPOUSELIFE", org, "No")

    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
