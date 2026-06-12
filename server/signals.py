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


def build_signals(items, opportunity, questions, get_block, org_answers):
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
        out.append({
            "lens": pos_lenses[qid], "kind": "behind", "question_id": qid,
            "value_display": "P%d" % round(i["percentile"]),
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
                "detail": "of peers %s — you don't yet" % _phrase(q.display_title),
                "impact": 10000 + adoption * 10,
            })
            seen_q.add(qid)

    # rank by impact, balance the briefing: at most max_per_lens per lens
    out.sort(key=lambda s: -s["impact"])
    capped, per_lens = [], {}
    max_per = cfg.get("max_per_lens", 2)
    for s in out:
        if per_lens.get(s["lens"], 0) >= max_per:
            continue
        per_lens[s["lens"]] = per_lens.get(s["lens"], 0) + 1
        s.pop("impact", None)
        capped.append(s)
        if len(capped) >= cfg.get("max_signals", 5):
            break
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
