"""Position analytics shared by every surface (overview, cards, board pack,
analyst, starter layout): one definition of percentile rank, favourability,
"biggest gaps/strengths", plain-English readouts, gap-to-£ and the gap register.
"""
import bisect
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, uj, get_meta
from library import load_questions
from aggregate import (aggregate_question_for_orgs, score_answer, score_polarity,
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
    s = "{:.1f}".format(v).rstrip("0").rstrip(".")
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
    if cut.get("dim") == "twin":
        b = (twin_blocks or {}).get("main")
        return b, "Organisations like you"
    return resolve_block(payload.get("all"), payload, cut)


def score_block_for(payload, cut, twin_blocks=None):
    sc = payload.get("scores")
    if sc is None:
        return None, ""
    if cut.get("dim") == "twin":
        return (twin_blocks or {}).get("score"), "Organisations like you"
    return resolve_block(sc.get("all"), sc, cut)


def matrix_row_block_for(row, cut, twin_blocks=None):
    if cut.get("dim") == "twin":
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
                v = coerce_number(org_answers.get((qid, row["row_id"])))
                if v is None:
                    continue
                blk, cut_label = matrix_row_block_for(row, cut, tb)
                if is_suppressed(blk):
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

def overview_summary(items):
    above = sum(1 for i in items if i["favourable"] == "good")
    below = sum(1 for i in items if i["favourable"] == "bad")
    inline = sum(1 for i in items if i["favourable"] == "mid")
    comparable = above + below + inline
    by_sp = defaultdict(lambda: {"available": 0, "above": 0, "below": 0, "inline": 0,
                                 "quartiles": [0, 0, 0, 0]})
    for i in items:
        c = by_sp[i["superpower"]]
        c["available"] += 1
        if i["favourable"] == "good":
            c["above"] += 1
        elif i["favourable"] == "bad":
            c["below"] += 1
        elif i["favourable"] == "mid":
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
        if i["favourable"] == "good":
            c["above"] += 1
        elif i["favourable"] == "bad":
            c["below"] += 1
        elif i["favourable"] == "mid":
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
    """Practice & policy maturity vs peer adoption. Adoption = the org's option
    score >= 50 on the question's own 0-100 scale (see methodology)."""
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
        if p is None or "scores" not in p:
            continue
        blk, cut_label = score_block_for(p, cut, (twin_blocks_by_q or {}).get(qid))
        raw = org_answers.get((qid, ""))
        s = score_answer(q, raw) if raw is not None else None
        in_place = (s >= 50) if s is not None else None
        adoption = None if is_suppressed(blk) else blk.get("adoption_pct")
        sector_adoption = None
        if sector_cut:
            sblk, _ = score_block_for(p, sector_cut, None)
            if not is_suppressed(sblk):
                sector_adoption = sblk.get("adoption_pct")
        if s is not None:
            sp_scores[q.superpower].append(s)
        if not is_suppressed(blk) and blk.get("p50") is not None:
            sp_peer_p50[q.superpower].append(blk["p50"])
        gap = (adoption - (100.0 if in_place else 0.0)) if (adoption is not None and in_place is not None) else None
        rows.append({
            "question_id": qid, "name": q.display_title, "superpower": q.superpower,
            "subpower": q.sub_power, "category": q.category, "tier": q.lumi_tier,
            "org_status": raw if raw is not None else "Not answered",
            "org_answered": raw is not None,
            "in_place": in_place,
            "org_score": round(s, 1) if s is not None else None,
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
    return {"rows": rows, "maturity": maturity}
