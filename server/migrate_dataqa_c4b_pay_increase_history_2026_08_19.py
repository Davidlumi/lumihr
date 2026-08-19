#!/usr/bin/env python3
"""Data QA class 4b — headline pay increase: history and projection (2026-08-19, David).

David: "We need to capture last three years headline pay increase and projection for 2027."
His four format decisions: rolling relative row labels, numeric % to one decimal, the MEDIAN
individual increase (not paybill), actuals scored and the projection informational.

Two findings changed the build, both ruled by David after being surfaced:

  1. The bank ALREADY asks this. PROP_634adacd — "the typical (median) base salary increase
     for eligible employees in the last completed pay review" — is exactly the chosen figure,
     but BANDED and for one year. Ruling: evolve it rather than add a duplicate, so the id,
     question_order and lineage survive and no member ever sees two cards asking one thing.

  2. Per-row scoring does not exist. market_position_config classifies per METRIC, so
     "actuals scored, projection informational" cannot sit on one four-row matrix. Ruling:
     split — a three-row matrix for the actuals, a separate numeric for next year.

WHAT HAPPENS TO THE 216 EXISTING ANSWERS. They are not discarded. Each banded answer becomes
a numeric on the "Last year" row, placed DETERMINISTICALLY INSIDE ITS OWN BAND rather than on
the midpoint — 66 organisations all landing on exactly 3.5% would be heaping, the artefact
batch b7 was written to remove. "Not measured" (2) stays out: it was is_na and still is.

The other two rows are seeded relative to each organisation's own last-year figure, declining
over time — UK settlements have eased year on year — so each organisation's trend is
internally coherent instead of three independent draws.

    two years ago   last year + 0.4 to 1.0
    this year       last year - 0.1 to 0.7   (floored at 0)
    next year       this year - 0.2 to 0.4   (floored at 0, separate question)

Comparability drops to "medium" on PROP_634adacd: banded to numeric is a real break and the
bank should say so rather than pretend the series is continuous.

Deterministic, history-appending. Run aggregate.run_snapshot(1) afterwards.
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

QID = "PROP_634adacd"
PROJ_QID = "REW266_PAY_INCREASE_NEXT"
ROWS = ["Two years ago", "Last year", "This year"]
SLUG = {"Two years ago": "two_years_ago", "Last year": "last_year", "This year": "this_year"}

# banded label -> (low, high) to place inside; None = drop (was is_na)
BANDS = {
    "0%": (0.0, 0.0),
    "0.1%–1.9%": (0.1, 1.9),
    "2.0%–2.9%": (2.0, 2.9),
    "3.0%–3.9%": (3.0, 3.9),
    "4.0%–4.9%": (4.0, 4.9),
    "5.0%+": (5.0, 7.0),
    "Not measured": None,
}

MATRIX_JSON = {
    "columns": [{"id": "percentage", "type": "percentage", "label": "Percentage (%)",
                 "placeholder": "e.g., 3.5"}],
    "help_text": "The typical (median) increase awarded to the main population in each pay "
                 "review. Leave a year blank if you did not run a review.",
    "answer_type": "percentage",
    "rows_source": "PAY_REVIEW_PERIODS_V1",
}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)

    q = conn.execute("SELECT * FROM questions WHERE id=?", (QID,)).fetchone()
    if not q:
        print("  %s not in this bank" % QID)
        return
    print("-- evolve %s --" % QID)
    print("   was : %-13s %s" % (q["type"], q["short_description"]))
    print("   now : matrix        Headline pay increase, by year")
    print("   rows: %s" % " · ".join(ROWS))

    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (QID,)).fetchall()
    conv, dropped = {}, 0
    for r in rows:
        band = BANDS.get((r["value"] or "").strip(), "?")
        if band is None:
            dropped += 1
            continue
        if band == "?":
            dropped += 1
            continue
        lo, hi = band
        conv[r["org_id"]] = round(lo if hi == lo else rnd.uniform(lo, hi), 1)
    print("   %d banded answers -> numeric inside their own band · %d dropped (was is_na)"
          % (len(conv), dropped))

    plan = {}
    for org, last in conv.items():
        two = round(min(15.0, last + rnd.uniform(0.4, 1.0)), 1)
        this = round(max(0.0, last - rnd.uniform(0.1, 0.7)), 1)
        nxt = round(max(0.0, this - rnd.uniform(-0.2, 0.4)), 1)
        plan[org] = {"two_years_ago": two, "last_year": last, "this_year": this, "_next": nxt}

    def med(k):
        v = sorted(p[k] for p in plan.values())
        return v[len(v) // 2] if v else 0
    print("   medians: two years ago %.1f%% · last year %.1f%% · this year %.1f%% · next year %.1f%%"
          % (med("two_years_ago"), med("last_year"), med("this_year"), med("_next")))

    print("\n-- new question %s (projection, informational) --" % PROJ_QID)
    exists = conn.execute("SELECT 1 FROM questions WHERE id=?", (PROJ_QID,)).fetchone()
    print("   %s · numeric %% · is_scored=0 · %d organisations seeded"
          % ("ALREADY EXISTS — will not re-create" if exists else "create", len(plan)))

    if not WRITE:
        print("\nRe-run with --write --confirmed-by-david to apply.")
        conn.close()
        return

    # 1. evolve the question
    conn.execute("""UPDATE questions SET type='matrix', unit='%', unit_type='percentage',
                    options_json='[]', matrix_json=?, matrix_rows_json=?,
                    default_chart_type='heatmap', data_display_type='matrix',
                    short_description=?, benchmark_display=?, text=?,
                    definition=?, help_text=?,
                    historical_comparability='medium', question_version='v3.0',
                    validation_json=?, tolerance_json=?
                    WHERE id=?""",
                 (json.dumps(MATRIX_JSON, ensure_ascii=False), json.dumps(ROWS, ensure_ascii=False),
                  "Headline pay increase, by year", "Headline pay increase, by year",
                  "What was the typical (median) base salary increase in each pay review?",
                  "Typical (median) base salary increase awarded to the main population in each "
                  "of the last three pay review cycles.",
                  "Enter the median increase for the main population. Leave a year blank if you "
                  "did not run a review that year.",
                  json.dumps({"required": False, "integer_only": False, "min_decimals": 0,
                              "max_decimals": 1, "max_length": None, "pattern": None}),
                  json.dumps({"hard_min": 0, "hard_max": 30, "soft_min": 0, "soft_max": 10,
                              "unit": "%"}),
                  QID))

    # 2. replace the flat answers with matrix rows
    conn.execute("DELETE FROM answers WHERE question_id=? AND snapshot_id=1 AND matrix_row_id=''",
                 (QID,))
    for org, vals in plan.items():
        for label in ROWS:
            slug = SLUG[label]
            v = str(vals[slug])
            conn.execute("INSERT INTO answers(org_id,snapshot_id,question_id,matrix_row_id,value,"
                         "submitted_at) VALUES (?,1,?,?,?,datetime('now'))", (org, QID, slug, v))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,"
                         "value,recorded_at) VALUES (?,1,?,?,?,datetime('now'))", (org, QID, slug, v))

    # 3. the projection question
    if not exists:
        conn.execute("""INSERT INTO questions
            (id,text,short_description,help_text,definition,superpower,sub_power,sub_power_order,
             type,category,options_json,default_chart_type,data_display_type,polarity,unit,
             unit_display_name,unit_type,currency_code,matrix_json,matrix_rows_json,lumi_tier,
             na_handling_json,benchmark_display,is_scored,scoring_config_json,score_map_json,
             validation_json,tolerance_json,is_required,search_description,question_order,
             question_version,historical_comparability,status,release_entered)
            VALUES (?,?,?,?,?,'Reward','Pay',1,'numeric','metric','[]','quartile_band','mean',
             'higher_is_better','%','%','percentage','', '{}','[]','Enhanced',?,?,0,?,'{}',?,?,0,?,?,
             'v1.0','high','active','2026-baseline')""",
            (PROJ_QID,
             "What headline base pay increase are you planning for the next pay review?",
             "Planned pay increase, next review",
             "Your current working assumption. A range is fine — enter the midpoint.",
             "Planned or budgeted median base salary increase for the next pay review cycle.",
             json.dumps({"exclude_from_scoring": True, "exclude_from_benchmarking": False}),
             "Planned pay increase, next review",
             json.dumps({"curve_type": "linear", "scoring_method": "numeric_linear",
                         "option_scores": {}, "polarity": "neutral"}),
             json.dumps({"required": False, "integer_only": False, "min_decimals": 0,
                         "max_decimals": 1, "max_length": None, "pattern": None}),
             json.dumps({"hard_min": 0, "hard_max": 30, "soft_min": 0, "soft_max": 10, "unit": "%"}),
             "planned pay increase next review headline base pay increase planning next pay review",
             671))
    for org, vals in plan.items():
        v = str(vals["_next"])
        conn.execute("INSERT OR REPLACE INTO answers(org_id,snapshot_id,question_id,matrix_row_id,"
                     "value,submitted_at) VALUES (?,1,?,'',?,datetime('now'))", (org, PROJ_QID, v))
        conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,"
                     "value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))", (org, PROJ_QID, v))

    conn.commit()
    print("\n   committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    conn.close()


if __name__ == "__main__":
    main()
