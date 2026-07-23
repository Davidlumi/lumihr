"""
r3sw29a — on-call pay-method (REW_PAY_017): clear the over-answer, self-condition on the on-call family.

Ruling A (David): condition REW_PAY_017 on the on-call FAMILY (On-call ∪ Standby ∪ Call-out tick in
REW_PAY_016, N=122). The 203 method-answerers over-answer a pay-method they can't have without an on-call
arrangement; clear the 92 NON-family method-answerers -> "Not offered / not applicable" (the child's own
NA). Post-clear base = 111. The 65 shift-only orgs ARE cleared (shift premium != on-call). Sector reading
is SCATTERED-FLAT (share-of-base: Tech 90/Fin 50/Media 30/ProfSvc 10; office mean ~45% vs operational ~57%)
-> no sector signal to gate on, so CLEAR on the inventory evidence, not a sector-gate.

BUILD SHAPE (b) SELF-CONDITION via own NA (SALSAC precedent): after the clear, the child self-conditions
via answerer_only on its own NA. NO external subset pair (the on-call family is multi-token OC∪SB∪CO and
the pair engine's parent_contains is single-token; extending it would touch shared qa_plausibility.py —
out of scope for an N/A tidy). NO structured_bases/generated_marginals change.

Data = UPDATE-only, config = applicable_bases only. 8 frozen targets asserted byte-identical. Dual-config
(r3sw7); dry-run default; --write --confirmed-by-david for served.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = "REW_PAY_017"
NA = "Not offered / not applicable"
P16 = "REW_PAY_016"
FAM = ["On-call allowance", "Standby allowance", "Call-out allowance"]
TOUCHED = [CHILD]
STAMP = "2026-07-23"
BASE = 111
BASE_LABEL = "organisations with on-call, standby or call-out arrangements"
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]


def toks(v): return [t.strip() for t in (v or "").split(";") if t.strip()]


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def frozen_snap(c):
    return {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", dest="cout", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if is_live:
            a.cout = a.cout or served_ab
            if not a.confirmed:
                print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
        else:
            if a.cout is None:
                sys.exit("REFUSED: throwaway needs --config-out (r3sw7)")
            if os.path.abspath(a.cout) == served_ab:
                sys.exit("REFUSED: throwaway may not target the served config (r3sw7)")

    c = sqlite3.connect(a.db)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert CHILD not in ft and P16 not in ft, "a target metric is unexpectedly frozen"
    p16 = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (P16,))}
    family = {o for o, v in p16.items() if any(t in FAM for t in toks(v))}
    assert len(family) == 122, "on-call family != 122 (%d)" % len(family)
    p17 = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (CHILD,))}
    m_sub = {o for o, v in p17.items() if v and v != NA}
    clear = sorted(m_sub - family)
    assert len(clear) == 92, "clear set != 92 (%d)" % len(clear)
    assert len(m_sub & family) == BASE, "post base != %d (%d)" % (BASE, len(m_sub & family))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(clear)), clear)}
    assert src <= {"seed"}, "non-seed org in clear set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  on-call family (OC∪SB∪CO)=%d ; method-answerers=%d" % (len(family), len(m_sub)))
    print("  CLEAR %d non-family method-answerers -> %r ; post base = %d" % (len(clear), NA, BASE))
    print("  11-org deferral (family answered NA) left as-is (recorded, not actioned): %d" % len(family - m_sub))
    print("  build shape (b): self-condition via own NA, NO pair, NO engine change")
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + --config-out for throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for o in clear:
        cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw29a pre-clear", CHILD, o))
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NA, CHILD, o) for o in clear])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    assert frozen_snap(c) == frozen_pre, "A FROZEN TARGET METRIC MOVED — HARD ABORT"
    now_sub = {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value!=''", (CHILD,)) if v != NA}
    assert now_sub == (m_sub & family) and len(now_sub) == BASE, "post substantive != on-call family method-answerers"
    assert now_sub <= family, "substantive not ⊆ on-call family"

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab.setdefault("metrics", {})[CHILD] = {"mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
        "_r3sw29a": "on-call pay-method conditioned on the on-call family (OC∪SB∪CO=122); 92 non-family over-answers cleared; self-conditioning via own NA (no pair); scattered-flat, no sector-gate"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.cout)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ab_text)
    os.replace(tmp, a.cout)
    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw29a_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"]); w.writerow([CHILD, "clear 92 non-family -> NA + answerer_only", "base %d" % BASE])
    print(json.dumps({"applied": True, "cleared": len(clear), "base": BASE, "frozen8": "byte-identical",
                      "row_count": "%d (unchanged)" % n_before, "pair": "NONE (self-conditioning)", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
