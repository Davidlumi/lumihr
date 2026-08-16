# Population-split benchmarking — decision spec (2026-08-16)

**Status: FOR DAVID'S DECISION — nothing here is built.**

## The finding

The practitioner panel's Head of Reward (retail plc): *"Pay is presented as one percentile
across 46 metrics for a workforce that is in reality bimodal — hourly store colleagues and
salaried head office… A single blended market position can read 'on market' while store rates
lag and head-office pay leads, which is exactly the failure mode this document exists to
catch."*

The reward document now **admits** this limitation on its Method page ("positions blend your
whole workforce… this document does not split them"). This spec is the decision about whether
to remove the limitation rather than admit it.

## What exists today

- Matrix metrics already carry a **level** dimension (Board/Exec … Entry), so pay by seniority
  splits; pay by **population** (store vs head office, hourly vs salaried) does not exist
  anywhere in the bank.
- `population_targets_json` captures **stated positions** for named populations in the strategy
  document — statements only, never evidenced, by design (no exec pay data; R-ruling 2026-08-15).
- Peer cuts slice by org attributes (sector, FTE band, group), never within-org populations.

## The three options

### A. Do nothing beyond the admission (today's state)
The Method page states the limitation. Zero cost, honest, and the document's credibility
survives — but the failure mode the Head of Reward named stays real for every retail,
hospitality and logistics member: the segment lumi most wants.

### B. A population dimension on answers (the full fix)
Add `population` ("all" | "frontline_hourly" | "salaried_office") to answers and payload
blocks, mirrored in aggregation and suppression.

- **Cost: large.** Touches the answer schema, `positions.py` aggregation, suppression
  (n-floors per population slice make thin data thinner — many splits will suppress),
  submission UI (members must enter twice), payload cache shape, and every gate that counts
  answers. A multi-session programme, and it doubles the ask on members' data entry —
  against the empty-state doctrine that got submission rates up.
- **Benefit: the blended-read failure mode dies** for the ~40 pay/hours metrics where it
  matters. Little value outside Pay and Time off.

### C. A frontline lens on EXISTING levels (the pragmatic middle)
No schema change. Designate, per org, which matrix **levels** are "frontline" (e.g. Entry +
Skilled for a retailer) in one org-level setting. The engine already has per-level values and
per-level peer blocks; a "frontline read" is a re-aggregation of rows the data already holds.

- **Cost: modest.** One org setting, one derived read in `positions.py`, one card on the Pay
  section ("your frontline levels read at the Nth percentile; salaried levels at the Mth"),
  suppression unchanged (level blocks already carry their own n).
- **Limitation: honest but imperfect** — levels are a proxy for populations (a store manager
  is salaried but frontline). The card must say it is a proxy.
- This also gives the **wage-floor risk** its missing number: frontline-level pay vs the
  floor, which the risk currently says lumi cannot see.

## Recommendation

**C**, next cycle, behind the existing rulings process: it converts the admitted limitation
into a proxy read using only data members have already entered, and it feeds the wage-floor
exposure with an actual figure. **B** only if population-level benchmarking becomes a selling
requirement — it is a bank-versioning programme (question_version + historical_comparability
already exist to support it) and should be priced as one.

## Decision needed from David

1. A / B / C (and if C: the default frontline-level mapping per sector, or org-chosen only).
2. If C: does the frontline read appear in the client document, or in-app only until proven?
