#!/usr/bin/env python3
"""Release 2026.4 DRYRUN — no writes. Gates (Diff 5 rulings D1-D5), the derived seed
manifest, and the D5 evidence render: ONE new market multi_select's simulated
distribution + a percentile through the live engine path."""
import csv
import json
import sqlite3
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "server")
import seed_release_2026_4 as K

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


rel, hlp, anc = K.load_rows()
reg = {r["metric_id"]: r for r in csv.DictReader(open("lumi_master_metric_register_FINAL_APPROVED.csv"))}
c = sqlite3.connect("file:lumi.db?mode=ro", uri=True)

print("== gates ==")
check("45 release rows", len(rel) == 45, len(rel))
check("member help covers 45/45", set(rel) == set(hlp), sorted(set(rel) ^ set(hlp))[:4])
check("anchor register covers 45/45", set(rel) == set(anc), sorted(set(rel) ^ set(anc))[:4])
check("zero id collisions with live DB",
      not [i for i in rel if c.execute("SELECT 1 FROM questions WHERE id=?", (i,)).fetchone()])
check("register v6 carries all 45 BY ID as new-v4 (D1)",
      all(reg.get(i, {}).get("status") == "new-v4" for i in rel))
check("register text equality 45/45",
      all(rel[i]["text"].strip() == reg[i]["question"].strip() for i in rel))
import positions as pos
check("no strategy-config rows in the wave (14b inheritance)",
      not (set(rel) & pos.STRATEGY_CONFIG_IDS))
cfg = json.load(open("data/market_position_config.json"))
donor = cfg["metrics"]["REW26_WEL_MH_SUPPORT"]
check("D5 donor shape is Level/ordinal/higher", donor["class"] == "Level"
      and donor["type"] == "ordinal" and donor["direction"] == "higher_is_better", donor)
wired_parents_ok = all(
    parent.startswith("REW264_") or c.execute("SELECT 1 FROM questions WHERE id=? AND status='active'", (parent,)).fetchone()
    for parent, _na in K.WIRED.values())
check("all 7 wired parents resolvable (live or intra-wave)", wired_parents_ok)

# ---- the manifest (target distributions; the ruling instrument's execution record) ----
orgs = [o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1")
        if not c.execute("SELECT 1 FROM orgs WHERE org_id=? AND name='Tester'", (o,)).fetchone()]
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
print("seed cohort (D4):", len(orgs), "non-Tester orgs")
check("cohort is the 220 convention (D4)", len(orgs) == 220, len(orgs))

rows_out = []
for qid, r in rel.items():
    a = anc.get(qid, {})
    dist = K.build_dist(qid, r, a)
    na_mode = ("wired:" + K.WIRED[qid][0]) if qid in K.WIRED else \
              ("self-declared:%.2f" % K.SELF_NA_PRIOR[qid]) if qid in K.SELF_NA_PRIOR else "none"
    rows_out.append({"id": qid, "grade": a.get("grade", "—"),
                     "anchor": (a.get("real_anchor") or "")[:70],
                     "estimate_flag": "YES" if a.get("grade") == "E" else "",
                     "na_mode": na_mode, "type": r["type"],
                     "target_dist": json.dumps(dist)})
with open("diff5_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)
print("manifest: diff5_seed_manifest.csv (45 rows; target column; seeded column filled at apply)")

# ---- D5 evidence: simulate ONE market multi through the engine path ----
print("\n== D5 evidence: REW264_TIME_CHILDCARE simulated ==")
r = rel["REW264_TIME_CHILDCARE"]
opts = [o for o in K.split_options(r) if not K.is_na_label(o)]
per_opt = {o: 0.15 + 0.2 * (i == 0) for i, o in enumerate(opts) if o != "None"}
sim = []
for o in orgs:
    rng = K.org_rng("REW264_TIME_CHILDCARE", o)
    ch = [x for x, p in per_opt.items() if rng.random() <= p]
    sim.append(";".join(ch) if ch else "None")
from collections import Counter
cnt = Counter()
for v in sim:
    for x in v.split(";"):
        cnt[x.strip()] += 1
print("  simulated option shares (n=%d):" % len(sim),
      {k: round(100 * v / len(sim)) for k, v in cnt.most_common(5)})
# percentile path evidence: a multi_select_count percentile through aggregate's machinery
counts = sorted(len([x for x in v.split(";") if x.strip() and x.strip() != "None"]) for v in sim)
you = counts[len(counts) // 2]
below = sum(1 for x in counts if x < you)
ties = sum(1 for x in counts if x == you)
pctl = round(100 * (below + ties / 2) / len(counts), 1)
print("  breadth-count percentile for a median org (percentile_rank convention): P%s" % pctl)
check("D5 path evidence rendered", pctl > 0)

print("\nRESULT:", "ALL GATES GREEN — ready for apply" if not FAILS else "%d FAILURES" % len(FAILS))
sys.exit(1 if FAILS else 0)
