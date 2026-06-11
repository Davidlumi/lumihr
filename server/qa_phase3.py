# -*- coding: utf-8 -*-
"""QA Phase 3 — render completeness: all 778 questions accounted for, no
silent drops, no contradictory labels, matrices complete and ordered."""
import json, os, sys, re, urllib.request, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions
from aggregate import score_answer, score_direction
BASE = "http://localhost:8060"
PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:120] + "]") if detail else ""))
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(path, method="GET", body=None):
    r = urllib.request.Request(BASE + path, method=method)
    data = json.dumps(body).encode() if body is not None else None
    if data: r.add_header("Content-Type", "application/json")
    return json.loads(opener.open(r, data=data, timeout=120).read())
api("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
qs = load_questions()

print("== 3.1 Walk all 778 questions ==")
SUPER = ["Reward","Processes","Wellbeing","Growth","Capability","Inclusivity","Attract","Leadership","Purpose","Change"]
tally = {"rendered": 0, "suppressed": 0, "locked": 0, "errored": []}
seen = set()
bad_json = []
for sp in SUPER:
    b = api("/api/benchmarks/" + urllib.request.quote(sp))
    for c in b["cards"]:
        seen.add(c["id"])
        txt = json.dumps(c)
        if "undefined" in txt or ": NaN" in txt:
            bad_json.append((c["id"], "undefined/NaN"))
        if c.get("locked"): tally["locked"] += 1
        elif c.get("suppressed"): tally["suppressed"] += 1
        elif c.get("block") or c.get("matrix_rows"): tally["rendered"] += 1
        else: tally["errored"].append(c["id"])
check("all 778 question ids served", len(seen) == 778, len(seen))
check("zero errored cards", not tally["errored"], tally["errored"][:5])
check("zero 'undefined'/NaN in card payloads", not bad_json, bad_json[:3])
print("   TALLY: rendered=%d suppressed=%d locked=%d errored=%d (full-tier org: locked expected 0)"
      % (tally["rendered"], tally["suppressed"], tally["locked"], len(tally["errored"])))

print("== 3.2 Status/answer contradiction sweep (whole gap register) ==")
reg = api("/api/gap-register")
contradictions = []
for r in reg["rows"]:
    if r["suppressed"] or not r["org_answered"] or r["in_place"] is None: continue
    q = qs.get(r["question_id"])
    s = score_answer(q, r["org_status"])
    expect = (s is not None and s >= 50)
    if expect != r["in_place"]:
        contradictions.append((r["question_id"], r["org_status"], r["in_place"]))
check("zero status/answer contradictions across %d register rows" % len(reg["rows"]),
      not contradictions, contradictions[:3])

print("== 3.3 One of every type/chart renders complete ==")
samples = {}
for sp in SUPER:
    b = api("/api/benchmarks/" + urllib.request.quote(sp))
    for c in b["cards"]:
        if c.get("locked") or c.get("suppressed"): continue
        samples.setdefault(c["type"], c)
for typ, c in sorted(samples.items()):
    has_n = c.get("n", 0) > 0
    has_cut = bool(c["cut"]["label"])
    body_ok = bool(c.get("block") or c.get("matrix_rows"))
    check("type %-13s renders with n + peer-cut label" % typ, has_n and has_cut and body_ok,
          "n=%s cut=%s" % (c.get("n"), c["cut"]["label"]))

print("== 3.4 Matrix rows complete and in library order ==")
bad_rows = []
for qid, q in qs.items():
    if q.type != "matrix": continue
    c = api("/api/benchmark/" + qid)
    if c.get("locked"): continue
    lib_rows = [rid for rid, _l in q.matrix_row_defs()]
    api_rows = [r["row_id"] for r in c.get("matrix_rows", [])]
    if lib_rows and api_rows != lib_rows:
        bad_rows.append((qid, len(api_rows), len(lib_rows)))
check("all 31 matrices show every library row in order", not bad_rows, bad_rows[:4])

print("\n== PHASE 3 SUMMARY: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL: print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
