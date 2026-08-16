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
check("A", "the two behind_intent directions are distinguishable (short vs past)",
      pos_c["Pay"]["direction"] == "short" and pos_c["Time Off & Family"]["direction"] == "past",
      {k: v.get("direction") for k, v in pos_c.items()})
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
# P5 + the scarce-role segments it tested were retired 2026-08-15 (no pay data)
out = sa.evaluate(RULES, {}, {"segments": {"differentiated": True}}, {}, [], EXCLUDE)
check("B", "retired P5 can no longer fire (segments removed with the pay-data claim)",
      not any(c["id"] == "rule:P5" for c in out["commitments"]))

print()
print("=" * 92)
print("SECTION C — the counts contract")
print("=" * 92)
out = sa.evaluate(RULES, strat(transparency="ranges"), {},
                  {"PAYTR_02_131bd412": "Yes"}, [], EXCLUDE,
                  visible_qids={"PAYTR_02_131bd412"})
check("C", "commitment sections retired 2026-08-15 — no provision/practice commitments emitted",
      not [c for c in out["commitments"] if c["kind"] in ("provision", "practice")])
# counts contract (brief §12): sum of statuses == commitments per category, all categories
S = strat(market_position="lead", transparency="open", pay_for_performance="strong")
big = sa.evaluate(RULES, S, {}, {"REW26_WEL_EAP": "Yes", "REW26_WEL_FINWELL": "No"}, DOMS, EXCLUDE)
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
# Tranche 2 (2026-08-16): every live category carries levers, so no domain section in the
# report ends on "a later tranche" where the reader expects recommendations. The check is
# now DERIVED from the taxonomy rather than a hardcoded three, so adding a category fails
# here — loudly — instead of quietly shipping a section with nothing under it.
_LIVE_CATS = {"Pay", "Benefits & Lifestyle", "Time Off & Family", "Incentives & Recognition",
              "Pensions & Savings", "Health & Protection", "Wellbeing", "Governance & Transparency"}
_cov = {l["category"] for l in LEV}
check("E", "every live category carries levers — no domain is a 'later tranche'",
      _cov == _LIVE_CATS, "missing: %s | unexpected: %s" % (sorted(_LIVE_CATS - _cov), sorted(_cov - _LIVE_CATS)))
_by_reg = {}
for _l in LEV:
    _by_reg.setdefault(_l["category"], set()).add(_l["register_effect"])
check("E", "every category carries BOTH registers, so no gap lands without options",
      all(v == {"Substance", "Approach"} for v in _by_reg.values()),
      {k: sorted(v) for k, v in _by_reg.items() if v != {"Substance", "Approach"}})
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
_over = [{"id": "position:Pay", "category": "Pay", "kind": "position", "status": "behind_intent",
          "direction": "past", "statement": "s"}]
_ov = sa.options_for(_over, levers=LEV)[0]
check("E", "an OVERSPEND gap is never offered cost-adding levers (2026-08-15)",
      _ov["levers"] == [], [l["name"] for l in _ov["levers"]])
check("E", "the overspend block says why it is empty (no silent cap)",
      "above this aim" in (_ov.get("coverage_note") or ""), _ov.get("coverage_note"))
check("E", "overspend note is directive- and legal-clean",
      not ca.DIRECTIVE_RE.search(_ov["coverage_note"]) and not ca.LEGAL_RE.search(_ov["coverage_note"]))
check("E", "a SHORT position gap still gets its levers (the fix is narrow)",
      len(_pay_pos["levers"]) > 0 and _pay_pos is not None)
# Every live category now carries BOTH registers, so this contract needs a synthetic
# fixture: a lever set stripped of Approach, against a gap that needs one. The rule it
# guards is unchanged — a covered category must never render an empty options block.
# A coherence SHORTFALL now draws Substance too (an absent provision is closed by adding
# it), so the fixture uses a CONTRADICTION — practice running against intent — which stays
# Approach-only, against a lever set stripped of Approach.
_subs_only = [l for l in LEV if l["register_effect"] == "Substance"]
_bare = sa.options_for([{"id": "rule:B2", "category": "Benefits & Lifestyle", "kind": "coherence",
                         "status": "contradicted", "statement": "s"}], levers=_subs_only)[0]
check("E", "covered category with no lever in the needed register is NEVER silently empty",
      not _bare["levers"] and (_bare.get("coverage_note") or "").strip(), _bare.get("coverage_note"))
# a stated provision that is ABSENT must be answerable by adding it (2026-08-16 review)
_absent = sa.options_for([{"id": "rule:W1", "category": "Wellbeing", "kind": "coherence",
                           "status": "behind_intent", "statement": "no EAP shows"}], levers=LEV)[0]
check("E", "a coherence SHORTFALL can be answered by adding the missing provision",
      any(l["register_effect"] == "Substance" for l in _absent["levers"]),
      [l["name"] for l in _absent["levers"]])
_contra = sa.options_for([{"id": "rule:G1", "category": "Governance & Transparency", "kind": "coherence",
                           "status": "contradicted", "statement": "s"}], levers=LEV)[0]
check("E", "a coherence CONTRADICTION still draws Approach only",
      _contra["levers"] and all(l["register_effect"] == "Approach" for l in _contra["levers"]),
      [l["register_effect"] for l in _contra["levers"]])
check("E", "no options block anywhere is both lever-less and note-less",
      all(o["levers"] or (o.get("coverage_note") or "").strip() for o in (OB + [_ov, _bare])))
_pens = next(o for o in OB if o["commitment_id"] == "position:Pensions & Savings")
check("E", "a formerly-uncovered category now carries real options (tranche 2)",
      len(_pens["levers"]) > 0 and not _pens.get("coverage_note"),
      (_pens.get("coverage_note"), len(_pens["levers"])))
# the no-silent-cap contract still has to hold for a category outside the taxonomy
_off = sa.options_for([{"id": "position:Made Up Area", "category": "Made Up Area", "kind": "position",
                        "status": "behind_intent", "statement": "s"}], levers=LEV)[0]
check("E", "an uncovered category still says so plainly (no silent cap)",
      not _off["levers"] and "later tranche" in (_off.get("coverage_note") or ""), _off.get("coverage_note"))
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
