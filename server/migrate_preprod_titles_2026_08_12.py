# -*- coding: utf-8 -*-
"""Pre-prod audit batch (2026-08-12): 16 garbled display titles + one verdict re-lock.

(1) TITLES (questions.benchmark_display, DB config class, ZERO answer writes):
    a stale title-generation pass left card headings / register rows / metric-page H1s
    reading as broken English ("Gender pay gap analysis at least annually conduct",
    "For on-call arrangements, how is the allowance typically"). The underlying
    question_text is fine; only the display strings are re-authored, house noun-phrase
    style. Asserts each row still carries the EXACT garbled value (refuses on drift).

(2) RE-LOCK (data/market_position_config.json, PROP_8e0b6316): the 197-flag lift
    (880384d) exposed that this metric's authored option_scores ladder (effective:
    Annually=100 … ad hoc=0) contradicts the David-ratified ordered scale
    (ad hoc < Annually < Twice a year < Quarterly) — the grid said "Below market · P1"
    for the org that reviews pay MOST often while the ordered-outlier signal correctly
    said "top end". r3sw25 had the verdict suppressed when the metric was scored; the
    bulk lift criterion could not see the disagreement. Until David rules the ladder
    direction, the verdict is re-suppressed (disclosure layer only — pool/donut/scores
    untouched, same class as the 23 standing holds).

Asserts: answers book row-count + hash unchanged; the 16 current titles match expected.
No re-aggregation needed: display titles resolve live (library.display_title) and the
mp config is hot-reloaded on mtime.
"""
import json, sqlite3, hashlib, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

TITLES = {   # qid: (expected CURRENT garbled value, authored replacement)
    "REW_PAY_017": ("For on-call arrangements, how is the allowance typically",
                    "On-call allowance payment basis"),
    "REW_BEN_039": ("A flexible benefits platform (employees can choose/adjust benefits) operation",
                    "Flexible benefits platform"),
    "RED_PROC_01": ("Documented redundancy process application consistently",
                    "Documented redundancy process"),
    "REW_FAI_STUDY_TIME_93b6ef22": ("Paid study time provided for employees undertaking funded",
                                    "Paid study time for funded qualifications"),
    "REW_BEN_041": ("Maximum additional leave that can typically be purchased",
                    "Maximum additional leave purchasable per year"),
    "OT_03_1a68c68a": ("Time off in lieu (TOIL) offered as an alternative to paid",
                       "Time off in lieu (TOIL) as an overtime alternative"),
    "EXT_REW_GAP_004": ("A long service award scheme operation",
                        "Long service award scheme"),
    "REW_INC_131": ("Any long-term incentive or equity plans for any levels operation",
                    "Long-term incentive or equity plans"),
    "REW_INC_071": ("Clawback provisions used (recover paid awards) in defined",
                    "Clawback provisions on paid awards"),
    "REW_INC_135": ("Sales commission or commission-based incentive plans operation",
                    "Sales commission plans"),
    "REW262_GOV_ACTIONPLAN": ("Do you have a published equality action plan, and which characteristics does it ",
                              "Published equality action plan coverage"),
    "REW_PAY_006": ("External pay benchmark data when setting pay ranges or offers usage",
                    "External pay benchmark data usage"),
    "REW_FAI_079": ("Gender pay gap analysis at least annually conduct",
                    "Annual gender pay gap analysis"),
    "REW_PRO_035": ("Pay progression based on outside of the annual review and promotions",
                    "Pay progression basis outside the annual review"),
    "REW_PRO_034": ("Promotion guidelines that specify recommended salary positioning on promotion usage",
                    "Salary positioning guidelines on promotion"),
    "REW_Q534581": ("For hourly-paid roles, what pay multipliers apply by time",
                    "Hourly pay multipliers by time band"),
}

MP_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                      "market_position_config.json")
RELOCK = "PROP_8e0b6316"

def book_hash(conn):
    h = hashlib.sha256()
    for r in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers ORDER BY org_id, question_id, matrix_row_id"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()[:16]

def main():
    conn = get_conn()
    before_hash = book_hash(conn)
    before_n = conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    for qid, (expect, new) in TITLES.items():
        row = conn.execute("SELECT benchmark_display FROM questions WHERE id=?", (qid,)).fetchone()
        assert row is not None, qid
        assert row["benchmark_display"] == expect, \
            f"{qid}: current title {row['benchmark_display']!r} != expected garble — drift, refusing"
        conn.execute("UPDATE questions SET benchmark_display=? WHERE id=?", (new, qid))
    assert book_hash(conn) == before_hash and conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == before_n, \
        "ANSWERS BOOK MOVED — aborting"
    conn.commit()
    print(f"titles re-authored: {len(TITLES)} (answers book untouched: {before_n} rows, hash {before_hash})")

    cfg = json.load(open(MP_CFG))
    m = cfg["metrics"].get(RELOCK)
    assert m is not None, RELOCK
    assert m.get("_unbench_lifted"), f"{RELOCK} not carrying the 197-lift tag — wrong target?"
    assert not m.get("unbenchmarked"), f"{RELOCK} already unbenchmarked — stale run?"
    m["unbenchmarked"] = True
    m["_preprod_relock_2026_08_12"] = ("authored option_scores ladder contradicts the ratified "
                                       "ordered scale (ad hoc<Annually<Twice<Quarterly) — verdict "
                                       "re-suppressed pending David's direction ruling")
    tmp = MP_CFG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, MP_CFG)
    print(f"{RELOCK} verdict re-locked (disclosure layer; pool/donut untouched)")

if __name__ == "__main__":
    main()
