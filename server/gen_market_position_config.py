# -*- coding: utf-8 -*-
"""Auto-classify every live metric for the Market Position Engine (handover Part A).

For each of the ~206 live Reward metrics this sets FOUR fields by the Part A
ruleset, then writes the extended config + flags the risky subset for David's
Part B firewall review:

  class           Level | Provision | Practice | Design   (by MEANING, not measurement)
  type            numeric | binary | ordinal | categorical (the engine mechanic)
  direction       higher_is_better | lower_is_better | neutral | null(Approach)
  lens            attract | retain | engage | save        (from live signal_lenses; cosmetic)
  + domain-level `competitiveness` (all true except Governance)

The build proceeds on this auto-pass; David refines via hot-reload (pre-launch,
no gate). Priority of harm: direction (misleads) > competitiveness (skews the
headline) > class (gauge in/out) > lens (cosmetic). The Part B doc lists only the
flagged metrics with proposed values.

    python3 server/gen_market_position_config.py            # dry-run: print the pass
    python3 server/gen_market_position_config.py --write    # write data/market_position_config.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions          # noqa: E402
from aggregate import score_direction       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTING_PATH = os.path.join(ROOT, "ordered_scale_routing.json")
LENS_PATH = os.path.join(ROOT, "data", "signal_lenses.json")
OUT_PATH = os.path.join(ROOT, "data", "market_position_config.json")

DOMAINS = ["Pay", "Incentives", "Benefits", "Time Off", "Wellbeing", "Recognition", "Governance"]
NON_COMPETITIVE = {"Governance"}            # shows favourable/context/differs, no headline verdict

DEFAULTS = {
    "market_band": [35, 65],                # on-market percentile band (LUMI_MARKET_BAND)
    "verdict_margin": 0.25,                 # below/on/above lean threshold (VERDICT_NET_LEAN)
    "uncommon_pct": 20,                     # Approach: < this peer share = atypical (UNCOMMON_PCT)
    "binary_prevalence_thresholds": [35, 65],  # Provision take-up bands for below/on/above
    "suppression_floor": 3,                 # min companies to show anything (aggregate.py)
    "domain_min_polarised": 3,              # firm vs indicative (app.py)
    "tile_min_positioned": 1,               # render gate (app.py)
}

# ---- Part A keyword heuristics (class by meaning). Order: Practice > Design > Level/Provision.
PRACTICE_KW = (
    "documented", "transparen", "publish", " audit", "analys", "governance", "governed",
    "monitor", "tracked", " track ", "benchmark", "calibrat", "communication", "strateg",
    "consistently", "fairness", " trained", "readiness", "gatekeeper", "objective",
    "regularly", "reviewed", "review cycle", "how often", "linked to", "before implementation",
    "before promotion", "before approval", "expectation before", "selection criteria",
    "plan to expand", "test whether", "differentiated by performance", "effectiveness",
    "clearly defined", "removed salary-history", "salary-history", "policy", " process",
    "are pay decisions reviewed", "review and refresh", "governs",
)
DESIGN_KW = (
    "which type", "what type", "which types", "scheme type", "type of pension", "vehicle",
    "how are", "how is", "which measures", "which sources", "which pillars", "which structures",
    "which commission", "what factors", "how do you apply", "ideal market position",
    "treated", "distributed", "which allowances", "which home-working", "which length",
    "which best describes", "which job levels", "which levels", "which role levels",
    "where are remote", "which location", "how are long service awards", "which of the following",
)
LEVEL_KW = (
    "%", "£", "amount", " rate", "budget per", " days", " weeks", "multiple", "multiplier",
    "value of", "premium", "per fte", "per employee", "contribution", "maximum", "max ",
    "target ", "how much", "how many weeks", "how long", "lowest", "salary increase",
    "pence per kwh", "reimbursement rate", "pay terms", "cover is provided", "per kwh",
)
# ---- direction overrides (only applied to Substance = Level/Provision)
LOWER_KW = ("pay gap", " ratio", "attrition", "turnover", "waiting period")
NEUTRAL_KW = (                                   # specific U-shaped/cost/count phrases only
    "workforce cost", "cost per", "cost as a", "cost as %", "% of total reward spend",
    "% of revenue", "percentage of revenue", "per fte", "span of control",
    "individual/business", " split", "payout as a percentage of maximum", "off-cycle",
    "proportion of employees", "what proportion", "increase budget", "pay mix changed",
    "ideal market position",
)

# Carry-forward of the prior hand pass (type + base direction_of_good). Class/3-way
# direction are layered on top of these.
RESOLUTIONS = {
    "REW_BEN_047": ("ordinal", "lower"), "REW_BEN_048": ("ordinal", "higher"),
    "PROP_9e4ad87f": ("numeric", "higher"), "PROP_634adacd": ("ordinal", "higher"),
    "PROP_36b990f9": ("ordinal", "higher"), "REW26_BEN_PENSION_COST_SHARE": ("numeric", "higher"),
    "REW_INC_061": ("categorical", None), "REW_INC_104": ("categorical", None),
    "REW_PAY_005": ("categorical", None), "PROP_e1d1e604": ("categorical", None),
    "REW26_PAY_SKILLS_PAY": ("categorical", None), "REW262_PAY_AISKILLSPAY": ("categorical", None),
    "EXT_REW_GAP_002": ("ordinal", "higher"), "EXT_REW_GAP_007": ("ordinal", "higher"),
    "RED_COST_01": ("ordinal", "higher"), "RED_TERM_02": ("ordinal", "higher"),
    "RED_TERM_03": ("ordinal", "higher"), "REW_BEN_FAM_001": ("ordinal", "higher"),
    "REW_BEN_HOL_001": ("ordinal", "higher"), "REW_BEN_HOL_006": ("ordinal", "higher"),
    "REW_PAY_HOURLY_MIN_1c6e096f": ("ordinal", "higher"), "REW26_WEL_STRATEGY": ("ordinal", "higher"),
    "REW26_BEN_PENSION_MATCH": ("ordinal", "higher"), "REW26_GOV_EU_PTD_PREP": ("ordinal", "higher"),
    "REW262_GOV_EQUALVALUE": ("ordinal", "higher"), "REW262_GOV_PAYINADVERTS": ("ordinal", "higher"),
    "REW262_GOV_EQUALPAYAUDIT": ("ordinal", "higher"), "REW262_PAY_GUARANTEEDHRS": ("ordinal", "higher"),
    "REW262_PAY_SHIFTNOTICE": ("ordinal", "higher"), "REW262_TIME_BEREAVEMENT": ("ordinal", "higher"),
    "RED_NOTICE_01": ("categorical", None), "RED_PAY_01": ("categorical", None),
    "REW_BEN_HOL_002": ("categorical", None), "REW262_GOV_AIINPAY": ("categorical", None),
    "ALLOW_01": ("categorical", None), "CAR_BN_02": ("categorical", None),
    "PROP_216f7323": ("categorical", None), "REW26_WEL_MH_SUPPORT": ("categorical", None),
    "REW26_PAY_JOBEVAL_COVERAGE": ("categorical", None), "REW262_GOV_ACTIONPLAN": ("categorical", None),
    # Diff 13 (ruled 2026-07-18): the 11 by-level matrix numerics run on EST practitioner
    # baselines (expert_baseline_by_level.json) — direction "neutral" = context, not a
    # verdict. No measured-market claim on estimate-grade data; reversible at real data.
    "323ffcf1-749b-43f3-bf34-1de6b8b1ca67": ("numeric", "neutral"),
    "a7ed418e-b057-4b70-ab58-31e897b7c1b6": ("numeric", "higher"),
    "fa0f46f6-61e3-41d1-a2d1-3e57483bb1cf": ("numeric", "neutral"),
    "REW_BEN_112": ("numeric", "neutral"), "REW_BEN_FLEX_ALLOW_01": ("numeric", "neutral"),
    "REW_BEN_PENS_EMP_MAX_01": ("numeric", "neutral"), "REW_INC_111": ("numeric", "neutral"),
    "REW_INC_LTI_MAX_01": ("numeric", "neutral"), "REW_INC_LTI_VALUE_TYP_01": ("numeric", "neutral"),
    "REW_PAY_MKT_POS_01": ("numeric", "higher"), "3faf1f0c-f753-497f-a395-384bba38c5e3": ("numeric", "higher"),
    "REW_BEN_PENS_EE_MAX_01": ("numeric", "neutral"),
    "b1785613-96ed-4a64-9fd7-762d0ac65f19": ("numeric", "neutral"), "REW_Q524161": ("numeric", "neutral"),
    "REW_Q528801": ("numeric", "higher"), "REW_Q534581": ("numeric", "higher"),
    "REW_BEN_139": ("categorical", None), "REW_FAI_TRONC_GROUPS_e5639ac2": ("categorical", None),
    "REW_INC_133": ("categorical", None), "REW_PAY_020": ("categorical", None),
    "REW_PAY_109": ("categorical", None),
}


def _routing():
    try:
        with open(ROUTING_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _lens_map():
    """qid -> live lens (attract/retain/engage/save) from signal_lenses.json."""
    try:
        with open(LENS_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return {}
    m = {}
    for key in ("position_lenses", "prevalence_lenses", "money_lenses"):
        m.update(cfg.get(key) or {})
    return m


def _non_na_opts(q):
    cfg = q.scoring_config or {}
    na = set(cfg.get("na_codes") or [])
    return [o for o in (q.options or []) if not o.get("is_na") and o.get("code") not in na]


def _type(q, routing):
    """The engine mechanic (numeric|binary|ordinal|categorical), carrying the prior pass."""
    if q.id in RESOLUTIONS:
        return RESOLUTIONS[q.id][0]
    scales = routing.get("scales") or {}
    depth_matrix = routing.get("depth_matrix") or {}
    if q.type == "numeric":
        return "numeric"
    if q.type == "matrix":
        return "ordinal" if q.id in depth_matrix else "numeric"
    if q.type == "yes_no":
        return "binary"
    if q.type == "multi_select":
        return "categorical"
    if q.type == "single_select":
        if q.id in scales:
            return "ordinal"
        if score_direction(q) != 0:
            return "binary" if len(_non_na_opts(q)) <= 2 else "ordinal"
        return "categorical"
    return "categorical"


def derive_class(q, mtype):
    """class by MEANING. Returns (class, edge_flag|None)."""
    t = (q.text or "").lower()
    if mtype == "numeric" and any(k in t for k in ("range width", "spread", "band width")):
        return "Design", "structural numeric (range/spread) — Design, kept out of the gauge"
    if any(k in t for k in PRACTICE_KW):
        cls = "Practice"
    elif mtype == "categorical" or any(k in t for k in DESIGN_KW):
        cls = "Design"
    elif mtype == "binary":
        cls = "Provision"
    elif mtype == "numeric":
        cls = "Level"
    elif mtype == "ordinal":
        cls = "Level" if any(k in t for k in LEVEL_KW) else "Practice"
    else:
        cls = "Design"
    flag = None
    if mtype == "binary" and cls == "Practice":
        flag = "binary-measured but a Practice — confirm it stays OUT of the gauge"
    elif mtype == "numeric" and cls == "Design":
        flag = "numeric-measured but a structural Design — confirm it stays OUT of the gauge"
    return cls, flag


def derive_direction(q, cls, base):
    """3-way direction for Substance; null for Approach. Returns (direction, flag|None)."""
    if cls in ("Practice", "Design"):
        return None, None                       # Approach — n/a, never in the gauge
    t = (q.text or "").lower()
    if any(k in t for k in LOWER_KW):
        return "lower_is_better", "lower_is_better — less is the goal"
    if any(k in t for k in NEUTRAL_KW):
        return "neutral", "neutral — U-shaped / cost / count: context, not a verdict"
    if base == "neutral":
        # Diff 13: curated neutral (EST by-level metrics) — context, not a verdict.
        return "neutral", "neutral — curated (EST baseline): no measured-market claim"
    if base == "lower":
        return "lower_is_better", "lower_is_better — from curated polarity"
    if base == "higher":
        return "higher_is_better", None         # the safe, common, no-review case
    return "higher_is_better", "DEFAULTED higher_is_better — confirm (no curated direction)"


def classify(q, routing, lensmap):
    mtype = _type(q, routing)
    # base direction = curated polarity only (NOT score_direction, whose sign is a
    # yes/no storage artifact). No curated direction -> derive_direction defaults
    # higher_is_better and flags it for confirm.
    base = RESOLUTIONS[q.id][1] if q.id in RESOLUTIONS else (
        "higher" if q.polarity == "higher_is_better"
        else "lower" if q.polarity == "lower_is_better" else None)
    cls, class_flag = derive_class(q, mtype)
    direction, dir_flag = derive_direction(q, cls, base)
    lens = lensmap.get(q.id) or "attract"
    entry = {"class": cls, "type": mtype, "direction": direction, "lens": lens, "weight": 1}
    return entry, class_flag, dir_flag


def main():
    write = "--write" in sys.argv
    routing, lensmap = _routing(), _lens_map()
    qs = load_questions()
    live = [q for q in qs.values() if q.superpower == "Reward" and (q.status or "active") != "retired"]
    live.sort(key=lambda q: (DOMAINS.index(q.sub_power) if q.sub_power in DOMAINS else 99, q.id))

    metrics = {}
    by_class, by_dir = {}, {}
    flag_dir, flag_gov, flag_class = [], [], []     # the three Part B buckets
    for q in live:
        entry, class_flag, dir_flag = classify(q, routing, lensmap)
        metrics[q.id] = entry
        by_class[entry["class"]] = by_class.get(entry["class"], 0) + 1
        dk = entry["direction"] or "n/a (Approach)"
        by_dir[dk] = by_dir.get(dk, 0) + 1
        row = {"id": q.id, "domain": q.sub_power, "class": entry["class"], "type": entry["type"],
               "direction": entry["direction"], "text": (q.text or "")[:90]}
        if dir_flag:                                # bucket 1 — DIRECTIONS (highest harm)
            flag_dir.append(dict(row, why=dir_flag))
        if q.sub_power == "Governance":             # bucket 2 — GOVERNANCE carve-out
            flag_gov.append(row)
        if class_flag:                              # bucket 3 — CLASS edge cases
            flag_class.append(dict(row, why=class_flag))

    domains_cfg = {d: {"competitiveness": d not in NON_COMPETITIVE} for d in DOMAINS}
    substance = sum(by_class.get(c, 0) for c in ("Level", "Provision"))
    gauge_feed = sum(1 for q in live if metrics[q.id]["direction"] == "higher_is_better"
                     and metrics[q.id]["class"] in ("Level", "Provision")
                     and q.sub_power not in NON_COMPETITIVE)

    print("Auto-classified %d live Reward metrics.\n" % len(live))
    print("class:      " + "  ".join("%s=%d" % (c, by_class.get(c, 0))
                                     for c in ("Level", "Provision", "Practice", "Design")))
    print("            -> Substance %d  |  Approach %d" % (substance, by_class.get("Practice", 0) + by_class.get("Design", 0)))
    print("direction:  " + "  ".join("%s=%d" % (k, by_dir[k]) for k in sorted(by_dir)))
    print("competitiveness: 6 true · Governance false")
    print("gauge feed (higher_is_better Substance in competitiveness domains): %d" % gauge_feed)
    print("\nPart B flag buckets (risk-ranked):")
    print("  1. directions to confirm : %d" % len(flag_dir))
    print("  2. governance carve-out  : %d" % len(flag_gov))
    print("  3. class edge cases      : %d" % len(flag_class))

    out = {
        "_readme": [
            "DAVID OWNS THIS FILE — per-metric market-position classification (handover Part A).",
            "FIREWALL: class/direction/competitiveness drive COMPUTED positions. Hot-reload: edit and the engine picks it up; no rebuild, no gate (pre-launch).",
            "Per-metric: class (Level|Provision|Practice|Design), type (numeric|binary|ordinal|categorical), "
            "direction (higher_is_better|lower_is_better|neutral|null for Approach), lens, weight (reserved v2).",
            "Only higher_is_better Substance (Level/Provision) in a competitiveness domain feeds the gauge. "
            "lower_is_better=favourable, neutral=context — shown beside it. Approach (Practice/Design)=differs.",
            "_domains.competitiveness=false (Governance) → favourable/context/differs, no headline verdict.",
            "Review the flagged subset in MARKET_POSITION_REVIEW.md (Part B). Priority of harm: direction > competitiveness > class > lens.",
        ],
        "_part_b_review": {
            "directions": flag_dir,         # every lower/neutral + DEFAULTED higher
            "governance": flag_gov,         # the Governance set (out of the headline)
            "class_edges": flag_class,      # binary-as-Practice + numeric-as-Design
        },
        "defaults": DEFAULTS,
        "_domains": domains_cfg,
        "metrics": metrics,
    }

    if not write:
        print("\n[dry-run] pass --write to write %s" % os.path.relpath(OUT_PATH, ROOT))
        return
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("\n[written] %s — auto-pass; David refines the flagged subset via hot-reload." %
          os.path.relpath(OUT_PATH, ROOT))


if __name__ == "__main__":
    main()
