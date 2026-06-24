# -*- coding: utf-8 -*-
"""Snapshot gauge + per-domain verdicts for a fixed org x cut set — the
before/after harness for wiring the market-position config into the engine.

Computes the hero via the IDENTICAL path /api/overview uses (build_items +
hero_signals), so the snapshot equals what users see. Run BEFORE the engine
change to capture the baseline, then AFTER to diff:

    python3 server/mp_baseline.py mp_baseline_before.json
    python3 server/mp_baseline.py mp_baseline_after.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app                       # noqa: E402  (defines the engine helpers + constants)
import positions as pos          # noqa: E402
from db import get_conn          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pass the classification config so the snapshot reflects the wired engine.
# Set MP_LEGACY=1 to reproduce the pre-wiring baseline (polarity-only path).
MP_CONFIG = None if os.environ.get("MP_LEGACY") else pos.market_position_config()


def org_by_name(conn, name):
    r = conn.execute("SELECT * FROM orgs WHERE name=?", (name,)).fetchone()
    return dict(r) if r else None


def compute(org, cut):
    """The overview's hero computation, verbatim (app.py:1297-1313)."""
    items, tb = app.build_items(None, org, None, cut)
    visq = app.org_visible_questions(org)
    ans = app.org_answers_for(org)
    ent = app.make_entitled(None, org)
    prev_items = pos.prevalence_items(org["org_id"], cut, visq, app.payloads(), ans, ent, tb)
    prac_items = pos.practice_position_items(org["org_id"], cut, visq, app.payloads(), ans, ent, tb)
    sec_order = []
    for q in visq.values():
        if q.sub_power and q.sub_power not in sec_order:
            sec_order.append(q.sub_power)
    sec_order.sort(key=lambda x: min(q.sub_power_order or 999 for q in visq.values() if q.sub_power == x))
    hero = pos.hero_signals(items, prev_items, sec_order, app.MARKET_BAND_LOW, app.MARKET_BAND_HIGH,
                            app.DOMAIN_MIN_POLARISED, app.VERDICT_NET_LEAN, app.UNCOMMON_PCT,
                            practice_items=prac_items, tile_min=app.TILE_MIN_POSITIONED,
                            mp_config=MP_CONFIG)
    summ = pos.overview_summary(items, mp_config=MP_CONFIG, practice_items=prac_items)
    headline = {"comparable": summ["comparable_metrics"], "above_median": summ["above_median"],
                "below_median": summ["below_median"], "broadly_in_line": summ["broadly_in_line"]}
    m = hero.get("market") or {}
    gauge = {"verdict": m.get("verdict"), "below": m.get("below"), "on": m.get("at"),
             "above": m.get("above"), "pool": m.get("pool")}
    doms = []
    for d in hero["domains"]:
        p = d.get("position") or {}
        ev = d.get("position_evidence") or {}
        doms.append({"name": d["name"], "verdict": p.get("verdict"), "basis": d.get("position_basis"),
                     "below": p.get("below"), "on": p.get("at"), "above": p.get("above"),
                     "pool": p.get("pool"), "polarised": ev.get("polarised"),
                     "practice": ev.get("practice"), "market_eligible": d.get("market_eligible")})
    return {"gauge": gauge, "headline": headline, "domains": doms}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "mp_baseline_before.json"
    conn = get_conn()
    th = org_by_name(conn, "Thornbridge Retail Group plc")
    ab = org_by_name(conn, "Ardenbank Industries Ltd")          # Manufacturing, 10,000+
    al = org_by_name(conn, "Alderstead Trust")                  # Healthcare, 250-999
    cases = [
        ("Thornbridge", th, {"dim": "all", "value": None}, "All"),
        ("Thornbridge", th, {"dim": "industry", "value": "Charity, Non-Profit & Social Enterprise"}, "Charity-thin"),
        ("Ardenbank(Mfg,10k+)", ab, {"dim": "all", "value": None}, "All"),
        ("Ardenbank(Mfg,10k+)", ab, {"dim": "industry", "value": "Manufacturing & Engineering"}, "Manufacturing"),
        ("Alderstead(Health,250-999)", al, {"dim": "all", "value": None}, "All"),
        ("Alderstead(Health,250-999)", al, {"dim": "industry", "value": "Healthcare & Life Sciences"}, "Healthcare-thin"),
    ]
    snap = {}
    for label, org, cut, cutlabel in cases:
        if org is None:
            continue
        snap[label + " | " + cutlabel] = compute(org, cut)

    with open(os.path.join(ROOT, out_path), "w") as f:
        json.dump(snap, f, indent=2)
    for key, v in snap.items():
        g = v["gauge"]
        hl = v["headline"]
        print("\n%-32s GAUGE %-9s  below/on/above = %s/%s/%s  (pool %s)" % (
            key, g["verdict"], g["below"], g["on"], g["above"], g["pool"]))
        print("%-32s HEADLINE  above median %s of %s  (%s below · %s in line)" % (
            "", hl["above_median"], hl["comparable"], hl["below_median"], hl["broadly_in_line"]))
        for d in v["domains"]:
            print("    %-12s %-9s [%-10s] pol=%s prac=%s pool=%s" % (
                d["name"], d["verdict"], d["basis"], d["polarised"], d["practice"], d["pool"]))
    print("\n[written] %s" % out_path)


if __name__ == "__main__":
    main()
