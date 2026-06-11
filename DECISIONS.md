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
