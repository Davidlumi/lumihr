# Seed-realism audit — full benchmark, 10-lens sweep (2026-08-10)

Ten independent auditor lenses over the live seeded benchmark (221 orgs, ~333
metrics, cut by sector and FTE band), each blind to the others, plus a
completeness critic. Every lens was primed with the known parsing traps and the
already-fixed list. Findings below are **deduped** across lenses and tagged with
verified constraint status:

- **free** — metric is in neither `frozen_targets.json` nor `generated_marginals.json`; values (even globals) may move.
- **marginal** — Tier-2 register marginal (±5pp); fixable only by sector/size reallocation that conserves the global.
- **frozen** — hand-ruled immovable global; fixable only by vector-swaps that conserve option counts exactly.

Confidence and the "already fixed" exclusions (car spread, Education LTIP, EMI
band, optical, EOT, EWA, profit-share, gender-pay-gap deferral) are respected.

---

## TIER 1 — Clear errors: internal contradictions & legal impossibilities
*Unambiguous. An analyst hits these on the first cross-tab. Recommend fixing now.*

| # | Finding | Metric(s) | Scope (verified) | Status |
|---|---------|-----------|------------------|--------|
| 1.1 | "Pension not offered" but org gives a 3–5% contribution in its own matrix — AE-impossible + self-contradiction | `PROP_36b990f9` | 14/14 orgs | free |
| 1.2 | "No sick pay provided" — SSP is mandatory for every UK employer | `REW_BEN_SICK_001` | 3 orgs | marginal (3-cell) |
| 1.3 | "Company-car-or-cash choice = Yes" while "no status car" | `CAR_STATUS_03` | 71 orgs | free |
| 1.4 | "None" co-selected with a substantive benefit | `REW_BEN_038` | 1 org | free |
| 1.5 | EAP: checklist disagrees with the (frozen) wellbeing EAP metric | `REW_BEN_038` vs `REW26_WEL_EAP` | 69 orgs | 038 free / WEL frozen |
| 1.6 | Benefits checklist disagrees with 6 mirrored standalone metrics 30–65% of the time (paternity, maternity, salsac car, life, PMI, EAP) | `REW_BEN_038` + parents | ~40–128 per benefit | 038 free |
| 1.7 | Tracks claims/utilisation for products the org doesn't hold | `REW263_WEL_DATA` | ~35 orgs | free |
| 1.8 | Mental-health support = "None" for orgs that hold an EAP (every EAP includes counselling) | `REW26_WEL_MH_SUPPORT` | 17–18 orgs | frozen (swap) |
| 1.9 | Recognition currency = "Not applicable" while org funds a recognition budget, measures impact, runs a platform | `REW263_REC_CURRENCY` | 42/45 orgs | free |
| 1.10 | Risk-benefit satellites claim cover the core life/IP metrics say is absent | `RISKFLEXUP`/`GIPREHAB`/`SPOUSELIFE` | 37 orgs | free (conserve `REW_BEN_046`) |
| 1.11 | PMI parents contradict the PMI cluster: 14 "Not offered" + 12 "All employees" | `REW_BEN_100`/`044`/`139` | 26 orgs | free |
| 1.12 | Enhanced-maternity org reports zero enhanced weeks | `REW_BEN_FAM_001` vs `FAM_002` | 25 orgs | both marginal (swap) |
| 1.13 | DB pension declared, but employer contribution is the 3% DC floor (real DB 19–29%) | `REW_BEN_112` (21 DB orgs) | 21/21 orgs | 112 free / type frozen |
| 1.14 | **Data bug:** build-tag strings (`"2026-07-18 diff15"`, `"tronc scope"`) sit in the `submitted_at` timestamp column | `answers.submitted_at` | 1,739 rows | bug |

---

## TIER 2 — Market calibration: off vs UK norms
*Real defects, but fixing them moves headline benchmark numbers → your sign-off.*

- **Life assurance under-seeded** (`REW_BEN_045`, free): 60% offer vs ~85–95% UK norm; *rarer than PMI*, which inverts a relationship every reward pro knows. 26% of 1,000–4,999 orgs have no life cover.
- **PMI over-seeded at small firms + zero all-employee schemes** (`REW_BEN_100/139/044`, free): 93% offer at 50–249 (norm ~35%); 0/154 frontline-eligible anywhere, even in Tech/FS/Prof-services where all-staff PMI is normal.
- **DB pensions**: contributions ~2× understated (see 1.13); **Education 0/10 DB** despite statutory TPS/USS (`REW26_BEN_PENSION_TYPE`, frozen → sector reallocation); public sector pension percentile mid-pack when it should lead.
- **Public sector should lead on pension/sick-pay/family/holiday and lags** (mixed free/marginal): 40% on SSP-only sick pay, 0 above 26 weeks (norm: 6 months full + 6 half); 7/15 zero enhanced maternity; 7/15 ≤24 days holiday.
- **Public sector PMI over-funded** (`REW_BEN_100`): 93% fund PMI (should be the "not offered" outlier).
- **Education runs broad bonus schemes** (`REW_INC_103`, free): 5/10 at 75%+ eligibility (schools/colleges on national pay frameworks don't).
- **Shift premium inverted** (`OT_04_b14623a6`, marginal): Tech 100% / Hospitality 27% (backwards).
- **Staff discount lowest in retail & hospitality** (`REW_BEN_038`, free): their signature benefit, seeded at the bottom.
- **Construction worst for death-in-service** (`REW_BEN_045`, free): 53% "not offered" vs CIJC-standard ~70–80% offering.
- **Salary-sacrifice cars 68% fuel-neutral** (`REW264_BEN_EVSALSAC`, free): the 2024–26 market is ~80–90% EV (BiK-driven); also over-prevalent at SMEs.
- **Dental seeded for only 11/220 orgs** (`REW263_BEN_DENTAL`, free): no negative class → unusable cut; needs ~209 orgs seeded.
- **Health cash-plan / virtual-GP size gradients off** (`REW264_HLT_CASHPLAN`, `REW264_HLT_VIRTUALGP`): cash plans absent in SMEs (where they live), 100% virtual-GP saturation at the top (register anchor is ~54%).
- **Benchmark sources single-source-heavy** (`REW_PAY_007`, free): 61% use one source; recruiter intel at 8% (norm ~35%).
- **Board *target* bonus hard-capped at 52%** (`REW_INC_111`, free): FS/listed exec target bonus reaches 60–100%+.
- **~10 size-gradient inversions** (mostly free, some marginal): bereavement support, allowance breadth, seasonal-peak pay, redundancy-fairness review, DEI pay analytics, benefit-utilisation tracking, remote-pay review, equal-value capability, EU-PTD prep, bereaved-partner paternity review-lag — all rise-with-size expectations currently flat or inverted.

---

## TIER 3 — Numeric texture: the data doesn't look human
*Values are individually in-range but distributionally synthetic. Larger, mostly mechanical regeneration; conserves medians/anchors.*

- **One identical pension ladder template across all 220 orgs** (`REW_BEN_112`, `PENS_EE_MAX_01`, `PENS_EMP_MAX_01`): fixed by-level offsets, **zero flat schemes** (most UK DC is a single rate). Also runs ~2× market at senior levels.
- **Target-bonus ladder is a fixed multiplier chain** (`REW_INC_111`): board/director ratio 1.333 (sd 0.017) — machine-tight, ~16% round-number heaping vs 98% on its own max-bonus sibling.
- **Salary-increase budget: uniform decimals, no .0/.5 heaping** (`PROP_9e4ad87f`): 2.9% is modal; real budgets pile on 3/3.5/4%.
- **Wellbeing budget: arbitrary pounds** (`REW26_WEL_BUDGET`): £113, £231 per head; real answers are £50/£100/£150/£200.
- **PMI premiums locked to exact 2.0×/2.5× tier ratios on a £20 grid** (`3faf1f0c…`).
- **Currency fields on fine generation grids** (cost/FTE £500-grid, allowances £50-grid, car allowance £250-grid): weak coarse round-number heaping — the inverse of human rounding.
- **Uniform-decimal % fields** (`REW26_BEN_PENSION_COST_SHARE`, `REW_BEN_FLEX_ALLOW_01`).
- **Timestamps are build-batched** (`answers.submitted_at`): 89,320 answers share **30 distinct values**; 220 unrelated orgs "answer" the same question in the same second. (Plus the 1,739 build-tag strings — bug 1.14.)
- **No partial-completer tail**: every org 88–97% complete, `drafts` table empty, `submission_complete=1` for all. Real panels have abandoners.
- **Response rate never reflects sensitivity**: disclosure items (ethnicity/disability pay-gap, pay-equity, RemCo sign-off) sit at 95–100%; real surveys see lower response on sensitive items.

---

## TIER 4 — Structural: the generation model itself (needs a ruling)

- **Single-latent over-coherence** *(highest structural lever)*: one hidden draw predicts every domain — health–family generosity correlate ρ=0.85; only 1/220 orgs is a "personality" outlier (≈14 expected). You can infer an org's maternity policy from its life-assurance multiple. Fix = multi-factor latent with per-domain noise + a handful of deliberate contrarians, implemented as within-metric rank reshuffles so **every anchor is conserved exactly**. A `MULTI_FACTOR_LATENT_SPEC.md` already exists in the repo.
- **FinWell register global looks jointly infeasible** with the frozen wellbeing incidence (`REW263_WEL_FINWELL`): 108 orgs run a programme but report "no provision". Needs a marginal ruling (same shape as gender-pay-gap).
- **Gender-pay-gap reporting** (`REW_FAI_079`): already deferred — statutory at 250+ but under-reported; marginal must move with the data.
- **Absolute £ magnitude calibration to 2026**: texture checks shape, not level. Pay-settlement budget centre (3.5%), PMI premium (£1,465 mean), cost/FTE (£45k) should be checked against 2026 references so the dataset isn't dated to the wrong year.
- **Ownership-type drives nothing** (`orgs.ownership_type`, fully populated): equity/pension should key on PLC (SAYE/SIP), VC/Founder (EMI), PE (lean+LTI), Charity/Public (no equity, better pension). Currently likely independent — cosmetic firmographic.
- **Declared positioning vs delivered generosity** & **take-up rates**: stated market stance and share-plan participation never cross-checked against realized reward.
- **Northern Ireland absent** from `hq_region` (minor coverage gap).

---

## Recommended sequencing

1. **Tier 1 now** — clear errors + the timestamp bug. Safe, high-confidence, mostly free metrics; the frozen/marginal ones fixed by conserving swaps. Verified on a throwaway with the full gate suite before live, per standing process.
2. **Tier 2** as a signed-off batch — it changes headline numbers, so worth a look before it lands.
3. **Tier 3** as a texture-regeneration pass (mechanical, conserves anchors).
4. **Tier 4** — rulings first (latent model, FinWell, gender-pay-gap, magnitude targets), then execute.
