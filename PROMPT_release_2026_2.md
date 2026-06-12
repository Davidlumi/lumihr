# Build: release 2026.2 — forward-looking question additions — lumi

Add 12 forward-looking questions to the core as release **"2026.2"** on the versioning rails, from the authoritative file `lumi_release_2026_2_questions.csv`. These future-proof the catalogue against the 2026–27 regulatory and AI shifts (EU Pay Transparency Directive, Employment Rights Act 2025, AI-in-reward). This is a **pure-additions release: zero comparability breaks, zero retirements, no existing question reworded.** Apply from the CSV programmatically — do not invent questions. Precondition: 2026.1 is current; app runs; restart before gates. Commit in logical stages.

## What to add
- The 12 questions in `lumi_release_2026_2_questions.csv`, each with full schema: `id_hint` (assign a real id), `category`, `text`, `type`, `options`, `polarity`, `unit`, plus authored help text from the `help_why` column. Distribution: Governance 6, Pay 4, Time Off 2.
- **All 12 are `required=FALSE` and `scored=FALSE`** — exactly like the 2026.1 additions. They do NOT enter the required set, do NOT change the unlock basis (stays 82), and can never re-lock or gate anyone. They are optional, narrative/practice questions that benchmark on prevalence as data accumulates.
- They enter at `release_entered='2026.2'`, have no prior history (trend from 2026.2 onward), and render honestly in their n=0 state until 5+ orgs answer (the standard suppression floor + holding state).

## Why optional/unscored (context, so the rationale is preserved)
Several of these are deliberately ahead of the market (equality action plans, AI-in-reward governance, guaranteed hours) — many members genuinely won't have an answer yet. Making them required would (a) raise the basis and nag every member to complete questions that didn't exist when they joined, and (b) force answers on metrics that can't benchmark anything yet (n=0). They earn their way into the required set at a future annual review once they have data and the market has caught up — the governed-review mechanism, not on arrival.

## Execute as release 2026.2
- Run as a single release "2026.2" via the versioning system (`releases.create_release` or the established release path), on top of 2026.1. 2026.1 stays reconstructable; the baseline chain is intact.
- **Zero comparability breaks, zero retirements:** this release only ADDS. No existing question's text, options, version, scoring, or category changes. The change log should read: 12 added, 0 retired, 0 reworded.
- Snapshot the new questions into the release like any other; the as-of-date reconstruction must include 2026.2.

## Category counts after 2026.2 (verify against these exactly)
Pay 45 · Incentives 21 · Benefits 50 · Time Off 28 · Wellbeing 14 · Recognition 7 · Governance 41 = **206**.


## QA hardening (apply these — caught in review)
- **IDs are HINTS, not literals.** `id_hint` (e.g. REW262_GOV_ACTIONPLAN) is a suggestion — assign real ids that don't collide with any existing id and follow the established convention (the 2026.1 additions used REW26_*). Verify zero id collisions before applying.
- **'None' must score zero, never a point.** The action-plan multi_select has a 'None' option (marked `none_scores_zero=TRUE`). They're unscored now, but set 'None' as an na_code / zero-score in the definition so the engine-audit F1 defect ("None scored a point") can never reappear if they're scored later.
- **N/A path where 'not applicable' is real** (`na_handling=offer_na`): guaranteed-hours, cancelled-shift, and shift-notice need a 'Not applicable' answer for all-salaried / no-shift orgs — otherwise they're forced into a misleading 'No'. Give those a first-class N/A (counts as answered, excluded from prevalence), consistent with the 2026.1 N/A≠0≠blank handling. The rest (`na_handling=none`) are covered by their own No/Never option.
- **Polarity is deliberate.** 11 are higher_is_better; ONE is neutral (AI-skills premium — a practice, prevalence-only, no market verdict). Do not "correct" the neutral to higher_is_better — that would invent a false 'you're behind' verdict.
- **Option labels carry no delimiters.** Labels were rewritten so none contain commas or semicolons (the multi-select split-bug class). Keep it that way; store/split multi_select on the same convention the fixed engine uses.
- **Hero census will move by exactly these 12 — derive it, don't flag drift.** Adding 11 polarised + 1 neutral shifts the qa_hero positionability census (as 2026.1 moved 87→98). The release must DERIVE the delta and show it equals these 12 additions, so qa_hero's change is accounted, not a false fail or a masked shift.

## Must not change
- All existing 194 questions: text, options, polarity, scoring, category, version — untouched.
- Aggregation, suppression, polarity, the matrix/multi-select fixes, the unlock gate (basis stays 82), versioning rails, pulses, bespoke, roles/tenancy, trust labels, design.
- No existing metric's computation or value changes. This is purely additive.


## Seed synthetic answers (firewall-compliant) — run AFTER the release is in
Generate synthetic responses for the 12 new questions so they benchmark (instead of sitting at n=0) for the demo. Use the provided `seed_release_2026_2.py`. This follows the same integrity firewall as the documented REW_INC_072 / pay-frequency regenerations — do NOT deviate from it:
- **David-signed baselines** are the documented distributions in the script's CONSTANTS block (grounded in 2026 research). Direction and targets are settled; do not invent new ones.
- **Conditioned on firmographics only** (frontline %, shift %, size, HR maturity, sector, ownership) — map the script's `firmo_flags` field names to the real registry (`sim_feature_space`). No per-org hand-tuning, no demo-org special-casing.
- **Calibrate to baseline (REQUIRED):** run the script's `calibrate()` loop against the REAL registry so each question's REALISED distribution lands within tolerance of David's signed baseline (the pay-frequency pattern — "first draw off, tilt coefficients reduced, re-drawn"). The baseline is the target the realised data must hit, not just a starting point. Print the realised vs signed distribution per question as proof.
- **Seeded + reproducible + org-blind:** seed = `f"{qid}|2026-06-12|{org_id}"`; the same rule runs for every org; re-running yields identical data.
- **offer_na routing:** the `na_rule` questions (guaranteed-hours, cancelled-shift, shift-notice) route inapplicable orgs (all-salaried / no-shift) to "Not applicable" — counts as answered, excluded from prevalence. Confirm the applicable-n is sensible (not all 220).
- **Double-guarded write:** the script only writes with `--write --confirmed-by-david`. Insert the generated answers into the CORE answer store for these 12 questions, then re-aggregate.
- **Integrity statement required:** confirm no existing metric was touched, no value hand-tuned, the demo org got no special treatment, and the realised distributions match the signed baselines (paste them).

## Verify (evidence required — real values/screens)
1. 12 new questions exist with complete valid schema (type/options/polarity/unit/help per the CSV), in the right categories; counts reconcile EXACTLY to Pay 45 / Incentives 21 / Benefits 50 / Time Off 28 / Wellbeing 14 / Recognition 7 / Governance 41 = 206.
2. **All 12 are optional + unscored:** the unlock basis is still 82; a fully-complete member is NOT made incomplete or re-locked by this release (show before/after — the sticky-unlock + unchanged-basis proof).
3. **Pure additions:** change log shows 12 added, 0 retired, 0 reworded; NO comparability breaks marked anywhere; every existing question's text/options/version/category is byte-identical to pre-2026.2 (independent diff).
4. New questions render honestly at n=0 (suppressed/holding state), trend from 2026.2, and show correct prevalence once 5+ orgs answer (prove a multi_select and a single_select aggregate correctly). The 'None' option scores zero if scoring is ever applied; the `offer_na` questions accept 'Not applicable' as a first-class answer (counts as answered, excluded from prevalence).
5. Release mechanics: 2026.2 is current; 2026.1 and 2025-baseline both still reconstruct; as-of-date includes 2026.2.
6. Hero census: the qa_hero positionability/polarised counts move by EXACTLY these 12 (11 polarised + 1 neutral), derived and shown — not a false fail, not a masked shift.
7. Regression: restart, then ALL gates green (qa_engine_audit, qa_integrity, qa_focus, qa_hero, qa_commentary, qa_release, qa_pulse) — confirming the existing catalogue and every engine path is untouched.
8. Seed integrity: realised distributions match David's signed baselines within tolerance (paste realised vs baseline per question); offer_na questions show a sensible applicable-n (salaried/no-shift orgs excluded as N/A); seed is reproducible (re-run → identical); demo org received no special handling; no existing metric changed.
9. Screenshots: a new Governance question (e.g. the equality action plan multi_select) now rendering a real prevalence distribution post-seed, the 2026.2 change log (12 added / 0 reworded), and the unchanged unlock basis.
