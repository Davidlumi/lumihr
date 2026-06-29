# -*- coding: utf-8 -*-
"""ADVERSARIAL QA GATE — AI per-DOMAIN summary (Pass 3).

Actively tries to make the domain summary fail. Two layers are attacked:
  1. The LIVE generation path (build_domain_summary_payload -> generate_domain_summary)
     across every reward domain x strategy on/off x cuts. The shipped output must always
     validate and the §2 floor must always be present (never an empty/broken block).
  2. The runtime VALIDATOR (validate_domain_summary) — fed deliberately hostile "model
     outputs" (ungrounded numbers, worded ratios, crossed position/strategy vocabulary,
     advice/considerations, directives, legal adjudication, alarm words, alignment with no
     strategy, market position on a non-competitive domain, missing provenance). The
     validator is what stands between a bad model and a member, so it is gated hardest.

With no ANTHROPIC_API_KEY configured the shipped surface is the deterministic floor; when a
key is added the SAME validator gates every model output and this harness re-runs unchanged.

Exit code 0 only if every check passes. LUMI_AI_DOMAIN_SUMMARY=on must not be set unless
this gate is clean.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claude_api as ca
import app as appmod
from db import get_conn

# The gate proves the VALIDATOR + the deterministic FLOOR (both key-independent and
# reproducible). By default we force the no-key path so the run is fast, free and
# deterministic — exactly the surface that ships without a key. Set LUMI_QA_WITH_MODEL=on
# to ALSO exercise live model generations (the same validator gates each; the shipped
# output is asserted valid either way). app loads .env.local on import, so we clear the
# key here AFTER import.
if os.environ.get("LUMI_QA_WITH_MODEL", "").lower() not in ("1", "on", "true"):
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    ca._client = None

RESULTS = []


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), str(detail)[:160]))
    print("  %s %-64s %s" % ("PASS" if ok else "FAIL", name[:64],
                             ("| " + str(detail)[:90]) if detail and not ok else ""))


conn = get_conn()
org = dict(conn.execute("SELECT * FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone())
user = {"role": "admin"}

# the reward domains, in question order
DOMAINS = []
for q in appmod.org_visible_questions(org).values():
    if q.sub_power and q.sub_power not in DOMAINS:
        DOMAINS.append(q.sub_power)
CUTS = [{"dim": "all", "value": None}, {"dim": "industry", "value": org.get("industry")}]

print("=" * 100)
print("SECTION A — live path: every domain x strategy on/off x cut ships a VALID, present summary")
print("=" * 100)
base_payloads = {}   # (domain, strat) -> a real payload, reused by later sections
for name in DOMAINS:
    for strat in (True, False):
        for cut in CUTS:
            payload = appmod.build_domain_summary_payload(conn, org, user, name, cut, apply_strategy=strat)
            if payload is None:
                check("A", "%s/strat=%s/%s payload" % (name, strat, cut["dim"]), False, "None payload")
                continue
            base_payloads.setdefault((name, strat), payload)
            res = ca.generate_domain_summary(payload)
            parts = res.get("parts") or {}
            present = all(isinstance(parts.get(k), str) and parts[k].strip() for k in ca.DOMAIN_PARTS)
            ok_v, why = ca.validate_domain_summary(parts, payload)
            label = "%s / strat=%s / %s" % (name, strat, cut["dim"])
            check("A", "%s — 4 parts present" % label, present, parts)
            check("A", "%s — shipped output passes validator" % label, ok_v, why)
            check("A", "%s — source is model|deterministic" % label,
                  res.get("source") in ("model", "deterministic"), res.get("source"))


print("=" * 100)
print("SECTION B — validator REJECTS hostile model outputs (each must fail closed)")
print("=" * 100)
pay_pay = base_payloads.get(("Pay", True))            # has position + alignment
pay_abs = base_payloads.get(("Pay", False))           # has position, alignment absent
gov = next((p for (d, s), p in base_payloads.items() if d == "Governance" and s), None) \
    or appmod.build_domain_summary_payload(conn, org, user, "Governance", CUTS[0], apply_strategy=True)


def floor(p):
    import copy
    return copy.deepcopy(ca._deterministic_domain_summary(p))


def expect_reject(name, parts, payload):
    ok, why = ca.validate_domain_summary(parts, payload)
    check("B", name, (not ok), "UNEXPECTEDLY PASSED" if ok else why)


# 1 ungrounded number
p = floor(pay_pay); p["notable"] = p["notable"] + " The widest gap touches 4321 employees."
expect_reject("ungrounded number (4321) rejected", p, pay_pay)
# 2 worded ratio
p = floor(pay_pay); p["position"] = "Nearly all of your metrics sit below market."
expect_reject("worded ratio ('nearly all') rejected", p, pay_pay)
p = floor(pay_pay); p["position"] = "Two-thirds sit below market."
expect_reject("worded ratio ('two-thirds') rejected", p, pay_pay)
# 3 crossed vocabulary
p = floor(pay_pay); p["position"] = p["position"] + " Several metrics sit behind market."
expect_reject("crossed vocab ('behind market') rejected", p, pay_pay)
p = floor(pay_pay); p["position"] = p["position"] + " This is below strategy."
expect_reject("crossed vocab ('below strategy') rejected", p, pay_pay)
# 4 advice / considerations
p = floor(pay_pay); p["notable"] = p["notable"] + " Organisations sometimes review their pay bands."
expect_reject("advice ('sometimes review') rejected", p, pay_pay)
p = floor(pay_pay); p["notable"] = p["notable"] + " It may be worth considering a market adjustment."
expect_reject("advice ('worth considering') rejected", p, pay_pay)
# 5 directive
p = floor(pay_pay); p["notable"] = p["notable"] + " You should close the widest gap."
expect_reject("directive ('you should') rejected", p, pay_pay)
# 6 legal adjudication
p = floor(pay_pay); p["notable"] = p["notable"] + " This is required by law."
expect_reject("legal ('required by law') rejected", p, pay_pay)
# 7 alarm / evaluative
p = floor(pay_pay); p["notable"] = p["notable"] + " This is a concerning gap."
expect_reject("alarm ('concerning') rejected", p, pay_pay)
# 8 alignment stated with no alignment field (strategy off)
p = floor(pay_abs); p["position"] = p["position"] + " This domain reads behind strategy."
expect_reject("alignment with no alignment field rejected", p, pay_abs)
# 9 market position on a non-competitive domain
p = floor(gov); p["position"] = "Three of five metrics sit below market."
expect_reject("market position on non-competitive domain rejected", p, gov)
# 10 provenance stripped of its numbers
p = floor(pay_pay); p["provenance"] = "Across your benchmarks, compared with the peer group."
expect_reject("provenance missing its figures rejected", p, pay_pay)


print("=" * 100)
print("SECTION C — a clean, grounded output PASSES (no false rejection)")
print("=" * 100)
ok_c, why_c = ca.validate_domain_summary(floor(pay_pay), pay_pay)
check("C", "deterministic floor (Pay, strategy) passes its own gate", ok_c, why_c)
# a hand-written model-style valid output
good = {
    "position": "%s of %s positioned metrics sit below market, %s on market and %s above market."
                % (pay_pay["position"]["below"], pay_pay["position"]["pool"],
                   pay_pay["position"]["at"], pay_pay["position"]["above"])
                + ((" Against the strategy you have set, this domain reads %s." % pay_pay["alignment"])
                   if pay_pay.get("alignment") else ""),
    "notable": ("Widest gaps: " + ca._named_items(pay_pay["gaps"]) + ".") if pay_pay["gaps"]
               else "No metric here sits below market.",
    "prevalence": "On practices, %s are common choices, of %s assessed."
                  % ((pay_pay.get("prevalence") or {}).get("match_market_majority", 0),
                     (pay_pay.get("prevalence") or {}).get("pool", 0)) if pay_pay.get("prevalence")
                  else "No practice questions are assessed in this domain.",
    "provenance": "Across your %s Pay benchmarks, compared with %s peers."
                  % (pay_pay["provenance"]["answered_count"], pay_pay["provenance"]["peer_pool_size"]),
}
ok_g, why_g = ca.validate_domain_summary(good, pay_pay)
check("C", "hand-written grounded output passes", ok_g, why_g)


print("=" * 100)
print("SECTION D — the deterministic FLOOR passes its own validator for EVERY domain x strategy")
print("=" * 100)
for (name, strat), payload in base_payloads.items():
    fl = ca._deterministic_domain_summary(payload)
    ok_d, why_d = ca.validate_domain_summary(fl, payload)
    check("D", "floor valid: %s / strat=%s" % (name, strat), ok_d, why_d)
    # generate() with no key must ship the floor, source=deterministic
    res = ca.generate_domain_summary(payload)
    check("D", "generate ships valid floor: %s / strat=%s" % (name, strat),
          res.get("source") in ("model", "deterministic") and
          ca.validate_domain_summary(res["parts"], payload)[0], res.get("source"))


print("=" * 100)
fails = [r for r in RESULTS if not r[2]]
total = len(RESULTS)
print("RESULT: %d/%d checks passed" % (total - len(fails), total))
if fails:
    print("\nFAILURES:")
    for sec, name, _ok, detail in fails:
        print("  [%s] %s — %s" % (sec, name, detail))
    sys.exit(1)
print("ALL CLEAR — qa_domain_summary gate is green.")
sys.exit(0)
