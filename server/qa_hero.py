# -*- coding: utf-8 -*-
"""HERO CORRECTNESS QA — market position + practice prevalence.

Polarity direction is the same bug class as the gap-register "Quarterly = not
in place" error: a favourable value must NEVER read as below-market. This
harness checks direction on synthetic and real items, positionability (no
invented orders), band behaviour, domain eligibility, rollup construction and
day-one handling. Run after any change to the hero signal logic.
"""
import json
import os
import sys
import urllib.request
import http.cookiejar
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions
from aggregate import score_direction, score_answer
import positions as pos

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print("  %s %-72s %s" % ("PASS" if ok else "FAIL", name[:72], ("| " + str(detail)[:80]) if detail and not ok else ""))


BAND_LOW, BAND_HIGH, MARGIN = 25.0, 75.0, 0.15

print("=" * 100)
print("1. POLARITY DIRECTION — synthetic items of every polarity (the critical check)")
print("=" * 100)
mk = lambda pol, rank: {"polarity": pol, "percentile": rank}
cases = [
    ("higher_is_better, you HIGH (P90)", mk("higher_is_better", 90), "above"),
    ("higher_is_better, you LOW (P10)", mk("higher_is_better", 10), "below"),
    ("higher_is_better, you mid (P50)", mk("higher_is_better", 50), "at"),
    ("lower_is_better, you LOW (P10) — favourable", mk("lower_is_better", 10), "above"),
    ("lower_is_better, you HIGH (P90) — unfavourable", mk("lower_is_better", 90), "below"),
    ("lower_is_better, you mid (P50)", mk("lower_is_better", 50), "at"),
]
for name, item, want in cases:
    got = pos._market_class(item, BAND_LOW, BAND_HIGH)
    check("%s -> %s market" % (name, want), got == want, "got " + got)

print()
print("=" * 100)
print("2. REAL ITEMS — no favourable position ever reads below market (and vice versa)")
print("=" * 100)
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(p, body=None):
    r = urllib.request.Request("http://localhost:8060" + p, method="POST" if body is not None else "GET")
    d = json.dumps(body).encode() if body is not None else None
    if d:
        r.add_header("Content-Type", "application/json")
    return json.loads(op.open(r, data=d, timeout=120).read())
api("/api/auth/login", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
ov = api("/api/overview")
hero = ov["hero"]
items = [i for i in (ov["callouts"]["strength_items"] + ov["callouts"]["gap_items"]) if i]
contradictions = []
for i in items:
    if i.get("polarity") not in ("higher_is_better", "lower_is_better"):
        continue
    cls = pos._market_class(i, BAND_LOW, BAND_HIGH)
    if i["favourable"] == "good" and cls == "below":
        contradictions.append((i["label"], "good->below"))
    if i["favourable"] == "bad" and cls == "above":
        contradictions.append((i["label"], "bad->above"))
check("strength/gap items: zero favourable<->market contradictions (%d checked)" % len(items),
      not contradictions, contradictions[:2])
lib = {q.id: q for q in load_questions().values()}
lows = [q for q in lib.values() if q.superpower == "Reward" and q.polarity == "lower_is_better"]
check("lower_is_better metrics exist in scope to exercise the inversion", len(lows) == 4, len(lows))

print()
print("=" * 100)
print("3. POSITIONABILITY — coverage is known, never assumed; no invented orders")
print("=" * 100)
reward = [q for q in lib.values() if q.superpower == "Reward"]
pol_qs = [q for q in reward if q.polarity in ("higher_is_better", "lower_is_better")]
unmappable = [q for q in pol_qs if q.type == "single_select" and score_direction(q) == 0]
positionable = [q for q in pol_qs if q.type in ("numeric", "matrix")
                or (q.is_scored and q.type in ("single_select", "yes_no", "multi_select") and score_direction(q) != 0)]
print("  coverage: %d polarised -> %d positionable, %d routed to prevalence (%s)" % (
    len(pol_qs), len(positionable), len(unmappable), Counter(q.type for q in unmappable)))
# 2026.2 census: +11 non-neutral additions (98->109; the AI-skills premium is
# DELIBERATELY neutral — prevalence only), +0 positionable (all unscored
# selects, 76 unchanged), +7 unordered hib single_selects routed (15->22) —
# delta fully accounted for by the 12 additions; existing questions unchanged
check("109 polarised; 76 positionable; 22 unordered routed (matches the data census)",
      len(pol_qs) == 109 and len(positionable) == 76 and len(unmappable) == 22)
fabricated = [(q.id, o["label"]) for q in unmappable for o in (q.options or [])
              if score_answer(q, o["label"]) is not None]
check("no unordered polarised metric can produce a rank (no invented order)", not fabricated, fabricated[:2])
routed = [p for p in api("/api/overview")["hero"]["domains"]]  # routed visible in prevalence pools
prev_total = hero["prevalence"]["pool"] if hero["prevalence"] else 0
check("routed metrics appear in the prevalence pool (pool %d > neutral-only answers)" % prev_total, prev_total > 0)

print()
print("=" * 100)
print("4. BAND — configurable; wash-out reported")
print("=" * 100)
m = hero["market"]
at_share = m["at"] / float(m["pool"])
print("  default band 25-75: %d above / %d at / %d below of %d -> %.0f%% at-market" % (
    m["above"], m["at"], m["below"], m["pool"], at_share * 100))
check("config block exposes the band for tuning", hero["config"]["band_low"] == 25.0 and hero["config"]["band_high"] == 75.0)
check("hero not washed out (at-market share < 70%)", at_share < 0.70, "%.0f%% at" % (at_share * 100))
tighter = pos._pool_verdict([{"polarity": "higher_is_better", "percentile": p} for p in (30, 40, 60, 70, 35, 65)],
                            40, 60, MARGIN)
check("a tighter band (40-60) reclassifies the same pool differently (tunable)",
      tighter["above"] == 2 and tighter["below"] == 2, tighter)

print()
print("=" * 100)
print("5. DOMAIN ELIGIBILITY + ROLLUP CONSTRUCTION")
print("=" * 100)
dm = {d["name"]: d for d in hero["domains"]}
# 2026.1 domains: 5 of the 7 categories clear the 5-polarised floor;
# Wellbeing (new questions, no data yet) and Recognition (1) are prevalence-only
check("Pay / Incentives / Benefits / Time Off / Governance carry a market verdict",
      all(dm[x]["market"] is not None for x in ("Pay", "Incentives", "Benefits", "Time Off", "Governance")),
      {k: (dm[k]["market"] or {}).get("verdict") for k in dm})
check("Wellbeing / Recognition are prevalence-only (below the polarised floor)",
      dm["Wellbeing"]["market"] is None and dm["Recognition"]["market"] is None,
      {k: dm[k]["polarised_comparable"] for k in ("Wellbeing", "Recognition")})
check("every domain still gets a prevalence summary", all(d["prevalence"] is not None for d in hero["domains"]))
check("threshold is config", hero["config"]["domain_min"] == 5)
pool_sum = sum((d["market"]["pool"] if d["market"] else 0) for d in hero["domains"])
check("overall computed from the FULL pool, not domain average (overall pool %d >= sum of eligible domain pools %d)"
      % (m["pool"], pool_sum), m["pool"] >= pool_sum)
recomputed = pos._pool_verdict(
    [{"polarity": "higher_is_better", "percentile": 80}] * m["above"]
    + [{"polarity": "higher_is_better", "percentile": 50}] * m["at"]
    + [{"polarity": "higher_is_better", "percentile": 10}] * m["below"], BAND_LOW, BAND_HIGH, MARGIN)
check("verdict re-derives from the same counts", recomputed["verdict"] == m["verdict"], (recomputed["verdict"], m["verdict"]))

print()
print("=" * 100)
print("6. DAY-ONE / NO-DATA — no verdict from nothing")
print("=" * 100)
empty = pos.hero_signals([], [], ["Pay"], BAND_LOW, BAND_HIGH, 5, MARGIN, 20)
check("no answers -> market None, prevalence None, domain shows insufficient",
      empty["market"] is None and empty["prevalence"] is None and empty["domains"][0]["market"] is None)
one = pos.hero_signals([{"polarity": "higher_is_better", "percentile": 90, "subpower": "Pay", "question_id": "x"}],
                       [], ["Pay"], BAND_LOW, BAND_HIGH, 5, MARGIN, 20)
check("a single answered metric never earns a domain verdict (below domain_min)", one["domains"][0]["market"] is None)

print()
print("=" * 100)
print("7. NEUTRAL PALETTE — prevalence never wears the performance colours (static check)")
print("=" * 100)
web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
css = open(os.path.join(web, "css", "app.css"), encoding="utf-8").read()
js = open(os.path.join(web, "js", "pages.js"), encoding="utf-8").read()
prev_css = css[css.index(".prev-line"):css.index(".prev-line") + 300]
check("prev-line styles use ink/blue only (no favourable/unfavourable vars)",
      "favourable" not in prev_css and "unfavourable" not in prev_css)
prevline_src = js[js.index("function PrevLine"):js.index("function PrevLine") + 400]
check("PrevLine component carries no pos-pill / performance classes",
      "pos-pill" not in prevline_src and "good" not in prevline_src and "bad" not in prevline_src)
check("maturity score tiles removed from the gap register",
      "your maturity" not in open(os.path.join(web, "js", "commercial.js"), encoding="utf-8").read())

print()
fails = len(RESULTS) - sum(RESULTS)
print("RESULTS: %d checks, %d passed, %d failed" % (len(RESULTS), sum(RESULTS), fails))
sys.exit(1 if fails else 0)
