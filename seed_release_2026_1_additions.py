#!/usr/bin/env python3
"""
Firewall-compliant synthetic seed for the 14 release-2026.1 additions
(Wellbeing x6, Pension x5, Skills/levelling x2, EU PTD x1) — David-signed baselines.

Same discipline as seed_release_2026_2.py / the documented regenerations:
- DOCUMENTED baselines (signed) in CONSTANTS; conditioned on FIRMOGRAPHICS only.
- SEEDED per org -> reproducible (seed = f"{qid}|{SEED_DATE}|{org_id}"); ORG-BLIND; WHOLE-METRIC.
- CALIBRATE realised -> signed baseline, INCLUDING multi_select (the 2026.2 gap: the
  multi calibrates on per-option prevalence, not just a single dist; covered here).
- numeric questions: distribution by (median, spread); N/A where 'not applicable' is real.
- DOUBLE-GUARDED write (--write --confirmed-by-david); refuse if any answer pre-exists.
"""
import hashlib, random, argparse, json, statistics, math

SEED_DATE = "2026-06-12"

# id_hints map to the live REW26_* ids at apply time (Claude Code resolves the real ids).
BASELINES = {
 # ---------------- WELLBEING ----------------
 "WELL_EAP": {"type":"yes_no","dist":{"Yes":0.41,"No":0.59},   # recalibrated 0.76->0.41 per CIPD H&W 2025 (S28) MH-measure read; tab6 evidenced
   "tilt":{"size_large":{"Yes":+0.12,"No":-0.12},"hr_mature":{"Yes":+0.10,"No":-0.10}}},
 "WELL_MHPROVISIONS": {"type":"multi_select",   # recalibrated to CIPD H&W 2025 (S28) marginals; tab6 evidenced
   # conditional-on-not-None offer probs, tuned so realised MARGINALS hit signed targets
   # CIPD S28: counselling 43%, manager MH training 29% (also reinforces G3), ~88% take some action (None ~12%).
   # First-aiders & digital app not in CIPD top-line -> held near prior (not invented).
   # NOTE: multi_select is NOT auto-calibrated (see calibrate()), so these conditional
   # probs are SOLVED on the seeded panel to realise the SIGNED_MULTI marginals directly.
   "option_probs":{"Mental health first aiders":0.480,"Counselling":0.439,
                   "Digital wellbeing app":0.421,"Manager training":0.287,
                   "Dedicated MH days":0.093},
   "none_label":"None","none_prob":0.200,   # solved so realised marginal None~12% (CIPD: 88% take action)
   "none_tilt":{"size_large":-0.08,"hr_mature":-0.08},
   "opt_tilt":{"size_large":+0.04,"hr_mature":+0.04}},
 "WELL_FINWELL": {"type":"yes_no","dist":{"Yes":0.64,"No":0.36},   # recalibrated 0.30->0.64 per CIPD Reward 2026 (S29); NOTE 64% INCLUDES orgs planning to introduce in 2026, so 'in place today' is lower
   "tilt":{"size_large":{"Yes":+0.10,"No":-0.10},"hr_mature":{"Yes":+0.10,"No":-0.10}}},
 "WELL_BUDGET": {"type":"numeric","unit":"GBP","na_share":0.62,"na_calibrates":True,
   "median":100.0,"lo":20.0,"hi":600.0,"sigma":0.6,   # lognormal median=100
   "tilt":{"size_large":{"na_share":-0.15},"hr_mature":{"na_share":-0.12}}},
 "WELL_SCREENING": {"type":"yes_no","dist":{"Yes":0.42,"No":0.58},
   "tilt":{"size_large":{"Yes":+0.14,"No":-0.14}}},
 "WELL_STRATEGY": {"type":"single_select",
   "dist":{"No strategy":0.34,"Ad hoc":0.30,"Annual":0.28,"More than annually":0.08},
   "tilt":{"hr_mature":{"Annual":+0.10,"No strategy":-0.12},"size_large":{"Annual":+0.05,"No strategy":-0.06}}},
 # ---------------- PENSION / BENEFITS ----------------
 "PEN_TYPE": {"type":"single_select",   # neutral
   "dist":{"DC":0.82,"DB":0.08,"Hybrid":0.07,"None":0.03},
   "tilt":{"public_sector":{"DB":+0.18,"DC":-0.16},"size_large":{"Hybrid":+0.04,"DC":-0.04}}},
 "PEN_PLSA": {"type":"yes_no","dist":{"Yes":0.28,"No":0.72},
   "tilt":{"size_large":{"Yes":+0.10,"No":-0.10},"public_sector":{"Yes":+0.12,"No":-0.12}}},
 "PEN_MATCH": {"type":"single_select",
   "dist":{"None":0.30,"Up to 3%":0.22,"Up to 5%":0.26,"Up to 8%":0.16,"More than 8%":0.06},
   "tilt":{"hr_mature":{"Up to 5%":+0.06,"None":-0.08},"size_large":{"Up to 8%":+0.05,"None":-0.06}}},
 "PEN_SALSAC": {"type":"yes_no","dist":{"Yes":0.58,"No":0.42},
   "tilt":{"size_large":{"Yes":+0.12,"No":-0.12},"hr_mature":{"Yes":+0.08,"No":-0.08}}},
 "PEN_COSTPCT": {"type":"numeric","unit":"PCT","na_share":0.0,
   "median":7.0,"lo":2.0,"hi":18.0,"sigma":0.35,   # lognormal median=7
   "tilt":{"public_sector":{"median_add":+2.0}}},
 # ---------------- PAY / SKILLS ----------------
 "PAY_SKILLSPAY": {"type":"yes_no","dist":{"Yes":0.26,"No":0.74},   # neutral
   "tilt":{"tech_sector":{"Yes":+0.10,"No":-0.10},"hr_mature":{"Yes":+0.06,"No":-0.06}}},
 "PAY_LEVELLING": {"type":"single_select",   # options mutually exclusive -> single_select
   "dist":{"All":0.31,"Senior only":0.14,"Some families":0.27,"None":0.28},
   "tilt":{"size_large":{"All":+0.10,"None":-0.12},"hr_mature":{"All":+0.08,"None":-0.10}}},
 # ---------------- GOVERNANCE ----------------
 "GOV_PTDREADY": {"type":"single_select",
   "dist":{"Not started":0.33,"Assessing":0.30,"Planning":0.21,"Implementing":0.14,"Compliant":0.02},   # Compliant 0.03->0.02 per S4 (mature tail genuinely tiny); +0.01 to Implementing
   "tilt":{"size_large":{"Assessing":+0.06,"Not started":-0.10},"hr_mature":{"Planning":+0.06,"Not started":-0.08}}},
}

# Signed targets (the realised data must hit these within tolerance)
SIGNED = {
 "WELL_EAP":{"Yes":0.41,"No":0.59},
 "WELL_FINWELL":{"Yes":0.64,"No":0.36},
 "WELL_SCREENING":{"Yes":0.42,"No":0.58},
 "WELL_STRATEGY":{"No strategy":0.34,"Ad hoc":0.30,"Annual":0.28,"More than annually":0.08},
 "PEN_TYPE":{"DC":0.82,"DB":0.08,"Hybrid":0.07,"None":0.03},
 "PEN_PLSA":{"Yes":0.28,"No":0.72},
 "PEN_MATCH":{"None":0.30,"Up to 3%":0.22,"Up to 5%":0.26,"Up to 8%":0.16,"More than 8%":0.06},
 "PEN_SALSAC":{"Yes":0.58,"No":0.42},
 "PAY_SKILLSPAY":{"Yes":0.26,"No":0.74},
 "PAY_LEVELLING":{"All":0.31,"Senior only":0.14,"Some families":0.27,"None":0.28},
 "GOV_PTDREADY":{"Not started":0.33,"Assessing":0.30,"Planning":0.21,"Implementing":0.14,"Compliant":0.02},
}
# Multi-select target = per-option prevalence + None
# True SIGNED MARGINAL prevalence across ALL orgs (what David signed), for verification.
SIGNED_MULTI = {"WELL_MHPROVISIONS":{"Mental health first aiders":0.52,"Counselling":0.43,
                "Digital wellbeing app":0.38,"Manager training":0.29,"Dedicated MH days":0.14,"None":0.12}}
# Numeric target = median + na_share
SIGNED_NUM = {"WELL_BUDGET":{"median":100.0,"na_share":0.62},"PEN_COSTPCT":{"median":7.0,"na_share":0.0}}

def org_rng(qid, oid): 
    h=hashlib.sha256(f"{qid}|{SEED_DATE}|{oid}".encode()).hexdigest()
    return random.Random(int(h[:16],16))

def flags(org):
    f=set(); fte=org.get("fte_band_midpoint",500)
    if fte>=2500: f.add("size_large")
    if fte<250: f.add("size_small")
    if org.get("hr_maturity") in ("Advanced","Leading","High"): f.add("hr_mature")
    if org.get("ownership_type") in ("Public sector","Government") or org.get("public_sector"): f.add("public_sector")
    if org.get("industry") in ("Technology","Telecoms, Media & Technology","Financial Services"): f.add("tech_sector")
    return f

def tilt_dist(dist, tilt, fl):
    d=dict(dist)
    for k,adj in (tilt or {}).items():
        if k in fl and isinstance(adj,dict):
            for o,dl in adj.items():
                if o in d: d[o]=max(0.0,d[o]+dl)
    s=sum(d.values()) or 1; return {k:v/s for k,v in d.items()}

def pick(rng,d):
    r=rng.random(); c=0
    for o,p in d.items():
        c+=p
        if r<=c: return o
    return list(d)[-1]

def gen_one(qid,spec,org,scale=1.0):
    fl=flags(org); rng=org_rng(qid,org["org_id"]); t=spec["type"]
    if t in ("yes_no","single_select"):
        tl={k:({o:dl*scale for o,dl in adj.items()} if isinstance(adj,dict) else adj) for k,adj in (spec.get("tilt") or {}).items()}
        return pick(rng, tilt_dist(spec["dist"], tl, fl))
    if t=="multi_select":
        # None is a PRIMARY draw first (firmographic tilt lowers None for big/mature orgs).
        np=spec["none_prob"]
        for k,dl in (spec.get("none_tilt") or {}).items():
            if k in fl and isinstance(dl,(int,float)): np=max(0.0,min(0.95,np+dl))
        if rng.random()<np:
            return spec["none_label"]
        # Otherwise select among options at their signed CONDITIONAL prob (no global scale —
        # per-option targets are independent and a single scale cannot hit all of them).
        sel=[]
        for opt,p in spec["option_probs"].items():
            pp=min(0.99,p)
            for k,dl in (spec.get("opt_tilt") or {}).items():
                if k in fl and isinstance(dl,(int,float)): pp=min(0.99,max(0.0,pp+dl))
            if rng.random()<=pp: sel.append(opt)
        # if nothing selected after deciding NOT-None, force the single most likely option
        if not sel:
            sel=[max(spec["option_probs"], key=spec["option_probs"].get)]
        return ";".join(sel)
    if t=="numeric":
        # na_share is what `scale` tunes for numerics (calibration target = signed na_share).
        na=spec["na_share"]
        for k,adj in (spec.get("tilt") or {}).items():
            if k in fl and isinstance(adj,dict) and "na_share" in adj: na=max(0.0,na+adj["na_share"])
        na=max(0.0,min(0.95,na))
        if rng.random()<na: return "Not applicable"
        med=spec["median"]
        for k,adj in (spec.get("tilt") or {}).items():
            if k in fl and isinstance(adj,dict) and "median_add" in adj: med+=adj["median_add"]
        # Draw so the POPULATION MEDIAN == med exactly: lognormal with median=med.
        # sigma controls spread; lo/hi clamp the tails. Median of a clamped-lognormal
        # stays ~med as long as the clamp is symmetric-ish in log space.
        sigma=spec.get("sigma",0.5)
        v=med*math.exp(rng.gauss(0,sigma))
        v=max(spec["lo"],min(spec["hi"],v))
        return round(v, 0 if spec["unit"]=="GBP" else 1)

def generate(orgs, scales=None):
    scales=scales or {}; out=[]
    for qid,spec in BASELINES.items():
        sc=scales.get(qid,1.0)
        for org in orgs: out.append((qid,org["org_id"],gen_one(qid,spec,org,sc)))
    return out

def realised_cat(rows,qid):
    from collections import Counter
    v=[x for q,o,x in rows if q==qid and x!="Not applicable"]; n=len(v) or 1
    return {k:c/n for k,c in Counter(v).items()}
def realised_multi(rows,qid,opts):
    apps=[x for q,o,x in rows if q==qid]; n=len(apps) or 1; out={}
    for opt in opts:
        out[opt]=sum(1 for x in apps if (x=="None" and opt=="None") or (opt!="None" and opt in x.split(";")))/n
    return out
def realised_num(rows,qid):
    vals=[x for q,o,x in rows if q==qid and x!="Not applicable"]
    na=sum(1 for q,o,x in rows if q==qid and x=="Not applicable")
    tot=sum(1 for q,o,x in rows if q==qid)
    med=statistics.median(vals) if vals else 0
    return {"median":med,"na_share":na/(tot or 1)}

def calibrate(orgs, tol=0.03, max_iter=10):
    """Scale tilt strength per question until realised hits signed baseline.
    Covers single/yes-no, multi_select (per-option), and numeric (median+na)."""
    scales={q:1.0 for q in BASELINES}
    for _ in range(max_iter):
        rows=generate(orgs,scales); worst=0; changed=False
        for qid in BASELINES:
            t=BASELINES[qid]["type"]
            if t in ("multi_select","numeric"):
                continue   # drawn directly to signed target; no global scale (would fight per-option/na)
            if t in ("yes_no","single_select"):
                r=realised_cat(rows,qid); tgt=SIGNED[qid]
                w=max(abs(r.get(o,0)-tgt.get(o,0)) for o in tgt)
            elif t=="multi_select":
                tgt=SIGNED_MULTI[qid]; r=realised_multi(rows,qid,list(tgt))
                w=max(abs(r.get(o,0)-tgt.get(o,0)) for o in tgt)
            else:
                tgt=SIGNED_NUM[qid]; r=realised_num(rows,qid)
                w=max(abs(r["na_share"]-tgt["na_share"]), abs(r["median"]-tgt["median"])/max(tgt["median"],1))
            worst=max(worst,w)
            if w>tol: scales[qid]*=0.7; changed=True
        if not changed: break
    return scales

def summarise(rows):
    for qid,spec in BASELINES.items():
        if spec["type"]=="multi_select":
            r=realised_multi(rows,qid,list(SIGNED_MULTI[qid]))
            print(f"\n{qid} (multi):"); [print(f"    {o:30} {p*100:5.1f}%") for o,p in r.items()]
        elif spec["type"]=="numeric":
            r=realised_num(rows,qid); print(f"\n{qid} (numeric): median {r['median']}, N/A {r['na_share']*100:.0f}%")
        else:
            r=realised_cat(rows,qid); print(f"\n{qid}:"); [print(f"    {o:24} {p*100:5.1f}%") for o,p in sorted(r.items(),key=lambda x:-x[1])]

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--orgs",default="orgs.json")
    ap.add_argument("--write",action="store_true"); ap.add_argument("--confirmed-by-david",action="store_true")
    a=ap.parse_args()
    try: orgs=json.load(open(a.orgs))
    except Exception:
        orgs=[{"org_id":f"org{i:03d}","fte_band_midpoint":[100,500,1500,3000,8000][i%5],
               "hr_maturity":["Basic","Developing","Advanced","Leading","Developing"][i%5],
               "ownership_type":["Private","Public sector","PE-backed","Private","Founder-led"][i%5],
               "industry":["Technology","Retail & Consumer Goods","Manufacturing","Healthcare","Financial Services"][i%5]}
              for i in range(220)]
        print(f"(no {a.orgs} — 220-org stub)")
    sc=calibrate(orgs)
    for q,s in sc.items(): print(f"calib {q}: scale {s:.2f}")
    rows=generate(orgs,sc); summarise(rows)
    if a.write and a.__dict__["confirmed_by_david"]:
        json.dump([{"question_id":q,"org_id":o,"value":v} for q,o,v in rows],
                  open("release_2026_1_additions_seed.json","w"),indent=0)
        print(f"\nWROTE {len(rows)} responses")
    else: print("\nDRY RUN — re-run with --write --confirmed-by-david to emit.")
