#!/usr/bin/env python3
"""Data QA class 10 — retire the two duplicate questions (2026-08-19, David's ruling).

David's p9 note asked whether pension contributions and caps were being asked twice. Two pairs
were. His rulings, 2026-08-19:

    ALLOW_03       "Are allowances pensionable?"        RETIRE — the by-level matrix
    REW_PAY_020    "Allowances pensionability by level"  KEEP    carries strictly more

    PROP_36b990f9  "Employer pension contribution rate"  RETIRE — same precedent as
    REW_BEN_112    "...by level"                         KEEP    PROP_634adacd: evolve,
                                                                 don't duplicate

    Seed answers: DELETE, following the Diff 14 precedent (status=retired AND seed answers
    removed). answers_history keeps the pre-retire snapshot, so nothing is truly lost and the
    live tables stop carrying rows no member can reach.

Note what retiring ALLOW_03 costs, so it is on the record: it held a David-signed 72/20/8
ruling from 2026-06-12, and REW_PAY_020 was originally seeded ALIGNED to it. That alignment
was the whole basis of the matrix's numbers. Retiring the anchor does not invalidate the
ladder — it was re-struck against the signed figure in class 9 and keeps those values — but
the signed ruling becomes historical rather than a live constraint, and the qa_engine_audit
pin for REW_PAY_020 is re-commented to say so rather than pointing at a retired question.

This does NOT use retire_metric.py, whose contract is "retire, never delete" and which writes
to the repo CSV regardless of LUMI_DB — unusable for a throwaway trial. The DB and CSV work
here is the same byte-surgical status swap that tool performs, plus the ruled deletion.

Dry-run by default. Writes only with:  --write --confirmed-by-david
Pass --skip-csv on a throwaway trial (the CSV is shared repo state, not per-database).
Run aggregate.run_snapshot(1), then regenerate the refresh register, afterwards.
"""
import csv
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
CSV_PATH = os.path.join(ROOT, "data", "lumi_questions.csv")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SKIP_CSV = "--skip-csv" in sys.argv

RETIRE = {
    "ALLOW_03": "duplicate of REW_PAY_020 (by level), which carries strictly more; "
                "David 2026-08-19",
    "PROP_36b990f9": "duplicate of REW_BEN_112 (by level); evolve-don't-duplicate precedent "
                     "from PROP_634adacd; David 2026-08-19",
}


def csv_retire(qid):
    """Byte-surgical status -> retired on the one matching line. CRLF and every other
    byte preserved, exactly as retire_metric.py does it."""
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        header = next(csv.reader([f.readline()]))
    s_idx = header.index("status")
    start = raw.find((qid + ",").encode("utf-8"))
    if start == -1:
        return None, "CSV row not found"
    eol = raw.find(b"\n", start)
    line = raw[start:eol]
    fields = next(csv.reader([line.rstrip(b"\r").decode("utf-8")]))
    before = fields[s_idx]
    if before == "retired":
        return raw, "already retired in CSV"
    old_tok = ("," + before + ",").encode("utf-8")
    new_line = line.replace(old_tok, b",retired,", 1)
    if new_line == line or new_line.replace(b",retired,", old_tok, 1) != line:
        return None, "status token ambiguous — refusing"
    return raw[:start] + new_line + raw[eol:], "%r -> 'retired'" % before


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s%s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed",
                            "  (CSV skipped)" if SKIP_CSV else ""))

    for qid, why in RETIRE.items():
        r = conn.execute("SELECT id, status, is_scored, text FROM questions WHERE id=?",
                         (qid,)).fetchone()
        if not r:
            print("   UNKNOWN %s — not in this bank" % qid)
            continue
        n_ans = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=?",
                             (qid,)).fetchone()["c"]
        n_hist = conn.execute("SELECT COUNT(*) c FROM answers_history WHERE question_id=?",
                              (qid,)).fetchone()["c"]
        print("-- %s --" % qid)
        print("   %s" % (r["text"] or "")[:76])
        print("   why      : %s" % why)
        print("   status   : %r -> 'retired'   (is_scored %s -> 0)" % (r["status"], r["is_scored"]))
        print("   answers  : %d -> 0   DELETED by ruling" % n_ans)
        print("   history  : %d rows PRESERVED — the pre-retire snapshot" % n_hist)

        if WRITE:
            # mirror every answer into history before deleting, so the snapshot is complete
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) "
                         "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,"
                         "datetime('now') FROM answers WHERE question_id=?", (qid,))
            conn.execute("DELETE FROM answers WHERE question_id=?", (qid,))
            conn.execute("UPDATE questions SET status='retired', is_scored=0 WHERE id=?", (qid,))
            conn.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (qid,))

        if not SKIP_CSV:
            new_raw, note = csv_retire(qid)
            print("   CSV      : %s" % note)
            if WRITE and new_raw is not None:
                with open(CSV_PATH, "wb") as f:
                    f.write(new_raw)
        print()

    if WRITE:
        conn.commit()
        print("committed.")
        print("  next: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
        print("        python3 server/gen_refresh_register.py --write   (bank shrinks by 2)")
        print("        restart the server — library caches question status")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
