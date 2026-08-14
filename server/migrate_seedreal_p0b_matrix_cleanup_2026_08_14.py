#!/usr/bin/env python3
"""P0-b — remove inapplicable matrix data on EXISTING orgs (2026-08-14, grounding review).

Finishes two earlier passes that only ran on the 50 new orgs / the OT_04 headline:
  1. Phantom bonus/LTI ladders on EXISTING seed orgs (V2-A only conditioned the 50 new orgs):
     - REW_INC_103 = "None" but a populated max-bonus (323ffcf1) or target-bonus (REW_INC_111) ladder
       -> delete those ladder rows (18 orgs, incl. Education b7c6fb0d and Public/Charity spine bodies).
     - REW_INC_131 = "No" equity but a REW_INC_LTI_MAX_01 ladder -> delete (2 orgs).
  2. Shift-differentiated overtime / hourly-band multiplier MATRICES (REW_Q528801, REW_Q534581) still
     carried by salaried office sectors (Tech/FS/ProfSvc/Media) — V2-D fixed the OT_04 headline only.
     -> delete those matrix rows for office-sector orgs.

All metrics are unanchored but CSV-lineage-locked, so rows are deleted from BOTH the DB and the
data/responses CSV. Re-records book_baseline. After --write, re-aggregate.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
OFFICE = ("Technology", "Financial Services", "Professional Services", "Media")
B323 = "323ffcf1-749b-43f3-bf34-1de6b8b1ca67"


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_delete(o, qids):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]; qi = hdr.index("question_id")
    keep = [rows[0]] + [r for r in rows[1:] if not (len(r) > qi and r[qi] in qids)]
    n = len(rows) - len(keep)
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(keep)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    deleted = defaultdict(int); csv_rows = [0]
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)

    def hl(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def has_rows(o, q):
        return c.execute("SELECT COUNT(*) FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1 AND matrix_row_id!='' AND value NOT IN ('','Not applicable','N/A')",
                         (o, q)).fetchone()[0]

    def wipe(o, qids):
        qids = [q for q in qids if has_rows(o, q)]
        if not qids: return
        for q in qids: deleted[q] += 1
        if WRITE:
            qm = ",".join("?" * len(qids))
            c.execute("DELETE FROM answers WHERE org_id=? AND question_id IN (%s) AND snapshot_id=1 AND matrix_row_id!=''" % qm, [o] + qids)
            csv_rows[0] += csv_delete(o, set(qids))

    none103 = [o for o, v in hl("REW_INC_103").items() if v == "None"]
    noeq = [o for o, v in hl("REW_INC_131").items() if v == "No"]
    for o in none103: wipe(o, [B323, "REW_INC_111"])
    for o in noeq: wipe(o, ["REW_INC_LTI_MAX_01"])
    for o in ind:
        if inS(o, *OFFICE): wipe(o, ["REW_Q528801", "REW_Q534581"])

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — orgs cleaned per metric: " + str({k[:22]: v for k, v in deleted.items()}))
    print("  CSV rows deleted:", csv_rows[0])
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
