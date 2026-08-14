#!/usr/bin/env python3
"""V2-B seed-realism — cross-question coherence repair (2026-08-14, from the 14 sector-persona QA).

Aligns contradicting metric pairs across ALL orgs so headline and detail agree:

  1. Carer's leave: REW_BEN_FAM_007 (provision) <- REW263_TIME_CARERPAID (paid status).
     236/270 orgs currently disagree (e.g. "no specific provision" + "some paid days"). FAM_007
     is a Diff-3 register metric (value-diff-skipped by qa_engine_audit L1), so it is edited in the
     DB only. CARERPAID is the finer-grained authority (unpaid / some paid / fully paid).
  2. Commission: REW265_INC_COMMCAP <- "Not applicable (no commission plans)" wherever REW_INC_135
     ("do you run commission plans?") = No. CARERPAID/COMMCAP are CSV-lineage-locked, so those edits
     touch the data/responses CSV row in lockstep with the DB.

LUMI_DB-aware. Dry-run default; apply with `--write --confirmed-by-david`. Deterministic. Re-records
data/book_baseline.json. After --write, re-aggregate:
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, csv, json, sqlite3, hashlib, glob

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def csv_path(org_id):
    hits = glob.glob(os.path.join(RESP, "*_%s.csv" % org_id))
    return hits[0] if hits else None


def apply_csv_edit(org_id, qid, mr, new_val):
    """Update your_answer for (qid, matrix_row_id) rows in the org's response CSV. Returns rows hit."""
    p = csv_path(org_id)
    if not p: return 0
    rows = list(csv.reader(open(p)))
    hdr = rows[0]
    qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == qid and (mr is None or (r[mi] or "") == mr):
            r[ai] = new_val; n += 1
    if n:
        with open(p, "w", newline="") as f:
            csv.writer(f).writerows(rows)
    return n


def main():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()

    def hl(qid):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 AND matrix_row_id='' AND value!=''", (qid,))}

    edits = []   # (org_id, qid, matrix_row_id_or_None, new_value, csv_locked)

    # ---- 1) carer's leave: CARERPAID (CSV-locked, UN-anchored) <- consistent with FAM_007.
    #      FAM_007 is itself a register marginal (~36% "offers provision"), so it can't move; instead
    #      bring the paid-status detail into line with the provision headline (a "no provision"/
    #      "unpaid only" org cannot also report paid carer's leave). ----
    cp = hl("REW263_TIME_CARERPAID"); f7 = hl("REW_BEN_FAM_007")
    PAID = ("Some paid days", "Fully paid carer's leave")
    for o, f in f7.items():
        cur = cp.get(o)
        if cur is None: continue
        if f == "Yes - paid leave is provided":
            want = cur if cur in PAID else "Some paid days"     # keep granularity if already paid
        else:                                                   # Unpaid leave only / No specific provision
            want = "Statutory unpaid only"
        if cur != want:
            edits.append((o, "REW263_TIME_CARERPAID", "", want, True))

    # ---- 2) commission: COMMCAP -> Not applicable where no commission plan (CSV-locked) ----
    plan = hl("REW_INC_135"); cap = hl("REW265_INC_COMMCAP")
    NA = "Not applicable (no commission plans)"
    for o, p in plan.items():
        if p == "No" and cap.get(o) not in (None, NA):
            edits.append((o, "REW265_INC_COMMCAP", "", NA, True))

    # ---- report ----
    from collections import Counter
    by_q = Counter(q for (_, q, _, _, _) in edits)
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d headline edits across %d orgs" %
          (len(edits), len({e[0] for e in edits})))
    for q, n in by_q.most_common():
        print("  %-26s %d edits" % (q, n))

    if not WRITE:
        con.close(); return

    # DB edits + CSV lockstep for locked metrics
    csv_hits = 0
    for (o, q, mr, v, locked) in edits:
        c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND snapshot_id=1 AND matrix_row_id=?",
                  (v, o, q, mr))
        if locked:
            csv_hits += apply_csv_edit(o, q, mr, v)
    con.commit()

    # re-record book_baseline
    rows = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                     "ORDER BY org_id, question_id, matrix_row_id").fetchall()
    digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rows).encode()).hexdigest()[:16]
    book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
    book["rows"] = len(rows); book["hash16"] = digest
    json.dump(book, open(BOOK, "w"), indent=2)
    con.close()
    print("WROTE: %d DB edits, %d CSV rows updated, book_baseline (%d rows, %s)" %
          (len(edits), csv_hits, len(rows), digest))


if __name__ == "__main__":
    main()
