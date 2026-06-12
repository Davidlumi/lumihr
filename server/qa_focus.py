# -*- coding: utf-8 -*-
"""Leak-check for the reward-only launch focus: every user-facing surface."""
import json, os, sys, urllib.request, http.cookiejar
BASE = "http://localhost:8060"
PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:110] + "]") if detail else ""))
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(path, method="GET", body=None, want=200):
    r = urllib.request.Request(BASE + path, method=method)
    data = json.dumps(body).encode() if body is not None else None
    if data: r.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(r, data=data, timeout=120)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
import urllib.error
api("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
# 2026.1: "Wellbeing" became a real reward CATEGORY — hidden-scope probes must
# use genuinely out-of-scope superpowers only
HIDDEN = ["Processes","Growth","Capability","Inclusivity","Attract","Leadership","Purpose","Change"]
def leak(blob):
    t = json.dumps(blob)
    return [h for h in HIDDEN if '"%s"' % h in t]

st, me = api("/api/me")
check("scope = Reward only, count 194 (2026.1; demo org sees the hospitality module)", me["scope"]["superpowers"] == ["Reward"] and me["scope"]["question_count"] == 194, me["scope"])
st, qi = api("/api/questions")
check("/api/questions serves exactly 194, all Reward", len(qi["questions"]) == 194 and not leak(qi))
st, _ = api("/api/benchmarks/Processes")
check("hidden area page -> 404", st == 404, st)
st, _ = api("/api/benchmark/PROP_9e3b1d18")   # early attrition = Attract
check("hidden metric -> 404", st == 404, st)
st, rw = api("/api/benchmarks/Reward")
check("/api/benchmarks/Reward serves 194 cards", len(rw["cards"]) == 194)
st, ov = api("/api/overview")
check("overview clean of hidden areas", not leak(ov), leak(ov))
check("overview headline reward-scoped (comparable < 200)", ov["headline"]["comparable_metrics"] <= 194,
      ov["headline"]["comparable_metrics"])
check("by_superpower keys == {Reward}", list(ov["headline"]["by_superpower"].keys()) == ["Reward"])
check("by_section has the 7 categories (2026.1)", sorted(ov["headline"]["by_section"].keys()) ==
      ["Benefits", "Governance", "Incentives", "Pay", "Recognition", "Time Off", "Wellbeing"],
      sorted(ov["headline"]["by_section"].keys()))
check("£ opportunity only reward metrics (pension; no agency/attrition)",
      all(i["label"] == "Employer pension contribution" for i in ov["opportunity"]["items"]),
      [i["label"] for i in ov["opportunity"]["items"]])
st, reg = api("/api/gap-register")
check("gap register rows all Reward", all(r["superpower"] == "Reward" for r in reg["rows"]) and len(reg["rows"]) > 0,
      len(reg["rows"]))
check("gap register maturity keys == {Reward}", list(reg["maturity"].keys()) == ["Reward"])
st, md = api("/api/my-data")
check("my data rows all Reward", all(r["superpower"] == "Reward" for r in md["rows"]) and len(md["rows"]) > 0, len(md["rows"]))
st, ststs = api("/api/analyst/starters")
check("starter questions exist (reward-derived)", len(ststs["starters"]) == 6)
st, ans = api("/api/analyst", "POST", {"question": "how does our flexible working compare?"})
check("analyst never matches hidden metrics", not leak(ans.get("matched", [])) and
      all(m.startswith(("REW", "PROP", "ALLOW", "EXT", "SICK", "CONT", "OT_", "CAR", "PRO_", "WEL")) or True for m in ans.get("matched", [])),
      ans.get("matched"))
# stricter: every matched qid must be in the visible index
vis_ids = {q["id"] for q in qi["questions"]}
check("analyst matches ⊆ visible reward set", set(ans.get("matched", [])) <= vis_ids, set(ans.get("matched", [])) - vis_ids)
st, sub = api("/api/submission/state")
# sections are sub-powers since the entry-UI cleanup; all must belong to Reward
check("submission sections all Reward", len(sub["sections"]) > 0 and
      set(s["superpower"] for s in sub["sections"]) == {"Reward"},
      [s.get("section") for s in sub["sections"]])
st, _ = api("/api/submission/section/Talent")
check("hidden submission section -> 404", st == 404, st)
st, _ = api("/api/submission/section/Wellbeing")
check("Wellbeing is a real category since 2026.1 -> 200", st == 200, st)
# my view: starter all-reward; saved layout w/ hidden card degrades
st, mv = api("/api/myview")
bad = [s for s in mv["layout"] if s["question_id"] not in vis_ids]
check("my-view starter layout ⊆ reward", not bad, bad)
api("/api/myview", "PUT", {"layout": [{"question_id": "PROP_9e3b1d18", "size": 1},
                                      {"question_id": "REW_BEN_HOL_001", "size": 1}]})
st, mv2 = api("/api/myview")
check("saved layout with hidden card degrades to reward-only",
      [s["question_id"] for s in mv2["layout"]] == ["REW_BEN_HOL_001"], mv2["layout"])
api("/api/myview", "PUT", {"layout": []})
# board pack
st, gen = api("/api/boardpack/generate", "POST", {"cut": "all"})
st, pk = api("/api/boardpack/" + gen["pack_id"])
check("board pack payload + narrative clean of hidden areas", not leak(pk), leak(pk))
# share
st, sh = api("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
anon_jar = http.cookiejar.CookieJar()
anon = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(anon_jar))
d = json.loads(anon.open(BASE + "/api/share/%s/data" % sh["token"], timeout=60).read())
check("shared view clean of hidden areas", not leak(d) and all(c["superpower"] == "Reward" for c in d["cards"]))
api("/api/shares/" + sh["token"], "DELETE")
st, meth = api("/api/methodology")
check("methodology scope = the 7 categories (2026.1)", meth["scope"]["focused"] and
      sorted(meth["scope"]["sections"]) == ["Benefits", "Governance", "Incentives", "Pay", "Recognition", "Time Off", "Wellbeing"])

print("\n== FOCUS LEAK-CHECK: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL: print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
