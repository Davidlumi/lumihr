# lumi — Market Position Engine & Display Spec

Build spec for Claude Code. One engine turns signals into a market position; the same
output renders identically at three grains — the "Where you stand" gauge, each domain
card, and any custom peer group. Reconciled to the platform terminology guide; where
naming differs, the glossary wins.

---

## 1. The core principle

Every signal is one of four **classes**, which roll up into two **registers**:

| Class | Engine type | Register | Feeds the gauge? |
|---|---|---|---|
| **Level** | numeric — £ vs market median | Substance | yes → below / on / above |
| **Provision** | binary — vs market prevalence | Substance | yes → below / on / above |
| **Practice** | ordinal — vs market norm | Approach | no → tallied separately |
| **Design** | categorical — vs market mode | Approach | no → tallied separately |

Only **Substance** (Level + Provision) feeds the below/on/above counts behind the
gauge and the domain arcs — and of those, only `higher_is_better` metrics actually move
the verdict (polarity carve-out, §5.5). **Approach** (Practice + Design) is the norm-fit
tally ("differs from market") and is never folded into below/on/above. This is the line that
stops "pay review quarterly" being counted as "above market" on pay — and it's why the
positioned count is lower than the total metric count.

---

## 2. Signal schema (per metric)

- `id`, `domain`, `lens`
- `class` — Level | Provision | Practice | Design
- `type` — numeric | binary | ordinal | categorical (the engine mechanic behind the class)
- `direction` — `higher_is_better` (default) · `lower_is_better` · `neutral`. Governs
  colour and **whether the metric feeds the competitiveness gauge** (see §5.5). Most
  Level/Provision metrics are `higher_is_better`; monotonic governance metrics
  (CEO pay ratio, pay gap) are `lower_is_better`; genuinely non-monotonic metrics
  (workforce cost %, span of control) are `neutral` — context, not a verdict.
- `on_market_band` — tolerance that counts as on market
- `prevalence_thresholds` — Provision only: market take-up bands for below / on / above
- `weight` — default `1`. Reserved for v2 (materiality).

> Bands, polarities and prevalence thresholds are **data config, not code**. The engine
> reads them, never hardcodes them.

---

## 3. Normaliser

| Engine type | Class | Register | Output |
|---|---|---|---|
| numeric | Level | Substance | position `below / on / above` (after `direction`) + 0–1 score |
| binary | Provision | Substance | position `below / on / above` vs prevalence + score |
| ordinal | Practice | Approach | `differs` / `in line` (+ internal score for sort) — **excluded from gauge counts** |
| categorical | Design | Approach | `differs` / `in line` — **excluded from gauge counts** |

**Suppression floor.** A metric must clear `SUPPRESSION_FLOOR` (= 3, `aggregate.py:28`)
peers in the cut, or it emits nothing and is counted nowhere.

---

## 4. Aggregation (identical for every cut)

1. Collect **Substance** positions where `direction = higher_is_better`. Count
   `below / on / above`. These — and only these — feed the competitiveness gauge.
   `lower_is_better` and `neutral` metrics are surfaced as signals but kept **out** of
   the below/on/above tally (see §5.5), so they can't drag or inflate the verdict.
2. **Verdict** = centroid of the Substance scores → band → headline
   (`below market` / `on market` / `above market`). "leaning slightly below/above" is
   the centroid's offset within on market.
3. **Firm vs indicative** — Substance count ≥ `DOMAIN_MIN_POLARISED` (= 3, `app.py:65`)
   → firm; below → `indicative`.
4. **Render gate** — show a verdict once Substance count ≥ `TILE_MIN_POSITIONED`
   (= 1, `app.py:68`).
5. **Approach** tallied separately: "N differ from market." Never in below/on/above.

The `group` dim returns `match_count` through the identical `cutSize` path (verified),
so custom peer groups get this for free.

---

## 5. Tag wording (per glossary)

Two registers only; every specific (£, prevalence %, cadence) lives in the subtitle.

- **Substance** → `below market` · `on market` · `above market` — amber · green · coral, by direction
- **Approach** → `differs from market` · `in line with market` — purple

---

## 5.5 Polarity — the three directions (resolves open decision #2)

The below/on/above words stay **factual to the number** (true to the subtitle), but the
**colour** and **gauge inclusion** are driven by `direction`. This keeps every tag honest
while stopping inverted metrics from reading as failures.

| `direction` | Example | Tag (factual) | Colour | In the competitiveness gauge? |
|---|---|---|---|---|
| `higher_is_better` | base pay, pension, target bonus | below / on / above market | amber · green · coral | **yes** |
| `lower_is_better` | CEO pay ratio, gender pay gap | below / on / above market | green when favourably low, amber when high | **no** — shown beside it |
| `neutral` | workforce cost %, span of control | below / on / above market | navy (no valence) | **no** — context only |

Worked through the three landmines the persona test surfaced:
- **CEO pay ratio 22:1 vs 35:1** → tag `below market` (true), coloured **green** with a
  quiet "lower is better" cue. Favourable, and it no longer drags the pay verdict down.
- **Gender pay gap below market** → same treatment: factual, green, out of the gauge.
- **Workforce cost 25% vs 37%** → tag `below market` (true), coloured **navy**, labelled
  *context, not a verdict*. This is the CFO landmine defused: HR isn't calling lean cost a
  "problem", and finance can't weaponise an amber flag that was never raised.

**The consequence to confirm:** the "Where you stand" gauge becomes a clean *competitiveness*
read — "are we paying and providing at market" — built from `higher_is_better` metrics only.
Governance polarity and cost efficiency are real signals, but they answer a different question
and sit beside the gauge, not inside it. This is the cut that removes the conflation every
persona tripped on.

---

## 6. Display contracts

### 6.1 "Where you stand" gauge
Proportional arc (blocks ∝ `higher_is_better` Substance below/on/above counts;
inverted/neutral metrics excluded per §5.5), needle at the centroid,
verdict text + leaning subtitle, footer = the three counts as the arc's key. The
Approach tally is a quiet companion line ("N differ from market"), never on the arc.

### 6.2 Domain card
Verdict pill (Substance band), slim below/on/above bar with **counts-in-the-bar**
(fallback: a thin segment's count lifts just above the bar), `indicative` when Substance
count < 3. No `X/Y`. Approach as the companion line.

### 6.3 Signals page
- **Primary filter is market position** — `All · below market · above market · differs
  from market` — coloured to match the row tags. This is the cut users actually come for.
  The engine's **class** (Level / Provision / Practice / Design) stays internal and
  surfaces only in the detailed/analyst view (workstream #4); it is never the default
  chip row. Note that the position chips subsume the register split for free —
  below/above = Substance, differs = Approach — so no separate Substance/Approach control
  is needed.
- Proportional bar coloured by **position** (below amber · above coral · differs purple);
  the chips filter it.
- Default grouping **domain**, with a `group by: domain · lens` toggle.
- Triage tabs (Inbox / Priority / Saved / Dismissed) are a separate axis.
- Row colour carries **polarity** (§5.5) — favourable green, context navy — independent
  of the position word.
- Each signal: title, market-fact subtitle, position tag, triage actions.

---

## 7. Data

Per-domain below/on/above = the overall Substance split partitioned by domain (overall
= sum of the per-domain splits). No new query.

---

## 8. Likely touch points (verify against repo)

`positions.py` (`_pool_verdict`), floors in `aggregate.py` / `app.py`, card rendering in
`pages.js`, styling in `app.css`. Starting points, not gospel.

---

## 9. Sequencing

1. Schema + normaliser (type → class → register).
2. Aggregator: Substance counts + centroid + firm/indicative; Approach tally.
3. Gauge: proportional arc + centroid needle.
4. Domain card: pill + bar + counts-in-the-bar + indicative; drop `X/Y`.
5. Signals page: market-position filter (below / above / differs), domain/lens toggle,
   polarity-coloured rows; class demoted to the detailed view.
6. v2: materiality weighting via `weight`.

---

## 10. Ranked workstreams (from the persona stress test)

Ordered by where the build breaks for the most users, not by build effort.

1. **Polarity — DONE pending sign-off (§5.5).** The landmine: "below market" reading as a
   failure on cost and governance metrics, handing the CFO ammunition. Resolved via the
   three directions; needs your nod on pulling inverted/neutral metrics out of the gauge.
2. **Peer group as a first-class object.** The Reward Director and Analyst trust nothing
   until the comparator is theirs; "All peers · 221" is noise. The selector deserves the
   design weight the gauge got — saved cuts, n shown, sector/size/region filters up front.
3. **Materiality lever.** "Below on *what*?" is the first wall for the RD and CFO. Equal-
   weighting isn't a v2 nicety. Ship at least a crude weight (pin/important per metric)
   feeding the centroid via the reserved `weight` field.
4. **Simple / detailed mode.** One surface serves two audiences badly — the Analyst wants
   *more* (per-metric n, match confidence, coverage), the SME generalist wants *less* (one
   answer + what to fix). Progressive disclosure: headline mode by default, depth on demand,
   restoring per-metric n behind the detailed view.
5. **Stakes inside "differs from market".** Some Approach signals (transparency, compliance)
   aren't "your call" — flatten a regulatory exposure into a neutral difference and the RD
   loses trust. Add a "notable" sub-flag for Approach signals with external stakes.

**Still genuinely open (need your input, not just build):**
- **Lens set** — only "Attract" is live; confirm Retain / Motivate / Govern or replace.
- **Needle colour** — green / neutral / match-the-block.
- **Role matching / match-confidence surfacing** — upstream of all of this; how much to expose.
