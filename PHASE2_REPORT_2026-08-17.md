# Phase 2 — report

**Basis:** `e6f9a01` (P2-A) on top of `24cfed4`. Measured on a throwaway pair made with
the SQLite backup API, never on `lumi.db`.

Companion documents: `FORMAT_AUDIT_2026-08-17.md` (§6.3, 17 F-numbered defects),
`GATE_A_INVENTORY_2026-08-17.md`, `VACUITY_SWEEP_2026-08-17.md`.

**§3 (Arm C sweep) is still running** and will be reported separately. Everything else
in the authorised scope is below.

---

## §2 — P2-A, and the honest result of the first full run

Committed at `e6f9a01`. Harness wiring only; no check's predicate changed.

The suite resolves the delivered artefact (`LUMI_DOC_PDF`, else
`artefacts/total_reward_strategy_and_plan.pdf`), passes it to Gate A as `--pdf <resolved
path>`, and prints path, **sha256 with the command that produced it**, and page count
before any gate runs. It never renders its own artefact — it judges delivered bytes.

Gate A and `qa_strategy_align` now count their `check()` call sites **from their own
syntax tree** and stamp each site that executes:

```
GATE-COUNTS: sites=66 exercised=66 run=66 failed=0 advisory=14
```

`run_gate` reads that trailer rather than judging a gate by its exit code, and the
closing line is now two different sentences — `ALL GATES GREEN — every gate ran every
check it defines`, or `ALL GATES PASSED, COVERAGE INCOMPLETE`. Both demonstrated: 66 of
66 with the artefact present; 34 of 66 with it moved aside, the 32 missing named by line
and check name, and the second wording emitted.

**A1.1 was the reason for a permanent 1-of-66 shortfall.** It was the `else` arm of the
register-anchor pair — a call site that could only execute while the document was wrong.
An if/else where exactly one arm can run is not two checks; it is one check whose result
decides whether the other two have anything to read. It now always runs.

### The honest result

**Nothing that was green at 34-of-66 went red at 66-of-66.** 0 blocking failures.

What the run does surface is **14 advisory checks firing that no suite run in this
engagement had ever executed**:

| check | owns | what it says |
|---|---|---|
| A5.3 | D005 | ordinal aim still plots a three-point stance as a percentile point |
| A4.3 | D017 | 2 unsourced forecast phrases |
| G53 | D076 | 10 respondent verbs bound to the comparison pool |
| G54 | D077 | asymmetric: Governance & transparency, Wellbeing |
| G55 | D077 | the note counts 8 areas; the register holds 6 position rows |
| G56 | D078 | the approval page presents options without naming what they were selected over |
| G57 | D079 | no Findings bucket carries Governance & transparency |
| G58 | D080 | the only priced gap (Pensions & savings) carries no this-cycle action |
| G59 | D081 | 5 unsplit gap counts |
| G60 | D082 | Part C claims 4 options against one gap; Part B's exhibit disagrees |
| G62 | D084 | past-aim areas still offering levers: Pay |
| G63 | D085 | 1 row claims answer-provenance without citing one |
| A6.5 | D036 | the approval record still shows a login |
| D034 | D034 | plan actions carry no gap key |

Every one is an already-known frozen item. The point is not that they are new — it is
that **"advisory until their fix lands" and "never executed" were being reported as the
same thing.** That is what inert twice over meant, and it is now visible on every run.

---

## §4.1 — Time off & family: §2.1 is complete, and this is a third state

Not "should be firing and isn't". The caveat's guard is
`pos.verdict && sigShown.length && !sigShown.some(x => x.position === pos.verdict)`
(`report.js:1897`). Time off & family's exhibit is **folded** by the zero-room rule
(`_room = inlineFollow ? 0 : …`, `report.js:1804`) — its sheet also carries the follow-up
inline, so `sigShown.length === 0` and the caveat is structurally unreachable.

So the three states are: caveat prints (Pay, Governance & transparency); caveat correctly
stands down because the shown rows now agree with the verdict (Wellbeing, post-fix); and
**caveat cannot print at all because no rows are shown** (Time off & family).

**The third state is a defect, and the fix made it worse.** Time off & family reads *on
market*, carries **nine** signals, and — on the payload — not one of them reads on market.
The substantive condition the caveat exists for is not merely met, it is met totally: zero
of nine agree with the heading. The area with the strongest claim on that warning is the
one guaranteed not to receive it, because the warning is gated on the rows being printed
rather than on the rows existing. Pre-fix it had three signals and the same suppression;
post-fix it has nine.

Recorded as **D088**, not fixed — the fix is a renderer change and is not authorised.

## §4.2 — D087 re-diagnosed, and it is materially worse

Deferred = signals the document names but does not print, pointing the reader at an app
they do not have.

| area | before | after |
|---|---|---|
| Pay | 3 | 7 |
| Pensions & savings | 5 | 7 |
| Health & protection | 0 | 0 |
| Benefits & lifestyle | 3 | 7 |
| **Time off & family** | 3 *(whole set folded)* | **9** *(whole set folded)* |
| Incentives & recognition | 0 | 2 |
| Wellbeing | 0 | 3 |
| Governance & transparency | 0 | 8 |
| **total deferred** | **14 of 25** | **43 of 55** |

**The document prints 11 of 25 signals before the fix and 12 of 55 after.** Deferral went
from 56% to 78% while what a reader actually sees moved by one row. The fix tripled what
the document *knows* and left what it *shows* unchanged — which is the correct reading of
D087 being unfrozen and materially worse, and the number to hold against any future
print-room ruling.

## §4.3 — F-000 logged

The group-cut spill is **F-000** in `FORMAT_AUDIT_2026-08-17.md`: 41 physical pages
against a footer claim of 40, §16 Governance & transparency past A4, three contents
entries mis-targeting from there. Blocker on any cut other than all-peers shipping.
Untouched.

Worth stating precisely: the group cut was never clean. Pre-P0-7f it verified at 40 pages
with 0 failures **because it carried zero signals in all eight areas**. F-000 is a latent
constraint the repair exposed, not one it introduced.

---

## §5 — V1 and V2, both answered

### V1 — the entry authorising `3035ef7` exists

**`DECISIONS.md:6897`**, quoted verbatim:

> **## 2026-07-14 — G&T competitiveness flag: TRUE (Diff 2, ruled Option 1)**
> Governance & Transparency flips competitiveness TRUE in market_position_config.json.
> Premise for FALSE (governance ≈ practice-heavy) retired by the 2026-07-14
> reclassification (61 market metrics). Verdict-changing by design: G&T's ↑-Substance
> market rows join the overall gauge. Metric-level Substance filter unchanged — the
> flag admits the domain, not cost/context rows. Headline movement is expected and
> reported, not a defect.

**Rationale:** the FALSE premise was retired by the same-day reclassification.
**Rejected alternative, recorded 22 lines earlier at `DECISIONS.md:6875`:** the flip was
deliberately *excluded* from Diff 1 —

> The G&T flip to TRUE is a live open ruling — its premise (governance ≈ practice-heavy)
> was retired by the 2026-07-14 reclassification (61 market metrics) — but it is
> verdict-changing and is therefore ruled separately at Diff 2, not inside the remap.

So the trail is complete: the alternative considered was doing it inside the metadata-only
Diff 1, and it was rejected because Diff 1 had to be verdict-neutral. **D077's branch is
unblocked on this point.**

### V2 — entry 8078 admits ASHE for a bounded purpose, not generally

`DECISIONS.md:8078`, *"ONS/DWP pass — corroborate and defend, register-only (ruled +
applied 18 July 2026)"*. Its own headline states the scope:

> the adjacent-source pass **CORROBORATED** the pension figures rather than replacing
> them — ASHE confirms the altitudes, so this is annotations + one context row, **NO SEED
> WRITE** (seed sha256 fcc967399d81c207 asserted byte-identical before/after; answers
> 232,497 untouched)

Five clauses, each bounding it further: ① PENSION_MATCH corroborates **altitude, not a
distribution replacement**, frozen dist not churned. ② AEDEFAULT — ASHE median added **as
context**. ③ a new context row with **NO LIVE METRIC**, deliberately not mapped onto
AUTOESC ("mis-mapping would be the audit's error class"). ④ the defensive annotation
recording ASHE's membership split as **legacy-stock, employee-weighted, not new-joiner
basis**, existing specifically to stop a later instance correcting a frozen carve-out
against legacy data. ⑤ **ASHE Table P10 PARKED** with a backlog note — available as a full
sourced distribution "if ever needed", explicitly not pulled.

**Answer: bounded purpose.** The entry admits ASHE as a corroborating and annotating
source for pension altitude, and it goes out of its way — twice — to refuse it as a
distribution source. Anything in BQ4 that relies on ASHE generally is not covered by this
entry and needs its own ruling.

---

## §6.2 — R-d: instancing works, and it is a one-way door for two of the three families

**Toolchain:** `fontTools 4.60.2` with `fontTools.varLib.instancer` and `brotli` — all
present. No new dependency.

**The families.** `InterVariable.woff2` (wght 100–900, 518 glyphs) and
`PlusJakartaSans-Variable.woff2` (wght 200–800). The CSS requests 100, 200, 400, 500, 550,
600, 650, 700, 750, 800. Note `fonts.css:3` claims 570 is requested; **it is not** — no
`font-weight: 570` exists anywhere in the served CSS or JS. The comment is stale.

**One wrinkle worth recording.** `instantiateVariableFont(..., updateFontNames=True)`
**fails** at the non-standard weights: `ValueError: Cannot find Axis Values {'wght': 550}`
— the STAT table carries named instances only at 100…900 in hundreds. Passing
`updateFontNames=False` instances cleanly at every weight; the outlines are right, only
the name table is not rewritten. Solvable, not a blocker.

**Result — measured, same harness, same live plan, only the font sources differing:**

| | pages | verification | Type 3 | Type 0 |
|---|---|---|---|---|
| delivered (all variable woff2) | 40 | 0 failures | **1339** | 0 |
| Inter + Plus Jakarta Sans as instanced statics | **40** | **0 failures** | 458 | 118 |
| + Poppins converted woff2 → TTF | 41 | **4 failures** | 1 | 161 |

**Row two is the answer to §6.2.** Instancing the two variable families produces static
TrueType at exactly the weights in use, real weights with no synthetic bold, the print
path picks them up, embedded subsets appear as Type 0 / Identity-H with real basefont
names — and it is **layout-neutral**: 40 pages, 0 failures, byte-for-byte the same
pagination.

**Row three is a warning.** Converting the three static Poppins `.woff2` to `.ttf`
eliminates Type 3 almost entirely (1 page-instance) but **breaks pagination** — 41 pages,
4 failures. The font dictionary shows why: all three Poppins faces collapse to a single
subset, `Poppins-Bold`. The three files are genuinely distinct (usWeightClass 500 / 600 /
700, internal families *Poppins Medium* / *Poppins SemiBold* / *Poppins*), so the
collapse is a matching problem introduced by the format change, not by the fonts. **Poppins
needs separate treatment; a blanket woff2 → TTF conversion is not safe.**

**The third driver.** The extraction argument needs narrowing: this artefact's Type 3 text
**is** extractable by PyMuPDF — Gate A's 32 artefact checks depend on it, and p15 yields
1,480 correct characters. No other extractor is installed here, so I cannot speak for
other consumers. The **PDF/UA and PDF/A eligibility** argument is unaffected and stands on
its own. So R-d has two firm drivers (weight fidelity, standards eligibility) and one that
should be stated as "extraction reliability across consumers we have not tested" rather
than "not extractable".

**Scope note.** §6.2 is not in Phase 2's authorised list, though §8's approval block asks
for it. I read that as an omission and did the read-only half only: instances were written
to the scratchpad and served from a scratch harness. **Nothing was installed into
`web/vendor/fonts` and `fonts.css` is untouched.** If that reading is wrong, no repo state
needs undoing.

---

## §6.3 — format audit

`FORMAT_AUDIT_2026-08-17.md`. **17 defects**, F-000 through F-017, each with page,
convention breached and cut-dependence. Rasterised, not extracted.

Headlines: four continuation conventions in one document and three tables consuming two
exhibit numbers each (F-A); ten section numbers heading two pages and **§12 heading three**
(F-B); basis of preparation as §23 of 40 (F-C); a sub-caption that wraps out of its column
into the next (F-E); two range dashes and two date formats **on the cover** (F-F); the
`—` saving tile (F-H); **the PDF title is `Overview · lumi`**, with empty author/subject and
the HeadlessChrome UA in `creator`, and no PDF outline against a 23-entry contents (F-I);
and **the dot-colour contradiction survives** — green *on market* dots plotted outside the
green *"range lumi reads as on market"* band, one of them at the same horizontal position
as a brown *below market* dot (F-J).

One dimension came back clean: **F-G, canonical names** — every area renders in one form
throughout. No F number issued. It still needs re-running against the R12 / Q15
terminology ruling when that lands, since internal consistency is not the same as
conformance.

Only F-000 is cut-dependent.
