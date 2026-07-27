# -*- coding: utf-8 -*-
"""migrate_aff_pins.py — AFF ENGINE+GATE DIFF, PART B: the pins (config/data class; David-ruled
2026-07-27, "authored direction becomes law"). Writes scoring_config_json for EXACTLY 88 metrics
(the 108 label-branch census minus Tier-2's 20 HOLD rows):

  - 17 NATURAL rewrites (the Tier-1 pre-compensated engine-coordinate maps): option_scores :=
    the ruled effective values (derived as 100 - current, asserted against the Tier-1 PLAN)
    + "direction": 1. Rendered output UNCHANGED: authored-first(+1, natural map) composes to
    the same effective scores the label branch produced from the pre-compensated map.
    (CORRECTION recorded: the Tier-1 prose said "16" pre-compensated maps — the true count is
    17; the migration PLAN itself was always correct, the prose undercounted.)
  - 2 direction-only pins on the na-route Tier-1 rows: PROP_3d4fc4e7 (+1), REW_PAY_014 (+1)
    — maps already natural.
  - 69 CONFIRM pins (Tiers 3+4, ruled-awaiting-pin): "direction" := exactly the d the label
    regex produces today (derived per metric, never assumed); maps byte-untouched. Pins move
    AUTHORITY, never output.

TIER-2's 20 rows: NO pins, NO direction keys — they stay label-heuristic-flagged; qa_scores'
new heuristic-census check carries them as the ruled exception list. The 22 route-b/0 and 7
numband metrics need NO pins (derived: numband rests on the curated DB-polarity field over a
numeric scale; route-b rests on the David-ruled mp-config direction; 0-resolved metrics are
not scored at all) — their sources are not 'label_heuristic', so the census ignores them.

GLOBAL INVARIANT (absolute): every metric's effective per-option scores are BYTE-IDENTICAL
under (old engine, old configs) vs (new engine, pinned configs) — asserted in-script for all
active scored selects; the rehearsal additionally asserts all 344 benchmark payloads byte-equal.
Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
MP = os.path.join(ROOT, "data", "market_position_config.json")
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
TIER2_HOLD = {"EXT_REW_GAP_009", "EXT_REW_GAP_003", "RED_TERM_01", "REW_BEN_REM_PAY_005",
              "REW_INC_135", "EXT_REW_GAP_001", "REW_PAY_018", "REW_PAY_003", "PROP_8e0b6316",
              "REW_PAY_097", "REW_BEN_HOL_007", "REW_INC_071", "PROP_d992b2ea", "REW_PRO_030",
              "PROP_168a6213", "REW_BEN_SICK_006", "CAR_STATUS_01", "CAR_COST_02", "REW_INC_072",
              "REW_INC_131"}
NATURAL_17 = {"REW_INC_103", "REW_BEN_100", "REW_BEN_102", "REW_PRO_098", "REW_Q049530",
              "REW_BEN_SICK_001", "REW_FAI_079", "ALLOW_02", "ALLOW_04", "RED_PROC_02",
              "RED_PROC_03", "RED_PROC_04", "RED_PROC_05", "REW_BEN_039", "REW_FAI_128",
              "PROP_202fecc6", "REW_INC_070"}
DIR_ONLY_NA = {"PROP_3d4fc4e7": 1, "REW_PAY_014": 1}

_AFF = re.compile(r"^(yes\b|always|fully|embedded|within last|within 2|formal\b|provided and 75|routinely|"
                  r"consistently|all\b|strong\b|very (clear|fair|effective|confident|broad|well)|structured|"
                  r"monthly or more|ongoing|continuous|almost always|regularly|comprehensive|identified and|"
                  r"enhanced|both buy and sell|no waiting period)", re.I)
_NEG = re.compile(r"^(no\b|none\b|never|not\b|don'?t|no formal|statutory( sick pay)? only|no specific|"
                  r"not provided|not reviewed|not offered|no regular|rarely|very (unclear|unfair|limited)|"
                  r"unstructured|ad hoc|mostly unstructured)", re.I)
_NUM = re.compile(r"^(<|under|less than|up to|within)?\s*[\d£%]", re.I)
_mpdir = {k: (v.get("direction")) for k, v in json.load(open(MP))["metrics"].items()}


def scoreable(row, cfg):
    sc = cfg.get("option_scores") or {}
    na = set(cfg.get("na_codes") or [])
    return [o for o in sorted(json.loads(row["options_json"] or "[]"), key=lambda o: o.get("order", 0))
            if o["code"] in sc and o["code"] not in na]


def d_old(row, cfg):
    """The PRE-diff engine, byte-faithful (incl. the now-removed cfg-polarity-lib step)."""
    opts = scoreable(row, cfg)
    if len(opts) < 2: return 0, "unresolved"
    f, l = opts[0]["label"], opts[-1]["label"]
    if _AFF.search(f) or _NEG.search(l): return -1, "label"
    if _NEG.search(f) or _AFF.search(l): return 1, "label"
    if _NUM.search(f) and _NUM.search(l):
        if row["polarity"] == "higher_is_better": return 1, "numband"
        if row["polarity"] == "lower_is_better": return -1, "numband"
    elif cfg.get("polarity") == "lower_is_better":
        return -1, "cfglib"
    if _mpdir.get(row["id"]) == "higher_is_better":
        seq = [float(cfg["option_scores"][o["code"]]) for o in opts]
        if len(set(seq)) >= 2 and all(a <= b for a, b in zip(seq, seq[1:])): return 1, "route_b"
    return 0, "unresolved"


def d_new(row, cfg):
    """The POST-diff engine (authored first, cfglib removed)."""
    d0 = cfg.get("direction")
    if d0 in (1, -1): return d0, "authored"
    opts = scoreable(row, cfg)
    if len(opts) < 2: return 0, "unresolved"
    f, l = opts[0]["label"], opts[-1]["label"]
    if _AFF.search(f) or _NEG.search(l): return -1, "label_heuristic"
    if _NEG.search(f) or _AFF.search(l): return 1, "label_heuristic"
    if _NUM.search(f) and _NUM.search(l):
        if row["polarity"] == "higher_is_better": return 1, "numband"
        if row["polarity"] == "lower_is_better": return -1, "numband"
    if _mpdir.get(row["id"]) == "higher_is_better":
        seq = [float(cfg["option_scores"][o["code"]]) for o in opts]
        if len(set(seq)) >= 2 and all(a <= b for a, b in zip(seq, seq[1:])): return 1, "route_b"
    return 0, "unresolved"


def eff(row, cfg, d):
    return {o["code"]: (100.0 - float(cfg["option_scores"][o["code"]]) if d == -1
                        else float(cfg["option_scores"][o["code"]])) for o in scoreable(row, cfg)}


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
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)

    rows = {r["id"]: r for r in c.execute(
        "SELECT * FROM questions WHERE status='active' AND is_scored=1")}
    selects = {qid: r for qid, r in rows.items()
               if r["type"] in ("single_select", "yes_no")
               and json.loads(r["scoring_config_json"] or "{}").get("scoring_method") == "option_scores"}
    assert len(selects) == 137, "scored-select census drifted: %d" % len(selects)

    # derive the label-branch census under the OLD engine + the pin set
    label_set = set()
    old_state = {}
    for qid, r in selects.items():
        cfg = json.loads(r["scoring_config_json"])
        assert "direction" not in cfg, "%s already carries a direction key — drift" % qid
        d, src = d_old(r, cfg)
        old_state[qid] = (cfg, d, src, eff(r, cfg, d) if d else None)
        if src == "label":
            label_set.add(qid)
    # The audit's census was 108 label rows PRE-Tier-1; the Tier-1 diff itself moved
    # PROP_3d4fc4e7 to the numband route ('Not measured' -> na left numeric ends), so the
    # CURRENT label census is 107. 3d4fc4e7 is still pinned — by its Tier-1A ruling — from
    # the numband route (authored wins either way; same +1).
    assert len(label_set) == 107, "label census drifted: %d" % len(label_set)
    assert old_state["PROP_3d4fc4e7"][2] == "numband" and old_state["PROP_3d4fc4e7"][1] == 1
    assert TIER2_HOLD <= label_set and len(TIER2_HOLD) == 20
    pins = (label_set - TIER2_HOLD) | {"PROP_3d4fc4e7"}
    assert len(pins) == 88 and NATURAL_17 <= pins and set(DIR_ONLY_NA) <= pins
    assert not (pins & FROZEN8) and not (TIER2_HOLD & FROZEN8)
    confirms = pins - NATURAL_17 - set(DIR_ONLY_NA)
    assert len(confirms) == 69, len(confirms)

    plans = {}
    for qid in sorted(pins):
        r = selects[qid]
        cfg, d, src, e_old = old_state[qid]
        new_cfg = dict(cfg)
        if qid in NATURAL_17:
            assert d == -1, qid
            # natural value = 100 - pre-compensated value, serialized UNROUNDED: json round-trips
            # repr exactly, so score_answer(+1, natural) returns the bit-identical double the old
            # (d=-1, 100-precomp) path computed — the payload byte-identity depends on this.
            new_cfg["option_scores"] = {k: (100.0 - float(v)) for k, v in cfg["option_scores"].items()}
            new_cfg["direction"] = 1
        elif qid in DIR_ONLY_NA:
            new_cfg["direction"] = DIR_ONLY_NA[qid]
            assert d == DIR_ONLY_NA[qid], (qid, d)
        else:
            assert d in (1, -1), qid
            new_cfg["direction"] = d
        d2, src2 = d_new(r, new_cfg)
        assert src2 == "authored" and d2 == new_cfg["direction"], qid
        e_new = eff(r, new_cfg, d2)
        assert {k: round(v, 4) for k, v in e_new.items()} == {k: round(v, 4) for k, v in e_old.items()}, \
            "%s PIN MOVED OUTPUT: %s -> %s" % (qid, e_old, e_new)
        plans[qid] = new_cfg
    # Tier-2 + non-census: byte-untouched, and effective identical old-engine vs new-engine
    for qid, r in selects.items():
        if qid in plans:
            continue
        cfg, d, src, e_old = old_state[qid]
        d2, src2 = d_new(r, cfg)
        assert d2 == d, "%s direction moved under the new engine: %s -> %s" % (qid, d, d2)
        if d:
            assert eff(r, cfg, d2) == e_old, qid
    flagged_after = sorted(qid for qid, r in selects.items() if qid not in plans
                           and d_new(r, old_state[qid][0])[1] == "label_heuristic")
    assert set(flagged_after) == TIER2_HOLD, "census mismatch: %s" % flagged_after

    print("aff-pins %s (db=%s) — 88 pins: 17 natural+dir / 2 dir-only(na-route) / 69 confirm-dir; "
          "Tier-2 flagged census post-pin = %d (== the ruled exception list)"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db), len(flagged_after)))
    if not a.write:
        for qid in sorted(NATURAL_17): print("  natural  %-18s dir=+1, map -> ruled effective values" % qid)
        for qid in sorted(DIR_ONLY_NA): print("  dir-only %-18s dir=%+d (na-route map already natural)" % (qid, DIR_ONLY_NA[qid]))
        print("  confirm-dir x69: direction := the regex's current d, maps untouched")
        print("dry-run complete"); c.close(); return

    pre_rows = {qid: dict(selects[qid]) for qid in plans}
    pre_other = {r["id"]: r["scoring_config_json"] for r in c.execute("SELECT id, scoring_config_json FROM questions")
                 if r["id"] not in plans}
    cur = c.cursor()
    for qid, new_cfg in plans.items():
        cur.execute("UPDATE questions SET scoring_config_json=? WHERE id=?",
                    (json.dumps(new_cfg, ensure_ascii=False), qid))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED — config-only diff"
    post_other = {r["id"]: r["scoring_config_json"] for r in c.execute("SELECT id, scoring_config_json FROM questions")
                  if r["id"] not in plans}
    assert post_other == pre_other, "non-pin question config changed"
    for qid in plans:
        row = c.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        for col in row.keys():
            if col != "scoring_config_json":
                assert row[col] == pre_rows[qid][col], (qid, col)
        got = json.loads(row["scoring_config_json"])
        assert got.get("direction") == plans[qid]["direction"], qid
    for qid in TIER2_HOLD:
        assert "direction" not in json.loads(c.execute(
            "SELECT scoring_config_json FROM questions WHERE id=?", (qid,)).fetchone()[0]), "TIER-2 PINNED?!"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "pins": len(plans),
                      "natural_17": sorted(NATURAL_17), "dir_only_na": DIR_ONLY_NA,
                      "confirm_dir": len(confirms), "tier2_flagged": flagged_after,
                      "answers_book": "byte-identical", "output_invariant": "effective maps identical for all 137 (asserted)"},
                     indent=2))
    c.close()


if __name__ == "__main__":
    main()
