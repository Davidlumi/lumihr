# -*- coding: utf-8 -*-
"""QA — ordered-scale routing integrity (Signals Phase 2 prerequisite).

Asserts ordered_scale_routing.json gives every ordered/outlier metric an
EXPLICIT magnitude order so the signal mechanism never infers rank from option
array index. Validates the authored scales against the REAL question options, so
a typo or a silently-dropped option fails the gate. Pure library, no server.
"""
import json
import os
import sys
from library import load_questions

ROUTING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ordered_scale_routing.json")
LENSES = {"attract", "retain", "engage", "save"}
DIRECTIONS = {"higher_is_better", "lower_is_better", "neutral_outlier"}
# the 22 ordered-outlier + 3 anchor IDs the brief hands us
BRIEF_OUTLIER = {"EXT_REW_GAP_003", "EXT_REW_GAP_009", "EXT_REW_GAP_012", "REW_BEN_045", "REW_BEN_047",
                 "REW_BEN_048", "REW_BEN_100", "REW_BEN_102", "REW_FAI_STUDY_TIME_93b6ef22", "REW_INC_061",
                 "REW_INC_103", "REW_INC_104", "REW_PAY_005", "REW_PAY_014", "REW_PAY_097",
                 "REW_PAY_TIPS_EXIST_7c80c508", "REW_PRO_035", "PROP_634adacd", "PROP_3d4fc4e7",
                 "PROP_36b990f9", "PROP_dff9a2a5", "PROP_e1d1e604"}
BRIEF_ANCHOR = {"REW_Q049530", "REW_PAY_003", "PROP_8e0b6316"}

PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:160] + "]") if detail else ""))


def main():
    qs = load_questions()
    cfg = json.load(open(ROUTING))
    outlier = cfg.get("ordered_outlier", {})
    anchor = cfg.get("anchor_risk", {})
    reroute = cfg.get("review_reroute", {})
    min_pts = cfg.get("thresholds", {}).get("min_scale_points", 3)

    sections = {"ordered_outlier": outlier, "anchor_risk": anchor, "review_reroute": reroute}
    allids = [qid for s in sections.values() for qid in s]

    # 1) no metric in two sections
    dup = [q for q in allids if allids.count(q) > 1]
    check("no metric appears in two routing sections", not dup, sorted(set(dup)))

    # 2) every id resolves to an active reward question
    bad = [qid for qid in allids if not (qs.get(qid) and qs[qid].superpower == "Reward" and qs[qid].status == "active")]
    check("every routed id is an active reward question", not bad, bad)

    # 3) scales validate against the REAL options (no typos, no dropped option, >= min points)
    label_problems, completeness, thin, baddir, badlens = [], [], [], [], []
    for sect in (outlier, anchor):
        for qid, spec in sect.items():
            q = qs.get(qid)
            if not q:
                continue
            real = {o["label"] for o in (q.options or [])}
            scale = spec.get("scale_low_to_high", [])
            na = spec.get("na", [])
            placed = set(scale) | set(na)
            # 3a every authored label is a real option
            ghost = [l for l in (scale + na) if l not in real]
            if ghost:
                label_problems.append((qid, "not real options: %s" % ghost))
            # 3b every real option is accounted for (in scale or na) — no silent drop
            missing = [l for l in real if l not in placed]
            if missing:
                completeness.append((qid, "options neither in scale nor na: %s" % missing))
            # 3c duplicates in scale
            if len(scale) != len(set(scale)):
                label_problems.append((qid, "duplicate scale label"))
            # 3d enough points to be a meaningful ordinal
            if len(scale) < min_pts:
                thin.append((qid, "%d scale points" % len(scale)))
            # 3e lens valid
            if spec.get("lens") and spec["lens"] not in LENSES:
                badlens.append((qid, spec.get("lens")))
    check("scale labels all match real options (no typos)", not label_problems, label_problems[:4])
    check("every non-listed option is placed (scale or na) — nothing silently dropped", not completeness, completeness[:4])
    check("every scale has >= %d magnitude points" % min_pts, not thin, thin)
    check("lens recommendations are valid", not badlens, badlens)

    # 4) anchor_risk carry an explicit direction
    nodir = [qid for qid, s in anchor.items() if s.get("direction") not in DIRECTIONS]
    check("every anchor-risk metric has an explicit direction set", not nodir, nodir)

    # 5) the 3 anchor-risk IDs are resolved (present, with direction) and NOT firing as outliers
    check("the 3 anchor-risk IDs are resolved with explicit direction", BRIEF_ANCHOR <= set(anchor), sorted(BRIEF_ANCHOR - set(anchor)))
    check("anchor-risk IDs are not in the ordered_outlier firing set", not (BRIEF_ANCHOR & set(outlier)), sorted(BRIEF_ANCHOR & set(outlier)))

    # 6) every brief outlier id has a home (outlier OR review_reroute) — none silently lost
    homed = set(outlier) | set(reroute)
    lost = BRIEF_OUTLIER - homed
    check("every brief ordered-outlier id is routed (firing or flagged for re-route)", not lost, sorted(lost))

    # 7) review_reroute metrics cannot fire (not in ordered_outlier)
    leak = set(reroute) & set(outlier)
    check("review_reroute metrics are excluded from the firing set", not leak, sorted(leak))

    print("\n  ordered_outlier (firing): %d | anchor_risk (resolved, parked): %d | review_reroute (held): %d"
          % (len(outlier), len(anchor), len(reroute)))
    print("\n== ORDERED-ROUTING GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
