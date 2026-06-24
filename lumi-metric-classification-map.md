# lumi — Metric Classification Map (model test)

A representative metric set run through the framework to see whether it holds:
`class` → `type` → `direction` → does it feed the competitiveness gauge, and how does it tag?
This is a **test set chosen to exercise the edges**, not the exhaustive live list. ⚠ marks a
metric that stresses the model.

**Legend.** Direction: ↑ higher is better · ↓ lower is better · ~ neutral (context) · — n/a (Approach).
Gauge = feeds the "Where you stand" competitiveness verdict (only `higher_is_better` Substance does).
Tag colour: amber below · green on / favourable · coral above · purple differs · navy context.

---

## Pay

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| Base salary (by level) | Level | numeric | ↑ | ✓ | below market (amber) |
| Salary percentile position | Level | numeric | ↑ | ✓ | on market (green) |
| Graduate starting salary | Level | numeric | ↑ | ✓ | below market |
| Salary increase budget % | Level | numeric | ~ ⚠ | ✗ | context (navy) — high = cost, low = lag |
| Pay range width / spread | Design ⚠ | numeric | — | ✗ | differs (purple) — numeric-measured, structural |
| Pay review frequency | Practice | ordinal | — | ✗ | differs |
| Salary in job adverts | Practice ⚠ | binary | — | ✗ | differs — binary-measured, but a *practice* |
| Gender pay gap | Level | numeric | ↓ | ✗ | below market (green, favourable) |

## Incentives

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| Bonus target % | Level | numeric | ↑ | ✓ | below market |
| Bonus actual payout % | Level | numeric | ~ ⚠ | ✗ | context — year-dependent |
| LTI target % | Level | numeric | ↑ | ✓ | below market |
| LTI eligibility (offered) | Provision | binary | ↑ | ✓ ⚠ | below market — *also* spawns an LTI-amount Level signal |
| LTI vehicle (options / RSU) | Design | categorical | — | ✗ | differs |
| Bonus deferral | Design | categorical | — | ✗ | differs |
| Performance metrics (ESG etc.) | Design | categorical | — | ✗ | differs |

## Benefits

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| Pension contribution % | Level | numeric | ↑ | ✓ | below market |
| Pension type (DB / DC) | Design | categorical | — | ✗ | differs |
| Private medical (offered) | Provision | binary | ↑ | ✓ | on market |
| Medical scope (exec-only / all) | Design | categorical | — | ✗ | differs |
| Life assurance multiple | Level | numeric | ↑ | ✓ | above market |
| Income protection (offered) | Provision | binary | ↑ | ✓ | below market |
| Number of benefits offered | Level ⚠ | numeric (count) | ~ | ✗ | context — count ≠ quality |
| EV salary sacrifice | Provision | binary | ↑ | ✓ | above market |

## Time Off

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| Holiday entitlement (days) | Level | numeric | ↑ | ✓ | below market |
| Sick pay (weeks full pay) | Level | numeric | ↑ | ✓ | on market |
| Maternity pay (weeks @ full) | Level | numeric | ↑ | ✓ | below market |
| Sabbatical (offered) | Provision | binary | ↑ | ✓ ⚠ | below market — offered + length = two signals |
| Holiday carry-over | Design | categorical | — | ✗ | differs |
| Notice period | Level ⚠ | numeric | ~ | ✗ | context — long = security *or* rigidity |

## Wellbeing

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| EAP (offered) | Provision | binary | ↑ | ✓ | on market |
| Wellbeing budget per head | Level | numeric | ↑ | ✓ | below market |
| Mental-health days (offered) | Provision | binary | ↑ | ✓ | below market |
| Wellbeing programme maturity | Practice ⚠ | ordinal | (↑?) — | ✗ | differs — maturity arguably *has* a direction |
| # wellbeing initiatives | Level | numeric (count) | ~ | ✗ | context |

> ⚠ Few `↑`-Substance metrics → Wellbeing's domain verdict will often be **indicative**.

## Recognition

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| Recognition scheme (offered) | Provision | binary | ↑ | ✓ | below market |
| Recognition budget per head | Level | numeric | ↑ | ✓ | below market |
| Peer recognition platform | Provision | binary | ↑ | ✓ | below market |
| Spot bonus (available) | Provision | binary | ↑ | ✓ | on market |
| Recognition frequency | Practice | ordinal | — | ✗ | differs |

> ⚠ Tiny domain → often **render-gated** or indicative. The floors handle this.

## Governance

| Metric | Class | Type | Dir | Gauge | Example tag |
|---|---|---|---|---|---|
| CEO pay ratio | Level | numeric | ↓ | ✗ | below market (green, favourable) |
| Gender pay-gap reporting (publish) | Practice | binary | — | ✗ | differs |
| Workforce cost % revenue | Level | numeric | ~ | ✗ | context (navy) — the CFO landmine |
| Span of control | Level | numeric | ~ | ✗ | context |
| RemCo exists | Provision | binary | ↑ | ✓ ⚠ | "above market"?? — governance ≠ competitiveness |
| Malus / clawback | Design | binary | — | ✗ | differs |
| Shareholding requirement (×salary) | Level | numeric | ↑/~ ⚠ | ✗ | context / differs |
| Board oversight model | Design | categorical | — | ✗ | differs |

---

## Where the model holds

Across the four **competitiveness domains** — Pay, Incentives, Benefits, Time Off — the
framework maps almost cleanly. Nearly every metric is a `↑` Level or Provision (feeds the
gauge) or a Design/Practice (`differs`), with only a couple of `~` outliers. The
separation of `type` (the comparison mechanic) from `class` (the meaning) is **vindicated**:
salary-in-adverts is measured `binary` but presented as a Practice, and without that split
it would have been miscounted as a benefit gap.

The **polarity carve-out (§5.5) is validated and load-bearing.** Inverted (`↓`) and neutral
(`~`) numerics aren't a rare edge — pay gap, CEO ratio, cost, span, increase budget, payout %,
counts. Pulling them out of the gauge is what keeps "Where you stand" meaning *competitive
levels and provision* rather than a muddle.

## Where it strains (ranked)

1. **Governance is not a competitiveness domain.** Its metrics are `↓` ratios, `~` cost, and
   governance provisions. "below/on/above market" is conceptually wrong here — you don't
   *compete* on having a RemCo. Today the thin-sample floors mask this (too few `↑`-Substance
   metrics → indicative), but that's an accident, not a design. **Fix:** a domain-level
   `competitiveness: true/false` flag; Governance shows favourability + differs, no gauge verdict.

2. **`class` must be explicit config, not inferred from `type`.** Binary → Provision *or*
   Practice; numeric → Level *or* Design *or* neutral. The schema already stores them
   separately (good), but §3's tidy type→class table is the *common case*, not a rule. Whoever
   loads a metric makes a deliberate class call by meaning.

3. **One feature → multiple signals.** LTI = offered (Provision) + amount (Level); sabbatical
   = offered + length. The engine is per-metric, so this works *if* the config author splits
   the feature into two metric ids. Worth stating explicitly so it isn't collapsed into one.

4. **Verdict-less domains need a card state.** Governance, and thin Wellbeing/Recognition, may
   have no `↑`-Substance to position. The domain card needs a graceful "no market position —
   N differ · M favourable/context" state, not an empty or misleading gauge.

5. **A few Practice ordinals have a real direction** (wellbeing/maturity, capability). Most
   Practice is directionless `differs` (correct), but maturity-type ordinals lose a "you're
   behind" read. Low volume — accept `differs`, or treat maturity as Level-like. Flag, don't fix.

6. **`neutral` could be banded (v2).** Genuinely U-shaped metrics (cost) are safely "context",
   but extreme values *do* matter. A banded neutral — context in range, flag at the extremes —
   recovers the signal later.

## Verdict

The framework holds. Almost all the strain traces to **one root cause: the gauge conflates
"competitiveness" with "all Substance," and Governance is not a competitiveness domain.** Add a
domain-level competitiveness flag (finding 1) and treat `class` as an explicit per-metric call
(finding 2), and the rest are minor or v2. The polarity model and the type/class separation
both pass the test.
