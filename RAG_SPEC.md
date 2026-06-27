# RAG / Strategy separation — shared spec (Phase B, 2026-06-27)

Two independent channels carry two different goals. They must never share a colour.

- **COLOUR = market position (RAG).** Distance from the market-default goal (on-market),
  which ~90% of orgs target. **FIXED for every org, INVARIANT to strategy.**
  `amber = below market · green = on market · red = above market`.
- **ALIGNMENT INDICATOR = a separate navy chip/glyph.** Distance from *this* org's own
  declared aim (its strategy). **Strategy-on only. Never recolours position.**

For the ~90% aiming on-market the two agree (green + "On plan"). For an org deliberately
aiming below, they diverge and that is informative: the row/tile stays **amber** (below the
default) and the **navy "On plan" chip** shows the intent matched — intent shows in the
indicator, never by recolouring amber→green.

Phase A confirmed this is **not a repaint** — `marketTone()` already returns
amber/green/red. It is a **revert** of four surfaces off the attainment lens back onto
`marketTone`, plus a new alignment indicator. Pure render: **no payload / GET / gauge math /
`signal_key` / rebaseline** touched (the server emits no colour — only verdict/favourable/
target enums; `_market_target` is an annotation that never changes verdict/counts/lean).

---

## §1 — Locked RAG position palette (single source)

**`marketTone(key)` ([web/js/pages.js:435]) is the single source of position hue.** It maps
the position string only: `below → amber · on/at → green · above → red`. Strategy-invariant
by construction; identical for every org.

Tokens (already single-sourced in [web/css/app.css]): `--amber-bright #F5A60A` (below) ·
`--favourable #2E7D52` (on) · `--unfavourable #C0392B` (above), with the gauge soft mixes
`--gauge-below / --gauge-on / --gauge-above`. The tone→value / tone→class tables
(`MKT_SOFT`, `MKT_RICH`, `MKT_CHIP`, `MKT_VCLS`) **stay** — the revert only swaps the *tone
source* feeding them from the attainment helpers back to `marketTone(position)`.

**To be REMOVED from the four aggregate surfaces** (gauge, tiles, spectrum, category-hero):
`attainTone()`, `bandToneAim()`, `ATTAIN_ALIGN`, `_gaugeAttain`. These are the strategy
inputs that currently recolour position by the org's aim. (They are *not* deleted globally
in Phase B — each revert pass removes its own usage.)

**Out of scope (already clean, do not touch):** the per-metric **signal rows**
(`posTag → marketTone`, polarity-aware by design — ruling **R1**), per-metric cards
(`card.js`), charts (`charts.js youColour`), and the board-pack/share `.chip good/bad`
(`commercial.js`). Signal rows stay polarity-aware: a below-market *lower-is-better* metric
is honestly green, not amber.

## §2 — Alignment indicator spec (the new piece)

**`<AlignmentChip target compact />` ([web/js/pages.js], `.align-chip` [web/css/app.css])** —
built dormant in Phase B, adopted by the revert passes (ruling **R2**).

- **Hue: navy (`--navy #1F2A44`) only.** Never amber/green/red (would re-merge with §1) and
  never coral (risk, §3). A target glyph reads "vs your aim".
- **Reads `target.alignment` only** (`on_target | behind | ahead`), from the existing
  server `_market_target` payload. Renders **nothing** when `target` is absent.
- **Labels:** `on_target → "On plan"` · `behind → "Behind plan"` · `ahead → "Ahead of
  plan"`. Distinguishes behind vs ahead (the old colour lumped both as amber). Full sentence
  (`targetCopy`) rides as the `title`.
- **Placement:** gauge → the caption line under the verdict (the existing `.arc-target`
  slot, recoloured navy); tiles → the header chip row, `compact` variant. No row of its own
  needed on either.

## §3 — Risk treatment (unchanged; collision resolved)

Risk and position occupy **different CSS properties**, so red-above coexists with risk-coral.
- Risk = coral `--lumi-coral #F08C6E`: a glyph/badge `.sig-risk` + an **inset left-edge
  shadow** `.signal-row.is-risk { box-shadow: inset 3px 0 0 }`. Background unchanged.
- Position = **background fill + `border-left-color`** (`.sig-tone-*`).
- Risk only ever overlays **signal rows** (the gauge/tiles carry no risk). The maternity row
  (`REW_BEN_FAM_002`, curated `risk_framed`, strategy-free, confirm-exempt) stays distinct
  in **both** strategy states: position fill (amber/red) + coral inset accent + coral shield.
- **Reserve RAG red _fill_ for above-market; keep risk as coral glyph + inset accent.**

## §4 — Degrade contract (the two-halves proof every pass inherits)

Each revert pass must prove **both halves** at green before commit:

1. **Strategy OFF → pure RAG position.** Hue = `marketTone(position)` (amber/green/red),
   **zero** alignment indicators.
2. **Strategy ON → RAG colour BYTE-IDENTICAL to strategy-off.** Indicators **ADDED only** —
   no position hue changes between the two states.

(Note: today strategy-off renders the gauge/tiles *grey*, not RAG — because they read the
attainment lens. After each revert, both states render the same `marketTone` RAG; that
identity *is* the pass's proof.)

---

## Revert sweep — four gated passes (none bundled; commit at green, push, STOP)

1. **Overview gauge donut** — `_gaugeAttain → marketTone`; add `<AlignmentChip>` to the
   `.arc-target` caption (recolour navy).
2. **Category tiles ×7** — tile tone `ATTAIN_ALIGN/attainTone → marketTone(verdict)`;
   add compact `<AlignmentChip>` to the header. **R3:** this reactivates the dead red
   `.cat-tile.v-above` / `.v-above-over` borders — verify above-market tiles finally render
   red.
3. **MarketSpectrum** — `attainTone → marketTone` on the hero **and** every category page
   ([pages.js:516]).
4. **Category-detail hero chip** ([pages.js:1602]) + **R3:** realign the inverted
   methodology legend ([pages.js:2112], currently below=red/on=amber/above=green) to the
   canonical `marketTone`.

**Phase B itself switches no surface** — it commits the spec + the dormant helper alone.
