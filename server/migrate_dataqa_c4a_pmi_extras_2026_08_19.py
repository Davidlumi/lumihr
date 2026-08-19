#!/usr/bin/env python3
"""Data QA class 4a — widen the PMI extras list (2026-08-19, David: "more to the list?").

REW265_BEN_PMICOMP asks what a PMI scheme includes beyond standard cover and offers seven
options. Four common UK extras are missing, so a member whose scheme has them can only
answer by omission — and the benchmark cannot show how common they are.

Added, with the prevalence each is seeded at (of the 188 PMI-holding organisations):

  Virtual / digital GP access      68%  near-universal in current UK schemes; its absence
                                        from the list was the conspicuous one
  Cancer care pathway              44%  enhanced/private cancer cover, often the most
                                        valuable extra and frequently bought separately
  Menopause & women's health       19%  fast-growing as a distinct extra; newer, so lower
  Complementary therapies          26%  acupuncture/osteopathy/chiropractic, usually capped

The new options are appended AFTER the existing substantive ones and BEFORE "None of these
— core cover only", so the exclusive option stays last where a reader expects it.

Seeding appends tokens to a deterministic subset and never touches an organisation that
answered "None of these", which would contradict itself. Existing counts are unchanged: this
only adds, so every current percentage on the card stays exactly as it is.

Deterministic (fixed seed, org_ids sorted), history-appending.
Run aggregate.run_snapshot(1) afterwards.

Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import json
import os
import random
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SEED = 20260819
QID = "REW265_BEN_PMICOMP"
EXCLUSIVE = "None of these — core cover only"

NEW = [
    ("Virtual / digital GP access", "VIRTUAL_DIGITAL_GP_ACCESS", 0.68),
    ("Cancer care pathway", "CANCER_CARE_PATHWAY", 0.44),
    ("Complementary therapies", "COMPLEMENTARY_THERAPIES", 0.26),
    ("Menopause & women's health support", "MENOPAUSE_WOMENS_HEALTH_SUPPORT", 0.19),
]


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))

    r = conn.execute("SELECT options_json FROM questions WHERE id=?", (QID,)).fetchone()
    if not r:
        print("  %s not in this bank" % QID)
        return
    opts = json.loads(r["options_json"] or "[]")
    have = {(o.get("label") or "").strip().lower() for o in opts}
    add = [(l, c, p) for l, c, p in NEW if l.strip().lower() not in have]
    print("-- option list --")
    if not add:
        print("   all four already present")
    else:
        keep = [o for o in opts if (o.get("label") or "") != EXCLUSIVE]
        tail = [o for o in opts if (o.get("label") or "") == EXCLUSIVE]
        nxt = max([o.get("order") or 0 for o in opts] or [0])
        newopts = []
        for i, (lab, code, _) in enumerate(add, 1):
            newopts.append({"code": code, "label": lab, "order": nxt + i, "is_na": False})
            print("   + %-38s %s" % (lab, code))
        merged = keep + newopts + tail
        for i, o in enumerate(merged, 1):
            o["order"] = i
        print("   %d options -> %d ('%s' stays last)" % (len(opts), len(merged), EXCLUSIVE))
        if WRITE:
            conn.execute("UPDATE questions SET options_json=? WHERE id=?",
                         (json.dumps(merged, ensure_ascii=False), QID))

    print("\n-- seeding (append-only; never touches a 'None of these' respondent) --")
    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (QID,)).fetchall()
    base = [r2 for r2 in rows if EXCLUSIVE not in (r2["value"] or "")]
    print("   %d respondents · %d eligible (excludes %d on core-cover-only)"
          % (len(rows), len(base), len(rows) - len(base)))
    rnd = random.Random(SEED)
    updates = {}
    for lab, _code, pct in NEW:
        k = int(round(pct * len(rows)))
        cand = [r2 for r2 in base if lab not in (r2["value"] or "")]
        if len(cand) < k:
            print("   REFUSE %-38s need %d, only %d eligible" % (lab, k, len(cand)))
            continue
        for r2 in rnd.sample(cand, k):
            updates.setdefault(r2["org_id"], set(
                p.strip() for p in (r2["value"] or "").split(";") if p.strip())).add(lab)
        print("   %-38s %3d of %d  (%.0f%%)" % (lab, k, len(rows), 100.0 * k / len(rows)))

    if WRITE:
        for org, toks in updates.items():
            val = "; ".join(sorted(toks))
            conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (val, org, QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                         (org, QID, val))
        conn.commit()
        print("\n   WROTE %d organisations. Now rebuild: "
              "python3 -c \"import aggregate; aggregate.run_snapshot(1)\"" % len(updates))
    else:
        print("\n   %d organisations would change. Re-run with --write --confirmed-by-david."
              % len(updates))
    conn.close()


if __name__ == "__main__":
    main()
