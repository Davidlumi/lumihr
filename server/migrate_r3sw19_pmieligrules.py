"""
r3sw19 — PMI eligibility-rules redesign: 6-option multi_select sprawl -> 3-option single_select,
conditioned on PMI-havers, re-weighted grade-dominant (EST, verdict-suppressed).

REW_BEN_044 "What are the PMI eligibility rules?" was a 6-option multi_select over all 220 orgs
with "Not offered" (37.3%) the biggest bar and grade/level under-weighted (25%). Redesign:
  TYPE      multi_select -> single_select
  OPTIONS   6 -> 3: All employees / Grade/level restricted / Service length requirement
            (post-probation folds conceptually into Service; contract-type dropped as noise;
             "Not offered" is NOT an option — non-havers leave via PMI-conditioning)
  BASE      conditioned on the 153 PMI-havers (REW_BEN_038 sector-gated set, r3sw15) — same
            PMI-family authority as composition/by-level/premium
  WEIGHT    grade-dominant EST: Grade/level 90% (138) / All employees 8% (12) / Service 2% (3)
  VERDICT   SUPPRESSED (mp-config unbenchmarked=True; was direction=higher_is_better) — EST
The standalone 62.8% offer marginal is RETIRED (generator_rules) — superseded by the 153 base.

Dual-config atomic (r3sw7 path-isolation): --config-out (applicable_bases) + --mp-config-out
(market_position_config). PMI-FAMILY SAFEGUARD: REW_BEN_038 is NOT touched, so the 153-haver set
+ composition/by-level/premium bases are inherently unmoved — asserted explicitly.
Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, re, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QID, PARENT, TOKEN = "REW_BEN_044", "REW_BEN_038", "Private Medical Insurance (PMI)"
NEW_OPTS = [("ALL_EMPLOYEES", "All employees"), ("GRADE_LEVEL_RESTRICTED", "Grade/level restricted"),
            ("SERVICE_LENGTH_REQUIREMENT", "Service length requirement")]
WEIGHT = {"Grade/level restricted": 0.90, "All employees": 0.08, "Service length requirement": 0.02}
STAMP = "2026-07-21"
PMI_CHILDREN = ("REW265_BEN_PMICOMP", "REW_BEN_139")  # conditioned == 153; premium == 153+Thornbridge


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def hrank(o):
    return hashlib.sha256(("r3sw19|" + o).encode()).hexdigest()


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
                       "WHERE question_id != ? ORDER BY 1,2,3,4", (QID,)):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)      # applicable_bases
    ap.add_argument("--mp-config-out", dest="mp_out", default=None)  # market_position_config
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
            sys.exit("REFUSED: throwaway may not target a served config (r3sw7 doctrine)")

    c = sqlite3.connect(a.db)
    havers = sorted({o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
                     if TOKEN in toks(v)})
    assert len(havers) == 153, "PMI-haver set moved: %d — re-diagnose" % len(havers)
    old = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (QID,))}
    assert len(old) == 220, "REW_BEN_044 answerer count moved: %d" % len(old)
    q = c.execute("SELECT type, options_json FROM questions WHERE id=?", (QID,)).fetchone()
    assert q[0] == "multi_select" and len(json.loads(q[1])) == 6, "REW_BEN_044 not in expected 6-opt multi_select state"
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(o.source,'x') FROM orgs o WHERE o.org_id IN (%s)"
                                   % ",".join("?" * len(old)), sorted(old))}
    assert src == {"seed"}, "non-seed REW_BEN_044 answerer: %s" % src

    # PMI-family snapshot (must be inherently unmoved — 038 untouched)
    pmi_children = {kid: {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (kid,))}
                    for kid in PMI_CHILDREN}

    # ruled weighting -> exact counts over 153, hash-assigned
    counts = {lab: round(w * 153) for lab, w in WEIGHT.items()}
    while sum(counts.values()) != 153:
        d = 153 - sum(counts.values()); counts["Grade/level restricted"] += (1 if d > 0 else -1)
    assert counts == {"Grade/level restricted": 138, "All employees": 12, "Service length requirement": 3}, counts
    ranked = sorted(havers, key=hrank)
    seed = {}; i = 0
    for lab in ("All employees", "Service length requirement", "Grade/level restricted"):
        for o in ranked[i:i + counts[lab]]:
            seed[o] = lab
        i += counts[lab]
    assert len(seed) == 153

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  REW_BEN_044: multi_select 6-opt (220 answers) -> single_select 3-opt, conditioned on 153 PMI-havers")
    print("  re-weight (grade-dominant EST): %s" % counts)
    print("  'Not offered' (%d) dropped via conditioning | contract-type dropped | post-probation -> Service"
          % sum(1 for v in old.values() if "Not offered" in toks(v)))
    print("  answers %d -> %d (220 -> 153) | verdict suppressed (unbenchmarked=True)" % (n_before, n_before - 220 + 153))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                (STAMP + " r3sw19 pre-redesign", QID))
    cur.execute("DELETE FROM answers WHERE question_id=?", (QID,))
    ver = c.execute("SELECT question_version FROM questions WHERE id=?", (QID,)).fetchone()[0]
    m = re.match(r"v(\d+)\.(\d+)", ver or "v1.0")
    oj = [{"code": cd, "label": lb, "order": j + 1, "is_na": False} for j, (cd, lb) in enumerate(NEW_OPTS)]
    cur.execute("UPDATE questions SET type='single_select', options_json=?, question_version=?, "
                "scoring_config_json=? WHERE id=?",
                (json.dumps(oj), "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1),
                 json.dumps({"scoring_method": "single_select", "polarity": "neutral"}), QID))
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,'',?,?)", [(o, QID, seed[o], STAMP + " 09:00:00") for o in havers])

    # ---- coherence + PMI-family-untouched asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (QID,))}
    assert ans == set(havers), "answerers != 153 PMI-havers"
    nowh = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,)) if TOKEN in toks(v)}
    assert nowh == set(havers) and len(nowh) == 153, "PMI-HAVER SET MOVED — abort"
    for kid, prev in pmi_children.items():
        assert {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (kid,))} == prev, \
            "PMI child %s base moved" % kid
    got = dict(c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (QID,)))
    assert got == counts, (got, counts)

    # ---- dual config: applicable_bases (conditioned) + mp-config (suppress verdict) ----
    ab = json.load(open(served_ab, encoding="utf-8"))
    ab["metrics"][QID] = {"mode": "conditioned", "base_label": "PMI-holding organisations",
                          "parent": {"qid": PARENT, "contains": TOKEN},
                          "_r3sw19": "6-opt multi_select redesigned to 3-opt single_select conditioned on the 153 PMI-havers; grade-dominant EST"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    mp = json.load(open(served_mp, encoding="utf-8"))
    mp["metrics"][QID]["unbenchmarked"] = True
    mp["metrics"][QID]["_r3sw19"] = "verdict SUPPRESSED — grade-dominant EST weighting, no market position"
    mp_text = json.dumps(mp, indent=2, ensure_ascii=False)

    c.commit()
    for path, text in ((a.config_out, ab_text), (a.mp_out, mp_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw19_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([QID, "redesign 6->3 single-select, condition on 153, EST-suppress", json.dumps(counts)])
    print(json.dumps({"applied": True, "type": "multi_select -> single_select", "options": "6 -> 3",
                      "base": "153 PMI-havers", "weighting": counts, "answers": n_before - 220 + 153,
                      "verdict": "suppressed (unbenchmarked=True)",
                      "pmi_family": "153 unmoved, composition/by-level bases unmoved — ASSERTED",
                      "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
