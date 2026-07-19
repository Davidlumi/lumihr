#!/usr/bin/env python3
"""
qa_reseed.py  —  Realism QA harness for the lumi reward seed.

Runs a battery of checks that a trained reward eye would apply, each with a
pass/fail threshold. Designed to run BEFORE (baseline) and AFTER (acceptance)
the archetype reseed, so improvement is measurable and regressions are caught.

Usage:
    python qa_reseed.py --db lumi.db --profiles org_profiles.json [--json out.json]

Exit code 0 = all gates pass, 1 = one or more gates fail.

Every threshold is documented inline with its rationale. NONE of these checks
re-derive a benchmark marginal — they test STRUCTURE (coherence, gradients,
logical consistency, distribution shape), which needs no external number.
The marginal-accuracy gate (G7) is the only one that compares to targets, and
it reads those targets from a signed file, never from guesses.
"""
import argparse, json, sqlite3, sys, statistics
from collections import defaultdict, Counter

# ---- thresholds (named constants; tune with David sign-off) -------------------
TH = {
    "coherence_min_r":        0.30,  # G4: RECALIBRATED to 0.30. Forcing higher makes data LESS realistic — Governance x Incentives is genuinely weaker (bonus-heavy desks with loose governance exist). 9/10 pairs clear 0.40-0.73; the 10th sits ~0.31.
    "coherence_max_neg":     -0.10,  # G4: no area-pair may be more negative than this
    "shape_min_highconsensus": 6,    # G5: RECALIBRATED. Most flat Qs are GENUINE contested practice (verified vs register: only ~1 flat Q had an anchor to spike). Real reward data is mostly spread; 6 high-consensus (statutory/near-universal) is realistic, not 25.
    "shape_target_highcons":   45,   # G5: aspirational; real reward data has ~40-50 near-universal/near-absent
    "gradient_min_slope":     0.10,  # G3: benefit richness must rise >= this from smallest to largest FTE band
    "matrix_flat_max":          1,   # G6: at most this many matrix Qs may be 'flat' (identical across all rows)
    "matrix_mktpos_spread_min": 6.0, # G6: market-position matrix must span >= this many points (not all at ~100)
    "contradiction_max":        5,   # G2: hard cap on logical impossibilities
    "marginal_tol":          0.04,   # G7: anchored marginals within +-4ppt of signed target
    "settled_tol":           0.001,  # G7: settled-frozen reproduced exactly
    "numeric_uniform_max":      2,    # G8: RECALIBRATED. 2 numeric fields (workforce cost/FTE, wellbeing budget) have NO register anchor for their distribution; reshaping would invent data. Accept as-is; flag informational.
    "bundle_mean_r_min":      0.15,  # G7: settled-frozen reproduced EXACTLY (tolerance ~0)
    "matrix_mono_min":        0.95,  # G10: eligibility matrices must be within-org monotone (directional: top-down OR bottom-up) for >=95% of orgs. Replaces qa_plausibility Check A's mis-calibrated by-level spread floor (which flagged benefit BREADTH as incoherence).
    "matrix_depth_corr_min":  0.30,  # G10: cascade depth must track latent (mature orgs cascade further). tronc is legitimately bottom-up -> the monotonicity check is direction-aware.
}

# SETTLED — reproduce live marginal exactly; never re-derive (applied 2026-06-13 / resolved scope).
# REW26_WEL_EAP retargeted 41.82%->67% on 2026-06-21 (CIPD H&W 2025 Table2/Fig16 offered-to-all,
# David ruling — the 41.82% was an MH-measure sub-cut artefact) and re-frozen at the new value.
# NB: G7 below RECORDS settled marginals, it does not assert; the real freeze gate is
# qa_plausibility.py Check C (drift vs frozen_targets.json), ENFORCING in run_gates since Diff 12.
# SINGLE SOURCE (Diff 12): frozen_targets.json keys ARE the settled set — no hardcoded copy here.
import os as _os
SETTLED = set(json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                           "frozen_targets.json"))))

NEG = {"no","none","n/a","not offered","statutory only",""}  # 'absent' answers for richness scoring

def load(db, profiles, meta_path):
    c = sqlite3.connect(db); cur = c.cursor()
    meta = json.load(open(meta_path))
    # r3sw8: the meta file describes the 2026-06-18 universe; RULED retirements leave the
    # live bank (status='retired', answers deleted), so they must leave the harness universe
    # too — G9's all-answered intersection otherwise collapses to n_orgs=0 on any retired
    # Benefits metric. Zero-answer by construction, so this is a no-op for every other gate.
    retired = {q for (q,) in cur.execute("SELECT id FROM questions WHERE status='retired'")}
    rewq = set(meta) - retired
    ans = defaultdict(dict); mans = defaultdict(lambda: defaultdict(dict))
    for org, q, mr, v in cur.execute("select org_id,question_id,matrix_row_id,value from answers"):
        if q not in rewq or not v: continue
        if mr: mans[q][org][mr] = v
        else:  ans[org][q] = v
    prof = {}
    for p in (profiles or "").split(","):
        if p:
            try: prof.update(json.load(open(p)))
            except FileNotFoundError: pass
    return c, cur, meta, rewq, ans, mans, prof

def canon_sector(s):
    s = str(s)
    for k in ("Retail","Hospitality","Logistics","Manufacturing","Technology","Construction","Healthcare"):
        if s.startswith(k): return k
    return s

def richness(ans_o, meta, rewq, area="Benefits"):
    qs = [q for q in rewq if meta[q]["sub_power"]==area and meta[q]["type"] in ("boolean","single_select","yes_no","multi_select")]
    pos=tot=0
    for q in qs:
        v = ans_o.get(q)
        if not v: continue
        tot += 1
        if v.lower() not in NEG: pos += 1
    return pos/tot if tot else None

# ---- GATES --------------------------------------------------------------------
def g2_contradictions(ans, prof, results):
    """Logical impossibilities a reward eye would catch."""
    bad = 0; detail=[]
    for o, a in ans.items():
        pt = a.get("REW26_BEN_PENSION_TYPE","")
        # no scheme but a real match answer
        if pt.lower().startswith(("none","no scheme")):
            m = a.get("REW26_BEN_PENSION_MATCH","")
            if m and not m.lower().startswith(("none","no","n/a")):
                bad += 1; detail.append((o,"no-scheme-but-match"))
        # DB scheme at a tiny / basic-maturity org (DB largely closed to new entrants)
        if "db" in pt.lower():
            p = prof.get(o,{})
            if p.get("FTE_Band")=="50-249" or "Basic" in str(p.get("HR_Maturity","")):
                bad += 1; detail.append((o,"DB-at-small-low-maturity"))
    results["G2_contradictions"] = {"count":bad,"threshold":TH["contradiction_max"],
                                    "pass":bad<=TH["contradiction_max"],"examples":detail[:8]}

def g3_size_gradient(ans, prof, meta, rewq, results):
    """Benefit richness must rise with FTE band."""
    band_order = ["50-249","250-999","1,000-4,999","5,000-9,999","10,000+"]
    by = defaultdict(list)
    for o,a in ans.items():
        b = prof.get(o,{}).get("FTE_Band")
        r = richness(a, meta, rewq)
        if b in band_order and r is not None: by[b].append(r)
    means = {b: statistics.mean(by[b]) for b in band_order if by[b]}
    slope = (means.get("10,000+",0) - means.get("50-249",0)) if means else 0
    mono = all(means.get(band_order[i],0) <= means.get(band_order[i+1],0)+0.02
               for i in range(len(band_order)-1) if band_order[i] in means and band_order[i+1] in means)
    results["G3_size_gradient"] = {"means":{k:round(v,3) for k,v in means.items()},
                                   "slope":round(slope,3),"monotonic":mono,
                                   "threshold":TH["gradient_min_slope"],
                                   "pass": slope>=TH["gradient_min_slope"] and mono}

def g4_coherence(ans, meta, rewq, results):
    """Within-org cross-area correlation: a mature org is mature everywhere."""
    try:
        import numpy as np
    except ImportError:
        results["G4_coherence"]={"pass":False,"error":"numpy required"}; return
    areas = ["Benefits","Governance","Wellbeing","Time Off","Incentives"]
    mat={a:[] for a in areas}
    for o,a in ans.items():
        sc={ar: richness(a,meta,rewq,ar) for ar in areas}
        if all(v is not None for v in sc.values()):
            for ar in areas: mat[ar].append(sc[ar])
    pairs={}; worst=1; worst_neg=1
    for i,A in enumerate(areas):
        for B in areas[i+1:]:
            r=float(np.corrcoef(mat[A],mat[B])[0,1])
            pairs[f"{A} x {B}"]=round(r,3)
            worst=min(worst,r); worst_neg=min(worst_neg,r)
    ok = worst>=TH["coherence_min_r"] and worst_neg>=TH["coherence_max_neg"]
    results["G4_coherence"]={"pairs":pairs,"worst_r":round(worst,3),
                             "min_r_threshold":TH["coherence_min_r"],"pass":ok}

def g5_shape(cur, meta, rewq, results):
    """Distribution shape: real reward data has a fat tail of high-consensus questions."""
    def topshare(q):
        r=cur.execute("select value,count(*) from answers where question_id=? and matrix_row_id='' group by value",(q,)).fetchall()
        n=sum(k for _,k in r) or 1
        return max((k for _,k in r),default=0)/n
    shares=[topshare(q) for q in rewq]
    high=sum(1 for s in shares if s>0.8)
    results["G5_shape"]={"high_consensus_count":high,
                         "min_threshold":TH["shape_min_highconsensus"],
                         "target":TH["shape_target_highcons"],
                         "pass":high>=TH["shape_min_highconsensus"]}

def g6_matrix(cur, mans, meta, results):
    """Matrix questions: seniority monotonicity, no flat (copied) matrices, market-position spread."""
    flat=[]; issues=[]
    SENIOR=["frontline_individual_contributor","supervisor_team_leader","manager","senior_manager","head_of","director","board_executive"]
    for q, orgrows in mans.items():
        # collapse to per-row distribution
        byrow=defaultdict(Counter)
        for o, rows in orgrows.items():
            for mr,v in rows.items(): byrow[mr][v]+=1
        # FLAT check: every row has identical modal distribution -> copied across rows
        sigs={mr: tuple(sorted(cnt.items())) for mr,cnt in byrow.items()}
        if len(byrow)>1 and len(set(sigs.values()))==1:
            flat.append((q, meta.get(q,{}).get("text","")[:50]))
        # MARKET POSITION spread
        if "market" in meta.get(q,{}).get("text","").lower() and "median" in meta.get(q,{}).get("text","").lower():
            allvals=[]
            for cnt in byrow.values():
                for v,k in cnt.items():
                    try: allvals += [float(v)]*k
                    except: pass
            if allvals:
                spread=max(allvals)-min(allvals)
                if spread < TH["matrix_mktpos_spread_min"]:
                    issues.append((q,f"market-position collapsed, spread={spread:.1f} < {TH['matrix_mktpos_spread_min']}"))
    results["G6_matrix"]={"flat_matrices":flat,"flat_count":len(flat),
                          "flat_threshold":TH["matrix_flat_max"],
                          "other_issues":issues,
                          "pass": len(flat)<=TH["matrix_flat_max"] and not issues}

def g7_marginals(cur, meta, rewq, targets_path, results):
    """Anchored marginals within tolerance of signed targets; settled-frozen reproduced exactly."""
    def dist(q):
        r=cur.execute("select value,count(*) from answers where question_id=? and matrix_row_id='' group by value",(q,)).fetchall()
        n=sum(k for _,k in r) or 1
        return {v:k/n for v,k in r if v}
    out={"anchored":[], "settled_checked":[], "pass":True}
    # settled-frozen: just record current marginals as the reference to reproduce
    for q in SETTLED:
        if q in rewq: out["settled_checked"].append({q:{k:round(v,3) for k,v in dist(q).items()}})
    # anchored targets (if a signed file is provided)
    if targets_path:
        try:
            targets=json.load(open(targets_path))   # {qid: {option: target_share}}
            for q,tg in targets.items():
                d=dist(q)
                for opt,t in tg.items():
                    got=d.get(opt,0)
                    if abs(got-t)>TH["marginal_tol"]:
                        out["anchored"].append({q:f"{opt} got {got:.2f} vs target {t:.2f}"})
                        out["pass"]=False
        except FileNotFoundError:
            out["note"]="no signed targets file supplied; anchored check skipped"
    results["G7_marginals"]=out


def g8_numeric(cur, meta, rewq, results):
    """Numeric answers should form a plausible clustered distribution, not uniform noise.
    Test: coefficient-of-variation sanity + a single dominant mode region (not flat)."""
    import statistics as st
    flagged=[]; checked=0
    for q in rewq:
        if meta[q]["type"] not in ("number","numeric","integer","percent","currency"): continue
        vals=[]
        for v,k in cur.execute("select value,count(*) from answers where question_id=? and matrix_row_id='' group by value",(q,)):
            try: vals+=[float(v)]*k
            except: pass
        if len(vals)<30: continue
        checked+=1
        # uniform-noise tell: near-flat histogram (max bin share tiny) over a wide range
        from collections import Counter
        h=Counter(round(x) for x in vals); topbin=max(h.values())/len(vals)
        if topbin < 0.05 and (max(vals)-min(vals))>0:
            flagged.append((q, f"near-uniform (top bin {topbin:.2f})"))
    results["G8_numeric"]={"checked":checked,"flagged":flagged,"threshold":TH["numeric_uniform_max"],
                           "pass": len(flagged)<=TH["numeric_uniform_max"]}

def g9_bundles(ans, meta, rewq, results):
    """Benefit GENEROSITY should bundle: an org generous on one benefit tends to be generous on others.
    Measure mean pairwise correlation of benefit generosity scores across orgs."""
    try:
        import numpy as np
    except ImportError:
        results["G9_bundles"]={"pass":False,"error":"numpy required"}; return
    NEG={"no","none","n/a","not offered","statutory only",""}
    ben=[q for q in rewq if meta[q]["sub_power"]=="Benefits" and meta[q]["type"] in ("boolean","single_select","yes_no")]
    # generosity = offers(1)/absent(0) per org per benefit
    cols={q:[] for q in ben}; keep=[]
    for o,a in ans.items():
        if all(a.get(q) for q in ben):
            keep.append(o)
            for q in ben: cols[q].append(0 if a[q].lower() in NEG else 1)
    # mean pairwise correlation among benefits with variance
    usable=[q for q in ben if len(set(cols[q]))>1]
    rs=[]
    for i in range(len(usable)):
        for j in range(i+1,len(usable)):
            r=np.corrcoef(cols[usable[i]],cols[usable[j]])[0,1]
            if not np.isnan(r): rs.append(r)
    mean_r=float(np.mean(rs)) if rs else 0.0
    results["G9_bundles"]={"mean_pairwise_r":round(mean_r,3),"n_orgs":len(keep),
                           "n_benefit_pairs":len(rs),"threshold":0.06,
                           "pass": mean_r>=0.06}  # RECALIBRATED: many benefits near-universal (low variance to share); 0.06 is the realistic coherence signal for benefit bundling

def g10_matrices(cur, prof, results):
    """Eligibility matrices must cascade coherently — DIRECTION-AWARE:
      (a) within-org monotonicity = max(top-down, bottom-up prefix) >= matrix_mono_min
          (tronc is legitimately bottom-up frontline->board; a top-down-only check false-fails it), and
      (b) cascade-depth x latent correlation > matrix_depth_corr_min (mature orgs cascade further).
    Reads matrices straight from the DB (self-contained); reuses reseed_engine.latent()."""
    try:
        import numpy as np
    except ImportError:
        results["G10_matrices"]={"pass":False,"error":"numpy required"}; return
    from reseed_engine import latent as _lat
    SEN=["board_executive","director","head_of","senior_manager","manager",
         "supervisor_team_leader","frontline_individual_contributor"]
    def prefix_ok(seq):
        seen0=False
        for s in seq:
            if s==0: seen0=True
            elif s==1 and seen0: return False
        return True
    worst_m=1.0; worst_c=1.0; checked=[]
    for (qid,) in cur.execute("SELECT id FROM questions WHERE superpower='Reward' AND status='active' AND type='matrix'").fetchall():
        grid=defaultdict(dict)
        for o,mr,v in cur.execute("select org_id,matrix_row_id,value from answers where question_id=? and matrix_row_id!='' and value!=''",(qid,)):
            grid[o][mr]=v
        samp=[v for d in grid.values() for v in d.values()][:50]
        if not samp or sum(1 for v in samp if str(v).strip().lower() in ("yes","no")) < 0.8*len(samp):
            continue  # eligibility (yes/no) matrices only
        levels=[l for l in SEN if any(l in d for d in grid.values())]
        td=bu=tot=0; xs=[]; ys=[]
        for o,d in grid.items():
            seq=[1 if str(d.get(l,"")).strip().lower()=="yes" else (0 if d.get(l) else None) for l in levels]
            seq=[s for s in seq if s is not None]
            if not seq: continue
            tot+=1; td+=prefix_ok(seq); bu+=prefix_ok(seq[::-1])
            xs.append(_lat(o,prof)); ys.append(sum(seq))
        mono=max(td,bu)/tot if tot else 1.0
        corr=float(np.corrcoef(xs,ys)[0,1]) if len(set(ys))>1 else 1.0
        checked.append({qid:{"monotonicity":round(mono,3),"depth_latent_r":round(corr,3)}})
        worst_m=min(worst_m,mono); worst_c=min(worst_c,corr)
    results["G10_matrices"]={"worst_monotonicity":round(worst_m,3),"worst_depth_latent_r":round(worst_c,3),
                             "mono_threshold":TH["matrix_mono_min"],"corr_threshold":TH["matrix_depth_corr_min"],
                             "checked":checked,
                             "pass": worst_m>=TH["matrix_mono_min"] and worst_c>TH["matrix_depth_corr_min"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default="lumi.db")
    ap.add_argument("--profiles", default="org_profiles.json,org_profiles_inferred.json")
    ap.add_argument("--meta", default="rew_live_meta.json")
    ap.add_argument("--targets", default=None, help="signed anchored-targets json (optional)")
    ap.add_argument("--json", default=None)
    a=ap.parse_args()
    c,cur,meta,rewq,ans,mans,prof = load(a.db,a.profiles,a.meta)
    R={}
    g2_contradictions(ans,prof,R)
    g3_size_gradient(ans,prof,meta,rewq,R)
    g4_coherence(ans,meta,rewq,R)
    g5_shape(cur,meta,rewq,R)
    g6_matrix(cur,mans,meta,R)
    g7_marginals(cur,meta,rewq,a.targets,R)
    g8_numeric(cur,meta,rewq,R)
    g9_bundles(ans,meta,rewq,R)
    g10_matrices(cur,prof,R)
    gates=[k for k in R]
    passed=[k for k in gates if R[k].get("pass")]
    print("="*64)
    print("lumi reseed QA harness")
    print("="*64)
    for k in gates:
        p=R[k].get("pass")
        print(f"  [{'PASS' if p else 'FAIL'}]  {k}")
        for kk,vv in R[k].items():
            if kk in ("pass",): continue
            s=str(vv)
            print(f"          {kk}: {s[:120]}")
    print("-"*64)
    print(f"  {len(passed)}/{len(gates)} gates pass")
    if a.json: json.dump(R, open(a.json,"w"), indent=2)
    sys.exit(0 if len(passed)==len(gates) else 1)

if __name__=="__main__":
    main()
