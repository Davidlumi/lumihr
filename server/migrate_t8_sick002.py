# -*- coding: utf-8 -*-
"""migrate_t8_sick002.py — Phase 2 · T8 STEP 1: the SICK_002 draw (SEED-DATA class; David-ruled
2026-07-30, "repair the 41 to a duration, drawn from the 71-org donor shape, completing M1's direction").

Closes the 89 flags M1 left, all on REW_BEN_SICK_002 (the r3sw25 chain, DECISIONS 8885):
  A  48 no-OSP orgs stating an enhanced-pay DURATION  -> 'None (statutory only)'
  C  41 OSP-holders stating 'None (statutory only)'   -> a DURATION, drawn from the book

THE FORK, RULED. "None" on an OSP-holder is either a contradiction to repair or evidence the PARENT
is wrong. Reading (ii) is REFUTED on the seed's own routing: REW_BEN_SICK_005 (eligibility rules,
conditioned on OSP-holders and never touched by M1) is answered by 36/41 = 88% of the contradictors
and 67/71 = 94% of coherent OSP-holders, but by 0 of 90 no-OSP orgs. Were SICK_001 wrong these orgs
should pattern with the no-OSP group; they do not. The 3 orgs M1 never touched corroborate
independently (two answer SICK_005 'Partly'; all three claim Enhanced/Combination).

THE CAVEAT, RECORDED VERBATIM AS RULED: two metrics have now moved on 38 orgs on the strength of ONE
parent answer corroborated only by SICK_005; all evidence is INTERNAL TO THE SEED. **This is a seed
self-consistency repair, not an external-truth repair.** Pre-M1 the record on those 38 was split 2-2
(SICK_001 + SICK_005 said OSP; SICK_002 + SICK_004 said not) and M1 broke the tie toward SICK_001;
this diff completes that direction rather than opening a fresh one.

THE DESTINATIONS ARE BOOK-DERIVED, not legislated (batch-6 native-texture doctrine). Donor = the 71
COHERENT verified OSP-holders: 13-26 weeks 28 (39.4%) / 5-12 weeks 22 (31.0%) / Up to 4 weeks 16
(22.5%) / More than 26 weeks 5 (7.0%). Largest-remainder over 41 -> 16 / 13 / 9 / 3. The shape is
healthy (no degenerate rung), so there is no implausibility to record — unlike M1's '>3 days = 1 org'.
Assignment is DETERMINISTIC: orgs sorted by sha256(org_id) and dealt to rungs in a fixed order.

SICK_001 is NOT TOUCHED (T7 ruled aligned, +0.14pp, no action). SICK_004 is NOT TOUCHED (M1 is closed).

Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
S1, S2 = "REW_BEN_SICK_001", "REW_BEN_SICK_002"
NOOSP = {"Statutory sick pay only", "No sick pay provided"}
NONE = "None (statutory only)"
# rung order is FIXED (ladder order, shortest -> longest) so the deal is reproducible
RUNGS = ["Up to 4 weeks", "5-12 weeks", "13-26 weeks", "More than 26 weeks"]


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def answers(c, qid):
    return {o: v for o, v in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND snapshot_id=1 AND matrix_row_id='' "
        "AND value!=''", (qid,))}


def largest_remainder(donor, n):
    """Allocate n across RUNGS in the donor's proportions; ties broken by the fixed rung order."""
    tot = sum(donor.values())
    exact = {r: donor.get(r, 0) / tot * n for r in RUNGS}
    out = {r: int(exact[r]) for r in RUNGS}
    for r in sorted(RUNGS, key=lambda k: (-(exact[k] - int(exact[k])), RUNGS.index(k)))[:n - sum(out.values())]:
        out[r] += 1
    assert sum(out.values()) == n, (out, n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    s1, s2 = answers(c, S1), answers(c, S2)
    osp = {o for o, v in s1.items() if v not in NOOSP}
    noosp = {o for o, v in s1.items() if v in NOOSP}

    # ---- PRE-STATE FINGERPRINTS (batch-6 discipline, permanent) ----
    assert len(s1) == 209 and len(s2) == 205, ("pre-state drift", len(s1), len(s2))
    assert len(osp) == 119 and len(noosp) == 90, ("OSP partition drift", len(osp), len(noosp))
    d2 = {}
    for v in s2.values():
        d2[v] = d2.get(v, 0) + 1
    assert d2 == {NONE: 79, "13-26 weeks": 41, "5-12 weeks": 38, "Up to 4 weeks": 37,
                  "More than 26 weeks": 10}, ("SICK_002 pre-dist drift", d2)

    A = sorted(o for o in noosp if s2.get(o) and s2[o] != NONE)
    C = sorted(o for o in osp if s2.get(o) == NONE)
    assert len(A) == 48 and len(C) == 41, ("repair-set drift", len(A), len(C))

    donor = {}
    for o in osp:
        if o in s2 and s2[o] != NONE:
            donor[s2[o]] = donor.get(s2[o], 0) + 1
    assert sum(donor.values()) == 71, ("donor drift", donor)
    assert donor == {"13-26 weeks": 28, "5-12 weeks": 22, "Up to 4 weeks": 16,
                     "More than 26 weeks": 5}, ("DONOR SHAPE CHANGED — the draw is book-derived", donor)
    quota = largest_remainder(donor, len(C))
    assert quota == {"Up to 4 weeks": 9, "5-12 weeks": 13, "13-26 weeks": 16,
                     "More than 26 weeks": 3}, ("quota drift", quota)

    # deterministic deal: stable hash order, rungs in fixed ladder order
    ordered = sorted(C, key=lambda o: hashlib.sha256(o.encode()).hexdigest())
    plan, i = {}, 0
    for r in RUNGS:
        for o in ordered[i:i + quota[r]]:
            plan[o] = r
        i += quota[r]
    assert len(plan) == len(C) and i == len(C)

    print("T8 SICK_002 %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  A  %d no-OSP stating a duration      -> %r" % (len(A), NONE))
    print("  C  %d OSP-holders on %r -> a duration, book-drawn" % (len(C), NONE))
    print("     donor (71 coherent OSP-holders): %s" % donor)
    print("     largest-remainder quota over 41: %s" % quota)
    print("  total answer writes: %d" % (len(A) + len(C)))
    for pre in ("5e67fa8c", "833beedb"):
        for o in list(A) + list(C):
            if o.startswith(pre):
                print("  FIXTURE %s: SICK_001=%r  SICK_002 %r -> %r  [ruled coherence correction, "
                      "Diff-19b/M1 precedent]" % (pre, s1[o], s2[o], NONE if o in A else plan[o]))

    post = dict(s2)
    for o in A:
        post[o] = NONE
    for o in C:
        post[o] = plan[o]
    dpost = {}
    for v in post.values():
        dpost[v] = dpost.get(v, 0) + 1
    print("  POST-REPAIR SICK_002 distribution: %s" % dpost)
    cond = {o: post[o] for o in post if o in osp}
    dc = {}
    for v in cond.values():
        dc[v] = dc.get(v, 0) + 1
    print("  over the OSP-CONDITIONED base (n=%d): %s" % (len(cond), dc))
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for o in A:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND snapshot_id=1 "
                    "AND matrix_row_id=''", (NONE, S2, o))
    for o, r in plan.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND snapshot_id=1 "
                    "AND matrix_row_id=''", (r, S2, o))
    # ---- POST-WRITE ASSERTS ----
    assert answers(c, S1) == s1, "SICK_001 MOVED — it is ruled untouched (T7 aligned, no action)"
    s4 = answers(c, "REW_BEN_SICK_004")
    assert len(s4) == 204, "SICK_004 row count moved — M1 is closed, this diff does not touch it"
    s2b = answers(c, S2)
    assert s2b == post, "post-state does not match the projection"
    assert len(s2b) == len(s2), "SICK_002 answer count changed — this diff re-values, never adds or drops"
    assert sum(1 for o in osp if s2b.get(o) == NONE) == 0, "an OSP-holder still states None"
    assert sum(1 for o in noosp if s2b.get(o) and s2b[o] != NONE) == 0, "a no-OSP org still states a duration"
    n_changed = sum(1 for o in s2 if s2[o] != s2b[o])
    assert n_changed == len(A) + len(C), ("changed-count mismatch", n_changed)
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "writes": n_changed,
                      "A_to_none": len(A), "C_drawn": quota, "post_dist": dpost,
                      "book_before": pre_book[:16], "book_after": book_hash(c)[:16]}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
