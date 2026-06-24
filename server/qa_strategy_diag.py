# -*- coding: utf-8 -*-
"""ADVERSARIAL QA GATE — reward strategy-execution diagnosis.

Tests the two trust layers without any API call:
  1. The deterministic FINDINGS engine (strategy_diag) — intent-vs-reality logic,
     on-plan exclusion, objective ranking, grounded evidence.
  2. The runtime VALIDATOR (claude_api.validate_diagnosis) fed hostile "model
     outputs" (ungrounded £, finding-count drift, malformed text, directives,
     legal adjudication). The validator is what stands between a bad model and a
     member; it is gated hardest.

Exit 0 only if every check passes. Do not enable LUMI_AI_STRATEGY unless clean.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategy_diag as sd
import claude_api as ca

R = []
def check(section, name, ok, detail=""):
    R.append((name, bool(ok)))
    print("  [%s] %s %-66s %s" % (section, "PASS" if ok else "FAIL", name[:66], ("| " + str(detail)[:80]) if detail and not ok else ""))

STRAT = {"market_position": "lag", "reward_mix": "benefits", "pay_for_performance": "strong",
         "primary_objective": "cost",
         "provenance": {k: "set" for k in ("market_position", "reward_mix", "pay_for_performance", "primary_objective")}}
DOMS = [
    {"name": "Pay", "verdict": "below", "below": 4, "at": 5, "above": 3, "pool": 12, "competitive": True},
    {"name": "Benefits", "verdict": "below", "below": 9, "at": 2, "above": 1, "pool": 12, "competitive": True},
    {"name": "Incentives", "verdict": "at", "below": 2, "at": 5, "above": 1, "pool": 8, "competitive": True},
    {"name": "Time Off", "verdict": "above", "below": 1, "at": 3, "above": 6, "pool": 10, "competitive": True},
    {"name": "Governance", "verdict": "below", "below": 3, "at": 1, "above": 0, "pool": 4, "competitive": False},
]
OPP = {"Benefits": {"gbp": 74790, "direction": "investment", "top_label": "Employer pension contribution", "top_gbp": 74790},
       "Time Off": {"gbp": 21000, "direction": "savings", "top_label": "Holiday entitlement", "top_gbp": 21000}}

print("=" * 92)
print("SECTION A — deterministic findings engine")
print("=" * 92)
F = sd.compute_findings(STRAT, DOMS, OPP)
areas = [f["area"] for f in F]
check("A", "benefits-led mix → below-market Pay is ON PLAN (not flagged)", "Pay" not in areas, areas)
check("A", "Benefits below market while aiming to lead → flagged as a gap", any(f["area"] == "Benefits" and f["kind"] == "gap" for f in F))
check("A", "Time Off above market while aiming to lag → flagged as overspend", any(f["area"] == "Time Off" and f["kind"] == "over" for f in F))
check("A", "non-competitive Governance never appears", "Governance" not in areas)
check("A", "cost objective ranks the overspend (savings) finding first", F and F[0]["area"] == "Time Off", areas)
check("A", "every finding carries grounded evidence with a count", all(re.search(r"\d+ of \d+", f["evidence"]) for f in F))
check("A", "£ attached only where an opportunity exists", all((f["money_gbp"] is None) == (f["area"] not in OPP) for f in F))
# on-plan: everything matches aim → no findings
on_plan_doms = [{"name": "Pay", "verdict": "below", "below": 1, "at": 1, "above": 0, "pool": 2, "competitive": True}]
on_plan_strat = {"market_position": "lag", "provenance": {"market_position": "set"}}
check("A", "all-on-plan org yields zero findings", sd.compute_findings(on_plan_strat, on_plan_doms, {}) == [])

print()
print("=" * 92)
print("SECTION B — deterministic narrative is itself clean & grounded")
print("=" * 92)
payload = sd.build_diagnosis_payload(STRAT, F, {"alignment": "ahead"}, "Control cost", ["Recognition"], True)
det = sd.deterministic_diagnosis(payload)
ok_det, why_det = ca.validate_diagnosis(det, payload)
check("B", "deterministic narrative passes its own validator", ok_det, why_det)
check("B", "summary + one narrated finding per computed finding", len(det.get("findings", [])) == len(F))
det_text = det["summary"] + " " + " ".join(x["headline"] + x["detail"] + x["option"] for x in det["findings"])
allowed = ca._diagnosis_numbers(payload)
extra = [t for t in re.findall(r"\d+(?:\.\d+)?", det_text.replace(",", "")) if float(t) not in allowed and round(float(t)) not in allowed]
check("B", "deterministic narrative invents no number", not extra, extra)
empty_payload = sd.build_diagnosis_payload(on_plan_strat, [], {"alignment": "on_target"}, "Attract", ["Pay", "Benefits"], True)
on_plan_det = sd.deterministic_diagnosis(empty_payload)
check("B", "on-plan affirmation renders with one reassuring finding", len(on_plan_det["findings"]) == 1 and "On plan" in on_plan_det["findings"][0]["headline"])

print()
print("=" * 92)
print("SECTION V — validator attacked with hostile 'model outputs'")
print("=" * 92)
good = {"summary": "Two areas pull against your lag-the-market aim.",
        "findings": [{"headline": "Benefits below your lead aim", "detail": "9 of 12 Benefits metrics sit below market; about £74,790 closes the largest gap.", "option": "Organisations often size up what closing part of the gap costs; your own budget comes first."},
                     {"headline": "Time Off above your lag aim", "detail": "6 of 10 Time Off metrics sit above market.", "option": "Organisations here often check the spend is deliberate; your priorities come first."},
                     {"headline": "Incentives short of your strong pay-for-performance aim", "detail": "Incentives sits on market overall.", "option": "Options others explore include reviewing which roles drive it; your constraints come first."}]}
ok, _ = ca.validate_diagnosis(good, payload)
check("V", "validator ACCEPTS a faithful diagnosis", ok)
def rej(name, parts, reason_substr=None):
    o, why = ca.validate_diagnosis(parts, payload)
    check("V", "rejects: " + name, not o, why if o else "")
import copy
bad = copy.deepcopy(good); bad["findings"][0]["detail"] = "about £999,999 closes the largest gap"
rej("invented £ figure", bad)
bad = copy.deepcopy(good); bad["findings"].pop()
rej("dropped a finding (count drift)", bad)
bad = copy.deepcopy(good); bad["findings"].append({"headline": "h", "detail": "d", "option": "o"})
rej("added a finding (count drift)", bad)
bad = copy.deepcopy(good); bad["findings"][0]["detail"] = "9 of 12 sit below\\ market"
rej("malformed text (backslash)", bad)
bad = copy.deepcopy(good); bad["findings"][0]["option"] = "You must close this gap immediately"
rej("directive phrasing", bad)
bad = copy.deepcopy(good); bad["findings"][0]["detail"] = "this is unlawful and in breach of equal pay law"
rej("legal adjudication", bad)
bad = copy.deepcopy(good); bad["summary"] = ""
rej("empty summary", bad)
bad = copy.deepcopy(good); bad["findings"][1]["detail"] = "placeholder"
rej("placeholder stub", bad)

print()
print("=" * 92)
passed = sum(1 for _, ok in R if ok)
print("RESULTS: %d checks, %d passed, %d failed" % (len(R), passed, len(R) - passed))
if passed == len(R):
    print("GATE CLEAN: strategy diagnosis is grounded, on-plan-aware, count-stable, "
          "directive-free and legally non-adjudicating.")
sys.exit(0 if passed == len(R) else 1)
