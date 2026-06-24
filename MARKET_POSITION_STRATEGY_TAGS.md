# Strategy reframe tags — review (David)

The reward-strategy capture's two remaining reframes (handover §5.2) are wired in the
engine but gated on per-metric **config tags** in `data/market_position_config.json`.
Claude auto-detected a conservative candidate set from the catalogue; **confirm or refine
below — the config hot-reloads, no redeploy.** Both reframes are opt-in (they only fire
when an org sets the matching dial), so a wrong tag is low-risk and never fabricates.

## `family_metric` — for `family_position = "Generous"` (over)
When an org declares a generous family stance, a family-benefit metric that reads **above
market / high spend (save)** is relabelled **"intended — your generous family stance"** and
demoted in the briefing (it's by design, not overspend). A family metric that's **below**
market is deliberately left as a flag — being below contradicts the stance, so it's worth
surfacing (trust rule: never hide a real gap).

| tagged | metric | what it measures |
|---|---|---|
| ✓ | `REW_BEN_FAM_001` | Maternity & adoption pay vs statutory |
| ✓ | `REW_BEN_FAM_002` | Weeks of enhanced maternity / adoption pay |
| ✓ | `REW_BEN_FAM_005` | Enhanced shared parental pay above statutory |
| ✓ | `REW_BEN_FAM_006` | Paid parental leave beyond statutory |
| ✓ | `REW_BEN_FAM_007` | Paid carer's leave |
| ✓ | `REW_BEN_FAM_012` | Paid menopause leave |
| ✓ | `REW262_TIME_BEREAVEMENT` | Paid bereavement leave above statutory |

To add/remove: set `"family_metric": true` on the metric's entry (or delete the key).

## `location_scoped` — for `location_approach = "Anywhere"` (agnostic)
A one-rate (location-agnostic) org's **per-location pay** metrics aren't applicable, so
they're dropped from the competitiveness gauge AND their "below local market" signals are
suppressed. Conservative: only genuine per-location-pay metrics.

| tagged | metric | what it measures |
|---|---|---|
| ✓ | `REW_BEN_REM_PAY_002` | Location used to determine base pay for remote roles |

Candidates deliberately NOT tagged (not per-location *pay*): `EXT_REW_GAP_010` (where remote
staff may work), `PROP_c1a3da61` (relocation support availability) — confirm or add.

---
_Both reframes degrade byte-for-byte when the org hasn't set the dial or no metric is tagged
(strategy=None / no tag → today's output). Tags live in `market_position_config.json`._
