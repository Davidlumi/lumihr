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
    return [t for t in re.findall(r"[a-z0-9%£]+", (s or "").lower()) if t not in STOP]


def _bigrams(toks):
    return {" ".join(toks[i:i + 2]) for i in range(len(toks) - 1)}


def distinctive_coverage(query, qids):
    """Share of the query's distinctive (non-generic) tokens that the matched
    questions actually contain. Low coverage = the dataset doesn't really
    cover this topic, however fuzzily it scored."""
    distinctive = [t for t in set(tokens(query)) if t not in GENERIC]
    if not distinctive:
        return 1.0  # nothing distinctive to judge — let the matches speak
    qs = load_questions()
    matched_doc = set()
    for qid in qids:
        q = qs.get(qid)
        if q:
            matched_doc |= set(tokens((q.search_description or "") + " " + (q.display_title or "")))
    hit = sum(1 for t in distinctive if t in matched_doc)
    return hit / float(len(distinctive))


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
