# -*- coding: utf-8 -*-
"""migrate_retro_inc070.py — RETRO CFG-POLARITY SWEEP fix (config/data class; David-ruled
2026-07-28: "census first, fix only what it finds"). THE CENSUS FOUND EXACTLY ONE LEAK:
REW_INC_070 — the Tier-1 supersession DELETED its stale 'lower_is_better' cfg-polarity key,
leaving the field ABSENT, and score_polarity treats absent != 'neutral': with its authored
direction pin (+1) favourability came back alive on a Practice-class metric with no flag
shield — 179 orgs carried live good/bad favourability on its items (the CAR_STATUS_01 shape;
missed because the prior attack sets covered the 13 re-routes + PAY_097, never INC_070).

FIX: scoring_config.polarity := 'neutral', explicitly (the lesson recorded: supersede a stale
polarity by SETTING neutral, never by deleting the key). Payloads untouched (favourability is
item-time; db polarity already neutral) — the 179 favourabilities die at render, enumerated
and attributed as the leak closing. Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
QID = "REW_INC_070"
# SWEEP ADDITIONS (the adversarial second-leak hunt, 2026-07-28): the census graded
# REW263_PAY_MERITMATRIX STRUCTURAL — the engine falsified it: practice_position_items builds
# live good/bad favourability for 220/223 orgs off its directional questions.polarity, render-
# dead today only contingently (gauge class-block + a domain-dot fallback engaging 0/223) —
# the ACCIDENTAL-shield class this sweep exists to kill. Fix: questions.polarity -> neutral
# (payload 'polarity' field changes on exactly this one metric — attributed). Plus the Diff-18
# PROP pair's stale cfg 'lower_is_better' keys -> 'neutral' (dead code since the engine diff
# removed the cfglib step; the exact stale-field trap class the rulings ban; byte-identical).
MERIT = "REW263_PAY_MERITMATRIX"
PROPS = ("PROP_e63cf45a", "PROP_d16bae79")


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
    cfg = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (QID,)).fetchone()[0])
    assert "polarity" not in cfg, "INC_070 cfg polarity unexpectedly present: %r" % cfg.get("polarity")
    assert cfg.get("direction") == 1 and {k: float(v) for k, v in cfg["option_scores"].items()} == {"YES": 100.0, "NO": 0.0}, cfg
    new = dict(cfg); new["polarity"] = "neutral"
    assert c.execute("SELECT polarity FROM questions WHERE id=?", (MERIT,)).fetchone()[0] == "higher_is_better", "MERIT drifted"
    pcfgs = {}
    for q in PROPS:
        pc = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (q,)).fetchone()[0])
        assert pc.get("polarity") == "lower_is_better", "%s stale-lib key drifted" % q
        pc["polarity"] = "neutral"; pcfgs[q] = pc
    print("retro-sweep %s (db=%s): INC_070 cfg polarity ABSENT->'neutral' (rendered leak, 179 orgs) | "
          "MERITMATRIX db polarity hib->neutral (accidental shield, 220-org practice favourability) | "
          "PROP pair stale cfg lib->'neutral' (dead-code trap class)"
          % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    if not a.write:
        print("dry-run complete"); c.close(); return
    touched = {QID, MERIT} | set(PROPS)
    pre_others = {r["id"]: (r["scoring_config_json"], r["polarity"]) for r in
                  c.execute("SELECT id, scoring_config_json, polarity FROM questions") if r["id"] not in touched}
    c.execute("UPDATE questions SET scoring_config_json=? WHERE id=?", (json.dumps(new, ensure_ascii=False), QID))
    c.execute("UPDATE questions SET polarity='neutral' WHERE id=?", (MERIT,))
    for q, pc in pcfgs.items():
        c.execute("UPDATE questions SET scoring_config_json=? WHERE id=?", (json.dumps(pc, ensure_ascii=False), q))
    assert book_hash(c) == pre_book, "ANSWERS CHANGED"
    post_others = {r["id"]: (r["scoring_config_json"], r["polarity"]) for r in
                   c.execute("SELECT id, scoring_config_json, polarity FROM questions") if r["id"] not in touched}
    assert post_others == pre_others
    got = json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (QID,)).fetchone()[0])
    assert got["polarity"] == "neutral" and got["direction"] == 1
    assert c.execute("SELECT polarity FROM questions WHERE id=?", (MERIT,)).fetchone()[0] == "neutral"
    for q in PROPS:
        assert json.loads(c.execute("SELECT scoring_config_json FROM questions WHERE id=?", (q,)).fetchone()[0])["polarity"] == "neutral"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live,
                      "fixes": {QID: "cfg polarity absent->neutral", MERIT: "db polarity hib->neutral",
                                PROPS[0]: "cfg lib->neutral", PROPS[1]: "cfg lib->neutral"},
                      "answers_book": "byte-identical"}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
