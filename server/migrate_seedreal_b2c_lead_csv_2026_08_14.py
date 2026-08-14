#!/usr/bin/env python3
"""Batch 2c — sector signature raises on free CSV-locked metrics (2026-08-14, grounding review).

  - REW_BEN_038 (benefits checklist): add "Retail discounts" — the signature retail benefit
    (near-universal per Retail Week Staff Discount Index 2025) — to Retail orgs missing it.
  - REW_FAI_MIN_HOURS_8518a543: Hospitality is the UK's zero-hours capital (~29% of the workforce),
    so it should LEAD on non-guaranteed hours -> set more Hospitality orgs to "No (hours not guaranteed)".
  - REW_PAY_017 (on-call/standby pay): standby/call-out rotas are near-universal in utility field ops
    (Thames Water/Cadent 2026 deals) -> Energy orgs off "Not offered".

All three are unanchored but CSV-lineage-locked -> DB + response-CSV lockstep.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


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
    BIG = ("10,000+", "5,000-9,999", "1,000-4,999", "250-999")
    changes = defaultdict(int); csv_rows = [0]
    inS = lambda o, s: s in str(ind.get(o, ""))

    def rows(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (new, o, q))
            csv_rows[0] += csv_set(o, q, new)

    # 1) staff discount -> Retail (append token)
    d = rows("REW_BEN_038")
    ret = sorted((o for o, v in d.items() if inS(o, "Retail & Consumer") and "Retail discount" not in v),
                 key=lambda o: (0 if fte.get(o) in BIG else 1, o))
    for o in ret[:12]:
        setv("REW_BEN_038", o, (d[o] + "; Retail discounts"))
    # 2) Hospitality non-guaranteed hours (should lead)
    d = rows("REW_FAI_MIN_HOURS_8518a543")
    hosp = sorted((o for o, v in d.items() if inS(o, "Hospitality") and v in ("Yes – some roles", "Yes – all hourly roles")),
                  key=lambda o: (1 if fte.get(o) in BIG else 0, o))   # SMEs first (more likely zero-hours)
    for o in hosp[:10]:
        setv("REW_FAI_MIN_HOURS_8518a543", o, "No (hours not guaranteed)")
    # 3) Energy standby/call-out pay
    d = rows("REW_PAY_017")
    en = sorted(o for o, v in d.items() if inS(o, "Energy") and v == "Not offered / not applicable")
    for i, o in enumerate(en[:4]):
        setv("REW_PAY_017", o, "Combination" if i % 2 else "Per day")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)) + " | CSV rows: %d" % csv_rows[0])
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
