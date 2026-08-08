# NEXT: strategy page deep polish + AI commentary overlay (David: "world class")

State: rebuild 2 shipped (61fe39d, DECISIONS d4ded7d). David: "better - but needs a deep
polish and an AI commentary overlay - look at the text ui ux strategy report everything -
needs to be world class." Recon DONE this session:

## AI overlay — build exactly on the house pattern (all verified in code)
- Gate: `require_ai(get_conn(), user, AI_COMMENTARY)` (app.py:645; AI_COMMENTARY flag :134;
  master AI_INSIGHTS_ENABLED :161 — dark until David flips; require_ai 403s → client hides).
- Endpoint model: `metric_commentary` (app.py:5113): grounded payload → sha256 phash with
  claude_api.COMMENTARY_GEN_VERSION → cache table → `peek` mode returns parts:None (no spend)
  → generate → INSERT OR REPLACE.
- CACHE REUSE (no migration): store in metric_commentary with question_id='__strategy__',
  cut_key='strategy'.
- Payload = strategy dials + the SAME alignment rows the board pack builds. The hero assembly
  lives inline in the pack route (app.py ~3560-3640: items/money/_visq/_get_block/_answers/
  cut/tb → pos.hero_signals → _strat_align rows). EXTRACT that setup into a helper
  `_strategy_alignment(conn, user, org)` used by both the pack route and the new endpoint —
  do NOT duplicate 50 lines.
- Generator: `claude_api.generate_strategy_commentary(payload)` mirroring
  generate_metric_commentary (:1038): deterministic fallback FIRST (compose from off-aim
  areas/ahead-behind/objective — always ships if AI dark/invalid), then call_claude with a
  compact 3-part schema {reading, tensions, watch}, validate: areas mentioned ⊆ payload areas,
  numbers ⊆ payload numbers, NO attribution verbs (P1D — qa_commentary will check).
- Client: "lumi's reading" panel on the strategy document between sections 01/02 —
  navy-tinted, peek on load, Generate CTA, hide entirely on 403, footer line "A description
  of your strategy against your data, not advice." Section numbering shifts (num() helper
  already dynamic).

## Deep polish list (from my own review of the shipped page)
- Stance: tighten prose lexicons (SD_MIX/SD_P4P read slightly listy when both present).
- Exhibit: aim ring is invisible when position coincides (dot covers it) — draw ring larger
  (14px) so the concentric state reads; add subtle row hover bg.
- Ledger: benefits_lead value "Financial" reads bare — prefix "Leads on".
- Review step (wizard step 3) still old-style ReviewSection cards — restyle to the sd- ledger
  language.
- Print: verify pagination (exhibit + ledger on one A4; masthead colour exact).
- Mobile: sd-mast meta wraps left (done); check exhibit at 375px.
- Capture: dial-card white boxes could lose borders for hairline dividers (designer spec said
  "fewer boxes") — optional, taste call.

## Process
Server change ⇒ full ./run_gates.sh (qa_commentary 44 checks will exercise P1D rules).
Cache bump AFTER edits (currently v467). Commit per class: server+gates, then client+CSS.
Suite green precedent: all 14 through v467.
