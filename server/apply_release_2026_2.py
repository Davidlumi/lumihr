# -*- coding: utf-8 -*-
"""RELEASE 2026.2 — 12 forward-looking additions, applied PROGRAMMATICALLY
from lumi_release_2026_2_questions.csv (the authoritative file; nothing
invented). A PURE-ADDITIONS release: zero comparability breaks, zero
retirements, zero rewordings — every existing question byte-identical.

QA-hardening encoded here (caught in review):
- id_hints are HINTS: real ids are assigned (REW262_* convention, matching
  the 2026.1 REW26_* pattern) and collision-checked before anything writes.
- 'None' scores zero, never a point: the action-plan multi_select carries a
  scoring_config with NONE: 0 even while unscored, so the engine-audit F1
  class can't reappear if scoring is ever switched on.
- offer_na questions (guaranteed-hours / cancelled-shift / shift-notice) get
  a first-class 'Not applicable' option (is_na, in na_codes) so all-salaried
  and no-shift orgs are never forced into a misleading 'No'.
- Polarity comes from the CSV verbatim — the ONE neutral (AI-skills premium)
  stays neutral: prevalence only, no market verdict ever.
- Option labels are asserted delimiter-free (no ',' or ';') — the
  multi-select split-bug class stays impossible.

All 12: required=FALSE, scored=FALSE — the unlock basis stays 82; nobody is
re-locked or gated. They trend from 2026.2 and sit honestly at n=0 until
seeded/answered. Dry-run default; --write applies and cuts the release.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from db import get_conn, j
import releases as rel

SRC = os.path.join(HERE, "..", "lumi_release_2026_2_questions.csv")
LIB_CSV = os.path.join(HERE, "..", "data", "lumi_questions.csv")
CATEGORY_ORDER = {"Pay": 1, "Incentives": 2, "Benefits": 3, "Time Off": 4,
                  "Wellbeing": 5, "Recognition": 6, "Governance": 7}
EXPECTED_AFTER = {"Pay": 45, "Incentives": 21, "Benefits": 50, "Time Off": 28,
                  "Wellbeing": 14, "Recognition": 7, "Governance": 41}

DEFINITIONS = {  # short factual restatements of each question (authored)
    "REW262_GOV_ACTIONPLAN": "Whether a published equality action plan exists and which characteristics it covers.",
    "REW262_GOV_EQUALVALUE": "Ability to group the workforce into categories of equal value (skills, effort, responsibility, working conditions).",
    "REW262_GOV_SALHISTORY": "Whether salary-history questions have been removed from hiring.",
    "REW262_GOV_PAYINADVERTS": "Whether pay or a pay range is included in job adverts.",
    "REW262_GOV_EQUALPAYAUDIT": "Whether proactive equal-pay audits run, and how often.",
    "REW262_GOV_AIINPAY": "Whether AI tools are used in pay decisions and under what governance.",
    "REW262_PAY_GUARANTEEDHRS": "Whether guaranteed-hours contracts are proactively offered to variable-hours workers.",
    "REW262_PAY_CANCELLEDSHIFT": "Whether workers are compensated for shifts cancelled at short notice.",
    "REW262_PAY_SHIFTNOTICE": "How much advance notice of shifts is given.",
    "REW262_PAY_AISKILLSPAY": "Whether a pay premium is paid specifically for AI skills.",
    "REW262_TIME_BEREAVEMENT": "Whether paid bereavement leave is offered above the statutory minimum.",
    "REW262_TIME_SICKDAYONE": "Whether occupational sick pay applies from day one with no waiting days.",
}


def slug_code(label):
    import re
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")[:48]


def main(write=False):
    conn = get_conn()
    if conn.execute("SELECT 1 FROM core_releases WHERE release_id='2026.2'").fetchone():
        print("2026.2 already exists — refusing.")
        sys.exit(1)
    cur = rel.current_release(conn)
    assert cur["release_id"] == "2026.1", "precondition: 2026.1 must be current (is %s)" % cur["release_id"]
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    assert len(rows) == 12, len(rows)

    # ids: hints validated against the convention + collision-checked
    existing_ids = {r[0] for r in conn.execute("SELECT id FROM questions")}
    plan = []
    for r in rows:
        qid = r["id_hint"].strip()
        assert qid.startswith("REW262_"), "id convention: %s" % qid
        assert qid not in existing_ids, "ID COLLISION: %s" % qid
        assert r["required"].upper() == "FALSE" and r["scored"].upper() == "FALSE", qid
        labels = [t.strip() for t in r["options"].split(";") if t.strip()]
        for l in labels:
            assert "," not in l and ";" not in l, "delimiter in option label: %r" % l
        plan.append((qid, r, labels))
    from collections import Counter
    cat_in = Counter(r["category"] for r in rows)
    print("ids OK (12, zero collisions) | additions by category: %s" % dict(cat_in))

    if not write:
        print("DRY RUN — pass --write to apply.")
        for qid, r, labels in plan:
            print("  %-26s [%s/%s] pol=%s na=%s opts=%d" % (
                qid, r["category"], r["type"], r["polarity"], r["na_handling"], len(labels)))
        return

    max_order = conn.execute("SELECT MAX(question_order) FROM questions WHERE question_order < 90000").fetchone()[0]
    for i, (qid, r, labels) in enumerate(plan):
        opts = [{"code": slug_code(l), "label": l, "order": k + 1, "is_na": False}
                for k, l in enumerate(labels)]
        scoring = None
        if r["na_handling"] == "offer_na":
            # first-class N/A: all-salaried / no-shift orgs are never forced
            # into a misleading 'No'. Counts as answered; excluded from
            # prevalence judgements (practice_status treats it as unknown).
            opts.append({"code": "NOT_APPLICABLE", "label": "Not applicable",
                         "order": len(opts) + 1, "is_na": True})
        if (r.get("none_scores_zero") or "").upper() == "TRUE":
            # future-proof the F1 class: if this is EVER scored, 'None' is 0
            scoring = {"scoring_method": "multi_select_count", "curve_type": "linear",
                       "polarity": r["polarity"],
                       "option_scores": {o["code"]: (0 if o["code"] == "NONE" else 1)
                                         for o in opts}}
        conn.execute(
            """INSERT INTO questions(id,text,short_description,help_text,definition,superpower,
               sub_power,sub_power_order,type,category,options_json,default_chart_type,
               data_display_type,polarity,unit,unit_display_name,unit_type,currency_code,
               matrix_json,matrix_rows_json,lumi_tier,na_handling_json,benchmark_display,
               is_scored,scoring_config_json,score_map_json,validation_json,tolerance_json,
               is_required,search_description,question_order,question_version,
               historical_comparability,status,replaced_by,release_entered,module)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (qid, r["text"], r["text"][:80], r["help_why"], DEFINITIONS[qid], "Reward",
             r["category"], CATEGORY_ORDER[r["category"]], r["type"], "practice",
             j(opts), "bar", "percentage_distribution", r["polarity"],
             None, None, "none", None, None, None, "Core",
             j({"exclude_from_scoring": True, "exclude_from_benchmarking": False,
                "na_codes": ["NOT_APPLICABLE"] if r["na_handling"] == "offer_na" else []}),
             r["text"][:80], 0, j(scoring) if scoring else None, None, None, None,
             0, (r["help_why"] or "") + " — " + r["text"], max_order + 1 + i,
             "v1.0", "high", "active", None, None, None))
    conn.commit()
    print("inserted 12 questions")

    # library CSV stays the import source of truth
    with open(LIB_CSV, encoding="utf-8-sig", newline="") as f:
        lib = list(csv.DictReader(f))
        fields = list(lib[0].keys())
    dbcols = {c[1] for c in conn.execute("PRAGMA table_info(questions)")}
    for qid, r, labels in plan:
        qrow = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        csv_row = {k: "" for k in fields}
        for k in fields:
            dbk = {"options": "options_json", "matrix": "matrix_json", "matrix_rows": "matrix_rows_json",
                   "na_handling": "na_handling_json", "scoring_config": "scoring_config_json",
                   "score_map": "score_map_json", "validation": "validation_json",
                   "tolerance": "tolerance_json"}.get(k, k)
            if dbk in dbcols and qrow[dbk] is not None:
                csv_row[k] = str(qrow[dbk])
        csv_row["is_scored"] = "FALSE"
        csv_row["is_required"] = "FALSE"
        lib.append(csv_row)
    with open(LIB_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(lib)
    print("library CSV synced (+12 rows)")

    changes = rel.create_release(
        "2026.2",
        "Forward-looking additions for the 2026-27 regulatory and AI shifts (EU Pay "
        "Transparency Directive, Employment Rights Act 2025, AI-in-reward): 12 optional, "
        "unscored questions — Governance 6, Pay 4, Time Off 2. Pure additions: zero "
        "comparability breaks, zero retirements, no rewording. They enter the required "
        "set only via a future governed annual review, once they carry data.",
        signed_off_by="David Whitfield (release 2026.2 brief, 2026-06-12)", conn=conn)
    counts = Counter(c[0] for c in changes)
    print("release 2026.2 cut: %s" % dict(counts))
    assert dict(counts) == {"added": 12}, "diff must be PURE additions: %s" % dict(counts)

    live = Counter(r[0] for r in conn.execute(
        "SELECT sub_power FROM questions WHERE superpower='Reward' AND status!='retired'"))
    assert dict(live) == EXPECTED_AFTER, "post-release counts diverge: %s" % dict(live)
    print("post-release category counts verified: %s = %d" % (dict(live), sum(live.values())))


if __name__ == "__main__":
    main("--write" in sys.argv)
