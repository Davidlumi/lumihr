"""Server-side Claude API client (never called from the browser).

Model and key come from environment config (ANTHROPIC_MODEL / ANTHROPIC_API_KEY).
In environments that inject credentials automatically the key header is omitted.
When the API is unreachable/unauthenticated, callers receive ok=False and fall
back to deterministic, clearly-labelled narrative — no fabricated numbers either way.
"""
import json
import os

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def call_claude(system, user_content, max_tokens=2000):
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        headers["x-api-key"] = key
    try:
        resp = httpx.post(API_URL, headers=headers, timeout=120.0, json={
            "model": MODEL, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user_content}],
        })
        data = resp.json()
        if resp.status_code != 200:
            return {"ok": False, "error": data.get("error", {}).get("message", "API error %d" % resp.status_code)}
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return {"ok": True, "text": text}
    except Exception as e:  # network, timeout, parse
        return {"ok": False, "error": str(e)}


BOARD_PACK_SYSTEM = """You are writing the narrative for a board-ready HR benchmarking pack
for a UK organisation, in the register of a PwC Saratoga executive summary: measured,
specific, plain English (UK), short sentences, active voice, no hype.

Hard rules — violating any of these makes the output unusable:
1. Use ONLY the numbers provided in the JSON payload. Every quantitative claim must cite a
   metric, percentile and n that appear verbatim in the payload. Do not introduce, derive,
   round differently, or estimate ANY number not present in the payload.
2. Do not describe charts or tables — they are rendered separately from the data.
3. Do not give general HR market commentary, predictions, or claims about causation.
4. Refer to the peer group exactly as named in the payload's cut_label fields.
5. Where the payload marks something suppressed or missing, you may note that data was
   insufficient — never guess at it.
6. Write for a CEO: a Reward Director should be able to read any sentence aloud without
   translating jargon. Percentiles may be glossed (e.g. "P18 — in the bottom quarter").

Return STRICT JSON with keys:
  "executive_summary": 2-3 paragraphs (string),
  "strengths_narrative": one short paragraph introducing the strengths table,
  "gaps_narrative": one short paragraph introducing the gaps table,
  "opportunity_narrative": one short paragraph on the indicative £ opportunities (if present),
  "recommended_actions": array of 4-6 strings, each one specific action grounded in a cited gap.
Return ONLY the JSON object, no markdown fences."""


def generate_board_pack_narrative(payload):
    res = call_claude(BOARD_PACK_SYSTEM, json.dumps(payload, ensure_ascii=False), max_tokens=3000)
    if not res["ok"]:
        return {"ok": False, "error": res["error"], "narrative": _deterministic_pack(payload)}
    try:
        text = res["text"].strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        narrative = json.loads(text)
        return {"ok": True, "narrative": narrative}
    except ValueError:
        return {"ok": False, "error": "Model returned non-JSON output", "narrative": _deterministic_pack(payload)}


def _deterministic_pack(payload):
    """Rule-based fallback narrative (clearly labelled in the UI) built only
    from the same payload — used when the Claude API is not configured."""
    org = payload.get("organisation", {})
    head = payload.get("headline", {})
    s = ("%s sits above the peer median on %s of %s comparable metrics in this benchmark "
         "(peer group: %s). The pages that follow set out the strongest areas of the people "
         "proposition, the largest gaps to peers, and the indicative value of closing them.") % (
        org.get("name", "The organisation"), head.get("above_median", "—"),
        head.get("comparable_metrics", "—"), payload.get("cut_label", "All peers"))
    gaps = payload.get("gaps", [])
    strengths = payload.get("strengths", [])
    acts = []
    for g in gaps[:5]:
        acts.append("Review %s: currently %s (P%s, %s, n=%s)." % (
            g["label"], g["value_display"], int(round(g["percentile"])), g["cut_label"], g["n"]))
    return {
        "executive_summary": s,
        "strengths_narrative": "The organisation is ahead of most similar organisations in the following areas." if strengths else "No statistically comparable strengths were identified in this cut.",
        "gaps_narrative": "The largest gaps to the peer median, ranked by distance, are set out below." if gaps else "No statistically comparable gaps were identified in this cut.",
        "opportunity_narrative": "Indicative annual values of moving to the peer median are shown below; all figures rest on the stated assumptions." if payload.get("opportunities") else "",
        "recommended_actions": acts or ["Complete more of the questionnaire to unlock specific recommendations."],
        "_fallback": True,
    }


ANALYST_SYSTEM = """You are "Ask lumi", the benchmark analyst inside lumi, a UK HR
benchmarking platform. You answer questions from an HR Director about how their
organisation compares with peers.

Hard rules:
1. Answer ONLY from the supplied JSON data (peer aggregates + this organisation's own
   answers). No general HR knowledge, no extrapolation, no forecasts, no advice beyond
   what the data shows.
2. Every figure you state must appear in the data. Always cite the percentile (P50 style),
   the peer cut label, and n for any benchmark figure, e.g. "(P63, All peers, n=181)".
3. If the relevant peer cut is suppressed (fewer than 5 organisations), say so plainly and
   offer the All-peers figure if available.
4. If the question cannot be answered from the supplied data, say exactly that: name what
   the dataset would need to contain. Do not answer from general knowledge.
5. Plain English (UK), short sentences. "Similar organisations", not "peer cohort".
6. Keep answers under 150 words. Use the metric names as given.

After your prose answer, output a line containing only:
CHIPS: [{"label": "...", "value": "...", "sub": "P63 · All peers · n=181", "question_id": "..."}]
— one chip per figure you cited (valid JSON array; [] if none)."""


def analyst_answer(question, data_payload):
    content = "QUESTION: %s\n\nDATA:\n%s" % (question, json.dumps(data_payload, ensure_ascii=False))
    res = call_claude(ANALYST_SYSTEM, content, max_tokens=1200)
    if not res["ok"]:
        return {"ok": False, "error": res["error"]}
    text = res["text"]
    chips = []
    if "CHIPS:" in text:
        text, _, chip_part = text.partition("CHIPS:")
        try:
            chips = json.loads(chip_part.strip())
        except ValueError:
            chips = []
    return {"ok": True, "answer": text.strip(), "chips": chips}
