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
