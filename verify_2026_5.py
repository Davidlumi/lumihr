#!/usr/bin/env python3
"""Verify Release 2026.5 post-aggregation. Convergence 336/336 by id; served marginals
vs manifest targets (TOL 0.06, tilted/near-floor rows exempt from the plain-target
deviation check but reported); RIDER 1: zero in-scope orgs holding the GPG scope-out;
RIDER 2: explicit No-SIP share reported; verify-queued CEILING assert; wired coherence
vs live SHAREPLAN; exclusive terminals never co-mingle; near-floor suppression shown."""
import csv
import json
import sqlite3
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "server")
import seed_release_2026_5 as K

TOL = 0.06
fails = []
c = sqlite3.connect("file:lumi.db?mode=ro", uri=True)
c.row_factory = sqlite3.Row
rel, hlp, anc, reg = K.load_rows()

import app as A
A.load_questions.cache_clear()
vis = A.visible_questions()
want = {q for q, r in reg.items() if r["status"].startswith("live")} | set(rel)
sym = set(vis) ^ want
print("convergence: visible %d vs register-live-family+wave %d | sym diff: %s" % (len(vis), len(want), sorted(sym)[:5] or "NONE"))
if sym or len(vis) != 336:
    fails.append("convergence")

man = {r["id"]: r for r in csv.DictReader(open("diff6_seed_manifest.csv"))}
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
fte_db = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id, fte_band FROM orgs")}

worst = (0, None)
for qid, r in rel.items():
    row = c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()
    if not row:
        fails.append("nopayload:" + qid)
        continue
    p = json.loads(row["payload_json"])["all"]
    n = p["n"]
    na_ct = sum(o["count"] for o in (p.get("options") or []) if o.get("is_na"))
    app_n = max(1, n - na_ct)
    if r["type"] == "multi_select" or man[qid]["tilt"] or man[qid]["near_floor"]:
        continue
    served = {o["label"]: o["count"] / app_n for o in (p.get("options") or []) if not o.get("is_na")}
    tgt = json.loads(man[qid]["target_dist"])
    dev = max(abs(served.get(o, 0) - tgt.get(o, 0)) for o in tgt)
    if dev > worst[0]:
        worst = (dev, qid)
    if dev > TOL:
        fails.append("dev:" + qid)
    # ceiling assert (verify-queued): positive-side served share never exceeds the anchor
    ceil = man[qid]["ceiling"]
    if ceil:
        _opts = list(tgt)
        lean = ([o for o in _opts if K.LEAN_RE.match(o)] or [_opts[-1]])[:1]
        pos_served = sum(v for o, v in served.items() if o not in lean)
        if pos_served > float(ceil) + 0.02:
            fails.append("ceiling:" + qid)
print("max plain-target deviation: %.3f (%s)" % worst)

# rider 1: zero in-scope orgs with the scope-out option
bad = 0
for row in c.execute("SELECT org_id, value FROM answers WHERE question_id='REW265_GOV_GPGNAMING' AND snapshot_id=1"):
    if (row["value"] or "").startswith("Not in scope"):
        band = fte_db.get(row["org_id"]) or (prof.get(row["org_id"]) or {}).get("FTE_Band")
        if band and band != "50-249":
            bad += 1
print("rider 1 — in-scope orgs holding scope-out:", bad)
if bad:
    fails.append("rider1")

# rider 2 + wired coherence + exclusive terminals
parent = {r["org_id"]: (r["value"] or "").strip() for r in c.execute(
    "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1", (K.SHAREPLAN_PARENT,))}
for child in sorted(K.WIRED):
    inc = 0
    nosip = pos_n = 0
    for row in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1", (child,)):
        pv = parent.get(row["org_id"], "")
        p_neg = (not pv) or any(pv.startswith(v) for v in K.SHAREPLAN_NEGATIVE)
        v = (row["value"] or "").strip()
        substantive = v and not K.is_na_label(v)
        if p_neg and substantive:
            inc += 1
        if child == "REW265_INC_SIPELEM" and not p_neg:
            if v == "No SIP operated":
                nosip += 1
            elif substantive:
                pos_n += 1
                if "No SIP operated" in v and ";" in v:
                    fails.append("terminal-comingle")
    extra = " | rider 2: No-SIP %d / elements %d among parent-positive" % (nosip, pos_n) if child == "REW265_INC_SIPELEM" else ""
    print("wired %-26s incoherent(parent-neg with substantive): %d%s" % (child, inc, extra))
    if inc:
        fails.append("wired:" + child)

# multi 'None' exclusivity
for qid in ("REW265_TIME_FLEXPATTERN", "REW265_TIME_EXTRADAYS", "REW265_BEN_GREENBEN", "REW265_GOV_VOLGAPS"):
    com = sum(1 for r in c.execute("SELECT value FROM answers WHERE question_id=? AND snapshot_id=1", (qid,))
              if "None" in [x.strip() for x in (r["value"] or "").split(";")] and ";" in (r["value"] or ""))
    if com:
        fails.append("None-comingle:" + qid)
print("exclusive-terminal co-mingles across market multis:", "NONE" if not any(f.startswith("None-") for f in fails) else "FOUND")

# near-floor suppression evidence
for qid in sorted(K.NEAR_FLOOR):
    row = c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()
    p = json.loads(row["payload_json"])["all"]
    pos_counts = [o["count"] for o in (p.get("options") or []) if not K.LEAN_RE.match(o["label"]) and not o.get("is_na")]
    print("near-floor %-28s positive-option counts: %s" % (qid, pos_counts))

print("\nRESULT:", "VERIFIED CLEAN" if not fails else "FAILURES: %s" % fails[:8])
sys.exit(1 if fails else 0)
