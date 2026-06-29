# -*- coding: utf-8 -*-
"""Soft-retire ONE metric: status='retired' in the DB (the single gate the engine
reads via visible_questions) AND in the CSV seed (durability across re-seed).

Retire, never delete: the question row and all member answers are untouched; the
metric simply leaves every member-facing/benchmarked surface and can be restored by
flipping status back. Dry-run by default (standing convention); applies only on --write.

    python3 retire_metric.py REW_PAY_MKT_POS_01            # dry-run (prints the plan)
    python3 retire_metric.py REW_PAY_MKT_POS_01 --write    # apply DB + CSV + invalidate

The CSV edit is a BYTE-LEVEL replacement of just the status token on the one matching
line — CRLF line endings and every other byte are preserved, so the diff is one field.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import releases
import library
from db import get_conn

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "lumi_questions.csv")


def main(qid, write):
    conn = get_conn()
    row = conn.execute("SELECT id, status, text FROM questions WHERE id=?", (qid,)).fetchone()
    if row is None:
        print("UNKNOWN question: %s" % qid); sys.exit(1)
    n_ans = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=?", (qid,)).fetchone()["c"]
    n_hist = conn.execute("SELECT COUNT(*) c FROM answers_history WHERE question_id=?", (qid,)).fetchone()["c"]

    # locate the CSV row + status field; surgical BYTE replace keeps CRLF + all other bytes
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        header = next(csv.reader([f.readline()]))
    s_idx = header.index("status")
    start = raw.find((qid + ",").encode("utf-8"))
    if start == -1:
        print("CSV row not found for %s" % qid); sys.exit(1)
    eol = raw.find(b"\n", start)                         # keep the line's trailing \r\n
    line = raw[start:eol]
    fields = next(csv.reader([line.rstrip(b"\r").decode("utf-8")]))
    csv_status_before = fields[s_idx]
    old_tok = ("," + csv_status_before + ",").encode("utf-8")
    new_line = line.replace(old_tok, b",retired,", 1)   # first occurrence = the status field
    surgical_ok = (new_line != line and new_line.replace(b",retired,", old_tok, 1) == line)

    print("=" * 90)
    print("RETIRE PLAN — %s" % qid)
    print("  text:                %s" % row["text"][:70])
    print("  DB status:           %r -> 'retired'" % row["status"])
    print("  CSV status (col %d):  %r -> 'retired'" % (s_idx, csv_status_before))
    print("  answers rows:        %d  (PRESERVED — not touched)" % n_ans)
    print("  answers_history:     %d  (PRESERVED — not touched)" % n_hist)
    print("  CSV change is surgical (only the status token on this one line)? %s" % surgical_ok)
    print("  --- old CSV line (truncated) ---\n  %s" % line.rstrip(b"\r\n").decode("utf-8")[:150])
    print("  --- new CSV line (truncated) ---\n  %s" % new_line.rstrip(b"\r\n").decode("utf-8")[:150])
    print("=" * 90)

    if not write:
        print("DRY RUN — pass --write to apply. No changes made.")
        return
    if not surgical_ok:
        print("ABORT: CSV change is not surgical (status token ambiguous). No write."); sys.exit(1)
    # APPLY
    releases.retire_question(qid)                       # DB: status='retired' (+ commit; idempotent)
    with open(CSV_PATH, "wb") as f:                     # CSV: byte-surgical status -> retired
        f.write(raw[:start] + new_line + raw[eol:])
    library.invalidate_cache()                          # clear this process's lru_cache
    after = conn.execute("SELECT status FROM questions WHERE id=?", (qid,)).fetchone()["status"]
    after_ans = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=?", (qid,)).fetchone()["c"]
    print("APPLIED. DB status now: %r | CSV status -> 'retired' | cache invalidated." % after)
    print("answers rows after: %d (must equal %d)" % (after_ans, n_ans))
    print("RESTART the running server for it to re-read the DB (its lru_cache is separate).")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "REW_PAY_MKT_POS_01", "--write" in sys.argv)
