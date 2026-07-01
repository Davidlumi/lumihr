# lumi — Platform Terminology

The single source of truth for what we call things, so the product reads as one voice.
If a screen, the build spec, or a prototype disagrees with this, this wins.

## Locked decisions

- **signal** is the noun; **flag** is the verb only ("we flag, you decide").
- Users filter and read by **market position** — below / on / above market, or a practice
  choice. The engine's signal **class** (Level / Provision / Practice / Design) is
  internal: it drives the tags and the headline but is **never** the user-facing filter.
- **domain** is the default grouping; **lens** is an optional "group by" toggle.
- **company** is a member of the peer group.
- **tags** carry a direction relative to market; every specific (£, %, cadence) goes in
  the subtitle, never the tag.

## Canonical vocabulary

| Concept | Use | Means | Don't use |
|---|---|---|---|
| Unit of comparison | **metric** | one comparable thing — a pay element, policy, or practice | "data point" |
| Result vs market | **position** | below market / on market / above market | "higher / lower than market" |
| A choice with no better/worse | **a practice choice** | you do it differently; no rate to be under or over | "non-standard" |
| Lower-is-better, on the good side | **favourable** | e.g. a small pay gap or CEO ratio | "good" / "ahead" *in the tag* |
| No inherent good direction | **context** | a fact to weigh, not a verdict (e.g. cost ratio) | "neutral" *(user-facing)* |
| Confidence caveat | **indicative** | shown when evidence is thin; the confident state carries no label | "firm" |
| A flagged metric | **signal** (noun) | a metric surfaced as worth a look | "flag" as a noun |
| The act of surfacing | **flag** (verb) | "we flag, you decide" | — |
| Default grouping | **domain** | Pay, Incentives, Benefits, Time Off, Wellbeing, Recognition, Governance | "category" |
| Alternative grouping | **lens** | a strategic view (e.g. how you Attract) — a "group by" toggle | — |
| The user-facing filter | **market position** | All · below market · above market | "class" (that's internal) |
| Comparison set | **peer group** (the **peers**) | the companies you're compared against | — |
| A member of it | **company** | one company in the peer group | "org", "organisation" |
| Triage | **Prioritise / Save / Dismiss** → Priority / Saved / Dismissed | the three triage actions and their tabs | "pin" as a label |

## What the user sees vs what the engine uses

- **Users** group by domain (default) or lens, and **filter by market position**. That is
  the whole surface vocabulary.
- **The engine** classifies each metric internally as Level / Provision / Practice /
  Design — that's how it decides what to compare against and what feeds the headline. It
  is not a user filter; it surfaces only in a detailed/analyst view.

## The engine model (internal — drives the tags and the headline)

| Class | What it is | Compared against | Register |
|---|---|---|---|
| **Level** | how much you pay / spend | market median (£) | Substance |
| **Provision** | what you offer | market prevalence | Substance |
| **Practice** | how you operate | the market norm (cadence, transparency) | Approach |
| **Design** | structural choices, no better/worse | the market mode | Approach |

- **Substance** (Level + Provision) = the "market-rate" stuff → tags as below / on / above
  market, and feeds the headline.
- **Approach** (Practice + Design) = the "choices" stuff → tags as a practice choice,
  never in the headline.
- Class is assigned per metric **by meaning, not by how it's measured** — a transparency
  policy is measured yes/no but is a Practice, not a Provision.

## Tag wording

Every tag states a direction relative to market; the subtitle carries the detail.

| Kind | Tags | Colour |
|---|---|---|
| Substance — market rate | below market · on market · above market | amber · green · coral |
| Substance — lower-is-better | below/on/above market (factual), read as **favourable** when on the good side | green |
| Substance — no good direction | below/on/above market (factual), shown as **context** | navy |
| Approach — choices | a practice choice | purple |

Worked examples:

| Signal | Tag | Subtitle |
|---|---|---|
| Base pay (senior) | below market | you P40 · market P50 |
| Pay review frequency | a practice choice | you quarterly · market annually |
| CEO pay ratio | below market *(favourable)* | you 22:1 · market 35:1 |
| Workforce cost % | below market *(context)* | you 25% · market 37% |

Rules that keep it honest:

- The tag always states the true position; the **colour** says how to read it — gap,
  fine, favourable, context, or difference.
- A Substance tag only shows on a real mismatch; matching the market doesn't flag.
- Figures, percentages and cadences go in the subtitle, never the tag.

## The headline ("Where you stand")

A **competitiveness** read — are you paying and providing at market — built only from
market-rate (Substance, higher-is-better) metrics. Governance (pay ratio, pay gap) and
efficiency (cost) sit **beside** it, not in it: you don't compete on those. On the
user-facing methodology page, Substance/Approach become plain English — "things with a
market rate" vs "choices with no right answer".

## Open items

1. **Lens set** — confirm the strategic lenses. Only "Attract" is from the live product;
   any others are proposed. Until confirmed, ship Attract and keep the toggle extensible.

---

*Supersedes looser terms used earlier (flag-as-noun, "Gaps / Choices", lens-only
grouping, class-as-filter). Reconcile screens, the build spec and the prototype to this.*
