---

## 2026-06-21 - Master recheck + reseed (whole register audited; 6 shipped, rest protected)

**What this was.** A full marginal-level recheck of all 121 anchored register rows against live `benchmark_snapshots` (snapshot 1), staged read-only -> eligible-list -> dry-run -> double-guarded write. Goal stated by David: maximise how *realistic* the seeded data is to a UK reward user, not maximise anchor-matching for its own sake.

**Headline finding: the seeding was already overwhelmingly realistic.** Most apparent "drift" was MAPPING ARTIFACT, not wrong data - the register anchors a target % but not the anchor->live-option mapping, so naive comparison over-counts. The session-fixed metrics (EAP/screening/bereavement) and a validation tier all landed on-anchor, confirming the pipeline. **Do not threshold naively off raw drift distributions** - verify mapping first.

**Shipped (6 confirmed-clean, gap 2-10pp, unambiguous mapping, latent-paired):**
| metric | -> realised |
|---|---|
| OT_04_b14623a6 | 59.8 -> 63.1% |
| REW_BEN_HOL_004 | 50.0 -> 56.9% |
| REW_BEN_HOL_003 | 40.1 -> 44.2% |
| REW_FAI_STUDY_TIME_93b6ef22 | 62.6 -> 69.9% |
| REW263_BEN_CICOVER | 20.0 -> 23.2% |
| PROP_8862fcad | 82.6 -> 77.0% |

All within +-0.2pp. **G4 coherence 0.345 -> 0.372 (IMPROVED)** - latent-pairing strengthened cross-area coherence. qa_reseed 9/9; qa_plausibility no new drift; idempotent. Backup `lumi.db.bak_pre_recheck6_20260621_132236`. None frozen (no frozen_targets.json edit).

**Dropped, with reasons (do NOT re-flag as drift next sweep):**
- `REW263_PAY_SSPALIGN` - anchor 62% is a SENTIMENT stat (think SSP too low), not alignment-readiness prevalence. Concept mismatch.
- `REW_BEN_FAM_008` - anchor 86% is PAID-only; live offer-total includes 30.7% unpaid. Base mismatch -> paid-basis verify batch.
- `REW_INC_104` - target 100% forces no-bonus NA orgs into bonus bands; structurally implausible.
- `REW_BEN_REM_PAY_001` - 99.4% NA base; near-zero real base to reshape.
- `REW263_BEN_PMIEXCESS` - direction/base unconfirmed ("No excess" is the generous option) -> verify batch.
- `REW_INC_060` (Operational-KPIs option) - 31% anchor is COST-CONTROL not operational, off weak 2019 FTSE-skewed legacy base. Needs proper per-option remap.

**Income protection ruling:** `REW_BEN_046` - the session-shipped **42%** (GRiD-flagged judgement) **HOLDS**; the register's 25% estimate is **superseded**. Not drift.

**Held for a later BASE-VERIFY batch (not done this session):** Tier-2 group-(4) genuine under-seed candidates (each needs its base confirmed before eligible) + FAM_008 (paid basis) + PMIEXCESS. The Tier-2 group-(1) over-count, group-(2) large-base-mismatch, and group-(3) band/value rows were REJECTED as artifacts - not drift, do not revisit.

**Method confirmed (carry forward):** org-blind latent-pairing (firmographic-only latent, on-spine, G4-safe) for all reseeds; dry-run first; `--write --confirmed-by-david`; writes to both `answers` + `answers_history`; separate `aggregate.run_snapshot(1)`; QA = qa_reseed 9/9 (G4>=0.30) + qa_plausibility no-new-drift. There is no `qa_release.py`. The mandatory two-row mapping call-out in the dry-run caught both SSPALIGN and FAM_008 as mismatches before any write - keep that call-out step for future reseed batches.
