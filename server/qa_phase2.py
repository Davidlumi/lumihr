# -*- coding: utf-8 -*-
"""QA Phase 2 — tenancy & security: manipulate the actual API, inspect actual
payloads, inspect the DB and response headers. UI behaviour proves nothing here.
"""
import csv
import glob
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import http.cookiejar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = "http://localhost:8060"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "responses")
PASS, FAIL = [], []
TESTED_ENDPOINTS = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:130] + "]") if detail else ""))


class Client(object):
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.last_headers = {}

    def req(self, path, method="GET", body=None):
        TESTED_ENDPOINTS.append("%s %s" % (method, path.split("?")[0]))
        r = urllib.request.Request(BASE + path, method=method)
        data = None
        if body is not None:
            r.add_header("Content-Type", "application/json")
            data = json.dumps(body).encode()
        try:
            resp = self.opener.open(r, data=data, timeout=60)
            self.last_headers = dict(resp.headers)
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, raw[:200]
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except ValueError:
                return e.code, {}


admin = Client()
st, _ = admin.req("/api/auth/login", "POST", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
assert st == 200

# identify a foreign org's id + a distinctive raw answer of theirs
foreign_org_id = foreign_name = None
foreign_numeric = None
for fn in sorted(glob.glob(os.path.join(DATA, "*.csv"))):
    rows = list(csv.DictReader(open(fn, encoding="utf-8-sig")))
    if rows and rows[0]["org_name"] != "Thornbridge Retail Group plc":
        foreign_org_id, foreign_name = rows[0]["org_id"], rows[0]["org_name"]
        for r in rows:
            if r["question_id"] == "PROP_e63cf45a" and r["your_answer"].strip():
                foreign_numeric = r["your_answer"].strip()
        break

print("== 2.1 Cross-tenant isolation (as Org A, attack Org B = %s) ==" % foreign_name[:30])
# Every data endpoint takes org identity from the session; probe the ones that
# accept ANY identifier, substituting foreign/forged values.
st, body = admin.req("/api/boardpack/%s" % foreign_org_id)            # forged pack id
check("GET /api/boardpack/{foreign-uuid} -> 404", st == 404, st)
st, body = admin.req("/api/benchmark/PROP_e63cf45a?cut=industry&cut_value=%s&org_id=%s"
                     % (urllib.parse.quote("Retail & Consumer Goods"), foreign_org_id))
leak = foreign_numeric and foreign_numeric in json.dumps(body)
check("GET /api/benchmark?...&org_id={foreign} ignored (session wins, no foreign value)", st == 200 and not leak)
st, body = admin.req("/api/my-data?org_id=%s" % foreign_org_id)
ok = st == 200 and all("Thornbridge" not in json.dumps(body.get("rows", [])[:2]) or True for _ in [0])
names_leak = foreign_name in json.dumps(body)
check("GET /api/my-data?org_id={foreign} returns only own org", st == 200 and not names_leak)
st, body = admin.req("/api/gap-register?org_id=%s" % foreign_org_id)
check("GET /api/gap-register?org_id={foreign} ignored", st == 200 and foreign_name not in json.dumps(body))
st, body = admin.req("/api/share/%s/data" % foreign_org_id)           # forged share token
check("GET /api/share/{forged-token}/data -> 404", st == 404, st)
st, body = admin.req("/api/submission/draft", "PUT",
                     {"question_id": "PROP_e63cf45a", "value": "999", "org_id": foreign_org_id})
check("PUT draft with injected org_id writes to own org only (session-scoped)", st in (200, 403))
# confirm the draft did NOT land on the foreign org
import sqlite3 as s3
db = s3.connect(os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))  # nonrew-2: honor LUMI_DB so the DELETE FROM drafts hits the throwaway, never live
row = db.execute("SELECT COUNT(*) FROM drafts WHERE org_id=?", (foreign_org_id,)).fetchone()
check("DB: no draft row created for foreign org", row[0] == 0, row[0])
db.execute("DELETE FROM drafts"); db.commit()

print("\n== 2.2 Raw-answer leakage in real payloads ==")
big = ""
for path in ("/api/overview", "/api/benchmarks/Reward", "/api/gap-register",
             "/api/analyst/starters", "/api/methodology"):
    st, body = admin.req(path)
    big += json.dumps(body)
st, packs = admin.req("/api/boardpacks")
if packs.get("packs"):
    st, body = admin.req("/api/boardpack/%s" % packs["packs"][0]["pack_id"])
    big += json.dumps(body)
check("no internal _values/_scores arrays in any payload", "_values" not in big and "_scores" not in big)
check("no foreign org names in any payload", foreign_name not in big)
# spot-check: foreign org's distinctive numeric answer value should not appear as a raw answer
# (it may coincide with an aggregate; use a 4+ digit exact value with low collision odds)
if foreign_numeric and len(foreign_numeric) >= 4:
    hits = big.count('"%s"' % foreign_numeric)
    check("foreign org's raw answer string absent from payloads", hits == 0, foreign_numeric)

print("\n== 2.3 Role enforcement (Viewer by direct URL) ==")
viewer = Client()
st, _ = viewer.req("/api/auth/login", "POST", {"email": "ceo@thornbridge.example", "password": "lumi-view-2026"})
for path, method, body in [("/api/submission/draft", "PUT", {"question_id": "PROP_e63cf45a", "value": "5"}),
                           ("/api/submission/submit", "POST", {}),
                           ("/api/shares", "GET", None),
                           ("/api/shares", "POST", {"kind": "dashboard", "config": {}}),
                           ("/api/team/invite", "POST", {"email": "x@x.xx"}),
                           ("/api/gap-register.csv", "GET", None),
                           ("/api/assumptions", "PUT", {"assumptions": {"median_salary_gbp": 1}}),
                           ("/api/submission/firmographics", "PUT", {"industry": "Financial Services"}),
                           ("/api/myview/save-default", "POST", {"layout": []})]:
    st, _b = viewer.req(path, method, body)
    check("viewer %s %s -> 403" % (method, path), st == 403, st)

print("\n== 2.4 Share-link lifecycle ==")
st, sh = admin.req("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
anon = Client()
st, d = anon.req("/api/share/%s/data" % sh["token"])
check("valid link works anonymously", st == 200)
check("valid link exposes only sharing org's view", d.get("org_name") == "Thornbridge Retail Group plc"
      and foreign_name not in json.dumps(d) and "_values" not in json.dumps(d))
st, _ = admin.req("/api/shares/%s" % sh["token"], "DELETE")
st, _d = anon.req("/api/share/%s/data" % sh["token"])
check("revoked link -> 404", st == 404, st)
st, sh2 = admin.req("/api/shares", "POST", {"kind": "dashboard", "config": {"cut": {"dim": "all"}}, "expiry_days": 7})
db.execute("UPDATE shares SET expires_at=datetime('now','-1 hour') WHERE token=?", (sh2["token"],)); db.commit()
st, _d = anon.req("/api/share/%s/data" % sh2["token"])
check("expired link -> 404", st == 404, st)
admin.req("/api/shares/%s" % sh2["token"], "DELETE")

print("\n== 2.5 Auth basics ==")
rows = db.execute("SELECT pw_hash FROM users LIMIT 5").fetchall()
check("passwords bcrypt-hashed in DB (no plaintext)", all(r[0].startswith("$2") for r in rows),
      rows[0][0][:12])
fresh = Client()
# capture Set-Cookie on login
req = urllib.request.Request(BASE + "/api/auth/login", method="POST",
                             data=json.dumps({"email": "director@thornbridge.example",
                                              "password": "lumi-demo-2026"}).encode())
req.add_header("Content-Type", "application/json")
resp = urllib.request.urlopen(req)
sc = resp.headers.get("set-cookie", "")
check("session cookie HttpOnly + SameSite", "httponly" in sc.lower() and "samesite" in sc.lower(), sc[:90])
# rate limit: 6 rapid bad logins for one email
codes = []
for i in range(7):
    st, _b = fresh.req("/api/auth/login", "POST", {"email": "ratelimit@test.example", "password": "wrong"})
    codes.append(st)
check("login rate-limited (429 after 5 attempts)", 429 in codes, codes)

print("\n== ENDPOINTS EXERCISED ==")
for e in sorted(set(TESTED_ENDPOINTS)):
    print("   ", e)
print("\n== PHASE 2 SUMMARY: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, d in FAIL:
    print("  FAILED:", n, d)
sys.exit(1 if FAIL else 0)
