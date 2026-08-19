# Data issues from David's review — inventory and plan

**Source:** 23 annotated cards (PDF, 2026-08-19) · **Status:** diagnosed, nothing written yet

Your 23 notes are samples of four distinct defects, not 23 separate ones. Measuring the bank
rather than the screenshots found the true extent: **38 options across 20 questions have zero
respondents**, out of 1,118 options (3.4%).

---

## Class 1 — an option that can never be chosen (2 options, 2 questions)

`REW263_BEN_DENTAL` and `REW263_BEN_CICOVER` each carry **"Not offered"** *and* **"Not
applicable"**. An org without dental cover answers "Not applicable" and is excluded from the
base — the card even says "of organisations with dental cover". So "Not offered" is a
duplicate of the NA state and is structurally unreachable: it will read 0% forever.

Your note on the dental card ("Numbers are wrong") is exactly this.

**Fix: remove the option — do NOT seed it.** Seeding would invent orgs that answered a
question they were excluded from.

## Class 2 — genuine seed gaps (36 options, 18 questions)

Reachable options that the seeded peer data never assigns. Worst first:

| question | scale |
|---|---|
| `RED_TERM_02` redundancy pay multiple | **6 of 6** substantive bands empty. 221 orgs answered; all sit in "Not applicable" (103) or "Varies by grade/tenure" (118) |
| `RED_TERM_03` weeks' pay cap | **7 of 7** bands empty, same 221 orgs, same shape |
| `REW_PAY_016` allowances | 5 empty: acting-up, homeworking, mobile/phone, market scarcity, none — **your page 1** |
| `REW_BEN_REM_PAY_001` remote base pay | 2 of 4 never used — **your page 5** |
| `RED_PAY_01` redundancy pay basis | "Includes variable pay", "Other" |
| `REW_BEN_048` income protection rate | `<50%` — **your page 10** |
| plus 12 more single-option gaps | see the full list below |

`RED_TERM_02` and `RED_TERM_03` are the serious ones: 221 organisations answered each, and
the questions still say nothing about actual redundancy terms.

## Class 3 — question wording (at least 3)

- p2 `Employees expectation to attend a workplace cadence` — ungrammatical, and the options
  are a frequency, so "cadence" is doing no work
- p3 `External pay/benefits benchmarking cadence` — titled a cadence, but the options are
  yes-formal / informal / none. Not a cadence at all
- p5 `Remote working base pay treatment` — you asked for the text and the answers to be checked

## Class 4 — coverage gaps (new capture)

- p6 last three years' headline pay increase + a 2027 projection — not currently asked
- p7 add "job adverts" and "ChatGPT" as benchmarking sources
- p12 "more to the list?"

These are new questions/options, which is a release operation, not a data repair.

---

## How these get fixed

The house mechanism is a dated `migrate_seedreal_*` script: dry-run by default, gated on
`--write --confirmed-by-david`, writing the DB **and** the CSV lineage in step for
CSV-locked questions (`ALLOW_*`, `PROP_*`). Fourteen of these already exist. Class 2 is
exactly what they are for, and `REW_PAY_016` (`ALLOW_01`) has been touched by one before.

Order I would take it in:

1. **Class 1** — remove two unreachable options. Smallest, and it stops a permanent 0%.
2. **Class 2, the two redundancy questions** — biggest honesty gap in the bank.
3. **Class 2, the rest** — one migration, count-conserving, sector-plausible.
4. **Class 3** — question text, needs your wording.
5. **Class 4** — new questions, a release.

Class 2 needs marginals that are *defensible*, not merely non-zero. Redundancy multiples and
weeks-cap distributions should follow known UK practice rather than be spread evenly, and
that is a judgement I would rather take from you than invent.

---

## Full Class 2 list

- **`PROP_36b990f9`** (n=267) — What was employer pension contribution as a typical percentage of pensionable 
  - `<3%`
- **`PROP_3d4fc4e7`** (n=240) — What proportion of employees actively enrol in at least one optional/flexible 
  - `Not measured`
- **`PROP_aa4061d5`** (n=243) — How does your organisation measure the effectiveness of reward/benefits commun
  - `No formal measurement`
- **`RED_PAY_01`** (n=204) — What pay basis is typically used to calculate redundancy payments?
  - `Includes variable pay (bonus/commission) where applicable`
  - `Other`
- **`RED_TERM_02`** (n=221) — What is the maximum redundancy pay multiple offered, excluding notice?
  - `Up to 1× weekly pay`
  - `More than 1× to 1.5×`
  - `More than 1.5× to 2×`
  - `More than 2× to 3×`
  - `More than 3× to 4×`
  - `More than 4×`
- **`RED_TERM_03`** (n=221) — What is the maximum number of weeks' pay used to calculate redundancy payments
  - `Up to 12 weeks`
  - `13–26 weeks`
  - `27–39 weeks`
  - `40–52 weeks`
  - `53–78 weeks`
  - `79–104 weeks`
  - `More than 104 weeks`
- **`REW263_INC_DEFERRAL`** (n=65) — For deferred bonuses, what is the typical deferral period and vehicle (cash vs
  - `No deferral`
- **`REW263_TIME_IVF`** (n=258) — How many funded IVF/fertility treatment cycles (or financial cap) do you provi
  - `2-3 cycles`
  - `Unlimited/uncapped`
- **`REW264_INC_EMICSOP`** (n=187) — Do you operate discretionary tax-advantaged option plans (EMI or CSOP)?
  - `Both`
- **`REW265_INC_SIPELEM`** (n=11) — If a SIP is offered, which elements are used?
  - `Dividend shares`
- **`REW_BEN_041`** (n=270) — What is the maximum additional leave that can typically be purchased per year?
  - `11+ days`
- **`REW_BEN_044`** (n=188) — What are the private medical insurance (PMI) eligibility rules?
  - `Service length requirement`
- **`REW_BEN_048`** (n=92) — If income protection is offered, what is the typical salary replacement rate?
  - `<50%`
- **`REW_BEN_100`** (n=270) — What proportion of employees are eligible for employer-funded PMI?
  - `<10%`
- **`REW_BEN_REM_PAY_001`** (n=123) — If an employee moves from office-based to remote working, how is their base pa
  - `Base pay may be adjusted over time`
  - `Base pay is adjusted immediately`
- **`REW_BEN_REM_PAY_005`** (n=223) — Do any pay premiums or discounts apply specifically to remote roles?
  - `Both premiums and discounts apply`
- **`REW_BEN_SICK_001`** (n=258) — How does your occupational sick pay compare to statutory sick pay (SSP)?
  - `No sick pay provided`
- **`REW_PAY_016`** (n=265) — Which allowances or premiums are currently paid?
  - `Market scarcity allowance`
  - `Acting-up allowance`
  - `Homeworking allowance`
  - `Mobile/phone allowance`
  - `None`

---

# Close-out: classes 6 and 7

Every remaining annotation in the PDF is now addressed. Twelve further findings, split across
two migrations, plus one structural finding that is David's ruling rather than a data fix.

Before any value moved, each question was checked against `frozen_targets.json` and the
`qa_plausibility` register. None of the twelve was anchored. (This check is here because it is
the one I skipped earlier today on `REW_BEN_REM_PAY_001`, which broke a frozen marginal by
15.2pp and was caught only by the freeze gate.)

## Class 6 — distribution shapes (`migrate_dataqa_c6_shape_corrections_2026_08_19.py`)

| Question | Was | Now | Why |
|---|---|---|---|
| `REW_PAY_020` p8 | all 7 levels at exactly 10% | 17% → 6% ladder | identical to the unit at every level is a generator artefact, not a finding |
| `REW_PAY_109` p17 | board/director/head all 44.4% | 72% → 1% ladder | a status car allowance is far more common at board than 44%, and three identical rungs is not a ladder |
| `RED_PROC_01` p16 | Yes 56% | Yes 76% | 39% with no documented redundancy process is not credible; basic employment-law hygiene |
| `REW_BEN_039` p20 | 35/33/32 three-way | Yes 40 · No 48 · in dev 12 | a third of the market "in development" is the least believable third of a three-way split |
| `REW_BEN_HOL_004` p21 | Yes 75.5% | Yes 44% | service-related leave is common, not near-universal |
| `REW_BEN_HOL_003` p22 | 27.5% could sell | 14% can sell, 38% buy-only | selling leave is rare; buying is not |
| `REW265_TIME_FLEXPATTERN` p23 | only 13.9% offered nothing | 31.8% | 86% offering a flexible pattern *as standard* overstates the market |

`RED_PROC_01`'s "Partially" option is `is_na=True`, so it was held at 11 rather than grown —
raising it would have shrunk the scored base instead of improving the card.

Housekeeping in the same migration: `migrate_dataqa_c4a` wrote `REW265_BEN_PMICOMP` with a
`"; "` join where the bank uses `";"`. Every aggregate split site strips, so no count was ever
wrong, but it was the only question stored that way and an exact-match query would have missed
those 180 rows. Normalised.

## Class 7 — the pages not previously mapped (`migrate_dataqa_c7_second_pass_2026_08_19.py`)

| Question | Was | Now | Why |
|---|---|---|---|
| `REW265_PAY_ACTINGUP` p4 | No 74.2% | No 36 · case-by-case 39 · formal 25 | an employer that asks someone to act up handles the pay somehow |
| `REW_BEN_038` p15 | cycle 50.0%, dental 38.1% | cycle 64.1%, dental 22.2% | cycle-to-work is a near-default salary-sacrifice scheme; dental is a bolt-on far fewer buy |
| `CAR_STATUS_01` p15 | Yes 32.1% | Yes 42.0% | stays coherent with the `REW_PAY_109` allowance ladder — car and cash allowance are alternatives offered side by side |
| `REW_BEN_FLEX_ALLOW_01` p13 | medians 2.1–2.7% | 3.2% → 9.0% | wrong twice: too low for a real flex allowance, and a 0.6pp spread across seven levels is not a by-level question |
| `RED_COST_01` p14 | `unit='GBP'` on a pay multiple | `unit='x'`, monthly basis stated | see below |

The flex-allowance rescale is **multiplicative within each level**, so every organisation keeps
its rank and its own cross-level shape; only the scale moves. n stays 196 and the payload shape
is byte-identical in structure (p50 = 9.0 exactly as targeted).

`RED_COST_01` was the only one of the twelve where the **distribution was fine and the labelling
was the defect** — and it was a real one. The options are pay multiples but `unit` and
`tolerance_json` both said `GBP`, so anything keying off unit would format a multiple as
currency; and the definition said "shown as a pay multiple" without ever saying a multiple of
*what*. Weekly, monthly and annual pay differ by roughly 50x here, which makes the card
unreadable. Now stated as a multiple of monthly base salary — the basis the existing
distribution is already drawn on.

## Already closed before this pass

- p11 critical illness "Not offered" at 0% — closed by class 1 (option removed)
- p18 / p19 redundancy multiple and weeks ladders — closed by class 2
- p9 pension `<3%` at 0% — deliberate: below the auto-enrolment minimum, so zero is correct

## OPEN — needs David's ruling, not a data fix

David (p9): *"Double check we have no overlaps in questions for pension contributions and caps
etc."* The sweep found two genuinely overlapping **pairs**:

**1. Allowance pensionability — fixed the symptom, the duplication is still there.**

| | |
|---|---|
| `ALLOW_03` | "Are allowances pensionable?" — whole-organisation, single-select |
| `REW_PAY_020` | "Allowances pensionability by level" — the same thing, per level |

These were actively **contradicting each other on screen**: `ALLOW_03` said 30% of employers
have some pensionable allowances while `REW_PAY_020` said 10% at every level. `ALLOW_03` is
aligned to the new ladder in class 7 so the two cards now agree (any-level-yes ≈ 24%), but a
member still answers the same question twice.

**2. Employer pension contribution — untouched.**

| | |
|---|---|
| `PROP_36b990f9` | "Employer pension contribution rate (Typical)" — banded, whole-organisation |
| `REW_BEN_112` | "Typical employer pension contribution by level" — per level |

The banded whole-org version is a degenerate copy of the matrix. This is the same shape as the
`PROP_634adacd` case in class 4b, where the ruling was **evolve, don't duplicate**.

I have not acted on either, because retiring or merging a question changes the refresh register
(currently 334), the scoring, and what members see — and the bank carries a contested
"retire, never delete" doctrine. Both are yours to rule on.

`REW_BEN_PENS_EMP_MAX_01` (maximum) against `REW_BEN_112` (typical) was also flagged by the
sweep and is **not** a duplicate — max and typical are different questions. No action.

## Verification

Both migrations were applied to a throwaway pair (SQLite backup API, not `cp`), re-aggregated,
and put through the full suite: **17/17 gates green**, including `qa_plausibility`, the
enforcing freeze gate. Then applied to the live DB and re-aggregated. 2,088 answers moved in
total, every question count-conserving.
