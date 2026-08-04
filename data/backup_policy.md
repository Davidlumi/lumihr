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

### Named exception: the pre-split backup pin

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
