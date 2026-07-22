"""
r3sw28 — pension salary-sacrifice NIC-cap ×2: render-only N/A-drop + 8-org coherence tidy.

NOT a defect. Both children (REW264_PEN_SALSACIMPACT, REW264_PEN_SALSACRESPONSE — the 2029 £2,000
pension-salary-sacrifice NIC-cap questions) were ALREADY conditioned by Diff 7 (14 July, ruled ③):
false-NA correction on the any-salsac union (REW26_BEN_SALSAC="Yes" ∪ WEL sal-sac benefit ticks = 197),
"0 substantive-without-evidence", 23 legitimate NA. The master-sweep "73/77" is a re-measurement
artifact — the LOGGED WEL-pension-tick(120) fork gap (Diff 7 F2), not a fresh contradiction.

  FIX 1  RENDER-ONLY N/A-DROP — declare both children answerer_only, dropping the 23 self-declared
         "Not applicable (no sal-sac)" from graph+n -> base 197. The metric self-conditions via its own
         NA (Diff 7's NICSHARING primitive). NO external subset pair — no single metric equals the 197
         any-salsac-union base (SALSAC=Yes 131 / WEL-pension 120 / WEL-any 170), so nothing to nest in;
         self-conditioning is the mechanism (like the life-assurance self-contained case).
  FIX 2  8-ORG COHERENCE TIDY — since Diff 7, 8 orgs drifted each way: 8 substantive-without-evidence
         -> NA; 8 NA-with-evidence (all carry SALSAC=Yes, the FROZEN pension-SS authority) -> substantive,
         RNG-mirrored to the current substantive marginal (Diff-7 primitive sha256(qid|date|org)). Net
         base unchanged (197). Restores "0 substantive-without-evidence" AND "NA == no-evidence".

PARENT FROZEN: REW26_BEN_SALSAC (Yes .5955/No .4045) is tier-1 frozen — asserted BYTE-IDENTICAL. This
diff does NOT re-condition on the 131 pension-SS base (that is the deliberate Diff-7 re-open, Option 2,
NOT this diff). Data = UPDATE-only, config = applicable_bases only (no coherence_pairs change). Dual-config
(r3sw7); dry-run default; --write --confirmed-by-david for served.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMP, RESP = "REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE"
NA = "Not applicable (no sal-sac)"
SALSAC, WEL = "REW26_BEN_SALSAC", "WEL_BMAP_FIN_SALARY_SACRIFICE_001"
CHILDREN = [IMP, RESP]
TOUCHED = CHILDREN
STAMP = "2026-07-22"
FROZEN_SALSAC = {"Yes": 131, "No": 89}
WEL_SS = ("Salary Sacrifice for Pension Contributions", "Cycle-to-Work Scheme", "Childcare Vouchers")
BASE, BASE_LABEL = 197, "organisations offering pension salary sacrifice"


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def rng01(qid, o):
    return int(hashlib.sha256(("%s|%s|%s" % (qid, STAMP, o)).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def assign(qid, o, marginal):
    tot = sum(n for _, n in marginal); r = rng01(qid, o) * tot; acc = 0
    for v, n in marginal:
        acc += n
        if r < acc:
            return v
    return marginal[-1][0]


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
    def val(q): return {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))}
    salsac = val(SALSAC); wel = val(WEL)
    salsac_dist = {k: sum(1 for v in salsac.values() if v == k) for k in FROZEN_SALSAC}
    assert salsac_dist == FROZEN_SALSAC, "SALSAC (frozen) dist drifted: %s" % salsac_dist
    salsac_pre = dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (SALSAC,)))
    union = {o for o, v in salsac.items() if v == "Yes"} | \
            {o for o, v in wel.items() if any(t.strip() in WEL_SS for t in v.split(";"))}
    assert len(union) == 197, "union != 197 (%d)" % len(union)

    imp, resp = val(IMP), val(RESP)
    imp_na = {o for o, v in imp.items() if v == NA}
    sub = {o for o, v in imp.items() if v and v != NA}
    assert imp_na == {o for o, v in resp.items() if v == NA}, "NA sets differ across children"
    assert sub == {o for o, v in resp.items() if v and v != NA}, "substantive sets differ across children"
    sub_no_ev = sorted(sub - union)          # -> NA
    na_with_ev = sorted(imp_na & union)      # -> substantive (RNG fill)
    assert len(sub_no_ev) == 8 and len(na_with_ev) == 8, (len(sub_no_ev), len(na_with_ev))
    assert all(salsac.get(o) == "Yes" for o in na_with_ev), "an NA-with-ev org lacks SALSAC=Yes"
    marg = {q: sorted(((v, n) for v, n in
            {vv: sum(1 for x in val(q).values() if x == vv) for vv in set(val(q).values()) if vv and vv != NA}.items()),
            key=lambda kv: -kv[1]) for q in CHILDREN}
    edit_orgs = sorted(set(sub_no_ev) | set(na_with_ev))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(edit_orgs)), edit_orgs)}
    assert src <= {"seed"}, "non-seed org in edit set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    fills = {q: {o: assign(q, o, marg[q]) for o in na_with_ev} for q in CHILDREN}
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  parent REW26_BEN_SALSAC FROZEN/UNTOUCHED: Yes %d / No %d" % (salsac_dist["Yes"], salsac_dist["No"]))
    print("  FIX1 render-only: declare both answerer_only, drop 23 NA -> base %d (self-conditioning, NO pair)" % BASE)
    print("  FIX2 tidy: %d substantive-without-evidence -> NA ; %d NA-with-evidence(SALSAC=Yes) -> substantive" % (len(sub_no_ev), len(na_with_ev)))
    print("    fills IMPACT :", {o[:8]: fills[IMP][o] for o in na_with_ev})
    print("    fills RESPONSE:", {o[:8]: fills[RESP][o] for o in na_with_ev})
    print("  total data edits = %d (UPDATE-only)" % (2 * (len(sub_no_ev) + len(na_with_ev))))
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + --config-out for throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for q in CHILDREN:
        for o in sub_no_ev + na_with_ev:
            cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                           SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                           WHERE question_id=? AND org_id=?""", (STAMP + " r3sw28 tidy", q, o))
        cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NA, q, o) for o in sub_no_ev])
        cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(fills[q][o], q, o) for o in na_with_ev])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED (SALSAC must be byte-identical!)"
    assert dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (SALSAC,))) == salsac_pre, "SALSAC MOVED — HARD ABORT (frozen)"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    for q in CHILDREN:
        cv = val(q)
        s = {o for o, v in cv.items() if v and v != NA}
        assert s == union, "%s substantive != union after tidy (%d, sym-diff %d)" % (q, len(s), len(s ^ union))
        assert not ({o for o, v in cv.items() if v == NA} & union), "%s NA still intersects union" % q

    ab = json.load(open(served_ab, encoding="utf-8"))
    for q in CHILDREN:
        ab.setdefault("metrics", {})[q] = {"mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
            "_r3sw28": "Diff-7-consistent render tidy: drop self-declared NA -> base 197; 8-org drift realigned to the any-salsac union; parent frozen; NO subset pair (self-conditioning)"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.cout)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ab_text)
    os.replace(tmp, a.cout)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw28_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        for q in CHILDREN:
            w.writerow([q, "declare answerer_only (render N/A-drop) + 8-org tidy", "base %d; 8->NA, 8->substantive" % BASE])
    print(json.dumps({"applied": True, "render": "both answerer_only, drop 23 NA -> base %d" % BASE,
                      "tidy": {"subst_to_na": len(sub_no_ev), "na_to_subst": len(na_with_ev)},
                      "data_edits": 2 * (len(sub_no_ev) + len(na_with_ev)), "row_count": "%d (unchanged)" % n_before,
                      "parent": "REW26_BEN_SALSAC FROZEN byte-identical", "subset_pair": "NONE (self-conditioning)",
                      "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
