#!/usr/bin/env python3
"""Batch 2b — "sector should lead" raises on ANCHORED (register-marginal) metrics (2026-08-14).

Same intent as 2a but on register marginals, so done as count-conserving per-sector swaps (flip k
neg->pos in the sector that should lead, k pos->neg in an over-represented one; the global marginal
holds to the org). DB-origin -> DB-only.

  - REW26_WEL_SCREENING (health assessments): up in physical sectors (Construction/Logistics/
    Manufacturing — statutory HAVS/noise/dust/D4 surveillance) <- office sectors (Tech/FS/ProfSvc).
  - REW262_GOV_PAYINADVERTS (salary in adverts): up in Public/Charity + frontline (advertise the rate)
    <- private prestige (FS/ProfSvc rarely publish exact pay).
  - REW_INC_072 (sign-on bonuses): up in Logistics (HGV/warehouse shortage) <- a sector that wouldn't.
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG = ("10,000+", "5,000-9,999", "1,000-4,999")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int)
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)

    def rows(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (new, o, q))

    def reallocate(q, pos, neg, raise_sel, lower_sel, cap):
        d = rows(q)
        raise_orgs = sorted((o for o in d if o in ind and raise_sel(o, d[o])), key=lambda o: (0 if fte.get(o) in BIG else 1, o))
        lower_orgs = sorted(o for o in d if o in ind and lower_sel(o, d[o]))
        k = min(len(raise_orgs), len(lower_orgs), cap)
        for o in raise_orgs[:k]: setv(q, o, pos)
        for o in lower_orgs[:k]: setv(q, o, neg)
        return k

    ks = {}
    ks["SCREEN"] = reallocate("REW26_WEL_SCREENING", "Yes", "No",
        lambda o, v: inS(o, "Construction", "Logistics", "Manufacturing", "Energy") and v == "No",
        lambda o, v: inS(o, "Technology", "Financial Services", "Professional Services", "Media") and v == "Yes", 12)
    ks["PAYADV"] = reallocate("REW262_GOV_PAYINADVERTS", "Some roles", "Never",
        lambda o, v: inS(o, "Public Sector", "Charity", "Retail", "Hospitality") and v == "Never",
        lambda o, v: inS(o, "Financial Services", "Professional Services", "Technology") and v in ("Some roles", "All roles"), 8)
    ks["SIGNON"] = reallocate("REW_INC_072", "Used for specific hard-to-fill roles", "Not used",
        lambda o, v: inS(o, "Logistics") and v == "Not used",
        lambda o, v: inS(o, "Public Sector", "Charity", "Education") and v != "Not used", 6)

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — pairs: " + str(ks) + " | cell changes: " + str(dict(changes)))
    for q in ("REW26_WEL_SCREENING", "REW262_GOV_PAYINADVERTS", "REW_INC_072"):
        print("  %s global: %s" % (q[:24], dict(Counter(rows(q).values()))))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
