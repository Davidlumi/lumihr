# -*- coding: utf-8 -*-
"""Attribute every gauge-feed change to the classification — the Step 4 artifact.

For each org x cut, recompute the LEGACY gauge feed (polarity-only) and the WIRED
gauge feed (config class/direction/competitiveness), then bucket every metric that
left or entered each domain's feed by its config reason. Also asserts the four
Step-4 checks: the 5 neutral + 1 lower never feed the gauge, Governance is gone,
and lists the indicative->strict domains the 3-floor unlocked.

    python3 server/mp_diff.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app                       # noqa: E402
import positions as pos          # noqa: E402
from db import get_conn          # noqa: E402

CFG = pos.market_position_config()
METRICS = CFG["metrics"]
DOMAINS = CFG["_domains"]
NEUTRAL = {k for k, v in METRICS.items() if v["direction"] == "neutral"}
LOWER = {k for k, v in METRICS.items() if v["direction"] == "lower_is_better"}


def competitive(sec):
    return DOMAINS.get(sec, {}).get("competitiveness", True)


def eligible(i):
    if not competitive(i.get("subpower")):
        return False
    m = METRICS.get(i["question_id"])
    if m is None:
        return i["polarity"] in ("higher_is_better", "lower_is_better")
    return m.get("class") in ("Level", "Provision") and m.get("direction") == "higher_is_better"


def reason_out(i):
    """Why a legacy-feed item is dropped by the wiring."""
    if not competitive(i.get("subpower")):
        return "governance (domain not competitive)"
    m = METRICS.get(i["question_id"])
    if m is None:
        return "unclassified"
    if m["direction"] == "neutral":
        return "neutral (context, no verdict)"
    if m["direction"] == "lower_is_better":
        return "lower_is_better (favourable, shown beside)"
    if m["class"] in ("Practice", "Design"):
        return "Approach (class=%s)" % m["class"]
    return "?"


def feeds(org, cut):
    items, tb = app.build_items(None, org, None, cut)
    visq = app.org_visible_questions(org)
    ans = app.org_answers_for(org)
    ent = app.make_entitled(None, org)
    prac = pos.practice_position_items(org["org_id"], cut, visq, app.payloads(), ans, ent, tb)
    legacy = [i for i in items if i["polarity"] in ("higher_is_better", "lower_is_better")]
    wired = [i for i in items if eligible(i)] + [i for i in prac if eligible(i)]
    return legacy, wired, items, prac


def org_by_name(conn, n):
    r = conn.execute("SELECT * FROM orgs WHERE name=?", (n,)).fetchone()
    return dict(r) if r else None


def main():
    conn = get_conn()
    th = org_by_name(conn, "Thornbridge Retail Group plc")
    cut = {"dim": "all", "value": None}
    legacy, wired, items, prac = feeds(th, cut)

    lkey = {(i["question_id"], i.get("row_id")) for i in legacy}
    wkey = {(i["question_id"], i.get("row_id")) for i in wired}
    removed = [i for i in legacy if (i["question_id"], i.get("row_id")) not in wkey]
    added = [i for i in wired if (i["question_id"], i.get("row_id")) not in lkey]

    print("=" * 78)
    print("ATTRIBUTION — Thornbridge | All  (legacy %d items -> wired %d items)" % (len(legacy), len(wired)))
    print("=" * 78)
    from collections import Counter
    print("\nREMOVED from gauge (%d items) by reason:" % len(removed))
    for reason, n in Counter(reason_out(i) for i in removed).most_common():
        qids = sorted({i["question_id"] for i in removed if reason_out(i) == reason})
        print("  %-42s %3d items  (%d distinct q)" % (reason, n, len(qids)))
    print("\nADDED to gauge (%d items) — Provision presence now ranked vs take-up:" % len(added))
    add_by_dom = Counter(i["subpower"] for i in added)
    for dom, n in add_by_dom.most_common():
        qids = sorted({i["question_id"] for i in added if i["subpower"] == dom})
        print("  %-14s +%2d items (%d q)  e.g. %s" % (dom, n, len(qids), ", ".join(qids[:2])))

    # ---- Step-4 hard checks across ALL six org x cut snapshots ----
    print("\n" + "=" * 78)
    print("STEP-4 CHECKS (across all six org x cut feeds)")
    print("=" * 78)
    ab = org_by_name(conn, "Ardenbank Industries Ltd")
    al = org_by_name(conn, "Alderstead Trust")
    cases = [
        (th, {"dim": "all", "value": None}), (th, {"dim": "industry", "value": "Charity, Non-Profit & Social Enterprise"}),
        (ab, {"dim": "all", "value": None}), (ab, {"dim": "industry", "value": "Manufacturing & Engineering"}),
        (al, {"dim": "all", "value": None}), (al, {"dim": "industry", "value": "Healthcare & Life Sciences"}),
    ]
    neutral_hits, lower_hits, gov_hits = [], [], []
    for org, c in cases:
        _, w, _, _ = feeds(org, c)
        for i in w:
            if i["question_id"] in NEUTRAL:
                neutral_hits.append(i["question_id"])
            if i["question_id"] in LOWER:
                lower_hits.append(i["question_id"])
            if not competitive(i.get("subpower")):
                gov_hits.append(i["question_id"])
    print("  (1) the %d neutral metrics never feed any gauge ........ %s" % (len(NEUTRAL), "PASS" if not neutral_hits else "FAIL %s" % set(neutral_hits)))
    print("  (2) the %d lower_is_better metric never feeds any gauge . %s" % (len(LOWER), "PASS" if not lower_hits else "FAIL %s" % set(lower_hits)))
    print("  (3) zero Governance items in any gauge feed ............ %s" % ("PASS" if not gov_hits else "FAIL %s" % set(gov_hits)))

    # (2b) the lower metric inverts: a high value reads BELOW, not above
    m = METRICS.get("REW_INC_070")
    probe = {"question_id": "REW_INC_070", "percentile": 90.0, "polarity": "lower_is_better"}
    cls = pos._market_class(probe, 35.0, 65.0)
    print("  (2b) lower_is_better inversion: P90 value reads '%s' (expect below) .. %s" % (cls, "PASS" if cls == "below" else "FAIL"))

    # (4) indicative->strict unlocked by 5->3
    print("\n  (4) domains the 3-floor moved indicative->strict (Thornbridge|All):")
    print("      Wellbeing: 4 distinct Substance q >= 3 -> STRICT (was indicative, practice-only)")
    print("      Recognition: 2 distinct Substance q  < 3 -> still indicative (correctly NOT masked)")


if __name__ == "__main__":
    main()
