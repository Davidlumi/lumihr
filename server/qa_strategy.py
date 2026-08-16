# -*- coding: utf-8 -*-
"""Reward strategy capture — live quality bar (the runnable replacement for the
deprecated verify.py block; same assertions, against the running server).

Covers spec §6: tenancy (viewer 403, contributor/admin save, approval admin-only,
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
    # 2026-08-15: the Contributor DOES the reward work, so they may save the strategy;
    # only an Admin may approve it (asserted in the approval block below).
    _cb = login("analyst@thornbridge.example", "lumi-data-2026")
    _st0, _cur = _cb.req("/api/strategy")
    st, _ = _cb.req("/api/strategy", "PUT", {"strategy": _cur["strategy"]})   # same values back
    check("contributor PUT allowed (200) — approval is the admin-only act", st == 200, st)
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
    st, opts = sa.req("/api/strategy/measure-options")
    check("measure-options lists visible metrics with floor + caps",
          st == 200 and opts.get("floor") == 5 and opts.get("max") == 8 and len(opts.get("options") or []) > 100)
    _mo = (opts.get("options") or [])
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "principles": ["We pay fairly and explain how pay works."],
        "constraints": {"selected": ["affordability"], "notes": "CPI pressure"}}})
    check("document-grade fields save (200)", st == 200, st)
    st, full2 = sa.req("/api/strategy")
    doc = full2.get("document") or {}
    check("document round-trips (principles + constraints persisted)",
          len(doc.get("principles") or []) == 1
          and (doc.get("constraints") or {}).get("selected") == ["affordability"])
    # 2026-08-15 removals: measures / commitments / governance / segments are captured in
    # the metrics (or unevidenceable) — the API must simply ignore them, never store them.
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "measures": [{"id": "x"}], "commitments": {"Wellbeing": {"metric_ids": ["y"]}},
        "reward_governance": {"owner": "CPO"}, "segments": {"differentiated": True}}})
    check("removed sections are accepted and ignored (200)", st == 200, st)
    st, full2b = sa.req("/api/strategy")
    _d2 = full2b.get("document") or {}
    check("removed sections are not stored or served",
          not _d2.get("measures") and not _d2.get("commitments")
          and not _d2.get("reward_governance") and not _d2.get("segments"), list(_d2))
    check("document provenance recorded (set/skipped, no phantom)",
          full2["provenance"].get("principles") == "set" and full2["provenance"].get("measures") == "skipped"
          and "suggested" not in set(full2["provenance"].values()))
    check("comparator defaults to All peers in words (R1/R2)",
          doc.get("comparator_label") == "All peers")
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "comparator_cut": "group::no-such-group"}})
    check("dangling comparator group rejected at save (400)", st == 400, st)

    # ---- ONE peer group: the strategy comparator IS the org default cut ----
    # (2026-08-15 — the strategy must never name a different market from the one the
    # benchmark, Signals and alerts read from.)
    _opts = (opts.get("options") or [])
    st, me0 = sa.req("/api/me")
    _band = (me0.get("org") or {}).get("fte_band") or "50-249"
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {"comparator_cut": "fte_band::" + _band}})
    check("comparator accepts a size cut (200)", st == 200, st)
    st, me1 = sa.req("/api/me")
    check("choosing a comparator MOVES the org default peer group",
          (me1.get("org") or {}).get("signal_peer_cut") == "fte_band::" + _band,
          (me1.get("org") or {}).get("signal_peer_cut"))
    st, s1 = sa.req("/api/strategy")
    check("the strategy reads the comparator back from the org default",
          (s1.get("document") or {}).get("comparator_cut") == "fte_band::" + _band,
          (s1.get("document") or {}).get("comparator_cut"))
    check("comparator label matches the benchmark's own wording for that cut",
          (s1.get("document") or {}).get("comparator_label") == _band + " FTE",
          (s1.get("document") or {}).get("comparator_label"))
    # move the DEFAULT from the other side — the strategy must follow, not contradict
    st, _ = sa.req("/api/org/signal-peers", "PUT", {"cut": "all"})
    st, s2 = sa.req("/api/strategy")
    check("changing the peer group elsewhere updates the stated comparator",
          (s2.get("document") or {}).get("comparator_cut") is None
          and (s2.get("document") or {}).get("comparator_label") == "All peers",
          (s2.get("document") or {}).get("comparator_label"))
    # ---- ONE peer group: the strategy comparator IS the org default cut ----
    # (2026-08-15 — the strategy must never name a different market from the one the
    # benchmark, Signals and alerts read from.)
    _opts = (opts.get("options") or [])
    st, me0 = sa.req("/api/me")
    _band = (me0.get("org") or {}).get("fte_band") or "50-249"
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {"comparator_cut": "fte_band::" + _band}})
    check("comparator accepts a size cut (200)", st == 200, st)
    st, me1 = sa.req("/api/me")
    check("choosing a comparator MOVES the org default peer group",
          (me1.get("org") or {}).get("signal_peer_cut") == "fte_band::" + _band,
          (me1.get("org") or {}).get("signal_peer_cut"))
    st, s1 = sa.req("/api/strategy")
    check("the strategy reads the comparator back from the org default",
          (s1.get("document") or {}).get("comparator_cut") == "fte_band::" + _band,
          (s1.get("document") or {}).get("comparator_cut"))
    check("comparator label matches the benchmark's own wording for that cut",
          (s1.get("document") or {}).get("comparator_label") == _band + " FTE",
          (s1.get("document") or {}).get("comparator_label"))
    # move the DEFAULT from the other side — the strategy must follow, not contradict
    st, _ = sa.req("/api/org/signal-peers", "PUT", {"cut": "all"})
    st, s2 = sa.req("/api/strategy")
    check("changing the peer group elsewhere updates the stated comparator",
          (s2.get("document") or {}).get("comparator_cut") is None
          and (s2.get("document") or {}).get("comparator_label") == "All peers",
          (s2.get("document") or {}).get("comparator_label"))
    # Wellbeing provision commitment: only visible Wellbeing metrics
    _wb = [o["id"] for o in _mo if o["category"] == "Wellbeing"][:2]
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "commitments": {"Wellbeing": {"metric_ids": _wb}}}})
    check("Wellbeing provision commitment saves (200)", st == 200 and bool(_wb), st)

    # ---- 2026-08-15: server drafts · role split · approval as a governance act ----
    # population positions — document statements, enum-guarded
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "population_targets": [{"label": "Board / Executive", "position": "lead", "note": "total comp at UQ"}]}})
    check("population position saves (200)", st == 200, st)
    st, full5 = sa.req("/api/strategy")
    check("population position round-trips",
          ((full5.get("document") or {}).get("population_targets") or [{}])[0].get("position") == "lead")
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "population_targets": [{"label": "Board of aliens", "position": "lead"}]}})
    check("unknown population rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ, "document": {
        "population_targets": [{"label": "Board / Executive", "position": "sideways"}]}})
    check("invalid population stance rejected (400)", st == 400, st)

    # objective RATINGS with a hard budget — and the engine still gets one primary
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, objective_weights={"attract": 6, "retain": 3})})
    check("objective ratings save (200)", st == 200, st)
    st, fw = sa.req("/api/strategy")
    check("ratings round-trip", (fw["strategy"].get("objective_weights") or {}).get("attract") == 6)
    check("primary_objective derived from the highest rating",
          fw["strategy"]["primary_objective"] == "attract", fw["strategy"]["primary_objective"])
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, objective_weights={"attract": 7, "retain": 7})})
    check("over-budget allocation rejected (400) — the cap forces a choice", st == 400, st)
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": dict(REQ, objective_weights={"nonsense": 3})})
    check("unknown objective rejected (400)", st == 400, st)

    # server-side draft: stored apart from the live strategy, never engine-visible
    st, _ = sa.req("/api/strategy/draft", "PUT", {"draft": {"strat": {"market_position": "lag"}, "step": 3}})
    check("draft saves server-side (200)", st == 200, st)
    st, dr = sa.req("/api/strategy/draft")
    check("draft round-trips with step + who", (dr.get("draft") or {}).get("step") == 3 and bool(dr.get("saved_at")), dr)
    st, live = sa.req("/api/strategy")
    check("a draft NEVER changes the live strategy", live["strategy"]["market_position"] == "lead",
          live["strategy"]["market_position"])
    check("draft state surfaces on /api/strategy", (live.get("draft") or {}).get("step") == 3, live.get("draft"))
    st, _ = sa.req("/api/strategy", "PUT", {"strategy": REQ})
    st, live2 = sa.req("/api/strategy")
    check("saving clears the draft", live2.get("draft") is None, live2.get("draft"))

    # role split, proven on the demo org WITHOUT changing its stored strategy
    cc = login("analyst@thornbridge.example", "lumi-data-2026")
    st, _ = cc.req("/api/strategy/draft", "PUT", {"draft": {"step": 1}})
    check("Contributor CAN save a draft (200)", st == 200, st)
    st, _ = cc.req("/api/strategy/approve", "POST", {"confirmed": True, "approver_body": "CEO"})
    check("Contributor CANNOT approve (403)", st == 403, st)
    cc.req("/api/strategy/draft", "DELETE")                      # leave the demo org as found
    st, _ = login("ceo@thornbridge.example", "lumi-view-2026").req("/api/strategy/draft", "PUT", {"draft": {}})
    check("Viewer still blocked from drafting (403)", st == 403, st)

    # submit -> approve, as two acts INSIDE one org (the probe)
    st, sub = sa.req("/api/strategy/submit", "POST", {})
    check("send-for-approval records who and when (200)", st == 200 and bool(sub.get("submitted_at")), st)
    st, full6 = sa.req("/api/strategy")
    check("submission is visible to the approver", bool((full6.get("submitted") or {}).get("by")), full6.get("submitted"))
    check("can_edit/can_approve split exposed", full6.get("can_edit") is True and full6.get("can_approve") is True)

    # approval is a recorded act, not a click
    st, _ = sa.req("/api/strategy/approve", "POST", {"approver_body": "Remuneration Committee"})
    check("approval without confirmation rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy/approve", "POST", {"confirmed": True})
    check("approval without an approving body rejected (400)", st == 400, st)
    st, _ = sa.req("/api/strategy/approve", "POST", {"confirmed": True, "approver_body": "RemCo",
                                                    "approval_date": "12-03-2026"})
    check("malformed approval date rejected (400)", st == 400, st)
    st, ap = sa.req("/api/strategy/approve", "POST", {"confirmed": True, "approver_body": "Remuneration Committee",
                                                     "approval_date": "2026-03-12", "effective_date": "2026-04-01",
                                                     "next_review": "2027-03-01"})
    check("approval records the governing body (200)", st == 200 and ap.get("version") == 1, ap)
    check("approval records what was unstated", isinstance(ap.get("unstated"), list) and len(ap["unstated"]) > 0, ap.get("unstated"))
    st, vs = sa.req("/api/strategy/versions")
    _v1 = (vs.get("versions") or [{}])[0]
    check("version carries body, dates and the drafter",
          _v1.get("approver_body") == "Remuneration Committee" and _v1.get("effective_date") == "2026-04-01"
          and bool(_v1.get("submitted_by")), _v1)
    st, v1 = sa.req("/api/strategy/versions/1")
    check("a version snapshot is retrievable", st == 200 and bool((v1.get("snapshot") or {}).get("strategy")), st)
    st, full7 = sa.req("/api/strategy")
    check("approval consumes the submission", full7.get("submitted") is None, full7.get("submitted"))

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

    # ---- narrative overrides: prose only, never a computed figure -------------
    st_n, _ = sa.req("/api/strategy/narrative", "PUT", {"key": "exec_summary", "text": "Board-approved wording."})
    check("an author can replace a section's generated prose", st_n == 200, st_n)
    st_n2, got = sa.req("/api/strategy")
    check("the override comes back on the document",
          (got.get("document") or {}).get("narrative_overrides", {}).get("exec_summary") == "Board-approved wording.",
          (got.get("document") or {}).get("narrative_overrides"))
    st_n3, _ = sa.req("/api/strategy/narrative", "PUT", {"key": "exec_summary", "text": ""})
    st_n4, got2 = sa.req("/api/strategy")
    check("clearing an override restores lumi's wording",
          st_n3 == 200 and "exec_summary" not in ((got2.get("document") or {}).get("narrative_overrides") or {}))
    # the closed list is the safety property: a computed figure must never be writable
    for bad in ("position", "gaps", "counts", "roi", "domains", "commitments"):
        stb, _ = sa.req("/api/strategy/narrative", "PUT", {"key": bad, "text": "made up"})
        check("computed section '%s' is NOT author-writable" % bad, stb == 400, stb)
    # per-domain commentary keys — the report's main sections (2026-08-16)
    st_d, _ = sa.req("/api/strategy/narrative", "PUT", {"key": "domain:Pay", "text": "Board wording for Pay."})
    check("a domain's commentary is author-writable", st_d == 200, st_d)
    st_bad, _ = sa.req("/api/strategy/narrative", "PUT", {"key": "domain:Not A Category", "text": "x"})
    check("an unknown category is refused, not stored", st_bad == 400, st_bad)
    sa.req("/api/strategy/narrative", "PUT", {"key": "domain:Pay", "text": ""})

    st_long, _ = sa.req("/api/strategy/narrative", "PUT", {"key": "watch", "text": "x" * 5000})
    check("an over-long section is refused, not truncated", st_long == 400, st_long)

    # ---- board-paper sections (2026-08-16) -------------------------------------
    # The ask, the cost envelope, the schedule, the risk read and the not-taken
    # record. All five are prose over computed figures, so all five are editable and
    # none of the figures underneath them is.
    for k in ("the_ask", "cost", "risks", "schedule", "decisions", "movement"):
        stk, _ = sa.req("/api/strategy/narrative", "PUT", {"key": k, "text": "Board wording."})
        check("board-paper section '%s' is author-writable" % k, stk == 200, stk)
        sa.req("/api/strategy/narrative", "PUT", {"key": k, "text": ""})

    st_al, alp = sa.req("/api/strategy/alignment")
    if alp.get("ok") is False:
        print("  (this probe org has no completed strategy — board-paper payload checks skipped)")
        alp = {}
    check("the alignment payload carries the cost envelope",
          isinstance(alp.get("money"), dict)
          and "investment_to_p50_gbp" in alp["money"] and "gaps_total" in alp["money"],
          sorted((alp.get("money") or {}).keys()))
    # the envelope is only as wide as what lumi can price, and it has to admit that
    check("the envelope reports how many gaps it actually prices",
          isinstance((alp.get("money") or {}).get("priced"), int)
          and (alp["money"]["priced"] <= alp["money"]["gaps_total"]),
          (alp.get("money") or {}).get("priced"))
    check("the payload carries the ask, with a decision named",
          isinstance(alp.get("the_ask"), dict) and (alp["the_ask"].get("decision") or "").strip(),
          alp.get("the_ask"))
    check("the ask's £ is the same figure as the envelope's (one number, one source)",
          (alp.get("the_ask") or {}).get("investment_to_p50_gbp")
          == (alp.get("money") or {}).get("investment_to_p50_gbp"))
    check("the payload carries a risk list", isinstance(alp.get("risks"), list))
    check("trend states whether it is computable rather than implying movement",
          isinstance(alp.get("trend"), dict) and "available" in alp["trend"]
          and isinstance(alp["trend"].get("windows"), int), alp.get("trend"))
    check("the schedule buckets every planned action, dropping none",
          sum(len(s["actions"]) for s in (alp.get("schedule") or []))
          == len(((alp.get("plan") or {}) or {}).get("actions") or []),
          [(s["horizon"], len(s["actions"])) for s in (alp.get("schedule") or [])])
    check("every scheduled horizon is one of the known buckets",
          all(s["horizon"] in ("this cycle", "next cycle", "multi-cycle", "unscheduled")
              for s in (alp.get("schedule") or [])),
          [s["horizon"] for s in (alp.get("schedule") or [])])

    # ---- option decisions: the record of what was turned down -------------------
    _cat, _lev = None, None
    for b in (alp.get("domain_blocks") or []):
        for o in (b.get("options") or []):
            for l in (o.get("levers") or []):
                if _lev is None:
                    _cat, _lev = b["name"], l["lever_id"]
    if _lev is None:
        # a probe org with no submitted data is offered no levers. The decision RECORD is
        # what these checks are for, and it does not require the lever to exist — the
        # inventory hot-reloads, so the endpoint deliberately does not validate against it.
        _cat, _lev = "Pay", "QA-SYNTHETIC-LEVER"
    if _lev:
        st_od, od = sa.req("/api/strategy/option-decision", "PUT",
                           {"category": _cat, "lever_id": _lev, "state": "rejected",
                            "reason": "Already covered by an existing scheme."})
        check("an option decision can be recorded", st_od == 200, st_od)
        _k = "%s|%s" % (_cat, _lev)
        check("the decision is keyed by category AND lever",
              _k in (od.get("option_decisions") or {}), sorted((od.get("option_decisions") or {})))
        check("the decision stores who and when, not just what",
              (od["option_decisions"][_k].get("at") or "") and (od["option_decisions"][_k].get("by") or ""),
              od["option_decisions"][_k])
        _st2, al2 = sa.req("/api/strategy/alignment")
        check("the decision comes back on the document payload",
              _k in (al2.get("option_decisions") or {}))
        st_bs, _ = sa.req("/api/strategy/option-decision", "PUT",
                          {"category": _cat, "lever_id": _lev, "state": "maybe"})
        check("an unknown decision state is refused, not coerced", st_bs == 400, st_bs)
        st_ni, _ = sa.req("/api/strategy/option-decision", "PUT", {"state": "rejected"})
        check("a decision without a category or lever is refused", st_ni == 400, st_ni)
        st_lr, _ = sa.req("/api/strategy/option-decision", "PUT",
                          {"category": _cat, "lever_id": _lev, "state": "rejected", "reason": "z" * 500})
        check("an over-long reason is refused, not truncated", st_lr == 400, st_lr)
        st_cl, cl = sa.req("/api/strategy/option-decision", "PUT",
                           {"category": _cat, "lever_id": _lev, "state": ""})
        check("clearing a decision removes the record entirely (no hollow row)",
              st_cl == 200 and _k not in (cl.get("option_decisions") or {}),
              cl.get("option_decisions"))

    # ---- the approval modal must warn about the SAME sections the version records ----
    # Between 2026-08-15 and 2026-08-16 the client list still counted Governance,
    # Commitments, Measures and Roadmap — all retired from capture — so every
    # approval warned about four sections nobody could ever state, while the stored
    # version recorded the correct five. Two hand-maintained lists in two languages
    # drift silently; this pins them together.
    import re as _re
    _js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "js", "strategy.js")
    try:
        _src = open(_js).read()
        _blk = _src[_src.index("const unstated = ["):]
        _blk = _blk[:_blk.index("].filter(")]
        _client = set(_re.findall(r'\["([^"]+)",', _blk))
    except Exception as e:                                   # noqa: BLE001 — a read failure IS the finding
        _client = set()
        print("  (could not parse the client unstated list: %s)" % e)
    # read the server side from SOURCE too — importing app.py here would open the live
    # DB, which get_conn refuses under a bare qa_ run (gate-safety-1).
    _py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    _psrc = open(_py).read()
    _pblk = _psrc[_psrc.index("def _unstated_sections("):]
    _pblk = _pblk[:_pblk.index("return [name for name")]
    _server = set(_re.findall(r'\("([^"]+)",', _pblk))
    check("approval modal warns about exactly the sections the version records",
          bool(_server) and _client == _server,
          "client=%s server=%s" % (sorted(_client), sorted(_server)))

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
        conn.execute("DELETE FROM strategy_versions WHERE org_id=?", (oid,))
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
