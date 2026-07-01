# -*- coding: utf-8 -*-
"""SIGNALS — outcome-lens flags for the home dashboard (2026-06-12).

A signal is a FLAG with a peer fact attached, routed to one of four outcome
lenses: save (money out vs peers), attract, retain, engage. They tell a
member where to LOOK; they never tell them what to do (the same stance
discipline as the AI commentary validator). Every signal derives from data
the engine already computes — position percentiles, practice prevalence
(gap-register rows), and the £ opportunity model. Nothing is recomputed.

THE LENS MAP AND THRESHOLDS ARE DAVID'S (data/signal_lenses.json — which
metric speaks to attraction vs retention is reward domain knowledge, not
engineering). The file hot-reloads like the validation thresholds; a
malformed edit keeps the last good config.

TRUST RULES (enforced here, asserted by qa_hero):
- A 'behind' signal can only come from a POLARISED metric whose
  polarity-adjusted percentile sits at/below the behind threshold.
- Neutral metrics can never produce 'behind' — they may only appear as
  'save' (a cost fact: you pay more than N in 10 peers) or via prevalence.
- A prevalence signal needs peer adoption >= the floor AND the org
  genuinely not in place (gap-register semantics — N/A is unknown, not no).
- Wording is factual ("55% of peers do X — you don't"), never a directive.
"""
import json
import os

import practice_axis                       # single source for the prevalence words (common/alternative/rare)
from db import get_conn

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                        "signal_lenses.json")
_cache = {"mtime": None, "cfg": {}}

LENS_LABELS = {"save": "save", "attract": "attract", "retain": "retain", "engage": "engage"}


def lens_config():
    try:
        mt = os.path.getmtime(CFG_PATH)
    except OSError:
        return _cache["cfg"]
    if _cache["mtime"] != mt:
        try:
            with open(CFG_PATH) as f:
                _cache["cfg"] = json.load(f)
            _cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _cache["cfg"]


ANCHOR_PROV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                                "anchor_provenance.json")
_prov_cache = {"mtime": None, "map": {}}


def anchor_provenance():
    """Per-metric anchor provenance (grade/est/source), hot-reloaded — CAPTURE-ONLY (stage 1,
    2026-06-26). A POSITIVE LIST of the 121 graded metrics distilled from the Anchor Register
    (data/anchor_provenance.json); a question_id ABSENT here is UNKNOWN provenance — never
    defaulted to verified or estimate. grade A/B/C = sourced/verified (descending quality),
    EST = estimate-flagged. Read at render in stage 2; NEVER feeds the gauge/verdict (metadata,
    not a value). Survives reseeds (benchmark_snapshots does not)."""
    try:
        mt = os.path.getmtime(ANCHOR_PROV_PATH)
    except OSError:
        return _prov_cache["map"]
    if _prov_cache["mtime"] != mt:
        try:
            with open(ANCHOR_PROV_PATH) as f:
                _prov_cache["map"] = (json.load(f) or {}).get("provenance") or {}
            _prov_cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _prov_cache["map"]


def signal_key(sig):
    """Stable identity for change-alert diffing: lens:kind:question_id:matrix_row.
    A signal carries lens/kind/question_id on every row; matrix rows additionally
    carry their row in sig_id as 'question_id::row_id'."""
    sid = sig.get("sig_id") or sig.get("question_id") or ""
    row = sid.split("::", 1)[1] if "::" in sid else ""
    return "%s:%s:%s:%s" % (sig.get("lens", ""), sig.get("kind", ""),
                            sig.get("question_id", ""), row)


ORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ordered_scale_routing.json")
_ord_cache = {"mtime": None, "cfg": {}}


def ordered_routing():
    """Hot-reloaded ordered-scale routing (David-owned). Gives ordered metrics an
    EXPLICIT magnitude order so the outlier mechanism never infers rank from the
    option array (the sick-pay fault class)."""
    try:
        mt = os.path.getmtime(ORD_PATH)
    except OSError:
        return _ord_cache["cfg"]
    if _ord_cache["mtime"] != mt:
        try:
            with open(ORD_PATH) as f:
                _ord_cache["cfg"] = json.load(f)
            _ord_cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _ord_cache["cfg"]


def _ordinal_stats(block, scale, org_label):
    """Org's ordinal position on an EXPLICIT magnitude scale vs the peer
    distribution. Peers answering off-scale (NA / unplaced) are excluded — for
    income-protection terms this naturally scopes to the offering cohort.
    Returns None when the block is suppressed or the org is off-scale."""
    if not block or block.get("suppressed"):
        return None
    idx = {lab: i for i, lab in enumerate(scale)}
    if org_label not in idx:
        return None
    has_counts = any(o.get("count") is not None for o in (block.get("options") or []))
    dist, n = {}, 0.0
    for o in block.get("options") or []:
        if o["label"] in idx:
            c = o.get("count") if has_counts else o.get("pct", 0)
            c = c or 0
            dist[idx[o["label"]]] = dist.get(idx[o["label"]], 0) + c
            n += c
    if n <= 0:
        return None
    org = idx[org_label]
    below = sum(c for k, c in dist.items() if k < org)
    at = dist.get(org, 0)
    cum, median = 0.0, max(dist)
    for k in sorted(dist):
        cum += dist[k]
        if cum >= n * 0.5:
            median = k
            break
    return {"org_ord": org, "pct": 100.0 * (below + 0.5 * at) / n, "median_ord": median,
            "modal_share": max(dist.values()) / n, "org_band_share": at / n,
            "n_placed": int(round(n)) if has_counts else block.get("n", 0)}


def _matrix_depths(conn, qid, covered="Yes", snapshot=1):
    """{org_id -> depth} where depth = how many role levels are 'covered' for an
    org. Raw per-org coverage (the per-level aggregate block can't give it)."""
    orgs, yes = set(), {}
    for org, rid, val in conn.execute(
            "SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=? AND snapshot_id=?",
            (qid, snapshot)):
        if not rid:
            continue
        orgs.add(org)
        if val and val.strip().lower() == covered.lower():
            yes[org] = yes.get(org, 0) + 1
    return {o: yes.get(o, 0) for o in orgs}


def matrix_depth_signals(conn, questions, org_id, seen_q):
    """Mechanism B — depth-of-provision outliers. Signal = how far DOWN the role
    hierarchy a benefit reaches vs peers, both tails, NO verdict. Same noise gate
    as the ordered-outlier path. Panel-scoped (cut-scoping is a refinement)."""
    ordr = ordered_routing()
    dm = ordr.get("depth_matrix") or {}
    th = ordr.get("thresholds", {})
    tail_pct, min_modal = th.get("tail_pct", 20), th.get("min_modal_share", 0.35)
    max_band, min_n = th.get("max_org_band_share", 0.50), th.get("min_n", 5)
    sigs = []
    for qid, spec in dm.items():
        if qid in seen_q:
            continue
        q = questions.get(qid)
        if q is None:
            continue
        depths = _matrix_depths(conn, qid, spec.get("covered", "Yes"))
        mine = depths.pop(org_id, None)            # demo depth; peers = the rest
        vals = list(depths.values())
        if mine is None or len(vals) < min_n:
            continue
        n = len(vals)
        below = sum(1 for v in vals if v < mine)
        at = sum(1 for v in vals if v == mine)
        pct = 100.0 * (below + 0.5 * at) / n
        modal_share = max(vals.count(v) for v in set(vals)) / n
        if modal_share < min_modal or at / n >= max_band:
            continue
        if not (pct <= tail_pct or pct >= 100 - tail_pct):
            continue
        median = sorted(vals)[n // 2]
        nlev = len(q.matrix_rows or [])
        short = _label(qid, q, spec.get("title"))
        sigs.append({
            "lens": spec.get("lens", "retain"), "kind": "depth", "question_id": qid,
            "name": short, "tag": "HIGHER THAN MARKET" if pct >= 50 else "LOWER THAN MARKET", "worth": False,
            "stand": "reaches %d of %d levels, market median %d" % (mine, nlev, median),
            "value_display": "%d of %d levels" % (mine, nlev),
            "label_short": "%s · reaches %d of %d levels" % (short, mine, nlev),
            "detail": "%s reaches %d of %d role levels — peer median %d" % (short, mine, nlev, median),
            "impact": 30000 + abs(pct - 50) * 200,
        })
        seen_q.add(qid)
    return sigs


def _short(title, row=None):
    """A terse display label for the dashboard (the full fact stays in
    `detail` for the tooltip): strip boilerplate, keep the essence."""
    import re as _re
    t = title or ""
    for pat in (r"\s+by level\s*%? of base pay", r"\s+by level", r"\s*\(.*?\)",
                r"\s+as a? ?% of payroll", r"\s+rate\b", r"^Maximum\s+", r"^Annual\s+", r"^Average\s+"):
        t = _re.sub(pat, "", t, flags=_re.I)
    t = t.strip().rstrip("?")
    if row:
        t += " — " + row
    if len(t) > 46:                       # truncate on a WORD boundary, never mid-word
        t = t[:44].rsplit(" ", 1)[0].rstrip(" ,;—-") + "…"
    return t


def _label(qid, q=None, fallback=None):
    """The clean short display name for a signal row. Prefers David's authored
    label (data/signal_lenses.json -> signal_labels), else derives one from the
    question title. Never raw question stem, never mid-word truncation."""
    lbl = (lens_config().get("signal_labels") or {}).get(qid)
    if lbl:
        return lbl
    return _short(fallback if fallback is not None else (q.display_title if q else ""))


def _phrase(title):
    """A question title as a verb phrase: 'Do you include pay in adverts?' ->
    'include pay in adverts'."""
    import re as _re
    t = (title or "").strip().rstrip("?")
    t = _re.sub(r"^(do|does|is|are|have|has|did|can|will)\s+(you|your organisation|your organization|there)\s+", "", t, flags=_re.I)
    return t[:1].lower() + t[1:] if t else t


def _fmt_gbp(v):
    if v >= 1000:
        return "£%dk/yr" % round(v / 1000.0)
    return "£%d/yr" % round(v)


def _compare(mine, med, higher):
    """The 'where you stand' line. Shows the two values when both are short
    enough to read at a glance ('you 4×, market median 1×'); collapses to a
    plain direction when they're long phrases ('below the market')."""
    mine, med = str(mine), str(med)
    if len(mine) > 16 or len(med) > 16:
        return "above the market" if higher else "below the market"
    return "you %s, market median %s" % (mine, med)


def _ordinal_leak(vd):
    """The position engine emits an internal 0-100 ordinal for banded/scale
    metrics; it must never reach the UI. Returns a plain-language replacement
    when value_display is that raw ordinal, else None (use the real value)."""
    import re as _re
    m = _re.match(r"^\s*(\d+)\s*/\s*100\s*$", str(vd or ""))
    if not m:
        return None
    return "you provide none, the market provides it" if m.group(1) == "0" else "below the market median"


def _signal_position(sig, cls):
    """Market position for the Signals page axis: below / on / above (Substance)
    or `differs` (Approach). Approach (config Practice/Design) and rarity always
    read as `differs`; otherwise the factual tag direction (HIGHER->above,
    LOWER->below) — §5.5 colour is applied separately, by polarity."""
    if cls in ("Practice", "Design"):
        return "differs"
    tag = sig.get("tag", "")
    if tag == "A RARE CHOICE":
        return "differs"
    if tag == "COMMON — YOU DON'T":          # a market provision you lack reads below; a practice differs
        return "below" if cls in ("Level", "Provision") else "differs"
    if tag == "£ GAP":
        return "below"
    if "HIGHER" in tag:
        return "above"
    if "LOWER" in tag:
        return "below"
    return "differs"


def _signal_polarity(sig, direction):
    """Row colour driver (§5.5): a cost/spend signal or a neutral metric is
    context (navy); lower_is_better flips favourability; everything else higher."""
    if sig.get("kind") == "save" or direction == "neutral":
        return "neutral"
    if direction == "lower_is_better":
        return "lower"
    return "higher"


def _market_adoption(q, blk):
    """Share of the market with a practice in place (in_place+partial over the
    assessable base) — the SAME computation block 4 (PREVALENCE) uses, so a
    signal recast from a verdict to prevalence carries an identical, honest
    adoption figure. Returns None when nothing is assessable."""
    if not q or not blk:
        return None
    from aggregate import practice_status, STATUS_POINTS
    assessable = in_place = 0.0
    for o in blk.get("options") or []:
        st = practice_status(q, o["label"])
        if st in STATUS_POINTS:
            assessable += o["pct"]
            if st in ("in_place", "partial"):
                in_place += o["pct"]
    return (100.0 * in_place / assessable) if assessable else None


# Reward-strategy objective re-ranker (handover §5.3) — a per-lens multiplier on
# signal impact BEFORE the sort. The founding strategy hook: a cost-cutting org
# must not be shown investment signals first. Pure re-rank — fabricates nothing,
# hides nothing — so the trust rules hold. strategy=None → all 1.0 → today's order
# byte-for-byte (the degrade-to-legacy contract, §5.5).
OBJECTIVE_LENS_MULT = {
    "attract":    {"attract": 1.6, "retain": 1.0, "engage": 1.0, "save": 0.9},
    "retain":     {"attract": 1.0, "retain": 1.6, "engage": 1.1, "save": 0.9},
    "cost":       {"attract": 0.6, "retain": 0.8, "engage": 0.8, "save": 1.7},
    "compliance": {"attract": 0.9, "retain": 1.0, "engage": 1.4, "save": 1.0},
    "hold":       {"attract": 1.0, "retain": 1.0, "engage": 1.0, "save": 1.0},
}


def _objective_mult(strategy, lens):
    """Per-lens impact scaler from the org's primary_objective. Neutral (1.0)
    when there is no strategy, no objective, or it was skipped (§5.4 provenance)."""
    if not strategy:
        return 1.0
    obj = strategy.get("primary_objective")
    if not obj or (strategy.get("provenance") or {}).get("primary_objective") == "skipped":
        return 1.0
    return (OBJECTIVE_LENS_MULT.get(obj) or {}).get(lens, 1.0)


# pay_for_performance RE-RANK (David 2026-06-24; PRECISION upgrade 2026-06-25) — a SECOND strategy
# multiplier on the same impact: the org's P4P intensity bumps VARIABLE-PAY signals. strong → 1.4
# (variable pay matters more), egal → 0.7 (demote variable pay so base-pay / fairness signals rise
# relatively), moderate / unset / skipped → 1.0. PRECISE keying (tagging pass): on the curated
# variable_pay_metrics SET (signal_lenses.json), NOT the whole Incentives domain — so governance
# (malus/clawback), scheme design, eligibility policy and overtime/shift premiums that merely SIT in
# Incentives no longer get the bump/demote. Composes with _objective_mult under a CAPPED PRODUCT
# (≤2.0) at the application site so the two can't runaway-stack. Empty set → 1.0 everywhere (degrade);
# were the set every Incentives metric, output = the old coarse behaviour byte-for-byte.
P4P_INCENTIVE_MULT = {"strong": 1.4, "egal": 0.7}    # moderate / None → 1.0 via .get default
def _p4p_mult(strategy, qid, variable_pay_set):
    if qid not in (variable_pay_set or ()):
        return 1.0
    return P4P_INCENTIVE_MULT.get(_strategy_field(strategy, "pay_for_performance"), 1.0)


# transparency RE-RANK (step-3 tagging unit 2, David 2026-06-25) — a THIRD strategy multiplier,
# keyed on the curated transparency_metrics tag. An org that RECONFIRMS transparency=open in the
# now-live field surfaces its transparency-practice signals higher ("gaps to full openness become
# actions"). ⭐ STALE-VALUE GATE (treat-as-unset-until-reconfirmed, the L2 flag's resolution): the
# value drives surfacing ONLY when field_provenance.transparency == "live" — a pre-wiring stored
# value (provenance "set", never seen in the visible field) reads as unset → 1.0. open → 1.4;
# ranges / closed / unset / unreconfirmed → 1.0. Folds into the SAME capped product (≤2.0) as
# objective × p4p at the application site — no separate uncapped multiply.
TRANSPARENCY_MULT = {"open": 1.4}    # ranges / closed / unset → 1.0 via .get default
def _transparency_mult(strategy, qid, transparency_set):
    if qid not in (transparency_set or ()):
        return 1.0
    if not strategy or (strategy.get("provenance") or {}).get("transparency") != "live":
        return 1.0                                       # stale / unset / unreconfirmed → never drives surfacing
    return TRANSPARENCY_MULT.get(strategy.get("transparency"), 1.0)


# STEP-3 LAYER 4 confirm-shedding demote (David 2026-06-24, ruling C). A non-risk signal
# whose DOMAIN confirms its aim (alignment == on_target — on_target ONLY: ahead=overspend
# and behind=gap both stay actionable) is the lowest briefing priority. This impact demote
# sinks it in the full Signals list; cap_briefing's confirm-aware pass is what actually
# sheds it off the home briefing. Tunable; 0 confirm signals → no-op (byte-identical).
CONFIRM_DEMOTE_MULT = 0.25


def _strategy_field(strategy, field):
    """A strategy dial value iff a real 'set' choice — None when absent/skipped."""
    if not strategy:
        return None
    v = strategy.get(field)
    if not v or (strategy.get("provenance") or {}).get(field) == "skipped":
        return None
    return v


def build_signals(items, opportunity, questions, get_block, org_answers, conn=None, org_id=None, cap=True, statuses=None, strategy=None, domain_alignment=None):
    """items: pos.position_items output (cut-scoped); opportunity: the £
    model dict; questions: org-visible library; get_block(qid) -> the cut's
    main distribution block; org_answers: {(qid,row): value}. Prevalence
    derives from aggregate.practice_status — the SAME single source of truth
    the gap register uses — applied to the block, so unscored questions
    (the 2026.1/2026.2 additions) flag too. Returns ranked signals capped at
    max_signals, with at most max_per_lens per lens for a balanced briefing."""
    cfg = lens_config()
    if not cfg:
        return []
    th = cfg.get("thresholds") or {}
    behind_at = th.get("behind_percentile", 25)
    save_at = th.get("save_percentile", 85)
    prev_floor = th.get("prevalence_floor", 50)
    money_min = th.get("money_min_gbp", 10000)
    out = []
    seen_q = set()

    # 1) MONEY: the £ model's gap-to-median items (biggest facts first)
    money_lenses = cfg.get("money_lenses") or {}
    for it in (opportunity or {}).get("items") or []:
        qid = it.get("question_id")
        gbp = it.get("to_p50_gbp") or 0
        if qid in money_lenses and gbp >= money_min and qid not in seen_q:
            q = questions.get(qid)
            out.append({
                "lens": money_lenses[qid], "kind": "money", "question_id": qid,
                "name": _label(qid, q, it.get("label")),
                "tag": "£ GAP", "fav": "bad", "worth": False,
                "stand": "%s below the market median" % _fmt_gbp(gbp),
                "value_display": _fmt_gbp(gbp),
                "label_short": "%s — gap to median" % _short(q.display_title if q else it.get("label", "")),
                "detail": "%s gap to the peer median" % (q.display_title if q else it.get("label", "")),
                "impact": 1000000 + gbp,
            })
            seen_q.add(qid)

    # 2) SAVE: cost metrics where the org pays at/above the save percentile.
    # Cost metrics are typically NEUTRAL — this is a fact about spend, never
    # a market verdict.
    cost = cfg.get("cost_metrics") or {}
    best_cost = {}
    for i in items:
        qid = i["question_id"]
        if qid in cost and i["kind"] == "value" and i["percentile"] >= save_at:
            if qid not in best_cost or i["percentile"] > best_cost[qid]["percentile"]:
                best_cost[qid] = i
    for qid, i in best_cost.items():
        if qid in seen_q:
            continue
        out.append({
            "lens": "save", "kind": "save", "question_id": qid,
            "name": _label(qid, None, i["label"]),
            "tag": "HIGHER THAN MARKET", "worth": False,
            "stand": "your spend is above %d in 10 in the market" % min(9, int(i["percentile"] / 10)),
            "value_display": "P%d" % round(i["percentile"]),
            "label_short": "%s — above %d in 10 peers" % (_short(i["label"]), min(9, int(i["percentile"] / 10))),
            "detail": "%s — you pay more than %d in 10 peers" % (
                i["label"], min(9, int(i["percentile"] / 10))),
            "impact": 500000 + (i["percentile"] - save_at) * 100,
        })
        seen_q.add(qid)

    # 3) BEHIND: polarised metrics mapped to a lens, sitting at/below the
    # behind threshold on the polarity-ADJUSTED scale (50 + distance).
    pos_lenses = cfg.get("position_lenses") or {}
    worst_pos = {}
    for i in items:
        qid = i["question_id"]
        if qid in pos_lenses and i["favourable"] == "bad":
            adj = 50.0 + i["distance"]
            if adj <= behind_at and (qid not in worst_pos or adj < worst_pos[qid][0]):
                worst_pos[qid] = (adj, i)
    for qid, (adj, i) in worst_pos.items():
        if qid in seen_q:
            continue
        row_lbl = (i["label"].split(" — ")[-1] if " — " in i["label"] else None)
        nm = _label(qid, questions.get(qid), i["label"].split(" — ")[0])
        if row_lbl:
            nm = "%s (%s)" % (nm, row_lbl)
        leak = _ordinal_leak(i["value_display"])
        stand = leak or _compare(i["value_display"], i["p50_display"] or "n/a", False)
        out.append({
            "lens": pos_lenses[qid], "kind": "behind", "question_id": qid,
            "name": nm, "tag": "HIGHER THAN MARKET" if i["percentile"] > 50 else "LOWER THAN MARKET",
            "fav": "bad", "worth": True, "stand": stand,
            "value_display": "P%d" % round(i["percentile"]),
            "label_short": "%s · %s vs %s" % (_short(i["label"].split(" — ")[0], row_lbl),
                                              i["value_display"], i["p50_display"] or "median"),
            "detail": "%s — %s vs %s peer median" % (i["label"], i["value_display"], i["p50_display"] or "the"),
            "impact": 100000 + (behind_at - adj) * 100,
        })
        seen_q.add(qid)

    # 3b) AHEAD (strength): the favourable mirror of BEHIND. Same routed set
    # (position_lenses), but where the polarity-adjusted position sits at/above
    # the ahead threshold — you LEAD the market here. Surfaced so strengths show,
    # not just gaps. A polarised metric fires behind XOR ahead, never both.
    ahead_at = th.get("ahead_percentile", 65)
    best_pos = {}
    for i in items:
        qid = i["question_id"]
        if qid in pos_lenses and i["favourable"] == "good":
            adj = 50.0 + i["distance"]
            if adj >= ahead_at and (qid not in best_pos or adj > best_pos[qid][0]):
                best_pos[qid] = (adj, i)
    for qid, (adj, i) in best_pos.items():
        if qid in seen_q:
            continue
        row_lbl = (i["label"].split(" — ")[-1] if " — " in i["label"] else None)
        nm = _label(qid, questions.get(qid), i["label"].split(" — ")[0])
        if row_lbl:
            nm = "%s (%s)" % (nm, row_lbl)
        # the TAG states the value direction (are you numerically higher/lower
        # than the market); the COLOUR (fav) states it's a strength. For a
        # lower-is-better metric a strength reads 'LOWER THAN MARKET' + green.
        hi = i["percentile"] > 50
        tag = "HIGHER THAN MARKET" if hi else "LOWER THAN MARKET"
        if _ordinal_leak(i["value_display"]) or not i["p50_display"]:
            stand = "above the market" if hi else "below the market"
        else:
            stand = _compare(i["value_display"], i["p50_display"], hi)
        out.append({
            "lens": pos_lenses[qid], "kind": "ahead", "question_id": qid,
            "name": nm, "tag": tag, "fav": "good", "worth": False, "stand": stand,
            "value_display": "P%d" % round(i["percentile"]),
            "label_short": "%s · %s vs %s" % (_short(i["label"].split(" — ")[0], row_lbl),
                                              i["value_display"], i["p50_display"] or "median"),
            "detail": "%s — %s vs %s market median" % (i["label"], i["value_display"], i["p50_display"] or "the"),
            "impact": 80000 + (adj - ahead_at) * 100,
        })
        seen_q.add(qid)

    # 4) PREVALENCE: practices most peers have in place and the org doesn't.
    # practice_status is the single source of truth (gap-register semantics:
    # N/A and don't-know are unknown, never "doesn't do it").
    from aggregate import practice_status, STATUS_POINTS
    prev_lenses = cfg.get("prevalence_lenses") or {}
    for qid, lens in prev_lenses.items():
        if qid in seen_q:
            continue
        q = questions.get(qid)
        blk = get_block(qid) if q else None
        mine = org_answers.get((qid, ""))
        if q is None or not blk or blk.get("suppressed") or mine in (None, ""):
            continue
        if practice_status(q, mine) != "not_in_place":
            continue          # the org has it (or it isn't assessable) — no flag
        assessable = in_place = 0.0
        for o in blk.get("options") or []:
            st = practice_status(q, o["label"])
            if st in STATUS_POINTS:
                assessable += o["pct"]
                if st in ("in_place", "partial"):
                    in_place += o["pct"]
        adoption = 100.0 * in_place / assessable if assessable else 0.0
        if adoption >= prev_floor:
            out.append({
                "lens": lens, "kind": "prevalence", "question_id": qid,
                "name": _label(qid, q), "tag": "COMMON — YOU DON'T", "worth": True,
                "stand": "%d%% of the market does this, you don't" % round(adoption),
                "value_display": "%d%%" % round(adoption),
                "label_short": "of peers %s" % _short(_phrase(q.display_title)),
                "detail": "of peers %s — you don't yet" % _phrase(q.display_title),
                "impact": 10000 + adoption * 10,
            })
            seen_q.add(qid)

    # 5) ORDERED-OUTLIER (neutral scales, BOTH tails, NO verdict). The org's
    # ordinal comes from an EXPLICIT magnitude scale (ordered_scale_routing.json),
    # never the option-array index. We state the position + the peer fact; the
    # user judges whether their end is good or bad. Off-scale (NA) peers are
    # excluded — for income-protection terms this scopes to the offering cohort.
    ordr = ordered_routing()
    oth = ordr.get("thresholds", {})
    tail_pct = oth.get("tail_pct", 20)
    min_modal = oth.get("min_modal_share", 0.35)
    max_band = oth.get("max_org_band_share", 0.50)
    min_n = oth.get("min_n", 5)
    scales = ordr.get("scales", {})
    for qid in ordr.get("ordered_outlier", []):
        if qid in seen_q:
            continue
        q = questions.get(qid)
        spec = scales.get(qid)
        mine = org_answers.get((qid, ""))
        if q is None or not spec or mine in (None, ""):
            continue
        st = _ordinal_stats(get_block(qid), spec["scale_low_to_high"], mine)
        if not st or st["n_placed"] < min_n:
            continue
        # noise gate: a meaningful tail needs a discernible norm (modal band big
        # enough) AND the org must not itself be that norm.
        if st["modal_share"] < min_modal or st["org_band_share"] >= max_band:
            continue
        if not (st["pct"] <= tail_pct or st["pct"] >= 100 - tail_pct):
            continue
        high = st["pct"] >= 50
        med = spec["scale_low_to_high"][st["median_ord"]]
        short = _label(qid, q)
        out.append({
            "lens": spec.get("lens", "engage"), "kind": "outlier", "question_id": qid,
            "name": short, "tag": "HIGHER THAN MARKET" if high else "LOWER THAN MARKET", "worth": False,
            "stand": _compare(mine, med, high),
            "value_display": mine,
            "label_short": "%s · %s end" % (short, "top" if high else "bottom"),
            "detail": "%s sits at the %s of your peer group — %s (peer median %s)" % (
                short, "top end" if high else "bottom end", mine, med),
            "impact": 30000 + abs(st["pct"] - 50) * 200,
        })
        seen_q.add(qid)

    # 5b) BEHIND_EXPLICIT: position metrics that fire 'behind' off the EXPLICIT
    # scale (their global score direction is unreliable — the anchor-risk set).
    # One-ended: fires only on the BAD tail per the metric's explicit direction.
    for qid in ordr.get("behind_explicit", []):
        if qid in seen_q:
            continue
        q = questions.get(qid)
        spec = scales.get(qid)
        mine = org_answers.get((qid, ""))
        if q is None or not spec or mine in (None, ""):
            continue
        st = _ordinal_stats(get_block(qid), spec["scale_low_to_high"], mine)
        if not st or st["n_placed"] < min_n:
            continue
        bad_is_high = spec.get("direction") == "lower_is_better"   # low ordinal is good -> high is the bad tail
        bad = st["pct"] >= 100 - behind_at if bad_is_high else st["pct"] <= behind_at
        if not bad:
            continue
        med = spec["scale_low_to_high"][st["median_ord"]]
        short = _label(qid, q)
        out.append({
            "lens": spec.get("lens", "retain"), "kind": "behind", "question_id": qid,
            "name": short, "tag": "HIGHER THAN MARKET" if st["pct"] >= 50 else "LOWER THAN MARKET", "worth": True,
            "stand": _compare(mine, med, st["pct"] >= 50),
            "value_display": mine,
            "label_short": "%s · %s vs %s" % (short, mine, med),
            "detail": "%s — %s vs %s peer median" % (q.display_title, mine, med),
            "impact": 100000 + abs(st["pct"] - 50) * 100,
        })
        seen_q.add(qid)

    # 6) DEPTH-OF-PROVISION matrices (how far down the org a benefit reaches),
    # both tails, no verdict. Needs raw per-org coverage, so it takes the conn.
    if conn is not None and org_id is not None:
        out.extend(matrix_depth_signals(conn, questions, org_id, seen_q))

    # 6b) MATRIX-ROW POSITION — each value-matrix ROW is its own signal. A matrix's
    # typical position hides rows that sit off the market in DIFFERENT directions
    # (one allowance below, another above); a single per-metric flag would lie.
    # So every row that crosses the 25-75 band fires its OWN neutral signal, both
    # tails, no verdict; identity is qid::row_id so they coexist and triage
    # independently. Auto-applies to ALL value matrices (lens via optional routing
    # override, else a default). Per-row items already exist in `items`.
    # tighter band than the 25-75 used for headline position: on a precise £ line
    # (e.g. £2,300 vs £1,900 median) P69 is genuinely above market, so a row flags
    # outside 35-65 by default. David-tunable (thresholds.matrix_low/high).
    mat_lo = oth.get("matrix_low", 35)
    mat_hi = oth.get("matrix_high", 65)
    mp_over = ordr.get("matrix_position") or {}
    mp_default_lens = mp_over.get("_default_lens", "retain")
    mp_max_rows = int(oth.get("matrix_max_rows", 4))   # cap per matrix so one grid can't flood
    rows_by_q = {}
    for i in items:
        if i.get("row_id") and i["kind"] == "value" and (i.get("n") or 0) >= min_n:
            rows_by_q.setdefault(i["question_id"], []).append(i)
    for qid, rws in rows_by_q.items():
        if qid in seen_q:                  # already flagged by money/behind/etc — one class per metric
            continue
        cross = [i for i in rws if i["percentile"] <= mat_lo or i["percentile"] >= mat_hi]
        if not cross:
            continue
        cross.sort(key=lambda x: -abs(x["percentile"] - 50))   # most divergent rows first
        spec = mp_over.get(qid) or {}
        lens = spec.get("lens", mp_default_lens)
        nm0 = _label(qid, questions.get(qid))
        for i in cross[:mp_max_rows]:
            high = i["percentile"] >= 50
            row_lbl = i["label"].split(" — ")[-1] if " — " in i["label"] else None
            nm = "%s (%s)" % (nm0, row_lbl) if row_lbl else nm0
            out.append({
                "lens": lens, "kind": "outlier", "question_id": qid,
                "sig_id": qid + "::" + (i.get("row_id") or ""),
                "name": nm, "tag": "HIGHER THAN MARKET" if high else "LOWER THAN MARKET", "worth": False,
                "stand": _compare(i["value_display"], i["p50_display"] or "n/a", high),
                "value_display": i["value_display"],
                "label_short": "%s · %s vs %s" % (nm, i["value_display"], i["p50_display"] or "median"),
                "detail": "%s — %s vs %s market median" % (i["label"], i["value_display"], i["p50_display"] or "the"),
                "impact": 28000 + abs(i["percentile"] - 50) * 100,
            })
        seen_q.add(qid)

    # 7) MULTI-SELECT per-OPTION prevalence (Mechanism C). Never answer-SET
    # rarity (that flags everyone). Fire on the single most DECISIVE option per
    # metric — one the org picked that ~nobody does (adoption <= decisive_low),
    # or one the org skipped that ~everybody does (adoption >= decisive_high).
    # Both directions, no verdict, one signal per metric.
    dec_low = oth.get("decisive_low", 15)
    dec_high = oth.get("decisive_high", 85)
    for qid, spec in (ordr.get("multi_prevalence") or {}).items():
        if qid in seen_q:
            continue
        q = questions.get(qid)
        blk = get_block(qid) if q else None
        if q is None or not blk or blk.get("suppressed") or blk.get("n", 0) < min_n:
            continue
        raw = org_answers.get((qid, "")) or ""
        mine = set(t.strip() for t in raw.split(";") if t.strip())
        best = None                       # (decisiveness, kind, label, pct)
        for o in blk.get("options") or []:
            if o.get("is_na"):
                continue
            a, lab, sel = o["pct"], o["label"], o["label"] in mine
            if sel and a <= dec_low:
                if best is None or (50 - a) > best[0]:
                    best = (50 - a, "rare", lab, a)
            elif (not sel) and a >= dec_high:
                if best is None or (a - 50) > best[0]:
                    best = (a - 50, "missing", lab, a)
        if best is None:
            continue
        _, knd, lab, a = best
        if knd == "rare":
            detail = "you selected “%s” — only %d%% of peers do" % (lab, round(a))
            tag, worth = "A RARE CHOICE", False
            stand = "only %d%% of the market offers it" % round(a)
        else:
            detail = "%d%% of peers select “%s” — you don't" % (round(a), lab)
            tag, worth = "COMMON — YOU DON'T", True
            stand = "%d%% of the market does this, you don't" % round(a)
        # the OPTION is the label here — never the multi-select question stem
        out.append({"lens": spec.get("lens", "engage"), "kind": "rare", "question_id": qid,
                    "name": lab, "tag": tag, "worth": worth, "stand": stand,
                    "value_display": lab, "label_short": "%s · %s" % (_short(q.display_title), lab),
                    "detail": detail, "impact": 22000 + best[0] * 100})
        seen_q.add(qid)

    # 8) GATED RARITY single-select (Mechanism D). The org's chosen value has low
    # peer adoption (<= rarity_floor) AND a clear norm exists (mode >= 50%, the
    # mode-gate asserted at fire). "You're the rare exception." No verdict.
    floor = oth.get("rarity_floor", 15)
    for qid, spec in (ordr.get("rarity") or {}).items():
        if qid in seen_q:
            continue
        q = questions.get(qid)
        blk = get_block(qid) if q else None
        mine = org_answers.get((qid, ""))
        if q is None or not blk or blk.get("suppressed") or blk.get("n", 0) < min_n or mine in (None, ""):
            continue
        opts = {o["label"]: o["pct"] for o in (blk.get("options") or []) if not o.get("is_na")}
        a = opts.get(mine)
        if not opts or a is None:          # org answered NA / off-list — no rarity
            continue
        if max(opts.values()) >= 50 and a <= floor:
            out.append({"lens": spec.get("lens", "engage"), "kind": "rare", "question_id": qid,
                        "name": _label(qid, q), "tag": "A RARE CHOICE", "worth": False,
                        "stand": "only %d%% of the market does this — you do" % round(a),
                        "value_display": mine, "label_short": "%s · %s" % (_short(q.display_title), mine),
                        "detail": "you answered “%s” — only %d%% of peers do" % (mine, round(a)),
                        "impact": 22000 + (50 - a) * 100})
            seen_q.add(qid)

    # per-user triage state: priority | saved | dismissed | None(new). Identity is
    # sig_id — usually the question_id, but qid::row_id for per-row matrix signals
    # so each row triages independently.
    st = statuses or {}
    import positions as _pos
    _cfg = _pos.market_position_config() or {}
    _metrics = _cfg.get("metrics", {})
    risk_set = set(cfg.get("risk_metrics") or [])   # RISK/POSITION split (David-curated; never a heuristic)
    vp_set = set(cfg.get("variable_pay_metrics") or [])   # variable_pay tag (David-curated): precise P4P keying
    tr_set = set(cfg.get("transparency_metrics") or [])   # transparency tag (David-curated): reconfirmed-open re-rank
    for s in out:
        s.setdefault("sig_id", s["question_id"])
        s["status"] = st.get(s["sig_id"])
        # market-position re-axis (spec §6.3): domain + position (below/on/above/
        # differs) + polarity, so the Signals page can chip-filter, group and colour
        _q = questions.get(s["question_id"])
        _m = _metrics.get(s["question_id"]) or {}
        s["domain"] = _q.sub_power if _q else None
        s["position"] = _signal_position(s, _m.get("class"))
        s["polarity"] = _signal_polarity(s, _m.get("direction"))
        s["mp_class"] = _m.get("class")          # internal class, surfaced only in the metric detail view
        # RISK/POSITION split (Option 1, step-3 prerequisite — David's curated risk_metrics list).
        # A stable, QUERYABLE property that rides the signal dict like position/domain (survives the
        # Fix-4 firewall, the §5.2 reframes, _suppress and cap_briefing): risk-framed = an absence/
        # exposure no pay strategy excuses (statutory/duty-of-care floor) vs a position distance a
        # strategy explains. DISPLAY-ONLY in EFFECT now (coral row accent on the client) — but
        # per-domain suppression (step-3 layer 5) will READ this to EXEMPT risks from confirm-
        # suppression (the maternity-zero guard). Never a heuristic — only the curated list.
        s["risk_framed"] = s["question_id"] in risk_set
        # NON-COMPETITIVE DOMAINS (Governance scoping ruling — signals layer, 2026-06-22):
        # market-relative framing (below/on/above/differs) applies ONLY to competitive
        # domains. A domain with no market position contributes 0 to the market axis —
        # reading the SAME _mp_competitive flag the hero scopes by (single source of
        # truth, so signals and the hero can't drift). Its signals carry the NON-market
        # "practice" position and, if they fired through a market verdict (behind/ahead),
        # are recast to a peer/practice statement — never a market label. RELABEL, kept in
        # the stream (sortable/filterable/dismissable), never dropped. The adoption FACT
        # keeps "the market" (it's prevalence, not a verdict); only the verdict framing goes.
        if not _pos._mp_competitive(_cfg, s["domain"]):
            s["position"] = "practice"
            if s.get("kind") in ("behind", "ahead"):
                was_behind = s.get("fav") == "bad"
                adoption = _market_adoption(_q, get_block(s["question_id"]) if _q else None)
                s.pop("fav", None)
                s["worth"] = True
                _ttl = _phrase(_q.display_title) if _q else (s.get("name") or "this")
                if was_behind and adoption is not None and adoption >= prev_floor:
                    # a common practice you lack — prevalence framing (adoption fact keeps
                    # "the market" per the ruling; only the position label changed).
                    _pct = round(adoption)
                    s["kind"] = "prevalence"; s["tag"] = "COMMON — YOU DON'T"
                    s["stand"] = "%d%% of the market does this, you don't" % _pct
                    s["value_display"] = "%d%%" % _pct
                    s["label_short"] = "of peers %s" % _short(_ttl)
                    s["detail"] = "of peers %s — you don't yet" % _ttl
                    s["impact"] = 10000 + _pct * 10
                elif _m.get("class") in ("Practice", "Design"):
                    # a yes/no approach with no clear majority — a peer-framed approach note
                    s["kind"] = "approach"; s["tag"] = "AN %s CHOICE" % practice_axis.bucket_word("established").upper()
                    s["stand"] = "an %s to the peer norm" % practice_axis.bucket_word("established")
                    s["detail"] = "your approach to %s is an %s to the peer norm" % (_ttl, practice_axis.bucket_word("established"))
                    s["value_display"] = ""
                    s["label_short"] = s.get("name") or _short(_q.display_title if _q else "")
                    s["impact"] = 9000
                else:
                    # a quantity (Level/Provision): a NEUTRAL peer-position note, never an
                    # above/below-MARKET verdict. Peer-framed, no RAG.
                    high = "HIGHER" in (s.get("tag") or "")
                    s["kind"] = "outlier"
                    s["tag"] = "HIGHER THAN PEERS" if high else "LOWER THAN PEERS"
                    s["stand"] = "sits at the %s end of your peer group" % ("high" if high else "low")
                    s["detail"] = "%s sits at the %s end of your peer group" % (
                        (_q.display_title if _q else _ttl), "high" if high else "low")
                    s["label_short"] = s.get("name") or _short(_q.display_title if _q else "")
                    s["value_display"] = ""
                    s["impact"] = 9000
            # defensive: any residual market-relative TAG on a non-competitive signal
            # (e.g. a native outlier/depth "HIGHER THAN MARKET") is peer-framed too. The
            # adoption STAND keeps "the market" by design (prevalence, not a verdict).
            if (s.get("tag") or "").endswith("THAN MARKET"):
                s["tag"] = s["tag"].replace("THAN MARKET", "THAN PEERS")
        # COMPETITIVE domains only — the original Approach (Practice/Design) recast:
        # A Practice/Design metric resolves to position "differs" — it is an
        # APPROACH, never a market deficiency. If such a metric fired through a
        # verdict block (behind/ahead — e.g. a practice routed via position_lenses),
        # strip the RAG verdict (kind/tag/fav) and re-cast it as prevalence
        # ("most do this, you don't") so the card reads as a practice gap, not a
        # red/green market position. The gauge already excludes Approach metrics;
        # this only corrects the Signals/home briefing read. (signal-colour fix #2)
        elif s["position"] == "differs" and s.get("kind") in ("behind", "ahead"):
            was_behind = s.get("fav") == "bad"
            adoption = _market_adoption(_q, get_block(s["question_id"]) if _q else None)
            s.pop("fav", None)
            s["worth"] = True
            _ttl = _phrase(_q.display_title) if _q else (s.get("name") or "this")
            if was_behind and adoption is not None and adoption >= prev_floor:
                _pct = round(adoption)
                s["kind"] = "prevalence"
                s["tag"] = "COMMON — YOU DON'T"
                s["stand"] = "%d%% of the market does this, you don't" % _pct
                s["value_display"] = "%d%%" % _pct
                s["label_short"] = "of peers %s" % _short(_ttl)
                s["detail"] = "of peers %s — you don't yet" % _ttl
                # re-baseline impact to prevalence tier (was behind/ahead tier): a
                # recast must not keep verdict-level impact, or it jumps the
                # cap_briefing diversity reserve meant for genuine prevalence.
                # Byte-matches native prevalence (block 4): 10000 + adoption*10.
                s["impact"] = 10000 + _pct * 10
            else:
                # leads on / differs in an approach with no clear adoption norm:
                # state the difference, assert no verdict (no fav, purple chip).
                # detail + label_short are rewritten too so the stale "X vs Y
                # market median" verdict never leaks into the persisted signal
                # state or the change-alert email (notifications.py reads detail).
                s["kind"] = "approach"
                s["tag"] = "AN %s CHOICE" % practice_axis.bucket_word("established").upper()
                s["stand"] = "an %s to the market norm" % practice_axis.bucket_word("established")
                s["value_display"] = ""
                s["detail"] = "your approach to %s is an %s to the market norm" % (_ttl, practice_axis.bucket_word("established"))
                s["label_short"] = s.get("name") or _short(_q.display_title if _q else "")
                s["impact"] = 9000          # below floor-level prevalence; a no-verdict flag ranks lower
        # FIX 4 (2026-06-23) — PRACTICE-TAB VOCABULARY FIREWALL (the differs lane). The recast
        # above only converts behind/ahead; depth/outlier (and any other) kinds that resolve
        # to position=differs keep their DIRECTIONAL "HIGHER/LOWER THAN MARKET" verdict and so
        # show on the dashboard Practice tab reading like a market deficiency. A practice
        # difference is never a market verdict, so route ANY residual directional market tag on
        # a differs signal to rarity/approach/peer vocab — keyed on the FINAL position (what
        # decides the tab), not the kind. Mirrors the non-competitive branching (a common
        # practice you lack → COMMON — YOU DON'T; a yes/no approach → DIFFERS FROM PEERS; a quantity →
        # HIGHER/LOWER THAN PEERS). DISPLAY-ONLY: tag + the stand/detail/label copy. position,
        # kind, impact, counts, ranking and the gauge are all left untouched (byte-identical).
        _ftag = s.get("tag") or ""
        if s.get("position") == "differs" and (
                _ftag.endswith("THAN MARKET") or _ftag == "£ GAP"
                or "ABOVE MARKET" in _ftag or "BELOW MARKET" in _ftag):
            _fttl = _phrase(_q.display_title) if _q else (s.get("name") or "this")
            _fadopt = _market_adoption(_q, get_block(s["question_id"]) if _q else None)
            if _fadopt is not None and _fadopt >= prev_floor:
                _fpct = round(_fadopt)
                s["tag"] = "COMMON — YOU DON'T"
                s["stand"] = "%d%% of the market does this, you don't" % _fpct
                s["value_display"] = "%d%%" % _fpct
                s["label_short"] = "of peers %s" % _short(_fttl)
                s["detail"] = "of peers %s — you don't yet" % _fttl
            elif _m.get("class") in ("Practice", "Design"):
                s["tag"] = "AN %s CHOICE" % practice_axis.bucket_word("established").upper()
                s["stand"] = "an %s to the peer norm" % practice_axis.bucket_word("established")
                s["value_display"] = ""
                s["label_short"] = s.get("name") or _short(_q.display_title if _q else "")
                s["detail"] = "your approach to %s is an %s to the peer norm" % (_fttl, practice_axis.bucket_word("established"))
            else:
                _fhigh = "HIGHER" in _ftag
                s["tag"] = "HIGHER THAN PEERS" if _fhigh else "LOWER THAN PEERS"
                s["stand"] = "sits at the %s end of your peer group" % ("high" if _fhigh else "low")
                s["value_display"] = ""
                s["label_short"] = s.get("name") or _short(_q.display_title if _q else "")
                s["detail"] = "%s sits at the %s end of your peer group" % (
                    (_q.display_title if _q else _fttl), "high" if _fhigh else "low")
        # v2 materiality weighting (handover §9.6): David's per-metric `weight`
        # (default 1, hot-reloaded) scales how strongly a signal surfaces in the
        # ranked briefing — a base-pay gap outranks a minor allowance. It does NOT
        # touch the gauge, which stays count-mass ("verdict reflects mass").
        _w = _m.get("weight", 1)
        s["weight"] = _w
        s["impact"] = round((s.get("impact") or 0) * (_w if _w is not None else 1))
        # reward-strategy re-rank — §5.3 objective (keyed on lens) × pay_for_performance
        # (keyed on the variable_pay metric tag), as a CAPPED PRODUCT (David 2026-06-24): the two
        # multipliers key on DIFFERENT axes, so both can hit one signal; multiply, then clamp
        # the COMBINED strategy multiplier to 2.0 so a strong-P4P + attract org can't double-
        # boost incentive-attract signals past the cap. 1.0 when strategy is absent/skipped
        # (objective alone ≤1.7 < cap, P4P 1.0 off-variable-pay/moderate/unset → byte-identical).
        _strat_mult = min(_objective_mult(strategy, s.get("lens")) * _p4p_mult(strategy, s.get("question_id"), vp_set)
                          * _transparency_mult(strategy, s.get("question_id"), tr_set), 2.0)
        s["impact"] = round(s["impact"] * _strat_mult)
        # applicability + family reframes (§5.2) — config tags gate them, the opt-in
        # stance drives them; both no-ops when untagged/unset (degrade byte-for-byte)
        if _strategy_field(strategy, "location_approach") == "agnostic" and _m.get("location_scoped"):
            s["_suppress"] = True          # per-location read doesn't apply to a one-rate org
        elif (_strategy_field(strategy, "family_position") == "over" and _m.get("family_metric")
              and (s.get("position") == "above" or s.get("kind") == "save")):
            # high family spend reads as intended, not overspend — relabel + demote,
            # never hide a family metric that's BELOW (that contradicts the stance)
            s["strategy_note"] = "intended — your generous family stance"
            s["impact"] = round((s.get("impact") or 0) * 0.4)
        # STEP-3 LAYER 4 — confirm-suppression (ruling C: demote + cap-aware). A non-risk
        # signal in a domain whose position CONFIRMS its aim (alignment == on_target) is
        # noise — you chose this stance and you're sitting on it. Flag `confirm` so
        # cap_briefing sheds it off the home briefing (tension/risk fill first), and demote
        # its impact so it sinks in the full Signals list — but it STAYS there, never
        # silently dropped. RISK-EXEMPT: a risk_framed absence is exposure, not confirmation
        # (the maternity-zero guard) — `not s["risk_framed"]` spares it. on_target ONLY
        # (David): ahead = overspend-vs-intent and behind = the gap both stay actionable.
        # domain_alignment degrades to the global market_position; strategy-off → empty map
        # → nothing confirms → byte-identical. No target / Governance → not in the map.
        if (not s.get("risk_framed")
                and (domain_alignment or {}).get(s.get("domain")) == "on_target"):
            s["confirm"] = True
            s["impact"] = round((s.get("impact") or 0) * CONFIRM_DEMOTE_MULT)
    out = [s for s in out if not s.get("_suppress")]
    # CHIP BUCKET (2026-06-30): ONE place computes each signal's filter chip, so the frontend
    # renders/counts/filters by s["bucket"] only — no prevalence-word literals in the JS. Precedence:
    # neutral FIRST (-> context, keeps neutral-below out of below-market), then Position RAG, then the
    # prevalence tag via practice_axis (single word source: common/alternative/rare). Tags are final
    # here (the approach recast above already set "AN ALTERNATIVE CHOICE"). DISPLAY-only — no effect
    # on position/kind/impact/ranking/the gauge.
    # canonical chip order (Position axis, then Prevalence common->alternative->rare, then Context);
    # bucket_order ships per-signal so the frontend orders chips WITHOUT knowing the prevalence words.
    _BUCKET_ORDER = {"below market": 0, "on market": 1, "above market": 2, "peer position": 3,
                     practice_axis.bucket_word("with_majority"): 4, practice_axis.bucket_word("established"): 5,
                     practice_axis.bucket_word("less_common"): 6, "context": 7}
    for s in out:
        if s.get("polarity") == "neutral":
            s["bucket"] = "context"
        elif s.get("position") in ("below", "on", "above"):
            s["bucket"] = s["position"] + " market"
        else:                                          # position in (differs, practice): practice / quantity
            _btag = s.get("tag") or ""
            if _btag in ("HIGHER THAN PEERS", "LOWER THAN PEERS"):
                s["bucket"] = "peer position"
            elif _btag == "COMMON — YOU DON'T":
                s["bucket"] = practice_axis.bucket_word("with_majority")     # common
            elif _btag == "A RARE CHOICE":
                s["bucket"] = practice_axis.bucket_word("less_common")       # rare
            else:                                       # approach ("AN ALTERNATIVE CHOICE")
                s["bucket"] = practice_axis.bucket_word("established")        # alternative
        s["bucket_order"] = _BUCKET_ORDER.get(s["bucket"], 99)
    # PER-METRIC GAP MAGNITUDE for the verdict severity adverb (clearly/moderately/marginally),
    # client-rendered on the Signals row (Ruling A, 2026-06-26). Mirrors the hero's depth adverb,
    # but per-METRIC and in REAL-TERMS %-gap from the peer median (not percentile — a reward
    # director judges materiality in gap size). ONLY positioned VALUE verdicts get it: prevalence
    # ("most do this", no value), neutral/context, and approach/differs are excluded BY PROPERTY
    # (no numeric value + p50). The client floors a <3% gap to NO adverb (at-market noise). Reuses
    # the item's value+p50; presentation-only -> gauge-neutral, and gap_pct is not in signal_key /
    # signal_state, so it never changes the change-alert identity (no rebaseline).
    _item_by_key = {}
    for _it in items:
        _item_by_key[(_it.get("question_id"), _it.get("row_id"))] = _it
    for s in out:
        if (s.get("position") not in ("below", "above") or s.get("polarity") == "neutral"
                or s.get("kind") in ("prevalence", "depth", "money")):
            continue                            # only positioned VALUE verdicts; prevalence (adoption,
        _sid = s.get("sig_id") or ""            # not a value gap) / depth / money are out of scope
        _row = _sid.split("::", 1)[1] if "::" in _sid else None
        _it = _item_by_key.get((s["question_id"], _row)) or _item_by_key.get((s["question_id"], None))
        if not _it:
            continue
        _v, _p = _it.get("value"), _it.get("p50")
        if _v is None or _p in (None, 0):
            continue
        try:
            s["gap_pct"] = round(abs(float(_v) - float(_p)) / abs(float(_p)) * 100.0, 1)
        except (TypeError, ValueError):
            pass
    # ANCHOR PROVENANCE capture (stage 1, 2026-06-26): attach the per-metric anchor grade for the
    # 121 graded metrics (A/B/C = verified · EST = estimate); a question_id ABSENT from the config is
    # UNKNOWN by omission (the ~723 ungraded — NEVER defaulted to verified). CAPTURE-ONLY: the grade
    # rides the signal payload so it's READABLE at render, but nothing renders it here — stage 2
    # (the verified/estimate/unknown render fork) is its own ruling. Metadata, not a value ->
    # gauge-neutral; not in signal_key / signal_state -> no rebaseline, no storm.
    _prov = anchor_provenance()
    if _prov:
        for s in out:
            _pv = _prov.get(s.get("question_id"))
            if _pv:
                s["anchor_grade"] = _pv.get("grade")
                s["anchor_source"] = _pv.get("source") or ""   # stage-2: citation for the verified hover
    if not cap:                                    # full set for the Signals explore page
        out.sort(key=lambda s: -s["impact"])
        for s in out:
            s.pop("impact", None)
        return out
    # home briefing: a dismissed signal never shows; a user-prioritised one
    # jumps the queue (a big impact boost so the cap picks it first).
    pool = [s for s in out if s["status"] != "dismissed"]
    for s in pool:
        if s["status"] == "priority":
            s["impact"] += 100000000
    cap_cfg = (ordered_routing().get("_david_ratified_2026_06_13", {}) or {}).get("briefing_cap", {})
    capped = cap_briefing(pool, cfg.get("max_signals", 5), cfg.get("max_per_lens", 2),
                          cap_cfg.get("max_behind", 3))
    for s in capped:
        s.pop("impact", None)
    return capped


def cap_briefing(out, max_signals=5, max_per_lens=2, max_behind=3):
    """David-ratified HARD RESERVE so behind signals don't crowd out the newer
    mechanisms. Up to max_behind behind; the rest reserved for non-behind kinds,
    filled by impact. If too few non-behind exist, unfilled reserved slots fall
    back to the next-highest behind — always max_signals when that many exist
    (within the per-lens cap), never a blank slot, never a silently dropped
    signal. Reserve size is panel-tunable.

    STEP-3 LAYER 4 (cap-aware confirm shedding): a `confirm` signal (non-risk, in a
    domain whose position is on_target with its aim) is the LOWEST briefing priority —
    tension + risk + every other non-confirm signal fill first; a confirm signal reaches
    the briefing only as a last-resort fallback when genuine room remains. It is NEVER
    dropped from the set (the cap=False full Signals list keeps it) — only deprioritised
    here. No confirm signals → `primary` == `out` → byte-identical to pre-layer-4."""
    out = sorted(out, key=lambda s: -s["impact"])
    reserve_nb = max(0, max_signals - max_behind)
    capped, per_lens = [], {}

    def room(s):
        return per_lens.get(s["lens"], 0) < max_per_lens

    def add(s):
        per_lens[s["lens"]] = per_lens.get(s["lens"], 0) + 1
        capped.append(s)

    primary = [s for s in out if not s.get("confirm")]   # tension / risk / other first
    bh = nb = 0
    for s in primary:                              # pass 1: behind<=max_behind + reserve non-behind
        if len(capped) >= max_signals:
            break
        if not room(s):
            continue
        if s["kind"] == "behind":
            if bh < max_behind:
                add(s); bh += 1
        elif nb < reserve_nb:
            add(s); nb += 1
    if len(capped) < max_signals:                  # pass 2: fallback — fill remaining by impact (non-confirm)
        taken = {id(s) for s in capped}
        for s in primary:
            if len(capped) >= max_signals:
                break
            if id(s) not in taken and room(s):
                add(s)
    if len(capped) < max_signals:                  # pass 3: last resort — confirm signals only if room remains
        taken = {id(s) for s in capped}
        for s in out:
            if not s.get("confirm") or id(s) in taken:
                continue
            if len(capped) >= max_signals:
                break
            if room(s):
                add(s)
    return capped


def domain_dots(items):
    """Per-category dot for the tiles: the MEDIAN polarity-adjusted
    percentile of the category's positioned items (50 = with the market;
    right of the peer band = ahead). None when nothing positions."""
    by_cat = {}
    for i in items:
        if i["favourable"] is None:
            continue
        by_cat.setdefault(i["subpower"], []).append(50.0 + i["distance"])
    out = {}
    for cat, vals in by_cat.items():
        vals.sort()
        n = len(vals)
        out[cat] = round(vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0, 1)
    return out
