# -*- coding: utf-8 -*-
"""migrate_aff_t2_reroutes.py — AFF TIER-2 APPLY, Part 1 (CLASSIFICATION class; David-ruled
2026-07-27, the joint pass; the Diff-18 pattern): the 13 PRACTICE re-routes.

(The ruling's header said "PRACTICE — 12"; the ruled NAME-LIST is 13 and partitions the 20-metric
Tier-2 roster exactly once — names govern, count corrected in-record, the 16→17 class.)

Per metric: mp-config class -> "Practice", direction -> null, `_tier2_ruled` note; DB polarity
neutralised (all 13 are directional hib — asserted). NO authored direction keys (ruled): under
the re-scoped census (authority policed where it renders — class not Practice/Design), the 13
exit the verdict scope; their regex-resolved scores are rendering-inert and printed by the
practice-scope census line, never invisible.

Consequences (enumerated at rehearsal, by design): all 13 currently render verdicts — every
org-metric verdict they carry leaves the market donut for the practice tally. Fixture answers
byte-held. Diff-15 apply ordering: ALL config asserts run before any DB commit; config staged to
temp, DB committed, config atomically replaced. Dry-run default; --write; live needs
--confirmed-by-david; non-live --db REQUIRES --mp-out (the r3sw7 staged-copy doctrine).
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
P13 = ["EXT_REW_GAP_009", "EXT_REW_GAP_003", "REW_BEN_REM_PAY_005", "REW_INC_135",
       "REW_BEN_HOL_007", "PROP_d992b2ea", "REW_PRO_030", "PROP_168a6213", "CAR_STATUS_01",
       "CAR_COST_02", "REW_INC_072", "REW_INC_131", "REW_BEN_SICK_006"]
NOTE = ("PRACTICE per the Tier-2 joint pass (David 2026-07-27): contested direction — "
        "the PAYCOMMS/PMIEXCESS precedent; no verdict renders, prevalence/alignment carries it")
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
            print("REFUSED: non-live --db requires --mp-out (r3sw7 staged-copy doctrine)"); sys.exit(2)
        if a.mp_out and os.path.abspath(a.mp_out) == LIVE_MP:
            print("REFUSED: --mp-out must not be the live config"); sys.exit(2)
    assert len(P13) == 13 and not (set(P13) & FROZEN8)

    raw = open(LIVE_MP, "rb").read()
    cfg = json.loads(raw); M = cfg["metrics"]
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)

    # ---- config asserts + staged edit (ALL before any DB commit — the Diff-15 lesson) ----
    import copy
    before = copy.deepcopy(M)
    for q in P13:
        assert M[q].get("class") in ("Level", "Provision"), "%s class drifted: %s" % (q, M[q].get("class"))
        assert M[q].get("direction") == "higher_is_better", "%s direction drifted" % q
        M[q]["class"] = "Practice"
        M[q]["direction"] = None
        M[q]["_tier2_ruled"] = NOTE
    for qid in before:
        if qid in P13:
            b, n = before[qid], M[qid]
            assert all(n.get(k) == b.get(k) for k in b if k not in ("class", "direction", "_tier2_ruled")), qid
        else:
            assert before[qid] == M[qid], "non-target config entry changed: %s" % qid
    new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()

    # ---- DB asserts ----
    pols = {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()[0] for q in P13}
    assert all(v == "higher_is_better" for v in pols.values()), "a re-route target is not directional: %s" % pols
    # scoring_config.polarity neutralised too (adversarial catch, 2026-07-27: Practice class
    # alone does NOT neutralise favourability — score_polarity reads THIS field, and
    # CAR_STATUS_01 (cfg hib, no unbenchmarked flag) leaked onto starter-layout gaps/strengths
    # and board-pack rows. The other 12 were shielded only by accident (cfg neutral or legacy
    # unbenchmarked flags). Neutralising the cfg field kills the favourability class-wide —
    # the ruled "polarity neutralised where directional" applied to the field the surfaces read.
    cfg_fix = {}
    for q in P13:
        sc = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (q,)).fetchone()[0])
        assert "direction" not in sc, "%s unexpectedly pinned" % q
        if sc.get("polarity") != "neutral":
            assert sc.get("polarity") == "higher_is_better", (q, sc.get("polarity"))
            sc["polarity"] = "neutral"
            cfg_fix[q] = sc

    print("aff-t2-reroutes %s (db=%s, mp_out=%s) — 13 PRACTICE re-routes (class+direction+note; DB polarity hib->neutral)"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db), a.mp_out or "LIVE"))
    for q in P13:
        print("  %-22s %s/hib -> Practice/null + polarity neutral" % (q, before[q].get("class")))
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for q in P13:
        cur.execute("UPDATE questions SET polarity='neutral' WHERE id=?", (q,))
    for q, sc in cfg_fix.items():
        cur.execute("UPDATE questions SET scoring_config_json=? WHERE id=?", (json.dumps(sc, ensure_ascii=False), q))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED"
    others = {r["id"]: r["polarity"] for r in c.execute("SELECT id, polarity FROM questions") if r["id"] not in P13}
    c.commit()
    others2 = {r["id"]: r["polarity"] for r in c.execute("SELECT id, polarity FROM questions") if r["id"] not in P13}
    assert others == others2
    dst = a.mp_out if a.mp_out else LIVE_MP
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dst)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_raw)
    os.replace(tmp, dst)
    print(json.dumps({"applied": True, "live": is_live, "reroutes": 13, "mp_target": os.path.basename(dst),
                      "db_polarity": "13x hib->neutral",
                      "cfg_polarity_neutralised": sorted(cfg_fix),
                      "answers_book": "byte-identical"}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
