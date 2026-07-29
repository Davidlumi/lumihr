# -*- coding: utf-8 -*-
"""migrate_gt_class6.py — the unresolved-six classification/scoring diff (David-ruled 2026-07-28,
"approved AS PROPOSED, all six (3 MARKET + 3 PRACTICE, per Claude Code's own table and row
names)"). CLASSIFICATION/SCORING class — never bundled with seed data.

  3 MARKET (score + authored pin; the Diff-17 score-map class):
    REW262_GOV_PAYINADVERTS   {NEVER:0, SOME_ROLES:50, ALL_ROLES:100}       dir +1
    REW262_GOV_EQUALPAYAUDIT  {NO:0, AD_HOC:33.33, ANNUALLY:66.67,
                               MORE_THAN_ANNUALLY:100}                      dir +1
    REW263_GOV_FLEXALLOW      {NO:0, LIMITED_CHOICE:50,
                               PERSONALISED_ALLOWANCE:100}                  dir +1
    is_scored=1; cfg polarity 'neutral' (the FAI_088/089 sibling convention — bands render
    without good/bad colouring; favourability upgrades are their own later ruling); mp config
    already Level/higher_is_better (asserted, untouched); db polarity hib kept (verdict rows).
    CONSEQUENCE: three metrics BEGIN rendering market verdicts — enumerated at rehearsal.
  3 PRACTICE (the Tier-2 re-route pattern, shield-compliant):
    REW263_GOV_UKPAYTRANS · REW26_GOV_EU_PTD_PREP · REW263_GOV_BENOBJ
    mp class -> Practice, direction -> null, _gt6_ruled note; db polarity hib -> neutral (the
    practice-shield's practice/value-stream rule); cfg polarity SET to 'neutral' (the INC_070
    lesson: supersede by setting, never leave directional/absent fields on Practice rows).
    They were already prevalence-routed (is_scored=0), so rendering is near-invariant —
    verified at rehearsal.

Dry-run default; --write; live needs --confirmed-by-david; non-live --db requires --mp-out.
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
MARKET = {
    "REW262_GOV_PAYINADVERTS": {"NEVER": 0.0, "SOME_ROLES": 50.0, "ALL_ROLES": 100.0},
    "REW262_GOV_EQUALPAYAUDIT": {"NO": 0.0, "AD_HOC": 33.33, "ANNUALLY": 66.67, "MORE_THAN_ANNUALLY": 100.0},
    "REW263_GOV_FLEXALLOW": {"NO": 0.0, "LIMITED_CHOICE": 50.0, "PERSONALISED_ALLOWANCE": 100.0},
}
PRACTICE = ["REW263_GOV_UKPAYTRANS", "REW26_GOV_EU_PTD_PREP", "REW263_GOV_BENOBJ"]
NOTE = ("classified per the Domain-7 unresolved-six ruling (David 2026-07-28, approved as "
        "proposed): composite/maturity/philosophy constructs carry no market direction")
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--mp-out", dest="mp_out", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write:
        if is_live and not a.confirmed:
            print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
        if not is_live and not a.mp_out:
            print("REFUSED: non-live --db requires --mp-out (r3sw7)"); sys.exit(2)
        if a.mp_out and os.path.abspath(a.mp_out) == LIVE_MP:
            print("REFUSED: --mp-out must not be the live config"); sys.exit(2)
    SIX = set(MARKET) | set(PRACTICE)
    assert len(SIX) == 6 and not (SIX & FROZEN8)
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    raw = open(LIVE_MP, "rb").read()
    mp = json.loads(raw); M = mp["metrics"]

    # ---- pre-state guards ----
    plans = {}
    for qid in SIX:
        r = c.execute("SELECT polarity, is_scored, scoring_config_json FROM questions WHERE id=?", (qid,)).fetchone()
        assert r["is_scored"] == 0, "%s unexpectedly scored" % qid
        assert r["polarity"] == "higher_is_better", "%s db polarity drifted" % qid
        assert M[qid].get("class") == "Level" and M[qid].get("direction") == "higher_is_better", qid
        cfg = json.loads(r["scoring_config_json"] or "{}")
        assert "direction" not in cfg and cfg.get("scoring_method") != "option_scores", qid
        plans[qid] = cfg
    import copy
    before = copy.deepcopy(M)
    for qid in PRACTICE:
        M[qid]["class"] = "Practice"; M[qid]["direction"] = None; M[qid]["_gt6_ruled"] = NOTE
    for qid in before:
        if qid in PRACTICE:
            assert all(M[qid].get(k) == before[qid].get(k) for k in before[qid]
                       if k not in ("class", "direction", "_gt6_ruled")), qid
        else:
            assert before[qid] == M[qid], "non-target mp entry changed: %s" % qid
    new_mp = json.dumps(mp, indent=2, ensure_ascii=False).encode()

    print("gt-class6 %s (db=%s, mp_out=%s)" % ("APPLY" if a.write else "dry-run",
                                               os.path.basename(a.db), a.mp_out or "LIVE"))
    for qid, sc in MARKET.items():
        print("  MARKET   %-26s score map %s + dir +1 + cfgpol neutral + is_scored=1" % (qid, sc))
    for qid in PRACTICE:
        print("  PRACTICE %-26s mp Level/hib -> Practice/null + db polarity neutral + cfgpol neutral" % qid)
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for qid, sc in MARKET.items():
        cfg = dict(plans[qid])
        cfg["curve_type"] = cfg.get("curve_type") or "linear"
        cfg["scoring_method"] = "option_scores"
        cfg["option_scores"] = sc
        cfg["na_codes"] = cfg.get("na_codes") or []
        cfg["polarity"] = "neutral"
        cfg["direction"] = 1
        cur.execute("UPDATE questions SET scoring_config_json=?, is_scored=1 WHERE id=?",
                    (json.dumps(cfg, ensure_ascii=False), qid))
    for qid in PRACTICE:
        cfg = dict(plans[qid]); cfg["polarity"] = "neutral"
        cur.execute("UPDATE questions SET scoring_config_json=?, polarity='neutral' WHERE id=?",
                    (json.dumps(cfg, ensure_ascii=False), qid))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED — classification diff touches no answers"
    others = {r["id"]: (r["scoring_config_json"], r["polarity"], r["is_scored"]) for r in
              c.execute("SELECT id, scoring_config_json, polarity, is_scored FROM questions") if r["id"] not in SIX}
    c.commit()
    others2 = {r["id"]: (r["scoring_config_json"], r["polarity"], r["is_scored"]) for r in
               c.execute("SELECT id, scoring_config_json, polarity, is_scored FROM questions") if r["id"] not in SIX}
    assert others == others2
    dst = a.mp_out if a.mp_out else LIVE_MP
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dst)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_mp)
    os.replace(tmp, dst)
    print(json.dumps({"applied": True, "live": is_live, "market_scored": sorted(MARKET),
                      "practice_rerouted": PRACTICE, "mp_target": os.path.basename(dst),
                      "answers_book": "byte-identical"}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
