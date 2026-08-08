# Backup retention policy — ruled 2026-07-30 (Privacy Phase 0, D1)

## The doctrine, verbatim as ruled
**Backups are managed PII artifacts from creation.** Every backup is retention-scheduled at the moment it
is created — **no unversioned, unscheduled full-DB copy is ever created**. *(The original draft doctrine
scoped this to "member-era" data; that distinction was withdrawn with the synthetic-era premise on
2026-07-30: the Phase-0 assertion test showed real-pattern rows exist in the live seed and therefore in
every backup of it — there never was a synthetic era. The doctrine applies from creation, always.)*

## The retention rule
- **DB class (`lumi.db.bak_pre_<tag>_<ts>`):** retain the **last 3 pre-diff backups** (plus their
  `-shm`/`-wal` sidecars, which belong to their copy). Creating a fourth schedules the oldest for
  deletion in the same close that created it.
- **Register class** (versioned-register `.bak` files): retained — they are provenance for ruled register
  transitions and carry organisation-level metric data only.
- **Config/code class** (`*.bak_pre_*` on `.py`/`.json` artifacts): outside this policy (no personal-data
  payload); housekeeping at David's discretion.
- **Scratch/throwaway copies** (session scratchpads): outside this policy today; in scope for the
  Phase 3–4 deletion-on-exit design, which must sweep them.

### Identity class (`identity.db.bak_pre_<tag>_<ts>`)

**Effective at the Phase-1 identity/reward split. No identity store exists
at the time this clause is written; the doctrine precedes the store it
governs.**

Retention: **retain the last 1**, scheduled for deletion at creation of
its successor, per the creation-time doctrine above.

Ground: unlike the DB class, every byte of an identity backup is the PII
concentrate this policy's Why section enumerates. No non-PII bulk dilutes
it, and its history carries no analytical value — there is nothing in an
older identity copy worth the exposure of holding it.

**The retain-1 rule is conditional, and the condition is binding.** Reward
data without the identity mapping is anonymised rubble, and the mapping is
**not reconstructible from the reward store**. A single bad copy is
re-identification of the membership by asking members. Retain-1 therefore
applies **only where the creating step records both**:

1. an integrity check of the new copy, and
2. a row-count assertion of the copy against the live identity store.

Where either is absent, **the retention for this class is retain-2**, not
retain-1. The assertion is the whole basis for holding one copy; without
it the second copy is the assurance.

Implementation of the check belongs in the backup-creating script. The
requirement belongs here, so that retain-1 cannot quietly come into effect
through a script rewrite that drops the assertion.

### Named exception: the pre-split backup pin — **PIN DEAD (R2, ruled 2026-08-08)**

**Status: the pinned artefact no longer exists and the pin is formally DEAD.** The
copy was deleted 2026-08-05 by a retention sweep that failed to honour this section
(incident recorded in DECISIONS.md that day), and the 2026-08-08 measurement proved
it unrecoverable (no Time Machine destination has ever existed on the machine; no
snapshot; no stray copy on disk). Per R2, an unrecoverable backup left nominally
alive on the books is worse than none — it invites the next reader to plan a
rollback around an artefact that cannot deliver one. **The successor to the pin is
the REBUILD RECIPE** (DECISIONS 2026-08-05 incident entry): the reward store still
carries the nulled identity columns and identity.db holds every moved value keyed by
the same ids, so a pre-split-shape store is reconstructible by re-join. **The
post-soak DROP diff's close condition is accordingly REWRITTEN: it no longer carries
pin-release (nothing to release); it carries instead the assertion that the rebuild
recipe has been re-verified against the stores AS THEY ARE at DROP time** — the DROP
destroys the recipe's ingredients, so the check belongs to the diff that removes
them. The standing lesson stays in force for every FUTURE pin: the rotation count
never includes pins, and any new pin lands in this file AND in every sweep's
exclusion guard together.

The original pin text is retained below for the record:

### (historical) the pre-split backup pin

The backup taken immediately before the Phase-1 split migration (S6 step 0
of `PRIVACY_PHASE1_SPLIT_SPEC_2026-07-30.md`) is a **named exception** to
the last-3 DB-class retention rule. It is **pinned** — excluded from the
rotation count — and held until released.

Ground: without the pin, three subsequent pre-diff backups age it out, and
rollback dies three diffs after the split. It is the only copy of the
pre-split shape.

**Release trigger, named explicitly: the close of the post-soak DROP
diff** — the commit that drops the nulled identity columns from the reward
store. **That transmission carries pin-release as one of its own close
conditions**; the pin is not released by anyone remembering it
independently.

Per the creation-time doctrine, **the pin's deletion is scheduled at
pin-creation**, conditional on that trigger. A pin with a release
condition but no scheduled release becomes a permanent PII concentrate
that nobody destroys.

While pinned, the copy is a full-PII artifact and is treated as such: it
is in scope for the Phase 3–4 deletion-on-exit design, and it is not a
working copy for any purpose other than rollback.

### Both stores, after the split

The creation-time scheduling doctrine applies **per store**, not per
migration. A migration that touches only the reward store must not
snapshot the identity store as a convenience copy — a copy taken for
convenience is a PII concentrate created without a retention decision,
which is precisely what this policy exists to prevent.

Reward-store backups **remain in the DB class** after the split. They no
longer carry names, but they still carry `org_id` join keys and are
therefore linkable; they do not become register-class by virtue of the
split alone.

## Why (the Phase-0 findings this encodes)
- Each full-DB copy freezes the complete PII set at copy time — emails, bcrypt hashes,
  live-at-copy-time session/share/invite tokens, real organisation names. Deleting or rotating in the
  live DB removes nothing from a copy.
- On 2026-07-30, 87 unmanaged copies (7.56 GB, 2026-06-13→07-29) were deleted by ruled, named-file
  execution — ground: **exposure-reduction** (all 87 contained real-pattern rows; the live DB retains
  every such row; nothing unique was lost). The retained set: the 3 most recent pre-diff backups + the
  register `.bak` + 2 sidecars, verified intact by hash.
- Historical one-shot scripts contain restore-instruction strings naming now-deleted backups (e.g.
  `reseed_engine.py:553`, `verify_diff7.py:17`); **the retained set is the only restore surface.**

Note, recorded at the Phase-1 split: rotation in the live identity store
(sessions, tokens — the most rotation-heavy data the platform holds)
removes nothing from identity-store backup copies. Data rotated out of
production persists in every copy taken before the rotation. This was a
Phase-0 finding; after the split it concentrates in the family where it
bites hardest.

## Enforcement
Discipline-only until Phase 1: the backup-creating step (migration scripts, `wal_checkpoint` + copy
ritual) gains a policy hook in the Phase-1 spec. This file is the ruled text those tools must encode.

---

## Dated correction — 2026-08-03 (PH-BAK-1, ruled by David)

**What the scope was, and why it was wrong.** The original ruling scoped
"Scratch/throwaway copies (session scratchpads)" as *"outside this policy today;
in scope for the Phase 3–4 deletion-on-exit design."* That carve-out was the
defect: the PH-BAK-1 census found every unmanaged identity-bearing copy living
precisely there — three pre-split gate throwaways with full identity data (223
org names, 8 emails, 8 pw_hash each) surviving four days in /tmp because
run_gates deleted its identity throwaway at teardown but never its reward one,
plus session-scratchpad identity copies. The governed .bak ritual, meanwhile,
was being followed exactly. The gap was the scope line, not the discipline.

**Amended scope, effective immediately:**

1. **Scratch and throwaway copies are IN scope.**
2. **No copy of the identity store persists beyond the process that created it.**
3. **Reward-store throwaways are deleted at teardown by the tooling that creates
   them** — run_gates.sh deletes `lumi_qa.db` (+sidecars) on the same EXIT-trap
   path as the identity throwaway, and asserts ZERO database copies survive in
   the workdir (a count, not a named-file check). Ad-hoc session copies are swept
   by `server/purge_throwaway_copies.py` (dry-run default, double-guarded), which
   is structurally unable to touch Group A or the live stores.

This correction is recorded as such, dated, with the prior text left standing
above — the gap is the finding, and a policy whose history is quietly rewritten
stops being evidence of anything.

---

## Amendment 2026-08-08 — R5 ceiling-binds, and the three production layers (Master Ruling Transmission, Commit F)

### R5: `BACKUP_RETENTION = CEILING_BINDS`, ceiling **35 days**

The ceiling BINDS; the count is a FLOOR beneath it. Concretely: a DB-class pre-diff
backup older than 35 days is deleted **even if that takes the set below 3** —
because a count says nothing about age: if migrations pause, three copies can be
seven months old and the member-facing retention disclosure is broken with no error
anywhere. Ceiling-binds fails safe; rotation-binds fails open (rejected, recorded in
DECISIONS 2026-08-08). Every retention mechanism in this file — DB class, identity
class, journald caps, the off-box bucket — carries the same 35-day ceiling. The
combined member-facing outer bound is computed in the Phase-4 spec (grace 30d +
ceiling 35d → the honest external statement is "90 days, with slack") and is C2
solicitor material.

### The three production backup layers — distinct purposes, never conflated

Conflating layers is how an estate ends up with 1,058 files and no restore (the
census-scoping lesson). On the deployed instance (deploy/DEPLOY_RUNBOOK.md):

1. **DLM daily EBS snapshots — machine-level restore.** Whole-volume, for "the
   instance died". NOT a data backup: restoring one resurrects every file on the
   box, so its retention is ALSO capped at 35 days (the DLM policy's own setting)
   or the ceiling silently breaks through the snapshot layer.
2. **On-box rotation (`server/backup_identity.py`) — operational restore.** WHICH
   CASE OBTAINS: the script already runs `PRAGMA wal_checkpoint(TRUNCATE)` first
   (line 112) and copies via the SQLite backup API, never cp — the layer-2
   requirement was already met as shipped; recorded here so a rewrite that drops
   the checkpoint fails review against this sentence.
3. **Off-box S3 copy (`deploy/offbox_backup.sh`) — the copy you actually restore
   DATA from (R1e, Gate 1).** eu-west-2, SSE, block-public-access, versioned.
   **THE VERSIONED-BUCKET TRAP, closed by rule:** a versioned bucket retains
   deleted and overwritten objects as noncurrent versions unless noncurrent-version
   expiration is ALSO configured. BOTH rules — current-version lifecycle expiry AND
   noncurrent-version expiration — must equal the 35-day ceiling, or the off-box
   copy silently defeats ceiling-binds and the retention disclosure becomes false.
   The backup script ASSERTS both rules exist before every upload and refuses to
   copy if either is missing (fail closed, not fail open).

### PH-LOG-1 containment on the deployed box (A4 ruling)

App logs (journald) carry auth links until D2 lands. Containment, unconditional:
journald retention capped at **35 days / 200M** (`MaxRetentionSec=35day`,
`SystemMaxUse=200M`), root-readable only, outside every web-served path, and
**excluded from every backup that leaves the box** — offbox_backup.sh copies the
two databases only, never logs; the DLM snapshot layer is machine-restore scope and
its 35-day cap bounds the residual copy of the journal it necessarily contains.
D2 (SES delivery) is a HARD PRECONDITION of first provisioning (A4), not merely
PH-LOG-1's close condition.
