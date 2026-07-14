# -*- coding: utf-8 -*-
"""DIFF 2 — Classification & polarity (market/practice) + the G&T competitiveness flag,
ratified 2026-07-14 (DECISIONS: Diff 2 scope, veto-gate rulings, headline rulings,
apply-gate rulings). One fix class: classification/polarity metadata.

Write-set (three authority files, read directly — nothing inlined):
  - lumi_reclassification_market_v_practice.csv (131 rows; the 38 REW263 placeholder
    rows are skipped here and executed from the ratified-gate artifact below)
  - diff2_addendum_generated.csv (61 rows incl. REW_FAI_079's ruled polarity flip)
  - diff2_rew263_ratified.csv (the 38-row full-text gate outcome, ratified 31M/7P)

Writes: data/market_position_config.json metrics{class,type,direction} + _domains
G&T competitiveness=true; questions.polarity for ↑ flips; lumi_questions.csv polarity
column. NEVER answers/answers_history (content-hash asserted). Final assertion: for
every live id in register v4, cfg market-ness == register classification (REW_PAY_005
strategy-config maps to practice-class; Diff-3 retirees absent from the register skip).
Double-guarded: --write --confirmed-by-david.
"""
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import app as A                      # noqa: E402
from db import get_conn              # noqa: E402

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
RECL = os.path.join(ROOT, "lumi_reclassification_market_v_practice.csv")
ADDENDUM = os.path.join(ROOT, "diff2_addendum_generated.csv")
REW263 = os.path.join(ROOT, "diff2_rew263_ratified.csv")
REGISTER = os.path.join(ROOT, "lumi_master_metric_register_FINAL_APPROVED.csv")
MP_CONFIG = os.path.join(ROOT, "data", "market_position_config.json")
QUESTIONS_CSV = os.path.join(ROOT, "data", "lumi_questions.csv")


def answers_hash(conn):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM %s "
                                "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


def costctx(direction):
    d = (direction or "").lower()
    return "cost" in d or "save-lens" in d or d.startswith("context")


def main():
    vis = A.visible_questions()
    conn = get_conn()
    cfg = json.load(open(MP_CONFIG))
    reg = {r["metric_id"]: r for r in csv.DictReader(open(REGISTER))}

    # ---- build the write-set from the three authorities -----------------------
    cls_writes, pol_writes = {}, {}

    def market_shape(q, klass):
        return {"class": klass,
                "type": "binary" if klass == "Provision" else ("numeric" if q.type in ("numeric", "matrix") else "ordinal"),
                "direction": "higher_is_better"}

    recl = [r for r in csv.DictReader(open(RECL, encoding="utf-8-sig"))
            if not r["metric_id"].startswith("REW263_")]
    for r in recl:
        qid = r["metric_id"]
        q = vis[qid]
        if r["proposed"] == "practice":
            cls_writes[qid] = {"class": "Practice"}
        elif costctx(r["direction"]):
            cls_writes[qid] = {"class": "Level", "direction": "neutral",
                               "type": "numeric" if q.type in ("numeric", "matrix") else "ordinal"}
        else:
            klass = "Provision" if "provision" in r["direction"].lower() else "Level"
            cls_writes[qid] = market_shape(q, klass)
            if q.polarity != "higher_is_better":
                pol_writes[qid] = "higher_is_better"
    for r in csv.DictReader(open(REW263)):
        qid = r["metric_id"]
        if r["ratified_class"] == "Practice":
            cls_writes[qid] = {"class": "Practice"}
        else:
            cls_writes[qid] = market_shape(vis[qid], r["ratified_class"])
            if vis[qid].polarity != "higher_is_better":
                pol_writes[qid] = "higher_is_better"
    for r in csv.DictReader(open(ADDENDUM)):
        qid = r["metric_id"]
        cls_writes[qid] = {"class": r["proposed_class"], "type": r["cfg_type"],
                           "direction": r["cfg_direction"]}
        if r["polarity_write"]:
            pol_writes[qid] = r["polarity_write"]

    # ---- reconciliation gate (standing, ruling 4 of the conflict rulings) -----
    missing = sorted(set(cls_writes) - set(vis))
    if missing:
        sys.exit("REFUSED: write-set ids not live: %s" % missing[:5])

    print("write-set: %d config-class writes, %d polarity writes" % (len(cls_writes), len(pol_writes)))
    if not WRITE:
        # dry-run: derived after-book vs register v4
        after_m = sum(1 for qid in vis
                      if (cls_writes.get(qid, cfg["metrics"].get(qid) or {}).get("class")) in ("Level", "Provision"))
        print("DRY: derived after market on live-243 = %d (register target 203)" % after_m)
        print("DRY RUN — pass --write --confirmed-by-david to execute")
        return

    h0 = answers_hash(conn)

    # 1. mp_config
    for qid, w in cls_writes.items():
        ent = dict(cfg["metrics"].get(qid) or {"lens": "attract", "weight": 1})
        ent.update(w)
        cfg["metrics"][qid] = ent
    cfg["_domains"]["Governance & Transparency"]["competitiveness"] = True   # apply-gate ruling
    json.dump(cfg, open(MP_CONFIG, "w"), indent=2, ensure_ascii=False)
    print("mp_config: %d metric entries updated + G&T competitiveness=true" % len(cls_writes))

    # 2. questions.polarity
    n = 0
    for qid, p in pol_writes.items():
        n += conn.execute("UPDATE questions SET polarity=? WHERE id=?", (p, qid)).rowcount
    conn.commit()
    print("DB polarity writes:", n)

    # 3. lumi_questions.csv polarity column
    with open(QUESTIONS_CSV, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames
        rows = list(rdr)
    ncsv = 0
    for r in rows:
        if r.get("id") in pol_writes and "polarity" in r:
            r["polarity"] = pol_writes[r["id"]]
            ncsv += 1
    with open(QUESTIONS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("lumi_questions.csv polarity updates:", ncsv)

    # 4. append-only + book assertions
    assert answers_hash(conn) == h0, "ANSWER TABLES MOVED — restore from backup NOW"
    print("answers/answers_history content hash IDENTICAL")
    bad = []
    for qid in vis:
        r = reg.get(qid)
        if r is None:
            continue          # Diff-3 retirees, absent from the register by design
        cfg_market = (cfg["metrics"].get(qid) or {}).get("class") in ("Level", "Provision")
        want = {"market": True, "practice": False, "strategy-config": False}[r["classification"]]
        if cfg_market != want:
            bad.append((qid, r["classification"], cfg_market))
    assert not bad, "cfg vs register-v4 divergence AFTER apply: %s" % bad[:5]
    from collections import Counter
    tally = Counter((cfg["metrics"].get(qid) or {}).get("class") in ("Level", "Provision") for qid in vis)
    print("derived live-243 book after: market %d / practice-class %d (register target 203 + retirees/strategy-config)"
          % (tally[True], tally[False]))
    print("cfg == register v4 for every live registered id.")


if __name__ == "__main__":
    main()
