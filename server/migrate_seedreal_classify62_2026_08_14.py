#!/usr/bin/env python3
"""Seed-realism — classify the 62 file-only ("Unclassified") seed orgs (2026-08-14, David).

Background: the seed registry-join left 158 orgs matched (firmographics known → classified) and
62 "file-only" — full answer sets (~403 each, submission_complete=1) but NO registry match, so
their industry/sector/FTE were unknown and they appeared in "All peers" ONLY, never in a sector or
size cut (`build_cuts` includes classified orgs only). David wants all 220 to carry a complete
profile so they show up in sector/size sample searches.

Method — CLONE, don't invent: each unclassified org copies the full firmographic tuple
(industry, subsector, fte_band, hq_region) of a REAL classified org, so the joint distribution
(industry↔size↔subsector↔region correlations) is preserved exactly and no combination is fabricated
that doesn't already exist in the pool. Template = a classified org OF THE SAME INDUSTRY where one
exists; the 3 "Other" orgs (no classified match) clone any classified org, taking its industry too.
Deterministic pick by sha256(org_id). Only the four firmographic columns + classified flag change;
answers, name, submission_complete, everything else is left untouched.

After --write, re-aggregate so the cuts pick up the newly-classified orgs:
    python3 -c "import sys; sys.path.insert(0,'server'); from aggregate import run_snapshot; run_snapshot(1)"

    python3 server/migrate_seedreal_classify62_2026_08_14.py                          # dry run
    python3 server/migrate_seedreal_classify62_2026_08_14.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from collections import Counter, defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def pick(seq, key):
    """Deterministic index into a sorted sequence from the org id."""
    h = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    return seq[h % len(seq)]


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    # templates: every distinct classified firmographic tuple, grouped by industry + a global list
    templates = [dict(r) for r in c.execute(
        "SELECT industry, subsector, fte_band, hq_region FROM orgs "
        "WHERE classified=1 AND industry IS NOT NULL AND fte_band IS NOT NULL")]
    by_ind = defaultdict(list)
    for t in templates:
        by_ind[t["industry"]].append(t)
    # deterministic order for reproducible picks
    for k in by_ind:
        by_ind[k].sort(key=lambda t: (t["subsector"] or "", t["fte_band"] or "", t["hq_region"] or ""))
    all_sorted = sorted(templates, key=lambda t: (t["industry"], t["subsector"] or "", t["fte_band"] or "", t["hq_region"] or ""))

    targets = list(c.execute(
        "SELECT org_id, industry FROM orgs WHERE classified=0 AND source='seed'"))
    before_ind = Counter(t["industry"] or "—" for t in targets)

    applied, reassigned_other = 0, 0
    after_ind, after_fte = Counter(), Counter()
    samples = []
    for r in targets:
        oid, ind = r["org_id"], r["industry"]
        pool = by_ind.get(ind)
        cross = False
        if not pool:                      # 'Other' / unmatched industry → clone any classified org
            pool = all_sorted
            cross = True
        t = pick(pool, oid)
        new_ind = t["industry"] if cross else ind
        if cross:
            reassigned_other += 1
        after_ind[new_ind] += 1
        after_fte[t["fte_band"]] += 1
        if len(samples) < 8:
            samples.append((oid[:8], new_ind, t["subsector"], t["fte_band"], t["hq_region"]))
        if WRITE:
            c.execute("UPDATE orgs SET industry=?, subsector=?, fte_band=?, hq_region=?, classified=1 "
                      "WHERE org_id=?", (new_ind, t["subsector"], t["fte_band"], t["hq_region"], oid))
        applied += 1
    if WRITE:
        c.commit()

    print(("APPLIED" if WRITE else "DRY RUN") + " — classified %d file-only seed orgs "
          "(%d 'Other' reassigned to a real sector)" % (applied, reassigned_other))
    print("  sample:")
    for s in samples:
        print("    %s  %s · %s · %s · %s" % s)
    print("  NEW sector spread (these 62):")
    for ind, n in after_ind.most_common():
        print("    %-45s +%d" % (ind, n))
    print("  NEW fte-band spread (these 62): " + ", ".join("%s=%d" % (b, n) for b, n in sorted(after_fte.items())))
    # sanity: classified count after
    tot = c.execute("SELECT COUNT(*) FROM orgs WHERE classified=1").fetchone()[0]
    still = c.execute("SELECT COUNT(*) FROM orgs WHERE classified=0").fetchone()[0]
    print("  classified now: %d  (unclassified remaining: %d)%s" % (
        tot, still, "" if WRITE else "  [dry run — no change written]"))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
