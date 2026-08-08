# Go-live checklist — what stands between here and the first founding member

Rewritten 2026-08-04 (PH-DOC-1): organised by the GATE that blocks each item.
Rule for every entry: **closed items carry their resolving commit; open items carry
their prompt ID and the specific condition that unblocks them.** The checklist points
at `DECISIONS.md`; it never restates it. The AI-insights go-live section (its own
gate, solicitor-signed) is preserved in full below the gates.

---

## Gate 1 — before the first organisation is provisioned

- [ ] **DEPLOYMENT — a publicly reachable instance (PH-CFG-1 Branch B finding,
  2026-08-04).** No deployed instance of the application exists: lumihr.co.uk serves a
  parking-class 403 (MX is Google — mail is real, the app is not there), and the repo
  has no deploy configuration. Every artifact that reaches a member (invite link, reset
  link, digest email) depends on this. *Unblocked by:* David ruling the hosting
  approach (host, TLS, domain/subdomain, where the production env lives) — a decision,
  then its own scoped work.
- [ ] **`LUMI_BASE_URL` + link-minting guard (PH-CFG-1 Branch A — DEPENDENT on the
  deployment item above).** Once somewhere exists to point at: one accessor everywhere
  (three divergent reads found and banked in DECISIONS — `_base_url()` dup; digest
  paths with a "" fallback emitting relative dead links), refuse to MINT invite/reset
  links when unset (gate the action, never the boot), https required for non-localhost,
  trailing-slash normalisation, boot-log the value. *Unblocked by:* the deployment item;
  then the Branch-A build against DECISIONS 2026-08-04 PH-CFG-1.
- [x] **PH-PROV-1f — provisioning log line → digest.** The provisioning invite's
  console/log fallback (AND the send-failure print) now carries a sha256[:12] digest via
  send_notification's `log_body` channel — the bearer never lands in a log; the API
  response still returns the link, and the real SMTP body still carries it. Tenant
  invite/reset emails untouched (they ARE delivery until D2; CF-1 governs).
  qa_backoffice S7a/S7b assert it on captured server stdout. **Commit: `edc7ff7`.**

## Gate 2 — before the first member submission

- [x] **PH-PAY-3 — suspension-reason visibility.** Every deactivation (org + user) now
  REQUIRES a reason (400 with the operator hint otherwise), stored in
  `orgs.deactivated_reason` / `users.disabled_reason`, audited, cleared at reactivation,
  and rendered in the console list chip, drill-down header, members table and user
  lookup; SOLE_ADMIN_RECOVERY.md names its reason verbatim. qa_backoffice = 105 checks.
  **Commits: `edc7ff7` (server) + `380ccd3` (console) + `a69fd69` (gate).**


- [ ] **PH-PROV-1c — the two mislabelled `source='signup'` orgs (HR Datahub, Tester).**
  Destructive, double-guarded, awaiting David's ruling. Now MORE visible: 2b's lifecycle
  column renders both as real members with lifecycle states; Tester's answer row is in
  the live answer book (89,321 → the book fingerprint moves when it goes); member counts
  read two high, including for provenance work. *Unblocked by:* David's ruling — **and
  the ⚠ factual correction below lands first.**
  - ⚠ **Factual correction required before 1c executes (PH-DOC-1 §3):** the drafted 1c
    rationale states HR Datahub has "no relationship to Lumi HR Ltd" and is a test
    artifact — but `david@hrdatahub.com` appears on the Offshore Wind Reward Forum
    distribution as a participant, so the org record may correspond to a real external
    contact. The disposition (DELETE) is unaffected; the wording in the permanent
    record is what must be right. *Unblocked by:* David restating the rationale
    factually. NOT resolved here.
- [ ] **C2 — member-facing retention disclosure gap.** DPA §5.2 states live-system
  deletion ≤30 days; nothing member-facing discloses that copies persist ≤90 days
  (PH-BAK-2 §A.4 C2, quoted verbatim in DECISIONS). Solicitor-bundle material, with the
  AI terms. *Unblocked by:* solicitor blesses the combined position (live ≤30d, copies
  ≤90d) as the §5.2 reading and sets the privacy notice's "limited period" number.

## Gate 3 — before Phase 2 (Postgres)

- [ ] **`db.py` fresh-database DDL divergence.** `CREATE TABLE orgs` still declares the
  pre-split shape (`name NOT NULL` etc.) — a fresh build is structurally impossible
  (proven, PH-SEED-1 §5) and Phase 2 would port the pre-split shape. *Unblocked by:* the
  DDL catching up with the step-5 world — related to the post-soak DROP diff, but the
  FRESH-DDL half cannot wait for soak end if Phase 2 moves first.

## Gate 4 — before a second environment exists (staging, pen test, off-live repro)

- [ ] **`seed_import` rebuild failure — the seed world no longer rebuilds.** Fresh build
  crashes (DDL/writer mismatch since step 5); CSVs stale (804 vs 344 live); registry 210
  vs 220; identity store never written by the importer. The live store is the sole
  authoritative world (PH-SEED-1 §5, README-flagged). *Unblocked by:* the seed-world
  reconciliation ruling + importer/DDL repair — its own scoped work.

## Gate 5 — before the 243-metric anchor register reconciliation starts

- [ ] **Question library has two competing sources of truth** — CSVs vs DB, CSVs
  deliberately stale by recorded convention; 138 of 344 live questions absent from the
  CSV (PH-SEED-1 measurement). The reconciliation maps by `metric_id` and must know
  which source is authoritative before it starts. *Unblocked by:* David ruling the
  authoritative source. Census-scoping doctrine applies: THE REGISTER IS NOT THE SCOPE —
  the live platform is (PH-BAK-2 §A.2).

## Pending David's ruling / action

- [ ] **PH-PAY-2 — suspension semantics: pause the clock, gate outbound mail.** Two
  defects recorded in PH-PAY-1 §B: (1) the 30-day submission clock burns while an org
  is suspended (named fix: pause on suspension, extend `clock_start` by the suspended
  duration on reactivation); (2) the sweep/digest paths carry no `deactivated_at` or
  `disabled_at` filter, so suspended members keep receiving benchmark emails.
  *Unblocked by:* David ruling the clock-pause fix; the mail gate rides in the same
  diff (both change what suspension DOES).


- [ ] **C1 — retention ceiling vs rotation depth.** Per-migration backups can outlive
  the 90-day ceiling if migrations pause; which rule yields is a ruling (PH-BAK-2 §A.4
  C1 — reported, not resolved). *Unblocked by:* David ruling ceiling-binds or
  rotation-binds.
- [ ] **Presplit pin — formal pin-dead ruling (2026-08-08).** The factual question is
  settled: the pinned backup is unrecoverable (TM never ran; no snapshot; no stray
  copy — evidence in the closed TM item above). What remains is the ruling: declare
  the pin DEAD in `data/backup_policy.md` and rewrite the post-soak DROP diff's
  pin-release close condition as a REBUILD-RECIPE precondition (the recipe is recorded
  in the 2026-08-05 incident entry, DECISIONS.md). *Unblocked by:* David's one-line
  ruling; the policy edit and DROP-diff condition rewrite then land together.
- [x] **Time Machine check — `/private/tmp` + presplit recovery (2026-08-08).** Resolved
  by direct measurement, stronger than the GUI check: `tmutil destinationinfo` = "No
  destinations configured", empty TM preferences (no SkipPaths/custom rules), no local
  snapshots — **Time Machine has never run on this machine**, so nothing (including
  /tmp gate workdirs and the in-tree bak copies) has ever been duplicated into a
  backup. **CF-2 is now CLOSED** (all three limbs; standing condition recorded: re-check
  /tmp scope if a TM destination is ever configured). SECOND ANSWER THE SAME EVIDENCE
  GIVES: the deleted `bak_pre_presplit` is **unrecoverable** — no TM copy, no snapshot,
  no stray copy on disk (mdfind + find sweep). The documented REBUILD recipe
  (identity.db values re-joined into the still-present nulled columns) is the only
  rollback vehicle. The formal **pin-dead ruling remains David's** (below).
- [ ] **AI Insights go-live flip** — David's steps a–d + steps 5/6 in the preserved
  section below. *Unblocked by:* David executing them in production.
- [x] **Stripe — RETIRED, not owed (PH-PAY-1, ruled all-payments-by-invoice).** The
  keys were never delivered; the card path (checkout routes, webhook, client redirect)
  is removed and `payments.py` is the invoice seam. Reinstating card is a deliberate
  build against DECISIONS 2026-08-04 PH-PAY-1. **Commit: see PH-PAY-1 §A.**
- [ ] **Solicitor bundle** (one visit): C2 above · AI-terms draft review
  (`lumi_AI_terms_DRAFT_for_solicitor.md` — AI-drafted text is never operative) ·
  privacy-notice retention number · paid-launch billing/refund clause (2026-06-22,
  now INVOICE-based per PH-PAY-1) · **non-payment/suspension gap (PH-PAY-1 §B.4): the
  Data Contribution Terms and membership terms are silent on non-payment, suspension,
  and what happens to contributed data in either state** · cookie policy analytics
  description (last draft-flagged legal doc).

## Deferred post-launch (deliberately; the stopping rules hold)

- [ ] **PH-PROV-1b** — `/api/team/invite` silent admin→viewer coercion becomes an
  explicit 400. Member-facing behaviour change; verified as-is in the gates meanwhile.
  *Unblocked by:* David scheduling it once launch settles (own diff, its prompt exists).
- [ ] **PH-PROV-1e** — identity_recon gate wiring (the split's step-7 debt), orphan
  remediation runbook, backup naming convention. *Unblocked by:* scheduling — no
  dependency; the manufactured-orphan cycle already exercises recon inside qa_backoffice.
- [ ] **D2 — real email delivery.** CF-1's close condition; console-logged links remain
  the accepted, contained exposure until then (PH-LOG-1 record). *Unblocked by:* the
  delivery build (SMTP already env-wired; `LUMI_SMTP_*`).
- [ ] **Seed/member provenance feature** (`is_seed`, blend-and-taper, real-contributor
  n) — now has its first caller (2b's lifecycle column, DECISIONS 2026-08-04).
  *Unblocked by:* David scheduling the provenance workstream.
- [ ] **PH-BAK-4 deferred script list** — run_gates' bounded residual and the unguarded
  inert stragglers (`regenerate.py`, `qa_reseed.py`); closed by the stopping rule, each
  reopens only with its own scope.
- [ ] **Post-soak DROP diff** — drops the dead `orgs.name`/`normalized_name` columns +
  `idx_orgs_norm`, and CARRIES PIN-RELEASE for `bak_pre_presplit` as one of its own
  close conditions (backup_policy.md). *Unblocked by:* soak ending.
- [ ] **Phase 4 — deletion-on-exit spec.** Now specifiable, no longer blocked: live-store
  deletion at exit + copies extinct within ≤90 days (PH-BAK-1 dependency resolution).
- [ ] **Wider docs pass** (README beyond the corrected lines, handover docs).
  *Unblocked by:* scheduling; single-line corrections have landed with their diffs.

---

# AI Insights — go-live (its own gate; solicitor sign-off RECEIVED 2026-06-28)

**Status: prep complete. ONE step remains — David's production env flip.** The lawful
basis is **legitimate interest (opt-out)** with an LIA on file; the legal text is
finalised, Anthropic is named as the AI sub-processor, and the terms version is `1.0`.
The master gate `AI_INSIGHTS_ENABLED` is still **default-OFF in code** as a backstop, so
**no real member sees any AI-generated content** until the single env flip below.

## How the gate works (unchanged)

Any AI feature renders **iff all three are true**:

1. `AI_INSIGHTS_ENABLED` (the master switch) is **on**, AND
2. that feature's own kill-switch is on (`LUMI_AI_COMMENTARY`, `LUMI_AI_ANALYST`,
   `LUMI_AI_BOARDPACK`, `LUMI_AI_PULSE`, `LUMI_AI_STRATEGY`, `LUMI_AI_DOMAIN_SUMMARY`), AND
3. the **member has not opted out** (`LUMI_AI_CONSENT_MODE=opt_out`: on by default; a member who turns
   AI Insights off in Settings records `kind="ai_insights_withdrawn"` and goes dark next request).

Under opt-out, flipping the master on exposes AI Insights to every member who has **not** opted
out — including members who joined before the feature existed (they are informed at signup / in the
privacy notice, and can opt out any time). Each member's choice is recorded per-person in the
`terms_acceptances` audit log, versioned to `AI_TERMS_VERSION` (`1.0`).

## What was done on sign-off (steps 1–4 — COMPLETE)

1. **Legal text finalised.** `legal/ai-insights-terms-v1.0.md` (draft suffix dropped,
   `LEGAL_INDEX` `draft:false`): banners removed, **Anthropic PBC** named as sub-processor,
   lawful basis set to legitimate interest, opt-out control wording.
2. **Lawful basis + mode set.** `LUMI_AI_CONSENT_MODE` default is now **`opt_out`** (legitimate
   interest); LIA confirmed on file.
3. **Terms version bumped** `1.0-draft → 1.0` (`AI_TERMS_VERSION`).
4. **Sub-processor + privacy disclosure.** The Anthropic row was added to the Sub-processor List
   (aggregated/derived figures only — no individual salaries; no training on inputs; zero/limited
   retention; DPA + transfer safeguards), and an **AI-assisted analysis** section was added to the
   Privacy Notice.

### Post-sign-off prerequisites (this release — COMPLETE)

- **C3 — opt-out cache deletion.** Turning AI Insights off now DELETES the org's cached AI
  summaries (`domain_summary` + `metric_commentary`), not just gates them — `purge_ai_cache()` in
  `server/app.py`, called on withdrawal. Verified: opt-out → cached rows gone + route 403, with a
  second org's cache untouched (per-org scope).
- **C4 — non-AI placeholders filled.** Privacy Notice rights contact = **dpo@lumihr.co.uk**;
  Sub-processor List hosting = **Amazon Web Services (AWS)**, email = **Amazon SES**. Both pages
  finalised (`-draft` suffix dropped, `LEGAL_INDEX` `draft:false`). Only the **Cookie Policy**
  remains draft (pending its analytics description — carried in the solicitor bundle above).
- **Article 30 / LIA attestation** produced: `compliance/ai-insights-data-minimisation-attestation.md`
  — send-ready; David emails it to the solicitor to append to the RoPA / LIA.

### David's actions before the flip (in order)

- **a.** Accept the **Anthropic DPA** in the Anthropic console (confirm zero-retention / no-training
  commercial terms + transfer mechanism match the Sub-processor List row).
- **b.** **Email the attestation** (`compliance/ai-insights-data-minimisation-attestation.md`) to the
  solicitor for the RoPA / LIA.
- **c.** Confirm the C4 values are live — that **dpo@lumihr.co.uk** receives mail, and that AWS / SES
  are the actual providers.
- **d.** Confirm the DPA / Article 30 records cover the AI processing and Anthropic, then proceed to
  step 5.

## The remaining step — David's, in production (step 5)

5. **Flip the switches on:** in the production environment set BOTH
   `LUMI_AI_INSIGHTS_ENABLED=on` (the member-facing surface gate) AND `LUMI_AI_LIVE=on`
   (the positive paid-API switch — added 2026-07-04). AI Insights then render for all
   non-opted-out members, feature-by-feature (each per-feature flag still independently
   killable without a deploy). Note `LUMI_AI_DOMAIN_SUMMARY` defaults OFF — set it `=on`
   too if the per-domain summary should ship. Ensure `ANTHROPIC_API_KEY` is configured in
   prod. **Until `LUMI_AI_LIVE=on` is set, every surface stays keyless/deterministic even
   with a key present** — so a key sitting in `.env.local` can never trigger paid calls on
   its own (closes the pre-go-live "empty-key env var is load-bearing" landmine).

6. **Re-run the adversarial gates on prod config** (`python3 server/qa_domain_summary.py`,
   `python3 server/qa_commentary.py`) and watch the first live generations.

## Kill switches (any time, no deploy)

- `LUMI_AI_LIVE=off` (or unset) — the paid Anthropic client never builds; every surface
  falls to its validated deterministic floor. This is the hard "no spend" switch.
- `LUMI_AI_INSIGHTS_ENABLED=off` — cuts ALL AI insight SURFACES instantly (the master).
- `LUMI_AI_<FEATURE>=off` — cuts one feature.
- A member toggles off in Settings — withdrawal recorded, their gate closes next request.

---

## Closed platform-safety blockers (hashes resolve; detail in DECISIONS.md)

- [x] **PH-SEED-1** — `seed_import.py` cannot default to the live store (`--db` mandatory
  both paths, live-store refusal + awkward override, dry-run default, destruction
  preview). **`a620921`** (docs `1f72817`). Its §5 finding (seed world no longer
  rebuilds) lives under Gate 4 above.
- [x] **PH-PROV-1 Phase A** — staff-provisioned membership, self-serve closed. **`90a8142`**
- [x] **PH-PROV-1d** — recon/gate outputs never print a bearer. **`86c6446`**
- [x] **PH-PROV-1g** — at most one live admin invite; the carve-out's boundary. **`257a0de`**
- [x] **PH-PROV-2a** — console provisioning form (members admittable). **`210e075`**
- [x] **PH-PROV-2b** — lifecycle column + invite actions + sole-admin recovery
  specified. **`9ce4044`** + **`9977838`**
- [x] **PH-LOG-1** — credential-bearing logs contained; CF-1 opened with its close
  condition. **`df3b95b`**
- [x] **PH-BAK-1** — clean-history proof, census corrective, purge mechanism + teardown
  fix (records in DECISIONS 2026-08-03).
- [x] **PH-BAK-2** — census-scoping + symlink doctrines, startup sweep. **`7ec5a79`** +
  **`a899bc7`**
- [x] **PH-BAK-3** — identity backup rotation fail-closed. **`dc68c49`**
- [x] **PH-BAK-4** — delete-path re-triage + policy-conformance line. **`eeeb2a6`** +
  **`7a2f78b`**
