#!/usr/bin/env python3
"""V2-J seed-realism — enhanced-maternity generous tail (2026-08-14, David spotted it).

REW_BEN_FAM_002 ("weeks of enhanced maternity/adoption pay") had its top two tiers EMPTY — 0 orgs at
27-39 weeks and 0 at 40-52 weeks — which is implausible: generous employers (Financial Services, Tech,
big corporates) genuinely offer 6-12 months' enhanced pay. The metric is a REGISTER MARGINAL, but the
marginal only pins the "offers ANY enhanced" share (~66% = not "None (statutory only)"). The spread
ACROSS the enhanced tiers is unanchored, so we can add a realistic top tail WITHOUT moving the marginal:
promote generous-sector / large orgs from "13-26 weeks" up to "27-39 weeks" (12) and "40-52 weeks" (18).
"None" is never touched -> the not-None share (the anchor) is held to the org. DB-only (Diff-3 skipped).

    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW_BEN_FAM_002"
BIG = ("10,000+", "5,000-9,999", "1,000-4,999")
N_FULLYEAR = 12   # -> 40-52 weeks (very generous: FS/Tech)
N_NINEMO = 18     # -> 27-39 weeks (generous: FS/Tech/ProfSvc/Healthcare/Media)


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = [0]

    def rows():
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (Q,))}

    def setv(o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (o, Q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[0] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, o, Q))

    d = rows()
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)
    at1326 = [o for o, v in d.items() if o in ind and v == "13-26 weeks"]
    # very generous: FS + Tech, large-first -> full year
    fy = sorted((o for o in at1326 if inS(o, "Financial Services", "Technology")),
                key=lambda o: (0 if fte.get(o) in BIG else 1, o))[:N_FULLYEAR]
    used = set(fy)
    # generous: FS/Tech/ProfSvc/Healthcare/Media, large-first -> 9 months
    nm = sorted((o for o in at1326 if o not in used and
                 inS(o, "Financial Services", "Technology", "Professional Services", "Healthcare", "Media")),
                key=lambda o: (0 if fte.get(o) in BIG else 1, o))[:N_NINEMO]
    for o in fy: setv(o, "40-52 weeks")
    for o in nm: setv(o, "27-39 weeks")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    nd = rows()
    ORD = ["None (statutory only)", "1-12 weeks", "13-26 weeks", "27-39 weeks", "40-52 weeks"]
    cnt = Counter(nd.values())
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d orgs promoted (%d->40-52, %d->27-39)" % (changes[0], len(fy), len(nm)))
    print("  distribution:", {k: cnt.get(k, 0) for k in ORD})
    print("  not-None (marginal ~0.66, must be unchanged): %d / %d = %.3f"
          % (sum(cnt.values()) - cnt["None (statutory only)"], sum(cnt.values()),
             (sum(cnt.values()) - cnt["None (statutory only)"]) / sum(cnt.values())))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
