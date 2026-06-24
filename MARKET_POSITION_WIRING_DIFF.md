# Market Position wiring — before/after verdict diff

Engine wired to `market_position_config.json` (2026-06-16). LEGACY = polarity-only feed; WIRED = Substance (Level+Provision, higher_is_better) in competitive domains. Every change below is attributable to the classification — no unexplained moves.

**Standing reasons** (apply throughout): Governance dropped from every gauge (competitiveness=false) · the 5 neutral cost/budget metrics no longer counted · the 1 lower_is_better (malus) out of the gauge · ~31 Practice/Design metrics reclassified to Approach (out) · Provision presence (offered-benefits, ranked vs take-up) routed IN · firm floor 5→3.


## Thornbridge | All

- **Gauge**: at (42/27/25, pool 94) → at (41/22/24, pool 87)
  - reason: pool 94→87 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict holds (at).
- **Incentives**: at [market] → above [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Wellbeing**: at [indicative] → below [market] — 5->3 firm floor + Provision presence routed in → now 4 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: at [indicative] → below [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: at [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

## Thornbridge | Charity-thin

- **Gauge**: below (37/30/16, pool 83) → at (31/18/19, pool 68)  ⟵ **verdict below→at**
  - reason: pool 83→68 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict moves below→at.
- **Incentives**: at [indicative] → above [market] — 5->3 firm floor + Provision presence routed in → now 9 Substance q ≥ 3 ⇒ strict (was indicative)
- **Benefits**: below [market] → at [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Wellbeing**: at [indicative] → below [market] — 5->3 firm floor + Provision presence routed in → now 4 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: at [indicative] → below [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: at [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

## Ardenbank(Mfg,10k+) | All

- **Gauge**: above (18/32/42, pool 92) → at (24/30/43, pool 97)  ⟵ **verdict above→at**
  - reason: pool 92→97 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict moves above→at.
- **Incentives**: above [market] → at [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Benefits**: at [market] → above [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Wellbeing**: at [indicative] → at [market] — 5->3 firm floor + Provision presence routed in → now 4 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: at [indicative] → above [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: above [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

## Ardenbank(Mfg,10k+) | Manufacturing

- **Gauge**: at (21/33/38, pool 92) → at (26/27/40, pool 93)
  - reason: pool 92→93 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict holds (at).
- **Pay**: at [market] → below [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Benefits**: at [market] → above [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Wellbeing**: at [indicative] → at [market] — 5->3 firm floor + Provision presence routed in → now 4 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: at [indicative] → above [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: above [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

## Alderstead(Health,250-999) | All

- **Gauge**: at (34/27/27, pool 88) → at (34/16/35, pool 85)
  - reason: pool 88→85 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict holds (at).
- **Incentives**: at [indicative] → below [market] — 5->3 firm floor + Provision presence routed in → now 15 Substance q ≥ 3 ⇒ strict (was indicative)
- **Wellbeing**: at [indicative] → at [market] — 5->3 firm floor + Provision presence routed in → now 5 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: below [indicative] → at [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: at [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

## Alderstead(Health,250-999) | Healthcare-thin

- **Gauge**: at (28/39/21, pool 88) → at (25/26/29, pool 80)
  - reason: pool 88→80 as Governance + neutral + lower + Approach leave and Provision presence enters; headline verdict holds (at).
- **Incentives**: at [indicative] → at [market] — 5->3 firm floor + Provision presence routed in → now 15 Substance q ≥ 3 ⇒ strict (was indicative)
- **Time Off**: below [market] → at [market] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Wellbeing**: at [indicative] → at [market] — 5->3 firm floor + Provision presence routed in → now 5 Substance q ≥ 3 ⇒ strict (was indicative)
- **Recognition**: below [indicative] → at [indicative] — Substance pool re-composed (neutral/lower/Approach out, Provision presence in)
- **Governance**: below [market] → None [None] — Governance excluded — competitiveness=false (no headline role)

---
_Generated by `server/mp_compare.py` from the two `mp_baseline_*.json` snapshots. Per-metric attribution for Thornbridge|All: `python3 server/mp_diff.py`._
