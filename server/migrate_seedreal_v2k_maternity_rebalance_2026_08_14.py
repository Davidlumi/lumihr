#!/usr/bin/env python3
"""V2-K seed-realism — rebalance the enhanced-maternity generous tail by sector (2026-08-14, David).

V2-J populated the empty top tiers but concentrated them in Tech/FS/Media — a "prestige = generous"
bias. Enhanced FAMILY leave is a trade-off benefit the PUBLIC sector, EDUCATION, CHARITY and FS lead
on (below-market pay offset by strong pension + family provision), while tech is variable. Rebalance
by sector, holding the same tier COUNTS (so the distribution shape and the not-None register marginal
are unchanged — this is a pure re-selection of WHICH orgs sit in the top tiers):

  * 27-39 weeks (9 months enhanced — the "very generous" band): PUBLIC SECTOR led, then Education,
    Charity, Healthcare, FS.
  * 40-52 weeks (a full year of above-statutory pay — genuinely rare/elite): FS + large corporates +
    a little Tech + a couple of the most generous public/education schemes.

Method: demote every current 27-39 / 40-52 org back to 13-26 (restore the pool), then re-promote 12
to 40-52 and 18 to 27-39 by family-benefit sector priority. "None" is never touched. DB-only.
"""
import os, sys, json, sqlite3, hashlib
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW_BEN_FAM_002"
BIG = ("10,000+", "5,000-9,999", "1,000-4,999")
# per-tier sector priority (family-benefit realism)
FULLYEAR_PRIO = ["Financial Services", "Technology", "Professional Services", "Healthcare", "Media",
                 "Manufacturing", "Energy", "Retail"]                      # elite/full-year, no single sector dominant
NINEMO_PRIO = ["Public Sector", "Education", "Charity", "Healthcare", "Financial Services",
               "Media", "Professional Services"]                          # public-sector-led generous
N_FULLYEAR, N_NINEMO = 12, 18
FY_SECTOR_CAP = 3    # a full year of enhanced pay is rare — don't let one sector own the tier


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = [0]
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)

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
    # 1) restore: demote current top tiers back to 13-26
    for o, v in d.items():
        if v in ("27-39 weeks", "40-52 weeks"):
            setv(o, "13-26 weeks")
    pool = [o for o, v in rows().items() if v == "13-26 weeks" and o in ind]

    def pick(prio, n, taken, cap=None):
        out = []; per = {}
        for sec in prio:
            for o in sorted((o for o in pool if o not in taken and o not in out and inS(o, sec)),
                            key=lambda o: (0 if fte.get(o) in BIG else 1, o)):
                if len(out) >= n: break
                if cap and per.get(sec, 0) >= cap: break
                out.append(o); per[sec] = per.get(sec, 0) + 1
            if len(out) >= n: break
        # top up from anything left if the priority lists ran short under the cap
        for o in sorted(o for o in pool if o not in taken and o not in out):
            if len(out) >= n: break
            out.append(o)
        return out[:n]

    fy = pick(FULLYEAR_PRIO, N_FULLYEAR, set(), cap=FY_SECTOR_CAP)
    nm = pick(NINEMO_PRIO, N_NINEMO, set(fy))
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
    SH = lambda o: (ind.get(o) or "?").split(",")[0][:18]
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d cell writes" % changes[0])
    for band in ("40-52 weeks", "27-39 weeks"):
        print("  %s: %s" % (band, dict(Counter(SH(o) for o, v in nd.items() if v == band))))
    cnt = Counter(nd.values())
    print("  not-None (marginal ~0.66, unchanged): %.3f" %
          ((sum(cnt.values()) - cnt["None (statutory only)"]) / sum(cnt.values())))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
