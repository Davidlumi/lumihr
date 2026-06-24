# Market Position — firewall review (David)

Claude auto-classified all **206** live metrics (handover Part A). The build runs on this auto-pass; **you refine the flagged subset below via hot-reload** — edit `data/market_position_config.json` and the engine picks it up, no rebuild, no gate (pre-launch).

**Work top-down; stop when confident.** Priority of harm: **direction** (misleads) › **competitiveness** (skews the headline) › **class** (gauge in/out) › lens (cosmetic, not shown here). Only flagged metrics appear; everything else rides.

**To override:** edit the metric's entry in the config — `class` (Level/Provision/Practice/Design), `direction` (higher_is_better/lower_is_better/neutral, or null for Practice/Design). Tick `[x]` here when confirmed.

_Net effect of the auto-pass: 64 higher-is-better Substance metrics feed the competitiveness gauge; Governance is out of the headline._


## 1 · Directions to confirm  (16) — do these properly

The only set that produces misleading output if wrong: a `lower_is_better` metric left on the default reads as an amber “gap” when it's actually favourable; a true `neutral` shown as a verdict becomes the CFO's amber flag. Confirm each.

| ✓ | Metric | Domain | What it measures | Proposed `direction` | Why flagged |
|---|--------|--------|------------------|----------------------|-------------|
| [ ] | `REW_INC_070` | Incentives | Are malus provisions used (reduce unpaid awards) for misconduct/risk/compliance issues? | **lower_is_better** | lower_is_better — from curated polarity |
| [ ] | `RED_COST_01` | Benefits | What was the average redundancy cost per employee in the last completed 12-month period? | **neutral** | neutral — U-shaped / cost / count: context, not a verdict |
| [ ] | `REW26_BEN_PENSION_COST_SHARE` | Benefits | Employer pension cost as a % of total reward spend? | **neutral** | neutral — U-shaped / cost / count: context, not a verdict |
| [ ] | `PROP_9e4ad87f` | Pay | What was the overall salary increase budget (merit/annual review) as a percentage of payro | **neutral** | neutral — U-shaped / cost / count: context, not a verdict |
| [ ] | `PROP_d16bae79` | Pay | What was total workforce cost per FTE in the last completed financial year (in GBP)? | **neutral** | neutral — U-shaped / cost / count: context, not a verdict |
| [ ] | `PROP_e63cf45a` | Pay | What was total workforce cost as a percentage of revenue in the last completed financial y | **neutral** | neutral — U-shaped / cost / count: context, not a verdict |
| [ ] | `REW_BEN_045` | Benefits | What life assurance cover is provided for the main population (multiple of salary)? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_INC_071` | Incentives | Are clawback provisions used (recover paid awards) in defined circumstances? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_INC_131` | Incentives | Does your organisation operate any long-term incentive or equity plans for any levels? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_INC_135` | Incentives | Does your organisation operate sales commission or commission-based incentive plans? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_BEN_058` | Pay | In the last 12 months, have you enhanced benefits in response to cost-of-living or labour  | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_PAY_011` | Pay | Do you pay overtime? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_PAY_TIPS_EXIST_7c80c508` | Pay | Do employees receive customer tips or service charges as part of their total earnings? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `EXT_REW_GAP_004` | Recognition | Do you operate a long service award scheme? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_PAY_014` | Time Off | What is the standard premium for working on UK bank holidays where applicable? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |
| [ ] | `REW_BEN_REM_PAY_005` | Wellbeing | Do any pay premiums or discounts apply specifically to remote roles? | **higher_is_better** | DEFAULTED higher_is_better — confirm (no curated direction) |

## 2 · Governance carve-out  (41) — one scan

Every Governance metric is **out of the headline** (`_domains.Governance.competitiveness = false`): it shows favourable / context / differs, never a below/on/above verdict. Confirm this is the right set (nothing here should be competing on a market rate).

| ✓ | Metric | Proposed `class` | `direction` | What it measures |
|---|--------|------------------|-------------|------------------|
| [ ] | `PAYTR_01_42eae7ec` | Provision | higher_is_better | Do job adverts typically include a salary or salary range? |
| [ ] | `PAYTR_03_db0108d6` | Practice |  | Is there a formal policy describing pay progression within bands? |
| [ ] | `PROP_10d1211d` | Practice |  | Does your organisation run disability pay gap analyses (or pay equity analyses by disabili |
| [ ] | `PROP_216f7323` | Practice |  | Which pillars are explicitly included in your total rewards strategy? |
| [ ] | `PROP_34ffb6e2` | Practice |  | Which best describes how promotion decisions are governed? |
| [ ] | `PROP_38555969` | Practice |  | Do you have a documented annual reward/benefits communication plan (e.g., pay review comms |
| [ ] | `PROP_674db2fc` | Practice |  | Does the organisation provide total reward statements to employees, and what proportion of |
| [ ] | `PROP_8862fcad` | Practice |  | Does your organisation have a documented total rewards strategy that integrates pay, benef |
| [ ] | `PROP_930043cc` | Practice |  | Does your organisation run ethnicity pay gap analyses at least annually? |
| [ ] | `PROP_aa4061d5` | Practice |  | How does your organisation measure the effectiveness of reward/benefits communications? |
| [ ] | `PROP_cdff5737` | Practice |  | Does the organisation run pay equity analyses across comparable roles (e.g., gender, ethni |
| [ ] | `PROP_d65a16e9` | Practice |  | When was your total rewards strategy last refreshed or formally reviewed? |
| [ ] | `PROP_d992b2ea` | Practice |  | Is there a standard minimum time-in-role or time-in-grade expectation before promotion (wh |
| [ ] | `PROP_e1d1e604` | Design |  | Approximately what proportion of employees receive an off-cycle pay increase outside the a |
| [ ] | `PROP_ef4ff31e` | Practice |  | Do you monitor promotion rates by protected characteristics to identify equity issues? |
| [ ] | `REW262_GOV_ACTIONPLAN` | Practice |  | Do you have a published equality action plan, and which characteristics does it cover? |
| [ ] | `REW262_GOV_AIINPAY` | Practice |  | Do you use AI tools in pay decisions, and with what governance? |
| [ ] | `REW262_GOV_EQUALPAYAUDIT` | Practice |  | Do you run proactive equal-pay audits, and how often? |
| [ ] | `REW262_GOV_EQUALVALUE` | Practice |  | Can you group your workforce into categories of equal value (by skills, effort, responsibi |
| [ ] | `REW262_GOV_PAYINADVERTS` | Practice |  | Do you include pay or a pay range in job adverts? |
| [ ] | `REW262_GOV_SALHISTORY` | Practice |  | Have you removed salary-history questions from your hiring process? |
| [ ] | `REW26_GOV_EU_PTD_PREP` | Practice |  | How prepared are you for the EU Pay Transparency Directive (2026)? |
| [ ] | `REW_FAI_079` | Practice |  | Does your organisation conduct gender pay gap analysis at least annually? |
| [ ] | `REW_FAI_081` | Practice |  | Are pay decisions reviewed for fairness before implementation (e.g., calibration, central  |
| [ ] | `REW_FAI_082` | Practice |  | Are exceptions to standard pay rules formally documented with justification? |
| [ ] | `REW_FAI_085` | Practice |  | Does your organisation review pay outcomes for compression and internal equity as part of  |
| [ ] | `REW_FAI_086` | Practice |  | Does your organisation review incentive outcomes by protected characteristic (where data i |
| [ ] | `REW_FAI_087` | Practice |  | Does your organisation have a documented pay transparency approach or policy? |
| [ ] | `REW_FAI_088` | Practice |  | Do employees have access to pay ranges for their grade/role family? |
| [ ] | `REW_FAI_089` | Practice |  | Does your organisation publish pay ranges on job adverts? |
| [ ] | `REW_FAI_091` | Practice |  | Over the next 12-24 months, do you plan to expand external pay transparency? |
| [ ] | `REW_FAI_092` | Practice |  | Have you completed a pay transparency readiness assessment (e.g., audit of structures, dat |
| [ ] | `REW_PAY_001` | Practice |  | Are formal pay ranges defined for all permanent roles? |
| [ ] | `REW_PAY_002` | Practice |  | Are pay ranges linked to a documented job evaluation or grading framework? |
| [ ] | `REW_PAY_003` | Practice |  | How often are pay ranges reviewed and refreshed using market data? |
| [ ] | `REW_PAY_006` | Practice |  | Does your organisation use external pay benchmark data when setting pay ranges or offers? |
| [ ] | `REW_PAY_019` | Practice |  | Are allowances consolidated into base pay at any point (e.g., on promotion or contract cha |
| [ ] | `REW_PRO_030` | Practice |  | Is progression eligibility linked to performance outcomes? |
| [ ] | `REW_PRO_034` | Practice |  | Does your organisation use promotion guidelines that specify recommended salary positionin |
| [ ] | `REW_PRO_035` | Practice |  | What is pay progression based on outside of the annual review and promotions? |
| [ ] | `REW_PRO_098` | Level | higher_is_better | What is the typical maximum pay increase for promotions? |

## 3 · Class edge cases  (9) — confirm out of the gauge

The deliberate edge: metrics **measured** binary/numeric but classed by **meaning** as a Practice or structural Design — so they tag “differs” and stay out of the competitiveness verdict. Confirm none should actually be a Level/Provision in the gauge.

| ✓ | Metric | Domain | Type | Proposed `class` | What it measures |
|---|--------|--------|------|------------------|------------------|
| [ ] | `RED_PROC_01` | Benefits | binary | **Practice** | Is there a documented redundancy process applied consistently? |
| [ ] | `RED_PROC_02` | Benefits | binary | **Practice** | Are selection criteria for redundancy documented and objective? |
| [ ] | `RED_PROC_03` | Benefits | binary | **Practice** | Are redundancy outcomes reviewed for fairness and bias? |
| [ ] | `RED_PROC_05` | Benefits | binary | **Practice** | Are line managers trained to manage redundancy conversations? |
| [ ] | `PAYTR_03_db0108d6` | Governance | binary | **Practice** | Is there a formal policy describing pay progression within bands? |
| [ ] | `PROP_d992b2ea` | Governance | binary | **Practice** | Is there a standard minimum time-in-role or time-in-grade expectation before promotion (wh |
| [ ] | `REW262_GOV_SALHISTORY` | Governance | binary | **Practice** | Have you removed salary-history questions from your hiring process? |
| [ ] | `REW_INC_065` | Incentives | binary | **Practice** | Is there a gatekeeper metric (e.g., profit, safety, compliance) that must be met for any p |
| [ ] | `ALLOW_02` | Pay | binary | **Practice** | Are allowances reviewed regularly as part of reward governance? |

## 4 · Everything else rides  (143 unflagged)

Obvious Level / Provision at `higher_is_better`, and all lens assignments, need no review — refine opportunistically later via hot-reload. The auto-pass errs toward **Approach / out-of-gauge** on ambiguity (safer than a false Level verdict).


---
_Generated by `server/gen_market_position_review.py` from `data/market_position_config.json`. Re-run to refresh after edits._
