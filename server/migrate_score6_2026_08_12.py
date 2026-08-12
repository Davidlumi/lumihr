# -*- coding: utf-8 -*-
"""Score the six unscored 2026.x singles (David-ruled 2026-08-12, "do all of these —
every metric clearly labelled"; labelling doctrine phase 2).

Config class — scoring_config_json + is_scored on SIX question rows. ZERO answer
writes; the answers book is untouched by construction. Each metric already carries a
ruled direction (higher_is_better in BOTH questions.polarity and the mp config, all
in the Diff-15-restored market pool); only the option ladder was missing, so the
engine refused to rank them (authored-direction-is-LAW doctrine — no heuristic maps).

Ladders are ORDER-PRESERVING equal-spaced readings of each option scale (the AFF
"natural ladder" class — provision depth/readiness, not invented judgment):
  NICSHARING   Yes fully=100 · Yes partially=50 · No=0        (na: no sal-sac scheme)
  COMMCAP      Uncapped=100 · Soft cap=50 · Hard cap=0        (na: no commission plans)
  SAYEDISC     20%=100 · 10-19%=66.67 · Under 10%=33.33 · No discount=0   (+na added)
  SHAREPART    Over 50%=100 · 26-50%=66.67 · 10-25%=33.33 · Under 10%=0   (+na added)
  ETHDISREADY  Reporting-ready=100 · Analysing=66.67 · Reviewing=33.33 · Not started=0
  GPGNAMING    Prepared=100 · Reviewing supplier data=50 · Not started=0
SAYEDISC + SHAREPART lacked na_codes for their "Not applicable" option — added, so an
N/A answer routes to disclosed absence (never a fake 0-rank).

Asserts: every ladder label resolves to a live option code (no guessed codes); every
na label resolves; answers table row-count + book hash unchanged; is_scored flips 0→1
on exactly these six. Re-aggregate after (python3 aggregate.py) so payload _scores
distributions include the newly-scored metrics.
"""
import json, sqlite3, hashlib, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

LADDERS = {
    "REW264_PEN_NICSHARING": {"Yes fully": 100.0, "Yes partially": 50.0, "No": 0.0},
    "REW265_INC_COMMCAP": {"Uncapped": 100.0, "Soft cap or decelerator": 50.0, "Hard cap": 0.0},
    "REW265_INC_SAYEDISC": {"20% (maximum)": 100.0, "10–19%": 66.67, "Under 10%": 33.33, "No discount": 0.0},
    "REW265_INC_SHAREPART": {"Over 50%": 100.0, "26–50%": 66.67, "10–25%": 33.33, "Under 10%": 0.0},
    "REW263_GOV_ETHDISREADY": {"Reporting-ready": 100.0, "Analysing gaps": 66.67, "Reviewing data readiness": 33.33, "Not started": 0.0},
    "REW265_GOV_GPGNAMING": {"Prepared": 100.0, "Reviewing supplier data": 50.0, "Not started": 0.0},
}
ADD_NA = {   # options that MUST route to N/A (disclosed absence), added where missing
    "REW265_INC_SAYEDISC": ["Not applicable"],
    "REW265_INC_SHAREPART": ["Not applicable"],
}

def book_hash(conn):
    h = hashlib.sha256()
    for r in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers ORDER BY org_id, question_id, matrix_row_id"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()[:16]

def main():
    conn = get_conn()
    before_hash = book_hash(conn)
    before_n = conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    changed = []
    for qid, ladder in LADDERS.items():
        row = conn.execute("SELECT id, is_scored, scoring_config_json, options_json, polarity FROM questions WHERE id=?", (qid,)).fetchone()
        assert row is not None, qid
        assert row["is_scored"] == 0, f"{qid} already scored — refusing (stale run?)"
        assert row["polarity"] == "higher_is_better", f"{qid} polarity {row['polarity']} != ruled higher_is_better"
        opts = json.loads(row["options_json"] or "[]")
        by_label = {o["label"]: o["code"] for o in opts}
        cfg = json.loads(row["scoring_config_json"] or "{}")
        option_scores = {}
        for label, score in ladder.items():
            assert label in by_label, f"{qid}: ladder label {label!r} not in live options {list(by_label)}"
            option_scores[by_label[label]] = score
        na = set(cfg.get("na_codes") or [])
        for label in ADD_NA.get(qid, []):
            assert label in by_label, f"{qid}: na label {label!r} not in live options"
            na.add(by_label[label])
        # every live option is either laddered or NA-routed — nothing silently unscorable
        unrouted = [o["label"] for o in opts if o["code"] not in option_scores and o["code"] not in na]
        assert not unrouted, f"{qid}: options neither laddered nor NA-routed: {unrouted}"
        cfg.update({"scoring_method": "option_scores", "curve_type": "linear",
                    "option_scores": option_scores, "na_codes": sorted(na),
                    "direction": 1,   # authored direction is LAW (AFF engine): 100 = best, higher = above market
                    "_score6_2026_08_12": "labelling doctrine — ladder authored per David 'do all of these'"})
        conn.execute("UPDATE questions SET scoring_config_json=?, is_scored=1 WHERE id=?", (json.dumps(cfg), qid))
        changed.append(qid)
    assert book_hash(conn) == before_hash and conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == before_n, "ANSWERS BOOK MOVED — aborting"
    conn.commit()
    print(f"scored {len(changed)}: {', '.join(changed)}")
    print(f"answers book untouched ({before_n} rows, hash {before_hash})")

if __name__ == "__main__":
    main()
