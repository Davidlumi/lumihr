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
