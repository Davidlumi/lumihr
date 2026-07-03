"""Retrieval for the 'Ask lumi' analyst: keyword + fuzzy match of a user
question against the library's search_description column. Returns the top
candidate questions whose aggregates (only) are passed to the model."""
import re
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions

STOP = set("""a an and are as at be but by for from has have how in is it of on or our than
that the their there this to was we what when where which who why will with you your
do does did organisation organisations company companies peers peer benchmark vs
""".split())

# words too generic to prove the dataset actually covers a topic
GENERIC = STOP | set("""typical average spend cost costs rate rates per employee employees
staff people compare comparison year annual measure offer offered amount level levels
much many usually normally similar most common
metric metrics data figure figures number numbers stat stats anything something""".split())


def tokens(s):
    # single letters are contraction shrapnel ("what's" → "what","s"), never a
    # topic — and as distinctive tokens they can veto a whole query's coverage
    return [t for t in re.findall(r"[a-z0-9%£]+", (s or "").lower())
            if t not in STOP and not (len(t) == 1 and t.isalpha())]


def _bigrams(toks):
    return {" ".join(toks[i:i + 2]) for i in range(len(toks) - 1)}


_vocab_cache = None


def library_vocab():
    """Every token appearing in any question's search text — the dictionary a
    singularisation candidate must be found in before it may replace a word
    (so 'pensions'→'pension' happens, 'bonus'→'bonu' never does)."""
    global _vocab_cache
    if _vocab_cache is None:
        v = set()
        for q in load_questions().values():
            doc = (q.search_description or "") + " " + (q.display_title or "") + " " + (q.text or "")
            v |= set(tokens(doc))
        _vocab_cache = v
    return _vocab_cache


def singularise(word):
    """Best-effort singular of one lowercase word, vocabulary-checked: a
    candidate ships only if the library actually contains it. English plural
    rules, not naive 's'-strip (which mangles 'allowances'→'allowanc')."""
    w = word.lower()
    vocab = library_vocab()
    cands = []
    if len(w) > 4 and re.search(r"(?:ses|xes|zes|ches|shes)$", w):
        cands.append(w[:-2])                               # bonuses->bonus, boxes->box
    if len(w) > 3 and w.endswith("ies"):
        cands.append(w[:-3] + "y")                         # policies->policy
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        cands.append(w[:-1])                               # pensions->pension, eaps->eap
    for c in cands:
        if c in vocab:
            return c
    return w


def topic_rank(query, qids):
    """The given qids re-ordered by how much of the query's distinctive topic
    each one actually carries (hit count desc, original order as tiebreak) —
    so a fallback readout for 'pensions' leads with the pension metrics, not
    whichever fuzzy match out-scored them."""
    distinctive = [singularise(t) for t in set(tokens(query)) if t not in GENERIC]
    if not distinctive:
        return list(qids)
    qs = load_questions()
    def hits(qid):
        q = qs.get(qid)
        if not q:
            return 0
        # a topic word in the TITLE outranks one buried in the search text —
        # search descriptions mention neighbouring topics ('pension' appears in
        # the sick-pay doc), titles say what the metric actually is
        title = set(tokens(q.display_title or ""))
        desc = set(tokens(q.search_description or ""))
        return sum(2 if t in title else (1 if t in desc else 0) for t in distinctive)
    return [qid for _h, _i, qid in
            sorted(((-hits(qid), i, qid) for i, qid in enumerate(qids)))]


def is_vague(query):
    """True when the query carries no distinctive topic token at all ("how much
    do peers usually offer?") — coverage can't be judged, so callers answer with
    the capabilities nudge instead of readouts of whatever fuzzy-scored."""
    return not any(t not in GENERIC for t in set(tokens(query)))


def distinctive_coverage(query, qids):
    """Share of the query's distinctive (non-generic) tokens that the BEST
    single matched question contains. Per-question, deliberately NOT the union
    across matches — six questions each covering one word of 'cycle to work
    scheme' is fuzzy noise, not coverage. All-generic queries score 0.0
    (nothing provable); callers pre-screen those with is_vague."""
    distinctive = [t for t in set(tokens(query)) if t not in GENERIC]
    if not distinctive:
        return 0.0
    qs = load_questions()
    best = 0.0
    for qid in qids:
        q = qs.get(qid)
        if not q:
            continue
        doc = set(tokens((q.search_description or "") + " " + (q.display_title or "")))
        cov = sum(1 for t in distinctive if t in doc) / float(len(distinctive))
        best = max(best, cov)
    return best


def search_questions(query, limit=6):
    """Score = weighted token overlap with search_description (+ title boost)."""
    qt = tokens(query)
    if not qt:
        return []
    qset, qbi = set(qt), _bigrams(qt)
    scored = []
    for qid, q in load_questions().items():
        doc = tokens(q.search_description or "")
        if not doc:
            doc = tokens("%s %s %s" % (q.text, q.superpower, q.sub_power or ""))
        dset = set(doc)
        overlap = len(qset & dset)
        if overlap == 0:
            continue
        score = overlap / float(len(qset))
        score += 0.5 * len(qbi & _bigrams(doc))
        title = set(tokens(q.display_title))
        score += 0.4 * len(qset & title)
        # prefer hard metrics when the user asks "what/how much/rate/median"
        if q.type in ("numeric", "matrix") and re.search(r"\b(rate|median|average|typical|how much|what is|p\d\d)\b", query.lower()):
            score += 0.3
        scored.append((score, qid))
    scored.sort(key=lambda t: -t[0])
    return [qid for _s, qid in scored[:limit]]
