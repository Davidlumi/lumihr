#!/usr/bin/env python3
"""Seed-realism correction #2 (widen sweep, 2026-08-10).

The widen pass over benefit metrics found one further sector-fit defect: orgs in
NON-PROFIT / public-money sectors (Public Sector, Charity, Education) answering
REW265_INC_PROFITSHARE = 'Profit share — all-employee'. Those bodies have no
profits to share, so 'profit share' is implausible there. Set them to 'No'.
'Gainshare (site or team)' is LEFT untouched — team efficiency-sharing is
defensible in public/charity bodies and isn't profit-dependent.

REW265_INC_PROFITSHARE is not a marginal, not a ruled distribution, and has no
coherence pair (verified), so this is a free, side-effect-free correction.
Everything else in the widen sweep (by-level bonus/LTI/pension/PMI/car-allowance
gradients, board bonus presence, share plans, recognition budgets) was clean.

    python3 server/migrate_seedreal_profitshare_2026_08_10.py                       # dry run
    python3 server/migrate_seedreal_profitshare_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW265_INC_PROFITSHARE"
BAD = "Profit share — all-employee"
NON_PROFIT = ("Public Sector", "Charity", "Education")   # substring match on industry


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = []
    for a in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (Q,)):
        sec = ind.get(a["org_id"], "")
        if a["value"] == BAD and any(n in str(sec) for n in NON_PROFIT):
            changes.append((a["org_id"], sec))
            if WRITE:
                c.execute("UPDATE answers SET value='No' WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                          (a["org_id"], Q))
    if WRITE: c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d profit-share -> No in non-profit sectors" % len(changes))
    from collections import Counter
    print("  by sector:", dict(Counter(s for _, s in changes)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
