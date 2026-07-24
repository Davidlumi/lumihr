# Register-maintenance pass — M1 INVENTORY · 2026-07-24 · READ-ONLY (nothing applied)

Live register: `lumi_anchor_register_CLAUDECODE.csv` (Jul 19, **249 rows**, 16 columns). Every change
below cites its authority; cell-level effect stated; anything queued-but-unruled sits in the exceptions
table, not here. **STOP after this file — M2 applies only what David approves.**

Schema note: the CSV already has a free-text `status` column ("ANCHORED", "unanchored - needs research",
…) — **no new column is needed**; retirements use `status`.

## The changes (10 groups, 216 row-touches, +6 rows)

**C1 · 8 retirements — authority: Phase-R ruling (DECISIONS c0d9638).**
Rows RETAINED (research preserved); cell effect per row: `status` → `"RETIRED (ruled 2026-07-24, Phase R — metric retired in live bank)"`; `notes` gets an appended `[maint-2026-07-24: retired]` breadcrumb. Rows: ALLOW_01 · PROP_dff9a2a5 · REW_PAY_022 · REW_PAY_126 · REW_PAY_HOURLY_MIN_1c6e096f · REW_PAY_MKT_POS_01 · EXT_REW_GAP_006 · REW_FAI_091. (8 rows, 2 cells each.)

**C2 · CONTEXT_AE_OPTOUT — authority: Task-0 ruling (DECISIONS c0d9638).**
`status` → `"RETIRED (ruled 2026-07-24 — never wired to platform)"`; `notes` appended: `"TPR AE opt-out rate remains a candidate engine context-input (anchor survives)"`. (1 row.)

**C3 · PMIMH→PMICOMP reconciliation — authority: Phase-R ruling (r3sw8 evidence).**
Finding: **REW265_BEN_PMICOMP already has its own populated row** (ANCHORED, notes already cite "R3SW8 REDESIGN: replaces REW263_BEN_PMIMH"). So this is NOT an id rename: PMIMH's row gets `status` → `"RETIRED-SUPERSEDED → REW265_BEN_PMICOMP (r3sw8; Phase-R ruling 2026-07-24)"`. PMICOMP row untouched. (1 row.)

**C4 · PENSION_TYPE empty-anchor fill — authority: Domain-3 review ruling (DECISIONS 632b080).**
The schema CAN express the supersession via text fields. REW26_BEN_PENSION_TYPE: `real_anchor` (currently EMPTY) → `"SUPERSEDED-BY-FROZEN-TARGET: operative anchor = frozen_targets.json (DC 88.6% / DB 9.5% / Hybrid 1.8%, re-frozen at Diff-15-underpeaking)"`; `source` appended `"; operative authority: frozen_targets.json per Domain-3 ruling 2026-07-24"`; grade stays A. (1 row.)

**C5 · Full-text question storage — authority: the Domain-2/3 truncation-artifact finding + this prompt's instruction.**
`question` cell ← full live question text (join on metric_id), for **ACTIVE metrics whose stored text ≠ live text: 195 rows**. The 10 rows whose metric is retired/absent (the 8 + PMIMH + AE_OPTOUT) **keep stored text** as instructed. Kills the wording-drift artifact class; the Wellbeing-review C-section per-row drift-withdrawal confirms (held) become moot.

**C6 · Tranche-1 additions — authority: PASS3_tranche1_verified (David sign-off 2026-07-24). Values verbatim from the ratified file; nothing from recall. +6 NEW rows:**
- `REW264_HLT_CASHPLAN` — A · ANCHORED · anchor: "Health cash plans: 23% all; 27% all-or-some (+3% dependent, 5% planned); size: SME 21 / Large 26 / VL 31 (to-all)" · source: CIPD RM 2022: Focus on employee benefits (Fig 7 + size table) · base: all-UK employers (CIPD/YouGov) · notes: funding split (employer-paid vs voluntary) unanchored; Feb-2026 refresh NEEDS-VISUAL-CHECK.
- `REW264_HLT_OPTICAL` — A · ANCHORED · "Free eye tests/eye-care vouchers: 63% all; 72% all-or-some; SME 61 / L 67 / VL 69; +17pp vs 2018" · CIPD RM 2022 · notes: anchor is provision-any — upper bound for the live "beyond DSE statutory" framing.
- `REW264_WEL_EWA` — A · ANCHORED · "Earned pay access: 11% all; 3% dependent; 14% all-or-some" · CIPD RM 2022 · notes: CORRECTED from drafted 10%; CIPP corroboration NOT registered (documents not held).
- `REW264_WEL_SEASONTICKET` — A · ANCHORED · "Season-ticket loan: 25% all + 5% some = 30%; size (to-all): SME 20 / L 33 / VL 42" · CIPD RM 2022 (Fig 10 + Table 20) · notes: replaces drafted 2018 recall.
- `REW265_TIME_FLEXPATTERN` — A · ANCHORED (partial) · **prose-verified quantities ONLY**: "28% offer some form of four-day week (most commonly compressed hours); Net-any-flexible 88%; four-day net 14%" · source: CIPD Flexible and hybrid working practices in 2025 (Jul 2025, employer n=2,050) · notes: **Figure-1 per-arm columns + annualised NOT ENTERED — held for David's visual check; "core hours" not a surveyed arm (partial option mapping)**.
- `REW264_PAY_HOLPAYMETHOD` — A (statutory) · ANCHORED (statutory reference) · **SI citation CONFIRMED LIVE against legislation.gov.uk (2026-07-24)**: The Employment Rights (Amendment, Revocation and Transitional Provision) Regulations 2023, **SI 2023/1426** (Part 2: Annual leave and holiday pay) inserting **WTR 1998 reg 16A — "Rolled-up holiday pay for irregular hours workers and part-year workers", 12.07% uplift** · bound/context anchor (no prevalence).

**C7 · PROFITSHARE — NOT ENTERED** (authority: David's sign-off). Stays on the wants-list ("CIPD RM: Focus on pay edition"); no re-grade this pass.

**C8 · Grade census (derived):**
| grade | before | after | delta |
|---|---|---|---|
| A | 64 | **70** | +6 (tranche-1) |
| B | 27 | 27 | — |
| C | 8 | 8 | — |
| EST | 9 | 9 | — |
| mixed-grade (3 legacy rows) | 3 | 3 | — |
| blank | 138 | 138 | — |
| **rows** | **249** | **255** | **+6** |

**C9 · Versioning proposal (David ratifies at this STOP):**
- New canonical file: **`lumi_anchor_register_v2026-07-24.csv`** (the M2 output). The Jul-19
  `lumi_anchor_register_CLAUDECODE.csv` is **never edited — preserved as the prior version**; the Jun-21
  JSON stays marked stale.
- Rule: *the highest-dated `lumi_anchor_register_vYYYY-MM-DD.csv` in the repo is canonical; every version
  is recorded in DECISIONS with its census.* No in-file version row (CSV consumers parse rows as metrics).
- **Consumer follow-up (reported, NOT changed in M2 — code class):** `generate_marginals.py` and
  `register_clean_diff1.py` reference the CLAUDECODE filename; both are offline tools, not runtime. Their
  path update is queued.

**C10 · Platform-tag follow-up preview (M2 reports, never changes):** the 6 tranche-1 metrics are
currently classified never-in-register with `unbenchmarked` tags — after M2 they have register rows, so
their live classification is stale → queued follow-up (config class, its own diff).

## Exceptions table (queued-but-unruled — NOT applied)
| item | why excluded |
|---|---|
| `seeded_headline` column refresh (June snapshot, stale for every reshaped metric) | never queued/ruled; superseded in practice by live recompute doctrine — future maintenance candidate |
| PMICOMP's own empty `real_anchor` cell (grade "B (structure)/EST (incidence)") | not queued; its anchor work is r3sw8-era, untouched |
| The 2 remaining mixed-grade legacy rows + 138 blank-grade rows | grade normalisation never ruled |
| Wellbeing C-section drift-withdrawal per-row confirms (HOLD) | mooted by C5; no separate action |

**STOP.** M2 applies exactly the approved rows above to the new versioned CSV — cell-level diff asserted against this inventory, prior CSV untouched, no DB/config/engine/code change.
