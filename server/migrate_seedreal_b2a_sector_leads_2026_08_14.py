#!/usr/bin/env python3
"""Batch 2a — "sector should LEAD its signature lever" raises, free/DB-origin (2026-08-14, review).

Each sector was seeded at/below the pool on a practice it should lead. All metrics here are unanchored
and DB-origin (value-diff-skipped -> DB-only, no conservation): raise the sector by converting orgs
from the floor value to the signature value. Grounded in external 2026 UK sources (Make UK, CITB,
Mates in Mind, RHA/Logistics UK, UKHospitality, BRC, CAF payroll giving).

  - REW265_PAY_EARLYCAREER: Manufacturing/Construction are the apprenticeship heartland; "no apprentices"
    is impossible at 250+ FTE -> structured framework.
  - REW265_INC_PROFITSHARE: production gainshare is a Manufacturing/Construction signature.
  - REW265_INC_ESGINCENT: safety/ESG measures in incentives for safety-critical Mfg/Construction/Energy.
  - REW263_WEL_MGRTRAIN: Construction's Mates-in-Mind MH manager-training drive.
  - REW265_INC_RETENTION: Logistics HGV/warehouse retention pressure.
  - REW265_PAY_SEASONAL: Retail/Hospitality/Logistics peak-season completion/premium pay.
  - REW264_PEN_PAYROLLGIVING: Charity's signature values-led benefit (Give As You Earn).
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG = ("10,000+", "5,000-9,999", "1,000-4,999", "250-999")

# (metric, sectors, [(from_value, to_value, count, large_first), ...])
PLAN = [
    ("REW265_PAY_EARLYCAREER", ("Manufacturing", "Construction"), [
        ("Not applicable (no apprentices or graduates)", "Yes — structured framework", 14, True),
        ("Ad hoc", "Yes — structured framework", 6, True)]),
    ("REW265_INC_PROFITSHARE", ("Manufacturing", "Construction"), [
        ("No", "Gainshare (site or team)", 10, True)]),
    ("REW265_INC_ESGINCENT", ("Manufacturing", "Construction", "Energy"), [
        ("No", "Yes — modifier or underpin", 14, True),
        ("No", "Yes — weighted measures", 6, True)]),
    ("REW263_WEL_MGRTRAIN", ("Construction",), [
        ("None", "Under 25%", 6, True), ("None", "25-75%", 4, True)]),
    ("REW265_INC_RETENTION", ("Logistics",), [
        ("No", "Case-by-case", 8, True), ("No", "Formal framework", 4, True)]),
    ("REW265_PAY_SEASONAL", ("Retail", "Hospitality", "Logistics"), [
        ("Neither", "Completion bonus", 18, True), ("Neither", "Peak premium", 12, False)]),
    ("REW264_PEN_PAYROLLGIVING", ("Charity",), [
        ("No", "Yes with employer match", 3, False), ("No", "Yes unmatched", 1, False)]),
]


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int)
    inS = lambda o, secs: any(s in str(ind.get(o, "")) for s in secs)

    def rows(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (new, o, q))

    for q, secs, repls in PLAN:
        d = rows(q)
        for (frm, to, cnt, large_first) in repls:
            cands = [o for o, v in d.items() if o in ind and inS(o, secs) and v == frm]
            cands.sort(key=lambda o: ((0 if fte.get(o) in BIG else 1) if large_first else 0, o))
            for o in cands[:cnt]:
                setv(q, o, to); d[o] = to   # mark consumed so a later repl on same 'from' won't re-pick

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
