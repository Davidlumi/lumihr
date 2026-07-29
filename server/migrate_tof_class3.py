# -*- coding: utf-8 -*-
"""migrate_tof_class3.py — Domain-8 B3/B4 classification routings (CLASSIFICATION class; David-ruled
2026-07-29, "go on ③+④"). Three metrics leave the market pool; ZERO answer writes.

  REW_BEN_FAM_007        -> PRACTICE — CARERPAID owns the paid-carer's-leave construct (its arms map
                           the anchor's paid-vs-statutory-unpaid split; FAM_007's 6.4% is the outlier
                           against every published figure).
  REW262_TIME_SICKDAYONE -> PRACTICE — SICK_004 owns the day-one-OSP construct. THE FREEZE IS NOT
                           TOUCHED: a class change moves no answers, and the frozen target
                           {Yes 0.6091, No 0.3909} n 220 equals the live distribution exactly
                           (asserted below). No unfreeze cycle occurs.
  REW263_TIME_DAYONELEAVE-> PRACTICE (verdict suppression) — compliance with a day-one statutory
                           right (gov.uk: "You're eligible for Paternity Leave from the first day of
                           employment") is not a market position; its 86 "below-market" verdicts are
                           suppressed. Its cfg polarity is directional TODAY and is neutralised here
                           for practice-shield (check-5) compliance.

Per metric: mp class -> Practice, direction -> null, `_tof3_ruled` note; DB polarity hib -> neutral;
scoring_config polarity -> neutral where directional (the INC_070 lesson: supersede by SETTING
neutral, never by deleting or leaving a directional field on a Practice row).

NOT REPAIRED HERE, stated plainly: the 77 carer's answer-level contradictions (FAM_007 x CARERPAID)
survive this routing — routing changes authority, not answers. They stay queued for the seed work,
which is BLOCKED on the gm marginal rulings (see the DECISIONS record).

Dry-run default; --write; live needs --confirmed-by-david; non-live --db requires --mp-out.
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
THREE = ["REW_BEN_FAM_007", "REW262_TIME_SICKDAYONE", "REW263_TIME_DAYONELEAVE"]
NOTE = {
    "REW_BEN_FAM_007": ("PRACTICE per the Domain-8 duplicate-construct ruling (David 2026-07-29): "
                        "REW263_TIME_CARERPAID owns the paid-carer's-leave construct; this row's 6.4% "
                        "is the outlier against every published figure. The 77 answer-level "
                        "contradictions are NOT repaired by this routing — queued to the seed work."),
    "REW262_TIME_SICKDAYONE": ("PRACTICE per the Domain-8 duplicate-construct ruling (David 2026-07-29): "
                               "REW_BEN_SICK_004 owns day-one OSP. Class change only — the frozen "
                               "distribution is untouched and no unfreeze cycle occurs."),
    "REW263_TIME_DAYONELEAVE": ("PRACTICE / verdict-suppressed per the Domain-8 ruling (David 2026-07-29): "
                                "compliance with a day-one statutory right (gov.uk paternity-leave "
                                "eligibility, verified 2026-07-29) is not a market position; 86 "
                                "'below-market' verdicts suppressed. Its answer vector is byte-identical "
                                "to SICKDAYONE's (seed-cloning artifact, ACCEPTED AND RECORDED, not fixed)."),
}
FROZEN_TGT = {"Yes": 0.6091, "No": 0.3909}


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
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    mp = json.loads(open(LIVE_MP, "rb").read()); M = mp["metrics"]

    # ---- pre-state guards ----
    plans = {}
    for qid in THREE:
        r = c.execute("SELECT polarity, is_scored, scoring_config_json FROM questions WHERE id=?", (qid,)).fetchone()
        assert r["polarity"] == "higher_is_better", "%s db polarity drifted: %s" % (qid, r["polarity"])
        assert M[qid].get("class") in ("Level", "Provision") and M[qid].get("direction") == "higher_is_better", qid
        cfg = json.loads(r["scoring_config_json"] or "{}")
        plans[qid] = cfg
    # the freeze proof: class change cannot move a distribution — assert live == frozen target first
    fz = json.load(open(os.path.join(ROOT, "frozen_targets.json")))["REW262_TIME_SICKDAYONE"]
    vals = [v for (v,) in c.execute("SELECT value FROM answers WHERE question_id='REW262_TIME_SICKDAYONE' "
                                    "AND COALESCE(value,'')!=''")]
    live_dist = {k: round(sum(1 for v in vals if v == k) / len(vals), 4) for k in ("Yes", "No")}
    assert live_dist == FROZEN_TGT == {k: round(v, 4) for k, v in fz["dist"].items()} and len(vals) == fz["n"], \
        "SICKDAYONE freeze pre-state drifted: %s vs %s" % (live_dist, fz["dist"])

    import copy
    before = copy.deepcopy(M)
    for qid in THREE:
        M[qid]["class"] = "Practice"; M[qid]["direction"] = None; M[qid]["_tof3_ruled"] = NOTE[qid]
    for qid in before:
        if qid in THREE:
            assert all(M[qid].get(k) == before[qid].get(k) for k in before[qid]
                       if k not in ("class", "direction", "_tof3_ruled")), qid
        else:
            assert before[qid] == M[qid], "non-target mp entry changed: %s" % qid
    new_mp = json.dumps(mp, indent=2, ensure_ascii=False).encode()

    print("tof-class3 %s (db=%s, mp_out=%s) — 3 routings, ZERO answer writes"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db), a.mp_out or "LIVE"))
    for qid in THREE:
        cfgpol = (plans[qid] or {}).get("polarity")
        print("  %-26s %s/hib -> Practice/null | db polarity -> neutral%s"
              % (qid, before[qid].get("class"), " | cfg polarity %s -> neutral" % cfgpol if cfgpol not in (None, "neutral") else ""))
    print("  freeze proof: SICKDAYONE live == frozen target %s (n=%d) — class change moves no answers" % (live_dist, len(vals)))
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for qid in THREE:
        cfg = dict(plans[qid])
        if cfg.get("polarity") not in (None, "neutral"):
            cfg["polarity"] = "neutral"
            cur.execute("UPDATE questions SET scoring_config_json=?, polarity='neutral' WHERE id=?",
                        (json.dumps(cfg, ensure_ascii=False), qid))
        else:
            cur.execute("UPDATE questions SET polarity='neutral' WHERE id=?", (qid,))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED — this is a classification diff"
    others = {r["id"]: (r["scoring_config_json"], r["polarity"], r["is_scored"]) for r in
              c.execute("SELECT id, scoring_config_json, polarity, is_scored FROM questions") if r["id"] not in THREE}
    c.commit()
    others2 = {r["id"]: (r["scoring_config_json"], r["polarity"], r["is_scored"]) for r in
               c.execute("SELECT id, scoring_config_json, polarity, is_scored FROM questions") if r["id"] not in THREE}
    assert others == others2, "non-target question row changed"
    vals2 = [v for (v,) in c.execute("SELECT value FROM answers WHERE question_id='REW262_TIME_SICKDAYONE' "
                                     "AND COALESCE(value,'')!=''")]
    assert vals2 == vals, "SICKDAYONE ANSWERS MOVED — the freeze must be untouched"
    dst = a.mp_out if a.mp_out else LIVE_MP
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dst)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_mp)
    os.replace(tmp, dst)
    print(json.dumps({"applied": True, "live": is_live, "routed": THREE,
                      "freeze": "SICKDAYONE distribution byte-identical; no unfreeze cycle",
                      "carers_77": "NOT repaired by this routing — queued to the blocked seed work",
                      "answers_book": "byte-identical", "mp_target": os.path.basename(dst)}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
