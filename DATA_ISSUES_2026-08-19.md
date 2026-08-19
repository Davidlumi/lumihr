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
