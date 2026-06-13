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
        short = _short(spec.get("title") or q.display_title)
        sigs.append({
            "lens": spec.get("lens", "retain"), "kind": "depth", "question_id": qid,
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
    return (t[:44] + "…") if len(t) > 46 else t


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


def build_signals(items, opportunity, questions, get_block, org_answers, conn=None, org_id=None):
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
        out.append({
            "lens": pos_lenses[qid], "kind": "behind", "question_id": qid,
            "value_display": "P%d" % round(i["percentile"]),
            "label_short": "%s · %s vs %s" % (_short(i["label"].split(" — ")[0], row_lbl),
                                              i["value_display"], i["p50_display"] or "median"),
            "detail": "%s — %s vs %s peer median" % (i["label"], i["value_display"], i["p50_display"] or "the"),
            "impact": 100000 + (behind_at - adj) * 100,
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
        short = _short(q.display_title)
        out.append({
            "lens": spec.get("lens", "engage"), "kind": "outlier", "question_id": qid,
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
        short = _short(q.display_title)
        out.append({
            "lens": spec.get("lens", "retain"), "kind": "behind", "question_id": qid,
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
        else:
            detail = "%d%% of peers select “%s” — you don't" % (round(a), lab)
        out.append({"lens": spec.get("lens", "engage"), "kind": "rare", "question_id": qid,
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
                        "value_display": mine, "label_short": "%s · %s" % (_short(q.display_title), mine),
                        "detail": "you answered “%s” — only %d%% of peers do" % (mine, round(a)),
                        "impact": 22000 + (50 - a) * 100})
            seen_q.add(qid)

    cap_cfg = (ordered_routing().get("_david_ratified_2026_06_13", {}) or {}).get("briefing_cap", {})
    capped = cap_briefing(out, cfg.get("max_signals", 5), cfg.get("max_per_lens", 2),
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
    signal. Reserve size is panel-tunable."""
    out = sorted(out, key=lambda s: -s["impact"])
    reserve_nb = max(0, max_signals - max_behind)
    capped, per_lens = [], {}

    def room(s):
        return per_lens.get(s["lens"], 0) < max_per_lens

    def add(s):
        per_lens[s["lens"]] = per_lens.get(s["lens"], 0) + 1
        capped.append(s)

    bh = nb = 0
    for s in out:                                  # pass 1: behind<=max_behind + reserve non-behind
        if len(capped) >= max_signals:
            break
        if not room(s):
            continue
        if s["kind"] == "behind":
            if bh < max_behind:
                add(s); bh += 1
        elif nb < reserve_nb:
            add(s); nb += 1
    if len(capped) < max_signals:                  # pass 2: fallback — fill remaining by impact
        taken = {id(s) for s in capped}
        for s in out:
            if len(capped) >= max_signals:
                break
            if id(s) not in taken and room(s):
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
