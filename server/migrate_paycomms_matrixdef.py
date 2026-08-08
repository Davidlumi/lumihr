#!/usr/bin/env python3
"""Repair REW265_PAY_PAYCOMMS's missing matrix column definition.

THE DEFECT (found 2026-08-05 during the refresh-system deep QA, root-caused
2026-08-05): Diff 15's PAYCOMMS redesign (single_select -> by-level matrix,
v2.0) set type/options_json/matrix_rows_json but never wrote matrix_json —
and BOTH the validator (app._matrix_col) and the questionnaire UI key off
matrix_json.columns[0]. Consequences today:
  * validate_answer falls to the numeric path -> every stored answer
    ("Letter only" / "Letter + manager conversation", all 1,540 rows valid
    labels from the ruled design) reads as a validation problem, which BLOCKS
    EVERY SUBMIT for any org that answered it (Thornbridge included);
  * the UI renders NUMBER inputs for a communication-method question, so a
    member cannot even enter a valid answer.

THE FIX: write the matrix_json the Diff-15 design implies — one select column
whose options are exactly the ruled option labels. NO answer row is touched;
the answers book hash is asserted identical before/after. Diff 17's
classification ruling (class=Practice, direction=null) is untouched.

No CSV echo: REW265_* is recognised DB-origin lineage (CSVs deliberately
stale for those — see DECISIONS, Diff-15 era).

Backup policy (data/backup_policy.md, ruled 2026-07-30): a pre-write backup
is taken via the SQLite backup API and retention-scheduled AT CREATION —
this close keeps the last 3 pre-diff backups and deletes older ones (with
sidecars), as the creation-time doctrine requires.

Dry-run by default. Writing needs BOTH --write AND --confirmed-by-david.
"""
import argparse
import glob
import hashlib
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
QID = "REW265_PAY_PAYCOMMS"
RETAIN = 3   # DB-class pre-diff backups to keep (policy: "retain the last 3")

MATRIX_DEF = {
    "columns": [{
        "id": "channel",
        "type": "select",
        "label": "Communication method",
        "options": ["Letter + manager conversation", "Letter only"],
        "placeholder": "Select...",
    }],
    "answer_type": "select",
}


def answers_book_hash(conn):
    h = hashlib.sha256()
    for r in conn.execute("SELECT org_id, question_id, COALESCE(matrix_row_id,''), value "
                          "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(map(str, r)) + "\n").encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", action="store_true")
    a = ap.parse_args()
    write = a.write and a.confirmed_by_david
    if a.write and not a.confirmed_by_david:
        sys.exit("REFUSING: --write requires --confirmed-by-david.")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    q = conn.execute("SELECT id, type, matrix_json, options_json, matrix_rows_json, "
                     "question_version FROM questions WHERE id=?", (QID,)).fetchone()
    if q is None:
        sys.exit("FATAL: %s not found in %s" % (QID, DB))
    opts = [o["label"] for o in json.loads(q["options_json"] or "[]")]
    print("db: %s" % DB)
    print("%s (%s, %s): matrix_json currently %r" % (
        QID, q["type"], q["question_version"],
        (q["matrix_json"][:60] + "…") if q["matrix_json"] and len(q["matrix_json"]) > 60
        else q["matrix_json"]))
    print("option labels in options_json: %s" % opts)
    if opts != MATRIX_DEF["columns"][0]["options"]:
        sys.exit("FATAL: options_json labels differ from the ruled design — refusing "
                 "(update MATRIX_DEF only if a ruling changed the options).")
    if q["type"] != "matrix":
        sys.exit("FATAL: %s is no longer a matrix — nothing to repair." % QID)
    vals = {r["value"]: r["c"] for r in conn.execute(
        "SELECT value, COUNT(*) c FROM answers WHERE question_id=? GROUP BY value", (QID,))}
    stray = {v: c for v, c in vals.items() if v not in opts and v != "Not applicable"}
    print("stored answer values: %s" % vals)
    if stray:
        sys.exit("FATAL: values outside the option set exist %s — this script only "
                 "writes the definition; those need their own ruling." % stray)
    print("proposed matrix_json: %s" % json.dumps(MATRIX_DEF))

    if not write:
        print("\nDRY-RUN (no changes). Re-run with --write --confirmed-by-david to apply.")
        return

    # pre-write backup (SQLite backup API — never cp), retention-scheduled at
    # creation. Backup AND sweep are scoped to the TARGET store's own path, so
    # a throwaway rehearsal can never touch the live backups.
    tag = time.strftime("%Y%m%d_%H%M%S")
    db_abs = os.path.abspath(DB)
    bak = "%s.bak_pre_paycommsdef_%s" % (db_abs, tag)
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(bak)
    src.backup(dst)
    dst.close(); src.close()
    print("backup: %s" % os.path.basename(bak))
    # PINNED backups are named exceptions to the retain-N rotation
    # (data/backup_policy.md "Named exception: the pre-split backup pin") and
    # MUST be excluded from the rotation count. This guard exists because this
    # very script's first run violated the pin and deleted bak_pre_presplit
    # (2026-08-05 incident, DECISIONS) — the policy's own warning ("the pin is
    # not released by anyone remembering it independently") proved true of
    # code, not just people. Any future pin must be added here AND in the
    # policy file.
    PINNED = ("presplit",)
    baks = sorted(glob.glob(db_abs + ".bak_pre_*"), key=os.path.getmtime)
    baks = [b for b in baks if not b.endswith(("-shm", "-wal"))]
    pinned = [b for b in baks if any(p in os.path.basename(b) for p in PINNED)]
    for p in pinned:
        print("pinned (excluded from rotation): %s" % os.path.basename(p))
    baks = [b for b in baks if b not in pinned]
    for old in baks[:-RETAIN]:
        for f in (old, old + "-shm", old + "-wal"):
            if os.path.exists(f):
                os.unlink(f)
                print("retention (policy 2026-07-30, keep last %d): deleted %s"
                      % (RETAIN, os.path.basename(f)))

    before = answers_book_hash(conn)
    conn.execute("UPDATE questions SET matrix_json=? WHERE id=?",
                 (json.dumps(MATRIX_DEF), QID))
    conn.commit()
    after = answers_book_hash(conn)
    if before != after:
        sys.exit("FATAL: answers book hash CHANGED (%s -> %s) — restore from %s"
                 % (before[:16], after[:16], os.path.basename(bak)))
    print("answers book hash unchanged: %s (sha256 of ordered "
          "org|question|row|value lines, first 16 hex: %s)" % ("OK", before[:16]))

    # prove the repair end-to-end at the validation layer
    sys.path.insert(0, HERE)
    import library
    library.invalidate_cache()
    from app import validate_answer
    qobj = library.load_questions()[QID]
    for label in opts:
        errs, _ = validate_answer(qobj, label, "board_executive")
        print("validate %r -> %s" % (label, "OK" if not errs else "STILL FAILING: %s" % errs))
        if errs:
            sys.exit("FATAL: validation still failing after write.")
    errs, _ = validate_answer(qobj, "Cheque in the post", "board_executive")
    print("validate off-list value correctly refused: %s" % ("OK" if errs else "NOT REFUSED"))
    if not errs:
        sys.exit("FATAL: off-list value passed — select validation not active.")
    print("\nWRITTEN. Restart the dev server (:8060 has the question bank cached).")


if __name__ == "__main__":
    main()
