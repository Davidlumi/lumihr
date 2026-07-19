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
import sqlite3, json, hashlib, argparse, os, re, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- multi-factor config (B2: load, never hardcode) ---------------------------
RHO = float(os.environ.get("LUMI_RHO", "0.45"))   # env-overridable for the qa_reseed sweep.
#      Prior ruling 2026-07-15 (three-factor): 0.45 (rho_decision.json, revised). Feasible band is only {0.40,0.45}:
             # 0.35 FAILS G4 (worst_r 0.268 < 0.30 floor); 0.50+ breaches the 0.70 cross-factor
             # ceiling. G4 binds from BELOW (pulls rho UP) — measured on the real reseed, not
             # assumed. 0.45 leaves +0.057 on G4 (vs +0.018 at 0.40) and +0.027 on the ceiling;
             # the anticipated re-basing of the 15 held rows moves coherence = G4, so margin
             # belongs there. G3 +0.240, G4 +0.357, cross-factor 0.673.

def _load(name):
    try:
        return json.load(open(os.path.join(HERE, name), encoding="utf-8"))
    except FileNotFoundError:
        return {}

CFG    = _load("persona_factor_config.json")
FMAP   = _load("metric_factor_map.json")
SPIKES = _load("anchored_spikes.json")     # DEAD as an input (kept only so legacy tooling imports don't crash)
LEVELS = _load("level_distributions.json") # NOT applied by reseed() — open item, see DECISIONS Diff 3
MARG   = _load("generated_marginals.json") # THE marginal set (Diff 2, David-approved final table)
ORD    = (_load("ruled_orderings.json") or {}).get("orderings", {})  # THE standing orderings artifact
B5     = _load("b5_levels_ruled.json")     # Diff 10: ruled within-offerer level distributions (3 applied / 13 dropped)

# ---- latent maturity from firmographics + signed sector tilt -------------------
FTE_RANK={"50-249":0.15,"250-999":0.35,"1,000-4,999":0.55,"5,000-9,999":0.78,"10,000+":0.95}
HR_RANK={"Basic":0.1,"Developing":0.45,"Advanced":0.85}

# Semantic lean pole (kit rule 2, Diff 7): NEVER positional. A prevalence target_share is
# the share NOT on the lean pole; a row with no natural lean option needs an explicit
# worst-option key and hard-errors rather than guessing by position.
LEAN_RE = re.compile(r"^(no\b|none\b|not offered|not provided|not applicable|not in scope|"
                     r"neither\b|statutory only|no policy|no plans|never\b|not used|not measured)", re.I)

def ruled_order(qid):
    """RULED lean->generous ordering from the spike entry (2026-07-15). Authored verbatim
    against live option strings and reviewed by David — never inferred by heuristic.
    'Not applicable'/'Don't know' are deliberately EXCLUDED: they are N/A skips, not levels,
    so the re-pair leaves those orgs' values untouched (it only reorders values present in
    the ordering). Precedence: ruled key > option_order() inference > NOMINAL (hard gate)."""
    o = (ORD.get(qid) or {}).get("option_order")
    return list(o) if o else None

def lean_pole(qid, opts):
    """Kit rule 2 (Diff 7): the lean pole is SEMANTIC, never positional.
    Order: explicit worst_option key from the spike entry -> semantic LEAN_RE -> HARD ERROR.
    A prevalence target_share is the share NOT on this pole."""
    wo = (ORD.get(qid) or {}).get("worst_option")
    if wo:
        for o in opts:
            if o.strip().lower() == str(wo).strip().lower():
                return o
        for o in opts:                       # tolerant contains-match for keyed poles
            if str(wo).strip().lower() in o.strip().lower():
                return o
        raise ValueError("worst_option %r not found in options for %s" % (wo, qid))
    for o in opts:
        if LEAN_RE.match(o):
            return o
    return None

def clamp01(x):
    return max(0.0, min(1.0, x))

def canon_industry(ind):
    """B2 silent-failure guard: explicit industry_canon map, never canon()'s prefix logic
    (which drops 6 of 14 to 'Other'). Accepts BOTH forms: the 158 real personas carry the
    LONG label ('Retail & Consumer Goods' = a map key); the 62 authored carry the SHORT
    canonical ('Retail' = a map value). Keying on the map alone silently flattened 60 of
    the 62 to 'Other'. Always returns the SHORT canonical, which is what the tilt tables
    and the legacy SECTOR_TILT are keyed on."""
    m = CFG.get("industry_canon") or {}
    if ind in m:
        return m[ind]
    if ind in set(m.values()):
        return ind
    return "Other"

def maturity_assign(qid, entry, rows, prof, lat):
    """Keyed-gradient mechanism (r3s2, GENERALISED r3sw2): per-org option assignment
    keyed on a declared profile attribute. entry fields:
      key: profile attribute ("HR_Maturity" default; "Industry" -> canon_industry)
      anchors {band: positive_pct} + positive_option + remainder_options +
        remainder_ratio {band: [a,b]}   — the positive/remainder form, OR
      band_distributions {band-or-_default: {option: pct}} — full per-band dists
      within_band: "hash" (default — the Step-2 maturity ruling) | "latent"
        (sector-keyed ordered metrics: the coherence spine, r3sw1 G10 lesson)
      sector_gate {exclude_industries:[...]}: gated orgs dropped (absence).
    Deterministic: largest-remainder per band; within-band order per policy.
    Backward-compatible: the three maturity entries carry no key/within_band/
    band_distributions -> identical behaviour to the r3s2 original (asserted by
    the r3sw2 migration's backcompat check against live state)."""
    gate = entry.get("sector_gate") or {}
    excl = set(gate.get("exclude_industries") or [])
    key = entry.get("key", "HR_Maturity")
    def band(o):
        v = (prof.get(o) or {}).get(key)
        if key == "Industry":
            return canon_industry(v or "")
        return v or "Developing"
    def industry(o):
        return canon_industry((prof.get(o) or {}).get("Industry") or "")
    orgs = [o for o, _ in rows if not excl or industry(o) not in excl]
    wb = entry.get("within_band", "hash")
    def order_band(members):
        if wb == "latent":
            return sorted(members, key=lambda o: (-lat.get(o, 0.5),
                          hashlib.sha256((qid + "|" + o).encode()).hexdigest()))
        return sorted(members, key=lambda o: hashlib.sha256((qid + "|" + o).encode()).hexdigest())
    out = {}
    if entry.get("band_distributions"):
        bd = entry["band_distributions"]
        by_band = {}
        for o in orgs:
            by_band.setdefault(band(o), []).append(o)
        for b, members in by_band.items():
            dist = bd.get(b) or bd.get("_default")
            assert dist, "no band distribution for %r on %s (and no _default)" % (b, qid)
            members = order_band(members)
            raw = {l: p * len(members) / 100.0 for l, p in dist.items()}
            fl = {l: int(raw[l]) for l in raw}
            for l in sorted(raw, key=lambda l: (-(raw[l] - fl[l]), l))[: len(members) - sum(fl.values())]:
                fl[l] += 1
            i2 = 0
            for l in dist:
                for _ in range(fl[l]):
                    out[members[i2]] = l; i2 += 1
        return out
    pos, rem_opts = entry["positive_option"], entry["remainder_options"]
    for b in entry["anchors"]:
        members = order_band([o for o in orgs if band(o) == b])
        if not members:
            continue
        n = len(members)
        k = int(round(entry["anchors"][b] / 100.0 * n))
        ra, rb = entry["remainder_ratio"][b]
        rem = n - k
        ka = int(round(rem * ra / float(ra + rb)))
        for i, o in enumerate(members):
            out[o] = pos if i < k else (rem_opts[0] if i < k + ka else rem_opts[1])
    return out


def load_profiles(paths):
    """B-ruling (1): accept a LIST artifact and key on org_id or source_org_id_live.
    seed_personas_220.json is a provenance-flagged list; only the 158 real rows carry
    org_id, the 62 authored carry source_org_id_live."""
    prof = {}
    for p in str(paths).split(","):
        p = p.strip()
        if not p:
            continue
        try:
            d = json.load(open(p if os.path.exists(p) else os.path.join(HERE, p), encoding="utf-8"))
        except FileNotFoundError:
            continue
        if isinstance(d, list):
            for r in d:
                key = r.get("org_id") or r.get("source_org_id_live")
                if key:
                    prof[str(key)] = r
        else:
            prof.update(d)
    return prof

def latent3(org_id, prof, rho=None):
    """Factor vector per org. TWO-FACTOR as ruled 2026-07-15: {G, S}. Name kept for call
    compatibility. All weights/encodings from persona_factor_config."""
    rho = RHO if rho is None else rho
    p = prof.get(org_id, {}) or {}
    enc  = CFG.get("ordinal_encode") or {}
    tilt = ((CFG.get("sector_tilts") or {}).get("normalised")) or {}
    own  = CFG.get("ownership_c") or {}
    damp = CFG.get("g_damper") or {}
    sect = canon_industry(p.get("Industry"))

    core = 0.45 * FTE_RANK.get(p.get("FTE_Band"), 0.4) + 0.30 * HR_RANK.get(p.get("HR_Maturity"), 0.45)
    well = (tilt.get("sector_well_tilt") or {}).get(sect, 0.5)
    gov  = (tilt.get("sector_gov_tilt")  or {}).get(sect, 0.5)
    pay  = (tilt.get("sector_pay_tilt")  or {}).get(sect, 0.5)
    bud  = (enc.get("Budget_Flexibility")  or {}).get(p.get("Budget_Flexibility"), 0.5)
    reg  = (enc.get("Regulatory_Pressure") or {}).get(p.get("Regulatory_Pressure"), 0.5)
    aud  = (enc.get("Audit_Scrutiny")      or {}).get(p.get("Audit_Scrutiny"), 0.5)
    risk = (enc.get("Risk_Appetite")       or {}).get(p.get("Risk_Appetite"), 0.5)
    front = (p.get("Workforce_Frontline_%") or 0) / 100.0
    union = (p.get("Workforce_Unionised_%") or 0) / 100.0
    gd = ((damp.get("Recent_Shock") or {}).get(p.get("Recent_Shock"), 0.0)
          + (damp.get("Direction_of_Travel") or {}).get(p.get("Direction_of_Travel"), 0.0))
    cbump = (own.get(p.get("Ownership_Type")) or {}).get("c_bump", 0.0)

    G = rho * core + (1 - rho) * (0.35 * bud + 0.20 * well - 0.12 * front + gd)
    # TWO-FACTOR MODEL (ruled 2026-07-15). M and C are merged into S (structure /
    # competitiveness). Rationale: G4 failed on COVERAGE, not tuning — Incentives has only
    # 2 of 23 metrics the re-pair can move (9%), so a separate C factor cannot express
    # itself and its pairs (Benefits x Incentives, Governance x Incentives) are exactly the
    # ones that collapse. Merge = average the two structure-side enrichment terms, so both
    # signals (regulatory/audit/gov-tilt AND pay-tilt/risk/ownership) survive at scale.
    _M = 0.30 * reg + 0.20 * aud + 0.15 * gov + 0.10 * union
    _C = 0.25 * pay + 0.20 * risk + cbump - 0.08 * union
    S = rho * core + (1 - rho) * 0.5 * (_M + _C)
    return {k: clamp01(v + jitter(org_id, k)) for k, v in (("G", G), ("S", S))}

def gates_for(org_id, prof):
    """B3 — gate = MASK (§9.4). Removes impossible cases only; never sets a share."""
    p = prof.get(org_id, {}) or {}
    o = p.get("Ownership_Type"); sect = canon_industry(p.get("Industry"))
    return {
        "ltip":  bool(((CFG.get("ownership_c") or {}).get(o) or {}).get("ltip_gate")),
        "shift": (p.get("Workforce_Shift_%") or 0) > 20,
        "tronc": sect in ("Hospitality", "Retail") and (p.get("Workforce_Frontline_%") or 0) > 40,
        "car":   o == "Partnership / LLP" or sect in ("Financial Services", "Professional Services"),
    }

# Two-factor merge map: the factor_map still says M/C; both are the structure factor now.
FACTOR_MERGE = {"M": "S", "C": "S", "G": "G", "S": "S"}

def factor_of(qid, meta):
    """B2 — factor per metric: explicit metric_factor wins, else subpower_factor.
    M and C are merged to S under the two-factor ruling (2026-07-15)."""
    mf = (FMAP.get("metric_factor") or {}).get(qid)
    if not mf:
        sp = (meta.get(qid) or {}).get("sub_power")
        mf = (FMAP.get("subpower_factor") or {}).get(sp, "G")
    return FACTOR_MERGE.get(mf, "G")

def spike_mode(qid):
    """B4 — hold_from_marginal routes latent-only via mode_effective (David ruling, 15 rows)."""
    s = SPIKES.get(qid) or {}
    if s.get("hold_from_marginal"):
        return s.get("mode_effective", "context")
    return s.get("mode")

def clean_marginal_ids():
    """The tune set: mode==prevalence AND not held. Demoted/held rows never tune."""
    return [q for q in SPIKES if spike_mode(q) == "prevalence"]
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

STAMP = "2026-07-15 16:30:00"

def reseed(db, profiles, meta_path, write=False, confirmed=False):
    """Three-factor reseed (Diff 9). Per metric: route on the spike mode, re-pair onto the
    metric's OWN factor (G/M/C), layer level distributions. Append-only write discipline
    (Diff 7/8 house pattern): snapshot the prior value into answers_history, DELETE the
    answers row, INSERT the corrected value. Marginals only move where an anchor says so."""
    c=sqlite3.connect(db); cur=c.cursor()
    meta=json.load(open(meta_path)); rewq=set(meta)
    prof=load_profiles(profiles)
    allorgs=[o for (o,) in cur.execute("select distinct org_id from answers where snapshot_id=1")]
    lat3={o:latent3(o,prof) for o in allorgs}

    reassignments=0; touched_q=0; skipped_nominal=0
    modes=defaultdict(int); marg_hits=[]; nominal_rejects=[]
    plan=[]  # (question_id, matrix_row_id, [(org, old, new)])
    cur.execute("select question_id,matrix_row_id,org_id,value from answers where snapshot_id=1")
    cells=defaultdict(list)
    for q,mr,o,v in cur.fetchall():
        if q in rewq and v: cells[(q,mr)].append((o,v))

    for (q,mr),rows in sorted(cells.items()):
        fac=factor_of(q,meta)
        lat={o:(lat3.get(o) or {}).get(fac,0.5) for o,_ in rows}
        cur_map=dict(rows)
        # route label derives from the GENERATED file (spike_mode/SPIKES are dead inputs)
        if q in MARG.get("marginals", {}): mode="marginal"
        elif q in MARG.get("floors", {}): mode="floor"
        elif q in MARG.get("context", {}): mode="context"
        else: mode="unspiked"
        obs=[v for _,v in rows]
        newmap=None

        if (q in MARG.get("maturity_gradients", {})) and not mr:
            # r3s2: maturity-gradient reshape — survives future reseeds by re-derivation
            # (band-conditional structure would drift under plain context re-pairing).
            newmap = maturity_assign(q, MARG["maturity_gradients"][q], rows, prof, lat)
            modes["maturity_gradient"] += 1

        elif (q in MARG.get("marginals", {})) and not mr:
            # DIFF-3 MARGINAL BRANCH (ruled 2026-07-16): targets come from generated_marginals.json
            # (Diff-2 David-approved final table); orderings from ruled_orderings.json (ruled) or
            # option_order() inference. LEAN-SIDE semantics: positive_from generalises the lean
            # pole to "all rungs below positive_from"; absent -> lean side = first rung only
            # (legacy behaviour, asserted default for 33 of 37 rows at generation).
            entry = MARG["marginals"][q]
            tgt = float(entry["target_share"])
            ordq = ruled_order(q) or option_order(meta[q].get("options","") or sorted(set(obs)), meta[q].get("text",""))
            wo = (ORD.get(q) or {}).get("worst_option")
            lean_side = pos_side = None
            if ordq:
                rank = {o:i for i,o in enumerate(ordq)}
                ordr = [(o,v) for o,v in rows if v in rank]      # NA/DK values absent from the ordering stay untouched
                pf = entry.get("positive_from")
                if pf:
                    assert pf in ordq, "positive_from %r not in ordering for %s" % (pf, q)
                    cut = ordq.index(pf)
                    lean_side = ordq[:cut]; pos_side = ordq[cut:]
                else:
                    lean_side = ordq[:1]; pos_side = ordq[1:]
            elif wo:
                # multi-select marginal (worst_option pattern): lean = the terminal combo;
                # positives = every other OBSERVED combo (per-option mix untouched).
                vals = sorted({v for _,v in rows if v})
                lean_lab = next((o for o in vals if o.strip().lower()==str(wo).strip().lower()), None)
                assert lean_lab is not None, "worst_option %r not observed for %s" % (wo, q)
                ordr = [(o,v) for o,v in rows if v]
                lean_side = [lean_lab]; pos_side = [v for v in vals if v != lean_lab]
                rank = {lean_lab: 0}
                rank.update({v: 1+i for i,v in enumerate(pos_side)})
            else:
                raise AssertionError("ORDERINGS-REQUIRED (engine): marginal %s has no ruled ordering, "
                                     "no worst_option, and none inferable" % q)
            if len(ordr) >= 5:
                n = len(ordr); pos_n = int(round(tgt*n)); lean_n = n - pos_n
                curc = defaultdict(int)
                for _,v in ordr: curc[v]+=1
                def _apportion(total, opts_):
                    base = {o: curc.get(o,0) for o in opts_}
                    tot = sum(base.values())
                    if tot == 0:
                        base = {o: 1 for o in opts_}; tot = len(opts_)
                    raw = {o: total*base[o]/tot for o in opts_}
                    fl = {o: int(raw[o]) for o in opts_}
                    for o in sorted(opts_, key=lambda o: -(raw[o]-fl[o]))[: total - sum(fl.values())]:
                        fl[o] += 1
                    return fl
                b5 = (B5.get("applied") or {}).get(q)
                def _ruled_apportion(total, shares):
                    # B5 (Diff 10): within-side mix set by RULED band shares, largest remainder.
                    raw = {o: total*shares.get(o,0.0) for o in shares}
                    fl = {o: int(raw[o]) for o in shares}
                    for o in sorted(shares, key=lambda o: -(raw[o]-fl[o]))[: total - sum(fl.values())]:
                        fl[o] += 1
                    return fl
                ms = []
                if b5 and b5.get("side") == "two-sided":
                    for o,k in _ruled_apportion(lean_n, b5["lean_shares"]).items(): ms += [o]*k
                else:
                    for o,k in _apportion(lean_n, lean_side).items(): ms += [o]*k
                if b5:
                    for o in b5["positive_shares"]:
                        assert o in pos_side or b5["positive_shares"][o] == 0.0, \
                            "B5 band %r not on the positive side of %s" % (o, q)
                    for o,k in _ruled_apportion(pos_n, b5["positive_shares"]).items(): ms += [o]*k
                else:
                    for o,k in _apportion(pos_n, pos_side).items():  ms += [o]*k
                ms = sorted(ms, key=lambda v: rank[v])
                # deterministic jitter tiebreak (B5 wiring rule 5): identical-factor orgs must not tie
                who = sorted((o for o,_ in ordr),
                             key=lambda o: (lat.get(o,0.5), hashlib.sha256((q+"|"+o).encode()).hexdigest()))
                newmap = dict(zip(who, ms))
                ach = sum(1 for v in newmap.values() if v not in lean_side) / n
                marg_hits.append({"qid": q, "grade": entry.get("grade",""), "target": tgt,
                                  "achieved": round(ach,4), "dev": round(abs(ach-tgt),4),
                                  "positive_from": entry.get("positive_from") or ""})
                modes["prevalence"] += 1

        if newmap is None:
            # context / floor / held / unspiked -> latent-only monotone re-pair on the factor.
            opts=meta[q].get("options","") or sorted({v for _,v in rows})
            order=ruled_order(q) or option_order(opts, meta[q].get("text",""))
            if not order:
                skipped_nominal+=1; continue
            rank={opt:i for i,opt in enumerate(order)}
            ordr=[(o,v) for o,v in rows if v in rank]
            if len(ordr)<5: continue
            ms=sorted((v for _,v in ordr), key=lambda v: rank[v])
            who=sorted((o for o,_ in ordr), key=lambda o: lat.get(o,0.5))
            newmap=dict(zip(who,ms))
            if not mr: modes[mode]+=1

        changes=[(o,cur_map.get(o),nv) for o,nv in newmap.items() if cur_map.get(o)!=nv]
        if changes:
            touched_q+=1; reassignments+=len(changes)
            plan.append((q,mr,changes))

    if not (write and confirmed):
        return {"applied":False,"touched_questions":touched_q,"reassignments":reassignments,
                "skipped_nominal":skipped_nominal,"modes":dict(modes),
                "marginals":{"n":len(marg_hits),"max_dev":max([m["dev"] for m in marg_hits] or [0])},
                "nominal_rejects":sorted(set(nominal_rejects))}

    # ---- APPLY: append-only (history snapshot -> delete -> insert) ----
    cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    def book_hash():
        h=hashlib.sha256()
        for r in cur.execute("select org_id,question_id,matrix_row_id,value from answers "
                             "where question_id not in (%s) order by org_id,question_id,matrix_row_id"
                             % ",".join("?"*len(rewq)), tuple(rewq)):
            h.update(("|".join(str(x) for x in r)+"\n").encode())
        return h.hexdigest()
    h0=book_hash()
    n=0
    for q,mr,changes in plan:
        for o,old,new in changes:
            cur.execute("insert into answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                        "values (?,1,?,?,?,?)",(o,q,mr or "",old,STAMP))
            cur.execute("delete from answers where org_id=? and snapshot_id=1 and question_id=? "
                        "and ifnull(matrix_row_id,'')=?",(o,q,mr or ""))
            cur.execute("insert into answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                        "values (?,1,?,?,?,?)",(o,q,mr or "",new,STAMP))
            cur.execute("insert into answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                        "values (?,1,?,?,?,?)",(o,q,mr or "",new,STAMP))
            n+=1
    c.commit(); cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert book_hash()==h0, "NON-REWARD BOOK MOVED — restore lumi.db.bak_pre_diff9_20260715"
    return {"applied":True,"cells_written":n,"touched_questions":touched_q,
            "reassignments":reassignments,"skipped_nominal":skipped_nominal,"modes":dict(modes),
            "marginals":{"n":len(marg_hits),"max_dev":max([m["dev"] for m in marg_hits] or [0])},
            "nominal_rejects":sorted(set(nominal_rejects)),"non_reward_book":"hash-identical"}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="lumi.db"); ap.add_argument("--profiles",default="org_profiles.json,org_profiles_inferred.json")
    ap.add_argument("--meta",default="rew_live_meta.json")
    ap.add_argument("--write",action="store_true"); ap.add_argument("--confirmed-by-david",dest="confirmed",action="store_true")
    a=ap.parse_args()
    r=reseed(a.db,a.profiles,a.meta,a.write,a.confirmed)
    print(json.dumps(r,indent=2))
