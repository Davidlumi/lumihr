# GM RECONCILIATION — every register-marginal target vs today's authority · 2026-07-29 · READ-ONLY
### Nothing applied · no target edited · no gm file touched · no seed repair · no gate change.

**Why this exists.** `generated_marginals.json` still carries
`_source: lumi_anchor_register_CLAUDECODE.csv (clean, Diff 1) + generator_rules.json +
structured_bases.json`. Its **40** targets predate the canonical register (now
**v2026-07-29**, via `register_resolve.py`) and every ruling since. Three of them blocked real
coherence work this session, and the maternity pin proved the deepest failure mode: **the seed
reached two targets only because orgs held contradictory answers — repair the incoherence and the
anchors fail.** This sheet asks of every target whether it is still true and whether the seed
reaches it honestly.

**SCOPE — corrected twice, and the arithmetic now reconciles.** `qa_plausibility` evaluates tier-2
through an **if/elif chain**: `if qid in FROZEN` → `elif MGRAD` → `elif RDIST` → `elif MS_INC` →
`elif MARG`. Consequences:
- **4 of this sheet's 40 rows are NEVER evaluated as marginals** — REW26_WEL_EAP, REW26_WEL_FINWELL,
  REW26_WEL_STRATEGY, REW26_BEN_PENSION_MATCH are `frozen_targets.json` keys, so the FROZEN branch
  catches them and their gm `target_share` is **dead code in the gate**. (The gm file's own
  `settled_refreeze` block names exactly those four — and **nothing in the repo reads that block**,
  so the declaration is inert.) v1 counted them as gate-verified PASS rows.
- **11 gate-checked targets live outside `marginals`** and were absent from v1 entirely:
  `ruled_distributions` (5), `maturity_gradients` (5 checked of 6 — PENSION_TYPE is FROZEN-shadowed),
  `multiselect_incidence` (1). There is also a **`floors`** family (3) v1 never mentioned.
- **Arithmetic: 40 − 4 shadowed + 11 = 47**, matching the gate's printed count. v1's "52 declared,
  47 checked, ~5 skipped for n<5" was the wrong explanation.
- **Two of the omitted rows carry the 2nd and 3rd largest drifts in the entire gate** — REW_INC_103
  (2.55pp) and REW_BEN_HOL_001 (2.45pp), both larger than anything this sheet ranks below
  REW_FAI_088, and both carrying **two authorities each** (a gradient entry *plus* a ruling —
  Tier-1A's ladder correction and r3sw4's sector-honest supersession respectively).
**So the title's "every register-marginal target" is true of `marginals` and false of the gate's
full tier-2 set.** Appendix B enumerates the 12; a second pass over them (plus `floors`) is the
named follow-up.

**Method note (fidelity) — and a METHOD FAILURE, corrected.** Achieved values use the gate's own
reading (`ORDS` entry else `reseed_engine.option_order`, `positive_from` cut else rung-1) and
reproduce the gate's printed statistics exactly. **But my first pass derived targets from the
REGISTER CELL ONLY and never read the gm entry's own `sme` / `large` / `rule` / `source` fields.**
Those fields document the generator's derivation — a **cohort blend `(sme×30 + large×190)/220`** —
and **all 8 targets carrying an SME/large pair are exact blend hits, zero misses.** That single
omission produced most of v1's Rank-2, and it produced one outright false accusation (M5). Both are
rewritten below. **Note the blend's cohort model itself: 30 SME vs 190 "large", i.e. the 62
unclassified orgs are treated as LARGE** — a modelling choice worth its own ruling, and not the
128/30/62 split the headline reviews weight with.

---

# THE HEADLINE CONTEXT FINDING — what "green" actually means

| |drift| band | rows |
|---|---|
| 0.0 – 0.5 pp | **37** |
| 1.0 – 2.0 pp | 2 |
| 4.0 – 5.0 pp | 1 (REW_FAI_088, −4.1) |
| > 5 pp | **0** |
| **median 0.14pp · max 4.09pp** (v1 printed 0.10/4.10 — median was taken over 1-dp-rounded values; corrected) | |

**37 of 40 targets sit within half a percentage point.** For genuinely independent anchors that
would be implausible. It is not a coincidence and not a fault: `reseed_engine` *reshapes the seed
to these targets*. **The freeze gate therefore measures seed-to-target FIDELITY; it has never
measured target-to-source TRUTH.** A green gate says "the reseed worked", not "the anchor is
right". This reconciliation is the only place the second question is asked.

> **CORRECTED 2026-07-29 (David-ruled, see CORRECTIONS at the foot).** This sentence previously
> read *"and it finds **8 targets that match no figure derivable from their own register cell**."*
> **That was false and is withdrawn.** Derived live: **every target but EXT_REW_GAP_004 is
> derivable from its own register cell; GAP_004's is derivable from a ruling (seedreal-1);
> PENSION_MATCH's only across two cells.** The "8" was a v1 figure this rewrite failed to delete —
> v1's own Rank-2 list, which the v2 body dismantles row by row (6 withdrawn as blend hits,
> REM_PAY_001 derivable, GAP_004 ruled-and-closed: 8 − 6 − 1 − 1 = 0 survivors).

---

# RANK 1 — MASKED: the achieved value is propped up (blocks coherence work)

**M1 · REW_BEN_SICK_004** — target 0.300 · achieved **0.303** (+0.3pp, PASS) · grade A · `positive_from='No waiting period'`
1. **Current**: passes comfortably.
2. **Authority today**: register v2026-07-29 — *"OSP waiting period: ~30% eligible from day one; rises to 43% public"*, base *"orgs with OSP"*. `structured_bases.json` states it imperatively: *"CONDITIONAL DENOMINATOR: base is orgs with OSP … generator must condition on the OSP parent."* Superseded by nothing; **an OPEN class-C ruling (r3sw25, DECISIONS 8885) already queues its conditioning.**
3. **MASKED — mechanically detected and confirmed**: the anchor declares a conditioned base, **no guarded coherence pair exists** (30 pairs exist; `SICK_005←SICK_001` is one, this is not) **and no `applicable_bases` declaration exists**, so the engine counts the full base. Of the gate's 122 in-scope answers, **48 are no-OSP orgs** (46 "Statutory sick pay only" + 2 "No sick pay provided") **and a further 8 have no SICK_001 answer at all — 56 of 122 are not verified OSP-holders.** **POST-REPAIR FIGURE CORRECTED (v1 printed 51.8%/+21.8pp, which reproduces under no base definition):** strict OSP-holder base **36/66 = 54.5% (+24.5pp)**; admitting the 8 unknowns **37/74 = 50.0% (+20.0pp)**. **Both FAIL by a wide margin — the finding's direction stands; v1's number did not.** The base definition is now pinned. The 30.3% match is produced by the incoherence.
4. Point source.
5. **Fix class: seed repair required first (seed-data) + base declaration (config) + target re-derivation (data), in that order.** Ruled sequence already recorded.

**M2 · REW_BEN_FAM_007** — target 0.360 · achieved **0.358** (−0.2pp, PASS) · grade A · `positive_from` **unset**
1. Passes.
2. **Authority today**: *"52% … have a policy/procedure … PAID carer's leave specifically offered by ~36% (RMS 2022) / **31-45%** (flex 2025)."* The metric is now **Practice-class** (Domain-8 B4, applied today).
3. **MASKED (construct)**: with `positive_from` unset the gate's "positive" = **any provision** (unpaid + paid), not the anchor's **paid** construct. The pass is pinned by **64% claiming no carer's provision at all** — implausible against the verified Carer's Leave Act 2023 (one week statutory *unpaid*, all employees). Repairing the contradictions breaks it (**111/204 = +18.4pp**) — precisely: **only the 38 "No specific provision × paid" rows move the gate value**; the other 39 ("Unpaid leave only × paid") are already scored positive by the unset cut, so v1's "any repair" was loose.
4. **RANGE source (31–45%)** — the point target 0.360 forces a precision the source never claimed.
5. **Fix class: `positive_from` correction (data) + schema extension (gate) + seed repair (seed-data).** Ruled target = the range; **not writable today** — see the schema finding.

**M3/M4 · REW_BEN_FAM_001 (0.670, achieved 0.671) + REW_BEN_FAM_002 (0.544, achieved 0.542)** — both PASS
1. Both pass at ≤0.2pp.
2. **Authority today**: FAM_001 — *"33% offer statutory-minimum maternity pay only"* (CIPD/YouGov 2022, n=2,000; target = the complement, a legitimate derivation). FAM_002 — *"60% large(250+); ~19% all UK-only"*; **its 0.544 matches no figure in the cell** — it is the **Diff-10/B5 ruled shape** (*"upper rungs EMPTY BY RULING"*), which supersedes the cell.
3. **MASKED — the pin, and it is arithmetic, not a data error**: on live bases the targets require **139** parent-positive orgs and **115** child-positive orgs. If enhanced weeks require enhanced pay (the conditioning B6 rules), **≥23–24 orgs MUST hold enhanced pay with zero enhanced weeks**; **25 observed**. Parent-side repair breaks FAM_001 (−11.9pp); child-side breaks FAM_002 (+11.6pp). **No seed repair satisfies both targets and coherence.** Compounding it, the two cells disagree at source (~67% vs ~19% all-UK for substantially the same prevalence).
4. Point sources.
5. **Fix class: SOURCE READ REQUIRED (research) — critical path.** Named documents: the FAM_001 cell's CIPD/YouGov **2022 working-parents** survey (n=2,000, weighted) and the FAM_002 cell's **CIPD Reward Survey Feb 2026** (Fig28) — both cells, their bases, their editions. **B6 suspended until it resolves.**

**M5 · REW_BEN_SICK_001 — v1's CIRCULARITY ACCUSATION IS WITHDRAWN AS FALSE**
v1 claimed target 0.568 "is neither the flat 18 nor the weighted 44.1 … a target that equals the
seed rather than the source is circular by construction." **That was wrong.** The gm entry records
`sme: 17.5, large: 63` — **the midpoints of the cell's own published ranges** (17-18% SME,
60-66% large) — and `(17.5×30 + 63×190)/220 = 0.56795 = 0.568` **exactly**. The target is a
documented source derivation, not a seed echo. The only surviving observation is that its legs are
**range midpoints**, which belongs under RANGE SOURCES, not here. **No masking, no fix needed.**
My error: deriving from the register cell while ignoring the entry that states its own arithmetic.

**M6 · REW_BEN_FAM_009 — PROMOTED TO MASKED (the reviewers' find; a LARGER instance than M2)**
Target 0.700 · achieved **0.7005** (+0.05pp, PASS) · `positive_from` unset. Anchor: *"70% of UK
employers offer **PAID** study leave."* The rung-1 cut counts **120 orgs answering "Unpaid leave
only"** as positive → 145/207 = 0.7005. **Strict (paid-only) = 25/207 = 12.1% — a 58.0pp construct
gap, versus 29.4pp for FAM_007, which v1 promoted while leaving this in the risk list.** Independent
corroboration: its duplicate-anchor sibling REW_FAI_STUDY_TIME reads 70.2% on a *paid-inclusive*
ladder, and Domain-8 already ruled the sibling owns the CIPD 70% figure. **Fix: `positive_from`
correction (data) + the duplicate-anchor ruling (Domain-8 B4).**

**M7 · REW263_WEL_FINWELL — PROMOTED TO MASKED (coherence, not construct)**
Target 0.150 · achieved **0.1500** (exact). But **108 orgs answer "No" (no financial-wellbeing
provision at all) on this ladder while answering "Yes" to the sibling REW26_WEL_FINWELL** ("Do you
offer a financial wellbeing programme?"). The ladder's "Ad hoc provision" rung describes exactly
those orgs and holds **3**. No coherence pair guards the pair. **The exact-on-target achieved value
sits on top of a 108-org contradiction.** (Its construct gap is only 1.4pp — the exposure is the
coherence, not the cut.) **Fix: seed repair + coherence pair (seed-data + config).** Note
REW26_WEL_FINWELL is **frozen**, so the repair direction matters.

**M8 · DUPLICATE-ANCHOR FAMILIES — one source figure, several targets (structural, missed by v1)**
v1 inspected every target in isolation. At least three families share a figure: **CIPD PPT Fig16
("~40% always; 53% always-or-sometimes") anchors THREE metrics** — PAYTR_01 (0.40), REW_FAI_089
(0.53), REW262_GOV_PAYINADVERTS (0.53); the latter two have identical ladders and targets yet
**disagree org-by-org on 12 orgs**. Fig18 anchors a second pair. **Each family is a
double-count: one source constrains N seeds, so N−1 of them are not independent evidence of
anything.** **Fix: a per-family ownership ruling (the Domain-8 FAM_009 precedent).**

---

# RANK 2 — TARGET vs TODAY'S AUTHORITY (rewritten: v1's list was mostly a method artifact)

Re-tested against **the generator's documented derivation** (the blend above) plus flat/complement
and the entry's own `rule`/`source` strings. **Six of v1's eight "non-derivable" rows are exact
blend hits** and are withdrawn: PROP_10d1211d (0.09/0.27 → 0.2455), REW263_WEL_OH (0.39/0.86 →
0.7959), REW26_WEL_SCREENING (0.23/0.47 → 0.4373), REW_BEN_046 (0.15/0.40 → 0.3659),
REW_BEN_FAM_002 (0.19/0.60 → 0.5441 — and its `rule` says so verbatim; the Diff-10/B5 ruling
governs the weeks-band shape, **not** this boundary, so v1 mis-cited it), REW_BEN_SICK_001 (M5).
**REW_BEN_REM_PAY_001** was self-contradictory in v1 (listed as failing while the same row said it
was derivable) — it is derivable, and the ordering objection against it is withdrawn too (R2-c).
What survives:

**R2-a · PROP_930043cc** — target 0.280, cell's `real_anchor` says 18%, cell's `notes` say *"28% ran
… (40% of large; 13% of SMEs)"*. **Not a derivation failure** (the figure is in the cell); it is the
**register cell contradicting itself**, already flagged at batch-7. **Fix: register cell (maintenance).**

**R2-b · EXT_REW_GAP_004 — v1 called this "−20.0pp unexplained". It is RULED AND CLOSED, and
v1 failed to check DECISIONS.** The entry's own source reads *"grade-2 register 'Yes 56%'
(seedreal-1 ruling, David 2026-07-24); supersedes grade-B legacy 76%"*, and DECISIONS (~9709-9760,
24 Jul) rules **LEAVE AS-IS** on the 56%, records the register row as internally inconsistent
(`seeded_headline` "Yes 56%" vs `real_anchor` 76%), **and rules that the entry's own provenance
stamp is FALSE — "grade 2" was seedreal-1 misreading the `tranche` column ("2 - leave/policy") as a
grade.** So: target correct, provenance stamp wrong, register row inconsistent. **Fix: provenance
stamp + register row (maintenance). No target change.** This repeats the grade-B-legacy trap the
sector-tilt memory already records.

**R2-c · REW_BEN_REM_PAY_001 — WITHDRAWN AS A DEFECT. There is no "stale ordering" defect class.**

> **CORRECTED 2026-07-29 (David-ruled). This row previously claimed a NEW defect class — "STALE
> `ruled_orderings` dragging N/A answers into the gate's base" — and put **95 orgs** inside the
> gate's measured base. BOTH were wrong, and the second was arithmetically impossible.**

The mechanism is real and correctly described: `qa_plausibility` builds `scope = set(ORDS[...])`,
not from live options, so an `is_na` label inside a ruled ordering does put N/A-flagged answers in
the measured base. Everything drawn from that mechanism was wrong:

1. **The count is 34, not 95.** 95 is the metric's *total* `is_na` headcount (61 `Not applicable`
   + 34 `Treatment varies by role or case`). `Not applicable` is **not in the ORDS scope**, so those
   61 are already excluded by the very mechanism this row called broken. **The gate's whole in-scope
   base is 94 — 95 orgs could never have sat inside it.**
2. **The ordering is not stale. It is RULED.** DECISIONS 7525-7532 (Diff 11, ruled + applied
   **18 July 2026**, commit 1aabdde): *"REM_PAY_001 ORDERING RULED: 'Treatment varies by role or
   case' is ORDINAL SECOND-LEANEST … **live is_na=true on 'varies' coexists (engine reshapes by
   ordering membership only)**. pf 'Base pay is protected' per the ruled extraction semantics (64%
   IS the protected share…). **Live landed 60 protected / 34 varies / 61 NA / 14 DK — 0.638 achieved
   on n=94 in-scope.**"* The `is_na` question was put and answered at ruling time, and **today's live
   state is identical to that ruled landing** (the 14 DK were stripped by r3sw13 two days later).
3. **The 0.64 target was extracted ON that base.** Removing the rung does not repair the metric — it
   changes the ruled denominator, which is why it detonates to **60/60 = 1.0000, +36.00pp**.
4. **The second instance is ruled too.** PROP_674db2fc's `Provided but access not tracked` is a
   **ruled KEEP** — r3sw13 (20 July 2026): *"substantive practice statements; not-measuring IS the
   finding"*. Its correction would move it 0.3395 → 0.3206 (−1.94pp, still PASS), but there is no
   defect to correct.

**Fix class: NONE. No ordering correction, no enforcing gate check** — an enforcing rule here would
criminalise two standing rulings with no exception mechanism. What survives is an **advisory**
surface so a future *accidental* inclusion is visible, and one genuine unrelated finding:
**REM_PAY_001's other two substantive rungs (`Base pay is adjusted immediately`, `Base pay may be
adjusted over time`) hold ZERO orgs** — a degenerate ladder, and a Phase-2 seed question, not an
ordering one. **My failure: I did not check the ruling history before calling a ruled artifact
stale — the exact discipline the `check-frozen-ruling-history` record exists to enforce.**

**R2-d · REW26_BEN_PENSION_MATCH — a CROSS-CELL BORROWED LEG.** Target 0.5141 = blend(16, 57); the
57 large leg is in its cell (Fig24), **the 16 SME leg is not — it is imported from REW_BEN_100's
notes** (*"Fig25 SME=16%"*), which the entry's `rule` states openly. Derivable, but from **two**
cells. v1 filed it clean under "frozen governs", which answers a different question. **Fix: none
mechanical; record the borrowed leg as a provenance note (maintenance).**

**R2-e · REW262_GOV_EQUALPAYAUDIT — the register records one source figure two ways.** Its
`real_anchor` says *"Equal-pay audit in last 12m: 35%"* (target 0.35) while REW_FAI_079's and
PROP_10d1211d's notes both say *"equal pay audit 32%"*, all citing CIPD PPT 2024. **Fix: register
reconciliation (maintenance).** (Same pair already flagged in the Domain-7 review.)

---

# RANK 3 — RANGE SOURCES (scope for the `target_range` schema extension)

**3 rows** whose register cell publishes a range while the target is a point:
- **REW_BEN_FAM_007** — *"31-45%"* → the ruled fix needs the schema.
- **REW_BEN_SICK_001** — *"60-66% large; 17-18% SME"* → any weighted derivation is itself ranged.
- **PROP_674db2fc** — *"34% … (37% private, 26% public, 17% voluntary; rises to 65% of 1,000+)"* → sector/size spread, currently pinned to a single 0.340.

**Your derived principle, applied:** *where a ranged source has been forced into a point target, the
seed has been reshaped toward a precision the source never claimed.* On these three the seed has
been reshaped to a fabricated precision. **The hand-pass was done by the reviewers and the count is ~9× higher: 28 of 40 cells publish
something other than a single unqualified point** — 3 explicit `n–m%`, 12 tilde-approximate, 5
"rises to"/"up from", 17 carrying two or more base-qualified rates. **Only 12 cells are true point
sources.** So the schema gap is not a 3-row curiosity: **on the majority of the set, the point
target is a precision the source never published** — and M5 shows the generator already handles it
silently by taking **range midpoints** (SICK_001's 17.5 and 63).

**The schema finding (already recorded in DECISIONS):** `qa_plausibility.py:174` reads
`float(entry["target_share"])` and gates on `abs(achieved − target) > 0.05`. **A range cannot be
expressed.** Proposed shape: `target_range: [lo, hi]`, gate tests membership plus the 5pp margin
*outside* the range, `target_share` fallback when absent. **Gate class; not built here.**

---

# RANK 4 — CONSTRUCT-MISMATCH RISK: `positive_from` unset on a >2-rung ladder

**23 of 40 targets** have **no `positive_from` AND a >2-rung ladder** (32 lack `positive_from`
outright — v1's sentence was loose). On a Yes/No pair the rung-1 cut is harmless; on a graded ladder
it silently redefines the construct.

**v1's "highest-risk" list was wrong in both directions and is replaced.** It named eleven metrics
while the prose twice said "the seven named above" (no set of seven existed), and three nominations
are contradicted by the entry's own `rule` string — **PROP_674db2fc** (*"constrains provision limb
only, access-rate bands unanchored"* — the rung-1 cut IS the anchor's construct),
**REW263_GOV_BENOBJ** (*"constrains objectives limb only"*), and one further row on the same basis.
Two more were weak: **REW_FAI_079**'s construct gap is 4.1pp (passes either way) and
**REW263_WEL_FINWELL**'s is 1.4pp (its real exposure is M7's coherence, not the cut).

**The quantified list, by construct gap:** **REW_BEN_FAM_009 58.0pp** (→ promoted to M6) ·
**REW_BEN_FAM_007 29.4pp** (M2) · **REW_BEN_FAM_010** — same *paid*-anchor shape as its two
siblings, and **just re-graded A→B** · **REW_BEN_046 6.8pp**, missed by v1 entirely: the anchor is
specifically *"Group income protection / long-term disability"* while the cut counts 15
"Short-term only" orgs as positive (0.3636 vs 0.2955 on the long-term-inclusive reading), and the
register itself flags the basis problem. The remainder need a per-row anchor-vs-cut check; those
four are where it starts.

---

# RANK 5 — CLEAN

The remaining rows reproduce their targets within the gate's tolerance with a derivation traceable to
today's authority and no detected masking. They are clean **in the fidelity sense** — subject to the
headline caveat that fidelity is what the gate measures.

---

# CONTEXT FINDINGS

**1 · The `_source` stamp and the convention it implies.** The stamp names a register file that is two
versions stale (`CLAUDECODE.csv` → v2026-07-24 → v2026-07-29). **Proposed convention (for ruling):**
*a target set is only as current as the register it was generated from.* Concretely — (a) `_source`
records the resolved register **filename + row count** at generation; (b) any register version bump
opens a reconciliation obligation for targets whose rows changed; (c) `generate_marginals.py`
already resolves through `register_resolve` (follow-up 1), so the stamp can be made self-maintaining;
(d) a gate check comparing the stamp against the resolver's current answer would make staleness
**loud** instead of latent. **(d) is the cheap high-value piece.**

**2 · Targets on metrics that no longer render market verdicts — moot, flagged, NOT deleted (5):**
`CAR_STATUS_01`, `REW263_GOV_BENOBJ`, `REW263_GOV_UKPAYTRANS`, `REW_BEN_FAM_007`, `REW_INC_072` —
all now **Practice-class** (Tier-2 and Domain-8 routings). Their targets still gate the *seed shape*,
which remains legitimate (prevalence still renders on practice surfaces), but they no longer defend a
market verdict. **Ruling needed: do Practice-class metrics keep register-marginal targets?** My read:
yes — prevalence is still shown to members — but the question should be settled explicitly rather
than left implicit.

**3 · frozen-8 × gm — CORRECTED: they cannot conflict, because the gm target never runs.**
v1 framed this as "4 rows exposed". The truth is sharper: the if/elif chain means EAP, FINWELL,
STRATEGY and PENSION_MATCH are evaluated **only** against their frozen distributions; their gm
targets are unreachable. The values happen to agree to ≤0.2pp, but agreement is irrelevant — one
side is dead code. **The real findings: (a) four gm entries are inert and should be marked as such
rather than maintained as if live; (b) the gm file's `settled_refreeze` block already names them and
NOTHING READS IT — an inert declaration of an inert fact; (c) if a future ruling ever wants one of
those four to move, the frozen side governs and the ruled unfreeze → reshape → re-freeze cycle
applies (batch-2 SALSAC precedent).**

---

# What this sheet does NOT answer (named, not guessed)
- **The maternity pin** needs the two source documents read (M4) — no desk analysis resolves it.
- **Six hand-reads** (Rank 2) need their register cells read against their sources: GAP_004,
  PROP_10d1211d, WEL_OH, WEL_SCREENING, BEN_046, plus SICK_001's provenance (M5).
- **The 23 construct-mismatch rows** need a per-row anchor-vs-gate-construct check; the seven named
  above are where I would start.
- Whether the implicit-range count exceeds the three detected (a prose pass over all 40 cells).


---

# APPENDIX B — the 12 targets outside `marginals` (scope-corrected; five-diagnostic pass NOT yet run)

| tier | target | status | live n | entry shape |
|---|---|---|---|---|
| 2b ruled_distributions | REW_PAY_005 | active | 192 | distribution · grade · source · semantics |
| 2b | EXT_REW_GAP_010 | active | 161 | " |
| 2b | REW265_PAY_RANGEMAX | active | 220 | " |
| 2b | REW_PAY_TIPS_EXIST_7c80c508 | active | **27** | " (near the n<5 skip floor for sub-cuts; also Diff-18 ruled Practice) |
| 2b | REW264_HLT_VIRTUALGP | active | 220 | " |
| 2c maturity_gradients | **REW_BEN_HOL_001** | active | 211 | key · within_band · band_distributions · sector_gate · grade — **also governed by r3sw4** |
| 2c | PROP_fe1a29ec | active | 215 | positive_option · anchors · remainder_options · remainder_ratio · sector_gate |
| 2c | REW_FAI_128 | active | 220 | " |
| 2c | REW_PAY_001 | active | 220 | " |
| 2c | **REW_INC_103** | active | 220 | key · within_band · … — **the Tier-1A corrected ladder** |
| 2c | REW26_BEN_PENSION_TYPE | active | 220 | " (**frozen-8 member** — the unfreeze-cycle exposure applies) |
| 2d multiselect_incidence | REW265_BEN_PMICOMP | active | 154 | prevalences · terminal · base · grade · source |

**Follow-up scope:** the same five diagnostics over these 12, with two structural questions the
`marginals` pass did not have to ask — (a) for tier 2c, whether the per-band anchors survive the
size/sector rulings made since Diff 1 (HOL_001's r3sw4 supersession is the known case), and (b) for
tier 2b/2d, whether the ruled distribution/incidence entries were themselves derived from the seed
rather than the source (the M5 circularity test, applied per entry). **PENSION_TYPE additionally
sits in the frozen-8**, so any correction there inherits the unfreeze → reshape → re-freeze cost.


---

# VERIFICATION (adversarial, three reviewers — all REFUTED v1; every correction folded above)
- **replica-and-drifts: REFUTED.** Confirmed: the gate-reading method, all quoted achieved values,
  the band counts 37/2/1/0, the max-drift metric identity (REW_FAI_088), the `_source` stamp, the
  30 coherence pairs, the 48 no-OSP orgs. Refuted: the median (0.10 → **0.14pp**), the table's max
  (4.10 → **4.09pp**, contradicting the sheet's own method note), M1's post-repair figure
  (51.8% reproduces under **no** base definition), the 40-vs-47 explanation (**FROZEN shadowing**,
  not n<5), and the "reproduces the live gate exactly" claim (the 47 it cites shares only 36 rows
  with the 40 it tabulates).
- **masked-and-pins: REFUTED** on the same statistics plus M5, and it **proved the maternity pin
  independently** (23–24 forced, 25 observed) — that finding stands.
- **adjudications-and-context: REFUTED**, most consequentially: **six of eight Rank-2 rows are exact
  hits of the generator's documented cohort blend**, which v1 never read; **M5's circularity charge
  is false**; **GAP_004 is ruled and closed** (and its provenance stamp is itself a recorded
  falsehood); PENSION_MATCH borrows an SME leg from another register row; the implicit-range count
  is **28 of 40**, not 3; two `ruled_orderings` entries carry an is_na option inside the gate's base
  (REM_PAY_001: **34** orgs — *the reviewer said 95 and called both entries stale; **both claims are
  withdrawn**, see R2-c*); **FAM_009 (58.0pp) and WEL_FINWELL (108-org contradiction)
  belong in Rank 1**; and duplicate-anchor families make several targets non-independent.

**Owned plainly: v1's Rank 2 was largely a method artifact.** I derived from register cells and
ignored the gm entries' own `sme`/`large`/`rule`/`source` fields, which state the arithmetic. The
corrected sheet has fewer false alarms and four *more* real findings than v1 — the net effect of the
adversarial pass was to make the workstream smaller and sharper, not larger.

---

# CORRECTIONS — three falsehoods removed from this sheet (David-ruled, 2026-07-29)

Recorded here so they cannot regenerate from a later reading of an uncorrected passage.

**C1 · "8 targets that match no figure derivable from their own register cell" (was line 62).**
False. **Every target but EXT_REW_GAP_004 is derivable from its own register cell; GAP_004's is
derivable from a ruling (seedreal-1); PENSION_MATCH's only across two cells.** The "8" was a v1
figure that survived the v2 rewrite unedited while the v2 body dismantled the very list it counted.
**Origin of the phantom pair, so it cannot come back:** exactly **8 of the 40 gm entries carry a
`positive_from`** and **32 do not** — the 8/32 split is the `positive_from` census wearing a
derivability label. It was never a derivability finding.

**C2 · "95 orgs holding an N/A answer are inside the gate's measured base" (was R2-c).**
False, and self-refuting: the gate's whole in-scope base for REM_PAY_001 is **94**. **The figure is
34.** 95 is the metric's total `is_na` headcount; the other 61 (`Not applicable`) were never in the
ORDS scope and were already excluded.

**C3 · "a NEW defect class: STALE `ruled_orderings`" (was R2-c).**
False. **Both instances are standing David rulings, not staleness** — REM_PAY_001's ordering was
ruled 18 July 2026 *with the `is_na` coexistence explicitly considered and the resulting n=94 base
recorded*, and PROP_674db2fc's option is a ruled KEEP from r3sw13 (20 July 2026). I called two ruled
artifacts stale without reading their rulings. **The reviewers' mechanism was sound; my inference
from it was not**, and it escalated through the ruling table into two ruling prompts before the
artifact's own note caught it.

**What this does NOT change:** every other finding in this sheet stands as verified — the headline
(fidelity-not-truth), the MASKED rows M1/M2/M3-M4/M6/M7/M8, M5's withdrawal, R2-a/b/d/e, the 28-of-40
range count, the 23 construct-mismatch rows, and Appendix B's scope.
