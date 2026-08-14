# Sector persona QA — findings + seed-realism v2 plan (2026-08-14)

14 reward-manager personas (one per sector) each reviewed ~340 metrics of their sector's seed data
against real-world sector norms (digest = sector distribution vs 270-org pool). David chose **full
seed-realism v2** — fix everything. Attribution verified against lumi.db (new = the 50 add50 orgs).

## Attribution summary (new vs existing on the key defects)
- **Phantom bonus/LTI**: `REW_INC_131`='No' + LTI matrix rows → **38 new / 2 existing** → INTRODUCED by add50 mosaic clone.
- Carer's leave (`REW_BEN_FAM_007` unpaid vs `REW263_TIME_CARERPAID` paid): **236 orgs (86%)**, 46 new / 190 existing → pre-existing, pool-wide.
- Redundancy (`RED_PROC_01`=Yes process vs `RED_PROC_02`=No criteria): 83 orgs, 16 new / 67 existing → pre-existing.
- Sub-NLW hourly floor: 66 orgs, 15 new / 51 existing → pre-existing.

---

## BATCH PLAN

### V2-A — Fix the add50 regression (phantom bonus/LTI conditioning) [MINE] ✅ DONE
Shipped: added an incentive-coherence pass to the add50 generator (blank `REW_INC_LTI_MAX_01`
where `REW_INC_131`='No'; blank `323ffcf1…`/`REW_INC_111` where `REW_INC_103`='None'). New-org
phantom records 38→0 (LTI) and 10→0 (bonus). 14/14 green on real DB. Remaining 2 LTI + 18 bonus
violations are PRE-EXISTING seed orgs → handled in V2-B.

<details><summary>original spec</summary>
The LTI/bonus MATRIX metrics (`REW_INC_LTI_MAX_01`, `REW_INC_LTI_VALUE_TYP_01`, `323ffcf1…` max-bonus, `REW_INC_111` target-bonus, and the bonus-detail family) must be conditioned on the org's `REW_INC_131` (equity Y/N) and `REW_INC_103` (bonus eligibility) headline. In the add50 generator, after cloning, CLEAR/blank the LTI matrices where `REW_INC_131`='No', and the bonus-detail matrices where `REW_INC_103`='None'. Also add these as coherence_pairs so the freeze gate catches future drift.

</details>

### V2-B — Coherence pairs, whole seed (data repair) ✅ carer + commission DONE
Shipped (`migrate_seedreal_v2b_coherence_2026_08_14.py`): (1) carer's leave — `CARERPAID`
(un-anchored, CSV-locked) brought into line with the `FAM_007` provision headline (FAM_007 is a
register marginal so it can't move); 95 orgs. (2) commission — `COMMCAP`→"Not applicable" where
`REW_INC_135`=No; 3 orgs. Also fixed a qa_focus false positive: `leak()` flagged the legitimate
`strategy_objective`="Attract" (a reward pillar) as a hidden-superpower leak. 14/14 green.
NOTE: the earlier "236 orgs" carer figure was a query bug ("Statutory unpaid" contains "aid"); the
true contradiction count was 95. Still TODO in V2-B: `ALLOW_03`↔`REW_PAY_020`, pension headline↔
by-level (fold into V2-C), `RED_PROC` (83 orgs), COL-action (Media). Original list:
- `REW_BEN_FAM_007` ↔ `REW263_TIME_CARERPAID` (carer's leave paid/unpaid) — 236 orgs.
- `RED_PROC_01` ↔ `RED_PROC_02` (documented process ⊇ documented criteria) — 83 orgs.
- `REW_INC_135` ↔ `REW265_INC_COMMCAP` (no commission ⇒ no comm cap).
- `ALLOW_03` ↔ `REW_PAY_020` (allowance pensionability agreement).
- headline pension % (`PROP_36b990f9`, `REW26_BEN_PENSION_COST_SHARE`) ↔ `REW_BEN_112` by-level.
- `REW_INC_131`/`REW_INC_103` ↔ LTI/bonus matrices (from V2-A) — wire globally.
- Promotion governance (`PROP_34ffb6e2`) ↔ pay-range/JE frameworks (Healthcare).
- COL action (`REW264_WEL_COLACTION`) ↔ COL-driven benefits (`REW_BEN_058`) (Media).

### V2-C — Sector pension fingerprints (DB where DB belongs) ✅ DONE
Shipped (`migrate_seedreal_v2c_pensions_2026_08_14.py`): frozen-conserving reallocation (7 swap
pairs) of `REW26_BEN_PENSION_TYPE` — moved DB/Hybrid out of Media/Hospitality/Retail/over-weighted
Logistics-FS INTO Manufacturing (1 DB + 3 Hybrid), Energy (2 DB), Education (3→4 DB). Global held
exactly (25 DB / 4 Hybrid / 241 DC). Cascade per B4: DB recipients get REW264_PEN_AEDEFAULT/
GREENDEFAULT = "Not applicable" + REW_BEN_112 flat 23% (TPS/LGPS); Hybrid keeps DC children +
blended 15%; de-DB'd donors drop to a DC ladder. 88 REW_BEN_112 CSV rows in lockstep. 14/14 green.
NOTE: frozen cap (national ~9% DB) limits how far each sector can go — Manufacturing lands 14%,
Energy 20%, Education 33% (persona ideals were higher but would require re-ratifying the frozen
anchor UP, a separate David call). Residual: DB orgs keep their prior MATCH/SALSAC (not gate-flagged,
frozen — a conserving swap of those could be a follow-up). Original spec:
- **Manufacturing**: inject closed/hybrid DB legacy (currently 0/28) — target ~15-25% DB/hybrid, concentrated 5,000+ FTE. Cascade: PLSA quality-mark, life-cover DIS, employer-contribution level.
- **Education**: DB should dominate (~75%+ via TPS/USS/LGPS) — currently 25%. Cascade: employer contributions 15-28%, PLSA mark pass, remove general bonus schemes (spine pay).
- **Energy/Utilities**: DB/hybrid legacy present (currently 0/10). Cascade as above.
- (Public Sector pensions already correct post-reseed.)

### V2-D — Signature benefits + frontline/office separation ✅ core DONE
Shipped (`migrate_seedreal_v2d_frontline_2026_08_14.py`): OT_04 shift premium reset marginal-conserving (office Tech/ProfSvcs/FS/Media 42-50%->~8%, frontline up; global held 170); Hospitality staff meals 24/32 -> Free/Subsidised; Manufacturing skills pay 12/28 Yes. 14/14 green. Deferred: shift-multiplier matrices (REW_Q528801/534581) office->N/A, retail staff discount (REW_BEN_038 coherence), REW_INC_103 frontline bands.

<!-- orig:
- **Retail** staff discount `REW_BEN_038` → ~85%+ (currently level with pool).
- **Hospitality** staff meals `REW264_WEL_MEALS` → majority Free/Subsidised (currently 94% None).
- **Manufacturing** skills-based pay + apprenticeship frameworks → above pool.
- **Frontline-in-office bleed**: remove shift premiums (`OT_04`), shift/hourly overtime multipliers, cancelled-shift/min-hours metrics from Tech, Professional Services, FS (salaried knowledge workers) → Not applicable.
- **Bonus-eligibility gradient** (`REW_INC_103`): add frontline bands (Retail/Hospitality/Logistics) to `band_distributions` so they're bonus-light like Public/Charity — currently only Charity + Public are special-cased, everyone else gets bonus-heavy `_default`.

### V2-E — Numeric floors + texture
- **Sub-NLW hourly floors** (66 orgs): anchor lowest-rate bands to 2026 NLW (~£12.21) except youth/apprentice.
- **AI-pay cluster** (`REW262_PAY_AISKILLSPAY`, `REW264_GOV_AIPAYREVIEW`, AITALENT/AIBENCH): deflate from 2-3x pool to low-teens; concentrate in Tech/Media/data roles.
- **Large-org (10,000+) realism**: dedicated reward team present (`REW263_GOV_REWTEAM`), death-in-service life cover, HRIS/comp-tool (not spreadsheet) at 5,000+.

### V2-F — Sector-strength corrections
- **Public Sector**: enhanced occupational sick pay (`REW_BEN_SICK_001/002`), pay transparency (`PAYTR_01/02`), JE coverage (`REW26_PAY_JOBEVAL_COVERAGE`), remove salary-sacrifice on DB, leave floor up. Remove phantom bonus/LTI (covered by V2-A).
- **Construction**: EAP (`REW26_WEL_EAP`) and occupational health (`REW263_WEL_OH`) up for large firms; allowances up.
- **FS**: RemCo sign-off (`REW263_GOV_SIGNOFF`) dominant; formal pay ranges (`REW_PAY_001`) up; employer pension level up.
- **Charity**: pay transparency up (sector leader); paid volunteering leave (`REW_BEN_FAM_010`).
- **Prof Services**: EMI gated to <250 FTE; incentive purpose (`REW_INC_077`) performance/retention not cost-control; redundancy pay basis = basic salary.

## Per-sector persona verdicts (one line each)
- Retail: retail-shaped; fix large-org reward-team resourcing + staff discount.
- Logistics: realistic; 10,000+ orgs have sub-NLW/£20-25 floors, no DIS, no shift premium.
- Hospitality: authentic; staff meals missing (94% None), pension too generous, sub-NLW.
- Construction: credible; EAP & OH too low for large firms; allowances low.
- Manufacturing: well shift-tilted; ZERO DB/hybrid (should lead); skills/apprentice/gainshare under pool.
- Public Sector: pensions/redundancy correct; phantom bonus/LTI on 3 new orgs; OSP/transparency/JE understated.
- Media: uniformly over-generous & over-AI-mature; COL-action & car-allowance contradictions.
- Technology: well-differentiated; frontline shift/hourly pattern bled in (OT_04 50%).
- Professional Services: plausible; RED_PROC contradiction; EMI at large firm; commission/shift/car overstated.
- Financial Services: bonus/deferral correct; pay-range, RemCo, pension-level implausibly low + contradictory.
- Education: benefits ok; DC-dominant pensions + general bonus schemes fundamentally wrong (should be DB + spine).
- Energy/Utilities: credible; DC 100% (DB heartland); overtime "N/A" contradicts own shift data.
- Charity: charity-shaped; 2 new orgs leak exec bonus/LTI; transparency & volunteering-leave gaps.
- Healthcare: credible; carer's-leave & commission contradictions; AI-pay inflated; promotion over-discretionary.
</content>
