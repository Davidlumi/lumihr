#!/usr/bin/env python3
"""Data QA class 1 — options that duplicate the NA state (2026-08-19, David's review).

REW263_BEN_DENTAL and REW263_BEN_CICOVER each carry BOTH "Not offered" AND "Not applicable".
An organisation without the cover answers "Not applicable" and is excluded from the base —
the card says so in its own footer, "of organisations with dental cover". "Not offered" is
therefore a duplicate of the NA state that no respondent in the base can ever select, and it
renders as a permanent 0% row. David, on the dental card: "Numbers are wrong."

The fix is REMOVAL, not seeding. Seeding it would invent organisations answering a question
they were excluded from — a worse lie than the 0%.

Nothing else changes: no answer is edited, no count moves, and both questions keep their NA
option, which is where "we don't offer this" already lives.

Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import json, os, sqlite3, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
TARGETS = {"REW263_BEN_DENTAL": "Not offered", "REW263_BEN_CICOVER": "Not offered"}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    changed = 0
    for qid, label in TARGETS.items():
        r = conn.execute("SELECT options_json, text FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            print("  SKIP %s — not in this bank" % qid)
            continue
        opts = json.loads(r["options_json"] or "[]")
        keep = [o for o in opts
                if (o.get("label") if isinstance(o, dict) else str(o)).strip().lower() != label.lower()]
        if len(keep) == len(opts):
            print("  SKIP %s — %r already absent" % (qid, label))
            continue
        # never leave a question without its NA escape hatch
        has_na = any("not applicable" in (o.get("label") if isinstance(o, dict) else str(o)).lower()
                     for o in keep)
        if not has_na:
            print("  REFUSE %s — removing %r would leave no NA option" % (qid, label))
            continue
        # and never remove an option somebody actually selected
        used = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=? AND value LIKE ?",
                            (qid, "%" + label + "%")).fetchone()["c"]
        if used:
            print("  REFUSE %s — %d stored answers use %r" % (qid, used, label))
            continue
        print("  %s  %s" % (qid, r["text"][:60]))
        print("      remove %r · %d options -> %d · 0 answers affected"
              % (label, len(opts), len(keep)))
        if WRITE:
            conn.execute("UPDATE questions SET options_json=? WHERE id=?",
                         (json.dumps(keep, ensure_ascii=False), qid))
        changed += 1
    if WRITE and changed:
        conn.commit()
        print("\ncommitted %d question(s). Re-run the snapshot build so the card stops "
              "rendering the removed row." % changed)
    else:
        print("\n%d question(s) would change. Re-run with --write --confirmed-by-david to apply."
              % changed)
    conn.close()


if __name__ == "__main__":
    main()
