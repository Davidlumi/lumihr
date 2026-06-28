# AI Insights — Go-Live Checklist

The AI Insights consent infrastructure is built and reviewable on demo/test data, but
**AI Insights are OFF in production**. The master gate `AI_INSIGHTS_ENABLED` is default-OFF,
so **no real member sees any AI-generated content** — including the five features that used
to default-on (commentary, analyst, board pack, pulse, strategy diagnosis). They go dark the
moment this lands and stay dark until David flips the master switch himself, after the steps
below.

This document is the switch-on runbook. **Every step is David's, post-solicitor — nothing
here is automated.**

## How the gate works (so the order is clear)

Any AI feature renders **iff all three are true**:

1. `AI_INSIGHTS_ENABLED` (the master switch) is **on**, AND
2. that feature's own kill-switch is on (`LUMI_AI_COMMENTARY`, `LUMI_AI_ANALYST`,
   `LUMI_AI_BOARDPACK`, `LUMI_AI_PULSE`, `LUMI_AI_STRATEGY`, `LUMI_AI_DOMAIN_SUMMARY`), AND
3. the **member has consented** (per `AI_CONSENT_MODE`).

So flipping the master on does **not** expose AI to everyone — only to members who have
consented (opt-in) or not withdrawn (opt-out). A member's consent is recorded per-person in
the `terms_acceptances` audit log (`kind="ai_insights"` / `"ai_insights_withdrawn"`), versioned
to `AI_TERMS_VERSION`.

## Reviewing the full flow on test data (before go-live)

Run the complete flow without touching production by setting the env var on the demo/preview
instance only:

```
LUMI_AI_INSIGHTS_ENABLED=on        # master on for THIS instance only
LUMI_AI_CONSENT_MODE=opt_in        # (default) or opt_out
# the per-feature flags are already on by default; ANTHROPIC_API_KEY in server/.env.local
```

Then exercise: sign up → tick the (separate, unticked) AI consent → AI insights render for
that consented test user → Settings → "Turn off AI Insights" (withdrawal) → AI disappears →
"Turn on" again → re-consent. A non-consented test user sees no AI, only the "review & enable"
prompt where a summary would be. Real members (production, master off) see nothing throughout.

## Go-live steps — David's, AFTER solicitor sign-off (in order)

1. **Replace the placeholder legal text.** Swap the draft files for the solicitor-approved
   final wording and drop the `-draft` suffix + `draft:true` flags:
   - `legal/ai-insights-terms-v1.0-draft.md` → final, update `LEGAL_FILES["ai_insights"]`
     and the `LEGAL_INDEX` entry (`draft: false`).
   - `legal/privacy-notice-v1.0-draft.md` and `legal/sub-processors-v1.0-draft.md` likewise
     (name the AI sub-processor in the latter).
   - Update the signup/settings copy that says "DRAFT — pending review."
2. **Confirm the lawful basis and set the mode.** The solicitor rules opt-in (consent) vs
   opt-out (legitimate interest). Set `LUMI_AI_CONSENT_MODE` accordingly (default `opt_in`).
   If opt-out, confirm the LIA (legitimate interests assessment) is on file and the privacy
   notice reflects it.
3. **Bump the terms version if the wording is materially different.** Set `AI_TERMS_VERSION`
   to the final version (e.g. `"1.0"`); a bump means existing consents pin the old version
   (re-consent can be required per the solicitor's definition of "material").
4. **Confirm the DPA / Article 30 records** cover the AI processing and the named sub-processor.
5. **Flip the master switch on:** `LUMI_AI_INSIGHTS_ENABLED=on` in production. AI Insights now
   render for consented members only, feature-by-feature (each per-feature flag still
   independently killable without a deploy).
6. **Re-run the adversarial gate** (`python3 server/qa_domain_summary.py`, and `qa_commentary.py`)
   on production config before/after, and watch the first live generations.

## Kill switches (any time, no deploy)

- `LUMI_AI_INSIGHTS_ENABLED=off` — cuts ALL AI insights instantly (the master).
- `LUMI_AI_<FEATURE>=off` — cuts one feature.
- A member toggles off in Settings — withdrawal recorded, their gate closes next request.
