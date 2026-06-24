# -*- coding: utf-8 -*-
"""DEEP DATA-INTEGRITY SWEEP — every live metric, all at once.

Adversarial, per-metric checks that catch the classes of demo-data fault found by
hand one card at a time (REW_INC_061 mis-typed matrix, REW_PAY_020 degenerate
by-level, "we have data but the card shows nothing"). Reads what is ACTUALLY served
(benchmark_snapshots payloads) and the RAW answers, and compares.

Severities:
  CRIT  — the card is wrong or shows nothing despite data (must fix)
  WARN  — degenerate / suspicious distribution (review)
  INFO  — thin coverage, redundancy, demo-org gaps (worth a glance)

Run:  python3 qa_metric_data.py            (live Reward metrics)
      python3 qa_metric_data.py --all      (every active question)
Exit 0 always — this is a report, not a gate. Nothing is mutated.
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
SNAP = 1
FLOOR = 5                      # suppression floor (positions.SUPPRESSED_COPY "fewer than 5")
DEMO_ORG_NAME = "Thornbridge Retail Group plc"   # exact — "Thornbridge Advisory plc" is a different seed org

findings = []                  # (severity, qid, name, code, detail)
def add(sev, qid, name, code, detail):
    findings.append((sev, qid, name, code, detail))


def uj(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def main():
    show_all = "--all" in sys.argv
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    qs = conn.execute("SELECT * FROM questions WHERE status='active'").fetchall()
    qs = [q for q in qs if show_all or q["superpower"] == "Reward"]
    qmap = {q["id"]: q for q in qs}

    # raw answer stats per question (one pass)
    raw_base = defaultdict(set)        # qid -> {orgs with a base-row (matrix_row_id='') answer}
    raw_rowed = defaultdict(set)       # qid -> {orgs with any matrix-row answer}
    raw_vals = defaultdict(list)       # qid -> [base values] (non-matrix)
    for r in conn.execute(
        "SELECT question_id, org_id, matrix_row_id, value FROM answers WHERE snapshot_id=?", (SNAP,)):
        qid, oid, rid, v = r["question_id"], r["org_id"], r["matrix_row_id"], r["value"]
        if qid not in qmap:
            continue
        if v is None or str(v).strip() == "" or str(v).strip().lower() == "null":
            continue
        if rid:
            raw_rowed[qid].add(oid)
        else:
            raw_base[qid].add(oid)
            raw_vals[qid].append(v)

    demo = conn.execute("SELECT org_id FROM orgs WHERE name = ?", (DEMO_ORG_NAME,)).fetchone()
    demo_id = demo["org_id"] if demo else None
    demo_answered = set()
    if demo_id:
        for r in conn.execute("SELECT DISTINCT question_id FROM answers WHERE snapshot_id=? AND org_id=? AND value IS NOT NULL AND value!=''", (SNAP, demo_id)):
            demo_answered.add(r["question_id"])

    payloads = {r["question_id"]: uj(r["payload_json"], {})
                for r in conn.execute("SELECT question_id, payload_json FROM benchmark_snapshots WHERE snapshot_id=?", (SNAP,))}

    # redundancy index: identical option-label sets
    optsig = defaultdict(list)

    for q in qs:
        qid = q["id"]
        name = q["benchmark_display"] or q["short_description"] or (q["text"] or "")[:48]
        typ = q["type"]
        p = payloads.get(qid, {})
        allb = p.get("all") if isinstance(p, dict) else None
        n_served = (allb or {}).get("n")
        suppressed = bool((allb or {}).get("suppressed"))
        n_rowed = len(raw_rowed.get(qid, ()))
        n_base = len(raw_base.get(qid, ()))

        # ---- shape integrity ---------------------------------------------------
        if typ != "matrix" and n_rowed > 0:
            add("CRIT", qid, name, "shape:rowed-non-matrix",
                "type=%s but %d orgs stored matrix-row answers — aggregation ignores them (only the %d base rows count)." % (typ, n_rowed, n_base))
        if typ == "matrix" and n_rowed == 0 and n_base > 0:
            add("CRIT", qid, name, "shape:matrix-no-rows",
                "type=matrix but answers are base-row only (%d) — renders empty." % n_base)

        # ---- coverage / silent suppression ------------------------------------
        raw_orgs = n_rowed if typ == "matrix" else n_base
        if not p:
            add("CRIT", qid, name, "payload:missing", "no benchmark payload for a live metric.")
        elif typ == "matrix":
            mr = p.get("matrix_rows") or []
            if raw_orgs >= FLOOR and not mr:
                add("CRIT", qid, name, "matrix:no-rows-served", "%d orgs have data but the payload carries no matrix rows." % raw_orgs)
        else:
            # legitimate, accounted-for reductions: N/A, non-numeric, unmatched labels
            acc = ((allb or {}).get("excluded_na") or 0) + ((allb or {}).get("excluded_non_numeric") or 0) \
                + ((allb or {}).get("unmatched") or 0) + ((allb or {}).get("unmatched_tokens") or 0)
            if (suppressed or (n_served or 0) < FLOOR) and raw_orgs >= FLOOR and (raw_orgs - acc) >= FLOOR:
                add("CRIT", qid, name, "suppressed-with-data",
                    "served n=%s (suppressed) yet %d orgs answered (%d accounted N/A etc.) — card shows nothing." % (n_served, raw_orgs, acc))
            elif n_served is not None and raw_orgs >= 10 and (n_served + acc) < raw_orgs * 0.75:
                add("CRIT", qid, name, "data-loss",
                    "served n=%d + %d accounted ≠ %d orgs — %d answers vanish UNEXPLAINED." % (n_served, acc, raw_orgs, raw_orgs - n_served - acc))

        # ---- degenerate / no-variation ----------------------------------------
        if typ == "matrix":
            mr = p.get("matrix_rows") or []
            sigs = []
            for row in mr:
                rb = row.get("all") or {}
                if rb.get("kind") == "select":
                    sigs.append(tuple((o.get("label"), o.get("count")) for o in (rb.get("options") or [])))
                elif "p50" in rb:
                    sigs.append((rb.get("p25"), rb.get("p50"), rb.get("p75")))
            if len(sigs) >= 3 and len(set(sigs)) == 1:
                add("WARN", qid, name, "matrix:identical-rows",
                    "all %d levels show an IDENTICAL distribution — no per-level variation (degenerate by-level)." % len(sigs))
        elif typ in ("single_select", "yes_no", "multi_select") and allb and not suppressed and (n_served or 0) >= FLOOR:
            opts = [o for o in (allb.get("options") or []) if not o.get("is_na")]
            tops = [o for o in opts if (o.get("pct") or 0) >= 99.5]
            if tops:
                add("WARN", qid, name, "no-variation",
                    "%.0f%% of peers gave one answer (%r) — effectively no spread." % (tops[0]["pct"], tops[0].get("label")))
        elif typ == "numeric" and allb and (n_served or 0) >= FLOOR:
            vals = allb.get("_values") or []
            if vals and min(vals) == max(vals):
                add("WARN", qid, name, "numeric:single-value", "every peer reported the same value (%s)." % vals[0])
            elif (n_served or 0) >= 20 and allb.get("p25") == allb.get("p50") == allb.get("p75"):
                add("WARN", qid, name, "numeric:zero-spread", "P25=P50=P75=%s — no interquartile spread on n=%d." % (allb.get("p50"), n_served))

        # ---- value validity ----------------------------------------------------
        if typ in ("single_select", "yes_no") and allb:
            unm = allb.get("unmatched") or 0
            if unm and n_served and unm > max(3, n_served * 0.05):
                add("WARN", qid, name, "unmatched-values", "%d answers match no option (n=%d) — value/option drift." % (unm, n_served))
        if typ == "numeric" and allb:
            tol = uj(q["tolerance_json"], {}) or {}
            lo, hi = tol.get("hard_min"), tol.get("hard_max")
            vals = allb.get("_values") or []
            if vals and (lo is not None or hi is not None):
                oob = [v for v in vals if (lo is not None and v < lo) or (hi is not None and v > hi)]
                if oob:
                    add("WARN", qid, name, "out-of-tolerance", "%d/%d values outside [%s,%s] e.g. %s." % (len(oob), len(vals), lo, hi, sorted(oob)[:4]))

        # ---- coverage / demo-org / redundancy ---------------------------------
        if not suppressed and n_served is not None and FLOOR <= n_served < 20 and typ != "matrix":
            add("INFO", qid, name, "thin-coverage", "served n=%d (5–19) — every cut filter risks suppression." % n_served)
        if q["is_required"] and demo_id and qid not in demo_answered:
            add("INFO", qid, name, "demo-org-missing", "the demo org has no answer for this required metric (no 'You' marker).")
        opts = q["options_json"]
        if opts and opts not in ("[]", "", None):
            labs = tuple(sorted(o.get("label", "") for o in (uj(opts, []) or [])))
            if len(labs) >= 2:
                toks = set(re.findall(r"[a-z]{3,}", (q["text"] or "").lower()))
                optsig[labs].append((qid, toks))

    # redundancy pass — only true near-duplicate CONCEPTS (identical options AND
    # strongly overlapping wording), so shared Yes/No scales don't flood the report.
    def jac(a, b):
        return len(a & b) / max(1, len(a | b))
    seen_pairs = set()
    for labs, items in optsig.items():
        for i in range(len(items)):
            for k in range(i + 1, len(items)):
                (qi, ti), (qk, tk) = items[i], items[k]
                if jac(ti, tk) >= 0.6 and (qi, qk) not in seen_pairs:
                    seen_pairs.add((qi, qk))
                    add("INFO", qi, qmap[qi]["benchmark_display"] or qi, "near-duplicate",
                        "near-identical wording + options to %s — possible redundant pair." % qk)

    # ---- report ----
    order = {"CRIT": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (order[f[0]], f[1]))
    counts = defaultdict(int)
    print("=" * 100)
    print("DEEP METRIC DATA-INTEGRITY SWEEP  (%d live metrics, snapshot %d)" % (len(qs), SNAP))
    print("=" * 100)
    cur_sev = None
    for sev, qid, name, code, detail in findings:
        counts[sev] += 1
        if sev != cur_sev:
            print("\n----- %s -----" % sev); cur_sev = sev
        print("  [%-22s] %-16s %s" % (code, qid, (name or "")[:40]))
        print("        %s" % detail)
    print("\n" + "=" * 100)
    print("SUMMARY: %d CRIT  %d WARN  %d INFO   across %d live metrics" %
          (counts["CRIT"], counts["WARN"], counts["INFO"], len(qs)))
    if not counts["CRIT"]:
        print("No CRITICAL data-integrity faults: every live metric serves the data it holds.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
