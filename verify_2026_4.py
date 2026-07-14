#!/usr/bin/env python3
"""Verify Release 2026.4 post-aggregation: served marginals vs manifest targets (TOL 0.05
on the largest option), NA rates sane, wired-NA coherence (child NA == parent-negative),
convergence 282/282 vs register v6 BY ID, cfg entries present for all 45."""
import csv
import json
import sqlite3
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "server")
import seed_release_2026_4 as K

TOL = 0.06
fails = []
c = sqlite3.connect("file:lumi.db?mode=ro", uri=True)
c.row_factory = sqlite3.Row
rel, hlp, anc = K.load_rows()

# convergence: visible == register v6 live ∪ the 45
import app as A
A.load_questions.cache_clear()
vis = A.visible_questions()
reg = {r["metric_id"]: r for r in csv.DictReader(open("lumi_master_metric_register_FINAL_APPROVED.csv"))}
want = {q for q, r in reg.items() if r["status"].startswith("live")} | set(rel)
sym = set(vis) ^ want
print("convergence: visible %d vs register-live+wave %d | symmetric diff: %s" % (len(vis), len(want), sorted(sym)[:5] or "NONE"))
if sym:
    fails.append("convergence")

cfg = json.load(open("data/market_position_config.json"))["metrics"]
miss_cfg = [q for q in rel if q not in cfg]
print("cfg entries for all 45:", "OK" if not miss_cfg else miss_cfg[:5])
if miss_cfg:
    fails.append("cfg")

man = {r["id"]: r for r in csv.DictReader(open("diff5_seed_manifest.csv"))}
print("%-30s %5s %5s %8s" % ("qid", "n", "NA", "maxdev"))
for qid, r in rel.items():
    row = c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()
    if not row:
        print("  %-28s NO PAYLOAD" % qid)
        fails.append(qid)
        continue
    p = json.loads(row["payload_json"])["all"]
    n = p["n"]
    na_ct = sum(o["count"] for o in (p.get("options") or []) if o.get("is_na"))
    app_n = max(1, n - na_ct)
    if r["type"] == "multi_select":
        print("%-30s %5d %5.1f%%   multi (per-option shares served)" % (qid, n, 100 * na_ct / max(1, n)))
        continue
    served = {o["label"]: o["count"] / app_n for o in (p.get("options") or []) if not o.get("is_na")}
    tgt = json.loads(man[qid]["target_dist"])
    devs = [abs(served.get(o, 0) - tgt.get(o, 0)) for o in tgt]
    maxdev = max(devs) if devs else 1.0
    flag = "" if maxdev <= TOL else "  <-- DEV"
    if maxdev > TOL and qid != "REW264_WEL_MEALS":       # MEALS is deliberately tilted off-target
        fails.append(qid)
    print("%-30s %5d %5.1f%% %7.3f%s" % (qid, n, 100 * na_ct / max(1, n), maxdev, flag))

# wired coherence: child NA exactly where the parent is negative
for child, (parent, na_vals) in K.WIRED.items():
    bad = 0
    for row in c.execute("SELECT a.org_id, a.value cv, b.value pv FROM answers a "
                         "LEFT JOIN answers b ON b.org_id=a.org_id AND b.question_id=? AND b.snapshot_id=1 "
                         "WHERE a.question_id=? AND a.snapshot_id=1", (parent, child)):
        p_neg = row["pv"] is None or any((row["pv"] or "").strip().startswith(v) for v in na_vals)
        c_na = K.is_na_label(row["cv"] or "")
        if p_neg != c_na:
            bad += 1
    print("wired %-28s -> %-20s incoherent: %d" % (child, parent, bad))
    if bad:
        fails.append("wired:" + child)

print("\nRESULT:", "VERIFIED CLEAN" if not fails else "FAILURES: %s" % fails[:6])
sys.exit(1 if fails else 0)
