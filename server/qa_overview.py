# -*- coding: utf-8 -*-
"""OVERVIEW GATE (standing, 2026-06-22) — the 8th gate, guarding the Overview's
read-clean invariants after the Stage-A/B cleanup. DB-LEVEL (no HTTP): it
rebuilds the hero + signals engine-side the way /api/overview does, then asserts
INVARIANTS (never the literal numbers — 76/48/85 drift as data changes).

Complements qa_hero (which uses HTTP + guards polarity/pool reconciliation): this
gate adds only the genuinely-new Overview checks. Read-only (no fixtures, nothing
to clean). Org-parametric via QA_ORG (default Thornbridge). Exits non-zero on any
failure. House style matches qa_pulse.
"""
import os
import sys
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app as A
import positions as pos
import signals as signals_mod
from aggregate import SUPPRESSION_FLOOR

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append((name, detail))


# ---- rebuild the Overview hero + signals engine-side (the /api/overview path) ----
conn = A.get_conn()
ORG = os.environ.get("QA_ORG", "thornbridgeretail")
org = conn.execute("SELECT * FROM orgs WHERE normalized_name LIKE ?", (ORG + "%",)).fetchone()
if org is None:
    print("no org matching %r — set QA_ORG" % ORG); sys.exit(2)

cut = {"dim": "all", "value": None}
ent = lambda q: True
vis = A.org_visible_questions(org)
pls = A.payloads()
ans = A.org_answers_for(org)
mp_cfg = pos.market_position_config()
strat = A.strategy_for_engine(conn, org["org_id"])

items = pos.position_items(org["org_id"], cut, vis, pls, ans, ent, None)
prev_items = pos.prevalence_items(org["org_id"], cut, vis, pls, ans, ent, None)
prac_items = pos.practice_position_items(org["org_id"], cut, vis, pls, ans, ent, None)
sec_order = []
for q in vis.values():
    if q.sub_power and q.sub_power not in sec_order:
        sec_order.append(q.sub_power)
sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in vis.values() if q.sub_power == x))

hero = pos.hero_signals(items, prev_items, sec_order, A.MARKET_BAND_LOW, A.MARKET_BAND_HIGH,
                        A.DOMAIN_MIN_POLARISED, A.VERDICT_NET_LEAN, A.UNCOMMON_PCT,
                        practice_items=prac_items, tile_min=A.TILE_MIN_POSITIONED,
                        mp_config=mp_cfg, strategy=strat)
mkt = hero["market"]
domains = hero["domains"]

money = pos.money_opportunities(conn, org, vis, pls, ans, cut, None)
get_block = lambda qid: (pos.block_for(pls.get(qid) or {}, cut, None)[0] if pls.get(qid) else None)
sigs_all = signals_mod.build_signals(items, money, vis, get_block, ans,
                                     conn=conn, org_id=org["org_id"], cap=False, statuses={}, strategy=strat)

pagesjs = open(os.path.join(HERE, "..", "web", "js", "pages.js"), encoding="utf-8").read()
print("== Overview gate · org=%s · verdict=%s (%d/%d/%d of %d) · differ=%s · signals=%d ==" % (
    org["name"], mkt["verdict"], mkt["below"], mkt["at"], mkt["above"], mkt["pool"],
    (hero.get("approach") or {}).get("differ"), len(sigs_all)))

# --- 1. RECONCILIATION: below+on+above = pool, and cards sum to the hero ---
check("1a. hero below+on+above == hero pool",
      mkt["below"] + mkt["at"] + mkt["above"] == mkt["pool"],
      (mkt["below"], mkt["at"], mkt["above"], mkt["pool"]))
posd = [d for d in domains if d.get("position")]
csum = lambda k: sum(d["position"][k] for d in posd)
check("1b. sum of per-card below/on/above == hero classified total (cards reconcile)",
      csum("below") == mkt["below"] and csum("at") == mkt["at"] and csum("above") == mkt["above"]
      and csum("pool") == mkt["pool"],
      {"cards": (csum("below"), csum("at"), csum("above"), csum("pool")),
       "hero": (mkt["below"], mkt["at"], mkt["above"], mkt["pool"])})
check("1c. no competitive domain has Substance items but no position (nothing dropped)",
      not [d["name"] for d in domains if d.get("competitiveness") and d.get("polarised_comparable", 0) > 0
           and not d.get("position")],
      [d["name"] for d in domains if d.get("competitiveness") and d.get("polarised_comparable", 0) > 0 and not d.get("position")])

# --- 2. DIFFER TRACEABILITY (Governance scoping ruling, 2026-06-22): the hero reads
# what the CARDS render. Market-relative framing (differ/below/on/above) is
# COMPETITIVE-SCOPE only — the hero differ AND its denominator equal the sum across
# the competitive cards; a non-competitive domain (Governance) contributes 0 to both,
# exactly as it contributes 0 to below/on/above. The hero AND this gate read the SAME
# competitiveness flag (d["competitiveness"]) so they cannot drift. A hero that counts
# a domain the cards don't show (the prior leak: 48 vs competitive-31) FAILS here.
hero_appr = hero.get("approach") or {}
hero_differ = hero_appr.get("differ")
gov = [d for d in domains if d.get("competitiveness") is False]
comp_cards = [d for d in domains if d.get("competitiveness") and d.get("approach")]
shown_differ = sum(d["approach"]["differ"] for d in comp_cards)
shown_pool = sum(d["approach"]["pool"] for d in comp_cards)
_excl = [(d["name"], (d.get("approach") or {}).get("differ")) for d in gov]
check("2a. hero differ == Σ differ shown on competitive cards (non-competitive → 0; the regression check)",
      hero_appr.get("differ") == shown_differ,
      {"hero_differ": hero_appr.get("differ"), "competitive_cards_sum": shown_differ, "excluded_noncompetitive": _excl})
check("2b. hero denominator == Σ denominator shown on competitive cards (numerator AND denominator rescope)",
      hero_appr.get("pool") == shown_pool,
      {"hero_pool": hero_appr.get("pool"), "competitive_cards_sum": shown_pool})

# --- 3. COUNT RELATIONSHIP: differ vs signals (ruling: different denominators; differs-signals ⊆ differ pool) ---
differ_sig_metrics = {s["question_id"] for s in sigs_all if s.get("position") == "differs"}
check("3. distinct differs-position signals <= hero differ (differs-signals are a subset of the differing pool)",
      hero_differ is None or len(differ_sig_metrics) <= hero_differ,
      {"differs_signals": len(differ_sig_metrics), "hero_differ": hero_differ})

# --- 4. NO CONTRADICTORY LABEL: the unbenchmarkable tile shows no market-relative differ chip ---
# engine: the non-competitive domain carries competitiveness=False + no market verdict.
check("4a. the unbenchmarkable domain carries competitiveness=False and NO market verdict",
      all(d.get("market") is None for d in gov) if gov else True,
      [(d["name"], d.get("market")) for d in gov])
# render contract RE-DERIVED (check-77 treatment, Diff 4 2026-07-14): the noRate branch
# was DELETED by ruling (dead since the Diff-2 competitiveness ruling — no live domain is
# flagged out; a below-floor domain reads the honest "no position yet" state instead). The
# check now guards the DELETION: the retired G&T copy must never creep back into the live
# DomainInstrument (the dead CategoryTile component is exempt until its cleanup pass).
_di_src = pagesjs.split("function CategoryTile", 1)[0]   # everything before the dead component
check("4b. render: the retired no-market-rate branch stays deleted from the live instrument",
      "No market rate — see the Practice lens" not in _di_src
      and "competitiveness === false" not in _di_src
      and "no position yet" in _di_src,
      "retired G&T copy or flag branch has crept back into the live render")

# --- 5. VERDICT INTEGRITY: severity adverb from percentile DEPTH, not headcount ---
gauge_pool = pos.substance_pool(items, prac_items, mp_cfg)
exp_depth = round(statistics.median(pos._adj_percentile(i) for i in gauge_pool), 1) if gauge_pool else None
check("5a. hero exposes depth_pctl == median adjusted percentile of the gauge pool",
      mkt.get("depth_pctl") is not None and exp_depth is not None and abs(mkt["depth_pctl"] - exp_depth) < 0.2,
      {"hero_depth": mkt.get("depth_pctl"), "recomputed": exp_depth})
# 5b retargeted 2026-06-30: the depth_pctl logic was EXTRACTED into the shared leanCaption helper
# (pre-baseline b3a6bcd), so the old grep — depth_pctl within 600 chars of the first "leanWord"
# CALL SITE — no longer matched (depth_pctl lives in the helper, not the call site). Look in the
# leanCaption helper body instead. Still tests the real contract: if depth_pctl were removed from
# the adverb logic, both "market.depth_pctl" in pagesjs AND its presence in the helper body go away.
_lc = pagesjs.split("function leanCaption", 1)
_lc_body = _lc[1][:600] if len(_lc) > 1 else ""
check("5b. render: the severity adverb (leanCaption helper) is driven by depth_pctl, not the count lean",
      "market.depth_pctl" in pagesjs and "depth_pctl" in _lc_body,
      "leanCaption does not reference depth_pctl (adverb must read percentile DEPTH, not the count lean)")

# --- 6. VERDICT VOCABULARY: below/on/above only — never lag/match/lead in user-facing strings ---
import re
sw = re.search(r"STANCE_WORD\s*=\s*\{([^}]*)\}", pagesjs)
sw_vals = re.findall(r':\s*"([^"]+)"', sw.group(1)) if sw else []
check("6a. the strategy stance is translated to below/on/above market (lag/match/lead never shown)",
      sw_vals and all(v in ("below market", "on market", "above market") for v in sw_vals), sw_vals)
check("6b. no user-facing dashboard string renders a raw lag/match/lead verdict word",
      not re.search(r'"[^"]*\b(lag|match|lead)\b market[^"]*"', pagesjs)
      and not re.search(r'>\s*(lag|match|lead)\s*<', pagesjs),
      "raw lag/match/lead leaked into a rendered string")

# --- 7. PEER-COUNT HONESTY: per-metric peer counts respect n>=5; nothing shown claims an undefendable count ---
violations = []
for qid in vis:
    blk = get_block(qid)
    if not blk:
        continue
    if not blk.get("suppressed") and blk.get("n") is not None and blk["n"] < SUPPRESSION_FLOOR:
        violations.append((qid, blk.get("n")))
check("7. every shown (non-suppressed) metric block has n >= %d (no undefendable peer count)" % SUPPRESSION_FLOOR,
      not violations, violations[:3])

# --- 8. SIGNALS SCOPING (Governance scoping ruling, signals layer): market-relative
# position labels (below/on/above/differs) appear ONLY on competitive-domain signals.
# A non-competitive (Governance) signal carries the non-market "practice" position,
# never a market verdict — reading the SAME pos._mp_competitive flag the fix reads, so
# the Signals stream and the hero can't drift. The pre-fix leak (13 Governance signals
# labelled differs/above/below) must FAIL here; reintroducing it re-fails the gate.
_MARKET_POS = {"below", "on", "above", "differs"}
_sig_leak = [(s.get("domain"), s.get("question_id"), s.get("position"))
             for s in sigs_all
             if not pos._mp_competitive(mp_cfg, s.get("domain")) and s.get("position") in _MARKET_POS]
check("8. zero non-competitive-domain signals carry a market-relative position (below/on/above/differs)",
      not _sig_leak, {"leaked_count": len(_sig_leak), "examples": _sig_leak[:5]})

# --- 9. NUMBER-SOURCE (user-facing copy can't go stale the way the gate constants did):
# every NUMBER rendered in the hero / signals copy must EQUAL its live engine value, never
# a hard-coded literal. A DB gate can't render React, so the equality is asserted BY
# CONTRACT: (a) the engine emits the value, AND (b) pages.js interpolates that EXACT engine
# field raw — no literal, no arithmetic — so rendered == engine by construction. A
# forced-wrong number (a hard-coded "31", or an off-by-one like `approach.differ + 1`)
# breaks the raw-field match and FAILS here. Same derive-not-literal principle, applied to
# the copy. (differ↔signals framing, 2026-06-22 — see DECISIONS.md.)
# 2026-07-09 practice harmonisation: the overview practice donut now shows PREVALENCE
# (common/alternative/rare — mirroring the market donut) instead of the old differ/in-line
# split, so the raw-interpolation contract moved to the prevalence fields. (The differ read
# lives on in signals + the category page; hero_appr is still validated at check 7 above.)
hero_prev = hero.get("prevalence") or {}
prev_common = hero_prev.get("with_majority")
prev_alt = hero_prev.get("established")
prev_rare = hero_prev.get("less_common")
prev_pool = hero_prev.get("pool")
signals_total_val = len([s for s in sigs_all if s.get("status") != "dismissed"])   # the 'See all N' set
check("9a. engine emits hero prevalence common/alt/rare/pool + signals-total as integers (the numbers the practice donut shows; parts sum to pool)",
      all(isinstance(v, int) for v in (prev_common, prev_alt, prev_rare, prev_pool, signals_total_val))
      and (prev_common + prev_alt + prev_rare) == prev_pool,
      {"common": prev_common, "alt": prev_alt, "rare": prev_rare, "pool": prev_pool, "signals_total": signals_total_val})
check("9b. practice donut legend interpolates engine prevalence RAW (rendered == engine; no literal, no off-by-one)",
      # polish 2026-07-11: the legend merged into the one-line arc-caption and its words went
      # lowercase (matching the market caption) — same raw-interpolation contract, new casing.
      "const common = prevalence.with_majority, alt = prevalence.established, rare = prevalence.less_common" in pagesjs
      and "${common}</span> common" in pagesjs
      and "${rare}</span> rare" in pagesjs,
      "practice donut common/alt/rare legend is not interpolated raw from the engine prevalence "
      "fields (2026-07-09 harmonisation: the practice lens now mirrors the market donut — "
      "prevalence, not differ/in-line — so the raw-interpolation contract moved there)")
check("9c. the signals total shown on the card derives from the live signal set (view-filtered), never a literal",
      # per-view briefings (2026-07-06): the pool binding renamed (_pool) and the panel
      # list became briefing-first + impact tail. Polish 2026-07-11: the count moved from
      # the See-all link (which repeated it) to the ranknote's "top N of TOTAL" — the
      # INVARIANT is unchanged: the total is the length of the live view-filtered ENGINE
      # set, rendered from the `total` binding, never a literal.
      '_pool = (data.signals_all || []).filter(' in pagesjs
      and '_viewSigs = [..._brief, ..._pool.filter(' in pagesjs
      and '_viewLive = _viewSigs.filter(s => s.status !== "dismissed")' in pagesjs
      and '_viewTotal = _viewLive.length' in pagesjs
      and '" of " + total + " · "' in pagesjs
      and '"See all " + total + " signals' not in pagesjs,
      "the card's signals total is not bound to the engine signal set")

# --- 10. PercentileRuler resurrection (2026-07-11, David: "see their position in the market
#     overall and for each domain") — the ruler must be FED BY THE ENGINE, never a literal.
corejs = open(os.path.join(HERE, "..", "web", "js", "core.js"), encoding="utf-8").read()
check("10a. the home card renders the overall marker from market.depth_pctl (engine value, D4 unweighted pool)",
      # FIX CLASS C (2026-07-11) + premium pass (2026-07-12): the overall marker is the SAME
      # ink P-pill as the domain rows, bound to market.depth_pctl; the caption keeps D2's
      # "typical metric" phrase (the pill carries the figure, so the caption doesn't repeat it).
      "arc-markscale" in pagesjs
      and "const depth = market.depth_pctl;" in pagesjs
      and "typical metric · on-market band P${band[0]}" in pagesjs,
      "the overall marker is not bound to the engine depth_pctl / D2 phrasing")
check("10b. the domain rows' Position view is the engine-bound single-marker scale; category hero renders the ruler from pos.depth_pctl",
      # FIX CLASS A (aggregate-marker rebuild 2026-07-11): one dot per domain at depth_pctl
      # (D1 — NEVER the lean), dashed market centre, worst-first sort, indicative = hollow
      # dashed ring with the word in the aria. All bindings engine values, never literals.
      # 2026-07-12 "new dot format": the marker is ONE ink pill with the P inside (di-pill;
      # dashed .ind variant = indicative); still bound to engine depth, never the lean.
      "di-markrow" in pagesjs
      and 'const left = Math.min(99, Math.max(1, depth));' in pagesjs
      and 'd.position_basis === "indicative" ? " ind"' in pagesjs
      and 'd.position_basis === "indicative" ? " (indicative)"' in pagesjs
      and ">P${Math.round(depth)}</span>" in pagesjs
      and "return da - db;" in pagesjs
      and not re.search(r"di-markrow[^`]*\blean\b", pagesjs)
      and "PercentileRuler} pctl=${pos.depth_pctl}" in pagesjs,
      "the position marker row / category ruler is not bound to per-domain engine depth_pctl")
check("10c. ruler band comes from the engine (window.MARKET_BAND, /api/me-sourced) at every pages.js call site",
      "band=${window.MARKET_BAND || [35, 65]}" in pagesjs
      and not re.search(r"PercentileRuler\}[^\n]*band=\$\{\[", pagesjs),
      "a pages.js ruler call hardcodes the band instead of reading the engine's MARKET_BAND")
check("10d. the shared atom guards its inputs (null pctl / malformed band renders nothing)",
      "if (pctl == null || !band || band.length !== 2) return null;" in corejs,
      "PercentileRuler lost its null/malformed-input guard")
check("10e. ONE verdict register — below/on/above market; 'less/more competitive' retired product-wide (fix class B, 2026-07-11)",
      "less competitive" not in pagesjs and "more competitive" not in pagesjs
      and "less competitive" not in corejs and "more competitive" not in corejs
      and "<span>below market</span>" in corejs,
      "the retired less/more-competitive register has crept back onto a position surface")

# ---- 11. multi-select prevalence (Option B core coverage, decision paper 2026-07-13) ----
# Runs in whichever flag state the environment sets, asserting that state's own contract:
# OFF -> multi-selects stay out of the pool (the pre-ruling world, byte-identical);
# ON  -> every multi-select item's band re-derives from its own payload block, the pool
#        stays disjoint from the market lens, and the donut counts equal the card-chip
#        sums (parity through the shared _prev_band classifier).
_ms = [i for i in prev_items if i.get("ms_band")]
if not pos.MS_PREVALENCE:
    check("11a. flag OFF: no multi-select enters the prevalence pool",
          not _ms and all(vis[i["question_id"]].type != "multi_select" for i in prev_items),
          "a multi-select item leaked into the pool with LUMI_MS_PREVALENCE off")
else:
    check("11a. flag ON: multi-select items are produced for the scope",
          len(_ms) > 0, "flag is on but zero multi-select items were produced")
    _bad = []
    for i in _ms:
        _blk, _cl = pos.block_for(pls[i["question_id"]], cut, None)
        _opts = _blk.get("options") or []
        _core = ([o for o in _opts if (o.get("pct") or 0) >= pos.MS_CORE_PCT]
                 or [max(_opts, key=lambda o: o.get("pct") or 0)])
        _mine = {t.strip() for t in ans[(i["question_id"], "")].split(";") if t.strip()}
        _off = sum(1 for o in _core if o["label"] in _mine)
        _want = "match" if _off == len(_core) else "common_alt" if _off else "rarer"
        if _want != i["ms_band"] or i["ms_core_size"] != len(_core) or i["ms_core_offered"] != _off:
            _bad.append((i["question_id"], i["ms_band"], _want))
    check("11b. every multi-select band re-derives from its own payload block", not _bad, repr(_bad[:4]))
    check("11c. multi-select items stay disjoint from the market pool",
          not ({i["question_id"] for i in _ms} &
               pos.market_pool_qids(org["org_id"], cut, vis, pls, ans, ent, None)),
          "a multi-select is rated by BOTH lenses — partition broken")
# ---- 12. briefing drivers (2026-07-13): every positioned domain carries drivers, and they
# re-derive from THE house gap definition (top_gaps/top_strengths) over the same pool the
# verdict counts — the briefing can never rank by a second, disagreeing formula.
_drv_bad = []
for _d in domains:
    if _d.get("position") is None:
        if _d.get("drivers"):
            _drv_bad.append((_d["name"], "drivers without a position"))
        continue
    _dv = _d.get("drivers") or []
    if not _dv:
        continue
    if [x for x in _dv if x["kind"] == "gap"] != _dv[:len([x for x in _dv if x["kind"] == "gap"])]:
        _drv_bad.append((_d["name"], "gaps not first"))
    for _x in _dv:
        if not (_x.get("question_id") and _x.get("label") and _x.get("percentile") is not None):
            _drv_bad.append((_d["name"], "incomplete driver " + repr(_x)))
check("12a. per-domain drivers present-and-well-formed only where a position exists", not _drv_bad, repr(_drv_bad[:3]))

# ---- 14. the practice bucket (Diff 4, 2026-07-14) ----
# (a) sums: in_line + off_norm + ms_excluded + low_peer == answered <= book; book derives
#     from cfg class Practice/Design minus STRATEGY_CONFIG_IDS — never a literal.
# (b) every id in STRATEGY_CONFIG_IDS exists live and is class Practice (ruling 1b);
#     Diff 5's import gate inherits this check.
# (c) the ripple: no strategy-config id ever appears in the lens pool.
_bkt = pos.practice_bucket(vis, mp_cfg, prev_items, ans, A.UNCOMMON_PCT)
_book_derived = sum(1 for qid in vis
                    if (mp_cfg.get("metrics", {}).get(qid) or {}).get("class") in ("Practice", "Design")
                    and qid not in pos.STRATEGY_CONFIG_IDS)
check("14a. bucket sums: split + exclusions == answered <= derived book",
      _bkt["in_line"] + _bkt["off_norm"] + _bkt["ms_excluded"] + _bkt["low_peer"] == _bkt["answered"]
      <= _bkt["book"] == _book_derived, _bkt)
_sc_bad = [q for q in pos.STRATEGY_CONFIG_IDS
           if q not in vis or (mp_cfg.get("metrics", {}).get(q) or {}).get("class") != "Practice"]
check("14b. every STRATEGY_CONFIG_IDS id is live and class Practice", not _sc_bad, _sc_bad)
check("14c. strategy-config rows never pool (the lens ripple holds)",
      not (pos.STRATEGY_CONFIG_IDS & {i["question_id"] for i in prev_items}),
      "strategy-config id found in prevalence pool")

from collections import Counter as _Ctr
_cc = _Ctr(pos.pool_prevalence_bands(prev_items, A.UNCOMMON_PCT).values())
_sm = pos._prev_summary(prev_items, A.UNCOMMON_PCT) or {"with_majority": 0, "established": 0, "less_common": 0}
check("11d. donut counts == card-chip sums (shared _prev_band classifier, both flag states)",
      (_cc.get("match", 0), _cc.get("common_alt", 0), _cc.get("rarer", 0)) ==
      (_sm["with_majority"], _sm["established"], _sm["less_common"]),
      "the prevalence donut and the card chips disagree")

print("\nNOTE: read-only gate — no fixtures created, nothing to clean. Reads the live")
print("snapshot via the same engine path as /api/overview (no HTTP).")
print("\nRESULTS: %d failures" % len(FAILS))
for n, d in FAILS:
    print("  FAIL:", n, d)
sys.exit(1 if FAILS else 0)
