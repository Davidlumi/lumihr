# External review — what was built, what was verified, what is yours to rule

> **v2 addendum (same day).** The reviewer's QA spec v2 arrived after this sheet was
> written. Its regression register named six defects live in the *shipped* build —
> all six verified true, three of them introduced by the previous hand-fix — and all
> six are now fixed with an owning assertion. **Gate A is built**
> (`server/qa_strategy_doc.py`, 34 checks, in `run_gates.sh`). What the spec leaves
> open for you is at the end: **R-I** (Gate A blocking/advisory split), **R-J**
> (Gate B fixtures), **R-K** (Gate C personas + sign-off), **R-L** (A2.2 controlled
> vocabulary), **R-M** (the delight items that need data or capture).

**Status: the buildable findings are FIXED and verified (see DECISIONS 2026-08-16, review
response). This sheet holds the items the reviewer himself marked "rule first", with the
verification results that bear on each. Nothing below is built.**

Every factual claim in the review was verified against code, the live DB and the ruling
history before anything was coded. Corrections to the review worth having on record:

- **"270 peers vs a pool documented at 220" is not a bug.** The pool grew from 220 to 270
  answering organisations on 2026-08-14 (the seedreal-1 +50 batch). The 220s in
  marketing.html, sample-board-pack.html and older docs are stale, not the report wrong.
- **"£27,000 is Board/Executive-only" is wrong.** Recomputed from live data: it spans five
  of seven levels; Manager alone is 52% of it, Board/Executive is 2% (£540).
- **"No provenance disclosure" was half right.** The operative ruling (amended R-P2,
  2026-08-08) deliberately keeps the product clean and puts ONE line on durable artefacts.
  The document was the one sibling artefact missing the ruled line — now carried (cover
  row + provenance foot). Per-figure disclosure would *contradict* the amendment.
- **"not_evidenced can never fire" is wrong in general** (it fires on suppressed cuts and
  unstated dials) but right for the demo org on its default cut.

---

## R-A. The three stated contradictions (reviewer blocker 3) — intent-vs-intent rules

All three are REAL and live in the stated data (verified in org_strategy):

| # | Stated A | Stated B | Data |
|---|---|---|---|
| 1 | Overall dial **lead** | 5 of 6 stated areas at/below market | `market_position='lead'`; domain_targets: Pay lag, TimeOff lag, Benefits/Health/Pensions match, Incentives lead |
| 2 | Family provision **over** market | Time off & family aimed **lag** | `family_position='over'` vs `domain_targets['Time Off & Family']='lag'` |
| 3 | Mix **Mostly pay** | Pay aimed **lag** | `reward_mix='cash'` vs `domain_targets['Pay']='lag'` |

The engine renders both sides faithfully (the §03 sentences are the deterministic floor
reading the stated dials — nothing invented). Only P6 tests intent-vs-intent today; the
`strategy_stance` evidence shape built for it generalises.

**Your ruling:** add three DRAFT R7 rules (P7 overall-dial-vs-area-aims, P8
family-vs-timeoff, P9 mix-vs-pay-aim) so §06 Tensions carries them as findings — or
block the contradiction at CAPTURE time (the wizard warns when a dial pair conflicts) —
or both. Note the reviewer's sharper point: nuance is legitimate (a deliberate spread is a
strategy), so a rule that *names* the tension beats a validator that *forbids* it.
(Reviewer's #1 counts eight areas; two are excluded from position targets by your own R3b
ruling — the rule drafting should count stated areas only.)

## R-B. Exhibit 2's aim marker (reviewer blocker 4)

Verified exactly as measured: `RR_AIM_PCT` plots lead at 82.5 (band 65 + half the
remainder), match 50, lag 17.5 — so an "above market" aim renders 17 points past the
band edge and Incentives reads ~53 points short of a target nobody set.

**Your ruling:** render the aim as a **bracket from the band edge** (lead = at-or-past
P65; lag = at-or-under P35; match = the band span). Purely client-side, one consumer,
data already on the payload. Recommended. Alternative: drop the aim marker from the chart
and let the "against your aim" stat carry it.

## R-C. Dot position vs dot colour, and the 29–39 clustering (blockers 5 + 13)

Verified mechanics: the dot's **x** is the median polarity-adjusted percentile (depth);
its **colour** is the verdict from the below/at/above lean (±0.25 band). Governance at
P32 "on market" beside Wellbeing at P32 "below" is both measures behaving as designed.
The clustering is **not a computation bug**: all eight medians recomputed independently
and matched the engine 8/8. The location (~34th) is a real profile; the *tightness* is
median-of-pool compression hiding item spreads of P1–P96 and splits as different as
Health (0/15/1) vs Pensions (15/16/1).

**Your ruling:** the chart leads with WHICH measure? Options, best first per the
methodologist review: (1) keep the dot, add the **below/at/above split** beside each row
(data already on domain_blocks) and an IQR whisker so the spread shows; (2) colour the
dot by depth-vs-band and move the verdict to the label; (3) drop the percentile axis and
chart the split directly. NOTE: depth-as-median is a frozen, gated design (Stage A item
C, qa_overview 5a) — changing what the chart *plots* is presentation; changing the
*median* would need a ruling and gate retarget.

## R-D. Counting doctrine: is "past a deliberately lower aim" off-strategy? (reviewer #7)

Now DISCLOSED (cover: "8 short or contradicted · 2 past a deliberately lower aim"; the
register names "Past the stated aim" as its own status). Still open: should those 2 count
in the headline 10 at all? Keeping them counts *any* divergence from the stated position;
dropping them counts only under-delivery.

## R-E. Per-area below-market evidence (reviewer #11, Big-4's strongest point)

Area verdicts rest on below-market metrics the document never lists (Wellbeing: "7 of 18
below" with its one shown signal reading above). Signals select by materiality — right
for Signals, wrong as verdict evidence. The fix is a content-model addition: top
below-market metrics per area (name, yours, median, percentile) on the payload + an
exhibit per area. Related doctrine: may a board paper defer evidence to the app at all?
(Two reviewers split on this.) Wants a spec, not a patch.

## R-F. The plan's this-cycle selection (reviewer #12)

Partly stale against today's build (this cycle covers 3 gaps across 3 areas, and the
pension gap DOES have an option scheduled). What stands: the model sequences by speed, so
the largest priced gap's costlier options land in later cycles — if that ordering is
policy, the schedule intro should say so; if not, the plan builder needs a
value-vs-speed instruction. Also the stored LIVE plan (lumi.db) predates the 2026-08-16
lever repairs and still carries pre-OpRA salary-sacrifice text — **rebuild the plan once
on the live server** (Rebuild plan in /plan, editor login) to pick up repaired levers,
rule 7 and the below-split evidence.

## R-G. The marketing provenance contradiction (reviewer blocker 1's other half — your open P0)

Unchanged from the pre-prod audit's held list, now sharpened: the ruled footer points
readers at lumihr.co.uk methodology — and the public methodology.html still carries a
card titled "Real member data" ("Nothing is scraped, purchased or modelled") while the
in-app methodology states the R-P10 truth ("a reference panel … modelled from published
UK survey data"). The durable PDF now cites the page that contradicts the in-app truth.
Also stale on those pages: "220 organisations" (pool is 270). This is the sale-side
wording decision that was held for you on 2026-08-11; the artefact fix makes it more
urgent, not less.

## R-H. Smaller David-owned items

- **R8 lever content** (your file): BEN-SALSAC's `typical_shape` still offers "car and
  technology schemes … where the workforce profile suits" inside a cost-saving lever
  (no NI claim, but worth a look); the NIC-forecast clause in its trade_off should be
  dated/sourced or cut ("announced NIC changes may cap the pension saving in future").
- **Approver display:** the record keeps the raw account email (it IS the record, marked
  "no board or committee was named"). If a name should render instead, identity-store
  display names need to reach the payload. Amendment *log* (what changed) needs per-field
  history that does not exist yet.
- **Density doctrine:** areas with no gap still get full sections (Health & protection).
  Compressing no-gap areas to a row contradicts the "one section per domain is the
  document" ruling — your call which wins.
- **Seven-vs-eight residue:** live surfaces are consistent at eight; the in-app
  methodology's "2026.1 restructured … into seven categories" release-history line was
  deliberately left (DECISIONS 2026-08-16) — confirm or amend. The reviewer's own v2
  brief needs its update either way.

---

# QA spec v2 — the rulings it leaves open

## What v2 found in the shipped build, and what happened to it

All six verified against the rendered PDF before any code moved. Three were mine,
introduced by the fix for the previous review — which is the spec's own thesis
demonstrated, and the reason Gate A now exists.

| ID | Verified? | Disposition |
|---|---|---|
| D001 register held 6 position rows for 8 areas while the summary counted 8 | **True** | Exec now counts the register's own objects: "a position for 6 of the 8 benchmarked areas and 7 coherence commitments besides — 13 in all". Owner: gate A1.1 + PDF A1.2/A1.3. |
| D014 banner stated two asks; body and cards stated one, and cards counted 4 option rows against the banner's 3 | **True** | One `askActs`/`askTwoPart` shape drives banner, both stat cards, lede and flow strip. Owner: A1.5 (source + PDF). |
| D020 "domain" leaking into a document that says "area" | **True** ×2 (plan intro + indicative caveat) | Both fixed. Owner: A4.5, asserted on source *and* on the artefact. |
| D024 cover dead space, no named author | **True** | "Prepared for — The Board" (from the approval record's body where one is named). A named *human* author needs a captured field: **R-M** below. |
| D025 stray full stop before an em-dash on the cover | **True** | Fixed at the source of the replace. Owner: A4.7. |
| D003 disclosure "defeated by 50× peers" | **Partly** | 175 "peer" hits are almost all the cut label in the running footer. The structural remedy is **R-L**. |

## R-I. Gate A: the blocking / advisory split (spec's sign-off line)

Built as 34 checks. **31 block. 3 are advisory**, and each advisory is advisory for a
stated reason, not for convenience:

| Check | Why advisory |
|---|---|
| A5.3 ordinal aim as a bracket | Encodes **R-B**, which is your ruling. It fails today by design — it is the gate holding the door open for the fix. |
| A4.3 forecast language | Warn-level by nature. Currently flags 2 lever trade-offs (BEN-SALSAC's NIC clause — see R-H — and GOV-PAY-REVIEW-CYCLE). |
| A6.5 approver as a person | Cannot pass without **R-M**'s captured field. |

**Your ruling:** accept this split, or promote any advisory to blocking (which blocks
the next release until its underlying ruling lands).

## R-J. Gate B — the fixture matrix

Not built. The spec's eight fixtures need a fixture harness that can synthesise org
states (3-dials-only, ~40% core, evidence suppressed, no-gaps, above-market-vs-low-aim,
principles populated). Two of those states now render *incidentally* and were both
verified today — the singular ask (live stored plan, 1 decision unit) and the
multi-unit either/or ask (rebuilt plan) — which is the fixture matrix's value
demonstrated at n=2.

**Your ruling:** build the harness (a session's work: a fixture builder writing org
states into a throwaway, plus golden text-layer captures), or keep the two live
states plus the fresh variant as the standing matrix. Note fixture 8
(principles + constraints populated) is the one the spec calls most valuable and the
one nobody has ever seen — Part A's weakest page is weak *because* it is empty.

## R-K. Gate C — personas and disposition

Cannot be built; it is a human protocol. The spec's disposition table is good and I
would adopt it as written. What it needs from you: the three mandatory personas per
release (spec suggests CFO, RemCo chair, reward director), and whether Q1 ("what is
this document asking me to do?") failing for any persona blocks a ship.

## R-L. A2.2 — controlled vocabulary for peer-describing copy

The spec's structural remedy for D003: peer-describing sentences render only from a
fixed field set, so free prose *cannot* describe the pool. Correct in principle and a
real change: every deterministic sentence that mentions the pool, the cut, n or
"peers" would move behind a small vocabulary layer. It also interacts with the
amended R-P2 ruling (in-product stays clean; the durable artefact carries one line).

**Your ruling:** worth a session, or is the current state — one ruled line on the
artefact, the truth on the methodology page, and the marketing contradiction closed
(**R-G**) — sufficient?

## R-M. Delight — three shipped, four need you

**Shipped today** (all pure-data, all traceable to the payload):
- *What we tested and it held* — the register's holding rows, named as claims that
  were checked and stood (category (b)).
- *What sits above market* — the areas and signals reading above, with the sample
  behind each, at the close of Findings. The document was entirely deficit-framed.
- *A closing line that isn't a disclaimer* — the last beat returns the document to
  the member instead of ending on lumi's wording caveat (category (c)).

**Held:**
1. **The rare thing** ("you are one of the N% who do X"). The single most quotable
   line available — needs peer-adoption prevalence on the report payload. Cheap-ish,
   real work.
2. **What happens if you do nothing.** The statutory half is available now (the
   wage-floor risk already says it); peer drift needs a second collection window.
   Ruling: state the statutory half alone now, or wait for both?
3. **The one-page pull-out.** Strategy on a page, ready to circulate. This is polish
   17's question in another form — see below.
4. **Named, dated, theirs.** Needs a captured "prepared by" (person + role) on the
   strategy record, and identity display names reaching the payload for the approver.
   Schema + identity-boundary work, so it is yours to schedule, not mine to guess.

## Polish register — what moved, what is yours

Shipped: 5 (cover space), 7-part (amendment date), 8 (the three ask surfaces agree),
12 (one word for the grouping), 14 partly (NIC clause now flagged by the gate), 16
n/a (running head already carries the section).

**Yours:** 1 (Exhibit 2 encoding = **R-B**), 2 (§06 receives intent-vs-intent =
**R-A**), 3 (comparator promoted to §05 *and* made a coherence check — the promotion
half is done, the check half is R-A's work), 4 (signal selection = **R-C**), 6 + 7
(named author, amendment log = **R-M**/**R-H**), 9 (no-gap areas compress — contradicts
the one-section-per-area ruling, your call), 10 (null-state family), 13 (salary
sacrifice from one source — the live stored plan still carries the pre-repair text
until it is rebuilt, **R-F**), 15 (Part A "in lumi"), 17 (**can Part A export
alone?** — the original standalone-strategy requirement. Worth answering directly:
the strategy variant already renders alone at `/strategy`, but it is not offered as
its own export from the plan document).

---

# v3.1 — the three frozen checks, answered

The spec's own sequence put diagnostics before writes. All three were run read-only
against the live store and the ruling history. **All three clear**, and two of them
clear in a way that matters more than the question asked.

## F1 — pool reconciliation: CLEARED, and the log is not defective

| Question | Answer |
|---|---|
| Live pool | **270** — `orgs` 271, minus one staff org with zero answers. `meta.peer_pool.responding_orgs` = 270. |
| `MAX(n)` any metric | **270**, and it is reached (81 of 344 metrics). No block anywhere exceeds the pool. **The invariant `max(n) ≤ pool` holds.** |
| One source? | **Yes.** Cover and footer both render the single server field `al.pool_footer`, built once from `meta.peer_pool`; that meta key is written in exactly one place (`aggregate.run_snapshot`, `len(responding)`), and the same `responding` set becomes the all-cut every metric's `n` aggregates over. |
| The 258 | A **per-metric base**, not a pool count: exactly five questions have n=258 because 12 pool members did not answer them. |
| DECISIONS entry | **It exists** — `DECISIONS.md:18280`, "## 2026-08-14 — +50 new seed orgs (benchmark pool 220 → 270), David-approved", naming the migration script, the re-ratified frozen targets at n=270 and the donor-clone fix. The six lines the reviewer cites are pre-growth June entries, correct as of their own dates under append-only semantics. |

**The reviewer's C1 hedge resolves the other way**: the pool is 270, the log recorded it,
and this exact claim was already adjudicated on this sheet. **The defect that survives** is
the one the reviewer half-saw: pool (270) and per-metric base (258) are different
quantities printed without labels that distinguish them. Fixed — signals now read "on the
N organisations that answered it".

## F2 — verdict grade: the premise is stale, the instinct lands one layer down

- **The floor is 3, not 5** (`DOMAIN_MIN_POLARISED`, ratified 2026-07-11; the old 5 was
  never a considered decision and was silently overridden by mp_config).
- **All eight areas come back `basis="market"`** for this org. Not one is indicative. So
  "indicative rendered as methodology-grade" does not describe this render.
- **Wellbeing has 18 polarised questions, not zero.** The reviewer is quoting a
  `DECISIONS.md` state the engine left behind (pre-5→3, pre-classified-pool).
- **The reviewer is right that `report.js` never reads `basis`** — the payload carries
  `position.basis` (app.py:6002-6005) and the PDF is the only surface that drops it. The
  SPA reads it (`pages.js:1224`, `commercial.js:411`). Today it would render nothing
  because every area is "market"; it is a latent gap, not a live defect.
- **The finding underneath, which is real and is yours:** `count.practice` is hardcoded
  `0` (`positions.py:1500`), so `count.polarised == count.metrics` for every area and the
  split the payload advertises is fiction. Wellbeing's 18 "metrics benchmarked" are 3
  benchmark-stream readings + 15 practice presence flags; Pay's 46 are 33 + 13. The
  document distinguishes them nowhere. **R-O′ (new):** should an area whose evidence is
  mostly presence flags say so on its own page? Fixing the count split is an engine change
  with gate impact (`count.metrics` currently equals `polarised`, so naively populating
  `practice` would double-count).

## F3 — taxonomy: CLEARED, David-authored and ratified

`DECISIONS.md:6832`, 2026-07-14, "Domain taxonomy: Option B′, 8 domains (RATIFIED)" —
with a row-level mapping (`domain_remap_mapping.csv`, 243 rows) from the 2026.1 seven.
Not drift. The floor is applied per `sub_power`, i.e. over the 8-way split, and **no area
falls below it** (smallest is Wellbeing at 18).

**Side-finding, fixed:** `/api/strategy/alignment` was the only one of five `hero_signals`
call sites not sorting by `sub_power_order` — it ordered areas by first appearance in
`question_order`. That is the root cause of the reviewer's D042 "four orderings". Now
sorted; contents, chart and sections share the taxonomy order.

## The renderer traces

- **D028 — reviewer right, fixed.** `p50_display` was hard-nulled for score-kind items
  (`positions.py:320`), so the template `"%s vs %s peer median"` degraded to the article:
  "25/100 vs the peer median". The median was in the block all along (p50=33.33). Both
  sides now print.
- **D030 — reviewer misread.** "1×" is the *Yours* column, not READS; `position` can only
  ever be below/at/above/differs. **But a real defect sits beside it:** `value_display` is
  overloaded — for rank-derived signal classes it holds `"P%d"`, elsewhere a formatted
  value. Worth a ruling on whether one field may carry two types (**R-AA**).
- **D063 — reviewer wrong, no change.** Midrank explains the 21st percentile exactly:
  103 of 246 peers score zero, r = 100 × (103 × 0.5) / 246 = 20.9 → P21. Correct
  survey-house convention, printed correctly.

## D034 — reviewer right on all four parts, and it is an engine change

Benefits & lifestyle really has **two** off-strategy commitments (the position gap and
coherence rule B2). The schedule reports one. Three mechanisms combine:
1. Candidates dedupe by `(category, lever_id)` across all option blocks, so position
   commitments (iterated first) claim all four Substance levers; B2 keeps only its two
   Approach-only levers.
2. `alt_group` is set on the candidate and then **dropped by both plan builders** —
   the persisted plan carries no gap attribution at all (`alt_group` is `None` on every
   stored action).
3. `altInfo` discards any group with fewer than two scheduled rows.

**Held as advisory in Gate A with the diagnostic attached.** The fix is to carry the gap
key through `PLAN_SCHEMA` into the stored plan and count per-area gaps from the register
rather than from lever names — a schema + builder change touching the ask's decision
units too, so it wants your word before it moves counts on four surfaces (**R-N** is its
neighbour).

---

# v3.3 — rulings owed, and the red-first evidence that is already built

**Nothing in v3.3 has been implemented.** Its §0.1 reserves the work to you, and D077
has two branches that produce different code. What IS built is the thing §0.5 requires
*before* any fix: the eleven checks, run against the shipped artefact and **shown red**.
Gate A reported 52/0 over three blockers; that is now corrected in the only way that
counts — the checks exist and fail on today's page.

## Q16 — gate trust: answered, and one thing does not reconcile

- The delivered file is **44 physical pages**, its own footers read "Page 44 of 44",
  and it is byte-identical (sha `e25c5cf7…`) to the file Gate A's 52 checks ran against.
  So the checks did run against this artefact, not a prior build.
- **The review reads it as 40pp.** That does not match any artefact produced here —
  v3.1 was reviewed as "40pp" when it was 45, v3.2 as "41pp" when it was 44. There is a
  consistent ~4-page gap across three reviews. Either the reviewer's copy is being
  transformed in transit, or a different file is reaching them. **Worth settling before
  the next cycle**, because a review of a different build explains some findings.

## Q17 — approver identity

`director@thornbridge.example` prints because the approval record stores the account
that approved, and no display name reaches the payload. It is the demo org's real login.
For a member organisation it will print their Admin's email on a circulated page. Already
held as R-U/D036 and advisory in Gate A; v3.3 asks you to confirm it is intended.

## Q13/Q14/Q18 and the D077 branch — not inferred

The review is explicit that Claude Code does not pick the branch, and I have not.
What the red evidence adds to your decision:

- **G54 fails in both directions**, as predicted: Wellbeing and Governance render an
  against-aim read with no register row; Health & protection holds a register row with
  no against-aim read. So the two code paths disagree *both* ways, not just one.
- **G55**: the Exhibit 2 note counts 8 areas against 6 position rows.
- Branch B is the smaller diff; Branch A makes the counts move on eight surfaces
  (cover, §01, §02, §06, §07, §08, §19, §20). Both remain defensible; the ruling is yours.

## The eleven checks — status on today's artefact

| Check | Owns | Result today |
|---|---|---|
| G53 | D076 | **RED** — 10 distinct respondent-verb hits bound to the pool |
| G54 | D077 | **RED** — asymmetric both ways (read-only: Wellbeing, Governance; row-only: Health) |
| G55 | D077 | **RED** — note says 8 areas, register holds 6 position rows |
| G56 | D078 | **RED** — approval page names no alternatives it was chosen over |
| G57 | D079 | **RED** — no Findings bucket carries Governance & transparency |
| G58 | D080 | **GREEN, and the check is coarser than the finding** — see below |
| G59 | D081 | **RED** — 6 unsplit gap counts |
| G60 | D082 | **RED** — Part C claims 3 options with no Part B mapping to check against |
| G61 | D083 | **RED** — but on a *different* pair than the one named; see below |
| G62 | D084 | **RED** — Pay is past-aim and still renders an options exhibit |
| G63 | D085 | **RED** — one row claims answer-provenance without citing a response |

**Two of my own first drafts were vacuous and I caught them only by demanding red.**
G57 originally asked whether an area's *name* appeared anywhere in §08 — which an
above-market card satisfies — and went green over the defect; it now reads the three
bucket sentences. G58 originally accepted the priced area appearing under *any* horizon,
which "next cycle" satisfies. That is the same failure class the review exists to correct,
found in the corrective itself, which is the argument for red-first in one line.

**G58 — green, but do not read it as D080 cleared.** This build's plan puts a Pensions &
savings action in this cycle, so an area-level check passes. The reviewer's point is
sharper: the *priced* gap is the employer contribution rate, and the scheduled Pensions
action (financial wellbeing support) does not move that metric. A sound check needs the
gap key that **D034/R-N** is waiting on — the plan carries no gap attribution today. So
G58 stays advisory and coarse until R-N lands, and D080 should be treated as open.

**G61 — found a collision, missed yours.** It flags `WEL-FRAMEWORK` ↔
`BEN-BENEFITS-FRAMEWORK` ("Setting out what … so provision reads as a choice"), a real
duplicate you may want to rule on. It does **not** flag `PAY-BANDS` ↔
`GOV-RANGES-INTERNAL`, because those two share little vocabulary while arguably naming
one action. Lexical overlap is not semantic identity, and closing that gap is a judgement
about what counts as the same lever — which is your call anyway (the review blocks the
merge on your line).

## What the red-first block does NOT do

It is **advisory**: it reports and never fails the suite, because failing a build over
unauthorised work would force the fix. **Each check flips to blocking in the same commit
as its fix** — that flip is the deliverable, not the check's existence. No document
behaviour changed in this pass; the only edit is the gate.

## Approval still owed

Q13, Q14, Q15 (R12), Q16 (see above — one item unreconciled), Q17, Q18, the D077 branch,
and the D083 library merge. Plus the standing set: R-N (still the largest live
contradiction), R-O′, R-P, R-Q, R-R, R-S, R-T, R-U, R-V, R-W, R-X, R-Y, R-Z.
