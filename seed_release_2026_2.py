#!/usr/bin/env python3
"""
Firewall-compliant synthetic seed generation for the 12 release-2026.2 questions.

Discipline (matches DECISIONS.md: REW_INC_072, pay-frequency, allowances-pensionable):
- DOCUMENTED baselines (David-signed, grounded in 2026 research) in the CONSTANTS block.
- Conditioned on FIRMOGRAPHICS only (no per-org hand-tuning, no demo-org special-casing).
- SEEDED per org -> reproducible: seed = f"{qid}|{SEED_DATE}|{org_id}".
- ORG-BLIND: the same rule runs for every org; no org is nudged toward a standing.
- WHOLE-METRIC: all participating orgs generated at once, never selectively.
- offer_na questions route inapplicable orgs to "Not applicable" (counts as answered,
  excluded from prevalence) rather than forcing a misleading "No".
- DOUBLE-GUARDED write: requires --write AND --confirmed-by-david.

This script PROPOSES values to insert into the engagement's response store for the
2026.2 questions. It does not touch any existing metric. Review the dry-run first.
"""
import hashlib, random, argparse, json

SEED_DATE = "2026-06-12"   # part of the per-org seed; fixed for reproducibility

# ------------------------------------------------------------------ #
# CONSTANTS — David-signed baselines (edit here; direction is settled) #
# Each entry: question id, type, baseline distribution (option -> share),
# na_rule (None = always applies; or a predicate name for offer_na),
# and tilt rules (firmographic -> option-share adjustments).            #
# ------------------------------------------------------------------ #
BASELINES = {
 # --- GOVERNANCE ---
 "REW262_GOV_ACTIONPLAN": {  # multi_select; 'None' OR a subset of characteristics
   "type":"multi_select",
   # P(has any plan) then which characteristics; 'None' is the no-plan state
   "p_has_plan":0.30,
   "char_probs":{"Gender":0.93,"Menopause":0.60,"Ethnicity":0.40,"Disability":0.30},  # conditional on having a plan
   "tilt":{"size_large":+0.18,"size_small":-0.12,"hr_mature":+0.15,"public_sector":+0.12},  # adjust p_has_plan
 },
 "REW262_GOV_EQUALVALUE": {
   "type":"single_select",
   "dist":{"No":0.35,"In progress":0.38,"Partially":0.19,"Fully":0.08},
   "tilt":{"hr_mature":{"Fully":+0.06,"Partially":+0.06,"No":-0.10},
           "size_large":{"In progress":+0.06,"No":-0.08}},
 },
 "REW262_GOV_SALHISTORY": {
   "type":"yes_no","dist":{"Yes":0.27,"No":0.73},   # nudged 0.32->0.27 per S4: salary-history ban is proposed, low awareness, few acted; tab6 evidenced
   "tilt":{"hr_mature":{"Yes":+0.12,"No":-0.12},"size_large":{"Yes":+0.06,"No":-0.06}},
 },
 "REW262_GOV_PAYINADVERTS": {
   "type":"single_select","dist":{"Never":0.45,"Some roles":0.38,"All roles":0.17},
   "tilt":{"hr_mature":{"All roles":+0.08,"Never":-0.10},"public_sector":{"All roles":+0.10,"Never":-0.12}},
 },
 "REW262_GOV_EQUALPAYAUDIT": {
   "type":"single_select","dist":{"No":0.30,"Ad hoc":0.38,"Annually":0.26,"More than annually":0.06},
   "tilt":{"hr_mature":{"Annually":+0.10,"No":-0.12},"size_large":{"Annually":+0.06,"No":-0.06}},
 },
 "REW262_GOV_AIINPAY": {  # FLAGGED weak baseline — David estimate
   "type":"single_select",
   "dist":{"No AI use":0.62,"AI with no formal oversight":0.14,
           "AI as decision-support with human oversight":0.19,
           "AI with human oversight and bias auditing":0.05},
   "tilt":{"hr_mature":{"AI as decision-support with human oversight":+0.06,"No AI use":-0.08},
           "size_large":{"AI as decision-support with human oversight":+0.05,"No AI use":-0.07},
           "tech_sector":{"AI as decision-support with human oversight":+0.08,"No AI use":-0.10}},
 },
 # --- PAY ---
 "REW262_PAY_GUARANTEEDHRS": {  # offer_na: salaried-only orgs -> Not applicable
   "type":"single_select","na_rule":"low_frontline",
   "dist":{"No":0.48,"On request only":0.34,"Yes proactively (after a reference period)":0.18},
   "tilt":{"high_frontline":{"Yes proactively (after a reference period)":+0.08,"No":-0.10},
           "hr_mature":{"Yes proactively (after a reference period)":+0.05,"No":-0.05}},
 },
 "REW262_PAY_CANCELLEDSHIFT": {  # FLAGGED weak baseline; offer_na
   "type":"yes_no","na_rule":"low_shift","dist":{"Yes":0.24,"No":0.76},
   "tilt":{"high_shift":{"Yes":+0.12,"No":-0.12},"hr_mature":{"Yes":+0.06,"No":-0.06}},
 },
 "REW262_PAY_SHIFTNOTICE": {  # offer_na: no-shift orgs -> Not applicable
   "type":"single_select","na_rule":"low_shift",
   "dist":{"No set notice":0.22,"Less than 1 week":0.31,"1-2 weeks":0.33,"2 or more weeks":0.14},
   "tilt":{"hr_mature":{"2 or more weeks":+0.08,"No set notice":-0.08},
           "high_shift":{"1-2 weeks":+0.05,"No set notice":-0.05}},
 },
 "REW262_PAY_AISKILLSPAY": {  # neutral — prevalence only, no verdict
   "type":"yes_no","dist":{"Yes":0.27,"No":0.73},
   "tilt":{"tech_sector":{"Yes":+0.14,"No":-0.14},"size_large":{"Yes":+0.05,"No":-0.05}},
 },
 # --- TIME OFF ---
 "REW262_TIME_BEREAVEMENT": {
   "type":"single_select",
   "dist":{"Statutory only":0.41,"1-5 days enhanced":0.44,"5 or more days enhanced":0.15},
   "tilt":{"hr_mature":{"5 or more days enhanced":+0.06,"Statutory only":-0.10},
           "size_large":{"1-5 days enhanced":+0.05,"Statutory only":-0.05}},
 },
 "REW262_TIME_SICKDAYONE": {
   "type":"yes_no","dist":{"Yes":0.58,"No":0.42},
   "tilt":{"hr_mature":{"Yes":+0.10,"No":-0.10},"public_sector":{"Yes":+0.12,"No":-0.12}},
 },
}

def org_rng(qid, org_id):
    h=hashlib.sha256(f"{qid}|{SEED_DATE}|{org_id}".encode()).hexdigest()
    return random.Random(int(h[:16],16))

def firmo_flags(org):
    """Derive boolean tilt flags from an org's firmographics. Adapt field names
    to the registry at apply time (DECISIONS.md sim_feature_space)."""
    f=set()
    fte=org.get("fte_band_midpoint",500)
    if fte>=2500: f.add("size_large")
    if fte<250: f.add("size_small")
    if org.get("hr_maturity") in ("Advanced","Leading","High"): f.add("hr_mature")
    if org.get("ownership_type") in ("Public sector","Government"): f.add("public_sector")
    if (org.get("frontline_pct") or 0) >= 40: f.add("high_frontline")
    if (org.get("frontline_pct") or 0) < 15: f.add("low_frontline")
    if (org.get("shift_pct") or 0) >= 30: f.add("high_shift")
    if (org.get("shift_pct") or 0) < 10: f.add("low_shift")
    if org.get("industry") in ("Technology","Telecoms, Media & Technology","Financial Services"): f.add("tech_sector")
    return f

def apply_tilt(dist, tilt, flags):
    d=dict(dist)
    for flag, adj in (tilt or {}).items():
        if flag in flags and isinstance(adj, dict):
            for opt,delta in adj.items():
                d[opt]=max(0.0, d.get(opt,0)+delta)
    s=sum(d.values()) or 1.0
    return {k:v/s for k,v in d.items()}

def pick(rng, dist):
    r=rng.random(); cum=0.0
    for opt,p in dist.items():
        cum+=p
        if r<=cum: return opt
    return list(dist)[-1]

def na_applies(rule, flags):
    if rule=="low_frontline": return "low_frontline" in flags
    if rule=="low_shift":     return "low_shift" in flags
    return False

def generate(orgs, write=False):
    out=[]
    for qid,spec in BASELINES.items():
        for org in orgs:
            oid=org["org_id"]; flags=firmo_flags(org); rng=org_rng(qid,oid)
            # offer_na: inapplicable orgs answer "Not applicable"
            if spec.get("na_rule") and na_applies(spec["na_rule"], flags):
                out.append((qid,oid,"Not applicable")); continue
            if spec["type"]=="multi_select":  # action plan
                base=spec["p_has_plan"]
                for flag,delta in spec.get("tilt",{}).items():
                    if flag in flags and isinstance(delta,(int,float)): base+=delta
                base=min(0.95,max(0.02,base))
                if rng.random()>base:
                    out.append((qid,oid,"None")); continue
                chosen=[c for c,p in spec["char_probs"].items() if rng.random()<=p] or ["Gender"]
                out.append((qid,oid,";".join(chosen)))
            else:
                d=apply_tilt(spec["dist"], spec.get("tilt"), flags)
                out.append((qid,oid,pick(rng,d)))
    return out

def summarise(rows):
    from collections import Counter
    byq={}
    for qid,oid,val in rows: byq.setdefault(qid,[]).append(val)
    for qid,vals in byq.items():
        n=len(vals); na=sum(1 for v in vals if v=="Not applicable")
        c=Counter(v for v in vals if v!="Not applicable")
        applic=n-na
        print(f"\n{qid}  (n={n}, applicable={applic}, N/A={na})")
        for opt,k in c.most_common():
            print(f"    {opt:52} {k/applic*100:5.1f}%")


def realised(rows, qid):
    from collections import Counter
    vals=[v for q,o,v in rows if q==qid and v!="Not applicable"]
    n=len(vals) or 1; c=Counter(vals)
    return {k:v/n for k,v in c.items()}

def calibrate(orgs, spec_key, target, tol=0.03, max_iter=12):
    """Scale this question's tilt magnitudes down until the realised distribution
    is within `tol` of the signed baseline `target`. Direction/texture preserved;
    only the STRENGTH of the firmographic spread is tuned so the MEAN lands on the
    baseline David signed (the pay-frequency calibration pattern)."""
    import copy
    spec=BASELINES[spec_key]; scale=1.0
    orig=copy.deepcopy(spec.get("tilt"))
    for _ in range(max_iter):
        # apply current scale to a working copy of tilts
        if isinstance(orig,dict):
            spec["tilt"]={f:({o:d*scale for o,d in adj.items()} if isinstance(adj,dict) else adj*scale)
                          for f,adj in orig.items()}
        rows=generate(orgs)
        r=realised(rows, spec_key)
        worst=max((abs(r.get(opt,0)-target.get(opt,0)) for opt in target), default=0)
        if worst<=tol: break
        scale*=0.7   # damp the tilts and re-draw
    return scale

# baseline targets David signed (single/yes-no only; action-plan calibrates on p_has_plan)
SIGNED_TARGETS={
 "REW262_GOV_EQUALVALUE":{"No":0.35,"In progress":0.38,"Partially":0.19,"Fully":0.08},
 "REW262_GOV_SALHISTORY":{"Yes":0.27,"No":0.73},
 "REW262_GOV_PAYINADVERTS":{"Never":0.45,"Some roles":0.38,"All roles":0.17},
 "REW262_GOV_EQUALPAYAUDIT":{"No":0.30,"Ad hoc":0.38,"Annually":0.26,"More than annually":0.06},
 "REW262_GOV_AIINPAY":{"No AI use":0.62,"AI with no formal oversight":0.14,"AI as decision-support with human oversight":0.19,"AI with human oversight and bias auditing":0.05},
 "REW262_PAY_GUARANTEEDHRS":{"No":0.48,"On request only":0.34,"Yes proactively (after a reference period)":0.18},
 "REW262_PAY_CANCELLEDSHIFT":{"Yes":0.24,"No":0.76},
 "REW262_PAY_SHIFTNOTICE":{"No set notice":0.22,"Less than 1 week":0.31,"1-2 weeks":0.33,"2 or more weeks":0.14},
 "REW262_PAY_AISKILLSPAY":{"Yes":0.27,"No":0.73},
 "REW262_TIME_BEREAVEMENT":{"Statutory only":0.41,"1-5 days enhanced":0.44,"5 or more days enhanced":0.15},
 "REW262_TIME_SICKDAYONE":{"Yes":0.58,"No":0.42},
}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--orgs", default="orgs.json", help="JSON list of org firmographics")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a=ap.parse_args()
    try: orgs=json.load(open(a.orgs))
    except Exception:
        # demo stub so a dry run shows shape even without the registry
        orgs=[{"org_id":f"org{i:03d}","fte_band_midpoint":[100,500,1500,3000,8000][i%5],
               "hr_maturity":["Basic","Developing","Advanced","Leading","Developing"][i%5],
               "ownership_type":["Private","Public sector","PE-backed","Private","Founder-led"][i%5],
               "frontline_pct":[5,20,45,60,10][i%5],"shift_pct":[2,15,35,50,5][i%5],
               "industry":["Technology","Retail & Consumer Goods","Manufacturing","Healthcare","Financial Services"][i%5]}
              for i in range(220)]
        print(f"(no {a.orgs} found — using a 220-org stub to show distributions)")
    # Calibrate tilt strength so realised distributions match David's signed baselines
    # (calibration runs on the REAL registry passed via --orgs; the stub is only illustrative).
    for qid,target in SIGNED_TARGETS.items():
        sc=calibrate(orgs, qid, target)
        print(f"calibrated {qid}: tilt scale {sc:.2f}")
    rows=generate(orgs)
    summarise(rows)
    if a.write and a.__dict__["confirmed_by_david"]:
        json.dump([{"question_id":q,"org_id":o,"value":v} for q,o,v in rows],
                  open("release_2026_2_seed.json","w"), indent=0)
        print(f"\nWROTE release_2026_2_seed.json ({len(rows)} responses)")
    else:
        print("\nDRY RUN — no write. Re-run with --write --confirmed-by-david to emit the seed JSON.")
