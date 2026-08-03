# -*- coding: utf-8 -*-
"""The seed cohort (D4), defined POSITIVELY — the one place nine scripts now share.

Nine root-level scripts used to build their cohort by excluding "the org named
'Tester'". Step 5 emptied `orgs.name`, so that exclusion stopped working: six
sites fired a `len == 220` assert, three went silent and let the Tester pollute
their downstream maths.

The cohort is defined here as **answer-bearing orgs with `orgs.source = 'seed'`**
rather than "everything except Tester". Measured equal to the old definition at
three independent points in time (the live store, the pre-step-5 backup, and the
30-July pre-split pin): 220 both ways, with no org in either difference.

Why this rather than a pinned org_id:
  * structural, not incidental — `seed_import.py` hardcodes source='seed' for every
    org it writes, and nothing in the tree ever UPDATEs `orgs.source`
  * survives a reseed and a fresh install; a pinned UUID would need updating in
    both cases, and would leave these nine scripts refusing until someone did
  * the Tester org is source='signup' (minted through /api/auth/register), so a
    reseed does not recreate it and cannot renumber it into the cohort
  * it is what the code already meant: dryrun_2026_4 prints "seed cohort (D4)"
  * it stays correct when real member orgs start submitting — those are
    source='signup' and must not enter a cohort the callers assert is 220

The query deliberately mirrors the shape it replaces — the same outer
`SELECT DISTINCT org_id FROM answers` with the predicate swapped — so row order is
unchanged from the original.
"""


def seed_cohort(conn, snapshot_id=1):
    """org_ids of the seed cohort for one snapshot, in the original row order."""
    seed = {r[0] for r in conn.execute(
        "SELECT org_id FROM orgs WHERE source = 'seed'")}
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT org_id FROM answers WHERE snapshot_id = ?",
        (snapshot_id,)) if r[0] in seed]
