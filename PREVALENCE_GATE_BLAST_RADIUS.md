# Prevalence-gate routing fix — blast-radius finding (read-only diagnosis)

**Date:** 2026-06-30 · **Status:** DIAGNOSIS ONLY — no fix applied · **Risk class:** engine-logic change (highest)

The proposed fix changes the prevalence-eligibility gate at **`server/positions.py:664`** to
route by **mp_config `class`** (`Practice`/`Design` → alignment; `Level`/`Provision` → position)
instead of legacy **`score_direction`**.

Numbers below come from a read-only simulation against the live DB
(`app.org_visible_questions` + `positions.market_position_config` + `aggregate.score_direction`),
Thornbridge as the reference org. The position pool is **unchanged** by this fix (it reads
`score_direction` nowhere — only line 664 does), so every move is within prevalence eligibility.

---

## 1. HEADLINE

The change affects **67 single_select/yes_no metrics across all 8 domains**, including
**5 COLLATERAL REGRESSIONS**. Split: **43 intended re-homes** (neither → alignment) +
**19 intended de-dups** (in BOTH pools → position-only) + **5 collateral** (alignment-only → NEITHER).

**Verdict: NOT a clean, contained fix.** It is far larger than the Pay-scoped picture
(Pay is only 15 of the 67), and it silently drops 5 metrics out of every rating pool.

---

## 2. THE 5 COLLATERAL REGRESSIONS  ← most important

All five are `single_select`, `class=Level`, `direction=neutral`, `score_direction=0`.
They are **banded "Level"-amount selects with no defensible rank**. Today the gate keeps them
in prevalence (because `score_direction==0`, so the exclusion clause doesn't fire), so members
see them as an **alignment** rating. Under the new gate: `class=Level` ⇒ excluded from prevalence,
AND `direction=neutral` ⇒ not position-eligible (position needs `higher_is_better`) ⇒ they fall
into **NEITHER pool** and lose their member-facing rating entirely. That silent drop is the regression.

| id | domain | current pool | would move to | why it's a regression |
|---|---|---|---|---|
| `RED_COST_01` | Benefits | alignment (prevalence) only | **NEITHER** | Level+neutral, no rank → dropped from both pools |
| `REW_PAY_HOURLY_MIN_1c6e096f` | Pay | alignment (prevalence) only | **NEITHER** | Level+neutral, no rank → dropped from both pools |
| `PROP_634adacd` | Pay | alignment (prevalence) only | **NEITHER** | Level+neutral, no rank → dropped from both pools |
| `EXT_REW_GAP_002` | Recognition | alignment (prevalence) only | **NEITHER** | Level+neutral, no rank → dropped from both pools |
| `EXT_REW_GAP_007` | Recognition | alignment (prevalence) only | **NEITHER** | Level+neutral, no rank → dropped from both pools |

---

## 3. INTENDED RE-HOMES (Pay)

**7 Pay Practice metrics that SHOULD move neither → alignment** (the fix's actual target):
`ALLOW_02`, `ALLOW_03`, `REW_FAI_CANCEL_1bbcc629`, `REW_FAI_MIN_HOURS_8518a543`,
`PROP_168a6213`, `PROP_8e0b6316`, `PROP_fe1a29ec`.

**6 Pay overlaps that de-dupe (in BOTH pools → position-only):**
`REW_BEN_058`, `REW_BEN_REM_PAY_005`, `REW_PAY_011`, `REW_PAY_TIPS_EXIST_7c80c508`,
`REW262_PAY_CANCELLEDSHIFT`, `REW262_PAY_SHIFTNOTICE`.

**Pay post-fix arithmetic:** position 12 (unchanged) · alignment 35 − 6 dedup − 2 collateral + 7 re-home = **34** ·
overlap 6 → **0** · distinct-rated **46** (12+34) · neither 18 − 7 + 2 = **13** · 46 + 13 = **59** ✓
(closes cleanly — but 2 of those 13 "neither" are the wrongly-dropped collateral pair).

---

## 4. CROSS-DOMAIN BREAKDOWN OF THE 67

| domain | total moved | re-home (→alignment) | de-dup (→position-only) | COLLATERAL (→neither) |
|---|---:|---:|---:|---:|
| Benefits | 15 | 10 | 4 | 1 (`RED_COST_01`) |
| Governance | 13 | 13 | 0 | 0 |
| Incentives | 3 | 0 | 3 | 0 |
| Pay | 15 | 7 | 6 | 2 (`REW_PAY_HOURLY_MIN_1c6e096f`, `PROP_634adacd`) |
| Recognition | 3 | 0 | 1 | 2 (`EXT_REW_GAP_002`, `EXT_REW_GAP_007`) |
| Time Off | 15 | 13 | 2 | 0 |
| Wellbeing | 3 | 0 | 3 | 0 |
| **TOTAL** | **67** | **43** | **19** | **5** |

Note: the 43 re-homes are a large *intended* member-facing shift in their own right — every
domain's alignment donut + AI summary + per-card prevalence band changes, not just Pay. Governance
and Time Off each gain 13 re-homed practices; Benefits gains 10.

---

## 5. THE OPEN AUTHORITY QUESTION

**No written ruling exists** that mp_config `class` supersedes `score_direction` for *pool routing*.
- mp_config `class` IS the David-curated authority for the **position gauge** ("class = gauge in/out",
  per `gen_market_position_config.py` docstring; Part B firewall review).
- The prevalence gate's `score_direction` check **predates** the mp_config wiring (mp_config was a later handover).
- The DECISIONS.md "routing consistency sweep" (~line 1134) is about **chart display**
  (chartAlternatives / OptionBars), **not** pool eligibility.

⇒ Aligning the prevalence gate to mp_config is a *logical consistency* change, but it changes
member-facing pool membership and is therefore an **unsettled product decision — David's call**,
not a mechanical bug-fix.

---

## 6. `score_direction` READER MAP

The fix changes only **how `positions.py:664` uses** `score_direction` — it does NOT change
`score_direction` itself. Therefore scoring and signals are untouched. Surgical to the
prevalence donut / AI-summary / per-card-band surface only.

| reader | file:line | role | touched by fix? |
|---|---|---|---|
| `score_direction` definition | `aggregate.py:262/267` | — | no |
| maturity score / `score_polarity` | `aggregate.py:308, 328` | **SCORING** | **no** (score_direction unchanged) |
| **the prevalence gate** | **`positions.py:664`** | **prevalence eligibility** | **YES — the one line** |
| position pool | `positions.py` (none beyond :664) | position eligibility | no (reads class/polarity, not score_direction) |
| signals | `signals.py` (none) | signal firing | no (builds own adoption pool via `prevalence_floor`/`_market_adoption`) |
| config generator | `gen_market_position_config.py:166,215` | offline | no |
| seed regeneration | `regenerate.py:157` | offline | no |
| test harnesses | `qa_hero.py:85/87`, `qa_phase1.py:148/151`, `qa_phase3.py`, `qa_scores.py` | tests | no |

`prevalence_items` consumers (the actual blast surface): `app.py:1416` (per-card band),
`1521/1545`, `1679/1688`, `1763/1770` (overview/hero), `3832` (domain-summary payload).
None of these are scoring or signals.

---

## 7. STANDING DECISION (verbatim)

> The prevalence-gate fix is NOT clean — 5 collateral regressions. Do NOT apply the global gate
> change. Options for a future pass: (a) David rules on each of the 5 collaterals individually, or
> (b) a narrower fix that re-homes the 7 Pay Practice metrics WITHOUT a global gate change.
> Engine-logic change — highest risk class. Diagnosis only; no fix applied.

---

## Working-tree note

The only tracked change on disk is `.claude/launch.json` (+2/−1) — the local-only master-on demo
env from a prior session (uncommitted, push-safe). All diagnosis here was read-only `python3 -c`;
**nothing was written by the simulations**. The large untracked line-count a GUI may show
(+21,726/−525) is the pre-existing untracked files at repo root (handover HTML/JSON, brand kit,
draft docs — the `??` entries in `git status`), not output of this analysis. Nothing to revert.
