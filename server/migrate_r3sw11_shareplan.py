"""
r3sw11 — share-plan family: coherence repair + conditioning (ruled, all five points).

REPAIR (77 rows, ALL UPDATEs — answer count unchanged, asserted):
  SAYEDISC  the 12 SIP-only '20% (maximum)' artifacts -> 'Not applicable' (base -> SAYE-side 31)
  SIPELEM   16 SAYE-only element fabrications -> 'No SIP operated'; the 6 real SIP operators
            currently 'No SIP operated' -> elements seeded INCIDENCE-MATCHED to the 12 legit
            operators' element mix (diff8 pattern — no flat modal spike; every org gets >=1)
  EMICSOP   parent authority WINS (one-authority principle): 27 parent-no-shares substantive
            -> 'Not applicable (no share capital)'; 16 parent-has-shares N/A -> 'Neither'
            (post: EMI 24 / CSOP 11 / Both 6 / Neither 140 / N/A 39 — N/A sets align exactly)
  SHAREPART clean (0/0) — untouched.

CONDITIONING (config, atomic with the data write): 4 answerer_only declarations into
applicable_bases.json via --config-out (staged path REQUIRED for throwaway; served path only
when --db is the live book — r3sw7 doctrine). The 4 subset pairs live in structured_bases /
generated_marginals and are enforced by qa_plausibility (child_value_not / parent_value_in).

Post-asserts run PRE-COMMIT (any failure = full rollback): all four contradiction classes
recompute to ZERO, exact target dists, book hash over untouched qids identical, per-cell
before/after manifest emitted. Dry-run default; apply needs --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = "REW264_INC_SHAREPLAN"
SHAREPART, SAYEDISC, SIPELEM, EMICSOP = ("REW265_INC_SHAREPART", "REW265_INC_SAYEDISC",
                                         "REW265_INC_SIPELEM", "REW264_INC_EMICSOP")
TOUCHED = [SAYEDISC, SIPELEM, EMICSOP]
SIP_NA, EMI_NA, P_NA = "No SIP operated", "Not applicable (no share capital)", "Not applicable (no shares)"
ELEMENTS = ["Free shares", "Partnership shares", "Matching shares", "Dividend shares"]  # canonical DB order
STAMP = "2026-07-19"
DECLS = {
    SHAREPART: {"mode": "answerer_only", "base_label": "organisations operating a share plan",
                "na_options": ["Not applicable"],
                "_r3sw11": "(a) share-plan family: conditioned on any-plan (43); pair-guarded"},
    SAYEDISC: {"mode": "answerer_only", "base_label": "organisations offering SAYE",
               "na_options": ["Not applicable"],
               "_r3sw11": "(a) share-plan family: conditioned on the SAYE side (31); 12 SIP-only artifacts repaired"},
    SIPELEM: {"mode": "answerer_only", "base_label": "organisations operating a SIP",
              "na_options": [SIP_NA],
              "_r3sw11": "(a) share-plan family: conditioned on the SIP side (18 — accepted thin base); two-sided repair"},
    EMICSOP: {"mode": "answerer_only", "base_label": "organisations with share capital",
              "na_options": [EMI_NA],
              "_r3sw11": "(a) share-plan family: conditioned on share-capital (181); parent N/A is THE authority"},
}


def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def contradictions(c):
    Pm = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (P,)))
    ops_any = {o for o, v in Pm.items() if v in ("SAYE", "SIP", "Both")}
    ops_saye = {o for o, v in Pm.items() if v in ("SAYE", "Both")}
    ops_sip = {o for o, v in Pm.items() if v in ("SIP", "Both")}
    cap = {o for o, v in Pm.items() if v != P_NA}
    out = {}
    for qid, na_lab, base in ((SHAREPART, "Not applicable", ops_any), (SAYEDISC, "Not applicable", ops_saye),
                              (SIPELEM, SIP_NA, ops_sip), (EMICSOP, EMI_NA, cap)):
        A = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (qid,)))
        sub = {o for o, v in A.items() if na_lab not in toks(v)}
        out[qid] = {"cic": sub - base, "deff": base - sub, "sub": sub, "base": base, "A": A}
    return Pm, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    a = ap.parse_args()

    served_db = os.path.join(ROOT, "lumi.db")
    served_cfg = os.path.join(ROOT, "data", "applicable_bases.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            if is_live:
                a.config_out = served_cfg
            else:
                sys.exit("REFUSED: throwaway --write needs an explicit staged --config-out (r3sw7 doctrine)")
        elif not is_live and os.path.abspath(a.config_out) == served_cfg:
            sys.exit("REFUSED: a throwaway --write may not target the served config (r3sw7 doctrine)")

    c = sqlite3.connect(a.db); c.row_factory = None

    Pm, con = contradictions(c)
    d12 = sorted(o for o in con[SAYEDISC]["cic"] if Pm.get(o) == "SIP")
    assert con[SAYEDISC]["cic"] == set(d12) and len(d12) == 12, len(con[SAYEDISC]["cic"])
    assert not con[SAYEDISC]["deff"] and not con[SHAREPART]["cic"] and not con[SHAREPART]["deff"]
    w16 = sorted(o for o in con[SIPELEM]["cic"] if Pm.get(o) == "SAYE")
    g6 = sorted(con[SIPELEM]["deff"])
    assert con[SIPELEM]["cic"] == set(w16) and len(w16) == 16 and len(g6) == 6, (len(con[SIPELEM]["cic"]), len(g6))
    e27 = sorted(con[EMICSOP]["cic"]); n16 = sorted(con[EMICSOP]["deff"])
    assert len(e27) == 27 and len(n16) == 16, (len(e27), len(n16))
    allt = set(d12) | set(w16) | set(g6) | set(e27) | set(n16)
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(allt)), sorted(allt))}
    assert src == {"seed"}, "non-seed org in the repair set: %s" % src

    # SIPELEM incidence-matched seeding for the 6: match the 12 legit operators' element mix
    legit = {o: con[SIPELEM]["A"][o] for o in (con[SIPELEM]["sub"] & con[SIPELEM]["base"])}
    assert len(legit) == 12, len(legit)
    have = {e: sum(1 for v in legit.values() if e in toks(v)) for e in ELEMENTS}
    n_base = 18
    plan6 = {o: [] for o in g6}
    for e in ELEMENTS:
        want = round(have[e] / 12.0 * n_base)
        deficit = max(0, want - have[e])
        ranked = sorted(g6, key=lambda o: hashlib.sha256(("r3sw11|%s|%s" % (e, o)).encode()).hexdigest())
        for o in ranked[:deficit]:
            plan6[o].append(e)
    for o in g6:                      # zero-pick would re-create the contradiction — backstop
        if not plan6[o]:
            e = min(ELEMENTS, key=lambda e: have[e] + sum(1 for x in g6 if e in plan6[x]))
            plan6[o].append(e)
    vals6 = {o: ";".join(e for e in ELEMENTS if e in plan6[o]) for o in g6}

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    assert n_before == 232490, n_before
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  SAYEDISC 12 SIP-only -> 'Not applicable' | SIPELEM 16 -> '%s', 6 seeded %s" %
          (SIP_NA, {o[-6:]: vals6[o] for o in g6}))
    print("  EMICSOP 27 -> N/A, 16 -> 'Neither' | total UPDATEs %d | answers stay %d" %
          (len(d12) + len(w16) + len(g6) + len(e27) + len(n16), n_before))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c, TOUCHED)
    cur = c.cursor()
    manifest = []

    def upd(qid, org, newv):
        old = c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (qid, org)).fetchone()[0]
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw11 pre-repair", qid, org))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (newv, qid, org))
        manifest.append([qid, org, old, newv])

    for o in d12: upd(SAYEDISC, o, "Not applicable")
    for o in w16: upd(SIPELEM, o, SIP_NA)
    for o in g6:  upd(SIPELEM, o, vals6[o])
    for o in e27: upd(EMICSOP, o, EMI_NA)
    for o in n16: upd(EMICSOP, o, "Neither")

    # ---- post-asserts BEFORE commit ----
    assert len(manifest) == 77, len(manifest)
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before
    assert book_hash(c, TOUCHED) == pre_hash, "NON-TARGET BOOK CHANGED"
    _, con2 = contradictions(c)
    for qid in (SHAREPART, SAYEDISC, SIPELEM, EMICSOP):
        assert not con2[qid]["cic"] and not con2[qid]["deff"], (qid, len(con2[qid]["cic"]), len(con2[qid]["deff"]))
    emi = dict(c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (EMICSOP,)))
    assert emi == {"EMI": 24, "CSOP": 11, "Both": 6, "Neither": 140, EMI_NA: 39}, emi
    sd = dict(c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (SAYEDISC,)))
    assert sd == {"20% (maximum)": 12, "10–19%": 11, "Under 10%": 5, "No discount": 3, "Not applicable": 189}, sd
    se_sub = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (SIPELEM,))
              if SIP_NA not in toks(v)}
    assert len(se_sub) == 18 and set(se_sub) == con2[SIPELEM]["base"]
    got = {e: sum(1 for v in se_sub.values() if e in toks(v)) for e in ELEMENTS}
    want_all = {e: have[e] + sum(1 for o in g6 if e in plan6[o]) for e in ELEMENTS}
    assert got == want_all, (got, want_all)
    for v in se_sub.values():
        assert toks(v) and set(toks(v)) <= set(ELEMENTS), v

    # ---- config: 4 declarations, serialized pre-commit, written atomically after ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    for qid, e in DECLS.items():
        assert qid not in cfg["metrics"], qid
        cfg["metrics"][qid] = e
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)
    assert all(q in json.loads(cfg_text)["metrics"] for q in DECLS)

    c.commit()

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw11_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric_id", "org_id", "before", "after"]); w.writerows(manifest)
    print(json.dumps({"applied": True, "updates": len(manifest), "answers": n_before,
                      "contradiction_classes": "all four ZERO",
                      "emicsop": emi, "saye_disc_n": 31, "sipelem_n": 18,
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
