# -*- coding: utf-8 -*-
"""Render the handover Part B firewall review from the auto-classified config.

Reads data/market_position_config.json (`_part_b_review` + `metrics` + `_domains`)
and writes MARKET_POSITION_REVIEW.md — the risk-ranked list of ONLY the flagged
metrics, so David works top-down and stops when confident. Pure presentation;
changes nothing computed. Re-run after editing the config to refresh.

    python3 server/gen_market_position_review.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "data", "market_position_config.json")
OUT = os.path.join(ROOT, "MARKET_POSITION_REVIEW.md")


def cell(s):
    return (str(s) if s is not None else "").replace("|", "\\|").replace("\n", " ")


def main():
    cfg = json.load(open(CFG, encoding="utf-8"))
    pb = cfg["_part_b_review"]
    metrics = cfg["metrics"]
    directions, governance, class_edges = pb["directions"], pb["governance"], pb["class_edges"]

    n_total = len(metrics)
    n_feed = sum(1 for m in metrics.values()
                 if m["class"] in ("Level", "Provision") and m["direction"] == "higher_is_better")
    L = []
    L.append("# Market Position — firewall review (David)\n")
    L.append("Claude auto-classified all **%d** live metrics (handover Part A). The build runs "
             "on this auto-pass; **you refine the flagged subset below via hot-reload** — edit "
             "`data/market_position_config.json` and the engine picks it up, no rebuild, no gate "
             "(pre-launch).\n" % n_total)
    L.append("**Work top-down; stop when confident.** Priority of harm: **direction** (misleads) "
             "› **competitiveness** (skews the headline) › **class** (gauge in/out) › lens "
             "(cosmetic, not shown here). Only flagged metrics appear; everything else rides.\n")
    L.append("**To override:** edit the metric's entry in the config — `class` "
             "(Level/Provision/Practice/Design), `direction` (higher_is_better/lower_is_better/"
             "neutral, or null for Practice/Design). Tick `[x]` here when confirmed.\n")
    L.append("_Net effect of the auto-pass: %d higher-is-better Substance metrics feed the "
             "competitiveness gauge; Governance is out of the headline._\n" % n_feed)

    # ---- 1. DIRECTIONS (highest harm) ----
    L.append("\n## 1 · Directions to confirm  (%d) — do these properly\n" % len(directions))
    L.append("The only set that produces misleading output if wrong: a `lower_is_better` metric "
             "left on the default reads as an amber “gap” when it's actually favourable; a "
             "true `neutral` shown as a verdict becomes the CFO's amber flag. Confirm each.\n")
    L.append("| ✓ | Metric | Domain | What it measures | Proposed `direction` | Why flagged |")
    L.append("|---|--------|--------|------------------|----------------------|-------------|")
    order = {"lower_is_better": 0, "neutral": 1, "higher_is_better": 2}
    for r in sorted(directions, key=lambda r: (order.get(r["direction"], 3), r["domain"] or "")):
        L.append("| [ ] | `%s` | %s | %s | **%s** | %s |" % (
            r["id"], cell(r["domain"]), cell(r["text"]), cell(r["direction"]), cell(r["why"])))

    # ---- 2. GOVERNANCE carve-out ----
    L.append("\n## 2 · Governance carve-out  (%d) — one scan\n" % len(governance))
    L.append("Every Governance metric is **out of the headline** (`_domains.Governance."
             "competitiveness = false`): it shows favourable / context / differs, never a "
             "below/on/above verdict. Confirm this is the right set (nothing here should be "
             "competing on a market rate).\n")
    L.append("| ✓ | Metric | Proposed `class` | `direction` | What it measures |")
    L.append("|---|--------|------------------|-------------|------------------|")
    for r in sorted(governance, key=lambda r: r["id"]):
        L.append("| [ ] | `%s` | %s | %s | %s |" % (
            r["id"], cell(r["class"]), cell(r["direction"]), cell(r["text"])))

    # ---- 3. CLASS edge cases ----
    L.append("\n## 3 · Class edge cases  (%d) — confirm out of the gauge\n" % len(class_edges))
    L.append("The deliberate edge: metrics **measured** binary/numeric but classed by **meaning** "
             "as a Practice or structural Design — so they tag “differs” and stay out of the "
             "competitiveness verdict. Confirm none should actually be a Level/Provision in the gauge.\n")
    L.append("| ✓ | Metric | Domain | Type | Proposed `class` | What it measures |")
    L.append("|---|--------|--------|------|------------------|------------------|")
    for r in sorted(class_edges, key=lambda r: (r["domain"] or "", r["id"])):
        L.append("| [ ] | `%s` | %s | %s | **%s** | %s |" % (
            r["id"], cell(r["domain"]), cell(r["type"]), cell(r["class"]), cell(r["text"])))

    # ---- 4. everything else rides ----
    n_flagged = len({r["id"] for r in directions} | {r["id"] for r in governance} | {r["id"] for r in class_edges})
    L.append("\n## 4 · Everything else rides  (%d unflagged)\n" % (n_total - n_flagged))
    L.append("Obvious Level / Provision at `higher_is_better`, and all lens assignments, need no "
             "review — refine opportunistically later via hot-reload. The auto-pass errs toward "
             "**Approach / out-of-gauge** on ambiguity (safer than a false Level verdict).\n")

    L.append("\n---\n_Generated by `server/gen_market_position_review.py` from "
             "`data/market_position_config.json`. Re-run to refresh after edits._\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("[written] %s" % os.path.relpath(OUT, ROOT))
    print("  1. directions   %2d" % len(directions))
    print("  2. governance   %2d" % len(governance))
    print("  3. class edges  %2d" % len(class_edges))
    print("  unflagged       %2d / %d" % (n_total - n_flagged, n_total))


if __name__ == "__main__":
    main()
