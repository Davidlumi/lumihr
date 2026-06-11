"""DEPRECATED (2026-06-11 delivery audit, defect D7): this suite assumes the
full 778-question scope and PRE-DATES the reward-only launch flag, the tier
removal and the required-set gate — its results are misleading under the
current configuration. Use instead:
  qa_focus.py        — reward-scope leak checks (23)
  qa_status_audit.py — gap-register presence semantics (full library)
  qa_hero.py         — hero polarity/positionability correctness (25)
  qa_commentary.py   — AI commentary adversarial gate (40)
Kept for the eventual all-superpowers relaunch; do not cite as evidence.
"""
import sys
if "--force" not in sys.argv:
    print(__doc__)
    print("Refusing to run (misleading under reward-only config). Use --force to override.")
    sys.exit(2)

"""lumi verification suite — runs the quality-bar checks against a live server.

Usage: python3 verify.py [--base http://localhost:8060]
Creates throwaway users/orgs as needed; safe to re-run.
"""
import argparse
import csv
import glob
import io
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import http.cookiejar

BASE = "http://localhost:8060"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)[:140]) if detail and not ok else ""))


class Client(object):
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, path, method="GET", body=None, raw=False):
        r = urllib.request.Request(BASE + path, method=method)
        data = None
        if body is not None:
            r.add_header("Content-Type", "application/json")
            data = json.dumps(body).encode()
        try:
            resp = self.opener.open(r, data=data, timeout=120)
            content = resp.read()
            return resp.status, (content if raw else json.loads(content or b"{}"))
        except urllib.error.HTTPError as e:
            content = e.read()
            try:
                return e.code, json.loads(content)
            except ValueError:
                return e.code, {"raw": content[:200]}


def login(email, pw):
    c = Client()
    st, _ = c.req("/api/auth/login", "POST", {"email": email, "password": pw})
    assert st == 200, "login failed for %s" % email
    return c


def main():
    print("\n== 1. Aggregation sanity (recompute medians from raw CSVs) ==")
    # covered by import-time hand-checks; re-verify one numeric via API vs CSV
    admin = login("director@thornbridge.example", "lumi-demo-2026")
    st, card = admin.req("/api/benchmark/PROP_9e3b1d18")  # early attrition, numeric
    vals = []
    for fn in glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "responses", "*.csv")):
        for row in csv.DictReader(open(fn, encoding="utf-8-sig")):
            if row["question_id"] == "PROP_9e3b1d18" and row["your_answer"].strip():
                try:
                    vals.append(float(row["your_answer"]))
                except ValueError:
                    pass
    vals.sort()
    k = (len(vals) - 1) * 0.5
    f = int(k)
    med = vals[f] + (vals[f + 1 if f + 1 < len(vals) else f] - vals[f]) * (k - f)
    check("numeric median matches independent recompute",
          abs(card["block"]["p50"] - med) < 1e-9, "%s vs %s" % (card["block"]["p50"], med))
    check("benchmark card carries n and cut label", card["n"] > 0 and card["cut"]["label"] == "All peers")

    print("\n== 2. No raw peer answers in client payloads ==")
    st, body = admin.req("/api/benchmarks/Reward")
    txt = json.dumps(body)
    check("no internal _values/_scores keys in API payloads", "_values" not in txt and "_scores" not in txt)
    # an org's raw answer should never appear: sample another org's distinctive numeric answer
    other_vals = set()
    for fn in glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "responses", "*.csv"))[:3]:
        rows = list(csv.DictReader(open(fn, encoding="utf-8-sig")))
        if rows and rows[0]["org_name"] != "Thornbridge Retail Group plc":
            other_vals.add(rows[0]["org_name"])
    check("other org names never appear in benchmark payloads",
          not any(n in txt for n in other_vals), list(other_vals))
    st, ov = admin.req("/api/overview")
    check("overview has callouts citing percentile and n",
          all(re.search(r"\(P\d+.*n=\d+\)", t) for t in ov["callouts"]["gaps"] + ov["callouts"]["strengths"]))

    print("\n== 3. Suppression ==")
    # find a question+cut that is suppressed: use a small sector with few answers
    st, qs = admin.req("/api/questions")
    suppressed_found, leak = False, None
    for qid in [q["id"] for q in qs["questions"] if not q["locked"]][:300]:
        st, c = admin.req("/api/benchmark/%s?cut=industry&cut_value=%s" % (qid, urllib.parse.quote("Charity, Non-Profit & Social Enterprise")))
        if c.get("suppressed"):
            suppressed_found = True
            if c.get("block") or c.get("histogram"):
                leak = qid
            break
    check("suppressed cut renders with no aggregates", suppressed_found and leak is None, leak)

    print("\n== 4. Tenancy & roles ==")
    viewer = login("ceo@thornbridge.example", "lumi-view-2026")
    st, _ = viewer.req("/api/submission/draft", "PUT", {"question_id": "PROP_9e3b1d18", "value": "5"})
    check("viewer cannot save submission drafts (403)", st == 403, st)
    st, _ = viewer.req("/api/shares", "GET")
    check("viewer cannot reach share management (403)", st == 403, st)
    st, _ = viewer.req("/api/team/invite", "POST", {"email": "x@y.zz"})
    check("viewer cannot invite (403)", st == 403, st)
    st, _ = viewer.req("/api/gap-register.csv")
    check("viewer cannot export gap register CSV (403)", st == 403, st)

    # cross-tenant: register a fresh org and try to read Thornbridge data
    mark = str(int(time.time()))
    stranger = Client()
    st, _ = stranger.req("/api/auth/register", "POST", {
        "org_name": "Verify Probe Ltd " + mark, "email": "probe%s@verify.example" % mark,
        "password": "probe-pass-123"})
    check("new org registration works", st == 200, st)
    st, mydata = stranger.req("/api/my-data")
    check("new org sees zero answers (no bleed)", st == 200 and len(mydata["rows"]) == 0)
    st, packs = stranger.req("/api/boardpack/c51d5dea-866d-48a5-a803-276e66465548")
    check("cannot fetch another org's board pack (404)", st == 404, st)
    st, mv = stranger.req("/api/me")
    check("new sign-up is core tier and benchmark-gated",
          mv["org"]["tier_entitlement"] == "core" and mv["benchmark_unlocked"] is False)
    st, c = stranger.req("/api/benchmark/REW_BEN_PENS_EMP_MAX_01")
    check("Enhanced question locked for core org (no aggregates)",
          c.get("locked") is True and "matrix_rows" not in c and "block" not in c)

    print("\n== 5. 778-question coverage (render / suppressed / locked — zero silent drops) ==")
    st, qs2 = admin.req("/api/questions")
    check("all 778 questions in index", len(qs2["questions"]) == 778, len(qs2["questions"]))
    missing = []
    for sp in ["Reward", "Processes", "Wellbeing", "Growth", "Capability", "Inclusivity",
               "Attract", "Leadership", "Purpose", "Change"]:
        st, b = admin.req("/api/benchmarks/" + sp)
        for cdd in b["cards"]:
            ok = cdd.get("locked") or cdd.get("suppressed") or cdd.get("block") or cdd.get("matrix_rows")
            if not ok:
                missing.append(cdd["id"])
    total_cards = 0
    for sp in ["Reward", "Processes", "Wellbeing", "Growth", "Capability", "Inclusivity",
               "Attract", "Leadership", "Purpose", "Change"]:
        st, b = admin.req("/api/benchmarks/" + sp)
        total_cards += len(b["cards"])
    check("every question renders, suppresses or locks", total_cards == 778 and not missing,
          "cards=%d missing=%s" % (total_cards, missing[:5]))

    print("\n== 6. Submission validation ==")
    # hard bound: candidate NPS hard range? use a numeric with tolerance
    st, sec = admin.req("/api/submission/section/Attract")
    hard_q = None
    for q in sec["questions"]:
        tol = q.get("tolerance") or {}
        if q["type"] == "numeric" and tol.get("hard_max") is not None:
            hard_q = q
            break
    if hard_q:
        st, r = admin.req("/api/submission/draft", "PUT", {
            "question_id": hard_q["id"], "value": str(hard_q["tolerance"]["hard_max"] * 1000 + 1)})
        check("hard_max violation blocks draft", st == 200 and r["ok"] is False and r["errors"])
        soft_ok = None
        if hard_q["tolerance"].get("soft_max") is not None:
            st, r2 = admin.req("/api/submission/draft", "PUT", {
                "question_id": hard_q["id"],
                "value": str(min(hard_q["tolerance"]["hard_max"], hard_q["tolerance"]["soft_max"] + 1))})
            soft_ok = r2["ok"] is True and len(r2["warnings"]) > 0
            check("soft bound warns but saves", soft_ok, r2)
    # multi_select None-exclusive
    st, secp = admin.req("/api/submission/section/Reward")
    ms = next((q for q in secp["questions"] if q["type"] == "multi_select"
               and any(o["label"].lower().startswith("none") for o in q["options"])), None)
    if ms:
        none_lbl = next(o["label"] for o in ms["options"] if o["label"].lower().startswith("none"))
        other_lbl = next(o["label"] for o in ms["options"] if not o["label"].lower().startswith("none"))
        st, r = admin.req("/api/submission/draft", "PUT", {
            "question_id": ms["id"], "value": "%s; %s" % (none_lbl, other_lbl)})
        check("'None' exclusive rule enforced", r["ok"] is False, r)
    # invalid select option
    sel = next(q for q in secp["questions"] if q["type"] == "single_select")
    st, r = admin.req("/api/submission/draft", "PUT", {"question_id": sel["id"], "value": "Not a real option"})
    check("unknown select option rejected", r["ok"] is False)

    print("\n== 7. Submission changes live peer n ==")
    # stranger org completes firmographics then submits one answer; n should rise for that q
    st, _ = stranger.req("/api/submission/firmographics", "PUT", {
        "industry": "Retail & Consumer Goods", "subsector": "Probe", "fte_band": "250-999",
        "hq_region": "London", "ownership_type": "Private (Founder/Family)"})
    check("firmographics accepted", st == 200)
    # answer one Core numeric — find a Core question stranger can draft
    st, qlist = stranger.req("/api/questions")
    core_numeric = None
    st, secA = stranger.req("/api/submission/section/Attract")
    for q in secA["questions"]:
        if q["type"] == "numeric" and q["tier"] == "Core":
            core_numeric = q
            break
    if core_numeric is None:
        for q in secA["questions"]:
            if q["type"] == "numeric":
                core_numeric = q
                break
    st, before = admin.req("/api/benchmark/" + core_numeric["id"])
    st, r = stranger.req("/api/submission/draft", "PUT", {"question_id": core_numeric["id"], "value": "42"})
    if not r.get("ok"):
        st, r = stranger.req("/api/submission/draft", "PUT", {"question_id": core_numeric["id"], "value": "10"})
    st, sub = stranger.req("/api/submission/submit", "POST", {})
    check("submission accepted", st == 200 and sub.get("ok"), sub)
    st, after = admin.req("/api/benchmark/" + core_numeric["id"])
    check("peer n increased after submission (%s)" % core_numeric["id"],
          after["n"] == before["n"] + 1, "%d -> %d" % (before["n"], after["n"]))
    # draft survives logout/login (use a fresh draft)
    st, _ = stranger.req("/api/submission/draft", "PUT", {"question_id": core_numeric["id"], "value": "11"})
    stranger2 = login("probe%s@verify.example" % mark, "probe-pass-123")
    st, secA2 = stranger2.req("/api/submission/section/Attract")
    qq = next(q for q in secA2["questions"] if q["id"] == core_numeric["id"])
    check("draft survives logout/login", str(qq["current"]) == "11", qq["current"])

    print("\n== 8. Shares lifecycle ==")
    st, sh = admin.req("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
    token = sh["token"]
    anon = Client()
    st, d = anon.req("/api/share/%s/data" % token)
    check("share link works without login", st == 200 and d["kind"] == "dashboard")
    txt = json.dumps(d)
    check("share payload has no internal keys", "_values" not in txt and "_scores" not in txt)
    check("share payload only the sharing org's identity", d["org_name"] == "Thornbridge Retail Group plc")
    st, _ = admin.req("/api/shares/" + token, "DELETE")
    st, d2 = anon.req("/api/share/%s/data" % token)
    check("revoked share link dies (404)", st == 404, st)
    # expired share: create directly then backdate via API is not possible -> covered by SQL in unit terms; skip
    st, shl = admin.req("/api/shares")
    audit = next(s for s in shl["shares"] if s["token"] == token)["audit"]
    check("share audit logs created+revoked", [a["action"] for a in audit] == ["created", "revoked"], audit)

    print("\n== 9. Peer Twin ==")
    st, tw = admin.req("/api/peer-twin")
    seed_names = set()
    for fn in glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "responses", "*.csv"))[:40]:
        rows = list(csv.DictReader(open(fn, encoding="utf-8-sig")))
        if rows:
            seed_names.add(rows[0]["org_name"])
    seed_names.discard("Thornbridge Retail Group plc")
    tw_txt = json.dumps(tw)
    check("twin available with rationale, no peer org names",
          tw["available"] and "attributes" in tw["rationale"] and not any(n in tw_txt for n in seed_names))
    st, tc = admin.req("/api/benchmark/PROP_9e3b1d18?cut=twin")
    check("twin cut aggregates respect suppression shape",
          tc["suppressed"] or (tc["n"] >= 5 and tc["block"]["p50"] is not None), tc.get("n"))

    print("\n== 10. Board pack number audit ==")
    st, gen = admin.req("/api/boardpack/generate", "POST", {"cut": "all"})
    st, pk = admin.req("/api/boardpack/" + gen["pack_id"])
    pl, nr = pk["payload"], pk["narrative"]
    payload_numbers = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(pl)))
    bad = [s for s in re.findall(r"\d+(?:\.\d+)?", json.dumps(nr)) if s not in payload_numbers]
    check("board pack narrative numbers all present in payload", len(bad) == 0, bad[:8])

    print("\n== 11. Analyst guardrails ==")
    st, a1 = admin.req("/api/analyst", "POST", {"question": "what will our turnover be next year?"})
    ans = a1["answer"].lower()
    check("analyst gives no forecast (fallback or refusal)",
          ("not configured" in ans) or ("can't" in ans) or ("cannot" in ans) or ("doesn't" in ans),
          a1["answer"][:120])

    print("\n== 12. £ model reproduction ==")
    st, card = admin.req("/api/benchmark/REW_BEN_PENS_EMP_MAX_01")
    opp = card["opportunity"]
    a = card["assumptions"]
    fte = a["fte_band_midpoints"]["50-249"]
    tot = 0.0
    for row in card["matrix_rows"]:
        if row["suppressed"] or "you" not in row:
            continue
        gap = max(0.0, row["block"]["p50"] - row["you"]["value"])
        tot += gap / 100.0 * a["median_salary_gbp"] * fte * a["level_shares"][row["row_id"]]
    check("pension £-to-P50 reproduces by hand", abs(tot - opp["to_p50_gbp"]) < 1.0,
          "%s vs %s" % (round(tot), opp["to_p50_gbp"]))

    print("\n== 13. Expired share link ==")
    st, sh2 = admin.req("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
    _backdate_share(sh2["token"])
    st, _d = anon.req("/api/share/%s/data" % sh2["token"])
    check("expired share link expires (404)", st == 404, st)

    print("\n== 14. Plain-English edge readouts ==")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import positions as pos
    cases = {1: pos.tens_phrase(1), 50: pos.tens_phrase(50), 99: pos.tens_phrase(99),
             63: pos.tens_phrase(63), 7: pos.tens_phrase(7), 93: pos.tens_phrase(93)}
    check("edge readouts grammatical",
          cases[1].startswith("among the very lowest") and cases[99].startswith("among the very highest")
          and "middle" in cases[50] and "6 in 10" in cases[63]
          and "9 in 10" in cases[93] and cases[7].startswith("among the very") is False and "in 10" in cases[7],
          cases)

    print("\n== 15. Pinned view survives logout/login ==")
    st, mv0 = admin.req("/api/myview")
    test_layout = [{"question_id": "PROP_9e3b1d18", "size": 2}]
    admin.req("/api/myview", "PUT", {"layout": test_layout})
    admin2 = login("director@thornbridge.example", "lumi-demo-2026")
    st, mv1 = admin2.req("/api/myview")
    check("my-view layout persists across sessions",
          mv1["source"] == "user" and mv1["layout"] == test_layout, mv1)
    admin2.req("/api/myview", "PUT", {"layout": mv0["layout"] if mv0["source"] == "user" else []})

    _cleanup()
    print("\n== Summary: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    for n, d in FAIL:
        print("  FAILED: %s — %s" % (n, str(d)[:200]))
    return 1 if FAIL else 0


def _backdate_share(token):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn
    conn = get_conn()
    conn.execute("UPDATE shares SET expires_at=datetime('now','-1 hour') WHERE token=?", (token,))
    conn.commit()


def _cleanup():
    """Remove probe orgs and test drafts so verification leaves the live
    benchmark exactly as it found it, then re-aggregate."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn
    from aggregate import run_snapshot
    conn = get_conn()
    probes = [r["org_id"] for r in conn.execute(
        "SELECT org_id FROM orgs WHERE name LIKE 'Verify Probe Ltd%'")]
    for oid in probes:
        for tbl in ("answers", "answers_history", "drafts", "org_assumptions",
                    "peer_twin_cache", "pinned_views", "shares", "board_packs"):
            conn.execute("DELETE FROM %s WHERE org_id=?" % tbl, (oid,))
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM users WHERE org_id=?)", (oid,))
        conn.execute("DELETE FROM users WHERE org_id=?", (oid,))
        conn.execute("DELETE FROM orgs WHERE org_id=?", (oid,))
    # drop drafts created on the demo org during validation checks
    demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()
    if demo:
        conn.execute("DELETE FROM drafts WHERE org_id=?", (demo["org_id"],))
    conn.commit()
    run_snapshot(1, verbose=False)
    print("\n[cleanup] removed %d probe org(s), cleared demo drafts, re-aggregated snapshot" % len(probes))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    args = ap.parse_args()
    BASE = args.base
    import urllib.parse  # noqa: F401  (used above)
    sys.exit(main())
