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

2026-06-25 — SIGNALS PAGE PASS 3 — TRIAGE HIERARCHY, RULING A+ (confirm-aware rank), BUILT (one line).
  Audit flagged the Signals list as "flat" — grouped by domain, within-group sorted by triage status only.
  Pass 2 added the confirm glyph + kept the L4 ×0.25 demote; question: is glyph+demote ENOUGH triage, or do
  confirm rows want a structural SUB-GROUP? DIAGNOSED on SCREENSHOT EVIDENCE (read-only, live Time Off→lag
  override). FINDING: the within-group sort is rank = triage-status-only (pages.js:1034), a STABLE sort, so
  the L4 impact-demote reached within-group position ONLY as the signals_all tiebreaker — never explicitly.
  Live Time Off group (10 rows) ordered: Risk #1, CONFIRM #2, Risk #3, confirm #4-10 — i.e. a confirm row
  ("Bank holiday working premium", impact-heavy enough that ×0.25 still beat sick-pay) SPLIT the two Risk
  rows; confirm did NOT cleanly clump at the tail. KEY INSIGHT that killed B: confirm is CONCENTRATED by
  construction (it fires only where a whole domain sits on its aim) — all 8 confirm rows were in the ONE
  on-target group; every other domain group had ZERO confirm (byte-identical to pre-Pass-2). So a sub-group
  (B) would have GUTTED the Time Off group — lift 8 of 10 rows out, leaving a 2-row Risk stub — fragmenting
  the domain reading; and B's "confirm clutters the tail" justification did NOT manifest (confirm was a
  uniform marked block, not clutter). RULING A+ (David): reject B; keep domain grouping; fix the only real
  blemish (the #2 confirm splitting the Risk pair) with a ONE-LINE confirm-aware rank:
    const rank = s => s.confirm ? 3 : (s.status === "priority" ? 0 : s.status === "saved" ? 1 : 2);
  Confirm rows deterministically sink to the group TAIL (rank 3) — the visible mirror of L4 demote-not-delete
  (tail, not removed; stays in its domain group, no sub-group). The 2 risk-exempt rows (never confirm → never
  rank 3) stay ADJACENT at the top. BUILD: web/js/pages.js:1034 (the rank fn) + comment; cache v255→v256.
  Frontend-only, one line. QA (in-browser, live override + transient strategy=off, no DB write): PROOF 1
  RE-ORDER — Time Off group now: Risk #1 (maternity REW_BEN_FAM_002) + Risk #2 (sick-pay REW262_TIME_
  SICKDAYONE) ADJACENT at top; all 8 confirm rows clump at the TAIL (#3-10, confirm_clumped_at_tail=true,
  risk_adjacent_at_top=true); "Bank holiday working premium" moved #2→#3, no longer splitting the Risk pair.
  PROOF 2 DEGRADE — strategy=off render: 0 confirm pills, and the Time Off order EXACTLY matches the pre-
  Pass-3 triage-status-only stable sort (order_matches_triage_only_sort=true) → the confirm?3 branch only
  bites where confirm fires → byte-identical. PROOF 3 MIXED GROUP — none exists under the single-domain
  override (confirm is whole-domain), but the Time Off group proves the rule: the 2 non-confirm Risk rows
  (rank 2) sort ABOVE all 8 confirm rows (rank 3); rank 3 > rank 0/1/2 guarantees confirm sinks below ANY
  non-confirm row (tension or risk) wherever they coexist. 0 console errors. NOTE: a PINNED confirm row also
  sinks in the grouped inbox (confirm beats triage status by design — quiet stays quiet); it still surfaces
  in the Priority TAB (filtered by status===priority). PASS 5 INTERACTION (header honesty): A+ makes the
  within-group ordering claim TRUE (impact = strategy-multiplied + confirm explicitly last), but the GROUP
  order is fixed SIG_DOMAINS order, not strategy-ranked — so the header "ordered for your strategy" is honest
  at the row level inside a domain yet loose globally; that domain-fixed-group-order question stays with
  Pass 5. Deferred Signals passes remaining: 4 context-row verify, 5 header honesty.

2026-06-26 — SIGNALS PASS 3.5 — PIN vs CONFIRM PRECEDENCE, RULING A (pin-only beats confirm), BUILT (one line).
  Pass 3's A+ rank (s.confirm ? 3 : (priority?0:saved?1:2)) checked confirm FIRST, so a row that was BOTH
  pinned (status=priority) AND confirm sank to rank 3 (group tail) — the engine's "on-plan, stay quiet"
  silently overrode the user's explicit pin. DIAGNOSED (read-only, in-memory rank simulation, no DB write):
  the precedence was confirm-wins (pinned confirm → rank 3 → tail). The cost was sharper than Pass 3 implied:
  because the Priority tab shares the SAME grouped+ranked pipeline (triaged=all.filter(cur.f) → groups →
  .sort(rank); only cur.f changes per tab), a pinned confirm row was demoted-within-group in the Priority
  tab TOO — the one view whose whole job is to honour pins. Still PRESENT/findable everywhere, never removed.
  RULING A (David) — PIN WINS, pin-only (A′ rejected). The session principle (honour the user's explicit
  choice over the engine's inference: per-domain override beats inferred mix in A′; a deliberate strategy
  change re-baselines notifications, never storms) = the USER WINS THE CONFLICT. KEY DISTINCTION that scoped
  it to pin-only: PIN = "keep this at the TOP" = a POSITION instruction → genuinely CONFLICTS with confirm's
  position-demotion → user wins → pin beats confirm. SAVE = "bookmark / track this" = a RETRIEVAL instruction
  → orthogonal to position; a saved+confirm row tail-clumping does NOT contradict what saving did (still in
  the Saved tab, still retrievable) → NO conflict → save need not beat confirm. A′ (saved also beats confirm)
  was CONSIDERED and REJECTED as over-reach — protecting saved-confirm from a demotion that doesn't undermine
  the save (a division that doesn't earn itself, cf. Pass 3 B). BUILD (one line, web/js/pages.js:~1034,
  cache v256→v257): rank = s => (s.status === "priority" ? 0 : s.confirm ? 3 : s.status === "saved" ? 1 : 2)
  — priority checked BEFORE confirm: a pinned confirm row lifts to rank 0 (group top); UNPINNED confirm still
  sinks to rank 3 (Pass 3 fully preserved); saved stays rank 1 (saved+confirm still tail-clumps). One line +
  comment; fixes BOTH the grouped inbox AND the Priority tab (shared pipeline, no separate scoping). GLYPH: a
  pinned confirm row at the group top STILL wears the green On-plan pill (pill is conditional on s.confirm
  only, status-independent) → reads "I'm watching this, and it's on plan" — coherent, glyph is a fact not a
  sort; a pinned row above an unpinned Risk row is correct (pin = explicit top; Risk keeps its coral shield
  regardless of position). QA — THREE PROOFS, all pass (in-browser, live Time Off→lag override; the pin was
  injected IN-MEMORY via a fetch patch — NO DB write — then a transient strategy=off render; org_strategy
  untouched). PROOF 1 PIN WINS: the injected-pin confirm row "Bank holiday working premium" lifts to group
  TOP (#1), above the 2 Risk rows (now #2/#3), STILL wearing the On-plan pill; the other 7 unpinned confirm
  rows STILL tail-clump (#4-10); verified #1 in the Priority tab too (alongside a pre-existing real Governance
  pin). Screenshot captured. PROOF 2 PASS-3 PRESERVED: with no pin, Time Off order unchanged (Risk #1/#2
  adjacent, confirm #3-10 tail-clumped). PROOF 3 BYTE-IDENTICAL-ABSENT: strategy=off → 0 confirm pills →
  order reverts to the pre-Pass-3 triage-only sort (the confirm?3 branch bites ONLY the narrow pinned-AND-
  confirm intersection). 0 console errors. Deferred Signals passes remaining: 4 context-row verify, 5 header
  honesty (inherits the domain-fixed-group-order vs "ordered for your strategy" question from Pass 3).

2026-06-26 — SIGNALS PASS 4 — CONTEXT-ROW VERIFY, RULING NO-BUILD (false alarm, confirmed on evidence).
  Audit flagged: a "context, not a verdict" row (neutral polarity, e.g. Workforce cost per FTE) appeared
  AMBER-ish in a screenshot — neutral rows should be visually distinct from the amber "below market" verdict
  tone. Two candidate causes to distinguish on evidence: (a) the metric isn't actually direction=neutral in
  config → getting a real verdict tone (DATA mis-tag), or (b) the metric IS neutral but the neutral CSS tone
  renders too close to amber (CSS issue). DIAGNOSED read-only (live demo org, no DB write). RESULT: NEITHER —
  all three layers correct. (1) CODE PATH: posTag (pages.js:922) checks `s.polarity === "neutral"` BEFORE the
  directional branches → a neutral row gets tone "neutral" + hint "context, not a verdict", can never fall
  through to a verdict tone; neutral rows are excluded from the RAG composition (pages.js:1040, `if (s.polarity
  === "neutral") return;`) so they add nothing to the position bar/chips and contribute nothing to the gauge
  (76/15/1/92 is the positioned-verdict pool). (2) DATA — cause (a) RULED OUT: the live org has exactly 2
  context rows, both genuinely polarity=neutral — "Workforce cost per FTE" (PROP_d16bae79) and "Workforce cost
  as % of revenue" (PROP_e63cf45a), both Pay, both position=below; a name-pattern sweep for cost/spend/ratio/
  per-FTE/budget metrics that are NOT neutral returned 0 suspects. The audit's example IS correctly tagged.
  (3) CSS — cause (b) RULED OUT: computed colours off the live DOM — neutral row = navy border rgb(31,42,68)
  on grey-blue bg rgb(238,240,247), navy pill (.pos-neutral bg #E9EBF6 / color var(--navy) rgb(31,42,68)); the
  amber verdict = amber-bright border rgb(245,166,10), dark-amber pill (rgb 138,88,5) on pale-amber bg
  rgb(251,239,217). Source: .sig-tone-neutral { background:#EEF0F7; border-left-color:var(--navy); }
  (app.css:985), .pos-neutral { background:#E9EBF6; color:var(--navy); } (app.css:996) — navy-on-grey-blue, a
  DIFFERENT HUE FAMILY from amber, not close. The audit's "amber-ish" read = JPEG compression of a navy pill on
  warm-paper background (navy muddies toward brownish under compression); a fresh screenshot renders it cleanly
  navy. The ONLY thing a neutral row shares with a verdict row is the WORDING "below market" (the position is a
  fact — the value IS below the market median), disambiguated by the navy tone + the italic "context, not a
  verdict" hint — this is BY DESIGN (state the position, refuse the good/bad verdict: below on cost-per-FTE is
  genuinely ambiguous — efficient vs under-resourced), and a VERIFY is not a redesign so the shared wording
  stays. CLOSE Pass 4 no-build. (Softening the shared "below market" wording on context rows — e.g. a distinct
  context label — would be its own scoped redesign pass, not this verify.) Deferred Signals passes remaining:
  5 header honesty (inherits the domain-fixed-group-order vs "ordered for your strategy" question from Pass 3).

2026-06-26 — SIGNALS PASS 5 — HEADER HONESTY, RULING B (drop the superlative), BUILT (one line). The final
  Signals pass. An exhaustive read-only honesty sweep of EVERY user-facing claim on the Signals page (header
  chip + tooltip + intro paragraph + strategy-check card + register foot + empty states + count) found 12
  ordering/materiality/strategy/provenance claims, 11 HONEST and exactly 1 LOOSE: the header-chip tooltip
  title= "The most material signals for your stance come first." VERIFIED honest (untouched): the VISIBLE chip
  "ordered for your <objective> strategy" (the order genuinely is objective-shaped — build_signals multiplies
  impact by _objective_mult/_p4p_mult/_transparency_mult and sorts by -impact; no global-materiality claim);
  the intro ("grounded in your peer data, never advice · we flag, you decide"); the strategy-check card ("read
  only from your own figures and your declared aims" — findings are deterministic via the strategy_diag
  firewall, model only narrates, with honest "AI · review before use"/"not advice" disclosures); the register
  foot ("Signals shows only the signals that cross a threshold" — actively undercuts any complete-ordering
  read). THE LOOSE TOOLTIP was loose at TWO levels: (1) GLOBALLY — the fixed SIG_DOMAINS group order (Pay →
  Incentives → Benefits → Time Off → Wellbeing → Recognition → Governance, pages.js:905/~1043, NOT materiality-
  reordered) means Pay's rows always come first, not the most material across domains; (2) WITHIN-AREA — Pass 3
  (confirm ×0.25 demote → tail) and Pass 3.5 (pin → top) DELIBERATELY made the within-area order NOT pure
  materiality, so a tooltip claiming "most material first" now CONTRADICTS the ordering we spent two passes
  building. RULING B (David): DROP the superlative entirely (not the minimal "within each area … most material
  first" scoping, which fixes only level 1 and leaves level 2 contradicting Pass 3/3.5). CHANGE (web/js/
  pages.js:~1089, title= string only, cache v257→v258): "The most material signals for your stance come first.
  Set in your reward strategy." → "Each area is ordered for your stance — pins stay on top. Set in your reward
  strategy." States what is TRUE at both levels: each AREA ordered FOR YOUR STANCE (impact is strategy-shaped),
  PINS STAY ON TOP (Pass 3.5 — and the ordering fact the user most needs, since they took the explicit pin
  action). Honest ABOUT Pass 3/3.5 rather than undermining it. The visible chip "ordered for your strategy" is
  UNTOUCHED (already honest). A rejected (knowingly keeps a loose superlative when the fix is free); C (strategy-
  rank the groups) rejected (breaks the stable, navigable fixed domain order — users learn "Pay is always
  first"; over-engineering — fixed order is a navigation feature, not a bug). DEGRADE (verified clean): the
  tooltip lives inside the same data.strategy_objective-gated span, so it never shows when strategy is off — no
  new conditional, zero degrade risk (sweep: this is the ONLY loose claim in SignalsPage; strategy_off_has_
  orphan_claim=false). QA (in-browser, v258, live demo org): strategy-ON → chip present, visible text "ordered
  for your Control cost strategy · edit" (untouched), tooltip = the new copy; strategy-OFF (overview?strategy=
  off render) → chip ABSENT, zero "most material" text anywhere on the page; 0 console errors. ✅ This CLOSES
  the 5-pass Signals strategy-coherence sequence: (1) colour = market DIRECTION (Pass 1), (2) confirm/tension
  ICON system — green On-plan pill (Pass 2), (3) confirm-aware rank → tail-clump (Pass 3 A+), (3.5) pin beats
  confirm (Pass 3.5 A), (4) context-row verify — no-build false alarm (Pass 4), (5) header honesty — drop the
  superlative (Pass 5 B). OUT-OF-SCOPE observation flagged for a future look (NOT a Pass 5 ordering issue): the
  sweep reports caveats.illustrative is captured into StrategyCheck state (pages.js:301) but never RENDERED, so
  an org on a synthetic peer pool may show no sample-data caveat in the strategy-check card — unverified, parked.

2026-06-26 — SIGNALS QA (post-Pass-5) — PAY GROUP ORDERING, RULING NO-BUILD (Q1 neutral sort position + Q2
  rest-of-order). Three live screenshots of the Pay group (domain groupBy, inbox tab, demo org) showed the 2
  NEUTRAL "context, not a verdict" rows — Workforce cost per FTE (PROP_d16bae79), Workforce cost as % of
  revenue (PROP_e63cf45a) — leading the group, ABOVE the actionable below-market verdicts. DIAGNOSED read-only
  (no DB write). Q1 — WHY neutral leads: they carry the HIGHEST BASE IMPACT in Pay (globalIdx 6 & 7 = the first
  two Pay rows; impact is popped server-side at signals.py:932 so the signals_all ARRAY ORDER is the impact-desc
  rank). They are kind="ahead" Level signals (you spend LESS than market — "LOWER THAN MARKET": £27,500 vs
  £44,000 ≈ £16.5k/FTE; 14% vs 37% = 23pp), polarity-neutralised because lower-cost is directionally ambiguous
  (efficient vs under-resourced). Their base verdict-tier impact scales with that large gap. NOTABLY the strategy
  re-rank DEMOTES them: lens=attract under the org's "cost" objective → OBJECTIVE_LENS_MULT["cost"]["attract"]
  =0.6 (signals.py:298), a STEEPER demote than the retain/engage below rows (×0.8) — yet they still lead, so the
  base gap dominates. NOT a sort bug. RULING Q1 (David): NO-BUILD. Demoting neutral to the group TAIL (the
  earlier diagnostic lean) is REJECTED — it would re-introduce the no-verdict↔low-value conflation Pass 4
  explicitly refused, by burying the LARGEST-materiality rows in the group. Neutral is HIGH-MATERIALITY CONTEXT,
  not low-priority signal — categorically unlike confirm (which tail-clumps CORRECTLY, Pass 3, because an on-plan
  row genuinely IS low-priority/nothing-to-act-on). The navy tone (.sig-tone-neutral / .pos-neutral) + the
  italic "context, not a verdict" hint already mark these rows, so leading with them does not mislead. THIS
  EXTENDS PASS 4: neutral context rows are correct on COLOUR (navy, distinct from amber), GAUGE-EXCLUSION
  (excluded from 76/15/1/92 via pages.js:1040), AND now SORT POSITION (high-impact context legitimately leads).
  Q2 — REST OF PAY ORDER: correct-by-rank, no action. The rendered inbox Pay order is strictly globalIdx-
  ascending (verified) = pure impact-desc across all tier-2 active rows; differs and below rows are INTERLEAVED
  by impact (Tronc gi8 / Pay-increase gi9 high; Utility gi42 / Pay-for-skills gi44 / Other gi54 low), NOT grouped
  by position — the expected impact-stable residual, not a bug. 0 confirm + 0 pin in Pay (Pay is not the
  on_target domain; the override is Time Off→lag), so Pass 3/3.5 don't apply here. FLAGGED FOR ITS OWN GATED PASS
  (NOT folded in, parked): the cost metrics' lens=attract tagging. For a cost-objective org the cost objective
  DEMOTES the cost rows ×0.6 (attract under cost) — they lead on base gap alone, FIGHTING the multiplier. If
  "Workforce cost per FTE" / "cost as % revenue" should be lens=save (boosted ×1.7 under cost), the strategy
  would point the SAME way as the gap = coherent. This is a STRATEGY-COHERENCE question (does the engine's lens
  tagging match the declared objective?), distinct from sort position. Its own gated diagnose when wanted —
  verify the intended lens semantics BEFORE any re-tag, gauge-neutral check (a lens change doesn't touch verdict
  mass), 2nd-org spot-check. Not actioned this turn.

2026-06-26 — LENS-TAG COHERENCE — cost metrics RE-TAGGED attract → save (ruling: MIS-TAG, BUILT). Surfaced by
  the Pay-group QA: "Workforce cost per FTE" (PROP_d16bae79) and "Workforce cost as % of revenue" (PROP_e63cf45a)
  were tagged lens=attract in signal_lenses.json position_lenses, so under the demo org's "cost" objective they
  were DEMOTED ×0.6 (OBJECTIVE_LENS_MULT["cost"]["attract"]) — they led Pay on base-gap materiality alone,
  FIGHTING the strategy multiplier. DIAGNOSED read-only (3-agent workflow): SEMANTICS — save is EXPLICITLY
  defined as employer spend/cost ("save (money out vs peers)" signals.py:5; "where your spend sits vs the
  market" pages.js:852; cost_metrics = "NEUTRAL spend metrics eligible for the 'save' lens — a fact about cost,
  never a market verdict" signal_lenses.json:6); attract = "how you draw talent in" (talent-draw, not spend).
  The lens MAP is David-owned (signals.py:11-13). CONSISTENCY — the two "total workforce cost…" rows were the
  ONLY cost-magnitude/spend metrics tagged attract; every sibling spend metric routes to save (pension cost
  share, PMI premium, car allowance, shift premiums, allowance pensionability); the only spend-adjacent attract
  (AI-skills pay premium) is an attraction PRACTICE, not a cost-magnitude metric. RULING (David): MIS-TAG →
  re-tag both to save within position_lenses (NOT moved to cost_metrics — keeps the position framing + neutral
  polarity). This is a COHERENCE fix, not a re-rank: both rows already lead Pay; under cost, save=×1.7 vs
  attract=×0.6 just makes them lead BECAUSE of the strategy instead of despite it. save is objective-independent-
  correct for a spend metric (cost boosts; attract/retain demote ×0.9 — all sensible). ORTHOGONALITY/GAUGE-
  NEUTRAL (proven structural): lens drives ONLY the impact multiplier (+ per-lens briefing cap + signal_key diff
  identity + group-by); polarity (signals.py:749, separate) drives the verdict tone (navy .sig-tone-neutral,
  Pass 4) + gauge exclusion; positions.py (the gauge) has ZERO lens references — a lens re-tag cannot move
  polarity, the navy "context" colour, or 76/15/1/92. BUILD (in order): (1) WAL checkpoint(TRUNCATE) + backup
  lumi.db → lumi.db.bak_pre_retag_lens_20260626_092653 (74M, gitignored). (2) edit data/signal_lenses.json
  position_lenses: PROP_e63cf45a + PROP_d16bae79 "attract"→"save" (2-line diff; hot-reloads via lens_config, no
  restart, NO web cache bump — lens isn't a web asset). (3) SILENT propagation: lens is part of signal_key
  ('%s:%s:%s:%s' % (lens,kind,question_id,row)), so the re-tag changed the key for these metrics in every org
  that has them in signal_state — a naive sweep would fire spurious cleared+appeared and storm the bell. Ran
  notifications.rebaseline (DELETE signal_state + record_baseline, fires 0 events) over EXACTLY the 154 orgs with
  a cost metric in signal_state (/tmp/dt_retag_rebaseline.py, in-process). NOT touched: data/lumi_questions.csv
  (no lens column), server/aggregate.py (no lens reference). QA — ALL PASS: notification_events 10804 → 10804
  (UNCHANGED → zero bell events, no storm); signal_state cost-metric lens now ONLY save (278 rows, 0 attract);
  /api/overview hero.market gauge 76/15/1/92 byte-identical (gauge-neutral confirmed); both rows render lens=save
  with polarity=neutral + position=below untouched (Pass-4 navy colour preserved); 154/154 orgs rebaselined, 0
  failures; .bak retained for rollback. The engine now points the SAME way as the declared objective for these
  spend metrics — strategy-coherence restored. (Note: a lens re-tag must go through silent rebaseline, never the
  nightly diff — the signal_key includes lens, established here as the pattern for any future lens-map edit.)

2026-06-26 — CAVEATS.ILLUSTRATIVE — strategy-check sample-data caveat, RULING NOT A GAP (no-build). The Pass-5
  honesty sweep reported that caveats.illustrative is captured into StrategyCheck state but may never RENDER —
  i.e. an org on a synthetic peer pool could read strategy-check findings with no "illustrative / sample data"
  warning. VERIFIED read-only end-to-end; the sweep was right on the render-absence but OVER-REPORTED it as a
  risk. TRACE: (SET) caveats.illustrative = bool(get_meta("synthetic_pool", False)) — produced at app.py:983 /
  1542 / 1558 / 3685 / 3722, meant to fire when the org sits on a synthetic peer pool. (CAPTURED) pages.js:301
  `illustrative: (r.caveats || {}).illustrative` into StrategyCheck state. (RENDERED) ZERO sites — exhaustive
  grep: the ONLY mention of illustrative/caveats in all of web/js is the capture at pages.js:301; the
  StrategyCheck render (pages.js:307-349) reads st.parts / st.source / st.onPlan / st.phase and NEVER st.
  illustrative. The captured field is dead state. So the binary answer is: it renders nowhere. WHY THIS IS NOT A
  GAP (three independent reasons): (1) DELIBERATE — task #68 retired the dev-era illustrative/synthetic self-
  labelling AT SOURCE (DECISIONS.md:3997-4007: "dropped the synthetic_pool field… flipped illustrative_sample_
  data to default OFF everywhere"), because the seed is expert-signed / plausibility-validated, so the benchmark
  is presented as real-member data PLATFORM-WIDE; the strategy-check card is CONSISTENT with every other surface,
  not dropping a caveat others keep. (2) QA-ENFORCED — qa_phase4 §4.5 + qa_commentary §D actively ASSERT no
  synthetic/illustrative label renders (and pass); qa_commentary.py:156 is explicit ("the 'illustrative sample
  data' caveat is retired; nothing renders it"). Rendering it would REVERSE a shipped decision AND fail 2 QA
  suites. (3) STRUCTURALLY DEAD FLAG — the synthetic_pool meta key is ABSENT from the live DB (only peer_pool
  exists, the real pool), so get_meta("synthetic_pool", False) returns False for every request → caveats.
  illustrative is ALWAYS false → NO live org fires it (demo org included). The honesty concern (synthetic-pool
  findings shown as real-peer) cannot manifest in current data. BLAST RADIUS: zero orgs. SIBLINGS: the strategy-
  check caveats object holds ONLY illustrative (no small_sample/coverage sibling), so there is no "a sibling
  renders but illustrative doesn't" signal. RULING (David): NOT A GAP → no-build. Optional, NOT actioned: the
  producer (5 app.py sites) + capture (pages.js:301) are vestigial (compute/stash a permanently-false flag) and
  could be deleted for tidiness, or left as a dormant hook — cosmetic, not corrective. FUTURE-REVIVAL GATE
  (recorded): if synthetic pools were ever revived (re-setting the synthetic_pool meta), the caveat would
  silently not render AND qa_phase4 §4.5 / qa_commentary §D would FAIL (they assert no label) — so the QA
  assertions force a deliberate re-introduction of the labelling at that time; the latent risk is self-guarding.
  No code, no cache bump. This closes the caveats.illustrative item parked in the Pass-5 entry (DECISIONS.md:5500).

2026-06-26 — EMPLOYER PENSION £206k — DE-MONEY on Signals (Ruling B), BUILT. The Benefits Signals group rendered
  "Employer pension · £206k/yr below the market median" — an aggregate £ among per-level % pension siblings.
  VERIFIED (prior turn): REW_BEN_PENS_EMP_MAX_01 ("Maximum employer pension contribution rate by level", unit=%,
  matrix per-level, higher_is_better, exclude_from_scoring) is the SOLE money_lenses member; £206k =
  Σ_levels (peer-median rate − your rate)/100 × median_salary × (org_FTE × level_share) (positions.py:514-515) —
  a deliberately-modelled INDICATIVE aggregate, NOT a bug, but headcount-scaled (measures org SIZE as much as
  design generosity), built off the MAX/ceiling rate of an exclude_from_scoring metric, with "below the market
  median" copy implying a £-median that doesn't exist. NOT the Pass-4 neutral case (pension is higher_is_better;
  money_opportunities skips neutral). RULING B (David): de-money on Signals — render it as the per-level % it
  actually is, like its 11 siblings; the £-opportunity stays ONLY on the board-pack £-model surface (where its
  indicative assumptions are labelled). PHASE A scoped the removal CLEAN (both STOP gates cleared): (1) the
  board pack reads MONEY_METRICS (positions.py) via money_opportunities — NOT money_lenses (signal_lenses.json),
  which drives ONLY the Signals row — so the two lists are already separate; removing from money_lenses is
  Signals-only and the board pack is untouched (proven in-process). (2) FALL-THROUGH proven: seen_q enforces
  one-class-per-metric, and the money block only claims a metric when it's in money_lenses; removed, the verdict
  block emits it as a per-level % ("you 5%, market median 9% · below market", kind=behind, higher_is_better) —
  unit-coherent. (3) GAUGE structurally safe: exclude_from_scoring → not in the 76/15/1/92 pool; lens/money
  never touch verdict mass. (4) The ceiling-rate % verdict reads honestly ("your max employer rate is below the
  market's max"). BUILD: removed REW_BEN_PENS_EMP_MAX_01 from money_lenses in data/signal_lenses.json (it was
  the ONLY entry → money_lenses now {}; no metric emits a Signals money row now — the £-model lives entirely on
  the board pack, exactly the ruling). KEPT it in MONEY_METRICS (positions.py) so the board-pack £ survives.
  SIGNAL_KEY DISCIPLINE (the lens-re-tag pattern): removing from money_lenses flips the signal's kind
  (money→behind) + row (aggregate→per-level), changing signal_key — so, like the cost-metric re-tag, this went
  through a SILENT rebaseline, not the nightly diff. Scope: only the 54 orgs where the money block was actually
  firing (signal_state kind='money'); the other 130 (ahead 87 / behind 43) were already on the % path → key
  unchanged → provably unaffected. WAL-checkpoint(TRUNCATE) + backup lumi.db.bak_pre_demoney_pension_20260626_
  121740 (74M, gitignored) FIRST; then rebaseline(conn, oid, org_signals) per the 54 (DELETE + record_baseline,
  fires 0 events). QA — FOUR PROOFS, all pass (live demo org, in-process board-pack check): (1) UNIT-COHERENT:
  pension renders "you 5%, market median 9% · below market" (kind=behind, amber), at position 2/26 in Benefits
  (NOT pinned top — the 1,000,000+gbp money impact is gone), in-line with its % siblings; NO £206k anywhere on
  Signals; screenshot captured. (2) £-MODEL PRESERVED: money_opportunities STILL returns pension at £206,280
  (MONEY_METRICS untouched) → board pack keeps the £-opportunity. (3) GAUGE 76/15/1/92 byte-identical. (4) OTHER
  MONEY METRICS INTACT: all 3 MONEY_METRICS (pension + attrition + agency) still defined; attrition/agency were
  never Signals rows (not in money_lenses) and are unaffected. STORM CHECK: notification_events 10804 → 10804
  (zero events); pension signal_state now ahead=87 / behind=92 / money=0; 54/54 orgs rebaselined, 0 failures; 0
  console errors. NOTE: de-moneying drops the pension Signals row for ~5 orgs whose £ gap was material but whose
  per-level rate gap is below the % signal threshold (the board pack retains their £) — the intended effect of
  removing headcount-scaling (a small rate gap shouldn't headline Signals just because the org is large). No web
  cache bump (signal_lenses.json is server-side, hot-reloaded; the Signals render is data-driven from
  /api/overview, not an asset — consistent with the lens re-tag). lumi_questions.csv + MONEY_METRICS (positions.py)
  + aggregate.py untouched. ✅ Pension now reads as the unit-coherent % verdict it is; the £-opportunity lives
  where its assumptions are labelled (the board pack).

2026-06-26 — SIGNALS VERDICT ADVERB — RULING A (per-metric severity adverb), BUILT. A skeptical reward director
  reads "below market" worded identically for a chasm (£700 vs £1,550 = 55%) and a rounding error (£1,500 vs
  £1,550 = 3%) as "this tool can't tell a real problem from noise." DIAGNOSED (prior turns): magnitude IS
  computed — depth_pctl already drives a "clearly/moderately/marginally" severity adverb ON THE HERO
  (pages.js:691-694) — but the per-metric SIGNAL verdict was flat. The fix is a CONSISTENCY/calibration win, not
  new machinery. THREE rulings resolved on live data before building (the STOP gate): (1) BASIS = %-GAP-FROM-
  MEDIAN on the signal (per-metric real-terms gap), NOT percentile. A reward director judges materiality in gap
  SIZE; percentile-depth (a) skewed ~40 clean signals into one bucket and (b) couldn't separate the £700/£1,500
  examples (a %-gap distinction). The HERO STAYS percentile (it's a DOMAIN verdict — peer-standing mass);
  signal=real-gap, hero=peer-standing — DIFFERENT SCOPES, both calibrated, not a contradiction (so the hero is
  NOT relabelled). (2) SCOPE = property-based: the adverb fires ONLY on positioned VALUE verdicts with a real
  %-gap — position in (below/above) AND polarity != neutral AND kind not in (prevalence/depth/money) AND the
  item has numeric value + p50 (≠0). Excludes prevalence ("most do this", adoption not a value gap), neutral/
  context (Pass 4), and approach/differs BY PROPERTY, not a list. Plus a <3% FLOOR: a sub-3%-gap row is at-
  market noise → plain verdict, NO adverb. (3) CALIBRATION = clearly >40% · moderately 15-40% · marginally
  3-15% (symmetric for above). David's initial >25/10-25/<10 lean gave an EMPTY MIDDLE on the demo org (29/0/8 —
  non-differentiating, the exact failure the STOP existed to catch). >40/15-40/<15 gives 16/13/8 (all buckets,
  round + defensible: "more than 40% below = clearly far below"). 2ND-ORG CALIBRATION GATE (the overfit check):
  across 6 diverse orgs (freight/tech/college/utilities/environmental/transport, all fte-bands) the buckets
  spread across all three every time (e.g. Yarrowwell 5/3/15, Larkholm 21/6/4, Fenland 5/16/1) — NOT Thornbridge-
  overfit; each org's adverb reflects its own gap profile. BUILD: (server/signals.py) a post-pass after the
  signal loop attaches s["gap_pct"] = round(|value − p50|/|p50| × 100, 1) for in-scope signals, reusing the
  item's value+p50 (matched by question_id + matrix row via sig_id); (web/js/pages.js) severityAdverb(s) +
  posTag prepends the adverb to the verdict text for the two positioned-value branches only. SIGNAL_KEY CHECK
  (confirmed before writing, per the lens-re-tag lesson): signal_key = lens:kind:question_id:row (signals.py:52)
  — the verdict STRING is NOT in it, and gap_pct is not a signal_state column → NO key change → NO rebaseline,
  NO storm. Presentation-only (a descriptive word before the unchanged verdict class) → gauge-neutral. SCOPE BUG
  caught + fixed in QA: the first server pass gated only on position+polarity, so 11 PREVALENCE rows (adoption
  0-vs-100 → 100% "gap") wrongly got "clearly" — added the kind not-in (prevalence/depth/money) exclusion;
  re-verified 0 prevalence / 0 neutral carry gap_pct. QA — FIVE PROOFS, all pass (live demo, v258→v259, server
  restart for the signals.py change): (1) DIFFERENTIATES — rendered 15 clearly / 12 moderately / 1 marginally,
  all buckets. (2) EXAMPLES — "Total allowance payment · you £700, market median £1,550" → "clearly below
  market"; "Base salary (Head of) · you 96%, market median 99%" → "marginally below market" (screenshot). (3)
  SCOPE — neutral cost rows "below market" (plain), prevalence/differs plain, sub-3% no adverb. (4) GAUGE
  76/15/1/92 byte-identical. (5) 2ND-ORG spread (above). 0 console errors. No DB write (no rebaseline). Cache
  v258→v259. ✅ The signal verdict now calibrates to the metric's real-terms gap — the hero↔signal flatness that
  a domain expert read as unreliability is closed; the hero keeps its percentile-depth scope, the signal answers
  the real-gap question, both honest.

2026-06-26 — SIGNALS FRESHNESS (confidence axis 2 of 3) — SPEC RULED, BUILD DEFERRED (dormancy). Self-data
  currency: "how old is my OWN figure" — distinct from magnitude (the verdict adverb) and peer-n (the single-
  source "Small sample" caveat). DIAGNOSED read-only. DATA: answers.submitted_at (db.py:98) is per-answer,
  defaults datetime('now'), updated on every INSERT OR REPLACE (app.py:3591), with answers_history — BUT
  get_org_answers (positions.py) selects only question_id/matrix_row_id/value, so submitted_at is NOT reachable
  at render today; it needs a thread (a submitted_at query → onto the item/signal, exactly like gap_pct and n
  were threaded). PLACEMENT: the figure line "you £X, market median £Y" is the signal's `stand` (signals.py:227)
  → the .sig-stand span, SEPARATE from the verdict pill (pos-tag) — so a currency cue attaches near the figure,
  not in the verdict. JUDGMENT FORK ruled: A (neutral date, "we flag, you decide") + B's DATA for SCOPE — i.e.
  the SPEC is: show a NEUTRAL DATE ("entered Mar 2025", never the word "stale"/"old"/⚠️) on the figure line,
  STABILITY-GATED to metrics that can actually go stale (the per-metric `stability` field EXISTS in
  lumi_questions.csv: stable=731 / variable=32 / volatile=15; plus update_frequency annually=543 / ad_hoc=220 /
  quarterly=15 — option B is feasible, no capture needed). Show the date only on the ~47 variable/volatile rows,
  SILENT on the 731 stable (pension design barely moves — a date there is noise). Metric-aware WHICH-rows +
  neutral WHAT-it-says: no crying-wolf, no clutter, no tool-asserts-"stale" judgment. C (flat "N months → stale"
  threshold) REJECTED — cries wolf on the 731 stable metrics. ANTI-MERGE clean: freshness is its OWN cue (a
  date), OWN word ("entered [date]"), OWN placement (the figure line) — does not touch the verdict adverb
  (magnitude) or the page-level "Small sample · N peers" single-source caveat (peer-n). signal_key/gauge
  unaffected (a date on the stand line is presentation, not a verdict class; submitted_at isn't in signal_key
  or signal_state). ⭐ DEFER RATIONALE (the load-bearing ruling): the synthetic seed was generated ALL-AT-ONCE —
  EVERY answer carries submitted_at in 2026-06 (demo org: 964 answers, all June, span Jun 11-23 = 3-15 days old;
  ALL orgs: 211,507 answers ALL 2026-06). There is NO stale self-data anywhere. So a freshness cue would render
  "entered this month" on every row — UNIFORM, RECENT, DORMANT — the exact "don't ship dormant against the data"
  failure ruled for the peer-n axis. AND unlike peer-n (which had the custom-cut path to fire on), freshness has
  NO live surface where it fires on this seed (no aged data to narrow to). RULING (David): DEFER the build until
  the seed gains temporal spread OR real orgs accumulate aged figures. The SPEC above is the durable artifact;
  the build is then a known scoped render-add (thread submitted_at + the stability gate + the .sig-stand date,
  ~mirrors the gap_pct pass). (Build-now-dormant was the alternative — capability lands ahead of real aged data,
  QA'd only via forced old timestamps, invisible on the demo — correct + future-proof but un-exercisable now;
  David ruled DEFER over it.) CONFIDENCE/STALENESS PROGRAMME STATUS: (1) magnitude → BUILT (the %-gap severity
  adverb). (2) peer-n → NO-BUILD (already handled by the single-source "Small sample · N peers" caveat, window
  [5,20); the Signals page is deliberately all-peers and "renders nothing extra"). (3) freshness → SPEC RULED,
  BUILD DEFERRED (this entry). (4) anchor quality → its own capture-first pass on the Anchor Register programme
  (grade/est provenance is an offline file read by no code; needs import into the runtime before any render).
  No code, no cache bump.

2026-06-26 — ANCHOR PROVENANCE — STAGE 1 CAPTURE (confidence axis 4), BUILT. The Anchor Register
  (lumi_anchor_register_CLAUDECODE.json: per-metric grade A/B/C/EST + est bool + source citations, 121 anchored
  rows) was an OFFLINE FILE READ BY NO CODE — only anchor VALUES were imported at seed time; the grade/est/source
  provenance never reached the runtime, so a Grade-A CIPD-verified median and an estimate-flagged derivation
  rendered IDENTICALLY. This is the real, NON-dormant, highest-leverage credibility axis (grades genuinely vary
  across rows — unlike peer-n [already single-sourced] and freshness [dormant on the all-June seed]). CAPTURE-
  FIRST: import provenance into the runtime so it's READABLE at render, BEFORE any render (stage 2 is its own
  ruling). DIAGNOSED read-only: join key = metric_id = question_id (ORPHAN=0 — every register row maps to a live
  snapshot metric; the join is sound); grade A=75/B=30/C=8 (sourced/verified, descending quality) + EST=8
  (estimate-flagged), est=true ⟺ grade=EST (the 8); the register's own meta WARNS "parsed_pcts are anchor values
  only; benchmark_snapshots is the live-value source of truth" → so the import is PROVENANCE-ONLY (grade/est/
  source by metric_id), never values, making value-drift irrelevant. ⭐ COVERAGE (the load-bearing finding): 121
  graded of 844 live question_ids → ~86% UNKNOWN (or 122 of the register's 243 tracked metrics). UNKNOWN is the
  DOMINANT state, forcing a genuine THREE-STATE (verified / estimate / UNKNOWN); an ungraded metric must NEVER
  default to verified (would falsely credential 723) nor estimate (would falsely flag fine rows). BUILD (capture-
  only, no render): (1) data/anchor_provenance.json — a curated per-metric config (question_id → {grade, est,
  source}, 121 entries) distilled from the register, same shape as signal_lenses.json — David-owned, hot-reloaded,
  SURVIVES RESEEDS (a benchmark_snapshots column would be wiped on reseed). (2) anchor_provenance() loader in
  signals.py (mtime-cached, mirrors lens_config). (3) build_signals post-pass attaches s["anchor_grade"] for the
  graded metrics; ABSENT = UNKNOWN by omission (POSITIVE-LIST semantics). The grade rides the signal payload so
  it's READABLE at render, but NOTHING renders it — stage 2 (the render fork) is a separate ruling. GAUGE-NEUTRAL
  by construction: metadata (a grade label), not a value — touches no value/verdict/score. SIGNAL_KEY untouched
  (anchor_grade not in lens:kind:question_id:row, not a signal_state column) → no rebaseline, no storm. QA — FIVE
  CAPTURE PROOFS, all pass: (1) CONFIG CORRECT — 121 entries (75 A / 30 B / 8 C / 8 EST); loader returns A for a
  verified metric, the EST flag for an estimate, ABSENT→UNKNOWN for an ungraded one. (2) THREE-STATE on the live
  payload — demo org's 88 signals: 49 graded (A=21/B=22/C=1/EST=5) + 39 UNKNOWN (anchor_grade absent — e.g. EV
  charging, Workforce cost per FTE — NOT defaulted to verified). (3) GAUGE 76/15/1/92 byte-identical. (4) BYTE-
  IDENTICAL-VISIBLE — pages.js v259 (NO cache bump, no client change), 81 rows render, verdicts/adverb intact, NO
  anchor/grade/verified text leaks to screen, 0 console errors (provenance captured but unrendered). (5) SANITY
  SPOT-CHECK — the 8 EST all still status "ESTIMATE-FLAGGED (no published prevalence)" source "-"; 3 sample A-
  grades all still CIPD-sourced, est=False. No DB write, no cache bump. ⭐ STAGE 2 (RENDER) IS A SEPARATE RULING:
  the coverage (~86% UNKNOWN) pushes AWAY from mark-estimate (which would imply the other 836 are verified) TOWARD
  mark-verified (credential only the earned 113) or an explicit three-state. The register stays the offline
  curation source-of-truth; data/anchor_provenance.json is the distilled runtime artifact. CONFIDENCE/STALENESS
  PROGRAMME: (1) magnitude → BUILT (severity adverb). (2) peer-n → NO-BUILD (single-source "Small sample"
  caveat). (3) freshness → SPEC RULED, BUILD DEFERRED (seed-dormant). (4) anchor → STAGE 1 CAPTURED (this), stage
  2 render pending.

2026-06-26 — ANCHOR PROVENANCE — STAGE 2 RENDER (ruling B), BUILT. Stage 1 captured s.anchor_grade (A/B/C
  verified · EST estimate · absent=UNKNOWN) onto the signal payload, unrendered. Stage 2 surfaces it. RULING B
  (David): MARK-VERIFIED + MARK-ESTIMATE, UNKNOWN silent-default. Rationale: UNKNOWN = provenance UNASSESSED
  (not in the curated register); ESTIMATE = ASSESSED-and-weak (curator-derived, no published source) — different
  claims, so collapsing assessed-weak into unassessed would HIDE a known weakness. Mark the two ASSESSED states
  (verified + estimate), leave the ~86% UNASSESSED bare. A rejected (estimate vanishes into unknown); C rejected
  (marking 723 unknowns = noise). GRADE: COLLAPSE A/B/C -> one "· verified source" on the row; the grade letter +
  citation ride the HOVER. PLACEMENT: the figure line (.sig-stand), anchored after the market-median portion (it
  is the ANCHOR's provenance) — distinct from the verdict adverb (in the pos-tag pill) and the page-level peer-n
  "Small sample" caveat. Reserves the "you £X" half of the figure line for the deferred freshness cue (the figure
  line is a two-cue zone: your-figure-freshness | anchor-provenance). GLYPH-CLASH GUARD honoured: the verified
  mark is TEXT ("· verified source"), NOT a check — the row's green ✓ "On plan" confirm pill (Pass 2) owns the
  check glyph; a row that is BOTH confirm AND verified shows both unambiguously (different zones/treatments).
  BUILD: (server/signals.py) threaded s["anchor_source"] alongside s["anchor_grade"] in the stage-1 post-pass
  (one line, same anchor_provenance() config) so the citation reaches the payload for hover. (web/js/pages.js)
  provMark(s): UNKNOWN -> null (no mark); EST -> quiet "· estimate" (title "Curator estimate — no published
  source. Treat directionally."); A/B/C -> quiet "· verified source" (title "Verified anchor (Grade <g>) ·
  <source citation>"); rendered in the Row .sig-stand after s.stand. (web/css/app.css) .sig-prov (cursor:help +
  faint dotted underline as the hover affordance), .sig-prov-ok (neutral ink), .sig-prov-est (muted amber
  caveat, italic) — quiet, distinct from each other and from the On-plan check. cache v259->v260. GAUGE-NEUTRAL:
  presentation only — anchor_grade/source are metadata, never feed the verdict/score; 76/15/1/92 byte-identical.
  SIGNAL_KEY untouched (anchor_grade/source not in lens:kind:question_id:row, not signal_state columns) -> no
  rebaseline, no storm. QA — FIVE PROOFS, all pass (live demo, v260, server restart for the source thread): (1)
  THREE-STATE RENDERS — verified=44 "· verified source", estimate=3 "· estimate", unknown=34 UNMARKED. (2) NO
  GLYPH CLASH — 4 rows are BOTH confirm AND verified (e.g. "Sabbatical or career break"): green ✓ On-plan pill on
  the name line + muted "· verified source" text on the figure line, distinct + unambiguous (screenshot). (3)
  SOURCE ON HOVER (the payoff) — verified hover shows the real citation ("Verified anchor (Grade B) · CIPD Labour
  Market Outlook Spring 2026"); estimate hover shows the honest "no published source" note. (4) BYTE-IDENTICAL-
  UNKNOWN — the 34 unknown rows render exactly as today (unmarked); the "you £X" freshness half untouched. (5)
  GAUGE 76/15/1/92 unchanged. 0 console errors. ✅ This CLOSES THE ANCHOR AXIS (stage-1 capture + stage-2 render)
  AND THE CONFIDENCE/STALENESS PROGRAMME: (1) magnitude -> BUILT (severity adverb); (2) peer-n -> NO-BUILD
  (single-source "Small sample" caveat, Signals deliberately renders nothing extra); (3) freshness -> SPEC RULED,
  BUILD DEFERRED (seed-dormant, the figure-line "you £X" half reserved for it); (4) anchor -> BUILT (verified +
  estimate marks, UNKNOWN silent-default, source-on-hover). Every confidence axis is now either surfaced, single-
  sourced, deferred-with-spec, or rendered — and the Signals verdict carries direction (Pass 1) + magnitude
  (adverb) + anchor provenance, with peer-n at the page level and freshness reserved.

2026-06-26 — SIGNALS FILTERING — SCOPED B (provenance + risk filters), BUILT. The Signals page computes rich
  per-row attributes but a director could only READ 81 signals, not SLICE the new credibility data. DIAGNOSED:
  position chips were ALREADY clickable filters (posF single-select -> visible; "option A" already shipped) +
  tabs=status + group-by=domain/lens; the GAP was the new data — magnitude (gap_pct), provenance (anchor_grade),
  risk_framed, confirm — unfilterable. RULING (David): scoped B — TWO new filters, not four. (1) PROVENANCE
  ("verified source") — the highest-value slice, makes the anchor programme usable (the board-brief "show only
  source-backed verdicts"). (2) RISK ("risk only") — duty-of-care focus. DEFERRED: magnitude (partly redundant
  with ordering+adverb) and confirm ("hide on-plan", redundant — already tail-clumped + glyph-marked) — legibility
  budget: +2 composable filters extends cleanly, +4 doubles the chip row and clutters a clean page. ⭐ COMPOSITION
  MODEL (the load-bearing design point): the position chips are MUTUALLY EXCLUSIVE (posF single value); provenance
  + risk are a DIFFERENT AXIS — a director wants "below market AND verified source", not either/or. So the two new
  filters are INDEPENDENT BOOLEAN PREDICATES that AND with position, NOT additions to the posF single-select group.
  visible = triaged.filter(position).filter(!provF || verified).filter(!riskF || risk_framed). UI = a distinct
  "show only" toggle group (.sig-filters / .sig-fchip) separate from the position chips, with a DIFFERENT visual
  language (DASHED border + a TINTED on-state, vs the chips' solid border + solid-dark on-fill) so they read "add
  these on", not "pick one instead". BUILD (web/js/pages.js + web/css/app.css, client-only): provF/riskF state
  (independent of posF); isVerified = anchor_grade in A/B/C; provCount/riskCount counts in triaged (toggles only
  render when >0); the two toggles in .sig-controls after the position chips; empty-result message generalised to
  "No signals match this view — clear a filter to see more" (the groups.length===0 guard already covers any
  emptying combo); reset-on-nav added to goToDomain (mirrors posF). cache v260->v261. PURELY PRESENTATIONAL: a
  client-side VIEW op (React state, like posF/cut-switching) — no payload change, no GET, no gauge effect, no
  signal_key, NO rebaseline. QA — FOUR PROOFS, all pass (live demo, v261): (1) COMPOSES — baseline 81 -> verified
  44 -> verified AND below-market 30 -> +risk 3 -> toggle all off restores 81 (filters AND, never replace). (2)
  INDEPENDENT AXIS — toggling the position chip does NOT reset the verified toggle (both held together; different
  axes). (3) EMPTY-RESULT GUARD — "above market" + "risk" -> 0 rows -> graceful "No signals match this view — clear
  a filter" fallback, not a blank page. (4) PRESENTATIONAL — gauge 76/15/1/92 byte-identical; filters reset on nav
  (set verified -> navigate away+back -> cleared). 0 console errors; screenshot shows the distinct "show only"
  group (verified source blue-tinted active + risk shield) beside the single-select position chips. The new
  credibility data (anchor provenance) and the duty-of-care risk state are now sliceable, composing cleanly with
  the existing position/tab/group axes — the expert questions ("only verified-source below-market gaps", "just the
  risk rows") answerable in two clicks.

2026-06-26 — OVERVIEW SIGNALS PANEL — FILTER-BEFORE-SLICE FIX (APPROVED), BUILT. The home "Signals · top 4"
  panel sliced the top-4 UPSTREAM (OverviewPage, on server status) then the panel's optimistic dismiss filtered
  POST-slice with no re-slice — so dismissing a row shrank 4->3 with an empty slot, never backfilling rank #5. The
  explore page was already correct (filters the full pool before any cut). Fix (2 pure-client edits, matching the
  explore page): (1) OverviewPage passes the FULL live pool signals=${_viewLive} (removed the now-dead _viewShown);
  (2) SignalsPanel filters THEN slices — const shown = sigs.filter(s => effStatus(s) !== "dismissed").slice(0,4).
  QA (4 proofs + edge): BACKFILL — dismiss #1 -> 4 rows (#5 slides up), dismiss #2 -> 4 rows (#6 slides up), never
  a hole; ORDER — non-dismissed order byte-identical to baseline (the move applies no re-sort, panel maps _viewLive
  in server impact-order); COUNT HONESTY — header "top 4" = visible, footer "See all 50" = _viewTotal (full view
  pool), unchanged by the move; PURE RENDER — zero new network calls (backfill is a client re-slice on the existing
  optimistic overlay), 0 console errors; EDGE — slice(0,4) on a <4 pool returns the whole array (JS-safe), renders
  however many remain without erroring. Gauge 76/15/1/92 byte-identical; 2 QA-dismissed signals restored (demo
  org clean). Cache v261 -> v262.

2026-06-26 — OVERVIEW SIGNALS PANEL — TOP-3 + DISMISS→BACKFILL ANIMATION (David: "change the number to 3 and
  create an animation when one is dismissed and another is added"), BUILT. (1) COUNT 4 -> 3: SignalsPanel
  slice(0,3); header "Signals · top 3", footer "See all N" unchanged. (2) ANIMATION — refilling-queue
  choreography: the dismissed row fades out IN PLACE (CSS @keyframes sig-leave-out .26s, opacity + scale/slide),
  then on commit the survivors FLIP up to their new slots and the next-ranked signal rises + fades in at the tail
  (one React.useLayoutEffect measuring offsetTop deltas; backfill enters from translateY(12)+opacity 0). Dismiss is
  two-phase (flag `leaving` -> CSS fade -> 260ms -> commit setStOv so the row drops and #4 backfills); Pin/Save
  commit instantly. ENABLERS: rows re-keyed by signal id (were key=index, which made React swap row CONTENT instead
  of mounting/unmounting — fatal for enter/leave), + data-sid hook + sig-leaving class. ACCESSIBILITY:
  prefers-reduced-motion commits instantly, no FLIP, no fade (CSS guard + JS branch). FLIP chosen over a layout
  change because .signals-list is space-evenly/flex:1 — removing the top row shifts survivors ~112px (measured), so
  a naive removal would jump; FLIP smooths it while preserving the card's filled layout. QA (live, market view):
  count=3; dismiss -> backfilled:true, count_held_3:true, order_preserved:true; leave row carries sig-leaving;
  backfill observed at enter initial state then settled opacity ~1; inline transforms/transitions fully cleaned up
  (no hover-slowdown leftover); gauge 76/15/1/92 byte-identical; 0 console errors. NOTE: smooth mid-flight motion
  not visually sampleable in preview (background tab throttles rAF/CSS-animation) — verified via start/end state +
  cleanup; plays smoothly in a foreground browser. Demo integrity: the 2 prior-task signals (Workforce cost,
  Maximum LTI) had silently reverted to dismissed; re-restored via status=null (app's real restore path) and
  confirmed it persists across reload. Cache v262 -> v263 (17 + 12, lockstep).

2026-06-27 — RAG / STRATEGY SEPARATION — PHASE A DIAGNOSE + PHASE B SPEC+HELPER, BUILT (Phase B; Phase A is
  read-only). RULING: two channels must never share a colour — COLOUR = market position RAG (amber=below /
  green=on / red=above), FIXED + strategy-INVARIANT; ALIGNMENT INDICATOR = a separate navy chip encoding distance
  from the org's OWN declared aim, strategy-on only, never recolours position. PHASE A (workflow: 6 surface
  readers + adversarial completeness critic, high confidence): per-surface map — domain page (CategoryPage) BLEED,
  home MIXED (gauge + tiles BLEED, signal rows + verdict-word CLEAN), Signals explore CLEAN (Pass 1 holds), on-plan
  pill CLEAN (the correct two-channel pattern; '.is-confirm' has NO CSS rule — inert), risk-colour separable,
  palette single-sourced-tokens / SCATTERED-logic. KEY FINDING: not a repaint — marketTone() (pages.js:435) ALREADY
  returns amber/green/red; the bleed is a 2026-06-23 'Fix 1' that swapped 4 surfaces (gauge donut, 7 tiles,
  MarketSpectrum, category-hero chip) onto an ATTAINMENT lens (attainTone/_gaugeAttain/ATTAIN_ALIGN, fed by server
  _market_target {stance,alignment}). So Phase B+ = a REVERT of those 4 onto marketTone + a new alignment chip.
  RED-ABOVE coexists with risk-coral: risk = coral glyph + INSET left-edge shadow (.is-risk box-shadow), position =
  background FILL + border-left-color (.sig-tone-*) — different CSS properties, no clash (maternity REW_BEN_FAM_002
  stays distinct in both strategy states). Pure render: server emits NO colour, only verdict/favourable/target
  enums; _market_target never changes verdict/counts/lean — NO signal_key/rebaseline. RULINGS: R1 signal rows STAY
  polarity-aware (do NOT flatten to literal RAG; a below-market lower-is-better metric is honestly green) — agreed.
  R2 alignment cue = navy 'target' chip (glyph + On plan / Behind plan / Ahead of plan) on BOTH gauge (caption
  slot) and tiles (header, compact) — David chose. R3 the two latent bugs (dead red v-above/v-above-over tile
  borders; inverted methodology legend pages.js:2112) get FIXED INSIDE the revert passes (passes 2 + 4), not
  deferred. PHASE B BUILT (commits alone, NO surface switched): (1) RAG_SPEC.md — the shared spec (§1 marketTone
  single source; §2 AlignmentChip; §3 risk; §4 degrade contract: strategy-off==strategy-on colour byte-identical,
  indicators added-only — every pass's gate; + the 4-pass sweep map). (2) AlignmentChip + ALIGN_LABEL dormant
  helper (pages.js:490) — navy chip, reads target.alignment only, renders null when absent, compact variant; wired
  onto NO surface. (3) .align-chip navy CSS (app.css:2270) — distinct from RAG + risk-coral. QA: pages.js PARSE_OK
  (no white-screen), AlignmentChip invoked 0 times (dormant), 21 attainTone/_gaugeAttain/ATTAIN_ALIGN refs intact
  (4 surfaces untouched), CSS served. Cache v263 -> v264 (17 + 12). NEXT: revert sweep = 4 gated passes (gauge ->
  tiles -> spectrum -> cat-hero+legend), none bundled, each proving the two-halves degrade contract.

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 1 (Overview gauge donut), BUILT. The hero "Where you stand" donut
  coloured by ATTAINMENT (_gaugeAttain = !market.target ? grey : on-aim?green:amber — one strategy-driven hue across
  the ring). Pass 1 reverts it to POSITION: each band carries its own marketTone hue (below=amber/on=green/
  above=red), the verdict band RICH. CHANGES (pages.js, pure render): (1) donut segments (v===band ? MKT_RICH :
  MKT_SOFT)[_gaugeAttain] -> [marketTone("below"/"at"/"above")] — colour now references NO strategy token (no
  _gaugeAttain/_onTarget/market.target); _gaugeAttain deleted. (2) the bled .arc-target alignment line
  (arc-target-<alignment>, green/amber + targetCopy) REPLACED (not added) by <AlignmentChip target=market.target />
  (Phase B navy chip) — strategy-ON only; strategy-OFF keeps the neutral "Strategy off — absolute market view" hint.
  CORRECTED CANARY (David ruled): NOT "off == today" — strategy-off donut was GREY today (the attainment artefact)
  and SHOULD change to marketTone RAG (a no-strategy org should see its position). The real proof = on==off colour
  PARITY. QA (live, demo org director@thornbridge, strategy on): counts 76/15/1/92 byte-identical; donut
  strategy-ON colours [below=amber-bright 58% RICH, on=--gauge-on, above=--gauge-above] === strategy-OFF colours
  (toggled live, byte-identical) — alignment left the colour channel; AlignmentChip "On plan" navy (#1F2A44)
  present ON, GONE OFF; old bled arc-target-* line absent (no double cue); the demo's divergent case now legible —
  below-market (amber) + "On plan" (intent matched, in the chip). 0 console errors. Verdict WORD still flips to
  "On target"/_onTarget (strategy TEXT framing, not colour) — left as-is (out of Pass 1 scope; flagged). Tiles
  still on attainment (Pass 2). Cache v264 -> v265.

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 2 (Category tiles ×7), BUILT. The 7 CategoryTiles coloured chip +
  top-border (vCls) + the whole position bar by ATTAINMENT (tone = ATTAIN_ALIGN[d.target.alignment] ||
  attainTone(verdict, aim) — the org's per-domain aim recolouring position). Pass 2 reverts tone to POSITION:
  tone = marketTone(verdict) (below=amber/on=green/above=red), strategy-INVARIANT; feeds chipCls (MKT_CHIP),
  vCls (MKT_VCLS) + the bar (MKT_RICH/MKT_SOFT) unchanged downstream. The alignment relationship now rides the
  compact navy AlignmentChip. DENSITY (David's explicit gate): the labelled chip on the name line OVERFLOWED the
  narrow tiles (134px tile / 102px header; "Incentives" name 99px + "On plan" 67px = head scrollWidth 174 >> 102)
  — reported, NOT shipped cramped. David ruled OWN-ROW: the chip rides its own full-width line under the verdict
  chip (.cat-tile-align, margin-top -s2 to group). QA (live, demo org director@thornbridge): all 6 substantive
  tiles v-below + chip-mid amber (Governance v-practice "no market rate", no chip); on==off colour parity TRUE
  (toggled live — every tile border+chipClass identical strategy-on vs off); AlignmentChip "On plan" present ON,
  GONE OFF (strategy-on only); own-row layout verified — chip below the name, align_row_overflow false,
  chip_overflows_tile false on all 7, uniform tile height 203px (no crowding). R3 LATENT BUG: the dead red
  .cat-tile.v-above / v-above-over borders — confirmed by synthetic probe (.cat-tile.v-above border-top-color =
  rgb(192,57,43) = --unfavourable; .tile-chip.chip-bad = red-tint bg + red text) that an above-market tile now
  renders position-red (path: above -> marketTone "red" -> v-above + chip-bad). FLAGGED: no demo org domain is
  above-market (all below/on), so R3 is confirmed-by-inspection, NOT live data; v-above-over ("redover") correctly
  STAYS retired (a strategy-overshoot concept with no meaning in the pure position lens). 0 console errors; parse
  OK. Screenshot tool mini-scaled (known quirk, stop/start did not clear) — density confirmed via pixel
  measurement, not eyeball. Cache v266 -> v267. NEXT: Pass 3 (MarketSpectrum hero + every category page).

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 3 (MarketSpectrum), BUILT. PHASE A: the MarketSpectrum
  (pages.js:514) is invoked ONLY on the category-detail page (:1638), NOT the overview hero (that's the
  Donut/gauge, Pass 1). Bands coloured tone = attainTone(v, aim) (:534) -> BLEED (aim = strategy stance). KEY
  Phase-A finding (a THIRD case, not replace-or-add): the spectrum ALREADY carries a SPATIAL alignment cue — the
  "your aim" bracket (:552-557) drawn in BLUE (--blue): a label + bracket + dashed zone-edges over the axis, plus
  the ink you-marker, strategy-on only (aimMid!=null). It is NOT a RAG-colour bleed (blue, separate SVG layer), so
  it neither needs replacing (it's not bled) nor is the slot empty. David ruled (option B): recolour the bracket
  blue -> navy (unify the alignment channel), keep it (richer spatial read than a chip for a scale), do NOT add an
  AlignmentChip to the spectrum (the category page's navy label-chip belongs at the cat-hero verdict = Pass 4).
  BUILD (pages.js, pure render): (1) band tone attainTone(v, aim) -> marketTone(g.k) — PER-BAND (below=amber /
  on=green / above=red), the verdict band rich; (2) the 4 aim-bracket fills/strokes var(--blue) -> var(--navy).
  CAUGHT IN QA: first wrote marketTone(v) (one verdict hue for ALL bands -> amber+amber); fixed to marketTone(g.k)
  (per-band). QA (live, demo org director@thornbridge, category Pay): bands now [below = amber-bright 58% RICH,
  on = --gauge-on soft GREEN] — per-band RAG, distinct; band parity on==off TRUE (toggled live, identical
  [amber,green]); navy "your aim" bracket renders var(--navy) strategy-ON, GONE strategy-OFF (degrade contract).
  RED BAND: above-band probe-confirmed red (MKT_RICH.red srgb 0.87/0.58/0.55, MKT_SOFT.red --gauge-above srgb
  0.91/0.70/0.68 — both R-dominant, distinct from amber/green). FLAGGED: the demo has only 1 above-metric total
  (no above-market DOMAIN), so the RICH red verdict-BAND is code-verified-not-live (carries the Pass 2 R3 debt);
  a Larkholm-style 96/107-above org would show it live (provisioning script handed to David). 0 console errors;
  parse OK. counts/geometry untouched (colour-only; band widths / aim-zone / marker unchanged). Cache v267 -> v269
  (v268 was the marketTone(v) bug build). NEXT: Pass 4 (category-detail hero chip + methodology legend realign).

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 4 (category-detail hero chip + methodology legend), BUILT. THE LAST
  REVERT — closes the 4-pass sweep. THREE pieces (pages.js, pure render): (1) cat-detail hero chip tone
  attainTone/ATTAIN_ALIGN[hero.target.alignment] -> marketTone(verdict) (:1616) — position lens, strategy-
  invariant. (2) added the navy AlignmentChip (full label, non-compact — hero is wide) beside the hero verdict
  chip (:1633), strategy-on only (hero.target). (3) R3 SECOND LATENT BUG — the methodology legend (.mp-legend,
  ~:2126) was INVERTED (below=--unfavourable red / on=--amber-bright / above=--favourable green); swapped to
  below=--amber-bright / on=--favourable / above=--unfavourable so it teaches the now-canonical marketTone (the
  prose's favourable/context labels stay honest — green covers on-market AND favourable-lower-better-below).
  QA (live, demo org director@thornbridge, category Pay): hero chip "below" = chip-mid AMBER; hero chip parity
  on==off TRUE (chip-mid both); navy AlignmentChip "On plan" (#1F2A44, full label) present ON, GONE OFF; spectrum
  navy bracket present. BRACKET+CHIP COMPOSE: the two navy cues sit 43px apart vertically (chip in the verdict
  row = state word; bracket in the chart below = spatial aim zone) — complementary, not a doubled cue. LEGEND
  verified live: below rgb(245,166,10) amber / on-favourable rgb(46,125,82) green / above rgb(192,57,43) red /
  differs purple / context navy — matches every live surface. 0 console errors; parse OK. RED debt: hero
  above-market chip = chip-bad (red, = the Pass 2 tile probe) — code-verified; Larkholm (96/107 above) NOT
  provisioned by David, so the rich-red hero/tiles/spectrum stay code-verified-not-live (provisioning script
  /tmp/provision_larkholm.py handed over). Cache v269 -> v270. CLEANUP FLAGGED (not done, out of scope): after the
  sweep, attainTone / ATTAIN_ALIGN / bandToneAim survive ONLY as defs + dead code (the unrendered pre-Donut `bands`
  arc array in OverallArc, superseded by the Donut) + comments — no live surface uses them; safe to delete in a
  follow-up. SWEEP COMPLETE: all 4 aggregate surfaces (gauge donut, 7 tiles, MarketSpectrum, cat-hero chip) now
  colour by marketTone (position, strategy-invariant); alignment rides the navy AlignmentChip / spectrum bracket
  (strategy-on only); signal rows stay polarity-aware (R1); risk coral unchanged; legend honest.

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 5 (verdict-word channel), BUILT. Closes the channel separation: the
  hero gauge verdict WORD + subtitle now = market POSITION, strategy-INVARIANT, matching the gauge colour + the
  below/on/above counts. PHASE A confirmed: word = (v==="below"?"Below":...) (:653), leanWord = the position lean
  descriptor (:700) — both position; the FIX-2 override headWord = _onTarget ? "On target" : word (:722) +
  headLean = _onTarget ? "sitting [dir] market, as you intend" : leanWord (:723) put the ALIGNMENT channel into
  the word (an amber gauge under "On target" read as a self-contradiction); strategy-off ALREADY showed the
  position strings (market.target absent → _onTarget false), so this is a revert-to-invariant; the "On plan" pill
  beneath = the Pass-1 AlignmentChip (:757), the existing alignment cue, unchanged. BUILD (pages.js, pure render):
  headWord = word; headLean = leanWord; — _onTarget + _dirPhrase fully removed (0 code refs; alignment lives ONLY
  in the AlignmentChip pill). QA (live, demo org director@thornbridge): word "Below" + subtitle "clearly below the
  market" — POSITION; word_parity on==off TRUE (identical "Below"/"clearly below the market" strategy-on vs off —
  the word is now strategy-invariant like the colour); pill present ON / GONE OFF (alignment channel, strategy-on
  only); pill correctly matches server alignment. NOTE: David changed the demo stance lag→MATCH between turns, so
  the org now reads alignment "behind" → pill "Behind plan" — a nice DIVERGENT demo (amber gauge + "Below" word +
  76 Below counts, all POSITION, beside "Behind plan" ALIGNMENT — two channels disagreeing honestly, no
  contradiction). In this "behind" state the word was already "Below" pre-fix (behind never triggered the
  override); the fix's visible change is the on_target/ahead case (was "On target" → now the position word),
  verified BY CONSTRUCTION (headWord = word unconditional). 0 console errors; parse OK. Cache v270 -> v271.
  CHANNEL SEPARATION NOW COMPLETE: colour (marketTone) + word/subtitle (position) + chip/bracket (alignment,
  strategy-on) all consistent across gauge / tiles / spectrum / cat-hero.

2026-06-27 — RAG / STRATEGY SEPARATION — R3 DEBT CLOSED + DEAD-CODE CLEANUP. (A) R3 LIVE-DATA DEBT CLOSED: ran
  /tmp/provision_larkholm.py (David-directed) → created a QA Admin login director@larkholm.example / lumi-above-2026
  on Larkholm Environmental Services Ltd, the most above-market seed org (96/107 above, already unlocked). Logged
  in + QA'd live: the rich RED now renders on ALL FOUR aggregate surfaces for an above-market org — gauge donut
  above-band = MKT_RICH.red (color-mix --unfavourable 54%); all 6 substantive tiles v-above + chip-bad (red border
  + red chip — the dead Pass-2 borders now reachable); MarketSpectrum above-band rich red; cat-hero chip chip-bad
  red. Closes the code-verified-not-live debt carried since Pass 2/3/4. (Larkholm login left in place as a
  persistent above-market demo org; it's a DB row, not committed.) (B) DEAD-CODE CLEANUP (pages.js, pure removal):
  retired the now-unused attainment lens — module-level POS_RANK / bandToneAim / attainTone / ATTAIN_ALIGN (zero
  live calls after the sweep; attainTone/ATTAIN_ALIGN only in comments, bandToneAim only fed the dead arc) — and
  the unrendered pre-Donut proportional-arc block in OverallArc (AIM / bandTone / the ARC CX,CY,R,W,capF
  destructure / gapF / polar / arcPath / a local arcSeams call / the `bands` array / tickAt / seams / tipY /
  NEEDLE / NTIP) — all computed but never rendered since the Donut replaced the dial. KEPT: arcSeams (still live in
  proportionalNeedleRot + MarketSpectrum), marketTone, MKT_BIDX, MKT_RICH/SOFT, AlignmentChip, proportionalNeedleRot.
  Refreshed the stale marketTone header comment (it described the retired two-mode off=marketTone/on=bandToneAim
  design). QA: parse OK; reload regression on BOTH cases post-cleanup — Larkholm (above) rich red gauge + 6 red
  tiles + spectrum/hero red; Thornbridge (below) rich amber gauge + "Below" word + 6 below tiles + "Behind plan"
  pill — render byte-unchanged (dead code carried no behaviour); 0 console errors. Cache v271 -> v272.

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 5 VOCABULARY (alignment language lock), BUILT. VOCABULARY RULING
  (David): POSITION channel (RAG colour + verdict word/chip + counts) = ALWAYS below/on/above market, every
  surface, strategy-INVARIANT (locked). ALIGNMENT channel (the navy AlignmentChip + spectrum bracket) = a parallel
  three-state, strategy-on only: behind / on / ahead OF STRATEGY (behind/ahead aren't position words; the shared
  "on" disambiguates by noun — on market vs on strategy). EDIT 1 (verdict-word revert off _onTarget) already
  shipped 981e7d8 — no-op. EDITS (pages.js, pure render): EDIT 2 — ALIGN_LABEL {on_target:"On strategy",
  behind:"Behind strategy", ahead:"Ahead of strategy"} (one map → gauge :686 / tile :1241 / hero :1562 chips).
  EDIT 3 — targetCopy tooltip "On/Ahead/Behind strategy — you aim to sit [STANCE_WORD]" (the chip's own tooltip,
  was "On your target …" — a mismatch is an internal contradiction). TILE-FIT (David's hard-floor ruling): the
  align-chip-sm font is ALREADY at the 11px type floor, and at 11px the full phrases overflow the tile's own-row
  (102px usable / 134px tile): "Behind strategy" 110px, "Ahead of strategy" 122px (clips) — measured live. Per
  ruling (shrink to 11px floor; if it still doesn't fit, abbreviate the TILE to the state word alone): added
  ALIGN_LABEL_SHORT {on_target:"On", behind:"Behind", ahead:"Ahead"} for compact=true; the full "… strategy"
  phrase stays on gauge/hero (non-compact) + the tooltip (targetCopy) on every chip. NO font sub-11px, NO wrap, NO
  negate-padding. QA (live): Thornbridge (behind) — gauge "Behind strategy" + tooltip full; tiles "Behind"/"On"
  (63/41px, 0 overflow), tile tooltip carries the full phrase. FORCED AHEAD (longest label, temporarily set
  Larkholm org_strategy market_position=match → above-market reads ahead, then REMOVED the QA strategy to restore
  Larkholm to no-strategy): gauge "Ahead of strategy" (full, fits the 322px slot); tile "Ahead" (61px, 0 overflow);
  hero "Ahead of strategy" (full); tooltip "Ahead of strategy — you aim to sit on market" on all. on==off (chips
  strategy-on only, gone off); 0 console errors; parse OK. OUT OF SCOPE (David, stays): signal-row green "On plan"
  pill (s.confirm, :864/:1094 — binary confirm glyph, GREEN channel, different indicator) + the strategy summary
  "On plan:" list (:339) — renaming would import three-state vocab onto a binary green pill and blur green/navy.
  Logged for a future consistency pass, NOT swept in. Cache v273 -> v274. CLOSES the channel separation: colour =
  position (marketTone), word/chip = position (below/on/above market), alignment = navy chip behind/on/ahead-of-
  strategy (strategy-on only) — three elements, two channels, no "amber but On target" contradiction.

2026-06-27 — RAG / STRATEGY SEPARATION — PASS 6 (donut centre = position verdict + hero tighten), BUILT. The gauge
  donut centre showed "92 / metrics" (a COUNT, not a finding) in the page's most prominent spot, while the position
  verdict word ("Below") floated BENEATH the donut — a 2-element word+lean stack (.arc-verdict, 59px) that pushed
  the domain tiles toward/below the fold. Two issues, one fix: pull the verdict INTO the centre, drop the float.
  BUILD (pages.js + app.css, pure render): (1) Donut gains an OPT-IN centerWord prop — the market gauge passes
  centerWord=headWord ("Below") so the centre = the verdict WORD (the donut self-contains: ring=distribution,
  centre=verdict) + a demoted small "92 metrics" line; the PRACTICE gauge does NOT pass it, so its count-centric
  centre is byte-unchanged. (2) "92 metrics" → small .donut-count under the word. (3) .arc-verdict collapses from
  word+lean (2 elements) to the single magnitude caption (.arc-lean = "clearly below the market", clearly/
  moderately/marginally — magnitude preserved per ruling (a)); the redundant floated verdict WORD is removed.
  CHANNEL DISCIPLINE (load-bearing): centre = POSITION verdict only ("Below"), NEVER the alignment state — the
  "Behind strategy" chip stays separate beneath; centre + chip never mix. COLOUR: centre word = NEUTRAL ink
  (var(--ink), the same the floated word used) — the RING carries the RAG colour, so the word isn't re-coloured
  (no doubled cue). .donut-word 24px head-font (sized to fit the longest verdict "On market" — probed 121px in the
  154px centre). QA (live, demo org director@thornbridge): centre "Below" + "92 metrics"; centre word colour
  rgb(33,27,38)=--ink; caption "clearly below the market"; floated .arc-word GONE (no duplicate verdict on the
  page); GUARD — practice donut centre unchanged ("76 practices", no donut-word); on==off — centre word "Below"
  IDENTICAL strategy-on vs off (position → strategy-invariant, like the colour); "On market" probe 121px fits.
  HERO HEIGHT: arc-card 435 -> 402px (-33px); first-tile top 675 -> 642px. TILE-FOLD: at 1320x900 the tile row
  fully clears (845 < 900) — cutoff fixed there; at a 1366x768 laptop the row now STARTS on-screen (top 642 < 768)
  but the bottom (845) is 77px below the fold — down from ~110px — so this is a meaningful STEP-1 tighten, not a
  full clear on short laptops (follow-up: trim the card-head / counts spacing). 0 console errors; parse OK; clean
  screenshot captured. Cache v274 -> v275.

2026-06-27 — RAG / STRATEGY SEPARATION — TILE ALIGNMENT-CHIP READ FIX, BUILT. Pass-5 abbreviated the tile chip to
  the state word alone (On/Behind/Ahead) to fit the 134px tile, but it read MUDDY: "below · On" (verdict chip +
  bare alignment chip) was ambiguous — "on what?" — and "On" looked almost contradictory beside the position
  "below". FIX (David's ruling): give the alignment chip a quiet LABEL mirroring the tile's existing "POSITION"
  label, so the abbreviated state word reads against it. BUILD (pages.js + app.css, pure render): (1) a new
  "STRATEGY" label = <div class="cat-axis num">strategy</div> — REUSES .cat-axis verbatim (9.5px / weight 650 /
  letter-spacing .07em / uppercase / --ink-faint), identical to "POSITION", no new chrome. (2) REORDER: the
  labelled alignment row moves from ABOVE the position bar to BELOW it, so the tile reads verdict-chip → POSITION
  [bar] → STRATEGY [Behind/On/Ahead] — position primary (the fixed fact), alignment secondary (the strategy
  overlay), primary-then-secondary, matching the gauge's vertical order. (3) both the STRATEGY label + the chip
  sit INSIDE the d.target gate → hide together strategy-off (no orphan label). .cat-tile-align margin-top
  calc(-1*--s2) → var(--s2) to mirror .cat-pos (label's negative margin-bottom snugs the chip up). The chip stays
  the abbreviated word; the full "Behind/On/Ahead strategy" stays on the gauge/hero + every tooltip. QA (live):
  ORDER correct (position-label y < bar < strategy-label <= chip); STRATEGY label byte-matches POSITION (9.5px,
  rgb(142,136,147)=--ink-faint, uppercase, .07em); all THREE states read clean under the label — BEHIND + ON
  (Thornbridge, e.g. Time Off="On"), AHEAD (Larkholm forced match→above=ahead, then strategy removed) — 0 tile
  overflow on any; strategy-OFF → 0 STRATEGY labels + 0 chips (degrade contract, no orphan); gauge/hero full
  phrase unchanged ("Behind strategy"/"Ahead of strategy"); tooltips carry the full phrase. 0 console errors;
  parse OK. (Screenshot mini-scaled — a flaky preview quirk — so verified by DOM measurement.) Resolves the
  gauge-vs-tile wording inconsistency: gauge states "On strategy" inline; tile states it via the "STRATEGY: On"
  label. Cache v275 -> v276.

2026-06-27 — DOMAIN PAGE — PASS 1 (§1 two-donut hero + on-page strategy toggle), BUILT. The category-detail §1
  was a chip + MarketSpectrum BAR (position) beside a bespoke prevDonut (practice). Rebuilt to the agreed mock:
  TWO SEPARATE CARDS, each a shared <Donut>. EXTRACTION (David ruling 2): pulled the gauge's verdict-WORD map +
  the ~15-line magnitude IIFE into shared verdictWord(v) + leanCaption(market) helpers (one source, no drift);
  OverallArc now calls them — PROVEN byte-identical (Overview gauge still "Below" / "92 metrics" / "clearly below
  the market"). Removed the now-unused lean/T/mag from OverallArc. CARD A "Market position" = the home
  Donut(centerWord) scoped to the domain: per-band marketTone segments (below=amber/on=green/above=red), centre =
  verdictWord(verdict) ("Below") + demoted pos.pool count, leanCaption(pos) magnitude caption, a below/on/above
  counts line, + the navy AlignmentChip (hero.target, strategy-on only). CARD B "Practice prevalence" = the SAME
  shared Donut re-skinned: its OWN blue palette (--blue-deep / blue mixes — NOT marketTone; practice is not a
  market position), centre = COUNT-HEADLINE (David ruling 1: with_majority big + "of N practices" small — no
  descriptor word; rarity is the signal, the count states the fact), "match the market majority" caption, a
  match/common-alt/rarer counts line, NO alignment chip (practice has no strategy relationship). DROPPED the
  MarketSpectrum invocation (the donut supersedes it; the component is now uninvoked → dead, flagged for a cleanup
  pass). ADDED an interactive strategy toggle at §1 top (reuses the ov-strat switch markup; gated on
  ov.strategy_complete; onClick onPref("_overview", {..._ovp, apply_strategy:!applyStrat}) → derived applyStrat
  recomputes → the existing useEffect refetches with &strategy=off → CARD A's chip appears/hides). CHANNEL
  DISCIPLINE QA (live, demo org, category Pay): CARD A centre = POSITION verdict only; CARD B centre = neutral
  count-headline (no verdict smuggled); A coloured marketTone (amber/green), B coloured BLUE (B_uses_marketTone
  false); alignment chip on A only. on==off: A word + counts byte-identical strategy-on vs off, ONLY the chip is
  the delta (ON present / OFF gone); CARD B fully identical. counts derive-not-literal (16/9/0 below/on/above =
  25 pool; 18/9/8 match/common-alt/rarer = 35 pool — engine values). Spectrum absent; toggle present; 0 console
  errors; parse OK; clean screenshot. The home OVERVIEW renders identical (only the shared Donut + the extracted
  helpers were reused — no Overview change). Cache v276 -> v277. NEXT: Pass 2 (count→chip filterable grid, remove
  the standalone signals list), Pass 3 (net-new AI domain summary).

2026-06-27 — DOMAIN PAGE — PASS 2a (per-card market_band — a DATA-INTEGRITY fix), BUILT. Pass-2's Phase-A QA
  surfaced a latent firewall bug: the domain donut classifies position via the post-firewall config (_market_class
  over the Substance pool), but the benchmark CARD carried no band — the frontend recomputed it from the card's
  LEGACY DB polarity (cardPosition), which disagreed (live, Pay: donut above=0 vs cardPosition above=4 — 4 cost/
  Design rows like 'Workforce cost as % of revenue' that the config calls neutral/excluded read 'above market' on
  legacy polarity). Ruling (David): fix at source, not a Pass-2 workaround. ADDED positions.pool_market_bands(items,
  practice_items, cfg, band_low, band_high, margin) → {qid: band}, built from the SAME substance_pool the gauge
  counts via a shared _metric_bands() helper; threaded market_band into assemble_card (a new kwarg → base dict
  field, null when not positioned); the /api/benchmarks route builds the pool once (build_items + practice_position_
  items, identical args to /api/overview) and stamps each card. GRANULARITY RULING (David, Option A): the donut's
  below/at/above count READINGS (matrix rows = mass — 'verdict reflects mass', the home needle keeps this), but the
  grid is one card per METRIC; summing per-card could never equal the reading-mass donut for matrix domains (Pay 25
  readings / 13 metrics; Benefits 40 / 14). So _metric_bands collapses a MATRIX metric to its OWN _pool_verdict
  verdict (sub-ruling: NOT majority, NOT worst-row — same engine, one level up), giving ONE band per metric; and
  hero.domains[].position_metrics (NEW) carries the metric-level below/at/above the §1 CARD A donut now reads. The
  home needle (hero.market mass _pool_verdict over the whole gauge_pool) is UNTOUCHED — the two surfaces answer
  different questions (home 'where Pay sits overall, reading-mass-weighted'; domain grid 'how many Pay metrics sit
  below market, show me which'). PROOF (live, Thornbridge): per-card market_band sum === position_metrics for ALL 7
  domains (Pay 8/5/0, Benefits 11/2/1, Incentives 6/1/0, Time Off 7/2/0, Wellbeing 3/0/0, Recognition 1/1/0,
  Governance null) — all_match true; home gauge mass byte-identical (76 Below / 15 On market / 1 Above, pool 92,
  'clearly below the market'); the 4 cost/Design rows resolve to null; consumer-safety audit (workflow, 22
  consumers) clears — all named-field reads, strip_internal passes non-_ fields, no market_band name collision.

2026-06-27 — DOMAIN PAGE — PASS 2b (count→chip filterable grid + signals-list retirement), BUILT on 2a. The §1
  CARD A donut REPOINTS to position_metrics (Pay reads 'Below · 13 metrics · 8 below · 5 on · 0 above' — the verdict
  WORD + lean adverb stay mass-level/canonical, only the counts/segments/pool go metric-level; ruled, not a
  regression). The 'All metrics' signal-state <select> → 3 COMPOSABLE neutral position chips (SignalsPage .sig-chip
  pattern, NO marketTone dot — a filter is a control, not a position readout; hide-0 so Pay shows 'below 8 · on
  market 5', no 'above 0'); counts read posM (=== the donut, one source); the filter predicate reads c.market_band
  (engine 'at' → chip 'on'), so count===donut===filtered-grid BY CONSTRUCTION. KEPT the orthogonal type select.
  RETIRED the standalone signals list (+ its orphaned sigEff/sigStOv/onSetSig/sigsShown/inCat triage overlay; kept
  sigMap — the grid still needs it). ADDED a slim '⚑ N flagged →' link-out (.cat-flag-link, NOT a chip) to
  #/signals (unscoped this pass; domain-scoping = a SignalsPage fast-follow). PROOF (live, Pay): click 'below 8' →
  exactly 8 cards; multi-select below+on → 13; 'All' clears; donut+chips metric-level (8/5/0); home gauge
  unchanged; 0 console errors. Cache v277 -> v279. Follow-ups: MarketSpectrum still dead (cleanup); single_benchmark
  carries market_band=null (only the grid consumes it this pass); location_approach=agnostic orgs read metric_bands
  strategy-invariant (donut may shrink under strategy for that rare reframe). NEXT: Pass 3 (net-new AI domain
  summary).

2026-06-28 — DOMAIN PAGE — PASS 3 PROMPT (locked) + 3a (server: payload + generator + validator + floor + table +
  green gate), BUILT. The §2 AI domain summary is the one net-new, philosophy-sensitive piece. PROCESS: mapped the
  per-metric scaffold (Phase A) → David drafted the generation prompt → adversarial pressure-test (a 5-lens
  red-team workflow STALLED on infra, so done directly) surfaced critical/high risks: position-vs-strategy
  vocabulary conflation, derived/worded-ratio numbers, the "considerations" advice leak (contradicting mirror-not-
  consultant), and missing branches for Governance/indicative/no-gaps → David hardened the prompt (vocab lock,
  "8 of 13" counts only, considerations DROPPED, no-position branch, strengths named, calibration kept) → a second
  pressure-test surfaced the seam issues now ruled as D1-D6. RULINGS: part-set = FOUR describe-only slots
  (position / notable[gaps+strengths] / prevalence-or-approach / provenance); peer_pool_size = responding_orgs
  nominal; §2 degrade = ALWAYS show the deterministic floor (never hide); separate AI_DOMAIN_SUMMARY flag (default
  OFF). BUILD (3a, server only — no route, no frontend): claude_api.py DOMAIN_SUMMARY_SYSTEM (the locked prompt) +
  DOMAIN_SUMMARY_SCHEMA (4 slots) + validate_domain_summary (post-gen gate) + _deterministic_domain_summary (the
  always-present floor) + generate_domain_summary (floor-first, ≤2 model attempts each gated, floor on any fail/no
  key) + DOMAIN_SUMMARY_GEN_VERSION; app.py build_domain_summary_payload (same engine the §1 donut uses — Pass 2a
  position_metrics, prevalence, approach, top_gaps/top_strengths, provenance) + AI_DOMAIN_SUMMARY flag; db.py
  domain_summary cache table (PK org+domain+cut_key; cut_key folds strategy on/off). D-RULINGS honoured: D1 gaps/
  strengths carry the favourability-ADJUSTED percentile (round(50+distance,1) — low=gap always, no wrong-direction
  P); D2 the number allowlist is built from DATA fields + the quoted metric NAMES only (never definitions — the
  domain payload carries none), and names use the concise q.short_description with digit-bearing parens + post-'?'
  explainers stripped (kills the "(100%) so 110% would be 10% above market" cruft); D3 alignment in DISPLAY vocab
  ("behind/on/ahead strategy"), present only strategy-on; D4 provenance = {answered_count, peer_pool_size(nominal)};
  D5 prevalence phrasing pinned per bucket; D6 four describe-only slots, no interpretive slot. GATE:
  qa_domain_summary.py mirrors qa_commentary — attacks the live path (7 domains × strategy on/off × cuts) AND the
  validator with 13 hostile outputs (ungrounded/worded numbers, crossed vocab, advice/directive/legal, alarm,
  alignment-without-strategy, market-position-on-Governance, missing provenance). 127/127 PASS (deterministic+
  validator path; LUMI_QA_WITH_MODEL=on to also exercise live generations). Floor reads honestly e.g. Pay: "8 of 13
  positioned metrics sit below market, 5 on market and 0 above market. Against the strategy you have set, this
  domain reads behind strategy." FOLLOW-UP (ruled, logged, NOT this pass): the per-metric _commentary_numbers
  allowlist scans the WHOLE payload JSON incl. definitions — the same D2 hole — to tighten to data-fields-only on
  that shipped surface. NEXT: 3b (route POST /api/domain-summary + §2 frontend block, flag-gated), after sign-off.

2026-06-28 — DOMAIN PAGE — PASS 3b (route + §2 frontend block), BUILT — WIRING ONLY, flag stays OFF. Displays the
  3a product (prompt+validator+floor untouched). ROUTE: POST /api/domain-summary (mirrors /api/metric-commentary) —
  flag-gated (403 if not AI_DOMAIN_SUMMARY); {domain, cut, apply_strategy} → build_domain_summary_payload →
  cut_key = dim::value::(strat|abs) (strategy-on/off cache separately) → sha256(payload+DOMAIN_SUMMARY_GEN_VERSION)
  → domain_summary cache → generate_domain_summary; never errors on model failure (the generator ships the
  validated floor). Exposed "domain_summary": AI_DOMAIN_SUMMARY in the /api/me features map. FRONTEND: a
  DomainSummary component at the 1620 seam (between .cat-hero close and the All-metrics <section>), feature-gated on
  me.features.domain_summary. FLAG CONTRACT (David ruling): flag OFF → §2 absent + not fetched → page byte-identical
  to post-2b (the flag is the launch kill-switch); flag ON → §2 ALWAYS present (the "never hide" rule is about INFRA
  — the floor fills in when the model is down, the block never disappears). Auto-fetches on mount + on
  applyStrat/cut change (lazy, no button — the one deviation from the button-triggered metric commentary, per
  ruling); skeleton → the four describe-only slots (3 labelled: Market position / Notable metrics / Practices +
  the provenance footer); deterministic source → a quiet "A plain-data summary, written from your figures." caveat
  (StrategyCheck source pattern); a quiet honesty marker "AI-generated · a description of your data, not advice"
  (mirrors the metric "review before use" chip — the describe-not-advise framing made visible). NO client
  editorialising — renders the 4 parts as-is, no recommendations UI, no action buttons. PROOF (live): flag OFF →
  §2 absent, route 403, §1+chips+grid+Overview unchanged (v280); flag ON (local, env-injected for the proof only,
  key blanked → deterministic floor) → §2 renders between hero and grid, 4 slots, skeleton→content, caveat +
  honesty marker present; strategy toggle → §2 refetches, the alignment clause ("…this domain reads behind
  strategy") appears strategy-on / absent strategy-off while the §1 donut counts stay 8/5/0 (strategy-invariant);
  0 console errors. Cache v279 -> v280. Committed with the flag OFF; real model prose surfaced separately for
  David's quality read before any flag-on. NEXT: David reads the prose → flag-on is his call.

2026-06-28 — DOMAIN PAGE — PASS 3 VOICE POLISH (4 gated prompt/payload tweaks from David's quality read of the
  real model prose), BUILT — flag STILL OFF, validator UNCHANGED, qa_domain_summary 127/127 after each. The first
  keyed model run read well but surfaced four wrinkles; David ruled each as a gated tweak. (1) INSTRUCTION-ECHO:
  the model narrated its own rule ("position and alignment are described here as separate things") — prompt rule 3
  now says apply the vocab lock SILENTLY, never mention/explain/narrate the separation or any rule (describe the
  effect, never recite the rule). (2) PERCENTILE FALSE-PRECISION: payload now rounds the gap/strength adj_pctl to an
  INTEGER (was 1dp) + prompt phrases "at the Nth percentile (n=X)" — belt+braces so the allowlist and the prose
  agree on the integer. (3) APPROACH NOISE: the "N differ from the market norm" approach register is dropped from
  the payload for competitive domains (build_domain_summary_payload: approach only when NOT has_position) — it's the
  Governance/non-competitive companion (H1), near-redundant beside prevalence on a competitive domain. (4)
  GOVERNANCE OVER-REJECT (investigated first per ruling): the model produced CORRECT no-position prose but conveyed
  it by NEGATING the market words ("no metric sits below market"), which the strict DOMAIN_MKTPOS_RE caught →
  floor shipped. RULING: Option A (prompt) ONLY, validator UNCHANGED (no safety traded). Rule 6 now tells the model
  to state plainly there is no market position and describe prevalence/approach WITHOUT enumerating below/on/above
  market at all — not even to deny it — in EVERY slot (the notable slot simply states there are no gaps or
  strengths). Result: Governance now ships a MODEL voice (was deterministic floor), reading naturally. GEN_VERSION
  bumped v1 -> v2-voice so the domain_summary route cache self-invalidates. RESIDUAL (logged, not blocking; David
  approved the voice): the model still occasionally (~1/3) slips a HYPHENATED enumeration ("above-market standing")
  past the space-based guard — harmless/contrastive, and the floor stays the net; a hyphen-aware validator tweak is
  a possible future item (would need a ruling, since validator-stays-strict was the #4 decision). NEXT: flag-on is
  David's call.

2026-06-28 — DOMAIN PAGE — COUNTS RECONCILIATION (the Pay page showed four unreconciled totals — 60 benchmarks /
  60 shown / 13 position-donut / 35 prevalence-donut). PHASE A diagnosis: the four are CORRECT but overlapping —
  60 = 13 positioned + 35 prevalence − 6 (in BOTH donuts) + 18 (in neither: Design/multi_select, neutral numerics,
  unanswered, non-rate practices); "60 benchmarks" === "60 shown" (same all.length); the donuts are subset LENSES,
  not a partition. Two real faults surfaced + ruled. (1) §2 PROVENANCE BUG (gated flag-on): the summary said
  "across your 13 answered Pay benchmarks, compared with a peer pool of 220" — 13 was position_metrics.pool
  (positioned, mislabelled "answered", colliding with the header's 60) and 220 was the whole-pool nominal (not the
  cut's 15). FIXED in build_domain_summary_payload: answered_count = the ACTUAL count of answered domain questions
  (any answer key per qid — matrices with partial rows count; = 60 for the fully-populated demo, matching the
  header exactly; David's "~58" estimate was a Phase-A artifact of checking the (qid,"") key, wrong for matrices);
  peer_pool_size = the CUT's peer count via new _cut_peer_n() (mirrors the client cutSize + board-pack cut_n:
  industry→industries[value]=15, fte_band→fte_bands, twin/group→member count, all→responding_orgs). This REVERSES
  the D4 ruling (was responding_orgs nominal) — the cut peer-n is correct AND matches the header. (2) SMALL SAMPLE
  (gated flag-on): the <20 "directional" caveat lived ONLY on the overview hero. Added a thin-cut caveat to the
  DOMAIN page (CategoryPage: thinSample = insights_unlocked && 5<=cutSize<20 → "Small sample · N peers · treat as
  directional", reusing .indic-flag); and the §2 summary now carries a small_sample payload flag → prompt rule 10 +
  the deterministic floor append "— a small peer group, so read this as directional" when the cut is thin. (3)
  DONUT/HEADER LEGIBILITY (correct-but-unlabelled) — LOWER priority, does NOT gate flag-on, deferred. PROOF (live,
  Pay @ Retail & Consumer Goods, n=15): header "60 benchmarks · Retail & Consumer Goods"; thin caveat "Small
  sample · 15 peers" present; §2 (flag-on, deterministic) provenance "Across your 60 Pay benchmarks, compared with
  15 peers — a small peer group, so read this as directional"; qa_domain_summary 127/127; 0 console errors.
  GEN_VERSION v2-voice -> v3-provenance; cache v280 -> v281. Flag still OFF. NEXT: #3 donut/header subset-lens
  labelling (a follow-up, non-gating).

2026-06-28 — DOMAIN PAGE — COUNTS RECONCILIATION #3 (donut/header legibility — LABELLING ONLY), BUILT. The two §1
  donuts (13 metrics / 35 practices) read as totals that should sum to the header's 60, but they're overlapping
  SUBSET-LENSES of the 60 (6 overlap, 18 in neither). Minimal fix (David ruling): append a quiet "· N of 60" anchor
  to each cat-hero-label so each donut reads as a lens on the 60, not a partition — CARD A "Market position · 13 of
  60", CARD B "Practice prevalence · 35 of 60". The "60" reads all.length (the STABLE parent — same source as the
  header's "60 benchmarks", NOT cards.length which shrinks under grid filters); posM.pool/prev.pool supply the
  13/35 (same scope, derive-not-literal). The header's "60 benchmarks" right above supplies the noun, so the bare
  "· N of 60" reads back as "13 of my 60 benchmarks carry a market position" — no repeated "benchmarks". Quiet
  styling (.cat-lens-of: weight 400 vs the label's 700, text-transform none, opacity .8) so the lens NAME reads
  first, the anchor subordinate. LABELLING ONLY — no count/donut-math/payload change; centres ("Below / 13 metrics",
  "18 / of 35 practices"), counts lines, chips, §2, grid all UNCHANGED; the overlap (6) and residual (18) are NOT
  spelled out (set-theory the member doesn't need — "of 60" alone kills the false-partition read). PROOF (live,
  Pay): labels "Market position · 13 of 60" / "Practice prevalence · 35 of 60"; applied the "below" chip → grid
  filtered 60→8 while the labels STAYED "· 13 of 60" / "· 35 of 60" (anchor reads all.length, not the shrinking
  cards.length); centres/counts/chips unchanged; 0 console errors. Cache v281 -> v282. The whole counts-
  reconciliation set (#1 provenance, #2 small-sample, #3 labelling) is done; flag-on remains David's call.

2026-06-28 — DOMAIN PAGE — PREVALENCE FILTERING PASS A (per-card prevalence_band, engine), BUILT. The §1 has two
  parallel donuts but only POSITION drove the grid filter (2a/2b market_band); prevalence (match/common-alt/rarer)
  was display-only — a member seeing "6 rarer" couldn't filter to them. Phase A confirmed the card carried only
  market_band → prevalence_band is net-new (the 2a mirror). ADDED positions.pool_prevalence_bands(prev_items,
  uncommon_pct) → {qid: 'match'|'common_alt'|'rarer'} from the SAME prevalence_items pool + the SAME bucketing
  _prev_summary counts (is_modal → match/with_majority; off-mode & your_share<uncommon_pct → rarer/less_common;
  else → common_alt/established). assemble_card gains a prevalence_band kwarg → base field; the /api/benchmarks
  route builds prevalence_items once (same cut/args as /api/overview) and stamps every card. CLEANER than 2a:
  prevalence_items is one-item-per-question (single_select/yes_no only, no matrix rows / per-option items), so
  summing per-card === the donut exactly — no metric-vs-mass or matrix-collapse. PROOF (live, Thornbridge, all
  cuts): per-card prevalence_band sum === hero.prevalence {with_majority, established, less_common} for ALL 7
  domains (all_match true; Pay 18/9/8, Benefits 13/4/6, Governance 15/13/4, …); field on 244 cards. Committed
  alone (server only — no frontend). NEXT: Pass B (the prevalence chips — mutually-exclusive with the position
  group, two labelled groups + divider).

2026-06-28 — DOMAIN PAGE — PREVALENCE FILTERING PASS B (the prevalence chips), BUILT on A. The grid filter now
  carries BOTH §1 dimensions. ADDED prevSel state + cardPrevBand (= c.prevalence_band) + the AND-ed null-safe
  predicate. ⭐ MUTUALLY-EXCLUSIVE GROUPS (David ruling): position and prevalence are near-disjoint (only 6 of
  Pay's cards are both), so cross-dimension AND mostly empties the grid (a trap) — so selecting a prevalence chip
  CLEARS the position selection and vice-versa (the two are ALTERNATIVE lenses, not composable refinements);
  WITHIN a group chips still compose (below+on); ONE shared "All" clears both. Restructured the control row into a
  second filter row below the head (.cat-filter-row): a shared "All" + a labelled POSITION group + a vertical
  divider + a labelled PRACTICES group (.cat-filter-axis labels reusing the home-tile pattern) + the orthogonal
  type select (pushed right) — two labelled dimensions, not six undifferentiated chips. Prevalence chips: match /
  common alt / rarer, counts from prev.with_majority/established/less_common (=== the §1 donut, one source);
  hide-0. PROOF (live, Pay): chips "match 18 · common alt 9 · rarer 8" === the prevalence donut; click "rarer 8" →
  exactly 8 cards; click "below" → prevalence cleared (mutual exclusion), grid 8; click "on market" → composes
  within position (grid 13); click "match" → position cleared, grid 18; shared "All" → grid 60; the row reads as
  two labelled groups (POSITION | PRACTICES) + type; 0 console errors. Cache v282 -> v283. Both passes shipped.

2026-06-28 — DOMAIN PAGE — FILTERS-UNDER-THEIR-DONUT restructure + card padding fix (render-placement + CSS only,
  NO logic/band/payload change), BUILT. (1) PADDING: .card has no padding and .cat-pos-card added none, so the
  donut card content was flush to the edge (the label, align-self:flex-start, sat hard in the top-left corner).
  Added padding:var(--s4) to .cat-pos-card (both cards, symmetric) — label + donut + footer now inset. (2)
  RELOCATE CHIPS: the combined two-group filter strip split — the 3 POSITION chips (below/on/above) moved INTO
  CARD A's footer under the position donut, the 3 PREVALENCE chips (match/common-alt/rarer) into CARD B's footer
  under the prevalence donut (.cat-card-chips: a quiet border-top footer, centred). Each donut is now a self-
  contained filterable unit. DROPPED the .cat-filter-axis "Position"/"Practices" labels — the donut title above
  each card already names the dimension (also kills the donut-title-vs-filter-label naming mismatch). The shared
  "All"/clear → relocated to the grid header (.cat-sec-head) as a quiet "Clear filter" (shown only when a chip is
  active; resets both posSel + prevSel); the orthogonal type select stays at the grid header (grid-level). The old
  .cat-filter-row + its CSS (cat-filter-row/axis/div/type-sel) removed. CHIP LOGIC UNCHANGED — same state
  (posSel/prevSel, CategoryPage scope), same mutual-exclusion handlers (position chip clears prevalence + vice-
  versa), same cardBand/cardPrevBand predicate, same counts (=== each donut), same hide-0 — only the JSX placement
  moved. PROOF (live, Pay): both cards padded (label inset, content not flush); position chips under the position
  donut, prevalence chips under the prevalence donut, no filter-axis labels; click "rarer 8" (now under the
  prevalence donut) → exactly 8 cards; "below" clears prevalence (mutual excl); below+on composes → 13; grid-header
  "Clear filter" → both reset → 60; the type select at the grid header filters grid-level (practice → 27); donut
  centres/counts/verdict + §2 unchanged; 0 console errors. Cache v283 -> v284.

2026-06-28 — DOMAIN PAGE — design crit pass (5 items from David's screenshot review) + AI SUMMARY GO-LIVE, BUILT.
  (1) FILTER FOOTERS SAME ROW (ruling: align under each donut, not recombine): .cat-card-chips now margin-top:auto
  — pins each card's chip footer to the card BOTTOM, so the two cards' chip rows align on the same level (grid
  stretches the cards equal-height). Verified side-by-side: both footers top=627, card heights 444=444. (2) DONUT
  TITLES MORE PROMINENT: .cat-hero-label bumped fs-caption→fs-body, weight 700→800, colour ink-faint→ink (15px
  dark). (3) PILLS OBVIOUSLY FILTERS: a quiet "FILTER" cue (sliders icon + label, .cat-filter-cue) prepended to
  each card footer — signals the pills are interactive controls, not static stats; the dimension is still named by
  the donut title above (no re-added axis label). (4) SIGNALS NOT OBVIOUS: the "flagged →" pointer promoted from a
  faint inline link to a prominent blue-tint pill BADGE (.cat-flag-link: blue-tint bg + border + 999px radius).
  (5) AI SUMMARY GO-LIVE (David ruling: "Turn it on"): flipped AI_DOMAIN_SUMMARY default off→on — the §2 domain
  summary now ships to ALL orgs (qa_domain_summary green + the voice signed off; LUMI_AI_DOMAIN_SUMMARY=off still
  cuts it without a deploy). PROOF (live, Pay, desktop 1280): footers aligned; titles 15px dark; "FILTER" cue in
  both footers; signals a blue badge; §2 renders MODEL output ("Across the 13 positioned Pay metrics, 8 sit below
  market and 5 sit on market… reads as behind strategy"); 0 console errors. Render/CSS + one-flag-flip only — no
  donut math / band / payload change. Cache v284 -> v285.

2026-06-28 — DOMAIN PAGE — AI-summary go-live REVERTED (compliance). Item (5) of the crit pass (88adb36) flipped
  AI_DOMAIN_SUMMARY default off→on, treating "an AI summary would be good" as launch authorization. That was WRONG:
  the comment affirmed the FEATURE (already built + rendering behind the flag), not a LAUNCH to all members. The
  flag-on decision is RESERVED for David and gated on the compliance track (DPA / privacy notice / sub-processor
  review — it ships AI-generated, member-facing content derived from member data). Reverted the default back to OFF
  (one line). The five UI changes from 88adb36 STAY (correct). The §2 summary remains demo/env-var only
  (LUMI_AI_DOMAIN_SUMMARY=on) until David explicitly authorizes go-live. PROCESS NOTE: a member-facing AI launch is
  an outward-facing, hard-to-reverse action — confirm explicitly, never infer authorization from feature praise.

2026-06-28 — AI INSIGHTS — CONSENT INFRASTRUCTURE (Option A, master gate), BUILT — MASTER LEFT OFF.
  Built the consent/authority plumbing for ALL SIX AI features (commentary, analyst, board pack, pulse, strategy
  diagnosis, domain summary) and wired every one to it, WITH THE MASTER SWITCH LEFT OFF for solicitor review before
  real go-live. This closes the compliance gap behind the reverted go-live above: member-facing AI content from
  member data must not render in production until David flips the master switch himself, post-sign-off.
  GATE (the safety property): any AI feature renders IFF `AI_INSIGHTS_ENABLED` (master, default OFF) AND that
  feature's own flag is on AND the member has consented (per AI_CONSENT_MODE). So flag-on != all-members-see-AI, and
  the five currently-default-on features go DARK in production the moment this lands, staying dark until the master
  is flipped. Implemented by making /api/me features EFFECTIVE (ai_feature_on(gate, flag)) so every existing client
  gate (me.features.X) auto-respects the master + consent with ZERO change to existing feature-gating code; the six
  AI routes call require_ai(conn, user, flag) (403 unless master+flag+consent).
  CONFIG (no hardcoding): LUMI_AI_INSIGHTS_ENABLED (default "off"); LUMI_AI_CONSENT_MODE ("opt_in" default |
  "opt_out" — the solicitor rules the lawful basis); AI_TERMS_VERSION "1.0-draft". The five existing per-feature
  flag defaults LEFT UNTOUCHED (still on); AI_DOMAIN_SUMMARY stays default OFF.
  CONSENT RECORD: mirrors terms_acceptances (append-only Article-30 audit log) — kind="ai_insights" (grant) /
  "ai_insights_withdrawn" (withdrawal), per-user, versioned to AI_TERMS_VERSION; current state derived from the
  latest event (opt_in: active iff granted; opt_out: active unless withdrawn). No new table. Helpers: record_ai_
  consent / record_ai_withdrawal / ai_consent_state / is_ai_consented / ai_gate / ai_feature_on / require_ai.
  SIGNUP GATE: an unbundled, unticked-by-default "Optional — I consent to lumi generating AI Insights… DRAFT"
  acknowledgment, SEPARATE from the platform T&C, on both the register form and the accept-invite form (auth.js);
  captured via accept_ai_insights → record_ai_consent (opt_in).
  SETTINGS: an "AI Insights" card (commercial.js SettingsPage) — status line + a toggle that POSTs /api/ai-consent
  (grant/withdraw → refreshMe); withdrawal closes the gate next request. Draft-terms link.
  EXISTING-MEMBER RE-CONSENT: a never-decided member (opt_in, no record → needs_decision) is shown a consent prompt
  where §2 would render (pages.js CategoryPage: "AI Insights can summarise this domain… Review & enable →" → #/settings),
  not the AI itself. Withdrawn members (have a record) get no prompt.
  PLACEHOLDER LEGAL: legal/ai-insights-terms-v1.0-draft.md, registered in LEGAL_FILES + LEGAL_INDEX with draft:true
  (mirrors the existing -draft.md / draft:true pattern), clearly marked "DRAFT — NOT LEGALLY VERIFIED · pending
  solicitor review". GO_LIVE_CHECKLIST.md documents David's post-solicitor switch-on order (replace placeholder
  legal text, confirm lawful basis/set AI_CONSENT_MODE, bump AI_TERMS_VERSION, confirm DPA/Article 30, flip
  LUMI_AI_INSIGHTS_ENABLED=on, re-run adversarial gates) + the kill switches.
  PROOF (live, master ON via env-var on the preview instance only): master OFF (default) → features all false +
  routes 403 + ai_insights{master:false,needs_decision:true,active:false}; grant→consented:true / withdraw→event
  "ai_insights_withdrawn" / regrant→consented:true; master ON + consented → features ALL true + domain route 200 +
  active:true; master ON + withdrawn → features ALL false + route 403; consented org → §2 present, no prompt;
  never-decided org → consent prompt present (Review&enable→#/settings), §2 absent; Settings AI card renders the
  toggle; 0 console errors. COMMITTING WITH THE MASTER OFF — the switch-on is David's, post-review. Cache v285 -> v286.

2026-06-28 — AI INSIGHTS — GO-LIVE PREP on solicitor sign-off (opt-out / legitimate interest), BUILT —
  MASTER STILL OFF (the prod env flip is reserved for David). David confirmed solicitor approval with four
  rulings: (1) lawful basis = LEGITIMATE INTEREST / opt-out, LIA on file; (2) approve the current draft legal
  wording as-is (fill the placeholders, drop the draft banners); (3) prepare everything but leave the production
  master flip to David; (4) name Anthropic as the AI sub-processor, its terms verified.
  CONSENT MODE → opt_out. AI_CONSENT_MODE default flipped opt_in→opt_out: AI Insights are ON by default and a
  member turns them off in Settings (records kind="ai_insights_withdrawn"); a never-decided member is active.
  is_ai_consented / ai_gate / needs_decision already supported BOTH bases — only the default changed. Under
  opt_out needs_decision is always False, so the opt_in domain-page "Review & enable" nudge goes dormant (right).
  SIGNUP → DISCLOSURE, NOT A TICK. A default-unticked opt-in checkbox is the wrong pattern under legitimate
  interest; both signup forms (register + accept-invite, auth.js) now show an informational NOTICE ("lumi
  generates AI Insights … on by default; you can turn them off any time in Settings") with a terms link — no
  checkbox, no accept_ai_insights field. The Settings card is reworded to opt-out ("on by default … turn them
  off here"; button "Turn off AI Insights"); all DRAFT markers removed.
  TERMS VERSION → 1.0 (AI_TERMS_VERSION "1.0-draft" → "1.0").
  LEGAL FINALISED. legal/ai-insights-terms-v1.0.md (renamed from -draft; LEGAL_FILES + LEGAL_INDEX draft:false):
  banners removed, Anthropic PBC named, lawful basis = legitimate interest (Art 6(1)(f) + LIA), Art 22 n/a,
  opt-out control, "only aggregated/derived figures — no individual salaries". The Anthropic row was added to the
  Sub-processor List (aggregated/derived only; no training on inputs; zero/limited retention; DPA + SCCs/UK
  Addendum) and an AI-assisted-analysis section to the Privacy Notice. Those two pages REMAIN draft:true for
  NON-AI residuals only (privacy contact address; hosting/email sub-processors) — David's to finalise; the
  authoritative AI disclosure is the final AI Insights Terms that every AI surface links to.
  MASTER STAYS OFF IN CODE. AI_INSIGHTS_ENABLED default remains "off" as the backstop; go-live is the single
  prod env action LUMI_AI_INSIGHTS_ENABLED=on, reserved for David. GO_LIVE_CHECKLIST.md rewritten: steps 1-4
  done, only the prod flip + DPA/Article-30 confirm remain.
  VERIFICATION. Adversarial gates green (qa_domain_summary 127/127, qa_commentary 40/40). Live (master on via
  env on the preview ONLY, opt_out): never-decided member → consented/active, all features true, domain route
  200, §2 renders, NO consent prompt; withdrawn → 403, §2 absent; re-enable works; Settings shows "Turn off AI
  Insights" + v1.0, no draft; register form shows the AI NOTICE (not a tick), only the platform-terms checkbox;
  legal page final (no DRAFT, names Anthropic, legitimate interest); 0 console errors. A 4-lens adversarial
  workflow swept for leftover draft text, opt_in residue, legal-claim↔payload accuracy and cross-doc consistency:
  NO high findings; the load-bearing "no individual salaries" claim VERIFIED true across all 8 AI call sites
  (strip_internal drops _-prefixed peer values; no individual-pay field exists in the schema); the only flags were
  the now-fixed stale checklist and the accepted non-AI draft residuals. Cache v286 -> v287. Committing master OFF.

2026-06-28 — AI INSIGHTS — POST-SOLICITOR PRE-FLIP STEPS (C3 cache-purge + Article-30 attestation +
  load-bearing-claim checkpoint), BUILT — MASTER STILL OFF. Conditional solicitor sign-off (legitimate
  interest, LIA formalised, wording approved); four prerequisites land BEFORE David's prod env flip.
  C3 — OPT-OUT CACHE PURGE. When a member turns AI Insights off (POST /api/ai-consent consent=false →
  ai_insights_withdrawn), the org's cached AI-generated summaries are now DELETED, not merely gated:
  purge_ai_cache(conn, org_id) (app.py) deletes the org's rows from domain_summary + metric_commentary.
  Pipeline bypass on subsequent cycles already held (require_ai → 403; AI is generated strictly on-demand
  at the two routes — NO background/batch regeneration exists). Board packs are member-INITIATED saved
  exports (created_by) handled under normal erasure/retention, NOT this auto-purge — stated, not overclaimed.
  PROOF (live, master on via env, opt_out): Larkholm cached 4 domain_summary rows → opt out → route 403 +
  Larkholm domain_summary/metric_commentary rows = 0, while a SECOND org's 3 rows stayed untouched (per-org
  scoping correct).
  ARTICLE 30 / LIA ATTESTATION. compliance/ai-insights-data-minimisation-attestation.md — a send-ready,
  regulator-readable exhibit David can email the solicitor to append to the RoPA + LIA. States, each with a
  code reference: what IS sent to Anthropic (domain position counts, named metrics + percentile + sample
  size, prevalence, peer-group size, the org's own org-level submitted figure, org firmographics); what is
  NOT (no individual salaries / base pay — backed TWO ways: (i) the answers schema (db.py:92-100) has NO
  individual-pay field at all, and (ii) strip_internal (app.py:495-501) removes raw _-prefixed peer values
  at block assembly (619/636/664), upstream of every payload builder); coverage (all 6 AI features, one API
  egress at claude_api.py:59, sweep traced 8 entry points); verification (adversarial sweep 2026-06-28, 0
  high, payload-accuracy clean); and an explicit scope/limits + signature line. Reflects payload commit
  d6b0401 (unchanged by the C3 cache change, which doesn't alter what's sent).
  ⭐ LOAD-BEARING-CLAIM CHECKPOINT. The Privacy Notice + AI Insights Terms representation "individual
  salaries and base-pay levels are not used" is LOAD-BEARING on the AI payload staying minimal. Any future
  change to what is sent to the AI provider — a new field in ANY AI payload, a new AI feature/surface, or a
  change to strip_internal or the answers schema — MUST re-run the payload-accuracy verification and re-issue
  the attestation BEFORE shipping. Treat "does this change the AI payload?" as a hard release checkpoint on
  the AI surfaces (commentary, analyst, board pack, pulse, strategy, domain summary).
  C4 (non-AI placeholders) handled separately; master default stays OFF — the prod flip is David's.

2026-06-29 — PRACTICE PREVALENCE -> PRACTICE ALIGNMENT (Pass 1 of 4: central map + AI floor/prompt +
  validator guard + QA harness), BUILT (server-side only; frontend labels are Pass 3). Created the
  central single-source map server/practice_axis.py: PRACTICE_AXIS (title "Practice Alignment"; states
  with_majority->common / established->alternative / less_common->rare), prevalence_verdict() (variant
  verdict line — was a FIXED string "match the market majority"; now largest-bucket-driven from the
  _prev_summary counts, tie resolves common>alternative>rare), bucket_phrase() (singular/plural grammar —
  a bucket count of exactly 1 DOES occur in real data, so "1 is a common choice"/"1 follows an alternative
  pattern"/"1 is rare" handled), and with_display() (spreads the frozen keys, adds title/states/verdict).
  API: the /api/overview handler attaches title/states/verdict ALONGSIDE the frozen keys on each domain's
  prevalence object (NOT app.py:3885 — that is the model-only payload the browser never sees; placing the
  verdict there would feed the model "most…" and risk an echo). The verdict string is FRONTEND-EXCLUSIVE —
  asserted to appear in NO model payload and NO floor string (qa SECTION 4), because prompt rule 1 bans
  "most" in model output.
  AI deterministic floor (claude_api.py): the prevalence sentence migrated to new vocab via bucket_phrase
  (counts read from the FROZEN AI-payload keys match_market_majority/established_alternative/less_common —
  byte-for-byte); the non-competitive POSITION sentence "practice prevalence"->"practice alignment"
  (claude_api.py:726-727 — mandatory: the new blocklist would otherwise reject the floor itself and break
  the no-loop guarantee). Prompt: rule-4 vocabulary swapped to common/alternative/rare + an explicit note
  that the legacy field names match_market_majority/established_alternative/less_common must be described in
  the new vocabulary and NEVER echoed as phrases (the model SEES those field names); the no-position example
  (rule 6) "practice prevalence"->"practice alignment"; the old forbidden-word "rare" removed (it is now
  canonical). :578 left untouched (already neutral). Runtime guard: DOMAIN_LEGACY_RE rejects the WHOLE
  legacy phrases — match the market majority | established alternative (Addition 1) | practice prevalence |
  common alt | rarer — and falls to the (new-vocab) floor. Deliberately NOT blocked: bare "less common"
  (innocent prose) and bare "prevalence" at runtime (prompt :578 still says "prevalence buckets", so a
  runtime block would over-fall to the floor); bare "prevalence" is instead guarded in the LIVE-QA grep.
  TWO INTERNAL KEY SETS FROZEN, byte-for-byte: engine keys (with_majority/established/less_common/pool,
  positions._prev_summary — positions.py untouched) and the AI-payload contract keys
  (match_market_majority/established_alternative/less_common/pool — app.py:3885 + claude_api floor .get()s).
  No pre-existing floor bug (writer/reader key-match verified 2026-06-29). qa_domain_summary.py SECTION C
  hand-written sample migrated off "match the market majority" (the new guard would have failed it).
  QA: server/qa_prevalence_rename.py — floor-only here (70/70 PASS): map unit logic, new floor across all
  domains x strat (valid + new-vocab + no legacy), validator rejects each legacy phrase, verdict
  frontend-exclusive, singular count=1 grammatical + valid. Live-sampling section self-skips without a key
  (run LUMI_QA_WITH_MODEL=on in a keyed env — greps generations for the forbidden phrases incl. bare
  "prevalence"). Existing gates stay green: qa_domain_summary 127/127, qa_commentary 40/40. Live /api/overview
  verified end-to-end: frozen keys intact + display fields present + §2 floor new-vocab. ALL SANDBOX CHECKS
  FLOOR-ONLY; live model-phrase QA deferred to the keyed harness (Addition: stress-tested vocab vs real
  metrics 2026-06-29).

2026-06-29 — PRACTICE ALIGNMENT (Pass 2 of 4: frontend migration), BUILT. Pointed every user-facing
  pages.js practice-axis site at the API-supplied display fields Pass 1 attached to hero.prevalence
  (prev.title / prev.states / prev.verdict) — words stay SINGLE-SOURCED in server/practice_axis.py, never
  re-hardcoded on the frontend. Seven sites: 1681 card title -> prev.title (CSS uppercases to "PRACTICE
  ALIGNMENT"); 1684 verdict cap -> prev.verdict (was a FIXED "match the market majority"; now variant-driven);
  1686 count row words -> prev.states (counts still prev.with_majority/established/less_common); 1688 aria ->
  prev.title.toLowerCase(); 1690 chip LABELS -> prev.states (chip KEYS match/common_alt/rarer UNCHANGED —
  filtering intact); 1678 fallback caption -> prev.title.toLowerCase(); 1268 overview tile -> prev.states
  .with_majority + prev.verdict tooltip. OPTION A (the only backend touch): practice_axis.with_display is now
  None-safe + the /api/overview handler calls it UNCONDITIONALLY, so every domain's prevalence carries
  title+states even with no practice questions (verdict null then) — no frontend fallback string needed
  (uniqueness invariant preserved). Model payload (build_domain_summary_payload @3885) unaffected — verified
  it carries ONLY the frozen AI-payload keys, no title/states/verdict (verdict must never reach the model;
  prompt rule 1 bans "most"). Null-verdict safety: 1684 cap is inside the prev.pool conditional (verdict is a
  real sentence whenever pool>0); 1268 tooltip is prev.verdict || "". Chip/engine keys and pages.js:740
  (Governance approach axis "in line with the market") and match_count (2354) untouched. Cache v287 -> v288.
  QA (deterministic, Thornbridge Retail Group plc): title "PRACTICE ALIGNMENT · 35 of 60"; count row "18
  common / 9 alternative / 8 rare"; chips common/alternative/rare with filtering still working (alternative
  chip -> "9 shown", key common_alt intact); VERDICT VARIANTS all three render from the API (common-led Pay:
  "most of your practices are common choices"; alternative-led Incentives real data: "many of your practices
  follow an alternative pattern"; rare-led injected: "several of your practices are rare choices" — proves the
  cap renders whatever the API sends, not a hardcoded common); overview clean (no "in line with the market
  majority", no "prevalence"); no-pool domain injected -> title renders cleanly, cap absent (no "null"),
  tooltip empty-safe; DOM grep on emitted Pay page for prevalence|market majority|common alt|rarer = ZERO,
  new vocab common/alternative/rare present; 0 console errors. NOT committed — Passes 1-3 commit together.

2026-06-29 — PRACTICE ALIGNMENT (Pass 3 of 4: Signals tag alignment + dead code), BUILT. PART A:
  the Signals gap-tags now read in the Practice Alignment register, neutral fact-not-judgment:
  "MOST DO THIS" -> "COMMON — YOU DON'T" (a common thing you LACK — peers do it, you don't; the gap),
  "FEW OFFER THIS" -> "A RARE CHOICE" (a rare thing you HAVE — worth=False, a difference, never a
  deficiency). Applied at every site (replace_all, byte-identical producer + comparator): signals.py
  engine display (552/722/806/854/895 + 718/749), the _signal_position LOCKSTEP comparators (275/277 —
  the tag string is both display AND a position key; both swapped together, BEHAVIOUR BYTE-IDENTICAL —
  proved: COMMON — YOU DON'T → below for Level/Provision else differs; A RARE CHOICE → differs, matching
  the old MOST DO THIS / FEW OFFER THIS mapping exactly), both SIG_KIND fallback maps (card.js:354 +
  pages.js:865, fallback-only behind sig.tag), and the hardcoded sample signal (pages.js:972). Signal-kind
  internal keys (prevalence/rare) FROZEN — display only. Uniqueness verified: nothing compares loosely
  against "RARE"/"COMMON" (only the lowercase kind key "rare", a different variable). PART B (prevDonut
  delete): HELD — a reference was found at apply time in server/qa_hero.py (lines 255-258 inspect
  prevDonut's source), so per the rule "if any reference is found, leave it and flag", prevDonut was
  RESTORED and left in place (dead but referenced by the gate). qa_hero.py:259-260 was a STALE assertion
  for the OLD tile caption (`title="practices in line with the market majority"`) that Pass 2 replaced with
  `title=${prev.verdict}`; updated it to assert the new neutral caption (same intent — test maintenance
  tracking the approved Pass-2 change, like qa_domain_summary.py:153 in Pass 1). ENGINE UNCHANGED:
  prevalence_floor / prevalence_lenses / multi_prevalence / practice_status / _prev_summary keys /
  STATUS_POINTS byte-identical (signals.py diff is tag literals only; positions.py / aggregate.py / the
  JSON configs untouched). QA (all FLOOR-ONLY / deterministic): _signal_position byte-identical proof;
  gates green — qa_signals_system 9/9, qa_ordered_routing 17/17, qa_release 0-fail, qa_status_audit, qa_hero
  59/59, qa_commentary 40/40, qa_domain_summary 127/127, qa_prevalence_rename 70/70; live cross-surface
  (Thornbridge) — engine emits tag "COMMON — YOU DON'T" for the prevalence signal "Salary range in job
  adverts" (stand "58% of the market does this, you don't"), and the Pay page shows the alignment card
  ("PRACTICE ALIGNMENT", "18 common / 9 alternative / 8 rare") AND the flagged practice ("COMMON — YOU
  DON'T") in one view — ONE vocabulary; DOM grep on the emitted page for prevalence|market majority|common
  alt|rarer|MOST DO THIS|FEW OFFER THIS = ZERO; 0 console errors. Cache v288 -> v289. The live-MODEL phrase
  sweep (qa_prevalence_rename §LIVE) still self-skips without a key — the one outstanding keyed-env
  confirmation. Rename now consistent across card + overview + AI summary + Signals (one vocabulary), with
  prevDonut dead-code cleanup the only deferred item (Pass 3 Part B held pending the qa_hero.py reference).

2026-06-29 — PRACTICE ALIGNMENT (Pass 3 FINALISED). prevDonut delete un-held: the only reference was
  the stale qa_hero.py:254-258 source-inspection of the dead function (a gate testing dead UI, not a
  live dependency). Deleted prevDonut (pages.js, the ~37-line function + comment) AND removed those two
  prevDonut checks from qa_hero.py. The repointed qa_hero.py tile-caption assertion KEEPS TEETH:
  `'class="caption num" title=${prev.verdict' in js` — fails if the overview tile prevalence line is ever
  rewritten to a performance/RAG-coloured class (it pins the neutral .caption num + verdict tooltip), so
  it still tests neutrality, not an always-pass. Repo-wide grep (web/js + server/): ZERO prevDonut
  references. qa_hero 59 -> 57 checks (dropped exactly the 2 prevDonut checks), 57/57 pass; full gate green
  (qa_release, qa_status_audit, qa_commentary, qa_domain_summary, qa_prevalence_rename 70/70,
  qa_signals_system 9/9, qa_ordered_routing 17/17). Cache v289 -> v290. Passes 1-3 committed together as one
  "Practice Alignment rename" unit. Outstanding (non-blocking): live-MODEL phrase sweep (keyed env) + a
  30-second on-sight check that a Signals tag renders as ONE badge across the em-dash.

2026-06-29 — REW_PAY_MKT_POS_01 RETIRED (soft-delete, status='retired' in DB + CSV, NOT hard delete).
  Base-salary positioning ("where does base salary sit versus market median by level", a self-reported
  % of market median) in tension with the structure/policy-not-base-pay promise — David's positioning-
  scope ruling. No £ figure was ever collected (privacy intact); this is scope, not a privacy fix.
  MECHANISM: single source of truth = questions.status, the gate visible_questions() reads (app.py:290);
  set 'retired' via releases.retire_question() (DB) + a byte-surgical one-field edit to the CSV seed
  (data/lumi_questions.csv, durability across re-seed) by the guarded server/retire_metric.py (dry-run
  default, --write to apply). NO skip-list, NO engine-logic change — the metric drops by DATA/status, and
  git diff is the new script + the CSV one field only (no app.py/positions.py/signals.py/claude_api.py).
  ANSWERS PRESERVED: answer rows for REW_PAY_MKT_POS_01 = 1023 before AND after (answers_history 1
  unchanged); the questions row stays (FK answers.question_id REFERENCES questions(id) intact) — no
  delete, no orphan. Reversible: verified active↔retired round-trip restores it (60/visible) and re-
  retires (59/hidden) with answers intact; left in 'retired' (DB + CSV agree).
  COUNTS recompute from source (no hardcoded literals): Pay 60 -> 59 (the 7-employee-level MATRIX counted
  as 1 benchmark, NOT 7 — only its "Head of" row was positioned); position donut 13 -> 12 (its sole
  positioned item); alignment donut 35 -> 35 (unchanged — not a prevalence metric). 12 + 35 = 47 of 59:
  the 12-metric denominator GAP is UNCHANGED (before 60-48=12; after 59-47=12) — so the 13+35!=60 finding
  is SEPARATE (12 Pay metrics are neither positioned nor alignment-rated) and is NOT resolved by this
  retirement. The AI-summary gap "base salary versus market median for Head of, at the 2nd percentile
  (n=147)" is GONE; Pay's widest gaps now read allowance premiums (Weekend P5/Night P7/Bank-holiday P8).
  Three base-pay POLICY questions RETAINED (REW_FAI_128, REW_BEN_REM_PAY_001, REW_PAY_019 — status active,
  still benchmarked). Gates green: qa_release (0 fail), qa_hero 57/57, qa_domain_summary, qa_status_audit;
  qa_engine_audit pre-existing-red on UNRELATED metrics (323ffcf1 store drift / ALLOW_02 / PROP_9e4ad87f
  rounding — REW_PAY_MKT_POS_01 in 0 failures; same failures with the metric temporarily active). NOT
  committed pending David's number review.

2026-06-29 — RETIRE REW_PAY_MKT_POS_01 — cache purge + commit. Purged 3 stale domain_summary cache
  rows (all Thornbridge), TWO distinct causes in one sweep: 2 Pay rows (retirement — held the retired
  "base salary versus market median by employee level — Head of" content) + 1 Benefits row (rename-era
  residue — pre-rename "match the market majority" vocab). Deleted by exact (org_id, domain, cut_key,
  payload_hash); NOT a domain-wide or whole-cache clear. Incentives/all::strat ("% of base salary" =
  REW_INC_111 bonus-as-%-of-base, the LEGITIMATE structure metric Lumi keeps) and Pay/all::strat (clean)
  explicitly preserved (5 -> 2 rows). Post-purge cache grep: "base salary versus market median" = 0,
  "match the market majority" = 0, "REW_PAY_MKT_POS_01" = 0 — cache matches current reality, not just the
  live render. Committed as its own unit, SEPARATE from the Practice Alignment rename (84a58b5); diff is
  DATA-ONLY (data/lumi_questions.csv one field + server/retire_metric.py + DECISIONS.md; no engine files;
  the cache purge is a runtime DB delete, not a tracked file). .claude/launch.json (local master-on demo)
  excluded. OPEN: the denominator gap — 12 Pay metrics neither positioned nor alignment-rated (12 + 35 =
  47 of 59) — is a SEPARATE finding, not resolved here; next.

## 2026-06-30 — Prevalence-gate routing fix: blast-radius diagnosis (NO fix applied)
Read-only diagnosis of the proposed change to the prevalence-eligibility gate at positions.py:664
(route by mp_config CLASS — Practice/Design -> alignment, Level/Provision -> position — instead of
legacy score_direction). Full finding: PREVALENCE_GATE_BLAST_RADIUS.md. Result: the change touches
67 single_select/yes_no metrics across ALL 8 domains (43 intended re-homes neither->alignment,
19 intended de-dups both->position-only, and 5 COLLATERAL regressions). The 5 collateral
(RED_COST_01, REW_PAY_HOURLY_MIN_1c6e096f, PROP_634adacd, EXT_REW_GAP_002, EXT_REW_GAP_007 — all
single_select / class=Level / direction=neutral / score_direction=0) are currently alignment-rated
and would silently fall into NEITHER pool. Reader map: the fix changes only HOW positions.py:664
uses score_direction; score_direction itself is untouched, so SCORING (aggregate.py) and SIGNALS
(signals.py builds its own adoption pool, reads score_direction nowhere) are unaffected — surgical
to the prevalence donut / AI-summary / per-card-band surface. Authority: NO written ruling exists
that mp_config class supersedes score_direction for POOL routing; mp_config class is the curated
authority for the POSITION gauge only, and the prevalence gate's score_direction check predates the
mp_config wiring — so this is an unsettled product decision (David's call), not a mechanical fix.
STANDING DECISION: The prevalence-gate fix is NOT clean — 5 collateral regressions. Do NOT apply the
global gate change. Options for a future pass: (a) David rules on each of the 5 collaterals
individually, or (b) a narrower fix that re-homes the 7 Pay Practice metrics WITHOUT a global gate
change. Engine-logic change — highest risk class. Diagnosis only; no fix applied.

## 2026-06-30 — Pay denominator: interim honest-header (Option B, copy/display only, pure-frontend)
The category header (web/js/pages.js, SectionPage) now reads "{N} benchmarks · {R} rated · {X} not
yet rated" instead of just "{N} benchmarks". Arithmetic closes (R + X = N; Pay = 59 = 41 + 18). The
two donuts are subset lenses that don't sum (position 12 + alignment 35 = 47, with 6 in BOTH); the
header discloses the DISTINCT-rated union (41) so a member can reconcile, and a hover tooltip/aria
explains the non-sum ("41 rated = 12 positioned + 35 aligned (6 counted in both). 18 not yet rated.").
Derived live from the per-card pool flags the page already holds (market_band ⇔ position donut,
prevalence_band ⇔ alignment donut); a card in both pools is ONE card in `cards`, so the 6-overlap is
counted once intrinsically — no overlap arithmetic to drift, no literal 59/41/18. Wording is "not yet
rated" (NOT "recorded") because some of the remainder are unanswered, so "recorded" would be a false
claim; "not yet rated" is true regardless of answered state. Graceful degradation verified both paths:
recorded===0 drops the third clause ("4 benchmarks · 4 rated"); the reduced/data-pending contributor
state (cards carry no band fields) suppresses the clause entirely ("27 benchmarks"), never "0 rated".
Rendered + confirmed on Thornbridge for Pay (59=41+18), Recognition (11=10+1), Governance (50=32+18,
no position donut — tooltip adaptively drops the empty "positioned" term: "32 rated = 32 aligned.").
ISOLATION: pure frontend. positions.py / aggregate.py / mp_config / score_direction / polarity / the
gate are ALL byte-identical; no metric moved pool, no score/signal changed. git diff = pages.js header
+ tooltip + degrade guard + cache bump (v290→v291). Gates green: qa_release (0 failures), qa_hero
(57/57), qa_domain_summary (127/127). This is TRUTHFUL DISCLOSURE OF THE GAP, NOT the routing fix. The
18 "not yet rated" (incl. the 7 single_select/yes_no routing orphans) remain in neither pool. The
underlying gate conflation (score_direction proxy vs mp_config class, 42 metrics across 5 domains)
remains OPEN as David's mp_config-authority decision. Do NOT read this as "denominator resolved" — the
routing is unfixed; the card is merely honest about it.

## 2026-06-30 — Position card neutralised (Q3=Mirror, Q4=above-red fixed), R-slate
The Market Position card was wearing the product's good/bad performance palette (marketTone:
below=amber / on=green=--favourable / above=red=--unfavourable) — colour doing judgment work that
contradicted the neutral-mirror principle, and an INVERSION (the engine favourability-adjusts, so
"above" already means BETTER than peers, yet rendered in the alarm red). David ruled Q3=MIRROR
(neutralise, like the already-de-judged Practice Alignment card) and Q4=YES (fix above=red
regardless). Brief: POSITION_RING_COLOUR_DECISION_BRIEF.md.
PALETTE: R-slate — a sequential SLATE ordinal ramp (POS_SOFT/POS_RICH, keyed by band: below->on->
above by LIGHTNESS, --grey-neutral / --grey-neutral-ink / --surface only). NO valence token on any
band (zero --favourable/--unfavourable/--amber-bright) => above=red is impossible BY CONSTRUCTION
(Q4). Slate (not the approved-N1 blue) was chosen at the collision check: the domain-page Practice
Alignment donut (CARD B) is ALREADY a blue ramp, so a blue Position ramp beside it would be
indistinguishable. Slate is self-contained — NO Alignment surface touched (hero stays violet
--differs, CARD B stays blue). blue=position/violet=alignment full unification (R-blue) was
considered and DEFERRED as a separate deliberate pass, not smuggled in.
SCOPE: Channel A (the aggregate Position card) FULLY neutralised across all 6 consumers — hero gauge
donut, MarketSpectrum bands, domain CARD A donut, category-tile bar + border + chip — keyed by band
name; marketTone is now CHANNEL-B-ONLY. The 4 dead valence maps (MKT_SOFT/RICH/CHIP/VCLS) were
removed (zero refs); new neutral classes .v-pos-lo/mid/hi + .chip-pos-lo/mid/hi added; the shared
.v-below/.v-at/.v-above + .chip-good/.chip-bad/.chip-mid left BYTE-IDENTICAL (used elsewhere).
above=red killed on ALL THREE channels: (A) Position card -> slate; (B) per-signal tag posTag line
946 higher-is-better above -> "neutral" (navy context), below/on tones kept; (C) signals
distribution bar posColor -> above -> "neutral" grey (--chart-band-mid). Channel B polarity-awareness
otherwise intact (lower-is-better below=green, neutral-polarity=navy). Four stale colour comments
(377, 642, 917-918, 923-924) + the inline hue comments rewritten to the slate map — the file no
longer lies about its own colours. Verdict word + legend already neutral ink (unchanged).
QA (Thornbridge, live): hero gauge + Pay/Benefits CARD A render slate (below->on->above by lightness,
3 distinguishable steps; deep step = slate ink, reads as category not disabled); the live above-market
metric (REW_BEN_045) renders slate on the card, navy pos-neutral on its signal tag, grey on the
distribution chip — NEVER red. Alignment unchanged BOTH surfaces (hero violet, CARD B blue). Shared
good/bad classes byte-identical. Gates green (qa_release 0, qa_hero 57/57, qa_domain_summary 127/127);
engine/routing/mp_config byte-identical; console clean; cache v291->v292. Frontend colour/display only.
CLOSES THE ORIGINAL REVIEW'S LAST VISUAL FINDING.

## 2026-06-30 — Q1=C routing applied (FIRST engine-logic change in the sequence)
The prevalence/position gate at positions.py:664 now routes Practice/Design by mp_config CLASS
(always -> alignment); Level/Provision — and any unclassified metric (safe legacy default) — keep
score_direction routing. The one edit: hoist `cfg = market_position_config()` once in
prevalence_items, then guard the existing exclusion with `cls not in ("Practice","Design")` where
`cls = (cfg.get("metrics", {}).get(qid) or {}).get("class")`. (NOTE: lookup is via .get("metrics") —
market_position_config() returns the FULL JSON, not the metrics dict; the diagnosis's top-level
.get(qid) would have silently no-op'd.) In-module loader, NO signature change, NO call-site churn
(app.py:1416/1521/1679/1763/3832 untouched). Brief: PREVALENCE_ROUTING_DECISION_BRIEF.md (Q1=C, Q2=3
amounts neutral).
RESULT: 43 metrics re-home NEITHER->alignment (42 Practice + CAR_COST_02 Design): Pay +7 / Benefits
+10 / Time Off +13 / Governance +13 / Incentives,Recognition,Wellbeing +0. The 5 contested Level
(PROP_634adacd, RED_COST_01, REW_PAY_HOURLY_MIN_1c6e096f, EXT_REW_GAP_002/007) STAY in alignment, OUT
of gauge — Q2's 3 amounts (Level+neutral) land out of the gauge with NO direction correction (path:
gauge_eligible needs Level/Provision+higher; neutral => out).
SCORES BYTE-IDENTICAL (the blocking gate, PROVEN): snapshot of score_answer over every metric x every
option label (5552 entries / 844 questions) BEFORE vs AFTER = ZERO diff. ALLOW_02 0.0 / RED_PROC_01
100.0 / REW_BEN_SICK_001 33.33 unchanged. prevalence_items reads score_direction but never alters it;
score_answer/score_polarity (aggregate.py) untouched. GAUGE byte-identical every domain (C adds
nothing to the gauge). signals.py / claude_api.py / data/market_position_config.json untouched (read-
only); AI privacy boundary intact — the re-homes are unit-less Practice/Design approach questions
(no £/level), and build_domain_summary_payload carries prevalence COUNTS not levels.
KNOWN DEBT (ruling d): the 19 de-dups (14 Provision / 5 Level) remain double-counted in the two
donuts BY DESIGN — C does not touch Level/Provision routing. The honest-header union keeps the
member-facing "rated" count correct (Pay not-yet-rated 18->11, Gov 18->5), so the debt is visual-only
(the two donuts vs the headline). De-dup resolution, if ever wanted, is a separate ruled pass touching
Level routing. Reconciles with the global-flip blast-radius: C avoids the 5 collateral regressions the
flip caused, leaves the 19 de-dups as debt — strictly additive.
GATES: qa_release 0, qa_hero 57/57, qa_domain_summary 127/127 GREEN. Two PRE-EXISTING failures
(qa_overview 5b leanWord/depth_pctl render assertion; qa_focus boardpack pack_id) reproduce IDENTICALLY
on committed code with this edit stashed — NOT introduced by Q1=C, unrelated to routing, flagged for a
separate look. Backend-only change: no web/ asset touched, so NO cache bump (the new routing surfaces
via API data, not ?v=-gated assets). Unclassed-default: 0 live select metrics lack a class (no
fall-through today; safe degrade for future releases). FIRST engine-logic change; scores proven
untouched.

## 2026-06-30 — Two pre-existing gate failures resolved test-side (no product bug)
qa_overview 5b: stale source-grep — broke when leanCaption was extracted (pre-baseline b3a6bcd); the
old check grepped for depth_pctl within 600 chars of the first "leanWord" CALL SITE, but depth_pctl
moved into the leanCaption HELPER. Retargeted to split on "function leanCaption" and check the helper
body. Real contract still covered (sibling 5a green; and proven NOT fake-green: simulate removing
depth_pctl from the adverb logic -> predicate goes red). qa_focus boardpack: app is CORRECT — boardpack
AI is gated behind LUMI_AI_INSIGHTS_ENABLED (off by default pre-go-live, David's go-live action), so
/api/boardpack/generate correctly 403s; the test assumed success and its api() helper swallowed the 403
to {} -> KeyError pack_id. Made AI-gate-aware via me["features"]["boardpack"]: defers/passes-with-note
when off (no crash), genuinely exercises generate->pack_id->fetch->leak/floor when on (+ api() hardened
to surface the status, not mask it). Proven both states: AI off (default) -> deferred PASS no KeyError;
AI on (forced on a THROWAWAY copy of lumi.db, deterministic narrative, no paid AI) -> 26 checks become
29, boardpack genuinely tested. Test-only; no app/engine change; master AI switch untouched (David's
go-live action). QA all green: qa_overview 0, qa_focus 26/0 (AI off), qa_hero 57/57, qa_domain_summary
127/127, qa_release 0. Diff = only qa_overview.py + qa_focus.py. NOTE: the throwaway-DB proof was run
correctly on a copy (board_pack inserted into the copy, not live: live board_packs stayed 92), but the
DB-level qa_overview/qa_domain_summary were run without LUMI_DB so they opened the LIVE db read-only and
triggered a benign WAL CHECKPOINT (WAL->main merge) — live lumi.db bytes changed but data is identical
(integrity_check ok, all counts intact, no QA write). lumi.db is gitignored, so this is not in any
commit. Lesson: point LUMI_DB at the copy for DB-level qa scripts too, not just HTTP ones.

## 2026-06-30 — Position card: RAG verdict-ring RESTORED (reverts the 3aca65f neutralisation)
Per David's decision the Market Position card returns to its EXACT pre-3aca65f RAG state via
`git revert 3aca65f` (byte-exact inverse, NOT a hand-rewrite): marketTone below=amber / on=green /
above=red restored; the MKT_SOFT/RICH/CHIP/VCLS performance maps back (--gauge-on/--favourable,
--gauge-below/--amber-bright, --gauge-above/--unfavourable); Channel-A routing back through
marketTone; posColor (921) + posTag line-946 back to marketTone (no neutral override); the four
colour comments back; cache v292->v291. The slate pos-* classes (.v-pos-lo/mid/hi, .chip-pos-lo/mid/
hi) are removed. ACCEPTED CONSEQUENCE (ruled, not re-opened): above-market higher-is-better again
tags RED on the Position card, the per-signal tag, and the signals distribution bar — the Q4
"above=red" outcome is re-accepted as intended. This SUPERSEDES the 3aca65f neutralisation
(Q3=Mirror / Q4) — that entry is KEPT above for history; this records the reversal + rationale.
Frontend-only: engine/routing/mp_config (positions.py from 888d606) and the Alignment card (hero
violet, domain CARD B blue) are untouched. Commits SEPARATELY from the signals common/alternative/
rare wording fix.

## 2026-06-30 — Signal verdict vocabulary unified to common/alternative/rare + clean Position/Context axes
ROOT CAUSE of the long-running "signals show differs from market" (the unreproducible ISSUE 2): the
dedicated Signals-LIST Row (pages.js:1105) rendered pt.text = POS_TAG_TEXT[s.position] ("differs from
market"/"differs from peers"), NOT s.tag — the 2026-06-29 rename updated s.tag (the home briefing, 875,
was already correct) but missed this surface. Fix: the Row renders s.tag (so it reads its own
COMMON—YOU—DON'T / A RARE CHOICE / AN ALTERNATIVE CHOICE tag); POS_TAG_TEXT differs/practice entries +
the "differs from market" fallback removed.
SINGLE WORD SOURCE: practice_axis.bucket_word(key) added (reads the existing states map: with_majority->
common / established->alternative / less_common->rare). SURFACE 1 — the approach tag (signals.py 814/
871/901) "DIFFERS FROM MARKET/PEERS" -> "AN ALTERNATIVE CHOICE" via bucket_word. SURFACE 3 — the verdict
prose "your approach differs from the market/peer norm" -> "an alternative to the market/peer norm" via
bucket_word (market/peers nuance kept in prose); the factual "X% of the market does this" kept.
GATING FINDING (confirmed): "differs from market" vs "differs from peers" was NEVER two computations —
it's the SAME prevalence axis labelled by domain competitiveness (signals.py:794 sets position="practice"
only for non-competitive domains = Governance). So the collapse is data-clean; competitive/peers nuance
kept in per-row prose, dropped from chips (David's ruling).
CHIPS (SURFACE 2): the two "differs" chips collapsed to common/alternative/rare; the non-competitive
Level peer-position outlier (HIGHER/LOWER THAN PEERS) -> its own "peer position" Position-axis chip (NOT
merged into above-market — that would re-impose the Governance-stripped RAG); neutral-context -> own
"context" chip (everything filterable; the pages.js:1084 neutral skip removed). Each signal gets a
server-computed s["bucket"] + s["bucket_order"] (signals.py, ONE place, prevalence words via bucket_word);
the frontend builds SIG_BUCKETS from the signals (distinct bucket, ordered by bucket_order) + counts/
filters by s.bucket — ZERO prevalence literal in the JS, no window/me-timing dependency. (The first cut
published window.PRACTICE_STATES from /api/me but the App-render me.config timing made it unreliable;
dropped for the self-contained s.bucket_order — app.py/app.js reverted, not in the diff.)
RECONCILIATION (Thornbridge all-peers): 87 signals = 76 Inbox (chipped) + 11 Dismissed. The 76 split
below 46 · above 1 · peer position 1 · common 16 · alternative 4 · rare 7 · context 1 = 76 (every signal
in exactly one chip; filter count==rows, e.g. common 16==16). Over signals_all (87): below 51/above 1/
peer 1/common 21/alternative 4/rare 7/context 2.
ISOLATION: Position RAG (below/above, restored in 57e9236) BYTE-IDENTICAL — above=red intact (HIGHER THAN
MARKET -> pos-red); the re-bucket only assigns s.bucket, a COMMON—YOU—DON'T Level provision stays
position=below -> below-market chip (rule 2 before rule 4). Engine routing (positions.py/aggregate.py/
mp_config) untouched. Gates green on a THROWAWAY DB copy (qa_release 0, qa_hero 57/57, qa_domain_summary
127/127, qa_overview 0, qa_prevalence_rename 70/70, qa_focus 26/0); live lumi.db byte-identical after
(LUMI_DB redirected to the copy for the DB-level gates too — isolation lesson applied). Cache v291->v292.
KNOWN/FLAGGED: the methodology "How lumi works" explainer (pages.js:2159/2165) still uses "differs from
market" + a violet legend swatch — a SEPARATE educational surface explaining the market-vs-choice concept,
not a signal tag/chip/prose. NOT changed this pass; David to rule whether it adopts the new vocab too.

## 2026-06-30 — Methodology explainer adopts three-category vocab (copy-only)
Methodology explainer adopts the three-category vocab (separate ruling after 9b042d8). Concept para: 'We label these differs from market' -> 'We show where your choice sits — common (what most peers do), an alternative pattern, or a rare choice'. Violet legend swatch 'differs from market' -> 'a practice choice: common / alternative / rare' (violet covers all three prevalence categories). Static teaching copy (direct literal, not bucket_word). Position-axis copy + the other four swatches untouched. KNOWN ITEM (separate, pending ruling): the single-metric analyst REGISTER still says 'differs from market' in 3 places (core.js:60 glossary, app.js:1108 mpReadChip, app.js:1122 mpReadCopy) — but that is a METRIC-TYPE classification ('this metric is an Approach, a choice not a market rate'), a DIFFERENT concept from per-org signal prevalence; it CANNOT be common/alternative/rare and needs its own term ('a practice choice'/'an approach') or may stay as-is. The rendered tree is NOT yet free of 'differs from market' — the register occurrences remain by design.

## 2026-06-30 — Vocabulary alignment complete: register/glossary/spec/terminology → "a practice choice" (PATH B)
register/glossary/spec/terminology → 'a practice choice' (PATH B), closing the last rendered 'differs from market'. App: Approach chip (app.js:1108) + copy (app.js:1122) + glossary headword (core.js:60 → Glossary card). cls 'differs'/var(--differs) violet UNCHANGED (colour is the anchor). Docs: spec palette (§5 L88) + concept refs (L24/198) migrated, §5 label-note + §6.3 stale-note added; spec retains 'differs from market' ONLY in the two change-records (L90/144, documenting the old term). Terminology: 6 occurrences migrated per-occurrence (filter-enum ref dropped — position filter has no Approach chip post-9b042d8; 'in line with market' companion dropped — single Approach label). Metric-TYPE label, distinct from signal prevalence (common/alternative/rare); sibling mp_config outputs, never mirrored (verified no runtime coupling). Resolves the same-page clash 5e13057 introduced. Rendered app tree grep-clean; every canonical source (app palette, terminology dict) agrees; old phrase survives only in spec change-records. QA note: preview login wrote 1 ephemeral sessions row to live WAL (benign, no benchmark change, main lumi.db byte-identical); launch.json-bound preview can't redirect LUMI_DB — logged limitation.

## 2026-06-30 — Approach-count surface de-"differ"ed to "off the norm" (binary model kept)
Approach-count surface: de-'differ' to 'off the norm' (binary model KEPT). 9 rendered occurrences (7 pages.js + 2 claude_api.py AI prose) 'differ' -> 'off the norm'; '63 in line with the market' kept (binary pairing); #8 'practice differences' -> 'practice patterns'. Concept prose ('a different way… not a gap', 'ranked by rarity') + internal enum/CSS/field-names UNCHANGED. Copy-only: server integers + approach payload {differ,in_line,pool}=43/63/106 byte-identical, binary model + privacy boundary untouched. Retargeted qa_overview:197 grep to the new headline copy (interpolation-contract intact — still catches a hardcoded number; the reword necessitated it, same class as 5ae54c5's 5b) + freshened qa_hero:126 comment. Closes the last rendered 'differ' count-prose: three difference-concepts now each have distinct vocab — metric-type 'a practice choice' / prevalence common·alternative·rare / modal-match 'off the norm vs in line'. AI fallback reword can't render pre-go-live (403 by design); rests on code-diff + payload byte-identical.

## 2026-06-30 — Signals: align the last user-facing differ-verb subtitle to "you don't"
Signals: align the last user-facing differ-verb subtitle to 'you don't'. signals.py:897/900 common+neutral re-tag subtitle 'your approach differs' -> 'you don't' / 'you don't yet' (all common-bucket subtitles now consistent regardless of polarity; byte-identical to the sibling common branches 808/811, 856/859). Server-only (no cache bump — the subtitle is composed server-side and returned live in the API payload; no JS/CSS changed). claude_api.py byte-identical: the modal-match count prose is already 'off the norm' (5c55c28, not re-touched), and the remaining 'differ'-family occurrences are CONCEPT register, deliberately kept (metric-commentary :470 'Differing... isn't a gap', same rule as explainer #4 'a different way of doing things') — model/commentary concept prose != user verdict. Tag/subtitle single-source (re-tag block :889-906) structure unchanged — only the two subtitle STRINGS edited; buckets/payload byte-identical. The differ VERB is now gone from user-facing VERDICT prose; survivors are internal enum/CSS/field-names + intentional concept-register phrasing. Gates green on a throwaway copy (qa_hero 57/57, qa_overview 0 fail, qa_focus 26/0); live lumi.db byte-identical.

## 2026-07-01 — Signals page redesigned: Market/Practice toggle + axis donut as the one filter UI
Signals page redesigned: Market/Practice toggle (Signals-OWN local state, never the shared _overview pref — verified no cross-drive) scopes both a donut and the signal list to its axis; donut built from the reusable Donut primitive fed the page's own per-bucket tally (posCounts over the axis-scoped signal set — the SIG_BUCKETS derive retired with the strip; no dual-donut component existed — CategoryPage's is inlined, untouched, zero diff hunks). ONE filter UI: donut chips AND segments -> setPosF -> the existing visible=filter(s.bucket===effPos); the standalone chip strip + the sig-bar DELETED (donut replaces the bar). Axis map: market = below/on/above market + peer position; practice = common/alternative/rare + context (context under practice; peer under market; both proven filterable). Reconciles: market 48 + practice 28 = 76 inbox, context counted once. No strategy toggle (none existed; the 'ordered for your strategy' note kept). Intro -> one line; strategy-check card -> below the list (DOM-order proven; its goToDomain jump now also resets axis->market — strategy diagnoses market stance). Zero-count chips render greyed/disabled with their 0 (new .sig-chip.is-zero; click no-op proven); empty axis -> caption in place of the ring ('No market-position signals in this view…', Saved+Market exercised live). Centre convention reused: market = verdictWord + 'N signals', practice = count-headline 'N signals' (noun 'signals' — the ring counts signals, not the metric pool). DEVIATION (logged): the shared Donut primitive gained an OPTIONAL onSeg prop + per-segment k so painted arcs are clickable (QA required segment clicks); callers passing neither render byte-identically (Overview/Category/Approach donuts unchanged). Frontend-only; buckets disjoint+exhaustive (signals.py:967-982); s.bucket/server byte-identical (server/ untouched). Responsive: donut/chips/toggle stack at 375px, no new overflow (only pre-existing topbar chrome). Gates green on a throwaway copy (qa_hero 57/57, qa_overview 0 fail incl. the 9b interpolation grep, qa_focus 26/0); live lumi.db byte-identical; cache v295->v296. Reuses Donut/verdictWord primitives + the Overview ov-seg toggle style.

## 2026-07-02 — Site-wide consistency pass: UX/UI polish, terminology alignment, a11y + delight (frontend-only)
Site-wide consistency review (5 parallel dimensions: copy/terminology, component patterns, design tokens, micro-interactions, accessibility; 53 raw findings → 26 implemented after per-line verification, 10 dropped as hallucinated/unsafe). Frontend-only — server/ byte-identical, all qa_overview grep contracts intact, locked vocabulary (a practice choice / common·alternative·rare / off the norm·in line / you don't / RAG) untouched. COPY: "No flag" pill → "No signal" (flag=verb, signal=noun); "Peer median" → "Market median" (card caption, aligning to every sibling surface); glossary headwords → sentence case ("A practice choice." not "A Practice Choice." — textTransform:capitalize dropped for first-letter-only, UK-gov register); "org's" → "organisation's" ×2 (Team page); lone "log in" → "sign in" (submit error); thin-sample tooltips "organisations" → "peers" ×2 (matching their chip); "To answer" tab → "To do" (matching rows/tiles); "This measure" → "This metric"; "few companies" → "few organisations" (explainer, matching its siblings); tooltip full stop. BRAND: descriptor unified to "UK reward benchmarking" ×5 (index title, auth subtitle, board-pack lockup, share footer, marketing footer — was "people analytics benchmark"); marketing "Log in" → "Sign in" ×5; "fewer than five" → "fewer than 5". COMPONENTS: .sig-chip DOUBLE DEFINITION consolidated to one canonical block — values are the pre-consolidation computed winners (999px/ink-soft/600/chrome-edge/.12s), verified byte-equal via getComputedStyle on BOTH consumer surfaces (Signals axis chips + Category donut filters); dead .num/.lens-*.on rules + legacy .signals-page .sig-filters margin + .sig-bar + .cat-pos-chips + duplicate .strat-diag .card-head deleted (all confirmed zero consumers); PageLoading atom (core.js) replaces the copy-pasted spinner row at 22 sites/7 files; domainLabel helper (core.js) — "Time Off" renders "Time off" everywhere (nav secLabel now aliases it; Overview tiles ×2 variants, Category h1, Signals group heads, "How your X reads", Your-data ×2), keys/routes keep "Time Off"; Signals group-by converged onto the shared .ov-seg pill (bespoke .seg CSS deleted, sole consumer); filtered-empty state got the signals-empty-ring icon; ⧉/✕ glyphs → Icon copy/close; .btn.block + .btn.disclose variants replace inline styles; type="button" on the Signals chips. A11Y: auth mode-switch + 4 legal anchors and submission wizard skip/def-toggle anchors now href="#" (keyboard-focusable — the front door was tab-unreachable); pulse cards + builder rows role=button/tabindex/Enter-Space ×2; Ask-lumi stat chips conditionally keyboard-operable (only when they navigate); global button:focus-visible border-radius override removed (10px corners no longer forced onto 999px pills — ring kept, verified 999px on focus). DELIGHT: --ease-fast token (.12s); sig-chip :active press scale(.97); Signals donut arcs morph (300ms dasharray/dashoffset; colour deliberately snaps — no RAG/violet blending; sole .sig-donut scope so Overview/Category donuts byte-identical; global reduced-motion backstop covers it) + clickable-arc hover brightness cue; ov-seg inactive hover; sig-tab underline hover hint; NEW-tag popIn; inbox-zero riseIn; .toast.success green (mirroring .toast.error). QA: gates green on a throwaway copy (qa_hero 57/57, qa_overview 0 fail — 9b/5b/9c/4b contracts verified intact, qa_focus 26/0); live-verified auth/Signals/Category/Overview/marketing renders; 375px no new overflow; console clean; live lumi.db byte-identical; cache v296→v298 (two bumps, one unit). One reviewer (design-tokens) died mid-run (API error) — its dimension has partial coverage only; a re-run is a known follow-up.

## 2026-07-02 — Board pack Tier 1: make it credible (pack layer + narrative + print; engine untouched)
Board pack deep dive (3-way: server generation/narrative · frontend render/print · boardroom-fitness gap analysis; 17 verified deficiencies) then the ruled Tier 1 "make it credible" unit. SELECTION INTEGRITY (the credibility trap): the pack layer now agrees with the app's market-position rulings — mp_config direction=neutral (context, e.g. workforce cost) can no longer appear as a board "strength"/"gap" (pre-fix: item-layer polarity called cost lower_is_better → £27,500 wage bill rendered as a green-chip P3 strength), and one matrix question can't consume the whole table (one row per question family; pre-fix 4 of 5 gaps were the same flexben matrix). Implemented as over-fetch(12)+filter at the PACK layer (app.py assemble_pack_payload) — top_gaps/top_strengths themselves untouched, other callers keep raw order; positions/aggregate/signals/mp_config byte-identical. PAYLOAD: headline.market {verdict, lean, depth_pctl} via substance_pool+_pool_verdict — the gauge's OWN path (word/needle agree by construction; QA proved byte-match with the live gauge: below/-0.8132/13.1). NOTE the deep-dive claim that overview_summary returns the verdict was WRONG (no such key — caught when the first QA pack came back verdict:None; recomputed properly). opportunity_totals {investment/savings_to_p50_gbp, fte_known} shipped; _pack_item ships polarity+favourable. NARRATIVE: _deterministic_pack rewritten (it IS the product pre-go-live — 87/92 stored packs are fallback): verdict-led 3-paragraph exec summary (verdict word + depth adverb mirroring leanCaption thresholds + counts + peer group/n; genuine strengths + £ totals; mirror-not-scoreboard close), count-aware section intros, actions from the deduped gaps with 3 rotating non-directive templates. AI GATE: the one AI surface without a validator got one — BOARD_PACK_SCHEMA structured output + validate_pack_narrative (shape / malformed-text / number-grounding vs payload / DIRECTIVE_RE / LEGAL_RE / NEW jargon screen banning payload-JSON-fallback-deterministic vocabulary), retry once → deterministic. Unit-proven 6/6 without the API (each screen fires for its own reason); the live call path rests on code-diff (no key pre-go-live), mirroring the commentary pattern. BUG FIX: saved-group cuts in generate shipped cut_label=null + empty criteria (wrong peer numbers in a board document) — now resolved via the parse_cut lookup (QA: 'My competitor set' n=30 resolves; stale/foreign id → All peers). UX: export button feature-gated on me.features.boardpack (domain_summary pattern — no guaranteed-403 clicks pre-go-live); dropdown error humanised (+ Review AI settings link); dev chip 'set ANTHROPIC_API_KEY' → 'Standard narrative — AI-written commentary arrives at go-live'; Download PDF sets document.title 'Board pack — {org} — {date}' (share view too) so the saved PDF stops being named after the app. PRINT: footers stay pinned (min-height 296mm vs the pre-fix auto), page break only BETWEEN pages (no trailing blank sheet), tables/cards/lists never split across sheets, analyst-pane/modal-back/toast-host print-hidden. RENDER: exec banner gains the verdict word cell; £ totals line above the opportunities table; PackTable chips colour by favourable with a 'lower is better here' gloss — ALL new fields guarded, so the 92 stored old-shape packs render byte-identically (QA-4 verified old shape intact). QA on a throwaway copy with gate ON + keyless (the demo env): real generate through the real endpoint; qa_hero 57/57, qa_overview 0, qa_focus 29/29 with the boardpack leak-checks EXERCISED (pack_id, hidden-area clean, n>=5 floor, unsuppressed rows); live lumi.db byte-identical; cache v298→v299. Tier 2 (story-arc redesign, charts via Donut primitives, signals/domains/strategy in the payload, pack management, versioning) + Tier 3 spec'd in the deep-dive output, pending ruling. Standing: one deep-dive test pack (8607b7c2) remains in live board_packs awaiting David's delete.

## 2026-07-02 — Board pack Tiers 2+3: story arc, charts, richer payload, management, delight
Tier 2 "make it good" + the feasible Tier 3 items, one unit on top of Tier 1 (24d9406). STORY ARC: pages recomposed Position → Money → Watch → Evidence → Appendix ("Where you stand" / "What closing the gaps is worth" / "What to watch" / "The evidence" / Appendix; page labels Cover+1-5). CHARTS: the shared Donut primitive is now window-exported (pages.js) and the Position page renders the below/inline/above ring (RAG segments, verdict centre word, aria + key) — the pack's first chart; print colour support already existed. PAYLOAD (all additive, every consumer optional-guarded): by_section per-domain position counts (from overview_summary, already computed); signals = the SAME balanced top-5 briefing the home page shows, in the ABSOLUTE view (no per-user triage, no strategy lens — org-level evidence; name/stand/tag/domain/risk/bucket); strategy {complete, objective} via strategy_for_engine + OBJECTIVE_LABELS; movement one-liner (only while a single snapshot exists); cut {dim,value} echo (for regenerate); methodology_version=1 (footer now reads it, not a hardcoded literal). AI prompt updated to weave the new sections in (verdict opens the exec summary, totals = the CFO's number, risk-marked signals in the narrative; strategy referenced never judged); schema/validator unchanged. MANAGEMENT: /api/boardpacks rows now carry cut_label/collection_window/ai-flag/creator (LIMIT 20→50); NEW DELETE /api/boardpack/{id} (require_admin, org-scoped, 404 on missing/foreign, double-delete proven); the Overview dropdown shows titled rows (cut · window · date · creator · AI) with an admin delete (confirm warns share links strand); BoardPackView gains Regenerate (uses the pack's stored cut), a staleness banner (GET now returns current_collection_window; banner when the pack's snapshot is older), share expiry selector 7/30/90 (server already validated those) + busy state + error toast + Copy button. GET also returns previous (the prior pack's headline) → the "Since your last pack" diff line (Tier 3). TIER 3 delivered: since-last-pack diff line; "Questions the board may ask" box on the Money page (deterministic, payload-grounded: cost-to-median, biggest lever, reliability/n); verdict-coloured cover accent + the real lumi logo on the cover (LUMI_LOGO_SVG window-exported from app.js, text-lockup fallback); auto-titles in the pack list; print body type → 10.5pt (beats inline styles, print only); P50 "—" now glossed as "score" with a title explaining score metrics. TIER 3 SKIPPED (logged): outcomes/retention page (the platform has no attrition data), CSS-counter print pagination (@page margin-box support too patchy), custom pack rename (needs a schema column; auto-titles cover the need). Back-compat: old packs render through the new structure with every new section skipped (QA-5: old shape intact via the new GET). QA on a throwaway copy (gate ON + keyless): QA-1 all 8 new-payload checks pass (signals top-5 incl. risk, strategy {complete:True, objective:'Control cost'}, by_section, movement, cut echo, Tier-1 fields intact); QA-2 current_collection_window + previous present; QA-3 enriched list (50 rows); QA-4 DELETE + double-delete 404; QA-5 old-pack shape intact; gates qa_hero 57/57, qa_overview 0, qa_focus 29/29 (boardpack leak-checks exercised — the new payload sections pass the hidden-area screen); engine (positions/aggregate/signals/mp_config) byte-identical; live lumi.db byte-identical; cache v299→v300. The new-shape visual render rests on code-guards + payload verification (the preview binds live — same Tier-1 limitation); David's next real export shows it.

## 2026-07-02 — Board pack Sprint 1: credibility furniture (WTW/Mercer research-driven)
Deep research (103-agent harness, 24/25 claims verified 3-0 against primary vendor sample pages + methodology guides) established what WTW Benchmark Select / Mercer TRS actually ship: rigorous DATA deliverables (full percentile spreads, graduated visible suppression, dual weighting, effective dates + aging, methodology-before-data, per-page confidentiality) with NO narrative — board-style framing exists only in bespoke consulting decks. lumi's pack already leads on narrative; this sprint closes the codified data-credibility gap. ENGINE NOTE — positions.py touched for the FIRST time this session, by explicit ruling: _item gains two ADDITIVE display fields (p25_display/p75_display, mirroring the p50_display line; zero deletions). Behaviour proven unchanged: all 8 engine outputs byte-match pre-change observations (verdict below / lean -0.8132 / depth 13.1 / 1-15-75 of 91 / £206,280), and the full gate suite is green including qa_domain_summary 127/127 run specially for this. PACK: (1) QUARTILE COLUMNS — evidence tables now You | P25 | Peer P50 | P75 | Percentile | n (the WTW/Mercer percentile-spread convention; blocks already carried p10-p90, aggregate.py:91); score metrics stay '—/score'; packs stored earlier keep the old 5-column layout (hasQ guard). (2) 'HOW TO READ THIS PACK' — methodology & provenance BEFORE the data (WTW structure): data-effective + live-benchmark/no-aging-needed line (the co-op difference, sold not apologised), peer construction incl. saved-group criteria (payload gains cut_criteria — QA: 'industry: Retail & Consumer Goods, Hospitality…' prints), organisation-weighting statement, suppression rule, anonymity-by-design, registry-matching model, the formal Mercer-register caution paragraph. Pages renumber Cover+1-6. (3) COMPETITIVENESS SCALE — the Mercer consulting-deck signature: horizontal P0-P100 band with amber/green/coral zones from the engine's own band (payload gains band {low:35, high:65} from MARKET_BAND_LOW/HIGH), marker at depth_pctl ('your typical metric: P13'), dispersion line ('15 of 91 within the on-market band'). Engine-native — no invented percent-of-median. (4) 'What competitive means here' boxed callout (median as reference, the band, percentile gloss). (5) 'Private & confidential · prepared for {org}' in every page footer (the universal vendor convention). All new render guarded — old packs verified untouched (no band/quartile keys → sections skip). QA on a throwaway copy (gate ON keyless): 5/5 payload checks incl. quartiles populated on value metrics + None on score metrics; group-cut criteria print; old-pack shape intact; gates qa_hero 57/57, qa_overview 0, qa_focus 29/29, qa_domain_summary 127/127; live lumi.db byte-identical; live server restored WITH the demo env (LUMI_AI_INSIGHTS_ENABLED=on — the earlier button-disappearance lesson); cache v300→v301. Research reference preserved in the workflow output (sources: WTW BSR sample pages, Mercer TRS sample content, 2024 Mercer methodology PDF, MercerWIN help, archived 2011 Mercer client deliverable). SPRINT 2 pending David's policy ruling: graduated suppression display with visible masking (anonymity floor stays 5; quartile tails would want 7/10-style thresholds), P10/P90 where n permits, pack-evidence CSV export.

## 2026-07-02 — Board pack Sprint 2: graduated suppression display, P10/P90 tails, evidence CSV
Sprint 2 of the WTW/Mercer roadmap, ruled by David. GRADUATED DISPLAY (the policy ruling): the n<5 anonymity floor stays ABSOLUTE everywhere (engine suppression untouched — nothing below 5 exists at any layer); above it the pack applies Mercer-convention display thresholds — quartiles at n>=7, P10/P90 tails at n>=10 — with masked cells rendering as '—' and a legend stating the rule plainly. Implemented at ASSEMBLY in _pack_item (app.py), so the stored payload IS the graduated truth and the AI narrative's number-grounding can never cite a masked statistic. Thresholds David-tunable (LUMI_PACK_QUARTILE_MIN_N=7 / LUMI_PACK_TAIL_MIN_N=10, house env pattern). Proven at every boundary via a unit test through the real _pack_item: n=5,6 masked/masked · n=7,9 shown/masked · n=10,220 shown/shown. FULL SPREAD: positions.py _item gains p10_display/p90_display (same additive mirror-pattern as Sprint 1, zero deletions — the diff is exactly those 2 fields + comment); evidence tables now You | P10 | P25 | Peer P50 | P75 | P90 | Percentile | n (fresh-pack verified: flexben n=146 → 1.4%/2%/3%/4%/4.5%); tail columns render only when a row qualifies (hasT guard); packs stored earlier keep their layouts (verified no new keys on old packs). EVIDENCE CSV: 'Download data (CSV)' beside Download PDF — client-side from the pack's own STORED payload (nothing recomputed): strengths/gaps with the full spread + percentile + n + lower-is-better notes, opportunities with both £ figures, practice gaps with adoption; provenance + confidentiality header rows; Excel BOM; named 'Board pack data — {org} — {date}.csv'. ENGINE BEHAVIOUR PROOF (second positions.py touch, same standard): all engine outputs byte-match pre-change again — verdict below / lean -0.8132 / depth 13.1 / 1-15-75 of 91 / £206,280; gates qa_hero 57/57, qa_overview 0, qa_focus 29/29, qa_domain_summary green. QA on a throwaway copy (gate ON keyless); live lumi.db byte-identical; live restored with the demo env; cache v301→v302. This completes the ruled WTW/Mercer roadmap — the remaining vendor conventions (aging/lead-lag, participant lists, incumbent weighting, YoY trend cuts) are deliberately NOT built: live co-op data needs no aging, anonymity forbids participant lists, org-level submission means single weighting, and YoY arrives with the second snapshot. Own the differences.

## 2026-07-02 — Board pack Sprint 3: print-grade layout (David's PDF review) + design-tokens re-run
David exported the real PDF and judged it below WTW standard ("needs exec summary, contents"). Reading his artefact (pypdf) confirmed the print truth the screen never showed: a 7-page pack printing as NINE sheets — the Executive-position and Evidence pages overflowed 296mm and spilled onto unnumbered continuation sheets (footers floating mid-page, page labels wrong), the 9-column gaps table squeezed metric names to one word per line, a same-day "Since your last pack: 1 → 1" noise line, no contents, no page titled "Executive summary". FIXES: (1) COVER CONTENTS — a WTW-style TOC block (dotted leaders, 8 entries) on the cover. (2) "Where you stand" SPLIT into "Executive summary" (verdict banner + narrative + competitiveness scale + movement + conditional since-last) and "Position by area" (donut + domain table + callout + maturity + composition) — each fits one sheet. (3) "The evidence" SPLIT into strengths (6) and gaps (7) pages; appendix → 8; all footers + TOC renumbered (Cover+1-8, 9 sheets, each exactly one page). (4) TABLE SQUEEZE — pack tables get first-column width 34% + nowrap numeric cells + the 9-column spread table drops a type size (.bp-wide); metric names read normally. (5) Since-last-pack line SUPPRESSED when nothing changed. (6) The P13 dispersion-line whitespace nit (htm collapse) fixed earlier this sprint. THE SPILL PROOF: a deterministic page-height check in the live render (296mm ≈ 1122px at CSS 96dpi) — before: page 7 at 1402px (spilling); after: all 9 pages ≤1099px, zero spill. Verified against David's own exported pack (869b715f — his export, so this pass needed no DB writes at all). DESIGN-TOKENS RE-RUN (the logged e71e264 follow-up; 3-agent workflow, per-line verified, 20/20 applied + 1 defect): GENUINE DEFECT — var(--line) was used at 6 sites (pulse builder borders/dots) but NEVER DEFINED, so those borders silently never rendered → var(--border); value-identical token swaps (#fff→var(--surface) ×2 incl. suggest-modal, rgb(37,71,176)→var(--quartile-fill), 10px→var(--radius-sm) ×4, 4px→var(--s1) ×3, padding shorthand collapse); dead-rule deletions verified by fresh zero-consumer greps (clock-chip/-ring day-one experience ×7 rules, watermark ×2, pstrip ×3, link-quiet ×2, title-info ×2, appr-bar ×2 — the old approach bar the Donut replaced), duplicate reduced-motion .sidebar rule, dead dial-card radius; core.js chart-fallback hexes corrected to current token values (#2547B0→#2048B0 blue, #7A5AF8→#6257C9 differs — fallback path only, runtime resolves the var). Net −2.3KB CSS. Remaining flagged near-miss colours (untokenised tints, one-off hovers) logged in the workflow output, not applied. Frontend-only; CSS braces balanced; live appr-*/statchip/legal-row selectors verified surviving; console clean; live lumi.db byte-identical; cache v303→v305 (three bumps, one unit). David should re-export the PDF — every sheet is now exactly one page with honest numbering, a contents cover, and a page titled Executive summary.

## 2026-07-02 — Board pack print pass 2: verified against REAL printed sheets (headless print pipeline)
David's re-exported PDF was still sub-board ("still not a pack I would send"). Rasterised his artefact (pymupdf) and SAW the truth the screen-height proxy missed twice: the exec banner card STACKED vertically in print (ugly indented column, stray border bars), the 9-col gaps table still crushed labels (fixed-width rule lost to nowrap cells → 9-line rows), the appendix overflowed by a hair → ORPHANED FOOTER on a blank 10th sheet, footers wrapped ("…Thornbridge Retail / Group plc", "lumi · / 8"), pages half-empty. FIXES: (1) exec banner → purpose-built .bp-statrow (3 stats across, guaranteed row in print; the UI card retired from the pack). (2) .bp-wide table → table-layout:fixed with EXPLICIT column widths (label 30%, n 7%, pctl 11%, six value cols share the rest) — first attempt (equal-share fixed + ellipsis) truncated values to '0…/44…/PERCI', caught and replaced in the same loop; header Percentile→Pctl and Peer P50→P50 in spread mode. (3) evidence pages RE-MERGED (compact rows fit one sheet again); appendix capped at 8 rows; TOC/footers renumbered Cover+1-7 (8 sheets). (4) footer middle → 'Private & confidential' (single line, org name lives on the cover + filename); pageno nowrap. (5) PRINT PAGINATION MADE BULLETPROOF: .pack-page print height EXACTLY 296mm (min+max+overflow:hidden) so content drift can never cascade page boundaries again (min-height was the orphan-footer root cause), .share-boardpack padding zeroed in print. (6) domainLabel applied in the by_section table ('Time off'). NEW VERIFICATION STANDARD: a real print pipeline — headless Chrome print-to-pdf against a share link on a THROWAWAY copy (share row written to the copy only, discarded after) → rasterise → eyeball every sheet. Iterated 3 prints in the loop: 11 sheets (share padding offset) → 8 sheets but truncated values → 8 SHEETS CLEAN: Cover+1-7, banner 3-across, gaps spread whole and readable (0.9%|1.4%|2%|3%|4%|4.5%|P3|146), appendix + footer on one sheet, single-line footers. The screen-height proxy is retired as print evidence — print claims now require printed sheets. Frontend-only; live lumi.db byte-identical; cache v305→v306.

## 2026-07-02 — Board pack analyst + design pass (David: "more analysis, commentary, coloured sections, a summary")
Content + design identity pass, verified via the headless print pipeline against a fresh pack on a throwaway copy. NARRATIVE MODEL EXTENDED (schema + prompt + validator + deterministic, all four in lockstep): key_findings (3-6 single-sentence, NED-quotable, each payload-grounded), position_commentary (reads the by_section table: widest area by ABSOLUTE below-count — the first cut ranked by share and crowned a 3-metric area over Benefits' 37-of-40, caught in-loop — plus the most in-line area and the Governance-beside-the-headline note), evidence_commentary (what the quartile spread shows, e.g. 'each of the largest gaps sits below the peer P25 — outside the middle half, not a rounding difference'). Deterministic composes all of it from payload figures (verdict phrase, by_section extremes, £ total + biggest lever, top gap vs its P25-P75 middle half, top missing practice adoption); the validator treats key_findings like recommended_actions (non-empty string list) and allows the two commentaries to be empty on thin data; unit-proven (clean accepted, empty findings rejected, directive finding rejected). AI prompt gains the three keys with grounding instructions. DESIGN IDENTITY: every page now opens with a numbered, colour-coded section head (filled number chip 01-07 + title + full-width coloured rule; brand-blue family per section, semantics-free) — the 'defined coloured sections' ask; KEY FINDINGS renders as a tinted panel (blue-7% wash, blue-deep left bar, uppercase micro title) between the stat strip and the narrative — the summary a NED reads first; position/evidence commentary paragraphs render under their tables (guarded — old packs without the fields skip them). Print-verified: 8 sheets exactly, exec page now dense (stat strip + 6 findings + 3 narrative paras + scale), position page carries the donut/table/commentary/callout/maturity stack; 'Time off' sentence-case in the area table. Gates: qa_hero 57/57, qa_overview 0, qa_focus 29/29 (leak checks scan the new narrative fields); live lumi.db byte-identical; cache v306→v307. NOTE: packs generated BEFORE this pass lack the new fields and render without the findings panel/commentary — regenerate to see the full document.

## 2026-07-03 — Board pack: Strategy alignment page (David's ruling)
New conditional page 04 "Strategy alignment": the declared reward strategy summarised, then the engine's own read of how today's position tracks against it. PAYLOAD: strategy_alignment {objective (OBJECTIVE_LABELS, provenance-skipped respected), overall_aim, overall_alignment, domains[{name, aim, aim_is_override, position, alignment}]} — computed via the SAME hero path the dashboard uses (hero_signals with the org's strategy applied; prevalence_items + sec_order replicated from the overview handler), stances translated server-side (lag/match/lead NEVER renders — verified by regex over payload+narrative: zero leaks; the standing 6a/6b vocabulary rule). Only present when a strategy exists AND is completed. NARRATIVE: strategy_commentary added to all four layers in lockstep (schema, prompt, validator [may be empty], deterministic — declared aim + objective in plain words, overall read, by-area grouping on/ahead/behind, closing with the mirror line 'a reading against your own declared aim — not a judgement of the strategy itself'); validator unit-proven (empty allowed, missing rejected). RENDER: conditional page (old packs + strategy-less orgs skip it — hasStrat guard) with DYNAMIC page numbering (money/watch/evidence/appendix shift 4-7 → 5-8 when present; TOC computed; SecHead numbers follow; bp-c8 colour added). The page: declared-strategy intro (objective + overall aim, area-override note), Area|Your aim|Your position|Read table (green on-aim / red behind-aim chips, area-level aims annotated '· area aim'), the commentary, the caveat. Print-verified via the pipeline: 9 sheets (Cover+1-8), TOC carries the row, footers renumber correctly; the demo org's data shows the page working hard — Time Off's area-level 'below market' aim reads on_target while five areas read behind the global on-market aim (the exact nuance a board needs). Gates qa_hero 57/57, qa_overview 0, qa_focus 29/29; live lumi.db byte-identical; cache v307→v308. Regenerate to see it — stored packs pre-date the field.
## 2026-07-14 — Domain taxonomy: Option B′, 8 domains (RATIFIED)
**Ruling (David).** Live taxonomy moves 7 → 8: Pay · Pensions & Savings · Health & Protection ·
Benefits & Lifestyle · Time Off & Family · Incentives & Recognition · Wellbeing · Governance &
Transparency. Pensions & Savings and Health & Protection extracted from Benefits; Recognition
merged into Incentives & Recognition (11 live + 0 pipeline fails the ~20-market-metric
meaningful bar alone); exit/redundancy/notice metrics sit in Benefits & Lifestyle.
**Mechanics.** Metadata-only remap per `domain_remap_mapping.csv` (243 rows, row-level authority —
supersedes any keyword rule). Answers untouched. `domain_min_polarised = 3` unchanged; every
domain clears it with margin. Seeded org CSVs and `market_position_config` re-derive from mapping.
**Rejected.** Option A (minimal, Pay stays overloaded); Option C (5 domains — destroys panel
diagnostics at ~340 metrics).

## 2026-07-14 — Market vs practice classification rule + reclassification (RATIFIED)
**Rule (David).** If an individual can relate the metric to comparing against market, classify
MARKET; if in doubt, MARKET. Operationalised: orderable by generosity/magnitude with a defensible
richer/leaner reading from the employee-offer side → market; genuinely unordered choices (method,
philosophy, timing, inventory, mechanism) → practice.
**Applied.** 65 of 96 non-polarised live metrics flip to market (+18 audit corrections incl.
REW_BEN_139 / REW_INC_133 eligibility matrices per David challenge). Final: 293 market /
41 practice / 1 strategy-config (REW_PAY_005 recategorised — strategy parameter, not a metric).
**Scope.** BENCHMARK/POSITION path only. Signals-path rulings of 2026-06-13 (prevalence reroutes)
untouched. Market TAGS ≠ gauge membership: "Where you stand" remains ↑-Substance only; cost-lens
(PMI premium) and context (payout % of target) metrics carry market tags but are gauge-excluded.
**Ratified exception (David).** REW_PAY_097 pay-differentiation-by-performance = PRACTICE,
overriding the tiebreak: egalitarian-vs-differentiated is a philosophy fork, not richer/leaner.
REW263_PAY_MERITMATRIX practice for consistency.
**Ratified directions** on five contested new metrics: EWA cap ↑=cap in place · 4-day week
↑=operates · commission ↑=uncapped · green pension ↑=net-zero aligned · remote-abroad ↑=higher cap.

## 2026-07-14 — Metric register finalisation (RATIFIED)
**Final register:** 335 metrics (`lumi_master_metric_register_FINAL_APPROVED.csv`) = 236 live-active + 99 approved additions (2026_4 ships 45; remainder queued 2026_5).
**Retirements (never delete — status flips, history preserved):**
- retire_boundary: REW_PAY_HOURLY_MIN_1c6e096f (pay level; replaced by NEW real Living Wage
  accreditation metric), REW_PAY_MKT_POS_01 (pay positioning = level).
- deactivate: REW_PAY_022 (ambiguous, overlaps 023), REW_PAY_126 (unanswerable), EXT_REW_GAP_006
  (long-service over-instrumentation), REW_FAI_091 (forward intent, no peer-mirror value),
  ALLOW_01 (consolidated into REW_PAY_016).
**Rewords/extensions:** REW_PAY_023 → "Which factors inform your annual pay budget?" (multi_select);
REW_PAY_016 options +Homeworking allowance, +Mobile/phone allowance, +None.
**Gate carried forward:** all 38 REW263 classifications re-derived from full questions-CSV text in
the Diff-2 pre-approval report before polarity writes (register texts are truncated; truncation
caused the audit misses).

## 2026-07-14 — Domain competitiveness flags for the B′ taxonomy (Diff 1 scope)
market_position_config.json _domains flags for the 8 domains: Pay TRUE, Pensions &
Savings TRUE, Health & Protection TRUE (both inherit from Benefits TRUE — no gauge
membership change), Benefits & Lifestyle TRUE, Time Off & Family TRUE, Incentives &
Recognition TRUE (both parents TRUE), Wellbeing TRUE, Governance & Transparency FALSE
(carried over). Rationale: Diff 1 is metadata-only and must be verdict-neutral.
The G&T flip to TRUE is a live open ruling — its premise (governance ≈ practice-heavy)
was retired by the 2026-07-14 reclassification (61 market metrics) — but it is
verdict-changing and is therefore ruled separately at Diff 2, not inside the remap.

## 2026-07-14 — Diff 1 pre-approval conflict rulings
1. REW_PAY_020 (allowances pensionable by level): ACTIVE, domain Pensions & Savings,
   classification market ↑. Root cause: FINAL register was built from a stale
   anchor-register snapshot predating the June regen. Register/mapping corrected;
   register is now 336 = 237 live-active + 99 new.
2. REW_PAY_MKT_POS_01: already retired in DB — acknowledged. Mapping row retained;
   Diff 3 action for this id = VERIFY retired, not flip.
3. REW_Q534581 / REW_Q528801: destination PAY. DB placement correct; premium-pay
   multipliers are pay structure, not incentive design. Mapping old/new corrected.
4. Standing gate: every future register/release diff opens with a row-level
   reconciliation against visible_questions() before any write.

## 2026-07-14 — G&T competitiveness flag: TRUE (Diff 2, ruled Option 1)
Governance & Transparency flips competitiveness TRUE in market_position_config.json.
Premise for FALSE (governance ≈ practice-heavy) retired by the 2026-07-14
reclassification (61 market metrics). Verdict-changing by design: G&T's ↑-Substance
market rows join the overall gauge. Metric-level Substance filter unchanged — the
flag admits the domain, not cost/context rows. Headline movement is expected and
reported, not a defect.

## 2026-07-14 — Diff 2 scope
Classification (market_eligible) and polarity writes per the reclassification file,
plus the REW263 full-text re-derivation gate below. Signals path untouched
(2026-06-13 rulings): ordered_scale_routing.json, signal_lenses.json out of scope.

## 2026-07-14 — Diff 2 veto-gate rulings
Root cause: the reclassification CSV shipped as the pre-ratification working draft;
review flags were never cleared post-ratification. Rulings:
- REW_PAY_097: PRACTICE stands per the ratified exception. Row removed (no-op).
- REW_PAY_MKT_POS_01: row removed — retired id, outside a changes-only live file.
- EXT_REW_GAP_013 (pay frequency): VETOED to practice — frequency is timing, named
  practice in the ratified rule. Current=neutral, so no-op; row removed.
- REW_INC_069 (deferral): VETOED to practice — governance mechanism, not employee
  generosity. Current=neutral, no-op; row removed.
- CLEARED as proposed (7): 3faf1f0c… PMI premium (market, cost/save lens,
  gauge-excluded by Substance filter); REW26_BEN_PENSION_TYPE (market ↑ DB>hybrid>DC);
  PROP_634adacd and PROP_9e4ad87f (market ↑ offer lens — subject to full-text
  confirming the offer-lens reading; bounce as divergence if text contradicts);
  REW_BEN_REM_PAY_001 (↑ maintain>reduce); REW_BEN_REM_PAY_005
  (↑ discount<none<premium); REW_INC_104 (market, context ↑, gauge-excluded).
  Distinction from PAY_097 for the record: remote-pay poles are orderable for the
  affected employee; egalitarian-vs-differentiated has no such ordering.
- Standing gate added: every authority CSV is linted at ship (veto column empty,
  ids reconciled against visible_questions()) before any diff prompt cites it.

## 2026-07-14 — Diff 2 headline rulings
1. 63-id divergence: REGISTER IS THE TARGET (option a). Root cause owned: the
   changes-CSV 'current' ledger was authored from polarity while the engine routes
   by config class (Q1=C ruling, 2026-06-30) — 63 polarity-market/class-practice
   strays were invisible to a changes-only file. The ratified book presumes the flip.
2. Register v3 (re-uploaded) is current authority: it absorbs today's veto rulings
   (GAP_013, INC_069 → practice) and the ratified 38-row gate outcome. Recomputed
   divergence set expected at 61; if it differs, enumerate before anything else.
3. Addendum mechanics: YOU generate the addendum rows from register v3 — for each
   divergent id: current = engine class, proposed = market, direction = register
   direction mapped through your extracted shape rule (Provision=binary presence,
   Level=ordinal/numeric; cost/context rows take the established Level+neutral
   market-tagged gauge-excluded shape). Any direction you cannot map mechanically
   is a DIVERGENCE for David — never a guess.
4. 38-row gate: RATIFIED as proposed, 31 market / 7 practice. All seven judgment
   flags cleared: PMIEXCESS market on the offer lens (lower excess = richer);
   ETHDISREADY + MENOPLAN are current-state maturity, not FAI_091-class intent;
   REWTEAM doubt→market; COMPARATIO practice on the REW_PAY_005 precedent;
   REC_IMPACT + HOLRECORDS market per the 61-flip pattern. INC_DEFERRAL practice
   citing the INC_069 veto is precedent applied correctly.
5. REW_PAY_020 verify outcome acknowledged: live neutral/Design, CSV row performs
   the real flip. Proceed.
6. Book correction: final register book is 291 market / 44 practice /
   1 strategy-config on 336 (live-237: 203/33/1). Supersedes the 293/41/1 figures
   in the finalisation entry — delta fully explained by GAP_013 + INC_069 vetoes
   and COMPARATIO. Diff 4's practice bucket sizes to 44 (33 live + 11 new).

## 2026-07-14 — Diff 2 apply-gate rulings
1. REW_FAI_079: ruled (a) — market, class Level, direction ↑ (conducted/annually),
   LIVE POLARITY FLIPS lower_is_better → higher_is_better. History: reword-without-
   repolarise stray (GPG magnitude ↓ reworded to analysis-conducted with polarity
   left standing); the live polarity agreeing with the register was two copies of
   one slip. Precedent chain: REC_IMPACT / HOLRECORDS / ETHDISREADY. Join it to the
   addendum write-set — the addendum table as posted is now exact (61 rows,
   G&T after 44/6, totals 203/40).
2. Register v4 re-uploaded: FAI_079 direction corrected. A full ↓-row scan found
   no other reword strays (PMIEXCESS, BEN_047 IP waiting, and the two workforce-
   cost PROPs are correct by design).
3. REW_INC_070 (malus): pre-ruled PRACTICE per the INC_069 precedent — governance
   mechanism, not employee generosity; market-↓ would read strong governance as
   below market. NOT in Diff 2's write-set (already engine-market): executes in
   Diff 3's hygiene batch. Logged now so Diff 3's spec inherits it.
4. Commit diff2_addendum_generated.csv in the same commit — it is executed
   authority and belongs in the audit trail.

## 2026-07-14 — Diff 3 scope (register hygiene)
Retirements per the finalisation entry, enumerated from the mapping:
retire_boundary: REW_PAY_HOURLY_MIN_1c6e096f · REW_PAY_MKT_POS_01 (VERIFY only —
already retired, per the Diff 1 ruling). deactivate: ALLOW_01 (consolidated into
REW_PAY_016) · REW_PAY_022 · REW_PAY_126 · EXT_REW_GAP_006 · REW_FAI_091.
Plus three ruled corrections: REW_INC_070 → practice (INC_069 precedent, ruled at
the Diff 2 apply gate); REW_PAY_023 reword ("Which factors inform your annual pay
budget?", multi_select); REW_PAY_016 option extension (+Homeworking, +Mobile/phone,
+None). Post-diff the engine's live set converges exactly to register v5 (237).

## 2026-07-14 — Diff 3 rulings
1. Status mechanics: option (a) ruled. `retired` is the engine's sole terminal
   state; retirement FLAVOUR (deactivate vs retire_boundary) is documentary and
   lives in release_retired as flavour:reason. Stamp format: date-based
   (2026-07-14-hygiene:<flavour>) unless release_retired carries an established
   release-number convention — follow the house format if so, and say which.
   The register/mapping remain flavour authority. No new engine states.
2. ALLOW_01 consolidation: LEAVE history under the deactivated id. No answer
   transformation — 215/220 overlap would double-represent, and the location/COL
   mapping is genuinely ambiguous; five orgs of n is below any floor that matters.
3. REW_PAY_023: IN-PLACE text edit to the ratified wording. No version bump;
   historical_comparability stands at high. Comparability breaks are for meaning
   changes (FAI_079-class), not phrasing.
4. REW_INC_070: sibling mirror means CLASS + DIRECTION, not type. Write
   class=Practice, direction=None, polarity=neutral; KEEP type=binary (069 is
   ordinal because 069 is ordinal; 070 is a binary question and stays one).

## 2026-07-14 — Diff 4 scope + split ruling
Practice surfaces per the ratified single-bucket design: home-dashboard bucket
card (crop-aware), "A practice choice" chips on domain metric lists, Practice
Alignment donut removed, G&T special-case card copy deleted, board-pack practice
section (bucket headline + rare stances, descriptive only). RULED: the
in-line/off-norm split computes over single-choice practices only; multi_select
inventories count in the bucket total and render in the lens but are excluded
from the split, disclosed in the basis line. Modal-match computation reuses the
existing practice-lens machinery — one implementation, never a second. No RAG
colour on any practice surface (POSITION_RING brief stays open, unpre-empted).
Vocabulary locked: in line / off the norm · common / alternative / rare ·
"A practice choice" (exact string) · below/on/above market never on practice.

## 2026-07-14 — Diff 4 pre-approval rulings
1. REW_PAY_005 lens leak: CONFIRMED, land the exclusion here — it is a
   correctness precondition for the surface this diff builds, not a deferrable.
   Named constant STRATEGY_CONFIG_IDS in prevalence_items, comment citing the
   DECISIONS strategy-config ruling. QA asserts (a) the ripple — every practice
   pool count −1 exactly where Pay pools counted it, lens shows 34 — and
   (b) every id in the constant exists live and is class Practice. Diff 5's
   import gate inherits a check: no new strategy-config row without extending
   the constant.
2. Toggle: CONFIRMED — the home Market|Practice toggle retires; the practice
   lens is reached via the bucket card click-through only. Explicit boundary:
   the Counts|Position toggle on Position-by-domain is a DIFFERENT control and
   is untouched.
3. Briefing practice read-line (word + minibar): RETIRE. Domain pages exclude
   practice from analysis; a read-line is analysis. Rows + chips remain.
4. Domain narrative "practices" sentence slot: RETIRE, same reason. The bucket
   and lens carry the practice story; domain pages stay clean.
5. Methodology paragraph: YES, update in this diff. Replacement copy, verbatim:
   "Governance and transparency metrics that can be ordered by generosity or
   maturity count toward your market position like any other domain. Practice
   choices — where organisations differ by design rather than by generosity —
   never carry a market verdict: they're shown as in line or off the norm,
   with how common each choice is among your peers."
6. §5 chip strip: ACCEPTED as specified — suppress the position pill on any
   card carrying prevalence_band, then add the chip. Logged as pre-existing
   since Diff 2 (grid fall-through on classification.register), caught here.
7. Spec correction noted for the record: the domain-page donut died in the
   briefing rebuild (6f6b311); this diff's removal target is the home
   PracticeArc. §4 live numbers verified against register v5 — by-domain
   practice split matches exactly (Pay 17 · I&R 11 · G&T 4 · B&L 1 · Well 1).

## 2026-07-14 — Diff 5 scope + seeding
Release 2026_4: 45 metrics imported unscored (required=FALSE, scored=FALSE),
polarity per CSV (42 higher_is_better · 3 neutral), config shape per the Diff-2
rule (Provision = binary presence, Level = ordinal/numeric; neutral rows =
class Practice). SEEDING: David's standing recommendation is seed-at-import for
the 66 demo orgs — anchor-informed targets where the anchor register grades A/B,
conservative for estimate-flagged rows, sector-tilt machinery where the anchor
notes it (MEALS), all recorded in a per-metric seed manifest (target vs anchor vs
seeded prevalence). The Phase 0 seed plan is the ruling instrument: David's
"apply" ratifies it; "apply, no seed" launches the wave unanswered.

## 2026-07-14 — Diff 5 pre-approval rulings
D1 — Register v6 re-uploaded with REAL ids: the 45 REW264_* ids are minted in the
   register (text-join, 45/45; 54 NEW_ placeholders remain for the 2026_5 queue).
   Re-run the id-level reconciliation against v6 — expect exact. The import
   manifest still records the NEW_xxx ↔ REW264_* mapping as audit trail.
D2 — The 13-row conditional table is RATIFIED as classified (the spec's "nine"
   was a stale pre-QA count — defect owned, David-side). Seven WIRED with the
   parents you named — apply-order must tolerate the intra-wave EWA parent —
   and six SELF-DECLARED where the NA option is the mechanism. EVSALSAC
   self-declared is correct: an option inside a live multi-select is not a
   resolvable parent.
D3 — RATIFIED as recommended: help_text ← the member CSV; help_why imports to
   NO member-visible column (lives in the committed authority CSV + changelog).
   The 2026_3 defect (38 live rows showing internal rationale as member help)
   is REAL and OUT OF SCOPE here: queued as its own post-sequence micro-diff;
   David-side authors the 38 member texts. Log it, don't touch it.
D4 — Seed cohort: 220 non-Tester orgs, matching the established pipeline. The
   "66" in the scope entry was a phantom — corrected in this ruling. Rationale:
   new-wave pools must be comparable with every live pool; a 66-org wave inside
   220-org peer sets would make 2026_4 prevalence structurally incomparable.
D5 — The four market multi_selects take their config shape by MIRRORING a live
   market-multi sibling (seven exist; REW26_WEL_MH_SUPPORT is a clean donor) —
   derive, don't invent. Dryrun must render ONE new market multi's distribution
   + percentile as evidence the path works before apply.

## 2026-07-14 — Diff 6: release 2026.5 imported + seeded (54 metrics, REW265)
Approved with three riders; applied same day. Live book 282 -> 336 (Pay 67 · G&T 65 ·
ToF&F 51 · I&R 44 · B&L 41 · P&S 25 · H&P 24 · Wellbeing 19); practice bucket 37 -> 45.
CONDITIONALS (7 offer_na): wired SAYEDISC/SHAREPART -> REW264_INC_SHAREPLAN
(parent-negative = Neither / Not applicable (no shares)); SIPELEM wired to the same
parent via its "No SIP operated" terminal (na_handling=none by design — SAYE-only orgs
are real; rider 2 seeds an explicit 0.40 No-SIP share among parent-positive, manifest-
visible: 15 No-SIP / 28 with elements). Self-declared: AIDISCLOSE, COMMCAP (sector-
driven: substantive in sales-heavy industries only), EARLYCAREER, ENHANCEDVR,
GPGNAMING (rider 1: scope-out DERIVED from each org's FTE band — 50-249 only, no
global rate; verify asserts zero in-scope orgs holding it — held at 0).
TWO-TIER SEED (anchor register status is the tier authority): 27 verify-queued ->
conservative-haircut (x0.75, hard ceiling at the named figure); 27 estimate-flag ->
unanchored-conservative (modal No/None/Statutory-only). Near-floor by design:
GRANDPARENT, UNLIMITEDAL, LEAVEDONATE, EOT (positive pools at/under 5 — live
suppression demonstrable). Sector tilts: EVCHARGE office/industrial, SEASONAL
retail/hospitality/logistics, COMMCAP sales-heavy, EIA + ACTINGUP public-sector,
PENBRIDGE DB-heritage.
FIRST-VERIFY CATCHES (the assert design working): (1) best-first option ordering
inverted the taper for 12 no-"No"-label rows — taper now anchors at the lean pole;
(2) the profile sector key is Industry, not Sector — all sector rules had silently
no-opped; (3) SHAREPART/PROMOPAY carry VALUE anchors (a participation band, a median
increase size), not org-prevalence figures — a prevalence ceiling is a category
error there; value-anchor rows detected mechanically, seeded on the 0.30 conservative
default, marked in the manifest. Final verify CLEAN: max target deviation 0.013,
zero wired incoherence, zero terminal co-mingles, rider-1 zero, convergence 336/336
by id vs register v8. RIDER 3 exact: headline pool 240 -> 279 readings = 42 market
singles minus Thornbridge's 3 NAs (2 wired + 1 FTE-derived scope-out); depth P30.1
-> P33.0; verdict below. The 4 market multis produce no headline reading (known
design observation). Gates: qa_overview 0 · qa_hero 59/59 · qa_release 0 on the
336 basis.

## 2026-07-14 — Close-out: register v9 canonical + seed-kit hardening (post-Diff-6)
1. SHAREPART and PROMOPAY conservative defaults RATIFIED — the value-anchor category
   error was correctly caught: those anchors are value distributions (a participation
   band, a median increase size), not prevalence figures; a prevalence ceiling does
   not apply. Both rows stand on the 0.30 conservative default, manifest-marked.
2. Taper/best-first interaction: spec-side ownership recorded — the 2026_5 CSV's
   best-first option convention met the kit's worst-last assumption. The kit fix
   (lean-pole fallback = last option; taper anchored at the lean pole) stands.
3. STANDING KIT RULES (all future waves): (a) tilt-application assert — every sector
   rule must prove non-zero application or fail loudly; a silent no-op is a prohibited
   failure shape (the Industry-vs-Sector key slip would have been caught at apply,
   not verify). (b) Mechanical value-anchor detection stays in the kit — value
   distributions are never prevalence ceilings.
4. Register v9 CANONICAL and now committed (the first register in git — the /*.csv
   ignore had kept every upload untracked; force-added per the ruling-4 precedent).
   336 live (290 market / 45 practice / 1 strategy-config), zero queued — the
   question bank programme is COMPLETE.


## Domain-summary validator: grounded metric-name exemption (14 July 2026, ruled — trust-gate change)
Word-list scanning applies to the residual prose after removing exact grounded metric-name phrases
present in the payload — whole-phrase removal only, never single-word or substring exemption. Banned
words surviving in the model's own prose still fail. All ten hostile-rejection checks retained as the
regression floor. Rationale: B′ remap made banned words legitimate metric names ("Critical illness
cover", "…reviewed regularly"); deterministic floor was failing its own gate and blanking drivers on
Pay, Wellbeing, H&P (shipped "—" for notable — found by the 2026-07-14 deep-QA pass once the crashed
gate was revived). Implementation: claude_api.validate_domain_summary text_scan (word boundaries guard
alphanumeric phrase edges); DOMAIN_SUMMARY_GEN_VERSION bumped to 2026-07-14.domain-v4-groundednames so
cached blanked outputs self-invalidate. Verified: qa_domain_summary 143/143 incl. all hostile rejections.

## QA infrastructure: four stale gates re-derived + run_gates.sh canonical (14 July 2026)
All four re-derived per check-77 (derive-don't-hardcode): qa_focus (competitive domains + methodology
scope from mp config; probe metric from live cards — ALLOW_01 literal died with Diff 3), qa_domain_summary
(Governance fixture name from the live taxonomy; the "non-competitive domain" hostile check re-derived
onto a synthetic has_position-stripped payload — Diff 2 removed the live premise), qa_commentary
(unanswered-metric fixture derived at run time — third hardcoded pick to die to a seed wave),
qa_engine_audit (ALLOW_01 spot metric derived). Failure pattern noted: the gates had been crashing since
Diff 3 and masking one another — a crashed gate hides everything behind the crash line.
qa_engine_audit lineage: rew_live_meta.json (18 June ruled surgical coherence reseed) PROMOTED to lineage
alongside REGEN_WHITELIST — only whitelisted, ruled manifests ever count as lineage; ref pools now mirror
the engine's completeness firewall (submission_complete=1 — Tester-org post-aggregation answers excluded
from ref counts); percentile comparison tolerates 2dp storage rounding (tol 5.01e-3).
run_gates.sh is the canonical gate entry point — doctrine encoded: SQLite-backup throwaway → re-aggregate
→ provably-fresh servers (lsof first, log to file, assert zero address-in-use, kill by PID) → ten gates
keyless → qa_pulse/qa_release LAST → always restore the dev server on the real DB. README points to it.

## Seed realism reseed — legal-form + coherence + anchor shapes (Diff 7, ruled 14 July 2026)
Surgical reseed of the 99 wave metrics (REW264_*/REW265_*) per the seed-realism review (SEED_REALISM_REVIEW.md) and David's rulings R1–R4 + ①②③. Old book (all non-wave answers) is ground truth and NEVER written — hash-asserted byte-identical pre/post. Append-only discipline: DELETE the changed answers row, snapshot the prior value into answers_history, INSERT the corrected value into answers + answers_history. Deterministic per-org RNG sha256(qid|SEED_DATE|org_id). Authority: lumi_seed_realism_fix_targets.csv (12 rows).

RULINGS (on the record):
- R1 (SHAREPART): approve modal shift to 10–25% (adjacent-below the 25–40% anchor band; conservative without absurdity).
- R2 (EOT): KEEP AS SEEDED, byte-identical (No 207 / Under consideration 9 / EOT-owned 4) — above the anchor-implied <1% base rate BY RULING, near-floor suppression demo value retained.
- ① (EVSALSAC): CAR_COST_02 is the governing EV-orientation signal, NOT the kWh field (216/220 substantive = seed noise that defeats the condition). Missing CAR_COST_02 = "not EV-oriented" -> flip. 54 flips to the negative family, assigned by mirroring the current Fuel-neutral-family marginal via per-org RNG (not a flat assign).
- ② (COMMCAP): TWO-WAY. 27 (REW_INC_135="No" + substantive) -> NA; 97 (135=Yes + NA) -> substantive. No COMMCAP row exists in the 12-row file (David's "row in the file" reference was a handoff miss); resolved by applying ruling ③'s mirror principle to COMMCAP — reshape the 97 by mirroring the 135=Yes substantive marginal Hard cap 50 : Soft cap 35 : Uncapped 15 across the FULL 123-org conditioned base, the 26 already-substantive counting toward satisfaction (double-count rider). The 26 are kept untouched; the 97 fill to hit 62/43/18.
- ③ (SALSAC): mirror the current substantive marginal (IMPACT and RESPONSE independently) via per-org RNG; no target row overrides. 132 writes (66 each) — the 89-org NA set is identical across both metrics; 66 carry sal-sac evidence (REW26_BEN_SALSAC "Yes" ∪ benefits-multi sal-sac items; union 197), 23 keep NA legitimately; 0 substantive-without-evidence.

FIVE FIX CLASSES:
- F1 legal-form (116 flips -> "Neither"): share-capital forms (plc/Ltd, from ownership_type + name-suffix fallback) holding the share-capital NA on EMICSOP (59) / SHAREPLAN (57) flip to the substantive lean. Non-share forms keep NA; 10 unknown-form orgs reported-not-flipped. Wired children unchanged (0 writes) — old and new parent both parent-negative.
- F2 cross-book contradiction map (cohort-wide): EVSALSAC 54, COMMCAP 27+97, SALSAC 132. New conditions on old; old never moves. Logged out of scope: the two pre-existing old-book contradictions (REW_INC_135 vs _136; WEL_BMAP vs REW26_BEN_SALSAC).
- F3 anchor shapes (SAYEDISC, SIPELEM, SHAREPART, BONUSTIME) + F4 pole corrections (WORKATION, BONUSDISC, GREENDEFAULT, HOLPAYMETHOD, CHILDCARE, BROKER, REBROKE, EOT-keep): target_distribution applied on each stated basis within 0.03 TOL, except the CHILDCARE floor override below.
- F5 shape jitter: 63 conservative-tier single-select wave rows (excl. the 12 target rows, near-floor trio, EOT, 6 F1/F2 rows, 8 anchored-tier rows) get deterministic per-metric ±5–8pp lean-pole jitter to kill the repeated (70,20,10)/(75,17,8)/(65,20,10,5) house shapes; ceilings hard-asserted post-jitter; the 7 non-target multis out of scope.

CHILDCARE FLOOR OVERRIDE (binding, on the record): the 20 current "Workplace nursery scheme" holders with old-book on-site-childcare evidence (WEL_SUP_FAC_002) are preserved as a floor -> achieved nursery incidence ~9% (20/220), above the file's 4% target on that one option. The binding preservation note intentionally overrides the 0.03 TOL for that cell (forcing them down would manufacture a new cross-book contradiction to hit a marginal); the target miss is documented in the manifest. Thornbridge is one of the 20 -> realism flag 5 preserved.

THREE KIT RULES PROMOTED (permanent, not patches):
1. Value-anchor regex extended to detect "the N% maximum"-style phrasings (the SAYEDISC value anchor the mechanical detector missed at Diff 6).
2. Lean-pole is SEMANTIC, never positional: any no-natural-"No" row requires an explicit worst-option key; hard error if absent.
3. Coherence conditioning: the seed kit accepts a conditioning map of existing-answer dependencies (the F2 mechanism, generalised for future waves).

HEADLINE LEDGER: Thornbridge Retail Group plc 279 -> 280 (net +1: EMICSOP +1, SALSACIMPACT +1, COMMCAP −1; SHAREPLAN/EVSALSAC 0; SALSACRESPONSE Practice -> practice bucket +1). Cohort-wide false-NA correction: F1 +116, COMMCAP net +70, SALSAC-IMPACT +66 = ~+252 market readings entering the pool (labelled line in the manifest, new absolute headline re-asserted against the live DB).

SECONDARY OBSERVATIONS (logged, not actioned): SAYEDISC/SIPELEM applicable-base imprecision (43/28 vs true SAYE-ops 31 / SIP-ops 18 — pre-existing child-NA wiring, later pass); the two old-book contradictions stay as ruled.

MANIFEST LINEAGE: diff7_seed_manifest.csv whitelisted into qa_engine_audit lineage per the ratified only-ruled-manifests rule (alongside rew_live_meta.json + REGEN_WHITELIST).

## Anchor-verified reseed — FLEXPATTERN / COUNTEROFFER / VOLGAPS (Diff 8, 15 July 2026)
Surgical reseed of 3 wave distributions to verified CIPD primary-source figures, superseding the
Diff-6 seed (and, on COUNTEROFFER, the Diff-7 F5 jitter — an anchored primary figure beats a shape
jitter; correct precedence). Same pipeline as Diff 7: DELETE + re-INSERT + answers_history snapshot,
deterministic per-org RNG sha256(qid|2026-07-15|org_id), is_na-aware base exclusion (the NICSHARING
primitive), exact-count multi assignment (NOT Bernoulli — the small-base TOL lesson from Diff 7).
Everything outside the 3 metrics hash-asserted byte-identical. Authority: lumi_diff8_targets.csv.

THE 3 CORRECTIONS (all CIPD primary, all supersede seed):
- REW265_TIME_FLEXPATTERN (multi, Level) — CIPD Flexible & Hybrid Working 2023, employer survey
  n=2,005, Fig 1. Per-option employer-offer incidence: Flexitime with accrual 51, Core hours 40,
  Compressed hours 34, Annualised hours 22; None derived residual -> 14% (30 orgs). Flexitime/
  compressed/annualised are direct employer-offer rates; "Core hours" is not separately surveyed by
  CIPD and is held at a conservative 40 (between flexitime and compressed, plausible). Exact counts
  112/88/75/48. Prior seed had None at 66% — the market read as far more rigid than CIPD shows.
- REW265_PAY_COUNTEROFFER (single, Practice) — CIPD Labour Market Outlook Summer 2023, n=2,003.
  40% counter in the last 12 months but only 22% hold a FORMAL policy. Mapping: Never counter 35 /
  Case-by-case with approval 40 (absorbs the informal-but-happens bulk) / Routinely counter 13 /
  No policy 12. Exact counts 77/88/29/26. Prior seed overstated formality.
- REW265_GOV_VOLGAPS (multi, Level) — CIPD Pay, Performance & Transparency 2024, n=832 (large-
  employer base; the lumi cohort skews large, so applicable). The question asks PUBLISH, not analyse:
  Ethnicity 40% analyse but only 18% share with employees -> 18; Disability 27% conduct, publishing
  lower -> 12; CEO pay ratio voluntary ~8 (not in PPT, conservative). None derived residual -> 65%.
  Exact counts 40/26/18.
Achieved max per-option deviation 0.0018 (integer rounding only — exact-count hits target by
construction). Exclusive-terminal rule holds by construction: None is assigned only to orgs with zero
substantive picks, never alongside one. 481 cell changes (186/186/109).

HEADLINE: distribution-only reshapes. All 3 metrics carry ZERO is_na options, so every org holds a
substantive answer before and after ("None" is substantive, not NA) — NA sets unchanged, comparable
counts unchanged. Headline asserted pre == post == 280 (Thornbridge Retail Group plc).

VERIFICATION PASS — 3-state outcome on 15 rows, recorded in a NEW `verification_state` column on both
anchor registers. WHY A NEW COLUMN, NOT A STATUS OVERWRITE (ruled 15 July 2026): the instruction to
"stamp unverifiable-free in the anchor register" would have overwritten `status`, which
seed_release_2026_5.py documents as THE TIER AUTHORITY and build_dist() branches on
(`elif tier == "verify-queued": pos = min(pct*0.75, pct)`). Stamping those rows would have silently
dropped them to the else-branch 0.25 unanchored haircut on any reseed, and failed dryrun_2026_5.py's
"two tiers 27/27" gate — and NONE of it would turn run_gates.sh red, because those scripts are not in
the suite. Worst failure shape: silent, load-bearing, invisible to the gates. `status` therefore stays
exactly as-is on every row; `verification_state` carries the new fact alongside it.
  anchored-reseed (3):     REW265_TIME_FLEXPATTERN, REW265_PAY_COUNTEROFFER, REW265_GOV_VOLGAPS
  verified-direction (3):  REW265_INC_SAYEDISC, REW265_INC_SIPELEM, REW265_INC_EOT — HMRC ESS
                           confirmed the ceiling / structure / base rate; Diff-7 shapes stand.
  directional (3):         REW265_PAY_PAYCOMMS, REW265_BEN_EVCHARGE, REW265_INC_ESGINCENT — data
                           found, no clean marginal; seed held.
  unverifiable-free (6):   REW265_INC_SHAREPART (ProShare), REW265_PAY_PROMOPAY / _GEOPAY / _RANGEMAX
                           / _ACTINGUP (Brightmine), REW264_HLT_CASHPLAN (LaingBuisson) — primary
                           source behind subscription. A legitimate PERMANENT state, not a queue:
                           chased to the paywall and stopped there, not overlooked.

MANIFEST LINEAGE: diff8_seed_manifest.csv whitelisted into qa_engine_audit lineage per the ratified
only-ruled-manifests rule (alongside diff7_seed_manifest.csv, rew_live_meta.json, REGEN_WHITELIST).

## Anchor seed + multi-factor latent reseed (Diff 9, ruled + applied 16 July 2026)
Reward-only seed reshape. reseed_engine.py rewritten: factor-vector latent, anchored-spike loader,
ruled orderings, hard gates. Applied at rho=0.40 with `--profiles seed_personas_220.json --write
--confirmed-by-david`. 18,160 cells re-paired; answers count unchanged 233,288 (append-only:
history snapshot -> DELETE -> INSERT, 36,320 history rows); non-reward book hash-identical.
FINAL QA: qa_reseed 9/9 (G4 0.427, G3 0.131, G2 4) on a fresh throwaway AND on the live result,
identical; run_gates.sh 10/10 green.

TWO-FACTOR MODEL (G + S), ruled after three-factor failed on COVERAGE not tuning:
- Three factors {G,M,C} failed G4 at 0.029-0.253. Diagnosis: G4 measures cross-AREA coherence, and
  the re-pair can only move metrics that have an ordering. Incentives had 2 of 16 richness metrics
  movable (12%), so a separate C factor could not express itself; its pairs collapsed. rho was
  irrelevant — the sweep was FLAT at 0.09-0.12 across rho 0.30->0.70. Not a knob.
- M and C merged into S (structure/competitiveness); G kept. S = rho*core + (1-rho)*0.5*(M_terms +
  C_terms) so both structure-side signals survive at scale. Final loading: Governance+Incentives -> S,
  Benefits+Wellbeing+TimeOff -> G.
- COVERAGE FIX (the actual cure): ruled orderings for 6 Incentives metrics took its movable share
  12% -> 50%, and Incentives' load on S went 0.268 -> 0.917. Benefits x Incentives 0.138 -> 0.538.
  Governance x Incentives — the pair qa_reseed.py:25 documents as permanently weak (~0.31) and which
  had collapsed to 0.031 — is now the STRONGEST pair at 0.83.

RETIRED HYPOTHESIS (recorded so it is not mistaken for a finding): "Incentives is structurally
categorical / genuinely low cross-area coherence" was WRONG. Coverage was 50% by metric COUNT but
~90% by VARIANCE — the 8 orderable Incentives metrics carry nearly all the spread; the 8 categorical
ones (LTIP types, commission structures, pool funding, incentive intent) are near-constant and
contribute almost none. Claude Code's own forecast (load ~0.4-0.6, Benefits x Incentives 0.2-0.35,
"straddling the floor") was wrong in the conservative direction; actual 0.917 / 0.538. The
documented-exception branch was prepared and is NOT needed — no G4 exception exists.

RHO = 0.40 (ruled on the measured number). Feasible band {0.40, 0.50}; 0.60 breaches the 0.70
cross-factor ceiling (corr(G,S)=0.779) AND at high rho both factors share an identical rho*core term,
so the headline G4 is partly factors correlating with themselves — the discriminant GAPS (Incentives
+0.21 toward S; Time Off +0.16 toward G) are the load-bearing evidence, not absolute magnitudes.
0.40 chosen for the cleanest REAL separation: corr(G,S)=0.566 (+0.134 ceiling headroom) with G4 at
0.427 (+0.127). Factor independence IS the point of the enrichment; 0.50 buys unneeded G4 margin by
spending separation.
- CORRECTION ON THE RECORD: an earlier ruling picked rho=0.40 (three-factor) on the reasoning that
  "G4 binds, G3 has headroom". Half right — G4 does bind, but it binds from BELOW (pulls rho UP),
  which was asserted rather than measured. Measuring on the real reseed reversed the choice to 0.45,
  then coverage work superseded the whole question. Measure the gate; do not reason about it.

THE NOMINAL-RESHAPE BUG (the incident this diff exists to not repeat): the prevalence branch applied
a target_share to any metric with a lean pole, including NOMINAL ones. REW26_BEN_PENSION_TYPE
(DC/DB/Hybrid/None) was reshaped, moving 152 orgs from "has a DC pension" to "no scheme" — a seed
asserting 71% of UK employers run no pension, which is false and illegal under auto-enrolment. 46 of
59 prevalence spikes were hitting nominal metrics. Only G2's pension rule made it visible; the other
45 would have shipped SILENTLY.
- HARD GATE (kit rule 2, one level up): a prevalence target_share is "the share NOT on the lean pole".
  That sentence is only meaningful on a genuine binary/ordinal OFFER axis. If no ordering can rank the
  metric -> HARD ERROR, never reshape. Wired into reseed_engine; 0 rejects at final state.

RULED ORDERINGS (38 total: 32 general + 6 Incentives). option_order() ranks only pure yes/no, numeric,
and 4 hard-coded ladders — far weaker than the data, which is why 46 rejected. Each ordering is an
explicit `option_order` key in the spike entry, authored verbatim against LIVE option strings and
ruled by David — NEVER inferred by heuristic (a lean-pole heuristic readmits PENSION_TYPE, and
keyword/shape heuristics misled this build six times).
- CICOVER PRINCIPLE (standing): "Not applicable"/"Don't know" are N/A SKIPS excluded from the
  ordering — not poles. The engine only re-pairs values present in the ordering, so excluded orgs keep
  their answer. This IS the conditioning mask: it makes parent/child coherence structural (e.g. orgs
  without income protection hold "Not applicable / not offered" on the replacement-level child and are
  never re-paired). Only CAR_STATUS_01 -> CAR_COST_02 needed explicit wiring.
- POLARITY (ruled): malus/clawback/gatekeeper are GOVERNANCE STRENGTH, not employee generosity —
  "more" is stricter. Coherent on S; would be WRONG on G.

9 CONFIRMED ANCHOR MIS-MAPS -> context + register re-source flag (figures are valid, but against a
DIFFERENT metric — find the true home, do not delete): REW_BEN_039 (anchor=flexible WORKING, question=
flexible BENEFITS PLATFORM), REW_BEN_100 (pension matching vs PMI eligibility), REW_BEN_SICK_005 (full
pay vs whether rules are DOCUMENTED), REW_PRO_034 (COLA at range max vs promotion guidelines),
REW_INC_132 (all-employee share plans vs LTIP types — also kinds), REW_BEN_102 (offering vs
participation), REW_INC_103 (linking pay to performance vs bonus eligibility), REW_BEN_REM_PAY_005
(kinds — premiums and discounts are OPPOSITE directions), REW_INC_069 (deferral is a RESTRICTION;
polarity ambiguous). PENSION_TYPE is the same class (contribution level vs scheme type). NO GATE
CATCHES THIS CLASS — 4 of the 9 are grade A/B. A keyword validator scored 2/9 recall: the defect is
semantic and needs a read of anchor-note against question-intent, one at a time.

PERSONAS — Option 5 (author the 62): live cohort is 220; the design had 210 personas of which only 158
bridged; the 52 unused are DIFFERENT companies from the 62 inferred orgs. 62 authored by
firmographic-conditional sampling, flagged generated:true + source_org_id_live, reversible.
- Fix applied: all 158 REAL personas were missing Audit_Scrutiny / Risk_Appetite / Recent_Shock (the
  62 authored had them) — assembled from org_profiles.json which lacks those fields. Recovered
  losslessly from data/seeded_orgs.json by Org_ID. Without it the SYNTHETIC orgs would have carried
  richer M/C inputs than the REAL ones.
- Loader: reseed() accepts a LIST artifact keyed on org_id or source_org_id_live (only the 158 real
  rows carry org_id). The approved command crashed before this fix.
- industry_canon guard: the 62 authored carry SHORT canonical names ("Retail"), the 158 real carry
  LONG ("Retail & Consumer Goods"). Keying on the map alone dropped 60 of 62 to "Other". canon_industry
  now accepts both. Related: the B1 tilts must be keyed SHORT (what canon_industry returns and the
  legacy SECTOR_TILT uses); keying them by the source table's LONG labels made every lookup miss —
  all 220 orgs would have silently read tilt 0.5, the entire sector signal inert with no error.

B1 SECTOR TILTS: the signed 6x15 grid (lumi_sector_tilt_table (2).xlsx -> Sector_tilt_v3, signed off
by David 2026-07-15) un-averaged into sector_well_tilt/gov_tilt/pay_tilt in persona_factor_config.json
(NOT market_position_config.json — that is the gauge/classification config, unrelated to seeding; the
original spec was wrong). Raw grid -2..+2 normalised (raw+2)/4 to the 0..1 the formulas require;
per-cell provenance retained. Energy/Utilities mean 1.333 vs legacy SECTOR_TILT 1.17 is moot — latent3
retires the averaged tilt. sector_well_tilt is WEB-directional in 8/15 sectors (approved as a weighted
factor input under direction-not-marginal).
- NOTE: a source regeneration of persona_factor_config.json clobbered this once. File is now
  engine-owned; David's inputs go to separate files.

TRONC BASELINE RESTATED 30 -> 42: the 30 was computed with the canon bug (short-named authored
personas fell to "Other" so their tronc gate never fired). Fixed lookup gates 12 genuine
Retail/Hospitality frontline>40 orgs ON. LTIP/Shift/Car unaffected (ownership/workforce-keyed or
identity-mapped sectors). gate_baselines_ACTUAL_220 = LTIP 100 / Shift 119 / Tronc 42 / Car 41,
all reproduced exactly at final state.

SPIKE ROUTING (160 entries): 45 prevalence applied / context / floor. 15 hold_from_marginal (wrong-base
subgroup rates) route latent-only via mode_effective. The clean marginal set hit target at max_dev
0.0022 — integer rounding only.

INSTRUMENT DISCIPLINE (the lesson of this diff): qa_reseed is the ONLY authoritative instrument for
G1-G10. A parallel harness built to measure G3/G4 reported +0.357 then +0.330 while qa_reseed said
0.253 — it measured a subset and had to be corrected twice. Its NEG set was also wrong (12 items vs
qa_reseed.py:51's 6, which includes "n/a" and ""). The harness's G2/G3/G4 reporting is retired.
- OPEN (follow-up diff, not a blocker): qa_reseed scores G2/G3 against org_profiles.json +
  org_profiles_inferred.json, NOT seed_personas_220.json — its loader only accepts dicts and cannot
  read the 220-persona list. G3 uses only FTE_Band (present in both) so it is sound; G2's HR_Maturity
  check is weakened for the 62 authored orgs. The gates are not reading the same personas the reseed
  used.

## Register clean — 20 mis-maps re-homed/cleared, generator rules ruled (Diff 1 of the reseed rebuild, 16 July 2026)
AUTHORITY (ruled): the register (lumi_anchor_register_CLAUDECODE.csv) is authoritative over the derived
spike file (anchored_spikes.json: demonstrated ~19-37% defect, base-collapse, one fabricated figure).
Where they disagree (44 rows, 5 of them applied marginals incl. EAP/CIC/life-assurance grade-A
contradictions), the register's sourced/based figure wins; the spike file is superseded and is REPLACED
at Diff 2 by a file GENERATED from the register by rule — no hand-transcription anywhere (every defect
this session traced to hand-derivation).
METHOD PEDIGREE: keyword validator 2/9 recall -> semantic pass 7/7 on testable reds (register) -> fully
blind pass 9/10 (spike file). Mis-map = true figure on the wrong question; only reading intent finds it.
DISPOSITIONS (adversarially verified, David-ruled): 10 DROP_DUPLICATE block-approved (figure already at
home; row clears to EST). 3 MOVE: PENSION_TYPE's contribution figure -> PLSA_QM as UPPER-BOUND PROXY
(>=6% employer necessary-not-sufficient for PQM; <=29% bound; grade A->B; generator bound-only/context;
resolves the PLSA fabrication into a sourced bound); MERITMATRIX merit-pay figure -> REW_PAY_097;
PAY_018 call-out figure -> REW_PAY_017 (shape caveat). 2 CONFLICT ruled: HOL_006's Payline quantum
APPENDED at HOL_004 as companion; FAM_012's CIPD policy figure -> MENOPLAN as Grade-C proxy, GENERATOR
CONTEXT-ONLY (policy != ERA-2025 action plan), incumbent Aon figure parks. 4 PARK -> parked_anchors.md
(figures held, never deleted; on-subject candidates captured: FAM_005 provision-extract action,
SSPALIGN's Brightmine candidate). 2 REVISED: PROP_8862fcad clears (both components already at true
homes; FW = FINANCIAL wellbeing, audit self-corrected); REW26_WEL_FINWELL mis-map OVERTURNED by the
register's own standing reconciliation — relabel only. Real mis-map count 20, not 21.
Extinguished (not parked): REW_BEN_100's '29% all?' fragment — mis-transcription, dies with the clear.
EXECUTED: register_clean_diff1.py — 25 rows changed (19 clears, 6 receives), 218 asserted byte-identical,
full ledger printed; backup .bak_pre_diff1_regclean_20260716. Anchored rows 121 -> 104.
GENERATOR RULES (ruled with this approval, generator_rules.json, 39 rows): BLEND_ELIGIBLE 7 (cohort blend
(SME*30+large*190)/220 — the cohort is 86% 250+, so all-UK bases understate and large-only overstate);
SINGLE_BASE 9 (no-blend, stated-base caveat; SALSAC's own rule is DO-NOT-EMIT — the founding-error guard,
hard-asserted at Diff 1 and to be hard-consumed by the generator); CONTEXT_VALUE 13; CONTEXT_SUBGROUP 8;
+ ruled context directives for MENOPLAN (proxy) and PLSA_QM (bound-only).
PREVIEW (shape of the regenerated marginal set, indicative): 46 firm candidates (15 blended + 31
single-base) + 2 new-anchor judgments + 25 anchored-but-unparseable rows needing STRUCTURED base fields
at Diff 2; 4 statutory floors; 166 context/EST. NOT the expected shrink below 45: the clean register
supports roughly as many marginals as the spike file applied, but the composition changes completely —
the 21 defective spike marginals die, replaced by properly-based blends. Preview parse is regex-grade
(it mis-paired all/large vs SME/large on ~5 rows, e.g. EAP 0.765 vs correct 0.727) — deliberate evidence
that Diff 2 must read structured base fields, never parse anchor prose.
NEXT GATES: Diff 2 (generate spike file from clean register; ruled orderings move to their own key —
phantom hygiene by construction) STOPS for David after the generated file + final marginal table.
Diff 3 (re-seed + full G1-G10 + run_gates) approved separately on the regenerated file. Live DB
untouched throughout Diff 1 (233,288 answers; current seed provisional — pipeline/UX demo only).

## Anchor-corrected reseed from the generated marginal set (Diff 3 of the rebuild, 16 July 2026)
Applied live: reseed from generated_marginals.json (Diff-2 David-approved final table) via the
rewired reseed_engine (inputs: generated_marginals.json + ruled_orderings.json; anchored_spikes.json
dead — kept on disk only so legacy imports don't crash). 37 marginals applied at max_dev 0.0041;
20,677 cells re-paired live (append-only history discipline); answers count unchanged 233,288;
non-reward book hash-identical. THROWAWAY GATE FIRST (ruled): qa_reseed 9/9 (G2 4, G3 0.177,
G4 0.515) + run_gates 10/10 on the reseeded throwaway BEFORE the live write; post-write live
matched the throwaway exactly (same G-scores, same cell counts) and run_gates 10/10 again.
The corrected seed is MORE coherent than Diff 9's (G4 0.427 -> 0.515, G3 0.131 -> 0.177).

THE FULL CORRECTION ARC (Diffs 1-3): register clean (20 mis-maps re-homed/cleared, PLSA fabrication
resolved into a sourced upper bound, 2 supersessions, 4 parks) -> generator (structured-fields-only,
verbatim fabrication guard, POLARITY guard, orderings-required guard, cohort blend (SME*30+large*190)
/220) -> reseed. FIVE PREVENTED SILENT DEFECTS beyond the original 21: the 4 no-lean-pole hard errors
at Diff 9, and FAM_001's polarity inversion (source figure 0.33 was the LEAN share; ships at 0.67 with
positive_from — caught only by the ruled source check; the polarity guard now inverts-or-fails on any
negative-pole extraction). COMPOSITION CHANGE (the point of the rebuild): EAP 0.309 -> 0.727,
CIC 0.629 -> 0.379, life assurance 0.807 -> 0.561, PMI-offer 0.628, pension-match 0.514; the 21
defective spike marginals are dead; 37 register-sourced marginals stand (31 A / 6 B).

LEAN-SIDE SEMANTICS (positive_from, ruled): the prevalence reshape's lean POLE generalised to a lean
SIDE (all rungs below positive_from). Exactly 4 ruled rows carry it (HOL_001 '25-27 days',
SICK_001 'Enhanced OSP', SICK_004 'No waiting period', FAM_001 'Enhanced pay'); default (absent) =
first-rung lean = legacy behaviour, asserted for the other 33 so nothing regressed. Without this,
three marginals would have seeded the wrong quantity (share-above-threshold != share-not-worst).

SETTLED RE-FREEZE (ruled): frozen_targets.json re-frozen AT APPLY for EAP/PENSION_MATCH/FINWELL/
STRATEGY at the corrected distributions, with backup. The G7 baseline was RE-ESTABLISHED
POST-CORRECTION: the prior frozen values protected the defective seed (EAP frozen 0.67 vs seeded
0.309 — and NOTE, discovered in execution: qa_reseed's G7 settled check is RECORD-ONLY and its
anchored branch defaults --targets None, so G7 never actually enforced the freeze; the earlier
"G7 fails by design without re-rule" reasoning was wrong about the mechanism. The re-freeze is the
ruled RECORD; enforcement is a queued gate improvement). A future instance must NOT read the
re-freeze as a freeze violation — it is the ruled re-ratification against corrected figures.

GATE FIXES SHIPPED IN THIS DIFF: qa_engine_audit honored a hardcoded ROOT/lumi.db instead of
LUMI_DB (latent — invisible while gate copies were made FROM live; exposed by LUMI_GATES_SRC
pointing the suite at a reseeded throwaway; the audit was comparing pre-reseed answers to
post-reseed payloads) -> now honors LUMI_DB. REGEN_WHITELIST exact-count pins are SUPERSEDED by
newer ruled manifests (REW_INC_072's 2026-06-11 pin vs its Diff-3 ruled 0.15 marginal);
generated_marginals.json whitelisted as Diff-3 lineage per the only-ruled-manifests rule.
run_gates.sh gains LUMI_GATES_SRC (default unchanged: live).

QUEUED (not blockers): the two cross-source conflicts (EAP CIPD-H&W row vs REW_BEN_038 compendium
'10% all / 61-62% large'; income protection BEN_046 25% vs Drewberry-implied 66%) -> source-of-record
ruling at the register's next pass. The 25-row base-extraction table (anchored-but-unstructured rows,
currently context). G7 enforcement (targets file + settled comparison). level_distributions.json
remains UNAPPLIED by reseed() (B5 was never in the write path — Diff 9 shipped without it; open item,
not a regression). Current headline moves with the corrected marginals by design — the seed now says
what the register says.

## B5 level-distribution wiring — 3 applied / 13 dropped (Diff 10, ruled + applied 16 July 2026)
B5 (within-offerer level distributions) was specced at Diff 9 but never in the write path. Wired now
against the CORRECTED live seed (cda0322), FILTERED not blanket: level_distributions.json was built
against the OLD register and mostly died with it — a blind 3-agent verification pass (not shown prior
classifications) ruled 3 HOLD -> applied / 13 DROP. David: "my '10 clean' was the old-register artefact
showing through."
APPLIED (ruled band maps, verbatim-or-ruled, b5_levels_ruled.json):
- REW_BEN_045 (life multiple): positive side 2x 0.379 / 3x 0.336 / 4x+ 0.284 (5x+ merged into 4x+);
  1x fed at ZERO (never from fixed/other — that would be parsing); 0.420 unmapped conditional mass
  (fixed sum + other) dropped by renorm; boundary hard-pinned to shipped 0.5607.
- REW_BEN_FAM_002 (maternity weeks): 1-12 0.462 / 13-26 0.538 among the shipped 0.544 offerers; band
  4-13 -> live 1-12 as nearest verbatim rung; upper rungs (27-39/40-52) EMPTY BY RULING — honest, not
  a gap; do not hold for a source that may not exist.
- REW_BEN_HOL_001 (leave days): TWO-SIDED — bands imply 0.714 positive vs the shipped 0.553 marginal,
  so B5 distributes WITHIN each side of positive_from (25-27 days) separately, never across. Positive
  0.600/0.233/0.167; lean 0.313/0.687 (merges 25+26-27 -> 25-27; 28 -> 28-30; 30+ -> More than 30).
DROPPED 13 (QA asserts ABSENCE, not just non-application): dimension-mismatch — SICK_001 (duration
bands belong to SICK_002), SICK_004 (months-of-service vs waiting-days), FAM_001 (weeks belong to
FAM_002), 046 (replacement-rate belongs to 048), PENSION_TYPE (ruled; THE nominal-incident metric);
ruled-context-full-reshape — SICK_002, 048, GAP_009 (set-not-pole), REC_CURRENCY (kinds);
binary-no-level — SICKDAYONE (also SETTLED-frozen), HOL_004, FAM_006; corrected-defect — HOL_006
(the service-uplift distribution the register clean re-homed to HOL_004).
THE TWO SMUGGLING CATCHES (why B5 is filtered-not-blanket): 046's dist source carries the Drewberry
"66% offer" — applying it would have injected the unruled side of the QUEUED cross-source conflict
ahead of its ruling; HOL_006 would have re-introduced the exact mis-map the register clean killed.
Both caught by the blind pass, both would have shipped as "realism".
ENGINE: ruled within-side apportion (largest remainder over ruled shares) overrides the
proportional-to-current split ONLY where a b5_levels_ruled entry exists; deterministic jitter
tiebreak sha256(qid|org) so identical-factor orgs never tie; who-offers boundary structurally
untouched (pos_n/lean_n from the marginal target as before).
VERIFIED: throwaway — B5 invariants ALL PASS (boundaries pinned to 4dp: 0.5591/0.5425/0.5539
pre==post; ruled bands hit within 0.005; absence holds 13/13); qa_reseed 9/9 (G4 0.515, G3 0.177,
G2 4 — level variance did not move coherence); run_gates 10/10. LIVE — 119 cells written (the
surgical within-side footprint), answers 233,288 unchanged (append-only), non-reward book
hash-identical, live-vs-throwaway distributions EXACT on all 16 B5 metrics, qa_reseed 9/9 identical,
run_gates 10/10 (qa_engine_audit: hard failures 0, warnings 0). Backup
lumi.db.bak_pre_diff10_b5_20260716.

## Cross-source rulings — EAP + income protection (16 July 2026)
Both queued conflicts dissolved on CONSTRUCT, not a source coin-flip. ① EAP: CIPD H&W 2025 (67/78/39,
size-banded, grade A) RATIFIED canonical; seed 0.7268 / live 0.7273 / frozen match — no register edit
(the clean already removed Drewberry's 31%, which survives only in the dead spike file). Residual is
CIPD-vs-CIPD: 038's compendium 'EAP 10% all' is the Reward Survey's standalone-paid-BENEFIT construct
vs H&W's wellbeing-PROVISION measure — annotated construct-divergent on 038, never reconciled.
② Income protection: CIPD 25/40/15 (offered-to-all, size-banded, grade A) RATIFIED canonical per the
size-banded-beats-all-size principle (cohort 86% large); GRiD ~42% large independently corroborates
CIPD's 40 — triangulation, not side-picking. Drewberry's 66% is ANY-OFFER on a broker-skewed base:
different quantity, corroborating context at 048 (whose own text already says so). AMENDMENT (David):
the shipped 0.366 uses offered-to-all rates on an any-offer question — a conservative floor and a
milder instance of the rebuild's defect class — tracked as an EXPLICIT OPEN ITEM (parked_anchors.md
OPEN RE-ANCHOR QUEUE + 046 notes): re-anchor to a clean any-offer source (GRiD) next register pass;
scheduled, not someday; not a re-seed now.

## RED_TERM_01 NA-flag correction (18 July 2026)
The 'Enhanced redundancy pay (varies by grade/tenure)' option carried is_na=true while its
substantive siblings were false — a mis-set skip flag on a real answer (found in the Diff-10-era
base25 extraction, RED_TERM_01 flags column; register: live/market/↑, enhanced options = positive
pole). Flipped to false via double-guarded server/migrate_red_term_01_na_flag.py
(--write --confirmed-by-david), echoed into data/lumi_questions.csv; answers append-only
(content-hash identical), backup lumi.db.bak_pre_redterm01_naflag_20260718. Aggregate NUMBERS
unmoved (select_block counts all matched options either way) — the flip restores the 5 affected
orgs to every is_na-honouring base: client real-option views, reseed-engine NA-skip exclusions,
qa_plausibility spine labels. DELIBERATELY KEPT: scoring_config_json.na_codes still excludes the
option from scoring — its rung on the 0/50/100 ladder (vs 'Discretionary') is the ordering the
register marks as needing DAVID'S RULING; removing it unruled would mis-score those orgs at 0.
OPEN ITEM for the next register pass: rule the ladder placement, then score the option.
Re-aggregated snapshot 1; qa_overview 0 failures; qa_release 0 failures; 8060 restarted fresh
(clean bind, flags verified on the served benchmark card).

## 25-row base-extraction fold — 9 promotions, 46 marginals (Diff 11, ruled + applied 18 July 2026)
The follow-on David queued at Diff 1: the 25 register rows whose bases were unparseable by rule,
extracted to a ruling table, ruled row-by-row (8 promotions + REM_PAY_001 held-then-promoted, 2 holds,
14 context). Folded into structured_bases.json + ruled_orderings.json; regenerated; delta approved;
commit 1aabdde.
THE 9 (all all_only): FAI_089 0.53 (A); HOL_003 0.559 (B, inverted from 44.1% no-offer);
REC_IMPACT 0.436 (C, inverted from 56.4% don't-track); FERTLEAVE 0.22 (A, pf 'Paid dedicated
leave'); FAM_008 0.86 (B, 4-rung discovery, pf 'Partially paid (case-by-case)' — any-paid read
RULED); EQUALPAYAUDIT 0.35 (A, pf 'Annually', Ad hoc excluded); CAR_STATUS_01 0.35 (C, grade-based
figure matches wording); PAYTR_02 0.40 (A, 'always' only); REM_PAY_001 0.64 (A, off hold).
REM_PAY_001 ORDERING RULED: 'Treatment varies by role or case' is ORDINAL SECOND-LEANEST
(guarantees nothing -> less protective than a universal glide path; conservative, under-claims
protection), ruled over the non-ordinal-permanent-context alternative — placement judgment on
record. Supersedes the partial 2/6 migrated ordering. NA/DK structural skips; live is_na=true on
'varies' coexists (engine reshapes by ordering membership only). pf 'Base pay is protected' per the
ruled extraction semantics (64% IS the protected share, "have not and do not intend to").
Live landed 60 protected / 34 varies / 61 NA / 14 DK — 0.638 achieved on n=94 in-scope.
POLARITY GUARD COMPLETED (ruled): explicit structured `polarity` field per base row takes
precedence over the target_semantics substring heuristic; substring reading of adjacent prose was
a soft form of the banned prose-inference. Caught live: first regeneration inverted FAI_089
0.53->0.47 off "NEGATIVE POLE complement" prose describing its COMPANION figure; explicit field
fixed it; heuristic retained as legacy fallback only. Guard also hyphen-normalises ('negative-pole').
PRINCIPLE SCOPED (ruled): unconditional-rung applies to FREQUENCY-SOURCED BINARIES only
(always/sometimes/never, regular/ad-hoc -> positive = the unconditional rung; stops 'sometimes X'
counting as 'does X'). It does NOT reach any-offer-sourced ordinals: case-by-case paid provision IS
paid provision (FAM_008 distributes across both offering rungs).
REGISTER (ledger-asserted, grade+notes only): FAM_008 A->B (dated ~280 private-skew base);
CAR_STATUS_01 ->C + ruled-0.35 caveat (2021, n~217). HOLDS STAND: FAM_011 (middle-rung figure),
NEURO (source self-disclaims UK-representativeness — disqualifying).
VERIFIED: regenerated set 46 marginals / 3 floors / 194 context, prior 37 HEAD marginals
byte-identical, all guards pass. THROWAWAY FIRST: qa_reseed 9/9 (G4 0.462, G3 0.15, G2 4);
run_gates 10/10. LIVE (LUMI_RHO=0.40, --profiles seed_personas_220.json --write
--confirmed-by-david): 4,909 cells re-paired across 201 questions (46 prevalence / 39 context /
1 floor), marginals max_dev 0.0041, answers 233,288 unchanged (append-only), non-reward book
hash-identical, live-vs-throwaway distributions EXACT on every cell of the book, qa_reseed 9/9
identical scores (JSON diff = list-ordering artifacts only), re-aggregated 943 payloads, 8060
restarted fresh, run_gates 10/10 (qa_engine_audit: hard failures 0, warnings 0). Backup
lumi.db.bak_pre_diff11_base25_20260718. NOTE: G4 worst-pair moved 0.515->0.462 with the 9 new
marginals in the pool — still 1.5x the 0.30 floor; expected direction (more anchored marginals =
less latent freedom), not a regression signal.

## Freeze gate wired — Check C enforcing, suite 10->11 (Diff 12, ruled + applied 18 July 2026)
FINDING (corrects the "G7 is record-only" framing): the freeze-enforcement logic EXISTED and was
CORRECT — qa_plausibility.py Check C, drift vs frozen_targets.json — but was NEVER WIRED into the
write-time suite. qa_reseed G7 records settled marginals BY DESIGN and defers to Check C; Check C
was in neither run_gates.sh nor qa_reseed. So the real freeze gate never ran during a write: every
write this session passed 10/10 with the freeze unchecked. It never bit because writes set frozen
values correctly on purpose — but an accidental drift would not have been caught. THE GUARD WAS
DARK. Proven live in the negative test: on a breached throwaway the OTHER TEN GATES ALL PASS —
nothing else in the suite sees a freeze drift.
FIX (wiring, not build — commit 95e43ba): qa_plausibility runs as GATE 11 in run_gates.sh
(root-dir block, direct-DB, nonzero rc = FAIL). FAILURE SEMANTICS RULED TIERED: settled-frozen
(= frozen_targets.json keys, 8) hard-fail on ANY per-option drift >0.001 — hand-ruled, immovable;
register marginals (generated_marginals.json, 46; the 4 frozen-overlap rows take tier-1 precedence
-> 42 checked) fail only >5pp — they keep legitimate ±4ppt reshape freedom. Tier-2 achieved-share
mirrors the engine's marginal branch exactly (scope = ordering membership, lean = rungs below
positive_from, first-rung default, worst_option combos, <5 in-scope skip).
SINGLE SOURCE: frozen_targets.json keys ARE the settled set; qa_reseed.py and qa_plausibility.py
both derive SETTLED from it — the three drift-prone copies are now one. Missing file is FATAL in
the gate (a silent {} fallback would put it back in the dark). LUMI_DB honoured (the qa_engine_audit
hardcoded-db bug class, spec #4): the gate validates the suite's throwaway pre-write and live
post-write, never implicitly live — proven by one script giving three verdicts on three env-selected
DBs. qa_plausibility.py + qa_reseed.py enter the repo (previously untracked while load-bearing).
NEGATIVE TEST (mandatory, evidence in freeze_gate_negative_test.md): perturbed throwaway (EAP
5 rows -> 2.27pp; REC_IMPACT 15 rows -> 6.9pp) fails BOTH tiers, suite FAIL(1) exit 1 (zsh EXIT
trap verified to preserve failure status through teardown); 2.31pp register perturb still PASSES
(freedom preserved, tolerance proven two-sided); clean throwaway 11/11 incl. qa_plausibility;
live gate run PASS (settled max drift 0.005pp, marginals max 0.41pp). All perturbations on scratch
copies only; live asserted untouched (233,288; EAP 160; REC_IMPACT 96). qa_reseed 9/9 unchanged
after the single-source change. GATE-WIRING ONLY: no reseed, seed unchanged at the 1aabdde state.

## #4 closed — audit env-driven confirmed + instrument track sweep (18 July 2026)
① qa_engine_audit LUMI_DB: fix confirmed in place (server/qa_engine_audit.py:42, env-driven,
comment-dated 2026-07-16) — same pattern the freeze gate now uses. ② Standalone re-run against
live at 95e43ba (LUMI_DB=absolute live path, keyless): hard failures 0 | warnings 0; app-vs-DB
cache freshness 336==336. MASKING ANALYSIS: nothing was hidden by the pre-fix hardcode. Proof the
fix was live for this session's arcs: the recorded gates_d3pre FAILURE — the audit failed on a
pre-write throwaway precisely because it read the throwaway's reshaped metrics (a live-hardcoded
instrument could not have produced that result). For any run predating the fix, every write in the
discipline verified live==throwaway EXACT at apply time, so at each gated moment the audit's
verdict held for both databases regardless of which it read. The 0/0 standalone run closes the
present tense. ③ TRACK SWEEP (the "instrument untracked" class, third occurrence): enumerated the
full load-bearing set — gate harness, 10 gate suites + aggregate/db, 4 seed instruments, 13 seed
inputs. Only org_profiles.json + org_profiles_inferred.json were untracked (qa_reseed's DEFAULT
G2/G3 profile inputs; qa_plausibility's latent source) — committed. Every gate and seed instrument,
and every input they read, is now version-controlled. QUEUE EMPTY: #3 shipped-and-proven (95e43ba),
#4 closed clean. The seed stands at the 46-marginal 1aabdde state — correct, realistic, and gated
by instruments that are themselves in git and proven-enforcing.

## By-level matrix correction — EST baselines, sector gates, verdict suppression (Diff 13, ruled + applied 18 July 2026)
ORIGIN: David's live-UI expert review. The by-level matrix charts ("X by seniority level") ran on ONE
hardcoded multiplier ladder (regen_priors MATRIX_DRIVERS) applied to every metric identically — a
category the entire anchor/register/generator correctness pass never examined. Maximally coherent,
therefore invisible to every coherence gate, and WRONG three ways: shape (LTI is a cliff, leave is
flat), altitude (LTI exec ~2x under; pension ~2ppt low at top, 4pp over at the statutory floor),
and sector existence (the intended charity/public gating had LEAKED: 7 gated orgs answered bonus,
6 held LTI Yes rows). STEP 0 enumerated 25 by-level matrices fresh from the questions table
(17 reward + 8 dormant Attract/Growth), confirmed NO leave-by-level matrix exists (baseline #4
vacuous — parked), and found a live 58-org incoherence: 98 car-matrix answerers vs only 40
overlapping CAR_STATUS_01's 74 Yes.
RULINGS (all David, 2026-07-18): ① pension national ladder all 220 (public-sector DB realism
deferred); ② car population = CAR_STATUS_01 Yes-set 74; ③ LTI population 74 (charity/public + the
3 SMEs gated); ④ companion corollaries as drafted (PENS_EMP_MAX = typical + 1-4pp headroom;
bonus-max gate-only + max>=target, 21 lifts; LTI values cliff-masked, medians move 125->150/95
because survivors skew senior — flagged); ⑤ leave parked (no target metric; retail/hospitality
20-day band = future gated HOL_001 diff). CONSCIOUSLY ACCEPTED: all-org LTI Board reads 30.5% not
37.7% (honest after gating; in-population rate 90%); FULL verdict suppression on all 11 by-level
numerics (no soft "vs practitioner baseline" channel).
APPLIED (commit 70a7092; migrate_diff13_bylevel_baselines.py --write --confirmed-by-david):
pension 17/12/10/8/8/3/3 exact (offset ladder, AE floor pinned, monotone asserted); employer max
20/15/12/10/10/5/5 exact; car 12k/10k/7k/5k/4k on the 74 (Manager rare n17, Sup/Front ABSENT never
0); bonus 40/30/20/15/10/3/1 on 157 (thinning preserved, bottom rows 1-8/1-3 median-pinned);
LTI cliff 67 Board / 52 Director / zero below, latent-ranked nested assignment (G10 coherence
held). Values from expert_baseline_by_level.json (EST, "practitioner benchmark - D. Whitfield") +
diff13_derivation_rules.json — no numbers in code. Seed orgs ONLY: the Tester signup org surfaced
in dry-run n=221 -> selective delete + real-org rows asserted byte-identical.
VERDICT SUPPRESSION (the integrity rule): EST-grade data renders NO measured-market claim.
Two coordinated layers, both reversible at real member data: curated market_position_config.json
11 entries direction->neutral (SURGICAL edit, _diff13 breadcrumbs) + questions.polarity->neutral
(kills the cardPosition legacy-polarity fallback on tiles). 55 directional metrics remain.
LANDMINE (open decision, David rules reconcile-vs-retire separately): gen_market_position_config.py
has DRIFTED from the curated config — my --write regen rewrote 1,716 lines, clobbering David-refined
rulings (Governance non-competitive flag, REW_PAY_005 Practice, the 8-domain taxonomy). Caught by
qa_hero/qa_focus/qa_overview going red on the throwaway; restored from git; flips re-applied
surgically. Curated file is HAND-OWNED; the generator is QUARANTINED — never --write it. Same class
as the Diff-9 persona-config clobber. (Generator's RESOLUTIONS + neutral handling were still
corrected for internal consistency.)
VERIFIED: throwaway first — qa_reseed 9/9 (G2 4, G3 0.15, G4 0.462, all unchanged from Diff 11),
run_gates 11/11 incl. freeze gate + engine audit (diff13_seed_manifest.csv whitelisted,
only-ruled-manifests rule). LIVE: backup lumi.db.bak_pre_diff13_bylevel_20260718; answers
233,288 -> 232,809 (delta -479 exactly as approved: car net -177, bonus-family gate deletions,
LTI tails); 7,272 history rows; non-touched book hash-identical; polarity flips 11/11; post-write
live-vs-throwaway EXACT on every distribution cell; manifest byte-identical to committed;
re-aggregated 943 payloads; 8060 fresh; post-write run_gates 11/11 green.
DEFERRED (logged in diff13_derivation_rules.json): public-sector pension realism; HOL_001 sector
band; expert max figures for the three derived companions; Car-41 persona discrepancy; the
generator-drift ruling.

## Config generator retired — archive-and-neuter (ruled + applied 18 July 2026)
RULING: gen_market_position_config.py is RETIRED. The curated data/market_position_config.json is
the SOLE SOURCE OF TRUTH, hand-owned, refined via hot-reload. Rationale: the generator drifted
1,716 lines from the curated artifact and the clobber class hit twice (Diff 9 persona config,
Diff 13 market-position config — Governance non-competitive flag, REW_PAY_005 Practice, 8-domain
taxonomy all reverted by one --write). Gates caught both; the standing risk is now closed
structurally, not left as a quarantine note.
MECHANISM (archive-and-neuter, not delete — deliberate): the file stays in the repo for
historical/reference value (it documents how the config was originally derived); --write
hard-exits 2 printing the retirement message + pointer to this entry; the OUT_PATH json.dump is
REMOVED from the code entirely (write path structurally impossible, not just gated); dry-run
analysis mode still runs (exit 0). Reviving or reconciling requires a deliberate David ruling.
CALLER SWEEP: nothing invokes the write path — run_gates.sh and all scripts clean; references are
documentation-only. VERIFIED: --write exits 2 and writes nothing; dry-run exits 0; config
byte-identical after both (cmp + clean git diff); seed untouched at 232,809. Code-quarantine diff
only (commit alongside this entry). FOR FUTURE INSTANCES: do not re-derive market_position_config
from any generator — hand-edit the curated file surgically, per ruling.

## Verdict authority — peer claims suppressed on 222 unanchored metrics, 2 retired (Diff 14, ruled + applied 18 July 2026)
WS1 + WS6 of David's pay/pensions audit. SCOPE RE-TARGETED with David's confirmation: the audit
prompt named the "No signal" pill, but that pill is the signals-system CLEAR state (org-relative,
runtime — "nothing flags here"), not an anchor flag. The honest scope is DISTRIBUTION AUTHORITY:
273 active reward metrics rendered directional peer verdicts; only 51 have ruled distribution
authority (42 active register marginals + 8 settled-frozen + 1 floor). The other 222 (89 never in
any register incl. the whole REW264/REW265 wave; 96 register-unanchored; 31 register-anchored
CONTEXT — a paper headline is not distribution authority; 6 EST-class) made measured-market claims
on engine-prior distributions. 81% of platform verdicts were unanchored. RULED: suppress all 222,
keep 51; verdicts get EARNED BACK by anchoring (round-2 corrections + member data), never
re-rendered. CONSCIOUSLY ACCEPTED: verdicts 273->51; Pay reads 4-thin, Pensions 3, Benefits 3;
no domain falls below domain_min_polarised=3; thin-but-true beats rich-but-fabricated.
THREE SUPPRESSION LAYERS (+1 seam found in test): ① curated market_position_config.json —
220 entries direction->neutral + unbenchmarked:true + _diff14 breadcrumbs (surgical, hand-owned
file; keepers byte-equal, verified key-by-key vs HEAD). ② questions.polarity->neutral (219
flipped, 1 already neutral) + data/lumi_questions.csv echo (112 rows; 108 flips absent from the
CSV = the documented REW263/264/265 DB-origin-lineage families). ③ NEW unbenchmarked channel:
assemble_card passes the flag; unbenchmarked cards render the distribution but NO position pill,
NO "X in 10 similar organisations" lead ("peer distribution shown for information only" +
Unbenchmarked chip), NO numeric readout/percentile and NO score percentile/peer_p50 — the numeric
and score forms of the same measured-market claim, suppressed as the same class. ④ SEAM: score
items take polarity from scoring_config, bypassing layers ①② — caught live when a 'behind' signal
fired on suppressed PROP_168a6213 (qa_hero red); closed at the single choke point positions._item,
which now consults the unbenchmarked authority for EVERY item kind. Signals, briefings, pools,
gap register and board pack all inherit through _item.
RETIRED (status=retired, release_retired='2026.4', SEED answers deleted after answers_history
snapshots, payload rows removed; all 436 rows asserted seed-org-only): ① PROP_dff9a2a5
pay-increase award rate — fictional-practice distribution (a run review ~always covers everyone;
the middle bands measure nothing) that carried a LOWER-THAN-MARKET verdict. C-FACTOR NOTE (ruled,
expected-not-surprise): PROP_dff9a2a5 was a C-term in metric_factor_map.json and is REMOVED — the
next reseed's S-factor composition shifts accordingly. Register row annotated RETIRED (anchor kept
for the record); ordered_scale_routing + rew_live_meta + signal_lenses signal_labels entry (David
say-so, _diff14_note breadcrumb; lenses/thresholds untouched) unwired. ② REW264_PEN_CONTRIBTIER
service/age-linked pension escalation — age-linked = Equality Act 2010 age-discrimination risk;
service-linked escalation extinct post-DC/AE. RAILS-BYPASS HYGIENE FINDING: it was in NO
release_questions row — the 2026.4 seeding bypassed the release rails; recorded here for the next
rails pass. RED_TERM_01's pending CSV echo was committed FIRST as its own micro-commit (695591c),
keeping this diff's history clean.
qa_engine_audit hardened with the diff: RETIRED_LINEAGE documented skip (ONLY ruled retirements —
a silent retirement still fails L1) + the L2 percentile spot excludes unbenchmarked metrics and
FAILS explicitly if a benchmarked metric stops serving its percentile (suppression over-reach
guard, both directions held).
VERIFIED: throwaway first — qa_reseed 9/9; run_gates 11/11 after the ripple fixes (qa_hero signal
leak + audit lineage/spot — the anticipated consumer ripple, no data surprises; throwaway DB
unchanged across the three suite runs). LIVE (backup lumi.db.bak_pre_diff14_verdictauthority_
20260718): answers 232,809 -> 232,373 (-436 exactly as diagnosed); non-target book hash-identical;
keepers' polarity untouched; post-write live-vs-throwaway EXACT (every distribution cell + every
questions-table row); suppress set 220/220 neutral on live; both retirees status=retired/2026.4
with 0 answers; re-aggregated 943 payloads; 8060 fresh; post-write run_gates 11/11. Commit 3960efd
(+ 695591c micro-commit). Cache v419.
ROUND 2 QUEUED (David's expert numbers pending): value corrections — under-peaking, option
redesign, gating. Verdict re-earn path: anchor -> marginal -> the unbenchmarked flag comes off.

## Under-peaking + option redesign + 1 retire (Diff 15, six rulings + applied 18 July 2026)
Pay/pensions audit round 2. PREMISE CORRECTED at diagnostic (David confirmed): NONE of the four
Part-A metrics was in Diff 14's 222 — REW_PAY_005 is strategy-config (Diff 4: never pools),
EXT_REW_GAP_010 + REW265_PAY_RANGEMAX were never directional, PENSION_TYPE is settled-frozen and
never lost its verdict. ANCHORED ≠ DIRECTIONAL, ruled and kept: GAP_010/RANGEMAX get correct ruled
distributions and render as PREVALENCE, no verdict — "where staff work" and "range-max policy"
have no honest better/worse pole.
NEW MECHANISM (ruling ⑥): ruled_distributions — full-distribution reshapes. Generator emits the
section from structured_bases ruled_distribution entries; the ENGINE needs no change (non-marginal
metrics context-route COUNT-PRESERVINGLY, so ruled dists survive future reseeds by construction);
freeze gate tier-2b checks per-option drift at the 5pp register line. Four members: REW_PAY_005
3/7/70/15/5 (ruling ①, reshape only, stays config; N/A-Don't-know stripped, 28 answers n-excluded
220->192); EXT_REW_GAP_010 78/4/2/1/15 (ruling ②; Don't-know stripped, 4 n-excluded 165->161);
REW265_PAY_RANGEMAX 60/16/16/8 (ruling ②; conditional derivation 40% have-ranges x 40/20/40;
FTE-gate round 3); PROP_fe1a29ec 60/30/10 (ruling ④).
PENSION_TYPE RE-FROZEN (ruling ③, EAP retarget precedent — G7 BASELINE RE-ESTABLISHED): DC
0.8455 -> 0.95, DB 0.0318, Hybrid 0.0182 (achieved 209/7/4 over 220); 'None' option REMOVED from
the bank — auto-enrolment makes a no-scheme employer a NON-COMPLIANT STATE, not a data point.
National-for-all; public-sector DB carve-out stays queued behind the sector-tag pre-condition.
PROP_fe1a29ec 46-SET OPTION SURGERY (ruling ④): Yes/Partially/No -> formal/structured / informally
only / no benchmarking; the Drewberry 0.495 share-marginal SUPERSEDED (the construct died with the
options) — marginals 46->45, prior 45 byte-identical; scoring ladder re-mapped mechanically onto
the same 0/50/100 shape; register grade B->EST; keeps higher_is_better (ordered maturity scale).
REW_PAY_006 logged as a construct-overlap dedup candidate. FTE-gradient (15@50 -> 60@500 ->
90@5000) is round 3; seeded cohort-centre 60/30/10 flat, flagged.
REW265_PAY_PAYCOMMS REDESIGNED (ruling ⑤): single_select -> by-level matrix (Letter + manager
conversation vs Letter only), per-level conversation 90/90/90/80/70/50/20 nested-by-latent
(nesting asserted), 220 -> 1,540 answers, v2.0, STAYS verdict-suppressed EST (Diff-13 discipline —
modelled gradient, no measured-market claim). Old options dumped 66% into 'Varies' — replaced.
RETIRED: REW264_PEN_PENLEAVEGAP (class 6) — pension is a % of pensionable pay; during UNPAID leave
there is no basis to contribute from; the one meaningful version (full-salary contributions during
PAID statutory leave) is excluded by the question's own scope. David declined the reframe. SECOND
2026.4 rails-bypass instance (no release_questions row) — strengthens the rails-pass case.
STANDING RULES RECORDED (all future work): ① NO Don'T-KNOW OPTIONS — unsure respondents leave
blank (n-excluded); a Don't-know option inflates itself and dresses non-answers as answers;
stripped here from REW_PAY_005 + GAP_010, never added again. ② REWARD MATURITY SCALES WITH FTE —
sophisticated-practice prevalence is FTE-linear (benchmarking, market pricing, formal ranges, TRS,
equal-pay audits family); one SHARED gradient mechanism, round 3. ③ SECTOR-TAG AUDIT IS A HARD
PRE-CONDITION for every sector-gate diff (public-sector DB, tips, bonus/LTI refinements): verify
the 220 seed profiles' sector tags BEFORE gating on them. Also parked per ruling: office
attendance = SOURCE, DON'T ESTIMATE (CIPD/ONS research task; redesigned options approved,
unapplied — register discipline: don't estimate what you can source).
VERIFIED: throwaway first — dists exact + nesting asserted (1,480 history rows), qa_reseed 9/9,
freeze gate PASS (re-frozen PENSION_TYPE tier-1 at 0.005pp; 4 ruled dists tier-2b), run_gates
11/11. LIVE (backup lumi.db.bak_pre_diff15_underpeaking_20260718): answers 232,373 -> 233,441
(-32 DK, -220 retire, +1,320 matrix rebuild); non-target book hash-identical; post-write
live-vs-throwaway EXACT (every distribution cell + every questions-table row incl. options/
scoring/type edits); manifest byte-identical; re-aggregated 943 payloads; 8060 fresh; post-write
run_gates 11/11. Commit e2227ab. ROUND 3 QUEUE: sector-tag audit (pre-condition) -> FTE-maturity
gradient mechanism -> gating workstream (tips, FTE-gradient family, allowances) -> office-
attendance sourcing -> GRiD/046 re-anchor -> REW_PAY_006 dedup -> public-sector carve-outs.

## Sector-tag audit — round 3 step 1, the sector-gate pre-condition (ruled + applied 18 July 2026)
Two-directional correctness audit of the 220 seed profiles (every future sector-gate fires on
these tags; a mis-tag makes the gate correct the wrong orgs). RULED RE-TAGS APPLIED (3): Alderstead
/ Severnbourne / Brightstone Trust — subsector "Public Health Provider" = NHS-Trust-style public
body; Healthcare & Life Sciences -> Public Sector & Government, applied consistently in
org_profiles.json + data/seeded_orgs.json + orgs.industry. Sector cuts now Healthcare 6 (holds the
n>=5 floor) / Public Sector 15. KEEPS verified correct: Hawvale (Mfg), Marshbrook (Mfg), Norpoint
(Fintech), Langwick (Biotech) — commercial companies named "Trust". NOTE: David's keep-list named
"Kingswood (Prof Services)" — NO such org exists in any profile (phantom from the earlier hand
scan; nothing to act on). FULL SWEEPS CLEAN: reverse check (public/charity-tagged with commercial
substance) surfaced only the 2 social enterprises below; public-pattern scan
(council/authority/NHS/academy names in commercial sectors) found ZERO beyond the ruled 3;
hospitality both directions structurally sound (tips-gate population correct); FTE_Band and
Industry 0 missing across 220.
FIELD RECOVERY (Diff-9 field-loss class, lossless): all 62 authored personas were missing
Workforce_Frontline_%/Shift_%/Unionised_% in org_profiles_inferred.json — the values exist 62/62
in seed_personas_220.json and were copied VERBATIM (186 values). No invention.
AWAITING DAVID (presented, not applied): ① 21 authored personas carry sector-IMPLAUSIBLE
Frontline% AS AUTHORED (source = seed_personas_220 itself, not field loss): hospitality/retail/
logistics/manufacturing orgs at 2-28% frontline (e.g. Dunbrook Hospitality Group 2%, Glenbrook
Restaurants 19%, Northgate Transport 2%), one Technology at 66%. These feed the tips/shift/
office-cadence gates — re-author or rule a sector-floor imputation before the gating round uses
Frontline%. ② Ravenside Trust Ltd + Thornmere Social Enterprise Ltd: commercial-form social
enterprises under the charity tag — recommend KEEP (social-enterprise substance), but
bonus-existence for social enterprises is David's call at the bonus/LTI gate refinement.
VERIFIED: answers hash-identical before/after on throwaway AND live (profile re-tags only — no
seed change, asserted); throwaway run_gates 11/11; live applied (backup
lumi.db.bak_pre_r3s1_sectortags_20260718), re-aggregated 943 payloads, 8060 fresh, post-write
run_gates 11/11. THE GATING WORKSTREAM IS UNBLOCKED subject to ① for Frontline%-dependent gates;
sector-membership gates (bonus/LTI charity+public, DB carve-out, tips-hospitality) can proceed on
the corrected tags now.

## Frontline floors/caps + social-enterprise keeps — sector-tag pre-condition CLOSED (18 July 2026)
RULING ①: Frontline% is a GATING INPUT, not a member-facing value — sector-floor imputation
suffices. Applied: floors Hospitality 60 / Retail 65 / Logistics-Transport 55 / Manufacturing 45 /
Healthcare 55 / Construction 55; caps Technology 15 / Financial Services 15 / Professional
Services 15 / Media 20; unlisted sectors keep authored values; in-range orgs untouched. 54 ORGS
ADJUSTED (39 authored personas + 15 real-org profiles, the real-org 15 mirrored into
data/seeded_orgs.json): full per-org list in commit; headline corrections Dunbrook Hospitality
2->60, Glenbrook Restaurants 19->60, Eldenland Retail 2->65, Northgate Transport 2->55, Glenwick
Digital 66->15 (the one over-cap office org). Originals preserved per-org in
_r3s1_frontline_imputed markers. seed_personas_220.json deliberately NOT edited — it remains the
authored artifact; org_profiles.json/org_profiles_inferred.json are the CORRECTED GATING AUTHORITY
for Workforce fields (a future profile rebuild from personas must re-apply the ruled floors/caps —
noted to prevent the clobber class). NOTE: the ruled floors were TIGHTER than the audit's flag
thresholds, so 54 adjusted vs 21 flagged — e.g. Construction (not in the flag scan) gained 14
raises, borderline cases like Valefield 59->60 and Moorwood 64->65 snapped to floor. Expected, per
the ruling's "raise ANY org below the floor".
RULING ②: Ravenside Trust Ltd + Thornmere Social Enterprise Ltd KEEP charity/non-profit —
commercial-form social enterprise is non-profit in substance; excluded from the bonus/LTI gate
like other non-profits. No change; on the record for the gate build.
INTEGRITY: no DB writes (Frontline% lives in JSON only) — answers 233,441, book sha256
ccae76d1b97de7bd unchanged, asserted. Frontline% FEEDS THE LATENT SPINE (reseed_engine:146 front
term; :170-171 shift flag + tronc eligibility Frontline%>40 for Hospitality/Retail) — future
reseeds will see the corrected values (tronc-eligible pool grows with the hospitality floor
raises: expected, correct direction); full run_gates 11/11 re-run with the imputed profiles;
qa_reseed 9/9 on live.
SECTOR-TAG PRE-CONDITION CLOSED. The gating workstream is fully unblocked on verified profile
data: sector membership verified (3 trusts re-tagged, zero hidden public bodies, hospitality
sound both ways, social enterprises ruled), Frontline%/Shift% populated 220/220 and
sector-plausible, FTE_Band complete. Round-3 queue proceeds: FTE-maturity gradient mechanism ->
gating workstream (tips/bonus-LTI refinement/allowances) -> office-attendance sourcing ->
GRiD/046 re-anchor -> REW_PAY_006 dedup -> public-sector DB carve-out.

## Maturity-gradient mechanism + benchmarking pilot (r3s2, three rulings + applied 18 July 2026)
PRINCIPLE MECHANISED: sophisticated reward practices scale with HR_MATURITY (the profiles' rating),
not raw FTE — David trusts the profiles and accepts a non-clean size gradient (a small-but-Advanced
org correctly reads high). PRE-CONDITION: HR_Maturity recovered 62/62 VERBATIM from
seed_personas_220.json (same field-loss class as the workforce recovery; 220/220 populated, zero
invention; org_profiles are the gating authority — rebuilds must preserve recovered fields).
Cohort mix: Basic 19 / Developing 102 / Advanced 99.
THE MECHANISM (general, family-reusable): per-metric three-level anchor maps declared in
structured_bases (maturity_anchors: positive_option, anchors, remainder_options, per-band
remainder_ratio, optional sector_gate) -> generator emits a maturity_gradients section ->
reseed_engine.maturity_assign() is the SINGLE implementation, called by both the engine's new
routing branch (future reseeds re-derive band structure — plain context re-pairing would drift it)
and the pilot migration. Sector-gate COMPOSES BY CONSTRUCTION: gated orgs are dropped from
assignment and absence is never re-created (engine apply only touches newmap members). Freeze gate
tier-2c: per-MATURITY-BAND drift vs anchors at the 5pp line (sub-floor bands skipped honestly).
Top-performer pricing and formal ranges plug in later with their own anchors — no bespoke code.
RULINGS: ① cohort formal 70.2% ACCEPTED — deliberate anchors (15/60/90) x the real 45%-Advanced
mix; a self-selected benchmarking co-op genuinely skews reward-mature. ② remainder informal:none
2:1 / 3:1 / 4:1 down the bands. ③ WITHIN-BAND ORDER IS HASH-ONLY, NEVER LATENT — the coherence
note on the record: latent-rank within band let SIZE back in through the coherence spine (the 12
small-Advanced orgs read 58% formal vs the 90% anchor because latent correlates with size and they
sank to the band's non-formal tail); hash-within-band honours maturity fully (small-Advanced
10/12 = 83% ~ anchor). COHERENCE VERIFIED UNDER HASH before the write, as ruled: qa_reseed 9/9
(G2 4, G3 0.15, G4 0.462 — unmoved), B-CHECK off-spine count 4 IDENTICAL to baseline, median corr
+0.527, freeze gate PASS (worst tier-2 drift 2.65pp = the 17-org Basic band's largest-remainder
granularity), run_gates 11/11. No regression — the decoupling is one metric's within-band
assignment; the spine holds.
PILOT (PROP_fe1a29ec): replaces the Diff-15 flat 60/30/10 cohort-centre placeholder. Bands land
Basic 3/17 (17.6% vs 15), Developing 60/100 (60.0%), Advanced 88/98 (89.8% vs 90) — largest-
remainder exact; cohort formal 151/215 = 70.2%; informal 47 / none 17. Cairnbank Council
(50-249 FTE, Advanced) reads FORMAL — maturity-not-size proven.
VERIFIED: throwaway (fresh from live post-ruling-③) — per-band exact asserted, non-target book
hash-identical, 215 history rows; run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3s2_maturity_
20260718; suite-gated write — the migration only fired on a green 11/11): answers 233,441
unchanged in count; post-write live-vs-throwaway EXACT including PER-ORG IDENTITY on the pilot
metric (cross-DB hash determinism proven); re-aggregated 943 payloads; 8060 fresh; post-write
run_gates 11/11. Commit alongside this entry. ROUND-3 QUEUE NEXT: gating workstream on the
verified tags + this mechanism (tips->hospitality, bonus/LTI charity+public refinement,
allowances), then top-performer pricing + formal ranges onto the gradient, office-attendance
sourcing, GRiD/046, REW_PAY_006 dedup, public-sector DB carve-out.

## Maturity family expansion + coupled range-max recompute (r3s3, ruled + applied 18 July 2026)
FAMILY PROOF: the Step-2 mechanism took both new members as PURE DECLARATIONS (maturity_anchors in
structured_bases; generator emits; engine + freeze gate pick them up) — zero new engine code, the
design promise held. ① REW_FAI_128 top-performer market pricing, anchors 5/25/70: bands land
5.3/25.5/69.7, cohort 43.6% Yes (was 59.1% engine-flat); no sector gate (any sector can be
maturity-mature). ② REW_PAY_001 formal pay ranges, anchors 5/30/90: bands 5.3/30.4/89.9, cohort
have-ranges 55.0% — supersedes the Diff-15 flat 40% conditioning. RULED DERIVATIONS: top-performer
remainder No:Planned 8:1/8:1/3:1 and formal-ranges remainder Partially:No 1:3/1:1/2:1 — consistent
family logic: non-doers further up the maturity ladder are nearer to doing it.
③ COUPLED RANGE-MAX RECOMPUTE (the coherence-critical piece): REW265_PAY_RANGEMAX re-derived
PER-ORG from REW_PAY_001's assignment under the RULED STRICT-YES conditioning (Partially does NOT
count — a partial-ranges org needn't have a firm at-max policy and answers 'No formal ranges').
The 121 have-ranges orgs split lump/continue/frozen 40/20/40 (49/24/48 largest-remainder,
hash-ranked); the other 99 answer 'No formal ranges' (99/220 = 45.0%, was 60%). THE
PAY-STRUCTURE-FAMILY COHERENCE GUARD: zero orgs with have-ranges != Yes holding a policy answer —
enforced FOUR ways: in-plan assert, hard write-abort in the migration (a conflict FAILS the write),
post-write re-check from the DB, and re-asserted on live after the write. DURABILITY BY
CONSTRUCTION, not convention: RANGEMAX is orderless-nominal (no ruled ordering, option_order()
infers none -> the engine nominal-skips it on every future reseed) and REW_PAY_001 re-derives
hash-deterministically from profiles — the per-org pair cannot drift.
Both metrics STAY VERDICT-SUPPRESSED EST (unbenchmarked flags untouched) per the standing
EST-no-measured-market doctrine. VERIFIED: throwaway — on-anchor per band, coherence 0 conflicts,
qa_reseed 9/9, freeze gate PASS (now 47 covered: 41 marginals + 3 ruled dists + 3 maturity
gradients, worst 2.65pp), run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3s3_family_20260718):
answers 233,441 unchanged; post-write live-vs-throwaway EXACT including PER-ORG IDENTITY on all
three metrics; LIVE COHERENCE RE-ASSERT = 0 conflicts; re-aggregated 943 payloads; 8060 fresh;
post-write run_gates 11/11. Commit alongside this entry. FAMILY QUEUE (declare-only now): TRS,
equal-pay-audit cadence beyond the ruled marginal, structured progression, pay-gap analytics
beyond mandatory — each just needs David's three-level anchors.

## Sector-scope gate (full hide) — tips pilot (r3s4, ruled + applied 18 July 2026)
THE FINDING: tips rendered 67.5% yes across n=212 — impossible (tips exist only in hospitality).
THE FIX IS A FULL HIDE, not a soft NA: outside a metric's declared sector scope the metric does
not exist — not asked at entry, no chart, no signals, not in the peer base.
MECHANISM (general, declaration-driven — the maturity-gradient discipline): data/sector_scopes.json
declares per-metric sector lists; enforcement is ONE filter added to org_visible_questions (THE
focus filter every member-facing route already flows through — entry, metric view, and the item
streams signals/briefings build from) plus seed-level answer ABSENCE for the peer base
(hot-reloaded, mtime-cached like the lens map). This GENERALISES the 2026.1 hospitality module
(tips carried module=hospitality, shown to hospitality AND retail — which is why it still rendered
for the demo org); the scope layer narrows on top of the module; module->scope unification is the
noted future cleanup. ZERO bespoke tips code; shift premiums / tronc / London weighting are one
JSON entry each.
APPLIED: 199 out-of-scope tips answers DELETED (the pollution, history-snapshotted — absence,
never NA); the 15 hospitality orgs (orgs.industry, Step-1-verified tags) reseeded 80/20 =
12 yes / 3 no (EST, D. Whitfield), hash-deterministic largest-remainder. Answers 233,441 ->
233,244; n 212 -> 15. PEER-BASE BOUNDARY (ruled, accepted): tips follows orgs.industry — the same
sector authority every peer cut uses; the ~9 authored personas whose hospitality tag lives only in
their profile (orgs-table industry NULL) are excluded from tips exactly as they are from every cut
today. The NULL-industry backfill is a QUEUED DATA-INTEGRITY FIX, deliberately NOT pulled into
this diff.
FOUR-SURFACE HIDE VERIFIED ON THROWAWAY AND ON LIVE, tested as Thornbridge (Retail —
module-eligible, scope-excluded, the sharpest case): ① entry — served question set excludes tips;
② chart — /api/benchmark 404; ③ signals — zero tips references in the overview payload; ④ peer
base — stored payload n=15 (12/3, NA at 0). In-scope verified three ways in-process: hospitality
sees it, retail does not, null-industry does not.
AUDIT TAUGHT THE SCOPE SEMANTICS (two ripple fixes, both scope-honest, ruled): the cache-freshness
check now expects core MINUS declared-scope hides for the audit org and distinguishes stale-cache
from scope-leak; the L2 per-metric API loop accepts a 404 ONLY when a declared scope excludes the
audit org — any other 404 still fails (the hide stays under test, never blanket-excused).
DISCLOSURE ON THE RECORD: the first freshness patch swallowed a NameError in a try/except and
silently computed zero hides — caught on the next suite run; rewritten with NO silent fallback
(the rule the incident proves).
Tips stays verdict-suppressed EST; freeze gate tier-2b covers the 80/20 (all answers in-scope by
construction); durability by construction (context routing is count-preserving over the 15;
absence never re-created). VERIFIED: qa_reseed 9/9; run_gates 11/11 pre + post; post-write
live-vs-throwaway EXACT incl. per-org identity; zero stray out-of-scope answers asserted on live;
re-aggregated 943 payloads; 8060 fresh. Backup lumi.db.bak_pre_r3s4_tipsscope_20260718. Commit
alongside this entry. QUEUED: NULL-industry orgs-table backfill for the 62 authored personas
(data-integrity, own diff); module->scope unification; next scope declarations (shift premiums,
tronc, London weighting) as David rules them.

## Tronc family — hospitality scope + tips->tronc conditioning (r3sw1, ruled + applied 18 July 2026)
Sweep-1 build. The four tronc/tips-distribution metrics carried module=hospitality (chart hidden)
but were SEED-POLLUTED across every sector — tips' exact sibling defect (Public Sector orgs holding
"pooled via tronc" answers; 74-89% NA padding). RULED: sector-scope Hospitality-only (per the tips
ruling — the module's retail inclusion narrowed for these too) + the conditioning chain, applied
through STANDING mechanisms only: 4 sector_scopes.json entries + one data-driven config
(r3sw1_derivation_rules.json) through a generic migration — zero per-metric code.
DEEPER CHAIN (drafted, then CONFIRMED by ruling): TYPES and GROUPS condition on TRONC=Yes (9), not
just tips-exist (12) — they ask about the tronc arrangement itself; a tips-but-no-tronc org must
not answer "which tips are in your tronc". The complete chain: hospitality scope -> tips-exist=Yes
(12) -> TRONC 9Y/3N -> TYPES/GROUPS over the 9. Coherence asserted FOUR ways (in-plan, hard
write-abort, post-write from the DB, live re-assert): ZERO conflicts at both chain levels.
SEED (ruled: hospitality-slice evidence accepted as-is, EST observed slices, verdict-suppressed):
TRONC 9Y/3N over 12; TIPS_DIST pooled5/employer3/direct3/combo1 over 12; TYPES card4/service3/
cash2 over 9; GROUPS by-level frontline9/supervisor9/manager5/zero-above, LATENT-nested.
G10 CATCH + HASH-RULING SCOPE CLARIFICATION (on the record): the first throwaway failed qa_reseed
G10 (TRONC_GROUPS depth x latent -0.101 vs 0.30) because the matrix was hash-nested. THE STEP-2
HASH RULING IS MATURITY-GRADIENT-SCOPED ONLY (within-band order); by-level matrices nest by LATENT
per the Diff-13 pattern — cascade depth must track the spine. Fixed config-driven; G10 passes.
The pre-write gate did its job.
COVERAGE (ruled): the coherence chain + r3sw1 manifest lineage (audit-wired, only-ruled-manifests)
guard these four INSTEAD of a 5pp freeze tier — at n=12 a single org is an 8.3pp quantum; a 5pp
line would be dishonest at that granularity. Thin-n noted: 12/12/9/9, above the n>=5 floor, cards
read honestly small.
VERIFIED: throwaway — coherence 0 conflicts, qa_reseed 9/9 (G10 pass post-fix), run_gates 11/11.
LIVE (backup lumi.db.bak_pre_r3sw1_troncscope_20260718): ~530 polluted rows deleted (history-
snapshotted), answers 233,244 -> 232,521; post-write live-vs-throwaway EXACT incl. per-org identity
on all four; LIVE full-chain coherence 0 conflicts; FOUR-SURFACE HIDE verified on live per metric
as Thornbridge/Retail (entry absent / chart 404 / zero signal refs / n=12/12/9/9); re-aggregated
943 payloads; 8060 fresh; post-write run_gates 11/11. Commit alongside this entry.
SWEEP-1 REMAINDER (ruled non-scope, logged): OT_04 shift premiums = ruled marginal + attribute-
keyed (Workforce_Shift_%) -> sweep 2; on-call pair = cross-sector concept, prevalence realism ->
sweep 2; meals = genuinely cross-sector; mileage REW_Q049530 = CONDITION-scoped on the car family
(n=175 vs car-population 74 — flagged for the conditioning pass); London weighting = NO metric +
NO location field (blocked on location capture); uniform = library gap. Scope count now 5.

## One gradient, two keys — sector-keyed generalisation + INC_103/131 (r3sw2, ruled + applied 18 July 2026)
GENERALISATION (ruled, 3 edits, NOT a new build): maturity_assign keys on any declared profile
attribute — `key` (HR_Maturity default; Industry via canon_industry), anchors-iteration replaces
the Basic/Developing/Advanced literal, `band_distributions` (full per-band dists incl. `_default`
fallback) joins the positive/remainder form, and `within_band: hash|latent` is EXPLICIT per entry
(hash reserved to the maturity family per the Step-2 ruling; latent for sector-keyed — the r3sw1
G10 lesson). BACKWARD-COMPAT PROVEN FOUR TIMES: the generalised code reproduces all three live
maturity metrics BYTE-IDENTICALLY (hard-abort assert at dry-run, throwaway apply, live apply, and
standalone against live post-write). "One gradient, two keys."
SELF-HEALING REGRESSION FIX (the structural point): sector-keyed declarations RE-DERIVE from
current tags on every application — the re-tag class (Step-1 re-tags landing after Diff-13's
one-shot gates left Brightstone + Severnbourne holding bonus/LTI ladders as Public bodies) cannot
recur for declared metrics. The two stale trusts were cleaned one-time here (24 bonus-matrix rows
deleted, 133 eligibility flipped to all-level No); the Diff-13 MATRICES stay one-shot and are
noted for a future matrix-to-declaration migration.
① REW_INC_103 bonus-eligible % (sector-keyed, ruled): exists Commercial 90 / Charity 20 / Public 5;
breadth broad/moderate/narrow expressed as per-band distributions (Claude's derivation of David's
two-stage figures, approved). Corrects Diff-13's absolute charity/public exclusion — low-but-
nonzero is the reality; kills the 8-public-orgs-at-"75%+" defect. ② REW_INC_131 operates-LTIP:
DERIVED per-org — Yes := EXACTLY the REW_INC_133 eligibility-holders = 65. NOT the count-framed
~74: the per-org coherence enforcement FOUND THE TRUE NUMBER — 7 Diff-13 construction phantoms
(Board-No/zero-eligibility "LTI-runners") + 2 stale trusts excluded. Live pre-state was worse than
the sweep showed: Yes=35 with only 32 coherent and 35 eligibility-holders saying No. STANDING
GUARD: `coherence_pairs` in generated_marginals (generator-emitted from structured_bases) checked
by the freeze gate — ANY future reseed that drifts the 131<->133 pair fails the suite.
QUANTUM-AWARE GATE LINE (ruled): tier-2c per-band fail line = max(5pp, 1/n). The gate caught its
OWN line being unachievable at sector granularity (first throwaway: Charity n=8 cannot round 80%
closer than 75% -> 7.5pp "drift" that is pure largest-remainder arithmetic; the earlier <=3.3pp
margin claim was wrong below n=10). An ACHIEVABILITY bound, not a loosening — bands >=20 keep the
flat 5pp. Post-fix worst: 2.55pp (Construction, genuine rounding). BACKLOG: 3 orgs canon to
"Other" (unmapped profile industries) — sub-floor, seeded on _default, flagged for the canon map.
Both new metrics VERDICT-SUPPRESSED EST. VERIFIED: throwaway — backcompat byte-identical, pair
exact, qa_reseed 9/9, run_gates 11/11 (after the quantum fix). LIVE (backup lumi.db.bak_pre_
r3sw2_sectorgrad_20260718): answers 232,521 -> 232,497 (-24 trust rows); post-write EXACT incl.
per-org identity on all 5 touched metrics; LIVE pair coherence 65==65 SET-IDENTICAL; LIVE
backcompat byte-identical; re-aggregated 943 payloads; 8060 fresh; post-write run_gates 11/11.
Commit alongside this entry. SWEEP-2 REMAINDER (ruled paths, queued): HOL_001 sector band =
marginal+B5 re-ruling; PENSION_TYPE public DB carve-out = tier-1 re-freeze (blocked on nothing —
sector tags verified); clawback/sign-on -> bonus-family conditioning chain; office cadence parked
for CIPD.

## Pension carve-out — public-sector DB from TPR, tier-1 re-freeze (r3sw3, ruled + applied 18 July 2026)
THE SPLIT COMES FROM SOURCE (David's ruling honoured): TPR Occupational DB landscape 2025 (data
31 Mar 2025, grade A, free/official) — 200 public-service schemes / 19.78m members, open to new
members BY STATUTE; CARE receives NO separate TPR classification = standard DB -> the public-sector
new-joiner answer lands in Lumi's "DB", not "Hybrid". New-employee basis throughout (standing
rule). The FOI route (db-and-hybrid-schemes-open-to-new-members) is a DOCUMENTED DEAD END — s.44
FOIA / s.82 Pensions Act 2004 restricted information; the landscape publications carry the
aggregate and are better anchors anyway.
APPLIED via the sector-keyed gradient: Public Sector & Government band DB 95 / DC 5 -> 14 DB /
1 DC over the 15 verified public orgs (post-Step-1 tags, incl. the 3 re-tagged trusts).
SURGICAL-BAND CONTRACT (ruled a PERMANENT mechanism capability): band_distributions WITHOUT
_default = declared-bands-only assignment — undeclared bands stay out of the newmap and untouched.
This is what makes carve-outs expressible without churning frozen data; every future sector/band
override uses it. Backward-compatible: all prior entries carry _default or full anchors; the four
prior gradient metrics re-proven BYTE-IDENTICAL on live post-write. Commercial/charity PENSION_TYPE
answers asserted per-org byte-identical at write AND re-verified on live (194 DC / 7 DB / 4 Hybrid
non-public — unchanged).
TIER-1 RE-FREEZE (EAP precedent — G7 BASELINE RE-ESTABLISHED): frozen_targets REW26_BEN_
PENSION_TYPE DC .95 -> .8864 / DB .0318 -> .0955 / Hybrid .0182 (national 209/7/4 -> 195/21/4,
n=220); the freeze gate enforced the new target on throwaway and live (settled max drift 0.005pp).
REGISTER (ruled ②③④): PENSION_TYPE grade->A with the TPR carve-out citation + construct flag
(TPR counts schemes/members vs Lumi org-offer — immaterial for public: statutory participation ~=
offer); COMMERCIAL 95/3/2 TPR-CORROBORATED as ANNOTATION ONLY (A-derived: ~340/5,060 open DB =
6.7%, 13% of members, hybrid 410/1.7m — a derived delta confirming the frozen value is not worth a
re-freeze); AE NONE-REMOVAL upgraded legal-principle -> SOURCED (TPR AE declaration of compliance,
May 2026: 2,734,305 employers declared, 11.45m auto-enrolled); REW264_PEN_AEDEFAULT statutory-floor
row ADDED (8% total / 5% employee on qualifying earnings, Pensions Act 2008, grade A — distribution
stays EST pending the ONS pass). Register 246 rows.
VERIFIED: throwaway — dry-run national aggregate == frozen target asserted, qa_reseed 9/9, freeze
gate PASS, run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3sw3_pensioncarveout_20260718): answers
232,497 unchanged in count; post-write EXACT incl. PENSION_TYPE per-org identity; live public band
{DB 14, DC 1}; live non-public byte-identical; live prior-gradient backcompat 4/4; re-aggregated
943 payloads; 8060 fresh; post-write run_gates 11/11. Commit alongside this entry.
QUEUED (Prompt 2, parallel research, NO write): ONS ASHE workplace-pension pass (contribution
distributions for PENSION_MATCH/AEDEFAULT) + DWP AE evaluation pass (opt-out) — TPR cannot carry
those; both free/official grade-A calibre.

## ONS/DWP pass — corroborate and defend, register-only (ruled + applied 18 July 2026)
OUTCOME: the adjacent-source pass CORROBORATED the pension figures rather than replacing them —
ASHE confirms the altitudes, so this is annotations + one context row, NO SEED WRITE (seed sha256
fcc967399d81c207 asserted byte-identical before/after; answers 232,497 untouched; qa_reseed 9/9 +
freeze gate PASS on live post-change).
① PENSION_MATCH: frozen distribution GRADE-A-CORROBORATED — ONS ASHE 2024 private-sector median
employer contribution 5-6% on qualifying earnings ('Employee workplace pensions in the UK: 2024
provisional and 2021 to 2023 final results', released 10 Mar 2026). Employee-weighted; corroborates
ALTITUDE, not a distribution replacement; frozen dist not churned. ② AEDEFAULT: ASHE median added
as context — two grade-A sources now bracket the modal answer (statutory 8%/5% floor + ASHE 5-6%
actual median). ③ CONTEXT_AE_OPTOUT (new register context row, grade A): AE opt-out 8-14% across
the programme, ~10% historical, 89% eligible-employee participation 2024 (DWP Workplace pension
participation and savings trends 2009-2024). NO LIVE METRIC — deliberately NOT mapped onto AUTOESC
(auto-escalation is a DIFFERENT CONSTRUCT; mis-mapping would be the audit's error class); library
backlog: add an opt-out metric. ④ THE DEFENSIVE ANNOTATION (the important one): ASHE's DB 34% /
DC 40% / GPP 25% membership split recorded on the PENSION_TYPE row as LEGACY-STOCK,
EMPLOYEE-WEIGHTED, NOT NEW-JOINER BASIS — it does NOT supersede the TPR new-joiner anchor (DB
landscape 2025). This annotation exists specifically to stop a future instance seeing "DB 34%" and
correcting the frozen carve-out against legacy data — it PROTECTS r3sw3. ⑤ ASHE Table P10 PARKED
with a backlog note (banded employer contributions by industry x pension type — available as a
full sourced distribution for PENSION_MATCH if ever needed; employee-weighted, needs ruled
org-level adjustment; not pulled because the frozen dist is plausible + corroborated).
Register 247 rows; parked_anchors.md echoes the P10 + opt-out backlog items. Commit alongside
this entry.

## Annual-leave sector floor — HOL_001 carve-out + a standing principle (r3sw4, ruled + applied 18 July 2026)
RULED: Retail / Hospitality / Logistics sit at the STATUTORY FLOOR for new joiners — modal
"Statutory minimum only (20 days)" (20+8BH = 28 = UK minimum); floor-band distribution 45/32/18/4/1
(Claude derivation of the modal-20 ruling, approved); all other sectors byte-untouched
(surgical-band contract). Applied via the sector-keyed gradient on the Step-1-verified tags;
per-band modal-20 enforced as a HARD WRITE-ABORT and re-verified on live (3/3 bands).
NEW STANDING PRINCIPLE (ruled ①, consciously): A SECTOR-HONEST SEED SUPERSEDES AN ALL-UK SOURCED
MARGINAL when the cohort's sector mix differs from the national economy — composition, not
contradiction; the source stays on the register as the all-UK reference. Applied here: HOL_001
LEAVES the grade-A marginal set (44 marginals remain, pf-count 7 — the PROP_fe1a29ec precedent;
a sector-blind global marginal would destroy the carve-out at the next reseed); the CIPD 0.553
all-UK 25+-share is retained as reference, no longer the seed driver; the cohort-honest global 25+
reads ~47% (cohort 38% floor-sectors vs CIPD economy-wide — 84/220).
B5 SECTOR-SPLIT (ruled ④): the floor bands' within-spread IS the declared band distribution
(centred on 20); the ruled two-sided shares (.5998/.2329/.1673 // .3127/.6873) now document the
STANDARD-sector structure only, never re-reshaped (sector-split note on b5_levels_ruled).
DK ASYMMETRY (ruled ③, accepted): the floor bands' 7 Don't-knows became real values under
re-derivation (no-DK rule); the standard side's 5 DKs are HELD by the byte-identical guarantee —
QUEUED MICRO-DIFF to strip them without breaking a surgical write. TENURE DEFERRED (ruled):
public/charity leave rises with service, not level — those orgs stay at the 25-day standard,
KNOWN-APPROXIMATE, pending the tenure-service field + tenure-banding mechanism (queued alongside
location-capture).
BUILD CATCHES (guards working, disclosed): the inherited backcompat check needed PARTIAL-COVERAGE
awareness — a surgical-band entry's newmap covers only its declared bands, so backcompat compares
over the newmap's own domain (the false alarm was the check, not the mechanism; standalone
re-verify 0-mismatch throughout); one cursor-shadowing slip caught immediately by crash. Also
noted: URI-mode sqlite paths break on the repo's space — plain connections in verify scripts.
VERIFIED: throwaway — floor modal-20 asserted, qa_reseed 9/9, freeze gate PASS (HOL_001 under
tier-2c floor-band checks), run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3sw4_leavefloor_
20260718): answers 232,497 unchanged in count; post-write EXACT incl. HOL_001 per-org identity;
floor bands modal-20 3/3 on live; STANDARD SECTORS 0 CHANGED vs the pre-write backup (proven
against the backup itself); prior gradient metrics 5/5 byte-identical; re-aggregated 943 payloads;
8060 fresh; post-write run_gates 11/11. Commit alongside this entry.

## Pre-audit bundle — NULL-industry fix + clawback conditioning + HOL DK strip (r3sw5, ruled + applied 18 July 2026)
Three independent fixes, separately asserted, closing pay/pensions to a clean base before the
other-domain audit. TWO PREMISE CORRECTIONS on the record: ① the NULL-industry set was 62 SEED
ORGS, not ~9 — every authored persona lacked orgs.industry, so 28% OF THE COHORT was silently
missing from every sector cut in every domain (the ~9 was just the hospitality subset); the 63rd
NULL is the staff org, correctly excluded. ② REW_INC_071 clawback is CONTEXT, not a ruled marginal
— the sweep-2 report misclassified it; the fix is conditioning-only, the 44-set untouched.
PART A (highest value, ruled): orgs.industry (+subsector where empty) populated for all 62 from
the Step-1-VERIFIED profile sectors (long labels via the canon inverse; the 3 authored-as-'Other'
trading companies populated honestly as 'Other'). CASCADE, additive-only: the 12 newly-tagged
hospitality orgs enter the tips scope — tips n 15 -> 27 (new 12 seeded 80/20 = 10Y/2N; aggregate
22Y/5N = 81.5%, inside the gate), tronc chain extends down the ruled r3sw1 ratios (TRONC +10,
TIPS_DIST +10, TYPES +7, GROUPS +49 latent-nested rows); the existing 15 hospitality orgs'
answers BYTE-PRESERVED; zero out-of-scope strays asserted. Every sector cut platform-wide now
sees the full cohort.
PART B (ruled UNIFORM/33): all bonus-less orgs (INC_103='None') read 'Not applicable' on clawback
— the 17 incoherent Yes (grown from 14 after the r3sw2 reshape) AND the 16 vacuous No ("No"
falsely implies a bonus that doesn't exist). Yes 128->111 / No 52->36 / NA 40->73. Sign-on
untouched (ruled legitimate — NHS golden-hellos). STANDING GUARD: 071-Yes ⊆ bonus-exists added to
coherence_pairs with the SUBSET-RELATION extension to the freeze-gate pair check (previously
equality-only) — live in the suite from this diff; a future INC_103 reseed that re-breaks the
conditioning fails run_gates.
PART C (ruled): HOL_001's 5 standard-side Don't-knows DELETED (n-excluded, never redistributed)
and the DK option removed from the bank — the leave-floor DK asymmetry resolved. THE BLANKET DK
DIFF IS QUEUED (definite next-round item): the sweep found ~60 pay/pensions-and-beyond metrics
carrying DK options with 2-23 answers each — hundreds of n-exclusions deserve their own
before/after and gate.
VERIFIED: throwaway — all three asserts pass independently (A: 0 NULL seed orgs, tips n=27, 0
strays; B: 0 clawback-Yes-without-bonus; C: 0 HOL DKs), qa_reseed 9/9, freeze gate PASS (subset
pair live), run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3sw5_preaudit_20260718): answers
232,497 -> 232,580 (+88 additive scope seeds, -5 DK); post-write EXACT incl. ORGS.INDUSTRY
IDENTITY live==throwaway; all three asserts re-ran on live (0/0/0); re-aggregated 943 payloads;
8060 fresh; post-write run_gates 11/11. Commit alongside this entry.
QUEUE AFTER THIS DIFF: blanket-DK diff (ruled, next round); sweep-3 anchors (David's numbers);
office-attendance CIPD sourcing; tenure-banding + location-capture mechanisms; REW_PAY_006 dedup;
canon-map 'Other' trio.

## PMI premium re-base — group-scheme basis + the first per-tier split verdict (r3sw6, ruled + applied 18 July 2026)
BASIS CORRECTION (ruled): the PMI premium matrix (Single/Partner/Family) was built on
INDIVIDUAL-POLICY figures — the wrong product for a company-funded group-scheme metric. Re-based:
Single £800 GRADE B (employer/group free multi-source: ~£480-840 mid-tier, up to £1,500 rich;
David set £800 for the larger-employer cohort) / Partner £1,600 = 2.0x EST / Family £2,000 = 2.5x
EST (group by-tier split is PAYWALLED — LaingBuisson/Mercer). Middle-50% bands ±25% BY
CONSTRUCTION: per-org multiplier uniform over [0.5,1.5] latent-ranked desc, the SAME m per org
across tiers (coherent ladder), £10-rounded — P25/P75 land exactly at 0.75/1.25x. DATA NOTE
(recorded): myTribe INDIVIDUAL by-tier was £990/£1,901/£2,168 (family only 2.2x); the ruled group
Family 2.5x reflects a richer company-scheme definition — defensible.
FIRST PER-TIER SPLIT VERDICT ON THE PLATFORM: Single (grade B) RENDERS a market position;
Partner/Family (EST) are ROW-SUPPRESSED — `unbenchmarked_rows` in the curated mp entry, enforced
at ONE choke point (positions.unbenchmarked_rows(): no rank, no position item, no £-opportunity
from EST tiers) + per-row card flag + a per-row EST caption in the chart. The card P-pill is the
median of ROW percentiles, so gated rows drop out naturally — the renderer carried the split with
three small changes, no rework. Verdict re-earn per tier: source the paywalled by-tier data ->
remove the row from unbenchmarked_rows.
DEMO ORG: Thornbridge's 680/1200/1600 are GENUINE UI ENTRIES (David's own, made this session —
NOT seed values; the earlier seed read 1350/2460/3480) — preserved through the re-base. LIVE
RENDER VERIFIED: Single £680 -> P35 vs group P50 £800 (below market, inside the middle 50%);
Partner £1,200 and Family £1,600 show values + P50 reference with NO position claim.
VERIFICATION CATCHES (guards + doctrine working, disclosed): ① TWO THORNBRIDGE ORGS exist
(Advisory plc + Retail Group plc) — the demo lookup's LIKE-prefix selector silently hit ADVISORY,
and the direct-check used the same selector = a FALSE CONFIRMATION; caught only by the end-to-end
render proof; fixed by resolving via the director account (never a name prefix — on the record).
② A stale-server false reading preceded it — the manual verify server wasn't provably fresh and
the migration doesn't re-aggregate; the GATE-RUN DOCTRINE (lsof/pid-asserted fresh server,
re-aggregate first) applies to MANUAL proofs too. ③ The demo values shifted mid-session
(1350->680) because David entered them through the UI while work was in flight — single-
environment reality. ④ Median one-rank quantum: re-ranking one org shifts a 131-org median by
<=1 rank (~£8-20); assert set at the quantum, documented.
TOPOLOGY (clarified for the record): ONE environment — lumi.db + the :8060 dev server from this
checkout IS what David sees; `--write --confirmed-by-david` writes THERE; git push archives code,
deploys nothing; go-live is a future deliberate step. All session diffs are live in that one
environment. STANDING PROCESS (ruled): config/code edits are STAGED and applied ATOMICALLY with
each data write from now on — no mixed-state window between render and data (the window David
observed was the approval gate holding data back while hot-reloaded config had already landed).
VERIFIED: throwaway — medians exact, bands exact, qa_reseed 9/9, run_gates 11/11 (on the APPLIED
state; one earlier suite ran against an unapplied throwaway after a guard abort and was discarded
as evidence). LIVE (backup lumi.db.bak_pre_r3sw6_pmirebase_20260718): answers 232,580 unchanged;
post-write EXACT incl. per-org identity (393 cells) + demo entries preserved; live split render
verified on a provably-fresh server; re-aggregated 943 payloads; post-write run_gates 11/11.
Commit alongside this entry. Benefits-domain queue continues per David.

## Virtual GP re-anchor — the first whole-metric verdict re-earn + gate-server config isolation (r3sw7, ruled + applied 19 July 2026)
BASIS CORRECTION (ruled): REW264_HLT_VIRTUALGP's seed read No 77.3% — an all-employer/all-size
prior for a cohort that is larger-private-sector weighted. Re-anchored to CIPD Health & Wellbeing
at Work 2025 (large private band): Yes-all 45 / Yes-some 13 / Via-PMI-only 11 / No 31. GRADE
SPLIT ON THE REGISTER: A/B on the TOTAL provision (69% offer in some form — direct CIPD read);
EST on the 3-way split (floored by vGP 54% > PMI 40% among large privates; the Yes-all/Yes-some/
via-PMI partition is estimated). SIZE GRADIENT (SME 23 / large 54) RECORDED AS REFERENCE, not
gated — no size-keyed mechanism yet; noted for a future size-key. Reshape: 220 answers via
largest-remainder to 99/29/24/68, latent-ranked descending with ORDER REVERSED (generous pole to
top-latent orgs); ruled ordering No < Via-PMI-only < Yes-some < Yes-all.
FIRST WHOLE-METRIC DIFF-14 RE-EARN: the metric was one of the 222 suppressed on distribution
authority. Anchor sourced -> flag lifted ATOMICALLY with the data write (--write applies data +
mp-config direction=higher_is_better + unbenchmarked popped + questions.polarity=higher_is_better
in one transaction; _r3sw7 breadcrumb replaces _diff14). The re-earn path is now PROVEN in both
grains: per-tier (PMI Single, r3sw6) and whole-metric (this). Positionable-with-authority 51 -> 52
(directional, unsuppressed, no row-split, live question).
LUMI_MP_CONFIG — STANDING GATE-SERVER DOCTRINE (ruled, folded into this diff): positions.py now
resolves the mp config from $LUMI_MP_CONFIG before falling back to data/market_position_config.json.
Gate servers and throwaway suites point at a STAGED COPY; the served file is IMMUTABLE until the
approved live write — staging is PATH-ISOLATED, not just edit-staged. Closes the mixed-state class
David observed at r3sw6 (throwaway apply hot-reloaded a lifted config onto the live view for ~4
min this diff — working tree reverted via git checkout, exposure disclosed; the override makes the
class structurally impossible).
HYGIENE NOTE (found at count reconciliation): REW_PAY_MKT_POS_01 carries a directional mp entry
with no live question (retired lineage) — never renders, cleanup queued, not churned into this diff.
VERIFIED: throwaway scratchpad/t26/lumi_r3sw7.db — dist exact 99/29/24/68, non-target book
hash-identical, qa_reseed 9/9, run_gates 11/11 on the lifted state; override verified both ways
(default resolves, /tmp path honoured). LIVE (backup lumi.db.bak_pre_r3sw7_virtualgp_20260718):
answers 232,580 unchanged; post-write EXACT (0 differing cells, per-org identity, polarity
higher_is_better, served config == staged lift, VIRTUALGP the ONLY entry changed vs HEAD);
re-aggregated 943 payloads; provably-fresh :8060 (pid==listener); LIVE RE-EARN VERIFIED via the
director account: dist served 45.0/13.2/10.9/30.9, unbenchmarked=False, readout present,
Thornbridge 'No' positions below a 69%-offer market; post-write run_gates 11/11. Commit alongside
this entry.

## PMI coverage-composition redesign — multi-select replace + the N/A-exclusion pilot (r3sw8, ruled + applied 19 July 2026)
STRUCTURAL REPLACE (ruled, all five points): REW263_BEN_PMIMH (single-select MH/DGP) RETIRED —
its N/A bar (56.8%) distorted the distribution, and it was provably incoherent: 73 of the 131
premium-matrix answerers simultaneously called it N/A because its NA routing followed the stale
WEL_BMAP presence map while r3sw6 re-based PMI-existence on REW_BEN_038. Diff-14 retire pattern
+ FIRST USE of replaced_by. REW265_BEN_PMICOMP created: multi-select "beyond standard cover",
6 benchmarked options + derived-exclusive terminal 'None of these — core cover only' (zero-pick
orgs stay in n). 4 UNIVERSALS ASSUMED STANDARD, stated in help_text, NOT options (in-patient,
digital GP, cancer cover, basic MH support line — ~90%+ everywhere; benchmarking them is noise).
Structure grade B (Bupa/AXA/Aviva/Vitality product tiers + broker guides); incidence EST,
structure-anchored; VERDICT-SUPPRESSED (unbenchmarked:true); per-option re-earn when sourced.
SEEDED over the APPLICABLE BASE ONLY: the 130 REW_BEN_038 PMI-tickers (the r3sw6 conditioning
set), exact-count per-option incidence (diff8 pattern): out-patient 101 (77.7%) / physio 78
(60.0%) / full-MH 65 (50.0%) / screening 55 (42.3%) / dental&optical 36 (27.7%) / overseas 29
(22.3%) / terminal 4 (3.1%). Spread 0x4/1x13/2x33/3x45/4x25/5x10, no org holds all six.
Answers 232,580 -> 232,490 (-220 +130); payloads 943 -> 944.
N/A-NOT-ON-GRAPH PILOT (first application, the template's DATA half): conditioned seeding means
no N/A option exists and graph+n = PMI-havers by construction — zero renderer change needed.
The 'base = PMI-havers' caption rides help_text (ruled: renderer stays untouched; the declared
applicable_bases.json + card base field is the FIRST BUILD ITEM of the queued N/A-inventory
sweep, built when the sweep needs it, not for one chart).
NEW MECHANISM (tier-2d + pair vocabulary, negative-proven): generated_marginals gains
multiselect_incidence (independent per-option prevalences — EXPLICITLY exempt from sum-to-100;
from structured_bases option_prevalences); qa_plausibility gates each option at max(5pp, 1/n)
+ terminal-exclusivity + an ARMING check (an active declared-incidence metric with n<20 hard-
fails MS-BASE-MISSING — losing the conditioned base can never pass silently). Coherence pairs
gain child_any_answer/parent_contains selectors, relation subset_orgs: composition answerers
⊆ REW_BEN_038 PMI-tickers, vacuous-pass pre-write. NEGATIVE TESTS ALL FAIL CLOSED: base
deleted -> MS-BASE-MISSING rc=1; 20-org drift -> MS-INCIDENCE-DRIFT 15.7pp rc=1; one non-PMI
answerer -> PAIR-INCOHERENCE rc=1.
ADVERSARIAL REVIEW (13-agent, pre-throwaway; all 10 confirmed findings resolved, disclosed):
① the --write path had an UNCONDITIONAL CRASH (a %-format landmine in a changelog string —
invisible to dry-run); ② --config-out DEFAULTED to the served config, inverting the r3sw7
doctrine — now a throwaway --write REFUSES to run without an explicit staged path and refuses
the served path outright; ③ commit ordering made 'atomic' false — now ALL DB post-asserts run
pre-commit (any failure = full rollback), config written temp+os.replace after; ④ a proven
green-side hole (deleting the conditioned base kept the suite green) — closed by the arming
check. DOCTRINE COMPLETIONS (ruled ⑤): qa_focus/qa_engine_audit/aggregate now honour
LUMI_MP_CONFIG (three direct readers bypassed the r3sw7 isolation); qa_reseed subtracts DB-
retired questions from the meta universe (G9's all-answered intersection collapsed to n=0 on
any retired Benefits metric — Diff 14 survived only by luck of family; no-op on live, proven).
ACCEPTED LIMITATION (ruled ③): the entry UI cannot answer-condition — no-PMI orgs still see
the question; a stray member answer trips the pair gate (caught, not corrupting; identical
exposure to clawback/LTIP). QUEUED: depends_on UI layer / seed-only pair scope as the general
fix. THORNBRIDGE LEFT OUT (ruled ④): not a REW_BEN_038 PMI-ticker — its exclusion correctly
surfaces its own incoherence (premium entries without the PMI tick); demo-data cleanup queued
(tick PMI deliberately, then answer composition — that order, or the pair fires). CLEANUP
(ruled ⑤): inert grade-A anchor_provenance entry for the retiree STRIPPED (register row stays
as lineage). SPUN-OUT METRICS (queued, not built): excess/underwriting type (moratorium vs
MHD); family/children cover (maps to tier work); EAP-via-PMI (belongs in an EAP metric);
out-patient limit/tier (depth sub-question). Also queued: config<->question-bank coherence gate.
VERIFIED: throwaway scratchpad/t27 — qa_reseed 9/9, run_gates 11/11 with the staged config via
LUMI_MP_CONFIG (served file untouched, 0-line diff — the r3sw7 doctrine held by construction),
render proof n=130/answered:false/7 bars on-share/old 404. LIVE (backup
lumi.db.bak_pre_r3sw8_pmicomp_20260719): answers 232,490; post-write match EXACT (0 differing
cells vs throwaway, history 220, changelog 2, served config == staged copy byte-equal);
re-aggregated 944 payloads; provably-fresh :8060; live render re-verify PASS; post-write
run_gates 11/11 + qa_reseed 9/9; full suite re-run after the provenance strip. NOTE (process,
disclosed): the first post-write match block died at the provenance-strip assert (entry nested
under 'provenance', not top-level) BEFORE any match check ran — the match was then run
genuinely, not assumed from the earlier green render. Commit alongside this entry.

## Applicable-base mechanism — the durable N/A-not-on-graph template (r3sw9 mechanism build, applied 19 July 2026)
THE MECHANISM (deferred from r3sw8 ②, built at the sweep as ruled): data/applicable_bases.json —
a metric DECLARES its applicable base; the graph, n and every payload consumer render over it.
Two modes: 'conditioned' (rows exist only for the base — r3sw1/r3sw8 seed pattern; the
declaration adds the member-facing caption, aggregation untouched, enforcement = the subset_orgs
pair + tier-2d arming) and 'answerer_only' (declared na_options leave the block AT AGGREGATION:
out of n, out of the bars, block carries excluded_na; declarations are RULED per metric because
they change rendered distributions; re-aggregate after declaring). Surfaces: card footer
(card.js base-note), metric-detail header + one-pager masthead (app.js), all reading a new
card 'base' field from assemble_card. LUMI_AB_CONFIG path override baked in from day one
(r3sw7 doctrine — gate servers/staged runs never read the served copy). qa_release VALIDATOR:
every declaration must name an active metric, a known mode, real option labels
(answerer_only) or an active parent (conditioned) — a typo'd declaration fails the gate
loudly instead of silently no-opping at render (the banned failure class). FIRST DECLARATION:
REW265_BEN_PMICOMP (conditioned, 'PMI-holding organisations') — the r3sw8 pilot chart now
carries the caption from config; help_text keeps the assumed-universals copy.
VERIFIED: answerer_only proven end-to-end on a SCRATCH db + staged config (REW263_BEN_DENTAL
test declaration: n 220 -> 93, excluded_na 127, no N/A bar, remaining bars re-percentage to
100) — scratch only, NOT shipped; shipped config declares only the conditioned pilot.
BYTE-NEUTRALITY proven: undeclared + conditioned metrics' payloads identical to the live
store. run_gates 11/11 on the mechanism code (validator live). Browser-verified on :8060
v422: 'All peers · n=130 · of PMI-holding organisations'. The N/A-INVENTORY (80 true-N/A
metrics enumerated; DK options are the separate blanket-DK diff; 'Varies'-type options stay
on-graph) is presented for per-metric rulings — every ruled metric becomes a declaration;
NO seed or declaration writes beyond the pilot until ruled. Commit alongside this entry.

## N/A sweep step 1 — the (b) batch: 29 simple re-percentages live (r3sw10, ruled + applied 19 July 2026)
ONE RENDER DIFF, NO SEED CHANGE (asserted): the 29 ruled (b)-class metrics from the r3sw9
inventory declared answerer_only in data/applicable_bases.json — each metric's N/A-type option
leaves the bars AND the denominator at aggregation, remaining options re-percentage over the
applicable base, excluded_na carried, base caption on all three n-surfaces. ANSWERS TABLE
BYTE-IDENTICAL through the entire live chain (sha256 pinned before the config write, re-verified
after suite — render-layer only, exactly as ruled). VERDICT STATUS UNCHANGED: no polarity/
mp-config/unbenchmarked flags touched — suppressed metrics stay suppressed, now on honest bases.
HEADLINERS: FERTROUTE 220 -> n=22 (198 excluded — ACCEPTED honest thin base, the only n<30);
GOV_UMBRELLA -> 137; ENHANCEDVR -> 142; REM_PAY_001 -> 108; EARLYCAREER -> 164; shift cluster
-> 183 (x3); guaranteed-hours pair -> 190 (x2); SHAREPLAN -> 181; REC_CURRENCY -> 175. Bespoke
captions where the base is nameable, generic 'organisations where this applies' elsewhere.
CAR_BN_02 (the roster's one multi-select) keeps independent per-option shares by design.
RULED ③: REW263_TIME_IVF ships in-batch and the exclusion REVEALS a near-dead signal ('None'
99.5%, n=210) — QUEUED for deliberate retirement-review, NOT auto-delete (fertility is
sensitive/growing; 99.5% None may be worth showing precisely to highlight rarity).
VERIFICATION-LAYER FIXES (ruled ②, ride the diff): ① qa_engine_audit L2's independent
recompute now applies declared exclusions (ab_apply, env-or-served config path) before
comparing — without it every declared metric read as FALSE DRIFT (caught on the first
throwaway suite: EARLYCAREER/ENHANCEDVR ref-220-vs-prod mismatches); provably no-ops when no
answerer_only declarations are served. ② The before/after checker wrongly asserted sum-to-100
on the multi-select — checker corrected, mechanism was right (per-option pct = count/n
verified for all 29).
VERIFIED: throwaway — all 29 before/afters EXACT (n drops by excluded, N/A bars gone,
selects sum to 100), answers byte-identical, qa_reseed 9/9, run_gates 11/11 with the staged
config via LUMI_AB_CONFIG (served file untouched until this approved write), declaration
validator 30/30. LIVE: served config == staged byte-equal; re-aggregated 944 payloads;
provably-fresh :8060; render re-verify PASS on a 6-metric sample incl. FERTROUTE
n=22/198-excluded and the untouched conditioned pilot; post-write run_gates 11/11.
QUEUED BEHIND: (a) families as per-family gated diffs (share-plan first; DEFERRAL/CICOVER/
RED_TERM_03 seed repairs are prerequisites); IP-family diagnosis-first (BEN_038-vs-BEN_046
authority conflict); TIME_IVF retirement-review; presence-gate minting for business-need-car
+ recognition families ((a)-upgrades). Commit alongside this entry.

## Share-plan family — coherence repair + first (a)-family conditioning (r3sw11, ruled + applied 19 July 2026)
THE COHERENCE GATE WORKED (diagnostic-first, as ruled): the sweep's 'cleanest family' was NOT
clean — SHAREPART was (0/0 vs any-plan 43), but SAYEDISC held 12 SIP-only orgs all on '20%
(maximum)' (engine-modal artifact), SIPELEM contradicted BOTH directions (16 SAYE-only orgs
with fabricated SIP elements + 6 real SIP operators saying 'No SIP operated'), and EMICSOP
carried a dual-authority conflict: its own 'no share capital' (28) vs the parent's 'no shares'
(39), incl. 6 orgs claiming EMI/CSOP with no share capital and 3 plan operators claiming no
capital — impossible both ways.
REPAIR (ruled ①③, 77 rows ALL UPDATEs, answers pinned 232,490, seed-only, per-cell manifest):
SAYEDISC 12 -> N/A (base -> SAYE-side 31); SIPELEM 16 -> 'No SIP operated' + the 6 operators
seeded INCIDENCE-MATCHED to the 12 legit operators' element mix (diff8 pattern, no flat spike;
per-element counts assert-matched); EMICSOP per ruling ② PARENT AUTHORITY WINS (one-authority
principle + low blast radius): 27 -> N/A, 16 -> 'Neither'; post EMI 24/CSOP 11/Both 6/Neither
140/N/A 39 — the two no-share-capital encodings ALIGN EXACTLY at 39. ALL FOUR CONTRADICTION
CLASSES ZERO post-repair, asserted pre-commit and RE-VERIFIED ON LIVE post-write.
CONDITIONING (ruled ⑤): 4 answerer_only declarations — SHAREPART 'of organisations operating
a share plan' (43), SAYEDISC 'offering SAYE' (31), SIPELEM 'operating a SIP' (18 — ACCEPTED
thin base, ruled ④: honest 18 beats the distorted 28 that included 16 fabrications; FERTROUTE
precedent), EMICSOP 'with share capital' (181). TWO NEW PAIR SELECTORS (r3sw5/r3sw8 shape):
child_value_not (substantive set = non-N/A answers, token-aware for multi-select terminals)
+ parent_value_in (type sub-bases: SAYE-side = parent in {SAYE, Both}, SIP-side {SIP, Both}).
4 subset pairs live in the freeze gate; NEGATIVE-PROVEN: SIP-only-with-discount,
SAYE-only-with-elements, no-shares-with-EMI each hard-fail PAIR-INCOHERENCE rc=1.
DISCLOSED WINDOW: the pairs were hot in the working tree against unrepaired live data during
the build (a live gate run pre-write would have honestly redded) — r3sw5-pattern single-session
window, closed by this write.
VERIFIED: throwaway scratchpad/t30 — repair exact, conditioned before/afters exact
(43/31/18/181), qa_reseed 9/9, run_gates 11/11, three negative tests fail closed. LIVE (backup
lumi.db.bak_pre_r3sw11_shareplan_20260719): post-write match EXACT (0 differing cells vs
throwaway; answers 232,490; served applicable_bases == staged, 34 declarations); re-aggregated
944; provably-fresh :8060; 4 bases + captions render correct, no N/A bars; ZERO-CONTRADICTION
RE-VERIFY ON LIVE (all four classes, both directions); post-write run_gates 11/11. NOTE
(process, disclosed): the first post-write config assert used the wrong expected count (38 vs
the true 34 — reporter arithmetic, not a write defect); the comparison was re-run genuinely:
served == staged byte-equal at 34. Commit alongside this entry. NEXT (a)-families per the
queue: EWA pair (parent REW264_WEL_EWA), insured-benefits cluster behind the IP-authority
diagnosis; DEFERRAL repair is the largest outstanding (141 contradictions).

## EWA family — first purely-declarative (a) conditioning, OFFER-OR-PILOT grain (r3sw12, ruled + applied 20 July 2026)
GRAIN RULED: Piloting COUNTS as offering — a piloting org has a live scheme with a real fee
model and real caps; pilots are the leading edge a benchmark should include for a growing
benefit. Base = 77 (Yes-all 44 + Yes-hourly/frontline 22 + Piloting 11), captions 'of
organisations offering or piloting earned wage access'. COHERENCE GATE (diagnostic-first):
CLEAN at the ruled grain — 0/0 both directions on BOTH children (EWAFEES, EWACAP); the 11
contradictions at the offer-only grain were exactly the piloting orgs, resolved by the grain
ruling rather than a repair. is_na flags clean (no RED_TERM-class mis-flags). Parent
REW264_WEL_EWA is a SINGLE clean authority: the two broader options elsewhere (WEL_SUP
'Salary advance OR EWA' 118 — a bundled either/or, structurally unusable; WEL_BMAP 'Salary
Advance Scheme' 40 — a distinct looser product) are different concepts, NOT an EMICSOP-class
conflict. ZERO REPAIR — the first (a) family to condition purely declaratively: 2
answerer_only declarations + 2 subset pairs reusing the r3sw11 selectors verbatim
(child_value_not 'Not applicable' + parent_value_in [Yes-all, Yes-hourly, Piloting]); no new
vocabulary. ACCEPTED AS-IS (noted, not repaired): the 11 piloting orgs' uniform 'Subscription
model' on EWAFEES — uniform-because-true (pilots cluster on provider subscriptions), unlike
the share-plan cross-contamination. QUEUED: the WEL_SUP 32-org EWA under-tick (the wellbeing
inventory predates the 2026.4 EWA question) -> cross-book coherence queue.
BEFORE/AFTERS: EWAFEES n 220 -> 77 (excl 143): employer-funded 61.0 / employee-pays 24.7 /
subscription 14.3. EWACAP n 220 -> 77 (excl 143): no-cap 74.0 / <=50% 14.3 / other-cap 11.7.
VERIFIED: throwaway scratchpad/t31 — before/afters exact, ANSWERS BYTE-IDENTICAL (declarative-
only asserted by sha256), qa_reseed 9/9, run_gates 11/11 (pairs live, declaration validator
36/36), negative test fails closed (a non-offerer with a fee answer -> PAIR-INCOHERENCE rc=1).
LIVE: served applicable_bases == staged byte-equal (36 declarations); answers hash pinned
BEFORE the config write and re-verified AFTER the full chain — byte-identical, n=232,490;
re-aggregated 944; provably-fresh :8060; both cards serve n=77/excl=143 with the ruled
caption, no N/A bars; ZERO-CONTRADICTION RE-VERIFY ON LIVE (both children 0/0);
post-write run_gates 11/11. Commit alongside this entry. REMAINING QUEUE: insured-benefits
cluster (behind the IP-authority diagnosis), DEFERRAL repair (141), presence-gate minting
(recognition, business-need car), blanket-DK diff, TIME_IVF retirement-review.

## Blanket-DK strip — the no-DK rule enforced platform-wide (r3sw13, ruled + applied 20 July 2026)
CLASSIFY-DON'T-BLANKET-STRIP (69 metrics, 70 DK-type options, all ruled): 62 STRIPPED (61 (a)
+ PROP_202fecc6 moved from keep — its explicit 'No' already carries not-tracking); 3 KEEPS as
ruled exceptions (PROP_674db2fc 'Provided but access not tracked', PROP_e1d1e604 'Not measured
/ not tracked', PROP_3d4fc4e7 'Not measured' — substantive practice statements; not-measuring
IS the finding) + PROP_634adacd 'Not measured / varies widely' (neither half DK, optional
relabel later); 1 ROUTED (REW_BEN_SICK_005 -> the N/A programme, OSP-exists conditioning,
joins the sick/insured family behind the IP diagnosis); 3 SPECIALS redesigned (RED_PAY_01
merged option -> plain 'Other'; RED_TERM_01 + RED_NOTICE_01 -> plain 'Not applicable' is_na,
RED_NOTICE_01's r3sw10 answerer_only declaration RELABELLED ATOMICALLY — na_options
['Not applicable'], asserted against post-edit labels, validator green).
THE STRIP: 629 answers N-EXCLUDED (never redistributed), history-snapshotted; 62 options
removed/replaced in the BANK (design change — future respondents can't pick DK), scoring
na_codes/option_scores pruned, question_version bumped; the matcher catches label variants
('Unsure', 'Not sure', 'not tracked'), not just the literal. Answers 232,490 -> 231,861.
Shape PROVABLY INVARIANT (pure n-exclusion scales all remaining shares uniformly — no modal
or ordering change anywhere); GATE-NEUTRAL BY CONSTRUCTION (no ordering in the register
contains a DK label — verified globally; zero tier-1 frozen overlap); zero positionability
flags. PLATFORM-WIDE ASSERT: no active Reward question carries a DK-type label outside the
ruled exceptions — enforced in the migration AND re-asserted on live post-write.
TWO GUARD CATCHES (disclosed, both the guards working): ① the keep ruling protects the
OPTION, not the metric — PROP_e1d1e604 holds a ruled keep AND a ruled strip; the first
throwaway apply correctly ABORTED on a too-coarse metric-level assert; fixed to option-level
(keep_options in the scope file), fresh throwaway, keep verified byte-unchanged (still on
graph at 14). ② the strip tripped qa_engine_audit's REGEN_WHITELIST lineage pins
(EXT_REW_GAP_013, ALLOW_03 — documented seeded outputs include DK); extended the Diff-3
supersession pattern CONDITIONALLY: a pin drops a stripped label from its expectation ONLY
when that label is actually gone from the store, keyed off the committed ruled-scope file —
throwaway logs exactly the two ruled adjustments, live pre-write audit exits 0 with ZERO
adjustments (no red window), and any UNRULED deletion still fails.
VERIFIED: throwaway scratchpad/t33 — apply exact, qa_reseed 9/9, run_gates 11/11,
declaration validator green on staged. LIVE (backup lumi.db.bak_pre_r3sw13_dkstrip_20260720):
post-write match EXACT (0 answer cells AND 0 question-bank rows differing vs throwaway;
231,861); served applicable_bases == staged; LIVE BANK-SWEEP DK-FREE re-assert green; render
spot-check PASS (no DK bars, keeps on-graph, RED_PAY_01 n=154 with plain 'Other');
re-aggregated 944; provably-fresh :8060; post-write run_gates 11/11 (2 ruled pin adjustments
logged). Commit alongside this entry. QUEUE: sick/insured family (SICK_005 route + IP
diagnosis), DEFERRAL repair (141), presence-gate minting, TIME_IVF retirement-review,
PROP_634adacd optional relabel.

## PMI eligibility-by-level — haver conditioning + ruled re-steepen (r3sw14, ruled + applied 20 July 2026)
COHERENCE GATE FIRST (standing (a)-family discipline): NOT clean — 48 CICOVER-class (any-Yes
orgs NOT REW_BEN_038 PMI-havers) + 48 DEFERRAL-class (havers all-No), SYMMETRIC: the old
seed's any-Yes set matched the haver COUNT (130) but not the SET — the pre-r3sw6 presence-map
defect class that broke the retired PMIMH metric. THE RULED HAVER RE-SEED IS THE REPAIR (both
classes vanish by construction); the 48/48 counts pinned as a pre-apply assert.
RE-SEED (ruled cliff, both fixes one diff): Board 95 / Director 90 / Head-of 80 / SrMgr 70 /
Manager 20 / Supervisor 2 / Frontline 0 over the 130 havers -> served 95.4/90.0/80.0/70.0/
20.0/2.3/0.0. Implemented as TOP-DOWN PREFIX DEPTHS latent-ranked descending (depth hist
0:6/1:7/2:13/3:13/4:65/5:23/6:3) — G10 monotonicity 1.0 + depth-latent hold by construction.
The SrMgr->Manager cliff (70->20) is the by-level shape correction (Diff-13 class). Frontline
0% is a REAL '0% eligible' row on the graph, not an exclusion. ACCEPTED CONSEQUENCE (ruled):
the Board-95% line leaves 6 havers all-No ('offers PMI, no standard level eligibility') —
discretionary/grandfathered bucket, honest at n=130.
CONDITIONING: conditioned-mode declaration (rows exist ONLY for havers; non-havers' 630 rows
deleted — answers 231,861 -> 231,231), caption 'of PMI-holding organisations', subset pair
child_any_answer ⊆ REW_BEN_038 PMI tick (r3sw8 composition vocabulary verbatim). FAMILY-SET
ASSERT: composition base == havers EXACTLY (130=130) — the PMI family (composition, by-level,
premium-modulo-Thornbridge) now conditions on ONE authority. Verdict stays suppressed (Diff-14
unbenchmarked flag asserted-untouched; EST shape renders, no market position). NEGATIVE-PROVEN:
a non-haver matrix row -> PAIR-INCOHERENCE rc=1. DEMO: Thornbridge's all-No rows were BULK-SEED
(2026-06-11, not genuine entries) — deleted; not a ticker -> outside the base, sees peer chart
n=130/answered:false; consistent with r3sw8 ④ (demo cleanup queued: tick PMI first, then answer).
DISCLOSED WINDOW: pair hot in the working tree against the pre-repair live 48/48 during the
build (r3sw11-pattern single-session window, closed by this write).
VERIFIED: throwaway scratchpad/t34 — apply exact, qa_reseed 9/9 (G10 explicitly green),
run_gates 11/11, negative test fails closed, demo recompute proven. LIVE (backup
lumi.db.bak_pre_r3sw14_pmilevels_20260720): post-write match EXACT (0 cells vs throwaway,
231,231; served applicable_bases == staged, 37 declarations); ZERO-CONTRADICTION RE-VERIFY ON
LIVE: 48/48 -> 0/0 (answerers==havers exactly, zero non-haver rows; residual = the ruled 6
all-No havers); re-aggregated 944; provably-fresh :8060; live cliff serves exactly
95.4/90.0/80.0/70.0/20.0/2.3/0.0 with the base caption; post-write run_gates 11/11. Commit
alongside this entry. QUEUE: sick/insured family (SICK_005 + IP diagnosis), DEFERRAL repair
(141), presence-gate minting, TIME_IVF retirement-review, demo-data cleanup (Thornbridge PMI
tick), PROP_634adacd relabel.

## PMI sector-gate — parent re-gate + atomic family re-condition (r3sw15, ruled + applied 20 July 2026)
THE FLAT ~59% PMI-HAVER SEED WAS WRONG BOTH WAYS — over-included the charity/public tails AND
under-included the large-skewed commercial cohort. Sourced (r3sw15 research, CIPD H&W 2025
Table 2, grade B, adversarially verified from CIPD's primary PDF, corroborated by CIPD 2022 +
gov.uk frameworks) and RULED: sector-gate REW_BEN_038 (PMI-exists) to Commercial 77% (CIPD
large-private 250+, COHORT-MATCHED — not all-private 61%, same principle as HOL_001/virtual GP),
Charity 24%, Public 17%, Education 40% (EST — mixed state/private, no clean CIPD split).
HAVER MOVEMENT 130 -> 153 (the honest arithmetic of flat-77% commercial = 144/187, NOT the ~139
blend headline): +27 commercial gated-in (highest-latent non-havers), -3 charity + -1 public
trimmed (lowest-latent havers), 126 retained. Post-gate rates on target: commercial 144/187=77,
charity 2/8=25, public 3/15=20, education 4/10=40.
ATOMIC FAMILY RE-CONDITION (all three PMI children condition on REW_BEN_038 — parent move +
children move together, NO parent-first-then-children lag): composition (r3sw8) additive —
retain 126 unchanged, delete 4, add 27 incidence-matched to the ruled prevalences (diff8, no
spike; served 77.8/49.7/60.8/41.8/26.8/22.9 vs ruled, <0.5pp). by-level (r3sw14) additive —
retain 126 depths, delete 4, add 27 on the ruled cliff via depth-histogram scaled to 27
(served 95.4/90.2/80.4/69.9/20.9/2.6/0, <1pp, G10 monotonicity 1.0). premium (r3sw6)
RE-DERIVED over the 153 havers.
PREMIUM RE-DERIVE PRINCIPLE (ruled ②, recorded as standing): premium's additive first pass
drifted the medians +£35-85 (~4%) because retained stayed on the old 130-rank multiplier while
new used the 153-rank; since SINGLE RENDERS A VERDICT vs the ruled £800 anchor, premium
full-re-derives the r3sw6 multiplier ladder over the 153 havers (uniform [0.5,1.5] latent-ranked
desc, £10-rounded) — restoring medians 800/1600/2000 and P25/P75 at 1.25/0.75x EXACTLY by
construction. Retained-haver premium churn ACCEPTED (all seed); Thornbridge's GENUINE
£680/£1,200/£1,600 untouched. STANDING PRINCIPLE: re-derive only where an anchor must be held,
leave the rest additive. Served median incl. Thornbridge 795/1590/1990 (the £5-10 one-org pull,
inside the r3sw6 one-rank quantum).
COHERENCE GATE — ZERO MISMATCH, ALL THREE (asserted pre-commit AND re-verified on live):
composition answerers == 153 havers EXACTLY; by-level == 153 EXACTLY; premium == 153 havers ∪
{Thornbridge} (the documented non-haver with genuine entries, demo cleanup still queued). The
count-matched-but-set-mismatched defect (just fixed on by-level at r3sw14) CANNOT recur — the two
family subset pairs read the moved REW_BEN_038 live and FAIL CLOSED (a non-haver given a
composition or by-level row -> PAIR-INCOHERENCE rc=1, negative-proven). Verdict statuses
UNTOUCHED (composition/by-level unbenchmarked EST; premium split-verdict partner/family
suppressed). Disclosed pre-write window (pairs hot vs the pre-regate parent until the write).
VERIFIED: throwaway scratchpad/t35 — coherence exact, before/afters on ruled targets, premium
haver-median exact, negative tests fail closed, qa_reseed 9/9, run_gates 11/11. LIVE (backup
lumi.db.bak_pre_r3sw15_pmisectorgate_20260720): answers 231,231 -> 231,484 (+253: parent 31
edits value-only, +27 orgs x(1 comp +7 bylev +3 prem)=+297, -4 orgs x11=-44); post-write match
EXACT (0 cells vs throwaway; served config == staged); re-aggregated 944; provably-fresh :8060;
LIVE ZERO-MISMATCH COHERENCE RE-VERIFY across all three children (composition 153, by-level 153,
premium 154); post-write run_gates 11/11. Commit alongside this entry. QUEUE: sick/insured family
(SICK_005 + IP-authority diagnosis), DEFERRAL repair (141), presence-gate minting, TIME_IVF
retirement-review, Thornbridge demo cleanup (PMI tick), PROP_634adacd relabel.

## DEFERRAL parent re-anchor — listing/FS gate + child re-condition (r3sw16, ruled + applied 21 July 2026)
THE PARENT WAS THE MIS-SEEDED AUTHORITY (not the child — unlike share-plan). REW_INC_069 claimed
82% defer (182 orgs), provably FLAT across sector and size, with 36 orgs "deferring" that have no
bonus scheme. Sourced (r3sw16 research: PRA/FCA SYSC 19D grade-A regulatory anchor + Deloitte FTSE
grade-C + CIPD/IA) and RULED: deferral is a LISTED-COMPANY / REGULATED-FS phenomenon —
re-anchored on a LISTING+FS GATE, NEVER size. FS industry 70% / Listed PLC 90% / PE-backed 35% /
general (private/subsidiary/public/charity/mutual) 12% (EST). HAVER-Yes 182 -> 53 DEFERRERS (24%,
central scenario), concentrated FS 6 / listed 27 / PE 4 / general 16. SIZE PROVABLY OUT OF THE
MECHANISM: the gate reads ownership_type + industry only (asserted); cross-check by ownership
(PLC 82% deferring / Private 18% / Subsidiary 23%) confirms ownership drives it; the emergent
91%-large skew is because listed cos ARE large, not a size gate. Within each segment: PREFER orgs
with real child vehicle detail (retain the coherent), then latent-ranked.
SUB-CASES RESOLVED BY THE GATE: all 41 no-bonus orgs -> No-deferral (the 36 parent-Yes-no-bonus
absurdities gone); Varies (15) -> 6 Yes / 9 No; 3 reverse (parent-No, child-substantive) -> all Yes.
Parent Yes-flavour narrow/exec-concentrated (Exec 24 / Senior 21 / Wider 8).
CHILD RE-CONDITION (REW263_INC_DEFERRAL now CONDITIONED on the deferrer set): all old rows
deleted, one per deferrer — 25 retained keep their real vehicle, 28 new incidence-matched to the
retained vehicle spread and SECTOR-PLACED (shares/multi-year to FS/listed) — FIXES the child's FS
BLIND-SPOT (FS deferrers 1 -> 6). Served vehicle dist 1yr 15 / multi-year 17 / shares 21.
TWO-LEVEL CHAIN COHERENCE (asserted pre-commit + re-verified on live): parent-Yes set == child
answerers == 53 EXACTLY; zero parent-Yes with no-bonus; zero Varies; child ⊆ parent-Yes ⊆
has-bonus (both levels). Two new subset pairs (child_any_answer ⊆ parent_value_in Yes-set;
child_value_not 'No deferral' ⊆ grandparent parent_value_not 'None') — NEGATIVE-PROVEN both ways.
Verdict status unchanged (both Practice — prevalence, no market verdict).
PROCESS CATCH (disclosed, the gated flow working): the FIRST live write passed all its own asserts
(53 deferrers, distribution exact, chain locked, suite 11/11) but the post-write throwaway match
found 4 differing cells — a NET-ZERO flavour swap (2 orgs Exec<->Wider x2, distribution identical)
caused by the flavour-retention step ITERATING OVER A SET (non-deterministic order across
processes). The live state was coherent and correct but NOT REPRODUCIBLE. Per discipline the
non-reproducible write was NOT accepted: the migration was fixed (sort the iteration —
deterministic, verified by two independent runs byte-identical), live RESTORED from
lumi.db.bak_pre_r3sw16_deferral_20260721, and the FIXED migration re-applied. Standing lesson:
NEVER iterate a set where the output depends on order — sort with a hash tiebreak.
VERIFIED: throwaway — coherence exact, qa_reseed 9/9, run_gates 11/11, negative tests fail closed.
LIVE (re-run, deterministic): post-write match EXACT (0 cells vs throwaway; served config ==
staged, child conditioned); answers 231,484 -> 231,317 (child 220 rows -> 53); re-aggregated 944;
provably-fresh :8060; LIVE TWO-LEVEL CHAIN RE-VERIFY (parent-Yes==child==53, zero no-bonus-defer,
chain both levels); post-write run_gates 11/11. Commit alongside this entry. QUEUE: sick/insured
family (SICK_005 + IP-authority diagnosis), presence-gate minting (recognition, business-need car),
TIME_IVF retirement-review, Thornbridge demo cleanup, PROP_634adacd relabel.

## IP-authority resolution + sick/insured cluster conditioning (r3sw17, ruled + applied 21 July 2026)
IP AUTHORITY RULED: REW_BEN_046 (dedicated structured "Does your org offer income protection?"
No/Short/Long/Both, 80 havers, CIPD H&W 2025) is THE income-protection authority; REW_BEN_038's
generic checklist "Income protection" tick (62) is the UNDER-REPORT DEFECT (same class as the
WEL_SUP EWA under-tick — a 20-item inventory systematically under-counts vs a dedicated question).
The disagreement was 92 orgs GROSS (not the 18 net): 55 under-ticked (046-haver, 038-not) + 37
over (038-tick, 046=No). The IP-detail children leaned ~2x to 046 (047/GIPREHAB 54 vs 29; 048
80 vs 43) — the tiebreaker.
PART 1 — 038 ALIGNED to 046: +55 IP tokens / -37 IP tokens -> 038 IP-haver 62 -> 80 == 046,
disagreement to ZERO. PMI-SAFEGUARD (038 is the r3sw15 PMI parent — HARD ABORT on any PMI move):
the IP-token edit touches only the IP position in each 038 multi-value, NEVER the PMI token —
PROVEN: PMI-haver set BYTE-IDENTICAL pre/post (153==153), both PMI family subset pairs
(composition, by-level) re-verify ⊆ PMI-haver clean. The r3sw15 sector-gate is UNDISTURBED.
IP tick proven ORTHOGONAL to PMI tick.
PART 2 — CLUSTER CONDITIONED on 046 (repair-then-condition; the children were over-seeded):
REW_BEN_047 (waiting period) 38 CICOVER cleared + 26 incidence-matched -> 80; REW_BEN_048
(salary replacement) 65 CICOVER cleared (was 145 substantive, badly over-seeded) -> 80;
REW264_HLT_GIPREHAB 38 cleared + 26 seeded -> 80. Each == the 80 046-havers exactly.
SICK_005 (OSP eligibility-rules governance) conditions on OSP-EXISTS (SICK_001 enhanced/
combination, 119 base) — a SEPARATE parent, NOT IP. SUBSET not equality (ruled): answerers
110 ⊆ 119 — documentation-maturity is a real governance filter; forcing equality would fabricate
answers. The 4 OSP-haver DKs stripped + the DK option removed from the bank (folds the
r3sw13-routed SICK_005 DK; the 8 non-OSP DKs were the N/A-in-disguise, resolved by conditioning).
Four new subset pairs (3 IP children ⊆ 046 parent_value_not 'No'; SICK_005 ⊆ SICK_001
parent_value_in enhanced/combination) — NEGATIVE-PROVEN. Verdicts unchanged (children Level,
EST-suppressed).
VERIFIED: throwaway scratchpad/t37 — PMI-untouched proof 153==153, coherence exact, qa_reseed
9/9, run_gates 11/11, negative tests fail closed both pairs. LIVE (backup
lumi.db.bak_pre_r3sw17_ipcluster_20260721): post-write match EXACT (0 cells vs throwaway; served
config == staged); PMI-UNTOUCHED RE-VERIFY ON LIVE (PMI-set pre==post 153==153, both family
pairs ⊆ PMI-haver — the safeguard on shipped work); cluster coherence 038-IP==046==80, each IP
child==80, SICK_005 110⊆119, DK gone; re-aggregated 944; provably-fresh :8060; post-write
run_gates 11/11. Commit alongside this entry. QUEUE: presence-gate minting (recognition,
business-need car), TIME_IVF retirement-review, Thornbridge demo cleanup, PROP_634adacd relabel.

## PROP_634adacd option relabel — not-measured harmonisation (r3sw18, ruled + applied 21 July 2026)
RELABEL: PROP_634adacd's kept option "Not measured / varies widely" -> "Not measured", harmonising
to the canonical label on the other kept not-measured options (PROP_e1d1e604 "Not measured / not
tracked", PROP_3d4fc4e7 "Not measured"). Option CODE (NOT_MEASURED_VARIES_WIDELY) + is_na + order
unchanged; question_version v2.0 -> v2.1.
STORAGE FINDING (surfaced before write, ruled): the bank stores answers by LABEL, not code (verified
— the 7 stored values are all option-label strings). So "relabel the option" and "answers
byte-identical" are MUTUALLY EXCLUSIVE for this metric: leaving the 2 answers byte-identical would
orphan them (value 'Not measured / varies widely' matches no option label -> dropped from the
distribution). David ruled RELABEL + RETAG the 2 answer values to keep them mapped — distribution
unchanged, mapping preserved, but NOT answers-byte-identical (2 cells change to track the label).
DISTRIBUTION BYTE-IDENTICAL BY CODE (the meaningful invariant): {0:8, 0.1-1.9:25, 2.0-2.9:42,
3.0-3.9:50, 4.0-4.9:23, 5.0+:16, NOT_MEASURED_VARIES_WIDELY:2} pre==post; the 2 answerers still map
to the option (now rendered "Not measured"). No re-seed, no verdict change. L1-safe (PROP_634adacd
is RESEED-whitelisted / DB-origin, so the 2-cell retag doesn't trip the CSV-diff).
VERIFIED: throwaway — distribution byte-identical by code, non-target book identical, option reads
"Not measured", 2 answers mapped, run_gates 11/11. LIVE (backup
lumi.db.bak_pre_r3sw18_relabel_20260721): post-write match EXACT (0 cells vs throwaway);
NON-TARGET BOOK byte-identical vs pre-write (only PROP_634adacd's 2 answers + its option label
changed); rendered label "Not measured", version v2.1; re-aggregated 944; post-write run_gates 11/11.
Commit alongside this entry. The not-measured family is now label-consistent. QUEUE: presence-gate
minting (recognition, business-need car), TIME_IVF retirement-review, Thornbridge demo cleanup.

## PMI eligibility-rules redesign — 6-opt sprawl -> 3-opt conditioned EST (r3sw19, ruled + applied 21 July 2026)
REW_BEN_044 "What are the PMI eligibility rules?" was a 6-option MULTI_SELECT (effectively single —
0 orgs picked >1) over all 220 orgs, "Not offered" (37.3%) the biggest bar, grade/level under-
weighted (25%); it ALSO rendered a verdict (direction=higher_is_better) AND was the standalone
62.8% PMI-offer MARGINAL — with broken coherence (31 non-havers carried a rule, 46 PMI-havers said
"Not offered"). REDESIGN (ruled ①): type multi_select -> single_select; options 6 -> 3 (All
employees / Grade/level restricted / Service length requirement); post-probation FOLDS to Service,
contract-type dropped as noise, "Not offered" is NOT an option (non-havers leave via conditioning);
CONDITIONED on the 153 PMI-havers (r3sw15 sector-gated set — the PMI-family authority); grade-
dominant EST re-weight Grade/level 138 (90%) / All 12 (8%) / Service 3 (2%) — consistent with the
by-level cliff (PMI is seniority-gated). VERDICT FLIP (ruled ②): higher_is_better -> unbenchmarked
EST (fixes the hidden inconsistency — it showed "No signal" yet rendered a verdict). MARGINAL
RETIREMENT (ruled ③): the flat 62.8% offer marginal RETIRED (generator_rules._retired_marginals)
— SUPERSEDED by the sector-gated 153-haver base. STANDING PRINCIPLE reaffirmed: a sector-honest
seed supersedes a flat all-UK marginal; the PMI family now has ONE offer authority, not two.
L1-safe (RESEED-whitelisted), generator pins unaffected (register 249, pf_count 7). Dual-config
atomic (r3sw7 path-isolation): applicable_bases (conditioned) + market_position_config
(unbenchmarked). Subset pair REW_BEN_044 ⊆ PMI-haver added.
PMI-FAMILY UNTOUCHED BY CONSTRUCTION: the migration touches ONLY REW_BEN_044 — never the parent
REW_BEN_038 — so the 153-haver set + composition/by-level/premium bases are inherently unmoved;
asserted pre-commit AND re-verified on live (PMI-haver 153==153, composition 153, by-level 153,
premium 154 all pre==post vs the backup).
VERIFIED: throwaway scratchpad/t39 — type single_select, answerers==153, dist 138/12/3, verdict
suppressed, PMI-family unmoved, qa_reseed 9/9, run_gates 11/11. LIVE (backup
lumi.db.bak_pre_r3sw19_pmieligrules_20260721): post-write match EXACT (0 cells vs throwaway;
answers 230,794 -> 230,727); PMI-FAMILY-UNTOUCHED RE-VERIFY ON LIVE (153==153 + all children
bases pre==post); coherence single_select / answerers==153 / 138-12-3 / suppressed; re-aggregated
944; post-write run_gates 11/11. Commit alongside this entry. QUEUE: presence-gate minting
(recognition, business-need car), TIME_IVF retirement-review, Thornbridge demo cleanup.

## Thornbridge PMI-tick cleanup — demo org into the haver set, family 153->154 (r3sw20, ruled + applied 21 July 2026)
THE INCOHERENCE (carried since r3sw6): Thornbridge (director@thornbridge.example, Retail/PLC/
50-249) held GENUINE PMI premium entries (£680/£1,200/£1,600, David's own UI entries) but never
ticked "offers PMI" in REW_BEN_038 — premiums without the scheme, the "documented exception".
FIX (parent-move, NOT orthogonal): tick Thornbridge (REW_BEN_038, its 6 other benefit ticks
preserved) -> PMI-haver 153 -> 154, commercial 144 -> 145. Sector-gate-SAFE: REW_BEN_038's
PMI-share is not count-gated (no marginal/frozen), and there is no ongoing 'commercial==144'
gate — the +1 is coherent.
RE-CONDITION +1 (all three children are EQUALITY-conditioned answerers==havers, so Thornbridge
MUST answer — none could be blank): premium £680/£1,200/£1,600 GENUINE, kept (the documented-
exception RETIRED — a real haver now); elig-rules seeded 'Grade/level restricted' (the 90%
modal); by-level seeded DEPTH-4 (board/director/head-of/senior-manager eligible, monotone
prefix); composition seeded out-patient + physiotherapy (the two most common elements). The
three seeds are INTERNALLY CONSISTENT (grade-restricted -> top-4 by-level -> out-patient/physio)
and plausible for a Retail/PLC/50-249 org. Answers 230,727 -> 230,736 (+9: parent value-only,
+1 comp, +7 by-level, +1 elig; premium untouched). Brief said 250-999; the org is actually
50-249 (corrected).
COHERENCE-GATE AGAINST 154: all four family bases == 154 (composition, by-level, elig-rules,
premium); the three existing pairs re-verify ⊆ 154; NEW PREMIUM PAIR ADDED (premium
child_any_answer ⊆ REW_BEN_038 PMI) — now guardable because Thornbridge is a genuine haver,
CLOSING THE LAST UNGUARDED FAMILY CHILD (all 4 now pair-guarded). Negative-proven: a non-haver
given a premium row -> PAIR-INCOHERENCE rc=1. Verdicts unchanged.
VERIFIED: throwaway scratchpad/t40 — all 4 bases == 154, premium pair fails closed, demo
recompute shows Thornbridge answers all four (was answered:false on every one), qa_reseed 9/9,
run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3sw20_thornbridge_20260721): post-write match
EXACT (0 cells vs throwaway); FAMILY COHERENCE RE-VERIFY against 154 (PMI-havers 154, all 4
bases == 154 ⊆ havers, Thornbridge a member, genuine premium preserved); re-aggregated 944;
provably-fresh :8060; LIVE DEMO RECOMPUTE — Thornbridge answers all four PMI charts; post-write
run_gates 11/11. Commit alongside this entry. The PMI family is now fully coherent and fully
pair-guarded. QUEUE: presence-gate minting (recognition, business-need car), TIME_IVF
retirement-review.

## Life-assurance multiple redesign — offer nudge + 1×-fix + answerer_only (r3sw21, ruled + applied 21 July 2026)
PREMISE CORRECTION (recorded — the load-bearing research finding): the "death-in-service is offered
by ~85-90%" intuition is LIVES-COVERED (~85% of EMPLOYEES have it, because the large employers who
offer it hold most headcount), NOT the EMPLOYER offer rate (~62%, CIPD Reward Feb 2026 large, grade
B). For an org-per-row benchmark the correction is a MINOR nudge, not a rescue. Lives-vs-employers
is the single biggest trap in this topic.
REW_BEN_045 "life assurance multiple, main population" showed "Not offered" 44% distorting the
multiples + 1×=0 (a defect). THREE FIXES (ruled): ① OFFER NUDGE — the 9 highest-latent "Not
offered" orgs (all large 1000+/5000+/10000+) -> offering; offerers 123 -> 132, "Not offered" 97 ->
88. Landed 60%/40%, NOT the 62% large-headline — the old marginal was already an SME-18.5/large-62
blend, and the SME-50-249 orgs pull the cohort blend below 62% (the honest cohort-matched number).
② 1×=0 FIXED — all 132 offerers re-seeded EST 10/30/30/30 (1× 13, 2× 40, 3× 40, 4×+ 39; rendered
9.8/30.3/30.3/29.5) — 1× carries its small-but-real share, flat core, no false modal (the
1×/2×/3×/4× split is paywalled/unsourced — grade C). ③ CONDITION + SUPPRESS — answerer_only
excludes "Not offered" (multiples render over the 132 offerers, "Not offered" bar gone, caption
"of organisations offering life assurance"); verdict EST-SUPPRESSED (was higher_is_better); the
flat offer marginal RETIRED (generator_rules, superseded by the cohort-matched seed — the r3sw19
pattern). NO EXTERNAL SUBSET PAIR (correct): REW_BEN_045 is single-select, so "Not offered" XOR a
multiple is STRUCTURALLY guaranteed — the r3sw10 (b)-batch pattern, unlike PMI's separate-parent.
4-ORG DISCREPANCY (note-don't-fix, ruled): REW_BEN_038 'Life assurance' tick (119) vs REW_BEN_045
offer (132 post-nudge) — a small residual; Thornbridge is one of the discrepant orgs (ticks Life
assurance in the inventory, "Not offered" on the multiple) — shows as a non-offerer viewing the
offerer chart (conditioning working). Alignment QUEUED for a future coherence/demo pass.
DUAL-CONFIG atomic (r3sw7). Answers UNCHANGED at 230,736 (all UPDATEs). VERIFIED: throwaway
scratchpad/t41 — offer 132, 1× fixed, 'Not offered' excluded (rendered n=132), verdict suppressed,
qa_reseed 9/9, run_gates 11/11. LIVE (backup lumi.db.bak_pre_r3sw21_lifeassurance_20260721):
post-write match EXACT (0 cells vs throwaway); non-target book hash-identical; served configs ==
staged; coherence offerers 132, multiple-answerers==offerers, 1×=13; re-aggregated 944;
LIVE RENDER RE-VERIFY (n=132 over offerers, 'Not offered' excluded, verdict suppressed);
post-write run_gates 11/11. PROCESS NOTE (disclosed): the first live render-check assert fired
BEFORE the re-aggregate and read the stale payload (n=220) — sequencing bug, not a data fault
(the re-aggregate + gates were green); re-verified genuinely post-aggregate. The "re-aggregate
before serving-checks" doctrine (r3sw6) applies to inline live-write verify blocks too. Commit
alongside this entry. QUEUE: presence-gate minting (recognition, business-need car), TIME_IVF
retirement-review, the 4-org life 038-vs-045 alignment.

## PMI excess/cost-share conditioning — 6th PMI-family child, subset (r3sw22, ruled + applied 22 July 2026)
REW263_BEN_PMIEXCESS "what employee cost-share or excess applies to PMI" showed "Not applicable"
56.4% distorting the cost-share distribution. THE EQUALITY-VS-SUBSET CHECK CAME BACK MESSY (the
count-matched-set-mismatched pattern): of 154 PMI-havers only 70 reported a real excess, 84
answered N/A, and 26 NON-havers held a real excess (CICOVER). RULED (David, subset-no-retag): the
84 haver-unknowns are LEFT OUT of the excess-type distribution — NOT retagged to "No excess",
because that would FABRICATE rare zero-excess generosity ("No excess" is a real minority stance,
not a default). SEMANTIC CORRECTION recorded: a haver's "Not applicable" here is a genuine
no-detail, and No-excess is rare-not-default — so the honest render is over the 70 who reported a
cost-share (SUBSET), not an equality that would invent 84 "No excess" answers.
DATA: 26 CICOVER non-haver excesses cleared -> "Not applicable" (a non-haver cannot have a PMI
excess); the 70's distribution UNCHANGED (No excess 34/48.6% modal, per-claim 16/22.9%, per-year
12/17.1%, co-pays 8/11.4% — no re-weight). CONFIG: answerer_only na_options=["Not applicable"],
caption "of PMI-holding organisations reporting a cost-share" (honest to the 70-base, NOT implying
154). Verdict already suppressed (unchanged). SUBSET PAIR: child_value_not "Not applicable" ⊆
REW_BEN_038 PMI — the 6th PMI-family child now pair-guarded (negative-proven: a non-haver given an
excess -> PAIR-INCOHERENCE rc=1). PMI-FAMILY-UNTOUCHED (this ADDS a child, does NOT move the
parent): parent 154 + the 5 existing children (composition/by-level/eligibility-rules/premium)
all unmoved — asserted pre-commit AND re-verified on live vs the backup.
VERIFIED: throwaway scratchpad/t42 — subset 70 ⊆ 154, N/A excluded (render n=70), family unmoved,
qa_reseed 9/9, run_gates 11/11, negative test fails closed. LIVE (backup
lumi.db.bak_pre_r3sw22_pmiexcess_20260722): post-write match EXACT (0 cells vs throwaway; answers
unchanged 230,736); PMI-FAMILY-UNTOUCHED RE-VERIFY ON LIVE (parent 154 + all 5 children bases
pre==post); excess coherence 70 ⊆ 154, N/A excluded, No-excess 48.6%; re-aggregated 944 BEFORE the
render-check (r3sw21 sequencing lesson applied); post-write run_gates 11/11. Demo: Thornbridge is a
haver-with-N/A -> correctly subset-excluded (sees the excess chart as context). Commit alongside
this entry. The PMI family is now SIX children, all conditioned on the 154-set and pair-guarded.
QUEUE: presence-gate minting (recognition, business-need car), TIME_IVF retirement-review, the
4-org life-assurance 038-vs-045 alignment.

## Dental cover sector-gate + funding conditioning — Design B, 038 Dental-tick as parent (r3sw23, ruled + applied 21 July 2026)
TWO-SIGNAL DISCOVERY: dental had TWO mis-seeded signals disagreeing — REW_BEN_038 "Dental cover"
tick (42, cost-heavy) and the REW263_BEN_DENTAL funding metric (32, cost-heavy), 9 overlap. Dental
is a RARE, sector-specific perk. RULED (David, Design B): the 038 Dental-tick is the PARENT (the
PMI pattern) — sector-gate it, condition the funding metric on it, ALIGNING both signals (the
42-vs-32 disagreement resolved, not relocated — the IP/PMI-eligibility/EMICSOP lineage).
SECTOR-GATE: 038 Dental-tick 42 -> 11, re-concentrated perk 8 / cost 2 / media 1 (from the
cost-heavy scatter); token removed from 31, prefer-coherent-then-latent. RATE-vs-COUNT (ruled a):
David's explicit ~5% (~11) WINS over the illustrative 22/4/12 band (which summed to 16) —
cost-constrained lands ~1% (2 orgs), the honest realization of "rare AND very sector-specific".
COLLAPSE: "Not offered" + "Not applicable" both vanish — the funding metric is CONDITIONED
(non-tickers' 209 rows deleted), n=11. FUNDING: Voluntary 7 / Employer-paid 4 -> served 63.6/36.4
(~65/35 voluntary-dominant EST). Answers 230,736 -> 230,527.
EST/GRADE-C (verdict SUPPRESSED, unbenchmarked=True): direction sourced (CIPD private-2.5x-public
+ LaingBuisson small insured base) but the CIPD 24% is DENTAL CASH PLANS — the WRONG product; no
free dental-INSURANCE sector data exists, so the rates are estimated. Thin base 11 accepted (rare
benefit, above the n<5 floor, suppressed anyway). Flat offer marginal RETIRED (superseded).
PMI-SAFEGUARD (038 is the PMI parent — HARD ABORT on any PMI move): the Dental-token edit touches
only the Dental position, never the PMI token — PROVEN pre-commit AND re-verified on live: PMI-tick
set 154 BYTE-IDENTICAL, all 5 existing PMI children bases (composition/by-level/elig-rules/premium
154, excess 220) unmoved. Dental token orthogonal to PMI. SUBSET PAIR (funding ⊆ 038 Dental-tick)
— 6th subset pair, negative-proven (a non-ticker given funding -> PAIR-INCOHERENCE rc=1).
G9 FIX (disclosed, r3sw13 class extended): conditioning dental (deleting 209 rows) collapsed
qa_reseed's G9 bundle gate to n_orgs=1 — the all-answered benefit-generosity intersection breaks on
a CONDITIONED metric (partial base by design; the meta snapshot tags dental "Benefits", the DB says
"Health & Protection"). Fixed surgically: G9's `ben` now EXCLUDES conditioned metrics (can't drop
from rewq globally — conditioned metrics keep partial rows, unlike retired ones). Proven both ways:
throwaway 9/9 with the fix, LIVE 9/9 (no-op — no Benefits metric is conditioned on live yet).
VERIFIED: throwaway scratchpad/t43 — 11-tick == funding, no-dental bars gone, PMI 154 + 5 children
byte-identical, qa_reseed 9/9, run_gates 11/11, negative test fails closed. LIVE (backup
lumi.db.bak_pre_r3sw23_dental_20260721): post-write match EXACT (0 cells vs throwaway); PMI-SAFEGUARD
RE-VERIFY ON LIVE (PMI-tick 154==154 + all 5 children bases pre==post); dental 038-tick 11 == funding,
render n=11 (63.6/36.4), no-dental bars gone; re-aggregated 944 BEFORE the render-check; post-write
run_gates 11/11 + qa_reseed 9/9. Demo: Thornbridge isn't a dental-ticker -> correctly outside the base.
Commit alongside this entry. QUEUE: presence-gate minting (recognition, business-need car), TIME_IVF
retirement-review, the 4-org life-assurance 038-vs-045 alignment.

## Critical-illness cover-level — signal alignment + collapse + flat condition + CI⊆IP chain (r3sw24, ruled + applied 21 July 2026)
CI IS A BUNDLED GROUP-RISK BENEFIT, NOT A RARE PERK (the decisive diagnostic finding): all 52
CI-havers are also IP-havers (CI rides inside the IP+life+CI package) — so FLAT condition (like
life assurance), NOT a sector-gate (like dental). Two mis-seeded signals disagreed: REW_BEN_038
"Critical illness cover" tick (42, cost-heavy) vs the dedicated REW263_BEN_CICOVER level metric
(52, better-distributed), overlap 11.
FIX 1 — ALIGN 038 CI-TICK UP to the dedicated 52 (IP pattern, DEDICATED-SIGNAL-WINS — the reverse
of dental, where both signals were bad and the 038-tick was re-gated): ADD the token to the 41
level-only orgs, REMOVE from the 31 tick-only -> 038 CI-tick == 52 == level-havers. Two-signal
disagreement RESOLVED (not relocated), same as IP's 038->046. FIX 2 — COLLAPSE + FLAT-CONDITION:
"Not offered" (86) + "Not applicable" (82) both collapse (168 non-haver rows deleted, conditioned);
the level split renders over the 52, UNCHANGED (Fixed 40.4 / 1x 36.5 / 2x+ 23.1 — NO re-weight, NO
sector-gate). FIX 3 — CI⊆IP BUNDLE CHAIN (two-level, DEFERRAL discipline): level-answerers (52) ⊆
CI-havers (038 tick, 52) ⊆ IP-havers (046, 80). NEW child_contains PAIR SELECTOR added (child =
the 038 CI-tickers, mirrors parent_contains) so the CI-tick⊆IP bundle lock is expressible; both
pairs NEGATIVE-PROVEN (a non-ticker given a level, and a CI-tick added to a non-IP org, both ->
PAIR-INCOHERENCE rc=1). A future reseed cannot create a CI-haver who isn't an IP-haver.
PMI-SAFEGUARD (038 is the PMI parent — HARD ABORT): CI-token-only edit -> PMI-tick 154
BYTE-IDENTICAL + all 6 PMI children (composition/by-level/elig-rules/premium/excess/dental) unmoved,
asserted pre-commit AND re-verified on live. Verdict EST-SUPPRESSED, flat offer marginal RETIRED.
Answers 230,527 -> 230,359.
VERIFIED: throwaway scratchpad/t44 — chain level==CI-tick==52 ⊆ IP 80, render n=52 no-CI bars gone,
PMI 154 + 6 children byte-identical, qa_reseed 9/9, run_gates 11/11, both pair negative tests fail
closed. LIVE (backup lumi.db.bak_pre_r3sw24_cicover_20260721): post-write match EXACT (0 cells);
PMI-SAFEGUARD RE-VERIFY ON LIVE (PMI-tick 154==154 + 6 children pre==post); CI⊆IP CHAIN re-verify
(CI-tick 52 == level, CI⊆IP, level⊆IP); render n=52 no-CI bars gone; re-aggregated 944 BEFORE the
render-check; post-write run_gates 11/11 + qa_reseed 9/9. Demo: Thornbridge not a CI-ticker ->
outside the base. Commit alongside this entry. QUEUE: presence-gate minting (recognition,
business-need car), TIME_IVF retirement-review, the 4-org life-assurance 038-vs-045 alignment.

## Master N/A sweep v2 — classify every remaining N/A-bar metric; fix only the batch-safe class (r3sw25, ruled + applied 22 July 2026)
THE HEADLINE FINDING: of the 27 remaining metrics carrying a "Not applicable"-type bar (excluding
the already-declared and the Don't-know class), EXACTLY ONE is cleanly batch-safe (A). The r3sw10
(b)-batch already exhausted the clean no-parent re-percentage set; what remained is precisely the
casework the per-chart discipline exists for — this is the discipline VINDICATED, not a shortfall.
Enumeration in scratchpad/t45_nasweep.json; classification VERIFIED against the live DB by a 4-agent
parallel workflow (wqwrd2k01) that measured each candidate's parent existence + overlap rather than
trusting the r3sw9 prior. Result: A=1, B=19 (has a verified parent), C=4 (a disagreeing second
signal / Design-B), D=3 (genuine substantive N/A). RULING (David): build only (A); flag B/C/D as an
individual-ruling queue; do NOT blanket-condition B/C — "the per-chart diagnosis is what caught the
excess/dental/CI errors."
(A) THE ONE — PROP_8e0b6316 "How often is the main pay review cycle conducted?" (Pay, single_select):
"Not applicable (no pay review)" is the ABSENCE of the measured frequency, not a point on the
frequency scale (contrast the RED_TERM statutory-only floor, which IS a point on its scale -> D).
No parent-exists metric (the cadence question is top-level; the pay-review-process siblings all
presume a review exists, none gates existence); no REW_BEN_038 tick / second signal (all three 038
word-matches spurious). DECLARED answerer_only: the 9 N/A answers leave the block at aggregation
(graph AND n), re-percentaging over the 203 answerers. base 212->203, Annually 81.1->84.7%, N/A bar
removed (excluded_na=9). RENDER-ONLY: zero `answers` rows touched; verdict already suppressed (mp
unbenchmarked=True, untouched). Config-only, no migration of data — same class as the 29 r3sw10 (b)
declarations. base_label "organisations that run a pay review".
(B) NEEDS RULING — 19, each with a VERIFIED parent + measured contradiction count (the dental-42-vs-32
shape); queued, NOT auto-conditioned. Grouped by shared parent for family-rulings: BONUS-EXISTS
(parent REW_INC_103 != 'None', 179 havers) x6 — REW_INC_071 clawback (0 contra, cleanest), _065
gatekeeper (29), _060 measures (26), _070 malus (39), _104 avg-payout% (40, child 205 > parent 179),
REW263_INC_POOLFUND (26); PENSION-DC (parent REW26_BEN_PENSION_TYPE incl-DC, 199) x2 — REW264_PEN_
AEDEFAULT (20), _GREENDEFAULT (18); PENSION-SALSAC (parent WEL_BMAP pension-SS tick, 120) x2 —
REW264_PEN_SALSACIMPACT (73), _SALSACRESPONSE (77); ALLOWANCES (parent REW_PAY_016) x2 — REW_PAY_019
consolidation (clean nest but 67 payers self-N/A), _017 on-call method (severe over-answer 203 vs 71
ticked); STANDALONE x5 — REW263_PAY_COMPARATIO (parent REW_PAY_001 ranges, 29 contra + muddy 'No
formal target' option), REW265_GOV_AIDISCLOSE (parent REW262_GOV_AIINPAY, 96 contra: 'No' chosen
where N/A belongs), REW_PAY_097 pay-perf (parent PERF_03, 26), EXT_REW_GAP_005 long-service (parent
EXT_REW_GAP_004, 30), REW_INC_136 commission-structures (parent REW_INC_135, 165 — tie to COMMCAP).
(C) NEEDS RULING — 4 two-signal/Design-B: REW_BEN_041 buy-leave-max (near-DUPLICATE of REW_BEN_HOL_006
[itself a B]; the two disagree 103-vs-16 — dedup them together); REW264_BEN_EVSALSAC EV-salsac (REAL
038 tick "Salary sacrifice car scheme" 27 vs 96 metric-havers, overlap 12); REW265_INC_COMMCAP
commission-cap (two commission signals IRRECONCILABLE: REW_INC_135 Yes=36 vs REW_INC_136 has-structure
=199 — pick the authority first, rule with _136); REW_BEN_SICK_004 sick-pay waiting-period (OVERRIDES
the initial D-hint: dedicated 2nd metric REW_BEN_SICK_001 occ-sick-pay-existence disagrees 48+40).
(D) GENUINE — 3, stay on graph: RED_TERM_02 redundancy-enhancement + RED_TERM_03 redundancy-weeks
("statutory only" is a real floor, RED_TERM precedent); REW263_GOV_ETHDISREADY (N/A is 100%
concentrated in the 50-249 FTE band — a real Equality-Bill-250+ out-of-scope fact).
SEED-REALISM FLAGS RAISED (separate from conditioning — for future seed work, NOT this diff): REW_INC_132
LTI-type has a 148/211 parent-contradiction (answered near-unconditionally though REW_INC_131 says only
65 operate LTI — likely a seed-conditioning defect); RED_TERM_03 is a DEGENERATE seed (0 respondents in
any real weeks-band; both remaining options flagged is_na; RED_TERM_01/03 incoherent on 65 orgs).
VERIFIED: throwaway proof (scratchpad/r3sw25_work) — TWO separate throwaway copies aggregated with the
served vs the staged config, all 944 payloads diffed: EXACTLY 1 moved (PROP_8e0b6316), 943 byte-identical;
the moved block 212->203 with N/A gone + excluded_na=9 + Annually 84.7/Twice 6.9/Quarterly 3.0/No-regular
5.4. qa_reseed 9/9 (answers untouched), run_gates 11/11 (staged config, freeze gate PASS, qa_release 0
fail). LIVE (backup lumi.db.bak_pre_r3sw25_payreviewna_20260722): answers content-hash BYTE-IDENTICAL to
backup (230,359 rows, a0abe28c — render-only proven); post-write match EXACT (0 of 944 cells vs throwaway);
render re-verify (DB payload n=203, N/A bar gone, excluded_na=9); dev server restarted (in-proc _payload_
cache is snapshot-keyed, goes stale on re-aggregate) + SIGNED-IN HTTP GET /api/benchmark/PROP_8e0b6316
confirms what David sees: n=203, base "organisations that run a pay review", N/A bar absent, unbenchmarked
=true. Config-only (no DB mutation); server/migrate_r3sw25_payreviewna.py is the dual-guarded config
applier (dry-run default, --confirmed-by-david for the served config, atomic tempfile+os.replace).
QUEUE now carries the 26-metric B/C/D individual-ruling work-list (family-rulings available: bonus x6,
HOL_006+BEN_041 dedup, COMMCAP+INC_136 commission-authority) + the two seed-realism flags, ahead of the
prior queue (presence-gate minting, TIME_IVF retirement-review, 4-org life-assurance 038-vs-045).

## Bonus-exists family ×6 — clear the impossible + condition on REW_INC_103 (r3sw26, ruled + applied 22 July 2026)
The first bonus-family ruling from the r3sw25-B work-list. Parent REW_INC_103 != 'None' (179 bonus-havers)
is the SOLE clean bonus authority — no 038 tick, no competing existence signal (diagnostic verified: every
other bonus metric is a detail child that presupposes a scheme). The 41 None-orgs SYSTEMATICALLY over-
answered the bonus-detail children with realistic values (all 41 over-answer >=1 child; 9 over-answer all
five) — the "over-population" seed defect. r3sw5 PART-B fixed this for clawback (_071) ONLY (ruled UNIFORM/33,
None-orgs -> 'Not applicable', with a standing 071-Yes⊆bonus-exists guard); this diff EXTENDS that precedent
to the other five and conditions all six. REPAIR-THEN-CONDITION (the share-plan pattern).
FIX 1 — CLEAR THE IMPOSSIBLE (160 answers): for the 5 detail children, every None-org's substantive answer
-> 'Not applicable' (a non-bonus org cannot have a pool-funding method / gatekeeper / payout% / malus /
bonus measure). CLEAR not align — parent is the sole authority and content can't tell impossible-from-real
(the impossible answers MIRROR the clean-haver distributions, e.g. POOLFUND 38/35/27 vs clean 44/54/34 —
realistic seed values, not uniform garbage). Counts: POOLFUND 26, _065 29, _104 40, _070 39, _060 26. (The
_104 "impossible" set is 40, NOT the naive 205-179=26 — only 165 of 179 havers answered substantively, so
the non-haver substantive set is 205-165=40; a definitive seed defect, cleared.)
FIX 2 — THE REMAP-VS-LEAVE PRINCIPLE (by metric type): governance haver-N/A -> 'No' for the 2 Yes/No metrics
(_065 gatekeeper 28, _070 malus 3) — a bonus-haver's 'Not applicable' means "No, we don't use that feature",
a legitimate Yes/No reading, so base holds at 179 (honest prevalence; leaving out would inflate the Yes-rate).
NOT applied to the 3 descriptive children (POOLFUND/_104/_060 have no 'No' option — haver-N/A is a genuine
"didn't specify" gap; remapping would fabricate, so leave-base): POOLFUND 132, _104 165, _060 136. _071
render-only (data already correct r3sw5), base 147.
FIX 3+4 — CONDITION + COHERENCE: all six declared answerer_only (drop 'Not applicable' from graph+n); six
subset pairs child-substantive ⊆ bonus-exists (REW_INC_103 != None) added to the freeze-gate coherence_pairs
(structured_bases.json + generated_marginals.json), the _071 guard UPGRADED Yes->substantive (a 'No' clawback
also implies a bonus). A future INC_103 reseed that re-breaks any child's conditioning fails run_gates.
SHIFTS (all honest haver-prevalence corrections, N/A-dilution removed): clawback Yes 50.5->75.5% (largest, pure
r3sw5-data dilution removal — David confirmed realistic); gatekeeper Yes 53.2->58.7% / No 28.6->41.3%; malus
Yes 36.8->40.8%; POOLFUND methods scale onto 132; _060 incidences rise onto 136. No register marginal / frozen
target moved (none of the 6 carry one — _104 is a CONTEXT_VALUE with no marginal by design), so NO marginal
retirement. Demo: Thornbridge Retail is itself a None-org that over-answered all five -> now 'Not applicable'
on all (coherent, no bonus); Thornbridge Advisory (haver 75%+) unchanged.
Data = UPDATE-only, 191 edits (160 clear + 31 remap), row-count 230,359 UNCHANGED, non-target book (incl. _071)
hash-identical to backup. VERIFIED: throwaway (scratchpad/r3sw26_work) — 6-of-944 payloads move (938 byte-
identical), zero None-org substantive on all 5, all 6 subset pairs hold, governance base=179, NEGATIVE TEST
(inject one None-org _065=Yes -> qa_plausibility rc=1 PAIR-INCOHERENCE, fails closed), qa_reseed 9/9, run_gates
11/11 (freeze gate with the 6 new pairs). Served files kept PRISTINE during the throwaway via swap-test-restore
(generated_marginals.json restored byte-identical). LIVE (backup lumi.db.bak_pre_r3sw26_bonusfamily_20260722):
post-write match EXACT (0 of 944 cells vs throwaway); non-target book + _071 answers byte-identical to backup;
coherence re-verify (zero None-org substantive, pairs hold, gov base=179); render re-verify (all 6 N/A bars gone,
bases 147/132/179/165/179/136); qa_plausibility on live rc=0 (FREEZE GATE PASS, register marginals within 5pp);
dev server restarted + signed-in HTTP (REW_INC_065 n=179, base "organisations with a bonus scheme", no N/A bar).
server/migrate_r3sw26_bonusfamily.py is the dual-guarded applier (data UPDATE + 3-file atomic config; staged
outs for throwaway per r3sw7). QUEUE: the remaining r3sw25-B work-list (pension-DC x2, pension-salsac x2,
allowances x2, COMPARATIO, AIDISCLOSE, PAY_097, GAP_005, INC_132) + C (HOL_006+BEN_041, EVSALSAC, COMMCAP+_136,
SICK_004) + the LTI-type/RED_TERM_03 seed-realism flags.

## Pension-DC ×2 — clear over-answered DC-detail, condition on 199 DC-havers, parent FROZEN (r3sw27, ruled + applied 22 July 2026)
A CORRECTION IS ON THE RECORD. The first r3sw27 direction (reclassify 21 DB->Hybrid/DC on a "new-joiner
basis") was WRONG and was NOT built: it missed r3sw3, which had ALREADY ruled this exact question from a
graded source — TPR Occupational DB landscape 2025 (grade A), NEW-JOINER basis, CARE receives no separate
TPR class = standard DB, so public-sector "DB" is correct — and TIER-1 FROZE REW26_BEN_PENSION_TYPE
(DC .8864 / DB .0955 / Hybrid .0182). The diagnostic that led to the reclassify did not check the pension-
type ruling history; David caught nothing because the diagnostic itself was the flaw. THE LESSON (standing):
before recommending a re-anchor/reclassify DIRECTION on any metric, check whether it is settled-frozen and
read its ruling history — a frozen target is a prior evidence-backed decision, and a "fix" that would move it
is a re-open, not an N/A tidy. Reclassifying here would have silently reversed a TPR-grade-A carve-out AND
moved a tier-1 immovable target.
THE CORRECT DIRECTION (r3sw3-consistent) is the bonus over-answer pattern: the 21 DB orgs are genuinely
DB/CARE (parent correct + frozen), but over-answered DC-detail that a DB/CARE scheme cannot have (no member
DC default fund, no AE default contribution rate). CLEAR the DC-detail; DO NOT touch the parent.
FIX 1 — cleared 38 DB over-answers -> N/A: AE-rate 20 (DB-org substantive -> "Not applicable (no DC scheme)"),
green-fund 18 (-> "Not applicable (no DC default fund)"). FIX 2 — re-anchored the 17 AE DEFERRAL (DC-havers who
answered "no DC scheme" -> "Statutory minimum only"; genuine DC-havers who auto-enrol, statutory floor is the
honest answer not exclusion); green DEFERRAL -> leave-base (3-level descriptive net-zero/ESG/standard, no clean
floor to remap). FIX 3 — both children declared answerer_only, conditioned on the 199 DC-havers (DC 195 +
Hybrid 4): AE base 199, green base 170. Two subset pairs child-substantive ⊆ DC-havers (parent != DB) added to
the freeze-gate coherence_pairs. Shifts: AE Statutory-min 71.4->80.4% (17 DEFERRAL + 20 DB cleared); green
ESG-tilted 29.6->33.5%, Standard 44.2->49.4%. remap-vs-leave principle: AE-rate has a clean floor (statutory-min)
-> floor-remap the DEFERRAL; green-fund has no floor -> leave-base. (Neither child is Yes/No, so no governance
remap; but AE's statutory-min IS a legitimate floor for a DC-haver, unlike a rate with no floor.)
PARENT HARD CONSTRAINT HELD (the safeguard the wrong direction would have broken): REW26_BEN_PENSION_TYPE
answers BYTE-IDENTICAL before/after, dist DC 195/DB 21/Hybrid 4 unmoved, frozen-target drift 0.0045pp (tol
0.1pp), parent payload byte-identical. Children are unanchored (no marginal) so no re-freeze. Demo: both
Thornbridge orgs are DC-havers -> untouched by the DB-only clear. Data = UPDATE-only, 55 edits, row-count
230,359 unchanged, non-target book (incl. parent) hash-identical to backup.
VERIFIED: throwaway (scratchpad/r3sw27_work) — 2-of-944 payloads move (parent byte-identical), zero DB-org
DC-detail, both subset pairs hold, AE substantive == 199 DC-havers, negative test (DB-org given AE=3pp+ ->
qa_plausibility rc=1 PAIR-INCOHERENCE), qa_reseed 9/9, run_gates 11/11 (freeze gate PASS with pension-type
unmoved). Served files kept pristine via swap-test-restore (generated_marginals restored byte-identical). LIVE
(backup lumi.db.bak_pre_r3sw27_pensiondc_20260722): post-write match EXACT (0 of 944 vs throwaway); frozen-
target re-verify (parent answers byte-identical to backup, dist unmoved, drift 0.0045pp, non-target book hash-
identical); render re-verify (both N/A bars gone, AE 199 / green 170); qa_plausibility on live rc=0 (freeze gate
PASS); dev server restarted + signed-in HTTP (AE n=199, base "organisations with a DC pension scheme", no N/A
bar). server/migrate_r3sw27_pensiondc.py is the dual-guarded applier (parent read-only + byte-identical assert).
QUEUE unchanged minus pension-DC: pension-salsac x2, allowances x2, COMPARATIO, AIDISCLOSE, PAY_097, GAP_005,
INC_132 (B); HOL_006+BEN_041, EVSALSAC, COMMCAP+_136, SICK_004 (C); LTI-type/RED_TERM_03 seed-realism.

## Pension salary-sacrifice NIC-cap ×2 — render tidy, NOT a defect (r3sw28, ruled + applied 22 July 2026)
THE FROZEN-RULING CHECK (now standing, r3sw27 lesson) caught it up front and reframed the whole diff:
REW26_BEN_SALSAC (the SS-exists parent) is TIER-1 FROZEN (Yes .5955/No .4045), AND both children
(REW264_PEN_SALSACIMPACT/RESPONSE — the 2029 £2,000 pension-salary-sacrifice NIC-cap questions) were
ALREADY conditioned by Diff 7 (14 July, ruled ③): false-NA correction on the any-salsac union
(REW26_BEN_SALSAC="Yes" ∪ WEL_BMAP sal-sac benefit ticks = 197), "0 substantive-without-evidence", 23
legitimate NA. Diff 7 F2 ALSO logged the WEL-pension-tick(120)-vs-SALSAC fork as a known out-of-scope
old-book contradiction. So the master-sweep "73/77" is a RE-MEASUREMENT ARTIFACT — the logged fork gap
(197 substantive − 120 WEL-pension-tick), NOT a fresh defect. This is a pure render tidy respecting all
three prior rulings; NOT a clear (they have sal-sac) and NOT a reclassify (parent frozen + correct).
FIX 1 — RENDER-ONLY N/A-DROP: both children declared answerer_only, dropping the 23 self-declared "Not
applicable (no sal-sac)" from graph+n -> base 197. The metric SELF-CONDITIONS via its own NA (Diff 7's
NICSHARING primitive). NO EXTERNAL SUBSET PAIR — no single metric equals the 197 any-salsac-union base
(SALSAC=Yes 131 / WEL-pension 120 / WEL-any 170), so nothing single-metric to nest in; self-conditioning
is the mechanism (the life-assurance self-contained precedent). Confirmed no pair added (structured_bases
+ generated_marginals git-clean).
FIX 2 — 8-ORG COHERENCE TIDY: since Diff 7, 8 orgs drifted each way. 8 substantive-without-evidence -> N/A;
8 NA-with-evidence -> substantive (RNG-mirrored to the current marginal, Diff-7 sha256 primitive). ALL 8
of the NA->substantive orgs carry SALSAC=Yes (the FROZEN authority says they DO have pension SS, so their
"no sal-sac" self-declaration was a contradiction — well-justified fill); all 8 substantive->N/A orgs have
NO any-salsac evidence (parent=No + WEL None). Net base unchanged (197). Restores Diff-7's invariant on
BOTH sides: substantive==union AND NA∩union=0. Both children leave-base (descriptive/ordinal — IMPACT "Not
yet" floor, RESPONSE "Undecided" floor; neither Yes/No, no remap). Shifts: IMPACT Not-yet 43.6->47.7%,
Yes-modelled 30.9->34.5%; RESPONSE Maintain 62.7->69.0%.
PARENT FROZEN HELD: REW26_BEN_SALSAC answers BYTE-IDENTICAL (md5/sha256 by 3 independent verifiers), dist
Yes 131/No 89 unmoved, frozen drift 0.0045pp. NOT re-conditioned on the 131 pension-SS base — that is the
deliberate Diff-7 RE-OPEN (Option 2), QUEUED as a separate pension-specific base-revisit, explicitly NOT
this diff. Children are unanchored (no marginal), so no re-freeze. Seed-realism: the £2,000 NIC cap on
pension salary sacrifice (April 2029) aligns with the Autumn 2025 Budget — a real forward policy, non-
degenerate distribution; NOT a TIME_IVF reframe/defer candidate. Data = UPDATE-only, 32 edits, row-count
230,359 unchanged, non-target book (incl. frozen SALSAC) hash-identical to backup.
VERIFIED: throwaway (scratchpad/r3sw28_work) — 2-of-944 payloads move (parent byte-identical), both children
substantive==any-salsac-union(197) as SETS + NA∩union=0, qa_reseed 9/9, run_gates 11/11 (freeze gate PASS,
SALSAC unmoved); 3/3 ADVERSARIAL SKEPTICS ALL_CONFIRMED (union=197 cross-checked two ways, all 8 fills
SALSAC=Yes, all 8 clears no-evidence, config purely additive, UPDATE-only). Config = applicable_bases ONLY
(no coherence_pairs change), so no gm swap. LIVE (backup lumi.db.bak_pre_r3sw28_salsacnic_20260722): post-
write match EXACT (0 of 944 vs throwaway); frozen-target re-verify (SALSAC byte-identical, dist unmoved,
drift 0.0045pp); coherence re-verify (substantive==union both children); render re-verify (both N/A bars
gone, base 197); qa_plausibility on live rc=0 (freeze gate PASS); dev server restarted + signed-in HTTP
(RESPONSE n=197, base "organisations offering pension salary sacrifice", no N/A bar).
server/migrate_r3sw28_salsacnic.py is the dual-guarded applier (frozen-parent byte-identical assert; RNG
fill = Diff-7 primitive). QUEUE: Option-2 pension-specific SALSAC base-revisit (tighten to 131, a Diff-7
re-open) + allowances x2, COMPARATIO, AIDISCLOSE, PAY_097, GAP_005, INC_132 (B); HOL_006+BEN_041, EVSALSAC,
COMMCAP+_136, SICK_004 (C); LTI-type/RED_TERM_03 seed-realism.

## On-call pay-method — clear the over-answer, condition on the on-call family (r3sw29a, ruled + applied 23 July 2026)
Shipped as a SEPARATE, independently-revertible diff from consolidation (r3sw29b) — different fix classes on
different metrics, never bundled. CLEAR is the CHILD-IMPOSSIBLE class: REW_PAY_017 "how is on-call paid" is
not answerable by an org with no on-call inventory. Ruling A (David, family-122 line): condition on the on-call
FAMILY = REW_PAY_016 tick of On-call ∪ Standby ∪ Call-out allowance (N=122). 203 orgs answered a pay-method
(92% of the cohort — implausible); CLEAR the 92 NON-family method-answerers -> "Not offered / not applicable".
Base 220 -> 111 (all 111 ⊆ the 122 family). The 65 shift-only orgs among the 92 are cleared DELIBERATELY:
a shift/night/weekend premium is not an on-call arrangement. NOT reclassify (would break the ALLOW_01 ~32%
on-call anchor) and NOT sector-gate (see below). CORRECTED DENOMINATOR (on the record): on-call family = 122,
narrow On-call-allowance-only tick = 71 — the earlier r3sw25-B "~71 havers" framing UNDERSTATED the family;
the true conditioning base is the 122-family, 111 of whom answered a method. The 11-org DEFERRAL (family-havers
who answered "Not offered / not applicable") is RECORDED, NOT ACTIONED under ruling A (small, left as-is).
SECTOR READING = SCATTERED-FLAT (settled by a complete-source reconciliation; artifact named so no future reseed
re-derives "concentrated"): my earlier r3sw25-B "operational-concentrated" read was an artifact of counting RAW
HAVER COUNTS in UNEQUAL BASES (Logistics 17 / Retail 16 / Hospitality 16 look large only because those sector
bases are 23-30). On SHARE-OF-BASE (DB orgs.industry, complete, 0 unmatched), on-call-family appears in all 14
industries at 10-90%: Technology is the SINGLE HIGHEST at 9/10 = 90%, and the office mean ~45% is comparable to
the operational mean ~57% (Tech 90 / Finance 50 / Media 30 / ProfServices 10). Office sectors are NOT near-
absent -> fails the "concentrated" test -> scattered-flat -> no coherent sector to gate on, hence CLEAR on the
inventory evidence not a sector-gate. (The separate org_profiles.json join drops 27 of 122 as unmatched — a
coverage artifact of a 158-org subset; the DB source with 0 unmatched is authoritative.)
BUILD SHAPE (b) SELF-CONDITION via own NA (SALSAC precedent), AND ITS KNOWN GAP: after the clear, the child
self-conditions via answerer_only on its own NA. NO engine change; blast radius = applicable_bases.json + this
one metric. Path (a) — extending the freeze-gate pair engine's parent_contains to a multi-token OR set (the
on-call family is OC∪SB∪CO) — was DECLINED because it touches shared qa_plausibility.py for an N/A tidy. CONSEQUENCE
(carried as a known gap, NOT as covered): there is NO forward coherence-pair guard against a future reseed
re-introducing non-family over-answers. That guard belongs in the REW_PAY_016 reseed diff (queued below), where
the on-call family becomes a first-class parent. Data = UPDATE-only, config = applicable_bases only.
VERIFIED: throwaway (scratchpad/r3sw29_work, tw_A) — 92 cleared (all non-family), base 111 ⊆ family, only
REW_PAY_017 moves, 8 frozen targets byte-identical, qa_reseed 9/9, run_gates 11/11; 3/3 adversarial skeptics
ALL_CONFIRMED. LIVE (backup lumi.db.bak_pre_r3sw29_allowances_20260723): post-write EXACT (live==tw_A on 017,
92 rows, UPDATE-only, row count 230,359 unchanged), non-target book + frozen-8 byte-identical, coherence
(111 ⊆ 122), render n=111 excluded_na=109 no N/A bar; live gate suite green. server/migrate_r3sw29a_oncall.py
is the dual-guarded applier (frozen-8 byte-identical assert).

## Allowance consolidation — clear 5 no-inventory + remap 67 governance-N/A to Never (r3sw29b, ruled + applied 23 July 2026)
The consolidation diff (separate + independently revertible from r3sw29a). TWO distinguishable operations landing
together. (i) CLEAR the 5 no-inventory CICOVER: orgs that answered a consolidation frequency but pay NO allowances
(no REW_PAY_016 row) -> "Not applicable" — a non-allowance org has nothing to consolidate. (ii) REMAP the 67
allowance-paying "Not applicable" -> "Never": governance N/A reads "Never" where the org DEMONSTRABLY pays
allowances; N/A is a mislabel (they simply never consolidate). "Never" is the governance floor, so the remap is
legitimate interpretation, not fabrication. Then self-condition (answerer_only, own NA) -> base 215 (= the
allowances-payers). BEFORE Always 82 / Sometimes 68 / Never 3 / N/A 67 -> AFTER Always 80 / Sometimes 65 /
Never 70, base 220 -> 215. RECORDED OUTCOME IS 80 / 65 / 70 (ratified by David). The ruling text's "82/68/70" was
an arithmetic slip — the remap was applied to the pre-clear distribution without subtracting the 5-org clear; the
report surfaced it and it is corrected here. Delta is self-explaining: the 5 cleared CICOVER were 2×Always +
3×Sometimes, so Always 82->80 and Sometimes 68->65. This ALSO fixes the implausible Never=3 (an allowance cohort
where almost nobody "never consolidates" is not credible; 70 is realistic). Build shape (b) as r3sw29a: self-
condition via own NA, no external pair (any-allowance is a multi-select parent, and REW_PAY_016 is a queued
reseed), no engine change.
VERIFIED: throwaway (tw_B) — 5 cleared (all non-allowance) + 67 remapped (all allowance-payers) = 72 edits,
after 80/65/70/5, substantive(215)==any-allowance, only REW_PAY_019 moves, 8 frozen byte-identical, qa_reseed
9/9, run_gates 11/11; 3/3 adversarial skeptics ALL_CONFIRMED. LIVE: post-write EXACT (live==tw_B on 019, 72 rows,
UPDATE-only, 230,359 unchanged), live payloads EXACT-match the both-applied throwaway (0 of 944 cells), non-target
book + frozen-8 byte-identical, coherence (substantive==any-allowance 215), render n=215 excluded_na=5 no N/A bar;
live gate suite green (qa_reseed 9/9, run_gates 11/11, freeze gate PASS — no drift from throwaway).
server/migrate_r3sw29b_consolidation.py is the dual-guarded applier.
QUEUE (separate, NOT in these diffs): ON-CALL SEED-REALISM — REW_PAY_016 yields a near-flat ~55% on-call rate
across all 14 industries with Tech at 90%, implausible vs UK reality (on-call concentrates in healthcare,
utilities, IT-ops, emergency/field-service). A REW_PAY_016 RESEED question; the r3sw29a build-shape-(b)
forward-guard gap (no coherence pair against reseed over-answers) ATTACHES to this item. Alongside LTI-type
148/211 and RED_TERM_03 seed-realism. Prior queue carries: Option-2 SALSAC 131-base re-open; COMPARATIO,
AIDISCLOSE, PAY_097, GAP_005, INC_132 (B); HOL_006+BEN_041, EVSALSAC, COMMCAP+_136, SICK_004 (C).

## Option-2 SALSAC base re-open — REJECTED; revert 17 Diff-7 fabrications (r3sw30, ruled + applied 23 July 2026)
The deliberate re-open r3sw28 queued: should the NIC-cap children (REW264_PEN_SALSACIMPACT/RESPONSE) condition
on pension-SS (131) instead of Diff 7's any-salsac union (197)? RULED: OPTION 2 REJECTED, BASE STAYS 197.
THE MISREAD (the reason): REW26_BEN_SALSAC='Yes' means "pension offered via salary sacrifice BY DEFAULT",
NOT "has pension SS". So 131 is the DEFAULT-pension-SS cohort, not the pension-SS cohort — Option 2's premise
was a misread of the frozen parent. Of the 66 SALSAC=No substantive answerers, 43 carry the WEL pension-SS tick
(OPT-IN pension SS): they ARE genuinely subject to the £2,000 pension-SS NIC cap and their answers are REAL.
Clearing 66 would have DESTROYED 43 legitimate opt-in answers + 6 genuine no-signal floor answers — a standing-
rule violation (never clear a substantive answer). Options B (clear->131), C (remap-to-floor) and D2 (also clear
the 6 genuine) all rejected. The tightened renders (131 and 174 bases) moved <2pp vs 197 — the base question was
near-cosmetic on output, part of why it does not justify re-opening a ruled decision. Diff 7's 197 any-salsac
base STANDS; re-open CLOSED. CORRECTED COHORT SEMANTICS (for future readers): SALSAC=Yes = 131 default-pension-SS;
WEL "Salary Sacrifice for Pension Contributions" tick = 120 available-incl-opt-in; broad pension-SS union
(SALSAC=Yes ∪ WEL tick) = 174; any-salsac substantive = 197.
THE ONE THING DONE — A STANDING-RULE RESTORATION, NOT A BASE TIGHTENING: reverted 17 Diff-7 FABRICATIONS. These
17 orgs (a) held a genuine "Not applicable (no sal-sac)" before 14 July, (b) were RNG-overwritten to substantive
by Diff 7's false-NA correction, (c) have NO pension-SS signal at all (neither SALSAC=Yes nor the WEL tick) — for
them the fill corrected nothing, it MANUFACTURED an answer for an org that had answered honestly (9 of the 17
were fabricated to IMPACT "Yes modelled" — a no-pension-SS org "modelling" a cap it isn't subject to). Reverted
both children to the exact pre-Diff-7 NA label (read from answers_history, derive-don't-hardcode; N==17 hard-
asserted, HARD-ABORT if the cohort had moved). Base 197 -> 180 is a CONSEQUENCE, not a goal. DELIBERATELY
PRESERVED (D2 declined): the 6 genuine no-signal floor answers (IMPACT Not-yet 4 / Yes-modelled 2; RESPONSE
Maintain 5 / Restructure 1 — real, floor-honest "no impact") and the 43 opt-in orgs — asserted UNTOUCHED as the
standing-rule guard. Data-only (34 edits, 17/child); NO config change (the existing answerer_only decl drops the
NA); no pair, no engine change.
METHOD FLAG (NARROW, on the record): Diff 7's false-NA correction manufactured substantive answers for 17 orgs
that had honestly answered "Not applicable" with no supporting evidence — the fabricated-data-wearing-a-
legitimate-label failure mode. The WIDER question (did Diff-7-era RNG fills overwrite honest N/As on OTHER
metrics?) is QUEUED, NOT answered here — scope/priority David's, later; do NOT bundle.
VERIFIED: throwaway (scratchpad/r3sw30_work) — 17 derived from provenance (==17), 2-of-944 payloads move, base
197->180 excluded_na 23->40, N/A bars stay gone, 43-opt-in + 6-genuine UNTOUCHED (guard), n>=5 suppression
intact, 8 frozen byte-identical, non-target book hash-identical, UPDATE-only (230,359), qa_reseed 9/9, run_gates
11/11 (freeze gate PASS). LIVE (backup lumi.db.bak_pre_r3sw30_revertfills_20260723): post-write EXACT (live==
throwaway, 17 rows/child; live payloads==throwaway 0/944), non-target book + frozen-8 byte-identical, standing-
rule guard re-verified (0 of 43 opt-in moved), render n=180 excluded_na=40 no N/A bar. server/migrate_r3sw30_
revertfills.py is the dual-guarded applier (provenance-derived, guard-asserted).
QUEUE (separate, NOT this diff): AUDIT whether Diff-7-era RNG fills overwrote honest N/As on other metrics
(scope/priority David's, later). Alongside: on-call seed-realism (REW_PAY_016 reseed + r3sw29 forward-guard gap),
LTI-type 148/211, RED_TERM_03, seed/member provenance diagnostic, CARE-option flag; the B/C work-list
(COMPARATIO, AIDISCLOSE, PAY_097, GAP_005, INC_132; HOL_006+BEN_041, EVSALSAC, COMMCAP+_136, SICK_004).

## Diff-7 fill audit — NOT systemic; 24 unevidenced fills total across 3 metrics (audit, read-only, 23 July 2026)
Triggered by the r3sw30 method-flag (Diff 7's false-NA correction fabricated 17 answers under a legitimate label).
READ-ONLY AUDIT: no DB write, no config change, no gate change, no migration ran; 8 frozen targets present +
untouched; answers row-count 230,359 unchanged. David ruled: log the finding, DEFER the 7 COMMCAP fabrications
into the queued commission-authority ruling (do NOT revert standalone), queue the provenance gate (do NOT build).
VERDICT — NOT SYSTEMIC (stated plainly): Diff-7 fills are confined to its 5 DOCUMENTED false-NA-correction
metrics. Platform-wide unevidenced fills = 24 TOTAL: 17 reverted (r3sw30) + 7 remaining (COMMCAP), across 3
metrics. The scary hypothesis (Diff-7 RNG fills spread across many metrics) is FALSE.
THE TIMESTAMP-SIGNATURE METHOD (the reusable part — record so a future thread does NOT re-run the 1,153-row
scare): the naïve r3sw30 pattern (earliest answers_history value = an is_na option AND current answer
substantive) fires 1,153 times across 27 metrics, which CONFLATES three genuinely different populations.
The EXACT recorded_at stamp separates them:
  · 570 (8 metrics) = SEED-CONSTRUCTION — N/A and value written at BYTE-IDENTICAL stamps (TIME_IVF, HOL_006,
    FERTLEAVE all '2026-07-15 16:30:00' -> '2026-07-15 16:30:00'): a placeholder overwritten within one seed
    batch, never a committed answer. NOT fabrications.
  · 272 = r3sw RULED CORRECTIONS — this programme's own David-ruled, evidence-gated work (tagged 'r3sw*'
    stamps). Out of scope.
  · 311 (5 metrics) = TRUE Diff-7 fills — committed seed N/A at one stamp, overwritten by Diff 7 at a SEPARATE
    stamp (seed '…17:30:00'/'…18:40:00' -> Diff-7 '2026-07-14 22:30:00'). THE audit target.
  Classifier: a fill is a Diff-7 fabrication candidate iff earliest-history is is_na, first-substantive stamp
  differs (exact) from the N/A stamp, and that stamp is a bare numeric 'YYYY-MM-DD HH:MM:SS' (untagged).
PER-METRIC EVIDENCE SPLIT (evidenced / fabricated): EMICSOP 59 / 0 ; SHAREPLAN 57 / 0 ; COMMCAP 90 / 7 ;
SALSAC-IMPACT and SALSAC-RESPONSE 49 fills each, 17 fabricated (ALREADY reverted r3sw30). Diff-7's F1 share-
capital fills were SOUND — all 116 (EMICSOP 59 + SHAREPLAN 57) land on companies with share capital; the method
was not wrong in principle. Evidence signals used: EMICSOP/SHAREPLAN = share-capital form (orgs.ownership_type
not in {Charity/Non-profit, Mutual/Co-operative, Partnership/LLP, Public Sector Body}, name ltd/plc fallback for
null); COMMCAP = commission exists (REW_INC_135='Yes' ∪ REW_INC_136 structure).
THE FAILURE MODE, NAMED: Diff 7 asserted a BLANKET claim about its fill cohort ("all had salary sacrifice",
"all 97 had commission") that held for MOST and failed AT THE EDGE — wrong by 17, then wrong by 7, SAME SHAPE
both times. This is the fabricated-data-under-a-legitimate-label class (the EAP failure mode) — a MARGIN failure,
not a wholesale one.
SEVERITY of the 7 COMMCAP fabrications (recorded honestly, DEFERRED not reverted): all POSITIVE-ACTION, none
floor — COMMCAP has NO floor option, so each asserts a specific cap policy (Uncapped 1 / Soft-cap 3 / Hard-cap 3)
on an org with no commission plan on either signal. Ownership: 2 Charity/Non-profit, 2 Public Sector Body, 1
PE-backed, 1 Subsidiary, 1 PLC. So the book currently records e.g. a CHARITY operating a hard cap on sales-
commission earnings — small, unscored, but FALSE. INTERIM EXPOSURE ACCEPTED (ruled): single unscored card
(is_scored=0), NO domain-rollup or market-position propagation, headline shift <0.5pp, n=220->213 if reverted.
Rationale for defer: the 7 are unevidenced BECAUSE the commission signal itself is contested (INC_135 Yes=36 vs
INC_136 structure=199); reverting now would pre-empt the very question the commission-authority ruling exists to
settle. They resolve there, not as a standalone diff.
DURABLE GENERAL CLASS (standing principle): a metric with NO evidence-signal parent cannot have its fills
falsified — every fill in such a metric is unevidenced BY CONSTRUCTION. This tells future work where the class
hides without re-running an audit.
THE GATE GAP (recorded OPEN, NOT built): no existing gate (run_gates, qa_reseed, qa_plausibility, qa_integrity,
freeze gate) checks PROVENANCE — they verify coherence-pairs, suppression, base integrity, marginal drift and
frozen targets, none of which asks "was this answer N/A before we touched it, and does evidence support the
fill?". The conditioned metrics (r3sw26-29) are guarded only INCIDENTALLY: the coherence-pair mechanism happens
to fail closed on unevidenced fills. COMMCAP sits unguarded precisely because it has no pair yet. Candidate
assertion, for the record: "no substantive answer may exist where the earliest history value was N/A and no
supporting-evidence signal is present." NOT built — queued, pairs with the seed/member provenance diagnostic
(a launch prerequisite), same class of question, scope together on David's ruling.
DETECTION PROVENANCE (the argument for the gate): the 17 were found INCIDENTALLY — the Option-2 base re-open
forced a provenance look at that cohort — NOT by any routine check. Nothing in the suite would have surfaced
either the 17 or the 7.
QUEUE: (a) 7 COMMCAP fabrications -> resolve WITHIN the commission-authority ruling (INC_135-vs-136), C-item; (b)
provenance gate -> pair with the seed/member provenance diagnostic (launch prerequisite), scope together, David's
ruling. Existing queue unchanged: on-call seed-realism (REW_PAY_016 reseed + r3sw29 forward-guard gap), LTI-type
148/211, RED_TERM_03, CARE-option flag; B — COMPARATIO, AIDISCLOSE, PAY_097, GAP_005, INC_132; C — HOL_006+
BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## LTI-types (REW_INC_132) — condition on the ruled parent, clear the seed over-answer (r3sw31, ruled + applied 23 July 2026)
Resolves the CONDITIONING half of the queued "LTI-type 148/211 seed-realism" item (the form-realism half stays
open — see queue). REW_INC_132 "which LTI types offered" was SEEDED UNCONDITIONED on its parent: 211 substantive
vs REW_INC_131=Yes=65 (the r3sw2-ruled exec-LTI operators = EXACTLY the INC_133 eligibility-holders, 131<->133
pair-locked in the freeze gate). Ruled (David): CONDITION on INC_131=Yes (65); CLEAR all 148 over-answers to the
existing "Not applicable" is_na option; base 211 -> 63.
THE PREMISE CORRECTION (record so the wrong framing does not resurface): the metric was queued as verdict-feeding
("more types = richer"). THE CONFIG DISPROVES IT — class=Practice, categorical, direction=None, polarity=NEUTRAL;
option_scores are CATEGORY CODES (RSUs 0 / Share options 25 / Performance shares 50 / Cash LTIP 75 / Other 100),
NOT a poor->rich scale; score_direction resolves to 0 and score_answer returns None (unscorable). PROVEN not
asserted (imported aggregate.score_direction/score_polarity/score_answer). NO directional verdict moves; only
INC_132's own payload changed (1 of 944) — zero propagation.
THE REAL HARM (correctly stated): peer prevalence "offers an LTI type" was inflated ~3x (211/220 = 96% vs true
65/220 = 30%) and 131 orgs each DISPLAYED A FABRICATED LTI PRACTICE on their own card (e.g. Thornbridge Retail,
INC_131=No, was shown offering an LTI type — now correctly N/A; Advisory, INC_131=Yes, keeps Share options). This
is data-correctness AT SCALE, not verdict miscategorisation.
THE 148 (derive-don't-hardcode, hard-asserted ==148, HARD-ABORT if moved) = 131 NO-SIGNAL (no LTI/equity evidence
at all) + 17 SECONDARY-EQUITY-ONLY (EMICSOP/SHAREPLAN operators — all-employee SAYE/SIP or discretionary EMI/CSOP,
which INC_131 deliberately excludes). The 17 CLEARED alongside the 131 (ruled): INC_131's ruled value is
specifically exec-LTI-by-level eligibility; holding the 17 would straddle two definitions. THE INC_131-vs-EMICSOP/
SHAREPLAN COHERENCE GAP IS REAL (union 82 vs ruled 65) and is LOGGED AS A KNOWN OUT-OF-SCOPE FORK — the same
treatment Diff 7 gave WEL_BMAP-vs-SALSAC — NOT resolved here.
PROVENANCE: REW_INC_132 has ZERO answers_history — pure original seed, seeded unconditioned on INC_131. An
ORIGINAL-SEED generation defect, NOT a Diff-7-style fabrication; the timestamp-signature method has nothing to
bite on. WIDER POINT (boundary on the queued provenance gate): metrics with no history CANNOT be provenance-
audited at all — the gate can only assert against current evidence, not "was this N/A before we touched it".
SECONDARY-SIGNAL CHECK AS STANDING METHOD: the naïve contradiction 146 became 131 real once EMICSOP/SHAREPLAN
were checked (union 82 vs ruled 65) — the THIRD time the union check has changed the count (after SALSAC's WEL
tick and pension-DC's opt-in); the union check is now standing method for any "child over-answers parent" finding.
NO reclassify (parent r3sw2-ruled + 131<->133 pair-locked; widening breaks the pair, out of scope), NO remap, NO
floor-add (no "None" option; N/A is the honest no-LTI answer; remapping the cleared to "Other" (score 100) would
FABRICATE — standing rule: never assign the rare/generous option to an unknown, exclude don't fabricate).
CONDITIONING: answerer_only + subset pair INC_132-substantive ⊆ INC_131=Yes (SINGLE-VALUE parent_value selector,
NO engine change — unlike r3sw29's multi-token on-call). Data = UPDATE-only, 148 edits.
VERIFIED: throwaway (scratchpad/r3sw31_work) — clear==148 (131+17), base 211->63, only INC_132 payload moves,
substantive(63) ⊆ INC_131=Yes(65), PARENT INC_131 + INC_133 byte-identical (131<->133 inputs untouched),
frozen-8 byte-identical, n>=5 suppression intact, NEGATIVE TEST (non-LTI org given INC_132=RSUs -> qa_plausibility
rc=1 PAIR-INCOHERENCE), qa_reseed 9/9, run_gates 11/11 (freeze gate PASS incl 131<->133). Served files pristine
via swap-test-restore (generated_marginals byte-identical). LIVE (backup lumi.db.bak_pre_r3sw31_ltitypes_20260723):
post-write EXACT (live==throwaway, 148 rows; live payloads==throwaway 0/944), coherence + parent/pair-inputs +
frozen-8 re-verified byte-identical, render n=63 excluded_na=157 no N/A bar, qa_plausibility on live rc=0 (freeze
gate PASS, 131<->133 holds), live gate suite 11/11 + 9/9. server/migrate_r3sw31_ltitypes.py is the dual-guarded
applier (parent + frozen-8 byte-identical asserts).
QUEUE: INC_131 LEGAL-FORM REALISM (the form-realism half, NOT this diff) — the parent's distribution is the wrong
shape on share-of-base (VC-backed 0% implausible for option-running startups; Mutual 55% and LLP 100% implausible
with no equity to grant; PLC 53% low; small bases on VC 5 / Mutual 11 / LLP 2 warrant caution). Sits on the
r3sw2-ruled, 131<->133-pair-locked INC_131=65 -> a RE-OPEN requiring David's authorisation, its OWN diagnostic
before any build. Recorded OPEN, not actioned. Existing queue unchanged: 7 COMMCAP (commission-authority ruling),
provenance gate (paired with seed/member provenance diagnostic), on-call seed-realism (REW_PAY_016 + r3sw29
forward-guard gap), RED_TERM_03, CARE-option flag; B — PAY_097 (prior "PRACTICE" ruling constrains), GAP_005,
AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## PAY_097 (pay differentiated by performance) — clear the 16 impossible, preserve the honest, log the gap (r3sw32, ruled + applied 23 July 2026)
Narrow honest fix on a two-directional seed defect. PRIOR RULING RESPECTED (quoted): the 14-July "Market vs
practice classification rule (RATIFIED)" — "Ratified exception (David): REW_PAY_097 pay-differentiation-by-
performance = PRACTICE, overriding the tiebreak: egalitarian-vs-differentiated is a philosophy fork, not
richer/leaner" (DECISIONS 6847-6848; "PRACTICE stands", 6905). That ruling constrains CLASSIFICATION (PRACTICE,
not MARKET) and DIRECTION (no richer/leaner ordering) ONLY. This diff clears impossible answers and touches no
classification, scoring, or option semantics — it constrains nothing the ruling governs.
VERDICT IMPACT = ZERO, PROVEN (not asserted): PAY_097 is class=Practice + polarity=neutral -> DOUBLE-EXCLUDED at
positions.py:778 `if cls not in ("Practice","Design") and polarised and q.is_scored and score_direction(q)!=0`
(fails clause 1 AND "polarised"); empirically its payload carries NO position/verdict/gap field. score_direction=-1
is a RED HERRING (label heuristic) — the MEMBERSHIP GATE is the authority; score_polarity=neutral (config) and the
Practice class keep it out of the gauge. SECOND CONSECUTIVE triage "scored -> verdict-feeding" premise disproved
(after INC_132). No org's below/on/above-market verdict moves; PAY_097 is a Practice adoption/prevalence surface.
THE UNION CHECK CHANGED THE COUNT A 4TH TIME (now standing method, four-for-four after SALSAC WEL / pension-DC opt-
in / INC_132 EMICSOP-SHAREPLAN): REW263_PAY_MERITMATRIX (132 users) is a REAL second mechanism — you can
differentiate pay via a merit matrix (rating x position) WITHOUT formal ratings. True applicable base = PERF_03-
uses-ratings ∪ MERITMATRIX = 195, not 170. The over-answer contradiction shrank 26 -> 22.
THE TWO-DIRECTIONAL DEFECT (the over-answer framing missed the larger half): PAY_097 was seeded LOOSELY COUPLED to
its mechanism in BOTH directions — 22 over-answers (substantive with no mechanism) AND 42 reverse-N/A (applicable
orgs who self-declared N/A). Zero answers_history confirms ORIGINAL-SEED generation, not a Diff-7-style fabrication.
FIX (ruled): CLEAR the 16 IMPOSSIBLE (Yes-strongly 10 + Yes-moderately 6, NO rating AND NO merit matrix) -> "Not
applicable" — they claim differentiation-BY-RATING with no mechanism to differentiate by (child-impossible).
PRESERVE the 6 "No-flat" no-mechanism answers BY DELIBERATE RULING (not arithmetic): a no-mechanism org answering
"we don't differentiate" is HONEST and substantive; the floor option carries the meaning; clearing all 22 would
have DESTROYED these 6 — the Option-2 trap avoided (standing rule: never clear a real answer into N/A). LEAVE the
42 reverse-N/A UNTOUCHED as a KNOWN, QUANTIFIED, OPEN GAP: filling FABRICATES (no independent evidence to falsify a
fill — the unfalsifiable-by-construction class from the Diff-7 audit); conditioning on the 195 union needs a MULTI-
SIGNAL parent engine change (declined on r3sw29 and again here). THE METRIC STILL UNDER-REPORTS BY 42 AFTER THIS
DIFF — DELIBERATE, recorded so it is not mistaken for completeness. NO condition on the union, NO coherence pair,
NO applicable_bases change — DATA-ONLY; the N/A bar STILL RENDERS (45 -> 61; this diff does not claim to clear it).
SOFT SEED-REALISM FLAG (log, do NOT act): 63% differentiated vs the ~48% private CIPD/ADP anchor (Pay/Performance/
Transparency 2024, n=832) — mild over-differentiation, WITHIN grade-C tolerance, explicitly NOT a hard defect like
INC_132's form distribution. There is NO anchored target for the strongly-vs-moderately split; none was invented.
Data = UPDATE-only, 16 edits. VERIFIED: throwaway (scratchpad/r3sw32_work) — clear==16 (10+6), only PAY_097 payload
moves, 6 No-flat + 42 reverse-N/A UNTOUCHED (guards), N/A bar still renders, verdict fields NONE, n>=5 suppression
intact, 8 frozen byte-identical, non-target book hash-identical, qa_reseed 9/9, run_gates 11/11 (freeze gate PASS).
LIVE (backup lumi.db.bak_pre_r3sw32_pay097_20260723): post-write EXACT (live==throwaway, 16 rows all Yes->NA; live
payloads==throwaway 0/944), guards re-verified (0 No-flat / 0 reverse-N/A moved), frozen-8 byte-identical, verdict
fields NONE on live, qa_plausibility rc=0. server/migrate_r3sw32_pay097.py is the dual-guarded applier (standing-
rule guard asserted).
QUEUE: PAY_097 REGENERATION (seed-realism, per ruling) — the metric was generated UNCOUPLED from the mechanism in
both directions; a proper regeneration conditions on PERF_03 ∪ MERITMATRIX and RESOLVES the 42. MUST carry an
honest anchored-vs-invented statement: the flat-vs-differentiated pole has a grade-C context anchor (~48% private,
CIPD/ADP PPT 2024, n=832); the strongly-vs-moderately split has NO anchor and would be INVENTED. Its own diagnostic
+ David's explicit sign-off — NOT folded into an N/A tidy (how Diff 7's fills got in unruled). Alongside on-call
seed-realism (REW_PAY_016) and INC_131 form-realism. Existing queue unchanged: 7 COMMCAP (commission-authority),
provenance gate (paired with seed/member provenance), RED_TERM_03, CARE-option; B — GAP_005, AIDISCLOSE,
COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## GAP_005 (long-service milestones) — render fix only (r3sw33, ruled + applied 23 July 2026)
WHAT THIS DIFF IS AND ISN'T: a STANDING-RULE RENDER FIX — declare EXT_REW_GAP_005 answerer_only so "Not
applicable" leaves the graph and the denominator (base 119 -> 114; the 5 N/A-only orgs excluded). It does NOT
condition GAP_005, does NOT resolve the 30 GAP_004 contradictions, adds NO subset pair, and does NOT claim the
metric is correct. DECLARATION-ONLY: applicable_bases.json only, ZERO answer rows changed (entire answers book
byte-identical to backup, 230,359 unchanged). Milestone option counts identical (5y 49 / 10y 74 / 15y 36 / 20y
59 / 25y+ 53 / Other 8); only the denominator moves.
STALE-SOURCE CORRECTION (record so exports aren't treated as live): the diagnostic prompt's premise came from the
seeded-org EXPORT snapshot, which is STALE on BOTH (i) GAP_004's distribution (export Yes 118/No 84/DK 10 vs LIVE
Yes 150/No 48/no-row 23) and (ii) its option set (export carries a "Don't know" option; LIVE does NOT — stripped
by r3sw13). LIVE is authoritative.
THE DECOUPLING MECHANISM (a NEW failure shape, worth naming): GAP_004 carries 264 answers_history rows, GAP_005
just 1. The PARENT was heavily RESEEDED while the CHILD stayed original seed -> they diverged. This is NOT the
unconditioned-generation shape of INC_132/on-call; it is PARENT-RESEEDED-AWAY-FROM-A-STATIC-CHILD. It predicts
where else to look: any metric whose parent was reseeded without the child.
UNION CHECK FIVE-FOR-FIVE: EXT_REW_GAP_007 (award value, 160 substantive) is a THIRD scheme signal; 18 of the 30
contradictions name a GAP_007 value -> they demonstrably HAVE a scheme (GAP_004=No is the error, milestones
honest). True child-impossible pool = 12, not 30. Clearing all 30 would have destroyed 18 honest answers — the
Option-2 trap for the THIRD time (after PAY_097's 6, and the standing-rule protections generally).
VERDICT IMPACT ZERO, PROVEN: GAP_005 is polarity=neutral + unbenchmarked=True (Diff-14 verdict-suppressed: "no
ruled authority") -> fails "polarised" at positions.py:778 AND separately suppressed; empirically the payload
carries NO position/verdict/gap field. THIRD CONSECUTIVE triage "scored -> verdict-feeding" premise moderated
(after INC_132, PAY_097). is_scored=1 is not evidence of propagation.
WHAT REMAINS OPEN ON THIS METRIC (explicitly deferred): the 30 contradictions (18 parent-error, 12 child-
impossible) and the union-base question (GAP_004=Yes ∪ GAP_007 = 195, multi-signal parent -> the engine change
declined twice) are DEFERRED pending GAP_004's own seed-realism diagnostic — so the metric isn't touched twice.
VERIFIED: throwaway (scratchpad/r3sw33_work) — only GAP_005 payload moves (1/944), base 119->114 excluded_na 5,
N/A bar off graph + out of denominator, milestone counts identical, entire answers book byte-identical (0 edits),
30 contra intact, 8 frozen byte-identical, n>=5 suppression intact, qa_reseed 9/9, run_gates 11/11 (freeze gate
PASS). LIVE (backup lumi.db.bak_pre_r3sw33_gap005render_20260723): post-write EXACT (live payloads==throwaway
0/944), answers book byte-identical, render n=114 excluded_na=5 no N/A bar, verdict fields NONE, 30 contra intact,
frozen-8 byte-identical, qa_plausibility rc=0. server/migrate_r3sw33_gap005render.py is the dual-guarded config
applier (0 DB writes asserted).
QUEUE (NOT in this diff): (a) GAP_004 SEED-REALISM — new item, own diagnostic. Live long-service prevalence 76%
overall vs real-UK ~40-50%, with Tech / Media / Finance / Professional Services / Energy / Education all at 100%
share-of-base (awards concentrate in public sector / manufacturing / long-tenure industries — this shape is
wrong); parent heavily reseeded (264 history). Precondition for conditioning GAP_005 and for the 18 parent-error
contradictions. Alongside INC_131 form-realism, on-call REW_PAY_016, PAY_097 regeneration. (b) PLATFORM-WIDE
"DON'T KNOW" SCOPE QUESTION — David's ruling, not actioned: 203 metrics carry a DK option, 186 with live answers
(2,118 total), ALL on the signals/engagement path (Capability 28, Processes 60, Growth 36, Wellbeing 29, Attract
15, ...); ZERO REW-prefixed metrics carry DK — the Reward path is CLEAN. r3sw13 enforced the no-DK rule REWARD-
ONLY (69 metrics, 62 stripped, 3 keeps). So NOT a violated rule but a SCOPE BOUNDARY: the standing rule reads
platform-wide, enforcement was Reward-scoped. Either restate the rule as Reward-scoped, or strip the signals path
too. Flagged open; NOT conflated with GAP_005. Existing queue unchanged: 7 COMMCAP (commission-authority),
provenance gate, RED_TERM_03, CARE-option; B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC,
COMMCAP+INC_136, SICK_004.

## Non-Reward hard-delete — config/doc cleanup ahead of the row deletion (nonrew-1, ruled + applied 23 July 2026)
THE STRATEGIC RULING (recorded on its own terms, ruled KNOWINGLY): Reward-only IS the product. All 600 non-Reward-
superpower questions and their 141,038 answers are to be HARD-DELETED — not retired, not hidden. David ruled this
deliberately, having seen that it CONTRADICTS two encoded design decisions: (1) releases.py:11 "Retire, never
delete" (leaving questions get status=retired + release_retired, stay in the bank and in every release snapshot so
historical benchmarks resolve); (2) app.py:172 "the other nine areas stay fully built (data, aggregation, scoring
untouched) and are hidden ... by THIS flag alone. Set LUMI_ACTIVE_SUPERPOWERS=all to re-show them — nothing else
needs touching." After this delete, re-showing any of the nine non-Reward areas requires a FULL RESEED, not a flag
flip. A future reader must see this was CHOSEN, not overlooked. (Mitigant on record: release_questions carries 0
non-Reward ids — the baseline releases were Reward-only — so historical release RECONSTRUCTION is not harmed; the
contradiction is with the invariant + the flag-revivable architecture, not with any existing release snapshot.)
THIS DIFF'S SCOPE — CONFIG/DOC ONLY, ZERO ROWS TOUCHED, SEQUENCED FIRST: everything here fixes something ALREADY
WRONG TODAY, independent of the deletion, so the irreversible row-delete (nonrew-2) lands against a stable baseline
with nothing else in flight to confuse its verification. Five edits: (1) README.md:4 "778 benchmark questions across
10 superpowers" -> "300+ reward benchmark questions across eight reward domains"; (2) web/js/app.js:238 removed the
stale fallback question_count:778 (server me.scope is sole authority; the literal fed only scopeN at app.js:926,
itself an UNUSED variable — zero render impact); (3) web/js/pages.js:5 SUPERPOWERS ["Reward"+9] -> ["Reward"]
(consumer commercial.js:13 gapGroups filters against data.maturity whose keys qa_focus.py:67 ASSERTS ==["Reward"],
so output is ["Reward"] before and after — non-breaking); (4) web/js/icons.js:94 SP_ICON 10-entry -> {Reward:"award"}
(consumer SpIcon has ||"target" fallback and is only ever passed sp="Reward"; the "Wellbeing" name-collision with the
Reward SUB-POWER does not reach SpIcon); (5) validation_thresholds.json regenerated Reward-only via seed_validation_
config.py — added `if q.superpower != "Reward": continue` to the loop (the sanctioned generator, now Reward-only
forward), 41 keys -> 19, dropping the 22 non-Reward keys; the 19 Reward entries + _readme are BYTE-IDENTICAL (0 hand-
edits: current file already equalled a fresh regen), and NO dropped key is load-bearing for a Reward metric (the only
cross-key ref is max_of; no Reward entry's max_of points at any dropped key). FOLDED IN (David's ruling, same class):
qa_phase3.py stale 778 — docstring "all 778 questions" -> "all in-scope", SUPER fallback 10-list -> ["Reward"],
EXPECT default 778 -> 0 sentinel (self-heals from live scope; a legacy gate, not in run_gates.sh). Deferred to
nonrew-2 because they are DELETION-CAUSED (break only when the rows/answers go): qa_engine_audit.py:331 LAYER 1 (must
be Reward-scoped, not re-literalled) and qa_phase1.py:127 fixture MET_cd8efe96 — keeping the stale-literal class here
leaves nonrew-2 containing only deletion-caused gate work.
COUNT-AUTHORITY FINDING (four frames already disagree, BEFORE any deletion): 344 all-Reward rows / 333 served
(active) / 249 marginals book / 243 anchor register — and the widely-quoted "336" matches NONE (it is the release-
2026.5 active count that r3sw retirements already dropped to 333; already stale independent of the delete). RULED
FRAME PER SURFACE — deliberately not uniform: README cites a FLOOR ("300+"), not a precise figure, because four
stale count literals were already found this thread (README 778, app.js 778, qa_phase3 778, verify_2026_5 336) — all
correct when written — and a floor never re-stales, matches pricing.html's "240+", and the precise live figure lives
in the server's dynamic me.scope where it belongs. app.js carries NO literal (server is authority). qa_phase3 uses a
0 sentinel. Frame A (344) was rejected for README: it includes 11 retired rows invisible to users, overstating the
live product. ALREADY-WRONG-TODAY register (all fixed here, all stale independent of the delete): README 778 + "10
superpowers", app.js fallback 778, SUPERPOWERS/SP_ICON 10-entry enumerations, 22 dangling validation_thresholds keys,
qa_phase3 778 + 10-list. verify_2026_5.py:28 (336) NOT touched — it already FAILS today (live vis=333) and is not in
the live suite; left for a later pass.
VERIFIED: throwaway backup via SQLite backup API (scratchpad/nonrew1/lumi_throwaway.db, q=944/ans=230,359); Reward-
only validation regen matched the throwaway preview byte-for-byte (19 keys, non-Reward=NONE, _readme preserved).
GUARD PROOF (config/doc diff — nothing in the DB may move): questions 944 + answers 230,359 UNCHANGED; frozen-8
answers hash 0a17a094… and whole answers-book hash 08112c2e… BYTE-IDENTICAL before and after (regeneration reads the
DB read-only). NO served number changes — platform already Reward-only; browser smoke-check on :8060 confirmed the
Benchmark page renders ("All reward · 218 benchmarks", award SpIcon glyph, peer selector) with ZERO console errors
after the SUPERPOWERS/SP_ICON reduction. run_gates 11/11 GREEN (freeze gate PASS) both pre- and post-write; py_compile
clean on the two edited Python files.
QUEUE (recorded, NOT actioned): nonrew-2 = THE ROW DELETION — 600 questions + 141,038 answers + 600 benchmark_
snapshots + 26 pulse_responses + the single pulse's question_ids_json/question_snapshot_json. MUST run FK-ON,
children-before-parents, ONE atomic transaction (pulse_responses -> benchmark_snapshots -> answers -> questions);
do NOT use the r3sw migration template — every r3sw script uses plain sqlite3.connect() (FK OFF), which would
SILENTLY ORPHAN 141k rows with no error. Requires a WAL-safe backup PLUS a repo-kept export of every deleted row
(the only inspectable record post-delete). Gate work belongs there: qa_engine_audit.py:331 LAYER 1 Reward-scoped (not
re-literalled); qa_phase1.py:127 fixture replaced or the legacy gate retired. ALSO QUEUED (own items): retrieval
filter-after-truncate bug (retrieval.py:129 scores the full bank, truncated to top-12 BEFORE app.py:3088's Reward
filter — deletion MASKS it, does not fix the ranking bug); DK submission guard (no is_na/DK filter at submission.js:450
— any guard must match the "Don't know" LABEL specifically, never is_na, since 41 legitimate Reward options are is_na
and must keep rendering). Existing queue unchanged: GAP_004 seed-realism, INC_131 form-realism, on-call REW_PAY_016,
PAY_097 regeneration, 7 COMMCAP, provenance gate, RED_TERM_03, CARE-option; B — AIDISCLOSE, COMPARATIO; C —
HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## Non-Reward HARD-DELETE — 600 questions + 141,038 answers removed (nonrew-2, ruled + applied 23 July 2026, IRREVERSIBLE)
THE STRATEGIC RULING (on its own terms, ruled KNOWINGLY): Reward-only IS the product. All 600 questions with
superpower != 'Reward' (404 active + 196 proposed) and their attached rows were HARD-DELETED — not retired. This
was chosen deliberately, having seen it CONTRADICTS releases.py:11 "Retire, never delete" (leaving questions get
status=retired + release_retired, stay in the bank + every release snapshot so historical benchmarks resolve) and
app.py:172's flag-revivable architecture ("the other nine areas stay fully built ... hidden ... by THIS flag alone.
Set LUMI_ACTIVE_SUPERPOWERS=all to re-show them — nothing else needs touching"). After this delete, re-showing any
of the nine non-Reward areas requires a FULL RESEED, not a flag flip. A future reader must see this was CHOSEN, not
overlooked. (Mitigant: release_questions held 0 non-Reward ids — baseline releases were Reward-only — so historical
release RECONSTRUCTION is not harmed; the contradiction is with the invariant + the flag-revivable design.)
THE FK FORK (recorded as a STANDING HAZARD for any future destructive work): db.py:24 get_conn() sets PRAGMA
foreign_keys=ON, but EVERY r3sw migration uses plain sqlite3.connect() (FK OFF). The FKs to questions(id) are
ON DELETE NO ACTION. The SAME `DELETE FROM questions` either ABORTS SAFELY (FK-ON) or SILENTLY ORPHANS 141,038
answers with no error (FK-OFF) — the outcome depends ONLY on the connection. This diff ran FK-ON DELIBERATELY (a
new dedicated runner, server/migrate_nonrew2_delete.py — NOT the r3sw template, whose default is the dangerous
side). One atomic transaction, children before parents: pulse_responses(26) -> benchmark_snapshots(600) ->
answers(141,038) -> questions(600), plus filtering pulse-90a56a58's question_ids_json/question_snapshot_json from
5 qids to its 3 Reward qids (dropping PULSE_PTD_DISCLOSURES + PULSE_PTD_EQUITY_AUDIT; its 110 Reward pulse_responses
kept). Dual-guarded (--write --confirmed-by-david); dry-run default; proven on a throwaway copy first.
THE RECOVERY POSITION: (1) 600 question definitions (full row, all columns) committed to the repo as
nonrew2_deleted_questions.json — the reconstruction record. (2) 141,038 answers + 600 benchmark_snapshots + 26
pulse_responses + the pulse JSON archived LOCALLY + UNCOMMITTED at nonrew2_local_archive/ (gitignored). (3) WAL-safe
backup lumi.db.bak_pre_nonrew2_delete_20260723 (backup API, the real full record). NOTE explicitly: the local archive
+ the .bak SHARE A MACHINE with lumi.db, so the committed question definitions are the ONLY geographically-
independent artefact.
GATE WORK — THE DIAGNOSTIC UNDER-COUNTED; a deterministic sweep of every gate file for deletion-set qids found MORE
than the workflow reported, including ONE in the LIVE suite: qa_focus:38+:92 (myview-degrade fixture, run_gates!) =
deleted PROP_9e3b1d18 -> retired-Reward REW264_PEN_CONTRIBTIER; qa_engine_audit:342 LAYER 1 -> skip `qid not in META`
(DB-derived, self-scopes, no-op pre-deletion); qa_phase1:82/:127 (PROP_9620d380/MET_cd8efe96 -> PROP_d16bae79/
REW_BEN_112) + §1.3 hardcoded ("Wellbeing","Reward") -> ("Reward",) since the Wellbeing SUPERPOWER is deleted;
qa_phase2 PROP_9620d380 -> PROP_e63cf45a (collision-tested clean). Re-sweep: ZERO deletion-set qids remain in any
gate. LIVE 11-gate suite GREEN on the deleted DB (freeze gate PASS); qa_phase2 25/0. qa_phase1 §1.1 stays red but
PRE-EXISTING and NOT deletion-caused: its raw-seed-CSV-vs-DB premise went obsolete when the r3sw corrections moved
answers away from the CSVs (original fixtures already failed; one fails only on a 2dp percentile-rounding edge) —
superseded by qa_engine_audit LAYER 1; full modernization is a separate item.
SURPRISES HANDLED: (a) 8 pre-existing signal_actions "orphans" = composite keys "<reward_matrix_qid>::rowkey" on
SURVIVING Reward matrices (0 reference a deleted qid) — the runner's first (over-broad) orphan check tripped and
correctly ROLLED BACK; refined to deletion-scoped + composite-aware. (b) COLLATERAL LIVE MUTATION, corrected:
qa_phase2 hardcoded ../lumi.db + `DELETE FROM drafts`, so verification runs wiped 2 live draft rows (REW_BEN_047/048,
org 5e67fa8c, autosaved 2026-07-23 07:43). RESTORED exactly from the Step-1 backup (drafts=2; answers-book unchanged)
AND fixed qa_phase2 to honor LUMI_DB so its DELETE can never hit live again.
ONE BEHAVIOURAL CHANGE (recorded): retrieval.py:129 scores the FULL bank and truncates to top-12 BEFORE app.py:3088's
Reward filter, so "Ask lumi" was crowded by non-Reward rows. Deletion DE-CROWDS that window -> the analyst may now
surface a Reward metric it previously refused on. An IMPROVEMENT — but it MASKS rather than fixes the filter-after-
truncate ranking bug, which stays QUEUED.
POST-DELETION COUNTS: questions 344 (333 served active + 11 retired) / answers 89,321 (= 230,359 - 141,038). Frame
per surface unchanged from nonrew-1 (README floor "300+", app.js no literal, qa_phase3 0-sentinel) so the four-frame
disagreement does not re-emerge.
VERIFIED: throwaway --write first (all asserts pass: FK=1, 344/89,321, 0 orphans, frozen-8 byte-identical, whole book
== pre-captured survivor hash b0ff15cb, pulse 5->3), 11-gate suite GREEN on the deleted copy, browser Benchmark
renders "All reward · 218 benchmarks" with 0 console errors (byte-identical to nonrew-1), both exports row-count
verified. LIVE (--write --confirmed-by-david, server stopped for a clean write + fresh cache): post-write EXACT match
to throwaway — questions 344, answers 89,321, 0 non-Reward remaining, 0 orphans, frozen-8 64e5dac7 byte-identical,
whole answers-book == survivor hash b0ff15cb (surviving Reward answers byte-identical), pulse -> its 3 Reward qids,
restored drafts intact; run_gates 11/11 GREEN (freeze PASS); live Benchmark 218 cards / ["Reward"] / 0 console errors.
QUEUE (unchanged, NOT actioned): retrieval filter-after-truncate bug; DK submission guard (match the "Don't know"
label specifically, never is_na — 41 legitimate Reward options depend on is_na rendering); qa_phase1 CSV-premise
modernization / retirement; GAP_004 seed-realism, INC_131 form-realism, on-call REW_PAY_016, PAY_097 regeneration,
7 COMMCAP, provenance gate, RED_TERM_03, CARE-option; B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC,
COMMCAP+INC_136, SICK_004.

## gate-safety-1 — harden get_conn() against silent live fallback (ruled + applied 23 July 2026)
ROOT CAUSE (stated plainly): server/db.py:13 was `DB_PATH = os.environ.get("LUMI_DB", <live>)` — get_conn() SILENTLY
DEFAULTED TO THE LIVE DB whenever LUMI_DB was unset. run_gates.sh always sets LUMI_DB (the live suite was safe), but
a bare `python qa_X.py` pointed at production. qa_phase2's hardcoded `../lumi.db` was a WORSE variant of the same
defect; the nonrew-2 fix (honor LUMI_DB) moved it INTO this class rather than out of danger.
THE INCIDENT THAT SURFACED IT: during nonrew-2 verification, qa_phase2's `DELETE FROM drafts` wiped 2 live draft rows
(REW_BEN_047/048, org 5e67fa8c), restored from backup. Found by ACCIDENT — nothing in the standing flow would have
caught it; drafts is not covered by any byte-identical assertion.
FIVE GATES were destructive-on-live if run bare — qa_release, qa_pulse, qa_strategy, qa_signals_system, qa_phase2.
qa_release the MOST DANGEROUS: `retire_question()` + `UPDATE questions SET is_required/version` change NO row count,
so they pass every standing assertion (only the 8 frozen targets are content-checked).
MECHANISM CHOSEN — process-name heuristic on argv0 (db.py._resolve_db_path). Precedence: (1) LUMI_DB set -> use it;
(2) LUMI_ALLOW_LIVE==1 -> live (explicit opt-in); (3) argv0 matches ^(qa_|verify_).*\.py$ -> RAISE with a message
naming the fix; (4) else -> live. WHY this and not the alternatives: the server has 150+ get_conn() call sites and
must work with NO env var (rules out an explicit allow_live= param); qa_release AND qa_pulse `import app`, so an
"app sets an opt-in flag at import" scheme would opt those two gates into live (rules it out); migration runners use
DIRECT sqlite3.connect() (not get_conn) so are unaffected. Process identity (uvicorn vs qa_X.py) is the only signal
left. Legit-live is distinguished from accidental by: the SERVER (argv0=uvicorn, not a gate) and DATA TOOLS
(aggregate/seed_/apply_/regen/mp_/notification_sweep — not gates) keep defaulting to live; MIGRATION RUNNERS keep
their own --confirmed-by-david guard; only qa_/verify_ processes must now name their DB. qa_phase2 (a direct connect)
was routed through get_conn so the guard reaches it too.
DATA TOOLS LEFT DEFAULTING TO LIVE (David ruled): deliberate-use, same class as migration runners with their own
guards. Forcing LUMI_ALLOW_LIVE into every rebuild would TRAIN THE BYPASS (operators would set it reflexively,
defeating the point).
THREE LIMITATIONS RECORDED (David's call to state plainly):
  (a) The mechanism is a NAME-CONVENTION HEURISTIC on argv0 — a gate named OUTSIDE qa_/verify_ (or invoked so argv0
      doesn't end in that) is NOT caught and would default to live. New gates must follow the naming convention or
      pass LUMI_DB.
  (b) OPERATING RULE: a bare-gate run must have :8060 pointed at a THROWAWAY first — get_conn cannot defend
      HTTP-mediated writes. Several gates (qa_strategy, qa_phase2, qa_focus:143, qa_engine_audit:716) mutate live via
      the API BEFORE any get_conn call; the DB guard fires too late for those.
  (c) The hardening makes bare HTTP-path runs LEAVE ORPHANS where they previously SELF-CLEANED: e.g. qa_strategy
      registers probe orgs via the API then DELETEs them via get_conn — post-hardening the get_conn cleanup REFUSES,
      so the API-created probe orgs are left orphaned. A VISIBLE failure (loud refuse) but a MESSIER end state than
      the silent self-clean it replaces. Demonstrated live during this diff's own proof: bare-running qa_strategy/
      qa_phase2 against the live :8060 created 2 "QA Strategy Probe" orgs + a Thornbridge draft that the refused
      cleanup left behind; restored exactly from lumi.db.bak_pre_nonrew2_delete_20260723 (all data tables == baseline;
      the only residual is a few ephemeral session tokens — auth, not data).
WHAT THIS DIFF DOES NOT FIX: the COVERAGE GAP (40 of 42 tables have no standing byte-identical assertion — why the
drafts wipe went unnoticed; the mechanism exists, this sweep computed all 42 counts — that is gate-safety-2). Also
NOT addressed: the API-mediated deletes that hit whatever is on :8060 (qa_focus:143 shares, qa_engine_audit:716
peer-groups, qa_phase2:140/147); 11 gates hardcode that URL. And the run_gates.sh trap gap (kill -9 / machine sleep
skips teardown, leaving :8060 on the throwaway DB with no "am I on the real DB?" check).
PAST OCCURRENCE UNDETERMINABLE (honest): no positive residue found (no 'REWORDED FIXTURE TEXT' on live, no leftover
fixture orgs before this diff), but the affected tables (drafts/shares/signal_actions/org_strategy/sessions/users/
orgs) mostly lack autoincrement keys, so a past mutation would leave no trace. NOT an all-clear.
VERIFIED: resolver unit test (4 branches: server->live, bare gates->REFUSE, LUMI_DB->throwaway, ALLOW_LIVE->live,
data tools->live); bare run of all 5 destructive gates REFUSES; run_gates 11/11 GREEN (freeze PASS) unchanged; bare
uvicorn serves /api/legal 200 + authenticated Benchmark renders "All reward · 218 cards / [Reward] / 0 console
errors"; migration double-guard intact (migrate_nonrew2 --write without --confirmed -> REFUSED) and migrations
connect fine (direct connect, unaffected); frozen-8 byte-identical; answers-book b0ff15cb + 41/42 tables exact
(sessions carries ephemeral login tokens only). db.py + qa_phase2.py the only files changed; ZERO data change.
QUEUE (added): route qa_plausibility.py and qa_reseed.py through get_conn or PROVE they can't write (both currently
use a direct connect / LUMI_DB read and bypass the guard; qa_plausibility is the freeze gate — read-only in intent,
unproven). gate-safety-2 (whole-DB table-count-and-hash standing assertion). Existing queue unchanged: API-mediated
:8060 deletes + :8060 hardcoding across 11 gates; run_gates trap gap; retrieval filter-after-truncate; DK submission
guard; qa_phase1 CSV-premise; GAP_004/INC_131/on-call REW_PAY_016/PAY_097 seed-realism; 7 COMMCAP; provenance gate;
RED_TERM_03; CARE-option; B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## gate-safety-2 — whole-DB standing assertion (ruled + applied 23 July 2026)
THE COVERAGE GAP + EVIDENCE: our standing assertions covered `answers` (whole-book sha256) + `questions` (COUNT only)
+ the 8 frozen targets — 40 of 42 tables had NO standing assertion. That is why qa_phase2's `DELETE FROM drafts`
went unnoticed during nonrew-2 (found by ACCIDENT, not any check), and why all three gate-safety-1 leaks (probe orgs,
users, org_strategy, terms_acceptances, a draft) were caught only by MANUALLY comparing all 42 table counts.
WHY STRUCTURAL BEATS PROCEDURAL (the justification, recorded plainly as a lesson beyond this diff): gate-safety-1
produced an operating rule — "point :8060 at a throwaway before bare-running gates." That rule was then FORGOTTEN
TWICE WITHIN THE SAME SESSION, by the person who wrote it, re-leaking the same fixtures both times. Procedural
controls decay; the get_conn guard (structural) did not. This diff makes DETECTION structural too.
THE DESIGN (server/dbsnapshot.py): fingerprint EVERY table derived from sqlite_master at RUNTIME (never a hardcoded
list — a table added later is covered automatically) as (row_count, content_hash). CONTENT hash, NOT count-only:
the qa_release case (`UPDATE questions SET is_required/version`) changes NO row count and would pass a count-only
check — demonstrated caught as "content changed, same count 344". Determinism: rows ordered by the table's PRIMARY
KEY (PRAGMA table_info), else by all columns — stable across runs / VACUUM. TIERING NOT NEEDED: full content hash of
41 tables / 218,304 rows in 0.26s (answers 0.11s, answers_history 0.09s); sqlite_sequence excluded (internal
counter, not data). EXPECTED-vs-UNEXPECTED: compare(before,after,expected=…) treats every undeclared table as
must-not-change — a migration declares the tables it writes; a gate/run_gates cycle declares nothing. A small,
justified VOLATILE allowlist (sessions, notification_events/reads, analyst_log, share_audit — server-log tables that
churn on normal use) is opt-in via --allow-volatile so it doesn't cry wolf on an ambient login. NAMES WHAT MOVED
("drafts count -2 (2->0)", not "state changed").
WHAT IT COVERS / DOESN'T (the load-bearing honesty): COVERED automatically — the whole run_gates cycle (wired: run_
gates.sh fingerprints live before the suite and asserts "live DB untouched by the suite ✓" at teardown; the suite
runs on the throwaway) and any migration that adopts the module. NOT COVERED automatically — a BARE, UNWRAPPED manual
gate run, which is exactly where every real leak came from. The standalone CLI (`dbsnapshot.py save/check`) makes that
a two-command wrap, but nothing FORCES it (procedural). The leaks are HTTP-MEDIATED (the gate writes via the :8060
API, not get_conn), so NO DB-side tool can auto-catch an unwrapped run — the structural fix for those is the :8060
hardening (queued). gate-safety-2 gives fast structural detection everywhere an operation is already wrapped, and a
cheap manual wrap elsewhere; it does not, and cannot, auto-cover the unwrapped bare run.
PLACEMENT — all three surfaces, each a different failure mode: (1) standalone CLI (bare-run wrap + manual audit — the
manual 42-table comparison done by hand ×3 this session, now one command); (2) run_gates.sh self-check (wired this
diff — defensive, proves the suite never leaks live); (3) reusable module (migrations `import dbsnapshot` — available
now; retrofit into the N existing runners DEFERRED as a mechanical follow-up, since migrations are already the best-
covered surface via answers + frozen-8 hashing — David ruled).
COMPLETION OF THE GATE-SAFETY SEQUENCE: the sweep (inventory of the hazard) -> gate-safety-1 (structural PREVENTION on
the DB path: get_conn refuses live-by-default for gate processes) -> gate-safety-2 (structural DETECTION: whole-DB
assertion). STILL OPEN (queued): HTTP-mediated writes via :8060 (11 gates hardcode the URL — same fix shape as gate-
safety-1 and the REAL remedy for the procedural rule); qa_plausibility/qa_reseed bypass get_conn (direct connect);
the run_gates.sh trap gap (kill -9 / sleep skips teardown, leaving :8060 on the throwaway).
VERIFIED: 0.26s full snapshot; catches the drafts wipe (count -2), the probe-org multi-table leak (orgs+2/users+1/
org_strategy+1/drafts+1, each named), and the qa_release content-only case; expected-delta suppresses declared changes
and fires on undeclared; false-positive check — a full run_gates cycle leaves live BYTE-IDENTICAL even in STRICT mode;
wired self-check prints "live DB untouched by the suite ✓"; run_gates 11/11 GREEN (freeze PASS); answers-book b0ff15cb
+ all 42 table counts byte-identical; frozen-8 byte-identical. Files: server/dbsnapshot.py (new) + run_gates.sh (self-
check wiring); ZERO data change.
QUEUE (added): retrofit dbsnapshot.compare into the migration runners (mechanical pass across N runners — generalise
their answers+frozen-8 hashing to all 42 tables with declared expected deltas). Existing queue unchanged: :8060 HTTP-
write hardening across 11 gates; route qa_plausibility/qa_reseed through get_conn or prove they can't write; run_gates
trap gap; retrieval filter-after-truncate; DK submission guard; qa_phase1 CSV-premise; GAP_004/INC_131/on-call
REW_PAY_016/PAY_097 seed-realism; 7 COMMCAP; provenance gate + seed/member provenance; RED_TERM_03; CARE-option;
B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## seedreal-1 — sector-tilt mechanism + GAP_004 regeneration (ruled + applied 24 July 2026)
OPTION A REJECTED, and why: adding an Industry term to regenerate.py's CORE latent (Profile.F/R) is the WRONG SHAPE.
The generator diagnostic proved the firmographic latent is CORRECT for maturity-driven practices (pay transparency,
formal-policy adoption, benefit richness track size/maturity, not sector) and wrong ONLY for genuinely sector-
concentrated ones — a SELECTIVE defect. Quantified blast radius that made the case: 88 of 333 active Reward metrics
generate sector-blind, of which 22 FEED MEMBER-FACING VERDICTS (positions.py:778, proven) and 5 sit in live
coherence pairs (one the REW_INC_103 controller); ~10 more carry hand-coded sector branches a core term would
DOUBLE-TILT; 214 are skipped (untouched). A core term would fix a handful by moving ~80 others away from correctness.
OPTION D CHOSEN — a structured per-metric SECTOR_TILT table in regen_priors.py, consumed by the generator via a pure
`if qid in SECTOR_TILT` hook (regenerate.py). HONEST CAVEAT: this is the SAME pattern that produced on-call's wrong
+0.22 Technology bump (L490). The GOVERNANCE is the difference, not the mechanism: each entry is an explicit,
David-ruled record carrying targets + rationale + anchor_status/shape_status as DATA. Double-tilt is not
auto-prevented — the guard is that David rules each entry against the documented hand-coded list.
ANCHOR POSITION (a future reader must tell which half is sourced): GAP_004's OVERALL 56% is ANCHORED (grade 2,
register 'Yes 56%') — the only sourced number. The SECTOR SHAPE is DAVID'S DOMAIN JUDGEMENT (2026-07-24), NO
published UK long-service-by-sector figure exists. Full ruled direction table (Yes-prevalence): Public/Education
77.5%; Manufacturing/Construction/Energy 67.5%; Healthcare/Charity 60%; Financial/Professional 50%; Logistics/Retail
40%; Media/Tech 30%; Hospitality 27.5% (rationales in SECTOR_TILT). The tilt is CENTRED so the org-weighted mean holds
the 56% anchor (the ruled targets average 50.6%, so realised ≈ ruled +5.4pp) — it redistributes shape, holds the total.
DETERMINISTIC QUOTA over Bernoulli (ruled): each sector gets round(centred_target·n) Yes; within a sector, orgs ranked
by a stable hash take the top-k. This DELIBERATELY TRADES within-sector variance for FAITHFUL SHAPE. At n≈8-10 the
Bernoulli draw buried the judgement — Tech landed 60% against a 30% target, INVERTING the ruled intent, and Education
reproduced the indefensible 100%. The quota expresses the shape: Tech 40% (below median), Education 88%, every sector
directionally correct. SMALL-CELL CAVEAT: six previously-100% sectors are n≈8-10, so cells remain rounded around a
defensible centre (Education 88%, Energy 75%) — deterministic, not pinned-at-100%.
RESULT (live): GAP_004 overall 75.8% -> 57.1% (holds 56% anchor); 89 orgs changed (63 Yes->No, 26 No->Yes). BLAST
RADIUS = 1: non-GAP_004 answers-book, frozen-8 (0a17a094, unchanged since programme start), and the 5 coherence-pair
metrics all BYTE-IDENTICAL; row count 89,321 unchanged. VERDICT-FEEDING (GAP_004 = class=Provision, higher_is_better,
scored, not suppressed): 63 orgs' GAP_004 card worsens, 26 improve; gauge recomputes green.
MARGINAL-PROVENANCE FINDING (David flagged): the freeze gate initially FAILED because generated_marginals.json pinned
GAP_004 at 0.76 — the GRADE-B LEGACY figure (lumi HR Data Hub 2019-20, n=42), NOT the grade-2 anchor. That is the
internal register tension. This diff updates the marginal 0.76 -> 0.56 (grade B -> grade 2) atomically with the reseed
(dual-config). SCAN: of 40 register marginals (31 grade-A / 7 grade-B / 2 grade-C), exactly ONE OTHER shares GAP_004's
'lumi legacy / HR Data Hub 2019-20' provenance — OT_04_b14623a6 (target 0.63) — flagged to check its anchor vs the
legacy figure.
r3sw33 SUPERSESSION (ruled): regeneration redraws every org, so the parked 30 contradictions are OVERWRITTEN, not
resolved; post-reseed count is 53 GAP_005-milestone-listers now GAP_004=No, 42 carrying a GAP_007 value (was 30/18).
The union-base logic is re-applied as a SEPARATE second diff against this new distribution.
NO FROZEN COLLISION: all 8 frozen targets are "skipped" (never regenerated) — none in the sector-blind set.
DEAD-CODE CAVEAT: regenerate.py is NO LONGER RUNNABLE against the live DB (SELECT_PRIORS reference DK options r3sw13
stripped; MULTI_PRIORS reference questions nonrew-2 deleted — it crashes in the OLD code before reaching GAP_004). So
the full-regen byte-identical proof CANNOT execute; the SECTOR_TILT hook is exercised ONLY via the targeted reseed
today (migrate_seedreal1_gap004.py, the r3sw pattern). Repairing the generator for full regens is queued.
VERIFIED: throwaway --write first (overall 57.1%, blast-radius=1, gates 11/11, freeze PASS with the staged marginal,
browser card renders); LIVE (--write --confirmed-by-david + re-aggregate + restart): post-write EXACT match to
throwaway (live GAP_004 == throwaway, non-GAP_004 book == throwaway = unchanged, marginal 0.56, served payload
57.1%/42.9%), frozen-8 0a17a094 byte-identical, run_gates 11/11 GREEN (freeze PASS, gate-safety-2 "live untouched by
suite ✓"), live Benchmark card Yes 57.1%/No 42.9% n=198 with 0 console errors. Files: regen_priors.py (SECTOR_TILT),
regenerate.py (hook+helpers), migrate_seedreal1_gap004.py (reseed), generated_marginals.json (GAP_004 0.76->0.56).
QUEUE (added): re-apply GAP_004/GAP_005 union-base logic against the new distribution (the r3sw33 successor — 53/42
contradictions); repair regenerate.py so the sector-tilt mechanism isn't dead code (align SELECT_PRIORS/MULTI_PRIORS
with the post-r3sw13/nonrew-2 live schema); check OT_04_b14623a6's grade-B-legacy 0.63 marginal against its anchor;
PAY_016 on-call anchor hunt (still unfixable without a by-sector source); PAY_097 pole-only regeneration; INC_131
ownership-locked (leave unless r3sw2 re-opened); on-call +0.22 Tech bump (correct via the tilt table once anchored).
Existing queue unchanged: :8060 HTTP-write hardening; migration retrofit of dbsnapshot.compare; qa_plausibility/
qa_reseed get_conn bypass; run_gates trap gap; retrieval filter-after-truncate; DK submission guard; 7 COMMCAP;
provenance gate; RED_TERM_03; CARE-option; B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136,
SICK_004.

## seed-realism CLOSE — three closures + one finding (ruled, DECISIONS-only, 24 July 2026)
Following the PAY_097 pole diagnostic, David ruled the remaining seed-realism items closed as documented DECISIONS
rather than open queue work. NET POSITION: all four seed-realism items are now RESOLVED — GAP_004 fixed (seedreal-1,
0d621ea); PAY_097 + PAY_016 unfixable pending sources; INC_131 deliberately locked. The queue shrank by documented
honesty, not by shipping. This entry is DECISIONS-only: no code, no DB, no config, no reseed.

(1) PAY_097 — CLOSED, NOT DEFERRED: the pole is not safely fixable.
  ANCHOR DOES NOT MAP ONTO THE POLE — three different quantities. CIPD/ADP PPT 2024 (n=832) measures MERIT-PAY
  PREVALENCE PER EMPLOYEE GROUP (MPT 41% / other 29%; private 48%/33%). REW_PAY_097 asks ORG-LEVEL, ANY GROUP — an org
  differentiating for MPT-only answers Yes, so org-level prevalence is STRUCTURALLY HIGHER than any group figure. And
  the register anchors Yes-STRONGLY at 34%, not the pole at all. The working figure "63% differentiated vs ~48%" was
  COMPARING UNLIKE THINGS: the live pole is 76.7% on the substantive base (Yes-strongly 64 + Yes-moderately 58 of 159)
  and has NO anchored target.
  DEFECT IS BOTH LEVEL AND SHAPE: Healthcare 100%, Financial 100%, Public Sector 90%, Charity 80%, Education 75% —
  implausibly high in exactly the spine-point/pay-scale sectors; flat 70-86% across FTE bands where larger employers
  should differentiate more. NEITHER has an anchored target, so a regeneration would INVENT BOTH.
  IT WOULD OVERWRITE r3sw32's deliberate work — the 16-clear, the 6 preserved honest "No-flat", and the ONLY record of
  the reverse-N/A cohort (the r3sw33 supersession pattern, but here DESTROYING EVIDENCE rather than superseding
  analysis).
  REOPEN CONDITION (explicit): a source that anchors ORG-LEVEL pay differentiation, OR David ruling the CIPD group
  figures onto the org level as a recorded judgement (the way GAP_004's sector shape was ruled). Absent either, leave
  as-is. PAY_097 is class=Practice, neutral, VERDICT-SUPPRESSED (re-proven at positions.py:778 — fails 'not Practice'
  AND fails 'polarised', direction=null), in NO coherence pair, and carries NO generated_marginals.json entry — so a
  reseed would be neither freeze-gate-blocked nor freeze-gate-validated.

(2) PAY_016 (on-call) — CLOSED PENDING RESEARCH, not queued as buildable work.
  NO UK on-call-by-sector anchor exists; the register records "needs research". Only a coarse overall ~32% on-call
  reference (ALLOW_01, r3sw29a). Any sector tilt would be INVENTED — the EAP failure mode. This is a RESEARCH task, not
  a build task; the metric stays unfixable until a source exists. The known-wrong hand-coded +0.22 Technology bump at
  regenerate.py:490 is BACKWARDS from real on-call concentration (healthcare, utilities, IT-ops, emergency/field
  service) and is a candidate for correction via the SECTOR_TILT table ONCE AN ANCHOR EXISTS — not before.

(3) INC_131 — CLOSED as DELIBERATELY LOCKED.
  Changing it re-opens r3sw2, breaks the live 131<->133 freeze-gate coherence pair, and moves INC_132's conditioning
  base (fixed r3sw31). The anchor is OVERALL-ONLY ("Yes 54%", grade 3) and CANNOT validate the cell-level implausibility
  that motivates the change. Three of the four implausible cells are TINY — VC n=5, Mutual n=11, LLP n=2 — so the
  apparent wrongness is partly small-sample noise. Recorded as a DELIBERATE decision to leave locked (stops it
  resurfacing as open). Reopen ONLY on David's explicit authorisation.

(4) TWO CORRECTIONS TO PRIOR FINDINGS (affect future work):
  (a) The seed-realism triage's "Group A" grouping was WRONG about PAY_097. PAY_097 is SKIPPED by the generator
      (scoring_config.polarity=neutral fails the 'laddered' test), so template_weights NEVER touches it — its
      distribution is ORIGINAL SEED, not a generator artefact. The triage placed it in the shared sector-blind-latent
      group; incorrect. PAY_016 must be RE-VERIFIED against the same question (laddered vs skipped) rather than
      inheriting the triage's classification.
  (b) nonrew-2 DEGRADED PAY_097's evidence base. PERF_03 ("Does your organisation use performance ratings?",
      superpower=Growth) was deleted. Consequences: the reverse-N/A count fell 42 -> 32 NOT because data changed but
      because IDENTIFIABILITY was lost (10 orgs were reverse-N/A only via PERF_03); and the twice-declined 195-union
      multi-signal parent has COLLAPSED to a single signal (MERITMATRIX alone) — the engine change that resolution
      depended on has lost one of its inputs.
  GENERAL LESSON (open question, NOT resolved): nonrew-2's pre-deletion diagnostic proved no Reward COMPUTED value read
  a non-Reward metric — which was TRUE. But PERF_03 was serving as EVIDENCE FOR ANALYSIS, not as a computed input — a
  DIFFERENT CLASS OF DEPENDENCY the diagnostic wasn't looking for. There may be other cases. Recorded as an open
  question. (Queued: audit whether other deleted non-Reward metrics served as analytical evidence — the PERF_03 class.)
QUEUE after this (recorded, not actioned): GAP_004/GAP_005 union-base re-application (r3sw33 successor — contradictions
now 53/42 post-reseed); regenerate.py repair (dead against live: DK-stripped SELECT_PRIORS, deleted MULTI_PRIORS
questions — now a dependency for any future tilt work); OT_04_b14623a6 marginal-provenance check; audit deleted
non-Reward metrics for analytical-evidence use (the PERF_03 class); :8060 hardening across 11 gates; migration retrofit
of dbsnapshot.compare; qa_plausibility/qa_reseed get_conn bypass; run_gates trap gap; retrieval filter-after-truncate;
DK submission guard; 7 COMMCAP; provenance gate + seed/member provenance; RED_TERM_03; CARE-option; B — AIDISCLOSE,
COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004.

## gap004-correct — anchor mis-grade + open parent-child state (ruled LEAVE AS-IS, DECISIONS-only, 24 July 2026)
The gap004-reconcile diagnostic established that seedreal-1 (0d621ea) rested on a MIS-READ anchor, and that neither
available figure is strong enough to justify further change. David ruled: LEAVE THE DATA AS-IS, correct the record.
This is DECISIONS-only — no code, no DB, no config, no reseed. The log currently asserts something FALSE; that is the
fix.

(1) THE ANCHOR WAS MIS-GRADED — correcting seedreal-1's record. seedreal-1's entry states GAP_004's overall 56% is
"ANCHORED (grade 2, register 'Yes 56%') — the only sourced number." THIS IS WRONG. The register's `grade` column reads
**B**; "2 - leave/policy" is the `tranche` column (a batch label), NOT a grade. seedreal-1 misread the tranche as the
grade. The 56% comes from the SAME grade-B legacy source (lumi HR Data Hub intake, 2019-20; large-employer/FTSE skew;
pre-2024 vintage) as the 0.76 marginal it replaced — one grade-B legacy figure swapped for another from the same
source, recorded as a grade-2 upgrade. The register row is INTERNALLY INCONSISTENT: `seeded_headline = Yes 56%`
(n=212) but `real_anchor = 76% operate a long-service award scheme`; seedreal-1 reseeded to 56% while the row's own
anchor field says 76%. NOTE it does measure the RIGHT THING — both are org-level "operate a long service award scheme"
(unlike PAY_097 there is NO unit mismatch); it is the right thing, WEAKLY measured.

(2) THE 96% CHILD-EVIDENCE FLOOR IS GENEROUS UNVALIDATED SEED, not verification. GAP_005 ∪ GAP_007 ∪ GAP_004=Yes =
191/198 = 96%. Both children are PURE ORIGINAL SEED — answers_history: GAP_005 = 1 row, GAP_007 = 18 (seed + the
r3sw13 DK strip); never reseeded, never fill-audited. Both UNANCHORED in the register (GAP_005 "needs research";
GAP_007 "needs research", its only reference an HMRC TAX figure explicitly "factual, not prevalence"). 96% is
implausible against published UK prevalence for FORMAL long-service schemes (~40-60%) — the same generous generator
that produced GAP_004's pre-reseed 76%. RECORD EXPLICITLY: volume was mistaken for verification in the earlier
reading — 191 orgs' answers from an unvalidated generator is NOT stronger evidence than a weak anchor.

(3) OPTION D (re-open toward the children) — CONSIDERED and REJECTED on evidence. It would move GAP_004 to ~96.5% —
AWAY from the 40-60% band published UK reality supports. It would KILL the ruled sector tilt: pinning 191/198 to Yes
leaves 7 orgs across 5 sectors to express a 15-sector shape — David's ruled directions would survive in name only. It
would require a new ~0.96 marginal — LESS defensible than 56% and unanchorable. Record that this was Claude's
recommendation BEFORE the diagnostic and was REVERSED by it.

(4) THE RULING: LEAVE AS-IS. GAP_004 landed in roughly the right place for the wrong reason. 57.1% sits INSIDE the
defensible 40-60% band — the CLOSEST of the three candidate figures (56% weak-anchored / 76% same weak source / 96%
unvalidated seed) to published reality. DO NOT re-open seedreal-1 — the mechanism (SECTOR_TILT table + hook), the
quota-over-Bernoulli choice, and the ruled sector directions all STAND. DO NOT condition the children down (the fifth
option): no anchor exists for GAP_005 or GAP_007, and clearing ~78 orgs' milestone/award answers on the strength of a
grade-B figure would propagate an error we cannot validate — the Option-2 trap applied to data whose correctness is
unknown in BOTH directions.

(5) THE OPEN STATE (recorded honestly so it is not mistaken for resolved). 78 PARENT-ERRORS: orgs with GAP_004=No
whose own GAP_005 milestones or GAP_007 award value evidence a scheme; 59 were CREATED by seedreal-1's reseed — the
sector quota assigned No without conditioning on existing child evidence. GAP_004 FEEDS A MEMBER-FACING VERDICT
(class=Provision, higher_is_better, not suppressed — proven positions.py:778), so a verdict-feeding metric currently
CONTRADICTS its own children for 78 orgs; GAP_005 is suppressed, GAP_007 is neutral and does not feed. The
"CHILD-IMPOSSIBLE" cohort DISSOLVED — all 11 candidates list real milestones (itself scheme evidence), so they are
parent-errors too; there is NO answerable clear-to-N/A cohort, and r3sw33's parked conditioning question is therefore
CLOSED AS UNANSWERABLE in its original form, not merely deferred. The resolution path is RESEARCH, not a build: real
UK prevalence for long-service schemes, and any anchor for milestone patterns (GAP_005) or award values (GAP_007);
absent those, no option improves on leaving it.

STANDING LESSON (the durable output of this thread): a reseed that reshapes a PARENT without conditioning on existing
CHILD evidence will MANUFACTURE contradictions. seedreal-1 created 59. Any future application of the SECTOR_TILT
mechanism MUST check for child metrics whose answers constrain the parent, BEFORE reseeding.
QUEUE update: GAP_004/GAP_005 union-base re-application — CLOSED as unanswerable, superseded by this entry. ADD:
anchor-register GRADE AUDIT — the `grade` vs `tranche` column confusion that produced this error may affect other
entries; check whether any other metric's recorded grade was read from the tranche column. Existing queue otherwise
unchanged (regenerate.py repair; OT_04_b14623a6 marginal check; audit deleted non-Reward metrics for analytical-
evidence use — the PERF_03 class; :8060 hardening; dbsnapshot.compare migration retrofit; qa_plausibility/qa_reseed
get_conn bypass; run_gates trap gap; retrieval filter-after-truncate; DK submission guard; 7 COMMCAP; provenance gate;
RED_TERM_03; CARE-option; B — AIDISCLOSE, COMPARATIO; C — HOL_006+BEN_041, EVSALSAC, COMMCAP+INC_136, SICK_004).
