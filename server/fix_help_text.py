# -*- coding: utf-8 -*-
"""Content QA fix (2026-06-13): correct help_text that contradicts the input type.

Found in the submission design QA:
  (1) the £-entry matrix "Total annual payment for each allowance" carried
      select-question help ("Select the option that best describes…");
  (2) 17 practice questions render as a 4-option choice (Yes / No /
      partial-or-ad-hoc / Don't know) but still said "Select Yes or No."

Metadata only — touches questions.help_text, never answers/aggregates. DRY RUN
by default; pass --write to apply. Idempotent (only rewrites the exact stale
strings). Backup taken before running.
"""
import argparse, json, os, sqlite3, sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
MATRIX_HELP = "Enter the typical total annual amount paid for each allowance (£). Leave a row blank where you don't offer it."
CHOICE_HELP = "Select the option that best describes your organisation."
STALE_YESNO = "select yes or no"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute("SELECT id,type,short_description,help_text,options_json,matrix_json "
                             "FROM questions WHERE status='active'"))
    plan = []  # (id, label, old, new)

    for r in rows:
        # (1) the £ matrix with select-style help
        if r["id"] == "a7ed418e-b057-4b70-ab58-31e897b7c1b6" and r["help_text"] != MATRIX_HELP:
            plan.append((r["id"], r["short_description"], r["help_text"], MATRIX_HELP))
        # (2) yes_no with >2 options still saying "Select Yes or No"
        if r["type"] == "yes_no":
            try:
                nopts = len(json.loads(r["options_json"] or "[]"))
            except Exception:
                nopts = 0
            if nopts > 2 and STALE_YESNO in (r["help_text"] or "").lower():
                plan.append((r["id"], r["short_description"], r["help_text"], CHOICE_HELP))

    print("help-text content fix — %s | %d change(s)\n" % ("WRITE" if args.write else "DRY RUN", len(plan)))
    for qid, label, old, new in plan:
        print("  %s" % (label or qid)[:60])
        print("     old: %r" % old)
        print("     new: %r\n" % new)
    if not plan:
        print("nothing to change (already corrected)."); return
    if not args.write:
        print("DRY RUN — pass --write to apply."); return
    for qid, label, old, new in plan:
        conn.execute("UPDATE questions SET help_text=? WHERE id=?", (new, qid))
    conn.commit()
    print("WRITTEN: %d help_text values corrected (metadata only; answers/aggregates untouched)." % len(plan))


if __name__ == "__main__":
    main()
