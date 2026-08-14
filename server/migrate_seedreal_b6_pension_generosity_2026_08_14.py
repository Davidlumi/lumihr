#!/usr/bin/env python3
"""Batch 6 — pension GENEROSITY level correction (2026-08-14, grounding review).

PROP_36b990f9 (typical employer pension contribution %) had Financial Services sitting DEAD LAST
(mean band 0.73 of 3), with nothing above 5-7%. UK FS is one of the most pension-generous sectors —
banks and asset managers routinely contribute 10-15% employer (PLSA/ONS ASHE pension tables 2025) —
so it should sit top-3, behind only the Public Sector. Size-grade the lift: the largest FS employers
are the most generous. Also lift Energy's two AE-floor (3%-4%) orgs, since regulated utilities carry
generous DB-legacy/DC schemes and shouldn't sit at the auto-enrolment minimum.

PROP_36b990f9 is a leaf (no coherence child) but CSV-lineage-locked (PROP_*) -> DB + response-CSV
lockstep. Free of any register marginal / gradient anchor. Pension TYPE (frozen) is untouched.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "PROP_36b990f9"
ORD = {"3%–4%": 0, "5%–7%": 1, "8%–10%": 2, "11%+": 3}
# FS target band by size — largest employers most generous (top-3 sector, mean ~1.9)
FS_BY_SIZE = {"10,000+": "11%+", "5,000-9,999": "11%+", "1,000-4,999": "8%–10%",
              "250-999": "8%–10%", "50-249": "5%–7%", "10-49": "5%–7%"}
FS_CAP_11 = 3   # cap the very-top band so it stays a credible spread, not a ceiling pile-up


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

    def rows():
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (Q,))}

    def setv(o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, Q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[Q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (new, o, Q))
            csv_rows[0] += csv_set(o, Q, new)

    d = rows()
    # FS: size-graded lift, only ever raising (never lower an already-generous org), 11%+ capped
    fs = sorted((o for o in d if inS(o, "Financial Services")),
                key=lambda o: (-ORD.get(FS_BY_SIZE.get(fte.get(o), "5%–7%"), 1), o))  # biggest-target first
    n11 = 0
    for o in fs:
        tgt = FS_BY_SIZE.get(fte.get(o), "5%–7%")
        if tgt == "11%+":
            if n11 >= FS_CAP_11: tgt = "8%–10%"
            else: n11 += 1
        if ORD.get(tgt, 0) > ORD.get(d[o], 0):   # raise only
            setv(o, tgt)

    # Energy: lift the AE-floor orgs one band (regulated utilities don't sit at the AE minimum)
    for o in [o for o in d if inS(o, "Energy") and d[o] == "3%–4%"]:
        setv(o, "5%–7%")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    nd = rows()
    def mean(sec):
        xs = [ORD[nd[o]] for o in nd if inS(o, sec)]
        return sum(xs) / len(xs) if xs else 0
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: %d | CSV rows: %d" % (changes[Q], csv_rows[0]))
    print("  FS band dist now:", dict(Counter(nd[o] for o in nd if inS(o, "Financial Services"))),
          "| FS mean %.2f  Energy mean %.2f" % (mean("Financial Services"), mean("Energy")))
    print("  global:", dict(Counter(nd.values())))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
