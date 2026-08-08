# Privacy Phase 4 — deletion on exit: SPECIFICATION (2026-08-08)

Status: **SPEC ONLY — nothing here is built.** Drafted under the standing programme
(Phase 0 diagnostic 2026-07-30 → Phase 1 split → soak). The checklist marked this
"now specifiable, no longer blocked" once PH-BAK-1 resolved the copies-retention
number (90 days). David rules on the open parameters in §6 before any build.

## 1. The promise being implemented

PH-PAY-1 §B fixed the boundary this spec depends on: **exit is the ONLY state that
ever removes data** (suspension gates access and deletes nothing; conversion from
suspension to exit is a DECISION, never a timer). Phase 4 implements what exit
means:

> On exit, the member's data leaves the live system promptly (DPA §5.2: ≤30 days),
> and every copy of it becomes extinct within the retention ceiling (≤90 days,
> PH-BAK-1 ruling) — including backups, scratch copies, and derived caches.

## 2. What "the member's data" is (deletion inventory)

Reward store (`lumi.db`), keyed by org_id:
- `answers`, `answers_history`, `drafts` — the contributed book, INCLUDING history
  (the refresh system's append-only preservation is a membership benefit, not a
  post-exit right).
- `org_strategy`, `org_assumptions`, `peer_groups`, `pinned_views`, `dashboards`,
  `metric_commentary` (org-scoped rows), `domain_summary`, `signal_state`/`signal_seen`/
  `signal_actions`, `notification_reads`/`notification_events` (user-scoped),
  `validation_overrides`, `terms_acceptances`, `shares` + `share_audit`,
  `pulse_responses` (see §6 Q3), `pulse_launch_orders` (see §6 Q4 — invoice ledger),
  `metric_requests`, `metric_suggestions` (see §6 Q5 — co-op contributions),
  `users` rows, `invites`, `password_resets`, and finally the `orgs` row.
- `admin_audit_log`: RETAINED — staff-action accountability is lumi's record, actor
  is a user_id, targets resolve to nothing after deletion (documented outcome).

Identity store (`identity.db`): `org_register`, `users`, `invites`, `sessions`,
`password_resets` rows for the org — via identity.py helpers ONLY (module boundary).

Aggregates: `benchmark_snapshots` rows are NOT per-member and are not deleted; the
next `aggregate.py` run after live-deletion recomputes every cut without the leaver
(n-floors re-apply; a cut dropping under n=5 suppresses — the correct consequence).

## 3. Mechanism (the shape of the build)

1. **`server/member_exit.py`** — the one deletion tool. House conventions: dry-run
   default printing a full per-table row-count preview; `--write --confirmed-by-david`;
   pre-write backup pair (reward + identity, SQLite backup API, policy-named tags,
   PINS EXCLUDED FROM ROTATION — the 2026-08-05 incident guard is the model);
   one transaction per store, reward first, identity second (mirror-order of
   provisioning so a crash leaves an identity-only orphan that identity_recon
   names, never a silent reward orphan); answers book hash asserted over the
   REMAINING book (exact expected delta printed first).
2. **Exit record**: a dated DECISIONS entry per exit (org_id, row counts per table,
   book hash before/after, operator) — the record proves the deletion happened;
   it contains no name/email (the identity rows are gone; the record must not
   resurrect them).
3. **Copies schedule**: at exit time, enumerate every backup that CONTAINS the
   member (creation-time doctrine: every backup is already retention-scheduled;
   exit does not extend any schedule). The exit record lists each copy and its
   already-scheduled death date; the LAST death date is the "extinct by" date the
   member can be told (≤90 days by the ceiling). No new mechanism — the policy's
   existing schedule IS the mechanism; the exit tool just computes and prints the
   date.
4. **Scratch sweep**: `purge_throwaway_copies.py` (Groups B/C) runs as part of the
   exit close — session scratchpads and gate workdirs are exactly where a copy
   could dodge the schedule. (Backstopped every suite run by the startup sweep.)
5. **Recompute + verify**: `aggregate.py` re-run; `identity_recon` PASS; full gate
   suite green; `qa_backoffice` E/F sections still hold (the org is gone, not
   deactivated — 404s, not 403s).

## 4. Interaction with existing rulings (all preserved)

- STAYS_IN_POOL (suspension) — untouched; this spec only fires on the exit DECISION.
- Sticky-unlock — moot post-exit (no users remain to see anything).
- Seed/member provenance — exit reduces real-contributor n; the provenance feature
  (queued) reads the store, so no coupling beyond recomputation.
- The presplit pin incident — §3.1's backup step inherits the pin-guard pattern;
  any pin extant at exit time is EXCLUDED from the "copies containing the member"
  death-date computation and must be called out in the exit record explicitly
  (a pinned copy holding a leaver is a conflict ONLY David can rule on).

## 5. Verification matrix (for the eventual build)

| # | Assertion |
|---|-----------|
| V1 | Dry-run preview counts == write-path deleted counts, table by table |
| V2 | Remaining-book hash matches the printed expectation |
| V3 | identity_recon PASS after exit (no one-store residue) |
| V4 | Every org-keyed table reports 0 rows for the org_id (census by namespace, not inventory — the census-scoping doctrine) |
| V5 | aggregate re-run: no cut carries the leaver; n-floor suppression applied where n dropped below 5 |
| V6 | Exit record lists every containing copy + death date; latest ≤ exit+90d |
| V7 | Full suite green; live-DB fingerprint moved ONLY by the expected delta |

## 6. Open parameters — DAVID RULES BEFORE BUILD

1. **Grace window**: exit effective immediately, or a cooling-off (e.g. 14 days
   suspended-then-deleted) so an accidental exit is recoverable? (The DPA's ≤30
   days runs from exit either way.)
2. **Terms-acceptance rows**: legal-defence value argues RETAIN (what was agreed,
   by whom, when) — but they are identity-adjacent (user ids). Retain reward-side
   rows with user_ids that resolve to nothing, or delete? (Solicitor question —
   already adjacent to the §B.4 terms gap on the bundle.)
3. **Pulse responses**: pooled, never individually served (`qa_pulse` firewall).
   Delete the leaver's rows (consistent with the promise) or retain as
   already-anonymous pool contributions? Deletion is the safer default; pool ns
   recompute like §2's aggregates.
4. **Invoice ledger** (`pulse_launch_orders`): accounting records normally outlive
   membership (statutory retention). Proposed: RETAIN, documented as the named
   exception with its own statutory clock. Confirm.
5. **Metric suggestions/requests**: contributed to the co-op's library. Proposed:
   retain CONTENT, null the org/user attribution at exit. Confirm.

*Written 2026-08-08 under "fix all - deliver all"; supersedes nothing; builds on
data/backup_policy.md, PH-BAK-1/2 records, PH-PAY-1 §B, and the census-scoping
doctrine.*
