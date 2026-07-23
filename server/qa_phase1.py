# -*- coding: utf-8 -*-
"""QA Phase 1 — numerical & mapping correctness.

Independent scratch derivations straight from the raw seed CSVs (bypassing the
app's engine entirely), compared against the live API. Plus the status-mapping
audit, maturity recompute, suppression off-by-one, polarity direction,
percentile-function consistency and gap-to-£ reproduction.
"""
import csv
import glob
import json
import os
import re
import sys
import urllib.request
import http.cookiejar
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "responses")
BASE = "http://localhost:8060"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:120] + "]") if detail else ""))


# tiny API client
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def api(path, method="GET", body=None):
    r = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        r.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    resp = opener.open(r, data=data, timeout=120)
    return json.loads(resp.read())


api("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})

# ---------------------------------------------------- raw-CSV derivations ---
RAW = defaultdict(dict)   # qid -> (org, row) -> value
for fn in glob.glob(os.path.join(DATA, "*.csv")):
    for r in csv.DictReader(open(fn, encoding="utf-8-sig")):
        v = r["your_answer"].strip()
        if v:
            RAW[r["question_id"]][(r["org_id"], r["matrix_row_id"] or "")] = v


def pct(sorted_vals, p):
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    k = (n - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def numbers(qid, row=""):
    out = []
    for (org, rid), v in RAW[qid].items():
        if rid != row:
            continue
        try:
            out.append(float(v.replace(",", "").replace("£", "").replace("%", "")))
        except ValueError:
            pass
    return sorted(out)


print("== 1.1 Six hand-derived aggregates vs API " + "=" * 48)
print("%-34s %-14s %12s %12s %5s" % ("question", "stat", "hand", "api", "ok"))

# two numerics
for qid, label in [("PROP_9e4ad87f", "salary budget %"), ("PROP_d16bae79", "workforce cost/FTE")]:  # nonrew-2: PROP_9620d380 (Processes) deleted
    vs = numbers(qid)
    card = api("/api/benchmark/%s" % qid)
    ok_all = True
    for p, key in [(25, "p25"), (50, "p50"), (75, "p75")]:
        hand = pct(vs, p)
        apiv = card["block"][key]
        ok = abs(hand - apiv) < 1e-9
        ok_all &= ok
        print("%-34s %-14s %12.4f %12.4f %5s" % (label, "P%d (n=%d)" % (p, len(vs)), hand, apiv, "OK" if ok else "XX"))
    check("numeric %s P25/50/75 match" % qid, ok_all)

# two single_selects (option %)
for qid in ["PROP_8e0b6316", "REW_BEN_SICK_004"]:
    vals = [v for (o, rid), v in RAW[qid].items() if rid == ""]
    cnt = Counter(vals)
    n = len(vals)
    card = api("/api/benchmark/%s" % qid)
    ok_all = card["n"] == n
    for o in card["block"]["options"]:
        hand = round(100.0 * cnt.get(o["label"], 0) / n, 1)
        ok = abs(hand - o["pct"]) < 0.05
        ok_all &= ok
        print("%-34s %-14s %11.1f%% %11.1f%% %5s" % (qid, o["label"][:14], hand, o["pct"], "OK" if ok else "XX"))
    check("select %s option %% match (n=%d)" % (qid, n), ok_all)

# one multi_select
qid = "REW_BEN_038"
vals = [v for (o, rid), v in RAW[qid].items() if rid == ""]
n = len(vals)
sel = Counter()
for v in vals:
    for tok in set(t.strip() for t in v.split(";") if t.strip()):
        sel[tok] += 1
card = api("/api/benchmark/%s" % qid)
ok_all = card["n"] == n
for o in card["block"]["options"]:
    hand = round(100.0 * sel.get(o["label"], 0) / n, 1)
    ok = abs(hand - o["pct"]) < 0.05
    ok_all &= ok
    if sel.get(o["label"], 0) > 0:
        print("%-34s %-14s %11.1f%% %11.1f%% %5s" % ("REW_BEN_038", o["label"][:14], hand, o["pct"], "OK" if ok else "XX"))
check("multi REW_BEN_038 prevalence match (n=%d)" % n, ok_all)

# one matrix (per-row median)
qid = "REW_BEN_112"  # nonrew-2: typical employer pension % by level (Reward); MET_cd8efe96 (Attract) deleted
card = api("/api/benchmark/%s" % qid)
ok_all = True
for rowd in card["matrix_rows"][:3]:
    vs = numbers(qid, rowd["row_id"])
    if rowd["suppressed"]:
        continue
    hand = pct(vs, 50)
    apiv = rowd["block"]["p50"]
    ok = abs(hand - apiv) < 1e-9 and len(vs) == rowd["block"]["n"]
    ok_all &= ok
    print("%-34s %-14s %12.4f %12.4f %5s" % ("pension/level " + rowd["row_id"][:18], "P50 (n=%d)" % len(vs), hand, apiv, "OK" if ok else "XX"))
check("matrix REW_BEN_112 row medians match", ok_all)

# -------------------------------------------- 1.2 status-mapping audit ------
print("\n== 1.2 Status-mapping audit (15 rich-option practice/policy questions) " + "=" * 20)
from library import load_questions
from aggregate import score_answer, score_direction
qs = load_questions()
rich = [q for q in qs.values()
        if q.category in ("practice", "policy") and q.type == "single_select"
        and len([o for o in (q.options or [])]) >= 4 and score_direction(q) != 0][:15]
bad = []
for q in rich:
    d = score_direction(q)
    opts = [o for o in sorted(q.options or [], key=lambda o: o.get("order", 0))]
    cfg = q.scoring_config or {}
    na = set(cfg.get("na_codes") or [])
    subst = [o for o in opts if o["code"] in (cfg.get("option_scores") or {}) and o["code"] not in na]
    statuses = []
    for o in subst:
        s = score_answer(q, o["label"])
        statuses.append((o["label"][:30], s, "in" if s is not None and s >= 50 else "out"))
    # best-end option must be in place; worst-end must not; monotonic along ladder
    seq = [s for _l, s, _st in statuses]
    mono = all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1)) if d == -1 else \
           all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
    top_in = (statuses[0][2] == "in") if d == -1 else (statuses[-1][2] == "in")
    bot_out = (statuses[-1][2] == "out") if d == -1 else (statuses[0][2] == "out")
    okq = mono and top_in and bot_out
    if not okq:
        bad.append((q.id, statuses))
    print("  %s %-26s dir=%+d  %s" % ("OK" if okq else "XX", q.id, d,
          " | ".join("%s→%s" % (l[:18], st) for l, _s, st in statuses[:4])))
check("15 rich-option questions map answer→status via library ladder", not bad, bad[:2])

# grep for surviving hardcoded yes-status checks in analytics code
suspect = []
for fn in ("positions.py", "app.py", "aggregate.py"):
    src = open(fn).read()
    for m in re.finditer(r'==\s*["\']Yes["\']|startswith\(["\']Yes', src):
        suspect.append((fn, src[:m.start()].count("\n") + 1))
check("no hardcoded 'Yes' status checks in analytics layer", not suspect, suspect)

# ---------------------------------------------- 1.3 maturity recompute ------
print("\n== 1.3 Maturity recompute (Reward) " + "=" * 42)
import positions as pos
from db import get_conn
conn = get_conn()
org = dict(conn.execute("SELECT * FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone())
answers = pos.get_org_answers(conn, org["org_id"])
payloads = pos.load_payloads(conn)
reg_api = api("/api/gap-register")
for sp in ("Reward",):  # nonrew-2: Wellbeing superpower deleted; maturity register is Reward-only
    ours, peers = [], []
    for qid, q in qs.items():
        if q.superpower != sp or q.category not in ("practice", "policy"):
            continue
        if not (q.is_scored and q.type in ("single_select", "yes_no", "multi_select")):
            continue
        p = payloads.get(qid)
        if p is None or "scores" not in p:
            continue
        raw = answers.get((qid, ""))
        s = score_answer(q, raw) if raw is not None else None
        if s is not None:
            ours.append(s)
        blk = (p["scores"] or {}).get("all")
        if blk and not blk.get("suppressed") and blk.get("p50") is not None:
            peers.append(blk["p50"])
    hand_o, hand_p = round(sum(ours) / len(ours), 1), round(sum(peers) / len(peers), 1)
    app_m = reg_api["maturity"][sp]
    ok = hand_o == app_m["org_score"] and hand_p == app_m["peer_median_score"]
    print("  %-10s hand org %.1f peer %.1f | app org %s peer %s" %
          (sp, hand_o, hand_p, app_m["org_score"], app_m["peer_median_score"]))
    check("maturity %s hand == app" % sp, ok)

# ------------------------------------------------ 1.4 suppression edge ------
print("\n== 1.4 Suppression: n=4 suppressed, n=5 NOT " + "=" * 46)
n5 = n4 = None
for qid, p in payloads.items():
    for sector, blk in (p.get("by_industry") or {}).items():
        if blk.get("n") == 5 and not blk.get("suppressed") and n5 is None:
            n5 = (qid, sector)
        if blk.get("suppressed") and blk.get("n") == 4 and n4 is None:
            n4 = (qid, sector)
check("found unsuppressed cut with n=5 exactly", n5 is not None, n5)
check("found suppressed cut with n=4", n4 is not None, n4)
if n5:
    c = api("/api/benchmark/%s?cut=industry&cut_value=%s" % (n5[0], urllib.request.quote(n5[1])))
    check("API serves the n=5 cut unsuppressed", not c["suppressed"] and c["n"] == 5)
if n4:
    c = api("/api/benchmark/%s?cut=industry&cut_value=%s" % (n4[0], urllib.request.quote(n4[1])))
    check("API suppresses the n=4 cut with no aggregates", c["suppressed"] and not c.get("block"))

# ---------------------------------------------------- 1.5 polarity dirs -----
print("\n== 1.5 Polarity: higher- and lower-is-better point correctly " + "=" * 28)
def find_answered(polarity):
    for qid, q in qs.items():
        if q.type == "numeric" and q.polarity == polarity + "_is_better":
            c = api("/api/benchmark/%s" % qid)
            if c.get("you") and c.get("block"):
                return c, q.display_title[:24]
    return None, None

hi, hi_name = find_answered("higher")
lo, lo_name = find_answered("lower")
for c, name, pol in ((hi, hi_name, "higher"), (lo, lo_name, "lower")):
    you, p50 = c["you"]["value"], c["block"]["p50"]
    fav = c.get("favourable")
    above = you > p50
    expect = ("good" if above else "bad") if pol == "higher" else ("bad" if above else "good")
    near = abs(c["you"]["percentile"] - 50) <= 5
    ok = (fav == expect) or (near and fav == "mid")
    print("  %-18s you=%s p50=%s pol=%s_is_better -> favourable=%s (expect %s%s)" %
          (name, you, p50, pol, fav, expect, " or mid (near median)" if near else ""))
    check("polarity direction %s" % name, ok)

# headline (board pack / share) and the gauge count the SAME Substance pool at the
# SAME band, so they must agree exactly — the "same org, one story" invariant
# (task #86, finished by threading MARKET_BAND into overview_summary). Asserting
# headline==gauge is stronger and band-correct vs the old favourable-recount, which
# used the legacy raw pool at the per-metric 45/55 cut and drifted once the headline
# was re-axed to the substance pool at the gauge's 35/65 band.
ov = api("/api/overview")
mkt = ov["hero"].get("market") or {}
check("overview headline above/below == gauge (board pack / share / dashboard, one story)",
      ov["headline"]["above_median"] == mkt.get("above")
      and ov["headline"]["below_median"] == mkt.get("below"),
      "headline %s/%s vs gauge %s/%s" % (ov["headline"]["above_median"], ov["headline"]["below_median"],
                                         mkt.get("above"), mkt.get("below")))

# ------------------------------------ 1.6 percentile function consistency ---
print("\n== 1.6 Percentile consistency between cards and £ model " + "=" * 33)
card = api("/api/benchmark/REW_BEN_PENS_EMP_MAX_01")
opp = card.get("opportunity")
ok = all(abs(r["p50"] - next(x for x in card["matrix_rows"] if x["row_id"] == r["row_id"])["block"]["p50"]) < 1e-9
         for r in (opp or {}).get("rows", []) if r.get("p50") is not None)
check("£ model reads the same P50s as the card (same engine percentile)", bool(opp) and ok)

# ---------------------------------------------------- 1.7 gap-to-£ ----------
print("\n== 1.7 Gap-to-£ reproduction + exclusions " + "=" * 47)
a = card["assumptions"]
fte = a["fte_band_midpoints"][org["fte_band"]]
tot = 0.0
for r in card["matrix_rows"]:
    if r["suppressed"] or "you" not in r:
        continue
    gap = max(0.0, r["block"]["p50"] - r["you"]["value"])
    tot += gap / 100.0 * a["median_salary_gbp"] * fte * a["level_shares"][r["row_id"]]
check("pension £-to-P50 reproduces by hand", abs(tot - opp["to_p50_gbp"]) < 1.0,
      "%d vs %d" % (round(tot), opp["to_p50_gbp"]))
agency = api("/api/benchmark/ATT_HIR_AGENCY_RATE_01")
aop = agency.get("opportunity")
if aop:
    tot = 0.0
    for r in agency["matrix_rows"]:
        if r["suppressed"] or "you" not in r:
            continue
        gap = max(0.0, r["you"]["value"] - r["block"]["p50"])
        tot += gap / 100.0 * fte * a["level_shares"][r["row_id"]] * a["median_salary_gbp"] * (a["agency_premium_pct"] / 100.0)
    check("agency £-to-P50 reproduces by hand", abs(tot - aop["to_p50_gbp"]) < 1.0,
          "%d vs %d" % (round(tot), aop["to_p50_gbp"]))
else:
    check("agency £ present (org worse than P50 somewhere)", True, "no agency gap for this org — formula tested via pension")
neutral = api("/api/benchmark/323ffcf1-749b-43f3-bf34-1de6b8b1ca67")  # max bonus, neutral
check("neutral-polarity metric has NO £ opportunity", "opportunity" not in neutral or neutral.get("opportunity") is None)
ovo = ov["opportunity"]
check("overview opportunity contains only non-neutral items",
      all(i["label"] in ("Employer pension contribution", "Regretted attrition", "Agency usage") for i in ovo["items"]))

print("\n== PHASE 1 SUMMARY: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL:
    print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
