# -*- coding: utf-8 -*-
"""What each AI surface actually costs, and how often its output survives the gate.

WHY. Choosing a model is a judgement call until it is a table. Before this, nothing here
recorded a single token: `_ai_calls` counted calls for the daily cap and threw the rest
away, so "is Opus the right model for the Ask lumi guide answer" had no answer except an
opinion. One row per model call turns it into arithmetic.

TWO NUMBERS, AND WHY BOTH. Tokens and latency say what a surface COSTS. The validator
verdict says whether the output was USABLE — and that is the model-comparable quality
signal, because the validators are the same regardless of which model produced the text.
A cheaper model that doubles the rejection rate is not cheaper; it is the same work done
twice plus a fallback.

NEVER RAISES. Every entry point swallows its own errors. Losing a metrics row is a
nuisance; losing a member's board pack because a metrics INSERT failed is not.

NO PRICE IS BAKED IN. Rates change and a wrong constant is worse than no constant, so the
report prints tokens by default and money only when LUMI_AI_PRICE_IN_PER_MTOK /
LUMI_AI_PRICE_OUT_PER_MTOK are set to the rates on your bill.
"""
import logging
import os

log = logging.getLogger("lumi")

# The surfaces, so a report can name one that has gone silent rather than just omitting it.
# Keep in step with the call_claude sites in claude_api.py (ai_live_sweep.py exercises them).
SURFACES = ("board_pack", "pulse_narrative", "analyst", "guide", "statement",
            "strategy_commentary", "metric_commentary", "domain_summary",
            "diagnosis", "action_plan")


def _conn():
    from db import get_conn                      # lazy: claude_api stays DB-free by design
    return get_conn()


def record_call(surface, model, ok, input_tokens=None, output_tokens=None,
                latency_ms=None, error=None):
    """One paid call happened. Written at the choke point (call_claude) so it cannot be
    forgotten by a new surface. Returns the row id for the later verdict, or None."""
    try:
        conn = _conn()
        cur = conn.execute(
            "INSERT INTO ai_calls(surface, model, ok, input_tokens, output_tokens, "
            "latency_ms, error) VALUES (?,?,?,?,?,?,?)",
            (surface or "unknown", model, 1 if ok else 0, input_tokens, output_tokens,
             latency_ms, (str(error)[:200] if error else None)))
        conn.commit()
        return cur.lastrowid
    except Exception:                             # noqa: BLE001 — see module docstring
        log.debug("[lumi] ai_metrics.record_call failed", exc_info=True)
        return None


def record_verdict(call_id, accepted, reason=None):
    """Whether that call's output passed its validator. Left NULL if a generator never
    reports one — which reads as "unknown" in the report rather than quietly as "fine"."""
    if not call_id:
        return
    try:
        conn = _conn()
        conn.execute("UPDATE ai_calls SET accepted=?, reject_reason=? WHERE id=?",
                     (1 if accepted else 0, (str(reason)[:200] if reason else None), call_id))
        conn.commit()
    except Exception:                             # noqa: BLE001
        log.debug("[lumi] ai_metrics.record_verdict failed", exc_info=True)


def _prices():
    """Per-million-token rates from the environment, or None. Never guessed."""
    try:
        pin = float(os.environ.get("LUMI_AI_PRICE_IN_PER_MTOK", "") or 0)
        pout = float(os.environ.get("LUMI_AI_PRICE_OUT_PER_MTOK", "") or 0)
    except ValueError:
        return None
    return (pin, pout) if (pin or pout) else None


def summary(conn, days=7):
    """Per-surface aggregates over the window: volume, tokens, latency, and how often the
    validator accepted. Ordered by output tokens — the thing that dominates the bill."""
    rows = conn.execute(
        "SELECT surface, model, COUNT(*) calls, "
        "       SUM(ok) api_ok, "
        "       SUM(COALESCE(input_tokens,0)) tok_in, "
        "       SUM(COALESCE(output_tokens,0)) tok_out, "
        "       AVG(latency_ms) avg_ms, "
        "       MAX(latency_ms) max_ms, "
        "       SUM(CASE WHEN accepted=1 THEN 1 ELSE 0 END) accepted, "
        "       SUM(CASE WHEN accepted=0 THEN 1 ELSE 0 END) rejected "
        "FROM ai_calls WHERE created_at >= datetime('now', ?) "
        "GROUP BY surface, model ORDER BY tok_out DESC",
        ("-%d day" % int(days),)).fetchall()
    return [dict(r) for r in rows]


def top_rejections(conn, days=7, limit=10):
    """The reasons output is being thrown away, commonest first. A surface whose rejects
    cluster on one rule is usually a prompt problem, not a model problem."""
    return [dict(r) for r in conn.execute(
        "SELECT surface, reject_reason, COUNT(*) n FROM ai_calls "
        "WHERE accepted=0 AND reject_reason IS NOT NULL "
        "AND created_at >= datetime('now', ?) "
        "GROUP BY surface, reject_reason ORDER BY n DESC LIMIT ?",
        ("-%d day" % int(days), int(limit)))]


def render(conn, days=7):
    """The table to read after a week of real use."""
    rows = summary(conn, days)
    out = []
    price = _prices()
    out.append("AI CALLS — last %d day(s)%s" % (days, "" if price else "   (set LUMI_AI_PRICE_IN_PER_MTOK / "
                                                "LUMI_AI_PRICE_OUT_PER_MTOK to cost it)"))
    if not rows:
        out.append("  no calls recorded — either nothing ran, or the model is not live here.")
        return "\n".join(out)
    head = "%-20s %-22s %6s %8s %9s %8s %8s %9s" % (
        "SURFACE", "MODEL", "CALLS", "TOK IN", "TOK OUT", "AVG s", "MAX s", "ACCEPTED")
    out.append(head)
    out.append("-" * len(head))
    tin = tout = 0
    for r in rows:
        tin += r["tok_in"] or 0
        tout += r["tok_out"] or 0
        judged = (r["accepted"] or 0) + (r["rejected"] or 0)
        acc = "%d/%d" % (r["accepted"] or 0, judged) if judged else "—"
        out.append("%-20s %-22s %6d %8d %9d %8.1f %8.1f %9s" % (
            r["surface"], (r["model"] or "")[:22], r["calls"], r["tok_in"] or 0,
            r["tok_out"] or 0, (r["avg_ms"] or 0) / 1000.0, (r["max_ms"] or 0) / 1000.0, acc))
    out.append("-" * len(head))
    out.append("%-43s %6s %8d %9d" % ("TOTAL", "", tin, tout))
    if price:
        pin, pout = price
        out.append("estimated spend: £%.2f  (in %.2f/Mtok, out %.2f/Mtok)"
                   % (tin / 1e6 * pin + tout / 1e6 * pout, pin, pout))
    quiet = [s for s in SURFACES if not any(r["surface"] == s for r in rows)]
    if quiet:
        out.append("no calls from: %s" % ", ".join(quiet))
    rej = top_rejections(conn, days)
    if rej:
        out.append("")
        out.append("REJECTED OUTPUT (the model answered, the gate refused it)")
        for r in rej:
            out.append("  %-20s %3d x  %s" % (r["surface"], r["n"], (r["reject_reason"] or "")[:70]))
    return "\n".join(out)
