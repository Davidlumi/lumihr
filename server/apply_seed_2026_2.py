# -*- coding: utf-8 -*-
"""Driver for seed_release_2026_2.py: real-registry orgs, FULL calibration to
David's signed baselines, double-guarded DB write.

WHY A DRIVER: the provided script's calibrate() only damps TILT strength —
two gaps remained against the firewall's "realised must land on the signed
baseline": (1) the action-plan multi_select is never calibrated (its tilts
pushed realised has-plan to 47% vs the signed 30%); (2) with tilts already
at ~zero, four questions still sat 3-6pp off target — fixed-seed sampling
variance the tilt loop cannot reach, including a modal flip on
pay-in-adverts. The established calibration precedent (pay-frequency,
2026-06-12: "first draw landed hot; coefficients reduced; re-drawn") is to
adjust the INPUT constants until the REALISED output hits the documented
baseline. This driver does exactly that, in memory, on the script's own
tunable CONSTANTS block:
  - tilt damping via the script's calibrate() (unchanged), then
  - base-distribution compensation: dist += (signed - realised), clamped and
    renormalised, iterated to tolerance — same rule for every org, same
    fixed seeds, no per-org or per-option favour (the target IS David's).
Org-blind, seeded, reproducible: rerunning this driver yields identical data.

Write path: --write --confirmed-by-david inserts into the CORE answer store
(these are core questions now) + answers_history, then re-aggregates.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import seed_release_2026_2 as S
from db import get_conn

TOL = 0.03
ORGS_PATH = "/tmp/orgs_2026_2.json"


def build_orgs(conn):
    MID = {"50-249": 150, "250-999": 600, "1,000-4,999": 3000, "5,000-9,999": 7500, "10,000+": 15000}
    out = []
    for r in conn.execute("SELECT * FROM orgs WHERE source='seed' AND submission_complete=1 ORDER BY org_id"):
        reg = json.loads(r["registry_json"]) if r["registry_json"] else {}
        ind = reg.get("Industry") or r["industry"] or ""
        out.append({
            "org_id": r["org_id"],
            "fte_band_midpoint": MID.get(reg.get("FTE_Band") or r["fte_band"], 500),
            "hr_maturity": reg.get("HR_Maturity") or "Developing",
            "ownership_type": "Public sector" if (reg.get("Ownership_Type") or r["ownership_type"]) == "Public Sector Body"
                              else (reg.get("Ownership_Type") or r["ownership_type"] or "Private"),
            "frontline_pct": reg.get("Workforce_Frontline_%") if reg.get("Workforce_Frontline_%") is not None else 35,
            "shift_pct": reg.get("Workforce_Shift_%") if reg.get("Workforce_Shift_%") is not None else 15,
            "industry": "Technology" if ind == "Technology, Software & Digital" else ind,
        })
    return out


def calibrate_all(orgs):
    # 1. the script's own tilt damping
    for qid, target in S.SIGNED_TARGETS.items():
        S.calibrate(orgs, qid, target)
    # 2. action plan: damp tilts + compensate p_has_plan to the signed 30%
    ap = S.BASELINES["REW262_GOV_ACTIONPLAN"]
    signed_p = 0.30
    orig_tilt = copy.deepcopy(ap["tilt"])
    base0 = ap["p_has_plan"]
    for _ in range(20):
        rows = S.generate(orgs)
        vals = [v for q, o, v in rows if q == "REW262_GOV_ACTIONPLAN"]
        realised_p = sum(1 for v in vals if v != "None") / len(vals)
        if abs(realised_p - signed_p) <= TOL:
            break
        ap["p_has_plan"] = max(0.02, min(0.9, ap["p_has_plan"] + (signed_p - realised_p) * 0.8))
        ap["tilt"] = {f: d * 0.6 for f, d in ap["tilt"].items()}
    print("action plan calibrated: base %.2f -> %.2f, realised has-plan %.1f%% (signed 30%%)" % (
        base0, ap["p_has_plan"], realised_p * 100))
    # 3. base-distribution compensation for the residual sampling offsets
    for qid, target in S.SIGNED_TARGETS.items():
        spec = S.BASELINES[qid]
        for _ in range(20):
            rows = S.generate(orgs)
            r = S.realised(rows, qid)
            worst = max(abs(r.get(o, 0) - target[o]) for o in target)
            if worst <= TOL:
                break
            d = {o: max(0.001, spec["dist"].get(o, 0) + (target[o] - r.get(o, 0)) * 0.8) for o in target}
            s = sum(d.values())
            spec["dist"] = {o: v / s for o, v in d.items()}


def main():
    conn = get_conn()
    orgs = build_orgs(conn)
    json.dump(orgs, open(ORGS_PATH, "w"))
    print("orgs: %d (real registry; firmographics only)" % len(orgs))
    calibrate_all(orgs)
    rows = S.generate(orgs)
    rows2 = S.generate(orgs)
    assert rows == rows2, "non-reproducible"
    print("reproducible: identical on re-run")

    print("\nREALISED vs SIGNED (final, post-calibration):")
    fails = []
    for qid, target in S.SIGNED_TARGETS.items():
        r = S.realised(rows, qid)
        worst = max(abs(r.get(o, 0) - target[o]) for o in target)
        modal_signed = max(target, key=target.get)
        modal_real = max(r, key=r.get)
        if worst > TOL or modal_real != modal_signed:
            fails.append(qid)
        print("  %-28s worst delta %.1fpp | modal signed=%r realised=%r" % (
            qid, worst * 100, modal_signed[:24], modal_real[:24]))
        for o in target:
            print("      %-46s signed %4.1f%%  realised %4.1f%%" % (o[:44], target[o] * 100, r.get(o, 0) * 100))
    vals = [v for q, o, v in rows if q == "REW262_GOV_ACTIONPLAN"]
    has = sum(1 for v in vals if v != "None") / len(vals)
    print("  %-28s signed has-plan 30.0%%  realised %.1f%%" % ("REW262_GOV_ACTIONPLAN", has * 100))
    if abs(has - 0.30) > TOL:
        fails.append("REW262_GOV_ACTIONPLAN")
    na_counts = {}
    for qid in ("REW262_PAY_GUARANTEEDHRS", "REW262_PAY_CANCELLEDSHIFT", "REW262_PAY_SHIFTNOTICE"):
        na = sum(1 for q, o, v in rows if q == qid and v == "Not applicable")
        na_counts[qid] = na
        print("  %-28s N/A (salaried/no-shift orgs): %d of 220 -> applicable n=%d" % (qid, na, 220 - na))
    if fails:
        print("\nNOT WITHIN TOLERANCE: %s — refusing to write." % fails)
        sys.exit(1)

    if not ("--write" in sys.argv and "--confirmed-by-david" in sys.argv):
        print("\nDRY RUN — pass --write --confirmed-by-david to insert into the core store.")
        return
    existing = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id LIKE 'REW262_%'").fetchone()[0]
    assert existing == 0, "REW262 answers already present (%d) — refusing" % existing
    for qid, oid, val in rows:
        for table in ("answers", "answers_history"):
            conn.execute("INSERT INTO %s(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?, '', ?)" % table,
                         (oid, qid, val))
    conn.commit()
    print("\nwritten: %d responses across 12 questions (core store)" % len(rows))
    from aggregate import run_snapshot
    run_snapshot(1, verbose=False)
    print("re-aggregated")
    demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()[0]
    demo_vals = {q: v for q, o, v in rows if o == demo}
    print("\nINTEGRITY STATEMENT: no existing metric touched (only REW262_* rows inserted, "
          "guarded by the zero-pre-existing assertion); no value hand-tuned (whole-metric seeded "
          "draw, calibrated to David's signed baselines as targets); the demo org is one of the "
          "220 and was drawn by the SAME blind rule as every other org — its drawn answers, for "
          "the record: %s" % demo_vals)


if __name__ == "__main__":
    main()
