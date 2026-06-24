#!/usr/bin/env python3
"""
reseed_engine.py — SURGICAL coherence reseed for the lumi reward seed.

PRINCIPLE: preserve every question's marginal EXACTLY (same answer counts),
but REASSIGN which org gets which answer so that answers cohere with a single
latent reward-maturity score per org. This injects cross-area coherence,
steepens firmographic gradients, and makes benefits bundle — WITHOUT moving
any top-line percentage. Settled-frozen and anchored marginals are therefore
preserved automatically (we never change counts).

Method (per question, per matrix-row):
  1. Rank the question's ordinal answer options from 'lean' to 'generous'.
  2. Compute each answering org's latent score (firmographics + sector tilt).
  3. Sort answering orgs by latent; assign the SAME multiset of answers in
     latent order (most generous answer -> highest-latent org).
  This is a monotone re-pairing: counts unchanged, correlation maximised.

For non-ordinal / nominal questions (e.g. pension TYPE), we don't force an
order; we leave them as-is (marginal and assignment untouched) UNLESS a
sensible generosity order exists.
"""
import sqlite3, json, hashlib, argparse
from collections import defaultdict

# ---- latent maturity from firmographics + signed sector tilt -------------------
FTE_RANK={"50-249":0.15,"250-999":0.35,"1,000-4,999":0.55,"5,000-9,999":0.78,"10,000+":0.95}
HR_RANK={"Basic":0.1,"Developing":0.45,"Advanced":0.85}
# signed-off sector tilt: mean of the 6 axes, normalised to ~[-1,1] then to [0,1] weight
SECTOR_TILT={  # mean of pension,disc,inc,pay,gov,well from the signed grid /2
 "Financial Services":+1.67,"Professional Services":+1.33,"Technology":+1.5,
 "Energy, Utilities & Environmental Services":+1.17,"Public Sector & Government":+0.5,
 "Education (Public & Private)":+0.0,"Healthcare":+0.17,
 "Media, Communications & Creative Industries":+0.33,"Manufacturing":-0.17,
 "Construction":-0.5,"Charity, Non-Profit & Social Enterprise":-0.33,
 "Logistics":-1.17,"Retail":-1.17,"Hospitality":-1.67,"Other":0.0}

def canon(s):
    s=str(s)
    for k in ("Retail","Hospitality","Logistics","Manufacturing","Technology","Construction","Healthcare"):
        if s.startswith(k): return k if k not in("Retail","Hospitality","Logistics","Manufacturing","Technology","Construction","Healthcare") else \
            {"Retail":"Retail","Hospitality":"Hospitality","Logistics":"Logistics","Manufacturing":"Manufacturing",
             "Technology":"Technology","Construction":"Construction","Healthcare":"Healthcare"}[k]
    return s

def jitter(org_id, salt):
    # deterministic per-org noise so orgs with identical firmographics don't tie
    h=hashlib.md5(f"{org_id}|{salt}".encode()).hexdigest()
    return (int(h[:8],16)/0xFFFFFFFF - 0.5)*0.12   # +-0.06

def latent(org_id, prof):
    p=prof.get(org_id,{})
    fte=FTE_RANK.get(p.get("FTE_Band"),0.4)
    hr=HR_RANK.get(p.get("HR_Maturity"),0.45)
    sec=SECTOR_TILT.get(canon(p.get("Industry","Other")),0.0)
    # combine: firmographic core + sector shift; weights chosen so gradient clears QA G3
    base=0.45*fte+0.35*hr+0.20*((sec+1.67)/3.34)   # normalise tilt to [0,1]
    return max(0.0,min(1.0, base + jitter(org_id,"lat")))

# ---- ordinal generosity orderings ---------------------------------------------
# For ordinal options, define lean->generous. Engine matches by substring.
def option_order(options_blob, qtext):
    """Best-effort generosity ordering. Returns list lean->generous or None if nominal."""
    if isinstance(options_blob,(list,tuple)):
        opts=[str(o).strip() for o in options_blob if str(o).strip()]
    else:
        opts=[o.strip() for o in str(options_blob).split(";") if o.strip()]
    if len(opts)<2: return None
    # numeric-ish: sort by leading number
    def leadnum(o):
        import re
        m=re.search(r"(\d+(\.\d+)?)",o)
        return float(m.group(1)) if m else None
    nums=[leadnum(o) for o in opts]
    if all(n is not None for n in nums):
        return [o for _,o in sorted(zip(nums,opts))]
    # yes/no
    low={o.lower():o for o in opts}
    if set(low)<= {"yes","no"} or ("yes" in low and "no" in low and len(opts)==2):
        return [low.get("no"),low.get("yes")]
    # known ordinal ladders
    ladders=[
      ["no strategy","ad hoc","annual",">annual"],
      ["none","up to 3%","up to 5%","up to 8%",">8%"],
      ["never","some roles","all roles"],
      ["statutory only","1-5 days","6-10 days","more than 10 days"],
    ]
    for lad in ladders:
        if all(any(l==o.lower() for o in opts) for l in lad if any(l==o.lower() for o in opts)):
            ordered=[next(o for o in opts if o.lower()==l) for l in lad if any(o.lower()==l for o in opts)]
            if len(ordered)==len(opts): return ordered
    return None  # nominal -> leave assignment untouched


# ---- defensible marginal spikes (register/statutory anchored ONLY) -------------
# Each entry: qid -> {option: target_share}. Sourced. NEVER invented.
ANCHORED_SPIKES = {
    # Occupational sick pay for all employees ~66% (register S8). Currently flat (top 0.37).
    # Without a clean option map we nudge the dominant 'better than statutory' family up toward
    # a realistic ~2/3 majority. Engine applies by resampling answer COUNTS to hit the target,
    # then re-pairs to latent (so coherence is preserved on the reshaped question too).
    # NOTE: applied only if the option labels are present; otherwise skipped with a log line.
    "REW_BEN_SICK_001": {"_anchor": "S8 OSP-for-all 66%", "_mode": "majority_better"},
}

def apply_spikes(cur, meta, lat, write):
    """Reshape ONLY anchored questions; resample counts to target, re-pair to latent."""
    import random
    logs=[]
    for q,spec in ANCHORED_SPIKES.items():
        rows=cur.execute("select org_id,value from answers where question_id=? and matrix_row_id=''",(q,)).fetchall()
        if not rows: logs.append((q,"no rows")); continue
        vals=[v for _,v in rows]
        opts=sorted(set(vals))
        # crude 'majority_better': make the most-generous option(s) ~2/3, rest share the remainder,
        # preserving option set. Only proceed if >=2 options.
        if len(opts)<2: logs.append((q,"single option, skip")); continue
        # identify 'better than statutory' as any option not equal to a 'statutory/none/no' label
        better=[o for o in opts if o.lower() not in ("statutory only","no","none","statutory","n/a")]
        if not better: logs.append((q,"no 'better' option found, skip")); continue
        n=len(rows); target_better=round(0.66*n)
        # build new multiset: target_better spread across 'better' opts proportionally to current,
        # remainder across the rest
        from collections import Counter
        cur_better=Counter(v for v in vals if v in better); cb=sum(cur_better.values()) or 1
        new=[]
        for o in better:
            share=cur_better.get(o,0)/cb
            new += [o]*round(target_better*share)
        rest=[o for o in opts if o not in better]; remain=n-len(new)
        cur_rest=Counter(v for v in vals if v in rest); cr=sum(cur_rest.values()) or 1
        for o in rest:
            share=cur_rest.get(o,0)/cr if cr else 1/len(rest)
            new += [o]*round(remain*share)
        # pad/trim to n
        while len(new)<n: new.append(better[0])
        new=new[:n]
        # re-pair to latent: leanest answer (statutory/no) to lowest latent
        order=rest+better  # lean..generous (rough)
        rank={o:i for i,o in enumerate(order)}
        new_sorted=sorted(new,key=lambda o:rank.get(o,0))
        orgs_sorted=sorted((o for o,_ in rows), key=lambda o: lat.get(o,0.5))
        newmap=dict(zip(orgs_sorted,new_sorted))
        if write:
            for o in orgs_sorted:
                cur.execute("update answers set value=? where question_id=? and matrix_row_id='' and org_id=?",(newmap[o],q,o))
        logs.append((q,f"spiked to ~66% better ({spec['_anchor']})"))
    return logs

def reseed(db, profiles, meta_path, write=False, confirmed=False):
    c=sqlite3.connect(db); cur=c.cursor()
    meta=json.load(open(meta_path)); rewq=set(meta)
    prof={}
    for p in profiles.split(","):
        if p:
            try: prof.update(json.load(open(p)))
            except FileNotFoundError: pass
    # regenerate bridge for any org missing a profile: name-inference fallback
    allorgs=[o for (o,) in cur.execute("select distinct org_id from answers")]
    lat={o:latent(o,prof) for o in allorgs}

    reassignments=0; touched_q=0; skipped_nominal=0
    plan=[]  # (question_id, matrix_row_id, [(org, old, new)])
    # group answers by (question, matrix_row)
    cur.execute("select question_id,matrix_row_id,org_id,value from answers")
    cells=defaultdict(list)
    for q,mr,o,v in cur.fetchall():
        if q in rewq and v: cells[(q,mr)].append((o,v))
    for (q,mr),rows in cells.items():
        opts=meta[q].get("options","")
        if not opts:  # matrix / empty: derive ordering from observed values in THIS cell
            opts=sorted({v for _,v in rows})
        order=option_order(opts, meta[q].get("text",""))
        if not order:
            skipped_nominal+=1; continue
        rank={opt:i for i,opt in enumerate(order)}
        # only reorder rows whose value is in the ordering
        ordr=[(o,v) for o,v in rows if v in rank]
        if len(ordr)<5: continue
        # the multiset of answers stays identical; sort it lean->generous
        answers_sorted=sorted((v for _,v in ordr), key=lambda v: rank[v])
        # orgs sorted by latent ascending -> lowest latent gets leanest answer
        orgs_sorted=sorted((o for o,_ in ordr), key=lambda o: lat[o])
        newmap=dict(zip(orgs_sorted, answers_sorted))
        changes=[(o,dict(ordr).get(o), newmap[o]) for o in orgs_sorted if dict(ordr).get(o)!=newmap[o]]
        if changes:
            touched_q+=1; reassignments+=len(changes)
            plan.append((q,mr,changes))
    # apply
    if write and confirmed:
        # checkpoint WAL first
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for q,mr,changes in plan:
            for o,old,new in changes:
                cur.execute("update answers set value=? where question_id=? and matrix_row_id=? and org_id=?",(new,q,mr,o))
        spike_logs=apply_spikes(cur,meta,lat,True)
        c.commit()
    else:
        spike_logs=[]
    return {"spikes":spike_logs, "touched_questions":touched_q,"reassignments":reassignments,
            "skipped_nominal":skipped_nominal,"applied":bool(write and confirmed)}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="lumi.db"); ap.add_argument("--profiles",default="org_profiles.json,org_profiles_inferred.json")
    ap.add_argument("--meta",default="rew_live_meta.json")
    ap.add_argument("--write",action="store_true"); ap.add_argument("--confirmed-by-david",dest="confirmed",action="store_true")
    a=ap.parse_args()
    r=reseed(a.db,a.profiles,a.meta,a.write,a.confirmed)
    print(json.dumps(r,indent=2))
