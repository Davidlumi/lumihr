#!/usr/bin/env python3
"""Batch 2d — EDI/transparency sector leadership + construction allowances (2026-08-14, review).

Deferred sector-signature items from Batch 2:
  - REW262_GOV_EQUALPAYAUDIT (equal-pay audits): values-led / statutory-transparency sectors (Charity,
    Public, Education) should LEAD proactive equal-pay auditing; private prestige (FS/ProfSvc/Tech) is
    not where voluntary EDI auditing concentrates. Register marginal -> count-conserving swap. [DB-only]
  - PROP_930043cc (ethnicity pay-gap analysis) & PROP_10d1211d (disability pay-gap analysis): same
    signature — Charity/Public lead voluntary pay-gap analytics. Register marginals -> conserving
    swaps (No <-> Partially, holding the No count). [CSV lockstep]
  - ALLOW_01 (allowances offered, multi-select): Construction & Logistics field workforces carry CIJC
    travel-time + subsistence (meal) allowances that office sectors don't -> append the Travel/Meal
    tokens where missing. Free but CSV-lineage-locked (ALLOW_*) -> DB+CSV. [not token-incidence anchored]

All four are leaves (no coherence child). The three EDI metrics conserve their register marginal to
the org; ALLOW_01 is unanchored.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG = ("10,000+", "5,000-9,999", "1,000-4,999", "250-999")
DBO = {"REW262_GOV_EQUALPAYAUDIT"}   # DB-origin; PROP_* and ALLOW_* are CSV-locked


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_set(o, q, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]; qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (r[mi] or "") == "":
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int); csv_rows = [0]
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
            if q not in DBO: csv_rows[0] += csv_set(o, q, new)

    def reallocate(q, pos, neg, raise_sel, lower_sel, cap):
        d = rows(q)
        raise_orgs = sorted((o for o in d if o in ind and raise_sel(o, d[o])), key=lambda o: (0 if fte.get(o) in BIG else 1, o))
        lower_orgs = sorted(o for o in d if o in ind and lower_sel(o, d[o]))
        k = min(len(raise_orgs), len(lower_orgs), cap)
        for o in raise_orgs[:k]: setv(q, o, pos)
        for o in lower_orgs[:k]: setv(q, o, neg)
        return k

    ks = {}
    # 1) equal-pay audits: Charity/Public/Education lead <- FS/ProfSvc/Tech
    ks["EQPAY"] = reallocate("REW262_GOV_EQUALPAYAUDIT", "Annually", "No",
        lambda o, v: inS(o, "Charity", "Public Sector", "Education") and v == "No",
        lambda o, v: inS(o, "Financial Services", "Professional Services", "Technology") and v in ("Annually", "More than annually"), 8)
    # 2) ethnicity pay-gap analysis: Charity/Public lead <- Tech/FS
    ks["ETHPG"] = reallocate("PROP_930043cc", "Partially", "No",
        lambda o, v: inS(o, "Charity", "Public Sector", "Education") and v == "No",
        lambda o, v: inS(o, "Technology", "Financial Services", "Manufacturing") and v in ("Partially", "Yes"), 6)
    # 3) disability pay-gap analysis: Charity/Public lead <- Tech/FS
    ks["DISPG"] = reallocate("PROP_10d1211d", "Partially", "No",
        lambda o, v: inS(o, "Charity", "Public Sector", "Education") and v == "No",
        lambda o, v: inS(o, "Technology", "Financial Services", "Manufacturing") and v in ("Partially", "Yes"), 6)

    # 4) ALLOW_01: append CIJC travel + subsistence to field-workforce sectors missing them
    d = rows("ALLOW_01")
    for tok in ("Travel allowance", "Meal allowance"):
        cands = sorted((o for o, v in d.items() if o in ind and inS(o, "Construction", "Logistics")
                        and tok not in (t.strip() for t in v.split(";")) and "None" not in v),
                       key=lambda o: (0 if fte.get(o) in BIG else 1, o))
        take = 10 if tok == "Travel allowance" else 6
        for o in cands[:take]:
            newv = d[o] + "; " + tok
            setv("ALLOW_01", o, newv); d[o] = newv
    ks["ALLOW_travel/meal"] = "appended"

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — pairs/moves: " + str(ks))
    print("  cell changes: " + str(dict(changes)) + " | CSV rows: %d" % csv_rows[0])
    for q in ("REW262_GOV_EQUALPAYAUDIT", "PROP_930043cc", "PROP_10d1211d"):
        nd = rows(q); print("  %s No-count: %d/%d (marginal hold)" % (q[:24], sum(1 for v in nd.values() if v == "No"), len(nd)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
