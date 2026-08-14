#!/usr/bin/env python3
"""V2-H seed-realism — remaining cross-question coherence (2026-08-14, realism review).

Four pre-existing contradictions a reward manager spots instantly; all on unanchored metrics.

  1. RED_PROC_01 (documented process = Yes) but RED_PROC_02 (documented objective criteria = No):
     83 orgs. A documented redundancy process almost always carries documented selection criteria
     (legal necessity). -> criteria = Yes (~60%) / Partially (~40%). [CSV-lineage-locked]
  2. PROP_34ffb6e2 = "Mostly manager discretion" for promotion AND has formal pay ranges (REW_PAY_001
     = Yes): 52 orgs. Range/grade architecture governs promotion. -> "Governed at business-unit level
     with criteria". [CSV-lineage-locked]
  3. REW264_WEL_COLACTION = "None" but REW_BEN_058 = "Yes" (enhanced benefits for cost-of-living):
     94 orgs. Enhancing benefits for COL IS a COL action. -> spread across One-off payments /
     Subsidies / Targeted low-earner uplift. [DB-origin]
  4. ALLOW_03 = "No - non-pensionable" but REW_PAY_020 (by-level) has pensionable ("Yes") rows: 51
     orgs. Most UK allowances are non-pensionable. -> REW_PAY_020 rows = No. [regen; PIN UPDATE]

REW_PAY_020's qa_engine_audit REGEN_WHITELIST pin must be re-recorded to the new store afterwards
(the migration prints the new counts). LUMI_DB-aware. Dry-run default; --write --confirmed-by-david.
Deterministic. Re-records book_baseline. Then re-aggregate.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
CSV_LOCKED = {"RED_PROC_02", "PROP_34ffb6e2"}


def h(*p): return int(hashlib.sha256("|".join(str(x) for x in p).encode()).hexdigest()[:12], 16)


def csv_path(o):
    hits = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return hits[0] if hits else None


def csv_edit(o, q, mr, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]
    qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (mr is None or (r[mi] or "") == mr):
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changes = defaultdict(int); csv_hits = [0]

    def hl(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, org, mr, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, q, mr)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (new, org, q, mr))
            if q in CSV_LOCKED: csv_hits[0] += csv_edit(org, q, mr, new)

    # 1) RED_PROC criteria <- process
    p1, p2 = hl("RED_PROC_01"), hl("RED_PROC_02")
    for o in p1:
        if p1[o].startswith("Yes") and p2.get(o) == "No":
            setv("RED_PROC_02", o, "", "Yes" if h("red", o) % 5 < 3 else "Partially")
    # 2) promotion governance <- grading
    pg, pr = hl("PROP_34ffb6e2"), hl("REW_PAY_001")
    for o in pg:
        if pg[o] == "Mostly manager discretion" and pr.get(o) == "Yes":
            setv("PROP_34ffb6e2", o, "", "Governed at business-unit level with criteria")
    # 3) COL action <- COL-driven benefit
    col, b58 = hl("REW264_WEL_COLACTION"), hl("REW_BEN_058")
    COL_OPTS = ["One-off payments", "One-off payments", "Subsidies (meals/travel)", "Targeted low-earner uplift"]
    for o in col:
        if col[o] == "None" and b58.get(o) == "Yes":
            setv("REW264_WEL_COLACTION", o, "", COL_OPTS[h("col", o) % len(COL_OPTS)])
    # 4) REW_PAY_020 (matrix) <- ALLOW_03 non-pensionable
    al = hl("ALLOW_03")
    nonpens = [o for o, v in al.items() if v.startswith("No")]
    for o in nonpens:
        for r in c.execute("SELECT matrix_row_id,value FROM answers WHERE org_id=? AND question_id='REW_PAY_020' AND snapshot_id=1 AND value='Yes'", (o,)):
            setv("REW_PAY_020", o, r["matrix_row_id"], "No")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    pay020 = {r["value"]: r["c"] for r in c.execute(
        "SELECT value, COUNT(*) c FROM answers WHERE question_id='REW_PAY_020' AND snapshot_id=1 GROUP BY value")}
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  CSV rows updated:", csv_hits[0])
    print("  >>> UPDATE qa_engine_audit REW_PAY_020 pin to:", {k: pay020[k] for k in sorted(pay020)})
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
