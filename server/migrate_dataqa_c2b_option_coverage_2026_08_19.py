#!/usr/bin/env python3
"""Data QA class 2b — the remaining reachable options nobody was ever assigned (2026-08-19).

After the redundancy fix, 23 options across 16 questions still had zero respondents. They
are NOT all defects, and this script is as much about what it refuses to touch as what it
changes.

LEFT AT ZERO ON PURPOSE — the data is right and seeding would make it wrong:

  PROP_36b990f9  "<3%"                    below the auto-enrolment minimum; a qualifying
                                          scheme cannot be there
  REW_BEN_SICK_001 "No sick pay provided" SSP is a statutory obligation in the UK
  REW264_INC_EMICSOP "Both"               EMI and CSOP are near-exclusive by company size
                                          (EMI is gross-assets capped)
  REW265_INC_SIPELEM "Dividend shares"    n=11; a zero here is small-sample, not a gap
  REW_PAY_016 "None"                      multi-select where every respondent pays something

REMOVED — the option duplicates the question's own NA state, so it can never be non-zero:

  REW263_INC_DEFERRAL "No deferral"       the question is "FOR DEFERRED BONUSES, what is the
                                          typical deferral period"; an org without deferral
                                          answers the separate "Not applicable". Same defect
                                          as the dental/critical-illness cards.

SEEDED — reachable options with a real-world prevalence that the generator never produced.
Single-select moves take respondents from an over-weighted neighbouring option so n is
conserved exactly; multi-select appends add a token to a subset. Prevalences are modelled on
UK practice, not measured — the same basis as the rest of this seeded bank.

Deterministic (fixed seed, org_ids sorted), count-conserving, history-appending.
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

# (question, take-from label, give-to label, how many) — single-select, n-conserving
MOVES = [
    ("REW_BEN_REM_PAY_001", "Base pay is protected", "Base pay may be adjusted over time", 14),
    ("REW_BEN_REM_PAY_001", "Base pay is protected", "Base pay is adjusted immediately", 6),
    ("REW_BEN_048", "50–65%", "<50%", 5),
    ("RED_PAY_01", "Includes regular overtime", "Includes variable pay (bonus/commission) where applicable", 8),
    ("RED_PAY_01", "Average earnings over a reference period", "Other", 3),
    ("REW_BEN_100", "10–24%", "<10%", 9),
    ("REW_BEN_041", "6–10 days", "11+ days", 4),
    ("REW_BEN_044", "Grade/level restricted", "Service length requirement", 16),
    ("REW_BEN_REM_PAY_005", "Premiums apply to some remote roles", "Both premiums and discounts apply", 7),
    ("REW263_TIME_IVF", "None", "2-3 cycles", 2),
    ("REW263_TIME_IVF", "None", "Unlimited/uncapped", 1),
    ("PROP_3d4fc4e7", "25%–49%", "Not measured", 12),
]

# (question, token to append, how many orgs) — multi-select, additive
APPENDS = [
    ("REW_PAY_016", "Mobile/phone allowance", 32),
    ("REW_PAY_016", "Acting-up allowance", 21),
    ("REW_PAY_016", "Homeworking allowance", 16),
    ("REW_PAY_016", "Market scarcity allowance", 11),
]

# (question, exclusive token, how many orgs) — multi-select, REPLACES the whole answer
EXCLUSIVE = [
    ("PROP_aa4061d5", "No formal measurement", 18),
]

REMOVE_OPTION = [("REW263_INC_DEFERRAL", "No deferral")]


def hist(conn, org, qid, val):
    conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,"
                 "value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))", (org, qid, val))


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)
    n_moved = n_app = n_exc = n_rem = 0

    print("-- single-select moves (n conserved) --")
    for qid, src, dst, k in MOVES:
        rows = conn.execute("SELECT org_id FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' AND value=? ORDER BY org_id", (qid, src)).fetchall()
        pool = [r["org_id"] for r in rows]
        if len(pool) < k:
            print("   REFUSE %-22s %r has only %d, need %d" % (qid, src[:28], len(pool), k))
            continue
        pick = rnd.sample(pool, k)
        print("   %-22s %-32s -> %-34s %d" % (qid, src[:32], dst[:34], k))
        if WRITE:
            for org in pick:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (dst, org, qid))
                hist(conn, org, qid, dst)
        n_moved += k

    print("\n-- multi-select appends (adds a token, n unchanged) --")
    for qid, token, k in APPENDS:
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        cand = [r for r in rows if token not in (r["value"] or "")
                and (r["value"] or "").strip() not in ("", "None", "Not applicable")]
        if len(cand) < k:
            print("   REFUSE %-22s only %d candidates for %r" % (qid, len(cand), token))
            continue
        pick = rnd.sample(cand, k)
        print("   %-22s append %-30s to %d of %d orgs" % (qid, token[:30], k, len(rows)))
        if WRITE:
            for r in pick:
                parts = [p.strip() for p in (r["value"] or "").split(";") if p.strip()]
                parts.append(token)
                val = "; ".join(sorted(set(parts)))
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (val, r["org_id"], qid))
                hist(conn, r["org_id"], qid, val)
        n_app += k

    print("\n-- multi-select exclusive (replaces the answer) --")
    for qid, token, k in EXCLUSIVE:
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        cand = [r for r in rows if token not in (r["value"] or "")]
        if len(cand) < k:
            print("   REFUSE %-22s only %d candidates" % (qid, len(cand)))
            continue
        pick = rnd.sample(cand, k)
        print("   %-22s set %-30s exclusively on %d of %d orgs" % (qid, token[:30], k, len(rows)))
        if WRITE:
            for r in pick:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (token, r["org_id"], qid))
                hist(conn, r["org_id"], qid, token)
        n_exc += k

    print("\n-- unreachable option removal --")
    for qid, label in REMOVE_OPTION:
        r = conn.execute("SELECT options_json FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            print("   SKIP %s — not in this bank" % qid)
            continue
        opts = json.loads(r["options_json"] or "[]")
        keep = [o for o in opts
                if (o.get("label") if isinstance(o, dict) else str(o)).strip().lower() != label.lower()]
        used = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=? AND value=?",
                            (qid, label)).fetchone()["c"]
        has_na = any("not applicable" in (o.get("label") if isinstance(o, dict) else str(o)).lower()
                     for o in keep)
        if len(keep) == len(opts):
            print("   SKIP %s — %r already absent" % (qid, label))
        elif used:
            print("   REFUSE %s — %d answers use %r" % (qid, used, label))
        elif not has_na:
            print("   REFUSE %s — would leave no NA option" % qid)
        else:
            print("   %-22s remove %r · %d options -> %d · 0 answers affected"
                  % (qid, label, len(opts), len(keep)))
            if WRITE:
                conn.execute("UPDATE questions SET options_json=? WHERE id=?",
                             (json.dumps(keep, ensure_ascii=False), qid))
            n_rem += 1

    print("\n%d moved · %d appended · %d set exclusively · %d option(s) removed"
          % (n_moved, n_app, n_exc, n_rem))
    if WRITE:
        conn.commit()
        print("committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
