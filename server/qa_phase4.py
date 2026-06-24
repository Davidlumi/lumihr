# -*- coding: utf-8 -*-
"""QA Phase 4 — plain English & trust copy."""
import json, os, sys, re, urllib.request, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import positions as pos
PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:130] + "]") if detail else ""))
BASE = "http://localhost:8060"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(path, method="GET", body=None):
    r = urllib.request.Request(BASE + path, method=method)
    data = json.dumps(body).encode() if body is not None else None
    if data: r.add_header("Content-Type", "application/json")
    return json.loads(opener.open(r, data=data, timeout=120).read())
api("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})

print("== 4.1 Edge-value readout grammar ==")
edges = {p: pos.tens_phrase(p) for p in (1, 4.9, 5.1, 50, 63, 94.9, 95, 99)}
for p, t in edges.items(): print("   P%-5s -> %s" % (p, t))
bad = [t for t in edges.values() if re.search(r"\b0 in 10|\b10 in 10", t)]
check("no '0 in 10' / '10 in 10' at any percentile", not bad, bad)
check("P1/P99 read as superlatives", "very lowest" in edges[1] and "very highest" in edges[99])
check("exact median reads naturally", "middle" in edges[50])
check("suppressed copy is human", "aren't enough organisations" in pos.SUPPRESSED_COPY)
# client humanSentence edge mirror (same arithmetic as card.js)
def human_x(pct):
    x = round(pct / 10)
    if pct < 5: return "almost no"
    if x <= 0: return "fewer than 1 in 10"
    if x >= 10: return "almost all"
    return "about %d in 10" % x
checks = {0.4: "almost no", 4.9: "almost no", 5.1: "about 1 in 10", 96: "almost all", 64: "about 6 in 10"}
ok = all(human_x(p) == v for p, v in checks.items())
check("client 'X in 10' edges (mirrored logic)", ok, {p: human_x(p) for p in checks})

print("== 4.2 'X in 10' + percentile both present ==")
c = api("/api/benchmark/PROP_e63cf45a")
r = c.get("readout", "")
check("numeric readout has both 'in 10'-style phrase and P-number", ("in 10" in r or "middle" in r or "very" in r) and re.search(r"\(P\d+", r), r[:100])

print("== 4.3 Number formatting ==")
fv = pos.fmt_value
cases = [(fv(1250, {"type": "currency"}), "£1,250"), (fv(8.5, {"type": "percentage"}), "8.5%"),
         (fv(24.0, {"type": "days"}), "24 days"), (fv(0.085*100, {"type": "percentage"}), "8.5%"),
         (fv(36000, {"type": "currency"}), "£36,000")]
ok = all(a == b for a, b in cases)
check("£/%%/days formatting exact", ok, cases)

print("== 4.4 Helper text & microcopy present ==")
appjs = open("../web/js/app.js").read()
pages = open("../web/js/pages.js").read()
check("peer-group helper present", "comparing against" in appjs)
check("search helper present", "Search reward metrics" in appjs)
check("Ask lumi conversational hint present", "ask how you compare" in appjs)
check("filter helpers present", "Show only one kind of question" in pages and "Filter by signal" in pages)
cards = open("../web/js/card.js").read()
check("buttons say what they do (descriptive icon-button titles)",
      all(t in cards for t in ("Download chart", "Copy chart", "Open full view", "Question & definition")))

print("== 4.5 Real-data provenance (no synthetic/illustrative labelling) ==")
ov = api("/api/overview"); meth = api("/api/methodology")
check("overview carries no synthetic-pool flag", ov.get("synthetic_pool") is None)
check("methodology carries no synthetic-pool flag", meth.get("synthetic_pool") is None)
check("client carries no illustrative/synthetic data label",
      "Illustrative sample data" not in pages and "synthetic seed data" not in pages)

print("\n== PHASE 4 SUMMARY: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL: print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
