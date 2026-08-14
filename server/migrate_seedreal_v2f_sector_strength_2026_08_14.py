#!/usr/bin/env python3
"""V2-F seed-realism — sector-strength corrections, unanchored subset (2026-08-14, persona QA).

The four fixes here touch UNANCHORED metrics (no frozen/register conservation needed):
- REW264_INC_EMICSOP: EMI share options are legally restricted to companies with < 250 employees.
  Any org at 250+ FTE answering "EMI" is an impossible record (Prof Services persona) -> "CSOP"
  (the large-company equivalent).
- REW263_GOV_SIGNOFF: a RemCo is effectively mandatory under the FCA/PRA remuneration codes, yet
  Financial Services rarely showed one (FS persona). Set FS final reward sign-off -> Remuneration
  Committee.
- REW_INC_077: Prof Services framed incentives as "cost control" — wrong for a fee-earner/partner,
  war-for-talent model. Re-point Prof Services -> Retention.
- REW26_PAY_JOBEVAL_COVERAGE: Public Sector runs analytical JE almost everywhere (Agenda for Change,
  NJC Green Book, HAY). Lift Public Sector "None" -> "All".

DEFERRED (anchored — need per-sector reallocation that conserves the frozen/register global, an
OT_04-style batch): REW26_WEL_EAP (frozen; Construction low), REW26_BEN_SALSAC (frozen; PubSec DB
can't salary-sacrifice), REW_BEN_SICK_001 (marginal; PubSec OSP), REW263_WEL_OH (marginal;
Construction), PAYTR_01/02 + REW_PAY_001 (marginal; PubSec/FS transparency), REW_BEN_FAM_010
(marginal; Charity volunteering leave).

LUMI_DB-aware. Dry-run default; --write --confirmed-by-david. Deterministic. Re-records book_baseline.
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
# REW_INC_077 is an older CSV-documented wave metric -> lockstep CSV; the REW26x/263x/264x are DB-origin
CSV_LOCKED = {"REW_INC_077"}
SMALL = ("50-249", "1-49", "Under 50")


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_edit(o, q, mr, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]
    qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (r[mi] or "") == mr:
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int); csv_hits = [0]
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
            if q in CSV_LOCKED: csv_hits[0] += csv_edit(org, q, "", new)

    # ---- 1) EMI only legal at < 250 FTE ----
    for o, v in rows("REW264_INC_EMICSOP").items():
        if o in ind and v == "EMI" and fte.get(o) not in SMALL:
            setv("REW264_INC_EMICSOP", o, "CSOP")
    # ---- 2) FS final reward sign-off -> RemCo ----
    for o, v in rows("REW263_GOV_SIGNOFF").items():
        if inS(o, "Financial Services") and v != "Remuneration Committee":
            setv("REW263_GOV_SIGNOFF", o, "Remuneration Committee")
    # ---- 3) Prof Services incentive purpose: cost control -> retention ----
    for o, v in rows("REW_INC_077").items():
        if inS(o, "Professional Services") and v == "Cost control":
            setv("REW_INC_077", o, "Retention")
    # ---- 4) Public Sector job-evaluation coverage: None -> All ----
    for o, v in rows("REW26_PAY_JOBEVAL_COVERAGE").items():
        if inS(o, "Public Sector") and v == "None":
            setv("REW26_PAY_JOBEVAL_COVERAGE", o, "All")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  CSV rows updated:", csv_hits[0])
    print("  EMI at 250+ remaining:", sum(1 for o, v in rows("REW264_INC_EMICSOP").items() if v == "EMI" and fte.get(o) not in SMALL))
    print("  FS RemCo:", sum(1 for o, v in rows("REW263_GOV_SIGNOFF").items() if inS(o, "Financial Services") and v == "Remuneration Committee"))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
