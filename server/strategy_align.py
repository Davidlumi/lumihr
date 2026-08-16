"""Strategy alignment — does what the org DOES deliver what it SAID? (2026-08-14,
brief v2 §5/§6, rulings R5/R7.)

The third read beside Position (engine) and Intent (org_strategy): every commitment
resolves to exactly ONE of four statuses, rolled up as COUNTS per category — never a
score, index or grade (R5). Deterministic; the model never authors a status.

  evidenced      practice matches intent
  behind_intent  practice short of the stated target, direction known
  contradicted   practice runs against the stated intent
  not_evidenced  enabling evidence unanswered / suppressed / not visible

Commitment set per category (the denominator the counts must sum to, brief §12):
  - a POSITION commitment for each position category with a stated stance
    (domain_targets override or the global dial) — status from the engine's own
    target read (`_market_target` alignment), never recomputed here;
  - one commitment per coherence rule whose intent HOLDS (a stated intent is a
    commitment to test). Rules live in data/strategy_coherence_rules.json —
    DAVID OWNS THE CONTENT (R7); this module is only the mechanism.

Trust rules: intents are read like `_strategy_field` — provenance 'set' only
('live' for transparency: the reconfirm contract means a pre-wiring value is not a
stated intent). Evidence is the org's OWN answer — no peer figure, so no n/
suppression exposure. A missing answer NEVER fabricates: it reads not_evidenced.
Statements are descriptive, both sides, no directive verbs.
"""
import json
import os

_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "data", "strategy_coherence_rules.json")
_CACHE = {"mtime": None, "rules": None}
_LEVERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "data", "reward_levers.json")
_LCACHE = {"mtime": None, "levers": None}

# R6 — the ruled framing sentence, verbatim, on every Options block.
OPTIONS_FRAMING = ("Here is the gap. Here is what the market does about it. "
                   "Here is what it would cost. The decision is yours.")

STATUSES = ("evidenced", "behind_intent", "contradicted", "not_evidenced")
_STANCE_WORD = {"lag": "below market", "match": "on market", "lead": "above market"}
_VERDICT_WORD = {"below": "below market", "at": "on market", "above": "above market"}


def load_rules(path=None):
    p = path or os.environ.get("LUMI_STRATEGY_RULES") or _RULES_PATH
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return []
    if _CACHE["mtime"] != mt or _CACHE["rules"] is None:
        with open(p) as f:
            _CACHE["rules"] = (json.load(f).get("rules") or [])
        _CACHE["mtime"] = mt
    return _CACHE["rules"]


def load_levers(path=None):
    """The David-owned lever inventory (R8). File order preserved — NEVER re-sorted,
    ranked or filtered by 'fit' (an ordered list is an implied recommendation)."""
    p = path or os.environ.get("LUMI_REWARD_LEVERS") or _LEVERS_PATH
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return []
    if _LCACHE["mtime"] != mt or _LCACHE["levers"] is None:
        with open(p) as f:
            _LCACHE["levers"] = (json.load(f).get("levers") or [])
        _LCACHE["mtime"] = mt
    return _LCACHE["levers"]


# which register a commitment kind needs its levers to move (brief §7):
# behind on POSITION/PROVISION -> Substance; a PRACTICE/coherence contradiction -> Approach.
_KIND_REGISTER = {"position": "Substance", "provision": "Substance",
                  "practice": "Approach", "coherence": "Approach"}


def _registers_for(c):
    """Which lever registers can answer this commitment.

    A coherence rule covers two different failures and they are NOT closed the same way
    (2026-08-16 consultancy review). CONTRADICTED means practice runs against the stated
    intent — an Approach problem. BEHIND_INTENT on a coherence rule almost always means a
    provision is ABSENT ("the package is stated to lead on mental wellbeing, and no
    Employee Assistance Programme shows in your responses"), and an absence is closed by
    ADDING the thing. Mapping both to Approach meant the document stated a gap and then
    offered options that could not close it — the reviewer's exact complaint.
    """
    kind = c.get("kind")
    if kind == "coherence" and c.get("status") == "behind_intent":
        return ["Substance", "Approach"]          # add the missing provision, or change the approach
    return [_KIND_REGISTER.get(kind, "Substance")]


def options_for(commitments, levers=None, visible_qids=None):
    """Options blocks for every commitment that is behind_intent or contradicted:
    the levers of that category whose register_effect matches what the gap needs,
    in FILE ORDER, each with its mandatory trade_off; plus the R6 framing string.
    Categories outside the v1 lever tranche say so plainly (no silent caps)."""
    levers = load_levers() if levers is None else levers
    covered = {l.get("category") for l in levers}
    out = []
    for c in commitments or []:
        if c.get("status") not in ("behind_intent", "contradicted"):
            continue
        # An OVERSPEND gap (the live read sits past a deliberately lower aim) is not
        # closed by adding substance — every lever in the inventory adds package, so
        # offering them here would recommend spending more to fix spending more. The
        # honest read is that the stated position, not the practice, is the open question.
        if c.get("direction") == "past":
            out.append({"commitment_id": c.get("id"), "category": c.get("category"),
                        "status": c.get("status"), "statement": c.get("statement"),
                        "framing": OPTIONS_FRAMING, "levers": [],
                        "coverage_note": ("Your practice already sits above this aim, so the levers here "
                                          "would add to a package that is ahead of the stated position — "
                                          "the open question is whether the aim itself still reads right.")})
            continue
        needs = _registers_for(c)
        need = needs[0]                            # the primary register, for the coverage note
        picks = []
        for l in levers:
            if l.get("category") != c.get("category") or l.get("register_effect") not in needs:
                continue
            l = dict(l)
            # entitlement (§2.5): a prevalence link the org can't see is dropped from the
            # lever (the lever itself stays — its category is visible to every org today).
            if visible_qids is not None and l.get("prevalence_metric_id") not in (visible_qids or set()):
                l.pop("prevalence_metric_id", None)
            picks.append(l)
        block = {"commitment_id": c.get("id"), "category": c.get("category"),
                 "status": c.get("status"), "statement": c.get("statement"),
                 "framing": OPTIONS_FRAMING,
                 "levers": [{k: l.get(k) for k in ("lever_id", "name", "what_it_is", "typical_shape",
                                                   "cost_character", "speed", "reversibility",
                                                   "prevalence_metric_id", "register_effect", "trade_off")}
                            for l in picks]}
        if c.get("category") not in covered:
            block["coverage_note"] = ("The lever inventory covers Pay, Benefits & Lifestyle and "
                                      "Time Off & Family at v1 — this area's levers are a later tranche.")
        elif not picks:
            # covered category, but nothing in it moves the register this gap needs —
            # say so rather than render an empty block (no silent caps).
            block["coverage_note"] = ("This gap is one of approach rather than what's on offer, and the "
                                      "inventory holds no %s lever for %s yet."
                                      % (need.lower(), c.get("category"))) if need == "Approach" else (
                                     "The inventory holds no %s lever for %s yet."
                                     % (need.lower(), c.get("category")))
        out.append(block)
    return out


def _dial(strategy, field):
    """A dial value ONLY when genuinely stated (mirrors _strategy_field, plus the
    transparency reconfirm contract: 'set'-but-not-'live' transparency is not a
    stated intent)."""
    prov = (strategy.get("provenance") or {}).get(field)
    if prov in (None, "skipped"):
        return None
    if field == "transparency" and prov != "live":
        return None
    return strategy.get(field) or None


def _intent_holds(rule, strategy, document):
    it = rule.get("intent") or {}
    f = it.get("field") or ""
    if f == "document.segments":
        return False        # scarce-role segments retired 2026-08-15 (no pay data to evidence them)
    if it.get("contains") is not None:
        vals = strategy.get(f) or []
        prov = (strategy.get("provenance") or {}).get(f)
        return prov not in (None, "skipped") and it["contains"] in vals
    v = _dial(strategy, f)
    return v is not None and v in (it.get("in") or [])


def _cond_eval(cond, answers):
    """One evidence condition against the org's own answers.
    Returns (state, matched_answer): state True (condition met = the problem shows),
    False (answered, condition not met), or None (needed answer missing)."""
    if "all" in cond:
        parts = [_cond_eval(c, answers) for c in cond["all"]]
        if any(p[0] is None for p in parts):
            return None, None
        met = all(p[0] for p in parts)
        return met, next((p[1] for p in parts if p[0]), None)
    if "any" in cond:
        parts = [_cond_eval(c, answers) for c in cond["any"]]
        if any(p[0] for p in parts):
            hit = next(p for p in parts if p[0])
            return True, hit[1]
        if any(p[0] is None for p in parts):
            return None, None
        return False, None
    qid = cond.get("metric")
    a = (answers.get(qid) or "").strip()
    if not a:
        return None, None
    if "answer_in" in cond:
        return a in cond["answer_in"], a
    if "answer_not_in" in cond:
        return a not in cond["answer_not_in"], a
    return False, a


def _rule_metrics(cond):
    if "all" in cond or "any" in cond:
        out = []
        for c in cond.get("all") or cond.get("any") or []:
            out += _rule_metrics(c)
        return out
    return [cond.get("metric")] if cond.get("metric") else []


def evaluate(rules, strategy, document, answers, domains, position_exclude,
             visible_qids=None, cut_label="your peer group"):
    """The full alignment read. domains: hero domains ({name, competitive/
    competitiveness, target:{stance, alignment}}). Returns commitments + counts.
    Pure — no DB, no request; the caller assembles the context."""
    strategy = strategy or {}
    document = document or {}
    answers = answers or {}
    commitments = []

    # ---- 1. position commitments (engine-evidenced — never recomputed here) ----
    dt = strategy.get("domain_targets") or {}
    global_stance = _dial(strategy, "market_position")
    for d in domains or []:
        name = d.get("name")
        if not d.get("competitive", d.get("competitiveness", True)) or name in (position_exclude or ()):
            continue
        stance = dt.get(name) or global_stance
        if not stance:
            continue                                   # nothing stated → no commitment
        tgt = d.get("target") or {}
        align = tgt.get("alignment")
        if align == "on_target":
            status, note, direction = "evidenced", "the live read matches it", None
        elif align == "behind":
            status, note, direction = "behind_intent", "the live read sits short of it", "short"
        elif align == "ahead":
            status, note, direction = ("behind_intent",
                                       "the live read sits past it — spend beyond the stated position", "past")
        else:
            status, note, direction = "not_evidenced", "no market read is available yet on " + cut_label, None
        commitments.append({
            "id": "position:" + name, "category": name, "kind": "position",
            "intent_label": "aim " + (_STANCE_WORD.get(stance, stance)) + (" (set for this area)" if name in dt else ""),
            "status": status, "direction": direction,
            "statement": "You aim %s on %s; %s." % (_STANCE_WORD.get(stance, stance), name, note),
            "evidence": {"source": "category market read", "cut": cut_label},
        })

    # (the Wellbeing "what we offer" and Governance "how we operate" commitments were
    # removed 2026-08-15 — every one of those provisions is already a metric answer, so
    # the coherence rules below read them directly rather than asking twice.)

    # ---- 3. coherence rules (one commitment per HELD intent) ----
    for rule in rules or []:
        if not _intent_holds(rule, strategy, document):
            continue
        state, matched = _cond_eval(rule.get("evidence") or {}, answers)
        if state is None:
            status = "not_evidenced"
            statement = "Stated: %s — the evidence for this is unanswered, so it can't yet be assessed." % rule.get("commitment")
        elif state:
            status = rule.get("status") or "contradicted"
            statement = (rule.get("statement") or "").replace("{answer}", matched or "") \
                                                     .replace("{answer_detail}", matched or "your response")
        else:
            status = "evidenced"
            statement = "Stated: %s — your responses are consistent with it." % rule.get("commitment")
        commitments.append({
            "id": "rule:" + rule["rule_id"], "category": rule.get("category"), "kind": "coherence",
            "intent_label": rule.get("commitment"), "status": status, "statement": statement,
            "evidence": {"source": "your own responses", "metric_ids": _rule_metrics(rule.get("evidence") or {}),
                         "answer": matched},
            "rationale": rule.get("rationale"),
        })

    # ---- counts per category — the R5 contract: counts, never a score ----
    counts = {}
    for c in commitments:
        cat = counts.setdefault(c["category"], {s: 0 for s in STATUSES})
        cat[c["status"]] += 1
    return {"commitments": commitments, "counts": counts}
