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
                        # the category is named so two overspend domains do not print
                        # the same sentence word for word (2026-08-16 panel)
                        "coverage_note": ("%s already sits above this aim, so every lever in the "
                                          "inventory would add to a package that is ahead of the stated "
                                          "position — the open question is whether the aim itself still "
                                          "reads right." % c.get("category"))})
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


def _cond_eval(cond, answers, strategy=None):
    """One evidence condition against the org's own answers — or, for ONE condition
    shape, against the strategy itself.
    Returns (state, matched_answer): state True (condition met = the problem shows),
    False (answered, condition not met), or None (needed answer missing)."""
    if "all" in cond:
        parts = [_cond_eval(c, answers, strategy) for c in cond["all"]]
        if any(p[0] is None for p in parts):
            return None, None
        met = all(p[0] for p in parts)
        return met, next((p[1] for p in parts if p[0]), None)
    if "any" in cond:
        parts = [_cond_eval(c, answers, strategy) for c in cond["any"]]
        if any(p[0] for p in parts):
            hit = next(p for p in parts if p[0])
            return True, hit[1]
        if any(p[0] is None for p in parts):
            return None, None
        return False, None
    # INTENT-VS-INTENT (2026-08-16, practitioner panel): a strategy can pull against
    # itself — an attract-led objective with pay aimed below market — and no metric
    # answer can evidence that; the evidence IS another stated dial. "strategy_stance"
    # reads the EFFECTIVE stance for a domain (its domain_targets override, else the
    # global dial), with the same trust rule as intent: an unstated dial is None,
    # never a fabricated answer. The matched value returns as the reader's word
    # ("below market"), because it prints inside a statement.
    if "strategy_stance" in cond:
        st = strategy or {}
        dom = cond["strategy_stance"]
        v = (st.get("domain_targets") or {}).get(dom) or _dial(st, "market_position")
        if v is None:
            return None, None
        return v in (cond.get("in") or []), _STANCE_WORD.get(v, v)
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
        state, matched = _cond_eval(rule.get("evidence") or {}, answers, strategy)
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



def _english_list(items):
    """a, b and c — an Oxford-free serial list, because a board paper is prose."""
    items = [str(i) for i in items if str(i).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------------- board-paper reads (2026-08-16)
# Six gaps a reward director named against the document: it never ASKS for anything,
# it carries no aggregate cost, it records no rejected option, its plan is a list not a
# schedule, it has no risk section, and it cannot show movement. Everything below is
# DERIVED from what the engine already found — no read here is a new assertion, and the
# prose around each one stays author-editable.

# The lever inventory speaks in three horizons, but a plan action's horizon is free text
# (the model may paraphrase), so actions are BUCKETED rather than string-matched.
# Anything unrecognised lands in "unscheduled" and is shown as such — an action silently
# dropped off a schedule is far worse than one the schedule admits it cannot place.
HORIZON_BUCKETS = (
    ("this cycle",  ("this cycle", "immediate", "current cycle", "this year", "now")),
    ("next cycle",  ("next cycle", "next year", "following cycle", "next review")),
    ("multi-cycle", ("multi-cycle", "multi cycle", "multiple cycles", "longer term",
                     "long term", "over time", "beyond")),
)
HORIZON_ORDER = ("this cycle", "next cycle", "multi-cycle", "unscheduled")


def horizon_bucket(text):
    t = (text or "").strip().lower()
    for name, needles in HORIZON_BUCKETS:
        if any(nd in t for nd in needles):
            return name
    return "unscheduled"


# A decision AGAINST an option is evidence too. Three states only: a longer vocabulary
# invites a status field nobody maintains.
OPTION_DECISION_STATES = {"considered": "Considered",
                          "not_now": "Not this cycle",
                          "rejected": "Rejected"}
OPTION_DECISION_MAX = 400


def option_decision_key(category, lever_id):
    """One lever can be offered against two categories and decided differently in each,
    so the category is part of the key."""
    return "%s|%s" % (category or "", lever_id or "")


def derive_risks(al, money, blocks, strat, doc, data_state, snapshot_single,
                 budget_labels=None, constraint_labels=None, domain_min=3, sector=None):
    """What could go wrong — restated from what the engine already established.

    Deliberately EXPOSURES, not predictions and never instructions: each one names a
    condition that is true of this organisation today and says what it bears on. The
    document is scrupulously non-directive everywhere else and a risk section is the
    easiest place to start giving advice by accident, so nothing here tells the reader
    to act. Where lumi cannot see the answer, the risk says so rather than guessing."""
    budget_labels = budget_labels or {}
    constraint_labels = constraint_labels or {}
    out = []
    invest = (money or {}).get("total_investment_to_p50_gbp") or 0
    budget = strat.get("budget_direction")
    gaps = [c for c in (al.get("commitments") or [])
            if c.get("status") in ("behind_intent", "contradicted")]

    # 1. AFFORDABILITY — the plan asks for money the stated budget direction does not have.
    if invest and budget in ("flat", "pressure"):
        out.append({
            "id": "affordability", "class": "Affordability",
            "title": "The priced gaps need money the stated budget direction does not carry",
            "detail": ("You described the budget as %s. Closing the gaps lumi can price to the peer "
                       "median is an indicative £%s a year on the published assumptions. The two "
                       "readings have to be reconciled before the plan is committed to — either the "
                       "figure, the pace or the budget description moves."
                       % (budget_labels.get(budget, budget),
                          "{:,}".format(int(invest)))),
        })

    # 2. EVIDENCE — a decision resting on an indicative read carries the read's uncertainty.
    thin = [b["name"] for b in (blocks or [])
            if b.get("gaps") and not (b.get("count") or {}).get("strict")]
    if thin:
        out.append({
            "id": "evidence", "class": "Evidence",
            "title": "%s %s carrying a recommendation on an indicative read"
                     % (len(thin), "area is" if len(thin) == 1 else "areas are"),
            "detail": ("%s %s fewer than %d benchmarked metrics behind %s market read, so %s position "
                       "is indicative rather than methodology-grade. Any recommendation made there "
                       "rests on the same evidence as the verdict above it."
                       % (_english_list(thin), "has" if len(thin) == 1 else "have",
                          domain_min,
                          "its" if len(thin) == 1 else "their",
                          "its" if len(thin) == 1 else "their")),
        })

    # 3. EXPOSURE — where you sit below market having said you would not.
    exposed = [b["name"] for b in (blocks or [])
               if (b.get("position") or {}).get("verdict") == "below"
               and (b.get("aim") or {}).get("stance") in ("match", "lead")]
    if exposed:
        out.append({
            "id": "exposure", "class": "Exposure",
            "title": "%s below the market on a stated aim to match or lead" % _english_list(exposed),
            "detail": ("%s below the peer group on lumi's read while the strategy aims at or above it. "
                       "That is a live gap between what candidates and employees encounter and what the "
                       "organisation says it offers, for as long as it stands."
                       % ("That area sits" if len(exposed) == 1 else "Each of these sits")),
        })

    # 4. CONCENTRATION — a plan that is really one area's plan.
    if len(gaps) >= 3:
        by_cat = {}
        for c in gaps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
        top, n = max(by_cat.items(), key=lambda kv: kv[1])
        if n / float(len(gaps)) >= 0.6:
            out.append({
                "id": "concentration", "class": "Delivery",
                "title": "%d of %d gaps sit in %s" % (n, len(gaps), top),
                "detail": ("The plan is concentrated in one area, so its delivery depends on one set of "
                           "owners, one budget line and one change window. A slip there is a slip in "
                           "most of the plan rather than part of it."),
            })

    # 5. COVERAGE — how much of your own data the whole document rests on.
    pct = round((data_state or {}).get("core_pct") or 0)
    if pct < 80:
        out.append({
            "id": "coverage", "class": "Evidence",
            "title": "The document rests on %d%% of your benchmark data" % pct,
            "detail": ("%d of %d core metrics are answered. Areas you have not answered cannot be "
                       "positioned at all, so they appear nowhere in the findings — an absence here "
                       "is an unknown, not a clean bill of health."
                       % ((data_state or {}).get("answered") or 0, (data_state or {}).get("basis_total") or 0)),
        })

    # 6. NO PRIOR PERIOD — the document cannot yet show whether things are improving.
    if snapshot_single:
        out.append({
            "id": "no_trend", "class": "Evidence",
            "title": "There is no prior period to measure movement against",
            "detail": ("This is lumi's first aggregated collection window, so every figure here is a "
                       "baseline. Whether a position is improving or slipping cannot be evidenced "
                       "until a second window closes, and no reading in this document should be taken "
                       "as a direction of travel."),
        })

    # 6b. THE WAGE FLOOR — for a sector paid at or near it, the statutory floor is the
    # binding annual driver, and a retail reward plan that never says so would not
    # survive an ExCo (2026-08-16 practitioner panel). Fires only where the sector
    # makes it live AND the pay stance or read makes it bite. An exposure, not advice:
    # lumi cannot see rate headroom, and says so.
    _floor_sectors = ("retail", "hospitality", "leisure", "consumer")
    _pay = next((b for b in (blocks or []) if b.get("name") == "Pay"), None)
    _pay_low = (strat.get("market_position") == "lag"
                or (strat.get("domain_targets") or {}).get("Pay") == "lag"
                or (_pay and (_pay.get("position") or {}).get("verdict") == "below"))
    if sector and any(k in sector.lower() for k in _floor_sectors) and _pay_low:
        out.append({
            "id": "wage_floor", "class": "Statutory",
            "title": "The statutory wage floor moves every April, and this pay position sits close to it",
            "detail": ("In this sector the National Living Wage is the binding floor under a large part "
                       "of the workforce. Each uplift compresses differentials above it and narrows the "
                       "room a below-market pay position has to exist at all. lumi cannot see your rate "
                       "headroom over the floor — how much of the annual uplift lands as unavoidable "
                       "spend is a judgement only you can make."),
        })

    # 7. THE ORGANISATION'S OWN CONSTRAINTS — stated in the wizard, never carried forward.
    cons = [constraint_labels.get(c, c)
            for c in (((doc or {}).get("constraints") or {}).get("selected") or [])]
    if cons:
        out.append({
            "id": "constraints", "class": "Stated constraint",
            "title": "Constraints you stated: %s" % _english_list(cons),
            "detail": ("These were recorded when the strategy was set and bear on anything in the plan "
                       "that needs money, negotiation or a system change. lumi cannot see how binding "
                       "they are — that judgement stays with you."),
        })
    return out
