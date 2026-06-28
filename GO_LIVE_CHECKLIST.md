# AI Insights — Go-Live Checklist

**Status: solicitor sign-off RECEIVED (2026-06-28). Prep complete. ONE step remains — David's
production env flip.** The lawful basis is **legitimate interest (opt-out)** with an LIA on file;
the legal text is finalised, Anthropic is named as the AI sub-processor, and the terms version is
`1.0`. The master gate `AI_INSIGHTS_ENABLED` is still **default-OFF in code** as a backstop, so
**no real member sees any AI-generated content** until the single env flip below.

## How the gate works (unchanged)

Any AI feature renders **iff all three are true**:

1. `AI_INSIGHTS_ENABLED` (the master switch) is **on**, AND
2. that feature's own kill-switch is on (`LUMI_AI_COMMENTARY`, `LUMI_AI_ANALYST`,
   `LUMI_AI_BOARDPACK`, `LUMI_AI_PULSE`, `LUMI_AI_STRATEGY`, `LUMI_AI_DOMAIN_SUMMARY`), AND
3. the **member has not opted out** (`AI_CONSENT_MODE=opt_out`: on by default; a member who turns
   AI Insights off in Settings records `kind="ai_insights_withdrawn"` and goes dark next request).

Under opt-out, flipping the master on exposes AI Insights to every member who has **not** opted
out — including members who joined before the feature existed (they are informed at signup / in the
privacy notice, and can opt out any time). Each member's choice is recorded per-person in the
`terms_acceptances` audit log, versioned to `AI_TERMS_VERSION` (`1.0`).

## What was done on sign-off (steps 1–4 — COMPLETE)

1. **Legal text finalised.** `legal/ai-insights-terms-v1.0.md` (draft suffix dropped,
   `LEGAL_INDEX` `draft:false`): banners removed, **Anthropic PBC** named as sub-processor,
   lawful basis set to legitimate interest, opt-out control wording.
2. **Lawful basis + mode set.** `AI_CONSENT_MODE` default is now **`opt_out`** (legitimate
   interest); LIA confirmed on file.
3. **Terms version bumped** `1.0-draft → 1.0` (`AI_TERMS_VERSION`).
4. **Sub-processor + privacy disclosure.** The Anthropic row was added to the Sub-processor List
   (aggregated/derived figures only — no individual salaries; no training on inputs; zero/limited
   retention; DPA + transfer safeguards), and an **AI-assisted analysis** section was added to the
   Privacy Notice. Confirm the DPA / Article 30 records cover the AI processing and Anthropic.

### Two NON-AI residual items (David's, not blocking the AI flip, but tidy before/soon after)

- **Privacy Notice contact address** — still says "the address published in the final notice".
  Set a real data-subject-rights contact, then flip `LEGAL_INDEX["privacy"].draft → false`.
- **Hosting + transactional-email sub-processors** — still "to be confirmed". Name them, then flip
  `LEGAL_INDEX["subprocessors"].draft → false`.
  (The authoritative AI disclosure is the final **AI Insights Terms** page, which every AI surface
  links to; these two pages remain `draft:true` only for the non-AI items above.)

## The remaining step — David's, in production (step 5)

5. **Flip the master switch on:** set `LUMI_AI_INSIGHTS_ENABLED=on` in the production environment.
   AI Insights then render for all non-opted-out members, feature-by-feature (each per-feature flag
   still independently killable without a deploy). Note `LUMI_AI_DOMAIN_SUMMARY` defaults OFF — set
   it `=on` too if the per-domain summary should ship. Ensure `ANTHROPIC_API_KEY` is configured in
   prod (without it, every surface shows its validated deterministic fallback).

6. **Re-run the adversarial gates on prod config** (`python3 server/qa_domain_summary.py`,
   `python3 server/qa_commentary.py`) and watch the first live generations.

## Kill switches (any time, no deploy)

- `LUMI_AI_INSIGHTS_ENABLED=off` — cuts ALL AI insights instantly (the master).
- `LUMI_AI_<FEATURE>=off` — cuts one feature.
- A member toggles off in Settings — withdrawal recorded, their gate closes next request.
