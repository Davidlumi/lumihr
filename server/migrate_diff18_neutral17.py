# -*- coding: utf-8 -*-
"""migrate_diff18_neutral17.py — Diff 18: apply the neutral-17 rulings + TIPS_EXIST closure
(David 2026-07-24). Classification apply, ONE fix class: the 17 neutral_beside metrics + TIPS_EXIST.

  PRACTICE (6): config class Level->Practice, direction neutral->null; DB questions.polarity
                neutralised where directional (PROP pair lower_is_better, RED_COST_01 higher_is_better).
  OUTLIER (11): config class stays Level, direction neutral->higher_is_better; DB polarity->higher_is_better;
                authored scale recorded in the _diff18_ruled note (scales from RULING_SHEET_neutral17,
                NEVER inferred from option order). --hold-out excludes any that fail the sequencing gate.
  TIPS_EXIST:   already class=Practice — confirm + tag (permanent OUT).

Tag all touched entries `_diff18_ruled`. Guards: dry-run default; live needs --write --confirmed-by-david;
throwaway needs --db <copy> and --mp-out <staged config, not live>. Post-asserts: only the ruled fields
change (per-entry semantic diff); non-scope config entries byte-identical; DB polarity changes only on the
ruled set; answers-book unchanged; frozen-8 untouched.
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
SCOPE = os.path.join(ROOT, "diff18_scope.json")
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]
TAG = "_diff18_ruled"


def answers_book(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def polarity_fp(c, exclude):
    h = hashlib.sha256()
    for r in c.execute("SELECT id,COALESCE(polarity,'') FROM questions WHERE superpower='Reward' "
                       "AND status!='retired' ORDER BY 1"):
        if r[0] in exclude:
            continue
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--mp-out", dest="mp_out", default=None)
    ap.add_argument("--hold-out", dest="hold_out", default="", help="OUTLIER ids to exclude (sequencing gate)")
    a = ap.parse_args()

    scope = json.load(open(SCOPE, encoding="utf-8"))
    held = [x.strip() for x in a.hold_out.split(",") if x.strip()]
    practice = list(scope["practice"])
    outlier = {k: v for k, v in scope["outlier"].items() if k not in held}
    neutralise = [q for q in scope["neutralise_db_polarity"] if q not in held]
    tips = scope["tips_exist_confirm_practice"]
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write:
        if is_live:
            if not a.confirmed:
                print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
            a.mp_out = LIVE_MP
        elif a.mp_out is None or os.path.abspath(a.mp_out) == LIVE_MP:
            print("REFUSED: throwaway needs --mp-out (not the live config) (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    live_raw = open(LIVE_MP, "rb").read()
    cfg = json.loads(live_raw); M = cfg["metrics"]

    # DB polarity target: neutralise the 3 directional PRACTICE; higher_is_better on OUTLIER
    pol_target = {}
    for q in neutralise:
        pol_target[q] = "neutral"
    for q in outlier:
        pol_target[q] = "higher_is_better"
    ruled_pol_set = set(pol_target)

    # pre-state asserts: all 17 currently neutral_beside
    bad = []
    for q in practice + list(outlier):
        m = M.get(q)
        if not m: bad.append((q, "missing from config")); continue
        if m.get("class") in ("Practice", "Design"): bad.append((q, "already class=%s" % m.get("class")))
        if m.get("direction") not in (None, "neutral"): bad.append((q, "already direction=%s" % m.get("direction")))
    if M.get(tips, {}).get("class") != "Practice":
        bad.append((tips, "TIPS_EXIST not already Practice — %s" % M.get(tips, {}).get("class")))
    if bad:
        print("PRE-STATE MISMATCH (aborting):")
        for q, w in bad[:40]: print("  %-40s %s" % (q, w))
        sys.exit(3)

    print("Diff 18 — %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  PRACTICE: %d | OUTLIER included: %d | held out: %s | neutralise DB pol: %d | TIPS confirm: %s"
          % (len(practice), len(outlier), held or "none", len(neutralise), tips))

    if not a.write:
        print("dry-run complete — pass --write (throwaway: +--mp-out; live: +--confirmed-by-david)")
        c.close(); return

    # ---- LAYER a (config, in-memory) ----
    import copy
    before = copy.deepcopy(M)
    for q in practice:
        M[q]["class"] = "Practice"; M[q]["direction"] = None
        M[q][TAG] = "ruled PRACTICE (Diff 18, David 2026-07-24)"
    for q, scale in outlier.items():
        M[q]["direction"] = "higher_is_better"          # class stays Level
        M[q][TAG] = "ruled OUTLIER_SCALE (Diff 18, David 2026-07-24) — " + scale
    M[tips][TAG] = "ruled OUT permanently (Diff 18) — Practice-class, pre-Diff-14 polarity neutral; Diff-15 held-out closed"
    new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()

    # config semantic assert: ONLY scope entries changed, and only the ruled fields
    scope_ids = set(practice) | set(outlier) | {tips}
    for qid, ent in before.items():
        if qid in scope_ids:
            continue
        assert ent == M[qid], "NON-SCOPE config entry changed: %s" % qid
    for q in practice:
        b = before[q]
        assert M[q]["class"] == "Practice" and M[q]["direction"] is None
        assert all(M[q].get(k) == b.get(k) for k in b if k not in ("class", "direction", TAG)), "extra field moved on %s" % q
    for q in outlier:
        b = before[q]
        assert M[q]["class"] == b["class"] and M[q]["direction"] == "higher_is_better"
        assert all(M[q].get(k) == b.get(k) for k in b if k not in ("direction", TAG)), "extra field moved on %s" % q
    assert all(M[tips].get(k) == before[tips].get(k) for k in before[tips] if k != TAG), "TIPS extra field moved"

    # ---- LAYER b (DB polarity) — apply, assert, before commit ----
    pre_book = answers_book(c)
    pre_fp = polarity_fp(c, ruled_pol_set)
    n_ans = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pol = {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()["polarity"] for q in FROZEN8}
    cur = c.cursor()
    for q, pol in pol_target.items():
        cur.execute("UPDATE questions SET polarity=? WHERE id=?", (pol, q))
    assert answers_book(c) == pre_book, "answers book changed"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_ans, "answers count changed"
    assert polarity_fp(c, ruled_pol_set) == pre_fp, "non-ruled polarity moved"
    assert {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()["polarity"] for q in FROZEN8} == frozen_pol, "frozen-8 polarity moved"

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.mp_out)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_raw)
    c.commit()
    os.replace(tmp, a.mp_out)
    print(json.dumps({"applied": True, "live": is_live, "practice": len(practice), "outlier": len(outlier),
                      "held_out": held, "db_polarity_changed": len(pol_target), "tips_confirmed": tips,
                      "answers_book": "unchanged", "non_ruled_polarity": "unchanged", "frozen8": "untouched"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
