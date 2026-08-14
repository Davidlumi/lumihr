#!/usr/bin/env python3
"""V2-G seed-realism — anchored sector-strength reallocations (2026-08-14, persona QA follow-up).

The V2-F remainder: sector strengths that live on FROZEN or REGISTER-MARGINAL metrics, so they can
only be REALLOCATED per sector (hold the global count exactly), never freely raised — the OT_04/B4
pattern. Each fix flips k orgs NEG->POS in the sector that should be strong and k orgs POS->NEG in an
over-represented/less-critical sector, so the frozen/register global is conserved to the org.

All seven are frozen or Diff-3 register marginals, hence value-diff-skipped by qa_engine_audit L1 ->
DB-only edits (no response-CSV lockstep).

  1. REW26_WEL_EAP (frozen):        Construction up (industry MH drive) <- Media/Tech/ProfSvc SMEs.
  2. REW26_BEN_SALSAC (frozen):     Public-Sector DB orgs can't salary-sacrifice main DB contribs ->
                                    down; Manufacturing/Retail (DC) up.
  3. REW263_WEL_OH (marginal):      Construction occupational health up (statutory surveillance) <-
                                    Media/Tech/FS SMEs.
  4. PAYTR_01/PAYTR_02 (marginal):  Charity + Public-Sector pay transparency up <- Energy/Tech/HC.
  5. REW_BEN_FAM_010 (marginal):    Charity volunteering leave up <- Tech/Healthcare.

STILL DEFERRED (need more than a plain swap):
  * REW_BEN_SICK_001 — its OSP-detail children (SICK_002 duration / SICK_004 waiting / SICK_005
    eligibility) are coherence-conditioned on OSP existing, so a swap must CASCADE the children
    (set substantive on raise, "Not applicable" on lower) — a B4-style bundle move, not this batch.
  * REW_PAY_001 — it is HR_Maturity-KEYED (a gradient), so it must be reallocated within maturity
    bands, not sectors, or the per-band keyed anchor drifts.

LUMI_DB-aware. Dry-run default; --write --confirmed-by-david. Deterministic. Re-records book_baseline.
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SME = ("50-249", "250-999")
BIGFIRST = ("10,000+", "5,000-9,999", "1,000-4,999")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    pt = {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW26_BEN_PENSION_TYPE' AND matrix_row_id='' AND snapshot_id=1")}
    changes = defaultdict(int)
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)

    def rows(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (org, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, org, q))

    def reallocate(q, pos_val, neg_val, raise_sel, lower_sel, cap, bigfirst_raise=False):
        """Flip k NEG->POS (raise sector) and k POS->NEG (donor); k conserves the global count."""
        d = rows(q)
        raise_orgs = [o for o in d if o in ind and raise_sel(o, d[o])]
        lower_orgs = [o for o in d if o in ind and lower_sel(o, d[o])]
        raise_orgs.sort(key=lambda o: (0 if fte.get(o) in BIGFIRST else 1, o) if bigfirst_raise else (o,))
        lower_orgs.sort()
        k = min(len(raise_orgs), len(lower_orgs), cap)
        for o in raise_orgs[:k]: setv(q, o, pos_val)
        for o in lower_orgs[:k]: setv(q, o, neg_val)
        return k

    ENH = ("Combination of enhanced sick pay and SSP", "Enhanced occupational sick pay (above SSP)")
    FAM_POS = ("Unpaid leave only", "Yes - paid leave is provided")
    plan = [
        # 1) EAP: Construction up <- Media/Tech/ProfSvc SMEs
        ("REW26_WEL_EAP", "Yes", "No",
         lambda o, v: inS(o, "Construction") and v == "No",
         lambda o, v: inS(o, "Media", "Technology", "Professional Services") and v == "Yes" and fte.get(o) in SME, 12, True),
        # 2) SALSAC: PubSec-DB down, Manufacturing/Retail up
        ("REW26_BEN_SALSAC", "Yes", "No",
         lambda o, v: inS(o, "Manufacturing", "Retail") and v == "No",
         lambda o, v: inS(o, "Public Sector") and v == "Yes" and pt.get(o) == "DB", 10, False),
        # 4) OH: Construction up <- Media/Tech/FS SMEs
        ("REW263_WEL_OH", "OH without SLA", "No OH service",
         lambda o, v: inS(o, "Construction") and v == "No OH service",
         lambda o, v: inS(o, "Media", "Technology", "Financial Services") and v != "No OH service" and fte.get(o) in SME, 6, False),
        # 5) PAYTR_01 / PAYTR_02: Charity + PubSec up <- Energy/Tech/Healthcare
        ("PAYTR_01_42eae7ec", "Yes", "No",
         lambda o, v: inS(o, "Charity", "Public Sector") and v == "No",
         lambda o, v: inS(o, "Energy", "Technology", "Healthcare") and v == "Yes", 8, False),
        ("PAYTR_02_131bd412", "Yes", "No",
         lambda o, v: inS(o, "Charity", "Public Sector") and v == "No",
         lambda o, v: inS(o, "Energy", "Technology", "Healthcare") and v == "Yes", 8, False),
        # 7) volunteering leave: Charity up <- Tech/Healthcare
        ("REW_BEN_FAM_010", "Unpaid leave only", "No specific provision",
         lambda o, v: inS(o, "Charity") and v == "No specific provision",
         lambda o, v: inS(o, "Technology", "Healthcare") and v in FAM_POS, 5, False),
    ]
    ks = {}
    for (q, pv, nv, rs, ls, cap, bf) in plan:
        ks[q] = reallocate(q, pv, nv, rs, ls, cap, bf)

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — pairs swapped per metric: " + str(ks))
    print("  cell changes: " + str(dict(changes)))
    # global-conservation proof
    for q in ("REW26_WEL_EAP", "REW26_BEN_SALSAC"):
        print("  %s global (frozen — must be unchanged): %s" % (q, dict(Counter(rows(q).values()))))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
