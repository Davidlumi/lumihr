# AI Insights — Data Minimisation Attestation
### (Data Protection by Design — evidence for the RoPA / Article 30 record and the Legitimate Interests Assessment)

**Controller:** lumi.benchmark (lumi)
**Sub-processor in scope:** Anthropic PBC (AI text generation, "AI Insights")
**Date of this attestation:** 28 June 2026
**Code baseline attested:** commit `d6b0401` (the AI payload-building code, independently
verified on 28 June 2026). The subsequent change in this release adds an opt-out cache-deletion
step only; it does **not** alter what is sent to the AI provider, so this attestation remains
accurate for the current code.

This document is a plain-English, factual record of **what member data is, and is not, sent to
the AI provider** when lumi generates an AI Insight, and the technical controls that guarantee it.
Every assertion below is backed by a specific reference to the source code. It is written so that a
data-protection adviser — and, if required, a regulator — can follow and rely on it without reading
the code.

---

## 1. What IS sent to the AI sub-processor

When a member views an AI Insight, lumi sends Anthropic a small set of **already-computed,
aggregated benchmark figures** for the view in question — the same numbers already shown on the
member's screen. In business terms, the payload contains:

- **Domain position counts** — how many of the organisation's reward metrics sit below, on, or
  above the market, out of the comparison pool.
- **Named benchmark metrics with their summary statistics** — for the most notable metrics: the
  metric's name, the organisation's percentile position, and the **sample size** (how many
  organisations are in the comparison).
- **Prevalence figures** — how common a practice is among peers (counts / percentages).
- **Peer-group size** — the number of organisations in the comparison group.
- **The organisation's own submitted answer for the metric in view** — an *organisation-level*
  figure the organisation itself entered (for example a ratio, a percentage, or a policy rate),
  shown so the summary can describe the organisation's own position.
- **Organisation identifiers** — organisation name, sector, size band and region (organisation
  information used to frame the summary, not personal data about any individual).

*Code references:* the payload builders are `build_domain_summary_payload`, `build_commentary_payload`,
the analyst/board-pack/pulse/strategy payload assembly (all in `server/app.py`). All generation is
sent to the provider through a **single exit point**, `client.messages.create(...)` at
`server/claude_api.py:59`.

## 2. What is NOT sent — the load-bearing assertion

> **Individual salaries and individual base-pay levels are not present in the data sent to the AI
> provider. No raw underlying submissions, no other organisation's identifiable data, and no
> personal data about any individual (no employee or member names, emails, or per-person records)
> are sent.**

This is guaranteed two independent ways:

**(i) The data model contains no individual-pay or base-salary field.** lumi stores benchmark
answers in a single table, `answers` (`server/db.py:92–100`), keyed by *organisation*, collection
snapshot, question and matrix row, with one value per question. There is **no per-person, per-
employee, or individual-salary column anywhere in the schema** — a repository-wide search for such
fields returns none. Every stored answer is an organisation-level value (a percentage, ratio, per-
FTE figure, or policy rate). There is therefore no individual pay figure that *could* be sent,
because none exists in the system at this layer.

**(ii) An automated stripping step removes raw underlying figures before any external call.** The
function `strip_internal(...)` (`server/app.py:495–501`) recursively removes every field whose name
begins with an underscore. The only place raw peer-by-peer value lists live is under such
underscore-prefixed keys (`_values`, `_scores`). `strip_internal` is applied when each metric's
peer block is assembled (`server/app.py:619, 636, 664`) and when the report view is built
(`server/app.py:1022, 4326`) — i.e. **upstream of, and shared by, every AI payload builder**. As a
result, no raw distribution of individual peer figures can reach any AI payload; only the derived
summary statistics (counts, percentiles, sample sizes, prevalence) remain.

## 3. Coverage

This minimisation holds for **all member-facing AI features** — metric commentary, the analyst
("Ask lumi", including its guide sub-mode), the board pack, the pulse summary, the strategy
diagnosis, and the per-domain summary. Two structural facts make the coverage uniform rather than
feature-by-feature: (a) every feature's payload is built from the **same sanitised benchmark data
layer** described in §2(ii), and (b) every feature sends through the **single API exit point** at
`server/claude_api.py:59`. The independent verification described in §4 traced **8 distinct
generation/validation entry points** and found the minimisation held at every one.

## 4. Verification method and result

On **28 June 2026**, an automated adversarial verification sweep was run over the codebase. One of
its four independent review passes was dedicated to payload accuracy: it traced every AI call site
and the exact fields each payload carries, against the claim in §2. The result was **clean — zero
high-severity findings**, with the "no individual salaries / aggregated figures only" claim
confirmed at every surface. The reviewer independently identified the same two controls set out
above (the absence of any individual-pay field in the schema, and the `strip_internal` step).

## 5. Scope and limitations

This attestation reflects the data sent to the AI provider **as of the code baseline named at the
top** (commit `d6b0401`, verified 28 June 2026). It does **not** attest to Anthropic's own internal
handling — retention, training, and transfer safeguards are covered separately by the data-
processing agreement and the Sub-processor List. A **material change to what lumi sends to the AI
provider** (a new field added to any AI payload, a new AI feature, or a change to `strip_internal`
or the data schema) would require this attestation to be **re-verified and re-issued** before
release, and could affect the "individual salaries are not used" representation in the Privacy
Notice and AI Insights Terms. lumi treats "does this change the AI payload?" as a release checkpoint
on those surfaces.

---

**Attestation.** To the best of my knowledge, having reviewed the source code referenced above, the
statements in this document are an accurate description of the data lumi sends to its AI sub-
processor as of the named code baseline.

Signed: ____________________________  Name/role: ____________________________  Date: ____________

*Prepared for lumi by its engineering process. This is a factual engineering attestation, not legal
advice; it is intended to support the controller's RoPA / Article 30 record and Legitimate Interests
Assessment.*
