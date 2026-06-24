"""Ask lumi — the GUIDE layer (find a metric · explain a term · how to use lumi).

This is the non-benchmark side of Ask lumi. The benchmark analyst (claude_api
.analyst_answer) stays strict and cited; everything here is structurally unable
to state a benchmark figure because it is never handed any peer data — its only
knowledge is the glossary, a platform feature guide, and the metric *catalogue*
(names/areas, never values). Intent is classified here; app.py routes benchmark
questions to the analyst and the rest to this module.
"""
import re

# Plain-English glossary — superset of the frontend GLOSSARY (web/js/core.js),
# kept in the same UK-gov register. The single source the term answers draw on.
GLOSSARY = {
    "percentile": "If you line every organisation up from lowest to highest, the percentile says where a value sits. P75 means three quarters of organisations are at or below it.",
    "median": "The middle value — half of organisations are above it, half below. lumi shows medians (P50) rather than averages so one unusual organisation can't skew the picture.",
    "quartile": "A quarter of the peer group. The top quartile is the highest 25%; the interquartile range (P25–P75) is the middle half.",
    "interquartile range": "The middle half of the peer group, from the 25th to the 75th percentile (P25–P75) — a quick read of the typical spread.",
    "suppressed": "When fewer than 5 organisations sit behind a number, lumi hides it so no single organisation's data can be worked out.",
    "peer group": "The organisations you're compared with. Use the ‘Comparing against’ selector to switch between everyone, your sector, your size, or organisations like you.",
    "n": "The number of organisations behind a comparison. A benchmark without its sample size isn't publishable, so n is always shown.",
    "indicative": "A modelled, directional figure built on stated assumptions — useful for sizing a conversation, not for budgeting.",
    "market position": "Where you sit versus peers — below, on, or above market. The headline uses only market-rate measures where higher is better, so it answers one question: how competitive is your reward?",
    "favourable": "A measure where being lower is the good outcome — such as a pay gap — and you sit on the good side of the market.",
    "context": "A measure with no inherently good direction — shown as a fact to weigh, not a verdict.",
    "signal": "A flag lumi raises where your position is worth a look — a gap to peers, an unusual choice, or new movement. We flag; you decide.",
    "peer twin": "A peer group built from organisations most like yours across sector, size and shape — the closest comparison lumi can assemble for you.",
    "reward strategy": "Your captured intent — market stance, pay/benefits mix and this year's objective — which lumi uses to order what it shows you. It never changes the underlying figures.",
}

# Synonyms → canonical glossary key (so "IQR", "sample size", "P50" resolve).
_SYNONYM = {
    "iqr": "interquartile range", "inter quartile": "interquartile range",
    "sample size": "n", "p50": "median", "p25": "quartile", "p75": "quartile",
    "p90": "percentile", "p10": "percentile", "above market": "market position",
    "below market": "market position", "on market": "market position",
    "flag": "signal", "flags": "signal", "twin": "peer twin",
    "suppression": "suppressed", "suppress": "suppressed",
    "percentiles": "percentile", "medians": "median", "quartiles": "quartile",
}

# Platform feature guide — the source for "how do I…" answers. Each entry:
#   keys   — lowercase trigger words matched against the question
#   answer — 1–3 plain sentences
#   route  — in-app destination (or None for actions that live in a menu/modal)
#   cta    — link label when a route is present
FEATURES = [
    {"keys": ["add data", "add my data", "submit", "enter data", "fill in", "your data",
              "my data", "complete", "questionnaire", "answer the questions", "input data"],
     "answer": "Add or update your figures under Your data. Pick a domain, answer the questions (‘Not applicable’ counts), then submit — each answer immediately shows where you stand against peers.",
     "route": "/your-data", "cta": "Go to Your data"},
    {"keys": ["peer group", "compare against", "comparing against", "change peers", "filter",
              "your sector", "your size", "organisations like", "similar organisations", "cut"],
     "answer": "Use the ‘Comparing against’ selector at the top of any benchmark page to switch peer group — everyone, your sector, your size, organisations like you, or a custom group you build. Every figure re-reads against the group you pick.",
     "route": "/benchmark", "cta": "Open the benchmark"},
    {"keys": ["dashboard", "dashboards", "my dashboards", "pin", "save a view", "my view", "arrange cards"],
     "answer": "My dashboards lets you build and save as many views as you like. Pin any card with the star (☆), drag to arrange, and switch between dashboards with the tabs at the top.",
     "route": "/dashboards", "cta": "Go to My dashboards"},
    {"keys": ["download", "export chart", "save chart", "png", "image", "picture of", "download chart", "save the chart"],
     "answer": "Open any card's ‘⋮’ menu and choose ‘Download chart (PNG)’. The image carries the lumi logo, the peer group it's on, and the sample size — ready to drop into a deck or board pack.",
     "route": None, "cta": None},
    {"keys": ["signal", "signals", "flag", "flags", "alert", "alerts", "what should i look at"],
     "answer": "Signals is your flag list — where your position is worth a look: gaps to peers, unusual choices and new movement. lumi flags; you decide what to act on. You can mark each one priority, saved or dismissed.",
     "route": "/signals", "cta": "Open Signals"},
    {"keys": ["strategy", "reward strategy", "objectives", "philosophy", "market stance", "capture strategy"],
     "answer": "Reward strategy captures your intent — market stance, pay/benefits mix and this year's objective. lumi uses it to order what it surfaces for you; it never changes the underlying figures.",
     "route": "/strategy", "cta": "Set your reward strategy"},
    {"keys": ["board pack", "board report", "export report", "pdf", "for the board", "board-ready"],
     "answer": "The board pack pulls your strongest areas, biggest gaps and indicative opportunities into a board-ready narrative. Suppressed figures are held back automatically. You'll find it from your Overview.",
     "route": "/overview", "cta": "Go to Overview"},
    {"keys": ["pulse", "pulses"],
     "answer": "Pulses are short, focused check-ins that run alongside the core benchmark — same engine, separate surface. Open Pulse to see the ones available to you.",
     "route": "/pulse", "cta": "Open Pulse"},
    {"keys": ["suppressed", "hidden", "not enough", "why can't i see", "why is it hidden", "n<5", "fewer than 5", "privacy", "anonymity"],
     "answer": "If fewer than 5 organisations sit behind a figure, lumi hides it so no single organisation's data can be worked out. Try a broader peer group — ‘All peers’ usually has the numbers.",
     "route": "/how-lumi-works/suppression", "cta": "Why figures are hidden"},
    {"keys": ["request", "suggest a metric", "missing metric", "add a metric", "can you add", "not benchmarked", "request a metric"],
     "answer": "If lumi doesn't measure something yet, use ‘Suggest a metric’ (top right). Member requests shape what lumi benchmarks next — I'll also offer the button whenever I can't find a match.",
     "route": None, "cta": None},
    {"keys": ["how calculated", "methodology", "how do you work out", "where does the data come from", "how is it calculated", "how does lumi work", "how are figures"],
     "answer": "Every figure is a median or percentile across valid peer answers — never an average — with small samples suppressed. The full method, assumptions and data sources are on the How lumi works page.",
     "route": "/how-lumi-works/calculations", "cta": "How the numbers are calculated"},
    {"keys": ["glossary", "terms", "jargon", "what do the words mean", "definitions"],
     "answer": "The glossary explains every term in plain English — percentile, median, suppressed, peer group and the rest. You can also just ask me ‘what does … mean’.",
     "route": "/how-lumi-works/glossary", "cta": "Open the glossary"},
    {"keys": ["team", "invite", "colleague", "add user", "add a user", "roles", "admin", "viewer", "contributor", "permission"],
     "answer": "Admins manage members under Team — invite colleagues and set each one as Admin, Contributor (can edit data) or Viewer (read-only). ",
     "route": "/team", "cta": "Go to Team"},
    {"keys": ["settings", "assumptions", "sharing settings", "account"],
     "answer": "Settings is where Admins adjust the modelling assumptions and sharing options for your organisation.",
     "route": "/settings", "cta": "Open Settings"},
    {"keys": ["get started", "getting started", "new here", "how does this work", "what can you do",
              "what can i ask", "help", "how do i use", "show me around", "i'm new"],
     "answer": "Three ways I can help: find the right metric (‘do you have anything on parental leave?’), explain a term (‘what does percentile mean?’), or show you how to use lumi (‘how do I add my data?’). And you can always ask how you compare on a metric — I'll pull the figure with its peer group and sample size.",
     "route": "/how-lumi-works", "cta": "How lumi works"},
]

# regex intent signals
_DEFN = re.compile(r"\b(what(?:'s| is| are| does)|what do you mean|define|defines|explain|meaning of|stands? for|in plain english)\b", re.I)
_HELP = re.compile(r"\b(how (?:do|can|would|should|might) i|how to|how does .* work|where (?:do|can|is|are) i?|(?:can|could) i (?:add|edit|update|change|download|export|save|delete|remove|create|make|set|invite|find|filter|use|build|pin|reset|rename|duplicate|switch)|help me|walk me through|guide me|get started|getting started|what can you do|what can i ask|how do i use|show me around)\b", re.I)
# bare help requests that aren't "how do I…" shaped — exact-ish prompts
_HELP_BARE = re.compile(r"^\s*(help|i need help|need help|what can you do|what can i ask|get(ting)? started|how does (this|lumi) work\??)\s*$", re.I)
_FIND = re.compile(r"\b(do you (?:have|track|benchmark|measure|cover|collect)|is there (?:a|any) metric|are there (?:any )?metrics|show me|list (?:the |all )?|what metrics|which metrics|metrics? (?:on|about|for|around|covering)|anything (?:on|about|around)|find (?:a |me |the )?|what do you (?:benchmark|measure|cover|track)|do you do)\b", re.I)
_BENCH = re.compile(r"\b(compare|compared|comparison|versus|vs\.?|against (?:peers|the market|similar|others)|where do(?:es)? (?:we|our|i) (?:sit|stand|rank|land)|how do(?:es)? (?:we|our)|what(?:'s| is) (?:our|my)|how competitive|are we (?:ahead|behind|above|below|competitive)|how (?:far )?(?:ahead|behind))\b", re.I)
_OWN = re.compile(r"\b(our|we|us|my|mine|we're|were)\b", re.I)


def glossary_key(q):
    """The glossary entry a question is about, or None. Longest match wins."""
    ql = " " + re.sub(r"[^a-z0-9% ]", " ", q.lower()) + " "
    best = None
    for k in GLOSSARY:
        if (" " + k + " ") in ql and (best is None or len(k) > len(best)):
            best = k
    for syn, k in _SYNONYM.items():
        if (" " + syn + " ") in ql and (best is None or len(syn) > len(best or "")):
            best = k
    return best


def help_match(q):
    """Best feature-guide entry for a how-to question (most keyword hits), or None."""
    ql = " " + q.lower() + " "
    best, score = None, 0
    for f in FEATURES:
        s = sum(1 for kw in f["keys"] if (" " + kw + " ") in ql or kw in q.lower())
        if s > score:
            best, score = f, s
    return best if score > 0 else None


def classify(q):
    """(intent, extra) where intent is benchmark|find|term|help. extra is the
    glossary key (term) or matched feature dict (help). Benchmark is the default
    so anything comparison-shaped still reaches the strict cited analyst."""
    if _HELP_BARE.search(q):
        return "help", help_match(q)
    bench = bool(_BENCH.search(q))
    if _HELP.search(q) and not bench:
        return "help", help_match(q)
    if _FIND.search(q) and not bench:
        return "find", None
    if _DEFN.search(q) and not bench and not _OWN.search(q):
        key = glossary_key(q)
        if key:
            return "term", key
    return "benchmark", None


CAPABILITIES = FEATURES[-1]["answer"]


def deterministic_answer(intent, extra, question, has_matches):
    """Plain answer used when the model is unavailable — already authoritative
    for terms (the glossary) and how-to (the feature guide)."""
    if intent == "term":
        return GLOSSARY.get(extra, "") + " You'll find more in the glossary."
    if intent == "find":
        if has_matches:
            topic = question.strip().rstrip("?").strip()
            return "Here's what lumi benchmarks closest to “%s” — tap any to open it and see the full peer picture." % topic
        return ("I couldn't find a lumi metric for that yet — so I won't guess. If it would be "
                "useful, use ‘Suggest a metric’ and the team will consider it for a future cycle.")
    if intent == "help":
        return (extra or {}).get("answer") or CAPABILITIES
    return ""


def links_for(intent, extra):
    if intent == "term":
        return [{"label": "Open the glossary", "route": "/how-lumi-works/glossary"}]
    if intent == "help":
        f = extra
        if f and f.get("route"):
            return [{"label": f.get("cta") or "Open", "route": f["route"]}]
        return [{"label": "How lumi works", "route": "/how-lumi-works"}]
    return []
