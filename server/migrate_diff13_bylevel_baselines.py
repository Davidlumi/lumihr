# -*- coding: utf-8 -*-
"""migrate_diff13_bylevel_baselines.py — Diff 13: by-level matrix metric correction.

Replaces the shared multiplier ladder (regen_priors MATRIX_DRIVERS) with David's
EST-grade practitioner baselines (expert_baseline_by_level.json) for the ruled
metrics, applies the ruled sector gates as ROW DELETION (absence semantics,
never zero), co-treats the coherence companions, and flips questions.polarity
to neutral for the 11 verdict-suppressed by-level metrics.

NO NUMBERS IN CODE: ruled values come from expert_baseline_by_level.json;
structural tunables from diff13_derivation_rules.json (rulings 1-5, 2026-07-18).

Dry-run by default. Requires BOTH --write AND --confirmed-by-david to touch the
db. Honours LUMI_DB / --db. Append-only: history snapshot -> delete -> insert
(answers_history), non-touched book hash asserted identical, manifest emitted
to diff13_seed_manifest.csv (only-ruled-manifests rule).
"""
import argparse, csv, hashlib, json, os, re, sqlite3, statistics, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # the same generosity spine the seed uses

BASE = json.load(open(os.path.join(ROOT, "expert_baseline_by_level.json")))
RULES = json.load(open(os.path.join(ROOT, "diff13_derivation_rules.json")))

LEVELS = ["board_executive", "director", "head_of", "senior_manager",
          "manager", "supervisor_team_leader", "frontline_individual_contributor"]
LABELS = BASE["_meta"]["levels"]                       # same order, display labels
SNAP = 1

Q_PENSION = "REW_BEN_112"
Q_PENS_MAX = "REW_BEN_PENS_EMP_MAX_01"
Q_CAR = "fa0f46f6-61e3-41d1-a2d1-3e57483bb1cf"
Q_CAR_STATUS = "CAR_STATUS_01"
Q_BONUS = "REW_INC_111"
Q_BONUS_MAX = "323ffcf1-749b-43f3-bf34-1de6b8b1ca67"
Q_LTI = "REW_INC_133"
Q_LTI_MAX = "REW_INC_LTI_MAX_01"
Q_LTI_TYP = "REW_INC_LTI_VALUE_TYP_01"
TOUCHED = [Q_PENSION, Q_PENS_MAX, Q_CAR, Q_BONUS, Q_BONUS_MAX, Q_LTI, Q_LTI_MAX, Q_LTI_TYP]

def u01(*parts):
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF

def table_pick(table, p):
    for cut, val in table:
        if p < cut:
            return val
    return table[-1][1]

def num(v):
    m = re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group()) if m else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()

    c = sqlite3.connect(a.db); cur = c.cursor()

    prof = {}
    for p in ("org_profiles.json", "org_profiles_inferred.json"):
        prof.update(json.load(open(os.path.join(ROOT, p))))
    # seed population ONLY (rules _population): real signup orgs are never rewritten
    orgs = [o for (o,) in cur.execute(
        "SELECT DISTINCT org_id FROM answers WHERE snapshot_id=?", (SNAP,)) if o in prof]
    lat = {o: latent(o, prof) for o in orgs}
    def industry(o): return (prof.get(o) or {}).get("Industry", "") or ""
    def fte(o): return str((prof.get(o) or {}).get("FTE_Band", "") or "")
    def gated(o, prefixes): return any(industry(o).startswith(p) for p in prefixes)

    def pr_rank(pool, salt):
        """latent-anchored percentile in [0,1], deterministic hash tiebreak."""
        order = sorted(pool, key=lambda o: (lat.get(o, 0.5), u01(salt, o)))
        n = max(len(order) - 1, 1)
        return {o: i / n for i, o in enumerate(order)}

    def row_scale(subset, salt, lo, hi):
        """WITHIN-ROW ranked symmetric scale (latent-ordered, hash tiebreak): the
        subset's median scale is exactly (lo+hi)/2, so each row's achieved median
        pins to its baseline value no matter how participation thinned the row."""
        order = sorted(subset, key=lambda o: (lat.get(o, 0.5), u01(salt, o)))
        k = max(len(order) - 1, 1)
        return {o: lo + (hi - lo) * i / k for i, o in enumerate(order)}

    def rows_of(qid):
        return {(o, mr): v for o, mr, v in cur.execute(
            "SELECT org_id, matrix_row_id, value FROM answers "
            "WHERE question_id=? AND snapshot_id=? AND matrix_row_id!=''", (qid, SNAP))}

    before = {q: rows_of(q) for q in TOUCHED}
    new = {}          # qid -> {(org, level): value-str}

    # ---------------- pension typical (ruling 1: national ladder, all orgs) ----
    pcfg = RULES["pension_REW_BEN_112"]
    shape = BASE["metrics"]["pension_by_level"]["per_level"]      # label -> value
    floor = pcfg["statutory_floor"]
    floor_rows = {lv for lv, lab in zip(LEVELS, LABELS) if shape[lab] == floor}
    pr_p = pr_rank(orgs, Q_PENSION)
    offs = {o: table_pick(pcfg["offset_table"], pr_p[o]) for o in orgs}
    m = {}
    for o in orgs:
        for lv, lab in zip(LEVELS, LABELS):
            if lv in floor_rows:
                v = floor if offs[o] <= 1 else floor + (offs[o] - 1)
            else:
                v = max(floor, shape[lab] + offs[o])
            m[(o, lv)] = str(int(v))
    new[Q_PENSION] = m

    # ---------------- pension employer max (ruling 4: typical + headroom) ------
    hcfg = RULES["pens_emp_max_REW_BEN_PENS_EMP_MAX_01"]
    senior = set(hcfg["senior_levels"])
    m = {}
    for o in orgs:
        u = u01(Q_PENS_MAX, o)          # one draw per org — senior/rest headrooms coherent
        for lv in LEVELS:
            h = table_pick(hcfg["headroom_table_senior" if lv in senior else "headroom_table_rest"], u)
            m[(o, lv)] = str(int(num(new[Q_PENSION][(o, lv)]) + h))
    new[Q_PENS_MAX] = m

    # ---------------- car allowance (ruling 2: CAR_STATUS Yes population) ------
    ccfg = RULES["car_fa0f46f6"]
    car_pop = sorted(o for (o,) in cur.execute(
        "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND snapshot_id=? AND value='Yes'",
        (Q_CAR_STATUS, SNAP)) if o in prof)
    car_shape = BASE["metrics"]["car_allowance_by_level"]["per_level"]
    lo, hi = ccfg["scale_band"]; qm = ccfg["quantum_gbp"]
    # Manager row membership: exact count, INDEPENDENT hash — the offering minority
    # must not be the generous minority, or the row median drifts off baseline.
    n_mgr = int(round(ccfg["manager_row_prevalence"] * len(car_pop)))
    mgr_members = set(sorted(car_pop, key=lambda o: u01(Q_CAR, "mgr", o))[:n_mgr])
    m = {}
    for lv, lab in zip(LEVELS, LABELS):
        spec = car_shape[lab]
        if not spec["offered"]:
            continue                                       # off the benefit — NO row, never 0
        subset = sorted(mgr_members) if spec.get("low_prevalence") else car_pop
        sc = row_scale(subset, Q_CAR + "|" + lv, lo, hi)
        for o in subset:
            v = int(round(spec["value"] * sc[o] / qm) * qm)
            prev = m.get((o, LEVELS[LEVELS.index(lv) - 1])) if lv != LEVELS[0] else None
            if prev is not None:
                v = min(v, int(prev))
            m[(o, lv)] = str(v)
    new[Q_CAR] = m

    # ---------------- target bonus (gate + reshape; ruling per baseline) -------
    bcfg = RULES["bonus_REW_INC_111"]
    bshape = BASE["metrics"]["bonus_by_level"]["per_level"]
    b_before = before[Q_BONUS]
    b_answer = sorted({o for (o, _) in b_before if o in prof})
    b_pop = [o for o in b_answer if not gated(o, bcfg["gate_industries_prefix"])]
    # current level-participation proportions -> exact top-n by latent (nested down the
    # ladder: an org paying bonus at Supervisor also pays at Manager and above)
    cur_share = {lv: (len({o for (o, l) in b_before if l == lv}) / len(b_answer)) for lv in LEVELS}
    part_order = sorted(b_pop, key=lambda o: (-lat.get(o, 0.5), u01(Q_BONUS, "part", o)))
    participants = {lv: part_order[:int(round(cur_share[lv] * len(b_pop)))] for lv in LEVELS}
    blo, bhi = bcfg["scale_band"]
    bot = bcfg["bottom_two_rows"]
    m = {}
    for lv, lab in zip(LEVELS, LABELS):
        subset = participants[lv]
        base_v = bshape[lab]["value"]
        if lv in bot:
            j = bot[lv]
            # piecewise median-pinned draw min -> base -> max, latent-ordered within row
            order = sorted(subset, key=lambda o: (lat.get(o, 0.5), u01(Q_BONUS + "|" + lv, o)))
            k = max(len(order) - 1, 1)
            for i, o in enumerate(order):
                u = i / k
                v = (j["min"] + u * 2 * (base_v - j["min"])) if u < 0.5 \
                    else (base_v + (u - 0.5) * 2 * (j["max"] - base_v))
                v = max(j["min"], int(round(v)))
                prev = m.get((o, LEVELS[LEVELS.index(lv) - 1]))
                if prev is not None:
                    v = min(v, int(prev))
                m[(o, lv)] = str(v)
        else:
            sc = row_scale(subset, Q_BONUS + "|" + lv, blo, bhi)
            for o in subset:
                v = max(1, int(round(base_v * sc[o])))
                prev = m.get((o, LEVELS[LEVELS.index(lv) - 1])) if lv != LEVELS[0] else None
                if prev is not None:
                    v = min(v, int(prev))
                m[(o, lv)] = str(v)
    new[Q_BONUS] = m

    # ---------------- max bonus (ruling 4: gate-only + max>=target lift) -------
    mcfg = RULES["bonus_max_323ffcf1-749b-43f3-bf34-1de6b8b1ca67"]
    m = {}
    lifted = 0
    for (o, lv), v in before[Q_BONUS_MAX].items():
        if o not in prof:
            continue                       # real signup org — preserved in place, never rewritten
        if gated(o, mcfg["gate_industries_prefix"]):
            continue
        keep = num(v)
        tgt = num(new[Q_BONUS].get((o, lv), ""))
        if tgt is not None and keep is not None and keep < tgt:
            keep = tgt; lifted += 1
        m[(o, lv)] = str(int(keep)) if keep == int(keep) else str(keep)
    new[Q_BONUS_MAX] = m

    # ---------------- LTI eligibility (ruling 3: population 74, cliff) ---------
    lcfg = RULES["lti_REW_INC_133"]
    lti_yes_now = {o for (o,) in cur.execute(
        "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND snapshot_id=? AND value='Yes'",
        (Q_LTI, SNAP)) if o in prof}
    running = sorted(o for o in lti_yes_now
                     if not gated(o, lcfg["gate_industries_prefix"])
                     and not fte(o).startswith(lcfg["gate_sme_fte_band_prefix"]))
    rates = BASE["metrics"]["lti_eligibility_by_level"]["per_level"]
    r_board = rates[LABELS[0]]["value"] / 100.0
    r_dir = rates[LABELS[1]]["value"] / 100.0
    order = sorted(running, key=lambda o: (-lat.get(o, 0.5), u01(Q_LTI, o)))
    n_board = int(round(r_board * len(running)))
    n_dir = int(round(r_dir * len(running)))
    board_yes = set(order[:n_board]); dir_yes = set(order[:n_dir])   # Director-Yes ⊆ Board-Yes
    m = {}
    for o in orgs:
        for lv in LEVELS:
            yes = (lv == LEVELS[0] and o in board_yes) or (lv == LEVELS[1] and o in dir_yes)
            m[(o, lv)] = "Yes" if yes else "No"
    new[Q_LTI] = m

    # ---------------- LTI value companions (ruling 4: cliff-mask only) ---------
    for q in (Q_LTI_MAX, Q_LTI_TYP):
        m = {}
        for (o, lv), v in before[q].items():
            if lv == LEVELS[0] and o in board_yes: m[(o, lv)] = v
            elif lv == LEVELS[1] and o in dir_yes: m[(o, lv)] = v
        new[q] = m

    # ---------------- report: before/after per-level tables --------------------
    def table(qid, kind):
        rows = []
        for tag, data in (("before", before[qid]), ("after", new[qid])):
            per = []
            for lv in LEVELS:
                vs = [v for (o, l), v in data.items() if l == lv]
                if not vs: per.append(("—", 0)); continue
                if kind == "yesno":
                    y = sum(1 for v in vs if v == "Yes")
                    per.append(("%.1f%%Y" % (100 * y / len(vs)), len(vs)))
                else:
                    ns = [num(v) for v in vs if num(v) is not None]
                    per.append(("%g" % statistics.median(ns), len(ns)))
            rows.append((tag, per))
        return rows

    print("Diff 13 dry-run — db=%s | orgs=%d" % (a.db, len(orgs)))
    print("gate sets: bonus charity/public answerers removed=%d | bonus-max removed=%d | "
          "LTI running=%d (board_yes=%d, dir_yes=%d) | car population=%d" % (
        len(b_answer) - len(b_pop), len({o for (o, _) in before[Q_BONUS_MAX]}) -
        len({o for (o, _) in new[Q_BONUS_MAX]}), len(running), len(board_yes), len(dir_yes), len(car_pop)))
    KINDS = {Q_LTI: "yesno"}
    for qid in TOUCHED:
        print("\n== %s" % qid)
        for tag, per in table(qid, KINDS.get(qid, "num")):
            print("  %-6s " % tag + " | ".join("%s(n%d)" % pv for pv in per))
    print("\nbonus-max rows lifted to target (max>=target): %d" % lifted)

    # ---------------- asserts (before write) -----------------------------------
    med = lambda qid, lv: statistics.median(
        [num(v) for (o, l), v in new[qid].items() if l == lv and num(v) is not None])
    for lv, lab in zip(LEVELS, LABELS):
        assert med(Q_PENSION, lv) == BASE["metrics"]["pension_by_level"]["per_level"][lab], (lv, "pension median")
    for lv, lab in zip(LEVELS, LABELS):
        spec = BASE["metrics"]["car_allowance_by_level"]["per_level"][lab]
        if spec["offered"]:
            assert med(Q_CAR, lv) == spec["value"], (lv, "car median")
        else:
            assert not any(l == lv for (_, l) in new[Q_CAR]), (lv, "car N/A row leaked")
    for lv, lab in zip(LEVELS, LABELS):
        assert med(Q_BONUS, lv) == BASE["metrics"]["bonus_by_level"]["per_level"][lab]["value"], (lv, "bonus median")
    for (o, lv), v in new[Q_PENS_MAX].items():
        assert num(v) >= num(new[Q_PENSION][(o, lv)]), "max<typical"
    for (o, lv), v in new[Q_BONUS_MAX].items():
        t = new[Q_BONUS].get((o, lv))
        assert t is None or num(v) >= num(t), "bonusmax<target"
    assert {o for (o, _) in new[Q_CAR]} == set(car_pop), "car population != CAR_STATUS Yes-set"
    assert sum(1 for (o, l), v in new[Q_LTI].items() if v == "Yes" and l == LEVELS[0]) == n_board
    assert sum(1 for (o, l), v in new[Q_LTI].items() if v == "Yes" and l == LEVELS[1]) == n_dir
    assert not any(v == "Yes" for (o, l), v in new[Q_LTI].items() if l not in LEVELS[:2]), "LTI below-Director Yes"
    for q in (Q_BONUS, Q_BONUS_MAX):
        gates = RULES["bonus_REW_INC_111"]["gate_industries_prefix"]
        assert not any(gated(o, gates) for (o, _) in new[q]), "gated org kept bonus rows"
    for o in orgs:
        seq = [num(new[Q_PENSION][(o, lv)]) for lv in LEVELS]
        assert all(x >= y for x, y in zip(seq, seq[1:])), "pension ladder not monotone"
    print("asserts: medians pinned, max>=typical/target, N/A absences, gates clean, cliff clean, monotone — ALL PASS")

    delta = sum(len(new[q]) - len(before[q]) for q in TOUCHED)
    print("answers delta: %+d (car adds %+d; deletions: bonus family, LTI tails)" % (
        delta, len(new[Q_CAR]) - len(before[Q_CAR])))

    if not (a.write and a.confirmed):
        print("\n[dry-run] no writes. Pass --write --confirmed-by-david to apply.")
        return

    # ---------------- APPLY (history snapshot -> delete -> insert) -------------
    book_pre = hashlib.sha256(("".join(
        "%s|%s|%s|%s" % r for r in cur.execute(
            "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
            "WHERE question_id NOT IN (%s) ORDER BY org_id,question_id,matrix_row_id"
            % ",".join("?" * len(TOUCHED)), TOUCHED))).encode()).hexdigest()
    # real (non-seed) org rows on touched metrics are preserved IN PLACE: the delete is
    # seed-population-selective, and new[] never contains non-seed rows.
    real_rows_pre = {(q, o, lv): v for q in TOUCHED for (o, lv), v in before[q].items() if o not in prof}
    seed_ids = sorted(prof)
    hist = 0
    for q in TOUCHED:
        for (o, lv), v in before[q].items():
            if o not in prof:
                continue
            cur.execute("INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                        "VALUES (?,?,?,?,?,datetime('now'))", (o, SNAP, q, lv, v)); hist += 1
        cur.execute("DELETE FROM answers WHERE question_id=? AND snapshot_id=? AND matrix_row_id!='' "
                    "AND org_id IN (%s)" % ",".join("?" * len(seed_ids)), (q, SNAP, *seed_ids))
        for (o, lv), v in new[q].items():
            assert o in prof, "attempted to write a non-seed org row"
            cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                        "VALUES (?,?,?,?,?,datetime('now'))", (o, SNAP, q, lv, v))
    # polarity flip for the 11 verdict-suppressed by-level metrics (reversible)
    flips = 0
    for qid in RULES["verdict_suppression"]["metric_ids"]:
        cur.execute("UPDATE questions SET polarity='neutral' WHERE id=? AND polarity!='neutral'", (qid,))
        flips += cur.rowcount
    c.commit()
    book_post = hashlib.sha256(("".join(
        "%s|%s|%s|%s" % r for r in cur.execute(
            "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
            "WHERE question_id NOT IN (%s) ORDER BY org_id,question_id,matrix_row_id"
            % ",".join("?" * len(TOUCHED)), TOUCHED))).encode()).hexdigest()
    assert book_pre == book_post, "non-touched book changed!"
    real_rows_post = {(q, r[0], r[1]): r[2] for q in TOUCHED for r in cur.execute(
        "SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=? AND snapshot_id=? "
        "AND matrix_row_id!=''", (q, SNAP)) if r[0] not in prof}
    assert real_rows_post == real_rows_pre, "real-org rows on touched metrics changed!"
    with open(os.path.join(ROOT, "diff13_seed_manifest.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric_id", "rows_before", "rows_after", "action"])
        acts = {Q_PENSION: "baseline reshape (national ladder)", Q_PENS_MAX: "corollary typical+headroom",
                Q_CAR: "population align + baseline reshape", Q_BONUS: "sector gate + baseline reshape",
                Q_BONUS_MAX: "sector gate + max>=target lift", Q_LTI: "cliff + sector/SME gate",
                Q_LTI_MAX: "cliff-mask", Q_LTI_TYP: "cliff-mask"}
        for q in TOUCHED:
            w.writerow([q, len(before[q]), len(new[q]), acts[q]])
    print("APPLIED: history rows +%d | polarity flips %d | non-touched book hash-identical | "
          "manifest diff13_seed_manifest.csv written" % (hist, flips))

if __name__ == "__main__":
    main()
