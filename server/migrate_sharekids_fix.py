#!/usr/bin/env python3
"""Share-family child repair (PH1-SEED-SHAREKIDS-FIX; parents at a8cd52e).

27 gate-derived instances -> the child's own NA form, in the same no-share orgs
whose parents moved to structural NA. DATA-ONLY BY RULING: apply_2026_5.py's wired
draw (:113-115) already conditions each child on the live parent answer, so a
reseed against the repaired parents redraws all 27 to NA (proven 27/27 at
rehearsal). The writer is deliberately untouched.

Manifest embedded (step-4a precedent): (qid, org_id, expected current value,
target NA form), derived at execution time from generated_marginals.json's own
pair dicts — the gate's rule, not a reimplementation of it.
"""
import os, sqlite3, sys
DB = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))
write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
NON = ("Public Sector Body", "Charity / Non-profit", "Mutual / Co-operative", "Partnership / LLP")
MANIFEST = [
    ('REW265_INC_SHAREPART', '5196bbd1-810b-446d-955a-5612c144cc31',
     'Under 10%', 'Not applicable'),
    ('REW265_INC_SHAREPART', '5c5370ac-a67c-4412-9617-e7837a8359cf',
     'Under 10%', 'Not applicable'),
    ('REW265_INC_SHAREPART', '75c9adff-1905-4a5d-9c73-5f60753df7d9',
     'Over 50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', '9c75f1e5-f56c-441c-8b62-e1c0398573f2',
     '10–25%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'b2819136-1b40-4004-a48a-7e3fbd885b9e',
     '10–25%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'b6eb7e35-06d0-41bb-8ff2-bc91c73d104d',
     '10–25%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'bd3aa717-8c5f-4ffc-932a-91d4a2cefeb5',
     'Over 50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'be6aac22-d8d0-4df4-bfeb-a4866e87c686',
     '26–50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'ce1a9bf8-4729-4640-9de4-72cda8b79f3c',
     '26–50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'd63e3c44-f0f8-4b74-a684-ca12a1cf5e52',
     '26–50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'da1d4830-1f41-445a-a759-50c1144a5d2e',
     '26–50%', 'Not applicable'),
    ('REW265_INC_SHAREPART', 'fe6ac321-50d9-4798-b422-fdd82253f782',
     '10–25%', 'Not applicable'),
    ('REW265_INC_SAYEDISC', '5196bbd1-810b-446d-955a-5612c144cc31',
     'No discount', 'Not applicable'),
    ('REW265_INC_SAYEDISC', '5c5370ac-a67c-4412-9617-e7837a8359cf',
     'Under 10%', 'Not applicable'),
    ('REW265_INC_SAYEDISC', '75c9adff-1905-4a5d-9c73-5f60753df7d9',
     '20% (maximum)', 'Not applicable'),
    ('REW265_INC_SAYEDISC', '9c75f1e5-f56c-441c-8b62-e1c0398573f2',
     '20% (maximum)', 'Not applicable'),
    ('REW265_INC_SAYEDISC', 'b2819136-1b40-4004-a48a-7e3fbd885b9e',
     '10–19%', 'Not applicable'),
    ('REW265_INC_SAYEDISC', 'b6eb7e35-06d0-41bb-8ff2-bc91c73d104d',
     '10–19%', 'Not applicable'),
    ('REW265_INC_SAYEDISC', 'bd3aa717-8c5f-4ffc-932a-91d4a2cefeb5',
     '20% (maximum)', 'Not applicable'),
    ('REW265_INC_SAYEDISC', 'da1d4830-1f41-445a-a759-50c1144a5d2e',
     '20% (maximum)', 'Not applicable'),
    ('REW265_INC_SIPELEM', '75c9adff-1905-4a5d-9c73-5f60753df7d9',
     'Partnership shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'bd3aa717-8c5f-4ffc-932a-91d4a2cefeb5',
     'Partnership shares;Matching shares;Dividend shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'be6aac22-d8d0-4df4-bfeb-a4866e87c686',
     'Partnership shares;Matching shares;Dividend shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'ce1a9bf8-4729-4640-9de4-72cda8b79f3c',
     'Free shares;Partnership shares;Matching shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'd63e3c44-f0f8-4b74-a684-ca12a1cf5e52',
     'Partnership shares;Matching shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'da1d4830-1f41-445a-a759-50c1144a5d2e',
     'Matching shares;Free shares', 'No SIP operated'),
    ('REW265_INC_SIPELEM', 'fe6ac321-50d9-4798-b422-fdd82253f782',
     'Matching shares', 'No SIP operated'),
]
assert len(MANIFEST) == 27
conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
for qid, org, expect, na in MANIFEST:
    row = conn.execute(
        "SELECT a.value, o.ownership_type, (SELECT value FROM answers WHERE "
        "question_id='REW264_INC_SHAREPLAN' AND org_id=a.org_id AND snapshot_id=1) AS parent "
        "FROM answers a JOIN orgs o ON o.org_id=a.org_id WHERE a.question_id=? AND a.org_id=? "
        "AND a.snapshot_id=1 AND (a.matrix_row_id IS NULL OR a.matrix_row_id='')", (qid, org)).fetchone()
    assert row and row["value"] == expect, (qid, org, row and row["value"])
    assert row["ownership_type"] in NON and (row["parent"] or "").startswith("Not applicable")
print("[kidsfix] 27/27 pre-asserted: substantive child value + no-share ownership + parent NA")
if not write:
    print("[kidsfix] DRY RUN — no write."); sys.exit(0)
cur = conn.cursor()
for qid, org, _e, na in MANIFEST:
    cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND snapshot_id=1 "
                "AND (matrix_row_id IS NULL OR matrix_row_id='')", (na, qid, org))
    assert cur.rowcount == 1, (qid, org)
conn.commit()
print("[kidsfix] POST: total answer rows %d (updates only)"
      % conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0])
print("[kidsfix] PASS")
