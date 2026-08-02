#!/usr/bin/env python3
"""DIFF 9 (anchor seed + multi-factor latent) — DRY RUN. No writes, ever.
Simulates B2-B5 at the ruled rho=0.40 and reports the pre-approval numbers:
factor histograms, marginals-hit-target by grade, gate N/A counts vs
gate_baselines_ACTUAL_220, and the real G3 (size gradient) + G4 (coherence) gates
computed on the reseeded answers using qa_reseed's own definitions.
"""
import json, os, random, statistics, sys
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3
import reseed_engine as RE

# hardcoded-path class: honour LUMI_DB; default to the repo-root store resolved from
# __file__ (not cwd), so running from another directory cannot silently create a new DB.
_LUMI_DB = os.environ.get("LUMI_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "lumi.db")

DB = _LUMI_DB
PROFILES = "seed_personas_220.json"
META = "rew_live_meta.json"
TOL_TIGHT, TOL_SOFT = 0.04, 0.08          # A/B tight (qa_reseed G7 marginal_tol), C soft
NEG = {"no", "none", "not offered", "not provided", "not applicable", "neither",
       "statutory only", "no policy", "never", "not used", "not measured", "none / not offered"}

meta = json.load(open(META))
prof = RE.load_profiles(PROFILES)
c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True); c.row_factory = sqlite3.Row
orgs = {r["org_id"]: dict(r) for r in c.execute("SELECT * FROM orgs")}
tester = next((o for o, r in orgs.items() if r["name"] == "Tester"), None)
resp = [o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1") if o != tester]
rewq = set(meta)

# answers: {org: {qid: value}} for single-value reward cells
ans = defaultdict(dict)
cells = defaultdict(list)
for r in c.execute("SELECT question_id, org_id, matrix_row_id, value FROM answers WHERE snapshot_id=1"):
    if r["question_id"] in rewq and r["value"]:
        if not (r["matrix_row_id"] or ""):
            ans[r["org_id"]][r["question_id"]] = r["value"]
        cells[(r["question_id"], r["matrix_row_id"] or "")].append((r["org_id"], r["value"]))

LAT = {o: RE.latent3(o, prof) for o in resp}

def lean_of(qid, opts):
    """Kit rule 2 via the engine: explicit worst_option -> semantic LEAN_RE -> None (hard error)."""
    return RE.lean_pole(qid, opts)

# ============ B4: spike application (simulated) ============
report_rows = []
no_lean = []
applied = Counter()
new_ans = {o: dict(ans[o]) for o in resp}

for qid in sorted(SP := RE.SPIKES):
    mode = RE.spike_mode(qid)
    spec = RE.SPIKES[qid]
    rows = cells.get((qid, ""), [])
    if not rows:
        applied["no_rows"] += 1
        continue
    fac = RE.factor_of(qid, meta)
    lat = {o: LAT[o][fac] for o, _ in rows if o in LAT}
    obs = [v for _, v in rows]
    opts = sorted(set(obs))
    if mode != "prevalence":
        # context / floor / held -> latent-only: keep the multiset, monotone re-pair by factor.
        applied[mode] += 1
        continue
    lean = lean_of(qid, opts)
    if lean is None:
        no_lean.append(qid); applied["HARD_ERROR_no_lean_pole"] += 1
        continue
    tgt = spec["target_share"]                       # share NOT on the lean pole
    n = len(rows)
    pos_n = round(tgt * n)
    pos_opts = [o for o in opts if o != lean]
    cur_pos = Counter(v for v in obs if v != lean)
    tot_cur = sum(cur_pos.values()) or 1
    multiset = [lean] * (n - pos_n)
    for o in pos_opts:                                # positive mass split proportional to current
        multiset += [o] * round(pos_n * cur_pos.get(o, 0) / tot_cur)
    while len(multiset) < n: multiset.append(pos_opts[0] if pos_opts else lean)
    multiset = multiset[:n]
    rank = {lean: 0}
    for i, o in enumerate(pos_opts, 1): rank[o] = i
    ms = sorted(multiset, key=lambda v: rank[v])
    if spec.get("direction") == "preserve":
        # rarity is the signal: hit the share but do NOT tie to factor
        rr = random.Random(hashlib_seed := abs(hash(qid)) % (2**31))
        who = [o for o, _ in rows]; rr.shuffle(who)
    else:
        who = sorted((o for o, _ in rows), key=lambda o: lat.get(o, 0.5))
    newmap = dict(zip(who, ms))
    for o, v in newmap.items(): new_ans.setdefault(o, {})[qid] = v
    ach = sum(1 for v in newmap.values() if v != lean) / n
    tol = TOL_TIGHT if spec.get("grade") in ("A", "B") else TOL_SOFT
    report_rows.append({"qid": qid, "grade": spec.get("grade"), "direction": spec.get("direction"),
                        "target": tgt, "achieved": ach, "dev": abs(ach - tgt), "tol": tol,
                        "hit": abs(ach - tgt) <= tol, "n": n})
    applied["prevalence"] += 1

# ============ B2 full monotone re-pair (the reseed's core) ============
# CRITICAL: the spike step above only re-pairs the 59 prevalence metrics. The reseed
# ALSO monotone-re-pairs every other reward metric onto ITS factor. Without this the
# G3/G4 below measure live-single-latent pairing, not the three-factor reseed — and the
# error is not in a safe direction (Governance->M and Incentives->C should pull that pair
# toward corr(M,C), which a spike-only sim never applies).
repaired = 0
for (qid, mr), rows in cells.items():
    if mr:                                     # matrix cells re-pair per row, same rule
        pass
    if RE.spike_mode(qid) == "prevalence":
        continue                               # already reshaped+re-paired above
    opts = meta[qid].get("options", "") or sorted({v for _, v in rows})
    order = RE.option_order(opts, meta[qid].get("text", ""))
    if not order:
        continue                               # nominal: leave untouched (engine rule)
    rank = {o: i for i, o in enumerate(order)}
    ordr = [(o, v) for o, v in rows if v in rank]
    if len(ordr) < 5:
        continue
    fac = RE.factor_of(qid, meta)
    ms = sorted((v for _, v in ordr), key=lambda v: rank[v])
    who = sorted((o for o, _ in ordr), key=lambda o: LAT[o][fac] if o in LAT else 0.5)
    for o, v in zip(who, ms):
        if not mr:
            new_ans.setdefault(o, {})[qid] = v
    repaired += 1

# ============ B5: level distributions (simulated, layered on who-offers) ============
lvl_rows = []
for qid, spec in RE.LEVELS.items():
    rows = cells.get((qid, ""), [])
    if not rows: continue
    bands = spec["bands"]
    offerers = [o for o, v in rows if v and v.lower() not in NEG]
    if not offerers: continue
    fac = RE.factor_of(qid, meta)
    who = sorted(offerers, key=lambda o: LAT[o][fac] if o in LAT else 0.5)
    ms = []
    for b, share in bands.items(): ms += [b] * round(share * len(offerers))
    while len(ms) < len(who): ms.append(list(bands)[-1])
    lvl_rows.append({"qid": qid, "dimension": spec.get("dimension"), "offerers": len(offerers),
                     "bands": len(bands), "assigned": min(len(ms), len(who))})

# ============ QA ============
def richness(a, area):
    qs = [q for q in rewq if meta[q].get("sub_power") == area
          and meta[q].get("type") in ("boolean", "single_select", "yes_no", "multi_select")]
    pos = tot = 0
    for q in qs:
        v = a.get(q)
        if not v: continue
        tot += 1
        if v.lower() not in NEG: pos += 1
    return pos / tot if tot else None

print("=" * 78); print("DIFF 9 DRY RUN — rho = %.2f — NO WRITES" % RE.RHO); print("=" * 78)
print("\n--- B4 spike application ---")
for k, v in sorted(applied.items()): print("  %-28s %d" % (k, v))
if no_lean:
    print("  *** HARD ERROR (kit rule 2) — no semantic lean pole: %s" % no_lean)

print("\n--- marginals hit target, by grade (clean set) ---")
by_grade = defaultdict(list)
for r in report_rows: by_grade[r["grade"]].append(r)
for g in ("A", "B", "C"):
    rs = by_grade.get(g, [])
    if not rs: continue
    hit = sum(1 for r in rs if r["hit"])
    print("  grade %s: %2d rows | tol +-%.2f | HIT %2d/%2d | max dev %.4f | mean dev %.4f"
          % (g, len(rs), rs[0]["tol"], hit, len(rs), max(r["dev"] for r in rs),
             statistics.mean([r["dev"] for r in rs])))
miss = [r for r in report_rows if not r["hit"]]
print("  MISSES: %d" % len(miss))
for r in sorted(miss, key=lambda r: -r["dev"])[:8]:
    print("    %-26s grade %s target %.3f achieved %.3f dev %.4f (tol %.2f, n=%d)"
          % (r["qid"], r["grade"], r["target"], r["achieved"], r["dev"], r["tol"], r["n"]))

print("\n--- B2 full monotone re-pair ---")
print("  non-prevalence reward metrics re-paired onto their factor: %d" % repaired)

print("\n--- B5 level distributions ---")
print("  metrics with a within-offerer distribution applied: %d / %d" % (len(lvl_rows), len(RE.LEVELS)))
for r in lvl_rows[:4]:
    print("    %-22s %-16s offerers=%-4d bands=%d" % (r["qid"], r["dimension"], r["offerers"], r["bands"]))

print("\n--- gate N/A counts vs gate_baselines_ACTUAL_220 ---")
BASE = RE.CFG["gate_baselines_ACTUAL_220"]
G = [RE.gates_for(o, prof) for o in resp]
got = {"ltip_eligible": sum(1 for g in G if g["ltip"]), "shift_eligible": sum(1 for g in G if g["shift"]),
       "tronc_on": sum(1 for g in G if g["tronc"]), "car_eligible": sum(1 for g in G if g["car"])}
for k in ("ltip_eligible", "shift_eligible", "tronc_on", "car_eligible"):
    print("  %-16s computed %-4d baseline %-4d  %s" % (k, got[k], BASE[k], "OK" if got[k] == BASE[k] else "*** MIS-WIRED ***"))

print("\n--- G3 size gradient (qa_reseed definition: Benefits richness by FTE band, slope >= 0.10) ---")
band_order = ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]
for label, A in (("BEFORE (live)", ans), ("AFTER  (reseed)", new_ans)):
    by = defaultdict(list)
    for o in resp:
        b = (prof.get(o) or {}).get("FTE_Band"); r = richness(A[o], "Benefits")
        if b in band_order and r is not None: by[b].append(r)
    means = {b: statistics.mean(by[b]) for b in band_order if by[b]}
    slope = means.get("10,000+", 0) - means.get("50-249", 0)
    mono = all(means.get(band_order[i], 0) <= means.get(band_order[i + 1], 0) + 0.02
               for i in range(len(band_order) - 1) if band_order[i] in means and band_order[i + 1] in means)
    print("  %s slope %+.3f  monotonic %-5s  PASS %s" % (label, slope, mono, slope >= 0.10 and mono))
    print("      means:", {k: round(v, 3) for k, v in means.items()})

print("\n--- G4 coherence (cross-area richness corr, min_r 0.30, max_neg -0.10) ---")
try:
    import numpy as np
    areas = ["Benefits", "Governance", "Wellbeing", "Time Off", "Incentives"]
    for label, A in (("BEFORE (live)", ans), ("AFTER  (reseed)", new_ans)):
        mat = {a: [] for a in areas}
        for o in resp:
            sc = {ar: richness(A[o], ar) for ar in areas}
            if all(v is not None for v in sc.values()):
                for ar in areas: mat[ar].append(sc[ar])
        pairs = {}
        for i, X in enumerate(areas):
            for Y in areas[i + 1:]:
                pairs["%s x %s" % (X, Y)] = round(float(np.corrcoef(mat[X], mat[Y])[0, 1]), 3)
        worst = min(pairs.values())
        print("  %s worst_r %+.3f  PASS %s" % (label, worst, worst >= 0.30 and worst >= -0.10))
        print("      pairs:", pairs)
except ImportError:
    print("  numpy unavailable")
print("\nDRY RUN COMPLETE — no writes performed.")
