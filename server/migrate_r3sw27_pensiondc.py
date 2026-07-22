"""
r3sw27 (CORRECTED) — pension-DC ×2: clear over-answered DC-detail, condition on the 199 DC-havers,
PARENT FROZEN/UNTOUCHED.

CORRECTION on the record: the first r3sw27 direction (reclassify 21 DB -> Hybrid/DC) was WRONG — it
missed r3sw3, which ruled (TPR Occupational DB landscape 2025, grade A, NEW-JOINER basis, CARE=DB)
that public-sector "DB" is correct and TIER-1 FROZE REW26_BEN_PENSION_TYPE (DC .8864 / DB .0955 /
Hybrid .0182). So this is the bonus over-answer pattern after all: the 21 DB orgs are genuinely DB/CARE
but over-answered DC-detail that a DB/CARE scheme cannot have (no member DC default fund, no AE default
contribution rate). CLEAR the DC-detail; DO NOT touch the parent.

  FIX 1  CLEAR the 21 DB orgs' impossible DC-detail -> N/A: AE-rate (20 substantive) -> "Not applicable
         (no DC scheme)"; green-fund (18 substantive) -> "Not applicable (no DC default fund)".
  FIX 2  RE-ANCHOR the 17 AE DEFERRAL: DC-havers who answered "Not applicable (no DC scheme)" on AE
         -> "Statutory minimum only" (genuine DC-havers who auto-enrol; statutory floor is the honest
         answer, not exclusion). green DEFERRAL -> leave-base (no clean floor).
  FIX 3  CONDITION both children answerer_only on the 199 DC-havers (DC 195 + Hybrid 4): AE base 199,
         green base 170. Subset pairs child-substantive ⊆ DC-havers (parent != DB).

PARENT HARD CONSTRAINT: REW26_BEN_PENSION_TYPE is tier-1 frozen — asserted BYTE-IDENTICAL before/after
(book_hash excludes only the two children; explicit per-org + raw-dist assert). Data = UPDATE-only.
Dual-config atomic (r3sw7); dry-run default; --write --confirmed-by-david for served.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = "REW26_BEN_PENSION_TYPE"
AE, AENA, AEFLOOR = "REW264_PEN_AEDEFAULT", "Not applicable (no DC scheme)", "Statutory minimum only"
GREEN, GRNA = "REW264_PEN_GREENDEFAULT", "Not applicable (no DC default fund)"
CHILDREN = [AE, GREEN]
TOUCHED = CHILDREN                              # parent NOT touched
STAMP = "2026-07-22"
FROZEN_PARENT = {"DC": 195, "DB": 21, "Hybrid": 4}   # r3sw3 tier-1 — must be unmoved
EXP = {"ae_clear": 20, "gr_clear": 18, "ae_reanchor": 17}
BASE = {AE: 199, GREEN: 170}
BASE_LABEL = "organisations with a DC pension scheme"
NA_OF = {AE: AENA, GREEN: GRNA}
NOTE = ("child-substantive ⊆ DC-havers (REW26_BEN_PENSION_TYPE != DB) — r3sw27 clear-direction; a "
        "DB/CARE scheme has no DC default fund / AE default rate, so DC-detail answers must be N/A; "
        "parent is r3sw3 tier-1 frozen and untouched")


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def subst_set(c, qid, na):
    return {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value!=''", (qid,))
            if v != na}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", dest="cout", default=None)
    ap.add_argument("--sb-out", dest="sbout", default=None)
    ap.add_argument("--gm-out", dest="gmout", default=None)
    a = ap.parse_args()

    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    served_sb = os.path.join(ROOT, "structured_bases.json")
    served_gm = os.path.join(ROOT, "generated_marginals.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if is_live:
            a.cout = a.cout or served_ab; a.sbout = a.sbout or served_sb; a.gmout = a.gmout or served_gm
            if not a.confirmed:
                print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
        else:
            for nm, v in (("--config-out", a.cout), ("--sb-out", a.sbout), ("--gm-out", a.gmout)):
                if v is None:
                    sys.exit("REFUSED: throwaway needs %s (r3sw7)" % nm)
            if os.path.abspath(a.cout) == served_ab or os.path.abspath(a.sbout) == served_sb \
                    or os.path.abspath(a.gmout) == served_gm:
                sys.exit("REFUSED: throwaway may not target a served config (r3sw7)")

    c = sqlite3.connect(a.db)
    pt = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (PARENT,))}
    DB = {o for o, v in pt.items() if v == "DB"}
    DCH = {o for o, v in pt.items() if v not in ("", "DB")}     # DC + Hybrid = 199
    parent_dist = {k: sum(1 for v in pt.values() if v == k) for k in FROZEN_PARENT}
    assert parent_dist == FROZEN_PARENT, "parent dist drifted from r3sw3 frozen: %s" % parent_dist
    assert len(DCH) == 199 and len(DB) == 21, (len(DCH), len(DB))
    parent_pre = dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (PARENT,)))

    ae, gr = ({o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))}
              for q in (AE, GREEN))
    ae_clear = sorted(o for o in DB if ae.get(o, "") not in ("", AENA))
    gr_clear = sorted(o for o in DB if gr.get(o, "") not in ("", GRNA))
    ae_reanchor = sorted(o for o in DCH if ae.get(o, "") == AENA)
    assert len(ae_clear) == EXP["ae_clear"], len(ae_clear)
    assert len(gr_clear) == EXP["gr_clear"], len(gr_clear)
    assert len(ae_reanchor) == EXP["ae_reanchor"], len(ae_reanchor)
    edit_orgs = sorted(set(ae_clear) | set(gr_clear) | set(ae_reanchor))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(edit_orgs)), edit_orgs)}
    assert src <= {"seed"}, "non-seed org in edit set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  parent (FROZEN/UNTOUCHED): DC %d / DB %d / Hybrid %d ; DC-havers=%d"
          % (parent_dist["DC"], parent_dist["DB"], parent_dist["Hybrid"], len(DCH)))
    print("  FIX1 clear DB over-answers -> N/A: AE %d, green %d" % (len(ae_clear), len(gr_clear)))
    print("  FIX2 AE DEFERRAL -> '%s': %d ; green DEFERRAL -> leave-base" % (AEFLOOR, len(ae_reanchor)))
    print("  total edits = %d (UPDATE-only)" % (len(ae_clear) + len(gr_clear) + len(ae_reanchor)))
    print("  resulting bases: AE %d, green %d" % (BASE[AE], BASE[GREEN]))
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + staged outs for throwaway)")
        c.close(); return

    pre_hash = book_hash(c)
    cur = c.cursor()
    for qid, orgs, tag in ((AE, ae_clear, "pre-clear"), (GREEN, gr_clear, "pre-clear"), (AE, ae_reanchor, "pre-reanchor")):
        for o in orgs:
            cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                           SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                           WHERE question_id=? AND org_id=?""", (STAMP + " r3sw27 " + tag, qid, o))
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(AENA, AE, o) for o in ae_clear])
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(GRNA, GREEN, o) for o in gr_clear])
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(AEFLOOR, AE, o) for o in ae_reanchor])

    # ---- asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED (parent must be byte-identical!)"
    assert dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (PARENT,))) == parent_pre, \
        "PARENT ANSWERS MOVED — HARD ABORT (r3sw3 tier-1 frozen)"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    for qid in CHILDREN:
        na = NA_OF[qid]
        subst = subst_set(c, qid, na)
        assert not (subst & DB), "%s still has DB-org substantive: %d" % (qid, len(subst & DB))
        assert subst <= DCH, "%s substantive not ⊆ DC-havers: %d strays" % (qid, len(subst - DCH))
    ae_now = subst_set(c, AE, AENA)
    assert ae_now == DCH, "AE substantive != 199 DC-havers (%d)" % len(ae_now)   # all DC-havers now answer AE
    assert all(v == AEFLOOR for v in (dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND org_id IN (%s)"
               % ",".join("?" * len(ae_reanchor)), [AE] + ae_reanchor)).values())), "re-anchored not all statutory-min"

    # ---- config writes ----
    ab = json.load(open(served_ab, encoding="utf-8"))
    for qid in CHILDREN:
        ab.setdefault("metrics", {})[qid] = {
            "mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA_OF[qid]],
            "_r3sw27": "pension-DC clear-direction (r3sw3-consistent): DB over-answers cleared, conditioned on 199 DC-havers; parent frozen/untouched"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    sb = json.load(open(served_sb, encoding="utf-8"))
    pairs = list(sb.get("_coherence_pairs") or [])
    for qid in CHILDREN:
        pairs.append({"child": qid, "child_value_not": NA_OF[qid], "parent": PARENT,
                      "parent_value_not": "DB", "relation": "subset_orgs", "note": NOTE})
    sb["_coherence_pairs"] = pairs
    sb_text = json.dumps(sb, indent=1, ensure_ascii=False)
    gm = json.load(open(served_gm, encoding="utf-8"))
    gm["coherence_pairs"] = pairs
    gm_text = json.dumps(gm, indent=1, ensure_ascii=False)

    c.commit()
    for path, text in ((a.cout, ab_text), (a.sbout, sb_text), (a.gmout, gm_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw27_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([AE, "clear DB over-answers -> N/A + DEFERRAL -> statutory-min", "clear %d + reanchor %d" % (len(ae_clear), len(ae_reanchor))])
        w.writerow([GREEN, "clear DB over-answers -> N/A (DEFERRAL leave-base)", "clear %d" % len(gr_clear)])
        for qid in CHILDREN:
            w.writerow([qid, "declare answerer_only + subset pair", "base %d" % BASE[qid]])
    print(json.dumps({"applied": True, "clear": {"AE": len(ae_clear), "green": len(gr_clear)},
                      "ae_reanchor": len(ae_reanchor), "edits": len(ae_clear) + len(gr_clear) + len(ae_reanchor),
                      "row_count": "%d (unchanged)" % n_before, "bases": {AE: BASE[AE], GREEN: BASE[GREEN]},
                      "parent": "FROZEN/UNTOUCHED (DC 195/DB 21/Hybrid 4 byte-identical)", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
