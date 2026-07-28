# -*- coding: utf-8 -*-
"""migrate_aff_t2_pins.py — AFF TIER-2 APPLY, Part 2 (SCORING/CONFIG class; David-ruled
2026-07-27): the 5 CONFIRM pins + the RED_TERM_01 tie-at-top AMEND.

  CONFIRM x5 (authored direction := the regex's current d; maps untouched; rendered scores
  BYTE-IDENTICAL, asserted per metric — a pin that moves any score is a defect):
    EXT_REW_GAP_001 +1 (GAP_002/007 consistency) · REW_PAY_018 +1 · REW_PAY_003 -1 +
    PROP_8e0b6316 -1 (the frequency pair — different constructs, pair-coherence recorded) ·
    REW_INC_071 -1 CONFIRM Yes-best, ruled with INC_070's Tier-3 map; the external-authority
    grounds ride in `_tier2_note` (Investment Association Principles: malus/clawback as
    governance expectation).
  AMEND x1: RED_TERM_01 tie-at-top — Statutory:0 / Enhanced formula:100 / Discretionary:100
  (unscored NA rungs untouched), direction authored +1. The verdict asserts the uncontested
  axis (beyond-statutory > statutory) and stays silent on the contested top-end order.
  THIS ONE MOVES VERDICTS BY DESIGN (the 100/50 Enhanced-vs-Discretionary gap collapses) —
  flips enumerated at rehearsal.

Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
IA_NOTE = ("CONFIRM Yes-best (David 2026-07-27, ruled with INC_070's Tier-3 map): the Investment "
           "Association Principles treat malus/clawback as governance expectation, so 'above "
           "market' reads as governance-maturity, consistent with the confirmed governance-ladder bulk")
PINS = {  # qid -> (direction, expected current-map drift guard)
    "EXT_REW_GAP_001": (1, {"NO_DEDICATED_RECOGNITION_BUDGET": 0.0, "UP_TO_25": 25.0, "26_50": 50.0,
                            "51_100": 75.0, "MORE_THAN_100": 100.0}),
    "REW_PAY_018": (1, {"NO_MINIMUM": 0.0, "1_HOUR": 33.33, "2_HOURS": 66.67, "3_HOURS_OR_MORE": 100.0}),
    "REW_PAY_003": (-1, {"QUARTERLY": 0.0, "BIANNUALLY": 25.0, "ANNUALLY": 50.0, "AD_HOC": 75.0,
                         "NOT_REVIEWED": 100.0}),
    "PROP_8e0b6316": (-1, {"ANNUALLY": 0.0, "TWICE_A_YEAR": 33.33, "QUARTERLY": 66.67,
                           "NO_REGULAR_CYCLE_AD_HOC": 100.0}),
    "REW_INC_071": (-1, {"YES": 0.0, "NO": 100.0}),
}
RT = "RED_TERM_01"
RT_OLD = {"STATUTORY_ONLY_NO_ENHANCEMENT": 0.0, "ENHANCED_REDUNDANCY_PAY_STANDARD_FORMULA": 50.0,
          "DISCRETIONARY_NEGOTIATED_CASE_BY_CASE": 100.0}
RT_NEW = {"STATUTORY_ONLY_NO_ENHANCEMENT": 0.0, "ENHANCED_REDUNDANCY_PAY_STANDARD_FORMULA": 100.0,
          "DISCRETIONARY_NEGOTIATED_CASE_BY_CASE": 100.0}


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    touched = sorted(list(PINS) + [RT])

    plans = {}
    for qid, (d, guard) in PINS.items():
        cfg = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (qid,)).fetchone()[0])
        assert "direction" not in cfg, "%s already pinned" % qid
        got = {k: float(v) for k, v in cfg["option_scores"].items()}
        assert got == guard, "%s pre-map drifted: %s" % (qid, got)
        new = dict(cfg); new["direction"] = d
        if qid == "REW_INC_071":
            new["_tier2_note"] = IA_NOTE
        # byte-identity: effective(d, map) == effective under the regex's current d (same d, same map)
        eff_old = {k: (100.0 - v if d == -1 else v) for k, v in got.items()}
        eff_new = {k: (100.0 - float(v) if d == -1 else float(v)) for k, v in new["option_scores"].items()}
        assert eff_new == eff_old, qid
        plans[qid] = new
    cfg = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (RT,)).fetchone()[0])
    assert "direction" not in cfg
    got = {k: float(v) for k, v in cfg["option_scores"].items()}
    assert got == RT_OLD, "RED_TERM_01 pre-map drifted: %s" % got
    new = dict(cfg); new["option_scores"] = dict(RT_NEW); new["direction"] = 1
    plans[RT] = new

    print("aff-t2-pins %s (db=%s) — 5 CONFIRM pins (byte-identical) + RED_TERM_01 tie-at-top AMEND (flips by design)"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    for qid in touched:
        d = plans[qid]["direction"]
        print("  %-18s dir=%+d%s" % (qid, d,
              "  map -> tie-at-top {stat:0, enhanced:100, discretionary:100}" if qid == RT else
              ("  + IA governance note" if qid == "REW_INC_071" else "")))
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_others = {r["id"]: r["scoring_config_json"] for r in c.execute("SELECT id, scoring_config_json FROM questions")
                  if r["id"] not in plans}
    cur = c.cursor()
    for qid, new in plans.items():
        cur.execute("UPDATE questions SET scoring_config_json=? WHERE id=?", (json.dumps(new, ensure_ascii=False), qid))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED"
    post_others = {r["id"]: r["scoring_config_json"] for r in c.execute("SELECT id, scoring_config_json FROM questions")
                   if r["id"] not in plans}
    assert post_others == pre_others, "non-target scoring config changed"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "pins": 5, "amend": RT,
                      "byte_identity": "asserted on the 5 (pins move authority, never output)",
                      "answers_book": "byte-identical"}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
