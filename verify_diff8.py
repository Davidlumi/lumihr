#!/usr/bin/env python3
"""Verify DIFF 8 post-aggregation. Reads LUMI_DB (default lumi.db).
Asserts: 3 targets within TOL on the served marginal; exact-count multis; exclusive
terminals clean; everything outside the 3 metrics byte-identical vs the pre-Diff-8
backup; verification_state stamped 15/15 with `status` (tier authority) untouched.
Headline (280) is asserted by the caller against a provably-fresh server."""
import csv
import json
import os
import sqlite3
import sys
from collections import Counter

DB = os.environ.get("LUMI_DB", "lumi.db")
HERE = os.path.dirname(os.path.abspath(__file__))
BAK = os.path.join(HERE, "lumi.db.bak_pre_diff8_20260715")
TOUCHED = ("REW265_TIME_FLEXPATTERN", "REW265_PAY_COUNTEROFFER", "REW265_GOV_VOLGAPS")
TOL = 0.03
fails = []
c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True) if " " not in DB else sqlite3.connect(DB)
c.row_factory = sqlite3.Row
TGT = {r["metric_id"]: r for r in csv.DictReader(open(os.path.join(HERE, "lumi_diff8_targets.csv")))}

# 1. targets within TOL on the served marginal
print("-- served marginal vs CIPD target --")
for qid, t in TGT.items():
    p = json.loads(c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()["payload_json"])["all"]
    n = p.get("n") or 0
    served = {o["label"]: o["count"] / max(1, n) for o in (p.get("options") or [])}
    worst = 0.0
    for part in t["target_distribution"].split(";"):
        k, v = part.rsplit("=", 1)
        if v.strip().lower() == "derived":
            continue
        dev = abs(served.get(k.strip(), 0) - float(v) / 100.0)
        worst = max(worst, dev)
    print("  %-28s n=%d max dev %.4f %s" % (qid, n, worst, "OK" if worst <= TOL else "FAIL"))
    if worst > TOL:
        fails.append("tgt:" + qid)

# 2. exclusive terminals on the multis
for qid in TOUCHED:
    if c.execute("SELECT type FROM questions WHERE id=?", (qid,)).fetchone()["type"] != "multi_select":
        continue
    com = 0
    for r in c.execute("SELECT value FROM answers WHERE question_id=? AND snapshot_id=1", (qid,)):
        parts = [x.strip() for x in (r["value"] or "").split(";") if x.strip()]
        if "None" in parts and len(parts) > 1:
            com += 1
    print("  %-28s exclusive-terminal violations: %d" % (qid, com))
    if com:
        fails.append("terminal:" + qid)

# 3. everything outside the 3 metrics byte-identical vs backup
if os.path.exists(BAK):
    import hashlib
    def oh(conn):
        h = hashlib.sha256()
        for r in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers "
                              "WHERE question_id NOT IN (?,?,?) ORDER BY org_id, question_id, matrix_row_id", TOUCHED):
            h.update(("|".join(str(x) for x in r) + "\n").encode())
        return h.hexdigest()
    b = sqlite3.connect(BAK)
    same = oh(b) == oh(c)
    print("outside-the-3 hash identical vs pre-Diff-8 backup:", same)
    if not same:
        fails.append("outside-moved")

# 4. verification_state stamped 15/15, status untouched (tier authority intact)
EXPECT = {"anchored-reseed": 3, "verified-direction": 3, "directional": 3, "unverifiable-free": 6}
got = Counter()
tiers = Counter()
for path in ("lumi_2026_4_anchor_register.csv", "lumi_2026_5_anchor_register.csv"):
    rows = list(csv.DictReader(open(os.path.join(HERE, path), encoding="utf-8-sig")))
    if "verification_state" not in rows[0]:
        fails.append("no-verification_state:" + path); continue
    for r in rows:
        if r.get("verification_state"):
            got[r["verification_state"]] += 1
        if path.endswith("2026_5_anchor_register.csv"):
            tiers[r["status"]] += 1
print("verification_state counts:", dict(got), "| expected:", EXPECT)
if dict(got) != EXPECT:
    fails.append("verification_state-mismatch")
print("2026_5 status tiers (must stay 27/27):", dict(tiers))
if sorted(tiers.values()) != [27, 27]:
    fails.append("tier-authority-moved")

print("\nRESULT:", "VERIFIED CLEAN" if not fails else "FAILURES: %s" % fails)
sys.exit(1 if fails else 0)
