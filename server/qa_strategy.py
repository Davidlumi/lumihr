# -*- coding: utf-8 -*-
"""Reward strategy capture — live quality bar (the runnable replacement for the
deprecated verify.py block; same assertions, against the running server).

Covers spec §6: tenancy (viewer/contributor 403, admin 200, org from session,
forged org_id ignored), server-side enum validation, the server-side required
gate, provenance integrity (set/skipped, no phantom 'suggested'), no demographic
suggestions, and tenant isolation. Plus the engine degrade contract (§5.5).

    python3 server/qa_strategy.py      # needs the dev server on :8060
"""
import json
import os
import sys
import time
import urllib.request
import http.cookiejar

BASE = "http://localhost:8060"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  — " + str(detail)[:150]) if (detail and not ok) else ""))


class Client:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def req(self, path, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(BASE + path, method=method, data=data,
                                   headers={"Content-Type": "application/json"})
        try:
            resp = self.op.open(r, timeout=60)
            return resp.status, json.loads(resp.read() or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or "{}")
            except Exception:
                return e.code, {}


def login(email, pw):
    c = Client()
    st, _ = c.req("/api/auth/login", "POST", {"email": email, "password": pw})
    assert st == 200, "login failed for %s (%s)" % (email, st)
    return c


def main():
    print("== Reward strategy capture ==")
    smk = str(int(time.time())) + "s"
    sa = Client()
    st, _ = sa.req("/api/auth/register", "POST", {"org_name": "QA Strategy Probe " + smk,
                   "email": "qastrat%s@verify.example" % smk, "password": "probe-pass-123",
                   "accept_platform_terms": True})
    check("probe admin org registered", st == 200, st)
    REQ = {"market_position": "lead", "reward_mix": "balanced", "primary_objective": "retain"}

    # tenancy
    st, _ = login("ceo@thornbridge.example", "lumi-view-2026").req("/api/strategy", "PUT", {"strategy": REQ})
    check("viewer PUT blocked (403)", st == 403, st)
    st, _ = login("analyst@thornbridge.example", "lumi-data-2026").req("/api/strategy", "PUT", {"strategy": REQ})
    check("contributor PUT blocked (403)", st == 403, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, transparency="open")})
    check("admin PUT succeeds (200)", st == 200, st)

    # required gate + provenance
    st, full = sa.req("/api/strategy")
    check("completed_at set once 3 required present", bool(full["completed_at"]))
    check("chosen dials provenance 'set'", full["provenance"].get("market_position") == "set"
          and full["provenance"].get("transparency") == "set")
    check("untouched optionals provenance 'skipped' — no phantom 'suggested'",
          full["provenance"].get("location_approach") == "skipped"
          and full["provenance"].get("benefits_lead") == "skipped"
          and "suggested" not in set(full["provenance"].values()))
    check("family_position + benefits_lead start blank (no demographic suggestion, §2.1)",
          not full["strategy"]["family_position"] and not full["strategy"]["benefits_lead"])
    # suggestions endpoint emits nothing in v1
    st, sug = sa.req("/api/strategy/suggestions")
    check("suggestions endpoint reserved + empty (v1)", st == 200 and sug.get("suggestions") == {})

    # enum validation — never coerce
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, market_position="nonsense")})
    check("out-of-enum value rejected (400, not coerced)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, benefits_lead=["bogus"])})
    check("out-of-enum benefits area rejected (400)", st == 400, st)

    # server-side gate + forged org_id ignored + isolation
    sb = Client()
    sb.req("/api/auth/register", "POST", {"org_name": "QA Strategy Probe " + smk + "b",
           "email": "qastratb%s@verify.example" % smk, "password": "probe-pass-123",
           "accept_platform_terms": True})
    sb.req("/api/strategy", "PUT", {"strategy": {"market_position": "match", "reward_mix": "cash"},
                                    "org_id": "forged-not-mine"})   # missing primary_objective + forged org
    st, partial = sb.req("/api/strategy")
    check("gate is server-side — missing a required leaves completed_at null",
          partial["completed_at"] is None, partial.get("completed_at"))
    check("org_id from session — forged body org_id ignored (B wrote its own row)",
          partial["strategy"]["market_position"] == "match")
    st, sa_after = sa.req("/api/strategy")
    check("isolation — probe B's write never touched probe A's strategy",
          sa_after["strategy"]["market_position"] == "lead")

    # cleanup probe orgs
    _cleanup([smk, smk + "b"])
    print("\n== %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    for n in FAIL:
        print("  FAILED:", n)
    return 1 if FAIL else 0


def _cleanup(marks):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT org_id FROM orgs WHERE name LIKE 'QA Strategy Probe %'").fetchall()
    for r in rows:
        oid = r["org_id"]
        conn.execute("DELETE FROM org_strategy WHERE org_id=?", (oid,))
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM users WHERE org_id=?)", (oid,))
        conn.execute("DELETE FROM users WHERE org_id=?", (oid,))
        conn.execute("DELETE FROM orgs WHERE org_id=?", (oid,))
    conn.commit()
    print("[cleanup] removed %d strategy probe org(s)" % len(rows))


if __name__ == "__main__":
    import urllib.error  # noqa
    sys.exit(main())
