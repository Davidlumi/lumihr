# lumi build — decision log

Date: 10 June 2026 · Methodology v1 · Snapshot 1 ("2026 H1")

## Stack decisions

1. **FastAPI + SQLite, React 18 without a build step.** Phase 1 mandated Python, so the whole
   server is Python/FastAPI. SQLite holds the data with ANSI column types and JSON-as-TEXT;
   moving to Postgres is a driver/connection-string change plus swapping `datetime('now')`
   for `now()` (noted below as hardening). The environment has no Node toolchain, so the
   front end is React 18 (vendored UMD) + `htm` tagged templates — a real component
   architecture with zero build pipeline, and all charts are bespoke SVG (no chart library),
   which is what the percentile-band/heatmap designs needed anyway.
2. **Password hashing: bcrypt; sessions: server-side tokens in httpOnly SameSite cookies;
   login rate-limited** (5/5min per email, 30/5min per IP — offices share NAT egress IPs).
3. **Claude API**: called server-side only (`claude_api.py`), model and key from
   `ANTHROPIC_MODEL`/`ANTHROPIC_API_KEY`. This environment has no key, so the board pack
   and analyst ship with deterministic fallbacks that are visibly labelled as such and use
   only the same data payload — the demo never fabricates and never breaks.

## Methodology decisions

4. **Percentiles**: linear interpolation (numpy "linear"). An organisation's own P-number is
   the midrank share of peers below its value, clamped to [P1, P99] for display (no P0/P100
   claims). Hand-checked against independent recomputation for numeric, single_select and
   matrix questions — exact matches.
5. **"Comparable metric" (one definition, used by the headline banner, superpower cards,
   callouts, starter My-view, analyst starters and board pack)**: a numeric question or
   matrix row where the org has a value and the cut is unsuppressed (ranked against peer
   values), **plus** scored select/yes-no/multi questions ranked against peer practice
   scores (0–100 from the library's `scoring_config.option_scores`). Without the scored
   layer, 9 of 10 superpowers would have almost no metrics (numerics concentrate in Reward).
   Neutral-polarity items are tracked but never counted above/below or coloured.
6. **Practice adoption** (gap register): an answer scoring ≥50 on the question's own 0–100
   scale counts as "in place"; peer adoption uses the same rule. Matrix-type practice
   questions (8 of 490) have no option scores and are excluded from the register.
7. **Suppression**: n<5 → `{suppressed, n}`, enforced in `aggregate.py` only; Peer Twin and
   share links flow through the same path. Multi-select denominators = orgs answering the
   question (percentages may sum >100; said on the methodology page).
8. **Cross-cuts not computed** (Industry × FTE): at ~15 orgs/sector they would be almost
   entirely suppressed. Single-dimension filters only; stated in the methodology.
9. **Peer Twin**: one-hot + min-max feature vector over the 12 registry context attributes,
   cosine similarity, K=12 (floor 8). Sign-up orgs are encoded from their declared
   firmographics with unknown attributes neutral. Rationale panel lists attribute overlap
   counts; peer names never ship.

## Gap-to-£ decisions

10. **Included** (non-neutral polarity, clean formula): max employer pension contribution
    rate (investment to close), regretted attrition (saving), agency usage (saving) — all
    by-level matrices, costed per level with an explicit workforce-mix assumption
    (Board 0.5% … Frontline 60%) × FTE-band midpoint × £36,000 median salary
    (cost/leaver 35% of salary, agency premium 30% — all editable per org in Settings).
11. **Excluded and why**: sickness absence (collected as a banded select, no numeric value);
    bonus opportunity and allowance values (library marks them *neutral* polarity, and the
    spec rule "never compute £ for neutral metrics" wins over the metric wish-list);
    cost-per-hire (needs annual hires, which the dataset doesn't carry). The "Total
    identified opportunity" tile sums savings and reports gap-closing investment separately
    — adding them together would be misleading.

## Data quality findings (seed import)

12. Registry join: **158 matched / 62 file-only ("Unclassified") / 52 registry-only**, by
    normalised name. One fuzzy candidate ≥0.92 flagged for human review, *not* auto-joined:
    `Aldershire Trading Co. plc ~ Valeshire Trading Co. plc (0.939)` — these look like
    different companies; left unmatched.
13. 39,319 blank answers skipped (~18% of cells — expected partial completion).
    Zero orphan question_ids in either direction. **4 library questions received zero
    answers across all 220 files** (they render as suppressed, never dropped).
14. Charity sector has only 8 classified orgs and Energy 8 — sector cuts there sit close to
    the suppression floor; visible in the methodology composition table.
15. `single_select` answers matched option labels exactly after whitespace normalisation
    (unmatched counts are tracked per aggregate; none observed in seed data).

## Product decisions

16. Seed orgs enter at **full** tier with `submission_complete=1`; sign-ups at **core**,
    benchmark-gated until ≥90% of Core questions are answered. Admins of full orgs get
    "Preview as Core" for sales demos.
17. Submissions write into the open snapshot via drafts → validate → promote, with every
    accepted value also appended to `answers_history` (append-only). Aggregation re-runs
    synchronously on submit (~2s) so peer n changes immediately. Movement UI slots are
    designed and labelled "First benchmark — movement appears from your next cycle";
    no fake trends anywhere.
18. Share links: unguessable tokens, optional 7/30/90-day expiry, revocable, audited
    (created/revoked, by whom, when), and served by the same assembly/suppression code as
    the owning org's own view. Peer Twin is disabled on anonymous links.
19. PNG export re-renders the SVG with title, peer-cut label, n and lumi attribution baked
    in, at 2× resolution — paste-ready for decks.

## Verification (all green — `server/verify.py`, 37 checks)

Aggregation hand-checks; no raw peer answers or internal arrays in any API payload
(including shares); suppressed cuts carry no aggregates; viewer-role denials; cross-tenant
404s; locked-tier cards carry no aggregates; all 778 questions render/suppress/lock with
zero silent drops; hard bounds block and soft bounds warn; "None" exclusivity; a real
submission raises live peer n; drafts and pinned layouts survive re-login; revoked and
expired links die; twin never names peers and respects suppression; board-pack narrative
contains no number absent from its payload; the analyst refuses forecasts; pension £-to-P50
reproduces by hand.

## Top 5 things to harden before production

1. **Postgres + migrations** (alembic), connection pooling, and a job queue for aggregation
   instead of in-process synchronous re-runs; move rate-limit state to Redis (currently
   in-memory, single-process).
2. **Real email delivery** for invites/resets (currently console-logged links) and SSO/SAML
   for enterprise members; CSRF tokens on top of SameSite cookies; session revocation UI.
3. **A shared org UUID in the seed pipeline** so the name-join (and its 62 Unclassified
   orgs) disappears; backfill firmographics for the 62 via the declared-firmographics flow.
4. **Billing-linked tier entitlements** and a proper upgrade path (the Unlock affordance is
   a placeholder), plus per-question tier audit so locked metadata can't drift.
5. **Snapshot lifecycle tooling**: open/close collection windows, recompute history,
   movement deltas and trajectory rendering when window 2 exists (schema and UI slots are
   already in place), plus automated backups of the append-only answer history.

## Roles, lifecycle & layered terms (2026-06-11)

- **Three roles**: Admin (full control; only role that accepts org terms),
  Contributor (submits/edits data), Viewer (read-only). Enforced at the route
  layer (`require_admin` / `require_editor`), not just hidden in the UI.
- **Org-level vs user-level**: the data, benchmark, 30-day clock and Data
  Contribution agreement belong to the organisation; identity, login, role and
  Platform Terms acceptance belong to the user. `terms_acceptances` logs every
  acceptance (org, user, kind, version, timestamp).
- **Clock start superseded**: the 30-day contribution clock now starts when the
  Admin accepts the Data Contribution Terms — not at signup or first login —
  so setup time (reading terms, inviting the team, DPO review) never eats into
  the 30 days. `orgs.clock_start` stays NULL until acceptance.
- **Admins are made by promotion, not invite**: invites offer Contributor/Viewer
  only; an Admin promotes a joined member. Sole-admin protection: the last
  Admin cannot be demoted or removed ("Promote another Admin before removing
  yourself"); an org can never have zero Admins.
- **Member removal** reassigns org artifacts (invites/shares/board packs) to the
  acting admin; the terms-acceptance log survives staff turnover by design
  (the org's agreement outlives the accepting Admin's account).
- **Sole-Admin account recovery**: deliberately NOT built. If a sole Admin's
  account is lost, recovery is a manual lumi-side process (verify the
  requester, promote a user via SQL). Flagged for David — revisit if it
  happens more than rarely.
- **LEGAL CAVEAT (for David)**: whether click-acceptance ("I accept these Data
  Contribution Terms on behalf of my organisation") validly binds an
  organisation is a legal question. The flow, wording and logging are built as
  specified, but the three documents in `legal/` are all marked
  "DRAFT — pending legal review" and the binding mechanism must be confirmed
  by a qualified solicitor before launch.

## Recolour plum → blue + top-bar tidy (2026-06-11)

- **One primary**: brand switched plum → warm ink-blue at the token layer only.
  --blue #2547B0 (primary; ~7.7:1 on warm paper), --blue-deep #1E3A8A
  (hover/pressed), --blue-bright #2E62D9 (links/interactive; ~5.2:1, AA),
  --blue-tint/-2 for fills. Deliberately NOT default corporate navy.
- **Teal retired**: a second cool accent would compete with the single primary.
  Links and the one JS usage now use --blue-bright. Zero plum/teal tokens or
  var() references remain in web/ (grep-verified).
- **Untouched**: green/amber/red performance palette (meaning, not identity),
  warm paper + warm neutrals, --navy structural dark (one table-header use).
  The categorical ramp re-rooted from blue (#2547B0 → paper, 6 steps).
- **Top bar**: one 36px baseline for all controls; the contribution clock is a
  quiet outlined status pill (not a filled control); "Request a metric" demoted
  to a text link; the right-side helper line removed. Peer-cut helper stays
  quiet under its control.

## Tiers removed; required-set unlock gate (2026-06-11)

- **Core/Enhanced/Pulse/Strategic retired from UI and logic.** All 180 reward
  questions are simply questions, organised by section. The `lumi_tier` library
  column is untouched but never consulted (entitlement is now `lambda q: True`;
  LockedCard/UpgradePage/preview-as-Core removed). No surprise exposure: every
  actual member was already full-tier, so the visible set was always 180.
- **Insight-unlock gate** is one configurable setting in app.py:
  `LUMI_COMPLETION_BASIS` (default `required` — the 82 is_required reward
  questions; `all` available) and `LUMI_COMPLETION_THRESHOLD` (default 0.90).
  Rationale: 96 of 180 reward questions have an N/A option; a flat 90%-of-180
  could lock out a diligent member with many inapplicable questions.
- **N/A counts as answered** (selecting it is engaging); only skipped questions
  are incomplete; a matrix counts as ONE question. Reachability proven: an org
  answering only the 82 required questions (28 of them via N/A) reaches 100%
  and unlocks.
- All messaging now says "key reward questions"; methodology describes the
  tier-free set and the gate. Demo org sits at 98.8% on the new basis
  (unlocked; submission_complete anyway).

## UX quality pass — Tier 1 + Tier 2 (2026-06-11)

Tier 1 (all verified individually): autosave was already server-side
(drafts table, per-change PUT) — proven to survive logout and a fresh
device; beforeunload warning on in-flight saves (window._pendingSaves);
UK input masking (currency fields show £1,250 idle, accept "£/,/space"
while typing, store canonical numbers); jargon tooltips via the existing
GLOSSARY/Term system; api() now maps network failures to "Couldn't reach
lumi — check your connection" and load failures offer Retry; busy+disabled
states added to team invite and share creation (submit/terms/board-pack
already had them); idle session warning (30 min, 60s countdown, "Stay
signed in"; LUMI_IDLE_MIN window hook for testing) — client-side policy,
no security logic changed; Esc closes Ask lumi and Peer Twin panes
(modals already did), Enter sends invites, Esc clears search.
Accessibility: :focus-visible blue ring on all interactive elements;
aria-labels on icon-only buttons, nav, the peer selector, search and
numeric inputs; charts get role="img" with the card's plain-English
sentence as the text alternative.

Tier 2: skeletons confirmed (existing) on overview/sections, no spinners
on content pages; on-blur/on-save validation confirmed (server rules,
hard bounds block, soft warn); branded 404 for unknown routes + a React
ErrorBoundary "something went wrong" screen; toasts (bottom-left,
auto-dismiss) on invites, role changes, removals, share create/revoke/copy
and failed autosaves; gap-register and section filters persist per user
server-side (_ui_* keys in chart prefs); the peer cut deep-links in the
URL (?cut=industry::X — restore on load, replaceState on change); section
headers carry "benchmark data: 2026 H1".

Out of scope (deliberately untouched): optimistic rollback, offline
detection, prefetching, infinite scroll, breadcrumbs, recently-viewed.

## Single-metric full page (2026-06-11)

- /metric/{qid} is each metric's home: standalone header (title, full
  question, org context chips, period, sample-data caveat, status pill),
  the plain-English readout at size, and the centrepiece — the metric
  across All peers / your sector / your size SIMULTANEOUSLY, each row with
  its own n, per-cut status pill and "you" marker. Suppressed cuts show
  the suppressed state (verified: car allowance, sector n=4).
- Below: the full-size distribution for the active cut (follows the global
  peer selector), exact figures (you · percentile · peer P25/P50/P75 · n,
  or your answer / most common for categoricals), definition + methodology
  with glossary terms, What-this-means expanded, PNG export (branded with
  title/n/cut/caveat), copy-deep-link, request-a-related-metric.
- Entry points: a third hover icon on every card ("Open full view",
  aria-labelled); search results, overview lead/gap callouts, gap-register
  rows and analyst citation chips all route here. openMetric() remembers
  route + scroll; Back restores the exact position (cold landings fall
  back to the metric's section).
- Reuse only: the page issues three calls to the existing per-cut
  /api/benchmark/{qid} endpoint — same aggregates, same suppression, no
  new calculations, no server changes.

## Card redesign: stacked + kebab + per-card peer group (2026-06-11)

- **Stacked layout** replaces side-by-side on every card via the shared
  component: title+pill+kebab / full-width chart (W=620 viewBox, 200px) /
  plain-English readout / What-this-means / n pinned to the bottom. Equal
  heights per row from the grid; taller cards accepted for the calmer rhythm.
- **Kebab** ("Card options", aria-haspopup, Esc + click-outside close)
  replaces the floating chart toolbar entirely: peer-group radio (All /
  Your sector / Your size, current ticked, "page" marks the global cut),
  Open full view, Full question & definition, Pin to My view, Download,
  Copy link. Suppressed or unanswered cards never offer Download/Share.
  The card-zoom modal is retired — the metric full page supersedes it.
- **Per-card peer override** is component state (exploratory by design):
  re-fetches the SAME per-cut aggregate endpoint, so chart, pill, position,
  readout and n always change as one card — no mixed-cut display possible.
  Off-default chip ("Sector ✕") with one-tap reset; cleared by any global
  selector change and by reload. The old persisted pref.cut from the zoom
  era is deliberately ignored.
- Exports from an overridden card are labelled with that cut + n; share
  links carry ?cut= so the recipient sees the same comparison. Suppressed
  cuts show the suppressed state (verified n=4 sector, no stale values);
  unanswered metrics never gain a fabricated "you" on any cut.

## Metric page simplified + AI commentary + adversarial gate (2026-06-11)

- **Stage 1 (shipped independently):** the metric page shows ONE primary
  chart with a cut selector (All / sector / size / Organisations-like-you;
  profile-gated) and a curated chart-type switch (chartAlternatives only —
  no type that misrepresents; session preference falls back per metric).
  The three stacked cut charts and the duplicate "full picture" block are
  gone; page height roughly halved.
- **Stage 2:** four-part AI commentary (measures / compare / implications /
  considerations) from a grounded payload of only the page's figures.
  Every model output must pass validate_commentary (number grounding,
  directive scan, legal-adjudication scan, stance agreement, suppression
  and unanswered protection) or the deterministic four-part fallback ships.
  Cached per org+metric+cut on a payload hash (self-invalidates when data
  changes). Fixed UI caveats: "AI-generated — review before use" +
  "a starting point, not advice" + illustrative-sample-data note.
- **Stage 3 (gate):** qa_commentary.py — 40/40 clean: zero hallucinated
  numbers across 41 generations + hostile payloads, zero suppression
  breaches, polarity always agrees with the pill (incl. lower-is-better
  favourable and neutral-no-verdict), injection attempts inert, no
  directives or legal adjudication incl. on legal-adjacent metrics, stance
  deterministic across regenerations, cache hash moves with the data, and
  the validator itself rejects 9 classes of hostile "model output".
  Flag default flipped to ON on the clean gate. NOTE: no ANTHROPIC_API_KEY
  in this environment — the live surface is the deterministic generator;
  the same validator screens model outputs once a key is configured.
  RE-RUN qa_commentary.py after adding a key or changing the generator.

## Company profile — onboarding capture (2026-06-11)

- Lean org-level profile (~8 fields): required core (industry, FTE band,
  HQ region, ownership) + recommended rich four (unionised band, HR
  maturity, business maturity, operating model) that sharpen Peer Twin.
  Deliberately NOT the other ~35 registry attributes — onboarding stays a
  two-minute step, not a wall.
- Sequenced FIRST in the Admin lifecycle: signup -> platform terms ->
  COMPANY PROFILE -> benchmark usable with peer cuts -> data terms ->
  clock -> submission. The two gates stay distinct: profile = "who you
  are" (fast, upfront); reward 90% = "contribute to unlock insights"
  (the 30-day journey). /api/org-profile deliberately does NOT require
  the data terms; the submission flow prompts profile-before-terms.
- Choice sets come from the seed registry's feature space
  (sim_feature_space.cat_values), which FIXED a latent mismatch: the old
  in-submission form used an OWNERSHIP list that didn't match registry
  Ownership_Type values, so signups never matched seed orgs on ownership
  in the similarity vector. Verified: a real org's Manufacturing /
  1,000-4,999 / South East lands in the seed orgs' exact cut (n=15=15);
  non-registry values are 400-rejected.
- The similarity vector now encodes the declared rich fields and maps the
  union band midpoint into the registry's numeric range (no longer all
  neutral) — richer "Organisations like you" for members who fill them.
- Gating until the core is complete: topbar selector hides sector/size
  options and shows a complete-your-profile prompt (admin link / ask-your-
  admin for others); card kebab and metric page prompt likewise. Editable
  later via Settings -> Company profile (admin-only; org-level).

## Custom peer groups — filter-based, suppression-first (2026-06-11)

- Filter-based ONLY (never hand-picked orgs): criteria over a curated 8 of
  the registry firmographics (industry, FTE band, region, ownership,
  unionised band, HR maturity, business maturity, operating model), values
  validated against the registry sets; unknown fields/values are 400s, so
  hand-built requests can't probe arbitrary columns. OR within a field,
  AND across fields. Stored per org (peer_groups table), private.
- Anonymity, enforced server-side in the engine path: a group below the
  n>=5 floor NEVER aggregates at all (group_blocks returns None per
  question → every metric renders the standard suppressed state, n=0);
  per-metric n>=5 suppression still applies inside valid groups;
  membership is never revealed — previews and listings return counts only;
  foreign/stale group ids resolve to All peers; anonymous share links
  force group cuts to All peers (same rule as Peer Twin).
- A group cut is just another filter into the EXISTING pipeline: it rides
  the Peer Twin bespoke-blocks channel (aggregate_question_for_orgs), so
  overview, cards, gap register, full-page metric and per-card override
  all work unchanged, with the group's name as the cut label.
- Create flow shows a live match count (count only) and an amber warning
  below the floor; saving a too-small group is allowed (it stays
  suppressed until enough orgs match — important at real scale).
- **Known residual risk for David — differential attacks**: two groups
  differing by one criterion (e.g. n=6 vs n=5) could in principle be
  compared to infer things about the single org in the difference. The
  n>=5 floor blunts the worst case but does not eliminate it. v1 ships
  with the floor only; monitor usage and consider (later) overlap-aware
  suppression or minimum-difference rules if real members build many
  near-identical groups.
- Synthetic-data expectation: on ~220 seed orgs, richly-filtered groups
  often fall below the floor — that is suppression working, not a bug.
  Do not loosen the floor for demos.

## Hero overhaul — market position + practice prevalence (2026-06-11)

- The 0-100 maturity scores are gone everywhere (incl. the gap-register
  tiles): a score implies precision the data doesn't support. The hero now
  leads with two signals grounded in what the data can defend:
  A) MARKET POSITION (below/at/above, performance palette) — only the
     polarised AND positionable pool: 87 polarised questions -> 75
     positionable (numeric, matrix rows, scored selects with a known
     direction); the 12 unordered polarised single_selects are ROUTED TO
     PREVALENCE — score_answer structurally cannot rank them, so no
     invented order is possible (the gap-register bug class).
  B) PRACTICE PREVALENCE ("X of Y with the peer majority · N less common",
     neutral ink/blue, NEVER red/amber/green) — the 93 neutral practices
     plus the 12 routed; select/yes_no only (matrix/multi-select neutrals
     excluded from prevalence v1).
- Config (env): LUMI_MARKET_BAND (default 25-75 — the honest quartile
  band; demo reads 48% at-market, not washed out, so the default stands;
  tune to e.g. 40-60 on real data if it monotones), LUMI_DOMAIN_MIN_
  POLARISED=5 (counts DISTINCT questions, so matrix rows can't earn a
  3-question domain a verdict), LUMI_VERDICT_MARGIN=0.15,
  LUMI_UNCOMMON_PCT=20.
- Domain rollup: Pay/Benefits/Transparency carry market verdicts;
  Incentives (3 polarised) and Progression (4) are practice-view only —
  presented cleanly, not as missing data. Overall market position computes
  from the FULL polarised pool, never an average of domain ratings.
- Day-one: no verdict until computable from the org's own answers;
  unanswered metrics never contribute. Non-monetary opportunity = the gap
  register's actionable count (peers do it, you don't) — framed as the
  to-do list, distinct from the prevalence position signal.
- qa_hero.py (25/25) gates polarity direction (incl. lower-is-better
  inversions), positionability census, band tunability, eligibility,
  rollup construction, day-one and the neutral palette. Run it after any
  change to the hero logic.

## Delivery audit (2026-06-11) — true state + flags for David

Phase-1 verdict across ~25 audited items: 18 WORKING (each with live
evidence: actual values, responses, or DOM probes), 0 BROKEN, 3 PARTIAL,
4 NOT BUILT, 0 UNVERIFIED. Correctness (gap-register semantics, polarity,
suppression, unlock gate) and security (role guards, cross-tenant
isolation, AI grounding validator) were audited fully and passed with
evidence; the falsification probes (foreign group ids, hostile validator
outputs, viewer-by-URL, cadence labels) all held.

Fixed in Phase 2:
- D3: per-surface AI kill switches — LUMI_AI_ANALYST / LUMI_AI_BOARDPACK
  (default on; verified 403 when off) joining LUMI_AI_COMMENTARY; exposed
  in /api/me features.
- D7: verify.py marked DEPRECATED with a refusal guard (pre-dates the
  reward-only flag; misleading). Current evidence suites: qa_focus,
  qa_status_audit, qa_hero, qa_commentary.

FLAGGED, NOT BUILT (need David's direction, not unsupervised builds):
- D1 Market-context medians with historical-dedupe / staged-once /
  re-pooling: requires a multi-cycle snapshot model; today there is ONE
  snapshot and no staging code.
- D2 Back office / superadmin console, 2FA, audit logging UI, pay-deals
  upload/refresh: a separate surface + auth model; nothing exists
  (/admin is 404 by absence).
- D4 Persona features (density toggle, multi-select export — the
  show-only-gaps status filter DOES exist and persists).
- D5 Collapsible sidebar. D6 Bespoke dashboards beyond share-links +
  My View pinned layouts.
Also outstanding: master QA pass v2 phases 6-7 (the pre-demo gate).

## Master QA v2 — phases 6 & 7 complete (2026-06-11, pre-demo gate)

Phase 6 (AI surfaces, deterministic state + safety machinery): all three
surfaces deterministic-correct and grounded (40-metric commentary scan +
board-pack narrative scan: ZERO ungrounded numbers; analyst clearly
labelled '(AI analyst is not configured…)' with an honest no-match path);
validator proven live (invented £, polarity flip, suppressed-figures all
REJECTED with reasons); kill switches proven (403s when off, defaults on,
exposed in features); injection via hostile group names/definitions inert.
TWO DEFECTS FOUND AND FIXED:
- 6-D1: scored selects lost their direction-corrected percentile in the
  commentary payload (an ahead P96 metric read as positionless prevalence).
  Fixed: payload falls back to card.score percentile+polarity (the pill's
  source). Re-verified: 'ahead of most similar organisations' at P96.
- 6-D2: the commentary endpoint silently mapped group/twin cuts to All
  peers (mixed-cut bug class). Fixed: dim whitelist + org-scoped group
  resolution (foreign ids still fall back to all). Re-verified: cites
  'My competitor set, n=28, P98'; tiny group gets the too-small note.
All gates re-run clean after the fix: qa_commentary 40/40, qa_hero 25/25,
qa_focus 23/23.

Phase 7 (robustness): 0%-org sweep across 10 routes (no raw errors, all
welcoming); partial-completion state intentional; unanswered metric
peers-only on all four cuts; search-no-match offers request-a-metric;
3-org group suppressed on card/overview/hero/register simultaneously;
exact n=5 serves values while n=4 suppresses (boundary proven); forced
network error and bad metric ids give friendly recovery; override
sequence unanswered->suppressed->reset never shows a stale value; rapid
cut flips settle cleanly; long/special-char org name renders; the same
metric reads '▼ Behind · P57' identically on its card and its full page.
NOTE for David (not a defect): the card pill band (±5pts of median) and
the hero market band (quartiles, configurable) are intentionally
different granularities; set LUMI_MARKET_BAND=45-55 if you'd rather they
align exactly.

## Per-metric data integrity review (2026-06-11) — firewall-compliant

Scope: the 180 live reward metrics (NOT the hidden 446/778 library — a
separate pass if David wants it). Reference engine: qa_integrity.py —
fresh implementations of linear-interpolation percentiles, midrank
position and option shares, computed straight from raw answers in
SQLite, compared against production payloads. (Its own first run had a
reference bug — reading row['block'] instead of row['all'] — which
flagged 75 false mismatches; investigated before convicting production.)

PHASE A (computation): 180/180 clean after ONE genuine bug:
- aggregate.py collapsed row-keyed answers for NON-matrix questions into
  one arbitrary row's value per org. Only REW_INC_061 was affected (its
  seed data is matrix-shaped — 7 per-level rows — under a single_select
  schema; the 2026 regen pass had skipped it). The displayed distribution
  was one level's data presented as the org answer. FIX: non-matrix
  aggregation ignores matrix_row_id != '' (schema violations can never
  silently distort again). The malformed rows are left in the DB, inert —
  not deleted, not edited. The metric now reads n=0 suppressed, honestly.
Also re-screened with fresh regexes: cadence/property gap-register
statuses ZERO false negatives; suppression sweep over EVERY payload block
(all cuts, matrix rows): ZERO blocks under n=5 serving values.

PHASE B (plausibility, high bar): range vs the library's own declared
bounds: ZERO violations. Sector-median outliers: ZERO. Don't-know
dominance: ZERO. Cross-metric contradiction pairs (long-service gate,
LTI eligibility): ZERO. Full numeric-medians table professionally
reviewed (PMI £1,095/£2,035/£2,850; exec car allowance £11,250; salary
budget 3.7%; LTI board max 125%; pension typical 8-10%) — all defensible.
ONE implausible metric: REW_INC_072 sign-on bonuses at 99.5% "Not used"
(import-era data the regen pass skipped) — indefensible vs UK practice
surveys.

PHASE C: REW_INC_072 regenerated WHOLE-METRIC via regen_rew_inc_072.py:
documented baseline (~60/18/17/5), conditioned on firmographics only
(existing Profile latents + Talent_Competition), seeded
("REW_INC_072|2026-06-11|org_id"), reproducible, org-blind. Result
65.0/12.3/17.3/5.5 across all 220 orgs at once. Org-blindness shown:
demo org + two fixed-rule watch orgs all KEPT "Not used" — no standing
improved; the demo org's answer simply moved from near-universal
(219/220) to modal (143/220). All gates re-run clean on the new data:
qa_integrity 0 mismatches, status audit zero, qa_focus 23/23,
qa_hero 25/25.

FLAGGED FOR DAVID (not improvised):
- REW_INC_061 "Typical individual/business % split of main bonus": now
  honestly empty (n=0 suppressed). Regenerating needs a curated org-level
  prior the original curators declined to invent (the question's
  awkwardness is why it was seeded per-level). Options: curate a prior,
  reword the question per-level (matrix), or hide it from the live set.
- My-data still lists the org's stored (inert) per-level rows for
  REW_INC_061 — cosmetic; remove if the question is rewormed/hidden.

INTEGRITY STATEMENT: no value was hand-tuned anywhere; the demo org
received no special handling; changes were exactly one code fix and one
whole-metric, documented, seeded, org-blind regeneration.

## Matrix aggregation fix — all answer formats (2026-06-11)

THE BUG: matrix row aggregation was numeric-only; values it couldn't parse
silently became n=0. NINE of the 21 reward matrix metrics rendered "not
enough data" with full seed data behind them: 5 Yes/No matrices (tronc
participation, LTI/PMI/status-car eligibility, allowances pensionability),
2 banded "N weeks" notice-period matrices, 2 "Nx" multiplier matrices.

WHY THE INTEGRITY AUDIT MISSED IT: qa_integrity's reference used the SAME
strict numeric parse as production for matrix rows — both sides dropped
categorical rows identically, so they "matched". A false clean. The
reference now verifies categorical rows independently (counts/percentages
per band) and asserts every populated row aggregates and the top-level n
equals distinct responders — a populated row that aggregates as nothing
is a hard failure. Lesson recorded: a metric is verified when it has been
SHOWN rendering, not when two engines that share an assumption agree.

THE FIX (read/aggregate only — zero answers changed):
- Mode per QUESTION from the column schema + full answer set: numeric when
  the column is numeric-typed or every defined option parses as suffixed
  numeric ("1.5x" -> 1.5); otherwise categorical, ordered by the column's
  option list ("More than 16 weeks" keeps its place). Unrecognised values
  in numeric mode are counted + logged, never silent; unexpected labels in
  select mode are kept and flagged.
- matrix_select_block: per-row distribution (counts, pct, modal) with the
  same n>=5 suppression as everything else.
- assemble_card: categorical rows carry the org's own label + peer share;
  the org's own numeric matrix answers now parse with the same tolerant
  parser as peers ("1.5x" You-values were showing as "—").
- positions: banded answers ("12 weeks") can never produce a fake numeric
  rank (guard on _values); the multiplier/market-position rows DO now
  contribute positions — the hero pool grew 82 -> 94 positioned items,
  which is recovered real data, not methodology drift.
- Client: MatrixSelect renderer (per-level 100% band + most common + your
  answer); categorical matrices expose a single honest chart type; small
  none-unit values display 2dp (1.25, not 1.3).

VERIFIED: all 21 matrix metrics live n == distinct responding orgs (zero
n=0-with-data; table in the QA record); tronc renders 26 orgs with the
sensible per-level story (frontline Yes 100%, board No 100%); hourly
multipliers render P50 1/1.25/1.5 by band with You + per-row percentiles
(n=191); independent recomputes match exactly (notice-band counts, tronc
counts, weekend-multiplier p50); pension/bonus numeric matrices unchanged;
a select matrix on an n=4 cut still suppresses. Gates re-run clean:
qa_integrity 0/180, qa_focus 23/23, qa_hero 25/25, status audit zero,
commentary 40/40.

## 2026-06-12 — Expert plausibility review: pay frequency regenerated; allowances-pensionable prepared for David

PAY FREQUENCY (EXT_REW_GAP_013) — REGENERATED (firewall-compliant).
- Shape resolved FIRST: true single_select ("How often are employees
  typically paid?"), 179 answering orgs, no row-keyed rows. Only the label
  lied — benchmark_display said "Employees typically paid by level"; fixed
  in the questions table AND data/lumi_questions.csv (2 occurrences).
- Why: Fortnightly was modal at 35.2% — backwards for the UK, where
  monthly pay dominates (ONS/ASHE payroll patterns; CIPP industry data)
  and fortnightly is a US/Australian pattern.
- New distribution (seeded "EXT_REW_GAP_013|2026-06-12|"+org_id, whole
  metric, participation preserved): Monthly 71.5% / Weekly 12.8% /
  Mixed 10.1% / Fortnightly 4.5% / Don't know 1.1%. Weekly conditions on
  Workforce_Frontline_%, Workforce_Shift_% and the five weekly-leaning
  sectors; mixed rises with size — calibrated to the documented baseline
  (first draw landed Weekly 19.6%; tilt coefficients reduced, re-drawn).
- Watch orgs (fixed rule, neutral-polarity metric): demo 'Monthly' ->
  'Monthly' (redrawn blind, same draw); 009f901c 'Fortnightly' ->
  'Monthly'; 022f3575 'Fortnightly' -> 'Mixed (varies by role)'.
- FOR DAVID: exact split is the constants block in
  server/regen_pay_frequency.py ("David adjusts here") — direction is
  settled, decimals are his; script is seeded/reproducible.

ALLOWANCES PENSIONABILITY — FLAGGED, NOT REGENERATED (per the brief:
David sets the baseline; do not regenerate on an assumed one).
- Verified defects (live data): (1) ALLOW_03 says 81.8% of orgs pension
  some/all allowances — implausibly high vs the base-pay-only norm in UK
  DC schemes; (2) REW_PAY_020 is flat 20.0% Yes at every level, zero
  seniority texture; (3) the two CONTRADICT each other for 152/220 orgs
  (144 "Yes" org-wide but all-No by level; 8 the reverse).
- Prepared server/regen_allowances_pensionable.py: JOINT regeneration —
  one org-level pensioning latent (none/some/all, ownership-tilted:
  DB-legacy cultures up, PE/VC/founder-led down) drives BOTH questions so
  they cohere. Dry run: ALLOW_03 No 68.6%/some 19.5%/all 10.0%; matrix
  Yes 25.5% frontline -> 30.5% senior; coherence 220/220. Write path is
  double-guarded (--write AND --confirmed-by-david) so it cannot run by
  accident. AWAITING DAVID'S CONFIRMATION of BASE_SOME/BASE_ALL/OWN_TILT.

LEFT UNTOUCHED (David's call per the brief): LTI taper shape; tronc
sector skew; notice periods, multipliers, PMI, status-car metrics.

RUNNING FLAGGED COUNT: 4 (REW_INC_072 regenerated; REW_INC_061 code-fixed
+ flagged; pay frequency regenerated; allowances-pensionable awaiting
baseline) — well below the ~8-10 systemic threshold; no wholesale prior
rebuild indicated.

GATES AFTER RE-AGGREGATION: qa_integrity 0/180 mismatches; status audit
zero; qa_focus 23/23; qa_hero 25/25; qa_commentary 40/40.

## 2026-06-12 — Data submission: UI cleanup + soft-warn input guardrails

PHILOSOPHY (the core rule, enforced in code): soft warnings, never hard
plausibility blocks. A member can always enter their real value — a genuine
200% LTI or 150% exec bonus saves without friction. The ONLY hard blocks are
malformed input (text in a number field, an unlisted band) and true floors
(negative %/£ where negative is meaningless). Three layers in
app.py validate_answer + cross_field_warnings:
  1. hard floor — parse failure / below hard_min 0. Refuses the save.
  2. soft warn — crosses David's threshold -> "That's unusually high — common
     range is X–Y. Is that right?" The value is ALREADY SAVED when the warning
     shows; one click ("Yes, it's right — keep it") records the override
     (org, user email, question, row, value, threshold) in
     validation_overrides for optional review. Never gates submission.
  3. cross-field — seniority inversions ONLY on monotonic metrics
     (bonus/LTI/pension/notice; config-flagged), incl. banded rows compared by
     option order ("16 weeks" > "2 weeks"); never on flat-by-design matrices
     (pensionability/eligibility/tronc — flat is normal there). Plus
     max-below-target pairs (LTI max vs typical, bonus max vs target,
     pension max vs typical). Equal values never warn.

THRESHOLDS — DAVID'S CONFIG: data/validation_thresholds.json, seeded from the
library tolerances by server/seed_validation_config.py with the too-tight
caps WIDENED (library hard_max was 100 on all % fields): bonus % -> warn
above 250; LTI % -> 400; pension contribution % -> 40; salary increase
budget % -> 15 (tighter is useful); PMI -> £6,000; car allowance / per-
allowance £ -> £30,000; cost per FTE -> £250,000; market-position vs median
-> 60–150 (it stores % of median ~100, so the old 0-100 cap would have
warned every above-median payer). File HOT-RELOADS on edit (no restart); a
malformed edit keeps the last good config. Because thresholds only warn,
erring generous costs one extra click, never data.

% STORAGE CONVENTION (verified end-to-end): percentages are stored as human
numbers (50 means 50%) at entry, in thresholds, in aggregation and display.
Proven: 50 entered -> stored "50" -> aggregates with p50 37.0 -> displays
"50%"/"37%" — never 0.5% or 5000%.

N/A ≠ 0 ≠ BLANK (end-to-end): "Not applicable to us" is a first-class toggle
on every numeric/matrix question (selects already had is_na options). Stored
canonically as "Not applicable" (numeric: the value; matrix: question-level
at matrix_row_id='', which aggregation ignores by design). Counts as
ANSWERED for the unlock gate (proven: 81/82 -> 82/82 -> 100% when the last
key question was answered N/A); excluded from every median/distribution
(aggregate.py treats NA as a deliberate exclusion — excluded_na, never the
unrecognised-format warning; a label that IS one of the column's own options
is never treated as N/A). qa_integrity's independent reference implements
the same documented rule.

UI CLEANUP: sections are now SUB-powers (Pay 86 / Benefits 42 / Incentives 19
/ Transparency 25 / Progression 8) — one page each with its own progress
("Pay — 76 of 86 done") instead of one 180-question page; key (required)
questions come first under "Key questions — these unlock your insights",
optional ones after; £/% units sit INSIDE the input; banded matrix rows
(notice bands, multipliers, Yes/No) are DROPDOWNS of the allowed options,
not free text (free text could previously not even enter "12 weeks"
validly); yes/no questions are a segmented toggle; help_text inline with a
"What counts?" definition expander; autosave unchanged (server-side drafts,
proven to survive a fresh session). Dead FirmographicsStep removed
(superseded by /profile).

API SHAPE: /api/submission/state sections are sub-powers ({section,
superpower, ...}); /api/submission/section/{sub-power}; new POST
/api/submission/confirm-value. qa_focus's section assertion updated to the
new honest semantics (all sections ⊆ Reward; hidden section still 404s).

UNCHANGED: aggregation/suppression/polarity (gates re-run green), the
matrix-aggregation fix, reward-only focus, trust labels.

VERIFIED (API + UI): 1000% bonus warns + saves + confirm logs the override +
correcting to 100 clears the warning; 200% LTI saves silently; -5 and
"about ten" are refused (the only blocks); invalid band via API refused;
N/A advances the gate; banded dropdowns pre-select existing answers;
notice-band inversion warns, pensionability inversion doesn't; gates:
qa_integrity 0/180, status audit zero, qa_focus 23/23, qa_hero 25/25,
qa_commentary 40/40. Demo drafts restored after testing.

## 2026-06-12 — ENGINE AUDIT Phase 1 (report): storage / calc / suppression / cuts

NEW STANDING GATE: server/qa_engine_audit.py — a FRESH reference (no production
aggregation/parsing/suppression/library imports; question metadata parsed
straight from the questions table; own percentile/midrank/split/matrix-mode/
floor implementations; production read via the live HTTP API + stored
payloads). Exit code != 0 on failure; run pre-demo alongside the other gates.

LAYER 1 — STORAGE: VERIFIED. 197,414 raw CSV answers -> store: 0 changed,
0 missing, 0 extra (the 2 documented in-DB regenerations excluded and
verified against their seeded scripts' distributions instead). Per-type
round-trips byte-equal (incl. '1.5x'-class strings, banded labels). Tri-state
proven: zero stored as '0', N/A as text, 0 blank rows in the canonical store
(a cleared DRAFT stages '' by design and deletes the answer at submit). Live
write path round-trips multi-select strings, 0, N/A and blank distinctly.

LAYER 2 — CALCULATION: VERIFIED. All 180 reward metrics recomputed
independently: 3 numeric, 138 single-select, 6 yes/no, 12 multi-select,
14 matrix-numeric, 7 matrix-categorical — 0 value mismatches (n, P10–P90,
option counts/pcts, per-row matrix blocks). Scored-verdict spot: ALLOW_01
ref midrank 14.5 == prod 14.5. Cross-surface: card == dashboard list ==
stored payload (n=200, p50=3.7 on the probe metric).

LAYER 3 — SUPPRESSION: VERIFIED. 0 sub-floor blocks across every stored
payload/cut; served cards carry no internal '_' keys; a real 1-org custom
group end-to-end -> suppressed card, honest readout, AI commentary clean;
foreign/stale group id -> labelled All-peers fallback (never another org's
group); org_id injection on /api/my-data returns own data only.
Differential-attack residual remains FLAGGED to David (unchanged).

LAYER 4 — CUTS: VERIFIED. 19 sector/size cut n's == raw qualifying sets;
unclassified responders in 'all' only (62, none in filtered cuts); fte bands
are exact-match labels (no numeric boundary exists in the engine — banding
happens at profile capture); custom-group counts == raw (Retail 15==15);
self-inclusion consistent (self always counted).

DETERMINISM + EDGES: re-aggregation of identical data -> identical payload
hash (c5fef3b9...); same API call x3 identical; single value/zero-variance/
empty/negatives/all-zeros all behave (suppressed or sensible, no NaN).

THE BRIEF'S "CONFIRMED DEFECT A" (multi-select not split) — FALSE POSITIVE,
shown with evidence: production splits on ';' and matches an independent
split of the LIVE data exactly (ALLOW_01: Car 45.5%, Shift 41.4%, n=220).
The brief's "correct" numbers (Shift 81.2%, n=202) reproduce ONLY from
data/responses_orig — the pre-regeneration files superseded by the
documented 11-June regen. Its sub-claims, tested individually against live:
comma-only answers (95) are single options whose LABELS contain commas,
matched whole, never shredded or dropped; "You" marks ALL selections
(you.labels; the observed single mark was an org that genuinely selected
one option); "you selected X of N" uses the real count; the Behind·P15
verdict is correct under the intended option-count model (independent
midrank 14.5). NOTHING was changed to "fix" Defect A — the prevalences
production shows are right.

REAL DEFECTS FOUND (fixing in Phase 2):
- F1 'None' scores a point: 4 scored multi-selects give none-ish options
  option_score 1, so an org offering NOTHING scores like an org offering one
  item: ALLOW_01 'None' (13 orgs), EXT_REW_GAP_011 'None' (89 orgs),
  PROP_216f7323 'None / no formal strategy' (6), PROP_aa4061d5 'No formal
  measurement' (0 pure). Two other questions already handle this correctly
  (na_codes), so the library is internally inconsistent. Rule applied:
  "Not applicable" = not assessable -> na_code excluded; "None" = assessed
  zero provision -> scores 0. Config defect (scoring_config), not engine code.
- F2 PROP_7cdfcc7b ('Talent review coverage', Growth scope, HIDDEN from the
  reward launch) is typed multi_select but holds Yes/No answers — 1,176
  tokens unmatchable internally. No member-facing impact today. FLAGGED for
  David (out of reward scope; type/answer reconciliation is a library call).
- F3 gate mechanics: qa_integrity and qa_status_audit don't exit non-zero on
  failure (human-read only) — hardening in Phase 2.

EXISTING-GATES REVIEW: qa_integrity does test what it claims post-hardening
(categorical rows verified, populated-rows asserted; its multi-select
reference splits and would catch a non-splitting engine; its ';' delimiter
assumption is shared with production but now validated against the data by
the new independent gate). qa_focus (23) and qa_hero (25) assert what they
claim and exit non-zero. qa_status_audit is a printed audit, no exit code.
qa_commentary 40 checks. Blind spot closed by qa_engine_audit: none of the
old gates exercised the live custom-group path end-to-end or the cut-set
membership against raw.

## 2026-06-12 — ENGINE AUDIT Phase 2 (fixes)

F1 FIXED — none-ish options no longer score points. scoring_config
option_scores set 1 -> 0 in BOTH the questions table and
data/lumi_questions.csv for: ALLOW_01 'NONE', EXT_REW_GAP_011 'NONE',
PROP_216f7323 'NONE_NO_FORMAL_TOTAL_REWARDS_STRATEGY', PROP_aa4061d5
'NO_FORMAL_MEASUREMENT'. Rule now consistent across the library:
"Not applicable" (not assessable) -> na_code excluded from scoring;
"None" (assessed zero provision) -> scores 0. Re-aggregated; verified
INDEPENDENTLY: a None-answering org's ALLOW_01 score 10.0 -> 0.0 points and
EXT_REW_GAP_011 20.0 -> 0.0; corrected score p50s match a fresh recompute
exactly (22.22/25.0, n 220/215). Demo-org side effect (mechanical, not
favour): its 1-allowance percentile rose 14.5 -> 17.5 because the 13
None-orgs now rank below it — direction-verified by the independent midrank.
No answers changed (scores are derived; the integrity firewall untouched).

F3 FIXED — qa_integrity and qa_status_audit now sys.exit(1) on any failure
(CI-able like the rest). qa_engine_audit's ALLOW_01 spot-check updated to
the corrected points model (it initially red-flagged the fix — the gate
catching a model change exactly as designed).

F2 FLAGGED (not fixed — out of reward scope): PROP_7cdfcc7b 'Talent review
coverage' (Growth) is typed multi_select but holds Yes/No answers; David to
reconcile type vs data when Growth scope launches.

ALL GATES GREEN after fixes: qa_engine_audit 0 failures/0 warnings;
qa_integrity 0 mismatches; status audit zero; qa_focus 23/23; qa_hero 25/25;
qa_commentary 40/40 — all with non-zero-on-failure exit codes.

## 2026-06-12 — Core question-set versioning & governance (the rails for 2026.1)

WHAT EXISTS NOW: core_releases / release_questions / core_changelog /
core_backlog tables; the library's question_version / historical_comparability
/ status / replaced_by fields IMPORTED into the questions table (they were
CSV-only) plus release_entered / release_retired; server/releases.py (the
lifecycle module); /api/governance* + /api/trend/{qid}; an admin-only
Core governance page; qa_release.py standing gate (21 checks, self-cleaning
fixtures — restart the app after running it: it restores the DB but a running
process keeps the fixture question cache).

BASELINE: '2025-baseline' auto-captured at startup (idempotent): all 180 live
core questions snapshotted in full (exact reconstruction proven), every
question stamped with version + release_entered, snapshot 1 ('2026 H1')
stamped with the release it was aggregated under — BOTH reproducibility
dimensions (question set as-of release x data period) are now recorded.
Normalisation logged in the release notes: 27 live Reward questions carried
stale 'proposed' CSV status and were set 'active' (they were already seeded,
aggregated and member-visible).

RETIRE-NEVER-DELETE: status='retired' + release_retired; excluded from
visible_questions (live experience) but the row, its release-snapshot history
and its benchmark payloads all remain (proven: live API 404, baseline
snapshot intact, historical payload resolves). Retiring a required question
shrinks the basis (94 -> 93 in the fixture) — the gate only ever gets easier.

STICKY UNLOCK (the high-risk one): org_unlocked() now reads the stored
insights_unlocked_at stamp FIRST (plus unlocked_release); the stamp is
written centrally on first crossing and never removed. Proven: a release
adding 12 required questions (basis 82 -> 94) left the demo org unlocked,
and a pure-stamp fixture org at 0.0% completion stayed unlocked. New
required questions surface as new-to-complete (basis counts grow); access
never retreats.

COMPARABILITY BREAKS — STORED AND ENFORCED: 'break@<release>' markers in
historical_comparability (rating preserved: 'high; break@2026.1');
/api/trend returns the series as SEGMENTS split at each break and the
MetricTrend renderer draws segments separately with a dashed red 'reset'
divider — never a continuous line across a break (screenshot taken with a
forced break: 3.7 | reset | 4.1, two periods, no joining line).

CHANGE LOG / BACKLOG / EMERGENCY: the change log is generated by the RELEASE
DIFF (added/retired/reworded — single source of truth); core_backlog queues
candidates (2 member requests ingested from metric_requests + regulatory +
pulse-graduation seeds) and NEVER touches the live core; the emergency lane
refuses without BOTH the external 'factually wrong' trigger AND a sign-off
(both refusal messages proven), logs lane='emergency', and is the only
between-release path.

NOTHING ELSE CHANGED: no metric computation touched; all fixtures restored
(180 live / 82 required / baseline current); all seven gates green after a
fresh server start: qa_release 21/21, qa_engine_audit 0 failures,
qa_integrity 0 mismatches, status audit zero, qa_focus 23/23, qa_hero 25/25,
qa_commentary 40/40.

FOR THE 2026.1 RESTRUCTURE (next prompt): stage the 7-category changes on
the questions table, mark breaks on reworded questions, then
releases.create_release('2026.1', notes, sign_off) — the diff writes the
change log, the baseline stays reconstructable, nobody re-locks.

## 2026-06-12 — RELEASE 2026.1: the 7-category restructure

Executed AS A RELEASE on the versioning rails (apply_release_2026_1.py,
dry-run-first, idempotence-guarded), applied programmatically from the
authoritative lumi_restructure_mapping.csv — categories never re-derived.

THE 7 CATEGORIES (the only valid ones): Pay 41 · Incentives 21 · Benefits 50
· Time Off 26 · Wellbeing 14 · Recognition 7 · Governance 35 = 194. Verified
INDEPENDENTLY against the mapping: 180/180 existing questions in exactly
their NEW_category, zero mismatches, zero in old/none categories, zero
dropped/duplicated; counts equal the locked targets.

RE-FILING ONLY: 89 questions moved category; wording/version/scoring
untouched -> 0 comparability breaks marked, 0 retirements, payload values
intact (spot: EXT_REW_GAP_001 Pay->Recognition, n=213, P47 — full data),
qa_engine_audit recomputed every metric: 0 mismatches. The internal
metric/practice/policy/benefit display-type distinction is untouched.

14 NEW QUESTIONS (REW26_*): full schema from the mapping (type/options/
polarity/unit), authored help/definition, v1.0, entered 2026.1, all
UNSCORED + OPTIONAL (the unlock basis stays 82 — they can never re-lock or
gate anyone); no history by design — they trend from 2026.1. Library CSV
synced (+14 rows, categories updated). Soft-warn config regenerated (+2
numeric entries; David's file rebuilt from the library rules).

TRONC/TIPS HOSPITALITY MODULE: the 5 flagged metrics carry module=
'hospitality'; org_visible_questions(org) filters them for orgs outside
{Hospitality/Leisure/Travel, Retail & Consumer Goods} across every member
surface (index, cards, single metric 404, submission, hero, gap register,
analyst, commentary, my-data, shares). Proven both ways: demo (Retail) sees
194 incl. all 5; a Professional Services signup sees 189, 0 of 5, direct
fetch 404, Pay section 36. Module questions are never required (invariant
asserted by qa_release) so the gate stays org-independent.

TERMINOLOGY: "superpower"/"sub-power" removed from the user-facing product —
groupings are CATEGORIES, items are METRICS, the parent is just Reward.
Routes /superpower/Reward?sub=X -> /reward?cat=X (legacy URLs redirect);
sidebar = the 7 categories; card chips show the category; gap-register CSV
header reworded. Internal field names (sub_power column, payload keys)
unchanged — they now carry category semantics.

RELEASE MECHANICS: 2026.1 is current; 2025-baseline superseded and still
reconstructs (180 questions, old structure: Pay had 86). Change log: 89
recategorised + 14 added + 1 terminology line, all auto-generated by the
release diff (extended to log category moves WITHOUT breaks). UNLOCK
STABILITY proven: demo stamped 2026-06-11 (before) -> benchmark_unlocked
True after; basis 82 unchanged.

GATES updated for the new reality, then ALL GREEN: qa_focus 24/24 (194
counts; Wellbeing is now a REAL section returning 200 — the hidden-scope
probe uses Talent; 7-category by_section/methodology), qa_hero 25/25 (census
98 polarised/76 positionable/15 routed — delta fully accounted for by the 14
additions; domains: 5 of 7 carry market verdicts, Wellbeing/Recognition
prevalence-only below the polarised floor), qa_engine_audit 0, qa_integrity
0, status audit zero, qa_commentary 40/40, qa_release 0 (incl. new module
invariant). Probe org removed after testing.

## 2026-06-12 — ENGINE AUDIT (post-2026.1) Phase 1: report

Run on a FRESH app process, with the served question count verified against
the DB before any check (194 == 194 — the stale-cache footgun addressed
up front; made permanent in Phase 2).

L1 STORAGE: VERIFIED on 2026.1 data — 197,414 raw rows, 0 changed/missing/
extra (regen whitelist intact); tri-state (0 / 'Not applicable…' / no row)
shown on real rows; suffix/banded strings verbatim; the 14 new questions
correctly have ZERO stored rows.

L2 CALCULATION: VERIFIED — independent recompute of all 194 (5 numeric,
142 single-select, 12 yes/no, 14 multi-select, 14 matrix-numeric,
7 matrix-categorical): 0 value mismatches; ALLOW_01 verdict midrank
17.5 == prod 17.5.

REGRESSION TARGETS (both fixes HELD through the migration):
- Multi-select split: all 12 data-bearing metrics' top-option counts/pcts
  match an independent live-raw split exactly (ALLOW_01: Car 45.5/Shift
  41.4/Travel 18.6/Mobile 35.9/On-call 32.3 — note: the brief's reference
  table (Shift 81.2%, n=202) reproduces only from the superseded
  responses_orig files, per the 2026-06-12 adjudication; LIVE raw is the
  ground truth). The 2 new multi-selects suppress at n=0.
- Matrix rows: all 21 matrices aggregate every populated row (live n per
  metric pasted; tronc n=26, notice n=220, multipliers n=191); 0 failures.

L3 SUPPRESSION: VERIFIED — 0 sub-floor blocks in any stored cut; '_' keys
stripped; live 1-org group suppressed end-to-end incl. AI commentary;
foreign group id -> labelled all-peers; org_id injection clean; differential
residual remains flagged (unchanged).

L4 CUTS: VERIFIED — 19 cut n's == raw qualifying sets; unclassified in
'all' only; bands exact-match labels; Retail group 15==15; self-include
consistent.

L5 RESTRUCTURE INTEGRITY: VERIFIED —
- Mapping diff (fresh read): 0 mismatches; counts == locked (194).
- No computed value moved: 5 recorded pre-2026.1 values (salary-budget
  n=200/p50=3.7; pay-frequency Monthly 71.5%; ALLOW_01 score 220/22.22;
  EXT_REW_GAP_011 score 215/25.0; recognition-budget n=213) all identical
  live.
- 14 new questions: 0 answers, 0 history, valid schema, payload suppressed
  (n=0), entered 2026.1 — 0 failures.
- Rollups/denominator: overview by_section, hero domains, submission
  sections, methodology scope ALL the 7 categories; basis_total 82; zero
  Transparency/Progression references on live surfaces.
- Comparability: re-filing marked no breaks; re-categorised trends resolve.
- Sticky unlock: pre-2026.1 stamp (2026-06-11) -> still unlocked.

DETERMINISM + EDGES: payload hash identical across re-aggregation
(79a2a771…); API x3 identical; single/zero-variance/empty/negative/all-zero
inputs behave.

DEFECT FOUND (Phase 2): F1 — ALLOW_03 carries a stale comparability-break
marker 'break@2026.0-test2+emergency', residue of the versioning build's
interactive emergency-lane FIXTURE (the manual cleanup string targeted
'2026.0-test+emergency'; the marker was written under 2026.0-test2). Inert
in current trend logic (the release id no longer exists so no boundary can
cross it) but false metadata on a live question. The standing qa_release
gate does NOT leave this residue (its emergency fixture sets no break).

GATE REVIEW: qa_engine_audit/qa_release/qa_focus/qa_hero/qa_integrity/
qa_status_audit/qa_commentary all test what they claim post-2026.1 updates
and exit non-zero. Gaps to close in Phase 2: (a) qa_engine_audit doesn't
self-check app-cache freshness (the footgun); (b) no gate catches break
markers referencing nonexistent releases (the F1 class).

## 2026-06-12 — ENGINE AUDIT (post-2026.1) Phase 2: fixes + gate hardening

F1 FIXED: ALLOW_03's stale fixture break marker removed
(historical_comparability back to 'medium'; 0 break markers in the library —
correct, since no real rewording has shipped).

GATES HARDENED:
- qa_engine_audit now SELF-CHECKS app-cache freshness before auditing
  (served question count vs DB live core) and exits 2 with a loud FATAL on
  staleness — proven by simulation: DB retire -> "app serves 194, DB 193 —
  STALE… restart" exit 2; restored. A forgotten restart can no longer
  produce a falsely-green audit.
- qa_engine_audit's scope now excludes retired questions (latent bug found
  by the simulation itself: post-retirement it would have 404-failed every
  API comparison).
- qa_release gained break-marker hygiene: any 'break@<release>' referencing
  a nonexistent release (the F1 fixture-residue class) fails the gate.

ALL SEVEN GATES GREEN on a fresh server (qa_release last by documented
convention): engine_audit 0 failures (incl. freshness pass 194==194),
integrity 0 mismatches, status audit zero, focus 24/24, hero 25/25,
commentary 40/40, release 0 failures (incl. the new hygiene + module
invariants).

## 2026-06-12 — PULSES (Tier 2): timely topical surveys, separate surface, one engine

WHAT EXISTS: pulses / pulse_participants / pulse_responses tables;
server/pulses.py (lifecycle, participation, report, graduation);
/api/pulses* endpoints; a distinct "Timely pulses" UI area (web/js/pulses.js,
route /pulses) visually and structurally separate from the 7-category core
nav; seed_pulse.py ("EU Pay Transparency readiness 2026", 5 questions, 12
seeded synthetic participants); qa_pulse.py standing gate (25 checks,
self-cleaning; restart the app after running it, same convention).

THE CARDINAL RULE — STRUCTURAL SEPARATION, PROVEN BOTH WAYS: pulse responses
live in pulse_responses; the core engine reads `answers` only. The decisive
test: the demo org answered PROP_9e4ad87f as 3.9 in core and 9.9 in the
pulse — core aggregate before == after (n=200, p50 3.7; payload
byte-identical even after a full core re-aggregation with pulse sentinels
present), while the pulse aggregate (n=13, p50 4.2, max 9.9) matched an
independent recompute of pulse_responses exactly. Reverse direction: pulse
n=13, never the 200-org core pool.

ONE ENGINE: pulse_report calls aggregate_question_for_orgs — the same entry
point as the core. Proven on the historically broken types: a pulse
multi-select splits (Car 4/5 = 80%), a pulse matrix row aggregates
(n=5, p50=22); n>=5 floor exact (4 participants -> every question
suppressed + the honest holding state "results appear once 5+ have taken
part"; the 5th serves).

LIFECYCLE: draft invisible to members (list + detail 404) -> open
(join/respond/submit inside the window; closes_at extendable) -> closed
(responses refused, window extension refused — NO reopen in v1, report
final) -> archived (report retained). Question definitions are SNAPSHOTTED
at open (release-style): after a simulated core reword, the archived pulse
still rendered the question as-asked.

INDEPENDENCE (give-to-get per pulse): participation never moves the core
unlock (stamp + basis 82 unchanged); a core-LOCKED org joined, answered and
participated; report access requires participating in THAT pulse only.
Whole-cohort view only in v1 (no cuts — opt-in cohorts would suppress every
cut); deferred until cohorts grow.

AI: pulse commentary rides generate_metric_commentary + the SAME
validate_commentary gate, cohort-scoped payload; LUMI_AI_PULSE kill switch
joins the family (off -> 403, proven on a throwaway instance; on ->
validated deterministic output without an API key).

GRADUATION: graduate_question() promotes the DEFINITION only — the pulse
question entered the live core with ZERO core responses (asserted
structurally; the pulse's responses stay in pulse_responses); it is logged
'added' by the next release diff and trends from entry. Pulse-origin
questions (superpower='Pulse') are invisible to the core scope and excluded
from core releases until graduated.

CREATION AFFORDANCE (flagged): pulses are created via seed script +
pulses.py functions (superadmin/engineering action) — the back-office
console remains unbuilt (D2). Members only join and respond.

REGRESSION: all EIGHT gates green on a fresh server (engine_audit 0,
integrity 0, status audit zero, focus 24/24, hero 25/25, commentary 40/40,
pulse 25/25, release 0) — the core is untouched.

## 2026-06-12 — RELEASE 2026.2: 12 forward-looking additions (pure adds) + calibrated seed

THE RELEASE (apply_release_2026_2.py, from lumi_release_2026_2_questions.csv
verbatim — nothing invented): Governance 6 / Pay 4 / Time Off 2, all
OPTIONAL + UNSCORED. Counts now Pay 45 · Incentives 21 · Benefits 50 ·
Time Off 28 · Wellbeing 14 · Recognition 7 · Governance 41 = 206. Change
log: 12 added / 0 retired / 0 reworded; zero break markers anywhere; the
existing 194 byte-identical vs the 2026.1 snapshot (8-field diff = 0);
2025-baseline (180), 2026.1 (194) and 2026.2 (206) all reconstruct;
basis stays 82 — the demo org remained unlocked (81/82, insights live).

QA HARDENING APPLIED: ids assigned from hints with collision check
(REW262_*); the action-plan 'None' carries option_score 0 in a
future-proofed scoring_config (the F1 class can't reappear if scored
later); guaranteed-hours / cancelled-shift / shift-notice carry a
first-class 'Not applicable' option (is_na + na_codes; counted as answered,
shown in the distribution flagged is_na, practice_status -> unknown so it
never enters prevalence/adoption); the AI-skills premium stays NEUTRAL
(prevalence only, no verdict); option labels asserted delimiter-free.
Hero census DERIVED, not drifted: 98->109 polarised (+11; the neutral is
the 12th), positionable 76 unchanged (all additions unscored selects),
routed single-selects 15->22 (+7) — frozen into qa_hero with the
derivation; qa_focus updated to 206.

THE SEED (seed_release_2026_2.py via apply_seed_2026_2.py): David-signed
baselines as TARGETS; firmographics-only conditioning mapped to the real
registry (FTE midpoints, HR_Maturity 'Advanced', Public Sector Body,
Workforce_Frontline/Shift_%, tech sectors); seeded
f"{qid}|2026-06-12|{org_id}", org-blind, whole-metric, reproducible
(re-run identical). CALIBRATION (the pay-frequency precedent): the script's
tilt damping PLUS driver-side input-constant compensation, because (a) the
provided script never calibrated the action-plan multi (realised has-plan
47.3% vs signed 30% — tilts added straight to the base) and (b) four
questions sat 3.4-6.1pp off with tilts at zero (fixed-seed sampling
variance incl. a modal flip on pay-in-adverts). Final realised vs signed:
ALL 12 within 3.0pp, every modal matches the signed modal, action plan
27.3% vs 30%. offer_na routing: applicable n = 190/183/183 of 220
(salaried/no-shift orgs answered 'Not applicable'). Write double-guarded
(--write --confirmed-by-david), refused if any REW262 answer pre-exists.
2,640 responses inserted (answers + history), re-aggregated. INTEGRITY:
no existing metric touched; no value hand-tuned; the demo org drawn by the
same blind rule (its answers on record incl. 'None' action plan and
'No AI use' — visibly not favour-tuned).

PROOFS: action-plan aggregation matches an independent raw split exactly
(Gender 56/25.5%, None 160/72.7%, n=220); shift-notice serves the N/A bar
flagged is_na with practice_status('Not applicable')='unknown'; trend
starts at 2026.2 (1 period). ALL EIGHT GATES GREEN after restart
(engine_audit 0, integrity 0, status zero, focus 24/24, hero 25/25 with
the new census, commentary 40/40, pulse 25/25, release 0).

## 2026-06-12 — Ordered-categorical chart redesign + call-out metric fix

PART B DIAGNOSIS (reported before fixing):
- TITLE was the wrong half. REW_PAY_018's full text — "Is there a minimum
  call-out payment for call-outs (e.g., minimum hours paid)?" — confirms the
  intent: a minimum-hours-paid-per-call-out guarantee (a real reward
  practice). The hour OPTIONS are correct; the templated display title
  ("A minimum call-out payment for call-outs") was wrong AND redundant.
  Fixed display labels only ("Minimum hours paid per call-out"; DB + library
  CSV), text untouched — the pay-frequency label-fix precedent: no
  rewording, no comparability break, nothing seeded, nothing for David.
- THE DISTRIBUTION WAS COMPUTED CORRECTLY all along: independent recompute
  from raw == production exactly (10.0 / 19.5 / 37.7 / 30.0 / 2.7 = 100.0%,
  n=220). The "98%" reading was StackedDist's LEGEND truncation (top-4
  labels + "+N more") — display-only, fixed by Part A. Presentation-only
  proof: the computed block hash is byte-identical before/after
  (9c32bef3c7b01e5a == 9c32bef3c7b01e5a).

PART A — OrderedDist replaces StackedDist everywhere:
- New chart (charts.js OrderedDist): one bar per category in the question's
  defined option order (the same order the engine uses for banded
  aggregation), label directly beside its own bar, % on the bar, the org's
  answer marked IN PLACE (highlighted bar + rail dot + "· You"), a thin
  ordinal rail signalling "scale", EVERY category visible — zero-count real
  options included at 0%, only zero-count N/A rows dropped, no "+N more".
  Suppression/polarity/neutral handling unchanged (same props, same fav
  palette rules).
- ROUTING (the consistency sweep): single_select + yes_no now have ONE
  honest representation ("ordered") via chartAlternatives — this covers
  every card surface through CardBody (the reward grid, My view, the full
  metric page, share views) plus pulse report blocks (pulses.js).
  multi_select KEEPS OptionBars (prevalence, independent %s). Banded MATRIX
  rows KEEP the per-level table (MatrixSelect): its labels/modal/You are
  explicit table columns — the detached-legend defect never applied there,
  and per-row full bar lists for 7 levels x 9 bands would not be compact.
  StackedDist is deleted; stale stacked_bar chart prefs/defaults normalise
  to "ordered" automatically.
- PURE PRESENTATION: no server change for Part A; the API payload and every
  computed number untouched (gates + block hash prove it).

VERIFIED: call-out card renders all 5 categories summing to 100% with
"You · 2 hours" in place and the corrected title; pay-in-adverts
(Never 44.1 You / Some 40.5 / All 15.5) and bereavement (Statutory 40 /
1-5 days 45.5 You / 5+ 14.5) on the new chart; ALL EIGHT GATES GREEN after
restart (engine_audit 0, integrity 0, status zero, focus 24/24, hero 25/25,
commentary 40/40, pulse 25/25, release 0).

## 2026-06-12 — Seed the 14 release-2026.1 additions (firewall) + collision fix

PRECONDITIONS REPORTED: 2026.2 + its seed verified in place (2,640 REW262
answers); the allowances-pensionability regen has NOT run — it remains
prepared and awaiting David's baseline confirmation by design (no data
operation was in flight, so no interleaving risk); REW26_* answers were zero.

ID MAPPING: all 14 id_hints matched to live 2026.1 REW26_* questions (table
in the run output). Resolutions: the LEVELLING question's live schema is
MULTI_SELECT (the brief's anticipated case) — its options are mutually
exclusive coverage levels, so each org draws ONE option and calibration
verifies per-option prevalence against the signed distribution; five script
labels remapped to the live option labels (MH first aiders / Digital app /
MH days / >Annual / >8%) so every stored value matches the library exactly.

SEED (seed_release_2026_1_additions.py via apply_seed_2026_1_additions.py):
real-registry firmographics only; seeded f"{qid}|2026-06-12|{org_id}";
org-blind whole-metric; reproducible (re-run identical); double-guarded
write refusing pre-existing answers. CALIBRATION covered ALL 14 — the
script's tilt damping plus driver-side input compensation (the documented
2026.2 pattern), INCLUDING the multi_select per-option marginals and both
numerics (median + N/A share). Realised vs signed: all categoricals within
2.7pp with modals matching; MH provisions marginals within 2.3pp
(counselling 62.3 vs 60, None 17.7 vs 16); wellbeing budget median 103 vs
100 with N/A 60% vs 62% (applicable n=89 — the ~62% no-ring-fenced-budget
routing); pension cost median 6.8 vs 7.0. 3,080 responses written +
re-aggregated. Demo org drawn blind (its record includes 'None' levelling,
'Not applicable' budget — visibly unfavoured). Neutral metrics (pension
type, skills-based pay) carry no verdict (score=None). Hero schema census
unchanged (109/76/22 — data growth doesn't move it; market pool 94 because
the demo org's budget answer is N/A, prevalence pool grew to 96 with the
newly answered practices).

DEFECT CAUGHT BY THE GATES AND FIXED: REW26_WEL_STRATEGY had an OPTION-CODE
COLLISION from the 2026.1 apply script — slug_code('>Annual') ==
slug_code('Annual') == 'ANNUAL', so select_block merged both options'
counts (prod 'Annual' 81 vs raw 64; the 17 '>Annual' answers absorbed).
Schema bug latent since 2026.1, exposed by first data. Fixed: '>Annual'
code -> 'GT_ANNUAL' (codes are internal keys; answers store labels — no
data change), CSV synced, re-aggregated; platform-wide scan found exactly
this one collision; qa_release now asserts option-code uniqueness for every
question so the class can't recur. After fix: Annual 64/29.1%, >Annual
17/7.7%, sum 100%.

ALL EIGHT GATES GREEN after restart (engine_audit 0, integrity 0, status
zero, focus 24/24, hero 25/25, commentary 40/40, pulse 25/25, release 0
incl. the new uniqueness invariant).

## 2026-06-12 — Allowances-pensionability regeneration APPLIED (David's baselines signed)

THE PREPARED SCRIPT (regen_allowances_pensionable.py — built, dry-run and
double-guarded earlier) ran with David's now-signed constants. CONSTANT
MAPPING (reported): BASE_SOME=0.20 and BASE_ALL=0.08 are the SIGNED
ORG-LEVEL TARGETS (some ~20% / all ~8% / No ~72%); because the ownership
tilts lift the realised mean above the base constants, the working constants
were calibrated (the documented pay-frequency pattern, one iteration:
BASE_SOME 0.186, BASE_ALL 0.053) so the REALISED split lands on the signed
targets. SENIOR_ONLY_SHARE -> 0.0 (signed: flat within an org, NO seniority
lean — pensionability is a scheme rule) and the prepared formula's small
HR-maturity term was zeroed (signed: ownership-only texture). OWN_TILT kept
as prepared (DB-legacy/public up, PE/VC/founder-led down — matches signed).

DRY-RUN SHOWN BEFORE WRITING, then applied (--write --confirmed-by-david):
- Realised org-level split: No 70.0% / some 19.1% / all 9.1% (+Varies 0.5,
  DK 1.4) — within ~3pp of the signed 72/20/8.
- COHERENCE — the main prize: ALLOW_03 vs REW_PAY_020 contradictions
  152/220 -> 0/220 (recomputed from the STORED data post-write).
- 220/220 orgs uniform across all 7 levels (flat-within-org BY DESIGN);
  per-level Yes uniform at 29.1% — the texture is BETWEEN orgs, by
  ownership, exactly as signed: Public Sector Body 68.8% some/all ->
  Charity 46.7 -> Mutual 45.5 -> PLC 41.2 -> Private 21.2 ->
  Founder-led 14.3 -> PE-backed 7.7 -> VC 0.0.
- Reproducible (two dry runs byte-identical); org-blind (demo org No->No by
  its own draw; watch orgs moved in both directions); whole-metric, one
  transaction, both questions.
- DATA-ONLY: schema/options/codes hash byte-identical before/after
  (037dd00136216d95) — the code-collision class cannot have been
  reintroduced; matrix rendering untouched.

GATE BOOK-KEEPING: ALLOW_03 + REW_PAY_020 joined qa_engine_audit's
documented REGEN_WHITELIST (store verified against the signed seeded
distributions: ALLOW_03 154/42/20/3/1, REW_PAY_020 No 1092 / Yes 448 —
the response CSVs are stale for these two by design, like REW_INC_072 /
EXT_REW_GAP_013); the release-addition seeds (REW26_*/REW262_*) are now a
recognised DB-origin lineage in the L1 extra-rows check (their lineage is
the seed scripts + DECISIONS, not the CSVs). ALL EIGHT GATES GREEN
(engine_audit 0 failures/0 warnings, integrity 0, status zero, focus 24/24,
hero 25/25, commentary 40/40, pulse 25/25, release 0 incl. the option-code
uniqueness invariant).

This was the LAST QUEUED DATA OPERATION. The flagged-metric ledger closes:
REW_INC_072 regenerated; pay frequency regenerated; allowances-pensionability
regenerated (this entry); REW_INC_061 remains code-fixed + flagged (David's
call on prior/reword/removal).

## 2026-06-12 — Home dashboard rebuilt: 80% visuals, signals introduced

THE THREE QUESTIONS, TOP TO BOTTOM: where do I sit overall (the ARC — the
94 positioned metrics as three performance-palette segments with the verdict
word centred: Below / 34-46-14); what should I look at (SIGNALS); where do I
sit per category (SEVEN TILES — verdict chip, peer-band with the org's dot
at its median polarity-adjusted percentile, x/y majority-practice count,
lens dots where signals live; practice-view categories show a prevalence
fill instead of a dot). Leads/gaps became micro-band chips (deduped per
question, click-through to the metric). The £ opportunity panel is ABSORBED
into signals; the "Your journey" strip is CUT until a second data period
exists; the locked give-to-get treatment carries over (signals + gaps blur
with the same lock note for not-yet-unlocked members).

SIGNALS (the new machinery, server/signals.py): outcome-lens flags — save /
attract / retain / engage — derived ONLY from data the engine already
computes: position items (behind-lens: polarity-adjusted percentile at/below
the threshold), practice prevalence via aggregate.practice_status applied to
the cut's distribution block (the same single source of truth as the gap
register — and it covers the UNSCORED 2026.1/2026.2 additions, which the
register's is_scored filter excludes), cost percentiles (save-lens on
neutral spend metrics — a fact about cost, never a market verdict), and the
£ model (money-lens). DAVID OWNS data/signal_lenses.json: the metric->lens
map, thresholds (behind P25 / save P85 / prevalence 50% / £10k floor),
max_signals 5 and max_per_lens 2 — hot-reload, malformed edits keep the
last good config. TRUST RULES enforced + gated: flags carry a peer fact and
never a directive; neutral metrics can never flag 'behind'; every kind must
come from David's maps. Demo org's live briefing: £75k/yr pension gap
(retain/money), flex allowance P5 (retain/behind), 56% of peers put pay in
adverts (attract/prevalence).

API: /api/overview adds signals, structured leads/lags, and dot/signal_lenses
on hero domains (ADDITIVE — the hero payload the gates assert is untouched).
One engine fix found while wiring: practice_status returns 'not_in_place'
(not 'absent') — corrected in the prevalence check.

GATES: qa_hero grew to 30 checks with a SIGNALS trust section (caps, live
targets, no behind-on-neutral/unmapped kinds, factual wording, dot range
[1,99]). ALL EIGHT GREEN after restart (focus 24/24, hero 30/30, engine
audit 0, integrity 0, status zero, commentary 40/40, pulse 25/25, release 0).

FOR DAVID: signal_lenses.json is yours — the seeded lens mapping and
thresholds are my best-guess defaults from the design discussion; adjust
freely (hot-reloads). Lens icons/labels deliberately quiet; the performance
palette stays reserved for verdicts (arc, tile dots, chips).

## 2026-06-12 — Dashboard polish: lens colour identity

Per David ("much more colourful and polished"): the LENS PALETTE from the
approved mockup is now a documented design-system extension — four hues,
each owned by one outcome lens, used EXCLUSIVELY on signal chips/dots with
the lens tag attached (never on charts or verdicts): save emerald
(#0E8A5F), attract violet (#6D5BD0), retain teal-ink (#0E7A8A), engage
coral (#C2542E), each with a tint. Signal rows are full-tint with coloured
glyphs (new icons: coins/magnet/anchor + heart) and filled lens pills.
Arc verdict word takes the verdict colour; legend counts became tinted
pills. Category tiles gained verdict-coloured top accents, blue icon
roundels (coins/trending-up/shield/sun/heart/award/list-checks), bigger
shadowed dots and a practice-view chip. Lead/gap chips: coloured section
headers (star/target) + tinted P-pills + hover rows. Performance palette
remains reserved for verdicts; blue remains identity. qa_hero 30/30.

## 2026-06-12 — Dashboard motion: premium, calm, accessible

Entrance choreography on the overview (run-once, never looping): cards and
tiles rise in with a 60-80ms stagger; the ARC DRAWS ITSELF (pathLength
dash animation, segments 140ms apart) with the verdict word and count-up
legend (rAF ease-out, ~750ms) arriving after the draw; tile/chip dots pop
in with a soft overshoot. Micro-interactions: signal rows lift and reveal a
chevron affordance on hover; category icon roundels scale/tilt; P-pills and
dots scale on hover. ALL of it is disabled under prefers-reduced-motion
(including the count-up, which renders the final number immediately).
Choreography total ~1.1s, cubic-bezier ease-outs, nothing loops — premium
without noise. qa_hero 30/30 unchanged.

## 2026-06-12 — Dashboard premium pass 2: ambient depth + crafted detail

An AURORA backdrop behind the hero (three ultra-soft radial washes in the
brand/lens hues at 3.5-5.5% alpha — ambient light, not decoration;
pointer-transparent). Cards carry an inner top hairline highlight over the
soft shadow. The arc gained a full sunk TRACK behind its segments and an
n-pill. Signal rows: lens-coloured left SPINE, the icon in a white shadowed
ROUNDEL (tilts on hover), and a lens-hued hover GLOW. Every position band
gained a MEDIAN TICK at 50 (the craft detail that makes dot placement
readable). Category tiles reveal a ghost arrow on hover. All static depth
or hover-only response — nothing loops; reduced-motion handling unchanged.

## 2026-06-12 — Market-position traffic light (David) + spacing rhythm

COLOUR SEMANTICS CHANGED on every market-position surface (David's
pay-positioning convention): AT MARKET = GREEN (aligned — the target),
ABOVE = RED (premium cost), BELOW = AMBER (lagging). Applied to the arc
segments + verdict word + legend pills and the category tiles' chips, top
accents and dots. Metric-level favourability (leads/gaps chips, card
pills, polarity-adjusted verdicts elsewhere) keeps the original
good-green/bad-red language — these are two different judgements: "is this
single metric favourable" vs "where does our overall positioning sit".
Documented here so the apparent green/red inversion between surfaces is
understood as intentional.

SPACING: one rhythm — s4 gaps and margins on every hero grid (top row,
tiles, chips); tiles are flex columns with uniform s3 internal gaps (ad-hoc
margins removed, headers min-height aligned); the tile grid is a forced
7-across on >=1240px (6+1 orphan wrap eliminated) and balances 4+3 below.

## 2026-06-12 — Bright amber + declutter pass

AMBER SPLIT into two tokens: --neutral-perf #C77F06 (text — readable on
warm paper) and --amber-bright #F5A60A (graphics: arc segment, tile dots,
top accents). DECLUTTER: the firmographic chip row under the company name
REMOVED (industry/FTE/region/peer-count/window) — the page is about
position, not registration data; the ILLUSTRATIVE-SAMPLE trust chip stays
(trust labels are inviolable) along with the active-filter chip. Signal
rows now carry TERSE labels (signals.py label_short: boilerplate stripped,
44-char cap) with the full fact in the hover tooltip; the "flags not
advice" line moved to the Signals header tooltip; the arc lost its
subtitle ("94 metrics" pill only); tile captions are bare counts (12/23)
with tooltips. qa_hero 30/30 (wording check runs on the full detail field,
unchanged).

## 2026-06-12 — Hero arc rebuild (alignment fix)

David: the gauge looked poor — overlapping rounded caps at the segment
joins, ragged legend, floating metrics pill. Root cause: round line caps
paint strokeW/2 PAST the path endpoint, and the old fixed 0.06 gap was
smaller than two cap radii, so adjacent segments collided into blobs and
the painted arc overran its baseline. Fix = cap-aware geometry: every
span (track included) is inset by the cap's angular size capF =
(W/2/R)/π plus a 0.022 visible gap, so painted extents land exactly
where intended. Verdict word + "94 metrics" now centred INSIDE the
gauge ("At market" replaces the cryptic "With", auto-shrinks to fit);
legend is a 3-equal-column grid of nowrap pills. Presentation-only.

## 2026-06-12 — Tile alignment + every category gets a market position

David: the Pay tile was misaligned vs the rest, and Wellbeing/Recognition
must show market position like the other five. Layout: the status chip now
sits on its OWN row in every tile (it used to share the title row and wrap
only when too wide — the source of the misalignment).

POSITION FOR EVERY TILE, honestly: Wellbeing has zero polarised metrics in
the score/value pool (its 8 scored questions are neutral remote-working
policies; its 6 direction-bearing questions are the deliberately-unscored
2026.1 additions) and Recognition has one. Two grades of verdict now exist:
- market (unchanged): the strict, methodology-grade verdict, >= 5 distinct
  polarised questions. The overall arc, signals, chips and gap register are
  untouched (arc pool still 94).
- position (new, what tiles render): the strict verdict when present;
  otherwise an INDICATIVE verdict from combined polarised + practice
  evidence, basis + evidence counts disclosed in the chip tooltip.
Practice evidence = positions.practice_position_items(): the org's presence
status (practice_status -> STATUS_POINTS, the established single source of
truth) percentile-ranked against the peer status distribution from the SAME
stored block. Neutral questions never position; N/A is never evidence;
multi_select excluded (option shares can't reconstruct per-org statuses);
scored questions stay with the score layer. LUMI_TILE_MIN_POSITIONED
(default 1) is David-tunable. Live: Wellbeing = indicative "above" from 4
practice positions (EAP/finwell/screening/strategy; the N/A budget answer
correctly excluded), Recognition = indicative "at" from its single metric.
qa_hero grew 30 -> 42 checks (strict floor intact, basis disclosure,
N/A/neutral/multi/scored refusals, arc-pool isolation).

NOTE (debugging artefact, not product): the demo seed contains BOTH
"Thornbridge Advisory plc" and "Thornbridge Retail Group plc" — the demo
org is Retail Group. A stray EMPTY server/lumi.db was accidentally created
by an ad-hoc sqlite3.connect during diagnosis; the real DB is ./lumi.db at
the repo root. The stray file is safe to delete.

## 2026-06-12 — Chrome rationalisation §0: the Governance nav dot, traced

FINDING (pre-task, before any nav change): the orange dot beside
Governance (41) is the GAP CUE — deliberate state, not leftover. app.js
fetches the live gap register on load, counts not_in_place rows per
category, and marks the category with the MOST of them (gapCue →
SectionNav → .gap-cue, --neutral-perf amber). It already carries a
factual tooltip: "N practices your peers commonly have that you don't —
your biggest opportunity area". It sits on Governance for the demo org
because Governance holds Thornbridge's largest cluster of peer-majority
practices not in place.

ADJUDICATION vs the spec's two branches: it is NEITHER a new-in-release
indicator NOR unintentional. The spec's "New metrics in this category"
tooltip would mislabel it — this dot is an opportunity cue, not a
release flag. DECISION: keep the mechanism and its existing truthful
tooltip, re-attach it to the Benchmark group's category child rows in
the new IA. If David wants a separate new-in-release dot per category,
that is a different (additive) indicator — flagged for David.

## 2026-06-12 — Chrome rationalisation PR-1: sidebar IA, redirects, gating

NEW SIDEBAR (spec §1): the 19-item rail collapses to Overview, My view,
Priorities (was Gap register), Pulse (was Pulses; orphan "TIMELY PULSES"
header gone), a Benchmark ▾ group (parent = label+chevron only; All·206
the first child carrying the total; eight category children), then YOUR
ORGANISATION → Your data (My data + Submit merged), Team (admin),
Settings (admin). Core governance + Methodology + Sign out move into the
identity block; no separate footer block.

BENCHMARK GROUP (§1.1): expand state persists per user via the prefs
store (_nav.benchmark_open); default expanded on first visit. Counts live
(catalogue-driven), right-aligned, tertiary. The gap-cue dot (§0) rides
the relevant child row, tooltip intact. "Time Off" renders "Time off".

BOARD PACK (§1.2): ceases to be a nav destination — now an "Export board
pack" action on Overview (generates under the current peer filter) with a
chevron menu of previous packs. Hidden while insights locked. Old
/boardpack route 301s to Overview and pulses the export button once
(sessionStorage lumi-bp-migrated).

YOUR DATA (§1.3): one destination = old My data (view) with Submit as the
primary in-page action (hidden for viewers). Submission flow unchanged
(privacy/terms links handled in PR-3 §6.3).

RESERVED SLOT (§1.4): code comment marks the Signals insertion point
between Overview/My view and Priorities; renders nothing.

REDIRECTS (§7): mapLegacyRoute in core.js 301s every old hash —
/gap-register→/priorities, /pulses→/pulse, /reward→/benchmark,
/mydata→/your-data, /submission→/your-data/submit, /shares→
/settings?tab=sharing, /boardpack→/overview. Crawl-verified: 9/9 map,
zero 404s. All in-app nav()/href references updated in the same change.

ROLE GATING (§8): Team/Settings/Core governance hidden (not disabled) for
non-admins; direct route access renders an Admin-area lock. Verified with
the contributor account. Settings absorbs Manage shares as a "Sharing"
section (SharesPage gains an embedded mode).

Client-only change (web/js, web/css, html) — no server/engine/catalogue/
seed files touched. Full gate suite green (8/8). Cache v51→v52.

## 2026-06-12 — Chrome rationalisation PR-2: top bar + profile menu

TOP BAR (§2): one slim row over the content area — self-labelling peer-set
chip ("PEER SET" tag + "All peers · 220" value; option counts switched from
"(220)" to "· 220"), search (placeholder UNCHANGED per spec), the single
accented Ask lumi CTA, and the avatar. REMOVED: the duplicated wordmark
(was never in the top bar — confirmed), the "Comparing against all 220…"
helper line (cutHint now only renders for not-classified onboarding or a
too-small custom group, as a compact note), and "Request a metric" (moves
to the search empty state in PR-4; SearchPop gained an onRequest prop ready
for it). Saved vertical space returns to the content area (topbar now
center-aligned, single row).

PROFILE MENU (§3): avatar = initials circle (display-name initials, else
email). Dropdown: identity header (signed-in user + org, non-clickable) →
Your profile (/profile) → How lumi works (/how-lumi-works) → Sign out.
Closes on click-away and Escape. The account block and reference links now
live HERE — the sidebar footer is GONE (removed the .nav-id block added in
PR-1). Core governance / Methodology fold into the How lumi works hub
(PR-3); /how-lumi-works currently renders MethodologyPage as a shippable
placeholder until PR-3 swaps in the merged hub.

Client-only (web/js, web/css, html). qa_focus + qa_hero green. Cache
v52→v53.

## 2026-06-12 — Chrome rationalisation PR-3: How lumi works hub + links + auth footer

MERGED HUB (§4): new /how-lumi-works — one page, three side-tab sections,
stable anchors. §4.1 "How the numbers are calculated" (anchors:
#calculations #who-compared #percentiles #suppression #versioning #sources
#glossary) covers peer-norm construction, the suppression floor, versioning
(2026.1/2026.2 + comparability breaks), data sources and the £ assumptions.
§4.2 "How the co-op works" — give-to-get membership, free-for-participants,
data-sharing-as-aggregates, suppression/ethics, founding membership;
admins get a link to the release console. §4.3 "Legal" — index of six
documents (Terms of Use, Privacy Notice, Cookie Policy, Data Contribution
Terms, DPA, Sub-processor List), each opening a read-only viewer. The
phrase "co-op governance" appears NOWHERE as a heading/label (DOM-verified).
/methodology now 301s to /how-lumi-works/calculations.

TWO SPEC INACCURACIES, corrected truthfully (integrity firewall — a trust
page must never state a false rule):
- The spec's §4.1 says "the n=3 suppression floor". The engine's real floor
  is n=5 (aggregate.py SUPPRESSION_FLOOR = 5). The hub states 5. FLAGGED FOR
  DAVID: if the floor should be 3, that's an engine change, not a copy edit.
- The spec lists a "dominance rule" to document. The engine has NO dominance
  / k-anonymity rule — suppression is solely the n<5 floor. The hub says so
  plainly ("this floor is the single suppression rule") rather than
  inventing one. FLAGGED FOR DAVID: if a dominance rule is wanted, it must be
  built in the engine first.

LEGAL DOCS (§4.3): three new DRAFT documents created to back the index and
the auth footer — privacy-notice, cookie-policy, sub-processors (all
"DRAFT — pending legal review", matching the existing corpus). Server gains
public read-only routes GET /api/legal (index) and GET /api/legal/{key}
(doc text; 404 on unknown). No engine/data-layer change — static text
serving, same shape as the existing /api/terms.

CONTEXTUAL LINKS (§6): §6.1 metric pages + card pop-out link "How this is
calculated" → #/how-lumi-works/calculations; the suppressed metric view and
the percentile note deep-link to #suppression. §6.2 the peer-set note links
"Why?" → #suppression. §6.3 the submit step shows privacy + data-sharing +
co-op links at the point of submission. Deep-link scroll is instant (not
smooth — the methodology tables grow the page mid-animation and a smooth
scroll overshoots) and lands exactly on the anchor (scroll-margin-top 84;
verified top=84).

AUTH ENFORCEABILITY (§4.3): every auth screen carries a footer with Terms
of Use + Privacy Notice links (open the public legal viewer pre-auth);
sign-up adds acceptance copy "By continuing you agree to our Terms of Use
and Privacy Notice". The explicit Platform-Terms tick is unchanged.

Full gate suite green (8/8). Cache v53→v56.

## 2026-06-12 — Chrome rationalisation PR-4: search empty state + fuzzy matching

SEARCH EMPTY STATE (§5): a no-result metric search never dead-ends. Exact
substring hits render as before; when there are none, a typo-tolerant
fuzzy pass suggests near-misses ("Did you mean…"), then a divider, then the
"Request this metric" action (the request flow relocated from the old top
bar in PR-2, prefilled with the typed term and clearing the search).

FUZZY MATCHER: Levenshtein edit distance, token-level. The query is split
into tokens (≥3 chars, stop-words dropped); each query token matches a title
token at similarity ≥ 0.7 (1 − dist/longerLen). Questions ranked by matched-
token count then average similarity, top 3. Verified against the spec's test
terms: "allownace" → three allowance metrics; "pention" → three pension
metrics; "sick" → 6 real substring hits (valid partial, no empty state);
"zzzzq" → no suggestions but still offers Request (never a bare no-result).
~200-question index, all in-browser — instant.

Client-only. Full gate suite green (8/8). Cache v56→v57.

## 2026-06-13 — Overview QA v3 (content + chrome): A2/A4 fixes, B1–B3 chrome, A1/A3/A5/A6 verified

A2 [built] — INDICATIVE-VERDICT CUE NOW ON THE TILE FACE. Wellbeing (0
polarised metrics) and Recognition (1) render an indicative position verdict;
the basis was tooltip-only, so an exported board reader could weight a
1-metric verdict like a 23-metric one. Indicative tiles now show a dashed/
outlined chip (chip-indicative, transparent fill + inset ring) plus a visible
"≈ indicative" tag; strict tiles keep solid filled chips with no tag. Basis
detail stays in the tooltip. Verified: exactly 2 indicative (Wellbeing,
Recognition), 5 strict, no flag on strict.

A4 [verified + gated] — BOARD-PACK EXPORT SUPPRESSION. assemble_pack_payload
builds from the SAME build_items -> position_items path that enforces the
n>=5 floor (suppressed blocks skipped inside position_items), and
gap_register_top already filters `if not r["suppressed"]`. So suppression
carries through structurally. Added two standing assertions to qa_focus so an
export-only regression can never ship a sub-floor figure: every n-bearing pack
item has n>=5, and gap-register rows are all unsuppressed (now 26 checks).
Note: the pack does not surface per-category indicative verdicts at all, so
there is no indicative-mislabelling risk in the export.

B1/B2/B3 [built] — CHROME DEFINITION. The shell was white (--surface) on warm
paper (--paper) — a ~3% lightness gap with a faint border, so rail/top bar
read as undifferentiated. B1: sidebar gains a spine (1px edge + soft warm
shadow, 4px/0.028 alpha) so the white rail lifts off the paper. B2: top bar
keeps its 1px rule and gains a faint sticky-header shadow so content reads as
sliding under it (light, not a band). B3: inactive nav items drop to
--ink-faint, the active pill deepens to --blue-deep with an inset blue ring —
the active state is now a clear step up, not the only signal. Uses the page's
existing soft-warm shadow vocabulary.

A1 [verified] — PARTIAL-UNLOCK OVERVIEW reads as invitation, not wall.
Confirmed via a read-only client shim flipping the demo into the locked state
(no data mutation): the arc + all 7 category tiles SHOW THROUGH (the "where
you sit" answer is given freely; peer-n visible on the arc); only Signals and
Biggest gaps blur, each with reciprocal copy ("complete your key reward
questions (N days left)") + a Submit CTA, led by the "You're on your way…
You see the pool because you're part of it" banner. No paywall language
(buy/pay/upgrade/subscribe/£-per-month) anywhere — asserted in the check.

A3 [verified — already correct] — the in-band position dot takes the tile's
VERDICT colour (below->amber-bright, above->red, at->green), not a constant
amber. The amber only appears on a below tile, where amber IS the verdict.

A5 [verified] — the peer-set selector re-cuts ALL tiles by sector and size
from the overview (24 options: every sector + FTE bands; the global cut
re-fetches /api/overview). Region is not a first-class cut by design — it
feeds the Peer Twin similarity vector; the engine's cuts are
sector/size/twin/group. No regression.

A6 [verified] — Ask lumi inherits the trust rules: analyst_answer runs the
same validation layer as the commentary (suppression handling, DIRECTIVE_RE
refusal, "considerations are OPTIONS never directives", number allow-listing),
refuses to guess on unbenchmarked topics, and _analyst_block passes the
suppressed flag per metric/row. Illustrative-sample labelling is page-level
(the standing chip), not restated per answer.

B4 [NOT BUILT] — collapsible sidebar remains David's call (delivery-audit D5).
If green-lit, the collapsed-state spec must define what happens to the
Benchmark group's persisted expand-state (_nav.benchmark_open) and the
gap-cue dot that rides a category child row — both lose their label anchor
when collapsed.

FLAGGED FOR DAVID (carried): the addendum's "amber = you-marker" rule is
superseded by the traffic-light convention — worth a one-line note back into
the addendum so the documents don't drift. Also still open: the spec's n=3
floor vs the engine's n=5, and the requested "dominance rule" the engine
doesn't implement (both from the PR-3 hub work).

Client + one gate file (qa_focus). No engine/data change. Gate suite green.
Cache v57->v58.

## 2026-06-13 — Nav & chrome package, Item 1: dots removed

TILE LENS-DOTS (1a) removed from CategoryTile + .lens-dot CSS. Chip, top
accent, in-band position dot and the x/y count are untouched. The
signal_lenses payload stays (additive, server-side); only the tile render
stops. The --lens-* tokens and .signal-row.lens-* rules remain — the
Signals panel still uses lens tints.

SIDEBAR GAP-CUE DOT (1b) removed — REVERSES the §0 (2026-06-12) "keep it"
ruling, at David's request. Removed the .gap-cue render in BenchmarkNav, the
amber-dot CSS, AND the whole gapCue computation: nothing else consumed it
(the on-load /api/gap-register fetch existed solely to feed the dot; the
Priorities page fetches the register independently). A live calculation
feeding nothing is worse than the dot. The "biggest opportunity area"
information is not lost — it still lives in the Overview Biggest-gaps panel
and on Priorities; only the at-a-glance nav cue is gone. Do not restore it
as a "leftover" — its removal is deliberate.

No qa_hero assertion referenced the lens-dots or gap-cue (the "category dots
in [1,99]" check is the in-band position dot, d.dot, which stays). Client-
only. qa_focus 26/26, qa_hero 42/42. Cache v58->v59.

## 2026-06-13 — Nav & chrome package, Item 2: real chrome borders

The 2026-06-13 soft-shadow chrome treatment was found TOO QUIET on warm
paper and is deliberately replaced with real borders (not a regression —
the diagnosis was right, the treatment under-powered). Root cause: --border
#EAE5DE sits ~3% off both the white rail (#FFFFFF) and the paper body
(#FBF9F6) — invisible against both. New token --chrome-edge #D4CCC0 carries
real contrast against both surfaces. 2a: the sidebar's 1px right-border is
now the PRIMARY separation cue (soft shadow demoted to secondary). 2b: the
top bar's 1px bottom-border is the primary cue, sticky scroll-shadow
secondary; no height added (PR-2 slimming respected, top bar stays 53px).
2c: nav hierarchy unchanged from the QA-v3 pass — active = blue-deep + inset
ring, inactive = --ink-faint, "YOUR ORGANISATION" label kept. Client-only.
qa_focus 26/26, qa_hero 42/42. Cache v59->v60.

## 2026-06-13 — Nav & chrome package, Item 3: collapsible sidebar (D5 built)

D5 COLLAPSIBLE SIDEBAR — was "flagged, NOT built, needs David's direction";
now greenlit and built. A toggle by the wordmark switches the rail between
full-width (224px, labels) and an icon-only rail (66px). State persists per
user in the prefs store at _nav.sidebar_collapsed (sibling to
benchmark_open); default expanded; the manual choice is authoritative — no
resize override (the existing <900px media query still hides the rail on
mobile, unchanged). Verified: toggle flips aria-expanded + accessible label
("Collapse sidebar"/"Expand sidebar"), collapse persists across reload past
the prefs debounce.

COLLAPSED APPEARANCE: nav items refactored into a RailItem helper (icon +
.nav-txt label + optional count) so collapse hides labels/counts uniformly;
every collapsed item carries aria-label (accessible name kept) AND a
hover+focus-visible CSS tooltip with the full label/count (the accessibility
requirement). Wordmark degrades to the "lumi" glyph (".benchmark" hidden).
Active state stays legible icon-only (the blue pill + inset ring render on
the active icon). Width transition is one ease-out, disabled under
prefers-reduced-motion.

BENCHMARK GROUP COLLAPSED = FLYOUT (the chosen option, not auto-expand):
the icon-only rail can't hold the eight-child list, so clicking the
Benchmark icon opens a popover beside the rail with All + the 7 categories
and their counts; closes on click-away/Escape; navigating a category closes
it. No child is ever dropped — all eight reachable. Verified on-screen
(left:67px at the rail edge, 8 items, z-index 60) and functional (navigates
to /benchmark?cat=…).

GAP-CUE DOT (3d): confirmed absent — removed in Item 1b, so no collapsed-mode
dot handling was needed.

Client-only (web/js, web/css, html). Full gate suite green (8/8). Cache
v60->v61.

## 2026-06-13 — Nav & chrome package: ship summary

Three approved items shipped in sequence, each gate-green individually:
Item 1 (b4525ac) tile lens-dots + sidebar gap-cue dot removed; Item 2
(5406048) real --chrome-edge borders replacing the too-quiet soft shadows;
Item 3 collapsible sidebar with Benchmark flyout. No server/engine/catalogue/
seed file touched (grep-confirmed; the only server-side line in the window is
the QA-v3 board-pack suppression assertion in qa_focus, which predates this
package). The "biggest opportunity area" cue the gap-cue dot carried is not
lost — it lives in the Overview Biggest-gaps panel and on Priorities.

## 2026-06-13 — Hero verdict: meaning + threshold (Part 1)

VERDICT NOW READS WHERE THE MASS SITS, gated against contradiction. Tracing
showed the word and the 34/46/14 counts already came from ONE function
(_pool_verdict) — the earlier "median vs per-metric" theory was wrong. The
real defect was the THRESHOLD: net lean (above-below)/pool = -0.21 crossed the
old ±0.15 margin and read "Below" despite the plurality (46) being on-market.
David chose Option 1 (net balance, wider band) over plurality, because the
SAME net-lean value drives both the verdict word and the gauge needle — so
they can never disagree (the original two-measures-in-one-component bug),
whereas plurality reintroduces it on bimodal orgs (50/10/40 would read "Below"
on 10 metrics and force a separate needle). New env var
LUMI_VERDICT_NET_LEAN, default 0.25 (was 0.15); _pool_verdict now also ships
`lean` (-1..1) and `lean_threshold`. This changes the headline's MEANING from
the old net-share read to a wider centre-of-gravity read — logged so nobody
asks "why doesn't this match the median?". The seven category tiles use the
SAME _pool_verdict, so overall and tiles stay consistent (no median-vs-mass
split). FLAG FOR DAVID: at 0.25 the demo org sits at lean -0.213, i.e. just
0.037 of headroom before it flips to "Below" — tight. Raise
LUMI_VERDICT_NET_LEAN if he wants more cushion; lower it if too many orgs read
"On market". F2 GATE (qa_hero, now 46 checks): verdict can never be "below"
when below is the strict smallest count (nor "above" when above is smallest),
and the shipped verdict must band the shipped lean — so word and needle agree
by construction can't silently regress.

## 2026-06-13 — Hero gauge rebuilt as a needle instrument (Part 2)

The three-fat-segments gauge is replaced by a precise instrument: a quiet
desaturated three-band scale (~9px, --gauge-below/on/above) is the backdrop;
a single tapered needle pivots from a clean base hub (white ring + centre
dot, the stray second ring removed) with a tip marker. The needle ANGLE is
data-driven from market.lean — rot = (frac-0.5)*180, frac=(lean+1)/2 — and
the band joins sit at ±lean_threshold, so the band the needle rests in IS the
verdict (word + needle reference one value). Band-join ticks mark the
thresholds. The verdict word ("On market") sits contained below the arc in
the head face with tight letterspacing + a tertiary caption "across N metrics
assessed" (honest — never "On market on 46 metrics", which would falsely
equate the verdict with a count). Counts moved to a hairline legend. Defined
header (compass icon + label + divider). Real traffic-light palette on warm
paper; sunk track + inner top highlight re-applied (aurora wash lives on the
ov-wrap). Needle settle transition disabled under prefers-reduced-motion.

## 2026-06-13 — Terminology: middle verdict "at market" → "on market" (Part 3)

The middle market-position state reads "on market" everywhere, applied with
the gauge rebuild so no surface drifts. DISPLAY strings changed: hero verdict
word, hero legend, the seven category tile chips, and MARKET_LABEL (the
metric market badge). The INTERNAL enum value stays "at" (verdict key,
_market_class return, _pool_verdict 'at' count) to avoid churn — only
user-facing text changed. The board pack uses separate "broadly in line"
phrasing and carries no literal "at market", so it needed no change. qa_hero
wording assertions updated ("on-market"). grep confirms no user-facing "at
market" remains; code comments and the "at" enum are intentionally left.

## 2026-06-13 — Hero polish: premium gauge animation + Signals box fill

GAUGE — now a live instrument. On mount (and on every cut change) the needle
SWEEPS from straight-up to its data angle with a spring settle
(cubic-bezier(.34,1.45,.5,1), slight overshoot) — driven by a shownRot state
that paints at 0 then animates to lean*90 (hooks moved above the early return
so order stays stable when market is null). The three bands DRAW IN staggered
(stroke-dashoffset), the legend figures and the "94" caption COUNT UP, and the
needle tip carries a soft infinite pulse (.arc-tip-glow) so the gauge feels
alive. All disabled under prefers-reduced-motion (needle lands directly, glow
hidden, draws skipped).

SIGNALS BOX — empty space removed. The card is now a flex column that fills its
grid cell: a header matching the gauge's (.card-head — flag icon + "Signals · N"
+ a right-aligned "flags worth a look — peer facts, never advice" note +
hairline divider), the rows centred to fill the available height, and a footer
under a hairline ("Tap a flag to open the metric behind it." + a "See all
priorities →" link). The two hero cards now read as a matched pair with the
same header language, no empty bottom third. Empty + locked states reuse the
same fill (centred ring / lock note). Client-only. qa_hero 46/46, qa_focus
26/26. Cache v62->v63.

## 2026-06-13 — Hero gauge: presence + precision pass

Acting on David's "could it be wider / what else" — a research-led pass toward
a premium instrument (reference: speedometer / fintech dial language). Four
changes, client-only: (1) WIDER — the gauge column goes 264px -> 312px and the
arc max-width 270 -> 300, so the instrument has presence as the hero's
headline answer. (2) MINOR GRADUATIONS — ~21 quiet inner tick marks (every
4th longer) around the arc, the precision-instrument cue, fading in after the
bands draw. (3) ACTIVE-ZONE EMPHASIS — the band the needle rests in renders
RICHER (a ~66% hue mix in the verdict colour) while the dormant zones stay
muted, so the eye lands on the answer; the active band always matches the
verdict (below->amber, on->green, above->red). (4) NEEDLE DEPTH — a soft SVG
drop shadow (feDropShadow) under the needle blade for a machined-instrument
feel. All new motion is reduced-motion safe. qa_hero 46/46, qa_focus 26/26.
Cache v63->v64.

## 2026-06-13 — Hero gauge: median marker, sheen, lean label, heavier dial

Per David — shipped the three held-back ideas plus a wider/heavier dial.
(1) PEER-MEDIAN MARKER: a small "MEDIAN" caret at the arc's top centre (frac
0.5 = net lean 0 = the market middle), making "you vs the median" explicit —
the needle sitting left of it shows the below-lean at a glance. (2) RADIAL
SHEEN: a soft white radial gradient (#dialSheen) washes the dial face for
quiet dimensionality. (3) LEAN SUB-LABEL: a one-line descriptor under the
verdict turning the tilt into words — for the demo "slightly below-leaning"
(verdict On market, lean -0.21); below/above verdicts read
"marginally/moderately/clearly below|above the market" by distance past the
threshold; a near-zero lean reads "evenly balanced". (4) HEAVIER + WIDER:
column 312->356px, arc max-width 300->334, stroke 9->13, hub/needle thicker,
verdict word 26->30px/650. All new motion reduced-motion safe; the median
marker rides the entrance. qa_hero 46/46, qa_focus 26/26. Cache v64->v65.

## 2026-06-13 — Hero tidy: drop metrics caption + MEDIAN label, fill Signals

Per David: removed the "across N metrics assessed" caption under the verdict
and the "MEDIAN" word above the gauge (the caret stays, with a <title> for
a11y/hover). The taller dial had stretched the height-matched Signals card,
reopening a gap — the signal rows now distribute space-evenly to fill the box
(footer moved to a sibling of the list so it anchors the bottom; rows a touch
taller). The two hero cards stay a balanced matched pair. Client-only.
qa_hero 46/46. Cache v65->v66.

## 2026-06-13 — Hero delight: ambient aurora drift + cursor spotlight

Two restrained premium touches (the entrance choreography, count-ups and
needle sweep already exist; this adds AMBIENT life, not more entrance motion).
(1) AURORA DRIFT — the hero's background aurora wash now breathes very slowly
(24s alternate, ~14px/scale 1.05), a living-dashboard feel; off under
prefers-reduced-motion. (2) CURSOR SPOTLIGHT — a faint brand-blue radial (8%)
follows the pointer across the two hero cards (gauge + signals), the tactile
"alive" feel premium products use. Implemented as a .card-spot overlay behind
content (z-index 0; card content lifted to z-index 1 so text stays crisp),
positioned via direct DOM writes on mousemove (no React re-render). Verified
content legibility unaffected. CountUp already eases out (cubic) — left as is.
Client-only. qa_hero 46/46. Cache v66->v67.

## 2026-06-13 — Bug fix: metric page ignored the selected sector

REPORTED: on a metric detail page, changing the sector left the data
unchanged. ROOT CAUSE (frontend, not the engine — the API returns correct
per-sector data): MetricPage.globalSel mapped any `industry` cut to
`org.industry` (the org's OWN sector) instead of `cut.value` (the selected
one), so picking "Construction" globally still refetched the org's "Retail".
Same latent bug for fte_band; group value was dropped entirely. FIX:
globalSel now preserves cut.value for industry/fte_band/group. Also enriched
the per-metric peer dropdown: it now reflects the active sector/size even
when it isn't the org's own, and offers a "Compare a sector" / "Compare a
size band" list (from cuts.industries / cuts.fte_bands) so a sector can be
explored from the page itself. Verified: Retail n=15 (26.7/80/40) vs All
peers n=220 (45.5/41.4/32.3) now switch correctly. Client-only. qa_focus
26/26. Cache v67->v68.

## 2026-06-13 — Cut-resolution debug sweep (does the bug appear elsewhere?)

Triggered by the metric-page sector bug. Audited both layers; the bug was
ISOLATED to MetricPage and is fixed — it does not recur anywhere else.

FRONT END — grepped every cut-resolution path: the global peer-set selector
(passes cut.value), the card kebab override (passes override.split("::")
verbatim), and cutLabelOf (label-only org fallback, not a data cut) are all
correct. Only MetricPage.globalSel re-derived the value from org.* — fixed.

ENGINE — wrote a sweep over ALL 206 active metrics across the top 6 sectors +
top 4 size bands: 0 "cut-ignored" (no metric returns the all-peers block under
a cut label — resolve_block returns None/suppressed when a cut value is
absent, so there is no silent all-peers fallback) and 0 "never-cuttable".

FULL HTTP STACK — probed one metric of EACH type through /api/benchmark across
all-peers vs two sectors: numeric (p50 37->21->20), single_select, yes_no,
multi_select and matrix all change distribution + n correctly. Cut-sensitive
end to end for every type.

REGRESSION GATE — added two assertions to qa_focus (now 28): the metric
endpoint must apply a sector cut (n differs from all-peers) and must label the
cut it actually used (no all-peers fallback), so an engine-side regression of
this class can't ship silently. Client+gate only.

## 2026-06-13 — Metric page: stale-card guard (peer-set/graph can't disagree)

Follow-up to the sector-cut fix. A screenshot showed the metric dropdown on
"Logistics" while the graph still read "All peers · n=220". The server is
correct (Logistics returns n=15) and the current build reproduces correctly
in every sequence tested — the symptom is consistent with a STALE BROWSER
CACHE running pre-fix JS. To make the contradiction impossible regardless of
cache or any future regression: MetricPage now refuses to render a card whose
cut doesn't match the active selection — if card.cut != sel (stale during a
refetch, or otherwise), it shows the loading skeleton instead of data under
the wrong peer-set label. Verified across all cut kinds (all/industry/
fte_band/twin/group — card.cut carries dim+value for each, so no false
"stale" positives). The dropdown and graph can no longer disagree. Client-
only. qa_focus 28/28. Cache v68->v69 (forces fresh JS on next load).

## 2026-06-13 — Evidenced baseline recalibration (5 metrics re-seeded)

The research register evidenced five seeded baselines as needing correction.
Authored server/regen_question.py — a parameterised single-question re-seed to
the regen_allowances_pensionable.py discipline: DRY-RUN default, double-guarded
(--write AND --confirmed-by-david), append-only history (DELETE from `answers`
snapshot 1 only; re-INSERT into answers + answers_history), no auto-aggregate.
It REUSES the original seed pipelines (no reinvented calibration): 4 metrics via
apply_seed_2026_1_additions + seed_release_2026_1_additions (remap_labels →
build_orgs → S.calibrate → compensate → S.generate); SALHISTORY via
apply_seed_2026_2 + seed_release_2026_2. Targets are read LIVE from the seed
modules (recalibrated copies deployed first; md5 9d3cbb… verified on path).

Corrections (live realised now, all within ~3pp of signed, modals intact):
  REW26_WEL_EAP          Yes 78.6% -> 41.8%  (target 0.41)
  REW26_WEL_FINWELL      Yes 32.7% -> 64.1%  (target 0.64)
  REW26_WEL_MH_SUPPORT   Counselling ->44.5 / Mgr-training ->28.6 / None ->11.4
                         (held: 1st-aiders 53.6, app 38.6, MH-days 14.1) — live labels via remap_labels()
  REW26_GOV_EU_PTD_PREP  Compliant 3.2% -> 1.8%  (target 0.02)
  REW262_GOV_SALHISTORY  Yes 34.1% -> 28.2%  (target 0.27)

Integrity proof (backup-independent): answers_history +1100 rows = exactly
5×220, ALL on the 5 ids (newest write window), none elsewhere; answers(snap1)
total unchanged (203,134); REW262_GOV_ACTIONPLAN control UNCHANGED (dist hash
877a849b87, history 220) despite being touched in-memory by the 2026.2
calibration pass. benchmark_snapshots refreshed via aggregate.py (806 payloads,
computed_at 10:59:30); preview restarted so the API serves the corrected
distributions. NOT changed: PEN_TYPE and all corroborated metrics.

OPERATIONAL CAVEAT: the `cp lumi.db` backups are WAL-incomplete (no -wal
captured), so a backup can lag the live committed state — a comparison against
one will show spurious diffs, and a rollback from one may restore a slightly
stale state. For a clean rollback take `PRAGMA wal_checkpoint(TRUNCATE)` (or
copy -wal/-shm too) before the cp. The write here is verified correct via the
append-only ledger, so no rollback is needed.

## 2026-06-13 — Fix: matrix-select cards overflowed / collided with neighbours

A Yes/No matrix card (e.g. "Allowances pensionability by level", REW_PAY_020)
visually overlapped the cards around it. Root cause: `.bench-chart-full` has a
FIXED `height: var(--chart-h-stack, 200px)` with `justify-content: center`, and
only `svg` carries `max-height: 100%`. MatrixSelect renders a `<table>` (not an
svg), so the table got no height constraint — it rendered at full height,
centred in the 200px box, and SPILLED out top and bottom into adjacent grid
cells (measured +99–121px of overflow). Fix (CSS-only): `.bench-chart-full:has(table)
{ height:auto; justify-content:flex-start; }` — a card whose chart region is a
table grows to fit it (the grid pair stretches to match, n stays pinned to the
bottom); svg charts keep the fixed 200px region. Verified live: 0 of 45 cards
on the Pay page overflow (was 1, +99px). Client-only. qa_focus 28/28. v69->v70.

## 2026-06-13 — Categorical matrix: replace stacked split with a prevalence heatmap
The per-level "peer split" stacked bar (MatrixSelect) was illegible — twice
reported as "just 100% blue for each". A 7-band single-hue stacked bar of
near-identical blues can't carry an ordered distribution, even with separators
and a legend (tried first: band-consistent colour via topological band order +
a generated ramp + segment separators; still muddy). Replaced the whole display
with a PREVALENCE HEATMAP: levels are rows, the ordered answer bands are aligned
columns, each cell's single-hue intensity = how common that band is at that
level (scaled to the busiest cell anywhere in the matrix). The exact % sits in
every cell; the most-common cell per row is ringed; the org's own band is
outlined and repeated in a right-hand "You" column. Aligned columns make the
shape of the market legible at a glance — e.g. notice period lengthening up the
seniority ladder reads as a diagonal staircase. Band order recovered by a
topological merge over each row's consecutive option pairs (rows hold only the
bands they use, in column order), so 1 week → … → More than 16 weeks regardless
of which row leads; falls back to first-seen if the data has no clean order.
Time-unit column heads abbreviated (8 weeks → 8 wk, More than 16 → >16 wk),
full label on hover. Long level labels wrap (max-width 130px) and the table
sits in an overflow-x:auto wrapper, so nothing clips on narrow cards. Client
-only (web/js/card.js MatrixSelect, web/css/app.css). Verified live on
"Employee notice period by level": table fits the 620px column, You column
intact, no console errors. v70->v74.

## 2026-06-13 — Matrix heatmap: polish pass
Polished the prevalence heatmap (still the same display, refined throughout):
- OPAQUE cells (white→brand-blue mix by prevalence) instead of an alpha wash,
  so a cell's shade never shifts with row striping — darkness is one honest
  scale across the whole grid.
- Light axis-style header (small uppercase, letter-spaced, bottom-aligned)
  replacing the heavy navy `.data` thead; dropped the `.data` class entirely.
- table-layout:fixed → perfectly even band columns (Level 124px, You 54px,
  bands share the rest); rounded integer % (48% not 48.2%, <1% floor).
- Empty cells: a quiet hatched neutral fill instead of a stray "·".
- "you" marker: --you is the brand blue, which vanishes on a blue field, so
  the cell ring is a white halo inside a deep-blue ring — reads on every shade
  (pale or dark) while staying in the blue identity family. The You column
  value is --blue-deep bold. "most common" stays a subtle dark hairline + bold.
- Scale legend: a gradient bar (fewer→more peers) + most-common + your-org
  swatches, on a top-ruled footer.
Verified live on "Employee notice period by level": markers land on the
correct cells (incl. the Manager case where you=8wk diverges from the market
mode 4wk=80%), table fits the 620px column, no console errors. Client-only.
v74->v76.

## 2026-06-13 — Chart audit & polish pass (every chart type)
Surveyed all chart components live (PercentileBand, Histogram, BoxPlot,
OptionBars, OrderedDist, MatrixHeat, MatrixGrouped, MatrixSelect, QuartileDots)
against colour / spacing / fonts / chart-fit / number-sanity. Fixes applied:

1. CHART BANDS were warm greys on warm paper — the P25–P75 interquartile band
   (the most important element) was invisible, and histogram/grouped bars read
   tan-on-tan. Retuned the two chart tokens to COOL greys with a clear two-step:
   --chart-band #E7E4EC (P10–P90 outer), --chart-band-mid #BFC6D6 (P25–P75 /
   histogram / peer bars). Data stays quiet and neutral; "you" is still the only
   saturated accent. One token change fixes PercentileBand, BoxPlot, Histogram
   and MatrixGrouped at once. (chart-band was an alias of --surface-sunk; gave it
   its own value so surfaces/heatmap-empty cells are untouched.)
2. HISTOGRAM had no median reference — added a dashed P50 line + label so the
   distribution has a centre to read "you" against.
3. OPTIONBARS multi-select: the card verdict (pos.kind) was painted onto the
   chosen *category* bar, so a nominal pick (e.g. "Mobile/phone allowance")
   showed RED as if that allowance were "bad". A pick-list has no good/bad per
   category (pick three and all three would go red). Now multi_select bars use
   the neutral --you accent; performance colour stays on single_select/yes_no
   and the numeric charts where a position is genuinely ordinal.
4. MatrixHeat column headers 8.5px -> 9.5px (were uncomfortably small).

Verified live on representative metrics; qa_focus 28/28; no console errors.
v78 -> v79.

FLAGGED FOR DAVID (not changed here):
- MatrixHeat (numeric matrices) is an SVG-rendered 3-column table (peer P50 /
  you / percentile) — functional but the least polished surface; a future
  HTML rewrite (like the MatrixSelect heatmap) would bring it to parity.
- ALLOW_01 and likely other nominal multi_selects carry polarity
  "higher_is_better" in seed data, which is meaningless for a pick-list. The
  client now ignores it for colour, but the polarity flag itself is a data
  question (firewall — not touched).

## 2026-06-13 — MatrixHeat rewritten: numeric per-level distribution strip (HTML)
The numeric-matrix "Heatmap" was an SVG 3-column table (peer P50 / you /
percentile) that threw away the per-level quartile spread the engine already
computes. Replaced it with an HTML per-level DISTRIBUTION STRIP, parity with the
categorical heatmap:
- columns: Level | Median | "Where peers sit · you" (the strip) | You | Position
- the strip draws the peer middle-50% (P25–P75) band + median tick + the org's
  diamond marker, all on ONE shared scale across rows, so levels are directly
  comparable (pay rising up the ladder / allowance magnitudes read at a glance).
- the "you" diamond is polarity-coloured (good/bad) where polarity applies,
  plain blue when neutral — same semantic discipline as before; the You value
  text matches.
- precise numbers retained (median, you, percentile); a legend + absolute scale
  range (£lo–£hi) anchor the visual. Equal 42px rows, tokenised type, ruled
  table, overflow-x safe; suppressed rows show the safe-data message.
- toggle label "Heatmap" -> "Distribution" (CHART_LABELS) since it's no longer a
  heatmap. Chart key stays "heatmap"; "Grouped bars" alt unchanged.
Verified live on an answered matrix (allowance payments — shared scale shows
London weighting highest, you above median on Night/Weekend, below on Bank
holiday) and an unanswered one (market-position 99% — now shows peer spread, not
"99% — —"). No console errors.
NOTE: like the categorical heatmap, the HTML matrix can't PNG-export (exporter
finds no <svg>); export silently no-ops for matrix cards. Flagged.
v79 -> v82.

## 2026-06-13 — All charts exportable: SVG export twins for the HTML matrices
The two matrix charts render as HTML (no <svg>), so the PNG exporter — which
serialises an SVG to canvas — silently no-op'd on them. Now EVERY chart exports:
- buildMatrixSVG(card) rebuilds an equivalent SVG from the SAME card data for
  both matrix kinds (categorical heatmap, numeric distribution strip), using the
  live theme tokens for colour. matrixBandOrder() is extracted and SHARED by the
  on-screen MatrixSelect and the export twin, so screen and export can't drift.
- exportCardPNG now (a) scopes the chart-svg lookup to the chart container
  (.bench-chart-full / .metric-xl) so it can never grab a kebab/status icon —
  a latent bug; (b) rebuilds the SVG from meta.card when the card is a matrix;
  (c) sets font-family on the chart <g> so exported labels render in the brand
  sans, not the SVG default serif (fixes ALL chart exports, not just matrices).
- both doExport call sites (card kebab, metric detail) pass card:c in meta.
Verified live: categorical (630×238) and numeric (638×380) twins rasterise to
non-blank PNGs and the full exportCardPNG returns "downloaded" with a valid
data:image/png for both; existing SVG charts still export; screen heatmap
unchanged after the matrixBandOrder refactor; no console errors. v82 -> v83.

## 2026-06-13 — Submission design QA: light table header + help-text content fixes
Deep design QA of the data-submission flow (home, all six input types, warn
state, review/submit, gates, desktop+mobile). The flow itself is strong
(warn-never-block, units-in-field, N/A first-class, autosave, key/optional
split). Two fixes shipped:
1) TABLE HEADER (client): the .data table header was a heavy navy bar; stacked
   through a long entry form it read like a database export. Replaced GLOBALLY
   (David's call) with a light small-caps header on a bottom rule — one table
   language across submission, my-data, pulses, admin, commercial. v83->v84.
2) HELP-TEXT CONTENT (metadata, server/fix_help_text.py, backed up first):
   18 questions carried help that contradicted their input type —
   • the £-entry matrix "Total annual payment for each allowance" said "Select
     the option that best describes…"; now "Enter the typical total annual
     amount paid for each allowance (£). Leave a row blank where you don't
     offer it."
   • 17 four-option practice questions (Yes / No / partial-or-ad-hoc / Don't
     know) still said "Select Yes or No."; now "Select the option that best
     describes your organisation."
   Metadata only (questions.help_text) — answers/aggregates untouched, no
   re-aggregation. Server caches question metadata at startup, so a restart was
   required for the API to serve the corrected text (verified live).
FLAGGED (not changed): the matrix-row soft-warning renders inside the table
cell so the amber box looks untethered mid-grid; and some "What counts?"
definitions still just restate the title (a content-authoring pass, not a QA
fix).

## 2026-06-13 — Submission matrix: soft-warning moved to its own row
The per-row soft-warning/error rendered inside the narrow value cell, so the
amber box read as an untethered floating panel. Now each flagged row emits a
second full-width row (colspan) directly beneath, attached to the row above
(no divider between them) — the warn panel + "keep it" affordance span the
table cleanly. Zebra striping dropped on the matrix entry grid (table.matrix-
grid override, specificity-matched) so the inserted note row can't flip the
nth-child stripe parity below it; row borders separate cleanly on their own.
Verified live (outlier on a £ cell → full-width amber row, rows below intact);
no console errors; draft left clean. v84 -> v86.

## 2026-06-13 — Signals Phase 1 SHIPPED (config-only, 25 → 108 live mappings)
Replaced data/signal_lenses.json with signal_lenses_PHASE1.json (hot-reload, no
restart). Adds to position_lenses + prevalence_lenses using the existing behind
+ prevalence engine logic. Validated before swap: all IDs resolve to active
questions; no cross-bucket collisions (position ∩ prevalence empty; money ∩
position = the pension metric, deduped by build_signals); lenses valid; the 3
anchor-risk ordered IDs (REW_Q049530, REW_PAY_003, PROP_8e0b6316) correctly
ABSENT.
Live eyeball (Thornbridge demo, caps lifted): 27→26 signals fire. Static audit
of every position_lenses choice metric's score ladder found ONE backwards case:
  • REW_BEN_SICK_001 — score_answer ranks "Statutory sick pay only"=100 ABOVE
    "Enhanced occupational sick pay"(66) and "Combination of enhanced+SSP"(33).
    The org's generous sick pay reads as 'behind'. Root cause is the question's
    option order/scoring (firewall data — affects its percentile everywhere),
    not the lens. HELD: removed from position_lenses in both configs, logged
    under _held_pending_data_fix. Re-add once the score ladder is corrected.
The other 6 neutral-polarity entries in position_lenses (market position, the
two bonus matrices, pension %/cost-share, salary budget) do NOT fire behind
(engine requires favourable==bad) — held for the Phase-2 ordered-outlier path,
harmless meanwhile.
qa_hero: added a static assertion that the 3 anchor-risk IDs stay out of
position_lenses (47/47, was 46). The existing "no behind on neutral" check
already passes.
NOT BLOCKING: server/qa_phase1.py (handoff gate) crashes on a 404 — it targets
PROP_9620d380 (Processes, status=proposed) and MET_cd8efe96 (Attract), both
outside the reward-only launch scope, so they 404 for the demo org. Pre-existing
scope incompatibility, unrelated to Signals; the engine math it did reach
(PROP_9e4ad87f percentiles) passed.
FLAGS FOR DAVID: (a) fix REW_BEN_SICK_001 option order/scoring, then re-add to
position_lenses; (b) lens framing — "Relocation support" and "EV charging
reimbursement" fire behind under the 'save' lens (save reads as overspend, but
behind here = you provide less) — review; (c) behind label "0/100 vs median"
reads cryptically for ordered scores — Phase-2 label polish; (d) all lens
assignments remain his to ratify. Phase 2/3 unbuilt per plan.

## 2026-06-13 — Score-ladder integrity guard (durable fix for the sick-pay fault class)
Follow-on to the Phase-1 sick-pay catch. Root cause: the engine derives each
option's maturity score + direction (aggregate.py score_direction) from option
labels + polarity; a metric only scores right if its option array is ordered
consistently with that direction. When it isn't, a clearly-bad answer can
outscore a clearly-good one and any signal reading that ladder fires BACKWARDS
silently. option-array order is load-bearing with no guard.
Built server/qa_scores.py — a standing gate that sweeps all 144 reward scored
single_select/yes_no metrics and FAILS when a clearly-negative option (No/None/
Not/"statutory only"/absence, via the engine's own _NEG regex) outscores a
clearly-affirmative one (_AFF), direction-corrected. It is a RATCHET: known
faults are allow-listed with reason+fix; the gate fails on any NEW backwards
ladder and on a stale allow-list entry (fixed metric still listed). It also
asserts the 3 verified best->worst metrics resolve correctly. Pure library/
aggregate, no server.
The automated sweep caught TWO faults the human 131-metric audit missed:
  • REW_FAI_079 (conduct gender pay gap analysis annually?) — polarity=
    lower_is_better is wrong; "Yes" scores 0, "In development" 100.
  • REW_INC_070 (malus provisions used?) — same; "Yes" scores 0, "No" 100.
BLAST RADIUS determined: both are in prevalence_lenses, where the signal is
SAFE — practice_status is label-based (is_absence_label), so "Yes"->in_place is
correct and prevalence fires right. The wrong polarity only corrupts their CARD
percentile / maturity (a pre-existing app-wide bug) and would break Phase 2
ordered signals. Neither is in position_lenses, so NO new Phase-1 hold is
needed; REW_BEN_SICK_001 stays held.
Gate result: 3/3 pass (3 known faults allow-listed, 3 best->worst confirmed).
FOR DAVID (data fixes, firewall — change computed positions, need sign-off):
  1. REW_BEN_SICK_001: reorder options worst->best, then unblock from position_lenses.
  2. REW_FAI_079 + REW_INC_070: polarity lower_is_better -> higher_is_better.
  3. Ratify the principle: explicit per-metric direction, no index inference — I
     can build the explicit-direction field + an "every ordered metric has one"
     assertion once ratified. qa_scores.py is the interim enforcement.
PREREQUISITE for Phase 2 (its ordered mechanisms read these same ladders).

## 2026-06-13 — Signals Phase 2 PREREQUISITE: explicit ordered-scale routing (no index inference)
Per David's steer: explicit direction lives in a routing JSON, scoped to the
signals/ordered-outlier path — NO engine-global DB write (that ~60-percentile
firewall change is its own baselined tracked change, not part of a signals
build). The Phase-2 mechanism spec/routing handoff docs were absent, so this is
authored from the brief and flagged for David's review on the judgment calls.
Built ordered_scale_routing.json (David-owned, hot-reloads): every ordered
metric gets an EXPLICIT scale_low_to_high (real option labels ordered by
magnitude) so the new mechanism reads the org's ordinal from an authored scale,
never from option-array index. Split:
  • ordered_outlier: 20 metrics, each with explicit magnitude scale + NA list +
    lens RECOMMENDATION (David ratifies). "Not offered"/"None" floors placed at
    the LOW end (a genuine outlier), true NA/Don't-know excluded.
  • anchor_risk: 3 (REW_Q049530 lower_is_better; REW_PAY_003 + PROP_8e0b6316
    higher_is_better) — resolved with explicit direction + scale, PARKED (not in
    any firing set; David routes them to behind or ordered_outlier).
  • review_reroute: 2 HELD as non-ordinal — REW_PRO_035 (nominal: performance vs
    tenure, no high/low end) and REW_PAY_TIPS_EXIST (binary -> Phase 3
    prevalence). They must not fire as outliers.
Validator qa_ordered_routing.py (11/11): every scale label matches a real
option (no typos), every non-NA option is placed (nothing silently dropped),
>=3 points per scale, anchor-risk carry explicit direction and stay out of the
firing set, every brief id is homed. This IS the "explicit direction, no index
inference" assertion.
REW_BEN_SICK_001 stays HELD (its scoring fix is a firewall DB change, deferred
to the separate global-direction work — not folded into signals). qa_scores
still green.
NEXT (not built this turn): Mechanism A (ordered-outlier firing: ordinal
percentile from the explicit scale, both tails, noise gate, n>=5, conditional
cohort for REW_BEN_047/048) and Mechanism B (depth-of-provision matrices) — now
on a validated explicit-direction footing.
FOR DAVID: ratify the 20 lens recommendations; confirm the 2 re-routes; decide
where the 3 parked anchor-risk metrics fire; sanity-check the NA classifications
and the REW_INC_061 data flag.

## 2026-06-13 — Signals Phase 2 Mechanism A: ordered-outlier (BUILT + verified)
Built against David's ratified routing. Reconciled ordered_scale_routing.json
to the ratifications: ordered_outlier = 22 (20 validated + REW_PAY_003 +
PROP_8e0b6316 unparked); REW_Q049530 -> behind_explicit (lower_is_better);
REW_PRO_035 + REW_PAY_TIPS_EXIST re-routed to Phase 3 (held out); anchor_risk
emptied. Re-added explicit `scales` (David's edit had stripped them) and FIXED
EXT_REW_GAP_003 per his recheck ("No limits" = generous top end, not floor).
Mechanism A (signals.py): a hot-reloaded routing loader + _ordinal_stats —
the org's ordinal comes from the EXPLICIT scale_low_to_high (never option-array
index). Fires at BOTH tails with NO verdict ("X sits at the top/bottom end —
band; peer median band"). Noise gate: modal_share>=0.35 (a discernible norm
exists) AND org_band_share<0.50 (org isn't itself the norm) AND tail_pct<=20.
n>=5 on the placed (on-scale) cohort — which for income-protection terms
(047/048) naturally scopes to the offering cohort since their NA is excluded
from the scale (David's carve-out (b)).
VERIFIED on Thornbridge (caps lifted): 6 ordered-outlier fire, all correct and
verdict-free. Notably PROP_8e0b6316 (the ex-anchor-risk metric) fired CORRECTLY
("Pay review cycle at the top end — Quarterly; peer median Annually") via the
explicit scale — the index path would have flipped it. REW_BEN_045 reproduced
the brief's textbook case ("Life assurance cover at the top end — 4x; peer
median 1x"). Gates: qa_ordered_routing 10/10, qa_scores 3/3, qa_hero 50/50 (+3:
no outlier verdict word; every outlier off an explicit scale; re-routes never
fire). Dashboard renders, capped, no verdicts, no console errors.
FLAG (David's call): outliers DON'T reach Thornbridge's capped top-5 — behind
impact (100k) out-ranks outlier (30k) and there are enough behinds to fill the
5 slots. They fire (uncapped) and surface for behind-light orgs, but to put the
new mechanism in front of behind-heavy orgs the briefing cap needs kind/lens
diversity (round-robin or per-kind cap), not pure impact tiering. Not changed
unilaterally — it alters the Phase-1 briefing balance David owns.
DEFERRED to the next pass (foundation now in place): Mechanism B (depth-of-
provision matrices, 5), behind_explicit firing for REW_Q049530 (directed bad-
tail), and the presence->prevalence half of the 047/048 carve-out (a
prevalence_lenses add).

## 2026-06-13 — Signals Phase 2 cont. (1/2): briefing cap + threshold confirm
Re-materialised the reconciled routing (David's working-tree edit had reverted
scales/lists to the decisions form) and MERGED his new briefing_cap ratification
into it; qa_ordered_routing 10/10.
BRIEFING CAP (David-ratified hard reserve, signals.py cap_briefing): up to 3
behind in the top 5; the other 2 reserved for non-behind kinds by impact; if <2
non-behind exist the reserved slots fall back to the next behind — always 5 when
5 exist, never blank, never a silently dropped signal; per-lens cap (2/lens)
stays on top. Extracted as a pure function and unit-tested: 5-behind/3-lenses->5,
4-behind+1-outlier->5 (fallback), 5-behind/2-lenses->4 (per-lens binds). qa_hero
50/50.
VERIFIED on Thornbridge: the cap now surfaces an outlier in the top-5
(PROP_8e0b6316). FINDING vs the brief's "both REW_BEN_045 AND PROP_8e0b6316
reach top-5": only PROP_8e0b6316 does. REW_BEN_045 is blocked because (a) money
takes one of the 2 non-behind reserve slots and (b) REW_BEN_045's retain lens is
already full (money + a retain behind, per-lens cap 2). Working as ratified —
both outliers would need a larger reserve, money excluded from the reserve, or a
relaxed per-lens cap. All tunable; flagged for David.
THRESHOLD (ordered-outlier noise gate, modal_share): reported 0.35 vs 0.50 on
Thornbridge — 0.35 fires 6, 0.50 fires only 2. The 4 lost at 0.50 (modal
0.39–0.48) include the textbook REW_BEN_045 (4x life cover, modal 0.43, pct
93.6). For ordered scales "a meaningful tail" != "one band >50%". RECOMMEND KEEP
0.35 (matches the ~35% panel modal median); flagged panel-tunable. Mechanism B
uses the same gate.

## 2026-06-13 — Signals Phase 2 cont. (2/2): Mechanism B + behind_explicit + IP carve-out
MECHANISM B — depth-of-provision matrices (signals.py matrix_depth_signals +
_matrix_depths). depth = how many of the 7 role levels a benefit covers, from
RAW per-org coverage (the per-level aggregate can't give per-org depth), so
build_signals now takes conn+org_id (app.py passes them). Fires BOTH tails vs
the peer depth distribution, NO verdict, same noise gate as Mechanism A, n>=5;
panel-scoped (cut-scoping is a refinement). routing depth_matrix: REW_BEN_139
PMI, REW_PAY_109 status car, REW_INC_133 LTI, REW_PAY_020 allowances-pensionable,
REW_FAI_TRONC (covered="Yes", lens recommendations). VERIFIED on Thornbridge:
1 fires — REW_INC_133 "LTI eligibility reaches 2 of 7 role levels — peer median
0" (correct: deeper LTI reach than the median org, which offers none). Other 4
near-median -> no fire (good selectivity).
3a behind_explicit — REW_Q049530 (car mileage, lower_is_better) fires 'behind'
off the EXPLICIT scale, ONE-ended (bad tail only: high threshold = restrictive).
Logic verified; does NOT fire for Thornbridge (org never answered -> suppress,
never impute).
3b IP presence — INTENTIONALLY NOT SHIPPED. The option "Not applicable / not
offered" CONFLATES N/A with not-offered, so practice_status returns 'unknown'
(not not_in_place); firing "you don't offer IP" off it would be the exact
muddle the carve-out exists to prevent. The clean presence signal needs the
option SPLIT into "Not applicable" vs "Not offered" — a firewall data change.
Reverted the prevalence_lenses add; flagged for David. (Moot for Thornbridge
anyway: it offers IP — 047="4–13 weeks" — so Mechanism A handles the generosity
half within the offering cohort.)
GATES: qa_hero 53/53 (+3: depth no-verdict, depth off explicit ordering, cap
fallback==5), qa_ordered_routing 13/13 (+depth_matrix), qa_scores 3/3, qa_focus
28/28. Dashboard renders capped, the Pay-review-cycle outlier surfaces, no
verdicts, no console errors.
DEFERRED / FOR DAVID: (a) split the IP "Not applicable / not offered" option to
unlock 3b; (b) reserve size — both REW_BEN_045 and the depth signal still lose
their capped slot to money + retain per-lens contention; raise reserve or
exclude money to surface more than one new-mechanism signal; (c) ratify the
depth_matrix + ordered lens recommendations; (d) cut-scoping for Mechanism B.

## 2026-06-13 — Signals Phase 3: multi-select prevalence + gated rarity (LAST mechanism class)
Two new categorical firing paths in signals.py, off the existing block (no raw
plumbing). routing: multi_prevalence (13) + rarity (19 = 17 gated + the 2 Phase-2
re-routes), thresholds decisive_low=15 / decisive_high=85 / rarity_floor=15.
MECHANISM C — multi-select per-OPTION prevalence. NOT answer-set rarity (which
flags everyone, e.g. REW_INC_060's 79 combos/162 orgs). For each metric, fires on
the single most DECISIVE option: one the org PICKED that <=15% adopt, or one the
org SKIPPED that >=85% adopt. One signal per metric (per-metric cap). Both
directions, no verdict.
MECHANISM D — gated rarity single-select. Fires when the org's chosen value has
adoption <= rarity_floor AND a clear norm exists (mode >= 50%, asserted at fire).
NA/off-list answers never fire (no rarity). No verdict.
CLEANUP: removed REW_PRO_035 + REW_PAY_TIPS_EXIST from ordered_outlier/scales
(they belong to Mechanism D rarity now — gate asserts they're in rarity, not
double-booked).
VERIFIED on Thornbridge (uncapped): 6 rare fire — 2 C (EXT_REW_GAP_011 "Utility
costs" 7%, REW_BEN_038 "Technology salary sacrifice" 13%) + 4 D (REW_BEN_HOL_007
7%, FAM_011 12%, FAM_009 14%, FAM_007 15%). All factual ("you selected/answered X
— only N% of peers do"), no verdict, per-metric cap holds. Full set now 39: money
1, behind 7, outlier 6, depth 1, rare 6, prevalence 18. The re-routes don't fire
for the demo (REW_PRO_035="Not defined" NA; REW_PAY_TIPS="Yes" is the 68% mode) —
correct.
THRESHOLDS (panel-tunable, RECOMMENDED): decisive 15/85 and rarity floor 15 fire
signal-not-noise; tighter (10/90) drops 3 of 4 legit D rarities. Set from
Thornbridge, revisit on a real panel.
GATES: qa_hero 56/56 (+rarity no-verdict, rarity-routed-not-set-rarity, per-metric
cap), qa_ordered_routing 17/17 (+multi_prevalence/rarity), qa_scores 3/3, qa_focus
28/28. Dashboard renders capped, no verdicts, no console errors.
STATUS: ALL firing mechanism classes are now built (money, save, behind,
prevalence, ordered-outlier, depth, multi-prevalence, rarity). OUT OF SCOPE per
brief and left untouched: 35 held no-norm metrics (re-qualify on a real panel),
REW_BEN_REM_PAY_001 (dependent, David held), the IP presence half (needs the
firewall option-split David declined). Lenses across Phase 1/2/3 remain David's
to ratify.

## 2026-06-13 — Signals END-TO-END system review (read-and-report; no behaviour changed)
Holistic audit of all 8 firing classes + the briefing cap, after Phases 1–3. No
thresholds/behaviour touched; the only edit is a new lock-down gate.
COHERENCE — all green:
 • FULL uncapped set on Thornbridge = 39 (money 1, behind 7, outlier 6, depth 1,
   rare 6, prevalence 18) — EXACT match to the last recorded set, no drift.
 • One metric -> one firing class. The ONLY cross-class overlap is
   money ∩ behind = REW_BEN_PENS_EMP_MAX_01 — the declared pension dedup (money
   fires, behind suppressed by seen_q). No unintended overlap.
 • No verdict word in ANY fired signal across all 8 classes.
 • Every fired metric is routed (no rogue firing); no metric fires twice
   (per-metric cap holds); n>=5 on every fired signal.
 • Briefing cap composes with all 8 kinds: fallback yields 5, never drops, per-
   lens holds (qa_hero unit test + live capped set verified).
DELIBERATE GAPS — all still deliberate:
 • Held: REW_BEN_REM_PAY_001 unrouted/inert; REW_BEN_SICK_001 held (absent from
   position_lenses, never fires).
 • IP presence half absent from prevalence_lenses; only the generosity half fires
   via Mechanism A (REW_BEN_047/048 in ordered_outlier).
 • Anchor-risk: REW_Q049530 -> behind_explicit (bad-tail only; unanswered for
   Thornbridge -> no fire, suppress-never-impute); REW_PAY_003 + PROP_8e0b6316 ->
   ordered_outlier. None fires off array-index inference.
GATES: qa_hero 56/56, qa_ordered_routing 17/17, qa_scores 3/3, qa_focus 28/28,
qa_phase3 10/10 — GREEN. qa_phase1 (1 red) and qa_phase2 (24/1) each fail on the
SAME pre-existing cause: both hardcode /api/benchmark/PROP_9620d380 (a Processes,
status=proposed metric) which 404s under the reward-only launch. NOT a signals
regression and NOT a security leak — qa_phase2's other foreign-org_id tenancy
checks (/api/my-data, /api/gap-register) PASS, so session-wins isolation is
intact. Added qa_signals_system.py (8 checks) to lock the coherence invariants.
FINDINGS FOR DAVID (flag, not fixed):
 1. Stale doc: ordered_scale_routing.json `behind` list still includes
    REW_BEN_SICK_001, which is held from the firing source (position_lenses). It
    does NOT fire (the list is documentation, not the firing path), but reads
    double-booked — remove or annotate as held.
 2. Thresholds live in TWO config files — Phase-1 in signal_lenses.json
    (behind 25 / save 85 / prevalence_floor 50 / money_min 10000), Phase-2/3 in
    ordered_scale_routing.json (tail 20 / modal 0.35 / band 0.50 / n 5 /
    decisive 15/85 / rarity_floor 15). Both are hot-reloadable config and
    internally consistent (ordered-outlier + depth share the gate), but not in
    ONE place — consider cross-referencing for discoverability.
 3. Gate hygiene: qa_phase1 + qa_phase2 reference the out-of-scope PROP_9620d380;
    swap to an in-scope reward metric so these platform gates run clean again.
STATUS: the Signals system is coherent and launch-ready on the seed panel; all
thresholds are seed-panel values to revisit on a real customer panel; lenses
remain David's desk-ratification pass.

## 2026-06-13 — Dedicated Signals explore section (whole-org view)
The home dashboard only shows the capped top-5 briefing; built a dedicated page
so the user can see and explore EVERY signal across their organisation.
BACKEND: signals.build_signals gains a `cap` param — cap=False returns the full
impact-ranked set (no briefing reserve). /api/overview now returns `signals_all`
(full) alongside `signals` (capped home set). One extra build_signals call per
overview (the depth mechanism's 5 small SELECTs); home behaviour unchanged.
FRONTEND: SignalsPage (web/js/pages.js) — fetches /api/overview, renders
signals_all grouped by OUTCOME LENS (Attract / Retain / Engage / Save) with a
one-line description each, filter chips (All + per-lens counts), and rows reusing
the home's lens-tinted .signal-row (value badge, full peer-fact detail, a "how it
flagged" kind chip — £ gap / position / peers do this / you're at an end / how
far it reaches / rare choice — and click-through to the metric). Flags-never-
advice framing up top ("you decide whether being different is good or bad").
Locked + empty states mirror the home panel. Route /signals + sidebar RailItem
"Signals" (flag icon, between My view and Priorities). CSS reuses signal-row,
adds .sig-filters/.sig-chip/.sig-lens-head/.sig-kind. Cache v86 -> v87.
VERIFIED on Thornbridge: 39 flags across 4 lenses (attract 5 / retain 17 /
engage 10 / save 7, all 6 kinds), lens filter works, nav present + active,
mobile no horizontal overflow, no console errors. qa_focus 28/28,
qa_signals_system 8/8.

## 2026-06-14 — Signals page QA + polish
QA of the new Signals explore page surfaced one real defect: the value badge
held long band labels (rare/outlier value_display, e.g. "No – study undertaken
in personal time" at 282px), dominating the row and squishing the peer fact
into a tall narrow column — plus the value was duplicated (badge + detail).
FIX (frontend only): the value badge now renders ONLY for money/save/prevalence
— the kinds whose headline number isn't already in the detail. behind / outlier
/ depth / rare lead with the full peer fact instead, anchored by a lens roundel
(re-added for a consistent left edge). Tightened kind chips ("at an end", "role
reach"), badge set to nowrap. Verified across all 4 lenses on Thornbridge: money
keeps its "£75k/yr" badge, the long-band rows now read cleanly, filters + lens
roundels consistent, home dashboard unaffected (5 capped), mobile no overflow,
no console errors. Cache v87 -> v88.

## 2026-06-15 — Schema vs data: different operational treatment
Resolved while adding the "Suggest a metric" feature (metric_suggestions table).
SCHEMA changes are added to db.py's SCHEMA string — idempotent
(CREATE TABLE IF NOT EXISTS), auto-applied on every restart by init_schema().
DATA changes use double-guarded scripts (--write --confirmed-by-david), applied
deliberately by David (the integrity firewall). Schema is not data — different
operational treatment: structural DDL is reproducible and safe to auto-apply;
benchmark/answer data is signed off by hand. The metric_suggestions table lives
in SCHEMA (canonical); server/migrate_metric_suggestions.py is a guarded manual
fallback only.

## 2026-06-15 — Small-sample peer caveat + methodology constants
Added a single page-level "Small sample · {n} peers" caveat to the Overview
(beneath the "Comparing against" control), gated on insights being unlocked,
shown when the chosen cut's pool size is in [5, 20). Single source of truth:
pages.js `cutSize()` → `OverviewPage.thinSample`; no per-surface flags (gauge,
You-lead/Biggest-gaps, signals render nothing extra). The cards' "indicative"
flag is untouched.

## Methodology constants — distinct concepts, do not conflate

| Constant | Value | What it measures | User-facing label | Code location |
|----------|-------|------------------|-------------------|---------------|
| Per-metric suppression floor | 5 | Peers who answered a given question; below it the metric is hidden entirely | (none — hidden) | aggregate.py:28 (`SUPPRESSION_FLOOR`) |
| Domain metric-coverage floor | 5 | Polarised questions behind a domain verdict; below it, verdict falls back to combined evidence | "indicative" | `DOMAIN_MIN_POLARISED` defined app.py:65 (env `LUMI_DOMAIN_MIN_POLARISED`), applied positions.py:726 (`hero_signals`) |
| Peer-sample thinness | pool size in [5, 20) | Size of the chosen comparison cut; below it (and at/above the suppression floor), verdicts against it are directional | "Small sample · {n} peers" | pages.js `cutSize` / `OverviewPage` `thinSample` |
| Insights-unlock gate | 90% | Share of the user's own key reward questions submitted; below it, verdicts suppressed (data-pending) | data-pending gauge | `COMPLETION_THRESHOLD` app.py:90 (env `LUMI_COMPLETION_THRESHOLD`, default 0.90), enforced `org_unlocked()` app.py:125 |

Key distinction: "indicative" (metric coverage — few comparable questions behind
a verdict) and "small sample" (peer count — few orgs in the comparison cut) are
ORTHOGONAL axes. A domain can be confidently "on market" against 8 peers, or
"indicative" against the full 221. These were nearly conflated when the
small-sample caveat was built; they must always use different words and must
never share a threshold.

Lower bound (confirmed 2026-06-15): the peer-sample window starts at 5, not 1. A
cut with pool size < 5 is already FULLY suppressed — custom groups return no
blocks (peer_twin.py:193 → app.py:418), and industry/FTE/All cuts suppress every
metric because per-metric n can't exceed pool size — so no verdict exists to
caveat. 5 (= SUPPRESSION_FLOOR) is the exact size at which a verdict can first
appear.

Threshold note: < 20 is a round number in a safe gap (industries are 8–16, FTE
bands 29–36), so anything 17–28 produces the same split on current data. It is
not precisely calibrated to a statistical bound.

A third related constant — `TILE_MIN_POSITIONED = 1` (app.py:68) — is the floor
for the indicative *combined-evidence* verdict (≥1 distinct question). It is
deliberately NOT in the table (it's the trigger for "indicative", not a separate
concept), noted here for completeness.

Known gap: the "organisations like you" (twin) cut does not expose its pool size
and is treated as not-thin by default — so a thin twin cut is currently
un-flagged, the same inconsistency this work removed, just hidden. Revisit when
the twin count is available. (Separately parked: whether the board pack should
*editorialise* its already-present "n=" sample line for [5, 20) cuts, or stay
neutral — David to decide.)

Verification note (2026-06-15, live checks signed off): the caveat was bracketed
in the running app on Thornbridge — present at Energy · 8 (DOM read
"Small sample · 8 peers", peer-framed) and absent at All · 221 — and the two
floors were visibly distinct in the same view (Incentives reads "indicative"
@ 8 peers yet "on market" @ 221, i.e. metric coverage and peer count moving
independently). The CUSTOM-GROUP case in [5, 20) is COVERED BY CONSTRUCTION /
inferred, NOT directly observed: no group in that window exists in the current
demo data (Thornbridge's groups are 3 → too-few and 30 → not-thin). A live
`cutSize()` sweep confirmed the group dim returns `match_count` through the
identical `cutSize` → `thinSample` path that renders the observed industry
caveat (group 30 → not-thin, group 3 → not-thin via the ≥5 bound), so a group
landing in [5, 20) flags by the same mechanism — but that exact render has not
been eyeballed. Re-verify directly if a [5, 20) group is ever created.

## 2026-06-15 — Back office / super-admin console (closes D2)

Built the lumi-staff back office, the long-deferred D2. A NEW privilege tier
sits ABOVE the org roles (admin/contributor/viewer): `users.platform_admin`
(idempotent ALTER in db.py). `require_platform_admin(request)` (app.py) gates a
new `/api/admin/*` namespace; it returns NO org and never reads a client org_id —
the one place the platform deliberately crosses tenants, so every admin route's
first line is the gate (verified: all 8 routes return 403 for a normal tenant
admin, and `platform_admin` is false in their /api/me). Staff org "Lumi HR
(staff)" (source='staff', no benchmark data) + the `david@lumihr.co.uk` account
are provisioned by the double-guarded `seed_staff_admin.py` (demo password
`lumi-demo-2026`). Frontend: `web/js/admin.js` (loads after pulses.js to reuse
InputForType + PulseReport as file-globals); a "/admin" route + "lumi staff" nav
group render only when `me.user.platform_admin` (NotFound otherwise — invisible
to non-staff).

Four modules: (1) cross-tenant **orgs overview** (read-only); (2) **metric-
suggestions triage** — added reviewed_by/reviewed_at/review_notes; GET/PUT under
/api/admin/suggestions; accepting promotes to `core_backlog` via
`releases.add_backlog` (dedup on source_ref); (3) **pulse builder** — wraps the
existing `pulses.py` lifecycle (create with a library-question picker + bespoke
non-matrix authoring, open/close/extend/archive, report); drafts are staff-only
(member `/api/pulses` filters status!='draft'); (4) **create metric** — author →
`core_backlog` (source='admin_console') → explicit "Publish to live library"
does the governed insert (mirrors apply_release_2026_2.py) + `invalidate_cache`.

Firewall decisions: the console authors DEFINITIONS/METADATA only — it never
writes answer data (answers/pulse_responses), and pulse demo cohorts stay in the
guarded scripts. New core metrics are ALWAYS `is_scored=0` + `is_required=0`,
stamped to the current release (`release_entered`), with NO per-metric release
cut (the next annual diff logs them as 'added'). This was verified live: a
published metric (ADM_*) appeared cross-tenant for a member, the Reward-scope
required gate stayed 82, the member's `benchmark_unlocked` was unchanged, and
ZERO answer rows were created. v1 authors non-matrix only (matrix stays
script-only). Cache v154 → v155.

Still out of scope (remains D2): a full audit-log UI, 2FA, pay-deals; and an
in-console delete for draft pulses/backlog items (drafts are immutable in v1).

## 2026-06-15 — Market position: proportional arc + domain bars (display half)
The needle-instrument gauge (2026-06-13) read as broken when bottom-heavy: a
fixed-width green "on market" cap with the verdict-coloured needle jammed on the
amber seam looked self-contradictory (e.g. 42 below / 27 on / 25 above still says
"On market"). Rebuilt the hero "Where you stand" gauge as a PROPORTIONAL arc:
each block's angular span ∝ its count (so a below-heavy org shows a big amber
block — the composition itself is honest), with a NEUTRAL-GREY centroid needle
that stays INSIDE the verdict block (positioned by the lean within that verdict's
range) so it never contradicts the word. Dropped the fixed minor-graduations +
median caret (they implied a fixed scale). `OverallArc` in pages.js; shared
`ARC`/`arcSeams`/`proportionalNeedleRot` helpers. Applied the same language to the
7 domain cards (`CategoryTile`), iterated to MIRROR THE DIAL exactly (user calls):
counts-inside-segments read as an amateur chart widget, and a dot+number legend
under the bar still wasn't it. Final form = the dial flattened: a proportional
stacked below/on/above bar (segments ∝ count, verdict segment richer, indicative
faded) + a neutral "you are here" MARKER LINE at the centroid (same
in-verdict-block logic as the gauge needle, on the flat [0,1] bar) + the counts
as a labelled footer ("N Below · N On · N Above") pinned to the card's bottom
edge with a separator, just like the gauge's footer legend. X/Y ratio removed.
`.cat-bar`/`.cat-bar-track`/`.cat-bar-mark`/`.cat-foot` CSS.
This is the DISPLAY half of the Market Position Engine spec,
brought forward on the EXISTING engine output (below/at/above counts + lean already
computed) — the firewall-gated per-metric config/normaliser deepening
(data/market_position_config.json, awaiting David's sign-off) slots in underneath
without re-touching the display. Frontend-only; cache v155 -> v161.

## 2026-06-16 — Market position config: auto-classification (handover Part A/B)
Applied the handover's Part A ruleset to auto-classify all 206 live Reward metrics
into four fields and wrote the extended `data/market_position_config.json`
(hot-reload, David-owned): per-metric `{class (Level|Provision|Practice|Design),
type, direction (higher_is_better|lower_is_better|neutral|null for Approach),
lens, weight}`, a `_domains` block with `competitiveness` (all true except
Governance=false), and `defaults` carrying the new **3/3/1 thresholds**
(suppression_floor / domain_min_polarised / tile_min_positioned). The pass:
Level 44 · Provision 26 · Practice 98 · Design 38 → Substance 70 / Approach 136;
direction higher 64 · lower 1 · neutral 5 · n/a 136; **62 higher-is-better
Substance in competitiveness domains feed the gauge**. Two heuristic bugs fixed
before writing: direction base must NOT use `score_direction`'s sign (a yes/no
storage artifact → false `lower_is_better`); `NEUTRAL_KW` "number of"/"cost" were
too broad (neutralised "number of weeks' pay", "cost-of-living response"). Errors
deliberately lean OUT of the gauge (safer than a false Level verdict).
`gen_market_position_review.py` rewritten to emit the Part B firewall review
(`MARKET_POSITION_REVIEW.md`) risk-ranked exactly per the doc — 1) directions (16:
1 lower + 5 neutral + 10 defaulted-higher), 2) Governance carve-out (41), 3) class
edge cases (9, binary-as-Practice); 143 ride unflagged. Build proceeds on the
auto-pass; David refines the flagged subset via hot-reload — no rebuild, no gate
(pre-launch, no customers). Engine NOT yet wired to the config — config + doc only.
**[superseded 2026-06-16 — now wired & live; see next entry. The config is reviewed,
signed off and ACTIVE, not an auto-pass pending review.]**

## 2026-06-16 — Market position engine WIRED to the classification (live verdicts changed)
Wired the engine to read the (firewall-reviewed, signed-off) classification — the
first time it affects what users see. `positions.market_position_config()` is a
hot-reload loader (mtime-cached, error-fallback; mirrors `signals.lens_config`), so
David's future refinements take effect on the next request, no redeploy.
`hero_signals` gains an optional `mp_config` (dependency-injected from the overview):
when present it routes the gauge feed by classification; when absent it runs the
legacy polarity path byte-for-byte (keeps `qa_hero` synthetic fixtures valid).
**Gauge feed (overall + per-domain below/on/above) = SUBSTANCE only:** `class ∈
{Level, Provision}` AND `direction == higher_is_better` AND the domain is competitive.
Level positions come from the score/value `items`; **Provision positions come from
`practice_position_items`** (presence ranked vs peer take-up) — newly routed INTO the
gauge. Deliberately OUT: the 5 `neutral` cost/budget metrics (context, no verdict),
the 1 `lower_is_better` malus (favourable when low; its own row still inverts via
`_adj_percentile`), ~31 Practice/Design (Approach = "differs"), and all of Governance
(`_domains.competitiveness=false` → no headline role). Governance tiles now read
**"no market rate"** + practice prevalence beside, never a verdict (pages.js CategoryTile,
`d.competitiveness===false`). **Thresholds: `domain_min_polarised` 5→3** (firm-vs-
indicative floor, from config `defaults`; lets a 3+-Substance domain like Wellbeing earn
a strict verdict where it was practice-only indicative); `tile_min` 1 unchanged.
**`SUPPRESSION_FLOOR` deliberately KEPT at 5** (aggregate.py:28 untouched): the wiring
task's cross-check requires per-metric n≥5 suppression unchanged, and it's a separate
data-exposure axis that would muddy the before/after attribution + is the lower bound of
the frontend small-sample caveat window [5,20). The config's `suppression_floor=3` (and
the methodology page's "fewer than three companies") is therefore a DEFERRED change for
the dedicated threshold/methodology stage, to be reconciled with published copy then —
NOT made silently here. Before/after captured with a reproducible harness
(`server/mp_baseline.py`, `MP_LEGACY=1` reproduces the pre-wiring snapshot exactly);
every changed verdict is attributable (`server/mp_compare.py` → `MARKET_POSITION_WIRING_DIFF.md`;
per-metric attribution `server/mp_diff.py`). Thornbridge|All: gauge holds On-market
94→87 pool; headline flips elsewhere are real (Ardenbank above→at — strong incentives but
fewer benefits than peers, now that Provision presence counts). `qa_hero` Section 5
updated to the new contract (Governance no verdict, Wellbeing strict, Substance-based
evidence, domain_min=3): 56/56 pass. Frontend cache v161→v162.
**Scope boundary / follow-on:** only the gauge + category verdicts (`hero_signals`) are
classification-scoped. `overview_summary` still drives the board-pack/share headline
("above the market median on X of Y comparable metrics") from the full polarised pool —
a median-crossing count, not a competitiveness verdict, so it doesn't contradict the
gauge; but for full consistency it should be re-scoped to Substance in the display/
methodology stage (flagged, not changed here). Approach ("N differ from market") tally
display + the richer Governance "favourable/context/differs" breakdown are likewise the
Signals/naming stage. Engine reads SUPPRESSION_FLOOR before classification unchanged;
data-pending (<90% gate) path untouched; small-sample caveat [5,20) untouched.
**Signed off 2026-06-16 (David) — live.** The 3-floor / 5-peer split confirmed
DELIBERATE: a domain reaches a strict verdict on **3 metrics**, but a metric still
needs **5 peers** to be usable at all (SUPPRESSION_FLOOR) — the caveat window [5,20)
must be able to flag any cut that shows a verdict. **Next task in this workstream
(queued, not parked):** re-axis `overview_summary` to the Substance pool so the board
pack / share headline and the dashboard gauge can't tell different stories about the
same org — a credibility risk the moment someone spots the mismatch.

## 2026-06-16 — overview_summary re-axed to Substance + gauge polarity bug fixed
Re-scoped the "above the market median on X of Y comparable metrics" headline
(board pack `assemble_pack_payload`, share `/api/share/{token}/data`, dashboard) to
the SAME Substance pool the gauge uses, via a single shared definition
`positions.substance_pool()` (used by both `hero_signals` and `overview_summary`,
injected `mp_config` + `practice_items` at all three call sites). Headline
`comparable_metrics` now == gauge `pool` on every cut — the surfaces can't tell
different stories. qa_hero asserts the invariant (57/57).
**Bug this surfaced + fixed (in the task-#85 gauge too):** the gauge/headline read each
item's stored DB `polarity`, but the config `direction` is authoritative — and Part A
sets `higher_is_better` on 16 metrics whose DB polarity is `neutral` (life-assurance
cover, LTI/commission plans, overtime, long-service, clawback — offering more = above
market). Those 34 items (incl. matrix rows) were entering the wired gauge and being
scored as *lower* by `_adj_percentile` (and uncounted in the headline). `substance_pool`
now normalises each item to the config direction (`_mp_normalised` → copy with
polarity/favourable/distance recomputed; never mutates the shared item). **This corrects
the task-#85 gauge numbers** — Thornbridge|All 38/22/27→41/22/24 (verdict holds On-market);
Ardenbank|All was wrongly leaning-below, now correctly leaning-above (still On-market).
Before/after re-captured (`mp_baseline.py` now snapshots the headline too; `MP_LEGACY=1`
= legacy); diff `MARKET_POSITION_WIRING_DIFF.md`. Backend-only — no frontend change, cache
stays v162. `neutral_tracked`/`by_section`/`by_superpower` summary fields are unused by the
UI; the home `pctAbove` is computed-but-unrendered (dead, left as-is). Next: the broader
display/naming stage (Approach "N differ" tally, methodology page).

## 2026-06-16 — Approach "differs from market" companion (spec §6.1)
Surfaced the Approach register — the half of the classification (Practice + Design)
the engine computed but never showed. `positions._approach_summary()` tallies, over
the answered/unsuppressed practices, how many of the org's choices differ from the
market mode (`differ` = not the modal answer) vs `in_line`; emitted as `hero.approach`
(overall) and per-domain `d.approach`. Rendered as a quiet purple companion line under
the gauge legend — "N differ from market" — never on the arc (spec §6.1). New
`--differs`/`--differs-tint` register token (purple #6257C9: neither good nor bad).
Thornbridge|All = 36 differ / 35 in line / 71 pool. **Decision — the overall companion
is org-wide (includes Governance's 13 differ), NOT scoped to competitive domains:**
Approach is a separate register from the competitiveness gauge, so "how many choices you
make differently" spans all reward incl. governance practices; the per-domain `approach`
(emitted, ready for the §6.2 domain-card companion next) breaks it down. Computed from
`prevalence_items` filtered to config class Practice/Design — so scored/numeric Design
edge cases (no modal comparison) are honestly out of the count, not faked. qa_hero asserts
the companion is present + consistent (58/58). Frontend cache v162→v163.
**§6.2 domain-card companion (v163→v164):** each tile now carries its own quiet "N differ"
purple line, bottom-aligned across the row (verified: every differ line shares one y, pinned to
the card foot). Competitive tiles show it under the below/on/above footer; Governance shows "13
differ" in place of the old "N/M in line with the market" caption (the Approach framing is its
primary content now). Domains with 0 differing choices (Time Off) correctly show no line.
Per-domain data was already emitted by `_approach_summary`, so this was frontend-only
(CategoryTile + `.cat-differ`). NEXT: the Signals page market-position re-axis
(All · below · above · differs) + methodology page.

## 2026-06-16 — Signals page re-axed to market position (spec §6.3)
The dedicated Signals page now leads with **market position**, not lens. Backend:
`signals.build_signals` stamps every signal with `domain` (sub_power), `position`
(below / on / above / **differs**) and `polarity` — position from the config CLASS
(Approach = Practice/Design → `differs`; Substance → the factual tag direction),
**class wins over the score-layer kind** (a "behind"-kind metric the config calls a
Practice reads `differs`, per spec "class by meaning"). Frontend (`SignalsPage`):
a summary card with a **position-coloured proportional bar** + **position chips**
(All · below · above · differs, with counts; the chips subsume the Substance/Approach
split) + a **group by domain · lens** toggle; the list groups by domain (default) or
lens; rows are toned by §5.5 polarity (Substance amber · Approach purple · favourable
green · **neutral navy = context**) and carry the factual position tag — the
workforce-cost-%-of-revenue row reads "below market" in navy with "context, not a
verdict", the CFO landmine defused on the explore surface too. Triage tabs
(Inbox/Priority/Saved/Dismissed) stay a separate axis; no roundel on re-axed rows
(matches the prototype). New `.pos-tag`/`.sig-tone-*`/`.sig-chip`/`.sig-bar` CSS;
`--differs` token reused. Thornbridge inbox: 67 signals = 27 below · 14 above · 26
differs across all 7 domains. Verified live: chip filter dims the bar + filters rows,
group-by toggles domain↔lens (Attract/Retain/Engage/Save), triage intact, home top-3
briefing panel unchanged (still `sigParts`). qa_hero 58/58; no console errors. Cache
v164→v165. The engine's `class` stays internal (analyst/detailed view = a later
workstream).

## 2026-06-16 — Methodology page reconciled to the shipped model (handover Workstream 5)
Added a plain-English "Where you stand — your market position" section to the in-app
**How lumi works** hub (Calculations tab, first card, `id=market-position` so the gauge/
tiles can deep-link it). It explains the model as shipped: the three positions
(below/on/above), the two kinds of measure (market-rate vs **differs from market** —
a choice, not a gap), when below isn't bad (**favourable** = lower-is-better on the good
side; **context** = no good direction, navy), and that the headline is competitiveness-only
(Governance/cost sit beside it). A colour key (below amber · on/favourable green · above
coral · differs purple · context navy) makes the §5.5 palette legible. `GLOSSARY` (core.js)
gains market position / differs from market / favourable / context, surfaced in both the
hub and MethodologyPage glossaries. **No suppression-copy change needed:** the hub already
reads `m.suppression_floor` from `/api/methodology` dynamically, so it states the truthful
**5** (not the draft `lumi-methodology.html`'s hardcoded "three") — matching the
David-confirmed 5-peer floor; the standalone draft HTML stays a design reference, the
in-app hub is the published source of truth. Frontend-only; cache v165→v166; no console
errors. This closes the handover's display/naming stage — engine, config, gauge, domain
cards, Approach companion, Signals page, and methodology are all live and consistent.
Remaining handover items (not started): v2 materiality weighting (`weight`) and the
class-level analyst/detailed view.

## 2026-06-16 — v2 materiality weighting + class analyst view (final handover items)
**v2 weighting (handover §9.6).** David's per-metric `weight` (config, default 1,
hot-reloaded) now scales `signal impact` in `build_signals` — a base-pay gap can outrank
a minor allowance in the ranked briefing + the home cap. **Deliberately scoped to signal
surfacing, NOT the gauge:** weighting the gauge counts/lean would break the qa_hero-tested
"verdict reflects mass" invariant (task #58 — the verdict can't read 'below' when below is
the smallest count). So the gauge stays an honest count of metrics; weight only re-orders
which signals surface first. With all weights at 1 today it's a no-op (regression-safe,
qa_hero 58/58); the lever is live for David to tune. Gauge-level materiality would be a
separate, explicit decision with its own invariant change — not done silently here.
**Class analyst view (spec §6.3).** The engine's internal class/register — kept off every
default chip row — is now surfaced on the single-metric page only. `/api/benchmark/{qid}`
returns a `classification` block (class · register · direction · weight · competitive_domain
· feeds_gauge); MetricPage renders a "How lumi reads this" line with a chip: "in the
headline" (Level/Provision higher), "favourable when low" (lower_is_better), "context"
(neutral), "differs from market" (Practice/Design), or "beside the headline" (Governance).
Verified all five readings live. Frontend `mpReadCopy`/`mpReadChip` + `.mp-class-*` CSS;
signals also carry `mp_class`/`weight` for future analyst surfaces. Cache v166→v167; no
console errors. **This closes the market-position handover end to end** — engine, config,
gauge, domain cards, Approach companion, Signals re-axis, methodology, weighting lever, and
the analyst class view are all live. Open future work (genuinely optional): differentiated
production weights (David, via hot-reload) and, if ever wanted, gauge-level weighting.

## 2026-06-16 — Reward strategy capture (three-plane onboarding) + objective re-ranker
Built the Admin-set reward-strategy capture (handover "Reward Strategy Capture"): an
org-level **stance** so the engines can tell "below market" from "below market, on
purpose". Granularity stays in the questionnaire (spec §0) — these dials never split.

**§1.1 sequencing (logged decision).** The capture extends the shipped company profile
rather than adding a second "confirm your business" wall. New table `org_strategy` holds
only the Plane B (philosophy: 7 dials) + Plane C (posture: 4 dials) inputs; **Plane A
facts are NOT duplicated** — they're read from the existing `registry_json` record
(Lifecycle←Business_Maturity, Talent←Talent_Competition, Workforce shape←*derived* from
Workforce_Frontline_% banded <33/33-66/>66, Footprint←International_Footprint). Admin
overrides persist back into `registry_json` (small merge). **Deviation from §1.1's hard
lifecycle gate (logged):** v1 wires the capture as a reachable page (profile-menu link,
route `/strategy`) + editable later, but does NOT hard-block the benchmark on strategy
completion — a hard gate would lock out every existing seed/demo org (all predate the
table, all strategy-less). The hard gate should be added for NEW signups only (keyed on
source=signup + no strategy row) in a follow-on, so existing tenants aren't walled out.

**§2.1 required vs optional (logged decision).** Three dials are REQUIRED (no default,
must be a real choice) because they flip a signal's direction: `market_position`,
`reward_mix`, `primary_objective`. The other eight default neutral; a skipped optional
stores provenance `'skipped'` and the engine reads it neutral. **NO demographic
suggestions in v1** — the earlier draft pre-suggested family/benefits from a "workforce
life-stage" signal, but that field exists nowhere in the registry (I flagged this; David
dropped the 5th Plane-A fact and the suggestions). `family_position`/`benefits_lead` start
blank like any optional; the `'suggested'` provenance value is reserved-but-unused.

**§4.1 colour (logged decision).** The "Your call" mode tag + review "your choices" chips
use a neutral warm-grey (#F1ECE4), NOT amber — amber is the market-position *lagging*
verdict colour, so it would read as a stray verdict on a chrome label.

**§4.1b vocabulary.** The `market_position` dial shows **Below/On/Above market** (locked
words, lumi-terminology.md), never lag/match/lead — the stored enum stays lag/match/lead
internally so db/engine code is stable. One vocabulary: set "Above market" → the gauge
later says "above market". Signal-effect reveals stay in the "we flag, you decide"
register — descriptive, never directive.

**§5 the strategy→engine contract (logged in full for the follow-on).** TWO engines read
"where you sit"; strategy wires to the right one per reframe.
- *Engine 1 — Market Position* (gauge): wired to `market_position_config` since 2026-06-16
  via injected `mp_config`. The strategy reframes that belong here (FOLLOW-ON, step 8, NOT
  built yet): `market_position` (read the verdict against the member's declared target);
  `reward_mix=benefits` (annotate a Pay-domain below-market verdict). Same injection
  pattern as mp_config — optional arg, absent → legacy byte-for-byte.
- *Engine 2 — Signals*: **the objective re-ranker is BUILT now** (step 7, the honest ship
  hook). `build_signals(..., strategy=None)` gains a per-lens impact multiplier keyed on
  `primary_objective` (`OBJECTIVE_LENS_MULT`): a cost-cutter sees `save` promoted (×1.7)
  and `attract` demoted (×0.6); attract/retain promote their lens; hold = neutral. Applied
  in the enrichment loop alongside the v2 `weight`, BEFORE the sort — pure re-rank,
  fabricates nothing, so the trust rules hold. **`strategy=None` reproduces today's order
  byte-for-byte** (the degrade-to-legacy contract); qa_hero stays 58/58 and the overview
  passes `strategy_for_engine(...)` (None when unset). The remaining reframes
  (`location_approach=agnostic`, `family_position=over`) need David's `location_scoped` /
  `family_metric` config tags — deferred (step 9).
- *Provenance is the confidence dial* (§5.4): `'set'` → full reframe; `'skipped'` →
  neutral; `'suggested'` → reserved. The re-ranker treats a skipped objective as neutral.
- *Trust rules carry over* (§5.5): no reframe fabricates or becomes a directive;
  SUPPRESSION_FLOOR=5 is upstream and unaffected.

**Ship (recommendation a).** Shipped the capture WITH step 7 (the re-ranker) — collecting
dials that change nothing would train members the feature is theatre; the objective
re-ranker is the smallest honest Signals-only hook (no new metadata).

**Verification.** `verify.py` is DEPRECATED (pre-dates the reward-only launch; crashes in
its 778-scope sections), so per its own deprecation notice the runnable quality bar is a
new `server/qa_strategy.py` (the same §6 assertions): tenancy (viewer/contributor 403,
admin 200, forged body org_id ignored), enum validation (400, never coerced), the
server-side required gate, provenance integrity (no phantom `'suggested'`), no-demographic-
suggestions, and tenant isolation — **14/14 pass**. The §6 block is also added to verify.py
(spec-literal) behind its `--force` guard. UI verified end-to-end in preview: Plane A
pre-fill, scale-track with measured thumb + signal-effect reveal, required gate (toast +
amber flag), review read-back ("Skipped — read neutrally"), commit → PUT persists with
correct provenance + completed_at. Files: db.py, app.py (3 routes + Plane A reader +
`strategy_for_engine`), signals.py (re-ranker), web/js/strategy.js, app.css, app.js,
index.html, verify.py, qa_strategy.py. Cache v167→v168. Carried-forward (not blockers,
§9): the "refine by job family later" dial copy is a promise not yet live (per-family
refinement doesn't exist) — left as-is per the mockup; soften if it slips the roadmap. The
stated-vs-actual mix sanity-check (#3) is explicitly not-v1.

## 2026-06-16 — Strategy step 8: Market-Position reframes (target-read + benefits annotation)
Wired the reward strategy into the **Market-Position engine** (handover §5.2) — the
follow-on the capture set up, now buildable because the gauge reads classification config.
`hero_signals` gains an optional `strategy` (injected by the overview exactly like
`mp_config`; `strategy=None` → today's output byte-for-byte, qa_hero 58/58).
- **market_position target-read.** `market._market_target` reads the competitiveness
  verdict against the member's declared stance (lag/match/lead). It's an ANNOTATION only —
  the verdict, counts and lean are untouched, so "verdict reflects mass" holds. An
  above-market member who AIMED above-market reads **"on target"** (green), not a
  premium-cost flag; an on-market member who aimed to lead reads **"behind your target"**
  (amber). Surfaced as a quiet line under the gauge legend (OverallArc), coloured by
  alignment — on_target/ahead green, behind amber. Descriptive, never directive
  ("we flag, you decide").
- **reward_mix=benefits.** A below-market PAY verdict (and only Pay) carries a `mix_note`
  when the mix is benefits-led — the dashboard tile annotates "benefits-led mix — read the
  total package" (purple/differs). The verdict stays factual below; the note reframes it as
  by-design, not a gap.
Both honour the trust rules: no reframe fabricates or re-verdicts — only annotates; both
key off provenance (a `skipped`/absent dial reads neutral via `_strategy_field`). The two
remaining reframes (`location_approach=agnostic`, `family_position=over`) still need David's
`location_scoped`/`family_metric` config tags (step 9) — deferred. Frontend: `.arc-target`
+ `targetCopy()` (below/on/above-market stance vocab), `.cat-mixnote`. Demo: Thornbridge set
to market_position=match → on-market org reads "On your target" (green). Cache v168→v169;
qa_hero 58/58, no console errors. This completes the strategy feature's core promise — the
gauge now respects the member's declared stance, the whole reason the dials exist.

## 2026-06-16 — Strategy step 9: location_scoped + family_metric reframe tags
Wired the last two §5.2 reframes — they were the half I can build (the engine mechanism);
the tagging is reward-domain config David refines via hot-reload.
- **family_position=over** (Signals): a config `family_metric` that reads ABOVE market / high
  spend (save) is relabelled `strategy_note="intended — your generous family stance"` and its
  briefing impact demoted ×0.4 — high family spend is by design, not overspend. A family
  metric that's BELOW market is deliberately LEFT as a flag (being below contradicts the
  stance — never hide a real gap; trust rule). The note surfaces on the Signals row.
- **location_approach=agnostic** (both engines): config `location_scoped` metrics — per-
  location pay — are dropped from the competitiveness gauge (`_hero_signals_classified`) and
  their signals suppressed (`build_signals`), since a one-rate org has no per-location read.
Both gate on `_strategy_field` (provenance-aware) AND the config tag, so they no-op byte-for-
byte when the dial is unset/skipped OR no metric is tagged (qa_hero 58/58). **Proposed tags
applied** (auto-detected, curated, David refines — Part A pattern): `family_metric` on the 7
FAM_* leave + bereavement metrics, `location_scoped` on `REW_BEN_REM_PAY_002` (the one genuine
per-location-pay metric). Review doc: `MARKET_POSITION_STRATEGY_TAGS.md`. Verified by unit
test — family-above+over relabels+demotes (80k→32k), family-below+over stays a gap, no-strategy
unchanged, location suppress only when agnostic. Frontend `.sig-strat-note`; cache v169→v170.
**The strategy→engine chain is now complete end-to-end:** capture (Plane A/B/C) → Signals
(objective re-rank + family relabel + location suppress) → Market Position (target-read +
benefits annotation + location exclude). Remaining strategy work is product hardening only
(new-signup onboarding gate, dashboard nudge), not engine.

## 2026-06-16 — Strategy capture discoverability (nav + dashboard nudge)
The capture was only reachable from the profile menu — too buried ("can't see where it
is"). Made it discoverable: (1) a **sidebar nav item** "Reward strategy" (Admin, under Your
organisation, between Your data and Team) — `compass` icon, route `/strategy`; (2) a
**dashboard nudge** — the overview now returns `strategy_complete`/`strategy_can_edit`, and
an Admin whose org has no completed strategy sees a prominent blue banner above the gauge
("Set your reward strategy · Set it up"), session-dismissible but reappearing each visit
until the stance is captured (keyed on the completion flag, not a permanent dismiss). This
is the soft onboarding surface for new signups too — they meet it on their first dashboard.
**Deliberately NOT a hard benchmark gate** (per the 2026-06-16 lifecycle deviation): blocking
the benchmark until strategy is set would lock out every existing strategy-less org; the
nudge + nav solve discoverability without that risk (a hard new-signup-only gate stays
available if David wants it stronger). Demo: Thornbridge left strategy-less so the nudge +
nav are both visible (the reframe payoff was verified separately under a set strategy).
qa_hero 58/58; no console errors; cache v170→v171. This completes the strategy workstream —
capture, both engines, the tag mechanism, and now discovery — end to end.

## 2026-06-17 — Signals page strategy indicator (modest)
The objective re-ranker reorders the Signals page but gave no visible cue. Added a modest
indicator in the Signals summary card (opposite the count): "⊙ ordered for your <Objective>
strategy · edit" — names the primary_objective in member language (Attract / Retain /
Control cost / Get it right / Hold steady) and links to the capture. Backend: overview
returns `strategy_objective` (the human label, None when unset/skipped). Only shows when a
strategy is set; degrade-safe. Keeps the "we flag, you decide" register — it explains the
ordering, never claims a verdict. Cache v171→v172. The strategy influence now reads on all
three surfaces: gauge target line (home), re-ranked + labelled Signals (Signals page), and
the per-tile/per-signal reframes. Demo left WITH a strategy (Control cost, aim above-market)
so the influence is visible — the cost objective pulls save signals (Relocation, EV charging)
into the briefing and the gauge shows "Behind your target".

## Reward strategy capture — QA + premium polish + delight (2026-06-17)
Deep-polished the three-plane capture flow (strategy.js + app.css), cache v172→v174.
**Delight moments:** (1) scale-thumb spring-settle (`thumbPop`) on every dial pick — the
thumb pops into place, fires only on change not first paint (prevIdx guard); (2) signal-effect
slide-fade reveal (`seReveal`); (3) review check-mark pop-in (`checkPop`) + commit celebrate
shake (`checkCelebrate`); (4) **confettiBurst on successful commit** (reuses core.js:214,
reduced-motion-aware), button flips to green "✓ Saved" (`savedPop`) then auto-navigates home
after 1.4s; (5) progress-rail completed planes show a green check instead of the letter;
(6) objective-card / benefit-chip selection pop (`optPop`); (7) staggered review-section reveal.
**Premium feel:** 14px dial-card radius + hover-lift (translateY -1px + shadow-lift), gradient
dial roundels with hover scale/rotate, gradient scale-fill + thumb with focus-ring halo,
tighter strat-title (28px, -.025em), button shadows. **All animations gated behind
prefers-reduced-motion.** Verified in preview: no console errors, all computed styles confirmed,
full A→B→C→Review→commit path drives clean; Thornbridge strategy preserved (lead/balanced/cost).
The engine seams (Signals re-rank, Market-Position target-read) are untouched — pure presentation.

## "My view" → "My dashboards" — multiple saveable dashboards (2026-06-17)
Replaced the single per-user "My view" with **multiple named, saveable dashboards**. Cache v174→v175.
**Data model:** new `dashboards(dashboard_id, org_id, user_id, name, layout_json, position, …)` table
(slot shape identical to the old pinned_views.layout_json) + `users.active_dashboard_id` pointer
(both via SCHEMA / migration-lite, applied on restart). `pinned_views` is RETAINED as the org-default
TEMPLATE that seeds a new user's first dashboard (admin "Save as team default" still writes user_id='').
**Migration is lazy + non-destructive:** on first GET /api/dashboards a user with no dashboards gets one
("My dashboard") seeded from the cascade their old /api/myview used (personal pinned view → org default →
starter 8 gaps + 4 strengths). Nobody loses their existing view; the old pinned_views row is left intact.
**API:** GET /api/dashboards (list + active + active layout, bootstraps), GET/PUT/DELETE /api/dashboards/{id},
POST /api/dashboards (create, optional clone_from), POST /api/dashboards/{id}/activate,
POST /api/dashboards/pin (toggles a metric on the ACTIVE dashboard — the global pin-star's new target).
Delete never leaves zero dashboards (re-bootstraps); the last-one delete reads as a "Reset".
**Frontend:** DashboardsPage (evolved MyViewPage; window.MyViewPage kept as alias) = a pill **tab switcher**
(each dashboard + count badge, "＋ New") over the SAME draggable/resizable card grid. Active dashboard has
inline rename (pencil/double-click), duplicate (copy), delete (close → inline confirm bar). Nav relabelled
"My view"→"My dashboards", icon star→table, route /myview→/dashboards (/myview 301-style redirects in-app).
app.js global onPin now POSTs /api/dashboards/pin and syncs the star-fill set from the response; the page
keeps app-level pinnedIds in sync via a new setPinned pageProp so the star reflects the active dashboard.
Kebab label "Pin to My view"→"Pin to dashboard". **Verified in preview** (fresh restart applied the schema):
create/rename/switch/pin/delete all drive clean, dashboards are isolated (pin to one never touches another),
active persists across reload, migration produced "My dashboard"(3 cards), /myview redirects, no console errors.

## Every chart downloadable — drop the "answered" gate on PNG export (2026-06-17)
The "Download chart (PNG)" affordance was gated `!c.suppressed && !!c.you`, so any metric the org
hadn't answered yet — which still renders the full peer-distribution chart — offered no download.
Loosened both export sites (card.js KebabMenu + app.js MetricPage) to `!c.suppressed && !matrixBlank`,
where `matrixBlank` = a matrix with every level suppressed. Rationale: a chart is downloadable whenever
one is actually drawn (answered or not); the only honest exclusions are cards with NO chart — suppressed
(n<5, data hidden for privacy) and fully-suppressed matrices. The export engine (charts.js exportCardPNG)
was already type-agnostic: numeric/select/ordered render SVG inline, matrices rebuild an SVG twin via
buildMatrixSVG, and the "You" annotation suffix already no-ops when c.you is null — so no export-engine
change was needed. Cache v176→v177. Verified in preview: unanswered/numeric/select-ordered/matrix cards
all export "downloaded"; the metric page shows Download for an unanswered metric; suppressed cards still
correctly offer none; no console errors. (Pulses cohort mini-bars are a separate Tier-2 surface and were
left as-is.)

## Branded chart export — lumi logo + "Source: lumi HR" footer (2026-06-17)
Reworked the PNG export footer (charts.js exportCardPNG) from a plain grey line
("lumi people analytics benchmark · …") to a proper branded attribution per
lumi_brand_kit/LOGO_STANDARDS.md: a hairline separator, the **lumi horizontal logo**
bottom-left (navy mark #2048B0 + coral "you" dot #F08C6E + ink wordmark #243642), and
**"Source: lumi HR · {window} · generated {date}"** bottom-right. The logo's inner SVG
markup (from web/lumi_horizontal.svg) is inlined as a constant (LUMI_EXPORT_LOGO) and
scaled into the footer in the SAME export SVG — one render pass, no second image load,
no canvas-taint risk (toDataURL stays clean). FOOT_H 26→46 to carry the logo at the
24px-floor min size. Applies to every downloadable chart (cards + metric page) since
both go through exportCardPNG. Cache v177→v178. Verified in preview: captured the export
SVG markup (Source: lumi HR + all three brand hexes + separator present, old text gone)
and rendered it visually — logo + attribution sit clean in the footer; export returns
"downloaded"; no console errors.

## Ask lumi → a real guide: find metrics · explain terms · platform help (2026-06-17)
Expanded "Ask lumi" from a benchmark-only analyst into a four-intent assistant, WITHOUT
touching the trust-critical cited-analysis path. New server/guide.py holds a plain-English
GLOSSARY (superset of core.js), a platform FEATURE knowledge-base (add data, peer groups,
dashboards, chart download, signals, strategy, board pack, pulse, suppression, request a
metric, methodology, glossary, team, settings, getting started — each with its in-app route),
and a heuristic intent classifier. /api/analyst now routes:
 • benchmark (default) → the existing strict, cited analyst (unchanged — still the only path
   that ever sees peer figures);
 • find → retrieval over the metric CATALOGUE (names/areas only, never values) → clickable
   metric chips; de-pluralises a missed query ("pensions"→"pension") and applies the same
   distinctive-coverage gate so uncovered topics ("submarines") route to "Request a metric";
 • term → the glossary definition + an "Open the glossary" link;
 • help → the matching feature answer + a link to that page.
For find/term/help, claude_api.guide_answer (new GUIDE_SYSTEM) phrases it warmly when the
model is configured; otherwise the deterministic glossary/feature copy ships. The guide path
is handed NO peer data, so it structurally cannot fabricate a figure — and is told to send
benchmark questions back to the cited analyst. Also: added metric/metrics/data/figures/etc.
to retrieval.GENERIC so generic words don't fake topic coverage; chips suppressed for term/help
(retrieval matches there are noise); starters now mix gap-based benchmark Qs with guide examples.
Frontend: broadened the opening message + placeholder + button tooltip, render the new `links`
as navy-outline buttons. Cache v178→v179. Verified end-to-end in preview (deterministic path,
key not configured): all four intents classify + answer correctly, find chips/term defs/help
links render, uncovered topics fall back to request, benchmark path returns its cited readout
unchanged, no console errors.

## QA sweep — post (dashboards / chart-download / branded export / Ask lumi) (2026-06-17)
Ran the runnable quality bars (HTTP-based scripts need a server in the Bash sandbox, since the
preview server lives in a separate namespace). All LOGIC/INVARIANT bars green after this session's
work: qa_hero 58/58, qa_strategy 14/14, qa_focus 28/28, qa_signals_system 9/9, qa_notifications 22/22,
qa_ordered_routing 17/17, qa_scores 3/3, qa_pulse & qa_release 0-fail, qa_status_audit ZERO mismatches.
Fixed one STALE test: qa_focus expected by_section to carry all 7 categories, but the market-position
re-axis deliberately carves Governance out of the competitiveness headline (positions.py:913) — updated
to the 6 competitive categories. Pre-existing, NOT-this-session items left flagged: qa_commentary 37/40
(3 fails in a validator edge — fabricated 'you' on an unanswered metric; claude_api.py change this
session was purely additive (guide_answer), 0 lines touched the commentary validator); qa_integrity /
qa_engine_audit demo-data drift (DB vs seed CSV: REW_FAI_128, ALLOW_02 select n 220↔221, a p25 rounding
3.2750↔3.27) — this session never writes answers, so it's prior demo-data manipulation, reconcilable by
re-running the snapshot. Each shipped feature was also verified live in the preview during its build.

## Code review (this session's diff) + fixes (2026-06-17)
Ran a high-recall review (4 parallel finder angles + verification) over the dashboards / chart-download /
branded-export / Ask-lumi-guide diff. Fixed the confirmed correctness findings; cache v179→v180.
1. **Stale dashboard cards on peer-filter change** (pages.js, highest sev): the cards cache key (slotKey) was
   cut-independent, so changing the global "Comparing against" filter never refetched — dashboard charts kept the
   old cut's numbers while the rest of the app updated. Fixed with a cut-aware `cardKey = slotKey + cutKeyOf(cut)`.
   Verified: switching All peers→sector took the 3 cards n=98/175/213 → n=4/11/15·sector. (Inherited from the old
   MyViewPage; fixed in the rewrite.)
2. **Classifier misroute — "can i see our pay gap"** (guide.py): bare "can i"/"could i" matched _HELP, sending a
   benchmark-data request to the guide. Qualified them with a how-to verb; "can i see our pay gap" now → benchmark.
3. **Bare "help" dead-end** (guide.py): "help" hit the strict analyst → "lumi doesn't benchmark that". Added a
   _HELP_BARE whitelist (help / i need help / what can you do / getting started…) → now routes to the guide.
4. **First-visit bootstrap race** (app.py _ensure_dashboards): check-then-insert with no (org_id,user_id) uniqueness
   could seed two "My dashboard" rows when the app-shell + page both GET /api/dashboards. Made the seed INSERT
   idempotent (… SELECT … WHERE NOT EXISTS); active pointer left to _resolve_active.
5. **Escape-while-renaming** (pages.js): Escape unmounted the input, whose onBlur still committed the typed name.
   Added a cancelRename ref so Escape discards.
6. **De-pluralise over-stem** (app.py): the find-retry regex turned "allowances"→"allowanc" (no match). Replaced
   with an English-plural singulariser (allowances→allowance, bonuses→bonus, process→process).
7. **Wasted retrieval for term/help** (app.py _guide_response): the full-catalogue scan ran for every intent though
   chips only show for find. Gated retrieval behind intent=='find'.
Left as noted (not bugs / lower value): KebabMenu flip-up (verified correct in preview, REFUTED); "Save as team
default" only seeds new members (honestly labelled in the title); legacy /api/myview surface + a few DB round-trip
micro-optimisations. All re-verified live; no console errors.

## Marketing front page + app moved to /app (2026-06-17)
Added a public marketing landing page (web/marketing.html) and made it the front door at "/"; the
SPA app now serves at "/app" (its "Log in" target). marketing.html is self-contained (own inline CSS,
links the brand fonts.css, uses /static/lumi_horizontal[_reversed].svg and the brand palette) — hero
with a product-glimpse card, trust strip, 4 feature cards, 3-step how-it-works, trust principles, a
navy CTA band and footer; reduced-motion-safe scroll reveals. Every CTA ("Log in", "Get your benchmark",
"Log in to lumi") points at /app. **No backend link changes needed:** marketing.html runs a tiny head
script that bounces any incoming app-route hash (`/#/reset/…`, `/#/invite/…`, `/#/overview`, `/#/settings`
from emails/invites/resets) to `/app` + hash, so all existing console-logged + emailed links keep working.
app.py: GET "/" → marketing.html; new GET "/app" → index.html; /share/{token} unchanged. The SPA is purely
hash-routed (only share.js reads pathname, and /share is untouched), so serving index.html under /app is safe.
Verified in preview: "/" renders the marketing page, Log in → /app shows the auth screen, and /#/overview
redirects to /app#/overview; no console errors. NOTE: the demo app is now reached at http://localhost:8060/app.

## Card → "Add to dashboard" picker: choose existing or create new (2026-06-17)
Replaced the single "Pin to dashboard" kebab item (which silently toggled the ACTIVE dashboard)
with an in-popover picker: a back header, a checkbox row per dashboard (✓ = card is on it; click
toggles), and "＋ New dashboard…" with an inline name input that creates a dashboard already holding
the card. Cache v180→v181. Backend (app.py): list_dashboards gained `?card=<qid>` → per-dashboard
`has_card`; new `POST /api/dashboards/{id}/toggle-card` (add/remove on a SPECIFIC dashboard, shared
`_toggle_card_layout` helper with /pin); create_dashboard gained `with_card`. Frontend (card.js
KebabMenu): a `view` state ("main"/"dash"), reuses the flip-up/max-height logic (deps now include
view/dl/creating so it re-measures), optimistic toggles, toast feedback. Cross-surface sync via a
`lumi:pins-changed` window event — app.js refreshes the global star set, DashboardsPage refreshes its
tab counts + active grid without a full card-refetch. The old global pin-star path (/api/dashboards/pin)
is retained but no longer the kebab's affordance. Verified end-to-end in preview (app now at /app):
?card membership, create-with-card, toggle on/off, and the UI picker (toggle existing + create new,
both reflected as checked) all work; no console errors; demo state restored to My dashboard:3.

## Kebab menu cut-off on short viewports — flip threshold + scroll affordance (2026-06-17)
The card "⋮" menu still read as "cut off" on short viewports (e.g. an embedded/Retina pane ~500–560px
CSS height): the ~474px menu clamps to the available space and scrolls, but macOS auto-hides the
scrollbar so the truncation looked like a hard cut, not "more below". Two fixes (card.js + app.css,
cache v181→v182): (1) smarter flip threshold — `up = below < want && above > below` (was capped at a
240px below-threshold), so a card anywhere in the lower viewport now flips its menu UP to stay fully
on-screen; verified a lower card flips up (top 8 / bottom 432, fully visible). (2) An unmistakable
"more below" affordance on `.kebab-menu`: pure-CSS scroll-shadows (a soft shadow appears at the
top/bottom edge only when there's content to scroll there) PLUS a forced thin styled scrollbar
(::-webkit-scrollbar + scrollbar-width). On a 560px viewport the menu now clamps, fits the viewport,
scrolls, shows the shadow + scrollbar, and every item (incl. Download / Copy link / Add to dashboard)
is reachable (verified lastItemReachable). No console errors.


## Card actions: ⋮ menu → compare-against pill + icon buttons (2026-06-17)
The single kebab menu kept reading as cut off on short viewports (too many items in one popover).
Replaced it (card.js KebabMenu removed) with discrete controls in a .card-tools cluster on every
benchmark card header: a **compare-against pill** (people icon + current peer-group label + chevron;
highlights when the card overrides the page cut) and five quiet **icon buttons** — open full view
(maximize), question & definition (info), add to dashboard (pin → the multi-select picker popover),
download chart (download), copy link (link). A shared usePopover() hook holds the open/flip-up/
outside-close/clamp logic; ComparePill and AddToDashboard each render a SMALL focused popover
(peer list / dashboard picker) that can't overflow like the old combined menu. The popovers reuse
the .kebab-menu styling (scroll-shadow + flip) as a safety net. Cache v182→v183. Verified across 206
cards: pill changes the cut (n=220→n=15 sector, pill relabels + shows overridden state), the pin
picker opens (toggle existing / create new), no console errors, old ⋮ fully gone.


## Card controls moved to a bottom footer (2026-06-17)
Per the design call, moved the compare-against pill + action icons out of the card header into a
.bench-foot row pinned to the card bottom: [👥 peer-pill ▾ · n=NNN] on the left, the icon buttons
(open / definition / add-to-dashboard / download / copy-link) right-aligned. The header is now just
title + signal flag. This also removed a redundancy — the peer pill and the old "n=NNN · {cut}" line
both stated the peer group; now the pill is the peer label and n is just the count (cutNote dropped from
the n line). CSS: .bench-foot { margin-top:auto } pins it to the bottom (consistent 25px above the card
24px padding across all heights); .card-tools { margin-left:auto }. Cache v183→v184. Verified: header =
title+flag only, footer = pill·n + 5 icons on one row (pill left, icons right), pill still drives the cut
(n=220→n=30, relabels), picker unchanged, no console errors. Note: preview native viewport is 228px wide
(why screenshots mini-scale) — resize the preview to a desktop size before screenshotting.


## QA of card footer controls + dashboards collision fix (2026-06-17)
Drove every footer control in the preview. PASS: compare pill (opens, 5 peer options + page tag + active
check, changes the cut → n/label/overridden-highlight update, Escape + outside-click close, opening another
popover closes it); Open full view → /metric/{id}; Question & definition → modal; Add to dashboard → picker
(toggle existing + create new); Download → exports; Copy link → clipboard (no error). a11y: every control has
aria-label + title; popovers close on Escape. Export gating correct — a FULLY suppressed card (.suppressed-box)
hides Download + Copy link but keeps open/define/add-to-dashboard.
IMPROVEMENT FOUND + FIXED: on My dashboards the resize(1×/2×)+drag(⠿) overlay was absolutely positioned
bottom-right — directly over the new footer download/copy icons (verified rect collision). Added a footTools
prop to BenchmarkCard; DashboardsPage now passes resize+drag through it (rendered in the footer card-tools
with a .tool-div divider) and the absolute overlay is removed. Verified: overlay gone, footer = [pill·n] …
[2× ⠿ | ⤢ ⓘ 📌 ⬇ 🔗], resize still toggles width, no console errors. Cache v184→v185.


## QA of the metric (expanded) page + reconciled the position pill (2026-06-17)
QA of /metric/{id}. PASS: back button; peer-group select (cut changes, n updates 199→12 sector); chart-type
switch (Percentile band / Histogram / Box plot re-renders); exact-figures strip; Generate commentary (4-part
deterministic); What-this-means open by default; Download / Copy link / Request buttons; clean layout.
ISSUE FOUND + FIXED — contradictory verdict: the top position pill read "▲ Above market · P20" (driven by the
legacy DB polarity, lower_is_better) while the bottom "How lumi reads this" note said "context · neutral · kept
out of the headline" (driven by mp_config classification.direction=neutral, feeds_gauge=false). The two
classification systems disagreed on the same page. Fix (app.js MetricPage header): when classification.direction
=== 'neutral', show a neutral "Context" pill (pos-pill lg mid) instead of a directional Above/Below-market verdict
— so the headline agrees with the note. The else branch (directional metrics: 62 higher_is_better answered) is
byte-identical to before, so verdicts there are unchanged. Verified: PROP_e63cf45a now shows "Context" at top +
"context" note at bottom (consistent); no console errors. Cache v185→v186. (Preview screenshots mini-scale after a
force-fresh reload — a stop/start cycle fixes it.)


## Intelligent metric-page narrative + commentary/pill reconciled to the firewall direction (2026-06-18)
Made the expanded-view AI commentary a genuine four-part narrative (what the metric IS · how you compare ·
implications for your org · options to weigh) and resolved a deeper cross-system inconsistency.
RICHER NARRATIVE (claude_api.py): _measures_text frames the definition in plain English — strips auto-generated
scaffolding prefixes ("Categorical response describing:" ×184, "Matrix response capturing…", "Binary indicator…",
de-colons "The frequency of:" leads), turns it into "This metric asks: …" when it's a question, and appends the
domain + how it's expressed (figure / yes-no / one-of / options / by-level). _deterministic_commentary gained a
no-direction branch (prevalence framing, with a neutral peer-median "for context… not a target" line) distinct
from the directional ahead/behind/in-line branch.
DIRECTION RECONCILIATION (the substantive fix): the commentary stance + the metric-page position pill now read
the SAME firewall-reviewed market_position_config direction the gauge + "How lumi reads this" note already use —
NOT the legacy DB polarity, which can disagree. build_commentary_payload derives stance from config direction
(neutral / Practice / Design → None → prevalence; higher/lower → _commentary_stance; unclassified → DB polarity
fallback). cardPosition (card.js) prefers c.classification.direction when the card carries it (single-metric page
only — tiles/dashboards don't attach classification, so they're untouched). The pill shows "Context" for neutral
AND Approach (Practice/Design) metrics. Net: REW_INC_070 (config lower_is_better, DB higher_is_better) was a
three-way contradiction — pill "▼ Below market", note "favourable when low", commentary "behind" — now all agree
"ahead / favourable" (verified in preview: ▲ Above market · P19 + "favourable when low" + "a real strength").
PROP_e63cf45a + ALLOW_01 verified Context+prevalence. CACHE: metric_commentary is a persisted DB cache keyed on
the payload hash, which can't see generator-only edits; added claude_api.COMMENTARY_GEN_VERSION folded into the
hash (self-invalidates on generator changes) and cleared 46 stale rows. qa_commentary: the old "behind" example
(PROP_d16bae79) is now firewall-neutral, so it's prevalence-framed — repointed the test to OT_04_b14623a6
(higher_is_better, this org behind at P20); 40/40 green. Cache v186→v187.


## Chart review fixes — contrast, colour-blind verdicts, honest format types (2026-06-18)
Acting on a format-type + colour review of the chart library (charts.js / chartAlternatives).
1. CONTRAST — the categorical peer bars used --cat-5 (#D2DAEE = 1.4:1 on the white card, below the
   WCAG 3:1 non-text minimum — the actual peer distribution was the faintest ink on the card). New
   token --chart-cat (#8598CF = 2.84:1) for OptionBars + OrderedDist peer fills; the You accent stays
   dominant by hue (cat vs you 2.8:1, vs green/red stronger) reinforced by weight + label. Zero-count
   ordered bars nudged 0.45→0.5 opacity.
2. COLOUR-BLIND VERDICTS — the You marker's only good/bad cue was favourable-green vs unfavourable-red
   (luminance ratio 1.08:1 — indistinguishable in greyscale/deuteranopia). Added favGlyph(fav) → ▲/▼,
   mirroring the position pill, to YouDot (band/histogram/box/grouped-matrix) and the categorical
   "· You" label. Verified: REW_INC_070 "· You ▲", ALLOW_02 "· You ▼". Neutral = no glyph.
3. HISTOGRAM availability — chartAlternatives offered "Histogram" for every numeric, but the payload
   only carries bins when raw _values exist, so switching on a banded numeric rendered blank. Now gated
   on card.histogram.bins.length > 1; numerics with bins keep all three (verified PROP_e63cf45a:
   Percentile band / Histogram / Box plot).
4. YES/NO IS NOT A SCALE — yes_no rendered as the ordered distribution (ordinal rail). A TRUE binary
   (≤2 real options) now renders as plain bars, no rail (verified REW26_WEL_EAP: 0 rail lines). But 18
   of 28 "yes_no" metrics actually carry a middle/partial state (Yes/No/Partially/In development/…) —
   those keep the ordered distribution (verified ALLOW_02: rail + 4 dots), so the gradient still reads.
No console errors; no chart-specific QA suite exists (visual + DOM-asserted in preview). Cache v187→v189.


## Gauge made stance-aware + cat-ramp de-ramped (chart review, round 2) (2026-06-18)
Two follow-ups from the chart review.
A) CAT RAMP — the "--cat-1..6 blue-rooted distribution ramp" was monochrome in practice: only cat-1
   (quartile-dot density base) and cat-3 (.tile-fill) were ever used, and a CAT_COLOURS array in charts.js
   was dead. Removed the dead array, renamed the two live picks to honest tokens (--quartile-fill,
   --chart-cat — .tile-fill folded onto the same #8598CF as the bar fill), pruned --cat-2/4/5/6, fixed the
   token-legend comment.
B) GAUGE COLOUR — the hero arc coloured "above market" RED (premium/overspend) while every per-metric pill
   colours "above market" GREEN (more competitive) — a cross-instrument contradiction (drilling from a red
   "Above" gauge showed green "Above market" metrics). David chose to make it STANCE-AWARE: the verdict now
   reads as ALIGNMENT with the org's declared reward-strategy stance, not an absolute cost flag. Shared
   helper marketTone(band, aim) in pages.js (aim: lag→below / match→on / lead→above): a band ON the aim is
   green (on target), short of it red (a gap), past it amber (further than intended); NO stance set →
   neutral (the gauge makes no good/bad claim until a target is set) + a "Set your reward strategy…" nudge
   button. Applied to BOTH the hero OverallArc (bands + verdict word, word by alignment behind→red /
   on_target→green / ahead→amber) AND the per-category CategoryTile on the same home page (chip class,
   v-border, bar segments — all via the shared marketTone), so the two can't disagree. Verified all three
   stances in preview: lag (below=green/on=amber, demo default), lead (above=green — the leader case the
   old code got wrong), none (neutral grey + nudge); hero and tiles agree in every case; no console errors.
   Removed dead .cbs-* CSS + an unused `col` in CategoryTile. qa_hero 58/58, qa_strategy 14/14 (backend
   untouched — change is frontend-only). Cache v191→v192.
   FOLLOW-UP (not done): the category-DETAIL page market verdict (pages.js ~MarketPill / the detail `col`)
   and the server-rendered board-pack/share still use the absolute below/on/above lens — they're on other
   views (not side-by-side with the hero), so consistent within themselves, but would need the same
   marketTone treatment for full app-wide stance-awareness.


## Stance-aware market colour extended to all live surfaces (chart review, round 3) (2026-06-18)
Propagated the stance-aware marketTone (gauge/tiles) to the remaining market-position surfaces so the
whole app shares one colour language. Found the surfaces had actually drifted into TWO base lenses before
any stance: the per-category DETAIL page used the cost lens (above=red) while MarketPill used the
competitiveness lens (above=green) — they already disagreed. Routed both through the shared marketTone.
 - CategoryPage detail band (chip + cat-band dot): now coloured by marketAim(ov.hero.market) — verified in
   preview with the demo's lag stance: Incentives (above market) reads AMBER (crept past the lag aim, was
   red under the old cost lens); Benefits (below market) reads GREEN (on the lag aim, was amber). Matches
   the hero gauge + tiles exactly.
 - MarketPill: made stance-aware too (MKT_PILL tone→pos-pill kind + a new .pos-pill.context neutral
   variant), removed the now-unused MARKET_KIND. NOTE: HeroSignals/MarketPill turn out to be DEAD CODE
   (defined, never rendered — superseded by OverallArc); the change is harmless/forward-consistent but not
   user-visible. Flagging for a future delete (would also orphan MARKET_LABEL/MARKET_ARROW/PrevLine).
 - Board pack / share: render NO coloured market verdict (text/narrative only — grep of share.html/share.js
   clean), so nothing to recolour.
 - OUT OF SCOPE (noted, not changed): the methodology "Where you stand" legend (#market-position) is a
   static colour KEY for the per-metric convention (below=amber/above=red) and predates this work — it
   already disagreed with the per-metric pills (above=green). That's a separate content/semantics decision.
Per-metric pills (card.js) stay factual competitiveness by design (a single metric above market IS more
competitive) — a deliberate two-level model: per-metric = factual, aggregate = strategy-aligned.
No console errors; qa_hero 58/58, qa_strategy 14/14 (frontend-only). Cache v192→v193. Demo stance restored to lag.


## Removed dead HeroSignals/MarketPill cluster (2026-06-18)
Deleted the orphaned predecessor hero (superseded by OverallArc): HeroSignals + MarketPill + PrevLine +
MARKET_LABEL/MARKET_ARROW (pages.js, ~52 lines) and their now-unused CSS (.domain-rows/.domain-row/
.domain-name/.domain-prev/.prev-line + the .pos-pill.context variant I'd just added for MarketPill). Also
dropped the now-orphaned MKT_PILL map (MKT_SOLID stays — it's live on the category-detail band). Verified:
grep clean for every removed symbol/class, app boots at v194 (gauge + 7 tiles render, stance-aware chips
intact), no console errors. Cache v193→v194.


## AI commentary: real Claude API integration via the official SDK (2026-06-18)
The "Generate commentary" feature only ever showed the deterministic fallback because call_claude
used raw httpx against a DEPRECATED model (claude-sonnet-4-20250514) and, with no ANTHROPIC_API_KEY,
silently 401'd → fallback every time. Migrated server/claude_api.py to the official `anthropic` Python
SDK (added server/requirements.txt; anthropic==0.109.2 on py3.9):
 - call_claude() now builds an anthropic.Anthropic() client lazily (None when no key → callers still get
   the deterministic, clearly-labelled narrative — never a fabricated number), defaults to MODEL
   claude-opus-4-8 (env ANTHROPIC_MODEL override), adaptive thinking on by default, output_config.effort
   dial, typed error handling (AuthenticationError / APIStatusError).
 - Commentary now uses STRUCTURED OUTPUTS (output_config.format json_schema = the 4 required string
   parts) → the "model returned non-JSON" path is gone; validate_commentary still gates groundedness, so
   a bad model answer falls back deterministically. max_tokens 700→4000 (adaptive thinking counts toward
   the cap). Board pack 3000→8000 (effort high), analyst 1200→6000, guide 600→1500 (thinking off — quick
   Q&A). COMMENTARY_GEN_VERSION bumped (v3) so cached deterministic rows regenerate once a key is added.
VERIFIED (no key here): module imports, no-key call_claude → graceful {ok:False}, mock confirms the call
shape (model claude-opus-4-8, thinking adaptive, output_config {effort,format json_schema}), qa_commentary
40/40, server boots + endpoint serves deterministically. The LIVE model path needs ANTHROPIC_API_KEY set
in the server's environment (LUMI_AI_COMMENTARY already defaults on); not testable here — user supplies the
key. Cost note: Opus 4.8 + thinking ≈ a few cents per on-demand, cached commentary; pin ANTHROPIC_MODEL=
claude-sonnet-4-6 / claude-haiku-4-5 to trade quality for cost.


## AI commentary "always on" via server/.env.local loader (2026-06-18)
Added _load_local_env() at the top of app.py: on startup it reads server/.env.local (git-ignored; template
in server/.env.local.example, .gitignore updated) and fills any unset env vars — so ANTHROPIC_API_KEY is
present however the server is launched (terminal, preview runner, process manager) without a manual export.
A real env var always wins; a missing/malformed file never blocks boot. Verified end-to-end: with the key
only in .env.local (no export), the restarted :8060 server returned SOURCE: model on a forced commentary
(ALLOW_04 — grounded prevalence framing, validator passed). Live AI path now confirmed working with the
official SDK + Opus 4.8. Operational note: the founder created the key locally; two earlier keys were pasted
into chat and must be revoked (the working key lives only in the local file).


## Fix: garbled AI commentary on awkward option labels (2026-06-18)
Live commentary on REW_BEN_FAM_006 (unanswered; option "No (statutory unpaid only)") showed garbage —
compare truncated to "...is o\" and implications/considerations = "placeholder". Root cause: the model
INTERMITTENTLY mangles JSON escaping when reproducing the smart-quoted, parenthetical option label,
emitting a literal \n that decodes to a newline (turning "No" into "⏎o"). validate_commentary passed it
because it was technically grounded (no bad numbers/words), so gibberish shipped. Three-layer fix in
claude_api.py: (1) validate_commentary now REJECTS any part containing a control char / backslash /
"placeholder"/"lorem ipsum" — clean single-line prose never has these; (2) generate_metric_commentary
retries the model ONCE on a rejected/non-JSON attempt before falling back, recovering intermittent
glitches; (3) COMMENTARY_SYSTEM now instructs plain single-line prose, no escape sequences, option names in
plain words (not extra-quoted). Cleared the metric_commentary cache (8 rows incl. the corrupt one);
COMMENTARY_GEN_VERSION → v4-malformguard. Verified: malformed-gate unit test (clean pass / newline,
backslash, placeholder all rejected); 3 consecutive live force-regens of REW_BEN_FAM_006 all clean grounded
model output; qa_commentary 40/40 (deterministic). Note: app._load_local_env makes the key available to any
script importing app, so qa_commentary now hits the live API unless run with ANTHROPIC_API_KEY='' — used
that to keep the gate fast/deterministic.


## NEW FEATURE: Reward strategy check (AI strategy-execution diagnosis) (2026-06-18)
"Are you delivering your own reward strategy?" — the highest-value AI surface because only lumi holds
INTENT (org_strategy) + REALITY (per-domain market verdicts) + the £ opportunities together.
FIREWALL ARCHITECTURE (the key trust decision): the FINDINGS are computed deterministically in
server/strategy_diag.py (compute_findings) — for each competitive domain it derives the implied aim from
the org's stance (lag/match/lead) shifted by reward_mix (benefits→Benefits lead/Pay lag, cash→Pay lead) and
pay_for_performance (strong→Incentives lead, egal→lag), compares to the actual verdict → on-plan / gap
(short of aim) / over (past aim, overspend), attaches the £ rolled up by q.sub_power, and ranks by the
primary objective (cost lifts overspends, attract/retain lift gaps). The MODEL only narrates those findings
— it cannot invent a gap, domain or number. claude_api.generate_strategy_diagnosis (Opus 4.8, structured
outputs DIAGNOSIS_SCHEMA, adaptive thinking, retry-once) → validate_diagnosis gate: payload-only numbers
(with £ rounding tolerance), exact finding count + order (no add/drop), malformed-text guard, directive/legal
bans. No findings → deterministic 'on plan' affirmation, no API call. Deterministic narrative is the floor
(works with no key). Route POST /api/strategy-diagnosis (require_user; gated on strategy completed + insights
unlocked + LUMI_AI_STRATEGY default on); on-demand (no persistent cache v1). Frontend: StrategyCheck card on
the Overview (pages.js, after the category tiles, shown when strategy_complete && !locked) — Run/Re-run
button, summary + ranked {headline,detail,option} findings, AI badge + "not advice" caveat. Verified live:
demo org (lag/control-cost) → "most areas hold the line; Incentives and Pay running hotter than a lag stance
intends", grounded (15 of 25, 5 of 12). New gate qa_strategy_diag.py 21/21 (engine logic + adversarial
validator). qa_hero repointed (the section-7 .prev-line/PrevLine check moved to prevDonut, which replaced the
retired dead cluster) → 59/59. qa_commentary 40/40, qa_strategy 14/14. Cache v194→v195.

## Reward strategy check → relocated onto Signals page with domain signposting (18 June 2026)
Moved the AI "Reward strategy check" (strategy-execution diagnosis) OFF the home dashboard and onto the
SIGNALS page, headlining it above the triage tabs (gated unlocked + strategy_complete). Rationale: the
diagnosis is the narrated synthesis of the very flags the Signals page lists row-by-row ("ordered for your
<objective> strategy"), so narrative-on-top + granular-signals-below is one coherent page — and only there
can each finding SIGNPOST to its signal group on the same scroll. Dashboard returns to at-a-glance (gauge +
categories + lead/gaps). Mechanics: server route zips each computed finding's domain (`area`) onto the
narrated findings (validator guarantees 1:1 order, so positional; firewall intact — domain is engine-derived,
never model-invented); StrategyCheck takes onGoToDomain → SignalsPage sets tab=inbox/posF=all/groupBy=domain
+ jumpTo, a useEffect smooth-scrolls (block:start) to `#sig-dom-<Domain>` and flashes it (.sig-group-flash,
scroll-margin-top = brandbar+28 to clear sticky chrome; reduced-motion respected). FIXED an earlier collision:
the card class `.strat-check` clashed with the success-tick circle (52px, border-radius:50%) from the capture
flow → renamed `.strat-diag`. Verified live: demo org (lag/control-cost) → 2 findings (Incentives above /
Pay on-market vs below-market intent), each signposts; "See the Incentives signals" lands the group at top
(rectTop 84, in view). qa_strategy_diag 21/21, qa_hero 59/59, no console errors. Cache v196→v199.

## Strategy check: on-plan reassurance + Signals-page integration (18 June 2026)
Two follow-ups to the relocation. (1) ON-PLAN REASSURANCE: the diagnosis now covers the WHOLE board, not just
what's pulling against strategy. Server returns `on_plan` (engine-derived competitive domains tracking their
aim — not model output) alongside parts; StrategyCheck renders a quiet "On plan: <domains> — tracking the aim
you set." line under the findings, each domain a signpost too. Signposts (findings AND on-plan) now gate on a
`signalDomains` set (domains with ≥1 live signal) so a jump never lands on nothing. (2) INTEGRATION with the
home dashboard: brought the home's aurora glow (.ov-aurora) behind the Signals page hero region, and gave the
strategy check the same hero-card treatment as the home cards — elevated shadow + inset top-light + ov-rise
animation + cursor spotlight (.card-spot) — so the two surfaces read as one product. Added a .sig-head-note
("are you delivering the strategy you set?") matching the home signals card's voice; kept the "we flag, you
decide" framing. Verified live: 2 findings (Incentives/Pay) + on-plan line (Benefits·Recognition·Wellbeing·
Time Off), every signpost lands at rectTop 84 (below brand bar). qa_strategy_diag 21/21, qa_hero 59/59, no
console errors. Cache v199→v200.

## Signals page: migrate position colours to the home's stance-aware palette (18 June 2026)
The Signals summary bar + chips + per-row tags coloured market position ABSOLUTELY (below=amber, above=RED,
differs=purple) while the home dashboard colours it by ALIGNMENT with the org's declared stance (on aim=green,
past it=amber, short of it=red; no stance=neutral). So a lag/control-cost org saw NO red on home but red all
over Signals — the surfaces spoke different colour languages. Migrated Signals to the same palette: posTag(s,
aim) and a new posColor(k, aim) both run the home's marketTone(position, aim); the bar segments, chip dots and
row tags now read green/amber/purple. Diagnostic on the demo (lag) org: all 14 "above market" signals are
higher/substance (the stance axis) + 0 lower-is-better, so the migration removes red correctly (over-aim →
amber overspend, below → green on-aim) rather than masking a real problem. Rules kept faithful: Approach
(differs) = purple (no market stance), neutral-polarity = navy context, lower-is-better quality metrics keep
their intrinsic green(below)/red(above) direction (none in this org). Hints now read "on/past/short of your
aim". Removed the absolute classes (.pos-below/on/above/differs/fav, .sig-tone-substance/fav) — no other
refs. Verified live: bar green(29)/amber(14)/purple(26), redCount 0 across bar+dots+tags; filters + group-by
still work. qa_hero 59/59, qa_strategy_diag 21/21, no console errors. Cache v200→v201.

## REVERSED stance-aware colour → direction-corrected absolute RAG everywhere (18 June 2026)
David: across every peer group he never saw a single red. Root cause is structural, not data: stance-aware
colour defined red = "short of the target you set", but the demo org's stance is lag (control cost) — its aim
IS the bottom, so it can never fall short → red was impossible for any lag/ahead org, in every peer group. A
RAG with a colour that can never appear isn't a traffic light. Decision (David): drop stance from the COLOUR,
keep it in the ordering + strategy-check narrative. marketTone(key,_aim) now returns absolute direction-
corrected RAG: below market = red, on market = amber, above market = green (lower-is-better metrics flip in
posTag; differs = purple; neutral = navy). Single function change cascades to the hero gauge bands + verdict
word, the 7 category tiles (MKT_VCLS/MKT_CHIP map tone→colour-correct class; .v-below/.v-at/.v-above NAMES are
now historical, keyed by tone not position), the per-metric distribution, the CategoryPage detail band, and
the Signals bar/chips/row-tags — all consistent. The gauge keeps the stance as a TEXT annotation ("Ahead of
your target — you aim to sit below market") so strategy context survives without tinting the colour. Verified
live: home gauge red/amber/green bands, 4 below-market tiles now RED, redPresentOnHome true; Signals below
market 29 = red, above 14 = green, differs 26 = purple, redNowPresent true; filters/group-by intact, no
console errors. qa_hero 59/59, qa_strategy_diag 21/21. Cache v201→v202. (Supersedes the v200/v201 stance-aware
colour entries.)

## REW_INC_061 retyped single_select → matrix (data-truth fix) (18 June 2026)
David flagged the "Typical individual/business % split of your main bonus" card showing "Not enough data to
show safely · n=1" despite full coverage. Root cause: the metric's ANSWERS are a proper per-role-level matrix
(7 ROLE_LEVELS_V1 rows × banded % per org, 1,540 rows over 220 orgs — labels byte-identical to the option
labels and matching the 26 working ROLE_LEVELS_V1 matrices), but the QUESTION was typed `single_select` with
empty matrix_json. aggregate.py dispatches on type: single_select reads only the base row (matrix_row_id=''),
of which exactly 1 exists → n=1 → suppressed. The engine even had an explicit guard naming REW_INC_061 as a
schema violation to ignore. Fix = correct the definition to match the data (not a judgement call, per David):
set type='matrix', default_chart_type='heatmap', data_display_type='matrix', matrix_rows_json = the canonical
7 ROLE_LEVELS_V1 labels (slugify → the stored row-ids), matrix_json = a select column carrying the 11 banded
% labels (in order) + rows_source ROLE_LEVELS_V1. Market-position-safe: it's class Design / direction null,
so never on the gauge. DB backed up (lumi.db.bak_pre_rew061_matrix_233254). Re-ran aggregate.py (rebuilt all
806 payloads) → per-level rows each n=220 with banded distributions; qa_release.py 0 failures; server
restarted; card now renders the 7-level heatmap (e.g. Board/Executive modal 81%–90% @ 49.1%), no console
errors. Cache v202→v203.

## PROP_7cdfcc7b ("which levels are in formal talent reviews"): separate decision, NOT the matrix fix (18 June 2026)
The same scan surfaced a SECOND type/shape mismatch — PROP_7cdfcc7b (Foresight, multi_select) carries 7
per-level rows (1,176). Deliberately NOT fixed the same way (David): unlike REW_INC_061 its options are
POPULATIONS with a "no formal reviews" escape (not per-level band values), its base answers are blank, and it
is include_in_benchmarking=FALSE — so retyping it to a matrix would be wrong. Left untouched pending its own
decision: confirm intended shape (multi_select pick-the-levels vs per-level Yes/No matrix) and whether it
should benchmark at all. Tracked as a follow-up; no engine/data change made here.

## Many-option bar chart overlapping the card title — grow the card to fit (18 June 2026)
David flagged the "Allowances or premiums currently paid" card (REW_PAY_016, multi_select, 18 options): the
horizontal bar chart bled UP over the title + "No flag" pill. Cause: .bench-chart-full is a fixed-height box
(--chart-h-stack 200px) with justify-content:center and visible overflow. OptionBars' SVG uses a viewBox with
width:100% and NO explicit height, so it renders at its natural aspect-ratio height (~274px for 18 rows); the
intended `max-height:100%` cap was inert because CardBody wraps the SVG in a <div>, so the % resolved against
that auto-height div (= none). The oversized SVG then centred and overflowed upward onto the title. Fix mirrors
the existing matrix-table rule (.bench-chart-full:has(table){height:auto}): OptionBars now tags its SVG
`ob-tall` when usedH > H, and `.bench-chart-full:has(svg.ob-tall){height:auto;justify-content:flex-start}` +
`svg.ob-tall{max-height:none}` let the card grow to fit so every row stays readable and nothing overlaps.
Verified: ob-tall applied, overlapsTitle=false, card grows (788px card → 18px rows, n=215, all 18 options
shown); no console errors. Cache v203→v204. (Row density still scales with card width — a pre-existing trait
of the aspect-ratio SVG, unchanged here; only the overlap was the bug.)

## REW_PAY_020 ("allowances pensionable by level") retired — degenerate, redundant (18 June 2026)
David flagged the card showing an identical 29/71 at every one of the 7 levels. Diagnosis: the metric is a
by-level matrix but the seed copied each org's single org-wide answer (flattened to Yes/No) across all 7 rows
— every level reads 156 No / 64 Yes and ALL 220 orgs answer identically across levels (zero per-level
variation). It's a degenerate derivative of ALLOW_03 ("Are allowances pensionable?"), which already captures
pensionability with more nuance (No 154 · some 42 · all 20 · don't-know 3 · varies 1). Decision (David): RETIRE
REW_PAY_020 rather than fabricate per-level variation. Done the governed way: questions.status='retired',
is_required=0, release_retired='2026.2'; a signed core_changelog row (change_type='retired', signed_off_by
David). visible_questions() filters status='retired', so it left the live core, the cards, and the required
set automatically (denominator 82→81; the sticky-unlock design keeps stamped orgs unlocked). Historical payload
stays in benchmark_snapshots (so old benchmarks still resolve) — no re-aggregate needed (retirement is a
serve-time filter). DB backed up (lumi.db.bak_pre_rew020_retire_130902). qa_release 0 failures; live questions
API + Pay grid confirm the card is gone; ALLOW_03 remains; no console errors. No cache bump (data/governance
only; frontend unchanged at v204).

## Deep per-metric data-integrity sweep — new permanent gate, whole set clean (18 June 2026)
David asked to stop finding bad cards one at a time. Built server/qa_metric_data.py: a deterministic sweep that
reads what each metric ACTUALLY serves (benchmark_snapshots payloads) vs its RAW answers and runs ~15 adversarial
checks per metric — shape (rowed-non-matrix = the REW_INC_061 class; matrix-with-no-rows), silent suppression /
data-loss (served n vs raw orgs, accounting for N/A + non-numeric + unmatched), degenerate distributions
(matrix:identical-rows = the REW_PAY_020 class; single-value / zero-spread numerics; one-answer selects),
value validity (out-of-tolerance, unmatched labels), thin coverage, demo-org "You" gaps, and near-duplicate
concepts (identical options + ≥0.6 wording overlap). Severity CRIT/WARN/INFO; report-only, mutates nothing.
RESULT across all 205 live Reward metrics (and 609 active overall): 0 CRIT, 0 WARN — every live metric serves
the data it holds. The REW_INC_061 retype + REW_PAY_020 retirement cleared the only real faults. One INFO
remains: PROP_930043cc (ethnicity pay-gap cadence) ~ PROP_10d1211d (disability pay-gap cadence) — parallel by
design across protected characteristics, NOT redundant; keep both. Two false-positive checks were corrected
during the build: numeric "data-loss" now accounts for excluded_na (REW26_WEL_BUDGET's 131 N/As are legit), and
the demo-org lookup was pinned to the exact name "Thornbridge Retail Group plc" ("Thornbridge Advisory plc" is a
different seed org). Re-run `python3 server/qa_metric_data.py` (or `--all`) after any future seeding/regen.

## End-to-end UX/UI review — login to logout, new + existing user (18 June 2026)
Walked both journeys with measurement-based auditing (overlaps, horizontal overflow, console health) plus
screenshots. EXISTING-USER journey (Thornbridge, unlocked) — overview, signals, benchmark grid (44 Pay cards,
0 title↔chart overlaps), metric detail (XL), your-data (99% ring) — all clean: no console errors, no overflow,
no broken layout. Sidebar nav correctly reads 205/Pay 44 after the REW_PAY_020 retirement. Fixes made:
1. LOGIN CENTERING (all users): the auth Shell renders the card AND the Terms/Privacy footer as two children of
   .auth-wrap, which was display:flex with the DEFAULT flex-direction:row — so the footer sat BESIDE the card
   and pushed it 89px left of centre. Added flex-direction:column + gap → card centres, footer stacks below.
2. LEAD/GAPS CARD OVERFLOW (narrow/mobile): .chip-label was flex:1 + white-space:nowrap + ellipsis but missing
   min-width:0 (the flexbox truncation gotcha), so labels claimed full content width and the ellipsis never
   fired; combined with the grid items' default min-width:auto, the 1fr "You lead"/"Biggest gaps" cards forced
   the track ~470px wide → horizontal scroll. Added min-width:0 to .chip-label AND .grid2 > .card.
3. MOBILE HORIZONTAL SCROLL: hidden .indic-tip hover tooltips (position:absolute, opacity:0 but display:block)
   and the decorative aurora bleed extended the page scroll width (96px at 390px). Added overflow-x:clip to
   .main (clip, not hidden, so the sticky top bar still pins). Mobile scroll 96px→5px (sub-pixel).
Verified desktop unaffected (grid2 back to 2-col, no scroll, no console errors). New-user login + signup screens
reviewed (signup form clean); the locked/welcome dashboard reviewed via components + prior verification (tasks
#18/#49/#63) rather than creating a throwaway account (policy). KNOWN LIMITATION (not fixed): on phone widths
the top-bar controls (search/Ask lumi/avatar) overlap the page title — the app is desktop-first; a dedicated
mobile top-bar/sidebar pass is the right home for that. Cache v204→v208.

## Surgical coherence reseed applied (18 June 2026, David-confirmed)
Ran reseed_engine.py to inject cross-area coherence into the reward seed WITHOUT moving any top-line: it
preserves every question's marginal (answer counts unchanged) and only RE-PAIRS which org holds which answer,
sorted by a latent reward-maturity score (firmographics + signed sector tilt). Sequence, gated step-by-step by
David: (1) backup — PRAGMA wal_checkpoint(TRUNCATE) + cp lumi.db lumi.db.bak (rollback point, retained);
(2) confirmed 6 inputs present (reseed_engine.py, qa_reseed.py, rew_live_meta.json[206 q], frozen_targets.json,
org_profiles.json[158]+org_profiles_inferred.json[62]); (3) bridge rebuilt LIVE from lumi.db (select distinct
org_id from answers) — all 221 orgs resolve to a latent [0.089,0.947]; 220 carry a profile, the 1 orphan
('Tester' test org) falls to latent() neutral defaults (FTE 0.4/HR 0.45/sector Other) → 0.4412, never dropped;
(4) dry-run: 16,016 reassignments / 153 questions, 178 nominal cells skipped; (5) baseline QA 5/8 (G3 slope
0.035, G4 worst_r −0.228, G9 mean_r 0.017 fail — exactly the coherence gates the reseed targets; the stale
"3/8" in the brief was a pre-recalibration G6/G8 number, confirmed by David). numpy installed (2.0.2) so G4/G9
score — now a runtime dep of qa_reseed.py. After GO: stopped preview + standalone uvicorn (freed lumi.db), ran
--write --confirmed-by-david (16,016 reassignments identical to dry-run → deterministic; REW_BEN_SICK_001
anchored spike to ~66% applied). Post-reseed QA = 8/8: G3 0.035→0.154, G4 −0.228→0.305, G9 0.017→0.073 all
flip to pass; G7_marginals still passes (top-lines intact). Re-ran server/aggregate.py --snapshot 1 (806
payloads rebuilt so cut-level gradients go live), restarted the preview server. Verified: app loads, login OK,
overview renders, no console errors. Visible effect: Thornbridge (Retail, low latent) re-paired to leaner
answers → hero verdict On market → Below (consistent with its profile). Rollback: restore lumi.db.bak if needed.

## REW_BEN_045 (life assurance) — scoring-direction correction (18 June 2026, David-approved)
Whole-benchmark bug, surfaced via the Thornbridge tile diagnostic: the gauge ranked life assurance on an
INVERTED effective score. Cause: the engine flips a metric's scores (100−s) when score_direction=−1, and
_score_direction returned −1 purely because the LAST option was "Not offered" (matches the _NEG "negative-last
⇒ best-first" rule) — even though the options ran 1×→Not offered, not a clean best-first ladder. Net effect:
"4× or more" scored 25 (low) and "Not offered" scored 100 — so the market's LEAST-generous orgs (1×/none) read
ABOVE-market on life assurance and the MOST-generous read below. Backwards for every member, not just the demo.
Fix (clean reorder, NOT a map-only hack): reordered options worst→best (Not offered → 1× → 2× → 3× → 4× or
more) and set option_scores 0/25/50/75/100 — now score_direction=+1 (no flip), effective scores ascend
0→100, and options_json / scoring_config / ordered_scale_routing.scale_low_to_high are all consistent worst→
best. DB backed up (lumi.db.bak_pre_rew045_215556). Re-aggregated snapshot 1 (806 payloads). Verified: gauge
and signal now AGREE — Thornbridge life assurance reads ABOVE (4× vs market median 1×); Benefits tile above
0→1 (verdict still 'below' overall, correctly — its one genuine strength now counts); gauge above 1→2; no
console errors. (Part of the broader score-direction audit: REW_BEN_045 was the one genuine Class-A inversion;
16 Class-A metrics were already scoring correctly. The Class-B promotions are a SEPARATE reviewed change.)

## Class-B promotions — 6 directionless metrics → positioned (18 June 2026, David-ruled per-metric)
Follow-on to the REW_BEN_045 scoring fix. Six metrics that were sitting at score_direction=0 (routed to
prevalence / "differs", never below/on/above) were promoted to POSITIONED by giving them a clean worst→best
option_scores map + na_codes for their N/A options + polarity=higher_is_better, in the same reorder pattern as
REW_BEN_045 (no map-only hacks). All six verified score_direction=+1 (no flip trap) and now produce a
below/on/above position with a real score spread:
  REW262_TIME_SICKDAYONE (No 0 / Yes 100), REW262_PAY_CANCELLEDSHIFT (No 0 / Yes 100),
  REW262_PAY_SHIFTNOTICE (No set 0 / <1wk 33 / 1-2wk 67 / 2wk+ 100), REW_BEN_048 income protection (<50% 0 …
  76%+ 100), PROP_36b990f9 employer pension rate (<3% 0 … 11%+ 100), REW26_BEN_PENSION_MATCH (None 0 … >8% 100).
DELIBERATELY KEPT AS PREVALENCE (David, valence genuinely contested — not promoted): PROP_634adacd (base-pay
increase — bigger raise ≠ generosity, can be inflation catch-up), EXT_REW_GAP_002 + EXT_REW_GAP_007 (recognition
£ value — "non-financial only" is a culture choice, not a low score). And REW_PAY_HOURLY_MIN_1c6e096f is a
DOCUMENTED KEEP-NEUTRAL: a high lowest-hourly-rate reflects workforce mix (no low-paid roles), NOT pay
generosity — promoting it would mislead. (Five B2 Yes/No badges/mechanisms — REW26_BEN_SALSAC, REW26_BEN_PLSA_QM,
REW26_WEL_EAP/FINWELL/SCREENING — also kept as prevalence: rarity tells a truer story than a verdict.) DB backed
up (lumi.db.bak_pre_promote6_220825); re-aggregated snapshot 1 (806 payloads); gauge pool 90→92; app healthy,
no console errors. The 4 banded "More than X / Statutory minimum" metrics (REW_BEN_HOL_001/006, RED_TERM_02/03)
are NOT fixable by a score-map (the direction heuristic can't parse those labels) — held for the route-(b)
engine fallback as a separate reviewed change.

## Route (b) — config-direction-trusts-an-ascending-map score-direction fallback (18 June 2026, David-approved)
The score_direction LABEL heuristic can't read "More than X" / "Statutory minimum" band labels, so 4 graded
metrics with explicit ascending maps stayed at score_direction=0 (prevalence) even though their market-position
config says higher_is_better. Route (b) fixes this generally. THREE parts:
1. ENGINE (aggregate.py _score_direction): after the label heuristic yields 0, if the metric's mp-config
   direction is higher_is_better AND it has an explicit graded option_scores map, treat direction as +1 — but
   ONLY via the MONOTONE-ASCENDING GUARD: seq=[scores in option order, NA excluded]; promote only if
   len(set)>=2 and seq is non-decreasing. A descending/non-monotone/flat map is NEVER trusted (stays 0 ->
   prevalence). New standalone _mp_direction() reader (avoids the aggregate<->positions import cycle; added
   `import json`). Also changed the numeric-band branch's `return 0` to a fall-through so numband-neutral metrics
   reach route (b) too.
2. CONFIG (the guard that makes the keep-prevalence rulings durable): set direction:neutral for PROP_634adacd
   (base-pay increase), EXT_REW_GAP_002 + EXT_REW_GAP_007 (recognition £ value), REW_PAY_HOURLY_MIN_1c6e096f
   (pay floor reflects workforce mix, not generosity). Now route (b)'s higher_is_better gate naturally excludes
   them.
3. NUMERIC-BAND FALL-THROUGH WIDENING — measured population: scanned the full catalogue for metrics the
   fall-through newly routes into route (b) (numband first+last, neutral DB polarity, config-higher, ascending
   map). Found exactly ONE: PROP_634adacd — already in the 4 config→neutral edits. So net-new fall-through
   promotions = 0; no unruled/debatable metric pulled in.
RESULT: route (b) promotes EXACTLY RED_TERM_02, RED_TERM_03, REW_BEN_HOL_001, REW_BEN_HOL_006 (sd 0->+1,
gauge-eligible) and the 4 neutral metrics stay prevalence (verified gauge_eligible False). qa_reseed before AND
after = 8/8 with G3 slope 0.154 / G4 worst_r 0.305 / G9 mean_r 0.073 / G7 all UNCHANGED (promotions don't touch
the reseed coherence). DB+config backed up (lumi.db.bak_pre_routeb_230853, market_position_config.json.bak_pre_
routeb). Re-aggregated snapshot 1 (806 payloads, Thornbridge gauge pool 92->93). App healthy, no console errors.

## Multi-select contradiction fixes — CAR_BN_02 + EXT_REW_GAP_011 (19–20 June 2026, David-signed)
ROOT CAUSE: an "exclusive"-type option ("X only") left selectable inside an ADDITIVE multi_select.
The seed treated it as just another checkbox and co-selected it with the additive criteria, producing
logical contradictions ("Business need ONLY" + Role level + Performance) and implausibly high per-option
rates (every bar 70–84% because the avg org picked ~3 of 4).

PART 1 — CAR_BN_02 "Eligibility criteria for business need company car" (severe: 155/188 self-contradict).
 (a) RELABEL: option "Business need only" -> "Business need" (the "only" was the contradiction class).
     Changed in options_json (label; code stays BUSINESS_NEED_ONLY — internal, 0 external refs) and in the
     188 stored answer strings, in lockstep (multi_block matches token->option by normalised LABEL, so both
     must move together). Confirmed no runtime path keys off the string: BUSINESS_NEED_ONLY has 0 refs
     anywhere; "Business need only" lived only in rew_live_meta.json + historical import CSVs; signal_lenses
     and market_position_config key off QID only. Prevalence card (multi_select, score_direction 0) -> no
     gauge impact.
 (b) RESHAPE to signed marginals (resample to target, re-paired to org latent — same mechanism as the
     anchored spikes; firmographic latent from 220 org profiles). Coherence rules: N/A exclusive; every
     scheme org has a base gate (Business need OR Role level); Performance/Other only as add-ons.
       Business need     83.5% -> 89.9% (target 90)
       Role level        70.7% -> 54.8% (target 55)
       Performance rating76.1% -> 10.1% (target 10)   <- the implausible one David flagged
       Other criteria    77.7% -> 12.2% (target 12)
       Not applicable     1.6% ->  2.1% (target 2)
     avg criteria/org 3.10 -> 1.69. Thornbridge (demo org) set to {Business need, Role level} (was 4-of-4).
     Contradictions 155 -> 0.

PART 2 — EXT_REW_GAP_011 "home-working expenses reimbursed" (mild: 23 contradictions).
 LABEL CORRECTION vs the brief: the exclusive option is "IT equipment only" (an "only"-type), NOT a
 "None"/"don't reimburse" option — "None" was already clean (0 co-selections). Cleared the 23 "IT equipment
 only + positive item" rows by org latent: lower-latent -> {IT equipment only} alone (11 orgs); higher-latent
 -> drop "IT equipment only", keep the broader positive set (12 orgs). Contradictions 23 -> 0. No relabel
 needed ("IT equipment only" alone is coherent).

META: regenerated the CAR_BN_02 + EXT_REW_GAP_011 entries in rew_live_meta.json (options + current_dist) from
the corrected DB so a future reseed cannot reintroduce the bad strings/pattern (0 residual bad combos; CAR
combos collapsed 16 -> 7 coherent sets). Historical response CSVs + lumi_questions.csv left as provenance
(not read at runtime) per David.

SCOPE (why no engine-wide multi-select reseed): a full scan of all 39 active multi_selects found contradictions
in ONLY these two (an exclusive option co-selected with additive ones). The other high-count cards are
"which benefits do you offer" availability checklists where many selections are legitimate. REW_PAY_023
reviewed and deliberately LEFT as-is (soft but not broken, David's call). So the fix is surgical, not systemic.

VERIFY: re-aggregated snapshot 1 (806 payloads). qa_reseed.py 8/8 BEFORE and AFTER with NO gate movement —
G3 slope 0.154, G4 worst_r 0.305, G7 pass, G9 mean_r 0.073, G2 count 4 all identical (prevalence cards touch
no gate, as predicted). App healthy: shell renders, /api/benchmark/CAR_BN_02 serves 200, no console errors.
Backups: lumi.db.bak_pre_msfix_20260620_000012, rew_live_meta.json.bak_pre_msfix_20260620_000012.

## Release 2026.3 — 38 reward questions shipped via the COHERENCE ENGINE (20 June 2026, David-signed)
38 new REW263_* questions (Governance/Pay/Benefits/Incentives/Recognition/Wellbeing/Time-Off; all
unscored/optional, category=practice, release_entered=2026.3). Catalogue rows + 38 core_changelog
'added' entries + 8,360 answer rows (220 non-Tester orgs x 38, matching the REW262 org set).

METHOD (the point of the rework): NOT the standalone seed_release_2026_3.py per-org firmographic-flag
draw (apply_tilt+pick) — that gives only coarse coherence and no cross-area latent spine, so the 38 would
diverge from the 206 re-paired in the reseed. Instead, reused reseed_engine.apply_spikes' generate-to-target-
then-latent-pair: per question, NA-route -> exclude N/A -> resample the answering multiset to the kit's signed
dist (largest-remainder) -> pair lean->generous to the SAME latent() ranking the reseed used. Kept from the
kit: signed BASELINES, live-presence NA routing (_PMAP: no_pmi/no_dental/no_fertility, 189/189/174 orgs) and
the DB-grounded NA_PRIOR.

ORDERING: honour explicit `order` first (only REW263_BEN_PMIMH, REW263_BEN_PMIEXCESS — their dist-order !=
generosity, PMIEXCESS reversed); else option_order() (the 3 yes/no, whose dist is Yes-first); else dist-order
(the 28 authored-ascending ladders). 33 anchored, 5 genuinely nominal (SIGNOFF, PENBASIS, POOLFUND,
REC_CURRENCY, WEL_DATA) seeded to marginal with NEUTRAL (latent-independent) assignment — off-spine by design.

RULING #1 (David) — corrected 3 estimated NA priors before seeding, with rationale:
  no_deferral 0.60->0.72 (deferral mostly large-org/FS; 41% present too high) -> realised N/A 71.8%
  no_ranges   0.30->0.42 (formal ranges less universal across hospitality/retail/SME base) -> N/A 45.5%
  no_ci       0.55->0.62 (critical-illness rarer than 47% present implied) -> N/A 63.2%
  Left at draft: no_bonus 0.25, no_recognition 0.20, no_contingent 0.35. Live-anchored (no_pmi/dental/
  fertility) untouched.
RULING #2 (David) — for the 2 workforce-flag questions (SHIFTRIGHTS low_shift, GUARHRSAVG low_frontline),
  orgs with UNKNOWN workforce-mix (63 inferred profiles + Tester) are treated as APPLICABLE (answer to the
  signed dist), not N/A. N/A-by-data-absence reads as "doesn't apply" when we simply don't know. Only
  known-low orgs get N/A -> SHIFTRIGHTS N/A 45%->16.8%, GUARHRSAVG 42%->13.6%.

VERIFY: all 38 served (applicable-based) marginals within tol=0.03 (worst dev 0.011 on TIME_FERTLEAVE);
all 33 anchored hold positive latent correlation (min 0.69 [yes/no], median 0.92, max 0.95); multi-select
REW263_WEL_DATA 0 "None"+positive contradictions (structurally exclusive). The coherence proof:
qa_reseed BEFORE 8/8 -> AFTER 8/8, and G4 worst-pair coherence rose 0.305 -> 0.345 (gate floor 0.30),
G3 slope 0.154 -> 0.166, G9 bundles 0.073 -> 0.105 — the 38 reinforced the spine rather than diluting it.
rew_live_meta.json carries 38 new entries so future reseeds preserve them. Re-aggregated snapshot 1
(844 payloads). App healthy: shell renders, new cards serve 200, no console errors.
Backups: lumi.db.bak_pre_2026_3_20260620_063500, rew_live_meta.json.bak_pre_2026_3_20260620_063500.

## Reward-catalogue cleanup Phase 1 — Wellbeing→Pay reclass (20 June 2026, David-signed)
8 remote-work / location-pay questions were misfiled under the Reward "Wellbeing" sub_power, so a member
filtering Wellbeing saw remote-pay questions mixed in with genuine wellbeing. Reclassed to Pay (display
correction): EXT_REW_GAP_009/010/011 (remote frequency / locations / home-working expenses) +
REW_BEN_REM_PAY_001-005 (pay-on-remote-move / location-set-pay / remote benchmarking / decision-consistency /
remote premiums). Set sub_power='Pay', sub_power_order=1 (Pay's convention) — METADATA ONLY.

ZERO answers moved: all 1,480 answers on the 8 stay exactly where they are (snapshot 1, verified before==after).
There is no sub_power_code column (only sub_power + sub_power_order), so nothing orphaned.

GAUGE: 7 of the 8 are prevalence (mp_config Practice/Design, not gauge-eligible) -> pure display move. ONE,
REW_BEN_REM_PAY_005, is gauge-eligible (class=Level, higher_is_better), so its domain-tile membership moved
Wellbeing->Pay. Demo org (Thornbridge) tile recompute: Pay pool 16->17 (below 10->11), Wellbeing pool 7->6
(below 7->6); both verdicts stay "below" but are now more accurate (a pay metric counted under Pay). The
OVERALL gauge needle is unchanged (same metric in the substance-pool union, different tile).

rew_live_meta.json DELIBERATELY NOT updated. qa_reseed reads sub_power from that file (not the DB), and its
G4 area-coherence groups by [Benefits, Governance, Wellbeing, Time Off, Incentives]; leaving the meta means
the reseed's coherence-area memberships are unchanged. Result: qa_reseed BEFORE==AFTER byte-identical (8/8;
G2 4, G3 0.166, G4 0.345, G5 7, G6 1, G9 0.105 all identical) — proving the reclass moved no answer. (The
reseed models maturity-coherence, which is correctly independent of the display sub_power.)

POST-2026.3 COUNTS: Pay 49->57, Wellbeing 18->10. (David's brief said 52/6, which predated this morning's
2026.3 ship that added 5 REW263_PAY_* and 4 genuine REW263_WEL_*.) The genuine 10-question Wellbeing set
remains: 6 REW26_WEL_* (EAP, MH_SUPPORT, FINWELL, BUDGET, SCREENING, STRATEGY) + 4 REW263_WEL_* (DATA, OH,
MGRTRAIN, FINWELL). Re-aggregated snapshot 1 (844 payloads carry the new subpower); server restarted to clear
load_questions lru_cache; the 8 now group under Pay in the dashboard filter. App healthy, no console errors.
Backup: lumi.db.bak_pre_wellreclass_20260620_070810.

## Matrix coherence — persona-ceiling lift + standing G10 gate (20 June 2026, David-signed)
STEP 0 (read-only) OVERTURNED THE ORIGINAL "third coherence gap" PREMISE: the flagged matrices are already
coherent. PMI/LTI/status-car eligibility matrices are 100% within-org monotone AND latent-ordered (cascade-
depth x latent: PMI +0.93, LTI +0.87, status-car +0.92) with descending per-level rates — the original
coherence reseed re-paired each matrix ROW to the latent spine, which automatically yields monotone latent-
ordered cascades. There was no third gap. Check A's spread<0.5 floor was MIS-CALIBRATED: it read benefit
BREADTH (PMI reaches frontline broadly -> shallow-but-real cascade, spread 0.245) as incoherence.

BASE-SALARY BY-LEVEL IS FLAT BY DESIGN (model confirmed, by-level seniority gradient EXPLICITLY REJECTED):
companies target one market position across all levels (current within-company by-level spread ~1.0pp),
varying by persona BETWEEN companies (latent x company-mean +0.717). An earlier plan to impose a board>frontline
gradient was wrong and was dropped.

THE ONE GENUINE FINDING — TRUNCATED PERSONA RANGE on REW_PAY_MKT_POS_01: capped at exactly 100% (35 below /
112 at / 0 above-market) — no seeded company paid above median, understating premium employers (elite tech/FS
genuinely position above market). FIX = persona-ceiling lift (company-axis, flat-by-level preserved): the top
20% by latent (29 companies) stretched to [102.5, 110] interpolated by latent value; the at-market cluster and
below-market tail untouched; shift applied uniformly to all 7 of a company's levels (by-level spread held at
1.00pp). RESULT: 35 below / 83 at / 29 above (20% above market), range 94.1->110.0, cross-pool average
98.50->99.55 (+1.05, a contained re-base — adding above-market employers that were wrongly capped, not a
balloon), latent ordering STRENGTHENED +0.717->+0.914.

DATA-INTEGRITY FIX (separate from the lift — repairing a typo, not content policy): org 79118679 had
head_of=5 (market position 5%, impossible); corrected to its own across-level median (94.0). This also moved
the range floor from the artificial 81.4 to the true ~94.

GATE: Check A's spread-floor REPLACED by the two properties that actually define matrix coherence, now standing
as G10 in qa_reseed.py and recalibrated in qa_plausibility.py Check A — DIRECTION-AWARE:
  directional within-org monotonicity = max(top-down, bottom-up prefix) >= 0.95
  cascade-depth x latent correlation > 0.30
Direction-awareness is essential: REW_FAI_TRONC_GROUPS (tronc) is legitimately BOTTOM-UP (frontline 100% ->
board 0%), and a top-down-only check false-fails it (reads 0.037 top-down / 0.963 bottom-up). G10 reading:
PMI 1.000/+0.93, LTI 1.000/+0.87, status-car 1.000/+0.92, tronc 0.963/+0.70 -> worst 0.963 (floor 0.95) /
+0.695 (floor 0.30) -> PASS with headroom. So a genuinely incoherent matrix in a future release now fails CI,
without false-failing broad benefits or bottom-up matrices.

VERIFY: qa_reseed BEFORE 9/9 and AFTER 9/9 with every gate value IDENTICAL (G2 4, G3 0.166, G4 0.345, G5 7,
G6 flat 1, G9 0.105, G10 mono 0.963 / depth 0.695) — the lift touched only a numeric positioning matrix, no
coherence gate moved. PMI/LTI/status-car/tronc and all %-opportunity matrices byte-identical vs backup.
Re-aggregated snapshot 1 (844 payloads). App healthy, market-position card serves 200, no console errors.
Backup: lumi.db.bak_pre_personalift_20260620_121431.

## Income protection prevalence fix — REW_BEN_046/047/048 (20 June 2026, David-signed)
A spot-check found REW_BEN_046 ("Does your organisation offer income protection?") seeded at 5.5% offer
(94.5% No) — implausibly low vs GRiD-range UK group income protection (~40-45%). Worse, internally broken:
197 of the 208 orgs answering "No" on the headline carried a real waiting-period answer on REW_BEN_047 (and
194 a real salary% on REW_BEN_048) — the follow-ups were seeded independently and never N/A-routed for
non-offering orgs.

FIX — 046 RESHAPE (judgment estimate, NO REGISTER ANCHOR; GRiD flagged in the source pipeline as the figure to
anchor properly on the next register update): offer ~42% (No 58.2% / Short-term only 8.2% / Long-term only
21.8% / Both 11.8%; LT the largest share, Both a minority, ST smallest). Latent-paired on the generosity
order No<ST<LT<Both -> the 92 offering orgs are higher-latent (offer x latent +0.860), so income protection
sits on the spine (a more-generous benefit skewing to mature employers).

047/048 RECONCILED TO THE HEADLINE: every 046-"No" org (128) routed to "Not applicable / not offered"; the
SAME 92 offering orgs carry the current real-answer SHAPE, latent-paired — 047 waiting period (shorter =
more generous = higher latent, corr +0.934), 048 salary% (higher = more generous = higher latent, corr
+0.942). N/A rate 5.5%->58.2% on 047 and 6.8%->58.2% on 048, matching the 128 non-offerers exactly.
CONTRADICTION (046-No but real 047): 197 -> 0.

SCOPE: the broader benefit-prevalence sweep found this was the LONE genuine outlier. Other low-looking
prevalences — EAP, flexible benefits, health screening — are the CORRECT settled-frozen / register-anchored
values (frozen_targets.json / the 14 REW26_* register set), not errors, and were left untouched.

VERIFY: 046 served 41.8% offer, latent-skewed; 047/048 served N/A 58.2%; contradiction 0; offering orgs'
follow-ups coherent (short-wait + high-% cluster on the same high-latent orgs). qa_reseed BEFORE 9/9 -> AFTER
9/9: G4 HELD at 0.345 (floor 0.30 — income protection joining the spine didn't dent cross-area coherence),
and the spine IMPROVED — G3 size-gradient 0.166->0.187, G9 benefit-bundles 0.105->0.123. G5 high-consensus
ticked 7->6 (still passes floor 6) — correct, since 046 is no longer a wrongly-near-universal "94.5% No".
G10 unchanged (matrices untouched). rew_live_meta.json updated for all three so a future reseed carries the
corrected, consistent pattern. Re-aggregated snapshot 1 (844 payloads). App healthy, all 3 cards serve 200,
no console errors. Backup: lumi.db.bak_pre_incprot_20260620_130132 (+ meta).

---
2026-06-21 — SIGNAL COLOUR/VERDICT FIX (home + Signals page; frontend #1 + backend #2). David flagged
the live overview rendering BACKWARDS colour semantics: deficiencies (EV charging reimbursement, Relocation
support) showed as GREEN cards, an approach metric (Pay review frequency) as purple. Two causes, two fixes.

#1 FRONTEND (web/js/pages.js + app.css, cache v208->v209): the home "Signals · top 3" cards were tinted by
LENS (`lens-${s.lens}`) while the Signals page already tinted by the RAG market-position VERDICT
(`sig-tone-${posTag().tone}`). Re-pointed the home cards to the same verdict tone (sig-tone-{red|amber|
green|approach|neutral}); the lens now survives ONLY as the roundel ICON colour (.signal-roundel.lens-*
svg{color:var(--lens-*)}), and the pos-tag pill is verdict-coloured. So a behind/below metric reads RED, a
neutral outlier/Approach reads purple — home now matches the gauge + Signals page exactly. VERIFY (live DOM,
computed colour): EV charging reimbursement border-left rgb(192,57,43)=--unfavourable (sig-tone-red, was
green); Flexible benefits allowance red; Pay review frequency rgb(98,87,201)=--differs (sig-tone-approach,
a neutral Quarterly-vs-Annually outlier, correctly no verdict).

#2 BACKEND (server/signals.py): 15 Practice/Design metrics sit in position_lenses, so when the org is on the
wrong side they fired through the BEHIND block and were stamped kind=behind/fav=bad/tag="LOWER THAN MARKET"
— a market verdict on an Approach metric that resolves to position="differs". Added a recast at the single
join where position/mp_class are attached: any signal resolving to position="differs" that fired through a
verdict block (behind/ahead) has its RAG verdict STRIPPED (fav dropped) and is re-cast as PREVALENCE — "N%
of the market does this, you don't" — using _market_adoption(), the SAME in_place+partial/assessable
computation block 4 uses (identical, honest %). When adoption < prevalence_floor or the org already has it,
it falls back to kind=approach / tag="DIFFERS FROM MARKET" (no fav, purple chip) rather than a false verdict.
Substance metrics (EV charging = class Level, position below) are UNTOUCHED — they keep their real verdict.
VERIFY (live /api/overview signals_all, 88 signals): zero differs-signals carry a fav (any_differs_with_fav
[]); Relocation support now kind=prevalence/tag="MOST DO THIS"/fav=null/"83% of the market does this, you
don't"; Pay-for-skills, Outplacement, Benefits participation, Low-emission car priority et al. likewise
clean. Gauge/board-pack unaffected (Approach metrics already excluded from the Substance pool).

---
2026-06-21 — GAUGE + DOMAIN TILES: alignment-aware verdict tone (Option A, David-picked). David flagged the
overview gauge reading a big alarm-red "Below" while the org is ON its declared "sit below market" lag
strategy (a contradiction with the green "On your target" note). FIRST a full QA confirmed the all-red is
DATA-CORRECT, not a bug: a faithful standalone replication of hero_signals reproduced the live gauge to the
unit (global 91/18/2, pool 111; every domain — Pay 11/6/0, Incentives 20/5/0, Benefits 39/2/2, Time Off
12/3/0, Wellbeing 6/0/0, Recognition 3/2/0, Governance excluded). Receipts: base salary P2, bonus opportunity
P3-8, employer pension P2-6 every level, EAP/financial-wellbeing/health-screening provisions absent — a
genuine below-market retail org on a deliberate lag. Graduated leans (-0.47..-1.0), and real greens inside
the red (Benefits has Life assurance P93.6 above) — not a stuck colour.

THE FIX (web/js/pages.js, cache v209->v210): the over-alarm was the documented absolute-RAG decision colliding
with the strategy. Reframed WITHOUT reversing "verdict reflects mass": added alignTone(verdict, aim) — reads a
position against the org's declared aim index (lag0/match1/lead2), mirroring positions._market_target: short
of the aim -> red, on it / past it -> green; null when no stance (caller falls back to absolute marketTone).
Applied to the single VERDICT read only — the gauge headline word (wordCol) and the domain tile chip + card
tint (CategoryTile `tone`). Every DISTRIBUTION surface — gauge bands, tile bands, needle, per-signal
positions, footer counts — stays ABSOLUTE marketTone, so the magnitude of the gap is never hidden. We
explicitly did NOT do a full stance-FLIP of all colours (the originally-rejected approach that makes red
structurally impossible for a lag org and kills the traffic light). Net: a deliberately-below org sees a big
red below-block (truth) under a green "Below" word + "On your target" note (framing), not a failure alarm.

VERIFY (deterministic — exact function replicas on the real data, preview was logged out post-restart and
demo password must not be entered): Thornbridge lag/on-target -> gauge word GREEN, all tiles GREEN, bands
below=red/on=amber/above=green (factual). Controls hold the traffic light: a 'match' org sitting below ->
RED word + RED tile (behind aim); no stance + below -> RED (absolute fallback, byte-for-byte unchanged).
Stale "Strategy NO LONGER tints the colour" comment block rewritten to describe the absolute-bands +
aim-aware-verdict split. Scope: live overview only; Signals per-card RAG and board-pack unchanged (separate
surfaces; flag if David wants them aligned too).

---
2026-06-21 — FULL-PLATFORM QA SWEEP (autonomous; data · engine · UX · UI). Method: ran the platform's own
qa_*.py harness for a baseline, then a 16-finder multi-agent workflow (one per surface×dimension) →
adversarial verify each finding against the intentional-decisions guardrail → 46 confirmed (9 high, 17 med,
20 low). Frontend fixes applied by a parallel per-file fix-workflow; backend/data fixes applied directly with
re-aggregation + harness re-verify. Backups: lumi.db.bak_pre_fullqa_*, market_position_config.json.bak_pre_rew263_*.

HIGH-SEVERITY FIXES (all verified):
- FIREWALL LEAK (aggregate.py run_snapshot): the responder universe was NOT gated on submission_complete — the
  lone firewall site missing the gate (peer_twin + qa_integrity both enforce it). An incomplete signup org
  ("Tester", submission_complete=0) that answered one question (ALLOW_02='Yes') leaked into the published
  benchmark (n=221 vs the canonical 220). Added `responding &= {submission_complete=1 orgs}`; re-aggregated →
  ALLOW_02 n=220, qa_integrity 0 mismatches. Structural: any future half-finished signup is now excluded.
- REW263 GAUGE LEAK: all 38 release-2026.3 metrics (category=practice) were never added to
  market_position_config.json (Part A predated them), so 19 rode the _mp_gauge_eligible legacy-polarity
  fallback INTO the competitiveness gauge, bypassing the firewall and inflating the pool (111). Classified all
  38 as Practice/direction=null (Approach → excluded from the gauge; David can promote any to Provision later),
  AND made _mp_gauge_eligible FAIL-CLOSED (unclassified metric in a populated config → out of the gauge, never
  admitted on raw polarity). Gauge pool 111→92; Recognition correctly drops from a false methodology-grade
  'market' verdict to indicative (it has only 2 genuinely-classified Substance metrics, below domain_min=3).
- REW_PAY_020 ("Allowances pensionable by level") was stuck status='retired' (release_retired=
  'qa-release-fixture') — a qa_release test fixture retired a REAL metric (220 answers, live snapshot) and
  never restored it, so visible_questions() hid it from every user. Restored to active → 244 live Reward qs.
- REW_BEN_SICK_001 seed scoring was INVERTED: "No sick pay provided" scored 100 (best), "Statutory only" 0.
  Corrected option_scores to generosity order (No-pay 0 < Statutory 33 < Combination 67 < Enhanced 100);
  re-aggregated.
- SECURITY: POST /api/notifications/run-sweep (a cross-tenant recompute+fan-out for EVERY org) was reachable
  by any ORG admin; changed to require_platform_admin (matches every other cross-tenant route).
- HEADLINE↔GAUGE CONSISTENCY (task #86 residue): the board-pack/share headline split the SAME Substance pool
  at the per-metric 45/55 `favourable` cut while the gauge used MARKET_BAND 35/65 (same org read 2/18/91 on the
  gauge but 6/11/94 in the board pack). Threaded band_low/high through overview_summary (classify via
  _market_class); headline now == gauge exactly. qa_phase1 assertion rewritten to enforce headline==gauge.
- FRONTEND: how-lumi-works legend palette was INVERTED (below=amber/above=red) vs the shipped absolute RAG —
  corrected to below=red/on=amber/above=green. Category-page verdict chip was NOT aim-aware (contradicted the
  Option A gauge/tile for a lag org) — made the chip aim-aware (alignTone), band dot stays absolute.

MEDIUM/LOW (selected): signals recast no longer inherits behind-tier impact (re-baselined to prevalence tier)
and no longer leaks a stale "vs market median" detail into change-alert emails; neutral-polarity (cost)
signals excluded from the Signals position bar/chip so context metrics never paint red; ~6 undefined CSS
tokens fixed (--font-body, --text/-soft, --shadow-soft/-sm, --fs-h3) restoring dropped fonts/shadows/rings;
amber text token darkened to #8A5805 for WCAG AA; histogram "You" marker clamped on-canvas; keyboard
activation (Enter+Space) added to all role=button rows; shared Modal given focus management/aria; "flag"→
"signal" noun terminology per lumi-terminology.md; dead MethodologyPage component removed; board-pack
peer-adoption + "at/above median" copy corrected; matrix_value strips £/commas, multi_block denominator is
matched-only + None-safe; qa_hero census + qa_focus/qa_pulse literals made self-tracking (no more release drift).

DEFERRED (flagged for David): the score_direction rule-ordering inversion affects exactly 3 questions —
PUR_CLAR_04 (Purpose) + PROP_bda2522c (Inclusivity/proposed) are both HIDDEN in the reward-only launch (zero
user impact) and the regex change is fix_safe=false/risky, so it is NOT shipped; the one VISIBLE inversion
(REW_BEN_SICK_001) was fixed directly via its option_scores. Also deferred (low value on a single-org demo):
submit/save_draft no-op short-circuit, /api/overview recompute-hoisting + a fields=signals fast path.

VERIFY: harness green — qa_hero 59/59, qa_integrity 0 mismatches, qa_phase1 headline==gauge, qa_ordered_routing
17/0, qa_scores/qa_signals_system/qa_strategy/qa_release/qa_metric_data all pass. Standalone engine repro
reproduces the cleaned gauge (pool 92, REW263 gone, Recognition indicative). SPA renders clean on v211 (all 8
edited frontend files parse). Pre-existing non-defects left as-is: qa_status_audit HTTP 429 (server rate-limit
under rapid test traffic — test infra, not a platform bug) and qa_phase1 PROP_9e4ad87f P25 rounding (known L2
±0.005 artifact). Cache v210→v211.

---
2026-06-21 — GAUGE/TILES: aim-aware DISTRIBUTION colour (v211→v212). David: "why are they all still red?".
Option A had greened only the VERDICT (word/chip/tile-border) but left the gauge arc + tile bars ABSOLUTE red —
so an on-target lag org read as a green "Below" word sitting over a red arc, and green tile borders over red
bars: an inconsistent, alarming, "looks-broken" mix. Extended the aim-awareness to the distribution bars:
new bandToneAim(k, aim) colours each band against the declared aim — the band that IS your aim = green (on
target), a band short of it = red, a band past it = amber (drifted up, caution). Wired into the gauge
(bandTone) and the overview tile bars (cat-bar-seg). Now Thornbridge (lag, on-target) reads a calm GREEN gauge
(the dominant below-block is green) + green tiles, consistent with the green verdict word. Segment PROPORTIONS
+ the below/on/above counts still carry the magnitude; the needle stays neutral grey. Verified deterministically:
lag on-target → below green / on,above amber; match org → below red (short) / on green; lead org → below,on
red / above green; no stance → absolute marketTone unchanged. TRADE-OFF (accepted, David-driven): a pure lag
org now never shows red on the gauge (you cannot fall "short" of a sit-below aim) — red is reserved for being
on the WRONG side of your aim, which a lag org reaches only by drifting above market. SPA renders clean v212.

---
2026-06-21 — GAUGE GEOMETRY BUG (real, pre-existing; v212→v213). David: "gauge still broken" — the dial showed
a split arc (green lower-left + grey gap across the top + green/amber lower-right) instead of a clean rainbow.
Root cause in OverallArc.arcPath (web/js/pages.js): the SVG large-arc-flag was `((f1-f0) > 0.5 ? 1 : 0)`, so
any single block spanning more than half the dial (e.g. a heavily-below org's ~83% below-block) drew the MAJOR
arc — the long way round, under the bottom — leaving its two ends as stubs on either side and the top
uncovered (grey base track). A gauge band never exceeds 180deg, so the minor arc is ALWAYS correct: changed the
flag to a constant 0. Pre-existing since the proportional-arc rebuild; only ever visible when one band
dominated the dial, and masked while that block was red (read as "a red gauge") — surfaced now that the
on-target block is green and David zoomed in. Diagnosed + verified by rendering the real arc math both ways
side-by-side in the preview (screenshot): old rule = split/grey-gap (matches David's image), flag=0 = one
continuous rainbow + needle in the block. Cache v212→v213. (Same fix also tidies the background track, which
used the identical buggy flag.)

---
2026-06-21 — "WHERE YOU STAND" HERO: market spectrum replaces the dial (v213→v214, A/B toggle). David asked
whether the needle dial is still the right chart now the model is aim-RELATIVE. It isn't: a speedometer
implies (a) a single value and (b) left=bad/right=good — both now false (it's a distribution, and the good end
is green-on-the-LEFT for a lag org), and it duplicates the domain-tile primitive (proportional segments +
marker) bent into a semicircle. Built OverallArc into a chart-swap: new default = a horizontal MARKET SPECTRUM
— the same proportional below/on/above blocks (aim-aware tones, so the mass still reads) unrolled onto a
below↔above axis, PLUS a "your aim" marker drawn on the axis and a "you are here" centroid marker. The point:
the methodology is now "where you sit vs the position you set", and only a spectrum can DRAW the aim (a dial
can only colour by it) — "on target" becomes literal (your marker sits in the aimed zone). The big verdict
word + "On your target" line + counts are unchanged (shared verdict block). The legacy dial is kept behind a
header toggle (Spectrum | Dial), persisted in localStorage 'lumi.standStyle' (default spectrum) so it's a real
A/B, not a guess. Self-contained in pages.js OverallArc; no data/engine/CSS-file changes. Verified by rendering
the real spectrum geometry in-preview (screenshot: aim points into the green below zone, you-marker inside it,
proportional green/amber bar) and SPA parses clean on v214. David to pick the keeper.

---
2026-06-22 — MARKET SPECTRUM shared across overview + all domain pages (v214→v215). David: the domain pages
should carry the same marker chart as the new hero, for consistency. Extracted the spectrum into a reusable
`MarketSpectrum({ market, aim })` component (web/js/pages.js) — proportional below/on/above blocks (aim-aware
tones) on a below↔above axis + a "your aim" marker + a "you are here" centroid; chart-only, robust to a
market with no explicit lean/verdict (derives them). OverallArc now renders `<MarketSpectrum>` in its spectrum
branch (dial branch unchanged; same toggle). CategoryPage's "Market position" cell swapped its single dot-band
(cat-band) for `<MarketSpectrum market=${pos} aim=${aim}>`, scoped to that domain's counts with the GLOBAL aim
drawn on it — so every domain reads "vs your aim" identically to the home hero. Verified at cell width
(screenshots: Pay 8/5/0 and Benefits 39/2/1 both render clean — aim+you in the green zone = on target; tiny
on/above segments correctly unlabelled). SPA parses clean on v215, zero console errors. NOTE for David: on a
heavily-below domain (e.g. Benefits) the aim point-marker sits at the aimed-zone centre while the you-marker
sits at the true centroid further left, so they read slightly apart though both green/on-target — the offered
"aim as a bracket spanning the whole aimed zone" refinement would remove that near-miss look if wanted.

---
2026-06-22 — SPECTRUM aim = BRACKET, not a point (v215→v216). David approved the refinement. In the shared
MarketSpectrum (web/js/pages.js) the "your aim" marker is now a bracket spanning the WHOLE aimed zone (the
below/on/above segment matching the stance) with faint dashed boundary lines down to the bar, instead of a
single triangle at the zone centre. So "you're inside your aim" reads literally — the you-marker sits within
the bracket — and the prior near-miss look on heavily-below domains (you-centroid far left of an aim point at
the zone centre) is gone. One change in the shared component → updates the overview hero AND all seven domain
pages at once. Verified: bracket spans the green below-zone with the you-marker inside it; SPA parses clean on
v216.

---
2026-06-22 — DESIGN/UX/UI REVIEW IMPLEMENTED (B+ review → fixes, v216→v217). Ran an 11-lens design review
(charts · dashboards · domain/metric · nav · download/export · share · submission/strategy · visual system ·
states/motion · a11y · content) → curated to top issues + quick wins + bigger bets, then implemented via a
per-file agent workflow (one agent per file + shared cross-file contracts). SHIPPED:
- DOWNLOAD/EXPORT (founder priority): NEW GET /api/benchmark.csv (one row per org-visible metric — you-value,
  p10..p90, n, cut, suppressed; same assemble_card path so numbers match the cards; suppressed cells blanked,
  never leak a small cell) + a "Download data (CSV)" button (commercial.js); board-pack print fidelity
  (print-color-adjust:exact + @page A4 so RAG verdict colour survives print-to-PDF); "Copy chart" (clipboard)
  item on cards.
- SHARE (founder priority): a ShareDialog (window.Modal) + "Share this view" buttons on the overview + every
  dashboard (POST /api/shares kind=dashboard → public /share/<token> link + copy); responsive public share page
  (A4 scales to phone width). [The create-share moment now lives at the point of intent, not buried in Settings.]
- BOARD-PACK no-advice: "Recommended actions" → "Options to consider" + the standard not-advice caveat, and
  claude_api.py BOARD_PACK_SYSTEM softened so the model emits observations grounded in cited gaps, not
  imperatives (key recommended_actions kept).
- MOBILE: replaced the <900px sidebar:display:none with a real off-canvas nav DRAWER (nav-hamburger + nav-scrim +
  body.nav-open slide-in; reduced-motion aware) — nav is no longer unreachable on a phone.
- A11y: keyboard COMBOBOX search (roles + arrow-keys + activedescendant + Enter, was mouse-only); skip-to-content
  link; dashboard tabs downgraded from a fake role=tablist to an aria-pressed toggle group; verdict pills + the n
  text darkened to clear WCAG AA; reduced-motion now stops the two infinite celebration loops + a global catch-all.
- CHARTS: .spectrum-svg width rule (fixes my own WebKit-collapse regression); truncated-label <title> tooltips on
  OptionBars/OrderedDist; histogram frequency reference; degenerate (unanimous) distribution state; unified "you"
  glyph; in-segment counts on the spectrum.
- POLISH: dynamic onboarding numbers (no more stale "180 / 90%"); --fs-subhead/--fs-micro rungs added; brand
  casing. DELIBERATELY DEFERRED (conservative, per brief): the wholesale type-token migration (~24 call-sites)
  — rungs added for future use, no risky visual-shifting sweep; QuartileDots confirmed dead, left in place.
VERIFY: SPA renders clean on v217, ZERO console errors (all 7 frontend files parse); backend imports + starts;
/api/benchmark.csv registered (401 auth-gated, identical to gap-register); all structural features wired
(grep-confirmed). NOT visually verified logged-in (preview auth + demo-password policy) — drawer/share-dialog/
combobox keyboard nav to be eyeballed on David's session. app.css survived two concurrent agents (app.css +
share.js) intact + balanced (1440/1440, all markers present). Cache v216→v217.

---
2026-06-22 — SIGNAL TRIAGE everywhere (v217→v218). David: a user should be able to dismiss/prioritise/save a
signal wherever it appears, not just on the Signals explore page. Extracted ONE shared <SignalActions
status sid onSet /> control (prioritise · save · dismiss / restore, with aria-pressed) + a signalAction(sid,
status) persistence helper (pages.js, near sigParts). Wired it into all three surfaces so behaviour is
identical: (1) the home "Signals · top 3" briefing (SignalsPanel) — added a local optimistic status overlay so
a dismiss removes the card instantly + a priority/save toggles; (2) every domain page (CategoryPage "Signals in
X") — same overlay, and the rows were unified to the home/Signals-page axis style (posTag/sig-tone + actions,
dropping the old lens-only style + go-arrow); (3) the Signals page Row was refactored to render the same
<SignalActions> (DRY — no behaviour change, its own setStatus stays the onSet). All POST /api/signals/action
(existing). Optimistic overlay per surface; server is authoritative on next load. Verified: SPA renders clean
on v218, zero console errors; pages.js balanced; 1 component def + 3 usages. Visual confirm of the buttons on
the logged-in home/domain rows is David's (preview auth + demo-password policy). Cache v217->v218.

---
2026-06-22 — SHIP-READY: HOW-LUMI-WORKS + LEGAL + METHODOLOGY review, real-company data provenance (v218→v219).
David: "review the how lumi works page — needs to be all finalised and ready to ship — review the legal docs and
methodology — never say the data is seeded — the data is from real companies." Reviewed all three; they already
describe the genuine co-operative model (peer norms built only from organisations that completed a lumi
submission; member submissions; anonymised aggregates; 5-org suppression floor) with NO seeded language — so the
How-lumi-works page, the /api/methodology copy and the 6 legal docs needed no rewrite, only the removal of the
residual dev-era "illustrative/synthetic" self-labelling. Retired that labelling at source: (1) dropped the
`synthetic_pool` field from /api/overview + /api/methodology; (2) flipped the `illustrative_sample_data` flag to
default OFF everywhere (`get_meta("synthetic_pool", False)` at app.py 973/1533/3600) so `caveats.illustrative`
is now false and nothing renders a sample-data caveat; (3) deleted the `synthetic_seed` meta row and stopped
seed_import.py setting it. Copy scrub: marketing glance "illustrative view of the benchmark" → "a preview of
your benchmark view"; metric-tile indicative tip "limited sample data" → "limited comparable data" (×2);
admin new-metric note "needs seeded answers" → "needs back-filled answers". QA tests updated to the new contract
(qa_phase4 §4.5 + qa_commentary §D now assert NO synthetic/illustrative labelling, both pass). Verified
authenticated: /api/methodology + /api/overview carry no `synthetic_pool` and no "synthetic" string; real pool
numbers intact (220 responding orgs, 158 classified, 14 sectors, 220 reconciled files); marketing "/" served
fresh has 0 "illustrative". Internal dev comments in seed scripts (seed_pulse.py, seed_import lineage) left
truthful — not user-facing. LEGAL DOCS: all 6 are content-complete and accurate but remain marked
"DRAFT — pending legal review" (and the privacy notice states a qualified DP adviser will review before launch);
left that chip in place — dropping it is a legal sign-off decision for David, NOT a copy edit. Pre-existing QA
fixture rot noted (not introduced here, out of scope): qa_phase4:40 hardcodes a now-404 metric id
(PROP_9e3b1d18); qa_commentary:132 expects REW_BEN_HOL_001 neutral but it's now higher_is_better. Cache v218->v219.

---
2026-06-22 — LEGAL CORPUS: lawyer-approved finalisation (PARTIAL) + QA fixture repairs (v219→v220).
David: "fix [the two QA fixtures] and all the legal elements have now been approved by my lawyer." A read-only
discovery workflow (9 agents) mapped every DRAFT reference and adversarially read all 6 docs for completeness.
FINALISED 3 structurally-complete docs to v1.0: platform-terms, data-contribution-terms, data-sharing-agreement
(DPA). For these: version banner "1.0-draft · DRAFT — pending legal review" → "Version 1.0"; PLATFORM_TERMS_VERSION
/ DATA_TERMS_VERSION "1.0-draft" → "1.0" (verified safe — the constants are write-only/audit; every acceptance
gate is existence-keyed on `kind`, never version-compared, so no re-acceptance is forced); LEGAL_INDEX draft flags
→ False for the three; DPA file renamed dropping -draft + LEGAL_FILES + download Content-Disposition updated;
frontend chips de-drafted (auth.js TermsModal [platform], submission.js [data-contribution], commercial.js
[settings], pages.js legal-index intro). HELD 3 docs at DRAFT because the discovery found genuine UNPOPULATED
placeholders that cannot honestly be called final — I will not fabricate the missing operational facts:
  • privacy-notice — "email the address published in the final notice" but NO contact email appears anywhere
    (GDPR rights are non-actionable without it);
  • cookie-policy — Analytics section defers to "described in the final policy"; the analytics cookies are not
    described in-body;
  • sub-processors — the "Current sub-processors" table names ZERO sub-processors (both rows "To be confirmed
    before launch").
These keep draft:True + their -draft filenames + DRAFT banners; the per-doc Draft chip + the data-driven
LegalDocModal note (pages.js:2058, only renders when d.draft) surface their status honestly. The legal-index
intro now reads "Any document still in review is marked Draft" (accurate for the mixed state). ASKED David to
supply the 3 missing values (contact email / analytics description / named sub-processors+purposes+locations) so
all six can be finalised in one clean pass. Verified: /api/legal flags platform F·privacy T·cookies T·data_contribution
F·dpa F·subprocessors T; /api/legal/dpa resolves the renamed file (draft False); /api/terms version "1.0";
download filename has no DRAFT; the 3 final docs are DRAFT-clean.
QA FIXTURE REPAIRS (both gates now green): qa_phase4 PROP_9e3b1d18 (now status='proposed', 404s) → PROP_e63cf45a
(workforce cost %, live, satisfies the 4.2 X-in-10+percentile assertion); fixing that crash unmasked 5 further
copy-drift checks (search/Ask-lumi/peer-set/filter/card-button labels reworded over time, all features intact, no
regressions) — re-pointed each to current copy. qa_commentary line-131 REW_BEN_HOL_001 (now higher_is_better) →
PROP_d16bae79 (config-neutral workforce-cost; the metric already named in the line-116 comment). Results:
qa_phase4 15/0, qa_commentary 40/40 GATE CLEAN. Cache v219->v220.

---
2026-06-22 — SELF-SERVICE PULSE BUILDER + PAID LAUNCH (v220→v221). David: "give the user the ability to create
their own pulse survey — a survey builder — they're charged for launching surveys to the community." Decisions
(David, 4-way): pay by Stripe card self-serve; lumi staff REVIEW every launch before it goes out; audience =
whole community; results = give-to-get for everyone who answers PLUS the sponsor. Built on the existing pulse
engine — same firewall, snapshot, n>=5 suppression, give-to-get report — adding only org ownership + a review +
a payment gate IN FRONT OF the unchanged open_pulse(). Lifecycle (pulses.launch_status, NULL for legacy staff
pulses): building -> in_review -> changes_requested|approved|rejected -> paid (==> status flips draft->open).
SCHEMA: pulses gains owner_org_id, created_by, launch_status, review_notes, reviewed_by, reviewed_at,
launch_fee_pence, visibility ('community'); new pulse_launch_orders ledger (Stripe session/intent, amount,
status). PAYMENTS (server/payments.py): Stripe Checkout via httpx + stdlib-HMAC webhook verification — NO stripe
SDK dependency; keys (LUMI_STRIPE_SECRET_KEY / _PUBLISHABLE_KEY / _WEBHOOK_SECRET) read from .env.local like the
Anthropic key, with a graceful "unconfigured" fallback so the flow is fully testable before keys exist. Webhook
(POST /api/stripe/webhook, signature-verified) marks the order paid -> open_pulse(); idempotent. Staff
"Confirm launch (no card)" path (/api/admin/pulses/{id}/confirm-launch) opens an approved pulse without Stripe
(invoiced / pre-keys / demos). ROUTES: org self-serve /api/org/pulses (GET list, POST create, GET/PUT/DELETE one,
submit-for-review, checkout) gated require_admin + owner-scoped (404 cross-org, never 403-leak); staff
/api/admin/pulse-reviews + /review (approve|changes|reject + fee) + confirm-launch gated require_platform_admin.
Owner-always-sees: app.py pulse_detail adds is_owner so the sponsor sees the report without participating.
FRONTEND: pulses.js RunPulsePage (owner dashboard) + PulseBuilderPage + PulseComposer (reuses the 4 pulse types
yes_no/single_select/multi_select/numeric + library reuse) + PulseLaunchPanel (stepper + Pay&launch / Stripe
redirect / unconfigured msg); admin.js AdminPulseReviewsTab (queue, read the questions for quality/PII, approve
+ set fee / request changes / reject / confirm-launch); app.js /run-a-pulse route + Admin-only rail item +
Pulse-page CTA; CSS pulse-stepper/libpick + launch-status badges. CONFIG: LUMI_PULSE_LAUNCH_FEE_GBP (default
750, staff-overridable per pulse at approval), LUMI_BASE_URL. Creation/launch = Admin-only (a paid action);
Contributors still answer. VERIFIED: data-layer end-to-end repro PASS; 15-check HTTP route test (temp server,
auth guards incl cross-org 404 + staff-only 403, full lifecycle, unconfigured + confirm-launch, member
visibility, webhook 400 on bad sig) PASS; live-db migration + read-only route check PASS; SPA boots with all new
components registered + zero console errors; qa_pulse extended with a self-service section (firewall holds for
org-authored pulses — sentinel never reaches core answers; payment gates draft->open; idempotent; cross-org
blocked) — 0 failures. STILL NEEDS DAVID: (1) add Stripe TEST keys to server/.env.local to switch on card
payments (until then the staff confirm-launch path runs the flow); (2) Terms/billing clause covering paid
launches + refunds (legal). Live authed builder click-through is David's (preview demo-password policy blocks
agent login). Cache v220->v221.

---
2026-06-22 — PULSE BUILDER design/UX sweep + delight (v221→v222). David flagged the two self-service pulse
pages "don't look like they belong on the site" — the New-survey form was visibly BROKEN (bare <label> fields
flowed inline and overlapped). ROOT CAUSE: the composer card used plain <label>X<input class="ctl"/></label>
with no form-layout rule (the app's .field styles inputs, conflicting with .ctl; .admin-form is staff-scoped).
FIX: a .pulse-form wrapper (labels display:block + .ctl width:100%, descendant selector so nested new-question
cards are covered too) — verified by DOM geometry (all fields block + inputs stacked below on distinct rows, no
overlap). On-brand polish: a 3-step "Build → We review → Go live" rail (.pulse-how, responsive stack), the
payment caption promoted to a proper .pulse-note, a premium empty state (round icon + CTA), hover-lift survey
rows (.pulse-srow), and richer launch states (.pulse-launch / .pulse-fee, a gradient "live" card). DELIGHT
(reuses window.confettiBurst from core.js, honours prefers-reduced-motion): a gentle burst on Submit-for-review,
and a full celebratory burst when a pulse goes live (once per pulse via localStorage guard). Verified: SPA boots
clean, all components registered, ZERO console errors; the composer mounted in isolation to confirm the layout
fix logged-out (preview demo-password policy blocks agent login, so David does the final authed click-through).
Cache v221->v222.

---
2026-06-22 — PLATFORM CONSISTENCY SWEEP (v222→v223). A 6-agent read-only audit (colour/icons/pills/menus/
type/branding) graded the design system fundamentally sound; applied the high-value, user-visible fixes and
skipped the invisible hygiene + the patterns that are already consistent platform-wide (the fullwidth ＋ and
trailing → arrows are used uniformly everywhere — NOT drift, so left alone; the .on-vs-.active tab split is
between genuinely different tab TYPES — left alone). FIXED: (1) admin status badges moved off hardcoded hex
(#E7F5EC/#1B7740, #FEF3DA/#8A5A00, #FBEAEA) onto the RAG design tokens (--favourable[-tint] / --neutral-perf
[-tint] / --unfavourable[-tint]) so the console matches the app's green/amber/red everywhere (admin-status-paid
stays the deliberate brand-blue badge). (2) Confetti recoloured from a Tailwind palette to the lumi palette,
resolved from CSS tokens at runtime (--blue-bright/--favourable/--amber-bright/--lumi-coral/--blue/--differs)
with brand-hex fallbacks; the submission unlock burst's off-brand colour override removed so it inherits the
brand default. (3) Board-pack cover title "LUMI PEOPLE ANALYTICS BENCHMARK" -> lowercase "lumi people analytics
benchmark" (brand rule: lumi is always lowercase, even on the premium external artifact). (4) Emoji in the
pulse builder brought onto the Icon system: ✦ Commentary -> <Icon sparkle> (matches the AI sparkle used in
app.js), the ✅/🎉 launch-state emojis -> on-brand <Icon check>/<Icon sparkle> in the tinted circle (confetti
still carries the delight), 🎉 removed from the submit-for-review toast copy. (5) .eyebrow promoted from a
.opp-hero-scoped rule to a base class — the admin console eyebrow ("lumi staff · back office") was rendering
unstyled. (6) Pulse launch-state headings 16px -> var(--fs-card-title). Verified: SPA boots clean, all
components registered, ZERO console errors; confetti tokens resolve to lumi hues; .eyebrow now applies. Cache
v222->v223.

---
2026-06-22 — OVERVIEW CLEANUP, STAGE A (dashboard logic & copy) — DIAGNOSE + APPLY (v223→v224). David's two-stage
brief (Stage B held behind a hard barrier). A-PHASE 1 diagnosis against the LIVE db (Thornbridge): the three
"differ"-type figures are a PRESENTATION problem, NOT a computation bug — proven by the hero approach count (48)
equalling the sum of the 7 tile differ counts (Pay 13 + Inc 6 + Ben 7 + TO 2 + Well 1 + Rec 2 + Gov 17 = 48), so
it reconciles to its parts including the unbenchmarkable Governance domain. Findings: (Q1) hero "differ" = answered
Practice/Design metrics whose choice != the modal peer choice (48 of a 108 pool); the Signals panel total = the
curated cross-lens briefing across ALL metric types (85 not-dismissed: 55 below + 2 above + 28 differs by
position; outlier/prevalence/rare/behind/...) — DIFFERENT denominators, a legitimate definitional difference.
(Q2) Governance shows "no market rate" AND "17 differ": both are technically true but on different axes — "no rate"
is correct (Governance earns no competitiveness verdict) and the 17 is a prevalence/mode comparison; neither label
is false, the juxtaposition just reads contradictory. (Q3) the hero severity adverb ("clearly below") is driven by
the COUNT lean (above-below)/pool = (1-76)/92 = -0.815 vs threshold 0.25 — NOT percentile depth; the biggest-gaps
P3-P4 panel measures depth, a different axis (both compute correctly). (Q4) the headline 220 is the pool; per-metric
drill-downs DO surface each metric's real post-suppression n (samples 200/216/214; 447 of 844 blocks at 220) — honest,
no propagation. NO computation bug found, so A-PHASE 2 is presentation-only, no data writes.
A-PHASE 2 RULINGS (David-signed): (1) hero approach line "N differ from market" -> "N of M practices differ from
market" (self-contained denominator so the reader needn't sum tiles; tooltip names it a separate lens from the
gauge + states the few worth acting on are the signals). (2) Governance/non-competitive tile chip "no market rate"
-> "approach", and its companion line made self-contained "N of M differ from market" — reframes the domain
honestly as approach-based and removes the apparent contradiction WITHOUT dropping the (meaningful) differ tally.
(3) every tile's differ line -> "N of M differ from market" (each number unambiguous; the 7 still sum to the hero
48). Guardrails kept: verdict language stays below/on/above market; structure-neutral copy, no pay/level language;
protected items intact (Spectrum/Dial toggle, your-aim overlay, "we flag, you decide", verdict word, all 7 cards).
SEPARATELY FLAGGED (config hygiene, NOT touched this pass): 2 Governance metrics carry a rate-bearing class
(PAYTR_01_42eae7ec Level, REW_PRO_098 Provision) yet sit in a non-competitive domain (domain-policy exclusion);
28 Governance config entries are class=None (unclassified). Neither feeds the differ count. Cache v223->v224.
STAGE B (type/spacing) HELD — awaiting David's "Stage A signed off — start B".

---
2026-06-22 — OVERVIEW STAGE A items C + D (completes Stage A) (v224→v225). The first brief truncated before items
C and D; David confirmed the full prompt and signed off the proposals.
ITEM C — VERDICT SEVERITY now DEPTH-driven, not count-driven. Phase-1 diagnosis found the severity adverb came
from lean=(above-below)/pool (a headcount ratio). New: _pool_verdict (positions.py) surfaces depth_pctl = the
MEDIAN polarity-adjusted percentile (_adj_percentile) across the gauge pool — "how far" not "how many". The client
leanWord (pages.js) now picks the adverb from depth_pctl: below <25 clearly / <40 moderately / else marginally;
above >75 / >60 / else (falls back to the old count lean only if depth_pctl is absent on a stale payload). The
verdict WORD (below/on/above) stays lean-driven and LOCKED ('verdict reflects mass'); only the adverb changed. No
data write (reads percentiles the gauge already computes). Thornbridge: depth_pctl=11.3 -> "clearly below" (same
word as the old count logic, since the org is both deep AND 76/92-below; the change BITES on a many-shallow-gaps
org, which now reads "marginally" instead of "clearly"). Heads-up logged: the gauge needle stays count-driven
(the protected mass gauge), so adverb (depth) and needle (count) can diverge for a shallow-many org — intended
honesty. qa_hero 59/59 (verdict invariants intact). Stage C gate #5 will assert this depth rule.
ITEM D — DECLUTTER: NO REMOVALS (David signed off). The Overview's percentile encodings are already unified (the
hero proportional bar and the 7 tile bars are one scale, learned once) and every number reconciles; the genuinely
confusing/no-weight figures were the differ<->signals<->Governance numbers, already resolved by items A+B. The
hero "differ" line is plain text+tooltip, not a link (already compliant). The gauge legend (exact counts) is kept
as the reconciliation, and the brand flourishes (aurora/card-spot/cursor glow) are intentional character, not
filler. Nothing removed.
STAGE A COMPLETE (A unify-differ + B governance-card + C depth-severity + D no-removals). Cache v224->v225.
Next: STAGE B (type/spacing token pass) Phase-1 audit.

---
2026-06-22 — OVERVIEW STAGE B: TYPE & SPACING TOKEN PASS (v225→v226). David approved Phase-1 audit + Phase-2 apply.
PREMISE CORRECTION: the brief assumed type/spacing weren't tokenised, but the platform already had --fs-* (×10:
micro 11/caption 12/label 13/body 15/card-title 16/subhead 18/section 22/metric 28/display 30/metric-lg 40) and
--s1..--s8 (4/8/12/16/24/32/48/64) + --radius/--radius-sm. So the work was MIGRATING the hardcoded literals that
bypass them, not inventing tokens (the suggested --space-1..6 would have duplicated --s*). APPLIED: 755 hardcoded
font-size + padding/margin/gap literals -> var(--fs-*) / var(--s*) across 13 files (app.css +504, then pages/
commercial/pulses/submission/admin/app/share/auth/card/core/icons/strategy js). PROPERTY-ANCHORED migration
(never touched width/height/border/stroke/SVG coords/line-height/box-shadow/transform/border-radius); CSS
shorthand handled per-value; 0 values preserved. Off-grid drift absorbed: 29 .5px font-sizes -> nearest --fs;
spacing ties resolved per David's sign-off (6->s2/8 ×94, 10->s3/12 ×81, 14->s3/12, 20->s5/24). Shifts: mostly
±0.5-2px, a few +4 (the 60px loading-spinner padding ×23 -> --s8/64, cosmetic centering). EXCEPTIONS KEPT (not
forced): spacing 1/2/3px (hairline borders + chip/badge insets — rounding to 4 would change chip heights), and
font-size 34px (success ring / hero glyph). Kept the 10-type/8-space SCALE rather than force-collapse to "6-7"
(merging steps like 16+18 or 28+30 would change layout intent, which the brief forbids). SPACING/TYPE ONLY — no
colour/copy/logic/element-count change. VERIFIED: dry-run diff audited for false positives (border/width/SVG all
untouched); CSS braces 1480/1480, 0 residual off-grid font-sizes (only the 34px exception), no malformed var();
SPA boots with ZERO console errors; hero + tiles mounted in isolation render correctly (padding resolves 16px from
--s4, leanWord 12px, tileOverflow=FALSE so no layout break); Stage A copy intact in the render. NO layout-break
exceptions detected. Authed before/after (hero/card/signal-row/table) is David's final eyeball (preview demo-pw
policy blocks agent login); the logged-out mount + computed-style + no-overflow checks are the no-break proof.
Future components must pick from --fs-*/--s*. Cache v225->v226.

---
2026-06-22 — OVERVIEW item B REVISED to the full spec (v226→v227). Once David supplied the complete brief, item B
was explicit: an unbenchmarkable domain shows "one honest line · No fake bar, no differ chip" and Stage C #4
asserts unbenchmarkable + differ-chip are mutually exclusive per card. My earlier item B (built on the truncated
brief) had KEPT a differ count on the Governance tile (chip "approach" + "17 of 32 differ from market"). David
chose (AskUserQuestion) to match the spec. REVISED: the non-competitive (Governance) tile now shows chip
"no market rate" (reverted from "approach") + ONE honest line "N practices tracked · approach choices" (N =
prevalence/approach pool); the prevalence bar AND the differ line are removed for noRate tiles. Competitive tiles
KEEP their differ companion (item A) — only the unbenchmarkable tile drops it. The hero "differ" (48) STILL
includes Governance's 17 by computation (item A reconciliation, asserted by the coming gate #2) — the tile simply
doesn't display it ("reconciliation is about the computation, not forcing a chip onto every card"). Satisfies
Stage C #4. Verified: source correct, SPA boots with ZERO console errors. This SUPERSEDES the earlier "approach +
differ" Governance treatment. Cache v226->v227.
STAGE A now fully matches the complete spec (A unify-differ · B governance one-line/no-differ · C depth-severity ·
D no-removals). STAGE B (token pass) done. REMAINING: STAGE C — qa_overview.py standing gate (DB-level, 7
invariants), to be built next.

---
2026-06-22 — OVERVIEW STAGE C: qa_overview.py STANDING GATE (the 8th). Built per the brief as a STANDALONE gate
alongside the existing seven (qa_release, qa_engine_audit, qa_focus, qa_hero, qa_integrity, qa_commentary,
qa_pulse) — NOT folded into qa_release. DB-LEVEL, no HTTP: rebuilds the hero + signals engine-side exactly as
/api/overview does (pos.position_items / prevalence_items / practice_position_items / hero_signals +
signals.build_signals, "all" cut, request-free since make_entitled is constant and tb=None). Read-only — no
fixtures created, nothing to clean. Org-parametric (QA_ORG env, default Thornbridge). House style matches qa_pulse
(check/FAILS/PASS-FAIL-per-line, exits non-zero). FIRST checked qa_hero for overlap (it already guards pool
reconciliation L193, approach consistency L129, Governance no-verdict L166, polarity/lean) — so qa_overview adds
ONLY the genuinely-new Overview checks, asserting INVARIANTS not literals:
  1. RECONCILIATION — hero below+on+above==pool; sum of per-card below/on/above==hero classified total; no
     competitive domain has Substance items without a position (nothing silently dropped).
  2. DIFFER TRACEABILITY — hero differ == sum of per-category differ INCLUDING the unbenchmarkable (Governance)
     category (the 17 counts in the hero 48 even though its tile no longer shows it).
  3. COUNT RELATIONSHIP — distinct differs-position signals <= hero differ (the differ↔signals ruling: different
     denominators; differs-signals are a subset of the differing approach pool).
  4. NO CONTRADICTORY LABEL — the unbenchmarkable domain carries competitiveness=False + no market verdict, AND
     the render contract holds (the CategoryTile noRate branch shows the honest "practices tracked" line and
     contains no differLine/cat-differ — the Governance fix, mutually exclusive per card).
  5. VERDICT INTEGRITY — hero.depth_pctl == median adjusted percentile of the gauge pool, AND the client leanWord
     is driven by depth_pctl not the count lean (encodes the item-C depth-severity change; guards against drift
     back to headcount).
  6. VERDICT VOCABULARY — STANCE_WORD translates lag/match/lead -> below/on/above market; no raw lag/match/lead
     leaks into a rendered string.
  7. PEER-COUNT HONESTY — every shown (non-suppressed) metric block has n >= 5 (SUPPRESSION_FLOOR); nothing
     displays an undefendable peer count.
RESULT on live Thornbridge: 13/13 checks pass, 0 failures. No suite runner exists (gates run individually);
qa_overview is the standalone 8th. No UI/data change (new test file only) — cache unchanged at v227.
ALL THREE STAGES COMPLETE: A (dashboard logic+copy) · B (type/spacing token pass) · C (standing gate).

---
2026-06-22 — GOVERNANCE SCOPING RULING (PRINCIPLE — governs every future non-competitive domain):

  "Market-relative framing (differ / below / on / above) applies ONLY to competitive-scope domains.
   Non-competitive domains (Governance) contribute 0 to ALL market-relative counts — numerator AND
   denominator — exactly as they already contribute 0 to below/on/above. Their prevalence differences
   remain real and surface as PRACTICE signals on their own tile, never as market differences."

CONTEXT — this REVERSES the interim decision recorded in the two entries above. Stage A item A and Stage C
gate assertion #2 had ruled that the hero "differ" counts Governance's 17 prevalence-differences by
computation (48 = competitive 31 + Governance 17) even though the Governance tile doesn't display them — i.e.
"reconciliation is about the computation, not forcing a chip onto every card." David ruled that wrong: a hero
that says "48 of 108 practices differ from market" while the Governance tile says "no market rate · approach
choices" is internally contradictory — the 48 silently counts a domain that has, by our own carve-out, no
market rate to differ FROM. The reconciliation must be to what the CARDS RENDER, not to the full source pool.

THE FIX (computation + denominator copy only — no anchor/seed/snapshot change):
- positions.py `_hero_signals_classified` — the hero `approach` is no longer `_approach_summary(prev_items,cfg)`
  over the whole prevalence pool. It is now the SUM of the per-competitive-card approach summaries:
  `hero_approach = Σ over [d for d in domains if d.competitiveness and d.approach] of {differ,in_line,pool}`.
  One source of truth → the hero and the cards can never drift. A non-competitive domain (Governance,
  competitiveness=False) contributes 0 to differ AND to the pool. NUMERATOR AND DENOMINATOR both rescoped:
  hero now reads **31 of 76** (was 48 of 108). 76 = competitive card denominators 27+10+18+11+4+6;
  31 = Pay 13 + Inc 6 + Ben 7 + Time 2 + Well 1 + Rec 2. (108 = 76 + Governance's 32; 48 = 31 + Governance's 17.)
- Governance tile UNCHANGED: market=null, "no market rate · 32 practices tracked · approach choices", no differ
  chip. Its prevalence differences (17 of 32) stay accounted for INSIDE the 32 on its own tile and surface as
  practice signals — never as market differences. The gauge below/on/above (76/15/1 of 92) is UNCHANGED.
- qa_overview gate assertion #2 REWRITTEN (supersedes the #2 described in the entry above). It no longer
  re-derives a source sum that includes Governance (the old #2 passed while the cards mismatched — it tested the
  wrong invariant). It now asserts what the cards RENDER, reading the SAME `d["competitiveness"]` flag the hero
  reads (single source of truth, so hero and assertion cannot diverge):
    2a. hero.differ == Σ differ shown on competitive cards (non-competitive → 0)   — the regression check
    2b. hero.pool  == Σ denominator shown on competitive cards                     — numerator AND denominator
  Confirmed the gate now FAILS on the pre-fix engine state (2a: 48≠31, excluded_noncompetitive=[('Governance',17)];
  2b: 108≠76) and PASSES post-fix (31==31, 76==76). Full gate 13/13 post-fix.

VERIFIED end-to-end: live /api/overview hero `approach={differ:31,in_line:45,pool:76}` (31+45=76 ✓), Governance
domain `market=null` with `approach={differ:17,pool:32}` on its own tile; rendered DOM hero "31 of 76 practices
differ from market", Governance tile "no market rate · 32 practices tracked · approach choices". Backend change
only — server restarted (uvicorn has no --reload); no frontend/cache change (pages.js already renders
`${approach.differ} of ${approach.pool}`), cache unchanged at v227.

REPORTED, NOT FIXED (step 6 — for David to decide before settling the differ↔signals copy): the Signals panel
count is NOT yet clean under this competitive-scope rule. Of 88 total signals on live Thornbridge, **13 sit on
Governance (non-competitive) metrics** and 12 of those carry a market-relative position label (11 "differs",
1 "above", 1 "below"; by kind: 9 prevalence, 3 approach, 1 ahead — e.g. "Pay outcomes for compression…",
"Total rewards strategy (Documented)…", "Promotion guidelines that specify…"). So a Governance practice-difference
that the hero no longer counts as a market difference CAN still surface in the Signals list framed as one. This
is the same class of leak the hero just fixed, one layer down. Left untouched per the brief — flag it so the
"31 differ ↔ N signals" copy isn't settled on a still-leaky signals denominator. Fixing it would mean scoping
signals.build_signals position-labelling to competitive domains (or relabelling Governance signals as practice,
not market) — a separate change, not made here.

---
2026-06-22 — SIGNALS LAYER now obeys the GOVERNANCE SCOPING RULING (the leak flagged in the entry above, closed).
This applies the SAME competitive-scope principle already logged (see "GOVERNANCE SCOPING RULING (PRINCIPLE …)"
above) one layer down, in signals.build_signals — it does NOT introduce a new rule. Diagnosis settled the count
from live Thornbridge (reproduced twice, independently): 88 total signals · 13 on Governance (the only
competitiveness=False domain) · ALL 13 carried a market-relative position (11 differs, 1 above, 1 below; 9
prevalence, 3 approach, 1 ahead; 11 Practice, 1 Level, 1 Provision). The earlier "12" undercounted — it is 13.

ROOT CAUSE: the signal position was assigned at signals.py `s["position"] = _signal_position(s, _m.get("class"))`
off the per-metric **class**, NOT the domain **competitiveness** flag the hero scopes by (`_mp_competitive`,
positions.py:768 → `_domains[sec].competitiveness`). Two different mechanisms → the two surfaces had already
drifted. THE FIX reads the SAME flag: in the labelling pass, `if not _pos._mp_competitive(_cfg, s["domain"])`
the signal gets the NON-market position `"practice"`, and any market-verdict copy (kind behind/ahead) is recast —
single source of truth, so the Signals stream and the hero can no longer diverge.

RELABEL, not drop (signals stay in the stream, still sortable/filterable/dismissable). DAVID-SIGNED-OFF decisions:
  • Position axis — ADD a non-market value `"practice"` rather than reuse `"differs"` (whose chip still says
    "differs from market"). Frontend: new SIG_POSITIONS/POS_TAG_TEXT entry "differs from peers", purple
    (var(--differs)) via posColor/posTag — pages.js. Model change, approved.
  • The 1 Level (quantity) signal — "Typical maximum pay increase for promotions" (was "above the market") —
    NEUTRAL peer-position reframe: kind=outlier, "sits at the high end of your peer group", no verdict (not a
    reclassification). A Level/quantity has no "most do this, you don't" form, so it reads as a peer outlier.
  • Adoption copy keeps "the market" ("X% of the market does this, you don't") — it's a prevalence FACT, not a
    verdict; only the position/verdict FRAMING is peer-scoped. The 3 no-norm approach signals are peer-framed:
    tag "DIFFERS FROM MARKET"→"DIFFERS FROM PEERS", stand "…the market norm"→"…the peer norm" (this tag/stand IS
    market framing, so it moved with the ruling).
Verdict vocabulary (below/on/above market) stays LOCKED and untouched; competitive-domain signals are unchanged
(75 of them: below 54 / differs 20 / above 1). Note: the metric-DETAIL register chip (app.js:1108, "differs from
market") is a separate surface keyed on a metric's register, not the signals stream — out of scope, left as-is.

GATE: qa_overview.py gains check #8 — "zero non-competitive-domain signals carry a market-relative position
(below/on/above/differs)", reading the SAME `pos._mp_competitive` flag the fix reads. Proven to FAIL on the
pre-fix stream (13 leaks) / on any reintroduced leak (injected 1 → caught), and PASS post-fix (0). Full gate 14/14.
VERIFIED on live Thornbridge: all 13 Governance signals now position="practice", 0 market-labelled, no Governance
tag contains "MARKET"; total still 88. Frontend cache v227→v228 (index.html + share.html); server restarted
(signals.py is backend, no --reload). No anchor/seed/snapshot change — labelling + one new position value only.

---
2026-06-22 — PRINCIPLE: QA GATE COUNTS DERIVE FROM THE REGISTERED VISIBLE-QUESTION COUNT, NEVER HARD-CODED.

  "QA gate counts derive from the registered visible-question count (me['scope']['question_count'] =
   len(org_visible_questions(org))), never hard-coded literals. Counts that track the question set self-update on
   library growth; this staleness class is closed, not just the 206 instance. Quantities that are NOT the question
   count (e.g. the gauge pool / comparable_metrics) assert against their OWN correct source, never a shared
   constant that happens to match today."

WHY: the core Reward library has grown twice (194 → 206 at 2026.1/.2 → 244 visible at 2026.3), and each growth
silently rotted hard-coded count constants in the gates. A known-wrong RED gate trains people to ignore the gate —
the most dangerous failure mode for a test suite. So gate counts must DERIVE, not be pinned.

INSTANCE FIXED (qa_focus.py — test-correctness only, no data/seed/snapshot change): two stale `206` literals
(the library is now 244). Diagnosed live on Thornbridge first — 244 (cards, 1:1 with visible questions) and 92
(comparable_metrics, the gauge pool) are DIFFERENT quantities, so they were NOT collapsed onto one constant:
  • line 38 `len(rw["cards"]) == 206` → `== me["scope"]["question_count"]` (equality preserved; cards track the
    visible-question count 1:1 — verified 244==244). Assertion text de-numbered to state the invariant.
  • line 41 `comparable_metrics <= 206` → `<= me["scope"]["question_count"]` (stays a <= BOUND; the ceiling is
    derived, not a magic literal — comparable_metrics 92 is always a subset of the question universe).
Both derive from `me`, already fetched at qa_focus.py:29 — no new query, no new literal. (Lines 30/32 already
tracked the live count from a prior pass — `>=240` bound + `== question_count` — so only 2 sites needed fixing,
not the 4 first assumed.) Confirmed NOT a data problem: benchmarks serves a card per visible question (244==244),
nothing missing. qa_focus now 28/28, 0 failed; no `206` literal remains.

OPEN (reported, not fixed — see Part C sweep below / next decision): other gates may carry the same magic-count
pattern. Notably qa_hero.py:95 `len(positionable) == 76` is the COMPETITIVE-POOL count (the "31 of 76" hero
denominator) — load-bearing for a live invariant AND will go stale on library growth. Flagged for David to decide
isolated-debt vs a dedicated derive-all-gate-counts sweep.

---
2026-06-22 — PRINCIPLE: DIFFER ↔ SIGNALS ARE DIFFERENT SCOPES (legibility copy, on the verified clean model).

  "The hero 'differ' count and the Signals count answer DIFFERENT questions and are DIFFERENT SCOPES — they
   overlap, they are NOT nested. 'Differ from market' (31 of 76) is a competitive-practice positioning stat: how
   many competitive practices sit off the market norm. 'Signals' (the attention queue) spans market positions
   (below/on/above) AND practice differences (yours vs peers, competitive and non-competitive). The differ count
   FEEDS signals (the differences worth acting on surface as signals — the competitive 'differs from market'
   subset), but signals also carry market positions and Governance practice gaps. Copy states the relationship
   QUALITATIVELY and must never imply a face-value subset/superset (31 is not 'of 88'; 88 is not a superset of 31).
   Every NUMBER rendered in hero/signals copy asserts == its live engine value, never a hard-coded literal."

This applies the competitive-scope ruling (see the GOVERNANCE SCOPING RULING + signals-layer entries above) at the
COPY layer — it introduces no new scope or count. The counts were verified clean and Governance-leak-free first.

COPY APPLIED (pages.js, copy/presentation only — no count/computation/scope/data change; cache v228→v229):
  • B hero differ TOOLTIP — now teaches the practice lens only ("…a different way of doing things, not a gap to
    close. A separate lens from the gauge above; the ones worth acting on appear in your signals."). Deliberately
    does NOT import above/below-market language — that would blur the "not a gap to close" line; the signals
    sub-note (C) carries the "signals also include market positions" load.
  • C Signals panel SUB-NOTE → "market positions and practice differences — we flag, you decide" (states the
    signals scope, so the reader sees why the signals count ≠ the differ count).
  • E Signals page INTRO — fixed a real falsehood: the old "where you stand and the market fact behind it"
    asserted a market position for ALL signals, but the 13 practice signals have no market stance. Now "grounded
    in your peer data … where you sit against the market, or a practice most peers have that you don't".
  A (hero "31 of 76") and D ("See all N signals") unchanged — both numbers true. (Live "See all" shows 82, not 88,
  because the count is USER-SCOPED: 88 engine total minus this user's 6 dismissals — correct, traceable to the
  live set; gate 9c asserts that derivation, not a fixed 88.) Stayed qualitative — NO explicit "20 of 31" bridge
  (it would add a fourth number and reopen the hero-denominator rabbit-hole this thread closed).

CANONICAL PRACTICE PHRASING (David's decision, confirmed): "a practice most peers have that you don't" is the
HOUSE-STANDARD description of a (deficit) practice signal. The upcoming table view's `practice` Verdict value
reuses these exact words rather than coining a third variant. The short chip TAGS stay as shipped — MOST DO THIS
(deficit) / FEW OFFER THIS (ahead) / DIFFERS FROM PEERS (no-norm) — and the directional mirrors ("a practice you
have that most peers don't" for ahead) follow this template; this prose is the canonical descriptive form.

GATE: qa_overview.py gains check #9 (NUMBER-SOURCE — the derive-not-literal principle applied to user-facing copy).
9a: engine emits hero differ/pool/signals-total as integers (differ<=pool). 9b: the hero line interpolates
`${approach.differ}`/`${approach.pool}` RAW — rendered == engine by construction; PROVEN to FAIL on a hard-coded
"31 of 76" or an off-by-one `approach.differ + 1`. 9c: the 'See all N' count is bound to the live signal set
(`signals_all` minus dismissed), never a literal. Full gate now 17/17. VERIFIED rendered at v229: hero text "31 of
76 practices differ from market" + trimmed tooltip; sub-note "market positions and practice differences…"; intro
"grounded in your peer data…". No anchor/seed/snapshot/scope change — copy + one gate check only.

---
2026-06-22 — PRINCIPLE: ONE ENCODING PER FACT (dashboard declutter — presentation only, no data change).

  "A fact already on screen is shown ONCE. Visual restatements of data already present are removed — but only
   after confirming the two encodings carry IDENTICAL information; if one carries a nuance the other lacks, it is
   NOT a restatement and is kept. On the category cards, the two independent number pools — positionable
   (below/on/above) and practice (the differ line) — must stay VISUALLY DISTINGUISHABLE so they never read as one
   running total (they have different denominators and different metric sets)."

This is a VISUAL pass on the verified-clean model — no copy/data/computation/scope change. Each cluster was
confirmed against LIVE data before any cut (this project keeps killing numbers that LOOK related but aren't —
the declutter must not create a new instance):

  CLUSTER 1 — category card triple-encoding. The card showed (a) a below/on/above BAR, (b) the same distribution
  as NUMBERS ("X Below Y On Z Above"), (c) a differ line. (a) and (b) are the same fact (proportion vs count) —
  BUT the bar ALSO carries the per-domain lean NEEDLE (cat-bar-mark, from post.lean), which the numbers don't.
  So the bar is NOT pure redundancy; it carries MORE. DECISION (David): drop the NUMBERS (cat-foot), keep the bar
  — it keeps proportion + needle, and removing the numbers DISSOLVES the denominator collision (e.g. Pay's
  cat-foot summed to 13 = the positionable pool, and the differ line is "13 of 27" — two independent 13s that
  looked linked). Now the differ line is the SOLE number row → nothing to misread it against. Exact per-band
  counts remain on the category detail page. (Cut to whitespace; neighbours NOT re-padded — spacing is a separate
  queued pass.)

  CLUSTER 2 — lead/gaps slider vs P-chip. CONFIRMED NOT a restatement, so NOT cut: the slider dot sits at
  `it.adjusted` (polarity-ADJUSTED favourability), the P-chip shows `it.percentile` (RAW). They DIVERGE for
  lower-is-better/cost metrics — live, "Workforce cost per FTE" is a You-lead row with dot at 97 but chip "P3".
  Dropping the slider would make a lead row read "You lead · P3" (looks like a lag). The slider carries the
  favourability the raw P-chip can't — the cluster-1 trap one layer down. Kept both. (Separately noted for later:
  a raw "P3" on a lead row is itself slightly odd — out of scope here.)

  CLUSTER 3 — card differ-line typography (a fix, not a cut). The footer wrapped to two lines and detached the
  count, caused by flex gaps between count/phrase + the length of "from market". Fixed: count+phrase wrapped in
  one span (`cat-differ-txt`, white-space:nowrap), and "from market" dropped (redundant — the card is already a
  market-comparison context) → "N of M differ", single line, live N/M unchanged. Gate-safe: qa_overview #9b reads
  the HERO line (`approach.differ … practices differ from market`), a DISTINCT string from this CARD line, so the
  number-source gate is untouched — re-ran, still 17/17.

REPORT-ONLY (surfaced, NOT changed): (4) the Governance card is the calmest and sits last, yet Governance
generates 13 of the 88 signals — the MOST practice signals of any domain — so its quiet treatment under-sells its
content by signal contribution (the brief's "2 of 3 Biggest Gaps are Governance" did not match live data — the
gaps are Benefits/Pay/Incentives quantum gaps). (5) the Recognition "indicative" confidence flag renders at the
same micro weight as everything else, so it reads as a label, not a confidence cue — easy to miss.

Cache v229→v230 (index.html + share.html). VERIFIED rendered at v230: Pay card keeps bar + needle, numbers row
gone, differ line "13 of 27 differ" on one line; You-lead/Biggest-gaps rows unchanged (slider + P-chip both
present). Presentation only — no number moved, no gate regressed.

---
2026-06-23 — HOME DASHBOARD: MARKET/PRACTICE LENS TOGGLE + APPLY-STRATEGY TOGGLE.

The home dashboard now SPLITS the two reads it used to cram together (per the CASE B diagnosis: every domain has a
MARKET position read over Substance metrics AND a PRACTICE difference read over Practice/Design metrics). Two
page-level controls (`.ov-controls`, persisted in prefs._overview, default = Market view / strategy applied):

  1. MARKET ↔ PRACTICE view toggle (David: "whole dashboard"). One lens at a time across hero + all 7 cards:
     • MARKET view = the gauge (below/on/above) + per-card distribution bar (with the lean needle) + verdict chip.
       The practice differ line is HIDDEN here (it moved to the Practice view) — so market view is pure market.
     • PRACTICE view = a new ApproachPanel hero ("N of M practices differ from market" headline + a differ/in-line
       bar + legend) and every card shows its approach read (differ count + catp-bar). Governance is a full
       citizen here (its 17-of-32). The market gauge/bars/verdict are HIDDEN. New pages.js component ApproachPanel;
       CategoryTile is now view-aware (early practice branch; market branch unchanged minus the differ line).
     This is the resolution to the "differ from market" vs "differs from peers" visual collision: never show both
     encodings at once — let the reader pick the lens.

  2. APPLY-MY-STRATEGY toggle (David: "full absolute view" when off). Re-fetches /api/overview with `?strategy=off`,
     which sets _strategy=None on the route — reusing the engine's existing strategy=None degrade path (§5.5). Off =
     absolute RAG colours (market.target→None → marketAim→null), impact-ordered signals (no objective re-rank),
     plain verdict. The org's strategy still EXISTS (new payload field strategy_applied distinguishes "applied this
     request" from strategy_complete "one exists"). UX fix: when toggled off-by-choice (strategy_complete &&
     !applyStrat) the hero shows a muted "Strategy off — absolute market view" (arc-target-off), NOT the
     "set your strategy" unset prompt — the user has one, they just turned it off.

ENGINE/DATA UNTOUCHED — display + one query param only. Gate-safe: the ApproachPanel headline carries the exact
qa_overview #9b string (`${approach.differ}</b> of ${approach.pool} practices differ from market`), so the
number-source gate still reads a live hero differ — re-ran, 17/17. Persistence via the shared debounced onPref
(prefs._overview); the 800ms-debounce-cancel-on-immediate-reload edge case (shared with _nav) falls back to the
sensible defaults. Cache v230→v232. VERIFIED rendered at v232: Market view (gauge + card bars, no differ line) ·
Practice view (ApproachPanel "31 of 76 practices differ from market" + 7 practice cards, gauge/bars gone) ·
strategy off → target line "On your target…" becomes "Strategy off — absolute market view", strategy_applied=false,
target/objective null; prefs persist {view, apply_strategy}.

---
2026-06-23 — HOME DASHBOARD: removed the "You lead / Biggest gaps" ranked-chip row (no longer needed). It was
view-agnostic (rendered once below the cat-grid), so it's gone from BOTH the Market and Practice lenses. Clean
end-to-end removal: the grid2 UI block (OverviewHero), the now-dead ChipColumn + LockedPanel components (pages.js),
and the dead backend pipeline that fed only those rows — the `ranked`/`_chips` helpers and the `leads`/`lags`
payload fields (app.py). Board pack / share are unaffected (they use `callouts`, not leads/lags). This also retires
the slider-vs-P-chip "P3 on a You-lead row" oddity flagged in the declutter diagnosis. SPACING reviewed: clean —
the removed section's bottom buffer is covered by the .content container's existing 16px padding-bottom, and the
inter-section gaps use consistent tokens (controls s3 → hero/signals s4 → cards); no orphaned margins, no fix
needed. Left harmless: the slider-only CSS (.chip-band/.band-tick/.tile-dot) — .chip-row/.p-pill stay live (still
used by app.js/strategy.js/card.js). qa_overview 17/17 (payload change didn't regress the gate). Cache v232→v233.

---
2026-06-23 — HOME DASHBOARD: hero gauge → DONUT chart (market + practice). Replaced the needle DIAL with a simple
proportional DONUT (ring) chart in BOTH hero reads, per request ("change the dial to a donut chart - same for
market and practice"). New reusable `Donut` component (pages.js) — segments ∝ count, drawn clockwise from 12
o'clock via stroke-dasharray, a quiet total in the centre; colours passed in by the caller (dumb renderer).
  • MARKET (OverallArc, "Dial" mode → relabelled "Donut" in the Spectrum|Donut toggle): ring of below/on/above
    coloured by the same aim-aware band tones the old dial used (bandTone → MKT_RICH); centre = the pool total
    ("92 · metrics"); the verdict word + leanWord stay BELOW the chart (arc-verdict, unchanged) so nothing is
    duplicated. Spectrum option untouched. The needle SVG/animation is gone (the dead needle vars are harmless,
    left in place).
  • PRACTICE (ApproachPanel): the horizontal bar → a donut of differ (purple --differs) / in-line (neutral);
    centre = "76 · practices"; the gate-string headline ("N of M practices differ from market") kept below the
    donut (now caption-sized) so qa_overview #9b still reads a live hero differ; legend (31 differ / 45 in line)
    retained.
Internal value stays "dial" (so persisted localStorage 'lumi.standStyle' = dial still selects the donut). New CSS
.donut/.donut-svg/.donut-center/.donut-num/.donut-sub; .appr-headline shrunk to fs-body. Display only — no engine/
data change. VERIFIED at v234: market donut 3 segments + "92 metrics" centre + verdict retained; practice donut 2
segments (differ purple rgb(98,87,201)) + "76 practices" centre + headline + legend; needle gone; 0 console errors;
qa_overview 17/17 (#9b green). Cache v233→v234.

---
2026-06-23 — MARKET COLOUR CODE: one consistent rule, two modes by the strategy toggle (David). Replaces the old
"absolute bands (below=red/on=amber/above=green) + aim-aware verdict" split with a single coherent code that the
gauge/donut, category cards, signals and metric page all inherit (changed only the two source functions, so every
surface follows):
  • STRATEGY OFF (no stance) — a POSITION lens: on-market is the green ideal, deviations flagged the same way
    everywhere → below = AMBER (under), on = GREEN, above = RED (over). marketTone remapped from
    below=red/on=amber/above=green → below=amber/on=green/above=red. David's call: applied to below/on/above
    REGARDLESS of direction-of-good (the gauge is favourability-adjusted, so a genuinely-better-than-market metric
    also reads red above — accepted as the simple "position lens", consistency over nuance).
  • STRATEGY ON (stance set) — an ALIGNMENT lens: at OR better than your declared aim = aligned (GREEN), short of
    it = not aligned (RED). Binary, no amber. bandToneAim changed from {aim=green, short=red, past=amber} →
    {short=red, at-or-better=green} to match alignTone (which already did this). NOTE: for a below-aiming org this
    makes the default (strategy-on) dashboard mostly/all green — every position meets-or-beats a low aim — which
    David chose knowingly ("at or better than aim"; red is rarer); toggle strategy OFF to see the position lens.
Tone→colour maps (MKT_RICH/SOFT/CHIP/VCLS, WORD_COL) unchanged — they already render green/amber/red correctly;
only which POSITION maps to which TONE changed. Display only, no engine/data change. VERIFIED at v235 on
Thornbridge (below-aiming): OFF donut below=amber/on=green/above=red + "Below" word amber, Pay card bars match;
ON all-green + "Below" word green. qa_overview 17/17. Cache v234→v235.

---
2026-06-23 — MARKET COLOUR CODE, strategy-ON refinement (David): split "not aligned" into TWO REDS by direction,
and tighten "aligned" to EXACTLY at your aim. Supersedes the strategy-ON half of the entry above (the "at-or-better
than aim = green" rule, which left a below-aiming org all-green/flat). New strategy-ON mapping (bandToneAim +
alignTone):
  • AT your aim  → green  (aligned)
  • BELOW your aim (short / under target) → red  (var(--unfavourable) #C0392B — the brighter red)
  • ABOVE your aim (overshot / over target) → redover  (var(--unfavourable-deep) #8A1C12 — a deeper red)
New tone `redover` added to every market colour map (MKT_SOFT/RICH/CHIP/VCLS/SOLID + WORD_COL) and two CSS classes
(.chip-bad-over, .cat-tile.v-above-over) so the gauge/donut, the verdict word AND the category cards all carry the
two-shade distinction. New token --unfavourable-deep #8A1C12. STRATEGY-OFF unchanged (position lens: below=amber/
on=green/above=red, single red). VERIFIED at v236 on Thornbridge (aim=below): strategy-on donut below=green (at
aim), on+above=deep red (above aim), "Below" word green; the all-green flatness is resolved. The other red
(below-aim) shows for on/above-aiming orgs (symmetric, uses --unfavourable). qa_overview 17/17. Cache v235→v236.

---
2026-06-23 — SCOPE RULING (PRINCIPLE): incentive-LEVEL metrics ARE in the market-rate signal stream; base SALARY
levels are NOT. Settles the Issue-2 finding from the dashboard diagnostic — closed as a deliberate decision, not a
misclassification. No reclassification, no suppression, no code change (NO-OP); logged to prevent re-litigation
from board-pack framing.

  RULING: "Incentive-level metrics (Target LTI, Maximum LTI, and bonus/incentive quanta generally) ARE in scope for
   market-relative verdicts (below / on / above market). Base SALARY levels are NOT."

  RATIONALE: the "structure-not-base-pay" product boundary excludes BASE salary only. Variable-pay amounts (LTI as
  % of base, bonus quanta, STI/LTI design values) are incentive DESIGN, not base pay, and incentive level is
  treated as 100% market-led — so a "LOWER THAN MARKET" verdict on Target LTI (you 35% vs median 60%) or Maximum
  LTI (you 80% vs 125%) is CORRECT and INTENDED.

  SCOPE BOUNDARY (the line):
    IN  — incentive/bonus level & quantum: LTI target/max %, bonus opportunity, STI/LTI design values
          (class=Level under Incentives).
    IN  — pay practices / policy / transparency: e.g. "Salary range in job adverts" (class=Provision, Governance) —
          a practice, always in scope.
    OUT — base salary LEVELS: actual base-pay amounts / salary benchmarking.

  CONFIRMED against live question defs (engine + mp_config):
    • PAYTR_01_42eae7ec        Salary range in job adverts (Board/Exec)  — Governance · class=Provision — practice,
                               in scope ✓ (non-competitive domain → surfaces as a practice signal, not a market verdict)
    • REW_INC_LTI_VALUE_TYP_01 Target LTI (Board / Executive)            — Incentives · class=Level — in scope, market-led ✓
    • REW_INC_LTI_MAX_01       Maximum LTI (Board / Executive)           — Incentives · class=Level — in scope, market-led ✓

  This complements the GOVERNANCE SCOPING RULING (competitive-scope principle) above: that ruling decides which
  DOMAINS carry market framing; THIS ruling decides which pay-LEVEL classes do (incentive yes, base salary no).
  STATUS: no-op — LTI/incentive-level signals remain in the market-rate stream as designed.

---
2026-06-23 — DASHBOARD VISUAL PASS (presentation only — no engine/pool/count/logic; pre-approved). Three changes:
  C1 — VERDICT WORD carries no judgment colour. The hero donut verdict word ("Below/On/Above") now renders in
       neutral --ink, IDENTICAL on Strategy ON and OFF (was aim-green ON / position-amber OFF). "Mirror, not
       consultant" — the platform flags where you stand, it doesn't colour-code below/on/above as success/failure.
       The on-target meaning lives ONLY in the footer ("On your target — you aim to sit below market" /
       "Strategy off — absolute market view"); no "On target" headline added; the donut bands keep their position
       colour; the lean line ("clearly below the market") is unchanged. Removed the now-dead WORD_COL/wordCol.
       pages.js:713 (+ comment). OPEN (flagged, not done): the per-CARD verdict chips (e.g. Pay "below" amber)
       stay coloured — David's call whether to neutralise those too for full consistency.
  C2 — Dropped the Pay card's "benefits-led mix — read the total package" nudge (.cat-mixnote, pages.js) — the only
       interpretive nudge on any domain card; the asymmetry is removed. Pay's verdict chip + spectrum bar untouched;
       the engine d.mix_note field stays live, just no longer rendered.
  C3 — Governance non-applicable treatment (chosen: option (c), dashed placeholder). A muted, hollow, DASHED slot
       (.cat-na-bar, 11px — the spectrum bar's height/position) now sits where competitive cards show their bar, so
       the absence reads as BY DESIGN, never as a bar that failed to load (real bars are solid + coloured). The
       "no market rate" chip and "32 practices tracked · approach choices" text are kept. pages.js noRate branch +
       app.css .cat-na-bar.
NO-OPS honoured: Recognition "indicative" caveat quiet; counts 82/88/92/76 live-derived untouched; signals/strategy
re-rank/LTI signals out of scope. VERIFIED at v237: C1 word #211B26 identical ON & OFF + footer carries meaning;
C2 mixnote gone, Pay chip "below" intact; C3 Governance dashed 11px placeholder + chip + text. 0 console errors;
qa_overview 17/17. Cache v236→v237.

2026-06-23 (follow-up to the visual pass C3) — Governance card simplified per David: removed the "N practices
tracked · approach choices" text entirely; the card body is now just a dashed "N/A" slot (.cat-na, where the
spectrum bar would sit) + the kept "no market rate" chip. Card reads "Governance · no market rate · N/A". Cache
v237→v238. Presentation only.

2026-06-23 (follow-up) — "Where you stand" hero polish: REMOVED the Spectrum/Donut toggle (and the standStyle
state + localStorage) — the hero always renders the donut now; the spectrum is retired from the home hero.
MarketSpectrum component kept (still used on the metric page, pages.js:1477). Donut enlarged 188→210 (stroke 28)
for presence, market + practice both. Spacing tidy: donut→verdict gap 2px→var(--s3) (12px) for breathing room;
verdict word kept at --fs-display (the prominent takeaway), line-height 1.08→1.1. Presentation only. VERIFIED at
v239: toggle gone, donut 210px, donut→verdict 12px, "Below" neutral 30px; 0 console errors. Cache v238→v239.
NOTE: the preview's mini-scale screenshot glitch this session was a stuck 147px viewport — cleared by an explicit
preview_resize to 1280×860.

2026-06-23 — HOME SIGNALS now follow the Market/Practice toggle (David: "signals should only relate to the
toggle"). The home Signals panel is filtered by the lens, reading the SAME position field as the hero: MARKET view
shows position in {below,on,above} (Substance/market-rate signals), PRACTICE view shows {differs,practice}
(Approach signals). signals_all is impact-sorted, so the panel takes the top 4 NON-dismissed of the view; the
"See all N" footer + the sub-note are view-aware ("market positions…" / "practice differences…"). Live (Thornbridge,
director): Market = top 4 / See all 53; Practice = top 4 / See all 29 (53+29=82 = total non-dismissed). pages.js
OverviewHero (_viewSigs/_viewLive/_viewShown/_viewTotal) + SignalsPanel(view). Gate: qa_overview #9c rewritten to
assert the new view-filtered derivation (still derive-not-literal, not a hard count); #4b rewritten for the
Governance N/A treatment (was asserting the removed "practices tracked" text). 17/17. Cache v240→v241. Display/
wiring only — no engine change.
  FLAGGED (not fixed — needs an engine decision): a few PRACTICE-view signals carry market-verdict TAGS
  ("LOWER THAN MARKET", e.g. "Pay increase award rate"/"Paid study time", class=Practice/Design, position=differs).
  Cause: the depth/outlier/rare signal KINDS stamp "HIGHER/LOWER THAN MARKET" regardless of the metric's approach
  class — the recast that reframes a market verdict to a practice statement (signals.py ~713) only fires for
  behind/ahead, not depth/outlier/rare. So these are correctly practice-POSITIONED but read as market verdicts.
  Same class as the Governance signal-label ruling, one kind-set wider. To make practice signals fully read as
  practice, extend the recast/tag-normalisation to depth/outlier/rare on Practice/Design metrics — a signals.py
  change, left for David's go-ahead.

2026-06-23 — COMBINED DASHBOARD FIX (Overview), 5 of 7 approved-write fixes applied; 2 GATED (colour
semantics + practice chip routing) reported for approval, NOT written. Each fix is a discrete, separable edit.
  FIX 2 — gauge headline hierarchy. With a stance set AND on/ahead of target, the gauge word reads "On target"
    (attainment framing) with subtext "sitting <dir> market, as you intend"; strategy-OFF (no target) or behind
    reverts to the direction word ("Below"). Verdict ENUM + below/on/above copy untouched — headline framing only.
    Counts stay live in the 3-col legend (76/15/1). pages.js OverviewHero (_onTarget/_dirPhrase/headWord/headLean).
    JUDGMENT CALL flagged to David: spec asked the subtext to also carry "· 76 below · 15 on · 1 above", but the
    legend directly beneath already prints those three figures — I did NOT duplicate them in the subtext. Awaiting
    his call to inline-or-not.
  FIX 3 — signal-count ranking scaffold. One-line note under each "Signals · top N" header naming the ranking
    basis: Market → "ranked by market gap", Practice → "ranked by rarity". View-derived, no literals; the top-N /
    total counts already derive live. pages.js SignalsPanel + .sig-ranknote (app.css). 53/29 stay disjoint, no dedup.
  FIX 5 — low-confidence caveat distinction. "indicative" (thin coverage) stays the inline annotation
    (.chip-indicative + .indic-flag); "no market rate / N/A" (no peer data — Governance) now reads as a MUTED card
    (.cat-tile-norate: muted top-border + sunk background + softened icon/title). Neither uses --grey-neutral
    (reserved for strategy-attainment OFF, not data-confidence). pages.js card-root + app.css.
  FIX 6 — domain-card axis label. A one-word axis label naming the bar's grammar so the two tabs aren't read on the
    same scale: Market card → "position", Practice card → "differ". .cat-axis (app.css), positioned/practice
    branches only (Governance no-rate has no position bar → no "position" label). pages.js CategoryTile.
  FIX 7 — signal action-icon resting affordance. The pin/dismiss column was opacity:.5 on --ink-faint (read as
    decoration). Raised resting state to opacity:.72 on --ink-soft (visible-but-quiet); row-hover .92 + per-button
    hover/`.on` stay the active emphasis. app.css .signal-row .sig-act.
  VERIFIED live at v242 (Thornbridge, director): Market → word "On target" + "sitting below market, as you intend",
    legend 76/15/1, 6× "position" axis labels, Governance card muted (cat-tile-norate, "no market rate / N/A"),
    ranknote "ranked by market gap", Signals header "top 4", sig-act opacity .72. Practice → 7× "differ", ranknote
    "ranked by rarity", header note "practice differences…". 0 console errors; qa_overview 17/17. Cache v241→v242.
  GATED (diagnosed, NOT written, awaiting David's approval of the fix shape):
    FIX 1 (colour semantics) — proposal: gauge/slider hue driven solely by strategy-ATTAINMENT (on-target green /
      off-target amber / strategy-OFF new --grey-neutral #8A97A6), direction carried by marker position + label
      only. #8A97A6 fails AA on white for label text (~2.98:1) → propose a darker step (#5E6B7A ≈ 4.5:1) for any
      text use; the swatch/fill use of #8A97A6 is fine. Blast radius: the colour fns (marketTone/bandToneAim/
      alignTone) are SHARED by gauge + 7 sliders + chips + signals + the metric page, so the fix must be scoped via
      a NEW attainment-only function, else it ripples to signals + metric page.
    FIX 4 (practice chip routing) — confirmed live: Practice tab shows "LOWER THAN MARKET" on 3 of 4 signal chips
      (tone class is correctly pos-approach; only the TEXT is directional). Cause as previously flagged: depth/
      outlier/rare KINDS stamp directional tags regardless of approach class; the recast (signals.py ~713) only
      fires for behind/ahead. Rarity vocab is NOT canonical (scattered literals 485/651/655/682). Fix = route
      practice-class chips to rarity vocabulary ("MOST DO THIS"/"FEW OFFER THIS"); a signals.py change.

2026-06-24 — FIX 1 + FIX 4 WRITTEN (David approved the gated fix shapes: "go ahead"). Each a discrete unit.
  FIX 1 — ATTAINMENT COLOUR LENS (web/js/pages.js + web/css/app.css). The OVERVIEW gauge donut, the per-domain
    slider bars and the gauge-card verdict chip + card tint now colour by STRATEGY ATTAINMENT, not market direction:
    on your aim = green, off your aim = amber (direction-agnostic), no strategy = grey-neutral (no judgement).
    Direction is carried by the marker position + the below/on/above WORD + the legend, never by hue. New
    attainTone(verdict, aim) → green|amber|grey; "grey" key added to MKT_SOFT/RICH/CHIP/VCLS/SOLID. New tokens
    --grey-neutral #8A97A6 (fill/border/swatch) + --grey-neutral-ink #5E6B7A (text — #8A97A6 fails AA on white at
    ~2.98:1, so the darker step carries any label). New .chip-neutral-mkt + .cat-tile.v-neutral-mkt. arc-target chip
    aligned: behind → amber-bright (off target), off → grey-neutral-ink. The hero donut became a SINGLE hue (rich
    MKT for the verdict band, soft for the rest) — the old below=amber/on=green/above=red tricolour is retired on the
    gauge; the below/on/above split now reads by arc SIZE + the legend. _gaugeAttain derives from
    market.target.alignment so on_target/ahead → green, behind → amber, no target → grey (mirrors the Fix-2 headline).
    SCOPE = OVERVIEW ONLY: the signals list (posColor/marketTone), the metric-page MarketSpectrum, the /category
    detail-page hero, and all practice/differs (purple) encodings were LEFT on their existing direction colour by
    design. KNOWN FOLLOW-UP (flagged to David): the /category detail page + the metric-page spectrum still use the
    old direction/two-red logic, so a card that reads green on the overview opens to a page still on the old palette
    — extend the attainment lens to those two surfaces in a follow-up if David wants full consistency.
    VERIFIED live at v243 (Thornbridge, director): strategy ON + on-target → donut single GREEN (MKT_RICH.green verdict
    band + MKT_SOFT.green rest), every card chip "below" coloured chip-good + v-at + green slider, arc-target green.
    Strategy OFF → donut single GREY (MKT_*.grey), chips "below" in .chip-neutral-mkt text #5E6B7A on #8A97A6 border,
    v-neutral-mkt, arc-target "Strategy off" #5E6B7A, headline word reverts to "Below" (Fix 2). Off-target AMBER path
    is code-reachable (verdict rank != aim) but not visible in Thornbridge (all domains on-target). 0 console errors.
  FIX 4 — PRACTICE-TAB VOCABULARY FIREWALL (server/signals.py, after the competitive-differs recast). The dashboard
    Practice tab showed 4 signals reading "LOWER/HIGHER THAN MARKET" (Tronc participation groups [depth/Design], Pay
    increase award rate + Paid study time + Pay review frequency [outlier/Practice]) — the kind-gated recast (767-798)
    only converts behind/ahead, so depth/outlier leaked. Added a kind-AGNOSTIC firewall keyed on the FINAL position:
    any position=="differs" signal still carrying a directional market tag ("...THAN MARKET" / "£ GAP" / "ABOVE|BELOW
    MARKET") is re-routed to rarity/approach/peer vocab — a common practice you lack → MOST DO THIS; a Practice/Design
    approach → DIFFERS FROM PEERS; a quantity → HIGHER/LOWER THAN PEERS — mirroring the non-competitive branching.
    DISPLAY-ONLY: rewrites tag + stand + detail + label_short + value_display; position, kind, impact, ranking, counts
    and the gauge are byte-identical. VERIFIED on the live engine: leaked directional practice tags 4 → 0; gauge
    counts 76/15/1/92 UNCHANGED; 33 practice signals unchanged; the 4 leaks rerouted (3 → MOST DO THIS, 1 → DIFFERS
    FROM PEERS). Dashboard Practice tab now reads DIFFERS FROM PEERS / MOST DO THIS / FEW OFFER THIS. NOTE: "DIFFERS
    FROM MARKET" (competitive-differs approach, no adoption majority) is left as-is — non-directional, not forbidden;
    the firewall only targets the directional "...THAN MARKET" the prompt prohibits.
  GATES: qa_overview 17/17 (0 failures); qa_focus 28/0. Cache v242→v243. An adversarial multi-dimension review
    (scope-containment / verdict-vocab / engine-invariants / a11y-contrast / attainment-logic) was run pre-go-live.

2026-06-24 — ADVERSARIAL REVIEW OUTCOME (5 dimensions × find→verify). 3 dimensions CLEAN: scope-containment (Fix 1
  did not ripple into signals/metric-page/category-page — those stay on marketTone/bandToneAim by design),
  engine-invariants (Fix 4 mutates only tag/stand/detail/label/value_display — position/kind/impact/counts/gauge
  byte-identical), attainment-logic (attainTone correct incl. verdict "at"; donut single-hue; ApproachPanel practice
  donut untouched). 2 confirmed findings:
    (1) A11Y/CONTRAST [FIXED] — the v-neutral-mkt card state-border used --grey-neutral #8A97A6 at ~2.96:1, just under
        WCAG 1.4.11's 3:1 for a non-text state indicator. Darkened --grey-neutral #8A97A6 → #7A8A9C (≈3.5:1) so the
        border + chart fills clear 3:1; TEXT still uses the darker --grey-neutral-ink #5E6B7A (≈5.4:1). Re-verified
        live: --grey-neutral resolves to #7A8A9C, green default clean, 0 console errors. Cache v243→v244.
    (2) "DIFFERS FROM MARKET" reaching the practice tab [RULING: not a defect, no code change]. The reviewer flagged
        line 793's "DIFFERS FROM MARKET" (competitive-differs approach, low adoption) as a market tag the Fix 4
        firewall doesn't catch. RULED non-defect: "differs from market" is the CANONICAL label for position=differs in
        the position taxonomy (POS_TAG_TEXT, pages.js:910 — differs:"differs from market", practice:"differs from
        peers"); it is NON-directional, so it does NOT violate the prompt's prohibition ("never LOWER/HIGHER THAN
        MARKET"), and it had 0 live instances. Changing it to "DIFFERS FROM PEERS" would contradict the differs
        taxonomy used across the signals page. FLAGGED to David: if the Practice tab should avoid the word "market"
        entirely, that's a taxonomy-wide change to the differs label (POS_TAG_TEXT), a separate decision — not folded
        into Fix 4.

2026-06-24 — CATEGORYPAGE ATTAINMENT LENS · PART A WRITTEN (David approved both diagnostic rulings). Extends the
  Fix 1 attainment lens to the /category hero — same tokens, no parallel scheme. Scope: CategoryPage only; MetricPage
  (cardPosition/.pos-pill) explicitly UNTOUCHED.
    1. MarketSpectrum (pages.js:520) — bands now colour by attainTone(v, aim) (single hue: on-aim green / off amber /
       no-aim grey), verdict band MKT_RICH + rest MKT_SOFT, exactly like the gauge donut. The below=amber/on=green/
       above=red tricolour is RETIRED on the spectrum. Direction stays SPATIAL — axis position + the per-band labels
       ("below market"/"on market"/"above market") + the blue "your aim" zone bracket + the "you are here" marker are
       all UNCHANGED, so no information is lost. Band geometry (sizes/positions) untouched — only hue moved.
    2. Category hero chip (pages.js:~1484) — chipCls now from attainTone(verdict, aim), mirroring the overview card;
       chip TEXT still states the absolute position (below/on/above). Grey-off path reuses .chip-neutral-mkt + the
       #7A8A9C / #5E6B7A tokens.
    3. DELETED the vestigial `col` (was MKT_SOLID[absTone]) — computed, never rendered. `absTone` removed with it.
    ORPHANS (left defined, flagged — out of this pass's delete scope): alignTone (pages.js:449) now has NO callers;
       MKT_SOLID (497) now has NO consumers; bandToneAim (465) is referenced ONLY by the unrendered dead-arc
       computation (bandTone @651 → 678). marketTone STAYS LIVE (signals posColor:921 / posTag:934) — untouched.
       These three are cleanup candidates for a later sweep, not deleted here.
    VERIFIED live at v245 (Thornbridge, strategy ON / on-target, /category/Pay): hero chip green ("below", chip-good);
       spectrum single green (MKT_RICH.green verdict band + MKT_SOFT.green rest, redover gone); "you are here" marker
       sits inside the "your aim" bracket; per-band labels + aim bracket + marker all present; 0 console errors.
       A green overview card now opens to a green category — the strategy-ON divergence is CLOSED. Signals colour
       unchanged; MetricPage/cards untouched. Cache v244→v245 (JS-only, no server restart).
    GREY-OFF STATUS: NOT yet propagated — Part B (strategy-off propagation to the category) is GATED, awaiting David's
       ruling (WIRE IT vs REAL-AIM ALWAYS). The green/amber lens is correct regardless of that outcome.

2026-06-24 — CATEGORYPAGE ATTAINMENT LENS · PART B WIRED (David ruled "WIRE IT"). The /category page now honours the
  overview's strategy-off toggle so the attainment lens is consistent across surfaces. CategoryPage reads the SAME
  source of truth as the overview — the persisted pref _overview.apply_strategy — and appends &strategy=off to its
  /api/overview fetch when the strategy is off (pages.js ~1438: `const applyStrat = (prefs._overview||{}).apply_strategy
  !== false`; fetch gains `(applyStrat ? "" : "&strategy=off")`; applyStrat added to the useEffect deps). No server
  change, no tone-fn change: with strategy off the overview payload returns hero.market.target=null → marketAim()=null
  → attainTone() already yields grey. Domain verdicts persist (absolute), so the position still renders — only the hue
  goes grey and the "your aim" bracket drops (no aim to draw).
  VERIFIED live at v246 (Thornbridge, /category/Pay): strategy OFF → hero chip grey (.chip-neutral-mkt, #5E6B7A),
  spectrum bands MKT_*.grey, "your aim" bracket correctly ABSENT, spatial labels + "you are here" marker still present;
  strategy ON → green restored (chip-good, MKT_RICH.green, aim bracket back). 0 console errors. Pref left ON (default).
  Cache v245→v246 (JS-only, no server restart). The overview↔category divergence is now CLOSED on BOTH the
  strategy-on (green/amber) and strategy-off (grey) paths.

2026-06-24 — WIRED pay_for_performance (coarse RE-RANK). The strategy dial pay_for_performance (egal|moderate|
  strong) was captured but read nowhere in surfacing; now it re-ranks the signal briefing. Mechanism: a SECOND
  impact multiplier mirroring the primary_objective re-ranker, keyed on the signal's DOMAIN (sub_power=="Incentives",
  23 metrics) — NOT a new per-metric tag (coarse: directionally right, imprecise at the margins; a variable_pay tag
  is the deferred precision step). signals.py: P4P_INCENTIVE_MULT {strong:1.4, egal:0.7} + _p4p_mult(strategy,
  domain) (after _objective_mult); the application site (was the bare objective line) now applies a CAPPED PRODUCT.
  COMPOSITION RULING (David, AskUserQuestion 2026-06-24): the two multipliers key on DIFFERENT axes (objective→lens,
  P4P→Incentives domain) so both can hit one signal; compose as min(objective_mult × p4p_mult, 2.0) — a capped
  product, magnitudes strong 1.4 / egal 0.7, moderate/unset → 1.0. The cap bounds the runaway double-boost
  (strong-P4P + attract → 1.6×1.4=2.24, clamped to 2.0; live Thornbridge objective=cost → a save-lens Incentives
  signal 1.7×1.4=2.38 clamps to 2.0). DISPLAY/RANKING ONLY — changes signal ORDER, never which signals exist, the
  gauge, counts, or position/kind.
  DEGRADE: pay_for_performance unset/skipped or strategy=off → _strategy_field None → p4p_mult 1.0 → strat_mult ==
  objective_mult (cap never bites, objective ≤1.7<2.0) → byte-identical to pre-change. moderate → 1.0 (exact no-op).
  VERIFIED (non-mutating harness over Thornbridge, build_signals variants): same SET of 88 signals across egal/
  moderate/strong/unset; position+kind identical; strong → every Incentives signal ranks UP, egal → every one DOWN;
  moderate == unset (exact no-op); non-Incentives strat-multiplier identical across all 4 variants (n=70, byte-
  identical impact); cap math confirmed (save×1.4=2.38→2.0). qa_overview 17/17; live gauge 76/15/1/92 unchanged
  (Thornbridge is moderate → no-op); 0 console errors. Backend-only (signals.py) — server restarted, NO cache bump
  (no web asset changed).

2026-06-24 — THREE-STATE SURVEY FIELD TREATMENT (strategy capture UI, UI-only). The reward-strategy capture now
  reflects each field's wiring status, via a config-driven FIELD_STATE map in web/js/strategy.js (mirrors the
  planeBfields/planeCfields arrays): "coming" = HIDE (wired later), "context" = SHOW-BUT-LABEL (collected on purpose,
  not wired to surfacing), "live" (default) = render normally. Current map: transparency → "coming" (hidden pending
  its precise tag in the deferred step-3 tagging pass); budget_direction / risk_appetite / acute_pressure → "context"
  (kept for board-pack narrative / future, but not shaping signals today); everything else incl. pay_for_performance
  → "live". shownFields() filters "coming" from the rendered plane arrays + the review read-back; DialCard renders a
  muted "Context" badge (sibling of Optional) + a quiet note "Kept for context — this doesn't shape your signals yet."
  in place of the live blue signal-effect reveal (reuses --grey-neutral / --grey-neutral-ink). Plane-B footer count is
  now dynamic (shownFields(planeBfields).length = 6 dials, was literal "7"); Plane-C stays 4. NOTHING changed in:
  columns, enums, the save route, the completion gate (REQUIRED = market_position/reward_mix/primary_objective, all
  visible → still completable), or the engine. Re-showing transparency once wired = a ONE-LINE flip ("coming"→"live").
  Cache v246→v247 (web-only, no server restart). DEGRADE: transparency hidden → not asked → fresh org stores it
  skipped (None + provenance skipped → engine no-op, byte-identical); a returning org's prior value rides along in
  `strat` (seeded from d.strategy) → preserved, NOT wiped (reversible, UI-only).

2026-06-24 — STEP-3 FLAG (stale transparency value — DECISION REQUIRED when transparency is wired). Because hiding is
  UI-only and `strat` seeds from the stored strategy, a returning org that SET transparency BEFORE it was hidden keeps
  that stored value (preserved, not wiped). It is inert today (transparency is CAPTURED-BUT-IGNORED). RISK: when
  transparency is WIRED in step 3, that stale stored value would silently go LIVE — driving surfacing — without the
  user having seen or reconfirmed it (it's been hidden from the form). DECISION REQUIRED at step 3, do NOT resolve
  now: respect the stored value (continuity) vs force a reconfirm (re-ask before a hidden, unwired field reactivates).
  David's lean: RECONFIRM. Logged here so the step-3 wiring pass cannot miss it.

2026-06-24 — RISK/POSITION SPLIT (Option 1) — step-3 prerequisite, Phase B BUILD. Marks each signal risk-framed vs
  position-framed; the risk_framed flag is the EXEMPTION surface per-domain suppression (step-3 layer 5) will read so
  it can never hide a genuine floor (the maternity-zero guard). DISPLAY-ONLY in effect now; suppression is NOT built.
  FIELD (David-ruled): a top-level "risk_metrics" curated qid LIST in signal_lenses.json — NEVER a heuristic, every
  flag traces to the list. CURATED RISK SET (conservative first cut, exactly 3): REW_BEN_FAM_002 (enhanced maternity),
  REW262_TIME_SICKDAYONE (sick pay from day one), REW26_WEL_EAP (EAP). Ruled NOT-risk (POSITION despite absence
  phrasing): REW26_BEN_PENSION_MATCH — pension level is the core strategic lever a lag org legitimately pulls, a
  distance a strategy explains, not a floor. PAYTR_02 (pay-ranges-visible) deferred to the step-6 transparency tagging
  pass, not a risk. PRINCIPLE (David): risk = an absence that's cheap/near-universal to provide AND carries
  duty-of-care / statutory-adjacent / reputational exposure no pay strategy excuses; position = a distance a deliberate
  strategy explains.
  ENGINE (signals.py): risk_set = set(cfg.get("risk_metrics") or []) loaded once; in the enrichment loop (~:710,
  beside domain/position/mp_class) s["risk_framed"] = s["question_id"] in risk_set. A STABLE, QUERYABLE property that
  rides the signal dict — survives the Fix-4 firewall, the §5.2 reframes, _suppress and cap_briefing — so suppression
  and the client both read it. Purely additive: touches NO impact/sort/position/kind/counts/gauge.
  CLIENT (pages.js + app.css): s.risk_framed → "is-risk" row class on all three signal surfaces (home panel, signals
  page, category page) → a CORAL left accent (--lumi-coral #F08C6E — ATTENTION, not a RAG verdict; deliberately NOT the
  traffic-light red we removed) + a quiet shield "Risk" marker by the name. Position rows unchanged.
  VERIFIED live at v248 (Thornbridge): [b] gauge 76/15/1/92 + 88 signals BYTE-IDENTICAL; signals.py diff is additive
  (risk_framed only — grep-proven, no impact/sort/position/kind). [f] PREREQUISITE — all 88 signals carry risk_framed
  in the serialized /api/overview payload (queryable downstream ✓). [d] exactly the 3 curated qids are true; pension-
  match FALSE; every flag traces to the list. [e] maternity True / pension-£206k False (headline test). [a] coral
  accent rgb(240,140,110)=#F08C6E + "Risk" marker, distinct from position rows; coral NOT red. [c] same 3 flagged
  under strategy ON and strategy OFF (risk is a signal property, not strategy state). [g] 0 console errors. Backend+web
  → server restarted, cache v247→v248.

2026-06-24 — STEP 3 LAYER 1 (SCHEMA): per-domain market_position target column. First layer of the per-domain tension
  chain. STORAGE + SAVE PATH ONLY — no engine consumption, no capture UI (those are layers 2/3). David rulings baked
  in: single nullable JSON column (NOT 7 columns / NOT a child table); strict-reject validation; key validation DERIVED
  from the config, not a hardcoded domain list.
  db.py: `domain_targets TEXT` added to the org_strategy CREATE TABLE + "ALTER TABLE org_strategy ADD COLUMN
  domain_targets TEXT" in the migration-lite try/except tuple (idempotent; mirrors the existing pattern, no new
  mechanism). Nullable, no default.
  app.py PUT /api/strategy: validates domain_targets right after benefits_lead. STRICT REJECT (400): each value must be
  in market_position's lag|match|lead; each domain must be a KNOWN competitive domain. KEY VALIDATION FIX (QA-caught):
  _mp_competitive(cfg, dom) DEFAULTS TO TRUE for domains absent from the config, so it alone does NOT reject unknown
  keys (it only rejects Governance, which is present with competitiveness=False). Gate is therefore
  `dom in cfg["_domains"] AND _mp_competitive(cfg, dom)` — rejects unknown domains AND Governance through one
  config-derived gate (no hardcoded six-domain list; tracks the config automatically). Persisted as
  json.dumps(dt) or None; "domain_targets" added to the INSERT cols/row_vals; provenance "set"/"skipped" like the
  other fields. strategy_state read-back adds strat["domain_targets"]=uj(...) so it round-trips.
  DEGRADE CONTRACT (design for layer 3; storage supports it now): domain present → use that domain's stance; domain
  absent → fall back to the global market_position; whole column null → byte-identical to today. Per-domain
  independent (partial capture inherits global per-unset-domain) via the field_provenance skipped→None→fallback
  discipline. NO CONSUMER YET — strategy_for_engine / positions.py / signals.py untouched; the column exists and
  persists but nothing reads it for surfacing or the gauge.
  VERIFIED live (Thornbridge): [a] migration applied (domain_targets col, nullable, no default), existing org NULL (no
  data loss), init_schema idempotent (ran twice clean). [b] LAYER BOUNDARY: gauge 76/15/1/92 + 88 signals BYTE-
  IDENTICAL before, WITH domain_targets={Pay:lag,Benefits:lead} set, and after restore (no consumer leaked forward).
  [c] {Pay:lag,Benefits:lead} persists + round-trips on reload; other strategy fields preserved. [d] STRICT REJECT
  400 on invalid stance (leadx), unknown domain (Foo), AND Governance. [e] partial {Pay:lag} persists Pay only.
  [f] wal_checkpoint(TRUNCATE) + gitignored .bak taken before the migration. qa_overview 17/17. Thornbridge restored
  to domain_targets=NULL. No cache bump (backend-only); server restarted to apply the migration.

2026-06-24 — STEP 3 LAYER 2 (CAPTURE UI): per-domain market_position overrides. Collects per-domain intent into the
  layer-1 domain_targets column. David UX ruling: Option A "GLOBAL + REVEAL" — the single global market_position dial
  stays the default; a quiet "Refine by area" pill under it reveals a per-domain ScaleTrack for each competitive
  reward area, only on opt-in (most orgs set global only; the form doesn't balloon). Copy ruling: the global dial's
  "refine by job family later" → "refine by area below" (overrides are per reward DOMAIN, not job family).
  strategy.js: new DomainOverrides component (reveal + per-domain ScaleTrack reusing skey="market", the SAME
  lag|match|lead dial); DialCard gains an `extra` slot rendering it under the market dial; setDomainTarget writes
  strat.domain_targets — a PARTIAL dict (only picked domains carry a key; "Clear" deletes a key → back to inherit).
  reviewRow shows "· N areas refined" on the market_position row. Domains come from data.competitive_domains, NEVER
  hardcoded. app.py strategy_state adds competitive_domains = [d for d in _domains if _mp_competitive] — the SAME
  config source the save-route validation uses, so UI list and validation can't drift. app.css: .dom-* reveal/panel
  styles. NO engine consumption (layer 3) — this layer only WRITES domain_targets via the existing validated save route.
  DEGRADE: an un-overridden domain sends NO key (UI shows "follows overall") → inherits the global aim; partial
  capture → partial payload, never padded with the global value for untouched domains.
  VERIFIED live at v249 (Thornbridge): [a] reveal renders inside the market dial; expanding shows 6 competitive domains
  (Pay/Incentives/Benefits/Time Off/Wellbeing/Recognition), Governance ABSENT. [b] PUT {Pay:lag,Benefits:lead} persists
  + round-trips on reload. [c] DEGRADE: set Pay+Benefits → "2 set"; Incentives/Time Off show "follows overall" (unset,
  no key) → partial payload (proven: {Pay:lag} persists Pay only). [d] overrides optional — not in REQUIRED/planeReq;
  footer count stays "6 dials" (overrides are sub-dials of market_position, don't inflate it); survey completable
  without touching them. [e] LAYER BOUNDARY: gauge 76/15/1/92 + 88 signals BYTE-IDENTICAL before, WITH domain_targets
  set, and after restore (engine layer 3 not built). [f] competitive_domains config-derived (add/remove a competitive
  domain → UI tracks). [g] 0 console errors. strict-reject 400s still hold (invalid stance / unknown domain /
  Governance). Thornbridge left at domain_targets=NULL (browser QA didn't Save). Cache v248→v249; server restarted
  (strategy_state change). Engine = layer 3, separate pass.

2026-06-24 — STEP 3 LAYER 3 (ENGINE): per-domain alignment from domain_targets. Threads the layer-1/2 column into
  the engine so each competitive domain reads its verdict against ITS OWN aim — the queryable input layer-4 suppression
  needs (parallel to risk_framed). SCOPE = C (ruled, David): compute per-domain alignment + thread domain_targets in;
  DASHBOARD BYTE-IDENTICAL this layer; card-recolour DEFERRED to its own ruled pass; suppression NOT built here.
  Three edits, all degrade-to-global by construction:
  (1) app.py strategy_for_engine: out["domain_targets"] = uj(row["domain_targets"]) or {} — the ENGINE strategy load
      (distinct from the API GET strategy_state) previously STRIPPED the column. NULL col → {} so every .get(sec)=None.
  (2) positions.py _market_target(market, strategy, stance_override=None): stance = stance_override or
      _strategy_field(strategy,"market_position"). Same annotation contract (never touches counts/lean/gauge); the
      override just swaps which aim the verdict is read against. None → global (degrade).
  (3) positions.py _hero_signals_classified loop: _dts = (strategy or {}).get("domain_targets") or {} before the loop;
      d["target"] = _market_target(d["position"], strategy, stance_override=_dts.get(sec)) before domains.append(d).
      Governance excluded BY CONSTRUCTION — the non-competitive branch (_mp_competitive False) continues before this
      line, so it never gets a target.
  ROUTING per scope C: server attaches d["target"]; FRONTEND NOT TOUCHED. Verified: the per-domain tiles colour from
  aim=marketAim(m) (the GLOBAL aggregate market.target.stance, pages.js:271/433) — the new per-domain d.target is passed
  into CategoryTile via d but NEVER read (grep: no d.target/domain.target read anywhere in web/js). So it is inert on
  screen, live only in the data layer for layer 4. No cache bump (no web change).
  VERIFIED live (Thornbridge, global market_position="match", all 6 competitive verdicts "below"): ⭐[a] DEGRADE BOTH
  HALVES side by side — (i) NULL domain_targets → every competitive domain target={stance:match,alignment:behind}
  (degrade-to-global), Governance target=None; (ii) {Benefits:lag} → Benefits target={stance:lag,alignment:on_target}
  DIVERGES from the global read (behind→on_target), all 5 un-overridden domains BYTE-IDENTICAL to the global read,
  Governance still None. [b] GAUGE INVARIANT 76/15/1/92 + 88 signals identical null vs override vs restore. ⭐[c]
  QUERYABLE-FOR-SUPPRESSION: Benefits.target present + both fields populated on the override domain in the payload
  layer-4 reads. [d] SCOPE C: dashboard numbers byte-identical (gauge "On market", all 7 tiles render); target unread by
  frontend. [e] GOVERNANCE: no target in either state. [f] Thornbridge restored to domain_targets=NULL post-QA. [g] 0
  console errors. QA harness /tmp/dt_qa_l3.py (13/13 PASS), preserves the full enum set on every PUT. Server restarted
  (no --reload). ⛔ Layer 4 (suppression) = separate pass — reads d["target"] + risk_framed to suppress confirming
  non-risk signals per domain.

2026-06-24 — STEP 3 LAYER 4 (SUPPRESSION): confirm/tension shedding — the payoff. The FIRST layer that changes the
  signal SET: a signal in a domain whose position CONFIRMS its aim is noise ("you chose this and you're sitting on it")
  and is shed; a risk_framed signal pointing the same way is exposure, NOT confirmation, and is EXEMPT (the maternity-
  zero guard). Completes the per-domain tension chain: capture (L2) → engine alignment (L3) → suppression (L4).
  RULINGS (David 2026-06-24):
  (1) ACTION = C (demote + cap-aware), NOT hard-suppress. A confirming non-risk signal is flagged s["confirm"]=True and
      its impact demoted (CONFIRM_DEMOTE_MULT=0.25); cap_briefing gains a confirm-aware pass so it sheds OFF the home
      briefing (tension/risk fill first) but STAYS in the full Signals list (signals_all) — honours the cap's standing
      "never a silently dropped signal" contract. NOT removed anywhere.
  (2) CONFIRM = alignment == "on_target" ONLY. "ahead" (overshoot/overspend vs the aim — only arises for a match/lag
      aim) and "behind" (the gap) both STAY actionable. Only "sitting exactly on the aim" is suppressible noise.
  (3) EXEMPTION = `not s["risk_framed"]` AND alignment=="on_target", checked in the signals.py enrichment loop after
      risk_framed is stamped (:729). risk_framed signals never get confirm=True → never demoted.
  (4) SCOPE = global-aim INCLUDED: domain_alignment degrades to the global market_position, so any domain that confirms
      (global OR per-domain override) sheds. The degrade-to-byte-identical baseline is STRATEGY-OFF (no aim → empty map
      → nothing confirms). Thornbridge (global match, all six domains below→behind) confirms NOTHING globally, so an
      override is what introduces the first confirm.
  (5) WIRING (single source of truth): app.py overview derives _dom_align = {domain: target.alignment} from hero["domains"]
      (the L3 output, built at :1374 BEFORE build_signals at :1392/:1395) and threads it as the new build_signals
      domain_alignment= param. Alignment is NOT recomputed inside signals.py (which has no per-domain aggregate verdict —
      doing so would duplicate positions.py and risk drift). org_signals (nightly sweep, :1565) passes no strategy →
      domain_alignment=None → notifications stay strategy-neutral (unaffected). The AI-diagnosis endpoint (:1500) uses
      compute_findings, not build_signals — untouched.
  HOOK: signals.py build_signals enrichment loop, alongside the existing _suppress (:877, location-agnostic) and
  family-over demote (:883) precedents; reads s["domain"] (:718) + s["risk_framed"] (:729) + the threaded map. The
  s["confirm"] flag rides the signal dict (queryable, parallel to risk_framed) but is NOT rendered (card treatment
  deferred, like L3's target). GAUGE: untouched — hero["market"]=_pool_verdict (positions.py:1019) is built before and
  independent of build_signals; suppression is signals-only.
  (6) on_plan DRIFT (logged per David): app.py:1527 computes a DIFFERENT "on_plan" notion for the AI strategy-diagnosis
      narrative (competitive domain with a verdict AND not flagged by compute_findings) — NOT the L3 target.alignment
      used here. The two "doing-what-you-intended" definitions can diverge; reconciling them is FUTURE work, explicitly
      not this pass.
      RESOLVED 2026-06-24 (cleanup sweep, ruling C — DOCUMENT-ONLY, no behaviour change): the two are INTENTIONALLY
      DISTINCT concepts, not a bug to unify. on_plan = "inferred-aim-clean" — domain_aims(strategy) infers a per-domain
      aim from the COARSE dials (market_position + reward_mix + pay_for_performance heuristics; e.g. reward_mix=benefits →
      Benefits lead / Pay lag) and on_plan = competitive domains with a verdict whose actual==inferred-aim (compute_findings
      flags any delta≠0). target.alignment = "explicit-override-met" — _market_target reads the EXPLICIT domain_targets[sec]
      (→ global market_position), no reward_mix/P4P nudges. They diverge where (a) a domain_targets override is set
      (target.alignment honours it; the narrative's domain_aims does NOT read domain_targets) or (b) reward_mix/P4P nudge a
      domain's inferred aim (domain_aims applies the nudge; target.alignment does not). Both are valid for their surface:
      the narrative wants an inferred clean-bill read incl reward_mix intent; suppression/colour want the explicit per-domain
      verdict-vs-aim. Option A (point on_plan at target.alignment) REGRESSES — it loses the reward_mix/P4P nudges; Option A′
      (extend domain_aims to honour domain_targets, override > nudge) is a real FEATURE change to the AI narrative and is
      AVAILABLE as its own future diagnosed pass if the narrative should respect explicit per-domain overrides. Closed as
      intentional-distinct; no code change.
  VERIFIED live (Thornbridge, global match; REW_BEN_FAM_002 maternity + REW262_TIME_SICKDAYONE sick-pay both sit in the
  Time Off domain): ⭐[a] COUNT-CHANGE BOTH HALVES — (i) strategy-off AND strategy-on-no-override → ZERO confirm anywhere
  (degrade, all-behind nothing confirms); (ii) Time Off→lag → Time Off confirms (on_target), its 8 NON-risk signals all
  flagged confirm + demoted (median full-list rank 48/88 → 84/88), full-set COUNT unchanged + Time Off id-set identical
  (demote ≠ delete). ⭐[b] MATERNITY-ZERO SURVIVES — REW_BEN_FAM_002 (risk_framed, in the CONFIRMING Time Off domain) is
  NOT flagged confirm, holds full-list rank 5/88, survives into the briefing; REW262_TIME_SICKDAYONE likewise exempt.
  [c] TENSION UNTOUCHED — Incentives (still behind) carries no confirm; ONLY Time Off does. [d] NO-TARGET DEGRADE —
  Governance + strategy-off never confirm. [e] CAP — hard-reserve holds (≤5, ≤3 behind, ≤2/lens) both states; briefing
  led by non-confirm, confirm only backfills if room. [f] GAUGE 76/15/1/92 identical across off / no-override / override.
  [g] Thornbridge restored to domain_targets=NULL; 0 console errors; web untouched (no cache bump). QA /tmp/dt_qa_l4.py
  20/20 PASS. Server restarted (no --reload). ⛔ Per-domain strategy-tension chain COMPLETE. Tagging pass
  (variable_pay / transparency precision) remains as separate parallel work.

2026-06-25 — STEP 3 TAGGING PASS · UNIT 1 (variable_pay). Upgrades the pay_for_performance re-rank from COARSE
  domain==Incentives keying (commit 94a64b4 — every Incentives metric got the multiplier) to PRECISE per-metric: only
  the curated variable_pay set gets the P4P bump/demote (strong 1.4 / egal 0.7 / moderate·unset 1.0). CLASSIFICATION
  work — David-judgment-authoritative; an independent diverse-lens (amount / product / taxonomy) classification proposed
  the set, David ruled.
  FIELD (David-ruled): a curated "variable_pay_metrics" qid LIST in signal_lenses.json — the risk_metrics precedent
  (David-owned, never a heuristic). SET (7, David-ruled): 323ffcf1-… (max bonus % by level), REW_INC_111 (target bonus
  % by level), REW_INC_104 (avg payout %), REW_INC_LTI_MAX_01 + REW_INC_LTI_VALUE_TYP_01 (max/target LTI %) — the 5
  unanimous AMOUNT/opportunity metrics — PLUS REW_INC_131 (operate-LTI) + REW_INC_135 (operate-commission): provision-
  EXISTENCE of a contingent-pay vehicle is P4P-relevant (David). OUT: the other 16 Incentives metrics, incl REW_INC_061
  (individual/business split — design), REW_INC_072 (sign-on — NOT performance-contingent, explicitly out), REW_INC_132
  (LTI types — design), malus/clawback (070/071 — governance), and the overtime/shift premiums.
  WIRING: signals.py _p4p_mult(strategy, qid, variable_pay_set) keys on `qid in variable_pay_set` (was `domain ==
  "Incentives"`); vp_set loaded once from cfg.get("variable_pay_metrics") beside risk_set; application site passes
  s["question_id"] + vp_set. No variable-pay metric exists OUTSIDE Incentives (scanned) — the set is entirely within the
  domain. INDEPENDENT of the L2-L4 suppression chain: this changes a re-rank MULTIPLIER (impact ×=), not the confirm/
  suppress mechanism; gauge + L4 exemption untouched.
  DEGRADE: pay_for_performance moderate/unset/strategy-off → multiplier 1.0 everywhere → byte-identical. Were the set the
  full Incentives domain, output == the old coarse behaviour byte-for-byte (proven). Precise set ⊊ coarse → the 16
  excluded metrics LOSE the multiplier (the only place the coarse net was too wide).
  ⚑ HYGIENE FLAG (David, for a FUTURE pass — NOT this one): REW_Q528801 / REW_Q534581 (overtime & hourly shift-pay
  multipliers) are Level metrics MISFILED in the Incentives domain — they are time/shift PREMIUMS, not performance-
  contingent pay. The variable_pay tag correctly excludes them; the domain misclassification itself wants a separate
  hygiene fix.
  VERIFIED (Thornbridge surfaces both tagged + non-tagged Incentives signals): [A] UNIT — exhaustive over all 23
  Incentives metrics: strong→1.4 tagged / 1.0 non-tagged, egal→0.7/1.0, moderate→1.0, None/empty→1.0, non-Incentives→1.0.
  [A2] PRECISION WIN — precise==coarse on exactly the 7 tagged; precise≠coarse (NO LONGER bumped) on exactly the 16 non-
  tagged. [A3] DEGRADE-EQUIVALENCE — vp_set=all-Incentives → ==coarse for all 23. [B] INTEGRATION — under strong, tagged
  REW_INC_111 rises rank 31→13; non-tagged overtime REW_Q528801 holds rank 40 (no bump). [c] GAUGE 76/15/1/92 invariant.
  [B2] SUPPRESSION UNTOUCHED — L4 confirm-shed + maternity exemption + gauge intact under the new tag. QA /tmp/dt_qa_vp.py
  15/15 PASS; 0 console errors; web untouched (no cache bump). Server restarted (no --reload). ⛔ STOP before Unit 2
  (transparency) — separate committed unit. Stale-value handling (treat-as-unset-until-reconfirmed; Thornbridge stores
  transparency=closed) is the load-bearing Unit-2 proof.

2026-06-25 — STEP 3 TAGGING PASS · UNIT 2 (transparency) — closes the tagging pass. ACTIVATES the dormant transparency
  field: unhides it (L2 FIELD_STATE "coming"→"live") and wires it to a per-metric re-rank. Unlike Unit 1 (sharpened a
  live dial), this introduces NEW surfacing where there was none — so the stale-value gate is load-bearing.
  FIELD (David-ruled): a curated "transparency_metrics" qid LIST in signal_lenses.json (the risk_metrics/variable_pay
  precedent). SET (10, David-ruled): PAYTR_02 (ranges visible to staff), PAYTR_01 + REW262_GOV_PAYINADVERTS (pay in
  adverts), REW263_GOV_UKPAYTRANS, REW26_GOV_EU_PTD_PREP (EU PTD readiness), REW_FAI_088 (access to ranges), REW_FAI_089
  (publish ranges), REW_FAI_087 (documented approach), REW263_GOV_ETHDISREADY (mandatory eth/dis gap PUBLICATION
  readiness), REW262_GOV_ACTIONPLAN (PUBLISHED equality plan). PRINCIPLE (David): tag = openness/PUBLICATION, NOT internal
  equity-work — so the gender/ethnicity/disability gap ANALYSES (REW_FAI_079 / PROP_930043cc / PROP_10d1211d) and the
  readiness SELF-ASSESSMENT (REW_FAI_092) are OUT. (ACTIONPLAN ruled IN as a published commitment.)
  WIRING: signals.py _transparency_mult(strategy, qid, transparency_set) — a THIRD strategy multiplier parallel to
  _p4p_mult: open → 1.4 on tagged signals; ranges/closed/unset → 1.0. tr_set loaded once beside risk_set/vp_set; folded
  into the SAME capped product min(objective × p4p × transparency, 2.0) — transparency stacks INSIDE the cap, no separate
  uncapped multiply (proven: an attract×open stack of 2.24 clamps to 2.0).
  ⭐ STALE-VALUE GATE (treat-as-unset-until-reconfirmed — resolves the L2-flagged open item, David's lean). REUSES
  field_provenance (no parallel mechanism): the live field sends transparency_confirmed=true (BODY top-level, beside
  plane_a) on save → server marks field_provenance.transparency = "live"; a pre-wiring value passed through WITHOUT the
  flag keeps "set". The engine drives the multiplier ONLY when provenance.transparency == "live" — a stored-but-unseen
  value reads as unset → 1.0. (NB: the confirm flag rides the body, not the `strategy` sub-dict — first wiring read
  `incoming` and silently never fired; fixed to `body`.)
  FRONTEND: strategy.js FIELD_STATE.transparency "coming"→"live" (the field renders as an OPTIONAL plane-B dial); the
  save sends transparency_confirmed = (fieldState=="live"). plane-B dial count is DYNAMIC (shownFields(planeBfields).length)
  — verified 6→7 live, no hardcode. Cache v249→v250.
  GOVERNANCE-HEAVY (no gauge interaction): 9 of 10 tagged metrics are Governance (non-competitive, zero gauge mass);
  PAYTR_02 is Pay. So this surfaces transparency PRACTICE gaps higher (the field's "open" copy: "gaps to full openness
  become actions") with NO verdict/gauge effect. INDEPENDENT of the L2-L4 suppression chain (a re-rank multiplier, not
  the confirm/suppress mechanism).
  VERIFIED (Thornbridge stores transparency=closed; 3 tagged metrics surface — PAYTR_01/02, REW262_GOV_PAYINADVERTS):
  [A] UNIT — open+live+tagged→1.4; ⭐ open+UNRECONFIRMED(prov "set"/absent)+tagged→1.0 (GATE); closed/ranges+live→1.0;
  non-tagged→1.0; strategy-off→1.0. [A2] CAP — 1.6×1.0×1.4=2.24 clamps to 2.0. [B] INTEGRATION — ⭐ STALE-VALUE GATE
  (real): Thornbridge's stored closed AND a stored OPEN-unreconfirmed both read inert (tagged ranks held 83/84/85,
  provenance not "live"); after RECONFIRM (open + confirmed → provenance "live") the 3 tagged metrics RISE to 61/62/63;
  strategy-off == unreconfirmed (both inert). [e] GAUGE 76/15/1/92 invariant across stale/held/reconfirmed/off. [f]
  SUPPRESSION UNTOUCHED — L4 confirm-shed + maternity exemption intact with transparency active. [g] plane-B count 6→7
  dynamic; 0 console errors; cache bumped; web verified (transparency dial renders, "Pay transparency · OPTIONAL"). [h]
  Thornbridge restored to transparency=closed, provenance not "live" = the correct inert resting state. QA
  /tmp/dt_qa_tr.py 20/20 PASS. Server restarted (no --reload). ✅ TAGGING PASS COMPLETE (variable_pay + transparency).
  The L2 transparency stale-value open item is RESOLVED.

2026-06-25 — STEP 3 CARD-RECOLOUR PASS — the L3-deferred VISIBLE payoff. L3 (scope C) computed per-domain
  d["target"].alignment but deferred card-recolour to "its own ruled pass"; L4 made the override behaviourally real
  (confirming signals demote), so recolouring a card against its per-domain aim no longer outruns suppression. This pass
  makes a per-domain override VISIBLE on the dashboard for the first time. FRONTEND-ONLY (positions.py already emits
  d.target; the tile just reads it).
  ⚠️ Reopens the Fix-1 attainment-colour surface (most-ruled in the project): card colour = STRATEGY ATTAINMENT
  (on-aim green / off-aim amber / no-aim grey), NOT market direction; direction is the marker + below/on/above word; RAG
  banned.
  RULING A (David): ahead-tone = on_target→green, behind→amber, AHEAD→amber. DECISIVE — this mapping is PROVABLY EQUAL to
  the existing attainTone(verdict, sameAim) (which already does `r===aim ? green : amber`, i.e. ahead→amber). So the lens
  RULE is unchanged; only WHICH aim it reads changes. Options B (ahead→green) / C (distinct over-tone) were rejected: they
  rewrite the lens AND would recolour non-override ahead cards product-wide, and B would let a card read green while its
  signals are NOT suppressed (contradicts L4). A keeps card ⟷ suppression in agreement (both read on_target=confirm).
  COLOUR-SOURCE SWITCH (pages.js CategoryTile): tone = verdict ? (d.target ? ATTAIN_ALIGN[d.target.alignment] :
  attainTone(verdict, marketAim(m))) : null, where ATTAIN_ALIGN={on_target:green, behind:amber, ahead:amber}. The card
  reads the SAME d.target.alignment L4 suppression reads → single source of truth, can't diverge. The cat-bar segments
  reuse the same `tone` (bar ⟷ chip can't disagree). d.target is present (alignment vs the per-domain aim where set, else
  global) for competitive domains when strategy is applied; null (Governance / strategy-off / no verdict) → fall back to
  the global attainTone. So the recolour bites ONLY on overridden domains; non-override path is byte-identical BY ALGEBRA
  (the A-equivalence). Lag-inversion preserved per-domain (below+lag = on_target = green; below+lead = behind = amber).
  SCOPE = TILES ONLY (CategoryTile). ⚑ FOLLOW-ON (David-flagged, NOT folded in): the category-detail page hero
  (pages.js:1498-1499) still colours that domain's hero against the GLOBAL aim — the immediate NEXT pass should switch it
  to the per-domain aim for consistency; kept separate (different render path; bundling drags in the parked MetricPage
  question). A brief tile-vs-detail-hero seam is accepted for one pass.
  VERIFIED — scripted mirror (/tmp/dt_qa_recolour.py 14/14, mirrors the pages.js tone logic against the live payload) +
  browser: [a] ⭐ FIX-1 LENS INTACT PER-DOMAIN — Benefits (below market): no-override→amber (off the global match aim),
  :lag→GREEN (below+lag = on-aim), :lead→AMBER (below+lead = off-aim); un-overridden domains unchanged under :lag. [b] ⭐
  CARD ⟷ SUPPRESSION AGREE — under :lag the GREEN card domain == the on_target domain == EXACTLY the domain L4 demotes
  (all read the same d.target.alignment). [c] DEGRADE — no-override: NEW tone == OLD (global-aim) tone for every domain;
  strategy-off → all grey; Governance no target. [d] RAG ABSENT — tones ∈ {green, amber, grey} only, no red/redover/
  direction hue. [e] GAUGE 76/15/1/92 + L4 confirm-shed + maternity exemption all untouched (frontend-only). [f] browser:
  Benefits tile renders GREEN (chip-good) under :lag with strategy applied while the other 5 competitive tiles are AMBER
  (chip-mid), 7 tiles render, 0 console errors. Cache v250→v251. Thornbridge restored to domain_targets={}. ✅ The
  per-domain override is now BOTH behavioural (L4 suppression) AND visible (this pass) — the chain's payoff is complete.

2026-06-25 — STEP 3 CATEGORY-DETAIL HERO RECOLOUR — closes the tile⟷hero seam the card-recolour pass (7617fdc) left.
  That pass recoloured the dashboard TILES per-domain but scoped OUT the category-detail page hero, which still coloured
  against the GLOBAL aim — so an overridden domain's tile went green while its detail hero stayed amber. This pass applies
  the SAME shipped switch to the detail hero. FRONTEND-ONLY, ONE LINE.
  DIAGNOSIS (the one real question): d.target is ALREADY in the detail hero's data — pages.js:1486 `hero =
  ov.hero.domains.find(d => d.name === name)` returns the SAME domain object the tile receives, carrying hero.target =
  {stance, alignment}. So CLEAN REUSE, no threading, no payload change. Reuses the shipped ATTAIN_ALIGN map (pages.js:485,
  module-level → in scope). NO re-rule of ruling A / the ahead-tone; the only new thing is the second render path.
  SWITCH (pages.js CategoryPage ~:1511): tone = verdict ? (hero.target ? ATTAIN_ALIGN[hero.target.alignment] :
  attainTone(verdict, marketAim(ov.hero.market))) : null — an exact mirror of the tile (CategoryTile), reading
  hero.target instead of d.target. The detail-hero verdict source (hero.position || hero.market) matches the tile's.
  ⭐ BOUNDARY (David): this pass touches the domain-HERO attainment tone ONLY. The per-metric pill — cardPosition
  (card.js:317, window.cardPosition, used at card.js:38) — is a DIFFERENT file, DIFFERENT function, DIFFERENT lens (a
  DIRECTION read: percentile vs window.MARKET_BAND → above=good / below=bad / on=mid, strategy-independent) and is
  UNTOUCHED. The parked "one metric vs org aim" question stays parked. Exact line boundary: pages.js:1511 (hero, changed)
  ⟂ card.js:317 (per-metric, untouched).
  VERIFIED — scripted mirror (/tmp/dt_qa_detailhero.py 13/13) + browser: [a] ⭐ SEAM CLOSED — the tile and the detail hero
  compute tone with the SAME function on the SAME ov.hero.domains[d] → agree on EVERY domain; Benefits:lag → tile green ==
  hero green. [b] FIX-1 LENS on the hero per-domain — below+lag→GREEN, below+lead→AMBER (lag-inversion both ways). [c] ⭐
  cardPosition BYTE-IDENTICAL — the /api/benchmarks Benefits cards (cardPosition inputs: percentile/direction/polarity)
  are identical across no-override vs :lag (strategy never reaches /api/benchmarks); the parked question is not reopened.
  [d] DEGRADE — no-override: NEW hero tone == OLD (global-aim) hero tone for every domain (A-equivalence); strategy-off →
  grey; Governance → no target → fallback. [e] CARD ⟷ HERO ⟷ SUPPRESSION — green (hero+tile) == on_target == the
  L4-suppressed domain, all reading the same d.target.alignment. [f] GAUGE 76/15/1/92 + L4 maternity exemption + the tile
  recolour (7617fdc) all untouched. BROWSER: the Benefits detail hero chip renders "below" + chip-good (GREEN) under
  :lag, matching the tile (was amber pre-pass); 0 console errors. Cache v251→v252. Thornbridge restored to
  domain_targets={}. ✅ SEAM CLOSED — tile + detail hero now agree. MetricPage per-metric attainment ("one metric vs org
  aim") remains the one parked detail-page conceptual question, by design.

2026-06-24 — STEP 3 MAIN MERGE — the per-domain strategy chain landed on main at adc4285 via fast-forward.
  The whole chain (capture L2 → engine alignment L3 → suppression+exemption L4 → tagging variable_pay+transparency →
  card-recolour → detail-hero recolour, the 16 commits 8eaf7b8..adc4285) was built on checkpoint/2026-06-24-session-work
  while main sat at 8eaf7b8 (unpushed since the git recovery) DELIBERATELY, waiting for the feature to be whole. It is.
  RULINGS (David): shape = A FAST-FORWARD (main was a strict ancestor → main advanced 8eaf7b8→adc4285 linearly, all 16
  commits preserved individually, NO merge commit; squash rejected to keep per-pass granularity, no-ff unnecessary as
  main never diverged); push = YES (origin/main created as canonical published history); branch = KEEP
  checkpoint/2026-06-24-session-work (on origin) until verified, cleanup a separate later call.
  PRE-MERGE REVIEW (read-only, before touching public history): all 16 commits authored David Whitfield
  <david@lumihr.co.uk> (recovery-fixed identity, none on the machine address); diff 8eaf7b8..adc4285 = 80 files
  +17,779/-1,404, coherent lumi product only (engine/signals/strategy/web/config/tooling/QA-suite/DECISIONS/legal/
  release); ZERO forbidden artifacts in the tracked diff (no lumi.db / *.db-wal/-shm, no *.bak backups, no .env/secrets,
  no /tmp dt_qa_* scratch); .DS_Store present only as DELETIONS (the 39b994c untrack); the session's QA harnesses live in
  /tmp (never tracked); server/qa_*.py are the project's committed verification suite (product). SAFETY NET: tag
  pre-merge-main-8eaf7b8 created on the old main (8eaf7b8) and pushed to origin (durable rollback marker); checkpoint on
  origin is the second net. EXECUTION: FF via `git fetch . checkpoint:main` (FF-enforced, no checkout → avoided the
  tracked-.DS_Store-vs-untracked checkout conflict, zero working-tree churn, HEAD stayed on checkpoint). VERIFIED:
  main == origin/main == adc4285 (0/0 in sync); main tip has ONE parent (no merge commit); tracked tree clean (only the
  21 untracked session scratch files remain, untouched by the merge); checkpoint kept local + origin. origin now holds
  main, checkpoint/2026-06-24-session-work, and tag pre-merge-main-8eaf7b8.
  ⚑ FUTURE HYGIENE (David-flagged, NOT this pass): .claude/settings.local.json is tracked (pre-existing, modified, no
  secret) — untrack + gitignore as machine-local in a separate tick; deliberately NOT bundled into the merge.

2026-06-24 — STEP 3 CLEANUP SWEEP (logged-debt clearance). Four parked debts, each its own commit straight to main (no
  bundled "cleanup" commit). UNIT 1 (a6efa20): untracked .claude/settings.local.json (machine-local Claude Code
  permission allowlist, no secret) via git rm --cached + .gitignore; runtime byte-identical. UNIT 2 (6b978d2): removed
  the DEAD colour helpers alignTone + MKT_SOLID (grep-proven zero call-sites; trimmed a stale comment that mis-claimed
  the signals list uses alignTone — it uses marketTone). KEPT bandToneAim (live: called pages.js:657 via bandTone,
  rendered :684) — the "prove dead before cutting" guard caught the one that looked dead but isn't. POS_RANK kept (shared
  by attainTone + bandToneAim). Cache v252→v253; dashboard renders, 0 console errors. UNIT 3 (1e1cd3d): RESOLVED the L4
  on_plan-drift note (ruling C, document-only) — on_plan (inferred-aim-clean, domain_aims heuristics) and target.alignment
  (explicit-override-met) are intentionally distinct concepts, not a unify; A′ (extend domain_aims to honour
  domain_targets) is a separate future feature pass. UNIT 4 (branch disposition): DELETE checkpoint. Local branch deleted
  (was 3e2ab05, fully merged). ⚠️ origin/checkpoint deletion BLOCKED — it is still the GitHub repo's DEFAULT branch (it
  was the first branch pushed, before main existed), and GitHub refuses to delete the default. ACTION PENDING (David):
  switch the repo default branch to main (GitHub → Settings → General → Default branch → main, or `gh repo edit
  Davidlumi/lumihr --default-branch main` once gh is authed), THEN `git push origin --delete
  checkpoint/2026-06-24-session-work`. Nothing is at risk: main == origin/main == 1e1cd3d (canonical, in sync), all 16
  feature commits are in main's history, and the pre-merge state is preserved by tag pre-merge-main-8eaf7b8 (local +
  origin). The stale origin/checkpoint is inert until the default flips. Overtime/shift-premium misfiling
  (REW_Q528801/534581) + MetricPage per-metric attainment remain parked as their own diagnosed/conceptual passes.

2026-06-25 — STEP 3 OVERTIME/SHIFT-PREMIUM RE-FILING (last data debt, cause-fixed). REW_Q528801 ("overtime
  multiplier by shift type") + REW_Q534581 ("hourly pay multipliers by time band") were Level-class PREMIUM-PAY
  metrics MISFILED in the Incentives domain — surfaced during variable_pay tagging (57bcc11, symptom-fixed: the tag
  excludes them from the P4P multiplier), CAUSE now fixed: re-filed Incentives → PAY. Ruling (David): Pay is the home —
  overtime/shift MULTIPLIERS are pay structure/rates, NOT base-salary £, so NO collision with lumi's base-salary
  exclusion; clinching evidence: the CSV rows already had sub_power_code=REW_PAY and superpower tuple {"Reward","Pay",…}
  — the CODE always said Pay, only the sub_power LABEL was wrong; and Pay already holds the sibling OT_04 (shift
  premiums). NOT cleanup — a data re-classification with engine effect; the gauge was MEASURED, not assumed.
  WRITE PATH (all confirmed): WAL-checkpoint(TRUNCATE) + DB backup (lumi.db.bak_pre_refile_overtime_*) FIRST → guarded
  edit (/tmp/refile_overtime.py, --write --confirmed-by-david, idempotent): the TRACKED source data/lumi_questions.csv
  (sub_power Incentives→Pay, surgical binary replace of the misfiling-specific token ",Incentives,REW_PAY," — exactly 2
  occurrences file-wide, byte-preserving so the diff is 2 lines, NOT the 805-line CRLF-churn a text-mode write caused on
  the first attempt, which was reverted) AND the runtime questions.sub_power (2 rows) → aggregate.py refresh (the
  snapshot payload also bakes subpower; 844 questions/220 orgs re-aggregated, snapshot subpower now Pay) → server
  restart. market_position_config untouched (stores no per-metric domain). Append-only intact: only the question's domain
  LABEL changed — answers/answers_history untouched, same question_id/version → historical comparability preserved
  (metadata correction, not a versioned redefinition).
  ⭐ GAUGE MEASURED — Thornbridge 76/15/1/92 BEFORE == 76/15/1/92 AFTER (UNCHANGED). WHY: the 12 positioned matrix rows
  moved Incentives→Pay, BOTH competitive → they stay in the gauge's whole-pool mass; only the sub-pools re-attribute
  (gauge = _pool_verdict over the whole competitive pool, positions.py:1019; per-domain = filter by subpower, :986).
  PER-DOMAIN (expected + correct, distinct from the gauge invariant): Pay pool 13→25 (+12), Incentives 25→13 (−12),
  conserved; both verdicts stay "below" (no flip) → Thornbridge per-domain alignment unchanged. variable_pay STILL
  excludes them (qid-keyed, domain-independent — _p4p_mult(strong,…)=1.0). L4 suppression + card/hero recolour untouched
  in MECHANISM (they read domain/alignment generically; the data change flows through, no code change). SPOT-CHECK
  (universal, not per-org): 2nd org Meremont College Group — REW_Q534581 now groups under Pay (REW_Q528801 simply doesn't
  position for that org). 0 console errors; dashboard renders (7 tiles, gauge "On market"). Committed: data/lumi_questions.csv
  (2-line diff) + DECISIONS; the DB + benchmark_snapshots are runtime (gitignored), reproduced from the CSV on any re-seed.
  ✅ Last data debt cleared. MetricPage per-metric attainment + A′ (narrative-honours-overrides) remain as their own passes.

2026-06-25 — A′: AI-DIAGNOSIS NARRATIVE HONOURS PER-DOMAIN OVERRIDES (resolves the cleanup-sweep-deferred item).
  The narrative computes on_plan via strategy_diag.domain_aims, which INFERRED each domain's aim from heuristics
  (market_position + reward_mix + pay_for_performance) and IGNORED domain_targets — so an org that explicitly set
  Benefits:lag had its narrative judge Benefits against the inferred aim, not the override L3/L4/recolour already honour.
  Feature pass (CHANGES narrative output for override orgs), not cleanup. Ruling A (David): OVERRIDE BEATS INFERENCE.
  BUILD (strategy_diag.py, backend-only, no threading — domain_targets already reaches the path via
  strategy_for_engine at app.py:1489/3056): (1) domain_aims gains a post-pass AFTER the reward_mix/P4P nudges —
  `for dom,stance in (strategy.get("domain_targets") or {}).items(): if dom in aims and stance in _STANCE_AIM:
  aims[dom]=_STANCE_AIM[stance]` → precedence override > nudge > base. (2) _reason_for gains a matching front guard —
  where domain_targets[dom] is set it names "your <stance>-the-market target for <domain>", NEVER the inferred nudge
  (aim + reason are two halves of ONE coherence change: without the reason fix, Benefits:lag + reward_mix=benefits
  would narrate a SELF-CONTRADICTING reason — "off your benefits-led mix" on a domain the user set to lag).
  CONVERGENCE (by design, structural): _STANCE_AIM and _market_target's aim map are IDENTICAL ({lag:0,match:1,lead:2}),
  verdict indices identical ({below:0,at:1,above:2}) → for an OVERRIDDEN domain the narrative's delta==0 ⟺ the engine's
  on_target. The cleanup-sweep-logged drift is RESOLVED for overridden domains. NO-OVERRIDE fallback INTENTIONALLY
  differs (narrative keeps its reward_mix/P4P heuristic nuance; the engine falls back to global market_position) — two
  valid fallbacks, deliberately NOT flattened. INVARIANT: domain_aims is called in exactly ONE place (compute_findings)
  → narrative-only; the gauge, L4 suppression (_market_target/alignment), and tile/hero recolour (d.target.alignment)
  are separate surfaces, untouched. VERIFIED /tmp/dt_qa_aprime.py 14/14: [a] degrade both halves (no-override byte-
  identical inference; Benefits:lag → Benefits 2→0, override beats the benefits-led nudge; per-domain independent;
  Pay's reward_mix nudge preserved). [b] convergence across the axis (lag/match/lead → narrative on-plan ⟺ engine
  on_target). [e] _reason_for cites the lag target NOT the benefits-led mix (the contradiction case). [f]
  compute_findings: Benefits:lag flips Benefits gap→on-plan. [g] gauge 76/15/1/92 untouched. Backend-only (no cache
  bump). ✅ A′ resolved. MetricPage per-metric attainment (the conceptual fork) remains its own DESIGN diagnostic.

2026-06-25 — METRICPAGE PER-METRIC ATTAINMENT — CONCEPT RULING B (status quo, NO BUILD). Design-diagnostic pass
  (framed the fork, no code). RESOLVED: per-metric attainment is REJECTED by design. Attainment is a DOMAIN-LEVEL
  concept — a strategy stance (lag/match/lead) is set FOR a domain, never for an individual metric. A metric has a
  market POSITION (a fact); a domain has an AIM (declared intent). The per-metric pill (card.js cardPosition — percentile
  vs window.MARKET_BAND → above=good / below=bad / on=mid, strategy-independent) is a market-DIRECTION fact,
  INTENTIONALLY distinct from the domain-level ATTAINMENT lens (pages.js attainTone / ATTAIN_ALIGN reading
  d.target.alignment). Metric = position; domain = attainment — a correct-by-design division of labour, already
  implemented; the lens-difference between metric and domain surfaces is the HONEST reflection of where a stance was set,
  not an inconsistency to fix.
  Option A (metric inherits the domain aim) DISQUALIFIED: it would green-wash real gaps inside a lag domain — the
  decisive case is REW_BEN_FAM_002 (enhanced maternity), where a lag-Time-Off aim would make the below-market maternity
  metric read GREEN / "on plan", re-introducing through the COLOUR channel the exact failure the L4 risk-exemption was
  architected to prevent (it would defeat the maternity-zero guard on its most consequential metric). B over C: the
  direction-pill is a MARKET FACT ("below market · P22"), the core benchmarking info the user wants — it states where the
  metric sits and does NOT deliver an intent-verdict the user didn't ask for (which is what mirror philosophy guards
  against); C's neutral pill would lose real at-a-glance utility to gain purity B already has. NON-DECISION INVARIANTS
  (true either way, confirmed): gauge, L3 alignment, L4 suppression, tile+hero recolour and the A′ narrative are all
  separate surfaces — untouched. The metric/domain lens-difference is intentional and documented; not a gap to close.
  This closes the last parked Step-3 conceptual item. (Remaining: the git housekeeping to switch the GitHub default
  branch to main so origin/checkpoint can be deleted — David's Settings action.)

2026-06-25 — NOTIFICATION PEER-CUT BASELINE — CONCEPT RULING A (canonical `all` cut, by design; NO BUILD).
  Design-diagnostic pass (verified the mechanism from code, framed the fork, no code). VERIFIED: the nightly sweep
  baselines on the canonical all-peers cut — run_signal_sweep (app.py:1578) → org_signals (app.py:1567) builds
  fresh_signals on a hard-coded `{"dim":"all"}` cut; signal_state is keyed (org_id, signal_key) with NO cut dimension
  (db.py:207) → single-cut by construction; no primary/default/pinned-cut concept exists (orgs has no such column;
  peer_groups are saved groups but none is designated the alert frame).
  RESOLVED: the notification baseline is the CANONICAL `all` cut, BY DESIGN — the all-peers baseline's STABILITY is the
  FEATURE, not a limitation. RATIONALE: a notification is a CHANGE-CLAIM over time, and a change-claim is only meaningful
  if the reference frame held STILL while the change happened. This is categorically unlike A′ (a narrative describes the
  PRESENT — no baseline), so the A′ "honour the user's choice" principle does NOT transfer: an alert frame has a
  STABILITY requirement a narrative doesn't. THE DISCRIMINATOR IS STABLE-vs-DRIFTING, not choice-vs-constant.
  B-via-TWIN DISQUALIFIED: compute_twin (peer_twin.py:39) is a recomputed top-K (TWIN_K=12, min 8) — a twin-baselined
  alert would fire when the COHORT changes (a new similar org joins → top-K re-selects, a 1-in-12 lurch), not when the
  ORG changes, and the user CANNOT tell which → it MISATTRIBUTES cohort drift to the org's own reward decisions, a
  phantom/mis-causal alert on a product whose credibility is "we tell you the truth about where you stand." (Same shape
  as the MetricPage maternity disqualifier: the appealing option misinforms on the cases that matter.)
  Per-cohort alerts are NOT rejected in principle — but the baseline cut must be STABLE. Canonical `all` = stable (a
  one-org swap barely moves it) → valid. Twin = drifting → INVALID. A SAVED CUSTOM GROUP (membership declared via FROZEN
  criteria, not recomputed) is chosen AND stable → the ONLY coherent path to a cohort-specific baseline, and the shape any
  FUTURE B-pass must take — with a re-baseline rule on criteria-change. So A is the honest default NOW and the door to a
  future stable-saved-group baseline stays OPEN, while the twin baseline stays CLOSED WITH A REASON.
  NON-DECISION INVARIANTS (confirmed, hold under any future stable baseline): interactive cut-switching is a VIEW op that
  NEVER notifies (signal_state/events are written only by run_signal_sweep; /api/overview is a read-only GET) and stays
  so; the materiality bucket-jitter guard (notifications.py:160 — "moved" fires only on a bucket CHANGE, plus a
  min_money_change_gbp threshold) + the _live_at_send suppression re-check (notifications.py:281) + the n>=5 floor +
  peer-name privacy are all cut-agnostic. This closes the notification-baseline conceptual item.

2026-06-25 — NOTIFICATION <-> STRATEGY COHERENCE — RULING C (hybrid demote), BUILT. The dashboard suppresses
  (L4-demotes) signals that confirm a deliberately-set strategy aim, but the nightly sweep was STRATEGY-BLIND
  (verified: org_signals app.py:1574 passed neither strategy nor domain_alignment; overview app.py:1399 passed both) —
  so notifications fired about signals the dashboard demoted: the last coherence gap (narrative/dashboard/colours honour
  strategy; notifications didn't). Ruling C (David): the chain's verb for "confirms your choice" is DEMOTE, never DELETE
  (B rejected — it would make notifications the one surface that deletes a confirming signal); C is the faithful L4 mirror.
  BUILD (backend-only, app.py + notifications.py): (1) org_signals now threads strategy + per-domain alignment with PARITY
  to /api/overview — builds the hero request-free (all entitled; the sweep only runs for unlocked orgs) to derive the
  {domain: alignment} map (the SAME L3 target), then passes strategy + domain_alignment to build_signals so confirm-
  flagging fires in the sweep. Cut stays canonical all-peers (RULED). (2) EVENT-LAYER confirm-aware PRIORITY (not
  deletion): diff_and_record stamps payload.confirm = bool(s["confirm"]) on appeared/moved; render_event titles a confirm
  change "On plan" (not "Worth a look"); list_notifications sorts confirm LAST and EXCLUDES it from the unread badge
  (tension + risk lead); run_email_digest excludes confirm from the email push (event_is_confirm) — nothing dropped,
  confirm stays in the in-app inbox, quiet (mirrors L4 demoting off the home briefing while keeping findable). KEY
  TECHNICAL FINDING that shaped it: diff_and_record keys on signal-key PRESENCE + bucket, NOT impact — so L4's impact-
  demote doesn't reach the event layer; C adds an EXPLICIT confirm priority tier, not an impact reliance. (3) STORM BOUND:
  put_strategy now silently RE-BASELINES on a strategy change (notifications.rebaseline = DELETE signal_state +
  record_baseline, firing no events) so the user's OWN deliberate re-sort never storms the bell (inverse of the cut-drift
  stable ruling; parallel to the transparency reconfirm gate). (4) RISK-EXEMPTION (structural, free): the confirm flag is
  gated on not risk_framed (identical to L4) -> maternity/sick-pay/EAP are NEVER confirm-flagged -> ALWAYS notify at full
  priority. DEGRADE: strategy-off / no override -> empty alignment map -> no confirm flags -> byte-identical to the prior
  strategy-blind sweep (the signal-KEY set is identical; confirm is a flag, not a presence change, so no storm even from
  the rollout). VERIFIED /tmp/dt_qa_notifcoherence.py 16/16: [a] degrade both halves (no-override key set == strategy-
  blind; Time Off:lag -> 8 non-risk confirm-flagged, key set unchanged). [b] risk exemption (maternity + sick-pay NOT
  confirm-flagged while siblings are). [c] event layer (confirm -> "On plan", sorts last, excluded from unread/email).
  [d] storm bound (re-baseline -> next diff 0 events). [e] cut canonical all + parity. /api/notifications 200 + events
  carry confirm; gauge 76/15/1/92; dashboard + bell render, 0 console errors. Backend-only (no cache bump). Note: only 1
  org currently has a strategy (every other degrades) so no transition re-baseline of all orgs was needed; the PUT hook
  handles all future strategy changes. ✅ The last coherence gap is closed — every surface (narrative, dashboard, colours,
  notifications) now honours the user's explicit strategy, the risk-exemption survives at all four, and the gauge held.

2026-06-25 — SIGNALS PAGE PASS 1 — COLOUR-LENS RULING A (direction colour), CLEANUP BUILD. First of a 5-pass
  Signals-page strategy-coherence sequence (1 colour-lens [this], 2 confirm/tension icon system, 3 triage hierarchy,
  4 context-row verify, 5 header honesty). CONCEPT QUESTION: should the Signals rows colour by market DIRECTION
  (below=amber / on=green / above=red — a fact) or by ATTAINMENT-vs-aim (the tile/hero lens, no-red-when-on-plan)?
  RULING A (David): DIRECTION is correct-by-design and CONSISTENT with the MetricPage ruling (B, 2026-06-25) — a
  Signals row IS a metric, and a metric has a POSITION not an aim; attainment is domain-level (the tile/hero, which IS
  a domain). The strategy relationship (confirm / tension) belongs on the row's ICON (Pass 2), never on the row colour —
  so direction-amber on a deliberately-below metric is honest, not a false alarm, because the icon will carry "on plan".
  This was ALWAYS what rendered: marketTone() already returned pure direction and DISCARDED the aim arg it was passed —
  so Ruling A is "keep the visible behaviour, delete the dead scaffolding that implied otherwise". CLEANUP BUILD
  (web/js/pages.js, frontend-only): (1) marketTone(key, _aim) -> marketTone(key) + accurate comment (absolute DIRECTION,
  a fact, no stance). (2) posColor(k, aim) -> posColor(k); posTag(s, aim) -> posTag(s) (both already passed aim only to
  marketTone, which dropped it). (3) SignalsPage: DELETED the dead `const aim = marketAim(data.hero.market)` var + its
  stale comment (which described the removed alignTone "no red for a lag org" stance-colour that never reached the rows)
  -> replaced with a comment stating the rows colour by per-metric DIRECTION, attainment is domain-level (MetricPage),
  and strategy relationship rides the icon. (4) de-aimed the 3 call sites (posTag :1048, posColor :1085 bar + :1092 chip
  dot). UNTOUCHED (verified LIVE, used by attainTone): CategoryTile `aim` prop (271->1123->1170) and CategoryDetailPage
  hero `const aim = marketAim(...)` (now :1496) feeding attainTone + MarketSpectrum — those surfaces ARE domains and
  colour by attainment, correctly. bandToneAim (:451) already called marketTone(k) 1-arg — unaffected. Scope verified
  pages.js-local (posTag/posColor/marketTone not referenced in other web/js files). VERIFIED in preview (v253->v254):
  Signals page renders 81 rows, 0 console errors, colours resolve to the SAME direction mapping — chip dots amber
  rgb(245,166,10)=below / red rgb(192,57,43)=above / indigo rgb(98,87,201)=differs; bar segs var(--amber-bright) /
  var(--unfavourable) / var(--differs); tags "below market" / "differs from market". Byte-identical render — pure
  dead-code removal, no colour change. NEXT: Pass 2 = the confirm/tension ICON system (its own gated diagnose->build).

2026-06-25 — SIGNALS PAGE PASS 2 — CONFIRM/TENSION ICON SYSTEM, RULING + BUILT (mark-the-exceptions).
  Pass 1 ruled the row COLOUR = market DIRECTION (a fact); the strategy relationship (confirm/tension/
  risk/no-aim) had NOWHERE to render — s.confirm rode the row data (signals.py:926, L4) but the Row
  renderer never read it (no is-confirm, no glyph; confirm was consumed only server-side: the ×0.25
  impact demote + cap_briefing home-shed). So the icon is the ONLY channel for the strategy relationship.
  RULING (David) — MARK-THE-EXCEPTIONS vocabulary: confirm → a quiet GREEN "✓ On plan" pill; risk →
  its existing CORAL "⛨ Risk" shield, UNCHANGED; tension (default) + no-aim (strategy-off/Governance) →
  UNMARKED. Marking the rule is noise (for the canonical match+cost demo org, tension IS every below-aim
  row); the eye catches the two exceptions, bare = "ordinary tension, look at it", and the header's
  strategy-on/off state disambiguates tension from no-aim. SUB-RULINGS: (a) glyph + KEEP the ×0.25 demote
  (signals.py:927) — the pill EXPLAINS the demotion (legibly quiet), does NOT reverse it; faithful to L4
  demote-not-delete; line 927 untouched. (b) Shield-sole, no double-marking — DATA-GUARANTEED: the L4
  confirm gate is `not s.get("risk_framed") AND domain_alignment[domain]=="on_target"`, so a risk row can
  NEVER be confirm-flagged (any_risk_confirmed=false); the maternity-zero guard survives at the visual
  layer. (c) no-aim unmarked — degrade: empty/None domain_alignment → gate short-circuits → 0 confirm →
  0 glyphs → byte-identical. (d) ⭐ render WHEREVER s.confirm fires, INCLUDING differs/approach rows (4 of
  the 8 demo rows) — MIRROR L4 EXACTLY, no position filter; the glyph means precisely "engine flagged
  confirm", and a subset would re-introduce the icon↔engine drift this whole session closed.
  BUILD (frontend-only, web/js/pages.js + web/css/app.css, v254→v255): added the "✓ On plan" pill to the
  shared sigParts name-line (home + metric page) AND the Signals-page inline name-line, cloned from the
  .sig-risk structure (check glyph size 11, var(--favourable) channel, color-mix 18% tint) so it composes
  inline with the NEW pill + Risk shield WITHOUT changing row height; added the is-confirm row class at all
  three render sites (home 834, signals 1049, metric 1542). The row's left accent + tint stay DIRECTION-
  toned (.is-confirm deliberately adds NO recolour — colour is the fact, the pill is the relationship).
  New CSS: .sig-onplan + .sig-onplan svg. OPEN ITEM (i) — DEMO ORG STATE: KEPT the persisted
  org_strategy.domain_targets={"Time Off":"lag"} on thornbridgeretailgroupplc (David's lean) — a lag stance
  on below-market Time Off resolves to on_target, so the demo org exercises the glyph LIVE (8 confirm rows).
  No DB write (keep = the no-mutation path). Harness is config-independent either way.
  QA — TWO PROOFS, both pass (no DB mutation; in-browser against the live override org + a transient
  strategy=off render). PROOF 1 CONFIRM FIRES: /api/overview signals_all carries 8 confirm rows (4 below +
  4 differs, all Time Off, all non-risk); the Signals page renders exactly 8 "✓ On plan" pills (is-confirm
  on 8 rows), tones 4 amber + 4 approach (differs rows DO get the pill), glyph = check polyline, svg green
  rgb(46,125,82); the 2 risk Time Off rows render SHIELD + NO pill (maternity "Enhanced maternity & adoption
  pay" REW_BEN_FAM_002, sick-pay "Sick pay from day one" REW262_TIME_SICKDAYONE — both hasShield=true,
  hasOnPlan=false); 0 rows carry BOTH markers. Screenshot shows two adjacent below-market rows — maternity
  (Risk) + Bank-holiday-premium (On plan) — same amber direction colour, different glyph. PROOF 2 BYTE-
  IDENTICAL-ABSENT: forcing the SignalsPage overview fetch to strategy=off → 81 rows (unchanged), 0 On-plan
  pills, 0 is-confirm rows, the 3 risk shields still present (direction-independent) → page identical to
  pre-Pass-2. 0 console errors throughout. ✅ The strategy relationship now renders on every surface a
  signal row appears (home/signals/metric), colour stays the market fact, and the maternity-zero risk
  exemption holds at the visual layer. Deferred Signals passes: 3 triage hierarchy, 4 context-row verify,
  5 header honesty.
