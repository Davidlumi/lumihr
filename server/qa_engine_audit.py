# -*- coding: utf-8 -*-
"""ENGINE AUDIT — standing independent gate (2026-06-12).

Verifies the data engine end-to-end: storage fidelity -> calculation ->
suppression/isolation -> peer cuts, plus determinism and edge cases.

CARDINAL RULE: the reference here is FRESH. It imports NO production
aggregation/parsing/suppression/library code — questions metadata is parsed
straight from the questions table, answers straight from SQLite, and every
computation (percentile, midrank, multi-select split, matrix parse/mode,
banded ordering, suppression floor) is its own implementation. Production
output is read from what members actually receive (HTTP API) and from the
stored benchmark_snapshots, never recomputed via production functions.
The ONLY production imports live in the EDGE section, where production code
is explicitly the SUBJECT under test (crafted inputs), not the referee.

INPUT DATA: the live DB (lumi.db) — the same input production aggregates.
data/responses/*.csv is the import-time ground truth for Layer 1, EXCEPT the
documented in-DB regenerations (REW_INC_072 2026-06-11, EXT_REW_GAP_013
2026-06-12) whose CSVs are stale by design; those are verified against their
seeded scripts' documented output distributions instead.

Run with the app up on :8060.  Exit code != 0 on hard failures.
"""
import csv
import glob
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import urllib.request
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
# Honor LUMI_DB like db.py — the audit must read the SAME database the app serves.
# (Latent bug found 2026-07-16: hardcoded live lumi.db; invisible while gate copies were
# made from live, exposed the first time LUMI_GATES_SRC pointed the suite at a throwaway.)
DB = os.environ.get("LUMI_DB", os.path.join(ROOT, "lumi.db"))
BASE = "http://localhost:8060"
FLOOR = 5  # the documented suppression rule, asserted independently

# in-DB regenerations whose CSVs are stale by design (documented in DECISIONS.md)
REGEN_WHITELIST = {
    "REW_INC_072": {"Not used": 143, "Used rarely in exceptional cases": 27,
                    "Used for specific hard-to-fill roles": 38,
                    "Used strategically as part of attraction strategy": 12},
    "EXT_REW_GAP_013": {"Monthly": 128, "Weekly": 23, "Mixed (varies by role)": 18,
                        "Fortnightly": 8, "Don't know": 2},
    # allowances-pensionability joint regen (2026-06-12, David-signed 72/20/8):
    "ALLOW_03": {"No – non-pensionable": 154, "Yes – some allowances only": 42,
                 "Yes – all allowances": 20, "Don't know": 3,
                 "Varies by allowance/contract": 1},
    "REW_PAY_020": {"No": 1092, "Yes": 448},
}

# Ruled retirements (Diff 14, 2026-07-18 — DECISIONS.md pay/pensions audit round 1):
# question status=retired and its SEED answers deleted by David's ruling
# (fictional-practice distributions; answers_history carries the pre-retire
# snapshot). Their response-CSV rows are historical lineage, not missing data.
# ONLY ruled retirements may be listed — a silent retirement must still fail L1.
RETIRED_LINEAGE = {
    "PROP_dff9a2a5": "Diff 14: pay-increase award-rate — fictional-practice distribution, retired",
    "REW264_PEN_CONTRIBTIER": "Diff 14: service/age pension escalation — legally-dead practice, retired "
                              "(never in response CSVs; listed for completeness)",
}

# The surgical coherence reseed (18 June 2026, David-confirmed — DECISIONS.md) rewrote
# per-org values across the book WITHOUT moving top-lines; rew_live_meta.json was a ruled
# input and names its question universe. Row-level CSV lineage for those qids ended that
# day by design, so the L1 value diff skips them (same treatment as REGEN_WHITELIST —
# found 2026-07-14 as 15,251 "mismatches", 50/50 qids inside the manifest).
try:
    RESEED_2026_06_18 = set(json.load(open(os.path.join(ROOT, "rew_live_meta.json"))))
except Exception:
    RESEED_2026_06_18 = set()

# Diff 7 (14 July 2026, ruled) surgically reseeded the 99 wave metrics; diff7_seed_manifest.csv
# is the ruled lineage record, whitelisted per the only-ruled-manifests rule. The whole REW264_/
# REW265_ wave is DB-origin (seed scripts, absent from the response CSVs by convention — same
# treatment as REW26_/REW262_).
try:
    DIFF7_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "diff7_seed_manifest.csv")))
                      if not r["metric_id"].startswith("__SUMMARY")}
except Exception:
    DIFF7_MANIFEST = set()

# Diff 8 (15 July 2026, ruled) reseeded 3 wave rows to verified CIPD primary figures;
# diff8_seed_manifest.csv is the ruled lineage record, whitelisted on the same rule.
try:
    DIFF8_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "diff8_seed_manifest.csv")))}
except Exception:
    DIFF8_MANIFEST = set()

# Diff 13 (18 July 2026, ruled) re-seeded the by-level matrix metrics from David's
# EST practitioner baselines (expert_baseline_by_level.json); diff13_seed_manifest.csv
# is the ruled lineage record, whitelisted on the same only-ruled-manifests rule.
try:
    DIFF13_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "diff13_seed_manifest.csv")))}
except Exception:
    DIFF13_MANIFEST = set()

# Diff 15 (18 July 2026, ruled) — under-peaking full-dist reshapes + option redesigns;
# diff15_seed_manifest.csv is the ruled lineage record (only-ruled-manifests rule).
try:
    DIFF15_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "diff15_seed_manifest.csv")))}
except Exception:
    DIFF15_MANIFEST = set()

# r3sw1 (18 July 2026, ruled) — tronc family scope clean + conditioned reseed;
# r3sw1_seed_manifest.csv is the ruled lineage record (only-ruled-manifests rule).
try:
    R3SW1_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "r3sw1_seed_manifest.csv")))}
except Exception:
    R3SW1_MANIFEST = set()

# r3sw2 (18 July 2026, ruled) — sector-keyed gradient (INC_103/131 + stale-trust cleanup).
try:
    R3SW2_MANIFEST = {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, "r3sw2_seed_manifest.csv")))}
except Exception:
    R3SW2_MANIFEST = set()

# r3sw5/r3sw6 (18 July 2026, ruled) — pre-audit bundle + PMI group-scheme re-base.
R3SW56_MANIFESTS = set()
for _mf in ("r3sw5_seed_manifest.csv", "r3sw6_seed_manifest.csv"):
    try:
        R3SW56_MANIFESTS |= {r["metric_id"] for r in __import__("csv").DictReader(open(os.path.join(ROOT, _mf)))}
    except Exception:
        pass


# Diff 3 (16 July 2026, ruled) reseeded 37 marginals from the register-generated set;
# generated_marginals.json is the ruled lineage record (only-ruled-manifests rule). Rows in it
# SUPERSEDE any older REGEN_WHITELIST exact-count pin (e.g. REW_INC_072's 2026-06-11 counts —
# re-ruled to the 0.15 large-only marginal at the Diff-2 final-table approval).
try:
    DIFF3_MARGINALS = set(json.load(open(os.path.join(ROOT, "generated_marginals.json")))["marginals"])
except Exception:
    DIFF3_MARGINALS = set()


def _db_origin(qid):
    if qid.startswith(("REW264_", "REW265_")) or qid in DIFF7_MANIFEST or qid in DIFF8_MANIFEST \
            or qid in DIFF13_MANIFEST or qid in DIFF15_MANIFEST or qid in R3SW1_MANIFEST \
            or qid in R3SW2_MANIFEST or qid in R3SW56_MANIFESTS:
        return True
    return qid in REGEN_WHITELIST or qid in RESEED_2026_06_18 or qid in DIFF3_MARGINALS

FAILS = []
WARNS = []


def fail(section, msg):
    FAILS.append((section, msg))
    print("  FAIL [%s] %s" % (section, msg))


def warn(section, msg):
    WARNS.append((section, msg))
    print("  warn [%s] %s" % (section, msg))


# ------------------------------------------------------ fresh reference bits
def ref_pctl(vals, p):
    """Linear interpolation percentile — own arrangement of the formula."""
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * (p / 100.0)
    f, c = int(math.floor(k)), int(math.ceil(k))
    if f == c:
        return float(s[f])
    return float(s[f] * (c - k) + s[c] * (k - f))


def ref_midrank(sorted_vals, x):
    if not sorted_vals:
        return None
    below = sum(1 for v in sorted_vals if v < x)
    eq = sum(1 for v in sorted_vals if v == x)
    return min(99.0, max(1.0, 100.0 * (below + 0.5 * eq) / len(sorted_vals)))


_REF_NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(x|×|%|weeks?|wks?)?\s*$", re.I)
_REF_NA = re.compile(r"^(not applicable|don'?t know|prefer not|unsure\b|n/?a$)", re.I)


def ref_num(v):
    """Own tolerant numeric parse ('1.5x', '98%', '12 weeks')."""
    m = _REF_NUM.match(str(v)) if v is not None else None
    return float(m.group(1)) if m else None


def ref_plain_num(v):
    t = str(v or "").strip().replace(",", "").replace("£", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def ref_norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def close(a, b, tol=1e-6):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


# question metadata parsed straight from the table — no library.py
def load_q_meta(conn):
    out = {}
    for r in conn.execute("SELECT * FROM questions ORDER BY question_order"):
        d = dict(r)
        for k in ("options_json", "matrix_json", "matrix_rows_json", "scoring_config_json"):
            try:
                d[k[:-5]] = json.loads(d[k]) if d[k] else None
            except ValueError:
                d[k[:-5]] = None
        out[d["id"]] = d
    return out


def q_matrix_col(meta):
    cols = ((meta.get("matrix") or {}).get("columns")) or []
    return cols[0] if cols else {}


def q_row_ids(meta):
    rows = meta.get("matrix_rows") or []
    if not rows and isinstance(meta.get("matrix"), dict):
        rows = [x.get("label") if isinstance(x, dict) else x
                for x in (meta["matrix"].get("rows") or [])]
    return [re.sub(r"[^a-z0-9]+", "_", (lbl or "").lower()).strip("_") for lbl in rows]


def api(opener, path):
    try:
        with opener.open(BASE + path, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def api_post(opener, path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def login(email, password):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    st, _ = api_post(op, "/api/auth/login", {"email": email, "password": password})
    if st != 200:
        print("FATAL: login failed (%s) — is the app running on :8060?" % st)
        sys.exit(2)
    return op


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
META = load_q_meta(conn)
# live core = Reward AND not retired (retired questions leave the member
# surface by design — including them would 404 every API comparison)
REWARD = {qid: m for qid, m in META.items()
          if m["superpower"] == "Reward" and (m.get("status") or "active") != "retired"}
print("scope: %d reward questions (reference derives scope from the questions table)" % len(REWARD))

raw_answers = {}   # (qid, org, row) -> value
for r in conn.execute("SELECT question_id, org_id, matrix_row_id, value FROM answers WHERE snapshot_id=1"):
    raw_answers[(r["question_id"], r["org_id"], r["matrix_row_id"] or "")] = r["value"]
responding = {o for (_q, o, _r) in raw_answers}

# ---- cache-freshness self-check (the footgun): a running app with a stale
# question cache makes every API comparison falsely green or falsely broken.
# Verify the served question count equals the DB live core BEFORE auditing.
_op0 = login("analyst@thornbridge.example", "lumi-data-2026")
_st, _me = api(_op0, "/api/me")
_served = ((_me.get("scope") or {}).get("question_count"))
# r3s4: sector-scoped metrics are FULLY hidden from out-of-scope orgs BY DESIGN,
# so the demo org's served count = core minus the scoped metrics its industry
# doesn't qualify for. sector_scopes.json is read as DATA (declaration, not
# production code) — the same rule as the questions table.
_demo_ind = conn.execute("SELECT industry FROM orgs WHERE normalized_name LIKE "
                         "'thornbridgeretail%'").fetchone()["industry"]
_scopes_path = os.path.join(ROOT, "data", "sector_scopes.json")
_scopes = (json.load(open(_scopes_path)).get("scopes") or {}) if os.path.exists(_scopes_path) else {}
_scope_hidden = sum(1 for q, e in _scopes.items()
                    if q in REWARD and _demo_ind not in (e.get("sectors") or []))
_expected = len(REWARD) - _scope_hidden
if _served != _expected:
    print("FATAL: app serves %s questions but the DB live core is %d (expected %d after"
          " %d sector-scope hides) — stale question cache OR a scope leak. Restart the"
          " app and re-run this gate." % (_served, len(REWARD), _expected, _scope_hidden))
    sys.exit(2)
print("cache freshness: app serves %d == DB live core %d - %d sector-scoped == %d"
      % (_served, len(REWARD), _scope_hidden, _expected))

# =========================================================== LAYER 1: STORAGE
print("\n================ LAYER 1 — STORAGE FIDELITY (out == in) ================")
csv_rows = {}
for f in glob.glob(os.path.join(ROOT, "data", "responses", "*.csv")):
    with open(f) as fh:
        for r in csv.DictReader(fh):
            v = (r["your_answer"] or "").strip()
            if v != "":
                csv_rows[(r["question_id"], r["org_id"], r["matrix_row_id"] or "")] = v

missing_in_db = mismatched = 0
type_examples = {}
for key, v in csv_rows.items():
    qid = key[0]
    if _db_origin(qid) or qid in RETIRED_LINEAGE:
        continue
    dbv = raw_answers.get(key)
    if dbv is None:
        missing_in_db += 1
        if missing_in_db <= 3:
            fail("L1", "CSV row absent from store: %s %s/%s = %r" % (qid, key[1][:8], key[2], v[:40]))
    elif dbv != v:
        mismatched += 1
        if mismatched <= 3:
            fail("L1", "value changed in store: %s %s/%s CSV=%r DB=%r" % (qid, key[1][:8], key[2], v[:40], dbv[:40]))
    else:
        t = META.get(qid, {}).get("type")
        if t and t not in type_examples:
            type_examples[t] = (qid, key[2], v)
# release-addition seeds (REW26_*/REW262_*) are documented DB-origin data —
# their lineage is the seed scripts + DECISIONS.md, not the response CSVs
extra_in_db = [k for k in raw_answers
               if k not in csv_rows and not _db_origin(k[0]) and k[0] in META
               and not k[0].startswith(("REW26_", "REW262_"))]
# question-level matrix N/A (row '') is a legitimate post-import state; so are drafts-era saves
extra_real = [k for k in extra_in_db if not (META[k[0]]["type"] == "matrix" and k[2] == "")]
print("CSV ground-truth rows: %d | exact in store: %d | changed: %d | missing: %d | extra in DB: %d"
      % (len(csv_rows), len(csv_rows) - mismatched - missing_in_db
         - sum(1 for k in csv_rows if k[0] in REGEN_WHITELIST or k[0] in RETIRED_LINEAGE),
         mismatched, missing_in_db, len(extra_real)))
if mismatched or missing_in_db:
    fail("L1", "%d mismatched / %d missing rows vs current raw CSVs" % (mismatched, missing_in_db))
if extra_real:
    for k in extra_real[:3]:
        warn("L1", "answer in DB with no CSV origin: %s %s/%s = %r" % (k[0], k[1][:8], k[2], str(raw_answers[k])[:40]))

print("\nper-type round-trip examples (raw CSV -> stored -> retrieved, byte-equal):")
for t, (qid, rid, v) in sorted(type_examples.items()):
    print("  %-14s %s%s: %r" % (t, qid, ("/" + rid) if rid else "", v[:58]))

# regenerated metrics: store must equal each script's documented seeded output —
# UNLESS a NEWER ruled manifest supersedes the pin (Diff-3 generated marginals).
for qid, expected in REGEN_WHITELIST.items():
    if qid in DIFF3_MARGINALS:
        print("  regen-whitelist %s: pin SUPERSEDED by the Diff-3 ruled marginal (generated_marginals.json)" % qid)
        continue
    got = {}
    for r in conn.execute("SELECT value, COUNT(*) c FROM answers WHERE question_id=? AND snapshot_id=1 GROUP BY value", (qid,)):
        got[r["value"]] = r["c"]
    if got != expected:
        fail("L1", "regenerated %s store != documented seeded output: %s vs %s" % (qid, got, expected))
    else:
        print("  regen-whitelist %s: store matches the documented seeded distribution %s" % (qid, expected))

# N/A vs 0 vs blank: three distinct states, shown on real data
print("\ntri-state check (N/A vs 0 vs blank are distinct):")
zero_ex = conn.execute("SELECT question_id, org_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 AND TRIM(value)='0' LIMIT 1").fetchone()
na_ex = conn.execute("SELECT question_id, org_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 AND LOWER(value) LIKE 'not applicable%' LIMIT 1").fetchone()
blank_ct = conn.execute("SELECT COUNT(*) FROM answers WHERE snapshot_id=1 AND (value IS NULL OR TRIM(value)='')").fetchone()[0]
print("  real zero stored:   %s" % (dict(zero_ex) if zero_ex else "none in seed (zeros enterable; none seeded)"))
print("  N/A stored as text: %s" % (dict(na_ex) if na_ex else "none at answer level"))
print("  blank rows in store: %d (blank = unanswered = NO row; %d would be a corruption)" % (blank_ct, blank_ct))
if blank_ct:
    fail("L1", "%d empty-string/NULL answer rows present — blank must be absence, not a stored value" % blank_ct)

# no silent coercion: suffix/banded/currency strings preserved verbatim
fancy = [r for r in conn.execute(
    "SELECT value FROM answers WHERE snapshot_id=1 AND (value LIKE '%x' OR value LIKE '%weeks%' OR value LIKE 'More than%') LIMIT 6")]
print("  suffix/banded values stored verbatim: %s" % [r["value"] for r in fancy])

# ====================================================== LAYER 2: CALCULATION
print("\n================ LAYER 2 — CALCULATION (independent recompute) ================")
op = login("analyst@thornbridge.example", "lumi-data-2026")
demo_org = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]

# The reference pool mirrors the engine's documented completeness FIREWALL
# (aggregate.run_snapshot): only submission-complete orgs contribute to the
# published benchmark — a half-finished signup that answered one question must
# not inflate ref counts either (the ALLOW_02 n=221-vs-220 case, the Tester org).
_complete = {r[0] for r in conn.execute("SELECT org_id FROM orgs WHERE submission_complete=1")}
bench_answers = {k: v for k, v in raw_answers.items() if k[1] in _complete}

checked = {"numeric": 0, "single_select": 0, "yes_no": 0, "multi_select": 0,
           "matrix-numeric": 0, "matrix-categorical": 0}
mismatches = 0


def ref_select_counts(qid):
    per_org = {o: v for (q2, o, r2), v in bench_answers.items() if q2 == qid and not r2 and str(v).strip()}
    return per_org


for qid, m in REWARD.items():
    per_org = ref_select_counts(qid)
    st, card = api(op, "/api/benchmark/%s?dim=all" % qid)
    if st != 200:
        # r3s4: sector-scoped metrics 404 for the out-of-scope audit org BY DESIGN
        # (the hide under test). Their stored payload is still verified below via
        # the benchmark_snapshots comparison on the next audit surface; here we
        # assert the 404 is the SCOPE speaking, not a serving fault.
        if qid in _scopes and _demo_ind not in (_scopes[qid].get("sectors") or []):
            print("  scope-hidden (by design): %s -> API %s for the %s audit org" % (qid, st, _demo_ind))
            continue
        fail("L2", "%s: API %s" % (qid, st))
        continue
    blk = card.get("block") or {}
    stored = json.loads(conn.execute(
        "SELECT payload_json FROM benchmark_snapshots WHERE question_id=?", (qid,)).fetchone()[0])

    if m["type"] == "numeric":
        vals = [f for f in (ref_plain_num(v) for v in per_org.values()
                            if not _REF_NA.match(str(v).strip())) if f is not None]
        n = len(vals)
        if n < FLOOR:
            if not (card.get("suppressed") or blk.get("suppressed")):
                fail("L2", "%s numeric n=%d below floor but served" % (qid, n))
        else:
            # stored percentiles are ROUNDED to 2dp, so a true value on a half-cent
            # (3.275 -> stored 3.27) legitimately sits 0.005 away from the raw ref
            for p_, key in ((10, "p10"), (25, "p25"), (50, "p50"), (75, "p75"), (90, "p90")):
                if not close(ref_pctl(vals, p_), blk.get(key), 5.01e-3):
                    fail("L2", "%s %s: ref %.4f vs prod %s (raw n=%d)" % (qid, key, ref_pctl(vals, p_), blk.get(key), n))
                    mismatches += 1
                    break
            if blk.get("n") != n:
                fail("L2", "%s numeric n: ref %d vs prod %s" % (qid, n, blk.get("n")))
        checked["numeric"] += 1

    elif m["type"] in ("single_select", "yes_no"):
        labels = [o.get("label") for o in (m.get("options") or [])]
        cnt = {}
        for v in per_org.values():
            cnt[str(v).strip()] = cnt.get(str(v).strip(), 0) + 1
        n = sum(cnt.values())
        if n >= FLOOR:
            prod_opts = {o["label"]: o for o in (blk.get("options") or [])}
            for lbl, c in cnt.items():
                po = prod_opts.get(lbl)
                if po is None or po.get("count") != c or not close(po.get("pct"), round(100.0 * c / n, 1), 0.051):
                    fail("L2", "%s option %r: ref %d (%.1f%%) vs prod %s" % (
                        qid, lbl[:30], c, 100.0 * c / n, po and (po.get("count"), po.get("pct"))))
                    mismatches += 1
                    break
            if blk.get("n") != n:
                fail("L2", "%s select n: ref %d vs prod %s" % (qid, n, blk.get("n")))
        checked[m["type"]] += 1

    elif m["type"] == "multi_select":
        labels = {ref_norm(o.get("label")): o.get("label") for o in (m.get("options") or [])}
        n = len(per_org)
        cnt = {}
        unmatched = 0
        for v in per_org.values():
            seen = set()
            for tok in str(v).split(";"):
                t = ref_norm(tok)
                if not t:
                    continue
                lbl = labels.get(t)
                if lbl is None:
                    unmatched += 1
                elif lbl not in seen:
                    seen.add(lbl)
                    cnt[lbl] = cnt.get(lbl, 0) + 1
        if unmatched:
            fail("L2", "%s: %d selections fail to map to a library option (silent drop)" % (qid, unmatched))
        if n >= FLOOR:
            prod_opts = {o["label"]: o for o in (blk.get("options") or [])}
            for lbl, c in cnt.items():
                po = prod_opts.get(lbl)
                if po is None or po.get("count") != c:
                    fail("L2", "%s multi option %r: ref %d vs prod %s" % (qid, lbl[:30], c, po and po.get("count")))
                    mismatches += 1
                    break
            if blk.get("n") != n:
                fail("L2", "%s multi n: ref %d vs prod %s" % (qid, n, blk.get("n")))
        checked["multi_select"] += 1

    elif m["type"] == "matrix":
        col = q_matrix_col(m)
        col_opts = col.get("options") or []
        by_row = {}
        for (q2, o, r2), v in bench_answers.items():
            if q2 == qid and r2 and str(v).strip():
                by_row.setdefault(r2, {})[o] = str(v).strip()
        distinct = {v for per in by_row.values() for v in per.values()
                    if not (_REF_NA.match(v) and v not in col_opts)}
        numeric_mode = col.get("type") in ("percentage", "currency", "number") or (
            bool(distinct) and all(ref_num(v) is not None for v in distinct))
        prod_rows = {r["row_id"]: (r.get("block") or {}) for r in (card.get("matrix_rows") or [])}
        for rid, per in by_row.items():
            vals = [v for v in per.values() if not (_REF_NA.match(v) and v not in col_opts)]
            pblk = prod_rows.get(rid) or {}
            if numeric_mode:
                nums = [ref_num(v) for v in vals if ref_num(v) is not None]
                if len(nums) >= FLOOR:
                    if pblk.get("n") != len(nums) or not close(ref_pctl(nums, 50), pblk.get("p50"), 1e-6):
                        fail("L2", "%s row %s: ref n=%d p50=%s vs prod n=%s p50=%s" % (
                            qid, rid, len(nums), ref_pctl(nums, 50), pblk.get("n"), pblk.get("p50")))
                        mismatches += 1
                elif pblk and not pblk.get("suppressed") and pblk.get("p50") is not None:
                    fail("L2", "%s row %s: n=%d below floor but served" % (qid, rid, len(nums)))
            else:
                cnt = {}
                for v in vals:
                    cnt[v] = cnt.get(v, 0) + 1
                n = sum(cnt.values())
                if n >= FLOOR:
                    if pblk.get("kind") != "select" or pblk.get("n") != n:
                        fail("L2", "%s row %s: populated categorical row not aggregated (ref n=%d, prod %s/%s)" % (
                            qid, rid, n, pblk.get("kind"), pblk.get("n")))
                        mismatches += 1
                    else:
                        pc = {o["label"]: o["count"] for o in (pblk.get("options") or [])}
                        bad = [l for l, c in cnt.items() if pc.get(l) != c]
                        if bad:
                            fail("L2", "%s row %s: option counts diverge on %r" % (qid, rid, bad[:2]))
                            mismatches += 1
        checked["matrix-numeric" if numeric_mode else "matrix-categorical"] += 1

    # cross-surface: served card vs stored snapshot (same numbers everywhere)
    s_all = stored.get("all") or {}
    if not (blk.get("suppressed") or s_all.get("suppressed")):
        if blk.get("n") is not None and s_all.get("n") is not None and blk["n"] != s_all["n"]:
            fail("L2", "%s: served n=%s != stored n=%s (surface divergence)" % (qid, blk.get("n"), s_all.get("n")))

print("recomputed per type: %s | value mismatches: %d" % (checked, mismatches))

# polarity spot-derivation on the scored multi-select (independent midrank).
# Points model (documented, 2026-06-12): each selected non-na option scores its
# option_score; none-ish options score 0 (assessed zero provision). The config
# is DATA (questions table) — reading it keeps the code path independent.
# Spot metric DERIVED: first live scored multi-select in the reward-visible set that
# the demo org has answered (the old ALLOW_01 literal died with the Diff 3 retirement).
# Diff 14: unbenchmarked metrics no longer SERVE a score percentile (that is the
# suppression under test elsewhere), so the spot must pick a benchmarked one. The
# curated config is read as DATA — the no-production-imports rule holds.
_unbench = {q for q, e in (json.load(open(os.path.join(ROOT, "data", "market_position_config.json")))
                           .get("metrics") or {}).items() if e.get("unbenchmarked")}
_spot = next((r["id"] for r in conn.execute(
    "SELECT id FROM questions WHERE status='active' AND is_scored=1 AND type='multi_select' "
    "AND scoring_config_json LIKE '%option_scores%' ORDER BY id")
    if r["id"] in REWARD and r["id"] not in _unbench and demo_org in ref_select_counts(r["id"])), None)
if _spot is None:
    warn("L2", "no benchmarked scored multi-select left for the percentile spot (all suppressed)")
_cfg = None if _spot is None else json.loads(conn.execute("SELECT scoring_config_json FROM questions WHERE id=?", (_spot,)).fetchone()[0])
if _spot is not None:
    _opt_code = {ref_norm(o["label"]): o["code"] for o in (REWARD[_spot].get("options") or [])}
    _scores, _na = _cfg["option_scores"], set(_cfg.get("na_codes") or [])
    _mx = float(sum(v for c, v in _scores.items() if c not in _na))

    def _points(ans):
        sel = {_opt_code.get(ref_norm(t)) for t in str(ans).split(";") if t.strip()}
        return 100.0 * sum(_scores.get(c, 0) for c in sel if c and c not in _na) / _mx

    vals = sorted(_points(v) for v in ref_select_counts(_spot).values())
    st, card = api(op, "/api/benchmark/%s?dim=all" % _spot)
    you_raw = "; ".join((card.get("you") or {}).get("labels") or [])
    mine = len((card.get("you") or {}).get("labels") or [])
    ref_p = ref_midrank(vals, _points(you_raw))
    prod_p = (card.get("score") or {}).get("percentile")
    if prod_p is None:
        fail("L2", "benchmarked spot %s serves no score percentile (suppression over-reach?)" % _spot)
    else:
        print("polarity/verdict spot (%s): you=%d options; ref midrank=%.1f vs prod %.1f; higher_is_better -> %s"
              % (_spot, mine, ref_p, prod_p, "Behind" if ref_p < 45 else "Ahead" if ref_p > 55 else "In line"))
        if not close(ref_p, prod_p, 0.51):
            fail("L2", "scored percentile diverges: ref %.1f vs prod %s" % (ref_p, prod_p))

# ===================================================== LAYER 3: SUPPRESSION
print("\n================ LAYER 3 — SUPPRESSION / ISOLATION ================")
leaks = 0
VALUE_KEYS = {"p10", "p25", "p50", "p75", "p90", "mean", "min", "max", "options", "modal_pct", "in_place_pct"}


def walk(node, path, qid):
    global leaks
    if isinstance(node, dict):
        n = node.get("n")
        if isinstance(n, int) and 0 < n < FLOOR and not node.get("suppressed"):
            if any(k in node for k in VALUE_KEYS):
                leaks += 1
                fail("L3", "stored block with n=%d unsuppressed at %s in %s" % (n, path, qid))
        for k, v in node.items():
            walk(v, path + "/" + str(k), qid)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + "[%d]" % i, qid)


for r in conn.execute("SELECT question_id, payload_json FROM benchmark_snapshots"):
    walk(json.loads(r["payload_json"]), "", r["question_id"])
print("stored payloads scanned for sub-floor values: leaks=%d" % leaks)

# the API must strip internal keys (raw _values) on every served card
st, card = api(op, "/api/benchmark/PROP_9e4ad87f?dim=all")
internal = [k for k in (card.get("block") or {}) if k.startswith("_")]
if internal:
    fail("L3", "served card leaks internal keys: %s" % internal)
else:
    print("served card carries no internal '_' keys (raw _values stripped)")

# live below-floor custom group end-to-end (admin builds groups)
opa = login("director@thornbridge.example", "lumi-demo-2026")
# find a genuinely below-floor industry x band combo from the orgs table (raw),
# then confirm the live engine refuses to aggregate it end-to-end
combo = conn.execute(
    """SELECT industry, fte_band, COUNT(*) c FROM orgs
       WHERE classified=1 AND submission_complete=1 AND industry IS NOT NULL AND fte_band IS NOT NULL
       GROUP BY industry, fte_band HAVING c BETWEEN 1 AND ? ORDER BY c LIMIT 1""", (FLOOR - 1,)).fetchone()
small_crit = None
prev = {}
if combo:
    small_crit = {"industry": [combo["industry"]], "fte_band": [combo["fte_band"]]}
    st, prev = api_post(opa, "/api/peer-groups/preview", {"criteria": small_crit})
    print("below-floor combo from raw: %s x %s = %d orgs | preview: HTTP %s %s"
          % (combo["industry"], combo["fte_band"], combo["c"], st, prev))
    if prev.get("match_count") != combo["c"]:
        fail("L3", "preview count %s != raw qualifying count %d" % (prev.get("match_count"), combo["c"]))
    if not prev.get("too_small"):
        fail("L3", "below-floor preview not marked too_small")
if small_crit:
    st, g = api_post(opa, "/api/peer-groups", {"name": "audit-tiny", "criteria": small_crit})
    gid = (g or {}).get("group_id") or (g or {}).get("id")
    # the REAL member cut params are cut=group&cut_value=<gid>
    st, card = api(opa, "/api/benchmark/PROP_9e4ad87f?cut=group&cut_value=%s" % gid)
    blk = card.get("block")
    served_vals = bool(blk) and not blk.get("suppressed") and any(k in blk for k in VALUE_KEYS)
    print("below-floor group (match=%s): suppressed=%s block=%s readout=%r -> %s" % (
        prev.get("match_count"), card.get("suppressed"),
        None if not blk else {k: blk.get(k) for k in ("n", "suppressed")},
        str(card.get("readout"))[:60], "OK" if not served_vals else "LEAK"))
    if served_vals:
        fail("L3", "below-floor custom group served values")
    if not card.get("suppressed"):
        fail("L3", "below-floor group card not marked suppressed")
    # AI surface: commentary for the suppressed cut must carry no peer numbers
    st, com = api_post(opa, "/api/metric-commentary",
                       {"question_id": "PROP_9e4ad87f", "cut": "group", "cut_value": gid})
    body = json.dumps(com)
    nums = re.findall(r"\d+(?:\.\d+)?\s*%", body)
    if nums and "fewer than 5" not in body and "suppress" not in body.lower():
        fail("L3", "commentary on a suppressed cut carries peer numbers: %s" % body[:140])
    else:
        print("AI commentary on the suppressed cut: clean (%s)" % str(com.get("parts", com))[:90])
    import urllib.request as _u
    req = _u.Request(BASE + "/api/peer-groups/%s" % gid, method="DELETE")
    opa.open(req).read()
    # a foreign/stale group id must resolve to all peers, honestly LABELLED
    st, c3 = api(opa, "/api/benchmark/PROP_9e4ad87f?cut=group&cut_value=not-a-real-id")
    lbl = (c3.get("cut") or {}).get("label")
    print("stale/foreign group id -> cut label %r (documented all-peers fallback, labelled)" % lbl)
    if (c3.get("cut") or {}).get("dim") == "group":
        fail("L3", "foreign group id resolved as a group cut")
else:
    warn("L3", "no naturally below-floor industry+size combination found to live-test (engine floor still verified via stored-payload scan)")

# cross-tenant: a foreign org's raw data must be unreachable
foreign = conn.execute("SELECT org_id FROM orgs WHERE org_id != ? LIMIT 1", (demo_org,)).fetchone()["org_id"]
st, body = api(op, "/api/my-data?org_id=%s" % foreign)
foreign_name = conn.execute("SELECT name FROM orgs WHERE org_id=?", (foreign,)).fetchone()["name"]
leak_names = foreign_name in json.dumps(body)
print("cross-tenant /api/my-data?org_id=<foreign>: HTTP %s, foreign org name present: %s" % (st, leak_names))
if leak_names:
    fail("L3", "foreign org data visible via org_id injection")

# differential residual (documented, flagged to David): two big cuts differing by one org
print("differential-attack residual: custom groups differing by one org can in principle be")
print("  differenced (mean*n arithmetic). Standing mitigation = counts-only previews + n>=5;")
print("  full k-overlap defence flagged to David in DECISIONS.md (unchanged by this audit).")

# ======================================================= LAYER 4: PEER CUTS
print("\n================ LAYER 4 — PEER-CUT ENGINE ================")
orgs_tbl = {r["org_id"]: dict(r) for r in conn.execute("SELECT * FROM orgs")}
# documented rule: all = responding; filtered cuts = classified responders with the label
ref_cut = {}
for o in responding:
    r = orgs_tbl.get(o)
    if r and r.get("classified"):
        if r.get("industry"):
            ref_cut.setdefault(("industry", r["industry"]), set()).add(o)
        if r.get("fte_band"):
            ref_cut.setdefault(("fte_band", r["fte_band"]), set()).add(o)

stored = json.loads(conn.execute(
    "SELECT payload_json FROM benchmark_snapshots WHERE question_id='EXT_REW_GAP_013'").fetchone()[0])
answered_013 = {o for (q2, o, r2) in bench_answers if q2 == "EXT_REW_GAP_013" and not r2}
cut_checks = 0
for (dim, val), org_set in sorted(ref_cut.items())[:0] or []:
    pass
for dim_key, payload_key in (("industry", "by_industry"), ("fte_band", "by_fte_band")):
    for val, blk in (stored.get(payload_key) or {}).items():
        expect = len(ref_cut.get((dim_key, val), set()) & answered_013)
        got = blk.get("n")
        if expect < FLOOR:
            if not blk.get("suppressed"):
                fail("L4", "cut %s=%s n=%d below floor but unsuppressed" % (dim_key, val, expect))
        elif got != expect:
            fail("L4", "cut %s=%s: ref n=%d vs prod n=%s" % (dim_key, val, expect, got))
        cut_checks += 1
print("cut sets recomputed from orgs table for EXT_REW_GAP_013: %d cuts, n verified against the raw qualifying set" % cut_checks)

three = sorted(ref_cut.items(), key=lambda kv: -len(kv[1]))[:3]
for (dim, val), s in three:
    print("  %s=%s qualifying orgs (raw): %d" % (dim, val, len(s)))

# null-attribute rule: unclassified orgs in 'all', absent from every filtered cut
unclassified = [o for o in responding if not orgs_tbl.get(o, {}).get("classified")]
in_cuts = [o for o in unclassified for s in ref_cut.values() if o in s]
print("null/unclassified responders: %d -> in 'all' (yes, by construction), in filtered cuts: %d (rule: excluded)"
      % (len(unclassified), len(in_cuts)))

# boundary: size bands are DECLARED labels (not numeric ranges at cut time) — the
# boundary question is delegated to band assignment at profile capture; cuts match exact labels.
bands = sorted({orgs_tbl[o].get("fte_band") for o in responding if orgs_tbl[o].get("fte_band")})
print("fte bands are categorical labels (exact-match cuts, no numeric boundary in the engine): %s" % bands)

# custom group set correctness + self-inclusion
st, prevR = api_post(opa, "/api/peer-groups/preview", {"criteria": {"industry": ["Retail & Consumer Goods"]}})
# group rule (documented): submission_complete orgs matching criteria — recompute from raw
ref_grp = [r["org_id"] for r in conn.execute(
    "SELECT org_id FROM orgs WHERE submission_complete=1 AND industry='Retail & Consumer Goods'")]
print("custom-group preview Retail: prod match_count=%s vs ref qualifying=%d" % (prevR.get("match_count"), len(ref_grp)))
if prevR.get("match_count") != len(ref_grp):
    fail("L4", "custom group count diverges: prod %s vs ref %d" % (prevR.get("match_count"), len(ref_grp)))
demo_in = demo_org in ref_grp
print("self-inclusion: pool aggregates are org-independent (self always in 'all'/sector cuts);")
print("  custom groups: demo org qualifies=%s and IS counted (match_count == raw incl. self) -> consistent self-include" % demo_in)

# ========================================================== DETERMINISM
print("\n================ DETERMINISM ================")
h = hashlib.sha256()
for r in conn.execute("SELECT question_id, payload_json FROM benchmark_snapshots ORDER BY question_id"):
    h.update(r["question_id"].encode())
    h.update(json.dumps(json.loads(r["payload_json"]), sort_keys=True).encode())
before_hash = h.hexdigest()
sys.path.insert(0, HERE)
from aggregate import run_snapshot as _prod_run  # SUBJECT under test (determinism probe)
_prod_run(1, verbose=False)
conn2 = sqlite3.connect(DB)
h2 = hashlib.sha256()
for r in conn2.execute("SELECT question_id, payload_json FROM benchmark_snapshots ORDER BY question_id"):
    h2.update(r[0].encode())
    h2.update(json.dumps(json.loads(r[1]), sort_keys=True).encode())
after_hash = h2.hexdigest()
print("payload-set hash before re-aggregation: %s" % before_hash[:16])
print("payload-set hash after  re-aggregation: %s" % after_hash[:16])
if before_hash != after_hash:
    fail("DET", "re-aggregating identical data changed output (nondeterminism)")
reps = set()
for _ in range(3):
    st, card = api(op, "/api/benchmark/PROP_9e4ad87f?dim=all")
    reps.add(json.dumps(card, sort_keys=True))
print("same API call x3: %d distinct responses" % len(reps))
if len(reps) != 1:
    fail("DET", "repeated identical API calls differ")

# ============================================================== EDGE CASES
print("\n================ EDGE CASES (production functions under crafted input) ================")
import aggregate as prod  # the SUBJECT — not used as a reference anywhere above

cases = [
    ("single value", lambda: prod.numeric_block([42.0])),
    ("zero variance n=6", lambda: prod.numeric_block([5.0] * 6)),
    ("empty", lambda: prod.numeric_block([])),
    ("legit negatives", lambda: prod.numeric_block([-2.0, -1.0, 0.0, 1.0, 2.0, 3.0])),
    ("zeros only n=5", lambda: prod.numeric_block([0.0] * 5)),
]
for name, fn in cases:
    try:
        b = fn()
        ok_shape = isinstance(b, dict) and ("suppressed" in b or "p50" in b)
        nan = any(isinstance(v, float) and (math.isnan(v) or math.isinf(v)) for v in b.values() if isinstance(v, float))
        print("  %-18s -> %s%s" % (name, {k: v for k, v in b.items() if k in ('n', 'suppressed', 'p50', 'p10', 'p90')},
                                   "  NaN/Inf!" if nan else ""))
        if nan:
            fail("EDGE", "%s produced NaN/Inf" % name)
        if name == "single value" and not b.get("suppressed"):
            fail("EDGE", "single-org block served unsuppressed")
        if name == "zero variance n=6" and b.get("p10") != b.get("p90"):
            fail("EDGE", "zero-variance percentiles inconsistent")
    except Exception as e:
        fail("EDGE", "%s raised %r" % (name, e))

# ================================================================= SUMMARY
print("\n================ SUMMARY ================")
print("hard failures: %d | warnings: %d" % (len(FAILS), len(WARNS)))
for s, m in FAILS:
    print("  FAIL [%s] %s" % (s, m))
for s, m in WARNS:
    print("  warn [%s] %s" % (s, m))
sys.exit(1 if FAILS else 0)
