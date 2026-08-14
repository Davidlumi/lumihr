# -*- coding: utf-8 -*-
"""ADVERSARIAL QA GATE — strategy alignment engine (2026-08-14, brief v2 §5/§6).

Pure-computation tests of strategy_align.evaluate() + the shipped rule library:
the four-status contract, counts-sum invariant (brief §12), skipped-intent
neutrality (_strategy_field contract), the transparency live-gate, starved-
fixture honesty (unanswered -> not_evidenced, never fabricated), entitlement
(invisible metric -> not_evidenced), R5 (no score anywhere), and directive/
legal cleanliness of every statement the library can emit.

    python3 server/qa_strategy_align.py     # no server, no DB
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategy_align as sa
import claude_api as ca

R = []
def check(sec, name, ok, detail=""):
    R.append((name, bool(ok)))
    print("  [%s] %s %-64s %s" % (sec, "PASS" if ok else "FAIL", name[:64], ("| " + str(detail)[:90]) if detail and not ok else ""))

RULES = sa.load_rules()
EXCLUDE = ("Wellbeing", "Governance & Transparency")
PROV = lambda **kw: {"provenance": dict({k: "set" for k in kw.pop("set_", [])}, **kw.get("extra", {}))}

def strat(**kw):
    fields = dict(kw)
    prov = {f: "set" for f in fields}
    if "transparency" in fields:
        prov["transparency"] = fields.pop("_tprov", "live")
    return dict(fields, provenance=prov, domain_targets=fields.get("domain_targets") or {})

DOMS = [
    {"name": "Pay", "competitive": True, "target": {"stance": "lead", "alignment": "behind"}},
    {"name": "Benefits & Lifestyle", "competitive": True, "target": {"stance": "lead", "alignment": "on_target"}},
    {"name": "Time Off & Family", "competitive": True, "target": {"stance": "lag", "alignment": "ahead"}},
    {"name": "Pensions & Savings", "competitive": True, "target": None},
    {"name": "Wellbeing", "competitive": True, "target": {"stance": "lead", "alignment": "behind"}},
    {"name": "Governance & Transparency", "competitive": True, "target": {"stance": "lead", "alignment": "behind"}},
]

print("=" * 92)
print("SECTION A — position commitments from the engine target read")
print("=" * 92)
S = strat(market_position="lead")
out = sa.evaluate(RULES, S, {}, {}, DOMS, EXCLUDE)
pos_c = {c["category"]: c for c in out["commitments"] if c["kind"] == "position"}
check("A", "one position commitment per stated position category", len(pos_c) == 4, sorted(pos_c))
check("A", "R3b — Wellbeing/Governance NEVER carry a position commitment",
      "Wellbeing" not in pos_c and "Governance & Transparency" not in pos_c)
check("A", "behind -> behind_intent", pos_c["Pay"]["status"] == "behind_intent")
check("A", "on_target -> evidenced", pos_c["Benefits & Lifestyle"]["status"] == "evidenced")
check("A", "ahead of a lag aim -> behind_intent (P2 overspend read)",
      pos_c["Time Off & Family"]["status"] == "behind_intent")
check("A", "no verdict -> not_evidenced (never fabricated)",
      pos_c["Pensions & Savings"]["status"] == "not_evidenced")
# domain_targets override drives the stance word
S2 = strat(market_position="lead"); S2["domain_targets"] = {"Time Off & Family": "lag"}
out2 = sa.evaluate([], S2, {}, {}, DOMS, EXCLUDE)
tof = next(c for c in out2["commitments"] if c["category"] == "Time Off & Family")
check("A", "domain_targets override quoted in the intent", "below market" in tof["statement"], tof["statement"])
check("A", "unstated strategy -> zero commitments (skipped reads neutral)",
      sa.evaluate(RULES, {"market_position": "lead", "provenance": {"market_position": "skipped"}}, {}, {}, DOMS, EXCLUDE)["commitments"] == [])

print()
print("=" * 92)
print("SECTION B — coherence rules: fired / consistent / starved")
print("=" * 92)
S = strat(transparency="open")
out = sa.evaluate(RULES, S, {}, {"REW262_GOV_PAYINADVERTS": "Never", "PAYTR_02_131bd412": "Yes"}, [], EXCLUDE)
g1 = next((c for c in out["commitments"] if c["id"] == "rule:G1"), None)
g2 = next((c for c in out["commitments"] if c["id"] == "rule:G2"), None)
check("B", "G1 fires: open transparency + never-in-adverts -> contradicted",
      g1 and g1["status"] == "contradicted")
check("B", "fired statement carries BOTH sides (intent + the org's answer)",
      g1 and "fully open" in g1["statement"] and "Never" in g1["statement"], g1 and g1["statement"])
check("B", "G2 consistent: ranges visible -> evidenced", g2 and g2["status"] == "evidenced")
out = sa.evaluate(RULES, S, {}, {}, [], EXCLUDE)
g1 = next((c for c in out["commitments"] if c["id"] == "rule:G1"), None)
check("B", "starved fixture: intent held, evidence unanswered -> not_evidenced",
      g1 and g1["status"] == "not_evidenced")
# transparency live-gate: 'set' (not reconfirmed) is NOT a stated intent
S = strat(transparency="open", _tprov="set")
out = sa.evaluate(RULES, S, {}, {"REW262_GOV_PAYINADVERTS": "Never"}, [], EXCLUDE)
check("B", "transparency 'set'-not-'live' never fires a rule (reconfirm contract)",
      not any(c["id"].startswith("rule:G") for c in out["commitments"]))
# any-of evidence: I1 via either leg
S = strat(pay_for_performance="strong")
out = sa.evaluate(RULES, S, {}, {"REW_INC_103": "None", "REW_PAY_097": "Yes – strongly differentiated"}, [], EXCLUDE)
i1 = next((c for c in out["commitments"] if c["id"] == "rule:I1"), None)
check("B", "I1 any-of: no-bonus population fires the contradiction", i1 and i1["status"] == "contradicted")
# document-intent rule: P5 segments declared, no mechanic anywhere
DOC = {"segments": {"differentiated": True, "segments": ["Engineering"]}}
out = sa.evaluate(RULES, {}, DOC, {"PROP_168a6213": "Not at all", "REW26_PAY_SKILLS_PAY": "No"}, [], EXCLUDE)
p5 = next((c for c in out["commitments"] if c["id"] == "rule:P5"), None)
check("B", "P5 document intent: declared segments with no mechanic -> not_evidenced",
      p5 and p5["status"] == "not_evidenced")

print()
print("=" * 92)
print("SECTION C — provision/practice commitments + the counts contract")
print("=" * 92)
DOC = {"commitments": {"Wellbeing": {"metric_ids": ["REW26_WEL_EAP", "REW26_WEL_FINWELL"]},
                       "Governance & Transparency": {"statement": "Ranges shared; equal pay reviewed annually."}}}
out = sa.evaluate(RULES, strat(transparency="ranges"), DOC,
                  {"REW26_WEL_EAP": "Yes", "REW26_WEL_FINWELL": "No", "PAYTR_02_131bd412": "Yes"},
                  [], EXCLUDE, visible_qids={"REW26_WEL_EAP", "REW26_WEL_FINWELL", "PAYTR_02_131bd412"})
wb = next(c for c in out["commitments"] if c["kind"] == "provision")
check("C", "W2 — a committed provision answered absent -> contradicted", wb["status"] == "contradicted")
gv = next(c for c in out["commitments"] if c["kind"] == "practice")
check("C", "practice commitment quotes the member verbatim", "Ranges shared" in gv["statement"])
check("C", "practice evidenced when transparency stands uncontradicted", gv["status"] == "evidenced")
DOC2 = {"commitments": {"Wellbeing": {"metric_ids": ["REW26_WEL_EAP"]}}}
out2 = sa.evaluate(RULES, {}, DOC2, {"REW26_WEL_EAP": "Yes"}, [], EXCLUDE, visible_qids=set())
wb2 = next(c for c in out2["commitments"] if c["kind"] == "provision")
check("C", "entitlement — an invisible committed metric reads not_evidenced", wb2["status"] == "not_evidenced")
# counts contract (brief §12): sum of statuses == commitments per category, all categories
S = strat(market_position="lead", transparency="open", pay_for_performance="strong")
big = sa.evaluate(RULES, S, DOC, {"REW26_WEL_EAP": "Yes", "REW26_WEL_FINWELL": "No"}, DOMS, EXCLUDE)
ok_sum = all(sum(v.values()) == len([c for c in big["commitments"] if c["category"] == cat])
             for cat, v in big["counts"].items())
check("C", "counts reconcile: statuses sum to commitments, every category", ok_sum, big["counts"])
check("C", "every commitment carries exactly one of the four statuses",
      all(c["status"] in sa.STATUSES for c in big["commitments"]))
check("C", "R5 — no score/index/grade key anywhere in the output",
      not re.search(r'"(score|index|grade|rank)"', __import__("json").dumps(big)))

print()
print("=" * 92)
print("SECTION D — every emittable statement is directive- and legal-clean")
print("=" * 92)
all_statements = []
for rule in RULES:
    all_statements.append(rule.get("statement", "").replace("{answer}", "X").replace("{answer_detail}", "X"))
    all_statements.append(rule.get("rationale", ""))
for c in big["commitments"] + out["commitments"]:
    all_statements.append(c.get("statement", ""))
joined = " ".join(all_statements)
check("D", "no DIRECTIVE_RE hit across the full statement library", not ca.DIRECTIVE_RE.search(joined),
      ca.DIRECTIVE_RE.search(joined) and ca.DIRECTIVE_RE.search(joined).group(0))
check("D", "no LEGAL_RE hit across the full statement library", not ca.LEGAL_RE.search(joined),
      ca.LEGAL_RE.search(joined) and ca.LEGAL_RE.search(joined).group(0))
check("D", "no invented authority (best practice / industry standard)",
      not re.search(r"industry standard|best practice", joined, re.I))
check("D", "rule library loads with unique ids + one category each",
      len({r["rule_id"] for r in RULES}) == len(RULES) and all(r.get("category") for r in RULES))

print()
print("=" * 92)
print("SECTION E — options blocks (R6/R8): levers, framing, never ranked")
print("=" * 92)
LEV = sa.load_levers()
check("E", "lever library loads with a trade_off on EVERY lever (no marketing)",
      LEV and all((l.get("trade_off") or "").strip() for l in LEV))
check("E", "every lever names a register_effect (Substance/Approach)",
      all(l.get("register_effect") in ("Substance", "Approach") for l in LEV))
check("E", "v1 tranche is Pay / Benefits & Lifestyle / Time Off & Family (R8)",
      {l["category"] for l in LEV} == {"Pay", "Benefits & Lifestyle", "Time Off & Family"})
_cs = [
    {"id": "position:Pay", "category": "Pay", "kind": "position", "status": "behind_intent", "statement": "s"},
    {"id": "rule:P4", "category": "Pay", "kind": "coherence", "status": "contradicted", "statement": "s"},
    {"id": "position:Benefits & Lifestyle", "category": "Benefits & Lifestyle", "kind": "position", "status": "evidenced", "statement": "s"},
    {"id": "position:Pensions & Savings", "category": "Pensions & Savings", "kind": "position", "status": "behind_intent", "statement": "s"},
]
OB = sa.options_for(_cs, levers=LEV)
check("E", "options only for behind_intent/contradicted — evidenced gets none",
      {o["commitment_id"] for o in OB} == {"position:Pay", "rule:P4", "position:Pensions & Savings"})
_pay_pos = next(o for o in OB if o["commitment_id"] == "position:Pay")
_pay_coh = next(o for o in OB if o["commitment_id"] == "rule:P4")
check("E", "register matching: a position gap gets Substance levers only",
      _pay_pos["levers"] and all(l["register_effect"] == "Substance" for l in _pay_pos["levers"]))
check("E", "register matching: a coherence contradiction gets Approach levers only",
      _pay_coh["levers"] and all(l["register_effect"] == "Approach" for l in _pay_coh["levers"]))
check("E", "levers keep FILE order (never re-ranked)",
      [l["lever_id"] for l in _pay_pos["levers"]] ==
      [l["lever_id"] for l in LEV if l["category"] == "Pay" and l["register_effect"] == "Substance"])
check("E", "R6 framing string verbatim on every block",
      all(o["framing"] == sa.OPTIONS_FRAMING for o in OB))
_pens = next(o for o in OB if o["commitment_id"] == "position:Pensions & Savings")
check("E", "outside-tranche category says so plainly (no silent cap)",
      not _pens["levers"] and "later tranche" in (_pens.get("coverage_note") or ""))
check("E", "no vendor/product names in the lever library",
      not re.search(r"\b(perkbox|benefex|zest|reward gateway|darwin)\b",
                    __import__("json").dumps(LEV), re.I))
_lever_text = " ".join((l.get("what_it_is", "") + " " + l.get("typical_shape", "") + " " + l.get("trade_off", "")) for l in LEV)
check("E", "lever copy is directive- and legal-clean",
      not ca.DIRECTIVE_RE.search(_lever_text) and not ca.LEGAL_RE.search(_lever_text))

print()
print("=" * 92)
passed = sum(1 for _, ok in R if ok)
print("RESULTS: %d checks, %d passed, %d failed" % (len(R), passed, len(R) - passed))
if passed == len(R):
    print("GATE CLEAN: alignment is four-status, count-true, starved-honest, "
          "entitlement-safe, score-free and directive-free.")
sys.exit(0 if passed == len(R) else 1)
