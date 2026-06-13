# -*- coding: utf-8 -*-
"""QA — ordered-scale routing integrity (Signals Phase 2 prerequisite).

Asserts ordered_scale_routing.json gives every ordered/outlier metric an
EXPLICIT magnitude order (scales[qid].scale_low_to_high) validated against the
REAL question options, so the mechanism never infers rank from option-array
index and a typo / silently-dropped option fails the gate. Pure library.
"""
import json
import os
import sys
from library import load_questions

ROUTING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ordered_scale_routing.json")
LENSES = {"attract", "retain", "engage", "save"}
DIRECTIONS = {"higher_is_better", "lower_is_better", "neutral_outlier"}

PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:160] + "]") if detail else ""))


def main():
    qs = load_questions()
    cfg = json.load(open(ROUTING))
    outlier = cfg.get("ordered_outlier", [])
    behind_x = cfg.get("behind_explicit", [])
    anchor = cfg.get("anchor_risk", [])
    scales = cfg.get("scales", {})
    rerouted = set(cfg.get("_david_ratified_2026_06_13", {}).get("reroute_to_phase3_prevalence", []))
    min_pts = cfg.get("thresholds", {}).get("min_scale_points", 3)

    # 1) firing metrics (outlier + behind_explicit) each need a scale
    firing = list(outlier) + list(behind_x)
    nodup = len(firing) == len(set(firing))
    check("no metric appears twice across firing lists", nodup,
          [x for x in firing if firing.count(x) > 1])
    noscale = [qid for qid in firing if qid not in scales]
    check("every firing metric has an explicit scale", not noscale, noscale)

    # 2) ids resolve to active reward questions
    bad = [qid for qid in firing if not (qs.get(qid) and qs[qid].superpower == "Reward" and qs[qid].status == "active")]
    check("every routed id is an active reward question", not bad, bad)

    # 3) scales validate against the REAL options
    ghosts, dropped, thin, badlens = [], [], [], []
    for qid in firing:
        q = qs.get(qid)
        spec = scales.get(qid, {})
        if not q:
            continue
        real = {o["label"] for o in (q.options or [])}
        scale = spec.get("scale_low_to_high", [])
        na = spec.get("na", [])
        ghost = [l for l in (scale + na) if l not in real]
        if ghost:
            ghosts.append((qid, ghost))
        missing = [l for l in real if l not in set(scale) | set(na)]
        if missing:
            dropped.append((qid, missing))
        if len(scale) < min_pts:
            thin.append((qid, "%d points" % len(scale)))
        if spec.get("lens") and spec["lens"] not in LENSES:
            badlens.append((qid, spec.get("lens")))
    check("scale labels all match real options (no typos)", not ghosts, ghosts[:4])
    check("every non-listed option is placed (scale or na) — nothing silently dropped", not dropped, dropped[:4])
    check("every scale has >= %d magnitude points" % min_pts, not thin, thin)
    check("lens recommendations are valid", not badlens, badlens)

    # 4) behind_explicit metrics carry an explicit direction
    nodir = [qid for qid in behind_x if scales.get(qid, {}).get("direction") not in DIRECTIONS]
    check("every behind_explicit metric has an explicit direction", not nodir, nodir)

    # 5) anchor-risk fully resolved (none left parked) and not firing without a scale
    check("anchor_risk is empty — all 3 resolved per David's ratification", not anchor, anchor)

    # 6) re-routed (Phase 3) metrics never fire here
    leak = rerouted & set(firing)
    check("Phase-3 re-routed metrics are excluded from all firing lists", not leak, sorted(leak))

    # depth_matrix (Mechanism B): real matrix questions, valid lens + covered value
    dm = cfg.get("depth_matrix", {})
    dm_bad = [qid for qid in dm if not (qs.get(qid) and qs[qid].type == "matrix" and qs[qid].status == "active")]
    check("every depth_matrix id is an active matrix question", not dm_bad, dm_bad)
    dm_lens = [(qid, s.get("lens")) for qid, s in dm.items() if s.get("lens") not in LENSES]
    check("depth_matrix lens recommendations are valid", not dm_lens, dm_lens)
    dm_cov = [qid for qid, s in dm.items() if not s.get("covered")]
    check("every depth_matrix metric defines a 'covered' value", not dm_cov, dm_cov)

    print("\n  behind:%d  behind_explicit:%d  ordered_outlier:%d  depth_matrix:%d  scales:%d  rerouted(P3):%d"
          % (len(cfg.get("behind", [])), len(behind_x), len(outlier), len(dm), len(scales), len(rerouted)))
    print("\n== ORDERED-ROUTING GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
