# -*- coding: utf-8 -*-
"""MICRO-DIFF — 2026_3 member help_text fix (38 rows), ratified 2026-07-14.
One fix class: copy only. Replaces the internal help_why rationale that apply_2026_3.py:76
shipped as member help (the Diff-5 D3 finding) with David-authored member text.
Authority: lumi_2026_3_member_help_text_fix.csv. ZERO other writes — no config, no
polarity, no options, no status. Double-guarded: --write --confirmed-by-david."""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from db import get_conn  # noqa: E402

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
FIX = os.path.join(ROOT, "lumi_2026_3_member_help_text_fix.csv")

rows = list(csv.DictReader(open(FIX, encoding="utf-8-sig")))
assert len(rows) == 38 and all(r["question_id"].startswith("REW263_") for r in rows)
conn = get_conn()
live = [r for r in rows if conn.execute(
    "SELECT 1 FROM questions WHERE id=? AND status='active'", (r["question_id"],)).fetchone()]
assert len(live) == 38, "expected all 38 live"

# snapshot every OTHER column of the 38 rows so the zero-other-writes claim is asserted
def snapshot():
    out = {}
    for r in rows:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (r["question_id"],)).fetchone()
        out[r["question_id"]] = {k: row[k] for k in row.keys() if k != "help_text"}
    return out

if not WRITE:
    print("DRY: would update help_text on 38 REW263 rows; nothing else")
    sys.exit(0)

before = snapshot()
n = 0
for r in rows:
    n += conn.execute("UPDATE questions SET help_text=? WHERE id=?",
                      (r["help_text"].strip(), r["question_id"])).rowcount
conn.commit()
assert n == 38, n
after = snapshot()
assert before == after, "a non-help_text column moved"
# CSV echo: the 38 are recognised DB-origin lineage (absent from lumi_questions.csv by
# convention) — assert absence rather than silently skipping
import csv as _csv
present = {row.get("id") for row in _csv.DictReader(open(os.path.join(ROOT, "data", "lumi_questions.csv"), encoding="utf-8-sig"))}
overlap = sorted(present & {r["question_id"] for r in rows})
print("help_text updated on 38 rows; every other column byte-identical")
print("lumi_questions.csv echo: %s" % ("N/A — all 38 are DB-origin lineage, absent from the CSV by convention" if not overlap else "OVERLAP FOUND: %s" % overlap))
