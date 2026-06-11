# -*- coding: utf-8 -*-
"""Definitive in-place status audit: every option of EVERY practice/policy
question in the library resolved through practice_status(), plus the live
gap register, named examples, mix and maturity checks. The audit, not a
spot-check, is the proof."""
import json
import os
import re
import sys
import urllib.request
import http.cookiejar
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions
from aggregate import practice_status, is_absence_label

qs = load_questions()
PRACTICE = [q for q in qs.values() if q.category in ("practice", "policy")
            and q.is_scored and q.type in ("single_select", "yes_no")]

print("=" * 96)
print("FULL OPTION AUDIT — %d practice/policy select questions (entire library, all areas)" % len(PRACTICE))
print("=" * 96)
status_counts = Counter()
not_in_place_labels = Counter()
in_place_negativeish = Counter()
partial_labels = Counter()
freq_misses = []
FREQ = re.compile(r"^(annually|twice a year|quarterly|monthly|weekly|biannual|every \d|within last|each)", re.I)

for q in PRACTICE:
    for o in (q.options or []):
        st = practice_status(q, o["label"])
        status_counts[st] += 1
        l = o["label"]
        if st == "not_in_place":
            not_in_place_labels[l] += 1
            if FREQ.match(l.strip()):
                freq_misses.append((q.id, l))
        elif st == "partial":
            partial_labels[l] += 1
        elif st == "in_place" and re.match(r"^(no|not|never)\b", l.strip(), re.I):
            in_place_negativeish[l] += 1

print("\nOption resolutions across the library:")
for k in ("in_place", "partial", "not_in_place", "unknown"):
    print("  %-13s %4d options" % (k, status_counts[k]))

print("\nTHE REVIEWABLE ABSENCE MAPPING — every distinct label resolving to NOT IN PLACE:")
for l, c in sorted(not_in_place_labels.items()):
    print("   %3dx  %s" % (c, l[:90]))

print("\nLabels resolving to PARTIALLY:")
for l, c in sorted(partial_labels.items()):
    print("   %3dx  %s" % (c, l[:90]))

print("\nNegative-looking labels that resolve IN PLACE (property answers — review):")
for l, c in sorted(in_place_negativeish.items()):
    print("   %3dx  %s" % (c, l[:90]))

print("\nFrequency/cadence labels wrongly resolved not-in-place: %s" % (freq_misses or "ZERO"))

# every cadence/frequency question: real frequencies must be in place
print("\nCADENCE FAMILY CHECK — questions with frequency-style options:")
cad_bad = []
for q in PRACTICE:
    labels = [o["label"] for o in (q.options or [])]
    freqs = [l for l in labels if FREQ.match(l.strip())]
    if not freqs:
        continue
    bad = [l for l in freqs if practice_status(q, l) != "in_place"]
    if bad:
        cad_bad.append((q.id, bad))
print("  %d cadence questions checked -> false not-in-place: %s" % (
    sum(1 for q in PRACTICE if any(FREQ.match(o["label"].strip()) for o in (q.options or []))),
    cad_bad or "ZERO"))

# ----------------------------------------------------------- live register --
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(p, body=None):
    r = urllib.request.Request("http://localhost:8060" + p, method="POST" if body is not None else "GET")
    d = json.dumps(body).encode() if body is not None else None
    if d:
        r.add_header("Content-Type", "application/json")
    return json.loads(op.open(r, data=d, timeout=120).read())
api("/api/auth/login", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
reg = api("/api/gap-register")

print("\n" + "=" * 96)
print("LIVE GAP REGISTER (demo org, reward scope)")
print("=" * 96)
mix = Counter(r.get("status") or ("not_answered" if not r["org_answered"] else "?") for r in reg["rows"])
total = sum(mix.values())
print("Mix:", ", ".join("%s %d (%.0f%%)" % (k, v, 100.0 * v / total) for k, v in mix.most_common()))

# zero contradictions: every row's status re-derived independently
bad_rows = []
for r in reg["rows"]:
    q = qs.get(r["question_id"])
    expect = practice_status(q, None if not r["org_answered"] else r["org_status"])
    if (r.get("status") or "unknown") != expect:
        bad_rows.append((r["question_id"], r["org_status"], r.get("status"), expect))
print("Row-level re-derivation mismatches:", bad_rows or "ZERO")

print("\nNAMED EXAMPLES:")
for name, ans_hint in (("Pay review cycle frequency", None), ("Allowances pensionab", None),
                       ("Total rewards strategy (Documented)", None)):
    row = next((r for r in reg["rows"] if name.lower() in r["name"].lower()), None)
    if row:
        print("  %-42s answer=%-28s -> %s" % (row["name"][:42], str(row["org_status"])[:28], row.get("status")))
    else:
        print("  %-42s (not in register rows)" % name)

print("\nMATURITY (presence-based) — register tiles:")
for sec, m in sorted(reg["maturity_sections"].items(), key=lambda kv: kv[1]["order"]):
    print("  %-13s org %5.1f  peer %5.1f  (%d questions)" % (sec, m["org_score"] or 0, m["peer_median_score"] or 0, m["questions_scored"]))

# hand-check one section: Pay
own, peers = [], []
import positions as pos
from db import get_conn
conn = get_conn()
org = dict(conn.execute("SELECT * FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone())
answers = pos.get_org_answers(conn, org["org_id"])
payloads = pos.load_payloads(conn)
from aggregate import STATUS_POINTS
for qid, q in qs.items():
    if q.superpower != "Reward" or q.sub_power != "Pay" or q.category not in ("practice", "policy"):
        continue
    if not (q.is_scored and q.type in ("single_select", "yes_no", "multi_select")):
        continue
    p = payloads.get(qid)
    if p is None or "presence" not in p:
        continue
    st = practice_status(q, answers.get((qid, "")))
    if st in STATUS_POINTS:
        own.append(STATUS_POINTS[st])
    blk = (p["presence"] or {}).get("all")
    if blk and not blk.get("suppressed") and blk.get("status_mean") is not None:
        peers.append(blk["status_mean"])
print("\nHAND-CHECK Pay: org %.1f vs peer %.1f  | app: org %s vs peer %s" % (
    sum(own) / len(own), sum(peers) / len(peers),
    reg["maturity_sections"]["Pay"]["org_score"], reg["maturity_sections"]["Pay"]["peer_median_score"]))
