#!/usr/bin/env python3
"""Generate data/metric_refresh_register.json — the refresh-cadence review.

Read-only against the question bank. Reviewed 2026-08-04; DEEP-QA'd 2026-08-05
(every one of the 333 assignments re-read): the class rules are the default,
and per-metric overrides carry every case where a question's substance disagrees
with its catalogue category. qa_refresh.py asserts this file regenerates
byte-identically — edit THIS script, never the JSON.

Classes:
  annual (12)      — quantitative market values (pay, bonus %, premiums, costs,
                     budgets, measured rates) plus rolling-12-month-window
                     questions whose answers expire by construction.
  benefit (18)     — provision *design* on renewal cycles: eligibility maps,
                     entitlement durations, scheme shape.
  structural (24)  — how reward is governed and operated. Changes are policy
                     events, not cycles.

Default rules (in order; overrides trump):
  category='metric' OR unit_type in (currency, percentage) -> annual
  category='benefit'                                       -> benefit
  else (policy, practice)                                  -> structural
The 'weeks' unit was REMOVED from the quantitative rule 2026-08-05: both weeks
questions (enhanced maternity / sick-pay duration) are design entitlements that
move at renewal pace, not market values.

Rerun after bank releases: python3 server/gen_refresh_register.py
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("LUMI_DB") or os.path.join(HERE, "..", "lumi.db")
OUT = os.path.join(HERE, "..", "data", "metric_refresh_register.json")

QUANT_UNITS = ("currency", "percentage")
CLASS_OF = {12: "annual", 18: "benefit", 24: "structural"}

# Substance disagrees with catalogue category — every entry carries its why.
OVERRIDES = {
    # -> annual: rates/values/budgets living outside category='metric'
    "REW_PAY_014": (12, "bank-holiday premium rate moves with the annual pay cycle"),
    "EXT_REW_GAP_001": (12, "annual recognition budget — reset every budget year"),
    "EXT_REW_GAP_002": (12, "£ value of a recognition award — erodes with inflation"),
    "EXT_REW_GAP_007": (12, "£ value of a long-service award — erodes with inflation"),
    "PROP_d65a16e9": (12, "'strategy last refreshed' is a date; the answer ages by itself"),
    "REW262_PAY_AISKILLSPAY": (12, "AI-skills premia are a fast-moving market"),
    "REW265_GOV_AITALENT": (12, "AI/digital talent arrangements are a fast-moving market"),
    "REW264_PEN_AEDEFAULT": (12, "default AE contribution rate — statutory-adjacent"),
    "REW264_PEN_SALSACIMPACT": (12, "2029 salary-sacrifice cap: landscape moves annually"),
    "REW264_PEN_SALSACRESPONSE": (12, "2029 salary-sacrifice cap: intended response will firm up"),
    "REW264_PEN_NICSHARING": (12, "NIC-savings sharing will shift as the cap lands"),
    "REW265_INC_SHAREPART": (12, "participation rate is a measured figure, not a design"),
    "REW265_GOV_AIREGRADE": (12, "asks about the LAST 12 MONTHS — expires by construction"),
    "REW_BEN_058": (12, "asks about the LAST 12 MONTHS — expires by construction"),
    # -> structural: design questions the metric category dragged to annual
    "CAR_BN_02": (24, "eligibility criteria are policy design, not a market value"),
    "CAR_COST_02": (24, "EV mandate is fleet-policy design"),
    "CAR_STATUS_01": (24, "status-car provision is benefit architecture"),
    "CAR_STATUS_03": (24, "car-vs-cash choice is benefit architecture"),
    "RED_NOTICE_01": (24, "how notice is handled is redundancy-policy design"),
    "RED_PAY_01": (24, "redundancy pay basis is policy design"),
    "RED_TERM_01": (24, "redundancy terms offered is policy design"),
    "PROP_202fecc6": (24, "whether utilisation is tracked is a capability, not a value"),
    "PROP_aa4061d5": (24, "how effectiveness is measured is a capability, not a value"),
    "REW_FAI_128": (24, "whether top-performer pay is tested is governance design"),
    "REW_INC_131": (24, "operating LTI plans is scheme architecture"),
    "REW_INC_132": (24, "LTI plan types are scheme architecture"),
    "REW_INC_135": (24, "operating commission plans is scheme architecture"),
    "REW_INC_136": (24, "commission structures are scheme architecture"),
    "REW_PAY_097": (24, "performance-differentiated increases is pay-policy design"),
    # -> benefit (18): eligibility maps + entitlement durations move at renewal pace
    "REW_BEN_139": (18, "PMI eligibility by level — renewal-cycle design"),
    "REW_INC_133": (18, "LTI eligibility by level — scheme-review-cycle design"),
    "REW_PAY_109": (18, "car-allowance eligibility by level — renewal-cycle design"),
    "REW_BEN_FAM_002": (18, "weeks of enhanced maternity pay — entitlement design, not a market value"),
    "REW_BEN_SICK_002": (18, "weeks of enhanced sick pay — entitlement design, not a market value"),
}


def classify(category, unit_type):
    if category == "metric" or (unit_type or "none") in QUANT_UNITS:
        return 12
    if category == "benefit":
        return 18
    return 24


def build(conn):
    rows = conn.execute(
        "SELECT id, category, unit_type, sub_power FROM questions "
        "WHERE status='active' ORDER BY id").fetchall()
    metrics, counts = {}, {"annual": 0, "benefit": 0, "structural": 0}
    for r in rows:
        months = classify(r["category"], r["unit_type"])
        entry = {"category": r["category"], "domain": r["sub_power"]}
        if r["id"] in OVERRIDES:
            months, entry["override_reason"] = OVERRIDES[r["id"]]
        entry["months"] = months
        entry["class"] = CLASS_OF[months]
        metrics[r["id"]] = entry
        counts[entry["class"]] += 1
    missing = [k for k in OVERRIDES if k not in metrics]
    if missing:
        sys.exit("FATAL: override ids not in active bank: %s" % missing)
    return {
        "reviewed": "2026-08-05",
        "policy": "Every active metric carries a refresh cadence in months. An answered "
                  "question is due a refresh when its oldest answer row is older than the "
                  "cadence. Refresh is a nudge only — stale answers keep counting in the "
                  "benchmark, and every accepted value is preserved in answers_history.",
        "classes": {"annual": 12, "benefit": 18, "structural": 24},
        "rules": [
            "category='metric' OR unit_type in %s -> annual (12)" % (QUANT_UNITS,),
            "category='benefit' -> benefit (18)",
            "category in ('policy','practice') -> structural (24)",
            "per-metric overrides trump the class rules (override_reason says why)",
        ],
        "class_counts": counts,
        "metrics": metrics,
    }


def main():
    conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    conn.row_factory = sqlite3.Row
    register = build(conn)
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    with open(out, "w") as f:
        json.dump(register, f, indent=1, sort_keys=True)
    print("wrote %s: %d metrics (%s)" % (os.path.relpath(out),
                                         len(register["metrics"]), register["class_counts"]))


if __name__ == "__main__":
    main()
