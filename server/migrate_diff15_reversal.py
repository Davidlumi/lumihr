# -*- coding: utf-8 -*-
"""migrate_diff15_reversal.py — Diff 15: two-layer reversal of Diff 14 (ruled 2026-07-24, David Option A).

Reverses Diff 14's verdict suppression across its original footprint, in the two layers Diff 14 used:
  LAYER a (config): market_position_config.json `direction` neutral -> restored (donor 695591c, all
                    higher_is_better), and re-tag `_diff14` -> `_diff15_restored` (note keeps the Diff-14
                    reference so history is traceable in the file itself).
  LAYER b (DB):     questions.polarity 'neutral' -> restored — reverses migrate_diff14_verdict_authority.py
                    line 71 (`UPDATE questions SET polarity='neutral'`).

Restore set + per-metric restore polarity come from diff15_scope.json (NO ids hardcoded):
  restore = _diff14-tagged ∩ donor-directional ∩ live-neutral ∩ (pre-Diff-14 DB polarity == donor dir).
  held_out = cross-verify disagreements + anything passed via --hold-out (gate backwards-ladder failures).
`unbenchmarked` flags, the register and all other fields are UNTOUCHED (disclosure/tracking, ruled).

Guards: dry-run by default. Live needs --write --confirmed-by-david (r3sw7 double-guard). Throwaway needs
--db <copy> and --mp-out <staged config> (never the live config). Post-write asserts: config diff = ONLY
`direction` + tag lines on restore metrics; DB polarity changed ONLY on restore metrics; answers-book hash
unchanged; frozen-8 config/polarity untouched.
Usage:
  throwaway: python3 migrate_diff15_reversal.py --db COPY --write --mp-out STAGED.json [--hold-out a,b]
  live     : python3 migrate_diff15_reversal.py --write --confirmed-by-david [--hold-out a,b]
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
SCOPE = os.path.join(ROOT, "diff15_scope.json")
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]
NEW_TAG = "_diff15_restored"
NOTE = ("direction+polarity restored (Diff 15, 2026-07-24, David Option A) — reverses Diff 14's "
        "2026-07-18 suppression (was _diff14: 'verdict suppressed: distribution has no ruled authority'); "
        "anchor truth-up continues via the register + member data, not by suppressing direction")


def answers_book(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def polarity_fp(c, exclude):
    """fingerprint of every active-Reward polarity EXCEPT the restore set — must not move."""
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
    ap.add_argument("--mp-out", dest="mp_out", default=None, help="throwaway: staged config path (not live)")
    ap.add_argument("--hold-out", dest="hold_out", default="", help="extra metric ids to exclude (gate fails)")
    a = ap.parse_args()

    scope = json.load(open(SCOPE, encoding="utf-8"))
    restore = dict(scope["restore"])                       # {metric: polarity}
    extra_hold = [x.strip() for x in a.hold_out.split(",") if x.strip()]
    for q in extra_hold:
        restore.pop(q, None)
    is_live = os.path.abspath(a.db) == LIVE_DB

    # resolve config destination + guards
    if a.write:
        if is_live:
            if not a.confirmed:
                print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
            a.mp_out = LIVE_MP
        else:
            if a.mp_out is None or os.path.abspath(a.mp_out) == LIVE_MP:
                print("REFUSED: throwaway needs --mp-out pointing away from the live config (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    live_cfg_raw = open(LIVE_MP, "rb").read()
    cfg = json.loads(live_cfg_raw)
    M = cfg["metrics"]

    # ---- pre-state asserts (each restore metric: config neutral + _diff14; DB polarity neutral) ----
    bad = []
    for q, pol in restore.items():
        m = M.get(q)
        dbrow = c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()
        if m is None: bad.append((q, "missing from config")); continue
        if m.get("direction") != "neutral": bad.append((q, "config direction=%s not neutral" % m.get("direction")))
        if "_diff14" not in m: bad.append((q, "no _diff14 tag"))
        if dbrow is None: bad.append((q, "missing from questions"))
        elif dbrow["polarity"] != "neutral": bad.append((q, "DB polarity=%s not neutral" % dbrow["polarity"]))
        if pol not in ("higher_is_better", "lower_is_better"): bad.append((q, "restore polarity=%s" % pol))
    if bad:
        print("PRE-STATE MISMATCH (aborting, no write):")
        for q, why in bad[:40]: print("  %-24s %s" % (q, why))
        sys.exit(3)

    pre_book = answers_book(c)
    pre_fp_nonrestore = polarity_fp(c, set(restore))
    n_ans = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_dir_pre = {q: (M.get(q) or {}).get("direction") for q in FROZEN8}
    frozen_pol_pre = {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()["polarity"] for q in FROZEN8}

    print("Diff 15 two-layer reversal — %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  restore set: %d | held out: %d (%s) + extra --hold-out: %s"
          % (len(restore), len(scope["held_out"]) + len(extra_hold), list(scope["held_out"]), extra_hold or "none"))
    print("  layer a: config direction neutral -> restored + retag _diff14 -> %s" % NEW_TAG)
    print("  layer b: questions.polarity neutral -> restored")

    if not a.write:
        print("dry-run complete — pass --write (throwaway: + --mp-out; live: + --confirmed-by-david)")
        c.close(); return

    # ==== LAYER a (config, in-memory) + config asserts — BEFORE any DB commit, so a config-diff failure
    #      never leaves a half-applied DB. ====
    for q, pol in restore.items():
        m = M[q]
        m["direction"] = pol
        m.pop("_diff14")                               # remove old tag (its meaning carried in NEW_TAG note)
        m[NEW_TAG] = NOTE
    new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()
    # line-diff assertion: edit changes only VALUES + renames one key per metric -> NO lines added/removed,
    # so old and new are line-count-identical and INDEX-ALIGNED (difflib's LCS misaligns on the thousands of
    # repeated lens/weight lines; index alignment is exact here).
    old_lines = live_cfg_raw.decode().splitlines()
    new_lines = new_raw.decode().splitlines()
    assert len(old_lines) == len(new_lines), "line count changed (%d->%d) — structure shifted" % (len(old_lines), len(new_lines))
    changed = [(i, old_lines[i], new_lines[i]) for i in range(len(old_lines)) if old_lines[i] != new_lines[i]]
    def _ok(o, n):
        return ('"direction":' in o and '"direction":' in n) or ('"_diff14":' in o and '"%s":' % NEW_TAG in n)
    offending = [(i, o, n) for i, o, n in changed if not _ok(o, n)]
    assert not offending, "CONFIG DIFF TOUCHED NON-direction/tag LINES:\n" + "\n".join(
        "  L%d: %s -> %s" % (i, o.strip(), n.strip()) for i, o, n in offending[:20])
    assert len(changed) == 2 * len(restore), "expected %d changed lines (dir+tag x%d), got %d" % (
        2 * len(restore), len(restore), len(changed))
    assert {q: (M.get(q) or {}).get("direction") for q in FROZEN8} == frozen_dir_pre, "frozen-8 config direction moved"

    # ==== LAYER b (DB polarity) — apply but DO NOT commit until DB asserts pass ====
    cur = c.cursor()
    for q, pol in restore.items():
        cur.execute("UPDATE questions SET polarity=? WHERE id=?", (pol, q))
    assert answers_book(c) == pre_book, "ANSWERS BOOK CHANGED — layer b touched answers"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_ans, "answers row count changed"
    assert polarity_fp(c, set(restore)) == pre_fp_nonrestore, "NON-RESTORE polarity moved (blast radius escaped)"
    left = {r["polarity"] for r in c.execute(
        "SELECT DISTINCT polarity FROM questions WHERE id IN (%s)" % ",".join("?" * len(restore)), list(restore))}
    assert left <= {"higher_is_better", "lower_is_better"}, left
    assert {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()["polarity"]
            for q in FROZEN8} == frozen_pol_pre, "frozen-8 DB polarity moved"

    # ==== commit sequence: stage config to temp -> commit DB -> atomic replace config ====
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.mp_out)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_raw)
    c.commit()                                         # DB first (config not yet visible)
    os.replace(tmp, a.mp_out)                          # then config (atomic same-fs rename)

    man = {"applied": True, "live": is_live, "restore_count": len(restore),
           "held_out": list(scope["held_out"]) + extra_hold,
           "config_lines_changed": len(changed), "config_out": os.path.basename(a.mp_out),
           "answers_book": "unchanged", "non_restore_polarity": "unchanged", "frozen8": "untouched"}
    print(json.dumps(man, indent=2))
    c.close()


if __name__ == "__main__":
    main()
