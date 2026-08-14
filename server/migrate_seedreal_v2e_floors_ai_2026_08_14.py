#!/usr/bin/env python3
"""V2-E seed-realism — numeric floors, AI-pay deflation, large-org realism (2026-08-14, persona QA).

- REW_PAY_HOURLY_MIN_1c6e096f: 29 orgs report a lowest directly-employed rate of "Under £10" or
  "£10-£11" — below the 2026 National Living Wage (~£12.21) for adult, non-apprentice staff, i.e.
  non-compliant. Lift those to "£12-£13" (at the NLW floor). "£11-£12" is left (defensible for
  youth-heavy sectors). CSV-lineage-locked -> DB + response-CSV lockstep.
- AI-pay cluster (REW262_PAY_AISKILLSPAY yes/no, REW264_GOV_AIPAYREVIEW): ran 2-3x the pool and read
  seeded rather than observed (Media, Healthcare personas). CONCENTRATE into the AI-forward sectors
  (Technology, Media, Financial Services); other sectors -> No. DB-origin -> DB-only.
- REW263_GOV_REWTEAM: large employers (5,000+) reporting "No dedicated reward resource" / a shared
  HR role is implausible (Retail persona). Lift 5,000+ orgs to a dedicated reward function. DB-only.

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
CSV_LOCKED = {"REW_PAY_HOURLY_MIN_1c6e096f"}
AI_FORWARD = ("Technology", "Media", "Financial Services")
BIG = ("5,000-9,999", "10,000+")


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

    # ---- 1) sub-NLW hourly floor -> £12-£13 ----
    for o, v in rows("REW_PAY_HOURLY_MIN_1c6e096f").items():
        if o in ind and v in ("Under £10", "£10–£11"):
            setv("REW_PAY_HOURLY_MIN_1c6e096f", o, "£12–£13")

    # ---- 2) AI-skills pay: concentrate Yes in AI-forward sectors ----
    for o, v in rows("REW262_PAY_AISKILLSPAY").items():
        if o in ind and v == "Yes" and not inS(o, *AI_FORWARD):
            setv("REW262_PAY_AISKILLSPAY", o, "No")
    # ---- 2b) AI pay-review: formal/informal -> No outside AI-forward sectors ----
    for o, v in rows("REW264_GOV_AIPAYREVIEW").items():
        if o in ind and v in ("Yes formally", "Yes informally") and not inS(o, *AI_FORWARD):
            setv("REW264_GOV_AIPAYREVIEW", o, "No")

    # ---- 3) large-org reward team ----
    for o, v in rows("REW263_GOV_REWTEAM").items():
        if o in ind and fte.get(o) in BIG:
            if v == "No dedicated reward resource":
                setv("REW263_GOV_REWTEAM", o, "2-4 dedicated FTE")
            elif v == "Shared HR/reward role" and fte.get(o) == "10,000+":
                setv("REW263_GOV_REWTEAM", o, "1 dedicated FTE")

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
    print("  sub-NLW floor remaining:", sum(1 for v in rows("REW_PAY_HOURLY_MIN_1c6e096f").values() if v in ("Under £10", "£10–£11")))
    print("  AISKILLSPAY Yes:", sum(1 for v in rows("REW262_PAY_AISKILLSPAY").values() if v == "Yes"))
    print("  AIPAYREVIEW formal:", sum(1 for v in rows("REW264_GOV_AIPAYREVIEW").values() if v == "Yes formally"))
    print("  REWTEAM 'no resource':", sum(1 for v in rows("REW263_GOV_REWTEAM").values() if v == "No dedicated reward resource"))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
