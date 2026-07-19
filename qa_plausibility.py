# -*- coding: utf-8 -*-
"""qa_plausibility.py — plausibility triage + the FREEZE GATE for active reward metrics.

Checks A/B and Check C's structural flags are triage (NOT pass/fail). Check C's
freeze enforcement is a GATE since Diff 12 (it existed correct but dark — never
wired into the write-time suite; run_gates.sh now runs it as gate 11):

  Check A  Matrix flatness   — eligibility-style matrices whose levels barely cascade.
  Check B  Coherence outliers — ordered selects whose generosity ignores the latent spine.
  Check C  Structural flags (triage) + FREEZE ENFORCEMENT (gate, tiered per David's
           ruling 2026-07-18):
             tier 1  settled-frozen (= frozen_targets.json keys, the single source):
                     hard FAIL on any per-option drift > 0.001 — hand-ruled, immovable.
             tier 2  register marginals (generated_marginals.json): hard FAIL only on
                     achieved-vs-target drift > 5pp — they keep ±4ppt reshape freedom.
           Exit status 1 on any hard fail (run_gates treats nonzero rc as gate FAIL).

Honours LUMI_DB (same bug class as the qa_engine_audit hardcoded-live-db fix): the
gate validates the SAME db the suite targets, never implicitly live.

Reuses reseed_engine.latent() and reseed_engine.option_order() — generosity is ranked
by option_order (the same ordering the reseed used), NEVER array position (position-based
ranking scores the settled-frozen EAP/FINWELL/sick-pay metrics backwards — a false positive).

Run:  python3 qa_plausibility.py
"""
import sqlite3, json, os, re, sys
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reseed_engine import latent, option_order, canon_industry

DB = os.environ.get("LUMI_DB") or "lumi.db"   # honour the suite's target db (Diff 12)
SNAP = 1
_ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- authoritative anchor sets (don't flag these; they have signed placement) ----
# SINGLE SOURCE (Diff 12 reconciliation): frozen_targets.json keys ARE the settled-frozen
# set. qa_reseed.py derives its SETTLED from the same file; neither script hardcodes it.
# Missing file is FATAL — a silent {} fallback would put the freeze gate back in the dark.
FROZEN = json.load(open(os.path.join(_ROOT, "frozen_targets.json")))
SETTLED = set(FROZEN)
SETTLED_TOL = 0.001   # tier 1: hand-ruled/immovable (qa_reseed settled_tol)
MARGINAL_FAIL = 0.05  # tier 2: register marginals fail only beyond 5pp (±4ppt reshape freedom)
# register marginal targets + orderings (tier 2), same artifacts the reseed engine reads
_GEN = json.load(open(os.path.join(_ROOT, "generated_marginals.json")))
MARG = _GEN["marginals"]
RDIST = _GEN.get("ruled_distributions") or {}   # Diff 15: full-dist reshapes, tier-2b at the same 5pp line
MGRAD = _GEN.get("maturity_gradients") or {}    # r3s2: per-band anchors, tier-2c — checked PER MATURITY BAND
MS_INC = _GEN.get("multiselect_incidence") or {}  # r3sw8: per-option incidence over an applicable base, tier-2d
ORDS = json.load(open(os.path.join(_ROOT, "ruled_orderings.json")))["orderings"]
# register-anchored = the 14 REW26_* firewall family (id starts 'REW26_', NOT REW262_/REW263_)

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    try: prof.update(json.load(open(p)))
    except FileNotFoundError: pass

orgs = [o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=?", (SNAP,))]
lat = {o: latent(o, prof) for o in orgs}

Q = {r["id"]: r for r in c.execute(
    "SELECT id,text,type,options_json,sub_power FROM questions WHERE superpower='Reward' AND status='active'")}
REGISTER = {qid for qid in Q if qid.startswith("REW26_")}          # the 14 firewall-anchored
ANCHORED = SETTLED | REGISTER                                       # excluded from off-spine flags

def opt_labels(q):
    oj = q["options_json"]
    if oj and oj not in ("[]", ""):
        return [o["label"] for o in json.loads(oj) if not o.get("is_na")]
    if q["type"] == "yes_no":
        return ["No", "Yes"]
    return []

def num(v):
    m = re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group()) if m else None

def short(t, n=44): return (t or "")[:n]

# ============================================================ CHECK A — matrices ==
def check_a():
    SEN = ["board_executive","director","head_of","senior_manager","manager",
           "supervisor_team_leader","frontline_individual_contributor"]
    def prefix_ok(seq):
        seen0 = False
        for s in seq:
            if s == 0: seen0 = True
            elif s == 1 and seen0: return False
        return True
    rows = []
    for qid, q in Q.items():
        if q["type"] != "matrix":
            continue
        grid = defaultdict(dict)
        for org, mr, v in c.execute(
            "SELECT org_id,matrix_row_id,value FROM answers WHERE question_id=? AND snapshot_id=? AND matrix_row_id!='' AND value!=''",
            (qid, SNAP)):
            grid[org][mr] = v
        if len(grid) < 2:
            continue
        sample = [v for d in grid.values() for v in d.values()][:50]
        elig = bool(sample) and sum(1 for v in sample if str(v).strip().lower() in ("yes", "no")) >= 0.8 * len(sample)
        if not elig:
            continue  # numeric %-opportunity / positioning: coherence is company-axis (G6), not Check A
        levels = [l for l in SEN if any(l in d for d in grid.values())]
        td = bu = tot = 0; xs = []; ys = []
        for o, d in grid.items():
            seq = [1 if str(d.get(l, "")).strip().lower() == "yes" else (0 if d.get(l) else None) for l in levels]
            seq = [s for s in seq if s is not None]
            if not seq: continue
            tot += 1; td += prefix_ok(seq); bu += prefix_ok(seq[::-1])
            if o in lat: xs.append(lat[o]); ys.append(sum(seq))
        mono = max(td, bu) / tot if tot else 1.0
        corr = float(np.corrcoef(xs, ys)[0, 1]) if len(set(ys)) > 1 else 1.0
        direction = "bottom-up" if bu > td else "top-down"
        flag = mono < 0.95 or corr < 0.30
        rows.append((mono, qid, direction, corr, flag, short(q["text"])))
    rows.sort()
    print("\n" + "=" * 92)
    print("CHECK A — MATRIX COHERENCE   (direction-aware; healthy: monotonicity ≥0.95 AND depth×latent >0.30)")
    print("  eligibility (yes/no) matrices only; flag = either property fails. numeric/%-opportunity -> G6 (company-axis).")
    print("=" * 92)
    print("  %-7s %-10s %-8s %-5s %s" % ("mono", "direction", "depthxL", "flag", "metric"))
    flagged = 0
    for mono, qid, direction, corr, flag, txt in rows:
        if flag: flagged += 1
        print("  %6.3f  %-10s %+7.3f %-5s %s" % (mono, direction, corr, "FLAG" if flag else "", txt))
    return flagged

# ====================================================== CHECK B — coherence ==
def check_b():
    rows = []
    for qid, q in Q.items():
        if q["type"] not in ("single_select", "yes_no"):
            continue
        labels = opt_labels(q)
        order = option_order(labels, q["text"])
        if not order:
            continue  # nominal/unordered — can't rank generosity (correct: not array position)
        rank = {o: i for i, o in enumerate(order)}
        xs, ys = [], []
        for org, v in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND snapshot_id=? AND matrix_row_id='' AND value!=''",
            (qid, SNAP)):
            if v in rank and org in lat:
                xs.append(lat[org]); ys.append(rank[v])
        if len(xs) < 20 or len(set(ys)) < 2:
            continue
        corr = float(np.corrcoef(xs, ys)[0, 1])
        rows.append((corr, qid, len(xs), qid in ANCHORED, short(q["text"])))
    rows.sort()
    allc = np.array([r[0] for r in rows])
    unanchored = [r for r in rows if not r[3]]
    print("\n" + "=" * 92)
    print("CHECK B — COHERENCE OUTLIERS   (latent vs option_order generosity; healthy ≳+0.3, suspect <0)")
    print("  ranked ascending; most-negative = most off-spine. anchored (settled-frozen + 14 register) excluded from flags.")
    print("  median corr (all %d ordered): %+.3f   |   anchored excluded: %d" % (len(allc), np.median(allc), len(rows) - len(unanchored)))
    print("=" * 92)
    print("  %-7s %-5s %s" % ("corr", "n", "metric (unanchored triage — bottom 15)"))
    for corr, qid, n, _, txt in unanchored[:15]:
        print("  %+6.3f  %-5d %s" % (corr, n, txt))
    return sum(1 for r in unanchored if r[0] < 0)

# ====================================================== CHECK C — marginals ==
def achieved_share(qid, q, vals):
    """Achieved positive share for a register marginal, mirroring reseed_engine's
    marginal branch exactly: scope = values in the ordering (NA/DK untouched);
    lean side = rungs below positive_from (absent -> first rung only, the legacy
    default); worst_option multi-selects: lean = that exact combo, scope = non-empty."""
    entry = MARG[qid]
    tgt = float(entry["target_share"])
    o = (ORDS.get(qid) or {}).get("option_order")
    wo = (ORDS.get(qid) or {}).get("worst_option")
    if not o and not wo:
        o = option_order(opt_labels(q), q["text"])
    if o:
        pf = entry.get("positive_from")
        cut = o.index(pf) if pf else 1
        lean = set(o[:cut]); scope = set(o)
        inscope = [v for v in vals if v in scope]
        if len(inscope) < 5:               # engine skips reshape below 5 in-scope
            return None, tgt
        return sum(1 for v in inscope if v not in lean) / len(inscope), tgt
    if wo:
        inscope = [v for v in vals if v]
        if len(inscope) < 5:
            return None, tgt
        lean_lab = str(wo).strip().lower()
        return sum(1 for v in inscope if v.strip().lower() != lean_lab) / len(inscope), tgt
    return None, tgt

def check_c():
    flags = []
    hard = []          # freeze-gate failures (tiered) — nonzero exit
    t1_max = 0.0; t2_max = 0.0; t2_n = 0
    for qid, q in Q.items():
        if q["type"] not in ("single_select", "yes_no", "multi_select"):
            continue
        vals = [v for (v,) in c.execute(
            "SELECT value FROM answers WHERE question_id=? AND snapshot_id=? AND matrix_row_id='' AND value!=''",
            (qid, SNAP))]
        rawcnt = defaultdict(int)                       # per-VALUE dist (matches frozen_targets format)
        for v in vals: rawcnt[v] += 1
        raw = {k: v / len(vals) for k, v in rawcnt.items()} if vals else {}
        if q["type"] == "multi_select":
            n = len(vals); cnt = defaultdict(int)
            for v in vals:
                for tok in (x.strip() for x in v.split(";") if x.strip()): cnt[tok] += 1
            labels = opt_labels(q)
            dist = {l: cnt.get(l, 0) / n for l in labels} if n else {}
        else:
            n = len(vals); cnt = defaultdict(int)
            for v in vals: cnt[v] += 1
            labels = opt_labels(q) or list(cnt)
            dist = {l: cnt.get(l, 0) / n for l in labels} if n else {}
        if n < 20 or not dist:
            continue
        anchored = qid in ANCHORED
        tag = "anchored" if anchored else "review"
        nonna = {k: v for k, v in dist.items()}
        top = max(nonna.values()); zeros = [k for k, v in nonna.items() if v == 0]
        spread = top - min(nonna.values())
        if top > 0.92:
            flags.append((top, "dominant", qid, tag, "%s %.0f%%" % (short(max(nonna, key=nonna.get), 22), top * 100)))
        if zeros and q["type"] != "multi_select":
            flags.append((1.0, "zero-opt", qid, tag, "%d option(s) at 0%%: %s" % (len(zeros), short("; ".join(zeros), 26))))
        if len(nonna) >= 3 and spread < 0.12 and q["type"] != "multi_select":
            flags.append((0.5, "uniform", qid, tag, "%d opts within %.0fpp" % (len(nonna), spread * 100)))
        # ---- FREEZE ENFORCEMENT (the gate; tiered per David's ruling 2026-07-18) ----
        if qid in FROZEN:
            sgn = FROZEN[qid].get("dist", {})
            drift = max((abs(raw.get(k, 0) - sgn.get(k, 0)) for k in sgn), default=0)
            t1_max = max(t1_max, drift)
            if drift > SETTLED_TOL:
                hard.append((drift, "FROZEN-DRIFT", qid,
                             "%.2fpp vs frozen_targets.json (tol %.1fpp — settled is immovable)"
                             % (drift * 100, SETTLED_TOL * 100)))
        elif qid in MGRAD:
            e = MGRAD[qid]
            key = e.get("key", "HR_Maturity")
            def _band(org):
                v = (prof.get(org) or {}).get(key)
                return canon_industry(v or "") if key == "Industry" else (v or "?")
            rows_b = {}
            for org, v in c.execute(
                "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=? AND matrix_row_id='' AND value!=''",
                (qid, SNAP)):
                rows_b.setdefault(_band(org), []).append(v)
            # per-band fail line is QUANTUM-AWARE: largest-remainder can only place
            # counts within 1/n of the declared share, so small bands (n=7-10) breach
            # a flat 5pp by rounding alone (Charity n=8: 80% -> 6/8 = 7.5pp). Line =
            # max(5pp, 1/n) per band — achievability, not a loosening (n>=20 stays 5pp).
            worst = 0.0
            if e.get("band_distributions"):
                bd = e["band_distributions"]
                for b, vals in rows_b.items():
                    dist = bd.get(b) or bd.get("_default")
                    if not dist or len(vals) < 5: continue
                    cnt = {}
                    for v in vals: cnt[v] = cnt.get(v, 0) + 1
                    bw = max(abs(cnt.get(l, 0) / len(vals) - p / 100.0) for l, p in dist.items())
                    tol = max(MARGINAL_FAIL, 1.0 / len(vals))
                    worst = max(worst, bw - (tol - MARGINAL_FAIL))   # normalise: breach iff bw > tol
            else:
                pos = e["positive_option"]
                for b, tgt in e["anchors"].items():
                    vals = rows_b.get(b) or []
                    if len(vals) < 5: continue          # sub-floor band: no honest check
                    bw = abs(sum(1 for v in vals if v == pos) / len(vals) - tgt / 100.0)
                    tol = max(MARGINAL_FAIL, 1.0 / len(vals))
                    worst = max(worst, bw - (tol - MARGINAL_FAIL))
            t2_max = max(t2_max, worst); t2_n += 1
            if worst > MARGINAL_FAIL:
                hard.append((worst, "KEYED-BAND-DRIFT", qid,
                             "%.1fpp worst band vs anchors (fail >%.0fpp)" % (worst * 100, MARGINAL_FAIL * 100)))
        elif qid in RDIST:
            tgt = {k: v / 100.0 for k, v in RDIST[qid]["distribution"].items()}
            drift = max((abs(raw.get(k, 0) - t) for k, t in tgt.items()), default=0)
            t2_max = max(t2_max, drift); t2_n += 1
            if drift > MARGINAL_FAIL:
                hard.append((drift, "RULED-DIST-DRIFT", qid,
                             "%.1fpp worst option vs ruled distribution (fail >%.0fpp)"
                             % (drift * 100, MARGINAL_FAIL * 100)))
        elif qid in MS_INC:
            # tier 2d (r3sw8): INDEPENDENT per-option incidence over the applicable base.
            # `dist` is already per-option share of answering orgs (multi_select branch above);
            # options deliberately don't sum to 100. Per-option line = max(5pp, 1/n) — the same
            # quantum-aware achievability bound as tier-2c (r3sw2 ruled).
            e = MS_INC[qid]
            tol = max(MARGINAL_FAIL, 1.0 / n)
            worst = max((abs(dist.get(l, 0) - p / 100.0) for l, p in e["prevalences"].items()), default=0)
            t2_max = max(t2_max, worst - (tol - MARGINAL_FAIL)); t2_n += 1
            if worst > tol:
                hard.append((worst, "MS-INCIDENCE-DRIFT", qid,
                             "%.1fpp worst option vs declared incidence (fail >%.1fpp, n=%d)"
                             % (worst * 100, tol * 100, n)))
            term = e.get("terminal")
            if term:
                cooccur = sum(1 for v in vals
                              if term in (t.strip() for t in v.split(";"))
                              and any(t.strip() and t.strip() != term for t in v.split(";")))
                if cooccur:
                    hard.append((1.0, "MS-TERMINAL-COOCCUR", qid,
                                 "%d org(s) hold '%s' alongside a substantive option" % (cooccur, term)))
        elif qid in MARG:
            ach, tgt = achieved_share(qid, q, vals)
            if ach is not None:
                d = abs(ach - tgt); t2_max = max(t2_max, d); t2_n += 1
                if d > MARGINAL_FAIL:
                    hard.append((d, "MARGINAL-DRIFT", qid,
                                 "achieved %.3f vs target %.3f (%.1fpp; fail >%.0fpp)"
                                 % (ach, tgt, d * 100, MARGINAL_FAIL * 100)))
    # order: dominant first, then others, by severity (soft triage only)
    sev = {"dominant": 1, "zero-opt": 2, "uniform": 3}
    flags.sort(key=lambda f: (sev.get(f[1], 9), -f[0]))
    print("\n" + "=" * 92)
    print("CHECK C — STRUCTURAL MARGINAL FLAGS (triage)  +  FREEZE GATE (enforcing)")
    print("  triage (flag, not fail): dominant >92% · any option at 0% · near-uniform (≥3 opts within 12pp)")
    print("  gate: settled drift >0.1pp = FAIL · register-marginal drift >5pp = FAIL")
    print("=" * 92)
    print("  %-9s %-9s %-26s %s" % ("trigger", "tag", "metric", "detail"))
    for score, kind, qid, tag, detail in flags[:15]:
        print("  %-9s %-9s %-26s %s" % (kind, tag, short(Q[qid]["text"], 26), detail))
    # r3sw2: declared coherence pairs — child positive set must EQUAL the parent-derived set
    # r3sw8 selectors: child_any_answer (child set = orgs with ANY non-empty answer — conditioned
    # metrics) and parent_contains (parent set = orgs whose multi-select ticks the named option).
    # r3sw11 selectors: child_value_not (child substantive set = answers other than the metric's
    # own N/A label — token-aware so a multi-select terminal counts as N/A) and parent_value_in
    # (type sub-bases, e.g. SAYE-side = parent in {SAYE, Both}).
    for pair in (_GEN.get("coherence_pairs") or []):
        if pair.get("child_any_answer"):
            child_yes = {o for (o,) in c.execute(
                "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value!=''", (pair["child"],))}
        elif pair.get("child_value_not") is not None:
            nl = pair["child_value_not"]
            child_yes = {o for (o, v) in c.execute(
                "SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (pair["child"],))
                if nl not in (t.strip() for t in v.split(";"))}
        else:
            child_yes = {o for (o,) in c.execute(
                "SELECT org_id FROM answers WHERE question_id=? AND value=?", (pair["child"], pair["child_value"]))}
        if pair.get("parent_value_in") is not None:
            vals_in = pair["parent_value_in"]
            parent_yes = {o for (o,) in c.execute(
                "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value IN (%s)"
                % ",".join("?" * len(vals_in)), [pair["parent"]] + list(vals_in))}
        elif pair.get("parent_contains") is not None:
            tok = pair["parent_contains"]
            parent_yes = {o for (o, v) in c.execute(
                "SELECT org_id, value FROM answers WHERE question_id=?", (pair["parent"],))
                if tok in (t.strip() for t in (v or "").split(";"))}
        elif pair.get("parent_value_not") is not None:
            parent_yes = {o for (o,) in c.execute(
                "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value!=? AND value!=''",
                (pair["parent"], pair["parent_value_not"]))}
        else:
            parent_yes = {o for (o,) in c.execute(
                "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND value=?", (pair["parent"], pair["parent_value"]))}
        rel = pair.get("relation", "equal")
        ok = child_yes <= parent_yes if rel in ("subset", "subset_orgs") else child_yes == parent_yes
        if not ok:
            d = len(child_yes - parent_yes) if rel in ("subset", "subset_orgs") else len(child_yes ^ parent_yes)
            hard.append((1.0, "PAIR-INCOHERENCE", pair["child"],
                         "%d orgs violate %s(%s) vs %s (%s)" % (d, rel, pair.get("child_value", "any-answer"),
                                                                pair["parent"], pair.get("note", "")[:60])))
    # r3sw8 ARMING: a declared-incidence metric that is ACTIVE must actually carry its base.
    # Without this, losing the conditioned rows deactivates tier-2d silently (the n<20 skip)
    # and the subset pair passes vacuously on the empty set — the gate must fail closed instead.
    # Pre-write the question doesn't exist in Q, so live stays green until the ruled write.
    for qid in MS_INC:
        if qid in Q:
            nq = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND snapshot_id=? AND value!=''",
                           (qid, SNAP)).fetchone()[0]
            if nq < 20:
                hard.append((1.0, "MS-BASE-MISSING", qid,
                             "declared-incidence metric active with n=%d (<20) — conditioned base lost" % nq))
    print("\n  FREEZE GATE: settled checked %d (max drift %.3fpp) | register marginals checked %d (max drift %.2fpp)"
          % (len([q for q in FROZEN if q in Q]), t1_max * 100, t2_n, t2_max * 100))
    for score, kind, qid, detail in sorted(hard, key=lambda h: -h[0]):
        print("  ** %-14s %-26s %s" % (kind, qid, detail))
    return len(flags), hard

print("qa_plausibility — db=%s | %d active reward metrics | %d orgs | anchored: %d settled-frozen + %d register" % (
    DB, len(Q), len(orgs), len(SETTLED), len(REGISTER)))
fa = check_a(); fb = check_b(); fc, hard = check_c()
print("\n" + "-" * 92)
print("TRIAGE: %d matrices incoherent, %d metrics off-spine, %d marginal flags — review these first." % (fa, fb, fc))
if hard:
    print("FREEZE GATE: FAIL — %d hard failure(s) above. Frozen means frozen." % len(hard))
    sys.exit(1)
print("FREEZE GATE: PASS — settled within 0.1pp of frozen_targets.json; register marginals within 5pp of target.")
