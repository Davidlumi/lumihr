# -*- coding: utf-8 -*-
"""PASS-1 QA — "Practice Prevalence" -> "Practice Alignment" vocabulary migration.

Proves, WITHOUT a live key (the deterministic surface that ships when no key is set):
  1. practice_axis unit logic — verdict argmax + tie-break; with_display spreads the frozen
     engine keys untouched and does not mutate its input; bucket_phrase singular/plural grammar.
  2. The new deterministic FLOOR prose, for every domain x strategy on/off: (a) passes
     validate_domain_summary (the no-loop guarantee — a rejected live generation always lands
     on a floor that itself passes), and (b) carries NONE of the blocked legacy phrases and DOES
     use the new vocabulary.
  3. The expanded DOMAIN_LEGACY_RE guard rejects each legacy phrase (fail closed); bare
     "less common" is NOT in the runtime blocklist (innocent in ordinary prose).
  4. VERDICT-STRING FRONTEND-EXCLUSIVE: prevalence_verdict() output appears ONLY on the
     /api/overview browser object (via with_display) and in NO model payload and NO floor string
     (it contains "most", which the domain-summary prompt's rule 1 bans in model output).
  5. Singular-count behaviour: a bucket count of exactly 1 renders grammatical singular and
     still passes the validator (incl. the legacy guard).

LIVE section (sampling real model generations) self-SKIPS without a key. Run it in a keyed
environment (CI/prod):  LUMI_QA_WITH_MODEL=on python3 qa_prevalence_rename.py
It samples each domain x strategy twice and FAILS on any generation containing a forbidden
phrase — including bare "prevalence", which the RUNTIME validator deliberately does NOT block
(prompt :578 still says "prevalence buckets", so a runtime block would over-fall to the floor;
the floor never emits it). Live sampling is where bare-"prevalence" leakage is caught.

Exit 0 only if every check passes.
"""
import os
import sys
import json
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import practice_axis as px
import claude_api as ca
import app as appmod
from db import get_conn

WITH_MODEL = os.environ.get("LUMI_QA_WITH_MODEL", "").lower() in ("1", "on", "true")
if not WITH_MODEL:                       # app loads .env.local on import; clear the key AFTER import
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    ca._client = None

RESULTS = []


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), str(detail)[:160]))
    print("  %s %-66s %s" % ("PASS" if ok else "FAIL", name[:66],
                             ("| " + str(detail)[:90]) if detail and not ok else ""))


# bare "prevalence" is live-only (see module docstring); the runtime blocklist is the 5 phrases.
LIVE_FORBIDDEN = ["match the market majority", "established alternative", "practice prevalence",
                  "common alt", "rarer", "prevalence"]
NEW_WORDS = ("common", "alternative", "rare")

conn = get_conn()
org = dict(conn.execute("SELECT * FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone())
user = {"role": "admin"}
DOMAINS = []
for q in appmod.org_visible_questions(org).values():
    if q.sub_power and q.sub_power not in DOMAINS:
        DOMAINS.append(q.sub_power)
CUT = {"dim": "all", "value": None}

# ------------------------------------------------------------------ SECTION 1
print("=" * 100); print("SECTION 1 — practice_axis unit logic"); print("=" * 100)
check("1", "verdict: with_majority leads -> common",
      px.prevalence_verdict({"with_majority": 5, "established": 2, "less_common": 1, "pool": 8})
      == "most of your practices are common choices")
check("1", "verdict: established leads -> alternative",
      px.prevalence_verdict({"with_majority": 1, "established": 6, "less_common": 2, "pool": 9})
      == "many of your practices follow an alternative pattern")
check("1", "verdict: less_common leads -> rare",
      px.prevalence_verdict({"with_majority": 1, "established": 2, "less_common": 7, "pool": 10})
      == "several of your practices are rare choices")
check("1", "tie common==alternative -> common (higher frequency wins)",
      px.prevalence_verdict({"with_majority": 4, "established": 4, "less_common": 1, "pool": 9})
      == "most of your practices are common choices")
check("1", "tie alternative==rare -> alternative",
      px.prevalence_verdict({"with_majority": 1, "established": 4, "less_common": 4, "pool": 9})
      == "many of your practices follow an alternative pattern")
check("1", "no pool -> None verdict",
      px.prevalence_verdict({"with_majority": 0, "established": 0, "less_common": 0, "pool": 0}) is None)
_in = {"with_majority": 5, "established": 2, "less_common": 1, "pool": 8}
_out = px.with_display(_in)
check("1", "with_display preserves frozen engine keys byte-for-byte",
      all(_out.get(k) == _in[k] for k in ("with_majority", "established", "less_common", "pool")), _out)
check("1", "with_display adds title/states/verdict",
      _out.get("title") == "Practice Alignment" and bool(_out.get("states")) and bool(_out.get("verdict")))
check("1", "with_display does NOT mutate its input", "title" not in _in)
check("1", "bucket_phrase plural common", px.bucket_phrase(5, "with_majority") == "5 are common choices")
check("1", "bucket_phrase singular common", px.bucket_phrase(1, "with_majority") == "1 is a common choice")
check("1", "bucket_phrase plural alternative", px.bucket_phrase(3, "established") == "3 follow alternative patterns")
check("1", "bucket_phrase singular alternative", px.bucket_phrase(1, "established") == "1 follows an alternative pattern")
check("1", "bucket_phrase plural rare", px.bucket_phrase(2, "less_common") == "2 are rare")
check("1", "bucket_phrase singular rare", px.bucket_phrase(1, "less_common") == "1 is rare")

# ------------------------------------------------------------------ SECTION 2
print("=" * 100); print("SECTION 2 — new floor: valid + new-vocab + no legacy, every domain x strat"); print("=" * 100)
base_payloads = {}
LEGACY_RE = ca.DOMAIN_LEGACY_RE
for name in DOMAINS:
    for strat in (True, False):
        payload = appmod.build_domain_summary_payload(conn, org, user, name, CUT, apply_strategy=strat)
        if payload is None:
            check("2", "%s/strat=%s payload" % (name, strat), False, "None payload"); continue
        base_payloads[(name, strat)] = payload
        fl = ca._deterministic_domain_summary(payload)
        ok_v, why = ca.validate_domain_summary(fl, payload)
        check("2", "floor passes validator: %s/strat=%s" % (name, strat), ok_v, why)
        joined = " ".join(fl.values())
        m = LEGACY_RE.search(joined)
        check("2", "floor has NO legacy phrase: %s/strat=%s" % (name, strat), not m, m.group(0) if m else "")
        if (payload.get("prevalence") or {}).get("pool"):
            check("2", "floor prevalence uses new vocab: %s/strat=%s" % (name, strat),
                  any(w in fl["prevalence"].lower() for w in NEW_WORDS), fl["prevalence"])

# ------------------------------------------------------------------ SECTION 3
print("=" * 100); print("SECTION 3 — validator rejects each legacy phrase (fail closed)"); print("=" * 100)
pay = base_payloads.get(("Pay", True))


def reject(name, prevalence_text):
    fl = copy.deepcopy(ca._deterministic_domain_summary(pay))
    fl["prevalence"] = prevalence_text
    ok, why = ca.validate_domain_summary(fl, pay)
    check("3", name, (not ok), "UNEXPECTEDLY PASSED" if ok else why)


reject("rejects 'match the market majority'", "On practices, 3 match the market majority, of 5 assessed.")
reject("rejects 'established alternative'", "On practices, 3 take an established alternative, of 5 assessed.")
reject("rejects 'practice prevalence'", "This domain is assessed on practice prevalence.")
reject("rejects 'common alt'", "On practices, 3 are common alt, of 5 assessed.")
reject("rejects 'rarer'", "On practices, 3 are a rarer choice, of 5 assessed.")
check("3", "'less common' is NOT in the runtime blocklist",
      not ca.DOMAIN_LEGACY_RE.search("these arrangements are less common in the market"))
check("3", "'rare' (new word) is NOT caught by the 'rarer' rule",
      not ca.DOMAIN_LEGACY_RE.search("3 are rare"))

# ------------------------------------------------------------------ SECTION 4
print("=" * 100); print("SECTION 4 — verdict string is FRONTEND-EXCLUSIVE (never payload, never floor)"); print("=" * 100)
VERDICTS = list(px._VERDICTS.values())
leaked_payload, leaked_floor = [], []
for (name, strat), payload in base_payloads.items():
    blob = json.dumps(payload, ensure_ascii=False).lower()
    leaked_payload += [(name, strat, v) for v in VERDICTS if v.lower() in blob]
    fljoin = " ".join(ca._deterministic_domain_summary(payload).values()).lower()
    leaked_floor += [(name, strat, v) for v in VERDICTS if v.lower() in fljoin]
check("4", "verdict NEVER appears in any model payload", not leaked_payload, leaked_payload[:3])
check("4", "verdict NEVER appears in any floor string", not leaked_floor, leaked_floor[:3])
check("4", "verdict DOES appear on the /api/overview browser object",
      px.with_display({"with_majority": 5, "established": 2, "less_common": 1, "pool": 8}).get("verdict") in VERDICTS)

# ------------------------------------------------------------------ SECTION 5
print("=" * 100); print("SECTION 5 — singular count=1 renders grammatical + still validates"); print("=" * 100)
spay = copy.deepcopy(pay)
spay["prevalence"] = {"match_market_majority": 1, "established_alternative": 1, "less_common": 1, "pool": 3}
sfl = ca._deterministic_domain_summary(spay)
check("5", "singular floor reads grammatically",
      "1 is a common choice" in sfl["prevalence"] and "1 follows an alternative pattern" in sfl["prevalence"]
      and "1 is rare" in sfl["prevalence"], sfl["prevalence"])
ok_s, why_s = ca.validate_domain_summary(sfl, spay)
check("5", "singular floor passes validator (incl. legacy guard)", ok_s, why_s)

# ------------------------------------------------------------------ LIVE
print("=" * 100); print("SECTION LIVE — sample real model generations (keyed env only)"); print("=" * 100)
if not WITH_MODEL or ca._client_or_none() is None:
    check("LIVE", "live model sampling", True, "SKIPPED — no ANTHROPIC_API_KEY (floor-only run)")
    print("  (run in a keyed env: LUMI_QA_WITH_MODEL=on python3 qa_prevalence_rename.py)")
else:
    hits = []
    for (name, strat), payload in base_payloads.items():
        for _ in range(2):
            res = ca.generate_domain_summary(payload)
            txt = " ".join((res.get("parts") or {}).values()).lower()
            hits += [(name, strat, ph, res.get("source")) for ph in LIVE_FORBIDDEN if ph in txt]
    check("LIVE", "no live generation surfaces a forbidden phrase (incl. bare 'prevalence')", not hits, hits[:5])

print("=" * 100)
fails = [r for r in RESULTS if not r[2]]
print("RESULT: %d/%d checks passed" % (len(RESULTS) - len(fails), len(RESULTS)))
if fails:
    print("\nFAILURES:")
    for sec, nm, _o, d in fails:
        print("  [%s] %s — %s" % (sec, nm, d))
    sys.exit(1)
print("ALL CLEAR — qa_prevalence_rename (%s) is green." % ("floor-only" if not WITH_MODEL else "floor + live"))
sys.exit(0)
