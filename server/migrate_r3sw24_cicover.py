"""
r3sw24 — critical-illness cover-level: align signals + collapse + flat-condition + CI⊆IP chain.

CI is a bundled group-risk benefit (all 52 CI-havers are also IP-havers — CI rides inside the
IP+life+CI package), NOT a rare perk. So FLAT condition (like life assurance), NOT a sector-gate
(like dental). Two mis-seeded signals disagreed: REW_BEN_038 "Critical illness cover" tick (42,
cost-heavy) vs the dedicated REW263_BEN_CICOVER level metric (52, better-distributed).

  FIX 1  align 038 CI-tick UP to the dedicated 52-haver metric (IP pattern, dedicated>inventory):
         ADD the token to the 41 level-only orgs, REMOVE from the 31 tick-only. Result: 038
         CI-tick == 52 == level-havers. PMI-SAFEGUARD (038 is the PMI parent): CI-token-only edit
         — PMI-tick 154 byte-identical + all 6 PMI children unmoved (HARD ABORT).
  FIX 2  collapse "Not offered" + "Not applicable" (both no-CI) + flat-condition the level split on
         the aligned 52: delete the 168 non-haver rows (conditioned), keep the 52 level values
         UNCHANGED (Fixed 21 / 1x 19 / 2x+ 12 — no re-weight). Caption "of organisations offering
         critical illness cover".
  FIX 3  two-level chain: level-answerers ⊆ CI-havers (038 tick) ⊆ IP-havers (046 != No). Pairs:
         level ⊆ CI-tick + CI-tick ⊆ IP (the new child_contains selector). Verdict EST-suppressed.
Dual-config atomic (r3sw7). Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P038, CITOK, PMITOK = "REW_BEN_038", "Critical illness cover", "Private Medical Insurance (PMI)"
LEVEL, IP = "REW263_BEN_CICOVER", "REW_BEN_046"
LEVELS = {"Fixed lump sum", "1x salary", "2x+ salary"}
STAMP = "2026-07-21"
TOUCHED = [P038, LEVEL]
PMI_CHILDREN = ["REW265_BEN_PMICOMP", "REW_BEN_139", "REW_BEN_044", "3faf1f0c-f753-497f-a395-384bba38c5e3",
                "REW263_BEN_PMIEXCESS"]


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    ap.add_argument("--mp-config-out", dest="mp_out", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    served_mp = os.path.join(ROOT, "data", "market_position_config.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            a.config_out = served_ab if is_live else sys.exit("REFUSED: throwaway needs --config-out (r3sw7)")
        if a.mp_out is None:
            a.mp_out = served_mp if is_live else sys.exit("REFUSED: throwaway needs --mp-config-out (r3sw7)")
        if not is_live and (os.path.abspath(a.config_out) == served_ab or os.path.abspath(a.mp_out) == served_mp):
            sys.exit("REFUSED: throwaway may not target a served config (r3sw7)")

    c = sqlite3.connect(a.db)
    p038 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,))}
    pmi_pre = {o for o, v in p038.items() if PMITOK in toks(v)}
    assert len(pmi_pre) == 154, "PMI-haver != 154 (%d)" % len(pmi_pre)
    citick = {o for o, v in p038.items() if CITOK in toks(v)}
    assert len(citick) == 42, "038 CI-tick moved: %d" % len(citick)
    lvl = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (LEVEL,))}
    havers = {o for o, v in lvl.items() if v in LEVELS}
    assert len(havers) == 52, "level-havers moved: %d" % len(havers)
    ip = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (IP,)) if v != "No"}
    assert havers <= ip, "%d CI-havers are NOT IP-havers — bundle premise broken" % len(havers - ip)
    add = sorted(havers - citick)     # level-haver, 038 didn't tick -> ADD
    drop = sorted(citick - havers)    # 038 ticked, not level-haver -> REMOVE
    assert len(add) == 41 and len(drop) == 31
    non_hav = sorted(set(lvl) - havers)   # the 168 no-CI (Not offered + Not applicable)
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(set(add) | set(drop) | set(non_hav))),
                                   sorted(set(add) | set(drop) | set(non_hav)))}
    assert src == {"seed"}, "non-seed org in the CI set: %s" % src
    base_pre = {q: {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))}
                for q in PMI_CHILDREN}
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  align 038 CI-tick 42 -> 52 (ADD %d level-only, REMOVE %d tick-only); PMI preserved" % (len(add), len(drop)))
    print("  collapse Not-offered+Not-applicable (%d rows) + flat-condition level on 52 (no re-weight): %s"
          % (len(non_hav), {v: sum(1 for o in havers if lvl[o] == v) for v in LEVELS}))
    print("  chain: level (52) ⊆ CI-tick (52) ⊆ IP (%d)" % len(ip))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    for o in add + drop:
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw24 pre-align", P038, o))
    for o in add:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                    ("; ".join(toks(p038[o]) + [CITOK]), P038, o))
    for o in drop:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                    ("; ".join(t for t in toks(p038[o]) if t != CITOK), P038, o))
    cur.executemany("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", [(STAMP + " r3sw24 pre-collapse", LEVEL, o) for o in non_hav])
    cur.executemany("DELETE FROM answers WHERE question_id=? AND org_id=?", [(LEVEL, o) for o in non_hav])

    # ---- coherence + PMI-safeguard asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    pmi_post = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,)) if PMITOK in toks(v)}
    assert pmi_post == pmi_pre and len(pmi_post) == 154, "PMI-TICK MOVED — HARD ABORT"
    for q, s in base_pre.items():
        assert {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))} == s, "PMI child %s MOVED" % q
    citick2 = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,)) if CITOK in toks(v)}
    assert citick2 == havers and len(citick2) == 52, "038 CI-tick != 52 level-havers"
    lnow = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (LEVEL,))}
    assert set(lnow) == havers and all(v in LEVELS for v in lnow.values()), "level-answerers != 52 havers"
    assert citick2 <= ip, "CI-tick not ⊆ IP after align"
    lvl_dist = {v: sum(1 for x in lnow.values() if x == v) for v in LEVELS}
    assert lvl_dist == {"Fixed lump sum": 21, "1x salary": 19, "2x+ salary": 12}, lvl_dist

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab["metrics"][LEVEL] = {"mode": "conditioned", "base_label": "organisations offering critical illness cover",
                            "parent": {"qid": P038, "contains": CITOK},
                            "_r3sw24": "038 CI-tick aligned up to the dedicated 52 (IP pattern); flat condition (bundle benefit, no sector-gate); level split unchanged; CI⊆IP chain; verdict suppressed"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    mp = json.load(open(served_mp, encoding="utf-8"))
    mp["metrics"][LEVEL]["unbenchmarked"] = True
    mp["metrics"][LEVEL]["_r3sw24"] = "verdict SUPPRESSED — EST level split (no market position); group-risk bundle metric"
    mp_text = json.dumps(mp, indent=2, ensure_ascii=False)
    c.commit()
    for path, text in ((a.config_out, ab_text), (a.mp_out, mp_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw24_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([P038, "CI-tick 42->52 (align up to dedicated metric); PMI preserved", "add 41 / remove 31"])
        w.writerow([LEVEL, "conditioned on 52; collapse Not-offered+Not-applicable (no re-weight)", json.dumps(lvl_dist)])
    print(json.dumps({"applied": True, "ci_tick": "42 -> 52 (aligned to dedicated metric)", "level_split": lvl_dist,
                      "chain": "level 52 ⊆ CI-tick 52 ⊆ IP %d" % len(ip),
                      "pmi_safeguard": "PMI 154 byte-identical + 5 children unmoved (asserted)",
                      "answers": n_before - len(non_hav), "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
