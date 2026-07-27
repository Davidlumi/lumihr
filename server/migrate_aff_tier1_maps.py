# -*- coding: utf-8 -*-
"""migrate_aff_tier1_maps.py — THE AFF TIER-1 MAP DIFF (David 2026-07-26, "invert 9, amend 9,
confirm 3+4, paste tier 2"). SCORING-MAP class: rewrites questions.scoring_config_json for
EXACTLY 19 metrics (Tier 1A x9 INVERT + Tier 1B x9 AMEND + INC_070, whose Tier-3-ruled map amend
rides with its allow-list retirement per the ruling's own tally instruction). ZERO answer writes.
Tier 2's 20 rows are guarded untouchable.

THE MECHANISM (each fix proven effective under the CURRENT resolution order — aggregate.py
_score_direction :320-355, label branch :331-334, numband :335-341, applier score_answer :364+,
which renders effective = 100-authored when d=-1):
  - 16 metrics keep their label-branch d=-1 (first-_AFF or last-_NEG labels unchanged): the NEW
    authored map is PRE-COMPENSATED (authored = 100 - ruled_effective), so the engine's inversion
    lands exactly the ruled scores. These maps are deliberately in ENGINE COORDINATES — the later
    pins/engine diff rewrites them into direction-pinned natural maps; that dependency is exactly
    why the engine diff is queued.
  - PROP_3d4fc4e7: 'Not measured' -> na_code (RULED) removes it from the scoreable set, so the
    label branch no longer sees a _NEG last option; both remaining ends are _NUMBAND -> step 4 ->
    DB polarity higher_is_better -> d=+1 -> the NEW natural ascending map applies as authored.
  - REW_PAY_014: 'Other' -> na_code (RULED); remaining first option 'No premium' is _NEG-first ->
    d=+1 -> existing band scores apply as authored (values unchanged; only the tail moves to NA).
  - STALE-FIELD SWEEP (ruled): scoring_config.polarity == 'lower_is_better' found on EXACTLY TWO
    of the 19 — REW_FAI_079 and REW_INC_070 — both keys DELETED (superseded; inert today because
    the label branch pre-empts step 5, but they would fight the maps under the future engine).
    The other 17 carry 'neutral' x8 / 'higher_is_better' x9 — neither fights (step 5 only fires
    on lib); left untouched.

Verdict flips are EXPECTED and correct (backwards member-visible verdicts being fixed) — the
rehearsal enumerates them per metric; a zero-flip Tier-1A metric is a defect. Fixtures' ANSWERS
byte-held (their verdicts may flip — attributed). Dry-run default; --write; live needs
--confirmed-by-david.
"""
import argparse, hashlib, json, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
STAMP = "2026-07-26 aff-tier1-maps"
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
TIER2_HOLD = {"EXT_REW_GAP_009", "EXT_REW_GAP_003", "RED_TERM_01", "REW_BEN_REM_PAY_005",
              "REW_INC_135", "EXT_REW_GAP_001", "REW_PAY_018", "REW_PAY_003", "PROP_8e0b6316",
              "REW_PAY_097", "REW_BEN_HOL_007", "REW_INC_071", "PROP_d992b2ea", "REW_PRO_030",
              "PROP_168a6213", "REW_BEN_SICK_006", "CAR_STATUS_01", "CAR_COST_02", "REW_INC_072",
              "REW_INC_131"}

# per metric: old map (drift guard) / new authored map / na additions / delete cfg polarity /
# ruled EFFECTIVE map (the proof target) / expected d + deciding branch after the fix
F = lambda **kw: kw
PLAN = {
    # ---- Tier 1A: the six %-band NEG-last rows (pre-compensated; d stays -1) ----
    "REW_INC_103": F(old={"10": 0.0, "10_24": 20.0, "25_49": 40.0, "50_74": 60.0, "75": 80.0, "NONE": 100.0},
                     new={"10": 80.0, "10_24": 60.0, "25_49": 40.0, "50_74": 20.0, "75": 0.0, "NONE": 100.0},
                     eff={"10": 20.0, "10_24": 40.0, "25_49": 60.0, "50_74": 80.0, "75": 100.0, "NONE": 0.0},
                     d=-1, branch="NEG-last"),
    "REW_BEN_100": F(old={"10": 0.0, "10_24": 20.0, "25_49": 40.0, "50_74": 60.0, "75": 80.0, "NOT_OFFERED": 100.0},
                     new={"10": 80.0, "10_24": 60.0, "25_49": 40.0, "50_74": 20.0, "75": 0.0, "NOT_OFFERED": 100.0},
                     eff={"10": 20.0, "10_24": 40.0, "25_49": 60.0, "50_74": 80.0, "75": 100.0, "NOT_OFFERED": 0.0},
                     d=-1, branch="NEG-last"),
    "REW_BEN_102": F(old={"10": 0.0, "10_24": 25.0, "25_49": 50.0, "50": 75.0, "NOT_OFFERED": 100.0},
                     new={"10": 75.0, "10_24": 50.0, "25_49": 25.0, "50": 0.0, "NOT_OFFERED": 100.0},
                     eff={"10": 25.0, "10_24": 50.0, "25_49": 75.0, "50": 100.0, "NOT_OFFERED": 0.0},
                     d=-1, branch="NEG-last"),
    "PROP_3d4fc4e7": F(old={"0": 0.0, "1_24": 16.67, "25_49": 33.33, "50_74": 50.0, "75_94": 66.67, "95_100": 83.33, "NOT_MEASURED": 100.0},
                       new={"0": 0.0, "1_24": 20.0, "25_49": 40.0, "50_74": 60.0, "75_94": 80.0, "95_100": 100.0},
                       na_add=["NOT_MEASURED"],
                       eff={"0": 0.0, "1_24": 20.0, "25_49": 40.0, "50_74": 60.0, "75_94": 80.0, "95_100": 100.0},
                       d=+1, branch="numband->db-polarity(hib)"),
    "REW_PRO_098": F(old={"3": 0.0, "3_5": 25.0, "6_9": 50.0, "10": 75.0, "NOT_CAPPED": 100.0},
                     new={"3": 100.0, "3_5": 75.0, "6_9": 50.0, "10": 25.0, "NOT_CAPPED": 0.0},
                     eff={"3": 0.0, "3_5": 25.0, "6_9": 50.0, "10": 75.0, "NOT_CAPPED": 100.0},
                     d=-1, branch="NEG-last"),
    "REW_Q049530": F(old={"11K": 0.0, "10K": 20.0, "8K_9K": 40.0, "6K_7K": 60.0, "4K_5K": 80.0, "NO_MINIMUM": 100.0},
                     new={"11K": 100.0, "10K": 80.0, "8K_9K": 60.0, "6K_7K": 40.0, "4K_5K": 20.0, "NO_MINIMUM": 0.0},
                     eff={"11K": 0.0, "10K": 20.0, "8K_9K": 40.0, "6K_7K": 60.0, "4K_5K": 80.0, "NO_MINIMUM": 100.0},
                     d=-1, branch="NEG-last"),
    "REW_BEN_SICK_001": F(old={"STATUTORY_SICK_PAY_ONLY": 33.33, "ENHANCED_OCCUPATIONAL_SICK_PAY_ABOVE_SSP": 100.0,
                               "COMBINATION_OF_ENHANCED_SICK_PAY_AND_SSP": 66.67, "NO_SICK_PAY_PROVIDED": 0.0},
                          new={"STATUTORY_SICK_PAY_ONLY": 66.67, "ENHANCED_OCCUPATIONAL_SICK_PAY_ABOVE_SSP": 0.0,
                               "COMBINATION_OF_ENHANCED_SICK_PAY_AND_SSP": 33.33, "NO_SICK_PAY_PROVIDED": 100.0},
                          eff={"NO_SICK_PAY_PROVIDED": 0.0, "STATUTORY_SICK_PAY_ONLY": 33.33,
                               "COMBINATION_OF_ENHANCED_SICK_PAY_AND_SSP": 66.67, "ENHANCED_OCCUPATIONAL_SICK_PAY_ABOVE_SSP": 100.0},
                          d=-1, branch="NEG-last"),
    "REW_FAI_079": F(old={"YES": 100.0, "NO": 50.0, "IN_DEVELOPMENT": 0.0},
                     new={"YES": 0.0, "NO": 100.0, "IN_DEVELOPMENT": 50.0},
                     del_polarity="lower_is_better",
                     eff={"YES": 100.0, "IN_DEVELOPMENT": 50.0, "NO": 0.0},
                     d=-1, branch="AFF-first"),
    "REW_PAY_014": F(old={"NO_PREMIUM": 0.0, "TIME_AND_A_HALF": 33.33, "DOUBLE_TIME": 66.67, "OTHER": 100.0},
                     new={"NO_PREMIUM": 0.0, "TIME_AND_A_HALF": 33.33, "DOUBLE_TIME": 66.67},
                     na_add=["OTHER"],
                     eff={"NO_PREMIUM": 0.0, "TIME_AND_A_HALF": 33.33, "DOUBLE_TIME": 66.67},
                     d=+1, branch="NEG-first"),
    # ---- Tier 1B: partial/planned above outright No (pre-compensated; d stays -1, AFF-first) ----
    "ALLOW_02": F(old={"YES": 0.0, "NO": 50.0, "AD_HOC_IRREGULAR": 100.0},
                  new={"YES": 0.0, "NO": 100.0, "AD_HOC_IRREGULAR": 50.0},
                  eff={"YES": 100.0, "AD_HOC_IRREGULAR": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "ALLOW_04": F(old={"YES": 0.0, "NO": 50.0, "SOME_ALLOWANCES_ONLY": 100.0},
                  new={"YES": 0.0, "NO": 100.0, "SOME_ALLOWANCES_ONLY": 50.0},
                  eff={"YES": 100.0, "SOME_ALLOWANCES_ONLY": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "RED_PROC_02": F(old={"YES": 0.0, "NO": 50.0, "PARTIALLY": 100.0},
                     new={"YES": 0.0, "NO": 100.0, "PARTIALLY": 50.0},
                     eff={"YES": 100.0, "PARTIALLY": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "RED_PROC_03": F(old={"YES": 0.0, "NO": 50.0, "SOMETIMES_AD_HOC": 100.0},
                     new={"YES": 0.0, "NO": 100.0, "SOMETIMES_AD_HOC": 50.0},
                     eff={"YES": 100.0, "SOMETIMES_AD_HOC": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "RED_PROC_04": F(old={"YES_OUTPLACEMENT_FOR_ALL_REDUNDANCIES": 0.0, "YES_FOR_SOME_GROUPS_ONLY": 33.33,
                          "NO_OUTPLACEMENT_SUPPORT": 66.67, "CASE_BY_CASE": 100.0},
                     new={"YES_OUTPLACEMENT_FOR_ALL_REDUNDANCIES": 0.0, "YES_FOR_SOME_GROUPS_ONLY": 33.33,
                          "NO_OUTPLACEMENT_SUPPORT": 100.0, "CASE_BY_CASE": 66.67},
                     eff={"YES_OUTPLACEMENT_FOR_ALL_REDUNDANCIES": 100.0, "YES_FOR_SOME_GROUPS_ONLY": 66.67,
                          "CASE_BY_CASE": 33.33, "NO_OUTPLACEMENT_SUPPORT": 0.0}, d=-1, branch="AFF-first"),
    "RED_PROC_05": F(old={"YES": 0.0, "NO": 50.0, "SOME_MANAGERS_ONLY": 100.0},
                     new={"YES": 0.0, "NO": 100.0, "SOME_MANAGERS_ONLY": 50.0},
                     eff={"YES": 100.0, "SOME_MANAGERS_ONLY": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "REW_BEN_039": F(old={"YES": 0.0, "NO": 50.0, "IN_DEVELOPMENT": 100.0},
                     new={"YES": 0.0, "NO": 100.0, "IN_DEVELOPMENT": 50.0},
                     eff={"YES": 100.0, "IN_DEVELOPMENT": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "REW_FAI_128": F(old={"YES": 0.0, "NO": 50.0, "PLANNED": 100.0},
                     new={"YES": 0.0, "NO": 100.0, "PLANNED": 50.0},
                     eff={"YES": 100.0, "PLANNED": 50.0, "NO": 0.0}, d=-1, branch="AFF-first"),
    "PROP_202fecc6": F(old={"YES_TRACKED_FOR_MOST_KEY_BENEFITS": 0.0, "YES_TRACKED_FOR_SOME_BENEFITS": 33.33,
                            "NO": 66.67, "IN_DEVELOPMENT": 100.0},
                       new={"YES_TRACKED_FOR_MOST_KEY_BENEFITS": 0.0, "YES_TRACKED_FOR_SOME_BENEFITS": 33.33,
                            "NO": 100.0, "IN_DEVELOPMENT": 66.67},
                       eff={"YES_TRACKED_FOR_MOST_KEY_BENEFITS": 100.0, "YES_TRACKED_FOR_SOME_BENEFITS": 66.67,
                            "IN_DEVELOPMENT": 33.33, "NO": 0.0}, d=-1, branch="AFF-first"),
    # ---- the rider: INC_070 (Tier-3-ruled map amend + allow-list retirement, per the tally instruction) ----
    "REW_INC_070": F(old={"YES": 100.0, "NO": 0.0},
                     new={"YES": 0.0, "NO": 100.0},
                     del_polarity="lower_is_better",
                     eff={"YES": 100.0, "NO": 0.0}, d=-1, branch="AFF-first"),
}

_AFF = re.compile(r"^(yes\b|always|fully|embedded|within last|within 2|formal\b|provided and 75|routinely|"
                  r"consistently|all\b|strong\b|very (clear|fair|effective|confident|broad|well)|structured|"
                  r"monthly or more|ongoing|continuous|almost always|regularly|comprehensive|identified and|"
                  r"enhanced|both buy and sell|no waiting period)", re.I)
_NEG = re.compile(r"^(no\b|none\b|never|not\b|don'?t|no formal|statutory( sick pay)? only|no specific|"
                  r"not provided|not reviewed|not offered|no regular|rarely|very (unclear|unfair|limited)|"
                  r"unstructured|ad hoc|mostly unstructured)", re.I)
_NUM = re.compile(r"^(<|under|less than|up to|within)?\s*[\d£%]", re.I)


def replicate_direction(opts_json, cfg):
    """Byte-faithful replica of aggregate._score_direction for option_scores selects."""
    sc = cfg.get("option_scores") or {}
    na = set(cfg.get("na_codes") or [])
    opts = [o for o in sorted(json.loads(opts_json), key=lambda o: o.get("order", 0))
            if o["code"] in sc and o["code"] not in na]
    if len(opts) < 2:
        return 0, opts, "unscorable"
    first, last = opts[0]["label"], opts[-1]["label"]
    if _AFF.search(first) or _NEG.search(last):
        return -1, opts, ("AFF-first" if _AFF.search(first) else "NEG-last")
    if _NEG.search(first) or _AFF.search(last):
        return 1, opts, ("NEG-first" if _NEG.search(first) else "AFF-last")
    if _NUM.search(first) and _NUM.search(last):
        return (1, opts, "numband->db-polarity(hib)")  # all touched numband rows are db hib (asserted by caller)
    return 0, opts, "fell-through"


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    touched = set(PLAN)
    assert len(touched) == 19, len(touched)
    assert not (touched & TIER2_HOLD), "TIER-2 GRAZED — absolute guard"
    assert not (touched & FROZEN8), "frozen-8 grazed"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    pre_other = {r["id"]: r["scoring_config_json"] for r in c.execute(
        "SELECT id, scoring_config_json FROM questions WHERE id NOT IN (%s)" % ",".join("?" * 19), sorted(touched))}
    pre_rows = {r["id"]: dict(r) for r in c.execute(
        "SELECT * FROM questions WHERE id IN (%s)" % ",".join("?" * 19), sorted(touched))}
    assert len(pre_rows) == 19, "metric missing from questions table"

    stale_lib = []
    plans = {}
    for qid, p in PLAN.items():
        row = pre_rows[qid]
        cfg = json.loads(row["scoring_config_json"])
        assert cfg.get("scoring_method") == "option_scores", qid
        got = {k: float(v) for k, v in (cfg.get("option_scores") or {}).items()}
        assert got == p["old"], "%s pre-map drifted: %s" % (qid, got)
        if cfg.get("polarity") == "lower_is_better":
            stale_lib.append(qid)
            assert p.get("del_polarity") == "lower_is_better", "%s carries UNPLANNED stale lib polarity" % qid
        new_cfg = dict(cfg)
        new_cfg["option_scores"] = {k: float(v) for k, v in p["new"].items()}
        if p.get("na_add"):
            new_cfg["na_codes"] = list(new_cfg.get("na_codes") or []) + list(p["na_add"])
        if p.get("del_polarity"):
            assert new_cfg.pop("polarity") == p["del_polarity"], qid
        # proof-of-effect under the CURRENT resolution order (replicated engine)
        d, opts, branch = replicate_direction(row["options_json"], new_cfg)
        if branch.startswith("numband"):
            assert row["polarity"] == "higher_is_better", "%s numband route needs db hib" % qid
        assert d == p["d"] and branch == p["branch"], "%s mechanism drifted: d=%s branch=%s" % (qid, d, branch)
        eff = {o["code"]: (100.0 - new_cfg["option_scores"][o["code"]] if d == -1 else new_cfg["option_scores"][o["code"]])
               for o in opts}
        assert {k: round(v, 2) for k, v in eff.items()} == {k: round(v, 2) for k, v in p["eff"].items()}, \
            "%s EFFECTIVE map wrong under current engine: %s" % (qid, eff)
        plans[qid] = new_cfg
    assert sorted(stale_lib) == ["REW_FAI_079", "REW_INC_070"], "stale-lib sweep mismatch: %s" % stale_lib

    print("aff-tier1 %s (db=%s) — 19 metrics (9 INVERT + 9 AMEND + INC_070 rider); stale-lib superseded: %s"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db), stale_lib))
    for qid in sorted(PLAN):
        p = PLAN[qid]
        print("  %-18s d=%+d %-26s eff: %s" % (qid, p["d"], p["branch"],
              " > ".join(k for k, _ in sorted(p["eff"].items(), key=lambda x: -x[1]))[:84]))
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for qid, new_cfg in plans.items():
        cur.execute("UPDATE questions SET scoring_config_json=? WHERE id=?",
                    (json.dumps(new_cfg, ensure_ascii=False), qid))
    # ---- asserts before commit ----
    assert book_hash(c) == pre_book, "ANSWERS CHANGED — this is a config-only diff"
    post_other = {r["id"]: r["scoring_config_json"] for r in c.execute(
        "SELECT id, scoring_config_json FROM questions WHERE id NOT IN (%s)" % ",".join("?" * 19), sorted(touched))}
    assert post_other == pre_other, "non-scope question config changed"
    for qid in touched:
        row = c.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        for col in row.keys():
            if col == "scoring_config_json":
                continue
            assert row[col] == pre_rows[qid][col], "%s non-config column moved: %s" % (qid, col)
        got = json.loads(row["scoring_config_json"])
        assert {k: float(v) for k, v in got["option_scores"].items()} == plans[qid]["option_scores"], qid
    for o in FIX:
        n = c.execute("SELECT COUNT(*) FROM answers WHERE org_id=?", (o,)).fetchone()[0]
        assert n > 0, "fixture vanished?!"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "metrics": 19,
                      "stale_lib_superseded": stale_lib, "answers_book": "byte-identical (config-only diff)",
                      "tier2": "untouched (guarded)", "proof": "all 19 effective maps verified under current resolution order"},
                     indent=2))
    c.close()


if __name__ == "__main__":
    main()
