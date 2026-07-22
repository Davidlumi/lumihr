"""
r3sw22 — PMI excess/cost-share conditioning (REW263_BEN_PMIEXCESS): the 6th PMI-family child.

"Not applicable" 56.4% (no-PMI orgs) distorted the cost-share distribution. Condition on the 154
PMI-havers via answerer_only (exclude "Not applicable"). The equality-vs-subset check came back
MESSY: of 154 havers only 70 report a real excess (84 answered N/A — no excess detail), and 26
NON-havers held a real excess (CICOVER). RULED (David, subset-no-retag): clear the 26 CICOVER to
"Not applicable" (a non-haver cannot have a PMI excess); leave the 84 havers-with-N/A untouched
(NO re-weight); the excess renders over the 70 excess-specifiers as a SUBSET ⊆ 154.
  DATA: 26 UPDATEs (CICOVER non-haver excess -> "Not applicable"). No re-weight of the 70's dist.
  CONFIG: answerer_only na_options=["Not applicable"]; verdict already suppressed (unchanged).
  PAIR: child_value_not "Not applicable" ⊆ REW_BEN_038 PMI (6th family child guarded).
  SAFEGUARD: this ADDS a child conditioning on the 154-set — it does NOT move the parent. Assert
  the PMI parent (154) + the 5 existing children bases are ALL unmoved.
Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QID, PARENT, TOKEN = "REW263_BEN_PMIEXCESS", "REW_BEN_038", "Private Medical Insurance (PMI)"
NA = "Not applicable"
REAL = ["No excess", "Excess per claim", "Excess per year", "Employee co-pays premium"]
STAMP = "2026-07-21"
PMI_CHILDREN = {"REW265_BEN_PMICOMP": 154, "REW_BEN_139": 154, "REW_BEN_044": 154,
                "3faf1f0c-f753-497f-a395-384bba38c5e3": 154}


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
                       "WHERE question_id != ? ORDER BY 1,2,3,4", (QID,)):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def havers(c):
    return {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
            if TOKEN in toks(v)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            a.config_out = served_ab if is_live else sys.exit("REFUSED: throwaway needs --config-out (r3sw7)")
        elif not is_live and os.path.abspath(a.config_out) == served_ab:
            sys.exit("REFUSED: throwaway may not target the served config (r3sw7)")

    c = sqlite3.connect(a.db)
    hv = havers(c)
    assert len(hv) == 154, "PMI-haver set != 154 (%d) — re-diagnose" % len(hv)
    A = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (QID,))}
    real = {o for o, v in A.items() if v != NA}
    cicover = sorted(real - hv)      # non-havers with a real excess -> clear
    assert len(cicover) == 26, "CICOVER count moved: %d (expected 26) — re-diagnose" % len(cicover)
    assert len(real & hv) == 70 and len(hv - real) == 84, (len(real & hv), len(hv - real))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(cicover)), cicover)}
    assert src == {"seed"}, "non-seed CICOVER org: %s" % src
    base_pre = {q: {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))}
                for q in PMI_CHILDREN}

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  RELATION: SUBSET — 70 excess-specifiers ⊆ 154 havers; 84 havers-with-N/A left (no re-weight)")
    print("  clear %d CICOVER non-haver excesses -> 'Not applicable' | answerer_only excludes N/A | render base 70" % len(cicover))
    if not a.write:
        print("  70-org excess dist (unchanged):", {v: sum(1 for o in real & hv if A[o] == v) for v in REAL})
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    cur.executemany("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", [(STAMP + " r3sw22 pre-clear", QID, o) for o in cicover])
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                    [(NA, QID, o) for o in cicover])

    # ---- coherence + PMI-family-untouched asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "answer count changed"
    real2 = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (QID,))
             if v != NA}
    assert real2 <= hv and len(real2) == 70, "excess-specifiers not the 70-haver subset (%d)" % len(real2)
    assert not (real2 - hv), "a non-haver still holds an excess"
    assert havers(c) == hv and len(hv) == 154, "PMI parent moved"
    for q, s in base_pre.items():
        assert {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))} == s, \
            "PMI child %s base MOVED" % q

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab["metrics"][QID] = {"mode": "answerer_only",
                          "base_label": "PMI-holding organisations reporting a cost-share",
                          "na_options": [NA],
                          "_r3sw22": "6th PMI-family child; SUBSET (70 excess-specifiers ⊆ 154 havers); 84 havers-with-N/A left, 26 non-haver excesses cleared; no re-weight; verdict already suppressed"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ab_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw22_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([QID, "clear %d CICOVER -> N/A + answerer_only (subset base 70)" % len(cicover),
                    json.dumps({v: sum(1 for o in real2 if c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (QID, o)).fetchone()[0] == v) for v in REAL})])
    print(json.dumps({"applied": True, "relation": "SUBSET (70 ⊆ 154)", "cicover_cleared": len(cicover),
                      "excess_base": 70, "havers_with_na_left": 84, "conditioning": "answerer_only excludes N/A",
                      "pmi_family": "parent 154 + 5 children bases UNMOVED (asserted)",
                      "answers": n_before, "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
