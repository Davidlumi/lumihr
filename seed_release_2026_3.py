#!/usr/bin/env python3
"""
Firewall-compliant synthetic seed generation for the 42 release-2026.3 questions.

Identical discipline to seed_release_2026_2.py (DECISIONS.md: REW_INC_072,
pay-frequency, allowances-pensionable):
- DOCUMENTED, David-signed baselines in the CONSTANTS block (PROPOSED here;
  grounded in CIPD Reward Survey 2026, REBA Health & Wellbeing 2025/26, Howden
  Benefits Design 2025, and the ERA 2025 implementation timeline).
- Conditioned on FIRMOGRAPHICS only. No per-org hand-tuning, no demo special-case.
- Per-org reproducible seed: f"{qid}|{SEED_DATE}|{org_id}".
- ORG-BLIND, WHOLE-METRIC: same rule for every org; all participants at once.
- offer_na routes inapplicable orgs to "Not applicable" (answered, excluded
  from prevalence) rather than a misleading "No".
- DOUBLE-GUARDED write: requires --write AND --confirmed-by-david.

PROPOSED baselines: every distribution below is a starting estimate for David
to confirm or adjust. Nothing writes without --confirmed-by-david.
"""
import hashlib, random, argparse, json, copy

SEED_DATE = "2026-06-19"
import os as _os
_PMAP={}
_pp=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else ".","seed_presence_map_2026_3.json")
if _os.path.exists(_pp):
    try: _PMAP=json.load(open(_pp))
    except Exception: _PMAP={}

BASELINES = {
 # --- GOVERNANCE ---
 "REW263_GOV_UKPAYTRANS": {"type":"single_select", "dist":{"No transparency":0.34, "Internal ranges only":0.33, "Ranges on adverts":0.22, "Published transparency policy":0.11}, "tilt":{"hr_mature":{"Published transparency policy":0.08, "No transparency":-0.1}, "public_sector":{"Ranges on adverts":0.1, "No transparency":-0.1}}},
 "REW263_GOV_MENOPLAN": {"type":"single_select", "dist":{"No plans":0.46, "Considering":0.31, "Planned this year":0.15, "Already published":0.08}, "tilt":{"hr_mature":{"Already published":0.07, "No plans":-0.12}, "size_large":{"Planned this year":0.06, "No plans":-0.08}}},
 "REW263_GOV_ETHDISREADY": {"type":"single_select", "na_rule":"size_small","dist":{"Not started":0.4, "Reviewing data readiness":0.31, "Analysing gaps":0.2, "Reporting-ready":0.09}, "tilt":{"hr_mature":{"Reporting-ready":0.07, "Not started":-0.12}, "size_large":{"Analysing gaps":0.06, "Not started":-0.08}}},
 "REW263_GOV_UMBRELLA": {"type":"single_select", "na_rule":"no_contingent","dist":{"No checks":0.44, "Ad hoc":0.33, "Documented checks":0.16, "Full parity framework":0.07}, "tilt":{"hr_mature":{"Documented checks":0.06, "No checks":-0.1}, "high_frontline":{"Ad hoc":0.05, "No checks":-0.05}}},
 "REW263_GOV_FIREREHIRE": {"type":"single_select", "dist":{"No policy":0.38, "Informal practice":0.34, "Documented policy":0.2, "Policy + consultation route":0.08}, "tilt":{"hr_mature":{"Documented policy":0.07, "No policy":-0.1}, "unionised":{"Policy + consultation route":0.08, "No policy":-0.08}}},
 "REW263_GOV_REWTEAM": {"type":"single_select", "dist":{"No dedicated reward resource":0.3, "Shared HR/reward role":0.34, "1 dedicated FTE":0.18, "2-4 dedicated FTE":0.13, "5+ dedicated team":0.05}, "tilt":{"size_large":{"5+ dedicated team":0.1, "2-4 dedicated FTE":0.1, "No dedicated reward resource":-0.18}, "size_small":{"No dedicated reward resource":0.15, "Shared HR/reward role":0.05}}},
 "REW263_GOV_SIGNOFF": {"type":"single_select", "dist":{"HRD":0.26, "CEO/MD":0.24, "Finance/CFO":0.14, "Remuneration Committee":0.18, "Joint HR + Finance":0.18}, "tilt":{"size_large":{"Remuneration Committee":0.14, "CEO/MD":-0.12}, "size_small":{"CEO/MD":0.12, "Remuneration Committee":-0.1}}},
 "REW263_GOV_BENOBJ": {"type":"single_select", "dist":{"No objectives":0.21, "Objectives not reviewed":0.33, "Objectives reviewed annually":0.31, "Objectives linked to productivity":0.15}, "tilt":{"hr_mature":{"Objectives linked to productivity":0.08, "No objectives":-0.1}, "size_large":{"Objectives reviewed annually":0.06, "No objectives":-0.06}}},
 "REW263_GOV_FLEXALLOW": {"type":"single_select", "dist":{"No":0.58, "Limited choice":0.29, "Personalised allowance":0.13}, "tilt":{"hr_mature":{"Personalised allowance":0.07, "No":-0.1}, "size_large":{"Limited choice":0.06, "No":-0.06}}},
 # --- PAY ---
 "REW263_PAY_COMPARATIO": {"type":"single_select", "na_rule":"no_ranges","dist":{"No formal target":0.3, "Below midpoint":0.14, "At midpoint (100%)":0.42, "Above midpoint":0.14}, "tilt":{"hr_mature":{"At midpoint (100%)":0.08, "No formal target":-0.12}}},
 "REW263_PAY_MERITMATRIX": {"type":"single_select", "dist":{"No":0.4, "Performance only":0.39, "Full merit matrix":0.21}, "tilt":{"hr_mature":{"Full merit matrix":0.1, "No":-0.12}, "size_large":{"Full merit matrix":0.07, "No":-0.07}}},
 "REW263_PAY_SHIFTRIGHTS": {"type":"single_select", "na_rule":"low_shift","dist":{"Neither":0.34, "Notice only":0.28, "Cancellation pay only":0.16, "Both":0.22}, "tilt":{"hr_mature":{"Both":0.08, "Neither":-0.1}, "high_shift":{"Both":0.06, "Neither":-0.06}}},
 "REW263_PAY_GUARHRSAVG": {"type":"single_select", "na_rule":"low_frontline","dist":{"No":0.46, "On request":0.34, "Proactively after reference period":0.2}, "tilt":{"high_frontline":{"Proactively after reference period":0.08, "No":-0.1}, "hr_mature":{"Proactively after reference period":0.05, "No":-0.05}}},
 "REW263_PAY_SSPALIGN": {"type":"single_select", "dist":{"Not reviewed":0.28, "Reviewing":0.33, "Aligned":0.29, "Aligned + enhanced OSP":0.1}, "tilt":{"hr_mature":{"Aligned":0.08, "Not reviewed":-0.1}, "size_large":{"Aligned":0.06, "Not reviewed":-0.06}}},
 # --- BENEFITS ---
 # PMIMH/PMIEXCESS carry an explicit lean->generous `order` so they anchor to the latent
 # spine like other benefits (option_order() can't infer their semantic generosity axis).
 # The seeding path reads `order` if present, else falls back to reseed_engine.option_order().
 "REW263_BEN_PMIMH": {"type":"single_select", "na_rule":"no_pmi","dist":{"No PMI / neither":0.22, "Mental health only":0.2, "Digital GP only":0.16, "Both":0.42}, "order":["No PMI / neither","Mental health only","Digital GP only","Both"], "tilt":{"hr_mature":{"Both":0.08, "No PMI / neither":-0.1}}},
 "REW263_BEN_PMIEXCESS": {"type":"single_select", "na_rule":"no_pmi","dist":{"No excess":0.4, "Excess per claim":0.24, "Excess per year":0.22, "Employee co-pays premium":0.14}, "order":["Employee co-pays premium","Excess per year","Excess per claim","No excess"], "tilt":{"size_large":{"No excess":0.06, "Employee co-pays premium":-0.05}}},
 "REW263_BEN_CICOVER": {"type":"single_select", "na_rule":"no_ci","dist":{"Not offered":0.46, "Fixed lump sum":0.22, "1x salary":0.2, "2x+ salary":0.12}, "tilt":{"hr_mature":{"2x+ salary":0.06, "Not offered":-0.1}}},
 "REW263_BEN_DENTAL": {"type":"single_select", "na_rule":"no_dental","dist":{"Not offered":0.4, "Voluntary (employee-funded)":0.34, "Employer-paid":0.26}, "tilt":{"hr_mature":{"Employer-paid":0.07, "Not offered":-0.1}}},
 "REW263_BEN_NEURO": {"type":"single_select", "dist":{"No":0.42, "Informal adjustments":0.34, "Formal process":0.17, "Formal process + dedicated support":0.07}, "tilt":{"hr_mature":{"Formal process":0.07, "No":-0.1}, "size_large":{"Formal process":0.05, "No":-0.05}}},
 "REW263_BEN_PENBASIS": {"type":"single_select", "dist":{"Qualifying earnings (band)":0.44, "Basic pay":0.38, "Total/full pay":0.18}, "tilt":{"hr_mature":{"Total/full pay":0.07, "Qualifying earnings (band)":-0.1}, "size_large":{"Basic pay":0.05}}},
 # --- INCENTIVES ---
 "REW263_INC_DEFERRAL": {"type":"single_select", "na_rule":"no_deferral","dist":{"No deferral":0.55, "1yr cash":0.16, "Multi-year cash":0.13, "Shares/equity deferral":0.16}, "tilt":{"size_large":{"Shares/equity deferral":0.1, "No deferral":-0.12}}},
 "REW263_INC_POOLFUND": {"type":"single_select", "na_rule":"no_bonus","dist":{"Top-down (profit share)":0.34, "Bottom-up (target-based)":0.4, "Hybrid":0.26}, "tilt":{"size_large":{"Hybrid":0.06, "Top-down (profit share)":-0.05}}},
 # --- RECOGNITION ---
 "REW263_REC_PEER": {"type":"single_select", "dist":{"No":0.5, "Informal peer recognition":0.31, "Points/platform-based":0.19}, "tilt":{"hr_mature":{"Points/platform-based":0.08, "No":-0.1}, "size_large":{"Points/platform-based":0.06, "No":-0.06}}},
 "REW263_REC_CURRENCY": {"type":"single_select", "na_rule":"no_recognition","dist":{"Monetary":0.32, "Experiential/voucher":0.27, "Points-based":0.16, "Mixed":0.25}, "tilt":{"size_large":{"Points-based":0.06, "Monetary":-0.05}}},
 "REW263_REC_MGRBUDGET": {"type":"single_select", "dist":{"No":0.48, "Central budget only":0.32, "Devolved manager budget":0.2}, "tilt":{"hr_mature":{"Devolved manager budget":0.07, "No":-0.1}}},
 "REW263_REC_IMPACT": {"type":"yes_no", "dist":{"Yes":0.22, "No":0.78}, "tilt":{"hr_mature":{"Yes":0.1, "No":-0.1}, "size_large":{"Yes":0.06, "No":-0.06}}},
 # --- WELLBEING ---
 "REW263_WEL_DATA": {"type":"multi_select", "p_has_plan":0.72, "char_probs":{"Absence rates":0.62, "PMI claims":0.35, "Wellbeing scores":0.23, "EAP utilisation":0.45}, "tilt":{"hr_mature":0.1, "size_large":0.08}},
 "REW263_WEL_OH": {"type":"single_select", "dist":{"No OH service":0.3, "OH without SLA":0.34, "OH SLA over 2 weeks":0.22, "OH SLA within 2 weeks":0.14}, "tilt":{"hr_mature":{"OH SLA within 2 weeks":0.07, "No OH service":-0.1}, "size_large":{"OH without SLA":0.05, "No OH service":-0.08}}},
 "REW263_WEL_MGRTRAIN": {"type":"single_select", "dist":{"None":0.34, "Under 25%":0.27, "25-75%":0.25, "Over 75%":0.14}, "tilt":{"hr_mature":{"Over 75%":0.08, "None":-0.1}, "size_large":{"25-75%":0.06, "None":-0.06}}},
 "REW263_WEL_FINWELL": {"type":"single_select", "dist":{"No":0.42, "Ad hoc provision":0.39, "Documented strategy":0.19}, "tilt":{"hr_mature":{"Documented strategy":0.08, "No":-0.1}}},
 # --- TIME OFF ---
 "REW263_TIME_IVF": {"type":"single_select", "na_rule":"no_fertility","dist":{"None":0.6, "1 cycle / capped":0.22, "2-3 cycles":0.13, "Unlimited/uncapped":0.05}, "tilt":{"hr_mature":{"2-3 cycles":0.06, "None":-0.1}, "tech_sector":{"2-3 cycles":0.06, "None":-0.08}}},
 "REW263_TIME_FERTLEAVE": {"type":"single_select", "na_rule":"no_fertility","dist":{"No":0.58, "Unpaid/flexible":0.27, "Paid dedicated leave":0.15}, "tilt":{"hr_mature":{"Paid dedicated leave":0.07, "No":-0.1}}},
 "REW263_TIME_NEONATAL": {"type":"single_select", "dist":{"Statutory only":0.66, "Enhanced pay":0.24, "Enhanced pay + leave":0.1}, "tilt":{"hr_mature":{"Enhanced pay":0.06, "Statutory only":-0.1}}},
 "REW263_TIME_PREGLOSS": {"type":"single_select", "dist":{"No specific provision":0.5, "Discretionary":0.31, "Paid policy":0.19}, "tilt":{"hr_mature":{"Paid policy":0.08, "No specific provision":-0.1}}},
 "REW263_TIME_PATPAY": {"type":"single_select", "dist":{"Statutory only":0.52, "1-2 weeks enhanced":0.24, "3-6 weeks enhanced":0.16, "6+ weeks enhanced":0.08}, "tilt":{"hr_mature":{"3-6 weeks enhanced":0.07, "Statutory only":-0.12}, "tech_sector":{"6+ weeks enhanced":0.06, "Statutory only":-0.08}}},
 "REW263_TIME_DAYONELEAVE": {"type":"yes_no", "dist":{"Yes":0.61, "No":0.39}, "tilt":{"hr_mature":{"Yes":0.1, "No":-0.1}, "size_large":{"Yes":0.08, "No":-0.08}}},
 "REW263_TIME_HOLRECORDS": {"type":"yes_no", "dist":{"Yes":0.74, "No":0.26}, "tilt":{"hr_mature":{"Yes":0.1, "No":-0.1}, "size_large":{"Yes":0.08, "No":-0.08}}},
 "REW263_TIME_CARERPAID": {"type":"single_select", "dist":{"Statutory unpaid only":0.56, "Some paid days":0.3, "Fully paid carer's leave":0.14}, "tilt":{"hr_mature":{"Some paid days":0.07, "Statutory unpaid only":-0.1}}},
}

def org_rng(qid, org_id):
    h=hashlib.sha256(f"{qid}|{SEED_DATE}|{org_id}".encode()).hexdigest()
    return random.Random(int(h[:16],16))

def firmo_flags(org):
    """Derive tilt flags from registry firmographics. Field names match
    seeded_orgs.json (Title_Case_%); see DECISIONS.md sim_feature_space."""
    f=set()
    band=str(org.get("FTE_Band",""))
    mid=org.get("fte_band_midpoint")
    if mid is None:
        mid={"1-49":25,"50-249":150,"250-999":600,"1000-4999":2500,"5000+":8000}.get(band,500)
    if mid>=2500: f.add("size_large")
    if mid<250: f.add("size_small")
    if str(org.get("HR_Maturity","")) in ("Advanced","Leading","High"): f.add("hr_mature")
    if str(org.get("Ownership_Type","")) in ("Public sector","Government"): f.add("public_sector")
    fl=org.get("Workforce_Frontline_%") or org.get("frontline_pct") or 0
    sh=org.get("Workforce_Shift_%") or org.get("shift_pct") or 0
    un=org.get("Workforce_Unionised_%") or 0
    try: fl=float(fl); sh=float(sh); un=float(un)
    except: fl=sh=un=0
    if fl>=40: f.add("high_frontline")
    if fl<15: f.add("low_frontline")
    if sh>=30: f.add("high_shift")
    if sh<10: f.add("low_shift")
    if un>=25: f.add("unionised")
    if str(org.get("Industry","")) in ("Technology","Telecoms, Media & Technology","Financial Services"):
        f.add("tech_sector")
    return f

# offer_na predicates. Some are firmographic; others are unknowable from
# firmographics alone (no_pmi, no_ci, no_dental, no_deferral, no_bonus,
# no_fertility, no_recognition, no_contingent, no_ranges) and are routed via a
# documented prior probability that the benefit/scheme is absent.
NA_PRIOR = {  # DB-grounded from live lumi.db presence data (2026-06-19)
 "no_pmi":0.57,        # PMI present 42.9% in WEL_BMAP_PHY_HEALTH_001 (n=189)
 "no_dental":0.59,     # dental present 41.3% (n=189)
 "no_fertility":0.74,  # fertility present 26.4% in WEL_BMAP_WLB_FAMILY_001 (n=174)
 "no_ci":0.55,         # critical illness: no live presence flag; estimate retained
 "no_deferral":0.60,   # estimate (no live anchor)
 "no_bonus":0.25,      # estimate (no live anchor)
 "no_recognition":0.20,# estimate (no live anchor)
 "no_contingent":0.35, # estimate (no live anchor)
 "no_ranges":0.30,     # estimate (no live anchor)
}

def na_applies(rule, flags, rng, org_id=None):
    if rule=="low_frontline": return "low_frontline" in flags
    if rule=="low_shift":     return "low_shift" in flags
    if rule=="size_small":    return "size_small" in flags
    # Live-presence routing (DB-grounded): org ABSENT on parent presence Q -> N/A.
    if rule in _PMAP and org_id is not None and org_id in _PMAP[rule]:
        return not _PMAP[rule][org_id]
    if rule in NA_PRIOR:      return rng.random() < NA_PRIOR[rule]
    return False

def apply_tilt(dist, tilt, flags):
    d=dict(dist)
    for flag,adj in (tilt or {}).items():
        if flag in flags and isinstance(adj,dict):
            for opt,delta in adj.items(): d[opt]=max(0.0,d.get(opt,0)+delta)
    s=sum(d.values()) or 1.0
    return {k:v/s for k,v in d.items()}

def pick(rng, dist):
    r=rng.random(); cum=0.0
    for opt,p in dist.items():
        cum+=p
        if r<=cum: return opt
    return list(dist)[-1]

def generate(orgs, write=False):
    out=[]
    for qid,spec in BASELINES.items():
        for org in orgs:
            oid=org.get("Org_ID") or org.get("org_id"); flags=firmo_flags(org); rng=org_rng(qid,oid)
            if spec.get("na_rule") and na_applies(spec["na_rule"], flags, rng, oid):
                out.append((qid,oid,"Not applicable")); continue
            if spec["type"]=="multi_select":
                base=spec["p_has_plan"]
                for flag,delta in spec.get("tilt",{}).items():
                    if flag in flags and isinstance(delta,(int,float)): base+=delta
                base=min(0.97,max(0.02,base))
                if rng.random()>base:
                    out.append((qid,oid,"None")); continue
                chosen=[c for c,p in spec["char_probs"].items() if rng.random()<=p]
                out.append((qid,oid,";".join(chosen) if chosen else "None"))
            else:
                d=apply_tilt(spec["dist"], spec.get("tilt"), flags)
                out.append((qid,oid,pick(rng,d)))
    return out

def realised(rows, qid):
    from collections import Counter
    vals=[v for q,o,v in rows if q==qid and v!="Not applicable"]
    n=len(vals) or 1; c=Counter(vals)
    return {k:v/n for k,v in c.items()}

def calibrate(orgs, key, target, tol=0.03, max_iter=12):
    """Scale tilt magnitudes down until realised dist lands within tol of the
    signed baseline mean. Direction/texture preserved; only spread strength tuned
    (the pay-frequency calibration pattern)."""
    spec=BASELINES[key]; scale=1.0; orig=copy.deepcopy(spec.get("tilt"))
    if not isinstance(orig,dict) or spec["type"]=="multi_select": return 1.0
    for _ in range(max_iter):
        spec["tilt"]={f:({o:d*scale for o,d in adj.items()} if isinstance(adj,dict) else adj*scale)
                      for f,adj in orig.items()}
        r=realised(generate(orgs), key)
        worst=max((abs(r.get(o,0)-target.get(o,0)) for o in target), default=0)
        if worst<=tol: break
        scale*=0.7
    return scale

def summarise(rows):
    from collections import Counter
    byq={}
    for qid,oid,val in rows: byq.setdefault(qid,[]).append(val)
    for qid,vals in byq.items():
        n=len(vals); na=sum(1 for v in vals if v=="Not applicable"); applic=n-na or 1
        c=Counter(v for v in vals if v!="Not applicable")
        print(f"\n{qid}  (n={n}, applicable={applic}, N/A={na})")
        for opt,k in c.most_common(): print(f"    {opt:46} {k/applic*100:5.1f}%")

SIGNED_TARGETS = {
 "REW263_GOV_UKPAYTRANS":{"No transparency":0.34, "Internal ranges only":0.33, "Ranges on adverts":0.22, "Published transparency policy":0.11},
 "REW263_GOV_MENOPLAN":{"No plans":0.46, "Considering":0.31, "Planned this year":0.15, "Already published":0.08},
 "REW263_GOV_ETHDISREADY":{"Not started":0.4, "Reviewing data readiness":0.31, "Analysing gaps":0.2, "Reporting-ready":0.09},
 "REW263_GOV_UMBRELLA":{"No checks":0.44, "Ad hoc":0.33, "Documented checks":0.16, "Full parity framework":0.07},
 "REW263_GOV_FIREREHIRE":{"No policy":0.38, "Informal practice":0.34, "Documented policy":0.2, "Policy + consultation route":0.08},
 "REW263_GOV_REWTEAM":{"No dedicated reward resource":0.3, "Shared HR/reward role":0.34, "1 dedicated FTE":0.18, "2-4 dedicated FTE":0.13, "5+ dedicated team":0.05},
 "REW263_GOV_SIGNOFF":{"HRD":0.26, "CEO/MD":0.24, "Finance/CFO":0.14, "Remuneration Committee":0.18, "Joint HR + Finance":0.18},
 "REW263_GOV_BENOBJ":{"No objectives":0.21, "Objectives not reviewed":0.33, "Objectives reviewed annually":0.31, "Objectives linked to productivity":0.15},
 "REW263_GOV_FLEXALLOW":{"No":0.58, "Limited choice":0.29, "Personalised allowance":0.13},
 "REW263_PAY_COMPARATIO":{"No formal target":0.3, "Below midpoint":0.14, "At midpoint (100%)":0.42, "Above midpoint":0.14},
 "REW263_PAY_MERITMATRIX":{"No":0.4, "Performance only":0.39, "Full merit matrix":0.21},
 "REW263_PAY_SHIFTRIGHTS":{"Neither":0.34, "Notice only":0.28, "Cancellation pay only":0.16, "Both":0.22},
 "REW263_PAY_GUARHRSAVG":{"No":0.46, "On request":0.34, "Proactively after reference period":0.2},
 "REW263_PAY_SSPALIGN":{"Not reviewed":0.28, "Reviewing":0.33, "Aligned":0.29, "Aligned + enhanced OSP":0.1},
 "REW263_BEN_PMIMH":{"No PMI / neither":0.22, "Mental health only":0.2, "Digital GP only":0.16, "Both":0.42},
 "REW263_BEN_PMIEXCESS":{"No excess":0.4, "Excess per claim":0.24, "Excess per year":0.22, "Employee co-pays premium":0.14},
 "REW263_BEN_CICOVER":{"Not offered":0.46, "Fixed lump sum":0.22, "1x salary":0.2, "2x+ salary":0.12},
 "REW263_BEN_DENTAL":{"Not offered":0.4, "Voluntary (employee-funded)":0.34, "Employer-paid":0.26},
 "REW263_BEN_NEURO":{"No":0.42, "Informal adjustments":0.34, "Formal process":0.17, "Formal process + dedicated support":0.07},
 "REW263_BEN_PENBASIS":{"Qualifying earnings (band)":0.44, "Basic pay":0.38, "Total/full pay":0.18},
 "REW263_INC_DEFERRAL":{"No deferral":0.55, "1yr cash":0.16, "Multi-year cash":0.13, "Shares/equity deferral":0.16},
 "REW263_INC_POOLFUND":{"Top-down (profit share)":0.34, "Bottom-up (target-based)":0.4, "Hybrid":0.26},
 "REW263_REC_PEER":{"No":0.5, "Informal peer recognition":0.31, "Points/platform-based":0.19},
 "REW263_REC_CURRENCY":{"Monetary":0.32, "Experiential/voucher":0.27, "Points-based":0.16, "Mixed":0.25},
 "REW263_REC_MGRBUDGET":{"No":0.48, "Central budget only":0.32, "Devolved manager budget":0.2},
 "REW263_REC_IMPACT":{"Yes":0.22, "No":0.78},
 "REW263_WEL_OH":{"No OH service":0.3, "OH without SLA":0.34, "OH SLA over 2 weeks":0.22, "OH SLA within 2 weeks":0.14},
 "REW263_WEL_MGRTRAIN":{"None":0.34, "Under 25%":0.27, "25-75%":0.25, "Over 75%":0.14},
 "REW263_WEL_FINWELL":{"No":0.42, "Ad hoc provision":0.39, "Documented strategy":0.19},
 "REW263_TIME_IVF":{"None":0.6, "1 cycle / capped":0.22, "2-3 cycles":0.13, "Unlimited/uncapped":0.05},
 "REW263_TIME_FERTLEAVE":{"No":0.58, "Unpaid/flexible":0.27, "Paid dedicated leave":0.15},
 "REW263_TIME_NEONATAL":{"Statutory only":0.66, "Enhanced pay":0.24, "Enhanced pay + leave":0.1},
 "REW263_TIME_PREGLOSS":{"No specific provision":0.5, "Discretionary":0.31, "Paid policy":0.19},
 "REW263_TIME_PATPAY":{"Statutory only":0.52, "1-2 weeks enhanced":0.24, "3-6 weeks enhanced":0.16, "6+ weeks enhanced":0.08},
 "REW263_TIME_DAYONELEAVE":{"Yes":0.61, "No":0.39},
 "REW263_TIME_HOLRECORDS":{"Yes":0.74, "No":0.26},
 "REW263_TIME_CARERPAID":{"Statutory unpaid only":0.56, "Some paid days":0.3, "Fully paid carer's leave":0.14},
}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--orgs", default="seeded_orgs.json")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a=ap.parse_args()
    try: orgs=json.load(open(a.orgs))
    except Exception:
        orgs=[{"Org_ID":f"org{i:03d}","FTE_Band":["50-249","250-999","1000-4999","5000+","250-999"][i%5],
               "HR_Maturity":["Basic","Developing","Advanced","Leading","Developing"][i%5],
               "Ownership_Type":["Private","Public sector","PE-backed","Private","Founder-led"][i%5],
               "Workforce_Frontline_%":[5,20,45,60,10][i%5],"Workforce_Shift_%":[2,15,35,50,5][i%5],
               "Workforce_Unionised_%":[0,10,30,5,0][i%5],
               "Industry":["Technology","Retail & Consumer Goods","Manufacturing","Healthcare","Financial Services"][i%5]}
              for i in range(210)]
        print(f"(no {a.orgs} found — using 210-org stub)")
    for qid,target in SIGNED_TARGETS.items():
        print(f"calibrated {qid}: tilt scale {calibrate(orgs,qid,target):.2f}")
    rows=generate(orgs); summarise(rows)
    if a.write and a.__dict__["confirmed_by_david"]:
        json.dump([{"question_id":q,"org_id":o,"value":v} for q,o,v in rows],
                  open("release_2026_3_seed.json","w"), indent=0)
        print(f"\nWROTE release_2026_3_seed.json ({len(rows)} responses)")
    else:
        print("\nDRY RUN — no write. Re-run with --write --confirmed-by-david to emit the seed JSON.")
