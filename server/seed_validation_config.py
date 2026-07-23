# -*- coding: utf-8 -*-
"""Seed data/validation_thresholds.json — the soft-warn guardrail config.

PHILOSOPHY (submission guardrails, 2026-06-12): soft warnings, never hard
plausibility blocks. A member must always be able to enter their real value,
however unusual. The ONLY hard blocks are malformed input (text in a number
field) and true floors where below is meaningless (negative bonus %, negative
headcount). Everything else warns + allows + logs.

The library's tolerance.hard_min/hard_max were authored as plausibility caps,
several of them too tight for real reward data (a 0-100 cap on exec bonus %
blocks a real 150% package). This script seeds them as SOFT-WARN thresholds
instead, WIDENING the known-too-tight ones. The output file is DAVID'S CONFIG:
he edits the JSON directly (it hot-reloads — no restart); re-running this
script REGENERATES it from the library + these rules, overwriting his edits,
so only re-run it to rebuild from scratch.

Because thresholds only ever warn, a slightly-wrong one costs a single extra
"is that right?" click — err generous, never tight.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                   "validation_thresholds.json")

# Widening rules, first match wins (pattern on the display title).
# (soft_min, soft_max, why)
WIDEN = [
    (r"market median|market pos", (60, 150,
        "stores % of market median (~100); the library 0-100 cap would warn on every above-median payer")),
    (r"\blti\b|long.term incentive", (None, 400,
        "senior LTI routinely 150-300%+ of base; library cap 100 far too tight")),
    (r"bonus", (None, 250,
        "exec bonus opportunity can exceed 100% of base; library cap 100 too tight")),
    (r"pension contribution", (None, 40,
        "UK employer/employee pension rarely >30% but possible; library cap 100 uselessly loose as a warn")),
    (r"salary increase budget", (None, 15,
        "pay budgets almost always <15%; tighter warn catches the 100-for-1.0 class of typo")),
    (r"medical insurance|\bpmi\b", (None, 6000,
        "GBP per employee per year; generous so senior-heavy books don't false-warn")),
    (r"car allowance", (None, 30000,
        "GBP per year; generous high end for executive schemes")),
    (r"payment for each allowance", (None, 30000,
        "GBP per year; covers London weighting / on-call at the generous end")),
    (r"cost per fte|cost per employee", (None, 250000,
        "GBP per year; generous for professional-services books")),
    (r"flexible benefits", (None, 30,
        "% of base; flex pots rarely exceed 10-15%")),
    (r"% of revenue|% of payroll|% of base|% of salary|rate\b|proportion|share\b|representation",
        (None, 100, "a percentage share; >100 is almost surely a typo — but still only a warn")),
]

# Matrices where the value is expected to CLIMB with seniority — an inversion
# (a junior level above a senior one) gets a soft warn. ONLY bonus / LTI /
# pension / notice (the brief's list). Never flat-by-design matrices
# (allowances pensionability, eligibility, tronc, overtime, multipliers).
MONOTONIC_SENIORITY = {
    "323ffcf1-749b-43f3-bf34-1de6b8b1ca67",  # Maximum bonus % by level
    "REW_INC_111",                            # Target bonus % by level
    "REW_INC_LTI_MAX_01",                     # Max LTI % by level
    "REW_INC_LTI_VALUE_TYP_01",               # Target LTI % by level
    "REW_BEN_112",                            # Typical employer pension % by level
    "REW_BEN_PENS_EE_MAX_01",                 # Max employee pension % by level
    "REW_BEN_PENS_EMP_MAX_01",                # Max employer pension % by level
    "b1785613-96ed-4a64-9fd7-762d0ac65f19",   # Employee notice period by level (banded)
    "REW_Q524161",                            # Employer notice period by level (banded)
}

# "Max can't sit below typical/target" pairs — same row, soft warn.
MAX_OF = {
    "REW_INC_LTI_MAX_01": "REW_INC_LTI_VALUE_TYP_01",
    "323ffcf1-749b-43f3-bf34-1de6b8b1ca67": "REW_INC_111",
    "REW_BEN_PENS_EMP_MAX_01": "REW_BEN_112",
}


def numeric_kind(q):
    if q.type == "numeric":
        return True
    if q.type == "matrix":
        col = ((q.matrix or {}).get("columns") or [{}])[0]
        return col.get("type") in ("percentage", "currency", "number")
    return False


entries = {}
for qid, q in load_questions().items():
    if q.superpower != "Reward":
        continue  # nonrew-1: Reward-only product; non-Reward superpowers are out of scope
    is_num = numeric_kind(q)
    if not is_num and qid not in MONOTONIC_SENIORITY:
        continue
    tol = q.tolerance or {}
    title = (q.display_title or q.text or "")
    e = {"label": title, "unit": q.unit_block().get("symbol") or ""}
    if is_num:
        # Hard floor ONLY where the library floor is 0 (negative meaningless).
        e["hard_min"] = 0 if tol.get("hard_min") == 0 else None
        soft_min, soft_max = None, tol.get("hard_max")
        why = "seeded from library hard_max (now a warn, never a block)"
        for pat, (lo, hi, note) in WIDEN:
            if re.search(pat, title, re.I):
                # the generic %-share rule only applies to actual % fields
                if note.startswith("a percentage share") and e["unit"] != "%":
                    continue
                soft_min, soft_max, why = lo, hi, note
                break
        e["soft_min"], e["soft_max"] = soft_min, soft_max
        e["why"] = why
    if qid in MONOTONIC_SENIORITY:
        e["monotonic"] = "seniority"
    if qid in MAX_OF:
        e["max_of"] = MAX_OF[qid]
    entries[qid] = e

config = {
    "_readme": [
        "Soft-warn thresholds for data entry. DAVID OWNS THESE NUMBERS.",
        "Crossing soft_min/soft_max shows 'is that right?' — it NEVER blocks; confirmed values save and are logged.",
        "hard_min is the only block (0 = negative impossible). Never add a hard plausibility cap here.",
        "monotonic:'seniority' warns when a junior level beats a senior one (bonus/LTI/pension/notice only).",
        "max_of:<qid> warns when this 'maximum' sits below its typical/target twin on the same level.",
        "Edits hot-reload (no restart). Re-running seed_validation_config.py REGENERATES this file from the library rules and overwrites manual edits.",
    ],
    "questions": entries,
}
with open(OUT, "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print("wrote %s (%d questions)" % (OUT, len(entries)))
for qid, e in entries.items():
    if e.get("soft_max") is not None and "widened" not in e.get("why", "") and "seeded" not in e.get("why", ""):
        print("  %-40s soft %s..%s %s  (%s)" % (e["label"][:38], e.get("soft_min"), e.get("soft_max"), e.get("unit"), e["why"][:50]))
