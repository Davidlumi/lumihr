# -*- coding: utf-8 -*-
"""Driver for seed_release_2026_1_additions.py — real ids, real labels,
real registry, full calibration, double-guarded write.

RESOLUTIONS made at apply time (reported in the run output):
- id_hint -> live REW26_* mapping (all 14 matched; refuses otherwise).
- LIVE OPTION LABELS differ from the script constants on 5 labels
  (MH first aiders / Digital app / MH days / >Annual / >8%) — the driver
  remaps the constants to the live labels so every stored value matches the
  library option list exactly (the engine matches on labels).
- The levelling question's LIVE schema is multi_select (the brief's
  anticipated case): its options are mutually exclusive coverage levels, so
  each org draws ONE option and calibration verifies PER-OPTION prevalence
  against the signed distribution (which sums to 100 by design).

Calibration covers all 14: the script's tilt-damping loop for single/yes-no,
plus driver-side INPUT compensation (the documented 2026.2 pattern) for any
residual fixed-seed sampling offset — including the multi_select marginals
(none_prob / option_probs) and the numerics (na_share / median scale).
Targets are David's signed baselines; same rule for every org; same seeds.

Write: --write --confirmed-by-david; refuses if ANY of the 14 already has
answers; inserts into answers + answers_history; re-aggregates.
"""
import copy
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import seed_release_2026_1_additions as S
from db import get_conn
from apply_seed_2026_2 import build_orgs   # the same real-registry mapping

TOL = 0.03

ID_MAP = {"WELL_EAP": "REW26_WEL_EAP", "WELL_MHPROVISIONS": "REW26_WEL_MH_SUPPORT",
          "WELL_FINWELL": "REW26_WEL_FINWELL", "WELL_BUDGET": "REW26_WEL_BUDGET",
          "WELL_SCREENING": "REW26_WEL_SCREENING", "WELL_STRATEGY": "REW26_WEL_STRATEGY",
          "PEN_TYPE": "REW26_BEN_PENSION_TYPE", "PEN_PLSA": "REW26_BEN_PLSA_QM",
          "PEN_MATCH": "REW26_BEN_PENSION_MATCH", "PEN_SALSAC": "REW26_BEN_SALSAC",
          "PEN_COSTPCT": "REW26_BEN_PENSION_COST_SHARE", "PAY_SKILLSPAY": "REW26_PAY_SKILLS_PAY",
          "PAY_LEVELLING": "REW26_PAY_JOBEVAL_COVERAGE", "GOV_PTDREADY": "REW26_GOV_EU_PTD_PREP"}

# script-constant label -> LIVE library option label
LABEL_MAP = {
    "WELL_MHPROVISIONS": {"Mental health first aiders": "MH first aiders",
                          "Digital wellbeing app": "Digital app",
                          "Dedicated MH days": "MH days"},
    "WELL_STRATEGY": {"More than annually": ">Annual"},
    "PEN_MATCH": {"More than 8%": ">8%"},
}


def remap_labels():
    for hint, mapping in LABEL_MAP.items():
        spec = S.BASELINES[hint]
        for old, new in mapping.items():
            for field in ("dist", "option_probs"):
                if field in spec and old in spec[field]:
                    spec[field][new] = spec[field].pop(old)
            for adj in (spec.get("tilt") or {}).values():
                if isinstance(adj, dict) and old in adj:
                    adj[new] = adj.pop(old)
        for tgt in (S.SIGNED, S.SIGNED_MULTI):
            if hint in tgt and any(o in tgt[hint] for o in mapping):
                for old, new in mapping.items():
                    if old in tgt[hint]:
                        tgt[hint][new] = tgt[hint].pop(old)


def compensate(orgs, scales):
    """Driver-side residual calibration (the documented 2026.2 pattern):
    nudge INPUT constants until realised hits the signed target — categorical
    dists, multi marginals (none_prob/option_probs) and numeric na/median."""
    for hint, tgt in S.SIGNED.items():
        spec = S.BASELINES[hint]
        for _ in range(20):
            rows = S.generate(orgs, scales)
            r = S.realised_cat(rows, hint)
            if max(abs(r.get(o, 0) - tgt[o]) for o in tgt) <= TOL:
                break
            d = {o: max(0.001, spec["dist"].get(o, 0) + (tgt[o] - r.get(o, 0)) * 0.8) for o in tgt}
            s = sum(d.values())
            spec["dist"] = {o: v / s for o, v in d.items()}
    for hint, tgt in S.SIGNED_MULTI.items():
        spec = S.BASELINES[hint]
        for _ in range(20):
            rows = S.generate(orgs, scales)
            r = S.realised_multi(rows, hint, list(tgt))
            worst = max(abs(r.get(o, 0) - tgt[o]) for o in tgt)
            if worst <= TOL:
                break
            spec["none_prob"] = max(0.01, min(0.9, spec["none_prob"] + (tgt["None"] - r.get("None", 0)) * 0.8))
            for o in spec["option_probs"]:
                spec["option_probs"][o] = max(0.01, min(0.99,
                    spec["option_probs"][o] + (tgt[o] - r.get(o, 0)) * 0.8))
    for hint, tgt in S.SIGNED_NUM.items():
        spec = S.BASELINES[hint]
        for _ in range(20):
            rows = S.generate(orgs, scales)
            r = S.realised_num(rows, hint)
            ok_na = abs(r["na_share"] - tgt["na_share"]) <= TOL
            ok_med = abs(r["median"] - tgt["median"]) / max(tgt["median"], 1) <= TOL
            if ok_na and ok_med:
                break
            spec["na_share"] = max(0.0, min(0.95, spec["na_share"] + (tgt["na_share"] - r["na_share"]) * 0.8))
            if r["median"]:
                spec["median"] = max(0.5, spec["median"] * (tgt["median"] / r["median"]) ** 0.8)


def main():
    conn = get_conn()
    # mapping must resolve completely or we stop
    for hint, qid in ID_MAP.items():
        if conn.execute("SELECT 1 FROM questions WHERE id=? AND release_entered='2026.1'", (qid,)).fetchone() is None:
            print("STOP: %s -> %s is not a live 2026.1 question" % (hint, qid))
            sys.exit(1)
    print("id mapping: all 14 hints matched to live 2026.1 questions")
    remap_labels()
    print("labels remapped to live options:", {h: list(m.values()) for h, m in LABEL_MAP.items()})
    print("levelling live schema: multi_select (mutually exclusive coverage levels -> one pick per org,")
    print("  calibrated on per-option prevalence)")

    orgs = build_orgs(conn)
    print("orgs: %d (real registry)" % len(orgs))
    scales = S.calibrate(orgs)
    compensate(orgs, scales)
    rows = S.generate(orgs, scales)
    assert rows == S.generate(orgs, scales), "non-reproducible"
    print("reproducible: identical on re-run\n")

    print("REALISED vs SIGNED (all 14):")
    fails = []
    for hint, tgt in S.SIGNED.items():
        r = S.realised_cat(rows, hint)
        worst = max(abs(r.get(o, 0) - tgt[o]) for o in tgt)
        modal_ok = max(r, key=r.get) == max(tgt, key=tgt.get)
        if worst > TOL or not modal_ok:
            fails.append(hint)
        print("  %-18s worst %4.1fpp modal %s" % (hint, worst * 100, "OK" if modal_ok else "FLIPPED"))
        for o in tgt:
            print("      %-22s signed %4.1f%%  realised %4.1f%%" % (o, tgt[o] * 100, r.get(o, 0) * 100))
    for hint, tgt in S.SIGNED_MULTI.items():
        r = S.realised_multi(rows, hint, list(tgt))
        worst = max(abs(r.get(o, 0) - tgt[o]) for o in tgt)
        if worst > TOL:
            fails.append(hint)
        print("  %-18s (multi, per-option marginals) worst %4.1fpp" % (hint, worst * 100))
        for o in tgt:
            print("      %-22s signed %4.1f%%  realised %4.1f%%" % (o, tgt[o] * 100, r.get(o, 0) * 100))
    for hint, tgt in S.SIGNED_NUM.items():
        r = S.realised_num(rows, hint)
        ok = abs(r["na_share"] - tgt["na_share"]) <= TOL and abs(r["median"] - tgt["median"]) / max(tgt["median"], 1) <= TOL
        if not ok:
            fails.append(hint)
        napp = sum(1 for q, o, v in rows if q == hint and v != "Not applicable")
        print("  %-18s (numeric) signed median %s / N/A %.0f%% -> realised median %s / N/A %.0f%% (applicable n=%d)" % (
            hint, tgt["median"], tgt["na_share"] * 100, r["median"], r["na_share"] * 100, napp))
    if fails:
        print("\nNOT WITHIN TOLERANCE: %s — refusing to write." % fails)
        sys.exit(1)

    if not ("--write" in sys.argv and "--confirmed-by-david" in sys.argv):
        print("\nDRY RUN — pass --write --confirmed-by-david to insert.")
        return
    live_qids = list(ID_MAP.values())
    existing = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id IN (%s)" %
                            ",".join("?" * len(live_qids)), live_qids).fetchone()[0]
    assert existing == 0, "answers already exist (%d) — refusing" % existing
    for hint, oid, val in rows:
        qid = ID_MAP[hint]
        for table in ("answers", "answers_history"):
            conn.execute("INSERT INTO %s(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?, '', ?)" % table,
                         (oid, qid, val))
    conn.commit()
    print("\nwritten: %d responses across 14 questions" % len(rows))
    from aggregate import run_snapshot
    run_snapshot(1, verbose=False)
    print("re-aggregated")
    demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()[0]
    demo_vals = {ID_MAP[q]: v for q, o, v in rows if o == demo}
    print("\nINTEGRITY STATEMENT: firmographic-only conditioning; seeded "
          "f'{qid}|2026-06-12|{org_id}'; org-blind whole-metric draw; no hand-tuning "
          "(calibration targets are David's signed baselines); ONLY these 14 questions' "
          "data added (zero-pre-existing assertion); the demo org drawn by the same "
          "blind rule — its answers for the record: %s" % demo_vals)


if __name__ == "__main__":
    main()
