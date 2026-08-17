# BOARD_QUALITY_PHASE0 — diagnosis, read-only

**Produced:** 2026-08-17, in response to `PROMPT_board_quality_2026-08-17.md` §2.
**Scope:** diagnosis only. No code, config, data or document changed. No DB written.
**Method:** live source and live store only. Every figure carries the command that
produced it. Anything unverified is marked `unresolved`, never inferred silently.
**Live DB opened only as** `sqlite3 'file:…/lumi.db?mode=ro'`. Where the engine had to be
*run*, a throwaway pair was made with the SQLite backup API into `/private/tmp`, used, and
deleted (deletion confirmed; live mtimes unchanged).

---

## 0. What this changes about the prompt

Three of the prompt's framings do not survive contact with the live source. Two of its
items are worse than stated. And the diagnosis found **one defect the review could not
have seen from the artefact**, which is now the highest-priority item in the pass.

| | |
|---|---|
| **P0-1 is false, in the opposite direction** | The prompt says: if the live config makes Wellbeing and Governance non-verdict-eligible, that is a wiring defect and the top item. **All eight areas carry `competitiveness: true` in the live config**, both areas have ample substance (Wellbeing 18 metrics, Governance 56) and both earn a *strict* verdict. Nothing to fix here. What is broken is elsewhere (P0-4) and was never about eligibility. |
| **NEW P0 — the signal engine is running blind** | `app.py:5943-5947` passes `lambda qid: tb and tb(qid)` as the block resolver. `tb` is a **dict**, never callable. On the all-peers cut it resolves to `None` for every metric, **silently disabling five of the eight signal mechanisms** in this document. On a twin/group cut it raises `TypeError`, which is swallowed, and **the entire document renders with zero signals in every area**. The demo org's own `default_cut` is a group. |
| **A2 is worse than stated** | There is no user-facing definition of the `0–100` scale *anywhere in the product* — and the document's own Method page says "Alignment is a count against your commitments — **never a score, index or grade**" (`report.js:2585`) while five exhibits print `x/100`. The document contradicts itself. There are also **more leaks than the five named**, including one whose label names its own unit: "EV home charging reimbursement rate (pence per kWh) — 20/100". |
| **S5's apology is not evidence, it is a certainty** | Signal `position` can only ever be `differs`/`below`/`above` (`signals.py:302-320`) — there is **no `at`**. So for any at-market area that prints a signal, the "most material ≠ most representative" paragraph fires **unconditionally, forever, regardless of the data**. It is not a copy patch over a selection problem; it is a guaranteed output of a vocabulary mismatch. |
| **A5/P0-8 is a stale artefact, not a rule** | The stored plan describes a lever inventory **that stopped existing 82 minutes after the plan was built**. |

---

## P0-1 — Taxonomy and verdict eligibility

**(a) Live category list** — eight areas, 333 active / 11 retired:
Pay 66 · Pensions & Savings 23 · Health & Protection 24 · Benefits & Lifestyle 41 ·
Time Off & Family 51 · Incentives & Recognition 44 · Wellbeing 19 ·
Governance & Transparency 65.
```
sqlite3 'file:/Applications/Lumi Project/lumi.db?mode=ro' \
  "select sub_power, sub_power_order, status, count(*) from questions group by 1,2,3 order by 2"
```
Stored casing is title-case; the document's lower-case rendering is display-only
(`web/js/core.js:206-214`). **No string-mismatch bug** — DB, config and
`STRATEGY_POSITION_EXCLUDE` all key on the same title-case strings.

**(b) `market_position_config.json`** — five keys. `_domains` is the eligibility switch
(one `{competitiveness: bool}` per area); `metrics` holds 340 entries. Two keys are
**dead**: `_part_b_review` (documentation) and `defaults` (no server module reads it —
`positions.py:1425-1428` records that the mp_config-defaults override was deliberately
removed on 2026-07-11 so env is the single authority). `defaults` happens to agree with
env today; it is an unread second copy and a future disagreement waiting to happen.

Eligibility is exactly two gates, both in `positions.py`:
```python
# positions.py:1072-1073
def _mp_competitive(cfg, sec):
    return cfg.get("_domains", {}).get(sec, {}).get("competitiveness", True)
# positions.py:1076-1093  _mp_gauge_eligible
if not _mp_competitive(cfg, item.get("subpower")): return False
return m.get("class") in ("Level","Provision") and m.get("direction") == "higher_is_better"
```

**(c) The answer, plainly: both are verdict-eligible.** All eight `_domains` entries are
`true`. Wellbeing carries 18 substance metrics, Governance & Transparency 56. Running the
live engine, both earn `basis="market"` (strict, not indicative): Wellbeing = below,
depth P32.4; Governance & Transparency = at, depth P32.2. **This is the engine working as
configured, not a wiring defect.**

The flip was deliberate and ruled: commit `3035ef7`, 2026-07-14, *"DIFF 2 — … G&T
competitiveness TRUE … verdict-changing BY DESIGN"*. Wellbeing was never false.

**The real defect here is documentation drift.** Two authoritative-sounding comments still
describe the pre-Diff-2 world and are now false:
- `data/market_position_config.json` `_readme` line 5 — *"competitiveness=false
  (Governance) → … no headline verdict"*
- `server/positions.py:1423` — *"Governance — competitiveness=false, no headline role at all"*

The non-competitive branch they describe (`positions.py:1447-1458`) is **dead code**: no
area can reach it. Anyone reading the source to answer this question is actively misled —
which is presumably how the prompt's hypothesis formed.

**(d) `competitiveness` and `STRATEGY_POSITION_EXCLUDE` are different concepts**, and the
code says so:
```python
# app.py:5109-5114 — R3b (David 2026-08-14)
# post-Diff-2 the engine can verdict all eight; the document stays honest by register.
STRATEGY_POSITION_EXCLUDE = ("Wellbeing", "Governance & Transparency")
```
They are composed, never conflated (`app.py:5275`, `:5314`), and both are enforced at
capture with distinct 400s (`app.py:6277-6285`). `competitiveness` = *may the engine
verdict this area* (all 8: yes). `STRATEGY_POSITION_EXCLUDE` = *may the member state an
aim, and does it get a register row* (6 only).

**The exclude was applied to capture and to the register — and never to the aim-inheritance
path or the section header.** That is P0-4, and it is the whole of A4/D077.

---

## P0-2 — Pool count

**270 is correct; no drift.** `meta.peer_pool.responding_orgs = 270`; 271 org rows;
`submission_complete=1` → 270; `COUNT(DISTINCT org_id) FROM answers` → 270. The 271st is an
incomplete signup (zero answers) excluded by the firewall at `aggregate.py:859-861`.

One source, two render sites: `aggregate.py:846` → `:859-861` → `:885-887`
(`set_meta("peer_pool", …)`) → `app.py:6190-6192` (`pool_footer`) → `report.js:1405-1407`
(cover) and `:2619-2624` (provenance foot).

**Load-bearing side finding, not in the prompt:** the demo org **is one of the 270**. The
subject of the report is counted inside its own comparison pool. At n=270 that is a 0.37%
self-inclusion; it is standard in some survey practice and unstated here. Worth a line in
Method or an explicit ruling.

---

## P0-3 — The on-market band

**They are two different objects, and that is the whole of S1.**

| | |
|---|---|
| **Per-reading band** | `MARKET_BAND_LOW/HIGH = 35.0 / 65.0` (`app.py:104-109`). Classifies **one reading**: `positions.py:941-951`, with a median-tie escape. |
| **Per-area verdict** | `VERDICT_NET_LEAN = 0.25` (`app.py:135-136`). A **net lean over classifications**: `lean = (above − below) / len(pool)`; `above` if `lean > 0.25`, `below` if `< −0.25`, else `at` (`positions.py:954-988`). |
| **Dot x-position** | `depth_pctl` — the **median** adjusted percentile of the pool (`positions.py` same block). |

So the shaded band is a *reading-level* threshold, the colour is an *area-level lean*, and
the x is a *median*. Governance & Transparency at depth P32.2 coloured "at" is all three
behaving correctly and disagreeing on the page: 18 below / 29 at / 7 above gives
`lean = (7−18)/54 = −0.20`, inside ±0.25 → `at`, while its median reading sits at P32.2,
outside the 35–65 band. **Nothing is wrong with either number. The exhibit asserts a
relationship between them that does not exist.**

---

## P0-4 — Aim inheritance

**The header rule** — `positions.py:1329-1345`:
```python
def _market_target(market, strategy, stance_override=None):
    stance = stance_override or _strategy_field(strategy, "market_position")
```
`stance_override or …` **is** the inheritance. An area with no `domain_targets` entry does
not go without a stance — it silently adopts the global dial. Called for **every
competitive area** at `positions.py:1523`, and `STRATEGY_POSITION_EXCLUDE` is **nowhere on
this path**. The payload carries it verbatim (`app.py:6011`).

The comment immediately above (`positions.py:1521`) says *"Governance never reaches here
(non-competitive branch above → no target)"* — **false since Diff 2**. It reaches it every
run.

**The register rule** — `strategy_align.evaluate` emits position commitments only for
areas in `position_domains`, i.e. the six.

**Why they disagree:** two paths, two definitions of "has an aim", one of them honouring a
ruling the other has never heard of. This is a one-predicate fix
(`area_has_binding_aim(area)`) whichever branch is chosen — and note the branch choice is
now *better informed*: Branch B ("stop rendering an aim read") is **consistent with R3b as
already written**, because R3b's own comment says the document "stays honest by register".

---

## P0-5 — The `x/100` values *(A2 — worse than stated)*

**The five metrics**, all `single_select`, all `is_scored=1`, ladders in
`questions.scoring_config_json.option_scores` (**not** in `market_position_config.json` —
its role for these is `direction` and `unbenchmarked` only):

| Signal | Question | Org answered | Ladder |
|---|---|---|---|
| Benefits participation | `PROP_202fecc6` | "No" | 100 / 66.67 / **0** / 33.33 — **not monotone in option order** |
| Long-service award value | `EXT_REW_GAP_007` | "Up to £50" | 0/25/50/75/100 |
| Individual recognition award value | `EXT_REW_GAP_002` | "£26–£50" | 0/25/50/75/100 |
| Promotion decision governance | `PROP_34ffb6e2` | "Central governance with clear criteria" | 0/33.33/66.67/100, **direction −1 (inverted)** |
| Maximum promotion increase | `REW_PRO_098` | "3–5%" | 0/25/50/75/100 |

Scoring: `aggregate.py:437-457` (`100.0 - s` when direction is −1). Median: P50 of the
peer distribution of the same direction-corrected scores (`aggregate.py:634-648`),
displayed by `positions.py:325-326` — the `/100`-vs-`/100` form is the **intended** state,
added deliberately as D028 in v3.1.

**(e) There is no user-facing definition of the scale anywhere in the product.** Searched:
the document's Method sheet (`report.js:2521-2610`), the in-app methodology page
(`pages.js:3891-4048`), the glossary (`core.js:106-118`), and the public
`web/methodology.html`. All define percentiles, medians, n≥5 and a separate 0–10
*confidence* score. **None mentions a 0–100 practice score.**

**And the document contradicts itself.** `report.js:2585-2586` prints *"Alignment is a
count against your commitments — never a score, index or grade"* on the same document that
shows five `x/100` figures.

**More leaks than the five named** — the Benefits & Lifestyle block alone carries three
more composed the same way: *"Relocation support availability — 0/100 vs 50/100"*,
*"Outplacement or career transition support offered — 0/100 vs 33/100"*, and the sharpest,
*"EV home charging reimbursement rate (pence per kWh) — 20/100 vs 60/100"* — a label that
names its own unit beside an option ordinal. **Any fix must target the score-kind display
contract** (`positions.py:312`, `:325-326`; `signals.py:606-613`, `:652-658`), not five
metric ids. *(Caveat: the extra three were enumerated with an all-visible stand-in rather
than the live entitlement path; re-confirm before quoting the count.)*

**BQ3 is renderable — and on one metric it changes the story.** Option labels and peer
modal answers all exist on this request path:

| | Your answer | Peer modal answer |
|---|---|---|
| Benefits participation | **No** | **No** (41.9%, 103 of n=246) |
| Long-service award | Up to £50 | £101–£250 (42.9%) |
| Individual recognition | £26–£50 | £51–£100 (37.1%) |
| Promotion governance | Central governance with clear criteria | Governed at BU level (63.2%) |
| Max promotion increase | 3–5% | 6–9% (32.2%) |

**Benefits participation needs a ruling before BQ3 ships.** Today it reads *"0/100 vs
33/100 peer median … below market, 21st percentile"*. Under BQ3 it reads *"your answer: No
· peer modal answer: No"* — **the org matches the most common peer answer**. Both are
arithmetically true (the ordinal *median* lands on "In development"; the *mode* is "No")
and they tell opposite stories. That is a methodology decision, not an engineering one.

---

## P0-6 — Costing inputs

All four live in one place, `server/aggregate.py:33-42` (`DEFAULT_ASSUMPTIONS`), stamped
into `meta.assumptions_defaults` at `:884` and resolved per-org at `positions.py:557-563`
(org override via `org_assumptions`; **this org has none**).

| Input | Value | Classification |
|---|---|---|
| Median salary | £36,000 | **lumi constant**, member-overridable, not overridden |
| Cost per leaver | 35% of salary | **lumi constant** — comment says "indicative" |
| Agency premium | 30% | **lumi constant** |
| Headcount | 150 = midpoint of `50-249` | **derived** from the member's stated FTE band |

**None is a published figure.** An exhaustive grep across `docs/`, `legal/`, `policies/`,
`data/`, `web/` and `DECISIONS.md` returns no publication, year or table for any of the
three. The document's own wording — *"lumi's cost model on its published assumptions"* —
means *published by lumi in this document*, which is defensible. **`pages.js:4036` is not**:
it presents the same numbers in a way that implies external sourcing. That line should be
corrected regardless of what BQ4 rules.

**ASHE — the answer is no, and the exclusion premise is wrong too.** Not one of the four
derives from ASHE; ASHE appears nowhere in `aggregate.py`, `positions.py`, `app.py` or any
data file touching the £ model. Its 12 repo hits are all in the seed/anchor register.

And there is **no general exclusion of ASHE from anchoring** — the opposite.
`DECISIONS.md:8078-8095` (18 July 2026) *admits* it as grade-A corroboration. The two
exclusions are narrow and specific: the DB/DC/GPP membership split is marked
legacy-stock/employee-weighted and does not supersede the TPR new-joiner anchor
(`DECISIONS.md:8089-8093`); and ASHE regional data would be a category error as a
*policy-prevalence* anchor (`PASS3_candidate_sources_2026-07-24.md:562`).

**So the ASHE question in BQ4 does not arise**, and the ruling that does is simpler: are
three unsourced lumi constants an acceptable basis for every £ in a board paper, and if so
how are they labelled on the page?

---

## P0-7 — Signal selection *(contains the new P0)*

**(a) Four sequential gates.** Production (`signals.py:517`, eight mechanisms, each
stamping an `impact` that is the **only** ordering key) → domain bucketing → an
"agreement" sort (`app.py:5961-5964`) → `_sigs[:4]` (`app.py:6008`) → the renderer's
`_room` slice (`report.js:1804-1805`).

### P0-7f — **NEW P0: the block resolver is broken on the document's own path**

```python
# app.py:5943-5947  (get_strategy_alignment)
_all_sigs = signals_mod.build_signals(
    items, _sig_money, org_visible_questions(org), lambda qid: tb and tb(qid), …)
```
`tb` is a **dict** (`app.py:2294`), never a callable. Every *other* `build_signals` call
site passes the real resolver (`app.py:2384`, `:2405`, `:4409`):
```python
lambda qid: pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0] …
```

Consequences:
- **all / industry / fte_band cuts** → `tb` is `None` → `None and tb(qid)` → `None` for
  every qid → **five of the eight signal mechanisms are silently disabled** in this
  document (prevalence, multi-select prevalence, and three others gate on `get_block`).
- **twin / group cuts** → `tb` is a non-empty dict (measured: 344 entries for this org) →
  `tb(qid)` raises `TypeError: 'dict' object is not callable` → swallowed by the bare
  `except` at `app.py:5948-5950` → `_all_sigs = []` → **the entire document renders with
  zero signals in every area**, with only a `log.warning`.

**The demo org's `default_cut` is a group.** The document is generated on the all-peers cut
today only because `parse_cut` defaults to `all` when the endpoint is called without
params. Anything that starts honouring the org's own default cut ships an empty document.

This is a one-line fix and it should not be bundled with anything.

### P0-7e — the apology paragraph is a certainty, not a finding

Domain verdicts speak `{below, at, above}` (`positions.py:979`). Signal positions can only
ever be `{differs, below, above}` (`signals.py:302-320`) — **there is no `at`**. Measured
over all 25 document-path signals: `{below: 19, differs: 4, above: 2}`. Zero `at`.

Therefore:
1. The agreement sort at `app.py:5961-5964` is a **structural no-op for every at-market
   area** — and measured on this org it reordered **zero** of the seven non-empty lists. It
   is dead code today.
2. The apology at `report.js:1897` fires **unconditionally** for any at-market area that
   prints a signal. Pay and Governance & Transparency are instances. **It is not evidence
   of a materiality-vs-representativeness tension; it is a guaranteed output.**

### P0-7c — what actually prints, per area

| Area | Verdict | below/at/above | Prints | Agrees? |
|---|---|---|---|---|
| Pay | at | 12/31/3 | Salary increase budget (P30) · Hourly shift multipliers | **No** — all 5 of Pay's signals read below |
| Pensions & savings | below | 15/16/1 | 2 below signals | Yes |
| Health & protection | at | 0/15/1 | **nothing** — area produces zero signals | n/a (genuinely quiet) |
| Benefits & lifestyle | below | 18/17/2 | 2 below signals | Yes |
| Time off & family | at | 11/24/8 | **nothing** — despite holding 3 signals that *all* read below | **silenced** |
| Incentives & recognition | below | — | matching below signal leads | Yes |
| Wellbeing | below | 7/9/2 | 1 signal, above market | **No** |
| Governance & transparency | at | 18/29/7 | 2 signals | **No** |

### P0-7g — the zero-room rule silences the area that most needed disclosure

`report.js:1780`, `:1804-1805`: an area with gaps but **no levers** gets `parts = 1` →
`inlineFollow` → `_room = 0` → prints nothing. Time off & family has 1 gap and 0 levers, so
its three below-market signals never appear — in an area whose verdict is `at`.

**So the prompt's "three of eight" is really four of eight**, and the apology set is
*"areas that disagree **and had room to print**"*, not *"areas that disagree"*.

---

## P0-8 — Plan distribution

**(a)–(b) There is no selection logic.** Candidates are a flat double walk
(`app.py:5443`, `:5445`, `:5493`), deduped on `(category, lever_id)` (`:5446`), head-sliced
to ten (`:5521`), then **head-sliced again to six** by `deterministic_plan`
(`claude_api.py:1993`). No sort, no ranking, no balancing anywhere.

Ordering is three nested *file/iteration* orders. Note `sec_order` at `app.py:5414-5417` is
built by **first appearance in `question_order`** — the identical bug fixed in the report
endpoint as D042 (v3.1, `app.py:4497-4501`) and never fixed here.

**(e) Nothing about materiality, £, severity, status or objective enters the ordering.**
The money model *is* computed in this handler (`app.py:5426`) and is used for exactly one
thing: choosing which sentence to write into the `roi` string. It never sorts anything.

The doctrine at `strategy_align.py:61-62` is explicit: *"File order preserved — NEVER
re-sorted, ranked or filtered by 'fit' (an ordered list is an implied recommendation)."*
**The plan builder then takes the head of that deliberately-unranked list and ships it as
the recommendation.** The cap re-imposes precisely the implied ranking the ruling forbade,
using file order as the ranking function. That is the finding under A5.

**(c) Why all four are Benefits & lifestyle — the stored plan is a stale artefact.**
At `built_at 2026-08-15 14:35:32` the lever library was tranche 1 (commit `85ac551`): 12
levers over three categories. Against this org's commitments: Pay and Time off were
*overspend* gaps the engine correctly refuses to answer with levers
(`strategy_align.py:108-122`); Pensions, Incentives, Wellbeing and Governance hit *"the
lever inventory covers Pay, Benefits & Lifestyle and Time Off & Family at v1"*; rule B2
needed Approach levers that did not exist. **Four candidates total — the caps never bound.**

Tranche 2 (all eight domains, both registers, commit `d983906`) landed at **15:57, 82
minutes later**. The plan was never rebuilt. **The document on the desk describes a lever
inventory that stopped existing the same afternoon.**

**(d) Why *Voluntary benefits platform* is the one this-cycle action:** horizon is the
lever's `speed` field copied verbatim (`app.py:5498`). Of the four, exactly one has
`speed: "this cycle"` — BEN-VOLUNTARY. Its own record reads
`"trade_off": "Perceived value is far below paid benefits — it widens choice, it does not
read as investment."` **That trade-off never reaches the page**: `deterministic_plan` copies
only five keys (`claude_api.py:1994-2000`), dropping `trade_off`, `cost_character` and
`alt_group`. So the sole action proposed in a year the strategy calls one of investment is
the one the inventory says does not read as investment, and the document cannot say so
because the field is discarded before rendering.

**(f) "One of ten" — precise wording matters.** Today: 13 commitments, 10 off strategy
(7 behind_intent + 3 contradicted), across **seven** gap-bearing areas. But at build time
rule P6 did not exist (added 2026-08-16), so the stored plan addresses **1 of 9**. Also,
two of the ten are *overspend* gaps the engine deliberately declines to answer — so the
honest denominator for "gaps a plan could act on" is **8**, not 10.

**Rebuilding today does not fix it.** Verified on a throwaway: 21 candidates → payload 10 →
plan 6, yielding 3 Incentives & Recognition + 3 Benefits & Lifestyle and nothing else —
**two of seven gap-bearing areas**, with Incentives leading only because it is first in
`question_order`. The single priced gap (£27,000, Pensions & Savings) is candidates #8–#10:
it survives `cands[:10]` into the payload and is cut by `cands[:6]`. **The only quantified
gap lumi has cannot reach the plan under today's code.**

---

## P0-9 — Lever conditioning

**(a)** Both strings confirmed verbatim: `WEL-FRAMEWORK` (`reward_levers.json:351`) *"…
uncomfortable in a year with no budget to fill them."*; `BEN-BENEFITS-FRAMEWORK` (`:426`)
*"… a harder conversation in a year with no budget."* Both `cost-neutral`, `Approach`,
`this cycle`.

**(b)** `org_strategy.budget_direction = 'investing'` — confirmed read-only.

**(c) No. Lever copy is never conditioned on the strategy object, and no templating or
substitution of any kind is applied to it.** `strategy_align.options_for` takes **no
strategy argument**; the emit is a pure key projection. So the conditional framing in the
library is unconditional in fact — it will contradict any member whose budget direction is
not "no budget".

---

## P0-10 — Font embedding

**All 1501 font references are Type 3, encoding empty, one unnamed base font.**
```
python3 -c "import fitz; d=fitz.open(p); [d.get_page_fonts(i, full=True) for i in range(d.page_count)]"
```
**Cause identified:** `web/css/fonts.css` ships Inter and Plus Jakarta Sans as **variable**
fonts (`format('woff2-variations')`). Chrome's print path cannot subset an interpolated
instance as static TrueType, so it emits Type 3 glyph procedures.

**This is a genuine trade-off, not a bug.** The variable-font change (2026-07-04) exists
precisely to stop weights 550–800 rendering as synthetic bold in the printed pack. Reverting
to static per-weight files would give TrueType subsets and take the fake weights back.
Text extraction and `ToUnicode` are clean, so it is not a blocker. **Testable remedy:**
render one page with static weights and re-run `get_page_fonts`; not attempted (Phase 0 is
read-only diagnosis and this is not on the critical path).

---

## Independently verified §5 items

Measured on the 44pp build in scratchpad (see caveat below):

- **C1** — a **second** missing-space instance, `y.Indicative`, distinct from the
  `area.Written` one fixed in v3.2. Same htm newline-collapse class, different site.
- **C2** — 17 curly / 23 straight apostrophes, straight ones exactly in the regions listed
  (`What we're asking`, `this approval's cost`, `A dot's place`, `lumi's overall verdict`,
  `the band's edge`, `towards the market's`). Certain template regions bypass `rrType`.
- **C3, C6, A8** — empty saving tile; continuation exhibits consuming fresh numbers (1–23
  contiguous); `director@thornbridge.example` present.
- **S10** — "employer brand is left doing the work" ×3.

**Caveat under Rule 3:** these counts come from the 44pp rebuilt-plan file, not David's
40pp live-plan artefact. The **defect classes** are identical; the **instance counts** are
not comparable. Every plan-dependent figure quoted in Phases 2–6 must come from a live-plan
render with its `built_at` and plan rows stated.

---

## What Phase 0 recommends changing about the plan of work

1. **A new item, ahead of everything:** fix `app.py:5943-5947` (P0-7f). One line. It is
   currently degrading every document and would empty any document generated on a group
   cut. It also invalidates any conclusion about signal *selection* until it is fixed,
   because five mechanisms are not running.
2. **P0-1 drops out of the pass** as a wiring item and becomes a **documentation-correction**
   item (two false comments, one dead branch, one dead config key).
3. **S5 changes class**: the apology is not a selection symptom, it is a vocabulary
   mismatch. Fixing selection will not remove it; giving signals an `at`/`on` position, or
   changing the apology's predicate, will.
4. **BQ3 needs a sub-ruling** on Benefits participation (median vs mode tell opposite
   stories) before it can ship.
5. **BQ4's ASHE question does not arise.** The real question is narrower and should be
   re-put: are unsourced lumi constants acceptable as the basis for every £ in a board
   paper, and how are they labelled?
6. **A5/BQ6 should be scoped as two defects**: the stale stored plan (rebuild + R-F
   discipline) *and* the head-slice-of-an-unranked-list design, which reproduces the
   problem on any rebuild and puts the only priced gap out of reach.

Nothing above has been acted on. No writes. Awaiting §9.
