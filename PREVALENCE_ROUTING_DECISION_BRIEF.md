# Prevalence/position routing — authority decision brief

**For:** David · **Date:** 2026-06-30 · **Status:** DECISION REQUIRED — neutral assembly, no fix proposed, no option recommended
**Read first:** `PREVALENCE_GATE_BLAST_RADIUS.md`; DECISIONS.md entries dated 2026-06-30 (prevalence-gate blast-radius diagnosis; Pay-denominator honest-header interim).

---

## THE DECISION

> **Should the prevalence/position pool-routing gate read mp_config `class` as the authority, instead of the legacy `score_direction` proxy?**

Today the gate at `server/positions.py:664` excludes a metric from the **alignment** (practice-prevalence) pool when `polarised AND is_scored AND score_direction != 0`. For `class=Practice` metrics that test is wrong — a metric can score directionally **and** be a practice that belongs in alignment. Routing on mp_config `class` is the only correct fix, but it is **global** (engine logic; 67 metrics move across 6 domains) and **no DECISIONS.md entry has ever ruled that mp_config supersedes `score_direction` for routing.** That ruling is the decision. Nothing below recommends an answer.

---

## 1. The question in plain terms

The engine carries two different per-metric facts that were built for two different jobs:

- **`score_direction`** (derived in `aggregate.py`) exists for **scoring** — it tells the maturity score which way is "better" so a "Yes / reviewed / annually" answer earns points. It is computed from the answer-option text.
- **mp_config `class`** (in `data/market_position_config.json`, curated by you in the Part B firewall review) exists to drive the **position gauge** — `Level`/`Provision` = a quantity/provision that can sit *above or below market*; `Practice`/`Design` = an *approach* with no better/worse.

The routing gate currently uses the **scoring** fact (`score_direction`) to decide a **placement** question (which pool a metric belongs in). That is the conflation: a practice question like *"Are allowances reviewed regularly?"* legitimately has a scoring direction (Yes is more mature) **and** is an approach that belongs in alignment — but the gate sees `score_direction ≠ 0` and evicts it from alignment, while mp_config (`class=Practice`) says it was never gauge-eligible, so it lands in **neither** pool. The curated authority (`class`) and the scoring proxy (`score_direction`) disagree, and **no written ruling says which wins for routing**:

- The 2026-06-30 **blast-radius** entry records explicitly: *"NO written ruling exists that mp_config class supersedes score_direction for POOL routing; mp_config class is the curated authority for the POSITION gauge only, and the prevalence gate's score_direction check predates the mp_config wiring."*
- The 2026-06-30 **honest-header** entry records the gap as *"OPEN as David's mp_config-authority decision."*
- The earlier "routing consistency sweep" in DECISIONS.md concerns **chart display**, not pool eligibility.

So the authority question has been surfaced twice and ruled on zero times. This brief is to close it.

---

## 2. The 43 re-homes — metrics the ruling would move into alignment

These are answered `single_select`/`yes_no` metrics that mp_config classes **Practice/Design** but the `score_direction` proxy currently excludes from alignment — so they sit in **neither** pool today (and the honest-header keeps disclosing them as "not yet rated"). Under **"mp_config governs"** they enter **alignment**; under **status quo** they stay in neither.

| domain | re-homes | examples (id — text) |
|---|--:|---|
| Governance | 13 | `PAYTR_03_db0108d6` — *Is there a formal policy describing pay progression within bands?* · `REW_FAI_079` — *Does your organisation conduct gender pay gap analysis at least annually?* |
| Time Off | 13 | `REW_BEN_FAM_007` — *Do you provide paid carer's leave…?* · `REW_BEN_FAM_008` — *Do you provide paid emergency or compassionate leave?* |
| Benefits | 10 | `RED_PROC_01` — *Is there a documented redundancy process applied consistently?* · `RED_PROC_02` — *Are selection criteria for redundancy documented and objective?* |
| Pay | 7 | `ALLOW_02` — *Are allowances reviewed regularly…?* · `REW_FAI_CANCEL_1bbcc629` — *Are hourly workers paid if scheduled shifts are cancelled at short notice?* |
| **Total** | **43** | across 4 domains |

*Number note:* the 43 is the count of metrics that would **gain an alignment rating**. An earlier Pay-narrow diagnostic counted **42** under a slightly different lens (`class=Practice` metrics excluded by the gate's `score_direction` test: Pay 7, Governance 13, Benefits 9, Time Off 13). The two differ by one Benefits `Design`/neutral-polarity practice that the gate-exclusion lens doesn't capture but is still a neither-pool practice. Both describe the same conflation; **43** is the precise re-home set.

The full set of metrics whose **routing changes** under the ruling is **67**: **43 re-home** (neither → alignment), **19 de-dup** (currently in *both* pools → position-only, removing a double-count), **5 collateral** (alignment-only → neither — see §3). This matches the blast-radius finding, re-verified live.

---

## 3. The 5 contested `Level` metrics — verdict flips on the ruling

All five are `single_select`, mp_config `class=Level`, `type=ordinal`, mp_config `direction=neutral`, engine `score_direction=0`, currently **alignment-only**. Under a class-based gate, `class=Level` evicts them from alignment; with `direction=neutral` they are not gauge-eligible, so they fall to **neither**. Whether that is a *correct removal* or a *regression* depends on the ruling:

| id | domain | text | DB polarity | mp_config dir | clean / contestable |
|---|---|---|---|---|---|
| `PROP_634adacd` | Pay | *typical (median) base salary increase* | **neutral** | neutral | **CLEAN** — both sources agree neutral |
| `RED_COST_01` | Benefits | *average redundancy cost per employee* (× salary) | higher_is_better | neutral | contestable (lean neutral — cost is double-edged) |
| `REW_PAY_HOURLY_MIN_1c6e096f` | Pay | *lowest base hourly rate paid* | higher_is_better | neutral | **contestable** (see §4) |
| `EXT_REW_GAP_002` | Recognition | *typical value of an individual recognition award* | higher_is_better | neutral | **contestable** (see §4) |
| `EXT_REW_GAP_007` | Recognition | *typical value of a long service award* | higher_is_better | neutral | **contestable** (see §4) |

**The flip, stated explicitly:**
- **If mp_config `direction=neutral` governs** → none has a defensible rank → all 5 leave alignment and land in **NEITHER** (lose their member-facing rating). For `PROP_634adacd` this is uncontested; for the other four it is a *consequence of trusting the neutral curation over the DB polarity*.
- **If DB-polarity / real-nature governs** → the four `higher_is_better` metrics have a defensible direction → their correct home is the **POSITION gauge** (they sit in alignment today only because `score_direction=0` from a label-heuristic gap). `PROP_634adacd` stays neutral under either reading → NEITHER.

So the ruling does not merely re-home practices; it also decides whether these five are *correctly dropped* or *wrongly dropped*. One (`PROP_634adacd`) is clean; the other four hinge on §4.

---

## 4. The 3 directional amounts — reward-judgment calls only David can make

For three of the contested five, the question is a **reward judgment**, not an engine fact: *is a higher value genuinely BETTER (→ position-gauge eligible) or just BIGGER/contextual (→ not gauge-eligible, belongs in alignment or neither)?* The DB says `higher_is_better`; mp_config says `neutral`. **This brief does not answer these — they are your call**, and answering them is **orthogonal to the gate change** (it is about correcting each metric's *direction* so it can reach the gauge, a separate edit from the routing authority).

| id | reward question | case for "better → gauge" | case for "just bigger → not gauge" |
|---|---|---|---|
| `REW_PAY_HOURLY_MIN_1c6e096f` | Is a **higher lowest hourly rate** a better market position? | A higher pay floor is unambiguously more generous and compliance-safe — clearly above/below market. | It is a level set by sector/geography/role mix; "higher" isn't strategy, and a low floor can be a deliberate mix choice. |
| `EXT_REW_GAP_002` | Is a **bigger individual recognition award** better? | More £ per award = more generous recognition spend — a positionable level. | Recognition *effectiveness* isn't £-value; bigger is just costlier, not better — contextual. |
| `EXT_REW_GAP_007` | Is a **bigger long-service award** better? | Larger milestone award = more generous — above/below market reads naturally. | Award size reflects tenure policy and demographics, not quality; bigger ≠ better. |

(`RED_COST_01` sits adjacent: redundancy cost is double-edged — generous severance vs. inefficiency — which is why mp_config's neutral is the easier call there. `PROP_634adacd` needs no judgment: a median pay-increase % has no defensible "better.")

---

## 5. What each ruling implies (computed, neutral)

Post-ruling member-facing counts, computed live for Thornbridge (all-peers). Under **Ruling A**: the 43 re-home into alignment, the 19 de-dups leave alignment for position-only (no longer double-counted), the 5 collateral leave alignment for neither. The **position pool is unchanged** by the ruling (it reads `class`/direction, never `score_direction`). "rated" = distinct metrics with a position **or** alignment read; "not rated" = neither pool.

| domain | N | — current — pos / align / rated / **not-rated** | — Ruling A — pos / align / rated / **not-rated** |
|---|--:|---|---|
| Pay | 59 | 12 / 35 / 41 / **18** | 12 / 34 / 46 / **13** |
| Benefits | 56 | 14 / 23 / 33 / **23** | 14 / 28 / 42 / **14** |
| Governance | 50 | 0 / 32 / 32 / **18** | 0 / 45 / 45 / **5** |
| Time Off | 36 | 9 / 13 / 20 / **16** | 9 / 24 / 33 / **3** |
| Incentives | 21 | 7 / 13 / 17 / **4** | 7 / 10 / 17 / **4** |
| Recognition | 11 | 2 / 9 / 10 / **1** | 2 / 6 / 8 / **3** |
| Wellbeing | 10 | 3 / 7 / 7 / **3** | 3 / 4 / 7 / **3** |
| **Platform** | **243** | rated 160 / **not-rated 83** | rated 198 / **not-rated 45** |

**Ruling A — "mp_config class governs routing"**
- The 43 re-home to alignment (the real fix); platform "not yet rated" falls **83 → 45**.
- The 5 contested resolve per their class (Level → out of alignment); `PROP_634adacd` cleanly to neither, the other four per your §4 call.
- **Recognition is the one domain that gets *worse*** (rated 10 → 8, not-rated 1 → 3): it has 0 re-homes but loses 2 collateral (`EXT_REW_GAP_002/007`) + 1 de-dup. Worth seeing before ruling.
- De-dup removes the 19 double-counts so the alignment donut stops over-stating (e.g. Pay alignment 35 → 34, but rated rises because re-homes outweigh).
- **Risk class:** engine-logic change, global, highest-risk per project convention. Needs its own diagnose → apply → platform-wide QA pass (qa_hero / qa_release / qa_domain_summary / qa_overview), not a quick edit.

**Ruling B — "keep status quo, disclose only"**
- The honest-header interim (already shipped, commit `0795436`) stands; every domain header reconciles ("N benchmarks · R rated · X not yet rated").
- The 43 stay in neither pool; platform "not yet rated" stays **83**. No engine change, no risk.
- The routing conflation persists as **known-and-disclosed debt**.

**Ruling C — "split authority" (a real, narrower option)**
- mp_config `class` governs only the **Practice/Design → alignment** direction (re-home the 43, which is uncontested in nature), while **Level/Provision** routing continues to defer to `score_direction`/polarity (leaving the 5 contested where they are today, in alignment, pending your §4 direction calls).
- Effect: gains the 43 re-homes and the de-dup correctness, **without** dropping the 5 collateral to neither — it sidesteps the contested flips. Still an engine-logic change (smaller blast radius), still needs a QA pass. Listed because it is genuinely available, not to pad the choice.

---

## 6. What is NOT being decided here (scope guard)

- This brief decides **routing authority only** — whether the gate should read mp_config `class`.
- It does **not** decide the **3 amounts' direction** (§4) — that is a separate reward judgment, and correcting those directions is a different edit from the gate change.
- It does **not** authorise any engine change. Ruling A or C would each require a **later diagnose → apply → platform-QA pass**, scoped and reviewed on its own. A ruling here is a *direction*, not a green light to edit `positions.py`.

---

## Decision required

1. **Routing authority: A, B, or C?**
   - **A** — mp_config `class` governs routing (global re-home of 43; 5 contested resolve per class; engine pass to follow).
   - **B** — status quo + honest-header disclosure only (no engine change; conflation stays as disclosed debt).
   - **C** — split authority (Practice/Design → alignment now; Level/Provision keeps deferring to score_direction; contested five untouched).
2. **The 3 amounts** (`REW_PAY_HOURLY_MIN_1c6e096f`, `EXT_REW_GAP_002`, `EXT_REW_GAP_007`): for each — **better → gauge**, or **just bigger → not gauge**?

*No fix is proposed and no option is recommended. All numbers are read-only from the live DB/engine; nothing in the repository was modified by assembling this brief.*
