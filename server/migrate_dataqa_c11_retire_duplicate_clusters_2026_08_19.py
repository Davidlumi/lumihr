#!/usr/bin/env python3
"""Data QA class 11 — retire the duplicate clusters found by the plain-English sweep
(2026-08-19, David's ruling: "keep the richest scale, retire the rest").

Reading all 332 question texts turned up six clusters asking one practice more than once,
usually on different scales — which is worse than a plain duplicate, because a member can
answer them inconsistently and two cards then report different numbers for the same practice.

Six retirements, each against the surviving question that measures it better:

  PAYTR_01_42eae7ec          Yes/No adverts            -> REW_FAI_089  (All/Some/No)
  REW262_GOV_PAYINADVERTS    Never/Some/All adverts    -> REW_FAI_089  (David's pick: keep
                                                          the Enhanced-tier scored one)
  PAYTR_02_131bd412          Yes/No ranges visible     -> REW_FAI_088  (Yes/Partial/No)
  REW262_PAY_CANCELLEDSHIFT  Yes/No/NA, unscored       -> REW_FAI_CANCEL_1bbcc629
                                                          (full shift / partial / no)
  REW265_GOV_TRS             3-point, unscored         -> PROP_674db2fc (6-point, scored)
  REW262_PAY_GUARANTEEDHRS   the ERA duplicate         -> REW263_PAY_GUARHRSAVG, whose text
                                                          names both the population
                                                          (zero-/low-hours) and the ERA basis
                                                          (reference-period average hours)

REW_FAI_MIN_HOURS_8518a543 is NOT retired. It asks whether hourly roles have a contractual
minimum, which is a different fact from whether you proactively offer guaranteed hours after
a reference period — David's ruling.

WHAT THIS COSTS, because it is not nothing. Three of the six carry GRADE-A register marginals
with CIPD citations:

    PAYTR_01                 0.40  CIPD Pay, Performance and Transparency 2024 (n=832)
    REW262_GOV_PAYINADVERTS  0.53  same source
    PAYTR_02                 0.40  same source

Their surviving questions already sit on the same prevalence — REW_FAI_089 is at 0.533
against that 0.53, and REW_FAI_088 is at 0.356 against that 0.40 — so no NUMBER is lost. But
the anchors themselves stay attached to retired questions and stop constraining anything.
The entries are deliberately left in generated_marginals.json rather than deleted, because
reseed_engine.py consumes target_share in the marginal branch and removing an entry silently
changes a future re-seed. Re-pointing them at the survivors is a register edit and therefore
a separate ruling — flagged in DATA_ISSUES_2026-08-19.md, not done here.

REW26_WEL_FINWELL IS DELIBERATELY NOT RETIRED, against the general rule. David's rule would
send it to REW263_WEL_FINWELL (3-point, richer), and the prevalence matches almost exactly
(0.6333 frozen vs 0.633 achieved on the survivor). But it is SETTLED-FROZEN — tier 1, 0.1pp
tolerance — carrying a full distribution, a documented 2026-07-16 G7 re-freeze, a 2026-08-14
re-ratification at n=270, and a note that its marginal is retained specifically because
reseed_engine reads it. Retiring it is a re-freeze, not a de-duplication. Put back to David.

Seed answers deleted, per the standing ruling and the Diff 14 precedent; answers_history keeps
the pre-retire snapshot. Status flipped in the DB and in data/lumi_questions.csv so it survives
a reseed.

Dry-run by default. Writes only with:  --write --confirmed-by-david
Pass --skip-csv on a throwaway trial (the CSV is shared repo state, not per-database).
Afterwards: aggregate.run_snapshot(1), then gen_refresh_register.py.
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
    "PAYTR_01_42eae7ec": "duplicate of REW_FAI_089 (pay in adverts) on a coarser Yes/No "
                         "scale; David 2026-08-19",
    "REW262_GOV_PAYINADVERTS": "duplicate of REW_FAI_089 (pay in adverts); David chose the "
                               "Enhanced-tier scored version, 2026-08-19",
    "PAYTR_02_131bd412": "duplicate of REW_FAI_088 (ranges visible to employees) on a "
                         "coarser Yes/No scale; David 2026-08-19",
    "REW262_PAY_CANCELLEDSHIFT": "duplicate of REW_FAI_CANCEL_1bbcc629 (cancelled shifts), "
                                 "which distinguishes full from partial payment and is "
                                 "scored; David 2026-08-19",
    "REW265_GOV_TRS": "duplicate of PROP_674db2fc (total reward statements), which captures "
                      "provision and access on a 6-point scale; David 2026-08-19",
    "REW262_PAY_GUARANTEEDHRS": "duplicate of REW263_PAY_GUARHRSAVG (ERA guaranteed hours), "
                                "whose text names the population and the reference-period "
                                "basis; David 2026-08-19",
}


def csv_retire(qid):
    with open(CSV_PATH, "rb") as f:
        raw = f.read()
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        header = next(csv.reader([f.readline()]))
    s_idx = header.index("status")
    start = raw.find((qid + ",").encode("utf-8"))
    if start == -1:
        return None, "CSV row not found (DB-origin question)"
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
        r = conn.execute("SELECT id, status, text FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            print("   UNKNOWN %s\n" % qid)
            continue
        if r["status"] == "retired":
            print("   %s already retired\n" % qid)
            continue
        n_ans = conn.execute("SELECT COUNT(*) c FROM answers WHERE question_id=?",
                             (qid,)).fetchone()["c"]
        print("-- %s --" % qid)
        print("   %s" % (r["text"] or "")[:78])
        print("   why    : %s" % why)
        print("   answers: %d -> 0 (deleted; history keeps the snapshot)" % n_ans)
        if WRITE:
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) "
                         "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,"
                         "datetime('now') FROM answers WHERE question_id=?", (qid,))
            conn.execute("DELETE FROM answers WHERE question_id=?", (qid,))
            conn.execute("UPDATE questions SET status='retired', is_scored=0 WHERE id=?", (qid,))
            conn.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (qid,))
        if not SKIP_CSV:
            new_raw, note = csv_retire(qid)
            print("   CSV    : %s" % note)
            if WRITE and new_raw is not None:
                with open(CSV_PATH, "wb") as f:
                    f.write(new_raw)
        print()

    print("HELD BACK (not retired): REW26_WEL_FINWELL — settled-frozen tier 1, full frozen")
    print("   distribution, documented G7 re-freeze and a reseed dependency. Needs a ruling.")
    if WRITE:
        conn.commit()
        print("\ncommitted.  next: aggregate.run_snapshot(1) then gen_refresh_register.py")
    else:
        print("\nRe-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
