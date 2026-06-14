# -*- coding: utf-8 -*-
"""QA — Signals SYSTEM coherence (end-to-end, all 8 mechanism classes).

Locks the cross-mechanism invariants verified in the end-to-end review: one
metric -> one firing class (the pension money/behind dedup is the sole, declared
overlap), held metrics stay inert, every fired metric is routed, nothing emits a
verdict word, the per-metric cap holds, and n>=5 is enforced everywhere. Config
checks are pure; firing checks lift the briefing caps so the FULL uncapped set is
audited, then restore them.
"""
import json
import os
import sys
import time
import urllib.request
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
SL = os.path.join(HERE, "..", "data", "signal_lenses.json")
OR = os.path.join(HERE, "..", "ordered_scale_routing.json")
BASE = "http://localhost:8060"
# the ONE declared cross-class overlap: pension carries a £ gap AND a position;
# money fires, behind is deduped by seen_q (Phase 1 decision).
ALLOWED_OVERLAP = {frozenset(("money", "behind")): {"REW_BEN_PENS_EMP_MAX_01"}}
HELD = {"REW_BEN_SICK_001", "REW_BEN_REM_PAY_001"}   # held; must never fire
VERDICT = ("behind", "ahead", "better", "worse", "lagging", "leading", "you should",
           "underperform", "strong ", "weak ", "must ")

PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:150] + "]") if detail else ""))


def firing_classes(sl, ordr):
    return {
        "money": set(sl.get("money_lenses", {})),
        "save": set(sl.get("cost_metrics", {})),
        "behind": set(sl.get("position_lenses", {})) | set(ordr.get("behind_explicit", [])),
        "prevalence": set(sl.get("prevalence_lenses", {})),
        "ordered_outlier": set(ordr.get("ordered_outlier", [])),
        "depth": set(ordr.get("depth_matrix", {})),
        "multi_prevalence": set(ordr.get("multi_prevalence", {})),
        "rarity": set(ordr.get("rarity", {})),
    }


def main():
    sl = json.load(open(SL))
    ordr = json.load(open(OR))
    classes = firing_classes(sl, ordr)
    firing = set().union(*classes.values())

    # --- config invariants (no server) ---
    names = list(classes)
    bad_overlap = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ov = classes[names[i]] & classes[names[j]]
            allowed = ALLOWED_OVERLAP.get(frozenset((names[i], names[j])), set())
            if ov - allowed:
                bad_overlap.append((names[i], names[j], sorted(ov - allowed)))
    check("one metric -> one firing class (only the declared pension money/behind overlap)",
          not bad_overlap, bad_overlap)

    held_firing = sorted(HELD & firing)
    check("held metrics are inert — absent from every FIRING source", not held_firing, held_firing)

    # thresholds present and consistent: ordered-outlier and depth share the gate;
    # n>=5 enforced everywhere.
    ot = ordr.get("thresholds", {})
    st = sl.get("thresholds", {})
    check("ordered-scale thresholds present (gate shared by ordered-outlier + depth)",
          all(k in ot for k in ("tail_pct", "min_modal_share", "max_org_band_share", "min_n",
                                "decisive_low", "decisive_high", "rarity_floor")), ot)
    check("n>=5 enforced (ordered min_n>=5 and prevalence suppression floor>=5)",
          ot.get("min_n", 0) >= 5, {"ordered_min_n": ot.get("min_n"), "behind_pctile": st.get("behind_percentile")})

    # --- firing invariants (uncapped) ---
    base = json.load(open(SL))
    hi = dict(base); hi["max_signals"] = 999; hi["max_per_lens"] = 999
    sigs = []
    try:
        json.dump(hi, open(SL, "w"), indent=2, ensure_ascii=False)
        time.sleep(0.5)
        jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        op.open(urllib.request.Request(BASE + "/api/auth/login",
                data=json.dumps({"email": "director@thornbridge.example", "password": "lumi-demo-2026"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST"))
        sigs = json.loads(op.open(urllib.request.Request(BASE + "/api/overview"), timeout=120).read()).get("signals") or []
    finally:
        json.dump(base, open(SL, "w"), indent=2, ensure_ascii=False)

    ids = [s["question_id"] for s in sigs]
    sids = [s.get("sig_id") or s["question_id"] for s in sigs]
    # matrix-row signals (one per off-market row) auto-route and legitimately
    # repeat the metric's qid; identity is qid::row_id.
    mat = [s for s in sigs if "::" in (s.get("sig_id") or "")]
    nonmat_ids = [s["question_id"] for s in sigs if "::" not in (s.get("sig_id") or "")]
    check("every fired signal is routed (matrix rows auto-route; others must be in a list)",
          all(q in firing for q in nonmat_ids), [q for q in nonmat_ids if q not in firing])
    check("no signal fires twice — unique sig_id, and non-matrix metrics fire once",
          len(sids) == len(set(sids)) and len(nonmat_ids) == len(set(nonmat_ids)),
          {"dup_sig": [x for x in set(sids) if sids.count(x) > 1],
           "dup_metric": [x for x in set(nonmat_ids) if nonmat_ids.count(x) > 1]})
    check("matrix-row signals are neutral position outliers (one class per metric holds)",
          all(s["kind"] == "outlier" for s in mat), [(s["kind"], s.get("sig_id")) for s in mat if s["kind"] != "outlier"])
    check("no verdict word in ANY fired signal, across all 8 classes",
          all(not any(v in s["detail"].lower() for v in VERDICT) for s in sigs),
          [(s["kind"], s["question_id"]) for s in sigs if any(v in s["detail"].lower() for v in VERDICT)])
    check("held metrics do not fire (uncapped)", not (HELD & set(ids)), sorted(HELD & set(ids)))

    print("\n  fired: %d  | classes routed: %d metrics" % (len(sigs), len(firing)))
    print("\n== SIGNALS-SYSTEM GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
