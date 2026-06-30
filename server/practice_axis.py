"""Single source of truth for the member-facing PRACTICE ALIGNMENT vocabulary.

"Practice Prevalence" -> "Practice Alignment" (rename 2026-06-29). This module owns
the DISPLAYED words and the verdict line ONLY; the counts come straight from the engine.

Two internal key-sets are NEVER renamed and NEVER displayed — this module touches neither:
  - engine keys      : with_majority / established / less_common / pool
                       (positions._prev_summary; read as prev.* on the frontend)
  - AI-payload keys  : match_market_majority / established_alternative / less_common / pool
                       (written by app.build_domain_summary_payload, read by the claude_api floor)
The substring "match" in match_market_majority is a KEY, not display text.

Leaf module: imports nothing internal, so both app.py and claude_api.py can import it
without any circular-import risk.
"""

PRACTICE_AXIS = {
    "title": "Practice Alignment",
    "states": {                      # engine key -> the member word
        "with_majority": "common",
        "established":   "alternative",
        "less_common":   "rare",
    },
}

# Variant verdict line, keyed by the leading engine bucket. FRONTEND/CARD ONLY — this string
# must NEVER reach the model or the deterministic floor: it contains "most", which the
# domain-summary prompt's rule 1 forbids in model output. Enforced by qa_prevalence_rename.py.
_VERDICTS = {
    "with_majority": "most of your practices are common choices",
    "established":   "many of your practices follow an alternative pattern",
    "less_common":   "several of your practices are rare choices",
}
# Tie-break order: a tie resolves to the higher-frequency bucket (common > alternative > rare).
_PRIORITY = ("with_majority", "established", "less_common")


def prevalence_verdict(prev):
    """The variant verdict line from the three _prev_summary counts. None when there is no pool.
    `prev` carries the engine keys (with_majority/established/less_common/pool)."""
    if not prev or not prev.get("pool"):
        return None
    counts = {k: (prev.get(k) or 0) for k in _PRIORITY}
    best = max(_PRIORITY, key=lambda k: (counts[k], -_PRIORITY.index(k)))
    return _VERDICTS[best]


def bucket_phrase(n, key):
    """One grammatical clause for a bucket count `n`, the word derived from PRACTICE_AXIS.
    Singular and plural are both handled (a bucket count of exactly 1 occurs in real data).
    The articles ("a"/"an") are tuned to the current vocabulary (common/alternative/rare);
    revisit this helper if those words ever change."""
    word = PRACTICE_AXIS["states"][key]
    if key == "with_majority":          # common  -> "1 is a common choice" / "N are common choices"
        return ("%d is a %s choice" if n == 1 else "%d are %s choices") % (n, word)
    if key == "established":            # alternative -> "1 follows an alternative pattern" / "N follow ... patterns"
        return ("%d follows an %s pattern" if n == 1 else "%d follow %s patterns") % (n, word)
    return ("%d is %s" if n == 1 else "%d are %s") % (n, word)   # rare -> "1 is rare" / "N are rare"


def bucket_word(key):
    """The member word for ONE prevalence bucket — the single source for the signal tags,
    chips and prose (signals.py attaches s["bucket"] from this; the frontend renders it).
    `key` is an engine bucket key (with_majority / established / less_common). Raises
    KeyError on an unknown key so a typo can never render a blank chip/tag."""
    return PRACTICE_AXIS["states"][key]   # with_majority->common · established->alternative · less_common->rare


def with_display(prev):
    """Return the prevalence dict with display fields ADDED ALONGSIDE the frozen engine keys.
    The spread copies with_majority/established/less_common/pool through untouched; only
    title/states/verdict are added. None-safe (Pass 2 / Option A): a domain with no practice
    questions still receives title + states, so the frontend never hardcodes the words; verdict
    is null when there is no pool. Used by the /api/overview handler for the browser object."""
    prev = prev or {}
    return {**prev,
            "title": PRACTICE_AXIS["title"],
            "states": PRACTICE_AXIS["states"],
            "verdict": prevalence_verdict(prev)}
