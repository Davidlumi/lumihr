#!/usr/bin/env python3
"""DIFF 8 — anchor-verified reseed (3 rows). Corrects FLEXPATTERN / COUNTEROFFER /
VOLGAPS to verified CIPD primary-source figures. Diff-7 pipeline inherited verbatim:
DELETE + re-INSERT + answers_history snapshot, deterministic per-org RNG, is_na-aware
base exclusion (NICSHARING primitive), exact-count multi assignment (NOT Bernoulli —
the small-base TOL lesson). Everything OUTSIDE the 3 metrics is hash-asserted
byte-identical. Double-guarded --write --confirmed-by-david.

Also stamps `verification_state` on both anchor registers (new column; `status` — the
tier authority build_dist() branches on — is NEVER touched).
Run: python3 diff8_reseed.py                          (DRYRUN)
     python3 diff8_reseed.py --write --confirmed-by-david
"""
import csv
import hashlib
import json
import os
import random
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, ".")
import reseed_engine as RE

SEED_DATE = "2026-07-15"
STAMP = "2026-07-15 06:40:00"
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
DB = os.environ.get("LUMI_DB", "lumi.db")
TARGETS = "lumi_diff8_targets.csv"
TOUCHED = ("REW265_TIME_FLEXPATTERN", "REW265_PAY_COUNTEROFFER", "REW265_GOV_VOLGAPS")

# lean -> generous, for latent pairing on the single-select
COUNTEROFFER_ORD = ["No policy", "Never counter", "Case-by-case with approval", "Routinely counter"]

# 3-state verification outcome (15 rows) -> new verification_state column
VERIFICATION_STATE = {
    "REW265_TIME_FLEXPATTERN": "anchored-reseed", "REW265_PAY_COUNTEROFFER": "anchored-reseed",
    "REW265_GOV_VOLGAPS": "anchored-reseed",
    "REW265_INC_SAYEDISC": "verified-direction", "REW265_INC_SIPELEM": "verified-direction",
    "REW265_INC_EOT": "verified-direction",
    "REW265_PAY_PAYCOMMS": "directional", "REW265_BEN_EVCHARGE": "directional",
    "REW265_INC_ESGINCENT": "directional",
    "REW265_INC_SHAREPART": "unverifiable-free", "REW265_PAY_PROMOPAY": "unverifiable-free",
    "REW265_PAY_GEOPAY": "unverifiable-free", "REW265_PAY_RANGEMAX": "unverifiable-free",
    "REW265_PAY_ACTINGUP": "unverifiable-free", "REW264_HLT_CASHPLAN": "unverifiable-free",
}


def org_rng(salt, org_id):
    return random.Random(hashlib.sha256(f"{salt}|{SEED_DATE}|{org_id}".encode()).hexdigest())


def largest_remainder(dist, m):
    raw = {o: dist[o] * m for o in dist}
    base = {o: int(raw[o]) for o in dist}
    for o in sorted(dist, key=lambda o: -(raw[o] - base[o]))[: m - sum(base.values())]:
        base[o] += 1
    return base


c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
orgs = {r["org_id"]: dict(r) for r in cur.execute("SELECT * FROM orgs")}
tester = next((o for o, r in orgs.items() if r["name"] == "Tester"), None)
resp = [o for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1") if o != tester]
assert len(resp) == 220, len(resp)
A = {}
for r in cur.execute("SELECT question_id, org_id, value FROM answers WHERE snapshot_id=1 AND (matrix_row_id IS NULL OR matrix_row_id='')"):
    A[(r["question_id"], r["org_id"])] = r["value"]
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
lat = {o: RE.latent(o, prof) for o in resp}
TGT = {r["metric_id"]: r for r in csv.DictReader(open(TARGETS))}
assert len(TGT) == 3 and set(TGT) == set(TOUCHED), sorted(TGT)


def opts_json(qid):
    return json.loads(cur.execute("SELECT options_json FROM questions WHERE id=?", (qid,)).fetchone()["options_json"])


def na_labels(qid):
    """is_na-aware (the NICSHARING primitive): read the options_json flag, not a label pattern."""
    return {o["label"] for o in opts_json(qid) if o.get("is_na")}


def parse_targets(qid):
    """{label: rate} for the named options; 'derived' terminals excluded."""
    out, derived = {}, []
    for part in TGT[qid]["target_distribution"].split(";"):
        k, v = part.rsplit("=", 1)
        if v.strip().lower() == "derived":
            derived.append(k.strip())
        else:
            out[k.strip()] = float(v) / 100.0
    return out, derived


changes = {}
def set_change(qid, org, val):
    if A.get((qid, org)) != val:
        changes[(qid, org)] = val


ach_rows = []
for qid in TOUCHED:
    qtype = cur.execute("SELECT type FROM questions WHERE id=?", (qid,)).fetchone()["type"]
    inc, derived = parse_targets(qid)
    db_order = [o["label"] for o in opts_json(qid)]
    nas = na_labels(qid)
    base = [o for o in resp if A.get((qid, o)) not in nas]      # is_na-aware base exclusion
    assert not nas, "%s unexpectedly carries is_na options — headline-neutrality claim needs re-check" % qid

    if qtype == "multi_select":
        # EXACT-COUNT per-option incidence: each option assigned to exactly round(rate*n)
        # orgs chosen by its own deterministic RNG. Terminal ('None') is DERIVED — assigned
        # only where an org drew zero substantive picks, so it can never co-occur.
        pick = {o: [] for o in base}
        plan = {}
        for opt in [l for l in db_order if l in inc]:
            k = round(inc[opt] * len(base))
            plan[opt] = k
            for o in sorted(base, key=lambda o: org_rng(qid + "|" + opt, o).random())[:k]:
                pick[o].append(opt)
        term = derived[0] if derived else "None"
        for o in base:
            picks = [l for l in db_order if l in pick[o]]        # canonical DB option order
            set_change(qid, o, ";".join(picks) if picks else term)
        got = Counter()
        for o in base:
            for x in (changes.get((qid, o), A.get((qid, o))) or "").split(";"):
                if x.strip():
                    got[x.strip()] += 1
        for opt in db_order:
            ach_rows.append({"metric_id": qid, "type": qtype, "option": opt,
                             "target_pct": round(100 * inc[opt], 1) if opt in inc else "derived",
                             "planned_n": plan.get(opt, ""), "achieved_n": got.get(opt, 0),
                             "achieved_pct": round(100 * got.get(opt, 0) / len(base), 1)})
    else:
        counts = largest_remainder(inc, len(base))
        rank = {o: i for i, o in enumerate(COUNTEROFFER_ORD)}
        seq = [op for op in sorted(counts, key=lambda o: rank.get(o, 999)) for _ in range(counts[op])]
        ordered = sorted(base, key=lambda o: (lat.get(o, 0.5), org_rng(qid, o).random()))
        for o, v in zip(ordered, seq):
            set_change(qid, o, v)
        got = Counter(changes.get((qid, o), A.get((qid, o))) for o in base)
        for opt in db_order:
            ach_rows.append({"metric_id": qid, "type": qtype, "option": opt,
                             "target_pct": round(100 * inc[opt], 1) if opt in inc else "derived",
                             "planned_n": counts.get(opt, ""), "achieved_n": got.get(opt, 0),
                             "achieved_pct": round(100 * got.get(opt, 0) / len(base), 1)})

# ---- report ----
per_metric = Counter(k[0] for k in changes)
print("DIFF 8 %s — %d cell changes across %d metrics" % ("WRITE" if WRITE else "DRYRUN", len(changes), len(per_metric)))
for q in TOUCHED:
    print("  %-28s writes %d" % (q, per_metric.get(q, 0)))
worst = 0.0
for r in ach_rows:
    if r["target_pct"] != "derived":
        worst = max(worst, abs(r["achieved_pct"] - r["target_pct"]) / 100.0)
print("max per-option deviation vs target: %.4f" % worst)
for q in TOUCHED:
    if cur.execute("SELECT type FROM questions WHERE id=?", (q,)).fetchone()["type"] != "multi_select":
        continue
    com = sum(1 for o in resp if "None" in (changes.get((q, o), A.get((q, o))) or "").split(";")
              and len([x for x in (changes.get((q, o), A.get((q, o))) or "").split(";") if x.strip()]) > 1)
    print("  %s exclusive-terminal violations: %d" % (q, com))
    assert com == 0, "terminal co-mingle on %s" % q

with open("diff8_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["metric_id", "type", "option", "target_pct", "planned_n", "achieved_n", "achieved_pct"])
    w.writeheader(); w.writerows(ach_rows)
print("manifest: diff8_seed_manifest.csv (%d option rows)" % len(ach_rows))

if not WRITE:
    print("\nDRY — no writes. Inspect diff8_seed_manifest.csv, then --write --confirmed-by-david.")
    sys.exit(0)

# ===================== APPLY =====================
def outside_hash(cur):
    """Everything OUTSIDE the 3 touched metrics — the old book AND the other 96 wave rows."""
    h = hashlib.sha256()
    for r in cur.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers "
                         "WHERE question_id NOT IN (?,?,?) ORDER BY org_id, question_id, matrix_row_id", TOUCHED):
        h.update(("|".join(str(x) for x in r) + "\n").encode())
    return h.hexdigest()

h0 = outside_hash(cur)
n = 0
for (qid, org), newv in changes.items():
    old = cur.execute("SELECT value, submitted_at FROM answers WHERE org_id=? AND snapshot_id=1 AND question_id=? AND (matrix_row_id IS NULL OR matrix_row_id='')", (org, qid)).fetchone()
    if old is not None:
        cur.execute("INSERT INTO answers_history (org_id, snapshot_id, question_id, matrix_row_id, value, recorded_at) VALUES (?,1,?,'',?,?)",
                    (org, qid, old["value"], old["submitted_at"] or STAMP))
    cur.execute("DELETE FROM answers WHERE org_id=? AND snapshot_id=1 AND question_id=? AND (matrix_row_id IS NULL OR matrix_row_id='')", (org, qid))
    cur.execute("INSERT INTO answers (org_id, snapshot_id, question_id, matrix_row_id, value, submitted_at) VALUES (?,1,?,'',?,?)", (org, qid, newv, STAMP))
    cur.execute("INSERT INTO answers_history (org_id, snapshot_id, question_id, matrix_row_id, value, recorded_at) VALUES (?,1,?,'',?,?)", (org, qid, newv, STAMP))
    n += 1
c.commit()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
assert outside_hash(cur) == h0, "SOMETHING OUTSIDE THE 3 METRICS MOVED — restore lumi.db.bak_pre_diff8_20260715"
print("APPLIED %d cell changes. Everything outside the 3 metrics hash-IDENTICAL." % n)

# ---- verification_state annotation (new column; `status` NEVER touched) ----
for path in ("lumi_2026_4_anchor_register.csv", "lumi_2026_5_anchor_register.csv"):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    before_status = {r["id_hint"]: r["status"] for r in rows}
    cols = list(rows[0].keys())
    if "verification_state" not in cols:
        cols.append("verification_state")
    hit = 0
    for r in rows:
        r["verification_state"] = VERIFICATION_STATE.get(r["id_hint"], "")
        if r["verification_state"]:
            hit += 1
    assert {r["id_hint"]: r["status"] for r in rows} == before_status, "status column moved — tier authority must be untouched"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)
    print("%s: verification_state stamped on %d rows; status untouched" % (path, hit))
stamped = sum(1 for v in VERIFICATION_STATE.values())
print("verification_state total stamped: %d/15" % stamped)
