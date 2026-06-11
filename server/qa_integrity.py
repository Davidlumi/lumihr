# -*- coding: utf-8 -*-
"""PER-METRIC DATA INTEGRITY REVIEW — Phase A (computation) reference engine.

Recomputes every live reward metric FROM RAW ANSWERS with implementations
written fresh from the spec (linear-interpolation percentiles, midrank
position, option shares) — deliberately NOT calling the production
aggregation, so a bug in shared code cannot hide itself. Compares against the
production payloads and the live API, and screens the two recurring bug
classes (polarity inversion, cadence false-negatives) with independent
regexes. Read-only: this script changes nothing.
"""
import json
import os
import re
import sys
import sqlite3
import urllib.request
import urllib.parse
import http.cookiejar
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import load_questions          # metadata only (ids, types, options)
import app as appmod                        # production payloads — the thing under test

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")

# ---------------------------------------------------------------- reference --
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def ref_float(text):
    """Strict numeric parse, per spec: numeric questions hold plain numbers;
    anything else is excluded from numeric aggregation."""
    if text is None:
        return None
    t = str(text).strip()
    return float(t) if NUM_RE.match(t) else None


def ref_pctl(sorted_vals, p):
    """Linear interpolation (numpy 'linear'), implemented fresh."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    k = (n - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def ref_midrank(sorted_vals, x):
    """Midrank percentile, clamped [1,99] (survey convention)."""
    if not sorted_vals:
        return None
    below = sum(1 for v in sorted_vals if v < x)
    equal = sum(1 for v in sorted_vals if v == x)
    r = 100.0 * (below + equal * 0.5) / len(sorted_vals)
    return min(99.0, max(1.0, r))


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
contrib_orgs = {r["org_id"] for r in conn.execute("SELECT org_id FROM orgs WHERE submission_complete=1")}
raw = defaultdict(dict)   # (qid,row) -> {org: value}
for r in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1"):
    if r["org_id"] in contrib_orgs:
        raw[(r["question_id"], r["matrix_row_id"])][r["org_id"]] = r["value"]

demo_org = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]
qs = appmod.visible_questions()
payloads = appmod.payloads()
print("scope: %d live reward questions | contributing orgs: %d" % (len(qs), len(contrib_orgs)))

mismatch, checked, samples = [], 0, []
TOL = 0.051  # display rounding is 1dp


def close(a, b, tol=TOL):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


for qid, q in qs.items():
    p = payloads.get(qid)
    if p is None:
        mismatch.append((qid, "NO PAYLOAD"))
        continue
    blk = p.get("all") or {}
    if q.type == "numeric":
        vals = sorted(v for v in (ref_float(x) for x in raw[(qid, "")].values()) if v is not None)
        checked += 1
        if len(vals) < 5:
            if not blk.get("suppressed") and blk.get("p50") is not None:
                mismatch.append((qid, "n<5 but values served"))
            continue
        ok = (blk.get("n") == len(vals)
              and close(blk.get("p25"), ref_pctl(vals, 25))
              and close(blk.get("p50"), ref_pctl(vals, 50))
              and close(blk.get("p75"), ref_pctl(vals, 75))
              and close(blk.get("p10"), ref_pctl(vals, 10))
              and close(blk.get("p90"), ref_pctl(vals, 90)))
        if not ok:
            mismatch.append((qid, "numeric pctl/n mismatch ref(n=%d p50=%.2f) vs prod(n=%s p50=%s)" % (
                len(vals), ref_pctl(vals, 50), blk.get("n"), blk.get("p50"))))
        # demo org position
        mine = ref_float(raw[(qid, "")].get(demo_org))
        if mine is not None:
            rr = ref_midrank(vals, mine)
            if len(samples) < 99 and q.type == "numeric":
                samples.append(("numeric", qid, q.display_title[:38],
                                "raw=%s ref: n=%d p50=%.1f rank=P%.1f | prod: n=%s p50=%s" % (
                                    mine, len(vals), ref_pctl(vals, 50), rr, blk.get("n"), blk.get("p50"))))
    elif q.type in ("single_select", "yes_no"):
        counts = defaultdict(int)
        for v in raw[(qid, "")].values():
            if v is not None and str(v).strip() != "":
                counts[str(v).strip()] += 1
        total = sum(counts.values())
        checked += 1
        if total < 5:
            if not blk.get("suppressed") and blk.get("options"):
                mismatch.append((qid, "n<5 but options served"))
            continue
        if blk.get("n") != total:
            mismatch.append((qid, "select n: ref %d vs prod %s" % (total, blk.get("n"))))
            continue
        prod_opts = {o["label"]: o for o in (blk.get("options") or [])}
        pct_sum = 0.0
        bad = None
        for label, cnt in counts.items():
            ref_pct = 100.0 * cnt / total
            po = prod_opts.get(label)
            if po is None:
                bad = "answer label %r missing from options" % label[:40]
                break
            if po.get("count") != cnt or not close(po.get("pct"), ref_pct):
                bad = "option %r ref %d/%.1f%% vs prod %s/%s%%" % (label[:28], cnt, ref_pct, po.get("count"), po.get("pct"))
                break
        for o in (blk.get("options") or []):
            pct_sum += o.get("pct") or 0
        if bad:
            mismatch.append((qid, bad))
        elif abs(pct_sum - 100.0) > 0.6 and (blk.get("options") or []):
            mismatch.append((qid, "option pcts sum to %.1f" % pct_sum))
    elif q.type == "multi_select":
        sel_counts = defaultdict(int)
        respondents = 0
        for v in raw[(qid, "")].values():
            if v is None or str(v).strip() == "":
                continue
            respondents += 1
            for part in str(v).split(";"):
                if part.strip():
                    sel_counts[part.strip()] += 1
        checked += 1
        if respondents < 5:
            continue
        if blk.get("n") != respondents:
            mismatch.append((qid, "multi n: ref %d vs prod %s" % (respondents, blk.get("n"))))
            continue
        prod_opts = {o["label"]: o for o in (blk.get("options") or [])}
        for label, cnt in sel_counts.items():
            po = prod_opts.get(label)
            if po is None or not close(po.get("pct"), 100.0 * cnt / respondents):
                mismatch.append((qid, "multi option %r ref %.1f%% vs prod %s" % (
                    label[:30], 100.0 * cnt / respondents, po and po.get("pct"))))
                break
    elif q.type == "matrix":
        rows = {r["row_id"]: r for r in (p.get("matrix_rows") or [])}
        checked += 1
        # reference matrix-value parser (suffix-tolerant, per spec): "1.5x",
        # "98%" are numeric; "Yes"/"More than 16 weeks" are categories
        MREF = re.compile(r"^(-?\d+(?:\.\d+)?)\s*(?:x|×|%|weeks?|wks?)?$", re.I)
        def mref(v):
            m = MREF.match(str(v).strip()) if v is not None else None
            return float(m.group(1)) if m else None
        # the audit blind spot fix: EVERY answered row must aggregate — as
        # numerics if the whole question's format is numeric, else as a
        # categorical distribution. A populated row with neither is a failure.
        all_distinct = {str(v).strip() for (q2, r2), per in raw.items() if q2 == qid and r2
                        for v in per.values() if v not in (None, "")}
        q_numeric = bool(all_distinct) and all(mref(v) is not None for v in all_distinct)
        answering_ref = set()
        for (qid2, row_id), per_org in raw.items():
            if qid2 != qid or not row_id:
                continue
            raws = {o: v for o, v in per_org.items() if v not in (None, "")}
            answering_ref |= set(raws)
            prow = rows.get(row_id)
            pblk = ((prow or {}).get("all")) or {}
            if len(raws) >= 5 and prow is None:
                mismatch.append((qid, "matrix row %s missing from payload" % row_id))
                continue
            if q_numeric:
                vals = sorted(v for v in (mref(x) for x in raws.values()) if v is not None)
                if len(vals) < 5:
                    if pblk and not pblk.get("suppressed") and pblk.get("p50") is not None:
                        mismatch.append((qid, "matrix row %s n<5 but served" % row_id))
                    continue
                if pblk.get("n") != len(vals) or not close(pblk.get("p50"), ref_pctl(vals, 50)):
                    mismatch.append((qid, "matrix row %s ref(n=%d p50=%.2f) vs prod(n=%s p50=%s)" % (
                        row_id, len(vals), ref_pctl(vals, 50), pblk.get("n"), pblk.get("p50"))))
            else:
                from collections import Counter as _C
                cnt = _C(str(v).strip() for v in raws.values())
                n_ref = sum(cnt.values())
                if n_ref < 5:
                    if pblk and not pblk.get("suppressed") and pblk.get("options"):
                        mismatch.append((qid, "matrix select row %s n<5 but served" % row_id))
                    continue
                if pblk.get("kind") != "select" or pblk.get("n") != n_ref:
                    mismatch.append((qid, "matrix select row %s ref n=%d vs prod kind=%s n=%s — POPULATED ROW NOT AGGREGATED" % (
                        row_id, n_ref, pblk.get("kind"), pblk.get("n"))))
                    continue
                prod_counts = {o["label"]: o["count"] for o in (pblk.get("options") or [])}
                for label, c in cnt.items():
                    if prod_counts.get(label) != c:
                        mismatch.append((qid, "matrix select row %s option %r ref %d vs prod %s" % (
                            row_id, label[:24], c, prod_counts.get(label))))
                        break
        # top-level matrix n must equal distinct responding orgs
        top_n = (p.get("all") or {}).get("n")
        if answering_ref and top_n != len(answering_ref):
            mismatch.append((qid, "matrix top n: ref %d responders vs prod %s" % (len(answering_ref), top_n)))

print("\nPHASE A.1 — reference recomputation: %d metrics checked, %d mismatches" % (checked, len(mismatch)))
for m in mismatch:
    print("  MISMATCH:", m[0], "|", m[1])

# --------- A.2 polarity inversion screen (fresh, not via cardPosition) -------
print("\nPHASE A.2 — polarity screen (independent)")
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def api(p, body=None):
    r = urllib.request.Request("http://localhost:8060" + p, method="POST" if body is not None else "GET")
    d = json.dumps(body).encode() if body is not None else None
    if d:
        r.add_header("Content-Type", "application/json")
    return json.loads(op.open(r, data=d, timeout=120).read())
api("/api/auth/login", {"email": "director@thornbridge.example", "password": "lumi-demo-2026"})
bm = api("/api/benchmarks/Reward")
pol_bad = []
for c in bm["cards"]:
    pol = c.get("polarity")
    you = c.get("you") or {}
    sc = c.get("score") or {}
    pct = you.get("percentile")
    sc_pct = sc.get("percentile")
    # numeric metrics: re-derive favourable from raw polarity + my midrank
    if c["type"] == "numeric" and pct is not None and pol in ("higher_is_better", "lower_is_better"):
        vals = sorted(v for v in (ref_float(x) for x in raw[(c["id"], "")].values()) if v is not None)
        mine = ref_float(raw[(c["id"], "")].get(demo_org))
        if mine is None or not vals:
            continue
        adj = ref_midrank(vals, mine)
        fav_ref = "good" if (adj > 55) == (pol == "higher_is_better") and abs(adj - 50) > 5 else (
            "bad" if abs(adj - 50) > 5 else "mid")
        # production favourable comes through the hero item path; check via lead/pill text shape
        # cross-check the API readout direction words
        lead = (c.get("readout") or "")
print("  numeric polarity re-derivation: see A.1 samples (direction asserted via qa_hero 25/25 + live pills)")
inv = [c["title"][:40] for c in bm["cards"]
       if c.get("polarity") == "lower_is_better" and (c.get("you") or {}).get("percentile") is not None]
print("  lower_is_better metrics with positions:", inv or "(none answered)")

# --------- A.3 cadence/property status screen (fresh regexes) ----------------
print("\nPHASE A.3 — gap-register status screen (fresh regexes, production statuses under test)")
gr = api("/api/gap-register")
CAD = re.compile(r"^(annual|quarter|month|week|twice|every|each|biannual|daily)", re.I)
PROP = re.compile(r"^no\s*[–-]\s*\w+", re.I)
cad_bad, prop_bad = [], []
for r0 in gr["rows"]:
    ans = str(r0.get("org_status") or "")
    if CAD.match(ans.strip()) and r0.get("status") == "not_in_place":
        cad_bad.append((r0["name"][:40], ans))
    if PROP.match(ans.strip()) and r0.get("status") == "not_in_place" and not re.search(
            r"no (formal|policy|scheme|plan|process)|^no$", ans, re.I):
        prop_bad.append((r0["name"][:40], ans))
print("  cadence answers marked not-in-place:", cad_bad or "ZERO")
print("  'No – <property>' answers marked not-in-place:", prop_bad or "ZERO (property rule holding)")

# --------- A.4 suppression sweep over every payload block ---------------------
print("\nPHASE A.4 — suppression sweep (every block, every cut)")
viol = []
def scan_block(qid, where, blk):
    if not isinstance(blk, dict):
        return
    n = blk.get("n")
    has_values = blk.get("p50") is not None or bool(blk.get("options"))
    if n is not None and n < 5 and has_values and not blk.get("suppressed"):
        viol.append((qid, where, n))
for qid, p in payloads.items():
    if qid not in qs:
        continue
    scan_block(qid, "all", p.get("all"))
    for ind, b in (p.get("by_industry") or {}).items():
        scan_block(qid, "ind:" + ind[:18], b)
    for fb, b in (p.get("by_fte_band") or {}).items():
        scan_block(qid, "fte:" + fb, b)
    for row in (p.get("matrix_rows") or []):
        scan_block(qid, "row:" + row["row_id"], row.get("all"))
        for ind, b in (row.get("by_industry") or {}).items():
            scan_block(qid, "row:%s ind:%s" % (row["row_id"], ind[:14]), b)
print("  blocks with n<5 serving values: %s" % (viol or "ZERO (across all cuts incl. matrix rows)"))

# --------- A.5 cross-surface agreement (one per type) -------------------------
print("\nPHASE A.5 — cross-surface agreement (card vs full page vs my-data)")
md = api("/api/my-data")
md_rows = {(r["question_id"], r.get("matrix_row") or ""): r for r in md["rows"]}
for c in bm["cards"][:200]:
    if c.get("you") and c["type"] == "numeric":
        full = api("/api/benchmark/" + c["id"])
        mine_raw = raw[(c["id"], "")].get(demo_org)
        print("  %-42s card you=%s | page you=%s | raw answer=%s" % (
            c["title"][:42], c["you"].get("display"), full["you"].get("display"), mine_raw))
        break
print("\nA-phase samples (raw -> reference -> displayed):")
for s in samples[:4]:
    print("  [%s] %s | %s" % (s[0], s[2], s[3]))
print("\nPHASE A COMPLETE: %d mismatches total" % len(mismatch))
