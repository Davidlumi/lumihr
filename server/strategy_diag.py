"""Strategy-execution diagnosis — where the org's DECLARED reward strategy and its
ACTUAL market position diverge.

The FINDINGS are computed deterministically here, from the same per-domain verdicts
the gauge uses plus the £ opportunity figures; claude_api.generate_strategy_diagnosis
only narrates them. That keeps the firewall intact — the model can never invent a
gap, a domain or a number, only phrase the ones the engine found. With no API key the
deterministic narrative below ships instead, so the feature works either way.
"""

_STANCE_AIM = {"lag": 0, "match": 1, "lead": 2}      # where the org aims on the below(0)/on(1)/above(2) axis
_VERDICT_IDX = {"below": 0, "at": 1, "above": 2}
_AIM_WORD = {0: "below market", 1: "on market", 2: "above market"}
_COMPETITIVE = ("Pay", "Incentives", "Benefits", "Time Off", "Wellbeing", "Recognition")

# objectives that care about closing TALENT gaps vs trimming COST overspend — used
# only to rank which findings surface first, never to invent them.
_GAP_OBJECTIVES = {"attract", "retain"}
_OVER_OBJECTIVES = {"cost"}


def _is_set(strategy, field):
    return (strategy.get("provenance") or {}).get(field) not in (None, "skipped")


def domain_aims(strategy):
    """Per-domain implied aim (0/1/2). Starts from the overall market-position stance
    and is nudged by the finer intents the org actually set:
      reward_mix=benefits → Benefits aim 'lead', Pay aim 'lag' (a deliberately cash-light
                            mix, so a below-market Pay is ON plan, not a gap);
      reward_mix=cash     → Pay aim 'lead';
      pay_for_performance strong → Incentives aim 'lead'; egal → Incentives aim 'lag'.
    """
    base = _STANCE_AIM.get(strategy.get("market_position"), 1) if _is_set(strategy, "market_position") else 1
    aims = {d: base for d in _COMPETITIVE}
    if _is_set(strategy, "reward_mix"):
        mix = strategy.get("reward_mix")
        if mix == "benefits":
            aims["Benefits"], aims["Pay"] = 2, 0
        elif mix == "cash":
            aims["Pay"] = 2
    if _is_set(strategy, "pay_for_performance"):
        pfp = strategy.get("pay_for_performance")
        if pfp == "strong":
            aims["Incentives"] = 2
        elif pfp == "egal":
            aims["Incentives"] = 0
    # A′ (2026-06-25): an EXPLICIT per-domain override BEATS the inferred aim — the narrative now
    # honours domain_targets[dom] (the SAME field L3 alignment / L4 suppression / tile+hero recolour
    # respect), so it converges with _market_target where an override is set. Applied AFTER the
    # reward_mix/P4P nudges, so override > nudge > base. Unset domains keep the heuristic inference —
    # the narrative's richer fallback is deliberately NOT flattened to the global stance.
    for dom, stance in (strategy.get("domain_targets") or {}).items():
        if dom in aims and stance in _STANCE_AIM:
            aims[dom] = _STANCE_AIM[stance]
    return aims


def _reason_for(domain, strategy):
    """One short phrase naming the strategy choice that sets this domain's aim."""
    # A′ (2026-06-25): an explicit per-domain override OWNS the aim — so it owns the reason too. Name
    # the target, never the inferred nudge, or an override that CONTRADICTS a nudge (e.g. Benefits:lag
    # + reward_mix=benefits) would narrate a self-contradicting reason on the very domain this fixes.
    # Mirrors the domain_aims override precedence (override > inference).
    dt = (strategy.get("domain_targets") or {}).get(domain)
    if dt in _STANCE_AIM:
        return "your %s-the-market target for %s" % (dt, domain)
    if domain == "Benefits" and _is_set(strategy, "reward_mix") and strategy.get("reward_mix") == "benefits":
        return "your benefits-led reward mix"
    if domain == "Pay" and _is_set(strategy, "reward_mix") and strategy.get("reward_mix") == "cash":
        return "your cash-led reward mix"
    if domain == "Incentives" and _is_set(strategy, "pay_for_performance") and strategy.get("pay_for_performance") == "strong":
        return "your strong pay-for-performance stance"
    stance = strategy.get("market_position")
    return "your %s-the-market stance" % stance if _is_set(strategy, "market_position") and stance else "your stated strategy"


def compute_findings(strategy, domains, opp_by_domain):
    """domains: [{name, verdict in below/at/above, below, at, above, pool, competitive}].
    opp_by_domain: {domain: {gbp, direction in investment/savings, top_label, top_gbp}}.
    Returns a ranked list of findings (gaps + overspends), each grounded with figures."""
    aims = domain_aims(strategy)
    objective = strategy.get("primary_objective") if _is_set(strategy, "primary_objective") else None
    findings = []
    for d in domains:
        name = d.get("name")
        if name not in _COMPETITIVE or not d.get("competitive", True):
            continue
        verdict = d.get("verdict")
        if verdict not in _VERDICT_IDX:
            continue
        aim = aims.get(name, 1)
        actual = _VERDICT_IDX[verdict]
        delta = actual - aim
        if delta == 0:
            continue                                    # on plan — not a finding to action
        kind = "gap" if delta < 0 else "over"
        opp = opp_by_domain.get(name) or {}
        money = opp.get("gbp") or 0
        pool = max(1, d.get("pool") or 1)
        n_below, n_at, n_above = (d.get("below") or 0), (d.get("at") or 0), (d.get("above") or 0)
        # magnitude: distance from aim, how decisively the domain sits off (count share), £ weight
        off = (n_below if kind == "gap" else n_above)
        score = abs(delta) * 10 + (off / pool) * 6 + min(money / 10000.0, 8)
        # objective lifts the kind it cares about (cost→overspend, attract/retain→gaps)
        if (kind == "gap" and objective in _GAP_OBJECTIVES) or (kind == "over" and objective in _OVER_OBJECTIVES):
            score *= 1.6
        # evidence states the ACTUAL distribution (verdict-accurate, not the off-count)
        if actual == 0:
            ev = "%d of %d %s metrics sit below market" % (n_below, pool, name)
        elif actual == 2:
            ev = "%d of %d %s metrics sit above market" % (n_above, pool, name)
        else:
            ev = "%s sits on market overall (%d of %d metrics), with %d above and %d below" % (name, n_at, pool, n_above, n_below)
        if money and kind == "gap" and opp.get("direction") == "investment":
            ev += "; about £%s would move the largest gap (%s) to the peer median" % ("{:,}".format(int(opp["top_gbp"] or money)), opp.get("top_label", "the biggest item"))
        elif money and kind == "over" and opp.get("direction") == "savings":
            ev += "; about £%s of headroom to the peer median sits here" % "{:,}".format(int(money))
        findings.append({
            "area": name,
            "intent": _AIM_WORD[aim],
            "actual": _AIM_WORD[actual],
            "kind": kind,
            "reason": _reason_for(name, strategy),
            "money_gbp": int(money) if money else None,
            "evidence": ev,
            "_score": round(score, 2),
        })
    findings.sort(key=lambda f: -f["_score"])
    for f in findings:
        f.pop("_score", None)
    return findings[:4]


def build_diagnosis_payload(strategy, findings, market_target, objective_label, on_plan_domains, illustrative):
    """The grounded input the model narrates (and the deterministic floor renders)."""
    align = (market_target or {}).get("alignment")
    stance = strategy.get("market_position") if _is_set(strategy, "market_position") else None
    return {
        "objective": objective_label,
        "stance": stance,
        "overall_alignment": align,                    # behind | on_target | ahead | None
        "findings": findings,
        "on_plan_areas": on_plan_domains,
        "illustrative_sample_data": bool(illustrative),
    }


def deterministic_diagnosis(payload):
    """Rule-based narrative built ONLY from the computed findings — the floor when the
    model is unavailable or its output fails the gate. Two parts: a one-line overall
    read and a list of {headline, detail, option} mirroring the model's shape."""
    findings = payload.get("findings") or []
    align = payload.get("overall_alignment")
    stance = payload.get("stance")
    obj = payload.get("objective")
    if not findings:
        summary = "Your position broadly matches the strategy you set" + (
            " — you're tracking your reward plan across the areas we can compare." if not stance else
            ", with no material area pulling against your %s stance." % stance)
        return {"summary": summary, "findings": [{
            "headline": "On plan across the board",
            "detail": "None of your competitive domains sit far enough from your stated aim to flag — " + (
                "keep watching them cycle to cycle." if not payload.get("on_plan_areas") else
                "areas like %s are sitting where you intend." % ", ".join(payload["on_plan_areas"][:3])),
            "option": "Revisit if your strategy or the market moves. A starting point, not advice."}]}
    gaps = sum(1 for f in findings if f["kind"] == "gap")
    overs = len(findings) - gaps
    bits = []
    if gaps:
        bits.append("%d area%s falling short of your aim" % (gaps, "" if gaps == 1 else "s"))
    if overs:
        bits.append("%d sitting more generously than you intend" % overs)
    summary = "Against the strategy you set" + (" (objective: %s)" % obj if obj else "") + ", " + " and ".join(bits) + "."
    out = []
    for f in findings:
        if f["kind"] == "gap":
            head = "%s is %s — short of %s" % (f["area"], f["actual"], f["reason"])
            opt = ("Organisations in this position often size up what closing part of the gap would take and cost, "
                   "against budget and the roles it affects. A starting point, not advice.")
        else:
            head = "%s is %s — further than %s intends" % (f["area"], f["actual"], f["reason"])
            opt = ("Organisations here often check the spend is deliberate and well-known to staff, or redirect some "
                   "toward areas that are short. Your own priorities come first — a starting point, not advice.")
        out.append({"headline": head, "detail": f["evidence"] + ".", "option": opt})
    return {"summary": summary, "findings": out}


DIAGNOSIS_PARTS = ("summary", "findings")
