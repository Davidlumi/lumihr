# Full metric×sector grounding review — consolidated plan (2026-08-14)

14 senior-reward-analyst agents (one per sector), each grounded in our internal docs + external 2026
UK research, reviewed all 340 metrics for their sector. Findings collapse into cross-sector batches.
Tags: [free]=direct edit · [marg/frozen]=conserving reallocation · [keyed]=within-band · [gate]=needs
qa pin/coherence update.

## P0 — REGRESSIONS / UNFINISHED FROM MY OWN v2 BATCHES (do first — these are mine)
1. **EAP inverted [frozen, mine]** — V2-I's EAP-bundling swap pulled EAP from lean non-PMI orgs; Public
   Sector/Charity/Education *are* non-PMI, so they dropped to 28/30/33% when they should LEAD (cheap,
   values-aligned). Re-tilt: EAP high in PubSec/Charity/Education/Construction/large; the 75 "No" sit
   in lean private SMEs (small Retail/Hosp/Logistics/Media/Tech). Conserve frozen 195/75.
2. **V2-A phantom-bonus gating never ran on EXISTING orgs [gate/free]** — org b7c6fb0d (Education) and
   ~18 other existing orgs answer REW_INC_103=None yet carry max/target-bonus ladders (323ffcf1,
   REW_INC_111) + LTI. Run the V2-A conditioning pool-wide, not just the 50 new orgs.
3. **V2-C DB-pension cascade incomplete [free]** — DB orgs got REW_BEN_112=23% but PLSA_QM, cost-share
   and headline employer % (PROP_36b990f9) still read DC. Cascade for all DB orgs (Education esp.).
4. **V2-D office-separation unfinished [free/CSV]** — shift-multiplier matrices (REW_Q528801/534581),
   cancelled-shift (REW_FAI_CANCEL), min-hours (REW_FAI_MIN_HOURS) still substantive in Tech/FS/
   ProfSvc/Media. Set Not applicable for salaried knowledge-worker orgs.

## BATCH 1 — Bonus gradient (REW_INC_103 + bonus-detail) [keyed + free + gate]
Frontline (Retail/Hospitality/Logistics) → bonus-light; no-bonus (Education/Public/Charity) → near-zero
AND blank the bonus-detail family (BUYOUT, BONUSTIME, BONUSDISC, gatekeeper REW_INC_065, clawback
REW_INC_071, purpose REW_INC_077, POOLFUND, 323ffcf1/REW_INC_111 ladders) where REW_INC_103=None.
Add frontline + Education bands to REW_INC_103 band_distributions.

## BATCH 2 — "Sector should LEAD its signature lever" raises [mostly free]
- Manufacturing+Construction: apprenticeship framework (REW265_PAY_EARLYCAREER — "no apprentices"
  impossible at Tier-1), production gainshare (REW265_INC_PROFITSHARE), safety-in-pay (REW265_INC_ESGINCENT).
- Construction: CIJC travel/lodging allowances (ALLOW_01), health screening (REW26_WEL_SCREENING),
  Mates-in-Mind manager training (REW263_WEL_MGRTRAIN).
- Logistics: retention (REW265_INC_RETENTION) + sign-on (REW_INC_072) + peak pay (REW265_PAY_SEASONAL),
  OH (REW263_WEL_OH), driver eye-care (REW264_HLT_OPTICAL), geo pay (REW265_PAY_GEOPAY), advert transparency.
- Retail: staff discount (REW_BEN_038 → ~90%), seasonal peak pay, big-ticket commission.
- Hospitality: non-guaranteed/zero-hours (REW_FAI_MIN_HOURS — sector should lead), seasonal pay.
- Energy: standby/call-out (REW_PAY_017), green/EV benefits (REW264_BEN_EVSALSAC/REW265_BEN_GREENBEN),
  rostered shift notice (REW262_PAY_SHIFTNOTICE), collectively-bargained vs merit progression.
- Public Sector: holiday (REW_BEN_HOL_001 → mostly ≥25d), pay-in-adverts, London/HCAS weighting, sick pay (SICK cascade).
- Charity: EDI pay-gap analytics (ethnicity/disability/equal-pay — charity leads), payroll giving
  (REW264_PEN_PAYROLLGIVING), formal pay progression (PAYTR_03), below-market positioning.
- Education: pay progression basis tenure/spine (REW_PRO_035), promotion-pay to grade (PROMOPAY).

## BATCH 3 — "Sector OVER-tilted" deflations [mostly free]
- Media (the over-generous sector): income protection (REW_BEN_046 86%→~24% UK norm), listed-PLC share
  plans/LTI (SAYE/SIP/CSOP/REW_INC_131), health-add-on cluster, DC pension LEVEL, incentive-governance
  (RemCo/malus/clawback in agencies), redundancy, family/leave, financial-wellbeing — all toward pool.
- Charity: flex-benefits platform (REW_BEN_039 80%→~20%), premium health, enhanced/garden-leave redundancy.
- Tech: gainshare/ESG-in-incentive OUT (they belong in Manufacturing) — a two-way reallocation.
- Healthcare: uniform redundancy-cost band (RED_COST_01 4-5x for every large org).

## BATCH 4 — Cross-sector artifacts & model bleeds [free/CSV/coherence]
- Tips/tronc bleed → No for non-hospitality (FS 2, Logistics 6, +others).
- REW_INC_077 incentive purpose cost-control → performance/retention pool-wide in talent sectors
  (FS, Healthcare, Media; ProfSvc already done).
- Sales commission (REW_INC_135/136): up in Tech(SaaS)/big-ticket Retail; zero in Education/Public/Charity.
- RED_PAY_01 redundancy basis = variable pay → basic salary (ProfSvc + pool-wide; legally wrong).
- Garden leave (RED_NOTICE_01) → PILON/worked for frontline sectors (Logistics, Education).
- Status company cars → cash allowance (FS, Healthcare).
- LTI type: options/RSUs ≥ perf-shares in Tech; cash-LTIP→PSP in Energy; partnership over-seeding in ProfSvc.
- REW263_GOV_SIGNOFF RemCo for large listed (FS, Energy — currently inverted by size).
- RED_PROC_01 documented process up in governance-strong sectors (FS).
- Umbrella/agency parity checks (REW263_GOV_UMBRELLA) not "N/A" at large frontline (Construction/Logistics/Media).

## BATCH 5 — Numeric texture: uniform-saturation & dated levels [free]
- Give a realistic negative tail to 100%-provision / 0%-negative-class benefit metrics (Media many,
  Tech REW_BEN_HOL_004, Healthcare RED_PROC_03) — a synthetic fingerprint.
- Dated pay-award levels (PROP_634adacd 5%+ → cluster ~3-4%, 2026 UK ~3.3%).
- Life assurance (REW_BEN_045) at large/salaried orgs (Retail/Logistics/Tech + pool-wide audit item).

## BATCH 6 — Pension GENEROSITY (level, not type) [free, esp. PROP_36b990f9 + REW_BEN_112]
FS/Energy/Education employer % off the AE floor toward sector norms (FS 8-12%, DB 15-28%); Media DC
level DOWN (too rich). Distinct from v2-C which fixed pension TYPE.

## NOT WORTH DOING / GOVERNANCE
- Frozen pension-type re-ratification UP (Education/Manufacturing beyond the ~9% national DB cap) — David's call.
- The full multi-factor latent (Tier-4) — bundling/deflation batches capture the visible 80%.
</content>
