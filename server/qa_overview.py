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
# render contract (2026-07-08 hero redesign): the live no-market-rate surface is the
# DomainInstrument row — its noRate branch must show the honest "No market rate" note
# and never a market-relative differ chip or a position dot. (The old CategoryTile
# cat-na branch retired from the Overview render with the tiles.)
nb = pagesjs.split("noRate ? html`", 1)
norate_branch = nb[1].split(": html`", 1)[0] if len(nb) > 1 else ""
_norate_note = norate_branch.split("`", 1)[0]   # the noRate arm alone, before the next template
check("4b. render: the 'no market rate' row branch shows the honest note and NO differ chip",
      "di-norate" in _norate_note and "No market rate" in _norate_note
      and "differLine" not in norate_branch and "cat-differ" not in norate_branch,
      "noRate branch leaked a differ chip" if ("cat-differ" in norate_branch or "differLine" in norate_branch) else "honest no-market-rate note missing")

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
hero_differ_val = hero_appr.get("differ")
hero_pool_val = hero_appr.get("pool")
signals_total_val = len([s for s in sigs_all if s.get("status") != "dismissed"])   # the 'See all N' set
check("9a. engine emits hero differ / pool / signals-total as integers (the numbers the copy shows; differ<=pool)",
      all(isinstance(v, int) for v in (hero_differ_val, hero_pool_val, signals_total_val))
      and hero_differ_val <= hero_pool_val,
      {"differ": hero_differ_val, "pool": hero_pool_val, "signals_total": signals_total_val})
check("9b. hero copy interpolates engine differ & pool RAW (rendered == engine; no literal, no off-by-one)",
      "${approach.differ}</b> of ${approach.pool} comparable practices differ from the peer norm" in pagesjs,
      "hero differ/pool line is not interpolated raw from the engine fields")
check("9c. 'See all N signals' count derives from the live signal set (view-filtered), not a hard-coded literal",
      # per-view briefings (2026-07-06): the pool binding renamed (_pool) and the panel
      # list became briefing-first + impact tail — the INVARIANT is unchanged: the total
      # is the length of the live view-filtered ENGINE set, never a literal.
      '_pool = (data.signals_all || []).filter(' in pagesjs
      and '_viewSigs = [..._brief, ..._pool.filter(' in pagesjs
      and '_viewLive = _viewSigs.filter(s => s.status !== "dismissed")' in pagesjs
      and '_viewTotal = _viewLive.length' in pagesjs
      and '"See all " + total + " signals' in pagesjs,
      "the See-all count is not bound to the engine signal set")

print("\nNOTE: read-only gate — no fixtures created, nothing to clean. Reads the live")
print("snapshot via the same engine path as /api/overview (no HTTP).")
print("\nRESULTS: %d failures" % len(FAILS))
for n, d in FAILS:
    print("  FAIL:", n, d)
sys.exit(1 if FAILS else 0)
