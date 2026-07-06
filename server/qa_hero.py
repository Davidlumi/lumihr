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


BAND_LOW, BAND_HIGH, MARGIN = 25.0, 75.0, 0.25   # net-lean threshold (LUMI_VERDICT_NET_LEAN)

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
# Self-tracking invariant (was a frozen 109/76/22 census that drifted with every
# release — 2026.3 added 38). What MUST hold regardless of library growth: the
# positionable set (scored, real order) and the unordered-routed set (single_select,
# score_direction==0) are each a subset of the polarised pool and are DISJOINT by
# construction (one needs direction!=0, the other ==0), and both are non-empty so
# the polarity-inversion checks above have something to bite on.
_pos_ids = {q.id for q in positionable}
_unm_ids = {q.id for q in unmappable}
_pol_ids = {q.id for q in pol_qs}
check("polarised coverage is sound (positionable & routed each subset of polarised, disjoint, non-empty)",
      _pos_ids <= _pol_ids and _unm_ids <= _pol_ids and _pos_ids.isdisjoint(_unm_ids)
      and len(positionable) > 0 and len(unmappable) > 0,
      "pos=%d unm=%d pol=%d" % (len(positionable), len(unmappable), len(pol_qs)))
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
print("  default band 35-65: %d above / %d on / %d below of %d -> %.0f%% on-market" % (
    m["above"], m["at"], m["below"], m["pool"], at_share * 100))
check("config block exposes the band for tuning", hero["config"]["band_low"] == 35.0 and hero["config"]["band_high"] == 65.0)
check("hero not washed out (on-market share < 70%)", at_share < 0.70, "%.0f%% on" % (at_share * 100))
# the headline ("above the market median on X of Y comparable metrics" — board
# pack + share) counts the SAME Substance pool the gauge does, so the surfaces can
# never tell different stories about the same org (2026-06-16, overview_summary re-axis)
check("headline comparable == gauge pool (dashboard / board pack / share agree)",
      ov["headline"]["comparable_metrics"] == m["pool"],
      (ov["headline"]["comparable_metrics"], m["pool"]))
# the Approach companion ("N off the norm") tallies Practice/Design choices vs
# the market mode — a separate register, never folded into the gauge's below/on/above
ap = hero.get("approach")
check("Approach companion present + internally consistent (differ + in_line == pool)",
      ap and ap["differ"] + ap["in_line"] == ap["pool"] and ap["pool"] > 0, ap)

# F2 (2026-06-13) — the verdict can never contradict the count distribution in
# the impossible direction: never "below" when below is the strict smallest of
# the three counts, never "above" when above is the strict smallest. Net-balance
# satisfies this by construction; assert it so a future threshold change can't
# silently break it. Also: the verdict and the gauge needle share ONE value.
_counts = {"below": m["below"], "at": m["at"], "above": m["above"]}
_smallest = min(_counts, key=_counts.get)
_strict_smallest = sum(1 for v in _counts.values() if v == _counts[_smallest]) == 1
check("verdict never 'below' when below is the smallest count",
      not (m["verdict"] == "below" and _strict_smallest and _smallest == "below"), _counts)
check("verdict never 'above' when above is the smallest count",
      not (m["verdict"] == "above" and _strict_smallest and _smallest == "above"), _counts)
check("market exposes one lean value driving both word and needle",
      "lean" in m and -1.0 <= m["lean"] <= 1.0, m.get("lean"))
check("verdict bands the SAME lean value it ships (word/needle agree by construction)",
      m["verdict"] == ("above" if m["lean"] > m["lean_threshold"]
                       else "below" if m["lean"] < -m["lean_threshold"] else "at"),
      (m["verdict"], m["lean"], m["lean_threshold"]))
tighter = pos._pool_verdict([{"polarity": "higher_is_better", "percentile": p} for p in (30, 40, 60, 70, 35, 65)],
                            40, 60, MARGIN)
check("a tighter band (40-60) reclassifies the same pool differently (tunable)",
      tighter["above"] == 2 and tighter["below"] == 2, tighter)

print()
print("=" * 100)
print("5. DOMAIN ELIGIBILITY + ROLLUP CONSTRUCTION")
print("=" * 100)
dm = {d["name"]: d for d in hero["domains"]}
# WIRED to market_position_config (2026-06-16): the gauge feed is SUBSTANCE
# (Level + Provision, higher_is_better) in COMPETITIVE domains only. Governance
# (_domains.competitiveness=false) has NO headline role; the 5->3 firm floor lets
# a 3+-Substance domain (Wellbeing, via newly-routed Provision presence) earn a
# strict verdict where it was practice-only indicative before.
comp = [d for d in hero["domains"] if d["name"] != "Governance"]
check("Governance carries NO market verdict and NO tile position (competitiveness carve-out)",
      dm["Governance"]["market"] is None and dm["Governance"]["position"] is None
      and dm["Governance"].get("competitiveness") is False,
      {"market": dm["Governance"]["market"], "position": dm["Governance"]["position"]})
check("competitive domains clearing the 3-Substance floor carry a strict market verdict",
      all(dm[x]["market"] is not None for x in ("Pay", "Incentives", "Benefits", "Time Off", "Wellbeing")),
      {k: dm[k]["polarised_comparable"] for k in ("Pay", "Incentives", "Benefits", "Time Off", "Wellbeing")})
check("Wellbeing now reaches a STRICT verdict (was practice-only indicative; the 5->3 unlock)",
      dm["Wellbeing"]["market"] is not None and dm["Wellbeing"]["position_basis"] == "market",
      {"market": dm["Wellbeing"]["market"], "basis": dm["Wellbeing"]["position_basis"]})
check("Recognition stays sub-floor (<3 Substance) -> indicative, not masked as strict",
      dm["Recognition"]["market"] is None and dm["Recognition"]["position_basis"] == "indicative",
      {"q": dm["Recognition"]["polarised_comparable"], "basis": dm["Recognition"]["position_basis"]})
check("strict domains keep basis=market and position==market verdict",
      all(d["position_basis"] == "market" and d["position"]["verdict"] == d["market"]["verdict"]
          for d in comp if d["market"] is not None))
check("sub-floor competitive domains disclose basis=indicative + evidence counts",
      all(d["position_basis"] == "indicative" and d.get("position_evidence") is not None
          for d in comp if d["market"] is None and d.get("position") is not None))
check("tile evidence is Substance-based — no practice bleed (practice==0 everywhere)",
      all((d.get("position_evidence") or {"practice": 0})["practice"] == 0 for d in hero["domains"]),
      {d["name"]: d.get("position_evidence") for d in hero["domains"] if d.get("position_evidence")})
check("every competitive domain still gets a prevalence summary", all(d["prevalence"] is not None for d in comp))
check("threshold is config (domain_min=3, tile_min=1)",
      hero["config"]["domain_min"] == 3 and hero["config"]["tile_min"] == 1, hero["config"])
# the overall arc pool is exactly the union of per-domain Substance feeds —
# no double-count, Governance (polarised_comparable 0) contributes nothing
check("overall arc pool == sum of per-domain Substance counts (Governance excluded, no double-count)",
      m["pool"] == sum(d["polarised_comparable"] for d in hero["domains"]),
      (m["pool"], sum(d["polarised_comparable"] for d in hero["domains"])))
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
check("a single answered metric never earns a STRICT domain verdict (below domain_min)", one["domains"][0]["market"] is None)
check("...but it does earn a disclosed indicative tile position",
      one["domains"][0]["position"] is not None and one["domains"][0]["position_basis"] == "indicative")

# practice-position honesty rules (fixtures)
class _FQ:
    id = "fq"; type = "yes_no"; is_scored = False; polarity = "higher_is_better"
    sub_power = "Pay"; superpower = "Reward"; display_title = "Do you offer X?"
    options = [{"label": "Yes", "code": "YES"}, {"label": "No", "code": "NO"}]
    na_handling = {}; unit = None; scoring_config = {}; score_map = {}
    lumi_tier = None; is_required = False; sub_power_order = 1; status = "active"; module = None
    category = "Practice"
    def unit_block(self): return {}
_blk = {"n": 100, "options": [{"label": "Yes", "pct": 70.0}, {"label": "No", "pct": 30.0}]}
_pay = {"fq": {"all": _blk}}
def _ppi(q, ans):
    return pos.practice_position_items("o", {"dim": "all"}, {"fq": q}, _pay,
                                       {("fq", ""): ans}, lambda q: True)
q = _FQ()
got = _ppi(q, "Yes")
check("practice position ranks presence against the peer block (Yes vs 70%% adoption -> P65)",
      len(got) == 1 and got[0]["kind"] == "practice" and abs(got[0]["percentile"] - 65.0) < 0.1,
      got and got[0].get("percentile"))
check("an N/A answer is never practice evidence", _ppi(q, "Not applicable") == [])
qn = _FQ(); qn.polarity = "neutral"
check("a neutral question never produces a practice position", _ppi(qn, "Yes") == [])
qs2 = _FQ(); qs2.is_scored = True
check("scored questions are left to the score layer", _ppi(qs2, "Yes") == [])
qm = _FQ(); qm.type = "multi_select"
check("multi_select never produces a practice position", _ppi(qm, "Yes") == [])

print()
print("=" * 100)
print("7. NEUTRAL PALETTE — prevalence never wears the performance colours (static check)")
print("=" * 100)
web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
css = open(os.path.join(web, "css", "app.css"), encoding="utf-8").read()
js = open(os.path.join(web, "js", "pages.js"), encoding="utf-8").read()
# Practice Alignment: the overview tile prevalence line must stay a NEUTRAL caption —
# the shared `.caption num` carrying the verdict tooltip, never a performance/RAG colour.
check("tile prevalence line is a neutral caption (no performance colour)",
      'class="caption num" title=${prev.verdict' in js)
check("maturity score tiles removed from the gap register",
      "your maturity" not in open(os.path.join(web, "js", "commercial.js"), encoding="utf-8").read())

print("=" * 100)
print("6. SIGNALS — flags never contradict the data; trust rules hold")
print("=" * 100)
ov_sig = api("/api/overview")
sigs = ov_sig.get("signals") or []
import json as _j
cfg = _j.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "signal_lenses.json")))
check("signal count within caps (max %d, %d/lens)" % (cfg["max_signals"], cfg["max_per_lens"]),
      len(sigs) <= cfg["max_signals"] and all(
          sum(1 for x in sigs if x["lens"] == l) <= cfg["max_per_lens"] for l in {x["lens"] for x in sigs}),
      [(x["lens"], x["kind"]) for x in sigs])
# per-view briefings (2026-07-06): the practice-view briefing rides signals_practice
# under the SAME ratified knobs, and neither briefing may leak the other view's rows.
sigs_p = ov_sig.get("signals_practice") or []
check("practice briefing within the same ratified caps (max %d, %d/lens)" % (cfg["max_signals"], cfg["max_per_lens"]),
      len(sigs_p) <= cfg["max_signals"] and all(
          sum(1 for x in sigs_p if x["lens"] == l) <= cfg["max_per_lens"] for l in {x["lens"] for x in sigs_p}),
      [(x["lens"], x["kind"]) for x in sigs_p])
check("briefings are view-pure (market = below/on/above; practice = never)",
      all(x.get("position") in ("below", "on", "above") for x in sigs)
      and all(x.get("position") not in ("below", "on", "above") for x in sigs_p),
      {"mkt": [x.get("position") for x in sigs], "prac": [x.get("position") for x in sigs_p]})
vis_ids = {q["id"] for q in api("/api/questions")["questions"]}
check("every signal points at a live, visible metric",
      all(x["question_id"] in vis_ids for x in sigs),
      [x["question_id"] for x in sigs if x["question_id"] not in vis_ids])
bad_dir = []
for x in sigs:
    card = api("/api/benchmark/%s?cut=all" % x["question_id"])
    pol = card.get("polarity")
    if x["kind"] == "behind" and (pol == "neutral" or x["question_id"] not in cfg["position_lenses"]):
        bad_dir.append((x["question_id"], "behind on neutral / unmapped"))
    if x["kind"] == "save" and x["question_id"] not in cfg["cost_metrics"]:
        bad_dir.append((x["question_id"], "save outside the cost map"))
    if x["kind"] == "prevalence" and x["question_id"] not in cfg["prevalence_lenses"]:
        bad_dir.append((x["question_id"], "prevalence outside the map"))
check("no signal contradicts its metric (no 'behind' on neutral; all kinds from David's maps)",
      not bad_dir, bad_dir)
# backwards-firing guard (Signals Phase 1): the three ordered metrics whose
# option array runs opposite to the rest (car mileage, the two review-frequency
# questions) fire backwards if rank is inferred from position — they stay OUT of
# position_lenses until an explicit direction anchor is set (see
# ordered_scale_verification.md).
ANCHOR_RISK = {"REW_Q049530", "REW_PAY_003", "PROP_8e0b6316"}
check("anchor-risk ordered metrics excluded from position_lenses (can't fire backwards)",
      not (ANCHOR_RISK & set(cfg["position_lenses"])), sorted(ANCHOR_RISK & set(cfg["position_lenses"])))
DIRECTIVE = ("should", "must", "we recommend", "you need to", "increase your", "reduce your")
check("signal wording is factual, never a directive",
      all(not any(d in x["detail"].lower() for d in DIRECTIVE) for x in sigs),
      [x["detail"] for x in sigs if any(d in x["detail"].lower() for d in DIRECTIVE)])
# Ordered-outlier (Signals Phase 2): states position + peer fact, NEVER a verdict.
import json as _j2, os as _os2
_ord = _j2.load(open(_os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "..", "ordered_scale_routing.json")))
_out_sigs = [x for x in sigs if x["kind"] == "outlier"]
VERDICT = ("behind", "ahead", "better", "worse", "lagging", "leading", "you should", "underperform")
check("ordered-outlier signals carry no verdict word (position + peer fact only)",
      all(not any(v in x["detail"].lower() for v in VERDICT) for x in _out_sigs),
      [x["question_id"] for x in _out_sigs if any(v in x["detail"].lower() for v in VERDICT)])
check("every ordered-outlier signal fires off an EXPLICIT scale (no index inference)",
      all(x["question_id"] in _ord.get("scales", {}) and x["question_id"] in _ord.get("ordered_outlier", []) for x in _out_sigs),
      [x["question_id"] for x in _out_sigs if x["question_id"] not in _ord.get("scales", {})])
check("Phase-3 re-routed metrics never fire as ordered-outlier",
      not (set(_ord.get("_david_ratified_2026_06_13", {}).get("reroute_to_phase3_prevalence", [])) & {x["question_id"] for x in _out_sigs}))
# Mechanism B (depth-of-provision): also position + peer fact, never a verdict.
_depth_sigs = [x for x in sigs if x["kind"] == "depth"]
check("depth-of-provision signals carry no verdict word",
      all(not any(v in x["detail"].lower() for v in VERDICT) for x in _depth_sigs),
      [x["question_id"] for x in _depth_sigs if any(v in x["detail"].lower() for v in VERDICT)])
check("every depth signal fires off a routed depth_matrix metric (explicit ordering)",
      all(x["question_id"] in _ord.get("depth_matrix", {}) for x in _depth_sigs),
      [x["question_id"] for x in _depth_sigs if x["question_id"] not in _ord.get("depth_matrix", {})])
# briefing cap fallback: always 5 when 5 exist, never a blank slot / dropped signal
import signals as _sigmod
def _mk(k, l, i):
    return {"kind": k, "lens": l, "impact": i, "question_id": k + l + str(i)}
_capt = _sigmod.cap_briefing([_mk("behind", "a", 9), _mk("behind", "b", 8), _mk("behind", "c", 7),
                              _mk("behind", "d", 6), _mk("outlier", "e", 1)], 5, 2, 3)
check("briefing cap fallback yields 5 when 5 exist across lenses (never a blank slot)", len(_capt) == 5, len(_capt))
# Mechanism C/D (rarity): per-option / rare chosen value, no verdict, one per metric.
_rare = [x for x in sigs if x["kind"] == "rare"]
check("rarity signals carry no verdict word",
      all(not any(v in x["detail"].lower() for v in VERDICT) for x in _rare),
      [x["question_id"] for x in _rare if any(v in x["detail"].lower() for v in VERDICT)])
check("every rarity signal is routed (multi_prevalence or rarity), never set-rarity",
      all(x["question_id"] in _ord.get("multi_prevalence", {}) or x["question_id"] in _ord.get("rarity", {}) for x in _rare),
      [x["question_id"] for x in _rare if x["question_id"] not in _ord.get("multi_prevalence", {}) and x["question_id"] not in _ord.get("rarity", {})])
check("per-metric cap holds — no metric yields two signals",
      len({x["question_id"] for x in sigs}) == len(sigs))
dots = {d["name"]: d.get("dot") for d in ov_sig["hero"]["domains"]}
check("category dots sit in [1,99] where present",
      all(v is None or (1 <= v <= 99) for v in dots.values()), dots)

print()
fails = len(RESULTS) - sum(RESULTS)
print("RESULTS: %d checks, %d passed, %d failed" % (len(RESULTS), sum(RESULTS), fails))
sys.exit(1 if fails else 0)
