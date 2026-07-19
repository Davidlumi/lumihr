# -*- coding: utf-8 -*-
"""migrate_r3sw6_pmi_rebase.py — PMI premium re-base: individual-policy -> group scheme.

New medians (ruled): Single £800 (grade B sourced) / Partner £1,600 (EST 2x) /
Family £2,000 (EST 2.5x). Middle-50%% bands ±25%% of median by construction:
per-org multiplier m uniformly spaced over [0.5, 1.5], LATENT-ranked descending
(richer orgs run richer schemes), the SAME m across all three tiers (org-coherent
ladder), values rounded to £10. Uniform spacing puts P25/P50/P75 at exactly
0.75/1.00/1.25 x median (bands 600-1000 / 1200-2000 / 1500-2500).
Split verdict rides in config/code (unbenchmarked_rows partner+family).
Dry-run default; --write requires --confirmed-by-david. Emits r3sw6_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent

QID = "3faf1f0c-f753-497f-a395-384bba38c5e3"
MEDIANS = {"single": 800, "partner": 1600, "family": 2000}
STAMP = "2026-07-18 r3sw6 pmi group re-base"
PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, _p))).items() if isinstance(v, dict)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()
    ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                        WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (QID,)).fetchone()[0]
    assert ns == 0, "non-seed answers — ABORT"

    orgs = sorted({o for (o,) in cur.execute(
        "SELECT DISTINCT org_id FROM answers WHERE question_id=?", (QID,))},
        key=lambda o: (-latent(o, PROF), hashlib.sha256((QID + "|" + o).encode()).hexdigest()))
    n = len(orgs)
    # m uniformly spaced 1.5 -> 0.5 down the latent ranking (top latent = richest scheme)
    mult = {o: 1.5 - (i / (n - 1)) if n > 1 else 1.0 for i, o in enumerate(orgs)}
    newvals = {(o, t): int(round(MEDIANS[t] * mult[o] / 10.0)) * 10 for o in orgs for t in MEDIANS}
    # Demo org pinned to David's specified display values (680/1200/1600 = 0.85/0.75/0.80
    # of the new medians — the below-median demo narrative, ruled in the re-base prompt).
    # unambiguous demo lookup: TWO Thornbridge orgs exist (Advisory + Retail Group);
    # resolve via the demo director account, never a name prefix.
    demo = cur.execute("""SELECT u.org_id FROM users u WHERE u.email='director@thornbridge.example'""").fetchone()
    if demo and demo[0] in {o for o in orgs}:
        newvals[(demo[0], "single")], newvals[(demo[0], "partner")], newvals[(demo[0], "family")] = 680, 1200, 1600
    before = {t: sorted(float(v) for (v,) in cur.execute(
        "SELECT value FROM answers WHERE question_id=? AND matrix_row_id=? AND value!=''", (QID, t))) for t in MEDIANS}
    print("%s: n=%d orgs" % ("APPLY" if a.write else "dry-run", n))
    for t in ("single", "partner", "family"):
        vals = sorted(newvals[(o, t)] for o in orgs)
        med = statistics.median(vals); q1 = vals[n // 4]; q3 = vals[3 * n // 4]
        print("  %-8s before med £%.0f -> after med £%d (P25 £%d / P75 £%d; band target ±25%%)"
              % (t, statistics.median(before[t]), med, q1, q3))
        # one-rank quantum: pinning the demo org re-ranks one value, shifting a
        # 131-org median by <=1 rank = 1/130 of the multiplier range (~0.77% ~ £8-20).
        assert abs(med - MEDIANS[t]) <= 25, (t, med)
        assert abs(q1 - 0.75 * MEDIANS[t]) <= 20 and abs(q3 - 1.25 * MEDIANS[t]) <= 20, (t, q1, q3)
    # org-coherent ladder: single < partner < family for every org (by construction)
    assert all(newvals[(o, "single")] < newvals[(o, "partner")] < newvals[(o, "family")] for o in orgs)
    # medians re-checked AFTER the demo pin (one org cannot move a 131-org median materially)
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, QID))
    for (o, t), v in newvals.items():
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=?",
                    (str(v), QID, o, t))
    c.commit()
    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    for t in MEDIANS:
        got = sorted(float(v) for (v,) in cur.execute(
            "SELECT value FROM answers WHERE question_id=? AND matrix_row_id=?", (QID, t)))
        assert abs(statistics.median(got) - MEDIANS[t]) <= 25, (t, statistics.median(got))
    with open(os.path.join(ROOT, "r3sw6_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader()
        w.writerow({"metric_id": QID, "action": "group-scheme re-base (split verdict: single B / partner+family EST)",
                    "before": json.dumps({t: statistics.median(before[t]) for t in MEDIANS}),
                    "after": json.dumps(MEDIANS)})
    print(json.dumps({"applied": True, "n": n, "medians": MEDIANS,
                      "non_target_book": "hash-identical", "manifest": "r3sw6_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
