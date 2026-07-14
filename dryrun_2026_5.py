#!/usr/bin/env python3
"""Release 2026.5 DRYRUN — no writes. D-ruling gates + the manifest + rider-3 evidence
(FLEXPATTERN simulated distribution + breadth percentile)."""
import csv
import json
import sqlite3
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "server")
import seed_release_2026_5 as K

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


rel, hlp, anc, reg = K.load_rows()
q54 = {i: r for i, r in reg.items() if r["status"] == "queued-2026_5"}
c = sqlite3.connect("file:lumi.db?mode=ro", uri=True)

print("== gates ==")
check("54 release rows / 54 queued register rows, ids exact (D1)",
      len(rel) == 54 and set(rel) == set(q54), sorted(set(rel) ^ set(q54))[:4])
check("text equality 54/54", all(rel[i]["text"].strip() == q54[i]["question"].strip() for i in rel))
check("member help 54/54 (D3)", set(rel) == set(hlp))
check("anchor register 54/54, two tiers 27/27",
      set(rel) == set(anc) and sorted(
          __import__("collections").Counter(a["status"] for a in anc.values()).values()) == [27, 27])
check("zero live-DB collisions", not [i for i in rel if c.execute("SELECT 1 FROM questions WHERE id=?", (i,)).fetchone()])
import positions as pos
check("no strategy-config rows (14b)", not (set(rel) & pos.STRATEGY_CONFIG_IDS))
cfg = json.load(open("data/market_position_config.json"))
donor = cfg["metrics"]["REW26_WEL_MH_SUPPORT"]
check("D5 donor Level/ordinal/higher", donor["class"] == "Level" and donor["direction"] == "higher_is_better")
check("register classification 46 market / 8 practice",
      sorted(__import__("collections").Counter(q54[i]["classification"] for i in rel).items())
      == [("market", 46), ("practice", 8)])
check("SHAREPLAN parent live", bool(c.execute(
    "SELECT 1 FROM questions WHERE id=? AND status='active'", (K.SHAREPLAN_PARENT,)).fetchone()))
check("SIPELEM na_handling=none by design, terminal option present",
      rel["REW265_INC_SIPELEM"]["na_handling"] == "none"
      and "No SIP operated" in rel["REW265_INC_SIPELEM"]["options"])
na7 = sorted(i for i, r in rel.items() if r["na_handling"] == "offer_na")
check("exactly the ratified 7 offer_na rows", len(na7) == 7, na7)

orgs = [o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1")
        if not c.execute("SELECT 1 FROM orgs WHERE org_id=? AND name='Tester'", (o,)).fetchone()]
check("cohort 220 (D4)", len(orgs) == 220, len(orgs))

# ---- manifest ----
rows_out = []
for qid, r in rel.items():
    a = anc[qid]
    dist = K.build_dist(qid, r, a)
    na_mode = ("wired:" + K.SHAREPLAN_PARENT) if qid in K.WIRED else \
              ("derived:FTE<250" if qid == "REW265_GOV_GPGNAMING" else
               "sector:sales-heavy" if qid == "REW265_INC_COMMCAP" else
               ("self:%.2f" % K.SELF_NA_PRIOR[qid]) if isinstance(K.SELF_NA_PRIOR.get(qid), float) else "none")
    rows_out.append({"id": qid, "tier": a["status"],
                     "anchor": (a.get("real_anchor") or "")[:70],
                     "ceiling": K.anchor_pct(a) if a["status"] == "verify-queued" else "",
                     "na_mode": na_mode,
                     "near_floor": "YES" if qid in K.NEAR_FLOOR else "",
                     "tilt": ",".join(K.TILTS[qid][0][:2]) + "+" if qid in K.TILTS else "",
                     "no_sip_share": K.NO_SIP_SHARE if qid == "REW265_INC_SIPELEM" else "",
                     "type": r["type"], "target_dist": json.dumps(dist)})
with open("diff6_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)
print("manifest: diff6_seed_manifest.csv (54 rows)")

# ---- rider 3 evidence: FLEXPATTERN ----
print("\n== rider-3 evidence: REW265_TIME_FLEXPATTERN simulated ==")
r = rel["REW265_TIME_FLEXPATTERN"]
opts = [o for o in K.split_options(r) if o != "None"]
per = {o: 0.12 + 0.18 * (i == 0) for i, o in enumerate(opts)}
sim = []
for o in orgs:
    rng = K.org_rng("REW265_TIME_FLEXPATTERN", o)
    ch = [x for x, p in per.items() if rng.random() <= p]
    sim.append(";".join(ch) if ch else "None")
from collections import Counter
cnt = Counter(x.strip() for v in sim for x in v.split(";"))
print("  shares (n=220):", {k: round(100 * v / 220) for k, v in cnt.most_common(4)})
counts = sorted(len([x for x in v.split(";") if x.strip() and x.strip() != "None"]) for v in sim)
you = counts[110]
pctl = round(100 * (sum(1 for x in counts if x < you) + sum(1 for x in counts if x == you) / 2) / 220, 1)
print("  breadth percentile (median org): P%s" % pctl)
check("rider-3 path evidence rendered", pctl > 0)

print("\nRESULT:", "ALL GATES GREEN" if not FAILS else "%d FAILURES" % len(FAILS))
sys.exit(1 if FAILS else 0)
