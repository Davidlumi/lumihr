"""Phase 1b — aggregation engine.

Computes all benchmark aggregates into benchmark_snapshots. Re-runnable
whenever new submissions land (also importable; Peer Twin cuts call the same
functions, so suppression is enforced in one code path).

Rules implemented here (and only here):
  * numeric / matrix-numeric -> n, min, P10..P90 (linear interpolation), max, mean
  * single_select / yes_no   -> per-option count + % in options.order
  * multi_select             -> % of answering orgs selecting each option
  * suppression              -> any aggregate with n < 5 emits {suppressed, n}
  * scored questions         -> peer score distribution + adoption rate
                                (adoption = option score >= 50 on the question's
                                own 0-100 scale; see methodology)

Run:  python3 aggregate.py [--snapshot 1]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_schema, j, set_meta  # noqa: E402
from library import load_questions, slugify  # noqa: E402

SUPPRESSION_FLOOR = 5

# £-modelling assumptions (Phase 3.2) — emitted alongside aggregates, always
# labelled as assumptions and overridable per org in the UI.
DEFAULT_ASSUMPTIONS = {
    "fte_band_midpoints": {
        "50-249": 150, "250-999": 625, "1,000-4,999": 3000,
        "5,000-9,999": 7500, "10,000+": 15000,
    },
    "median_salary_gbp": 36000,
    "cost_per_leaver_pct_salary": 35,   # % of salary per leaver (recruit + ramp), indicative
    "working_days_per_year": 260,
    "agency_premium_pct": 30,           # agency day-rate premium over employed cost
}


# ------------------------------------------------------------- primitives ---

def percentile(sorted_vals, p):
    """Linear-interpolation percentile (numpy 'linear'), p in 0..100."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    k = (n - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


_num_re = re.compile(r"^-?\d+(\.\d+)?$")


def coerce_number(text):
    """Coerce an answer to float; returns None for non-numeric."""
    if text is None:
        return None
    t = str(text).strip().replace(",", "").replace("£", "").replace("%", "").strip()
    if not _num_re.match(t):
        return None
    return float(t)


def suppressed(n):
    return {"suppressed": True, "n": n}


def numeric_block(values, excluded=0):
    """Aggregate a list of floats with suppression."""
    n = len(values)
    if n < SUPPRESSION_FLOOR:
        b = suppressed(n)
        if excluded:
            b["excluded_non_numeric"] = excluded
        return b
    vs = sorted(values)
    # round display percentiles to 2dp — strips float-interpolation artefacts
    # (e.g. 60.400000000000034 -> 60.4); the raw values stay in _values for scoring
    r = lambda p: round(percentile(vs, p), 2)
    return {
        "n": n, "min": round(vs[0], 2), "max": round(vs[-1], 2),
        "p10": r(10), "p25": r(25),
        "p50": r(50), "p75": r(75),
        "p90": r(90), "mean": round(sum(vs) / n, 2),
        "excluded_non_numeric": excluded,
        "_values": vs,   # server-side only; stripped by the API layer
    }


def _norm_label(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# Matrix row values come in four formats (integrity fix, 2026-06-11):
# plain numeric ("50"), suffixed numeric ("1.5x", "98%", "12 weeks" when no
# open-ended band exists), Yes/No, and ordered bands incl. open-ended ("More
# than 16 weeks"). A value the numeric parser can't read must NEVER silently
# vanish into n=0 — rows aggregate numerically only when the WHOLE format is
# numeric; otherwise they aggregate as a per-row categorical distribution.
MATRIX_VAL_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*(?:x|×|%|weeks?|wks?)?$", re.I)


def matrix_value(v):
    if v is None:
        return None
    # strip thousands separators + currency the same way coerce_number does, so a
    # currency/number matrix cell entered as "£12,500" parses instead of dropping
    # out of the distribution and the org's own rank. NOT '%' — the regex below
    # intentionally consumes a trailing %/x/weeks suffix.
    s = str(v).strip().replace(",", "").replace("£", "")
    m = MATRIX_VAL_RE.match(s)
    return float(m.group(1)) if m else None


def matrix_select_block(option_order, raw_answers):
    """Categorical distribution for one matrix row (Yes/No, ordered bands).
    Ordered by the column's defined option list; unexpected labels are KEPT
    (appended, flagged) — never dropped."""
    counts = defaultdict(int)
    for a in raw_answers:
        if a is not None and str(a).strip() != "":
            counts[str(a).strip()] += 1
    n = sum(counts.values())
    if n < SUPPRESSION_FLOOR:
        return suppressed(n)
    order = [o for o in (option_order or []) if o in counts] + \
            [l for l in counts if l not in (option_order or [])]
    opts = [{"label": l, "count": counts[l], "pct": round(100.0 * counts[l] / n, 1)} for l in order]
    modal = max(opts, key=lambda o: o["count"])
    unexpected = [l for l in counts if option_order and l not in option_order]
    blk = {"n": n, "kind": "select", "options": opts,
           "modal_label": modal["label"], "modal_pct": modal["pct"]}
    if unexpected:
        blk["unexpected_labels"] = unexpected
        print("[aggregate] WARN matrix row has labels outside its schema: %r" % unexpected[:3])
    return blk


def select_block(q, raw_answers):
    """raw_answers: list of option-label strings (one per org)."""
    by_label = {_norm_label(o["label"]): o for o in (q.options or [])}
    na_ex = _ab_na_labels(q.id)          # r3sw9: declared answerer_only exclusions
    excluded_na = 0
    counts = defaultdict(int)
    unmatched = 0
    for a in raw_answers:
        if na_ex and _norm_label(a) in na_ex:
            excluded_na += 1
            continue
        o = by_label.get(_norm_label(a))
        if o is None:
            unmatched += 1
        else:
            counts[o["code"]] += 1
    n = sum(counts.values())
    if n < SUPPRESSION_FLOOR:
        b = suppressed(n)
        b["unmatched"] = unmatched
        if na_ex is not None:
            b["excluded_na"] = excluded_na
        return b
    opts = []
    for o in sorted(q.options or [], key=lambda o: o.get("order", 0)):
        if na_ex and _norm_label(o["label"]) in na_ex:
            continue                     # a declared N/A option never renders, even at 0
        c = counts.get(o["code"], 0)
        opts.append({"code": o["code"], "label": o["label"], "is_na": bool(o.get("is_na")),
                     "count": c, "pct": round(100.0 * c / n, 1)})
    b = {"n": n, "options": opts, "unmatched": unmatched}
    if na_ex is not None:
        b["excluded_na"] = excluded_na
    return b


def multi_block(q, raw_answers):
    """raw_answers: list of semicolon-delimited strings (one per org).
    Denominator = orgs that contributed at least one RECOGNIZED selection — a
    blank or all-unmatched row adds nothing to counts, so it must not deflate
    every option's pct. Mirrors select_block's matched-only convention and is
    None-safe (the answers.value column is nullable)."""
    by_label = {_norm_label(o["label"]): o for o in (q.options or [])}
    na_ex = _ab_na_labels(q.id)          # r3sw9: declared answerer_only exclusions
    excluded_na = 0
    counts = defaultdict(int)
    unmatched_tokens = 0
    n = 0
    for a in raw_answers:
        seen = set()
        had_na = False
        for tok in (a or "").split(";"):
            tok = tok.strip()
            if not tok:
                continue
            if na_ex and _norm_label(tok) in na_ex:
                had_na = True            # dropped token: doesn't count, doesn't keep the org in n
                continue
            o = by_label.get(_norm_label(tok))
            if o is None:
                unmatched_tokens += 1
            elif o["code"] not in seen:
                seen.add(o["code"])
                counts[o["code"]] += 1
        if seen:
            n += 1                       # this org contributed a recognized selection
        elif had_na:
            excluded_na += 1             # org held ONLY declared-N/A tokens: leaves the base
    if n < SUPPRESSION_FLOOR:
        b = suppressed(n)
        b["unmatched_tokens"] = unmatched_tokens
        if na_ex is not None:
            b["excluded_na"] = excluded_na
        return b
    opts = []
    for o in sorted(q.options or [], key=lambda o: o.get("order", 0)):
        if na_ex and _norm_label(o["label"]) in na_ex:
            continue                     # a declared N/A option never renders, even at 0
        c = counts.get(o["code"], 0)
        opts.append({"code": o["code"], "label": o["label"], "is_na": bool(o.get("is_na")),
                     "count": c, "pct": round(100.0 * c / n, 1)})
    b = {"n": n, "options": opts, "unmatched_tokens": unmatched_tokens}
    if na_ex is not None:
        b["excluded_na"] = excluded_na
    return b


# ----------------------------------------------------------------- scoring ---
# The library's option_scores are option-ORDER ranks scaled 0-100 (95% of
# scored selects match the rank pattern exactly), not quality scores: for most
# practice questions the BEST answer is listed first and so scores 0. Every
# consumer therefore works in direction-corrected "maturity points" (always
# higher = better) via score_direction():
#   -1  inverted: first option best (Yes/Always/Within last 12 months...)
#   +1  ascending: last option best (Not at all -> Embedded; banded % where
#       the question's polarity says higher is better)
#    0  unknown: no safe reading — excluded from in-place/favourability calls.

_AFF = re.compile(
    r"^(yes\b|always|fully|embedded|within last|within 2|formal\b|provided and 75|routinely|"
    r"consistently|all\b|strong\b|very (clear|fair|effective|confident|broad|well)|structured|"
    r"monthly or more|ongoing|continuous|almost always|regularly|comprehensive|identified and|"
    r"enhanced|both buy and sell|no waiting period)", re.I)
_NEG = re.compile(
    r"^(no\b|none\b|never|not\b|don'?t|no formal|statutory( sick pay)? only|no specific|"
    r"not provided|not reviewed|not offered|no regular|rarely|very (unclear|unfair|limited)|"
    r"unstructured|ad hoc|mostly unstructured)", re.I)
_NUMBAND = re.compile(r"^(<|under|less than|up to|within)?\s*[\d£%]", re.I)

_direction_cache = {}

_mp_dir_cache = {"mtime": None, "dir": {}}


def _mp_direction(qid):
    """Per-metric direction from data/market_position_config.json (David-owned,
    hot-reloaded). Used ONLY by the route-(b) score-direction fallback below. A
    standalone reader (not positions.market_position_config) to avoid the
    aggregate<->positions import cycle."""
    path = os.environ.get("LUMI_MP_CONFIG") \
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                        "market_position_config.json")   # r3sw8: staged-copy override (r3sw7 doctrine)
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    if _mp_dir_cache["mtime"] != mt:
        try:
            with open(path) as f:
                cfg = json.load(f)
            _mp_dir_cache["dir"] = {k: (v or {}).get("direction")
                                    for k, v in (cfg.get("metrics") or {}).items()}
            _mp_dir_cache["mtime"] = mt
        except (ValueError, OSError):
            pass
    return _mp_dir_cache["dir"].get(qid)


_ab_cache = {"mtime": None, "data": {}}


def _ab_na_labels(qid):
    """r3sw9 N/A-not-on-graph: declared answerer_only N/A labels for a metric — those
    answers leave the block entirely at aggregation (graph AND n render over the
    applicable base). Standalone reader like _mp_direction (no positions import);
    LUMI_AB_CONFIG path override (r3sw7 doctrine). A malformed config RAISES —
    silently disabling exclusions is the failure class the house bans."""
    path = os.environ.get("LUMI_AB_CONFIG") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "applicable_bases.json")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    if _ab_cache["mtime"] != mt:
        with open(path, encoding="utf-8") as f:
            _ab_cache["data"] = json.load(f).get("metrics") or {}
        _ab_cache["mtime"] = mt
    e = _ab_cache["data"].get(qid)
    if not e or e.get("mode") != "answerer_only":
        return None
    return {_norm_label(l) for l in (e.get("na_options") or [])}


def score_direction(q):
    """+1 raw scores already run worst->best; -1 inverted (best first); 0 unknown."""
    if q.id in _direction_cache:
        return _direction_cache[q.id]
    d = _score_direction(q)
    _direction_cache[q.id] = d
    return d


def _score_direction(q):
    cfg = q.scoring_config or {}
    if q.type == "multi_select":
        return 1  # count-based: more selected = more in place
    sc = cfg.get("option_scores") or {}
    na = set(cfg.get("na_codes") or [])
    opts = [o for o in sorted(q.options or [], key=lambda o: o.get("order", 0))
            if o["code"] in sc and o["code"] not in na]
    if len(opts) < 2:
        return 0
    first, last = opts[0]["label"], opts[-1]["label"]
    if _AFF.search(first) or _NEG.search(last):
        return -1
    if _NEG.search(first) or _AFF.search(last):
        return 1
    if _NUMBAND.search(first) and _NUMBAND.search(last):
        # ascending numeric bands: the question's own polarity gives direction
        if q.polarity == "higher_is_better":
            return 1
        if q.polarity == "lower_is_better":
            return -1
        # neutral band: no DB-polarity signal — fall through to route (b) below
    elif cfg.get("polarity") == "lower_is_better":
        return -1
    # ---- route (b) (2026-06-18): config-direction trusts an ASCENDING map ----
    # The label heuristic above couldn't read a direction (we'd return 0). If the
    # market-position config marks this metric higher_is_better AND it carries an
    # explicit graded option_scores map, trust the map — but ONLY if it is monotone
    # ASCENDING in option order (worst->best). A non-ascending map is NEVER trusted
    # (stays 0 -> prevalence): safe for any future metric, not just today's set.
    if _mp_direction(q.id) == "higher_is_better":
        seq = [float(sc[o["code"]]) for o in opts]
        if len(set(seq)) >= 2 and all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1)):
            return 1
    return 0


def score_polarity(q):
    """Polarity of the corrected points scale for favourability judgements."""
    if (q.scoring_config or {}).get("polarity") == "neutral":
        return "neutral"
    return "higher_is_better" if score_direction(q) != 0 else "neutral"


def score_answer(q, value):
    """One org's answer as direction-corrected maturity points (0-100, higher
    = more in place / more mature). Returns None when unscorable, NA, or the
    direction is unknown for select questions."""
    cfg = q.scoring_config or {}
    method = cfg.get("scoring_method")
    option_scores = cfg.get("option_scores") or {}
    na_codes = set(cfg.get("na_codes") or [])
    by_label = {_norm_label(o["label"]): o["code"] for o in (q.options or [])}

    if method == "option_scores" and q.type in ("single_select", "yes_no"):
        code = by_label.get(_norm_label(value))
        if code is None or code in na_codes:
            return None
        s = option_scores.get(code)
        if s is None:
            return None
        d = score_direction(q)
        if d == 0:
            return None
        return 100.0 - float(s) if d == -1 else float(s)

    if method == "multi_select_count" and q.type == "multi_select":
        scoreable = [c for c in option_scores if c not in na_codes]
        if not scoreable:
            return None
        sel = set()
        for tok in value.split(";"):
            code = by_label.get(_norm_label(tok.strip()))
            if code:
                sel.add(code)
        got = sum(float(option_scores.get(c, 0)) for c in sel if c in scoreable)
        mx = sum(float(option_scores[c]) for c in scoreable)
        return 100.0 * got / mx if mx > 0 else None
    return None


# ------------------------------------------------- in-place status (presence)
# THE single status-resolution function: is this practice/policy IN PLACE?
# Presence is not quality: any real, substantive answer ("Quarterly",
# "No - non-pensionable", "21-24 days") means the practice EXISTS. Only
# explicit-absence options mean it doesn't; is_na options and blanks are
# unknown/not assessable. Used by the gap register, adoption rates, maturity
# scores and the board pack appendix — one function, one source of truth.

_ABS_EXACT = re.compile(r"^(no|none|never|nothing|0|0%)$", re.I)
_ABS_NOT = re.compile(r"^not\b", re.I)                      # "Not used", "Not monitored", ...
_ABS_WORD = re.compile(r"^(none\b|never\b|nothing\b|mostly unstructured|statutory( sick pay| pay)? only\b|statutory minimum only)", re.I)
_NA_LABEL = re.compile(r"^(not applicable|don'?t know|prefer not|unsure\b)", re.I)
# "No <property>" answers that describe HOW an existing practice works rather
# than denying it exists — the small reviewable whitelist
_NO_PROPERTY = re.compile(r"^no (change|difference|cap\b|limit\b|maximum\b|preference|impact)", re.I)
_NO_QUALIFIER = re.compile(r"^no\s*[\(\u2013\u2014,-]\s*(.*)$", re.I)
_PARTIAL_RE = re.compile(
    r"^(partial(ly)?|partly|in (development|progress)|in some\b|some (areas|roles|parts|teams|cases|groups|sites)\b|"
    r"somewhat\b|informal(ly)?\b|ad[ -]?hoc\b|sometimes\b|occasionally\b|mixed$|under (review|development)|"
    r"planned\b|limited\b|emerging\b|developing\b|basic\b|"
    r"yes\s*[\u2013\u2014-]\s*(some|informal|limited|pilot|in some|but)|yes[, ]+(some|partly|partially))", re.I)


def is_absence_label(label):
    """Does this option label state the asked-about practice is ABSENT?
    Generic "No ..."/"Not ..." statements are absence; "No - <property>"
    qualifiers and the whitelist ("No change", "No cap") are real answers
    about an existing practice."""
    l = re.sub(r"\s+", " ", (label or "").strip().lower())
    if _NA_LABEL.match(l):
        return False                      # not-assessable, handled as unknown
    if _ABS_EXACT.match(l) or _ABS_WORD.match(l) or _ABS_NOT.match(l):
        return True
    m = _NO_QUALIFIER.match(l)
    if m:
        # absence only when the qualifier itself negates the provision
        return bool(re.search(r"statutory|unpaid|\bnone\b|nothing|\bnot\b|\bno\b|don'?t", m.group(1)))
    if _NO_PROPERTY.match(l):
        return False
    if re.match(r"^no\b", l):
        return True                       # "No minimum", "No on-site childcare", ...
    return False


def practice_status(q, raw):
    """'in_place' | 'partial' | 'not_in_place' | 'unknown' for one org's answer."""
    if raw is None or not str(raw).strip():
        return "unknown"
    raw = str(raw).strip()
    cfg = q.scoring_config or {}
    na_codes = set(cfg.get("na_codes") or [])
    by_label = {_norm_label(o["label"]): o for o in (q.options or [])}

    if q.type == "multi_select":
        toks = [t.strip() for t in raw.split(";") if t.strip()]
        if not toks:
            return "unknown"
        subst = []
        for t in toks:
            o = by_label.get(_norm_label(t))
            if o is None or o.get("is_na") or o["code"] in na_codes:
                continue
            subst.append(o["label"])
        if not subst:
            return "unknown"
        if all(is_absence_label(l) for l in subst):
            return "not_in_place"
        return "in_place"

    o = by_label.get(_norm_label(raw))
    if o is None:
        return "unknown"
    if o.get("is_na") or o["code"] in na_codes or _NA_LABEL.match(o["label"].strip()):
        return "unknown"
    label = o["label"]
    if is_absence_label(label):
        return "not_in_place"
    if _PARTIAL_RE.match(re.sub(r"\s+", " ", label.strip().lower())):
        return "partial"
    return "in_place"


STATUS_POINTS = {"in_place": 100.0, "partial": 50.0, "not_in_place": 0.0}


def presence_block(statuses):
    """Peer presence for one question under one cut. Adoption counts a
    practice that is at least partly in place; unknowns are excluded from
    the denominator. Same n>=5 suppression as everything else."""
    assessable = [st for st in statuses if st in STATUS_POINTS]
    n = len(assessable)
    if n < SUPPRESSION_FLOOR:
        return suppressed(n)
    in_n = sum(1 for st in assessable if st == "in_place")
    pa_n = sum(1 for st in assessable if st == "partial")
    return {
        "n": n,
        "in_place_pct": round(100.0 * in_n / n, 1),
        "partial_pct": round(100.0 * pa_n / n, 1),
        "adoption_pct": round(100.0 * (in_n + pa_n) / n, 1),
        "status_mean": round(sum(STATUS_POINTS[st] for st in assessable) / n, 1),
    }


def score_block(scores, with_adoption):
    n = len(scores)
    if n < SUPPRESSION_FLOOR:
        return suppressed(n)
    vs = sorted(scores)
    b = {
        "n": n, "p25": percentile(vs, 25), "p50": percentile(vs, 50),
        "p75": percentile(vs, 75), "mean": sum(vs) / n, "_scores": vs,
    }
    if with_adoption:
        b["adoption_pct"] = round(100.0 * sum(1 for s in vs if s >= 50) / n, 1)
    return b


# --------------------------------------------------------------- cut logic ---

def aggregate_question_for_orgs(q, org_ids, answers_for_q):
    """Single entry point used by ALL cuts (incl. Peer Twin): aggregates one
    question over a set of org ids. answers_for_q: {(org_id, matrix_row_id): value}.
    Returns (block, matrix_rows_blocks, score_blk)."""
    org_ids = set(org_ids)
    if q.type == "matrix":
        rows = q.matrix_row_defs()
        observed = defaultdict(dict)  # row_id -> org -> value
        for (oid, rid), v in answers_for_q.items():
            if oid in org_ids and rid:
                observed[rid][oid] = v
        if not rows:  # fall back to observed ids if the library has no row list
            rows = [(rid, rid.replace("_", " ").title()) for rid in sorted(observed)]
        # mode is a property of the QUESTION, decided from its column schema and
        # the FULL answer set (so every cut classifies identically): numeric if
        # the column is numeric-typed or every defined option parses numerically
        # ("1.5x"); otherwise categorical (Yes/No, banded "More than 16 weeks").
        col0 = ((q.matrix or {}).get("columns") or [{}])[0]
        col_opts = col0.get("options") or []
        numeric_mode = col0.get("type") in ("percentage", "currency", "number")
        if not numeric_mode and col_opts:
            numeric_mode = all(matrix_value(o) is not None for o in col_opts)
        # N/A is a first-class entry-side answer (never 0, never blank). At
        # row level it is deliberately EXCLUDED from the distribution — not an
        # "unrecognised format". A label that appears in the column's own
        # option list is a real choice, never treated as N/A.
        def _row_na(v):
            s = str(v).strip()
            return bool(_NA_LABEL.match(s)) and s not in (col_opts or [])
        if not numeric_mode and not col_opts:
            all_vals = {str(v).strip() for (oid, rid), v in answers_for_q.items()
                        if rid and v not in (None, "") and not _row_na(v)}
            numeric_mode = bool(all_vals) and all(matrix_value(v) is not None for v in all_vals)
        mr = []
        answering = set()
        for rid, label in rows:
            raws = []
            for oid, v in observed.get(rid, {}).items():
                if v is not None and str(v).strip() != "":
                    raws.append(v)
                    answering.add(oid)
            na = sum(1 for v in raws if _row_na(v))
            raws = [v for v in raws if not _row_na(v)]
            if numeric_mode:
                vals = [f for f in (matrix_value(v) for v in raws) if f is not None]
                excl = len(raws) - len(vals)
                if excl:
                    print("[aggregate] WARN %s row %s: %d values failed numeric parse (kept as excluded count)" % (q.id, rid, excl))
                blk = numeric_block(vals, excl)
            else:
                blk = matrix_select_block(col_opts, raws)
            if na:
                blk["excluded_na"] = na
            mr.append({"row_id": rid, "label": label, "block": blk})
        top = {"n": len(answering)} if len(answering) >= SUPPRESSION_FLOOR else suppressed(len(answering))
        return top, mr, None, None

    # Non-matrix answers live at matrix_row_id='' by schema. Row-keyed answers
    # under a non-matrix question are a schema violation (seed-import artefact,
    # e.g. REW_INC_061) and must be IGNORED — never silently collapsed into a
    # single arbitrary row's distribution (integrity-review Phase A fix).
    per_org = {oid: v for (oid, rid), v in answers_for_q.items() if oid in org_ids and not rid}
    raw = list(per_org.values())

    if q.type == "numeric":
        # N/A answers count as answered (the gate) but never enter the
        # distribution — kept distinct from a real 0 and from blank.
        vals, excl, na = [], 0, 0
        for v in raw:
            f = coerce_number(v)
            if f is not None:
                vals.append(f)
            elif _NA_LABEL.match(str(v).strip()):
                na += 1
            else:
                excl += 1
        blk = numeric_block(vals, excl)
        if na:
            blk["excluded_na"] = na
    elif q.type in ("single_select", "yes_no"):
        blk = select_block(q, raw)
    elif q.type == "multi_select":
        blk = multi_block(q, raw)
    else:
        blk = suppressed(0)

    score_blk = None
    presence_blk = None
    if q.is_scored and q.type in ("single_select", "yes_no", "multi_select"):
        scores = [s for s in (score_answer(q, v) for v in raw) if s is not None]
        score_blk = score_block(scores, with_adoption=q.category in ("practice", "policy", "benefit"))
        if q.category in ("practice", "policy"):
            presence_blk = presence_block([practice_status(q, v) for v in raw])
    return blk, None, score_blk, presence_blk


def build_payload(q, cuts, answers_for_q):
    """cuts: {'all': set(org_ids), 'by_industry': {sector: set}, 'by_fte_band': {band: set}}."""
    all_blk, mr_all, score_all, presence_all = aggregate_question_for_orgs(q, cuts["all"], answers_for_q)
    payload = {
        "question_id": q.id,
        "tier": q.lumi_tier,
        "superpower": q.superpower,
        "subpower": q.sub_power,
        "type": q.type,
        "category": q.category,
        "polarity": q.polarity,
        "chart": q.default_chart_type,
        "unit": q.unit_block(),
        "all": all_blk,
        "by_industry": {},
        "by_fte_band": {},
    }
    scores = {"all": score_all, "by_industry": {}, "by_fte_band": {}} if score_all is not None else None
    presence = {"all": presence_all, "by_industry": {}, "by_fte_band": {}} if presence_all is not None else None
    matrix_rows = None
    if q.type == "matrix":
        matrix_rows = [{"row_id": m["row_id"], "label": m["label"], "all": m["block"],
                        "by_industry": {}, "by_fte_band": {}} for m in mr_all]

    for dim, key in (("by_industry", "by_industry"), ("by_fte_band", "by_fte_band")):
        for cut_val, org_set in cuts[dim].items():
            blk, mr, sc, pres = aggregate_question_for_orgs(q, org_set, answers_for_q)
            payload[key][cut_val] = blk
            if matrix_rows is not None and mr is not None:
                by_rid = {m["row_id"]: m["block"] for m in mr}
                for row in matrix_rows:
                    row[key][cut_val] = by_rid.get(row["row_id"], suppressed(0))
            if scores is not None:
                scores[key][cut_val] = sc
            if presence is not None:
                presence[key][cut_val] = pres
    if matrix_rows is not None:
        payload["matrix_rows"] = matrix_rows
    if scores is not None:
        payload["scores"] = scores
    if presence is not None:
        payload["presence"] = presence
    return payload


# --------------------------------------------------------------- snapshot ---

def load_answers(conn, snapshot_id):
    """{question_id: {(org_id, matrix_row_id): value}}"""
    out = defaultdict(dict)
    for r in conn.execute(
            "SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=?",
            (snapshot_id,)):
        out[r["question_id"]][(r["org_id"], r["matrix_row_id"] or "")] = r["value"]
    return out


def build_cuts(conn, responding_org_ids):
    """All peers = every org with answers in the snapshot (incl. Unclassified).
    Filtered cuts = classified orgs only."""
    cuts = {"all": set(responding_org_ids), "by_industry": defaultdict(set), "by_fte_band": defaultdict(set)}
    for r in conn.execute("SELECT org_id, classified, industry, fte_band FROM orgs"):
        if r["org_id"] not in cuts["all"] or not r["classified"]:
            continue
        if r["industry"]:
            cuts["by_industry"][r["industry"]].add(r["org_id"])
        if r["fte_band"]:
            cuts["by_fte_band"][r["fte_band"]].add(r["org_id"])
    cuts["by_industry"] = dict(cuts["by_industry"])
    cuts["by_fte_band"] = dict(cuts["by_fte_band"])
    return cuts


def run_snapshot(snapshot_id=1, verbose=True):
    conn = get_conn()
    init_schema(conn)
    questions = load_questions()
    answers = load_answers(conn, snapshot_id)
    responding = {oid for qa in answers.values() for (oid, _r) in qa}
    # FIREWALL: only orgs that COMPLETED submission contribute to the published
    # benchmark — the same gate peer_twin and qa_integrity enforce. Without this,
    # a half-finished signup that answered a single question leaks into the live
    # counts and option shares (the ALLOW_02 n=221-vs-220 inflation). build_cuts
    # already restricts the filtered cuts to classified orgs; this gates the
    # 'all' universe too. Incomplete is orthogonal to classified, so no complete
    # peer is dropped.
    complete = {r[0] for r in conn.execute("SELECT org_id FROM orgs WHERE submission_complete=1")}
    responding &= complete
    cuts = build_cuts(conn, responding)
    if verbose:
        print("Aggregating snapshot %d: %d questions, %d responding orgs (%d classified in cuts)"
              % (snapshot_id, len(questions), len(responding),
                 sum(len(s) for s in cuts["by_industry"].values())))

    snap = conn.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    count = 0
    for qid, q in questions.items():
        payload = build_payload(q, cuts, answers.get(qid, {}))
        payload["snapshot"] = {
            "snapshot_id": snapshot_id,
            "snapshot_date": snap["snapshot_date"],
            "collection_window": snap["collection_window"],
        }
        conn.execute(
            "INSERT OR REPLACE INTO benchmark_snapshots(snapshot_id, question_id, payload_json) VALUES (?,?,?)",
            (snapshot_id, qid, j(payload)))
        count += 1
    conn.execute("UPDATE snapshots SET status='aggregated' WHERE snapshot_id=?", (snapshot_id,))

    set_meta("assumptions_defaults", DEFAULT_ASSUMPTIONS, conn)
    set_meta("peer_pool", {
        "snapshot_id": snapshot_id,
        "responding_orgs": len(responding),
        "classified_orgs": len({o for s in cuts["by_industry"].values() for o in s}),
        "industries": {k: len(v) for k, v in sorted(cuts["by_industry"].items())},
        "fte_bands": {k: len(v) for k, v in sorted(cuts["by_fte_band"].items())},
    }, conn)
    conn.commit()
    if verbose:
        print("Stored %d benchmark payloads for snapshot %d" % (count, snapshot_id))
    return count


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=int, default=1)
    args = ap.parse_args()
    run_snapshot(args.snapshot)
