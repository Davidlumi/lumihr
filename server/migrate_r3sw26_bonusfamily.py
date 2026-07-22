"""
r3sw26 — bonus-exists family: clear the impossible, remap governance haver-N/A, condition all six.

Parent REW_INC_103 != 'None' (179 bonus-havers) is the sole clean bonus authority (no 038 tick,
no competing existence signal — diagnostic r3sw25-B). The 41 None-orgs systematically over-answered
the bonus-detail children with realistic values; r3sw5 PART-B fixed this for clawback (_071) only.
This diff extends the r3sw5 precedent to the other five and conditions all six.

  FIX 1  CLEAR THE IMPOSSIBLE (precedented r3sw5 PART-B). For the 5 detail children, set every
         None-org's substantive answer -> "Not applicable" (a non-bonus org cannot have a pool-funding
         method / gatekeeper / payout% / malus / bonus measure). Clear, NOT align — the parent is the
         sole authority and content can't distinguish impossible-from-real (the impossible answers
         mirror the clean-haver distributions). Counts: POOLFUND 26, _065 29, _104 40, _070 39,
         _060 26 (=160).
  FIX 2  GOVERNANCE HAVER-N/A -> "No" (the 2 Yes/No governance metrics only). A bonus-haver who
         answered "Not applicable" on gatekeeper/malus means "No, we don't use that feature" — a
         legitimate Yes/No reading, so remap keeps the base at 179 (honest prevalence; leaving out
         would inflate the Yes-rate). _065: 28 -> No, _070: 3 -> No. NOT applied to the 3 descriptive
         children (POOLFUND/_104/_060 have no "No" option — haver-N/A is a genuine "didn't specify"
         gap; leave-base). NOT applied to _071 (data already correct r3sw5; render-only).
  FIX 3  CONDITION ALL SIX answerer_only (drop "Not applicable" from graph+n). Bases: _071 147,
         POOLFUND 132, _065 179, _104 165, _070 179, _060 136. _071 is render-only (no data change).
  FIX 4  COHERENCE — six subset pairs (child-substantive ⊆ bonus-exists), mirroring the standing
         r3sw5 071-guard; the _071 pair is UPGRADED from child_value="Yes" to child_value_not="Not
         applicable" (broader: a "No" clawback answer also implies a bonus exists). A future INC_103
         reseed that re-breaks any child's conditioning fails the freeze gate.

Data = UPDATE-only (no INSERT/DELETE); answers row-count unchanged. Dual-config atomic (r3sw7):
applicable_bases via --config-out, coherence pairs via --sb-out/--gm-out (structured_bases +
generated_marginals, identical lists). Dry-run default; --write --confirmed-by-david for served.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = "REW_INC_103"
NA = "Not applicable"
CLAWBACK = "REW_INC_071"
FIVE = ["REW263_INC_POOLFUND", "REW_INC_065", "REW_INC_104", "REW_INC_070", "REW_INC_060"]
GOV = ["REW_INC_065", "REW_INC_070"]          # Yes/No governance: haver-N/A -> "No"
ALL6 = [CLAWBACK] + FIVE
MULTI = {"REW_INC_060"}
STAMP = "2026-07-22"
TOUCHED = FIVE                                  # only these 5 have answer edits
EXP_CICOVER = {"REW263_INC_POOLFUND": 26, "REW_INC_065": 29, "REW_INC_104": 40, "REW_INC_070": 39, "REW_INC_060": 26}
EXP_HAVER_NA = {"REW_INC_065": 28, "REW_INC_070": 3}
EXP_BASE = {"REW_INC_071": 147, "REW263_INC_POOLFUND": 132, "REW_INC_065": 179,
            "REW_INC_104": 165, "REW_INC_070": 179, "REW_INC_060": 136}
BASE_LABEL = "organisations with a bonus scheme"
NOTE = ("child-substantive ⊆ bonus-exists (REW_INC_103 != None) — r3sw26 extends the r3sw5 071-guard "
        "to the whole bonus-detail family; a non-bonus org cannot answer bonus detail, and a future "
        "INC_103 reseed that re-breaks the conditioning fails the freeze gate")


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def is_subst(v, multi):
    if multi:
        return any(t != NA for t in toks(v))
    return bool(v) and v != NA


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def child_subst_set(c, qid):
    multi = qid in MULTI
    return {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value!=''", (qid,))
            if is_subst(v, multi)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", dest="cout", default=None)     # applicable_bases
    ap.add_argument("--sb-out", dest="sbout", default=None)        # structured_bases
    ap.add_argument("--gm-out", dest="gmout", default=None)        # generated_marginals
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
    pv = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (PARENT,))}
    havers = {o for o, v in pv.items() if v not in ("", "None")}
    none_orgs = {o for o, v in pv.items() if v == "None"}
    assert len(havers) == 179 and len(none_orgs) == 41, (len(havers), len(none_orgs))

    # measure the edits
    clear = {}      # qid -> [orgs None+substantive -> N/A]
    remap = {}      # qid -> [havers N/A -> No]
    for qid in FIVE:
        multi = qid in MULTI
        subst = {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value!=''", (qid,))
                 if is_subst(v, multi)}
        clear[qid] = sorted(subst & none_orgs)
        assert len(clear[qid]) == EXP_CICOVER[qid], "%s CICOVER %d != expected %d" % (qid, len(clear[qid]), EXP_CICOVER[qid])
    for qid in GOV:
        na_ans = {o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value=?", (qid, NA))}
        remap[qid] = sorted(na_ans & havers)
        assert len(remap[qid]) == EXP_HAVER_NA[qid], "%s haver-N/A %d != expected %d" % (qid, len(remap[qid]), EXP_HAVER_NA[qid])
    n_clear = sum(len(v) for v in clear.values())
    n_remap = sum(len(v) for v in remap.values())
    assert n_clear == 160, n_clear

    # everything cleared/remapped must be a seed org
    edit_orgs = sorted({o for v in clear.values() for o in v} | {o for v in remap.values() for o in v})
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(edit_orgs)), edit_orgs)}
    assert src <= {"seed"}, "non-seed org in the edit set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  parent REW_INC_103: havers=%d None=%d" % (len(havers), len(none_orgs)))
    print("  FIX1 clear impossible (None-org substantive -> N/A):")
    for qid in FIVE:
        print("    %-22s %3d cleared" % (qid, len(clear[qid])))
    print("  FIX2 governance haver-N/A -> No: " + ", ".join("%s %d" % (q, len(remap[q])) for q in GOV))
    print("  total answer edits: %d clear + %d remap = %d (UPDATE-only, row-count unchanged)" % (n_clear, n_remap, n_clear + n_remap))
    if not a.write:
        # dry-run: show the resulting bases without mutating
        print("  resulting bases (answerer_only over havers):")
        for qid in ALL6:
            print("    %-22s base %d" % (qid, EXP_BASE[qid]))
        print("dry-run complete — pass --write (+ --confirmed-by-david + staged outs for throwaway)")
        c.close(); return

    pre_hash = book_hash(c)
    cur = c.cursor()
    # history snapshot for every row we touch
    for qid in FIVE:
        for o in clear[qid]:
            cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                           SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                           WHERE question_id=? AND org_id=?""", (STAMP + " r3sw26 pre-clear", qid, o))
    for qid in GOV:
        for o in remap[qid]:
            cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                           SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                           WHERE question_id=? AND org_id=?""", (STAMP + " r3sw26 pre-remap", qid, o))
    # FIX 1 — clear impossible
    for qid in FIVE:
        cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                        [(NA, qid, o) for o in clear[qid]])
    # FIX 2 — governance remap
    for qid in GOV:
        cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                        [("No", qid, o) for o in remap[qid]])

    # ---- asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED (UPDATE-only expected)"
    for qid in FIVE:                                         # zero None-org substantive
        subst = child_subst_set(c, qid)
        assert not (subst & none_orgs), "%s still has None-org substantive: %d" % (qid, len(subst & none_orgs))
        assert subst <= havers, "%s substantive not ⊆ havers: %d strays" % (qid, len(subst - havers))
    for qid in GOV:                                          # base holds at 179
        subst = child_subst_set(c, qid)
        assert subst == havers, "%s substantive != 179 havers (%d)" % (qid, len(subst))
    # _071 untouched + ⊆ havers
    cb = child_subst_set(c, CLAWBACK)
    assert cb <= havers, "clawback substantive not ⊆ havers"

    # ---- config writes (atomic) ----  merge into the SERVED applicable_bases as the base
    ab = json.load(open(served_ab, encoding="utf-8"))
    for qid in ALL6:
        ab.setdefault("metrics", {})[qid] = {
            "mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
            "_r3sw26": "bonus-exists family: %s (r3sw5 PART-B extension; conditioned on REW_INC_103 havers)" %
                       ("render-only, data already correct r3sw5" if qid == CLAWBACK else "impossible cleared + conditioned")}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)

    # coherence pairs — replace _071 Yes-pair with substantive; add the other five
    sb = json.load(open(served_sb, encoding="utf-8"))
    pairs = [p for p in (sb.get("_coherence_pairs") or []) if p.get("child") != CLAWBACK]
    for qid in ALL6:
        pairs.append({"child": qid, "child_value_not": NA, "parent": PARENT,
                      "parent_value_not": "None", "relation": "subset_orgs", "note": NOTE})
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
    with open(os.path.join(man_dir, "r3sw26_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        for qid in FIVE:
            w.writerow([qid, "clear None-org substantive -> N/A", "%d cleared" % len(clear[qid])])
        for qid in GOV:
            w.writerow([qid, "governance haver-N/A -> No", "%d remapped" % len(remap[qid])])
        for qid in ALL6:
            w.writerow([qid, "declare answerer_only + subset pair", "base %d" % EXP_BASE[qid]])
    print(json.dumps({"applied": True, "clear": {q: len(clear[q]) for q in FIVE},
                      "remap": {q: len(remap[q]) for q in GOV},
                      "answer_edits": n_clear + n_remap, "row_count": "%d (unchanged)" % n_before,
                      "bases": EXP_BASE, "pairs_added": len(ALL6), "non_target_book": "hash-identical",
                      "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
