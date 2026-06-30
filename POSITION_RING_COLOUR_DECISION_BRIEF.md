# Market Position ring colour — philosophy decision brief

**For:** David · **Date:** 2026-06-30 · **Status:** DECISION REQUIRED — neutral assembly, no fix proposed, no option recommended
**Source:** the read-only verdict-ring diagnosis (this session). All facts below are documented from that trace — nothing recomputed.
**Companion brief:** `PREVALENCE_ROUTING_DECISION_BRIEF.md` (the routing-authority decision). Both await your ruling.

---

## THE DECISION

> **Is the Market Position card a NEUTRAL MIRROR — like Practice Alignment, which was deliberately stripped of performance colour — or a DELIBERATE COST-EFFICIENCY LENS (above-market = over-paying = red, on-market = efficient = green, below-market = under-investing = amber)?**

The card currently wears a performance palette. Whether that is correct depends on what the card is *for* — to describe where you stand without judging (mirror), or to judge spend efficiency (lens). This brief lays out both readings and one defect that must be fixed under either. It recommends nothing.

---

## 1. The current palette

The donut bands are coloured by `marketTone` ([web/js/pages.js:431-434](web/js/pages.js:431)), rendered at the gauge call site ([pages.js:677-682](web/js/pages.js:677)):

| band (meaning) | hue | token |
|---|---|---|
| **below** market (worse than peers) | amber | `--gauge-below` / `--amber-bright` (#F5A60A) |
| **on/at** market (at par) | green | `--gauge-on` / **`--favourable` (#2E7D52)** |
| **above** market (better than peers) | red | `--gauge-above` / **`--unfavourable` (#C0392B)** |

The green and red are the product's **literal good/bad tokens** — the same `--favourable` / `--unfavourable` used by `chip.good`, `chip.bad`, `callout.good/bad`, `btn.danger` ([app.css:89-92, 369-370](web/css/app.css:89)). So the ring is painted in the same colours the product uses everywhere else to mean "good" and "bad." Colour is doing judgment work.

The verdict band renders rich/saturated, the other two soft. Segments are sized by count. The **centre verdict word ("Below") is neutral ink** (`.donut-word { color: var(--ink) }`) — the word itself does not judge; only the ring does.

*(Note: a stale code comment at [pages.js:642](web/js/pages.js:642) still describes the old map "below=red, on=amber, above=green". The live map is the inverse, above. The comment is wrong, not the code.)*

---

## 2. The Alignment precedent — the inconsistency, stated plainly

The sibling card, **Practice Alignment**, was **deliberately neutralised**: its donut ([pages.js:730-734](web/js/pages.js:730)) uses **neutral categorical** colours — `--differs` (#6257C9, violet) and `--chart-band-mid` (grey) — **no red/amber/green**. The strategy relationship was moved out of colour entirely, into the separate **navy `AlignmentChip`**.

**Position still wears the performance palette; Alignment does not.** Two cards that sit side by side, built on the same donut component, now follow two different colour philosophies. That inconsistency is the heart of the decision: either Position should join Alignment in neutrality (mirror), or the divergence is intentional and should be *documented* with a reason (lens).

The stated rationale for the split (from the 2026-06-27 RAG/strategy-separation comments) is that **position legitimately has a direction** (below/on/above is a real scale) where alignment does not (an approach has no better/worse). That argument supports *some* encoding on Position — but does not by itself decide mirror vs lens, nor justify the specific hues chosen.

---

## 3. THE INVERSION — a defect under EITHER ruling

The engine **favourability-adjusts** before banding: `_adj_percentile` ([positions.py:694](server/positions.py:694)) flips lower-is-better metrics so that high = good regardless of polarity. Therefore **"above" already means BETTER than peers** — yet the "above" band renders **RED** (`--unfavourable`, the alarm colour).

**A member who is above market — a genuine win, often the strategic goal — sees it painted in the product's "bad" colour.** Symmetrically, "on market / par" is painted **green** (the "good" colour), so merely-average reads as success.

- This is **currently masked** only because Thornbridge's above-market count is ~0 (overall 1 of 91; Pay 0 of 12), so almost no red appears today.
- It is **wrong whether Position mirrors or judges**: a mirror should not paint a better-than-peers fact as alarm; a cost-efficiency lens should still let its colours agree with its favourable-adjusted bands. Either way, "above = better, shown red" is incoherent.
- It is **fixable independent of the philosophy ruling** — see the scope guard.

---

## 4. The two rulings and what each implies

**Ruling MIRROR — "Position is a neutral describer, like Alignment"**
- Neutralise the palette: re-map the bands to neutral categorical colours (the Alignment treatment — e.g. a single neutral ramp or the violet/grey family), so the ring shows *composition*, not *judgment*.
- Any genuine direction signal (you're behind / ahead) moves to a separate, non-performance element (a word, a marker, or a navy chip — mirroring how Alignment moved strategy to its chip).
- Resolves the inconsistency with Alignment by making the two cards consistent.
- **Fix scope:** colour-map, frontend only (`marketTone` + the band tokens). The inversion in §3 dissolves automatically (no good/bad colour left to invert).

**Ruling COST-EFFICIENCY LENS — "Position deliberately judges spend efficiency"**
- Keep a judgment palette, but **fix the §3 inversion** so the colours agree with the favourable-adjusted bands (i.e. above-market = better must not read as alarm; the lens must be internally coherent about which direction is "good").
- **Document the deliberate inconsistency with Alignment** — a written rationale for *why Position judges and Alignment mirrors* (the "position has a direction, approach does not" argument, made explicit and recorded), so the divergence is a decision, not drift.
- **Fix scope:** narrower re-map (correct the band→hue assignment) + a documented rationale. Heavier on the "why," lighter on the pixels, than Mirror.

*(No third option is manufactured. The two rulings are genuinely distinct: one removes judgment colour, the other keeps but corrects it.)*

---

## 5. Scope guard

- This brief decides the **Position card's colour PHILOSOPHY only** — mirror vs cost-efficiency lens.
- The **above=red inversion (§3) is a defect under both rulings** and should be fixed **regardless** of the philosophy outcome. It is the one item that does **not** wait on this ruling — it can be corrected as soon as you confirm it (a mirror ruling fixes it by neutralising; a lens ruling fixes it by re-aligning hue to the favourable-adjusted band).
- No engine change is implied by either ruling — this is a frontend colour-map matter. The favourability-adjustment in the engine is correct as-is; only the *colour mapping over it* is in question.
- As with the routing brief: a ruling here is a *direction*, not authorisation to edit — the fix is a later scoped pass.

---

## Decision required

**Mirror or Cost-efficiency lens?** *(The above=red inversion gets fixed either way.)*

- **MIRROR** — neutralise the palette (Alignment treatment); direction moves to a non-colour element. Frontend colour-map.
- **COST-EFFICIENCY LENS** — keep judgment colour but fix the inversion so hue agrees with the favourable-adjusted bands; document why Position judges where Alignment mirrors.

*No fix proposed and no option recommended. All facts are documented from the read-only diagnosis; nothing in the repository was modified by assembling this brief.*
