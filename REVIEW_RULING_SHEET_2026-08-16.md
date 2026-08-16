# External review — what was built, what was verified, what is yours to rule

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
