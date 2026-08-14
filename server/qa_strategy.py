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


PROBE_IDS = []


def _org_ids():
    """Every org_id currently in the reward store — the before/after snapshot the
    probe ids are derived from."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn
    return {r["org_id"] for r in get_conn().execute("SELECT org_id FROM orgs")}


def main():
    print("== Reward strategy capture ==")
    smk = str(int(time.time())) + "s"
    # The cleanup used to RE-FIND its probes by orgs.name, which step 5 emptied — so it
    # matched nothing and the gate passed while leaking. The ids are captured here
    # instead, by diffing the org set across the registrations that create them: a
    # shape that cannot miss, because it never asks what the probes are called.
    _before_ids = _org_ids()
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

    # ---- Total Reward Strategy document capture (2026-08-14, rulings R1-R13) ----
    # R3b: a position target on Wellbeing / Governance is blocked at capture (brief §12).
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, domain_targets={"Wellbeing": "lead"})})
    check("R3b — position target on Wellbeing rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, domain_targets={"Governance & Transparency": "match"})})
    check("R3b — position target on Governance rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, domain_targets={"Pay": "lead"})})
    check("R3b — position target on Pay still accepted (200)", st == 200, st)
    # document caps + entitlement
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ,
                   "document": {"principles": ["p"] * 7}})
    check("principles cap — 7 statements rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ,
                   "document": {"principles": ["x" * 141]}})
    check("principle length cap — 141 chars rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ,
                   "document": {"measures": ["NOT_A_REAL_METRIC"]}})
    check("guardrail 6 — invisible metric as a measure rejected (400)", st == 400, st)
    st, opts = sa.req("/api/strategy/measure-options")
    check("measure-options lists visible metrics with floor + caps",
          st == 200 and opts.get("floor") == 5 and opts.get("max") == 8 and len(opts.get("options") or []) > 100)
    _mo = (opts.get("options") or [])
    _nine = [o["id"] for o in _mo[:9]]
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {"measures": _nine}})
    check("R4 — 9 measures rejected (400, cap 8)", st == 400, st)
    _five = [o["id"] for o in _mo[:5]]
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "measures": _five, "principles": ["We pay fairly and explain how pay works."],
        "constraints": {"selected": ["affordability"], "notes": "CPI pressure"},
        "reward_governance": {"owner": "CPO", "review_cadence": "annual", "effective_date": "2026-09-01"},
        "roadmap": [{"title": "Introduce salary bands", "horizon": "this_cycle"}],
        "segments": {"differentiated": True, "segments": ["Engineering"]}}})
    check("document-grade fields save (200)", st == 200, st)
    st, full2 = sa.req("/api/strategy")
    doc = full2.get("document") or {}
    check("document round-trips (measures + principles + governance persisted)",
          doc.get("measures") == _five and len(doc.get("principles") or []) == 1
          and (doc.get("reward_governance") or {}).get("review_cadence") == "annual")
    check("document provenance recorded (set/skipped, no phantom)",
          full2["provenance"].get("measures") == "set" and full2["provenance"].get("commitments") == "skipped")
    check("comparator defaults to All peers in words (R1/R2)",
          doc.get("comparator_label") == "All peers")
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "reward_governance": {"review_cadence": "monthly"}}})
    check("out-of-enum cadence rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "comparator_cut": "group::no-such-group"}})
    check("dangling comparator group rejected at save (400)", st == 400, st)
    # Wellbeing provision commitment: only visible Wellbeing metrics
    _wb = [o["id"] for o in _mo if o["category"] == "Wellbeing"][:2]
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "commitments": {"Wellbeing": {"metric_ids": _wb}}}})
    check("Wellbeing provision commitment saves (200)", st == 200 and bool(_wb), st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "commitments": {"Pay": {"statement": "nope"}}}})
    check("commitment on a position category rejected (400)", st == 400, st)

    # server-side gate + forged org_id ignored + isolation
    sb = Client()
    sb.req("/api/auth/register", "POST", {"org_name": "QA Strategy Probe " + smk + "b",
           "email": "qastratb%s@verify.example" % smk, "password": "probe-pass-123",
           "accept_platform_terms": True})
    PROBE_IDS.extend(sorted(_org_ids() - _before_ids))
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
    # teardown moved to the __main__ finally so it fires on the failing path too;
    # calling it here as well would run it twice.
    print("\n== %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    for n in FAIL:
        print("  FAILED:", n)
    return 1 if FAIL else 0


def _cleanup(probe_ids):
    """Remove the probe orgs from BOTH stores, by the ids captured at creation.

    Two changes from the version that leaked. It no longer re-finds by orgs.name (empty
    since step 5) — it uses ids it holds, so it cannot miss. And it now clears the
    identity store too: /api/auth/register writes both sides, so a reward-only delete
    would leave identity-only orphans, which identity_recon calls FATAL."""
    if not probe_ids:
        print("[cleanup] no probe ids captured — nothing removed")
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn
    import identity
    conn = get_conn()
    for oid in probe_ids:
        conn.execute("DELETE FROM org_strategy WHERE org_id=?", (oid,))
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM users WHERE org_id=?)", (oid,))
        conn.execute("DELETE FROM users WHERE org_id=?", (oid,))
        conn.execute("DELETE FROM orgs WHERE org_id=?", (oid,))
    conn.commit()
    for oid in probe_ids:
        identity.remove_org_identity(oid)          # D6: identity only through identity.py
    print("[cleanup] removed %d strategy probe org(s) from both stores" % len(probe_ids))


if __name__ == "__main__":
    import urllib.error  # noqa
    # _cleanup used to be the last statement of main(), so any exception before it
    # skipped teardown entirely — the shape that has kept verify.py's cleanup from
    # running since it went red. A finally makes it fire on the failing path too,
    # which is the path a leak fix most needs to survive.
    try:
        _rc = main()
    finally:
        _cleanup(PROBE_IDS)
    sys.exit(_rc)
