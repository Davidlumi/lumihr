# -*- coding: utf-8 -*-
"""regen_question.py — parameterised single-question RE-SEED to a recalibrated
signed baseline, to the established regen discipline (cf.
regen_allowances_pensionable.py):

  * DRY RUN by default; double-guarded write (--write AND --confirmed-by-david);
  * append-only history: DELETE from `answers` (snapshot_id=1) ONLY, never from
    `answers_history`; re-INSERT into BOTH;
  * does NOT auto-aggregate — run `python aggregate.py` (run_snapshot(1)) after,
    or the API keeps serving the stale benchmark_snapshots payload;
  * touches ONLY the question id(s) named on the command line. Other questions
    in the pipeline are recalibrated in memory but never written.

REUSE, not reinvention. The org-blind calibration + generation is the SAME
machinery the original apply drivers use; the recalibrated signed baselines are
read LIVE from the seed modules (this script hardcodes no target):

  - 2026.1-additions pipeline  (apply_seed_2026_1_additions + seed_release_2026_1_additions)
      REW26_WEL_EAP, REW26_WEL_FINWELL, REW26_WEL_MH_SUPPORT, REW26_GOV_EU_PTD_PREP
  - 2026.2 pipeline            (apply_seed_2026_2 + seed_release_2026_2)
      REW262_GOV_SALHISTORY

remap_labels() is applied for the MH-provisions multi_select so generated values
carry the LIVE option labels (e.g. "MH first aiders"), not the script-side ones.
The seed modules live at the repo root, so the root is added to sys.path.

Usage:
  python regen_question.py --question-id REW26_WEL_EAP                 # dry run
  python regen_question.py --question-id REW26_WEL_EAP --target eap    # (target optional, validated)
  python regen_question.py --question-id REW262_GOV_SALHISTORY --write --confirmed-by-david
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from db import get_conn

TOL = 0.03

# live question id -> {pipeline, seed-module hint key, kind, friendly metric name}
REGISTRY = {
    "REW26_WEL_EAP":          {"pipe": "add1", "hint": "WELL_EAP",          "kind": "cat",   "metric": "eap"},
    "REW26_WEL_FINWELL":      {"pipe": "add1", "hint": "WELL_FINWELL",      "kind": "cat",   "metric": "finwell"},
    "REW26_WEL_MH_SUPPORT":   {"pipe": "add1", "hint": "WELL_MHPROVISIONS", "kind": "multi", "metric": "mhprovisions"},
    "REW26_GOV_EU_PTD_PREP":  {"pipe": "add1", "hint": "GOV_PTDREADY",      "kind": "cat",   "metric": "ptd"},
    "REW262_GOV_SALHISTORY":  {"pipe": "rel2", "hint": "REW262_GOV_SALHISTORY", "kind": "cat", "metric": "salhistory"},
}

_PIPE = {}   # pipe -> (A_driver, S_module, rows)


def calibrated_rows(pipe, conn):
    """Run the pipeline's own org-blind calibration ONCE and return its
    generated rows. Reproducibility is asserted (identical on re-draw)."""
    if pipe in _PIPE:
        return _PIPE[pipe]
    if pipe == "add1":
        import apply_seed_2026_1_additions as A          # noqa: E402
        import seed_release_2026_1_additions as S        # noqa: E402
        A.remap_labels()                                 # MH labels -> live option set
        orgs = A.build_orgs(conn)
        scales = S.calibrate(orgs)
        A.compensate(orgs, scales)
        rows = S.generate(orgs, scales)
        assert rows == S.generate(orgs, scales), "non-reproducible (add1)"
    else:
        import apply_seed_2026_2 as A                    # noqa: E402
        import seed_release_2026_2 as S                  # noqa: E402
        orgs = A.build_orgs(conn)
        A.calibrate_all(orgs)
        rows = S.generate(orgs)
        assert rows == S.generate(orgs), "non-reproducible (rel2)"
    _PIPE[pipe] = (A, S, rows)
    return _PIPE[pipe]


def evaluate(qid, conn):
    """Returns dict with this qid's generated (org,value) rows, target, realised,
    worst-delta, modal-ok. Asserts the registry id matches the pipeline id."""
    reg = REGISTRY[qid]
    A, S, rows = calibrated_rows(reg["pipe"], conn)
    hint = reg["hint"]
    if reg["pipe"] == "add1":
        assert A.ID_MAP[hint] == qid, "registry/ID_MAP mismatch: %s -> %s != %s" % (hint, A.ID_MAP[hint], qid)
        key = hint                                       # add1 rows are keyed by hint
    else:
        key = qid                                        # rel2 rows are keyed by live qid
    qrows = [(o, v) for (k, o, v) in rows if k == key]

    if reg["kind"] == "multi":
        target = S.SIGNED_MULTI[hint]
        realised = S.realised_multi(rows, hint, list(target))
        modal_ok = True                                  # multi: per-option tolerance only
    elif reg["pipe"] == "add1":
        target = S.SIGNED[hint]
        realised = S.realised_cat(rows, hint)
        modal_ok = max(realised, key=realised.get) == max(target, key=target.get)
    else:
        target = S.SIGNED_TARGETS[qid]
        realised = S.realised(rows, qid)
        modal_ok = max(realised, key=realised.get) == max(target, key=target.get)

    worst = max(abs(realised.get(o, 0) - target[o]) for o in target)
    return {"qrows": qrows, "target": target, "realised": realised,
            "worst": worst, "modal_ok": modal_ok, "kind": reg["kind"], "metric": reg["metric"]}


def main():
    ap = argparse.ArgumentParser(description="Re-seed one or more questions to their recalibrated signed baseline.")
    ap.add_argument("--question-id", action="append", default=[], metavar="LIVE_ID",
                    help="live question id to re-seed (repeatable)")
    ap.add_argument("--target", default=None,
                    help="optional friendly metric name; validated against the id if given")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    args = ap.parse_args()

    qids = args.question_id
    if not qids:
        print("STOP: pass at least one --question-id"); sys.exit(2)
    for qid in qids:
        if qid not in REGISTRY:
            print("STOP: %s is not an in-scope recalibration id. In scope: %s"
                  % (qid, ", ".join(REGISTRY))); sys.exit(2)
    if args.target and len(qids) == 1 and REGISTRY[qids[0]]["metric"] != args.target.lower():
        print("STOP: --target %r does not match %s (expected metric %r)"
              % (args.target, qids[0], REGISTRY[qids[0]]["metric"])); sys.exit(2)

    conn = get_conn()
    print("regen_question — DRY RUN (org-blind, reproducible) | TOL=%.0fpp\n" % (TOL * 100))
    fails = []
    results = {}
    for qid in qids:
        r = evaluate(qid, conn)
        results[qid] = r
        live_n = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND snapshot_id=1", (qid,)).fetchone()[0]
        bad = (r["worst"] > TOL) or (not r["modal_ok"])
        if bad:
            fails.append(qid)
        print("== %s  (%s, %s)  current live answers=%d ==" % (qid, r["metric"], r["kind"], live_n))
        print("   worst delta %.1fpp | modal %s | %s" % (
            r["worst"] * 100, "OK" if r["modal_ok"] else "FLIPPED",
            "WITHIN TOLERANCE" if not bad else "OUT OF TOLERANCE"))
        for o in r["target"]:
            print("      %-46s signed %5.1f%%  realised %5.1f%%" % (
                o[:44], r["target"][o] * 100, r["realised"].get(o, 0) * 100))
        # show live-vs-new marginal so the change is legible
        if r["kind"] != "multi":
            live = conn.execute(
                "SELECT value, COUNT(*) FROM answers WHERE question_id=? AND snapshot_id=1 GROUP BY value", (qid,)).fetchall()
            lt = sum(x[1] for x in live) or 1
            ld = {v: c / lt for v, c in live}
            print("      (live now: %s)" % ", ".join("%s %.1f%%" % (v, p * 100) for v, p in sorted(ld.items(), key=lambda x: -x[1])))
        print()

    if fails:
        print("NOT WITHIN TOLERANCE: %s — refusing to write." % fails)
        sys.exit(1)

    if not (args.write and args.confirmed):
        print("DRY RUN — pass --write --confirmed-by-david to apply the re-seed.")
        print("(remember: re-aggregate afterwards — python aggregate.py)")
        return

    # ---- WRITE PATH (double-guarded, append-only history) -------------------
    written = {}
    for qid in qids:
        rows = results[qid]["qrows"]
        # DELETE only from `answers` (snapshot 1); answers_history is append-only.
        conn.execute("DELETE FROM answers WHERE question_id=? AND snapshot_id=1", (qid,))
        for oid, val in rows:
            for table in ("answers", "answers_history"):
                conn.execute("INSERT INTO %s(org_id, snapshot_id, question_id, matrix_row_id, value) "
                             "VALUES (?,1,?, '', ?)" % table, (oid, qid, val))
        written[qid] = len(rows)
    conn.commit()
    print("WRITTEN (answers replaced; answers_history appended):")
    for qid, n in written.items():
        hist = conn.execute("SELECT COUNT(*) FROM answers_history WHERE question_id=?", (qid,)).fetchone()[0]
        print("   %-26s %d answers re-seeded | answers_history now %d rows" % (qid, n, hist))
    print("\nNOT re-aggregated by this script — run:  python aggregate.py   "
          "(refreshes benchmark_snapshots; required before the API reflects the change)")
    print("\nINTEGRITY STATEMENT: firmographic-only conditioning; whole-metric org-blind "
          "re-draw via the original seed pipeline; calibrated to the recalibrated SIGNED "
          "baselines (read live from the seed modules, no hand-tuning); ONLY the named "
          "question id(s) written; answers_history retains the prior version.")


if __name__ == "__main__":
    main()
