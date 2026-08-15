# -*- coding: utf-8 -*-
"""RED_TERM_01 NA-flag correction, 2026-07-18 (found in the Diff-10-era 25-row base
extraction — base25_extraction_table.csv, RED_TERM_01 flags column).

One fix: in questions.options_json for RED_TERM_01 ("What redundancy pay terms does
your organisation typically offer?"), the option 'Enhanced redundancy pay (varies by
grade/tenure)' carries is_na=true while its substantive siblings are is_na=false.
It is a real answer (the org DOES offer enhanced redundancy pay), not a skip:
- master register (lumi_master_metric_register_FINAL_APPROVED.csv): live, market, ↑ —
  enhanced options are the positive pole, so a 'varies by grade/tenure' answer is
  positive-side evidence, never not-assessable;
- base25 target semantics for this row: "positive side = enhanced options; lean pole
  = 'Statutory only (no enhancement)'";
- 5 orgs answered it — is_na=true silently drops them from every is_na-honouring base
  (client real-option views, reseed-engine NA-skip base exclusions, qa_plausibility
  spine labels).
Aggregate NUMBERS do not move: select_block counts all matched options either way and
only carries is_na per option — the re-aggregate refreshes that attribute in stored
payloads.

DELIBERATELY NOT TOUCHED — scoring_config_json: na_codes keeps
ENHANCED_REDUNDANCY_PAY_VARIES_BY_GRADE_TENURE (and the option gets no option_score).
That is the scoring dimension, not the skip dimension: the option has no ruled rung on
the 0/50/100 ladder (register note: placement of the two enhanced options vs
'Discretionary' is genuinely ambiguous and NEEDS DAVID'S RULING). Removing it from
na_codes without a ruled score would mis-score those 5 orgs at 0. Consistent with
na_handling_json = exclude_from_scoring:true / exclude_from_benchmarking:false.

Zero answer writes (answers/answers_history content-hash asserted). CSV echo into
data/lumi_questions.csv (options cell). Pre-write backup via the SQLite backup API
(never cp — live WAL). Double-guarded: --write --confirmed-by-david.
"""
import csv
import hashlib
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from db import get_conn, DB_PATH     # noqa: E402

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
QID = "RED_TERM_01"
CODE = "ENHANCED_REDUNDANCY_PAY_VARIES_BY_GRADE_TENURE"
NA_CODE = "NOT_APPLICABLE_DON_T_KNOW"
REGISTER = os.path.join(ROOT, "lumi_master_metric_register_FINAL_APPROVED.csv")
QUESTIONS_CSV = os.path.join(ROOT, "data", "lumi_questions.csv")
BACKUP = os.path.join(ROOT, "lumi.db.bak_pre_redterm01_naflag_20260718")


def answers_hash(conn):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM %s "
                                "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


def main():
    conn = get_conn()

    # ---- intent verification (register is the authority) ----
    reg = {r["metric_id"]: r for r in csv.DictReader(open(REGISTER, encoding="utf-8-sig"))}
    r = reg.get(QID)
    assert r, "%s missing from master register" % QID
    assert r["status"] == "live" and r["classification"] == "market", \
        "register intent changed (%s/%s) — re-verify before flipping" % (r["status"], r["classification"])
    print("register: %s is live/market, direction %s — substantive-answer intent confirmed" % (QID, r["direction"]))

    # ---- pre-state assertions ----
    row = conn.execute("SELECT options_json, scoring_config_json, status, type FROM questions WHERE id=?",
                       (QID,)).fetchone()
    assert row and row["status"] == "active" and row["type"] == "single_select"
    opts = json.loads(row["options_json"])
    assert len(opts) == 5, "option set changed (%d) — re-verify" % len(opts)
    flags = {o["code"]: bool(o.get("is_na")) for o in opts}
    assert flags[CODE] is True, "%s already is_na=false — nothing to do" % CODE
    assert flags[NA_CODE] is True, "genuine NA option lost its flag — wider problem, stop"
    assert [c for c, f in flags.items() if f] == [CODE, NA_CODE] or \
           sorted(c for c, f in flags.items() if f) == sorted([CODE, NA_CODE]), \
        "unexpected extra is_na flags: %s" % flags
    cfg = json.loads(row["scoring_config_json"])
    assert CODE in (cfg.get("na_codes") or []) and CODE not in (cfg.get("option_scores") or {}), \
        "scoring config shape changed — the keep-na_codes decision needs re-checking"
    n_ans = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?",
                         (QID, next(o["label"] for o in opts if o["code"] == CODE))).fetchone()[0]
    print("pre-state OK: %s is_na=true (mis-set), %d org answers affected; "
          "na_codes keeps the scoring exclusion (David's ladder ruling pending)" % (CODE, n_ans))

    if not WRITE:
        print("DRY RUN — would flip is_na true->false for %s only; scoring_config_json untouched." % CODE)
        print("pass --write --confirmed-by-david to execute")
        return

    # ---- backup (SQLite backup API — cp on a live WAL db risks a torn copy) ----
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(BACKUP)
    with dst:
        src.backup(dst)
    dst.close(); src.close()
    print("backup written:", os.path.basename(BACKUP))

    h0 = answers_hash(conn)
    cfg_before = row["scoring_config_json"]

    for o in opts:
        if o["code"] == CODE:
            o["is_na"] = False
    n = conn.execute("UPDATE questions SET options_json=? WHERE id=?",
                     (json.dumps(opts), QID)).rowcount
    assert n == 1
    conn.commit()

    # ---- CSV echo (data/lumi_questions.csv options cell holds the same JSON) ----
    with open(QUESTIONS_CSV, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames
        rows = list(rdr)
    nc = 0
    for cr in rows:
        if cr.get("id") == QID and cr.get("options"):
            copts = json.loads(cr["options"])
            for o in copts:
                if o["code"] == CODE and o.get("is_na"):
                    o["is_na"] = False
                    nc += 1
            cr["options"] = json.dumps(copts)
    with open(QUESTIONS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("lumi_questions.csv echo: %d flag flipped" % nc)
    assert nc == 1, "CSV echo did not find exactly one mis-set flag"

    # ---- post verification ----
    post = conn.execute("SELECT options_json, scoring_config_json FROM questions WHERE id=?", (QID,)).fetchone()
    pflags = {o["code"]: bool(o.get("is_na")) for o in json.loads(post["options_json"])}
    assert pflags == {**flags, CODE: False}, "post-state flags wrong: %s" % pflags
    assert [c for c, f in pflags.items() if f] == [NA_CODE], "only the genuine NA option may stay flagged"
    assert post["scoring_config_json"] == cfg_before, "scoring_config_json moved — it must not"
    assert answers_hash(conn) == h0, "ANSWER TABLES MOVED — restore %s NOW" % BACKUP
    print("post-state OK: only %s is is_na; scoring config byte-identical; "
          "answers/answers_history content hash IDENTICAL" % NA_CODE)
    print("done — re-run aggregate.py, then qa_overview + qa_release (gates), then restart the app server")


if __name__ == "__main__":
    main()
