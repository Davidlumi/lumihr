#!/usr/bin/env python3
"""P0-c — complete the DB-pension cascade to the pension children (2026-08-14, grounding review).

V2-C reallocated REW26_BEN_PENSION_TYPE to DB/Hybrid for the right sectors and set REW_BEN_112 to a
TPS/LGPS-style 23%, but the OTHER pension children still read DC for those DB orgs (Education review):
  - REW26_BEN_PLSA_QM = "No" (DB employer contributions far exceed the PLSA 12%/6% quality mark).
  - PROP_36b990f9 (headline employer %) sitting in 3-7% bands (TPS 28.7% / USS 14.5% / LGPS ~15-25%).
  - REW26_BEN_PENSION_COST_SHARE at 5-9% of reward spend (DB employer cost is materially higher).
Applied to PURE DB orgs (PENSION_TYPE="DB"); Hybrid keeps its DC-section contribution %, but its DB
part still clears the quality mark so PLSA_QM -> Yes for those too. None are anchored; PLSA_QM and
cost-share are DB-origin (DB-only), PROP_36b990f9 is CSV-lineage-locked (DB+CSV lockstep).
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
CSV_LOCKED = {"PROP_36b990f9"}


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_edit(o, q, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]
    qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (r[mi] or "") == "":
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changes = defaultdict(int); csv_rows = [0]

    def hl(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (o, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, o, q))
            if q in CSV_LOCKED: csv_rows[0] += csv_edit(o, q, new)

    pt = hl("REW26_BEN_PENSION_TYPE")
    pure_db = [o for o, v in pt.items() if v == "DB"]
    hybrid = [o for o, v in pt.items() if v == "Hybrid"]
    cs = hl("REW26_BEN_PENSION_COST_SHARE"); pr = hl("PROP_36b990f9")

    for o in pure_db:
        setv("REW26_BEN_PLSA_QM", o, "Yes")
        if pr.get(o) in ("3%–4%", "5%–7%", "8%–10%", None):
            setv("PROP_36b990f9", o, "11%+")
        try:
            if float(cs.get(o, "0")) < 12:
                setv("REW26_BEN_PENSION_COST_SHARE", o, "16.0")
        except ValueError:
            pass
    for o in hybrid:
        setv("REW26_BEN_PLSA_QM", o, "Yes")   # DB section clears the quality mark

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)) + " | CSV rows: %d" % csv_rows[0])
    print("  DB-org PLSA_QM now:", dict(Counter(hl("REW26_BEN_PLSA_QM").get(o) for o in pure_db + hybrid)))
    print("  DB-org PROP_36b990f9 now:", dict(Counter(hl("PROP_36b990f9").get(o) for o in pure_db)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
