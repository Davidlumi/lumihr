#!/usr/bin/env python3
"""Batch 4 — cross-sector model bleeds & wrong-model answers (2026-08-14, grounding review).

  - REW_INC_077: incentive purpose "Cost control" is wrong for talent-competitive sectors -> Retention
    (FS/Healthcare/Media/Tech; Prof Services already done in V2-F). [CSV]
  - RED_PAY_01: "Includes variable pay (bonus/commission)" is legally wrong — statutory/enhanced
    redundancy uses a week's pay = BASIC salary -> "Basic salary + contractual allowances". [CSV]
  - RED_NOTICE_01: garden leave is a white-collar device; frontline sectors PILON or work notice ->
    PILON for Retail/Hospitality/Logistics/Manufacturing/Construction. [CSV]
  - REW263_GOV_SIGNOFF: large listed Energy PLCs should sign off pay at RemCo. [DB-only]
  - REW_INC_135: sales commission doesn't exist in Education/Public/Charity -> No. [CSV]
  - REW_PAY_TIPS_EXIST: non-hospitality orgs don't receive customer tips (a hospitality/tronc bleed).
    Register marginal -> count-conserving swap: non-hospitality Yes->No, Hospitality/Retail No->Yes. [CSV]
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
TIPS = "REW_PAY_TIPS_EXIST_7c80c508"
DBORIG = {"REW263_GOV_SIGNOFF"}   # DB-only; everything else here is CSV-locked
BIG = ("10,000+", "5,000-9,999", "1,000-4,999")


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
            if q not in DBORIG: csv_rows[0] += csv_set(o, q, new)

    # 1) incentive purpose
    for o, v in rows("REW_INC_077").items():
        if inS(o, "Financial Services", "Healthcare", "Media", "Technology") and v == "Cost control":
            setv("REW_INC_077", o, "Retention")
    # 2) redundancy basis (legal)
    for o, v in rows("RED_PAY_01").items():
        if v == "Includes variable pay (bonus/commission) where applicable":
            setv("RED_PAY_01", o, "Basic salary + contractual allowances")
    # 3) garden leave -> PILON for frontline
    for o, v in rows("RED_NOTICE_01").items():
        if inS(o, "Retail", "Hospitality", "Logistics", "Manufacturing", "Construction") and v == "Garden leave is typically used":
            setv("RED_NOTICE_01", o, "Payment in lieu of notice (PILON) is typically used")
    # 4) Energy large -> RemCo
    for o, v in rows("REW263_GOV_SIGNOFF").items():
        if inS(o, "Energy") and fte.get(o) in ("10,000+", "5,000-9,999") and v != "Remuneration Committee":
            setv("REW263_GOV_SIGNOFF", o, "Remuneration Committee")
    # 5) commission bleed out of Education/Public/Charity
    for o, v in rows("REW_INC_135").items():
        if inS(o, "Education", "Public Sector", "Charity") and v == "Yes":
            setv("REW_INC_135", o, "No")
    # 6) tips bleed — conserving swap (non-hospitality Yes->No, Hospitality/Retail No->Yes)
    tv = rows(TIPS)
    yes_val = next((v for v in tv.values() if "Yes" in v), "Yes")
    no_val = next((v for v in tv.values() if v == "No" or "No" in v[:3]), "No")
    donors = sorted(o for o, v in tv.items() if o in ind and "Yes" in v and not inS(o, "Hospitality", "Retail"))
    recips = sorted(o for o, v in tv.items() if o in ind and v == no_val and inS(o, "Hospitality", "Retail"))
    k = min(len(donors), len(recips))
    for o in donors[:k]: setv(TIPS, o, no_val)
    for o in recips[:k]: setv(TIPS, o, yes_val)

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)) + " | CSV rows: %d | tips pairs: %d" % (csv_rows[0], k))
    print("  tips global (marginal, hold):", dict(Counter(rows(TIPS).values())))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
