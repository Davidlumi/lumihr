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
