# Freeze-gate negative-test evidence (Diff 12, 18 July 2026)

Proves qa_plausibility Check C ENFORCES (not just records) after wiring into run_gates.sh
as gate 11. All perturbations were made on scratch throwaway copies (SQLite backup API);
live lumi.db was never written — asserted after the runs: answers 233,288, EAP Yes=160
(0.7273), REC_IMPACT Yes=96 (0.436), all at pre-test values.

## Tiered failure semantics (David's ruling)
- **Tier 1 — settled-frozen** (= `frozen_targets.json` keys, 8): hard FAIL on any
  per-option drift > 0.001. Hand-ruled, immovable.
- **Tier 2 — register marginals** (`generated_marginals.json`, 46; 4 overlap the frozen
  set and take tier-1 precedence → 42 checked): hard FAIL only on achieved-vs-target
  drift > 5pp. They keep their ±4ppt reshape freedom.

## Runs (same script, three DBs selected via LUMI_DB — also proves LUMI_DB honoured)

| db | perturbation | expected | observed | exit |
|---|---|---|---|---|
| live `lumi.db` | none | PASS | settled max drift 0.005pp; marginals max 0.41pp | **0** |
| `perturbed.db` | EAP 5×No→Yes (2.27pp > 0.1pp tol) + REC_IMPACT 15×No→Yes (6.9pp > 5pp) | FAIL both tiers | `** MARGINAL-DRIFT REW263_REC_IMPACT achieved 0.505 vs target 0.436 (6.9pp)` + `** FROZEN-DRIFT REW26_WEL_EAP 2.27pp vs frozen_targets.json` | **1** |
| `smallperturb.db` | REC_IMPACT 5×No→Yes (2.31pp < 5pp) | PASS (freedom preserved) | settled 0.005pp; marginals max 2.31pp | **0** |

## Full-suite runs
- **Negative** (`LUMI_GATES_SRC=perturbed.db`): `PASS (10) … FAIL (1): qa_plausibility (rc=1)`.
  The other ten gates ALL passed on the breached data — the "guard was dark" finding
  demonstrated live: no other gate sees a freeze drift. Suite exit 1 (zsh EXIT trap
  preserves the failure status through teardown — verified: `trap … EXIT; exit 1` → 1).
- **Positive** (clean throwaway): `PASS (11)` incl. qa_plausibility, suite exit 0.

## Revert
Perturbations existed only in scratch copies (discardable); live asserted untouched above.
qa_reseed re-run on live after the single-source SETTLED change: 9/9, unchanged.

## Single source reconciliation
`frozen_targets.json` keys ARE the settled set. Both `qa_reseed.py` and
`qa_plausibility.py` now derive SETTLED from it; the two hardcoded copies are gone.
Missing file is now FATAL in qa_plausibility (a silent `{}` fallback would put the
gate back in the dark).
