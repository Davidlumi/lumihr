"""Phase 1a — seed import.

Loads the question library, the organisation registry, and the 220 seed
response files into the database as tenant organisations, then prints a full
reconciliation report (matched / file-only / registry-only, fuzzy candidates).

Run:  python3 seed_import.py [--data DIR] [--fresh]
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_schema, j, set_meta  # noqa: E402

COLLECTION_WINDOW = "2026 H1"

# Contextual attributes feeding the Peer Twin similarity vector (per spec).
SIM_CATEGORICAL = [
    "Industry", "FTE_Band", "Ownership_Type", "Archetype", "Turnover_Band",
    "Avg_Tenure_Band", "HR_Maturity", "Operating_Model", "Business_Maturity",
]
SIM_NUMERIC = ["Workforce_Frontline_%", "Workforce_Shift_%", "Workforce_Unionised_%"]


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def token_set_ratio(a, b):
    """fuzzywuzzy-style token_set_ratio in pure stdlib, returns 0..1."""
    ta, tb = set(norm_tokens(a)), set(norm_tokens(b))
    if not ta or not tb:
        return 0.0
    inter = " ".join(sorted(ta & tb))
    sa = (inter + " " + " ".join(sorted(ta - tb))).strip()
    sb = (inter + " " + " ".join(sorted(tb - ta))).strip()
    pairs = [(inter, sa), (inter, sb), (sa, sb)]
    return max(SequenceMatcher(None, x, y).ratio() for x, y in pairs if x or y)


def norm_tokens(s):
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- library ---

def import_library(conn, path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    conn.execute("DELETE FROM questions")
    n = 0
    for i, r in enumerate(rows):
        polarity = r.get("polarity") or {
            "positive": "higher_is_better", "negative": "lower_is_better"
        }.get(r.get("response_polarity"), "neutral")
        conn.execute(
            """INSERT INTO questions(id,text,short_description,help_text,definition,
               superpower,sub_power,sub_power_order,type,category,options_json,
               default_chart_type,data_display_type,polarity,unit,unit_display_name,
               unit_type,currency_code,matrix_json,matrix_rows_json,lumi_tier,
               na_handling_json,benchmark_display,is_scored,scoring_config_json,
               score_map_json,validation_json,tolerance_json,is_required,
               search_description,question_order)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["id"], r["text"], r.get("short_description"), r.get("help_text"),
                r.get("definition"), r["superpower"], r.get("sub_power"),
                to_int(r.get("sub_power_order")), r["type"], r.get("category"),
                _json_or_none(r.get("options")), r.get("default_chart_type"),
                r.get("data_display_type"), polarity, r.get("unit"),
                r.get("unit_display_name"), r.get("unit_type"), r.get("currency_code"),
                _json_or_none(r.get("matrix")), _json_or_none(r.get("matrix_rows")),
                r.get("lumi_tier"), _json_or_none(r.get("na_handling")),
                r.get("benchmark_display"), 1 if r.get("is_scored") == "TRUE" else 0,
                _json_or_none(r.get("scoring_config")), _json_or_none(r.get("score_map")),
                _json_or_none(r.get("validation")), _json_or_none(r.get("tolerance")),
                1 if (r.get("is_required") or "").upper() in ("TRUE", "1") else 0,
                r.get("search_description"), i,
            ),
        )
        n += 1
    conn.commit()
    return n


def _json_or_none(text):
    """Defensive JSON column parse: returns canonical JSON text or None.
    Library CSV uses doubled quotes inside quoting (csv module unescapes them);
    anything that still fails to parse is dropped with a warning."""
    if text is None or text.strip() == "":
        return None
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except ValueError:
        cleaned = text.replace('""', '"')
        try:
            return json.dumps(json.loads(cleaned), ensure_ascii=False)
        except ValueError:
            print("  WARN unparseable JSON column value: %r..." % text[:60])
            return None


# ----------------------------------------------------------- registry join ---

def build_similarity_vectors(registry_records):
    """One-hot categoricals + min-max scaled numerics over the registry
    population. Returns ({Company_Name: [floats]}, feature_names)."""
    cat_values = {a: sorted({(r.get(a) or "—") for r in registry_records}) for a in SIM_CATEGORICAL}
    num_ranges = {}
    for a in SIM_NUMERIC:
        vals = [float(r[a]) for r in registry_records if r.get(a) is not None]
        num_ranges[a] = (min(vals), max(vals)) if vals else (0.0, 1.0)

    feature_names = []
    for a in SIM_CATEGORICAL:
        feature_names += ["%s=%s" % (a, v) for v in cat_values[a]]
    feature_names += SIM_NUMERIC
    # persistable feature space so new sign-up orgs can be encoded consistently
    build_similarity_vectors.feature_space = {
        "cat_values": cat_values,
        "num_ranges": {k: list(v) for k, v in num_ranges.items()},
    }

    vectors = {}
    for r in registry_records:
        vec = []
        for a in SIM_CATEGORICAL:
            val = r.get(a) or "—"
            vec += [1.0 if val == v else 0.0 for v in cat_values[a]]
        for a in SIM_NUMERIC:
            lo, hi = num_ranges[a]
            x = r.get(a)
            vec.append(0.5 if x is None else (float(x) - lo) / (hi - lo) if hi > lo else 0.5)
        vectors[r["Company_Name"]] = vec
    return vectors, feature_names


# ----------------------------------------------------------------- import ---

def run(data_dir, fresh=False):
    db_path = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(__file__), "..", "lumi.db"))
    if fresh and os.path.exists(db_path):
        os.remove(db_path)
        for ext in ("-wal", "-shm"):
            p = db_path + ext
            if os.path.exists(p):
                os.remove(p)
    conn = get_conn()
    init_schema(conn)

    lib_path = os.path.join(data_dir, "lumi_questions.csv")
    nq = import_library(conn, lib_path)
    print("Question library: %d questions imported" % nq)
    qids = {r["id"] for r in conn.execute("SELECT id FROM questions")}

    registry = json.load(open(os.path.join(data_dir, "seeded_orgs.json")))
    print("Registry: %d organisations" % len(registry))
    reg_by_norm = {norm_name(r["Company_Name"]): r for r in registry}
    sim_vectors, feature_names = build_similarity_vectors(registry)

    conn.execute(
        "INSERT OR REPLACE INTO snapshots(snapshot_id, snapshot_date, collection_window, status) "
        "VALUES (1, ?, ?, 'open')", (date.today().isoformat(), COLLECTION_WINDOW))

    resp_dir = os.path.join(data_dir, "responses")
    files = sorted(fn for fn in os.listdir(resp_dir) if fn.endswith(".csv"))

    matched, file_only, fuzzy_candidates = [], [], []
    orphan_qids_in_files = Counter()
    answer_rows = 0
    blank_skipped = 0
    matched_norms = set()

    for fn in files:
        with open(os.path.join(resp_dir, fn), encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            print("  WARN empty response file: %s" % fn)
            continue
        org_id, org_name = rows[0]["org_id"], rows[0]["org_name"]
        nn = norm_name(org_name)
        reg = reg_by_norm.get(nn)
        if reg is None:
            # one fuzzy pass, reported for human review — never silently joined
            best = max(
                ((token_set_ratio(org_name, r["Company_Name"]), r["Company_Name"]) for r in registry),
                default=(0.0, None))
            if best[0] >= 0.92:
                fuzzy_candidates.append((org_name, best[1], round(best[0], 3)))
            file_only.append(org_name)
        else:
            matched.append(org_name)
            matched_norms.add(nn)

        conn.execute(
            """INSERT OR REPLACE INTO orgs(org_id,name,normalized_name,source,
               tier_entitlement,classified,industry,subsector,fte_band,hq_region,
               ownership_type,registry_json,similarity_vector_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                org_id, org_name, nn, "seed", "full",
                1 if reg else 0,
                reg.get("Industry") if reg else None,
                reg.get("Subsector") if reg else None,
                reg.get("FTE_Band") if reg else None,
                reg.get("HQ_Region") if reg else None,
                reg.get("Ownership_Type") if reg else None,
                j(reg) if reg else None,
                j(sim_vectors.get(reg["Company_Name"])) if reg else None,
            ),
        )
        # seed orgs are complete submitters by definition
        conn.execute("UPDATE orgs SET submission_complete=1 WHERE org_id=?", (org_id,))

        for r in rows:
            qid = r["question_id"]
            if qid not in qids:
                orphan_qids_in_files[qid] += 1
                continue
            val = (r.get("your_answer") or "").strip()
            if val == "":
                blank_skipped += 1
                continue
            conn.execute(
                "INSERT OR REPLACE INTO answers(org_id,snapshot_id,question_id,matrix_row_id,value) "
                "VALUES(?,?,?,?,?)",
                (org_id, 1, qid, r.get("matrix_row_id") or "", val))
            answer_rows += 1
    conn.commit()

    registry_only = sorted(r["Company_Name"] for r in registry if norm_name(r["Company_Name"]) not in matched_norms)

    answered_qids = {r["question_id"] for r in conn.execute("SELECT DISTINCT question_id FROM answers")}
    lib_orphans = sorted(qids - answered_qids)

    set_meta("sim_feature_names", feature_names, conn)
    set_meta("sim_feature_space", build_similarity_vectors.feature_space, conn)
    # the seeded pool is realistic-but-synthetic illustrative data — surfaced
    # as a label wherever the peer group is described
    set_meta("synthetic_seed", True, conn)
    set_meta("registry_only_orgs", registry_only, conn)
    recon = {
        "files": len(files),
        "library_questions": nq,
        "matched_orgs": len(matched),
        "file_only_orgs": len(file_only),
        "registry_only_orgs": len(registry_only),
        "fuzzy_candidates": fuzzy_candidates,
        "answer_rows": answer_rows,
        "blank_answers_skipped": blank_skipped,
        "orphan_question_ids_in_files": dict(orphan_qids_in_files),
        "library_questions_never_answered": lib_orphans,
        "collection_window": COLLECTION_WINDOW,
    }
    set_meta("reconciliation", recon, conn)

    print("\n================ RECONCILIATION REPORT ================")
    print("Response files ingested:        %d" % len(files))
    print("Answer rows stored:             %d  (blank answers skipped: %d)" % (answer_rows, blank_skipped))
    print("Registry-matched orgs:          %d" % len(matched))
    print("File-only orgs (Unclassified):  %d" % len(file_only))
    print("Registry-only orgs (no file):   %d" % len(registry_only))
    print("\n-- File-only orgs (kept in 'All peers', excluded from filtered cuts):")
    for nme in sorted(file_only):
        print("   ", nme)
    print("\n-- Registry-only orgs (ignored for aggregation):")
    for nme in registry_only:
        print("   ", nme)
    print("\n-- Fuzzy-match candidates (token_set_ratio >= 0.92, FOR HUMAN REVIEW, not auto-joined):")
    if fuzzy_candidates:
        for a, b, s in fuzzy_candidates:
            print("    %.3f  %s  ~  %s" % (s, a, b))
    else:
        print("    (none)")
    print("\n-- Orphan question_ids in response files (not in library): %d" % len(orphan_qids_in_files))
    for qid, c in orphan_qids_in_files.items():
        print("    %s (%d rows)" % (qid, c))
    print("-- Library questions with zero answers across all files: %d" % len(lib_orphans))
    for qid in lib_orphans:
        print("    %s" % qid)
    print("========================================================\n")
    return recon


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()
    run(args.data, fresh=args.fresh)
