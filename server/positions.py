"""Position analytics shared by every surface (overview, cards, board pack,
analyst, starter layout): one definition of percentile rank, favourability,
"biggest gaps/strengths", plain-English readouts, gap-to-£ and the gap register.
"""
import bisect
import json
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, uj, get_meta
from library import load_questions
from aggregate import (aggregate_question_for_orgs, score_answer, score_polarity, matrix_value,
                       practice_status, STATUS_POINTS,
                       coerce_number, SUPPRESSION_FLOOR, DEFAULT_ASSUMPTIONS)

# ---------------------------------------------------------------- formatting

def fmt_value(v, unit, decimals=None):
    """Survey-house formatting: £12,500; 8.5%; 24.3 days. unit = unit_block dict."""
    if v is None:
        return "—"
    ut = (unit or {}).get("type", "none")
    if ut == "currency":
        return "£{:,.0f}".format(round(v))
    if ut == "percentage":
        s = "{:.1f}".format(v).rstrip("0").rstrip(".")
        return s + "%"
    if ut in ("days", "hours", "weeks"):
        s = "{:.1f}".format(v).rstrip("0").rstrip(".")
        return "%s %s" % (s, ut)
    fmt = "{:.2f}" if abs(v) < 10 else "{:.1f}"
    s = fmt.format(v).rstrip("0").rstrip(".")
    return s


def percentile_rank(sorted_vals, x):
    """Midrank percentile of x within sorted peer values. Clamped to [1, 99]
    for display (survey-house convention: never claim P0 or P100)."""
    if not sorted_vals:
        return None
    lo = bisect.bisect_left(sorted_vals, x)
    hi = bisect.bisect_right(sorted_vals, x)
    r = 100.0 * (lo + (hi - lo) * 0.5) / len(sorted_vals)
    return min(99.0, max(1.0, r))


# ---------------------------------------------------------------- cut logic

def resolve_block(payload_section_all, payload_section_cuts, cut):
    """Returns (block, cut_label) for a cut dict {dim, value?, label?}."""
    dim = cut.get("dim", "all")
    if dim == "all":
        return payload_section_all, "All peers"
    if dim == "industry":
        return (payload_section_cuts.get("by_industry", {}).get(cut.get("value")),
                cut.get("value", ""))
    if dim == "fte_band":
        return (payload_section_cuts.get("by_fte_band", {}).get(cut.get("value")),
                "%s FTE" % cut.get("value", ""))
    return None, ""


def block_for(payload, cut, twin_blocks=None):
    """Main (non-score) block for a question payload under a cut."""
    if cut.get("dim") in ("twin", "group"):
        b = (twin_blocks or {}).get("main")
        return b, cut.get("label") or "Organisations like you"
    return resolve_block(payload.get("all"), payload, cut)


def score_block_for(payload, cut, twin_blocks=None):
    sc = payload.get("scores")
    if sc is None:
        return None, ""
    if cut.get("dim") in ("twin", "group"):
        return (twin_blocks or {}).get("score"), cut.get("label") or "Organisations like you"
    return resolve_block(sc.get("all"), sc, cut)


def presence_block_for(payload, cut, twin_blocks=None):
    pr = payload.get("presence")
    if pr is None:
        return None, ""
    if cut.get("dim") in ("twin", "group"):
        return (twin_blocks or {}).get("presence"), cut.get("label") or "Organisations like you"
    return resolve_block(pr.get("all"), pr, cut)


def matrix_row_block_for(row, cut, twin_blocks=None):
    if cut.get("dim") in ("twin", "group"):
        return ((twin_blocks or {}).get("rows", {}).get(row["row_id"]),
                "Organisations like you")
    return resolve_block(row.get("all"), row, cut)


def is_suppressed(block):
    return block is None or block.get("suppressed")


# ------------------------------------------------------------ org answers

def get_org_answers(conn, org_id, snapshot_id=1):
    out = {}
    for r in conn.execute(
            "SELECT question_id, matrix_row_id, value FROM answers WHERE org_id=? AND snapshot_id=?",
            (org_id, snapshot_id)):
        out[(r["question_id"], r["matrix_row_id"] or "")] = r["value"]
    return out


def load_payloads(conn, snapshot_id=1):
    return {r["question_id"]: uj(r["payload_json"])
            for r in conn.execute(
                "SELECT question_id, payload_json FROM benchmark_snapshots WHERE snapshot_id=?",
                (snapshot_id,))}


# ------------------------------------------------- comparable position items

def position_items(org_id, cut, questions, payloads, org_answers,
                   entitled, twin_blocks_by_q=None):
    """One item per comparable data point. Comparable = (a) numeric question or
    matrix row with an org value and an unsuppressed cut, ranked against peer
    values; (b) scored select/yes_no/multi question, ranked against peer
    practice scores. Single definition reused everywhere "biggest gaps" appears."""
    items = []
    twin_blocks_by_q = twin_blocks_by_q or {}
    for qid, q in questions.items():
        if not entitled(q):
            continue
        p = payloads.get(qid)
        if p is None:
            continue
        tb = twin_blocks_by_q.get(qid)
        if q.type == "numeric":
            v = coerce_number(org_answers.get((qid, "")))
            if v is None:
                continue
            blk, cut_label = block_for(p, cut, tb)
            if is_suppressed(blk):
                continue
            r = percentile_rank(blk["_values"], v)
            items.append(_item(q, None, v, r, blk, cut_label, "value"))
        elif q.type == "matrix":
            for row in p.get("matrix_rows", []):
                v = matrix_value(org_answers.get((qid, row["row_id"])))
                if v is None:
                    continue
                blk, cut_label = matrix_row_block_for(row, cut, tb)
                # categorical rows (select blocks) carry no value distribution —
                # a banded answer like "12 weeks" must never become a fake rank
                if is_suppressed(blk) or "_values" not in blk:
                    continue
                r = percentile_rank(blk["_values"], v)
                items.append(_item(q, row, v, r, blk, cut_label, "value"))
        elif q.is_scored and q.type in ("single_select", "yes_no", "multi_select"):
            raw = org_answers.get((qid, ""))
            if raw is None:
                continue
            s = score_answer(q, raw)
            if s is None:
                continue
            blk, cut_label = score_block_for(p, cut, tb)
            if is_suppressed(blk):
                continue
            r = percentile_rank(blk["_scores"], s)
            it = _item(q, None, s, r, blk, cut_label, "score")
            it["org_answer_label"] = raw
            items.append(it)
    return items


def practice_position_items(org_id, cut, questions, payloads, org_answers,
                            entitled, twin_blocks_by_q=None):
    """Direction-bearing PRACTICE positions for questions the score layer
    cannot rank (unscored — e.g. new-release additions). The org's presence
    status (practice_status -> STATUS_POINTS) is ranked against the peer
    status distribution reconstructed from the SAME stored block, weighted
    by option share. Honest by construction: neutral questions never
    position; N/A / unknown statuses are never evidence; multi_select is
    excluded (an option distribution cannot reconstruct per-org statuses).
    Feeds ONLY the home-tile rollup — the overall arc, signals, chips and
    the gap register keep the score/value pool untouched."""
    from aggregate import practice_status, STATUS_POINTS
    items = []
    twin_blocks_by_q = twin_blocks_by_q or {}
    for qid, q in questions.items():
        if not entitled(q):
            continue
        if q.polarity not in ("higher_is_better", "lower_is_better"):
            continue
        if q.type not in ("single_select", "yes_no") or q.is_scored:
            continue                       # scored questions already rank (or
        raw = org_answers.get((qid, ""))   # legitimately refuse to)
        if raw in (None, ""):
            continue
        st = practice_status(q, raw)
        if st not in STATUS_POINTS:
            continue                       # N/A / don't-know is never evidence
        p = payloads.get(qid)
        if p is None:
            continue
        blk, cut_label = block_for(p, cut, twin_blocks_by_q.get(qid))
        if is_suppressed(blk):
            continue
        mine = STATUS_POINTS[st]
        below = equal = total = 0.0
        for o in blk.get("options") or []:
            ost = practice_status(q, o["label"])
            if ost not in STATUS_POINTS:
                continue
            w = o.get("pct") or 0.0
            total += w
            pts = STATUS_POINTS[ost]
            if pts < mine:
                below += w
            elif pts == mine:
                equal += w
        if total <= 0:
            continue
        r = 100.0 * (below + equal / 2.0) / total
        it = _item(q, None, mine, r, blk, cut_label, "practice")
        it["value_display"] = st.replace("_", " ")
        it["org_answer_label"] = raw
        items.append(it)
    return items


def _item(q, row, value, rank, blk, cut_label, kind):
    # score items live on the direction-corrected points scale (higher = better)
    if kind == "score":
        pol = score_polarity(q)
    else:
        pol = q.polarity
    favourable = None
    if pol == "higher_is_better":
        favourable = rank > 55 and "good" or (rank < 45 and "bad" or "mid")
    elif pol == "lower_is_better":
        favourable = rank < 45 and "good" or (rank > 55 and "bad" or "mid")
    label = q.display_title + ((" — " + row["label"]) if row else "")
    return {
        "question_id": q.id,
        "row_id": row["row_id"] if row else None,
        "label": label,
        "superpower": q.superpower,
        "subpower": q.sub_power,
        "kind": kind,                       # value | score
        "value": value,
        "value_display": fmt_value(value, q.unit_block()) if kind == "value" else "{:.0f}/100".format(value),
        "percentile": round(rank, 1),
        "polarity": pol,
        "favourable": favourable,           # good | mid | bad | None(neutral)
        "distance": (rank - 50.0) * (1 if pol == "higher_is_better" else -1 if pol == "lower_is_better" else 0),
        "n": blk["n"],
        "p50": blk.get("p50"),
        "p50_display": fmt_value(blk.get("p50"), q.unit_block()) if kind == "value" else None,
        # additive display fields (board pack quartile columns, 2026-07-02; tails Sprint 2) —
        # no other consumer reads these; scoring/routing/gauge behaviour unchanged by
        # construction. The pack layer applies the graduated display thresholds.
        "p25_display": fmt_value(blk.get("p25"), q.unit_block()) if kind == "value" else None,
        "p75_display": fmt_value(blk.get("p75"), q.unit_block()) if kind == "value" else None,
        "p10_display": fmt_value(blk.get("p10"), q.unit_block()) if kind == "value" else None,
        "p90_display": fmt_value(blk.get("p90"), q.unit_block()) if kind == "value" else None,
        "cut_label": cut_label,
        "unit": q.unit_block(),
        "tier": q.lumi_tier,
        "category": q.category,
    }


def top_gaps(items, k):
    """THE definition of 'biggest gaps': polarity-adjusted percentile distance
    below the median, worst first. Reused by overview callouts, starter layout,
    analyst starter questions, and the board pack."""
    gaps = [i for i in items if i["polarity"] != "neutral" and i["distance"] < 0]
    return sorted(gaps, key=lambda i: i["distance"])[:k]


def top_strengths(items, k):
    s = [i for i in items if i["polarity"] != "neutral" and i["distance"] > 0]
    return sorted(s, key=lambda i: -i["distance"])[:k]


# ------------------------------------------------------ plain-English layer

def tens_phrase(rank):
    """'higher than about 7 in 10 similar organisations' (never replaces the
    technical percentile — rendered alongside it)."""
    x = int(round(rank / 10.0))
    x = max(0, min(10, x))
    if rank >= 95:
        return "among the very highest in this peer group"
    if rank <= 5:
        return "among the very lowest in this peer group"
    if 48 <= rank <= 52:
        return "right around the middle of this peer group"
    if x >= 10:
        return "higher than 9 in 10 similar organisations"
    if x <= 0:
        return "lower than 9 in 10 similar organisations"
    return "higher than about %d in 10 similar organisations" % x


def readout_numeric(item):
    return "Your %s (%s) is %s (P%d, %s, n=%d)." % (
        _lower_first(item["label"]), item["value_display"],
        tens_phrase(item["percentile"]), int(round(item["percentile"])),
        item["cut_label"], item["n"])


def readout_score(item, q):
    return "Your approach to %s scores %s on lumi's practice scale — %s (P%d, %s, n=%d)." % (
        _lower_first(item["label"]), item["value_display"],
        tens_phrase(item["percentile"]), int(round(item["percentile"])),
        item["cut_label"], item["n"])


def readout_select(q, org_label, blk, cut_label):
    """For categorical cards: relate the org's choice to the distribution."""
    if is_suppressed(blk):
        return SUPPRESSED_COPY
    opts = blk.get("options", [])
    mine = next((o for o in opts if o["label"].strip().lower() == (org_label or "").strip().lower()), None)
    top = max(opts, key=lambda o: o["count"]) if opts else None
    if mine is None:
        if top is None:
            return None
        return "The most common answer among %s (%d%%) is “%s” (n=%d)." % (
            _peers(cut_label), int(round(top["pct"])), top["label"], blk["n"])
    if top and mine["code"] == top["code"]:
        return "Like %d%% of %s, you answered “%s” — the most common approach (n=%d)." % (
            int(round(mine["pct"])), _peers(cut_label), mine["label"], blk["n"])
    return "You answered “%s”, as did %d%% of %s; the most common answer is “%s” (%d%%, n=%d)." % (
        mine["label"], int(round(mine["pct"])), _peers(cut_label),
        top["label"], int(round(top["pct"])), blk["n"])


SUPPRESSED_COPY = "There aren't enough organisations in this peer group to show this safely (fewer than 5)."


def _peers(cut_label):
    if cut_label == "All peers":
        return "similar organisations"
    if cut_label == "Organisations like you":
        return "organisations like you"
    return "%s peers" % cut_label


def _lower_first(s):
    return s[0].lower() + s[1:] if s and s[1:2] != s[1:2].upper() else s


# ----------------------------------------------------------------- overview

def overview_summary(items, mp_config=None, practice_items=None,
                     band_low=None, band_high=None):
    """The "above the market median on X of Y comparable metrics" headline
    (board pack + share). When `mp_config` is supplied it counts the SAME
    Substance pool the gauge uses (Level + Provision, higher_is_better,
    competitive domains) so the headline and the dashboard gauge agree by
    construction; without it, the legacy full-polarised pool is counted.

    When band_low/band_high are given (the gauge's MARKET_BAND), each comparable
    item is bucketed by _market_class at the SAME thresholds the gauge uses, so
    above/on/below match hero.market exactly (finishing task #86 — the headline
    was re-axed to the Substance POOL but still split it at the per-metric 45/55
    `favourable` cut, drifting from the gauge's 35/65). Neutral items (favourable
    None) stay excluded from the comparable count. No bands → legacy 45/55 path
    (degrades byte-for-byte)."""
    if mp_config and mp_config.get("metrics"):
        items = substance_pool(items, practice_items, mp_config)

    def _cls(i):
        if i.get("favourable") is None:
            return None                       # neutral — not comparable, never counted
        if band_low is not None and band_high is not None:
            k = _market_class(i, band_low, band_high)
            return "good" if k == "above" else "bad" if k == "below" else "mid"
        return i["favourable"]

    above = sum(1 for i in items if _cls(i) == "good")
    below = sum(1 for i in items if _cls(i) == "bad")
    inline = sum(1 for i in items if _cls(i) == "mid")
    comparable = above + below + inline
    by_sp = defaultdict(lambda: {"available": 0, "above": 0, "below": 0, "inline": 0,
                                 "quartiles": [0, 0, 0, 0]})
    for i in items:
        c = by_sp[i["superpower"]]
        c["available"] += 1
        fc = _cls(i)
        if fc == "good":
            c["above"] += 1
        elif fc == "bad":
            c["below"] += 1
        elif fc == "mid":
            c["inline"] += 1
        qx = min(3, int(i["percentile"] // 25))
        c["quartiles"][qx] += 1
    by_sec = defaultdict(lambda: {"available": 0, "above": 0, "below": 0, "inline": 0,
                                  "quartiles": [0, 0, 0, 0]})
    for i in items:
        if not i.get("subpower"):
            continue
        c = by_sec[i["subpower"]]
        c["available"] += 1
        fc = _cls(i)
        if fc == "good":
            c["above"] += 1
        elif fc == "bad":
            c["below"] += 1
        elif fc == "mid":
            c["inline"] += 1
        qx = min(3, int(i["percentile"] // 25))
        c["quartiles"][qx] += 1
    return {
        "comparable_metrics": comparable,
        "above_median": above,
        "below_median": below,
        "broadly_in_line": inline,
        "neutral_tracked": len(items) - comparable,
        "by_superpower": dict(by_sp),
        "by_section": dict(by_sec),
    }


def callouts(items, questions, k=3):
    """Top-3 strengths and gaps, each citing metric, percentile, cut, n."""
    out = {"strengths": [], "gaps": []}
    for key, rows in (("strengths", top_strengths(items, k)), ("gaps", top_gaps(items, k))):
        for it in rows:
            quart = ("top quartile" if it["percentile"] >= 75 else
                     "upper half" if it["percentile"] >= 50 else
                     "lower half" if it["percentile"] >= 25 else "bottom quartile")
            adj_quart = quart
            if it["polarity"] == "lower_is_better":
                adj_quart = {"top quartile": "highest quartile", "upper half": "upper half",
                             "lower half": "lower half", "bottom quartile": "lowest quartile"}[quart]
            if it["kind"] == "score":
                txt = "Your approach to %s scores %s on lumi's practice scale — the %s of %s (P%d, n=%d)." % (
                    _lower_first(it["label"]), it["value_display"], adj_quart,
                    _peers(it["cut_label"]), int(round(it["percentile"])), it["n"])
            else:
                txt = "Your %s (%s) sits in the %s of %s (P%d, n=%d)." % (
                    _lower_first(it["label"]), it["value_display"], adj_quart,
                    _peers(it["cut_label"]), int(round(it["percentile"])), it["n"])
            out[key].append({"text": txt, "item": it})
    return out


# ------------------------------------------------------------- gap-to-£ ----

# Default workforce mix by role level — an explicit, editable assumption.
LEVEL_SHARES = {
    "board_executive": 0.005, "director": 0.015, "head_of": 0.03,
    "senior_manager": 0.07, "manager": 0.13, "supervisor_team_leader": 0.15,
    "frontline_individual_contributor": 0.60,
}

MONEY_METRICS = [
    {
        "question_id": "REW_BEN_PENS_EMP_MAX_01", "kind": "pension",
        "label": "Employer pension contribution",
        "direction": "investment",
        "formula": "(peer percentile % − your %) × median salary × FTE at level (level mix assumption)",
    },
    {
        "question_id": "ATT_OBO_REGRET_ATTR_01", "kind": "attrition",
        "label": "Regretted attrition",
        "direction": "saving",
        "formula": "(your % − peer percentile %) × FTE at level × cost per leaver (35% of median salary)",
    },
    {
        "question_id": "ATT_HIR_AGENCY_RATE_01", "kind": "agency",
        "label": "Agency usage",
        "direction": "saving",
        "formula": "(your % − peer percentile %) × FTE at level × median salary × agency premium (30%)",
    },
]


def get_assumptions(conn, org_id):
    base = dict(get_meta("assumptions_defaults", DEFAULT_ASSUMPTIONS, conn))
    base["level_shares"] = dict(LEVEL_SHARES)
    row = conn.execute("SELECT assumptions_json FROM org_assumptions WHERE org_id=?", (org_id,)).fetchone()
    if row:
        base.update(uj(row["assumptions_json"], {}))
    return base


def money_opportunities(conn, org, questions, payloads, org_answers, cut, twin_blocks_by_q=None):
    """Rule-based £ modelling. Only non-neutral, non-suppressed metrics; every
    output labelled indicative with the formula attached."""
    a = get_assumptions(conn, org["org_id"])
    fte = a["fte_band_midpoints"].get(org["fte_band"] or "", None)
    salary = a["median_salary_gbp"]
    results = []
    for mm in MONEY_METRICS:
        q = questions.get(mm["question_id"])
        p = payloads.get(mm["question_id"])
        if q is None or p is None or q.polarity == "neutral":
            continue
        rows_out, tot50, tot75 = [], 0.0, 0.0
        any_data = False
        for row in p.get("matrix_rows", []):
            v = coerce_number(org_answers.get((q.id, row["row_id"])))
            blk, cut_label = matrix_row_block_for(row, cut, (twin_blocks_by_q or {}).get(q.id))
            if v is None or is_suppressed(blk):
                continue
            any_data = True
            share = a["level_shares"].get(row["row_id"], 0.0)
            lvl_fte = (fte or 0) * share
            for pct_key, tgt in (("p50", blk.get("p50")), ("p75", blk.get("p75"))):
                if tgt is None:
                    continue
                if q.polarity == "higher_is_better":
                    gap_pp = max(0.0, tgt - v)
                else:
                    gap_pp = max(0.0, v - tgt)
                if mm["kind"] == "pension":
                    impact = gap_pp / 100.0 * salary * lvl_fte
                elif mm["kind"] == "attrition":
                    impact = gap_pp / 100.0 * lvl_fte * (a["cost_per_leaver_pct_salary"] / 100.0 * salary)
                else:  # agency
                    impact = gap_pp / 100.0 * lvl_fte * salary * (a["agency_premium_pct"] / 100.0)
                if pct_key == "p50":
                    tot50 += impact
                else:
                    tot75 += impact
            rows_out.append({
                "row_id": row["row_id"], "label": row["label"], "your_value": v,
                "p50": blk.get("p50"), "p75": blk.get("p75"), "n": blk["n"],
            })
        if not any_data or (round(tot50) == 0 and round(tot75) == 0):
            continue
        results.append({
            "question_id": q.id, "label": mm["label"], "kind": mm["kind"],
            "direction": mm["direction"], "formula": mm["formula"],
            "to_p50_gbp": round(tot50), "to_p75_gbp": round(tot75),
            "rows": rows_out, "fte_known": fte is not None,
            "cut_label": (block_for(p, cut, (twin_blocks_by_q or {}).get(q.id)))[1],
        })
    total_savings = sum(r["to_p50_gbp"] for r in results if r["direction"] == "saving")
    total_invest = sum(r["to_p50_gbp"] for r in results if r["direction"] == "investment")
    return {
        "items": results,
        "total_savings_to_p50_gbp": round(total_savings),
        "total_investment_to_p50_gbp": round(total_invest),
        "assumptions": a,
        "fte_known": fte is not None,
        "indicative": True,
    }


# --------------------------------------------------------------- gap register

def gap_register(conn, org, questions, payloads, org_answers, cut, sector_cut=None,
                 entitled=None, twin_blocks_by_q=None):
    """Practice & policy register on PRESENCE semantics: a substantive answer
    (any real frequency/approach/level) means the practice is in place; only
    explicit-absence options mean it isn't; is_na answers and blanks are not
    assessable. practice_status() is the single source of truth — the same
    function drives the org's own status, peer adoption and maturity."""
    rows = []
    sp_scores = defaultdict(list)
    sp_peer_p50 = defaultdict(list)
    for qid, q in questions.items():
        if q.category not in ("practice", "policy"):
            continue
        if entitled and not entitled(q):
            continue
        if not (q.is_scored and q.type in ("single_select", "yes_no", "multi_select")):
            continue
        p = payloads.get(qid)
        if p is None or "presence" not in p:
            continue
        blk, cut_label = presence_block_for(p, cut, (twin_blocks_by_q or {}).get(qid))
        raw = org_answers.get((qid, ""))
        status = practice_status(q, raw)
        own_points = STATUS_POINTS.get(status)
        in_place = (True if status in ("in_place", "partial") else
                    False if status == "not_in_place" else None)
        adoption = None if is_suppressed(blk) else blk.get("adoption_pct")
        sector_adoption = None
        if sector_cut:
            sblk, _ = presence_block_for(p, sector_cut, None)
            if not is_suppressed(sblk):
                sector_adoption = sblk.get("adoption_pct")
        if own_points is not None:
            sp_scores[q.superpower].append(own_points)
        if not is_suppressed(blk) and blk.get("status_mean") is not None:
            sp_peer_p50[q.superpower].append(blk["status_mean"])
        gap = (adoption - own_points) if (adoption is not None and own_points is not None) else None
        rows.append({
            "question_id": qid, "name": q.display_title, "superpower": q.superpower,
            "subpower": q.sub_power, "category": q.category, "tier": q.lumi_tier,
            "org_status": raw if raw is not None else "Not answered",
            "org_answered": raw is not None,
            "status": status,
            "in_place": in_place,
            "org_score": own_points,
            "peer_adoption_pct": adoption,
            "sector_adoption_pct": sector_adoption,
            "n": blk["n"] if blk else 0,
            "suppressed": bool(is_suppressed(blk)),
            "gap": round(gap, 1) if gap is not None else None,
        })
    rows.sort(key=lambda r: -(r["gap"] if r["gap"] is not None else -999))
    maturity = {}
    for sp in set(list(sp_scores) + list(sp_peer_p50)):
        ours = sp_scores.get(sp) or []
        peers = sp_peer_p50.get(sp) or []
        maturity[sp] = {
            "org_score": round(sum(ours) / len(ours), 1) if ours else None,
            "peer_median_score": round(sum(peers) / len(peers), 1) if peers else None,
            "questions_scored": len(ours),
        }
    # the same rollup by section (sub_power), driving the focused-mode tiles
    sec_scores, sec_peer = defaultdict(list), defaultdict(list)
    sec_order = {}
    for r in rows:
        q = questions.get(r["question_id"])
        if q is None or not q.sub_power:
            continue
        sec_order.setdefault(q.sub_power, q.sub_power_order or 999)
        if r["org_score"] is not None:
            sec_scores[q.sub_power].append(r["org_score"])
        if not r["suppressed"]:
            blk, _ = presence_block_for(payloads.get(r["question_id"], {}), cut,
                                        (twin_blocks_by_q or {}).get(r["question_id"]))
            if blk and not is_suppressed(blk) and blk.get("status_mean") is not None:
                sec_peer[q.sub_power].append(blk["status_mean"])
    maturity_sections = {}
    for sec in set(list(sec_scores) + list(sec_peer)):
        ours = sec_scores.get(sec) or []
        peers = sec_peer.get(sec) or []
        maturity_sections[sec] = {
            "org_score": round(sum(ours) / len(ours), 1) if ours else None,
            "peer_median_score": round(sum(peers) / len(peers), 1) if peers else None,
            "questions_scored": len(ours),
            "order": sec_order.get(sec, 999),
        }
    return {"rows": rows, "maturity": maturity, "maturity_sections": maturity_sections}


# ============================================================= HERO SIGNALS ==
# Two signals, each grounded in what the data can defend:
#   A) MARKET POSITION (below/at/above market) — polarised metrics only, and
#      only those with a defensible rank (numeric values, matrix rows, and
#      scored selects with a known direction). The 12 polarised-but-unordered
#      single_selects can NEVER enter this pool (score_answer returns None for
#      them) — they are routed to prevalence instead. No invented order, ever.
#   B) PRACTICE PREVALENCE (with the majority / established / less common) —
#      neutral practices + the routed unmappables. Information, not verdict:
#      rendered WITHOUT the performance palette.
# All thresholds are configuration, passed in by the caller.

from aggregate import score_direction


def market_pool_qids(org_id, cut, questions, payloads, org_answers, entitled, twin_blocks_by_q=None):
    """The set of metrics the MARKET lens rates — substance-pool MEMBERSHIP (band values
    irrelevant), computed from the same items + practice_position_items + config gate the
    gauge counts. This is the PARTITION AUTHORITY for one-category-per-metric (David,
    2026-07-09): a metric in this set is market-rated (below/on/above) and must never
    also be prevalence-rated (common/alternative/rare). prevalence_items excludes by this
    set, so the two lenses are disjoint BY CONSTRUCTION on every surface."""
    cfg = market_position_config()
    items = position_items(org_id, cut, questions, payloads, org_answers, entitled, twin_blocks_by_q)
    prac = practice_position_items(org_id, cut, questions, payloads, org_answers, entitled, twin_blocks_by_q)
    return {i["question_id"] for i in substance_pool(items, prac, cfg)}


def prevalence_items(org_id, cut, questions, payloads, org_answers, entitled, twin_blocks_by_q=None):
    """One item per answered, unsuppressed select/yes_no practice with no
    defensible direction: how common the org's chosen approach is vs peers.
    PARTITIONED (2026-07-09): any metric the market lens rates is excluded here
    (market wins) — one category per metric, the two pools disjoint."""
    out = []
    twin_blocks_by_q = twin_blocks_by_q or {}
    cfg = market_position_config()                      # Q1=C: routing authority (read-only, hot-reloaded, cached)
    _market = market_pool_qids(org_id, cut, questions, payloads, org_answers, entitled, twin_blocks_by_q)
    for qid, q in questions.items():
        if qid in _market:
            continue  # market-rated -> the market lens owns it (one category per metric)
        if not entitled(q) or q.type not in ("single_select", "yes_no"):
            continue
        cls = (cfg.get("metrics", {}).get(qid) or {}).get("class")
        polarised = q.polarity in ("higher_is_better", "lower_is_better")
        # Q1=C routing (2026-06-30): Practice/Design route by mp_config class (always -> alignment);
        # Level/Provision — and any UNCLASSIFIED metric (cls None) -> safe legacy default — keep
        # score_direction routing. Scoring is untouched: this gate only reads score_direction, never
        # alters it; score_answer/score_polarity (aggregate.py) are byte-identical.
        if cls not in ("Practice", "Design") and polarised and q.is_scored and score_direction(q) != 0:
            continue  # Level/Provision with a defensible rank -> market position handles it
        raw = org_answers.get((qid, ""))
        if raw is None:
            continue
        p = payloads.get(qid)
        if p is None:
            continue
        blk, cut_label = block_for(p, cut, twin_blocks_by_q.get(qid))
        if is_suppressed(blk):
            continue
        opts = blk.get("options") or []
        mine = next((o for o in opts if o["label"] == raw), None)
        if mine is None or not opts:
            continue
        modal = max(opts, key=lambda o: o.get("pct") or 0)
        out.append({
            "question_id": qid, "label": q.display_title,
            "superpower": q.superpower, "subpower": q.sub_power,
            "your_answer": raw, "your_share": mine.get("pct"),
            "modal_answer": modal["label"], "modal_share": modal.get("pct"),
            "is_modal": mine["label"] == modal["label"],
            "n": blk["n"], "cut_label": cut_label,
            "routed_from_polarised": polarised,
        })
    return out


def _adj_percentile(item):
    """Favourable-direction percentile: high = good, regardless of polarity."""
    return item["percentile"] if item["polarity"] == "higher_is_better" else 100.0 - item["percentile"]


def _market_class(item, band_low, band_high):
    a = _adj_percentile(item)
    return "above" if a > band_high else "below" if a < band_low else "at"


def _pool_verdict(pool, band_low, band_high, margin):
    """The headline verdict + the continuous position value that drives it.

    `lean` = (above - below) / pool, the net centre-of-gravity in [-1, +1].
    The SAME value bands the verdict (below/at/above at the `margin` threshold)
    and drives the gauge needle on the client, so word and needle agree by
    construction. By construction this can never read "below" when below is the
    smallest of the three counts (below smallest => above > below => lean > 0 =>
    never "below"), and likewise for "above" — asserted in qa_hero.
    """
    if not pool:
        return None
    above = sum(1 for i in pool if _market_class(i, band_low, band_high) == "above")
    below = sum(1 for i in pool if _market_class(i, band_low, band_high) == "below")
    at = len(pool) - above - below
    lean = (above - below) / float(len(pool))
    verdict = "above" if lean > margin else "below" if lean < -margin else "at"
    # depth_pctl: the MEDIAN polarity-adjusted percentile across the pool — how FAR
    # the org sits from market, not how MANY metrics are below it. Drives the
    # severity ADVERB on the client (clearly/moderately/marginally); the verdict
    # WORD stays lean-driven ('verdict reflects mass', qa_hero). Distribution, not
    # headcount (Stage A item C, 2026-06-22).
    pctls = sorted(_adj_percentile(i) for i in pool)
    n = len(pctls)
    depth = pctls[n // 2] if n % 2 else (pctls[n // 2 - 1] + pctls[n // 2]) / 2.0
    return {"verdict": verdict, "above": above, "at": at, "below": below,
            "pool": len(pool), "lean": round(lean, 4), "lean_threshold": margin,
            "depth_pctl": round(depth, 1)}


def _prev_summary(pool, uncommon_pct):
    if not pool:
        return None
    modal = sum(1 for i in pool if i["is_modal"])
    uncommon = sum(1 for i in pool if not i["is_modal"] and (i["your_share"] or 0) < uncommon_pct)
    return {"with_majority": modal, "established": len(pool) - modal - uncommon,
            "less_common": uncommon, "pool": len(pool)}


_MP_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                            "market_position_config.json")
_mp_cache = {"mtime": None, "cfg": {}}


def market_position_config():
    """Hot-reloaded market-position classification (David-owned). Per-metric
    `class` (Level/Provision = Substance; Practice/Design = Approach),
    `direction`, `lens`; a `_domains` block with `competitiveness`; and
    `defaults` (thresholds). The engine reads class/direction/competitiveness
    from here to decide which metrics feed the competitiveness gauge — so
    David's refinements take effect on the next request, no redeploy. A
    malformed edit keeps the last good config (mirrors signals.lens_config)."""
    try:
        mt = os.path.getmtime(_MP_CFG_PATH)
    except OSError:
        return _mp_cache["cfg"]
    if _mp_cache["mtime"] != mt:
        try:
            with open(_MP_CFG_PATH) as f:
                _mp_cache["cfg"] = json.load(f)
            _mp_cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _mp_cache["cfg"]


def _mp_competitive(cfg, sec):
    return cfg.get("_domains", {}).get(sec, {}).get("competitiveness", True)


def _mp_gauge_eligible(item, cfg):
    """Does this item feed the competitiveness read? Only higher_is_better
    Substance (Level/Provision) in a competitive domain. FAIL-CLOSED: a metric
    with no config classification is one the firewall hasn't reviewed, so it
    leans OUT of the gauge (the signed-off "errors lean OUT" invariant) — it
    never earns a verdict on raw DB polarity. This runs only on the classified
    path (mp_config present); the legacy no-config path filters polarity inline
    in hero_signals, so nothing it owns is affected. A populated config holds
    every active Reward metric, so the missing-entry branch only guards a future
    un-classified release, which must be classified rather than auto-admitted."""
    if not _mp_competitive(cfg, item.get("subpower")):
        return False
    m = cfg.get("metrics", {}).get(item["question_id"])
    if not m:
        # Only fall back to legacy polarity if the WHOLE metrics map is empty
        # (mis-loaded config); a populated config with a missing entry =
        # unclassified -> excluded (fail-closed).
        return (not cfg.get("metrics")) and item["polarity"] in ("higher_is_better", "lower_is_better")
    return m.get("class") in ("Level", "Provision") and m.get("direction") == "higher_is_better"


def _approach_summary(prev_items, cfg):
    """The Approach register's companion tally — "N differ from market".

    Approach = config class Practice/Design (a choice with no better/worse). Over
    the answered, unsuppressed practices the org's choice is compared to the market
    mode: differ = not the modal answer, in_line = the modal answer. Never folded
    into the competitiveness gauge's below/on/above — it's a separate, quiet count
    (spec §6.1). Returns None when the org has no Approach metric in scope."""
    metrics = cfg.get("metrics", {})
    pool = [i for i in prev_items
            if (metrics.get(i["question_id"]) or {}).get("class") in ("Practice", "Design")]
    if not pool:
        return None
    differ = sum(1 for i in pool if not i.get("is_modal"))
    return {"differ": differ, "in_line": len(pool) - differ, "pool": len(pool)}


def _mp_normalised(item, direction):
    """Re-score an item on the CONFIG direction (authoritative), not the metric's
    stored DB polarity. Part A sometimes sets direction=higher_is_better on a
    metric whose DB polarity is `neutral` (e.g. life-assurance cover, LTI plans,
    overtime — offering more = above market). Left as-is, `_adj_percentile` would
    read the neutral polarity and score it as lower, and `favourable` would be
    None (uncounted in the headline). Returns a COPY (never mutates the shared
    item, which other surfaces read on its original polarity)."""
    if item.get("polarity") == direction and item.get("favourable") is not None:
        return item
    rank = item.get("percentile") or 0.0
    if direction == "lower_is_better":
        fav, dist = ("good" if rank < 45 else "bad" if rank > 55 else "mid"), -(rank - 50.0)
    elif direction == "higher_is_better":
        fav, dist = ("good" if rank > 55 else "bad" if rank < 45 else "mid"), (rank - 50.0)
    else:
        return item
    c = dict(item)
    c["polarity"], c["favourable"], c["distance"] = direction, fav, dist
    return c


def substance_pool(items, practice_items, cfg):
    """THE competitiveness feed — Level (scored/numeric `items`) + Provision
    (presence-ranked `practice_items`), routed by the config and re-scored on the
    config direction. The single definition shared by the gauge (hero_signals)
    AND the headline summary (overview_summary) so the dashboard and the board
    pack can never tell different stories about the same org."""
    metrics = cfg.get("metrics", {})
    out = []
    for i in list(items) + list(practice_items or []):
        if not _mp_gauge_eligible(i, cfg):
            continue
        m = metrics.get(i["question_id"])
        out.append(_mp_normalised(i, m["direction"]) if m else i)
    return out


def _metric_bands(pool, band_low, band_high, margin):
    """{question_id: 'below'|'at'|'above'} — ONE band per METRIC.

    A single-valued metric is classified by _market_class; a MATRIX metric (several pool
    items, one per row) is collapsed to its OWN _pool_verdict verdict — the same engine,
    one level up — so it reads as a single below/on/above, never row-by-row (sub-ruling,
    2026-06-27). This is the METRIC-level companion to _pool_verdict's per-READING mass
    count: the domain grid + position chips ask 'how many metrics sit below market and
    which', the home needle 'where the reading mass sits'. Shared by pool_market_bands
    (per-card bands) and the §1 domain donut's metric counts, so card, donut and chip can
    never disagree. A question with no usable item drops out (→ absent / null)."""
    by_q = {}
    for i in pool:
        by_q.setdefault(i["question_id"], []).append(i)
    out = {}
    for qid, its in by_q.items():
        if len(its) == 1:
            out[qid] = _market_class(its[0], band_low, band_high)
        else:
            v = _pool_verdict(its, band_low, band_high, margin)
            out[qid] = v["verdict"] if v else None
    return out


def pool_market_bands(items, practice_items, cfg, band_low, band_high, margin):
    """{question_id: 'below'|'at'|'above'} per METRIC for the Substance pool — the SAME
    substance_pool the competitiveness gauge counts, collapsed to one band per metric via
    _metric_bands (matrices → their own verdict). A per-card market position that can
    never disagree with the §1 donut's metric count it sums into: same pool, same
    classifier, metric-level on both sides. A metric OUTSIDE the pool — Approach
    (Practice/Design), neutral, lower_is_better, non-competitive (Governance), or
    unclassified — is absent from the map → the card reads it as null (no market rate to
    be under/over). Fixes the firewall drift where the card's legacy DB polarity
    disagreed with the config direction (a cost ratio read 'above market' the config calls
    neutral/excluded).

    Strategy-invariant by design (no location_approach=agnostic filter — that reframe
    lives only in _hero_signals_classified): the position chips that consume this never
    move under the strategy toggle (position counts are strategy-invariant)."""
    return _metric_bands(substance_pool(items, practice_items, cfg), band_low, band_high, margin)


def pool_prevalence_bands(prev_items, uncommon_pct):
    """{question_id: 'match'|'common_alt'|'rarer'} per prevalence-rated practice — the SAME
    prevalence_items pool + the SAME bucketing _prev_summary counts (is_modal + your_share
    vs uncommon_pct). A per-card prevalence band that can never disagree with the §1
    prevalence donut count it sums into: match = with_majority (your answer IS the market
    mode), rarer = less_common (off-mode AND held by < uncommon_pct of peers), common_alt =
    established (off-mode but not rare). One-per-question (prevalence_items has no matrix
    rows / per-option items), so summing per-card === the donut counts exactly — no
    metric-vs-mass complication. A metric outside the prevalence pool is absent → null."""
    out = {}
    for i in prev_items:
        if i["is_modal"]:
            out[i["question_id"]] = "match"
        elif (i["your_share"] or 0) < uncommon_pct:
            out[i["question_id"]] = "rarer"
        else:
            out[i["question_id"]] = "common_alt"
    return out


def _strategy_field(strategy, field):
    """A strategy dial's value iff it's a real 'set' choice — None when the
    strategy is absent, the field unset, or it was skipped (§5.4 provenance)."""
    if not strategy:
        return None
    v = strategy.get(field)
    if not v or (strategy.get("provenance") or {}).get(field) == "skipped":
        return None
    return v


def _market_target(market, strategy, stance_override=None):
    """Read the competitiveness verdict against the member's declared
    `market_position` target (handover §5.2) — an ANNOTATION only; it never
    changes the verdict, counts or lean (so 'verdict reflects mass' holds, and
    strategy=None degrades byte-for-byte). An above-market member who AIMED
    above-market reads 'on target', not a premium-cost flag. `stance_override`
    (step-3 layer 3): a per-domain aim (domain_targets[sec]); None → falls back
    to the global market_position (degrade-to-global)."""
    stance = stance_override or _strategy_field(strategy, "market_position")
    if not market or not stance:
        return None
    rank = {"below": 0, "at": 1, "above": 2}.get(market.get("verdict"))
    aim = {"lag": 0, "match": 1, "lead": 2}.get(stance)
    if rank is None or aim is None:
        return None
    align = "behind" if rank < aim else ("on_target" if rank == aim else "ahead")
    return {"stance": stance, "alignment": align}


def hero_signals(items, prev_items, section_order, band_low, band_high,
                 domain_min, margin, uncommon_pct, practice_items=None, tile_min=1,
                 mp_config=None, strategy=None):
    """The hero's two signals + per-domain rollups. Overall market position is
    computed from the FULL polarised pool, never an average of domain ratings.

    Two grades of domain verdict (David, 2026-06-12):
    - market: the strict, methodology-grade verdict — needs >= domain_min
      DISTINCT polarised questions. Unchanged.
    - position: what the home tile shows. The strict verdict when it exists;
      otherwise an INDICATIVE one from the combined polarised + practice
      evidence (>= tile_min distinct questions), with its basis and evidence
      counts disclosed so thin data is never dressed up as a census.

    When `mp_config` (data/market_position_config.json) is supplied, the gauge
    feed is routed by the classification instead of raw polarity — see
    _hero_signals_classified. Without it, the legacy polarity path below runs
    unchanged (keeps qa_hero's synthetic fixtures valid)."""
    practice_items = practice_items or []
    if mp_config and mp_config.get("metrics"):
        return _hero_signals_classified(items, prev_items, section_order, band_low,
                                        band_high, domain_min, margin, uncommon_pct,
                                        practice_items, tile_min, mp_config, strategy)
    pol_items = [i for i in items if i["polarity"] in ("higher_is_better", "lower_is_better")]
    domains = []
    for sec in section_order:
        d_pol = [i for i in pol_items if i.get("subpower") == sec]
        d_prev = [i for i in prev_items if i.get("subpower") == sec]
        d_prac = [i for i in practice_items if i.get("subpower") == sec]
        # eligibility counts DISTINCT polarised questions, not data points —
        # matrix rows must not let a 3-question domain earn a market verdict
        d_pol_questions = len({i["question_id"] for i in d_pol})
        strict = _pool_verdict(d_pol, band_low, band_high, margin) if d_pol_questions >= domain_min else None
        position, basis = strict, ("market" if strict else None)
        if strict is None:
            combined = d_pol + d_prac
            if len({i["question_id"] for i in combined}) >= tile_min and combined:
                position, basis = _pool_verdict(combined, band_low, band_high, margin), "indicative"
        domains.append({
            "name": sec,
            "market": strict,
            "market_eligible": d_pol_questions >= domain_min,
            "polarised_comparable": len(d_pol),
            "position": position,
            "position_basis": basis,
            "position_evidence": ({"polarised": len(d_pol), "practice": len(d_prac)}
                                  if position is not None else None),
            "prevalence": _prev_summary(d_prev, uncommon_pct),
        })
    return {
        "market": _pool_verdict(pol_items, band_low, band_high, margin),
        "prevalence": _prev_summary(prev_items, uncommon_pct),
        "domains": domains,
        "config": {"band_low": band_low, "band_high": band_high,
                   "domain_min": domain_min, "margin": margin, "uncommon_pct": uncommon_pct,
                   "tile_min": tile_min},
    }


def _hero_signals_classified(items, prev_items, section_order, band_low, band_high,
                             domain_min, margin, uncommon_pct, practice_items, tile_min, cfg, strategy=None):
    """Classification-driven gauge feed (market_position_config.json).

    The competitiveness gauge — overall AND per domain — is fed by SUBSTANCE
    only, and only where it reads as a market rate you can be under or over:

      class in {Level, Provision}  AND  direction == higher_is_better
      AND the metric's domain is competitive (_domains.competitiveness)

    Everything else is deliberately kept OUT of the below/on/above counts:
    - neutral Substance (workforce-cost %, span of control) — context, not a verdict;
    - lower_is_better Substance (the malus provision) — favourable when low, shown
      beside the gauge; its own row still inverts via _adj_percentile elsewhere;
    - Approach (Practice/Design) — 'differs from market', never a rate;
    - Governance — competitiveness=false, no headline role at all.

    Level positions come from `items` (scored/numeric ranks); Provision positions
    come from `practice_items` (presence ranked vs peer take-up). Thresholds come
    from the CALLER (the env constants) — fix class D (2026-07-11): the silent
    mp_config-defaults override that made the json a second, disagreeing authority
    is removed; env is the single source (value ratified at the live 3)."""
    dmin = domain_min
    tmin = tile_min

    # Substance pool: Level (scored/numeric) + Provision (presence-ranked), routed
    # by the config — the SAME definition overview_summary's headline uses.
    gauge_pool = substance_pool(items, practice_items, cfg)
    # location_approach=agnostic reframe (§5.2): a one-rate org's per-location pay
    # metrics aren't applicable — drop config-tagged location_scoped from the gauge.
    # No-op when unset or untagged (degrade byte-for-byte).
    if _strategy_field(strategy, "location_approach") == "agnostic":
        _m = cfg.get("metrics", {})
        gauge_pool = [i for i in gauge_pool if not (_m.get(i["question_id"]) or {}).get("location_scoped")]

    domains = []
    _dts = (strategy or {}).get("domain_targets") or {}   # step-3 layer 3: per-domain aims (null → {} → global fallback)
    for sec in section_order:
        d_prev = [i for i in prev_items if i.get("subpower") == sec]
        if not _mp_competitive(cfg, sec):
            # non-competitive (Governance): no market position — surfaced as
            # favourable / context / differs beside the headline, never a verdict
            domains.append({
                "name": sec, "market": None, "market_eligible": False,
                "polarised_comparable": 0, "position": None, "position_basis": None,
                "position_evidence": None, "competitiveness": False,
                "prevalence": _prev_summary(d_prev, uncommon_pct),
                "approach": _approach_summary(d_prev, cfg),
            })
            continue
        d_sub = [i for i in gauge_pool if i.get("subpower") == sec]
        # DISTINCT Substance questions gate the verdict (matrix rows never inflate)
        d_questions = len({i["question_id"] for i in d_sub})
        strict = _pool_verdict(d_sub, band_low, band_high, margin) if d_questions >= dmin else None
        if strict is not None:
            position, basis = strict, "market"
        elif d_questions >= tmin and d_sub:
            position, basis = _pool_verdict(d_sub, band_low, band_high, margin), "indicative"
        else:
            position, basis = None, None
        # METRIC-level counts (Pass 2a, ruling 2026-06-27): how many DISTINCT metrics sit
        # below/on/above — the unit the domain grid + position chips use (matrix metric =
        # its own verdict via _metric_bands), vs the per-READING mass _pool_verdict above
        # that the home needle keeps. The §1 CARD A donut reads THIS; summing it === the
        # chip counts === the filtered grid, all metric-level. None when no positioned metric.
        position_metrics = None
        if position is not None:
            _mb = _metric_bands(d_sub, band_low, band_high, margin)
            _bc = {"below": 0, "at": 0, "above": 0}
            for _v in _mb.values():
                if _v in _bc:
                    _bc[_v] += 1
            position_metrics = {"below": _bc["below"], "at": _bc["at"],
                                "above": _bc["above"], "pool": len(_mb)}
        d = {
            "name": sec, "market": strict,
            "market_eligible": d_questions >= dmin,
            "polarised_comparable": len(d_sub),
            "position": position, "position_basis": basis,
            "position_metrics": position_metrics,
            "position_evidence": ({"polarised": len(d_sub), "practice": 0}
                                  if position is not None else None),
            "competitiveness": True,
            "prevalence": _prev_summary(d_prev, uncommon_pct),
            "approach": _approach_summary(d_prev, cfg),
        }
        # reward_mix=benefits reframe (§5.2): a below-market PAY verdict is the
        # cash-light mix working as intended — annotate, never re-verdict
        if (sec == "Pay" and position and position.get("verdict") == "below"
                and _strategy_field(strategy, "reward_mix") == "benefits"):
            d["mix_note"] = "benefits"
        # per-domain market-position alignment (step-3 layer 3): the domain's verdict read
        # against ITS aim — domain_targets[sec] if overridden, else the global market_position
        # (degrade-to-global, inside _market_target). ANNOTATION only — never touches counts /
        # the gauge; this is the queryable input layer-4 suppression reads (parallel to
        # risk_framed). Governance never reaches here (non-competitive branch above → no target).
        d["target"] = _market_target(d["position"], strategy, stance_override=_dts.get(sec))
        domains.append(d)
    market = _pool_verdict(gauge_pool, band_low, band_high, margin)
    target = _market_target(market, strategy)
    if target:
        market = dict(market)
        market["target"] = target
    # Market-relative framing (differ / below / on / above) applies ONLY to
    # competitive-scope domains. A non-competitive domain (Governance) contributes 0
    # to the hero differ — NUMERATOR AND DENOMINATOR — exactly as it already
    # contributes 0 to below/on/above. The hero approach is therefore the SUM of the
    # competitive cards' approach summaries (one source of truth, so the hero and the
    # cards can never drift); a non-competitive domain's prevalence differences stay
    # real on its own tile, surfaced as practice signals, never as market differences.
    # (Governance scoping ruling, 2026-06-22 — see DECISIONS.md.)
    _comp_appr = [d["approach"] for d in domains if d.get("competitiveness") and d.get("approach")]
    hero_approach = ({"differ": sum(a["differ"] for a in _comp_appr),
                      "in_line": sum(a["in_line"] for a in _comp_appr),
                      "pool": sum(a["pool"] for a in _comp_appr)} if _comp_appr else None)
    return {
        "market": market,
        "prevalence": _prev_summary(prev_items, uncommon_pct),
        "approach": hero_approach,
        "domains": domains,
        "config": {"band_low": band_low, "band_high": band_high,
                   "domain_min": dmin, "margin": margin, "uncommon_pct": uncommon_pct,
                   "tile_min": tmin, "classified": True},
    }
