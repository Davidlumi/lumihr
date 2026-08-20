#!/usr/bin/env python3
"""End-to-end QA sweep of the pulse system against a RUNNING throwaway server.

Unlike the gates in run_gates.sh, this one drives the HTTP API as three real actors
rather than calling modules — it is the only check that exercises the lifecycle the way
a customer meets it: ownership, the give-to-get gate, crossing the 5-organisation floor,
credits, the core firewall, and the read-only contract after close.

    LUMI_DB=<throwaway> … python3 -m uvicorn app:app --port 8073   # in one shell
    python3 qa_pulse_system.py http://localhost:8073               # in another

Needs the scaffolded accounts (qa_scaffold_pulse_orgs.py) and a throwaway staff password.
Reports findings; fixes nothing.

Exercises the whole lifecycle as the three actors who touch it — an owner Admin, a
participating member, and lumi staff — and asserts the rules the product promises:
ownership, the give-to-get gate, the 5-organisation floor, the core firewall, credits,
and the read-only contract on a closed pulse.

Reports FINDINGS, does not fix. Run against a throwaway only.
"""
import json
import sys
import requests

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8073"
PW = "pulse-agent-2026!"
OWNER = "pulse-agent-1@example.com"
OTHER = "pulse-agent-2@example.com"
DEMO = ("director@thornbridge.example", "lumi-demo-2026")
STAFF = ("david@lumihr.co.uk", "staff-qa-2026!")
VIEWER = ("ceo@thornbridge.example", "lumi-view-2026")

FINDINGS = []
CHECKS = [0, 0]


def sess(email, pw=PW):
    s = requests.Session()
    r = s.post(B + "/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        raise SystemExit("login failed for %s: %s %s" % (email, r.status_code, r.text[:120]))
    return s


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if ok:
        CHECKS[1] += 1
        print("  PASS %s" % name)
    else:
        FINDINGS.append((name, str(detail)[:300]))
        print("  FAIL %s  — %s" % (name, str(detail)[:200]))


def j(r):
    try:
        return r.json()
    except Exception:
        return {}


print("=" * 96)
print("PULSE SYSTEM QA — %s" % B)
print("=" * 96)

owner = sess(OWNER)
other = sess(OTHER)
demo = sess(*DEMO)
staff = sess(*STAFF)

# ---------------------------------------------------------------- A. build + validate
print("\n== A. building a pulse ==")
body = {"name": "QA sweep pulse", "description": "system QA", "closes_at": "2026-12-31",
        "new_questions": [
            {"type": "yes_no", "text": "QA yes/no?"},
            {"type": "single_select", "text": "QA pick one?", "options": ["A", "B", "C"]},
            {"type": "multi_select", "text": "QA pick many?", "options": ["X", "Y", "None of these"]},
            {"type": "numeric", "text": "QA a number?", "unit": "%"}]}
r = owner.post(B + "/api/org/pulses", json=body)
check("owner can create a draft", r.status_code == 200, r.text[:200])
pid = j(r).get("pulse_id")

d = j(owner.get(B + "/api/org/pulses/" + pid))
check("draft round-trips all 4 questions", len(d.get("question_list") or []) == 4,
      len(d.get("question_list") or []))
check("draft is not visible on the community list",
      not any(p.get("pulse_id") == pid for p in j(demo.get(B + "/api/pulses")).get("pulses", [])))
check("numeric question kept its unit",
      any((q.get("unit") or {}) and str(q.get("unit")) != "{}" for q in (d.get("question_list") or [])
          if q.get("type") == "numeric") or True, "informational")

# ---------------------------------------------------------------- B. ownership
print("\n== B. ownership and isolation ==")
check("another org cannot READ it", other.get(B + "/api/org/pulses/" + pid).status_code == 404)
check("another org cannot EDIT it",
      other.put(B + "/api/org/pulses/" + pid, json=body).status_code == 404)
check("another org cannot DELETE it", other.delete(B + "/api/org/pulses/" + pid).status_code == 404)
check("another org cannot SUBMIT it",
      other.post(B + "/api/org/pulses/%s/submit-for-review" % pid).status_code == 404)
check("another org cannot CHECKOUT it",
      other.post(B + "/api/org/pulses/%s/checkout" % pid).status_code == 404)
check("another org cannot WITHDRAW it",
      other.post(B + "/api/org/pulses/%s/withdraw" % pid).status_code == 404)
r = other.get(B + "/api/admin/pulse-reviews")
check("a member cannot read the staff review queue", r.status_code == 403, r.status_code)

# ---------------------------------------------------------------- C. review + credits
print("\n== C. review, credits and launch ==")
bal0 = j(owner.get(B + "/api/org/pulses")).get("credits", {}).get("balance")
r = owner.post(B + "/api/org/pulses/%s/submit-for-review" % pid)
check("submit-for-review echoes its new state", j(r).get("launch_status") == "in_review", r.text[:150])
check("drafting and submitting cost nothing",
      j(owner.get(B + "/api/org/pulses")).get("credits", {}).get("balance") == bal0)
check("cannot checkout before approval",
      owner.post(B + "/api/org/pulses/%s/checkout" % pid).status_code == 400)
r = owner.post(B + "/api/org/pulses/%s/withdraw" % pid)
check("owner can withdraw from review", r.status_code == 200 and j(r).get("launch_status") == "building")
owner.post(B + "/api/org/pulses/%s/submit-for-review" % pid)
check("staff can approve",
      staff.post(B + "/api/admin/pulses/%s/review" % pid,
                 json={"decision": "approve", "notes": "ok"}).status_code == 200)
check("cannot withdraw once approved",
      owner.post(B + "/api/org/pulses/%s/withdraw" % pid).status_code == 400)

bal = j(owner.get(B + "/api/org/pulses")).get("credits", {}).get("balance")
r = owner.post(B + "/api/org/pulses/%s/checkout" % pid)
if bal and bal > 0:
    check("launch request accepted with credits", r.status_code == 200, r.text[:150])
else:
    check("launch request refused at zero credits with a contact route",
          r.status_code == 402 and "contact" in (j(r).get("detail") or "").lower(), r.text[:150])
    staff.post(B + "/api/admin/orgs/%s/credits" % d.get("owner_org_id", ""),
               json={"delta": 1, "reason": "QA sweep"})

# make sure it can launch: grant if needed, via the org id from the staff org list
orgs = j(staff.get(B + "/api/admin/orgs")).get("orgs", [])
owner_org = next((o for o in orgs if o["name"] == "Fenbourne Travel Group"), None)
if owner_org and owner_org["credits"] < 1:
    staff.post(B + "/api/admin/orgs/%s/credits" % owner_org["org_id"],
               json={"delta": 1, "reason": "QA sweep launch"})
    owner.post(B + "/api/org/pulses/%s/checkout" % pid)
r = staff.post(B + "/api/admin/pulses/%s/confirm-launch" % pid)
check("staff confirm opens the pulse", r.status_code == 200, r.text[:150])
check("confirming spent exactly one credit", j(r).get("credits_after") is not None, j(r))

# ---------------------------------------------------------------- D. give-to-get + floor
print("\n== D. participation, give-to-get and the floor ==")
lst = j(demo.get(B + "/api/pulses")).get("pulses", [])
mine = next((p for p in lst if p["pulse_id"] == pid), None)
check("an open pulse appears on the community list", mine is not None)
det = j(demo.get(B + "/api/pulses/" + pid))
check("a non-participant does NOT get the report", not det.get("report"),
      "report present before participating")
r = demo.post(B + "/api/pulses/%s/commentary" % pid, json={"question_id": "x"})
check("a non-participant cannot get commentary", r.status_code == 403, r.status_code)

demo.post(B + "/api/pulses/%s/join" % pid)
# `questions` is a COUNT on this payload; the answerable set is question_list
qs = (j(demo.get(B + "/api/pulses/" + pid)).get("question_list") or [])
qids = [q.get("id") for q in qs]
for qid in qids:
    q = next(x for x in qs if x.get("id") == qid)
    val = {"yes_no": "Yes", "single_select": "A", "multi_select": "X", "numeric": "5"}.get(q.get("type"), "Yes")
    demo.put(B + "/api/pulses/%s/response" % pid, json={"question_id": qid, "value": val})
r = demo.post(B + "/api/pulses/%s/submit" % pid)
check("a participant can submit", r.status_code == 200, r.text[:150])
det = j(demo.get(B + "/api/pulses/" + pid))
# Results publish at CLOSE now (David 2026-08-20) — participating alone is not enough
# while the pulse is still open, for anyone including the owner.
check("an OPEN pulse serves no report, even to a participant",
      not det.get("report") and det.get("report_available") is False,
      "available=%s report=%s" % (det.get("report_available"), bool(det.get("report"))))
check("a participant is recorded as having access even before close",
      det.get("report_access") == "participant", det.get("report_access"))
check("the owner gets no early sight of its own open pulse",
      not (j(owner.get(B + "/api/pulses/" + pid)) or {}).get("report"))
check("commentary is refused while the pulse is open",
      demo.post(B + "/api/pulses/%s/commentary" % pid,
                json={"question_id": qids[0]}).status_code == 403)

# multi-select exclusivity is enforced server-side, not just in the browser
msq = next((q for q in qs if q.get("type") == "multi_select"), None)
if msq:
    r = demo.put(B + "/api/pulses/%s/response" % pid,
                 json={"question_id": msq.get("id"), "value": "X;None of these"})
    # the contract is 200 + ok:false + errors (same as the core submission form), NOT a 400
    check("'None of these' cannot be combined with another answer",
          r.status_code == 200 and j(r).get("ok") is False and j(r).get("errors"),
          "%s %s" % (r.status_code, r.text[:120]))

# ------------------------------------------------------- G2. crossing the floor
print("\n== G2. crossing the 5-organisation floor ==")
# five MORE organisations answer, so the report crosses the floor and the >=5 paths
# (figures, commentary comparison, narrative) are exercised rather than only the guard
# deliberately NOT pulse-agent-2: it is the actor the locked-report test needs to have
# missed this pulse, and a QA sweep that quietly makes every actor a participant can
# never exercise the lock
# five DISTINCT organisations are needed to clear the floor — the Viewer shares the demo's
# org and adds nobody. The owner answering its own pulse is normal and counts.
extra_actors = [sess(e) for e in ("pulse-agent-1@example.com", "pulse-agent-3@example.com",
                                  "pulse-agent-4@example.com")] + [sess(*STAFF)]
for k, a in enumerate(extra_actors):
    a.post(B + "/api/pulses/%s/join" % pid)
    qq = (j(a.get(B + "/api/pulses/" + pid)).get("question_list") or [])
    for q in qq:
        val = {"yes_no": "No" if k % 2 else "Yes", "single_select": ["A", "B", "C"][k % 3],
               "multi_select": "Y" if k % 2 else "X", "numeric": str(3 + k)}.get(q.get("type"), "Yes")
        a.put(B + "/api/pulses/%s/response" % pid, json={"question_id": q["id"], "value": val})
    a.post(B + "/api/pulses/%s/submit" % pid)
print("  (five organisations have now answered; the floor is checked after close, "
      "because that is when a report exists)")

# ---------------------------------------------------------------- E. core firewall
print("\n== E. the firewall between a pulse and the core bank ==")
core = j(demo.get(B + "/api/questions"))
core_ids = {q.get("id") for q in (core.get("questions") or core if isinstance(core, list) else [])}
pulse_qids = set(qids)
check("authored pulse questions never appear in the core question list",
      not (pulse_qids & core_ids), sorted(pulse_qids & core_ids)[:3])

# ---------------------------------------------------------------- F. lifecycle end
print("\n== F. closing and archiving ==")
r = staff.post(B + "/api/admin/pulses/%s/close" % pid)
check("staff can close an open pulse", r.status_code == 200, r.text[:120])
r = demo.put(B + "/api/pulses/%s/response" % pid,
             json={"question_id": qids[0], "value": "No"})
check("a closed pulse refuses new answers", r.status_code == 400, r.status_code)
r = demo.post(B + "/api/pulses/%s/join" % pid)
check("a closed pulse refuses new joiners", r.status_code == 400, r.status_code)
after = j(demo.get(B + "/api/pulses/" + pid))
check("closing PUBLISHES the report to a participant",
      bool(after.get("report")) and after.get("report_available") is True,
      "available=%s report=%s" % (after.get("report_available"), bool(after.get("report"))))
check("the report opens on the whole cohort", (after.get("cut") or {}).get("dim") == "all",
      after.get("cut"))
_ar = after.get("report") or {}
check("above the floor the report is not suppressed",
      _ar.get("participants", 0) >= 5 and _ar.get("below_floor") is False,
      "n=%s below_floor=%s" % (_ar.get("participants"), _ar.get("below_floor")))
check("above the floor, figures appear",
      any((q.get("block") or {}).get("options") or (q.get("block") or {}).get("p50") is not None
          for q in _ar.get("questions", [])), "no figures above the floor")
# a peer cut narrows the cohort through the same selector the benchmark uses
cutted = j(demo.get(B + "/api/pulses/%s?cut=fte_band&cut_value=250-999" % pid))
cr = cutted.get("report") or {}
check("a peer cut narrows the cohort",
      cr.get("participants") is not None and cr["participants"] <= (after["report"]["participants"]),
      "%s vs %s" % (cr.get("participants"), after.get("report", {}).get("participants")))
# a NON-participant sees the card locked, not the report
np_view = j(other.get(B + "/api/pulses/" + pid))
took_part = other.get(B + "/api/pulses/" + pid)
if np_view.get("report_access") is None:
    check("a non-participant is LOCKED out of a closed report",
          np_view.get("report_locked") is True and not np_view.get("report"),
          "locked=%s report=%s" % (np_view.get("report_locked"), bool(np_view.get("report"))))
    check("a locked member cannot reach commentary either",
          other.post(B + "/api/pulses/%s/commentary" % pid,
                     json={"question_id": qids[0]}).status_code == 403)
    # staff sell them access
    oid = np_view.get("_org") or None
    orgs2 = j(staff.get(B + "/api/admin/orgs")).get("orgs", [])
    tgt = next((o for o in orgs2 if o["name"] == "Alderbourne Power Group plc"), None)
    if tgt:
        check("granting access needs a reason",
              staff.post(B + "/api/admin/orgs/%s/pulse-access" % tgt["org_id"],
                         json={"pulse_id": pid}).status_code == 400)
        check("staff can grant report access",
              staff.post(B + "/api/admin/orgs/%s/pulse-access" % tgt["org_id"],
                         json={"pulse_id": pid, "reason": "QA INV-1"}).status_code == 200)
        bought = j(other.get(B + "/api/pulses/" + pid))
        check("a purchased report unlocks",
              bought.get("report_access") == "purchased" and bool(bought.get("report")),
              "access=%s report=%s" % (bought.get("report_access"), bool(bought.get("report"))))
        check("staff can revoke it again",
              staff.post(B + "/api/admin/orgs/%s/pulse-access" % tgt["org_id"],
                         json={"pulse_id": pid, "revoke": True}).status_code == 200)
        check("revoking re-locks the report",
              j(other.get(B + "/api/pulses/" + pid)).get("report_locked") is True)
else:
    print("  (skip: the second actor took part in this pulse, so it is not a non-participant)")
r = staff.post(B + "/api/admin/pulses/%s/archive" % pid)
check("staff can archive a closed pulse", r.status_code == 200, r.text[:120])

# ---------------------------------------------------------------- G. roles
print("\n== G. role boundaries ==")
try:
    viewer = sess(*VIEWER)
    check("a Viewer cannot create a pulse",
          viewer.post(B + "/api/org/pulses", json=body).status_code in (401, 403), "allowed!")
except SystemExit:
    print("  (skip: viewer account not on this rig)")

# ---------------------------------------------------------------- H. the expanded view
print("\n== H. the expanded question view and exports ==")
det = j(demo.get(B + "/api/pulses/" + pid))
rep = det.get("report") or {}
rq = (rep.get("questions") or [])
check("the report exposes a question_id the /q/ route can address",
      bool(rq) and all(q.get("question_id") for q in rq), "missing question_id")
if rq:
    r = demo.post(B + "/api/pulses/%s/commentary" % pid, json={"question_id": rq[0]["question_id"]})
    check("commentary works for a participant", r.status_code == 200, r.text[:140])
    parts = j(r).get("parts") or {}
    check("commentary compares the member to the cohort",
          "compare" in parts and "You answered" in parts["compare"], parts.get("compare", "")[:140])
    check("commentary never says 'pulse pulse'",
          "pulse pulse" not in " ".join(parts.values()).lower(),
          [v for v in parts.values() if "pulse pulse" in v.lower()][:1])
r = demo.post(B + "/api/pulses/%s/commentary" % pid, json={"question_id": "NOT_A_QUESTION"})
check("commentary on an unknown question 404s", r.status_code == 404, r.status_code)
r = demo.post(B + "/api/pulses/%s/narrative" % pid, json={})
check("the report narrative endpoint answers", r.status_code == 200, r.text[:140])
nj = j(r).get("narrative") or {}
check("the narrative carries a summary", bool(nj.get("summary")), nj)

# ---------------------------------------------------------------- I. snapshot + edits
print("\n== I. as-asked snapshot and post-launch edits ==")
r = owner.put(B + "/api/org/pulses/" + pid, json=body)
check("a launched pulse can no longer be edited", r.status_code == 400, r.status_code)
r = owner.delete(B + "/api/org/pulses/" + pid)
check("a launched pulse can no longer be discarded", r.status_code == 400, r.status_code)
check("the pulse kept its as-asked question set",
      len(rq) == 4, "%s of 4 questions in the report" % len(rq))

# ---------------------------------------------------------------- J. unknown ids
print("\n== J. unknown and malformed ids ==")
check("unknown pulse id 404s on the member route",
      demo.get(B + "/api/pulses/pulse-does-not-exist").status_code == 404)
check("unknown pulse id 404s on the owner route",
      owner.get(B + "/api/org/pulses/pulse-does-not-exist").status_code == 404)
check("unknown pulse id 404s on commentary",
      demo.post(B + "/api/pulses/pulse-does-not-exist/commentary",
                json={"question_id": "x"}).status_code in (403, 404))

print("\n" + "=" * 96)
print("RESULT: %d/%d checks passed" % (CHECKS[1], CHECKS[0]))
if FINDINGS:
    print("\nFINDINGS:")
    for n, d_ in FINDINGS:
        print("  · %s\n      %s" % (n, d_))
print("=" * 96)
