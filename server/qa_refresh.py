# -*- coding: utf-8 -*-
"""Refresh-cadence gate: the metric refresh register + flagging engine + the
Your-data payload contract (built 2026-08-05 from the deep-QA of the system).

MUST run against a THROWAWAY: section C backdates answer timestamps for the
demo org and drives a draft+submit round-trip (values unchanged; original
submitted_at strings restored afterwards, history rows legitimately remain —
append-only telemetry). Refuses to start without LUMI_DB (gate-safety).

Sections:
  A  register <-> bank: exact coverage, sane months, override hygiene,
     regeneration idempotence (the JSON is generated, never hand-edited)
  B  engine (direct): class cutoffs both sides, matrix MIN semantics, NA row,
     provenance-tagged timestamps, zero-write property, hot-reload, malformed
     register keeps last good, unknown-question fallback
  C  HTTP contract on BASE: payload sums, sort order, viewer parity,
     section<->overview agreement, submit round-trip (flag clears, history
     appended, canonical timestamp), nudge-never-gates (completion identical)

Usage (run_gates.sh): LUMI_DB=... LUMI_IDENTITY_DB=... python3 qa_refresh.py
"""
import http.cookiejar
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("LUMI_QA_BASE", "http://localhost:8060")
DB = os.environ.get("LUMI_DB")
REGISTER = os.path.join(HERE, "..", "data", "metric_refresh_register.json")
ORG = "5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7"          # Thornbridge (demo org)
ADMIN = ("director@thornbridge.example", "lumi-demo-2026")
VIEWER = ("ceo@thornbridge.example", "lumi-view-2026")

if not DB:
    print("qa_refresh: REFUSING to run without LUMI_DB (section C rewrites answer "
          "timestamps for the demo org — throwaway only).")
    sys.exit(2)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  [" + str(detail)[:110] + "]") if detail else ""))


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def api(opener, path, method="GET", body=None):
    r = urllib.request.Request(BASE + path, method=method)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(r, data=data, timeout=120)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"_http_status": e.code}


def conn_rw():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


class QStub(object):
    def __init__(self, qid, category="practice", unit_type="none"):
        self.id, self.category, self.unit_type = qid, category, unit_type


# =============================================================== A. REGISTER ==
print("== A. register <-> bank ==")
reg = json.load(open(REGISTER))
conn = conn_rw()
active = {r["id"]: dict(r) for r in conn.execute(
    "SELECT id, category, unit_type FROM questions WHERE status='active'")}
m = reg["metrics"]
check("A1 register covers exactly the active bank",
      set(m) == set(active), "reg=%d bank=%d" % (len(m), len(active)))
check("A2 every cadence is 12/18/24 and matches its class name",
      all(v["months"] in (12, 18, 24) and
          v["class"] == {12: "annual", 18: "benefit", 24: "structural"}[v["months"]]
          for v in m.values()))
check("A3 class_counts add up and match the entries",
      sum(reg["class_counts"].values()) == len(m) and
      all(reg["class_counts"][c] == sum(1 for v in m.values() if v["class"] == c)
          for c in reg["class_counts"]))
ovs = {k: v for k, v in m.items() if "override_reason" in v}
check("A4 every override names an active question and a reason",
      len(ovs) > 0 and all(k in active and v["override_reason"].strip() for k, v in ovs.items()),
      "%d overrides" % len(ovs))
# A5: the JSON is generated — regenerating must be byte-identical (hand edits
# and bank drift both surface here)
tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
tmp.close()
try:
    r = subprocess.run([sys.executable, os.path.join(HERE, "gen_refresh_register.py"), tmp.name],
                       env=dict(os.environ, LUMI_DB=DB), capture_output=True, text=True)
    regen = json.load(open(tmp.name)) if r.returncode == 0 else None
    check("A5 register regenerates identically from the bank (no drift, no hand edits)",
          regen == reg, r.stderr.strip()[:80] if r.returncode else "")
finally:
    os.unlink(tmp.name)

# ================================================================ B. ENGINE ==
print("== B. engine (refresh_policy, direct) ==")
sys.path.insert(0, HERE)
import refresh_policy

now_minus = {}
for spec in ("-11 months", "-13 months", "-17 months", "-19 months", "-23 months", "-25 months"):
    now_minus[spec] = conn.execute("SELECT datetime('now', ?) c", (spec,)).fetchone()["c"]

MONTHS_OF = {12: ("-11 months", "-13 months"), 18: ("-17 months", "-19 months"),
             24: ("-23 months", "-25 months")}


def state_for(rows, questions):
    """Run refresh_state against a scratch table shaped like answers."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE answers (org_id TEXT, snapshot_id INT, question_id TEXT, "
              "matrix_row_id TEXT DEFAULT '', value TEXT, submitted_at TEXT)")
    c.executemany("INSERT INTO answers VALUES ('o', 1, ?, ?, 'v', ?)", rows)
    before = c.total_changes
    st = refresh_policy.refresh_state(c, "o", 1, questions)
    return st, c.total_changes - before


# B1/B2: both sides of every class cutoff (uses the REAL register via three
# representative metrics, one per class)
by_class = {v["class"]: k for k, v in sorted(m.items())}
for cls, months in (("annual", 12), ("benefit", 18), ("structural", 24)):
    qid = by_class[cls]
    q = QStub(qid, active[qid]["category"], active[qid]["unit_type"])
    inside, outside = MONTHS_OF[months]
    st, _ = state_for([(qid, "", now_minus[inside])], {qid: q})
    check("B1 %s: answer %s old is NOT due" % (cls, inside.strip("-")),
          st[qid]["due"] is False and st[qid]["months"] == months)
    st, _ = state_for([(qid, "", now_minus[outside])], {qid: q})
    check("B2 %s: answer %s old IS due" % (cls, outside.strip("-")),
          st[qid]["due"] is True)

# B3: matrix MIN semantics — one stale row flags the question; all-fresh clears
qid = by_class["annual"]
q = QStub(qid, "metric", "none")
st, _ = state_for([(qid, "r1", now_minus["-11 months"]),
                   (qid, "r2", now_minus["-13 months"])], {qid: q})
check("B3a matrix: one stale row makes the question due", st[qid]["due"] is True)
st, _ = state_for([(qid, "r1", now_minus["-11 months"]),
                   (qid, "r2", now_minus["-11 months"])], {qid: q})
check("B3b matrix: all rows fresh clears it", st[qid]["due"] is False)
st, _ = state_for([(qid, "", now_minus["-13 months"]),
                   (qid, "r1", now_minus["-11 months"])], {qid: q})
check("B3c matrix: an aged question-level NA row ('') counts", st[qid]["due"] is True)

# B4: unanswered / invisible questions never appear
st, _ = state_for([(qid, "", now_minus["-13 months"])], {})
check("B4 a question outside the visible set is absent from the state", st == {})

# B5: provenance-tagged timestamps ("YYYY-MM-DD <tag>", written by past regens)
# still order correctly by their date prefix
old_tag = conn.execute("SELECT date('now', '-14 months') c").fetchone()["c"] + " diff15"
new_tag = conn.execute("SELECT date('now', '-1 months') c").fetchone()["c"] + " r3sw5 pre-audit bundle"
st, _ = state_for([(qid, "", old_tag)], {qid: q})
check("B5a provenance-tagged OLD timestamp reads as due", st[qid]["due"] is True)
st, _ = state_for([(qid, "", new_tag)], {qid: q})
check("B5b provenance-tagged FRESH timestamp reads as not due", st[qid]["due"] is False)

# B6: computing state writes nothing
st, writes = state_for([(qid, "", now_minus["-13 months"])], {qid: q})
check("B6 refresh_state performs zero writes", writes == 0)

# B7: unknown question (not in register) falls back to the class rules —
# and the fallback agrees with the generator's rules for every active question
check("B7a fallback: unregistered metric-category question -> 12",
      refresh_policy.months_for(QStub("GHOST_Q1", "metric", "none")) == 12)
check("B7b fallback: unregistered practice question -> 24",
      refresh_policy.months_for(QStub("GHOST_Q2", "practice", "none")) == 24)
check("B7c fallback: weeks unit no longer counts as quantitative",
      refresh_policy.months_for(QStub("GHOST_Q3", "benefit", "weeks")) == 18)

# B8: register hot-reload + malformed-file fail-safe (against a scratch copy)
scratch = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
scratch.close()
shutil.copyfile(REGISTER, scratch.name)
orig_path, orig_cache = refresh_policy.REGISTER_PATH, dict(refresh_policy._cache)
try:
    refresh_policy.REGISTER_PATH = scratch.name
    refresh_policy._cache.update({"mtime": None, "months": {}, "classes": {}})
    qid12 = by_class["annual"]
    got = refresh_policy.months_for(QStub(qid12, "practice", "none"))  # register says 12
    check("B8a scratch register loads (register value beats the class rule)", got == 12)
    doc = json.load(open(scratch.name))
    doc["metrics"][qid12]["months"] = 18
    json.dump(doc, open(scratch.name, "w"))
    os.utime(scratch.name, None)
    check("B8b an edit hot-reloads on mtime change",
          refresh_policy.months_for(QStub(qid12, "practice", "none")) == 18)
    open(scratch.name, "w").write("{not json")
    os.utime(scratch.name, None)
    check("B8c a malformed register keeps the last good copy",
          refresh_policy.months_for(QStub(qid12, "practice", "none")) == 18)
finally:
    refresh_policy.REGISTER_PATH = orig_path
    refresh_policy._cache.clear()
    refresh_policy._cache.update(orig_cache)
    os.unlink(scratch.name)

# ========================================================== C. HTTP CONTRACT ==
print("== C. HTTP contract on %s ==" % BASE)
adm = client()
s, _ = api(adm, "/api/auth/login", "POST", {"email": ADMIN[0], "password": ADMIN[1]})
check("C0 demo admin signs in", s == 200)

# canary (qa_backoffice convention): the server must be reading THIS throwaway —
# refuse to mutate anything if not
canary = conn.execute("SELECT COUNT(*) c FROM answers WHERE org_id=?", (ORG,)).fetchone()["c"]
s, d = api(adm, "/api/data-overview")
srv_answered = d.get("answered") if s == 200 else None
if not (s == 200 and canary > 0):
    print("FATAL: canary failed (status=%s, db answers=%s) — server/DB pairing wrong; aborting before any write." % (s, canary))
    sys.exit(2)

# The round-trip (C10-C12) needs a SUBMITTABLE org, so two known obstructions
# are neutralised on this THROWAWAY first — before the baseline, so fixture
# candidates and expectations can never include a neutralised question:
#  * leftover stored drafts would ride along with our submit and change values
#    — deleted (drafts are volatile client state);
#  * stored answers that fail CURRENT validation block every submit (the
#    PAYCOMMS type-drift defect, DECISIONS 2026-08-05, ruling pending) — those
#    rows are deleted here. When that defect is fixed for real, this is a no-op.
n_drafts = conn.execute("SELECT COUNT(*) c FROM drafts WHERE org_id=?", (ORG,)).fetchone()["c"]
conn.execute("DELETE FROM drafts WHERE org_id=?", (ORG,))
conn.commit()
s, dv = api(adm, "/api/submission/validate", "POST")
bad_qids = {p["question_id"] for p in (dv.get("problems") or [])}
for bq in bad_qids:
    conn.execute("DELETE FROM answers WHERE org_id=? AND snapshot_id=1 AND question_id=?",
                 (ORG, bq))
conn.commit()
if n_drafts or bad_qids:
    print("  NOTE neutralised on throwaway: %d leftover drafts, %d validation-blocked "
          "answers (%s)" % (n_drafts, len(bad_qids), ", ".join(sorted(bad_qids)) or "-"))
check("C0b org is submittable once known obstructions are neutralised",
      not api(adm, "/api/submission/validate", "POST")[1].get("problems"))
s, d = api(adm, "/api/data-overview")

# baseline BEFORE the fixture. CLOCK-SAFE BY DESIGN: as the world ages, seed
# answers will genuinely come due (annual metrics from mid-2027) — so the gate
# captures whatever is due pristinely and asserts the fixture's DELTA, never
# an absolute zero.
base_answered, base_pct = d["answered"], d["pct"]
pristine_due = {q["question_id"] for dom in d["domains"] for q in dom["questions"]
                if q["needs_refresh"]}
check("C1 pristine baseline captured (informational)", True,
      "%d already due" % len(pristine_due))

# fixture: one due metric per class + one fresh control, originals recorded;
# candidates exclude anything already due so the delta is exact
picked, originals = {}, {}
for cls, months in (("annual", 12), ("benefit", 18), ("structural", 24)):
    cands = [k for k, v in sorted(m.items()) if v["class"] == cls and k not in pristine_due]
    got = [r["question_id"] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answers WHERE org_id=? AND snapshot_id=1 "
        "AND question_id IN (%s)" % ",".join("?" * len(cands)), [ORG] + cands)]
    picked[cls] = got[:2]                      # [0] -> due, [1] -> fresh control
    inside, outside = MONTHS_OF[months]
    for qid, spec in zip(picked[cls], (outside, inside)):
        for r in conn.execute("SELECT matrix_row_id, submitted_at FROM answers "
                              "WHERE org_id=? AND snapshot_id=1 AND question_id=?", (ORG, qid)):
            originals[(qid, r["matrix_row_id"])] = r["submitted_at"]
        conn.execute("UPDATE answers SET submitted_at=? WHERE org_id=? AND snapshot_id=1 "
                     "AND question_id=?", (now_minus[spec], ORG, qid))
conn.commit()
due_expect = {picked[c][0] for c in picked}

try:
    s, d = api(adm, "/api/data-overview")
    flags = {q["question_id"]: q for dom in d["domains"] for q in dom["questions"]}
    got_due = {k for k, v in flags.items() if v["needs_refresh"]}
    want = pristine_due | due_expect
    check("C2 flags are exactly pristine-due + the fixture (controls clean)",
          got_due == want, "extra=%s missing=%s" % (got_due - want, want - got_due))
    check("C3 top-level to_refresh == sum of domains == flag count",
          d["to_refresh"] == sum(x["to_refresh"] for x in d["domains"]) == len(got_due))
    check("C4 staleness never touches completion (nudge, not a gate)",
          d["answered"] == base_answered and d["pct"] == base_pct)
    check("C5 unanswered questions are never due",
          all(v["needs_refresh"] is False for v in flags.values() if not v["answered"]))
    check("C6 every flagged question carries last_updated + refresh_months",
          all(flags[k]["last_updated"] and flags[k]["refresh_months"] in (12, 18, 24) for k in got_due))
    for dom in d["domains"]:
        ans = [q for q in dom["questions"] if q["answered"]]
        first_fresh = next((i for i, q in enumerate(ans) if not q["needs_refresh"]), len(ans))
        check("C7 %s: due questions sort before fresh answered" % dom["name"],
              all(q["needs_refresh"] for q in ans[:first_fresh]) and
              not any(q["needs_refresh"] for q in ans[first_fresh:]))

    # section endpoint agreement (the editor page's source)
    a_due = picked["annual"][0]
    sec = next(dom["name"] for dom in d["domains"]
               for q in dom["questions"] if q["question_id"] == a_due)
    s, ds = api(adm, "/api/submission/section/" + urllib.parse.quote(sec))
    by_id = {q["id"]: q for q in ds["questions"]}
    ov_dom = next(dom for dom in d["domains"] if dom["name"] == sec)
    check("C8 section endpoint agrees with data-overview on every flag",
          s == 200 and all(by_id[q["question_id"]]["needs_refresh"] == q["needs_refresh"]
                           for q in ov_dom["questions"] if q["question_id"] in by_id))

    # viewer parity: same flags, read-only role
    vw = client()
    s, _ = api(vw, "/api/auth/login", "POST", {"email": VIEWER[0], "password": VIEWER[1]})
    s2, dv = api(vw, "/api/data-overview")
    check("C9 viewer sees the same flags", s == 200 and s2 == 200 and
          {q["question_id"] for dom in dv["domains"] for q in dom["questions"]
           if q["needs_refresh"]} == due_expect)

    # submit round-trip on a SINGLE-VALUE due question: re-confirm same value ->
    # flag clears, history appended, canonical timestamp
    single = next((k for k in due_expect
                   if conn.execute("SELECT COUNT(*) c FROM answers WHERE org_id=? AND "
                                   "snapshot_id=1 AND question_id=?", (ORG, k)).fetchone()["c"] == 1
                   and not flags[k]["rows"]), None)
    if single is None:
        check("C10 submit round-trip (no single-value due metric in fixture)", False)
    else:
        val = conn.execute("SELECT value FROM answers WHERE org_id=? AND snapshot_id=1 "
                           "AND question_id=?", (ORG, single)).fetchone()["value"]
        h0 = conn.execute("SELECT COUNT(*) c FROM answers_history WHERE org_id=? AND "
                          "question_id=?", (ORG, single)).fetchone()["c"]
        s, _ = api(adm, "/api/submission/draft", "PUT",
                   {"question_id": single, "matrix_row_id": "", "value": val})
        s2, dsub = api(adm, "/api/submission/submit", "POST")
        c2 = conn_rw()   # fresh connection: the server committed on its own handle
        h1 = c2.execute("SELECT COUNT(*) c FROM answers_history WHERE org_id=? AND "
                        "question_id=?", (ORG, single)).fetchone()["c"]
        row = c2.execute("SELECT value, submitted_at FROM answers WHERE org_id=? AND "
                         "snapshot_id=1 AND question_id=?", (ORG, single)).fetchone()
        s3, d3 = api(adm, "/api/data-overview")
        still = {q["question_id"] for dom in d3["domains"] for q in dom["questions"]
                 if q["needs_refresh"]}
        check("C10 re-confirming the same value clears the flag", s == 200 and s2 == 200
              and single not in still and still == (pristine_due | due_expect) - {single})
        check("C11 the prior answer is preserved (history +1, value unchanged)",
              h1 == h0 + 1 and row["value"] == val)
        check("C12 the refreshed timestamp is canonical 19-char sqlite UTC",
              len(row["submitted_at"] or "") == 19 and row["submitted_at"][4] == "-")
        c2.close()
finally:
    # restore every original timestamp — including the C10 qid's, so the world
    # returns to its exact pristine staleness (values were never changed; the
    # extra history row legitimately remains, append-only telemetry)
    for (qid, row_id), ts in originals.items():
        conn.execute("UPDATE answers SET submitted_at=? WHERE org_id=? AND snapshot_id=1 "
                     "AND question_id=? AND matrix_row_id=?", (ts, ORG, qid, row_id))
    conn.commit()

s, d = api(adm, "/api/data-overview")
final_due = {q["question_id"] for dom in d["domains"] for q in dom["questions"]
             if q["needs_refresh"]}
check("C13 teardown: staleness restored to the pristine baseline",
      s == 200 and final_due == pristine_due,
      "extra=%s" % (final_due ^ pristine_due) if final_due != pristine_due else "")

print("== REFRESH GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
if FAIL:
    for name, detail in FAIL:
        print("  FAILED: %s %s" % (name, detail))
    sys.exit(1)
