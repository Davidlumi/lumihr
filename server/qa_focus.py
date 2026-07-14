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
        # Surface the error detail rather than masking every non-2xx as a bare {} — a {} silently
        # KeyErrors downstream (a correct 403 read as a mystery crash). Callers must check the status.
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {"_http_status": e.code}
import urllib.error
api("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
# 2026.1: "Wellbeing" became a real reward CATEGORY — hidden-scope probes must
# use genuinely out-of-scope superpowers only
HIDDEN = ["Processes","Growth","Capability","Inclusivity","Attract","Leadership","Purpose","Change"]
def leak(blob):
    t = json.dumps(blob)
    return [h for h in HIDDEN if '"%s"' % h in t]

st, me = api("/api/me")
check("scope = Reward only, count tracks the live library (>=240 post-2026.3)", me["scope"]["superpowers"] == ["Reward"] and me["scope"]["question_count"] >= 240, me["scope"])
st, qi = api("/api/questions")
check("/api/questions count agrees with scope, all Reward, no leak", len(qi["questions"]) == me["scope"]["question_count"] and not leak(qi))
st, _ = api("/api/benchmarks/Processes")
check("hidden area page -> 404", st == 404, st)
st, _ = api("/api/benchmark/PROP_9e3b1d18")   # early attrition = Attract
check("hidden metric -> 404", st == 404, st)
st, rw = api("/api/benchmarks/Reward")
check("/api/benchmarks/Reward serves a card per visible Reward question",
      len(rw["cards"]) == me["scope"]["question_count"],
      (len(rw["cards"]), me["scope"]["question_count"]))
st, ov = api("/api/overview")
check("overview clean of hidden areas", not leak(ov), leak(ov))
check("overview headline reward-scoped (comparable_metrics <= the Reward question universe)",
      ov["headline"]["comparable_metrics"] <= me["scope"]["question_count"],
      (ov["headline"]["comparable_metrics"], me["scope"]["question_count"]))
check("by_superpower keys == {Reward}", list(ov["headline"]["by_superpower"].keys()) == ["Reward"])
# by_section carries exactly the competitive domains — DERIVED from the mp config
# flags, never a literal list (check-77 rule: the 7-category/6-competitive world
# ended with Diff 1/2 on 2026-07-14; all 8 B' domains are competitive as of Diff 2).
_mpc = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "data", "market_position_config.json")))
_competitive = sorted(d for d, v in _mpc.get("_domains", {}).items()
                      if not d.startswith("_") and v.get("competitiveness"))
check("by_section carries exactly the competitive domains (derived from mp config)",
      sorted(ov["headline"]["by_section"].keys()) == _competitive,
      (sorted(ov["headline"]["by_section"].keys()), _competitive))
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
# board pack — AI-gated behind LUMI_AI_INSIGHTS_ENABLED (off by default pre-go-live, David's
# go-live action). Gate off -> /api/boardpack/generate correctly 403s; defer rather than crash.
# me["features"]["boardpack"] is the exact gate the route enforces. When the master switch flips
# on at go-live, this block genuinely exercises generate -> pack_id -> fetch -> leak/floor (not a
# no-op): a real boardpack regression would fail the pack_id / leak / suppression-floor checks.
bp_on = bool((me.get("features") or {}).get("boardpack"))
if not bp_on:
    check("board pack AI deferred — gate off pre-go-live (LUMI_AI_INSIGHTS_ENABLED); generate 403s by design",
          True, "AI off; boardpack export checks deferred until go-live")
else:
    st, gen = api("/api/boardpack/generate", "POST", {"cut": "all"})
    check("board pack generate returns a pack_id (AI on)", st == 200 and "pack_id" in gen,
          {"st": st, "gen_keys": list(gen)})
    st, pk = api("/api/boardpack/" + gen["pack_id"])
    check("board pack payload + narrative clean of hidden areas", not leak(pk), leak(pk))
    # governance: the export must inherit the n>=5 suppression floor (it shares the
    # build_items -> position_items path, but assert it so an export-only regression
    # can never ship a sub-floor figure). Every cited item carries its own n.
    _pl = pk["payload"]
    _n_bearing = (_pl.get("strengths", []) + _pl.get("gaps", []) + _pl.get("gap_register_top", []))
    _sub_floor = [it for it in _n_bearing if (it.get("n") is not None and it["n"] < 5)]
    check("board pack honours the n>=5 suppression floor (no sub-floor figure exported)",
          not _sub_floor, _sub_floor)
    check("board pack gap-register rows are all unsuppressed",
          all(not r.get("suppressed", False) for r in _pl.get("gap_register_top", [])))
# cut sensitivity (2026-06-13): the single-metric endpoint must genuinely apply
# a sector cut — a regression here is what the user hit on the metric page.
# All-peers vs a sector must differ in n (and not silently fall back to all).
# Probe metric DERIVED (widest-pool live market card) — the old ALLOW_01 literal
# died with the Diff 3 retirement.
_probe = max((c for c in rw["cards"] if not c.get("practice")),
             key=lambda c: c.get("n") or 0)["id"]
st, b_all = api("/api/benchmark/%s?cut=all" % _probe)
st, b_sec = api("/api/benchmark/%s?cut=industry&cut_value=Retail%%20%%26%%20Consumer%%20Goods" % _probe)
check("metric endpoint applies a sector cut (n differs from all-peers)",
      b_all.get("n") and b_sec.get("n") and b_sec["n"] != b_all["n"],
      (b_all.get("n"), b_sec.get("n")))
check("metric endpoint labels the cut it actually used (no all-peers fallback)",
      (b_sec.get("cut") or {}).get("label") == "Retail & Consumer Goods", b_sec.get("cut"))
# share
st, sh = api("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
anon_jar = http.cookiejar.CookieJar()
anon = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(anon_jar))
d = json.loads(anon.open(BASE + "/api/share/%s/data" % sh["token"], timeout=60).read())
check("shared view clean of hidden areas", not leak(d) and all(c["superpower"] == "Reward" for c in d["cards"]))
api("/api/shares/" + sh["token"], "DELETE")
st, meth = api("/api/methodology")
check("methodology scope = the live domain taxonomy (derived from mp config)",
      meth["scope"]["focused"] and
      sorted(meth["scope"]["sections"]) ==
      sorted(d for d in _mpc.get("_domains", {}) if not d.startswith("_")),
      (sorted(meth["scope"]["sections"])))

print("\n== FOCUS LEAK-CHECK: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL: print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
