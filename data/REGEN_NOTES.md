# Seed-data regeneration — notes & audit record

Date: 11 June 2026. Replaces the uniform-random answers in all 220 response files with
realistic, profile-driven synthetic data. **This is illustrative seed data, not real member
data** — labelled as such in the app (overview hero chip + methodology notice).

Code: `server/regen_priors.py` (priors, rationales, driver map),
`server/regenerate.py` (profile model + sampling engine),
`server/regen_validate.py` (validation gate). Machine-readable audit record incl. full
question lists: `data/regen_report.json`. Originals preserved in `data/responses_orig/`.

## Approach

Three tiers, per the brief:

1. **Curated priors — 109 questions** (52 selects, 11 multi-selects, 29 matrices,
   17 numerics): hand-written named-option weights / value ranges for the mainstream
   reward & HR mechanics members will sanity-check first (pay review cadence, pension,
   sick pay, holiday, probation, bonus prevalence, allowances, GPG reporting, hybrid,
   collective bargaining, turnover/absence bands, the by-level reward matrices, all 17
   numerics). Each carries a one-line rationale and a source class — published norms
   (ONS, gov.uk statutory duties, CIPD/XpertHR-style survey norms) or
   **"estimate"** where it is practitioner judgement; estimates are never presented as
   published statistics.
2. **Pattern templates — 398 selects**: questions whose option set forms a graded
   ladder (the library's own `option_scores` 0–100 scale with non-neutral polarity).
   Weights come from a good-practice adoption kernel centred by the org's latent
   maturity **F** (weak coupling for banded *metric* questions, full for
   practice/policy), so the aggregate leans middle-positive rather than uniform and
   every org's answers cohere with its profile.
3. **Skipped — 271 questions**: no defensible baseline and no ladder signal (mostly
   neutral-polarity "which approach" questions, niche multi-selects, the WEL_BMAP_*
   mega-lists, two non-curated matrices). Their previous generic answers are preserved
   unchanged and they are listed in `regen_report.json["skipped"]` for hand-curation.
   Zero questions were silently dropped.

## Profile model (the central requirement)

Per-org latent **formality/maturity F** = 0.40·HR_Maturity + 0.28·HR_Systems_Maturity +
0.20·FTE_Band + 0.12·Ownership_Type (+ small per-org noise), and **benefits richness R**
from Budget_Flexibility/size/ownership. F biases every template question and every
tilted curated question, so each company reads as one coherent entity; per-question
noise (σ≈0.16) keeps similar orgs different at the margin. 23 question-specific anchors
apply strong/deterministic profile conditioning. Within-org consistency is enforced by
shared latent state: one pension value drives the pension band *and* both pension
matrices; the allowance set drives ALLOW_01, REW_PAY_016 *and* the allowance-value
matrix; sick-pay yes/no gates the three sick-pay detail questions; bonus eligibility
gates the bonus/LTI matrices and bonus-measures multi; tronc gates its two dependents;
buy/sell leave gates the two purchase-cap questions; maternity enhancement gates the
weeks question.

**158 orgs generated profile-driven; 62 unmatched files baseline-only** (realistic priors,
mid-spread latent, no profile anchors), exactly per the brief.

## Driver map (curated questions — attribute → direction)

Selects (full rationale + source per question in `regen_priors.py` / `regen_report.json`):

| Question | Driver(s) |
|---|---|
| Pay review cycle | F/FTE_Band: small informal → ad hoc; large → Annually (80% baseline) |
| % received pay rise | Budget_Flexibility up → 95–100%; Public Sector/unionised → spine-point near-universal |
| Off-cycle increases | Turnover_Band high / Talent_Competition High → more off-cycle |
| Employer pension band | Ownership=Public Sector → 11%+ (DB); size/richness up; shares latent with pension matrices |
| Sick pay (4 questions) | F/size up → enhanced OSP; hospitality high-frontline → statutory-only; details gated on the offer |
| Probation length | Size up → 6 months; small → 3 months/varies |
| Gender pay gap analysis | **Deterministic-strength**: FTE 250+ → Yes ≈0.93 (statutory); <250 voluntary minority |
| Holiday entitlement | Public/Charity → 27–30+; small+Tight budget → statutory/21–24 |
| Buy/sell leave (+2 caps) | Size/F up → buy schemes; caps gated on scheme existence |
| Shutdown periods | Sector: Manufacturing/Construction → shutdowns ×3 |
| Bonus eligibility | Ownership: PLC/PE → broad; Public/Charity/Mutual → None ×5; gates all bonus matrices |
| EAP / MH support | Size/F up (near-universal in large employers) |
| Life assurance | Size/Budget richness up → offered, higher multiples |
| Pay ranges / job evaluation / refresh / benchmarking use (5 qs) | F strongly (formality scales with size+governance) |
| Pay transparency trio | F/size up; Public Sector → salary-on-advert standard |
| Collective bargaining (2 qs) | **Workforce_Unionised_%**: >40% → pay+core ≈0.82; <10% → No ≈0.92 |
| Absence bands (2 qs) | Workforce_Frontline_% + Public Sector up; one latent rate feeds both questions |
| Voluntary turnover band | **Registry Turnover_Band anchors the answer directly** |
| Early/90-day attrition | Scaled from the same turnover latent |
| Office attendance | Light only (hybrid 1–2/3+ days dominant per ONS-style norms) |
| Flexible working (2 qs) | F/size → formal policy; Frontline_% high → "some roles" |
| Overtime / TOIL | Workforce_Shift/Frontline_% high → pay overtime ≈0.9; Public/Charity → TOIL up |
| Maternity (3 qs) | Size/richness up → enhanced; weeks gated on enhancement |
| Salary sacrifice participation | FTE_Band up → offered + higher participation |
| Tronc (3 qs) | Sector: Hospitality → operated; everywhere else Not applicable; dependents gated |
| EAP utilisation | Light F (measurement) |
| PMI eligibility rules | Gated on PMI presence in benefits multi; classic grade-restriction |
| Long-service scheme (+ milestones multi) | Richness R; milestones gated on scheme |

Multi-selects: allowances (ALLOW_01/REW_PAY_016) — **Workforce_Shift_%** drives
shift/night/weekend/BH/on-call/standby/call-out; London HQ → location allowance;
low-frontline+richness → car/mobile. Benefits (REW_BEN_038) — all odds scaled by R, PMI
also by size and down for public sector. Union scope — unionised % decides recognition
and which groups. Pre-employment checks — right-to-work ≈1.0 (statutory), criminal →
Health/Education/Charity/Public, credit → Financial Services. Pay-budget factors —
NLW pressure from Frontline_%, union factor from Unionised_%. Outsourcing — payroll
share falls with size. Salary-sacrifice schemes — pension scales with size; childcare
vouchers low (closed to new entrants 2018).

Matrices: all by-level matrices ladder coherently (bonus Board>…>Frontline ~65→7% of
salary scaled by ownership; LTI top-levels only for PLC/PE/VC; notice 12wk Board→1–4wk
frontline with employer ≥ employee; agency % rises toward frontline scaled by shift%;
time-to-hire ~90→20 days; pension by level from the org latent; PMI premium
Single<Partner<Family; representation by sector gender mix with London ethnicity
weighting). Full per-matrix lines in `regen_report.json["matrix_drivers"]`.

Numerics: all 17 curated with ranges (engagement/eNPS from Employee_Voice/Advocacy;
salary-increase budget 2.7–5% from Budget_Flexibility; early attrition from
Turnover_Band; revenue/workforce-cost family sector-scaled — marked estimate).

## Validation gate — all green

- **Curated distribution table**: 52/52 pass (no modal-answer-at-~0%, no NA domination
  outside legitimately-conditional questions). Pattern heuristics: 0 near-uniform,
  0 NA-dominated → nothing moved to the skip list.
- **Profile spot table (20 orgs across the F spectrum)**: low-F (Basic/Spreadsheets)
  mean practice score 33.7 vs high-F 63.6 (PASS, no Basic/Spreadsheets org with a
  top-maturity profile); shift allowance offered by 73% of high-shift orgs vs 29% of
  low-shift (PASS); gender-pay-gap analysis Yes for 94% of 250+ orgs (PASS).
- **Before/after (10 headline questions)** — the bug is dead, e.g.:
  - Pay review cycle: Annually **0% → 82.7%** (was 43% "ad hoc", 50% "not applicable")
  - Employer pension band: 5–7% **0% → 45.2%**, 8–10% 0% → 24% (was 97% varies/NA)
  - Probation: 3 months **0% → 45.6%**, 6 months 0% → 32.1%
  - % receiving a rise: 95–100% 10% → 38.9% (modal), monotone-decreasing tail
  - Sick-pay waiting: statutory-only NA now 37% consistent with the OSP question
  - Allowances: shift allowance 81% (uniform artefact) → 46%, profile-correlated
- **Blank rate: 18.3% → 7.8%** overall (curated/template ~2–8% incl. Don't-know;
  numerics now answered ~92%; skipped questions keep their original treatment);
  required questions 100% answered.
- Platform verification suite after re-import: **37/37 pass** (medians re-verified by
  hand against the new files; suppression, tenancy, £-model all green).

## Labelling

- Overview hero: amber **"Illustrative sample data"** chip with plain-English tooltip.
- Methodology → "Who you're compared with": highlighted notice that the pool is
  synthetic seed data generated from published norms + firmographic profiles, pending
  real member submissions, and must not be cited as a market statistic.
- `synthetic_seed` flag stored in DB meta at import so the label is data-driven and can
  be switched off when real submissions replace the pool.

## Known items for hand-curation (logged, not hidden)

- 271 skipped questions (list in `regen_report.json["skipped"]`).
- The library's `option_scores` for a few cadence questions rank *more frequent* as
  *better* (e.g. pay-review frequency scores Quarterly above Annually), so an org doing
  the 83%-norm annual review shows a "Behind · P44" pill. That is the scoring config —
  out of scope here (no app/library changes) — but worth a curation pass on
  `scoring_config` for cadence-type questions.
- Baseline-only (unmatched) orgs have no firmographics, so their template answers are
  mid-spread by design; they remain excluded from filtered cuts as before.
