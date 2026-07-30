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

## Enforcement
Discipline-only until Phase 1: the backup-creating step (migration scripts, `wal_checkpoint` + copy
ritual) gains a policy hook in the Phase-1 spec. This file is the ruled text those tools must encode.
