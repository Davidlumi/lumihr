# -*- coding: utf-8 -*-
"""migrate_diff20.py — Diff 20 data companions to the engine mechanisms (David 2026-07-24). Scoped so
the ENGINE fix class and the one CLASSIFICATION companion commit separately.

  --scope scoring    is_scored=1 + scoring_config on the 6 HOLDs (the minimal data companions of the
                     new aggregate/positions mechanisms):
                       matrix_count_yes/breadth  : REW_BEN_139, REW_PAY_109, REW_PAY_020
                       matrix_count_yes/range_max: REW_INC_133
                       max_of_ticked             : REW26_PAY_JOBEVAL_COVERAGE (ladder All100/Some66/Senior33/None0)
                       ordinal_select            : REW_Q524161 (authored band->ordinal map, "More than 16 weeks"=9 top)
  --scope q524161dir CLASSIFICATION completion of Q524161's held Diff-18 OUTLIER ruling: mp_config
                     direction neutral->higher_is_better + DB polarity neutral->higher_is_better
                     (longer employer notice = above market, as ruled). Separate fix class.
Guards: dry-run default; live needs --write --confirmed-by-david; throwaway config scope needs --mp-out.
"""
import argparse, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
Q524161 = "REW_Q524161"

ORDINAL_MAP = {"1 week": 1, "2 weeks": 2, "3 weeks": 3, "4 weeks": 4, "6 weeks": 5,
               "8 weeks": 6, "12 weeks": 7, "16 weeks": 8, "More than 16 weeks": 9}
SCORING = {
    "REW_BEN_139": {"scoring_method": "matrix_count_yes", "mode": "breadth"},
    "REW_PAY_109": {"scoring_method": "matrix_count_yes", "mode": "breadth"},
    "REW_PAY_020": {"scoring_method": "matrix_count_yes", "mode": "breadth"},
    "REW_INC_133": {"scoring_method": "matrix_count_yes", "mode": "range_max"},
    "REW26_PAY_JOBEVAL_COVERAGE": {"scoring_method": "max_of_ticked",
                                   "option_scores": {"ALL": 100, "SOME_FAMILIES": 66, "SENIOR_ONLY": 33, "NONE": 0}},
    Q524161: {"scoring_method": "ordinal_select", "ordinal_map": ORDINAL_MAP},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True, choices=["scoring", "q524161dir"])
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--mp-out", dest="mp_out", default=None)
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write:
        if is_live:
            if not a.confirmed:
                print("REFUSED: live needs --confirmed-by-david"); sys.exit(2)
            a.mp_out = LIVE_MP
        elif a.scope == "q524161dir" and (a.mp_out is None or os.path.abspath(a.mp_out) == LIVE_MP):
            print("REFUSED: throwaway q524161dir needs --mp-out (not live)"); sys.exit(2)
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    print("scope=%s %s (db=%s)" % (a.scope, "APPLY" if a.write else "dry-run", os.path.basename(a.db)))

    # pre-verify every scored metric's options/bands exist verbatim in the live bank
    if a.scope == "scoring":
        for q, sc in SCORING.items():
            opts = {o["label"] for o in json.loads(c.execute("SELECT COALESCE(options_json,'[]') FROM questions WHERE id=?", (q,)).fetchone()[0])}
            if sc["scoring_method"] == "max_of_ticked":
                labels = {o["label"]: o["code"] for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0])}
                for code in sc["option_scores"]:
                    assert code in set(labels.values()), "JOBEVAL code %s not in live bank" % code
            if sc["scoring_method"] == "ordinal_select":
                mj = json.loads(c.execute("SELECT COALESCE(matrix_json,'{}') FROM questions WHERE id=?", (q,)).fetchone()[0])
                bands = set((mj.get("columns") or [{}])[0].get("options") or [])
                for band in sc["ordinal_map"]:
                    assert band in bands, "Q524161 band %r not a live column option (stale map)" % band
                assert bands == set(sc["ordinal_map"]), "ordinal_map bands != live bands: %s" % (bands ^ set(sc["ordinal_map"]))
    if not a.write:
        print("dry-run — pass --write (+ --confirmed-by-david live, + --mp-out throwaway-cfg)"); c.close(); return

    cur = c.cursor()
    if a.scope == "scoring":
        for q, sc in SCORING.items():
            cur.execute("UPDATE questions SET is_scored=1, scoring_config_json=? WHERE id=?", (json.dumps(sc), q))
        c.commit()
        print(json.dumps({"applied": True, "scope": "scoring", "scored": list(SCORING)}))
    else:  # q524161dir
        cur.execute("UPDATE questions SET polarity='higher_is_better' WHERE id=?", (Q524161,))
        raw = open(LIVE_MP, "rb").read(); cfg = json.loads(raw); M = cfg["metrics"]
        assert M[Q524161].get("direction") in (None, "neutral"), "Q524161 not neutral pre-flip"
        M[Q524161]["direction"] = "higher_is_better"
        M[Q524161]["_diff20"] = "OUTLIER direction applied (held from Diff 18) — longer employer notice = above market; ordinal_select scored (Diff 20)"
        before = json.loads(raw)["metrics"]
        for qid in before:
            if qid == Q524161:
                continue
            assert before[qid] == M[qid], "non-target config changed: %s" % qid
        new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.mp_out)), suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(new_raw)
        c.commit(); os.replace(tmp, a.mp_out)
        print(json.dumps({"applied": True, "scope": "q524161dir", "config_out": os.path.basename(a.mp_out)}))
    c.close()


if __name__ == "__main__":
    main()
