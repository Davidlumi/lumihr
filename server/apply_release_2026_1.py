# -*- coding: utf-8 -*-
"""RELEASE 2026.1 — the 7-category restructure, applied PROGRAMMATICALLY from
the authoritative mapping file (lumi_restructure_mapping.csv). Nothing is
re-derived or guessed: every existing question's new category and every new
question's spec comes from the CSV.

What it does, in order:
  1. Verifies the mapping covers exactly the live core (180 existing ids).
  2. Re-tags the 180 existing questions to their NEW_category (sub_power now
     carries CATEGORY semantics). Wording untouched -> trends stay
     comparable; NO comparability breaks, NO retirements.
  3. Inserts the 14 NEW questions with full schema (unscored, optional —
     they cannot move the unlock gate; they trend from 2026.1 onward).
  4. Flags the 5 tronc/tips metrics module='hospitality' (sector-gated).
  5. Syncs data/lumi_questions.csv (categories updated + 14 rows appended)
     so the library file stays the import source of truth.
  6. Cuts release "2026.1" — the diff writes the change log
     (recategorised/added); the 2025 baseline stays reconstructable.

Dry-run by default; --write applies. Idempotence guard: refuses if 2026.1
already exists.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from db import get_conn, j
import releases as rel

MAPPING = os.path.join(HERE, "..", "lumi_restructure_mapping.csv")
LIB_CSV = os.path.join(HERE, "..", "data", "lumi_questions.csv")

CATEGORY_ORDER = {"Pay": 1, "Incentives": 2, "Benefits": 3, "Time Off": 4,
                  "Wellbeing": 5, "Recognition": 6, "Governance": 7}
EXPECTED_COUNTS = {"Pay": 41, "Incentives": 21, "Benefits": 50, "Time Off": 26,
                   "Wellbeing": 14, "Recognition": 7, "Governance": 35}

# ids for the 14 NEW rows, in mapping-file order (stable, semantic)
NEW_IDS = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL",
           "REW26_WEL_BUDGET", "REW26_WEL_SCREENING", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PLSA_QM", "REW26_BEN_PENSION_MATCH",
           "REW26_BEN_SALSAC", "REW26_BEN_PENSION_COST_SHARE",
           "REW26_PAY_SKILLS_PAY", "REW26_PAY_JOBEVAL_COVERAGE", "REW26_GOV_EU_PTD_PREP"]

# authored display copy per new id (title, help, definition, internal category)
NEW_COPY = {
    "REW26_WEL_EAP": ("Employee Assistance Programme offered", "Count any employer-paid EAP, including one bundled with insurance.",
                      "Whether the organisation provides an Employee Assistance Programme (confidential advice/counselling line) to employees.", "benefit"),
    "REW26_WEL_MH_SUPPORT": ("Mental-health support provisions", "Tick everything currently offered to any employee group.",
                             "The mental-health support provisions available to employees.", "benefit"),
    "REW26_WEL_FINWELL": ("Financial wellbeing programme offered", "Include education, tools or coaching — not just signposting.",
                          "Whether a financial wellbeing programme (education, tools, coaching) is offered.", "benefit"),
    "REW26_WEL_BUDGET": ("Annual wellbeing budget per employee", "Annual spend divided by headcount; enter 0 if none.",
                         "The annual wellbeing budget per employee in GBP.", "metric"),
    "REW26_WEL_SCREENING": ("Health screening or assessments offered", "Any employer-funded screening or health assessment counts.",
                            "Whether health screening or health assessments are offered.", "benefit"),
    "REW26_WEL_STRATEGY": ("Wellbeing strategy and review cadence", "Choose the option matching your documented position.",
                           "Whether a documented wellbeing strategy exists and how often it is reviewed.", "practice"),
    "REW26_BEN_PENSION_TYPE": ("Pension scheme type (main population)", "The scheme covering your largest employee population.",
                               "The type of pension scheme offered to the main population.", "practice"),
    "REW26_BEN_PLSA_QM": ("Meets PLSA quality-mark threshold", "PLSA quality mark: 12% total contributions with at least 6% employer.",
                          "Whether the main scheme meets the PLSA quality-mark threshold (12% total / 6% employer).", "practice"),
    "REW26_BEN_PENSION_MATCH": ("Pension contribution matching level", "The maximum employer matching available, not the default.",
                                "Whether pension contribution matching is offered and up to what level.", "practice"),
    "REW26_BEN_SALSAC": ("Pension via salary sacrifice by default", "Default arrangement for new joiners.",
                         "Whether pension is offered via salary sacrifice by default.", "practice"),
    "REW26_BEN_PENSION_COST_SHARE": ("Employer pension cost share of total reward", "Employer pension contributions as a share of total reward spend.",
                                     "Employer pension cost as a percentage of total reward spend.", "metric"),
    "REW26_PAY_SKILLS_PAY": ("Skills- or capability-based pay framework", "A framework that pays for verified skills/capabilities rather than role alone.",
                             "Whether a skills- or capability-based pay framework is operated.", "practice"),
    "REW26_PAY_JOBEVAL_COVERAGE": ("Job-evaluation / levelling coverage", "Tick the populations covered by a formal framework.",
                                   "Which job levels are covered by a formal job-evaluation or levelling framework.", "practice"),
    "REW26_GOV_EU_PTD_PREP": ("EU Pay Transparency Directive readiness", "The 2026 directive affects UK organisations with EU workforce.",
                              "Preparedness for the EU Pay Transparency Directive (2026).", "practice"),
}

HOSPITALITY_NOTE = "hospitality sector module: shown to hospitality/retail organisations; hidden otherwise"


def slug_code(label):
    import re
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")[:48]


def parse_options(raw, qtype):
    if qtype in ("numeric",):
        return None
    seps = ";" if ";" in raw else "/"
    labels = [t.strip() for t in raw.split(seps) if t.strip()]
    return [{"code": slug_code(l), "label": l, "order": i + 1, "is_na": False}
            for i, l in enumerate(labels)]


def main(write=False):
    conn = get_conn()
    if conn.execute("SELECT 1 FROM core_releases WHERE release_id='2026.1'").fetchone():
        print("2026.1 already exists — refusing.")
        sys.exit(1)
    with open(MAPPING, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    existing = [r for r in rows if r["status"] == "existing"]
    new = [r for r in rows if r["status"] == "NEW"]
    assert len(existing) == 180 and len(new) == 14, (len(existing), len(new))
    assert len(NEW_IDS) == len(new)

    # 1. coverage check: mapping ids == live core ids, exactly
    live = {r["id"] for r in conn.execute(
        "SELECT id FROM questions WHERE superpower='Reward' AND status!='retired'")}
    mapped = {r["question_id"] for r in existing}
    missing, extra = mapped - live, live - mapped
    print("coverage: mapping %d | live core %d | not-in-live %d | unmapped-live %d"
          % (len(mapped), len(live), len(missing), len(extra)))
    if missing or extra:
        print("  REFUSING — mapping and live core disagree:", list(missing)[:5], list(extra)[:5])
        sys.exit(1)

    # planned moves
    moves = []
    for r in existing:
        cur = conn.execute("SELECT sub_power FROM questions WHERE id=?", (r["question_id"],)).fetchone()[0]
        if cur != r["NEW_category"]:
            moves.append((r["question_id"], cur, r["NEW_category"]))
    cat_counts = {}
    for r in rows:
        cat_counts[r["NEW_category"]] = cat_counts.get(r["NEW_category"], 0) + 1
    print("planned: %d category moves, 14 additions; target counts %s" % (len(moves), cat_counts))
    assert cat_counts == EXPECTED_COUNTS, "mapping counts diverge from the locked targets"

    if not write:
        print("\nDRY RUN — pass --write to apply.")
        for m in moves[:8]:
            print("  move:", m)
        return

    # 2. re-tag the 180 (category only — wording, version, scoring untouched)
    for r in existing:
        conn.execute("UPDATE questions SET sub_power=?, sub_power_order=? WHERE id=?",
                     (r["NEW_category"], CATEGORY_ORDER[r["NEW_category"]], r["question_id"]))

    # 3. insert the 14 new questions
    max_order = conn.execute("SELECT MAX(question_order) FROM questions").fetchone()[0] or 0
    for i, r in enumerate(new):
        qid = NEW_IDS[i]
        title, help_text, definition, internal_cat = NEW_COPY[qid]
        qtype = r["type"]
        opts = parse_options(r["options"], qtype)
        unit_type = {"£": "currency", "%": "percentage"}.get((r["unit"] or "").strip(), "none")
        tolerance = None
        if qtype == "numeric":
            tolerance = {"hard_min": 0, "hard_max": 100 if unit_type == "percentage" else None,
                         "soft_min": None, "soft_max": None,
                         "unit": "GBP" if unit_type == "currency" else "%"}
        conn.execute(
            """INSERT INTO questions(id,text,short_description,help_text,definition,superpower,
               sub_power,sub_power_order,type,category,options_json,default_chart_type,
               data_display_type,polarity,unit,unit_display_name,unit_type,currency_code,
               matrix_json,matrix_rows_json,lumi_tier,na_handling_json,benchmark_display,
               is_scored,scoring_config_json,score_map_json,validation_json,tolerance_json,
               is_required,search_description,question_order,question_version,
               historical_comparability,status,replaced_by,release_entered,module)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (qid, r["question_text"], title, help_text, definition, "Reward",
             r["NEW_category"], CATEGORY_ORDER[r["NEW_category"]], qtype, internal_cat,
             j(opts) if opts else None,
             "quartile_band" if qtype == "numeric" else "bar",
             "mean" if qtype == "numeric" else "percentage_distribution",
             r["polarity"] or "neutral",
             "GBP" if unit_type == "currency" else ("%" if unit_type == "percentage" else None),
             "£ per employee" if unit_type == "currency" else ("%" if unit_type == "percentage" else None),
             unit_type if unit_type != "none" else "none",
             "GBP" if unit_type == "currency" else None,
             None, None, "Core",
             j({"exclude_from_scoring": True, "exclude_from_benchmarking": False}),
             title, 0, None, None, None, j(tolerance) if tolerance else None,
             0, (r["source_note"] or "") + " — " + r["question_text"], max_order + 1 + i,
             "v1.0", "high", "active", None, None, None))

    # 4. the hospitality module flags
    hosp = [r["question_id"] for r in existing if (r["hospitality_module"] or "").upper() == "YES"]
    for qid in hosp:
        conn.execute("UPDATE questions SET module='hospitality' WHERE id=?", (qid,))
    conn.commit()
    print("re-tagged 180 | inserted 14 | module-flagged %d: %s" % (len(hosp), hosp))

    # 5. sync the library CSV (categories + appended new rows)
    with open(LIB_CSV, encoding="utf-8-sig", newline="") as f:
        lib = list(csv.DictReader(f))
        fields = list(lib[0].keys())
    by_id = {r["question_id"]: r for r in existing}
    for row in lib:
        if row["id"] in by_id:
            row["sub_power"] = by_id[row["id"]]["NEW_category"]
            row["sub_power_order"] = str(CATEGORY_ORDER[by_id[row["id"]]["NEW_category"]])
    dbcols = {r[1] for r in conn.execute("PRAGMA table_info(questions)")}
    for i, r in enumerate(new):
        qrow = conn.execute("SELECT * FROM questions WHERE id=?", (NEW_IDS[i],)).fetchone()
        csv_row = {k: "" for k in fields}
        for k in fields:
            dbk = {"options": "options_json", "matrix": "matrix_json", "matrix_rows": "matrix_rows_json",
                   "na_handling": "na_handling_json", "scoring_config": "scoring_config_json",
                   "score_map": "score_map_json", "validation": "validation_json",
                   "tolerance": "tolerance_json"}.get(k, k)
            if dbk in dbcols and qrow[dbk] is not None:
                v = qrow[dbk]
                csv_row[k] = str(v) if not isinstance(v, str) else v
        csv_row["is_scored"] = "FALSE"
        csv_row["is_required"] = "FALSE"
        lib.append(csv_row)
    with open(LIB_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(lib)
    print("library CSV synced (+14 rows, categories updated)")

    # 6. cut the release — the diff writes the change log
    changes = rel.create_release(
        "2026.1",
        "The 7-category restructure: Reward re-filed into Pay / Incentives / Benefits / "
        "Time Off / Wellbeing / Recognition / Governance; 'superpower'/'sub-power' terminology retired "
        "(Categories and Metrics); 14 new questions added (unscored, optional); the 5 tronc/tips "
        "metrics become a hospitality sector module. Re-filed questions keep their wording — "
        "existing trends remain comparable, no breaks, nothing retired.",
        signed_off_by="David Whitfield (restructure brief, 2026-06-12)", conn=conn)
    # one explicit terminology line in the log
    conn.execute("INSERT INTO core_changelog(release_id, lane, change_type, detail, signed_off_by) VALUES (?,?,?,?,?)",
                 ("2026.1", "release", "terminology",
                  "User-facing terminology: 'superpower'/'sub-power' retired; groupings are CATEGORIES, items are METRICS. "
                  "Tronc/tips (5 metrics) gated to hospitality/retail sectors as a module.",
                  "David Whitfield (restructure brief, 2026-06-12)"))
    conn.commit()
    from collections import Counter
    print("release 2026.1 cut: %s" % dict(Counter(c[0] for c in changes)))


if __name__ == "__main__":
    main("--write" in sys.argv)
