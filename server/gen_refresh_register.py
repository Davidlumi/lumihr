#!/usr/bin/env python3
"""Generate data/metric_refresh_register.json — the refresh-cadence review.

Read-only against the question bank. Reviewed 2026-08-04: every active metric
is assigned a refresh cadence (months) from three ruled classes plus a small
per-metric override list for questions whose text hides an annually-moving
value inside a 'practice'/'policy'/'benefit' category.

Classes (the review's core finding):
  annual (12)      — category='metric' (quantitative figures: pay levels,
                     bonus %, premiums, costs) OR any question whose unit_type
                     is currency/percentage/weeks. These track the market and
                     are collected annually by every reward survey.
  benefit (18)     — category='benefit', non-quantitative: provision *design*
                     (eligibility, scheme shape) reviewed on renewal cycles —
                     slower than the amounts, faster than structure.
  structural (24)  — category='policy'/'practice': how reward is governed and
                     operated. Changes are policy events, not cycles.

Overrides (all → 12): premium/contribution rates and measured rates living in
practice questions; the 2029 salary-sacrifice-cap trio (moving legislation);
AI-talent pay (fast market); 'strategy last refreshed' (a date that ages);
the annual recognition budget.

Rerun after bank releases: python3 server/gen_refresh_register.py
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "lumi.db")
OUT = os.path.join(HERE, "..", "data", "metric_refresh_register.json")

QUANT_UNITS = ("currency", "percentage", "weeks")

OVERRIDES = {
    "REW_PAY_014": "bank-holiday premium rate moves with the annual pay cycle",
    "EXT_REW_GAP_001": "annual recognition budget — reset every budget year",
    "PROP_d65a16e9": "'strategy last refreshed' is a date; the answer ages by itself",
    "REW262_PAY_AISKILLSPAY": "AI-skills premia are a fast-moving market",
    "REW265_GOV_AITALENT": "AI/digital talent arrangements are a fast-moving market",
    "REW264_PEN_AEDEFAULT": "default AE contribution rate — statutory-adjacent",
    "REW264_PEN_SALSACIMPACT": "2029 salary-sacrifice cap: landscape moves annually",
    "REW264_PEN_SALSACRESPONSE": "2029 salary-sacrifice cap: intended response will firm up",
    "REW264_PEN_NICSHARING": "NIC-savings sharing will shift as the cap lands",
    "REW265_INC_SHAREPART": "participation rate is a measured figure, not a design",
}


def classify(category, unit_type):
    if category == "metric" or (unit_type or "none") in QUANT_UNITS:
        return "annual", 12
    if category == "benefit":
        return "benefit", 18
    return "structural", 24


def main():
    conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, category, unit_type, sub_power FROM questions "
        "WHERE status='active' ORDER BY id").fetchall()
    metrics, counts = {}, {"annual": 0, "benefit": 0, "structural": 0}
    for r in rows:
        cls, months = classify(r["category"], r["unit_type"])
        if r["id"] in OVERRIDES:
            cls, months = "annual", 12
        metrics[r["id"]] = {"months": months, "class": cls,
                            "category": r["category"], "domain": r["sub_power"]}
        if r["id"] in OVERRIDES:
            metrics[r["id"]]["override_reason"] = OVERRIDES[r["id"]]
        counts[cls] += 1
    missing = [k for k in OVERRIDES if k not in metrics]
    if missing:
        sys.exit("FATAL: override ids not in active bank: %s" % missing)
    register = {
        "reviewed": "2026-08-04",
        "policy": "Every active metric carries a refresh cadence in months. An answered "
                  "question is due a refresh when its oldest answer row is older than the "
                  "cadence. Refresh is a nudge only — stale answers keep counting in the "
                  "benchmark, and every accepted value is preserved in answers_history.",
        "classes": {"annual": 12, "benefit": 18, "structural": 24},
        "rules": [
            "category='metric' OR unit_type in %s -> annual (12)" % (QUANT_UNITS,),
            "category='benefit' -> benefit (18)",
            "category in ('policy','practice') -> structural (24)",
            "per-metric overrides below trump the class rules",
        ],
        "class_counts": counts,
        "metrics": metrics,
    }
    with open(OUT, "w") as f:
        json.dump(register, f, indent=1, sort_keys=True)
    print("wrote %s: %d metrics (%s)" % (os.path.relpath(OUT), len(metrics), counts))


if __name__ == "__main__":
    main()
