"""
r3sw13 — blanket-DK strip: the no-DK rule enforced platform-wide (ruled, all classes).

Scope-driven (r3sw13_ruled_scope.json — NEVER hardcoded ids):
  STRIP    62 DK-type options (61 (a) + PROP_202fecc6 moved from keep): answers n-excluded
           (NEVER redistributed) + option removed from options_json + scoring_config na_codes/
           option_scores pruned + question_version bumped. 3 bank-only (zero answers).
  SPECIALS RED_PAY_01 merged option -> plain 'Other' (substantive); RED_TERM_01 -> plain
           'Not applicable' (is_na); RED_NOTICE_01 -> plain 'Not applicable' (is_na) with its
           r3sw10 applicable-base declaration RELABELLED atomically (na_options must track the
           new label or the declaration validator fails — asserted both sides).
  UNTOUCHED the 3 ruled keeps + PROP_634adacd + REW_BEN_SICK_005 (routed to the N/A programme).

Post-asserts pre-commit (failure = full rollback): exact per-option deletion counts, answers
232,490 -> 231,861, zero DK-type labels left in the bank outside the ruled exceptions,
keeps byte-untouched, RED_NOTICE_01 declaration valid post-relabel, non-target book hash.
Dry-run default; apply needs --write --confirmed-by-david. Config staged via --config-out
(REQUIRED for throwaway; served only when --db is the live book — r3sw7 doctrine).
"""
import argparse, csv, hashlib, json, os, re, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = "2026-07-20"
DK_PAT = re.compile(r"don'?t know|unsure|not sure|not tracked|not measured|access not tracked", re.I)


def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def bump(ver):
    m = re.match(r"v(\d+)\.(\d+)", ver or "v1.0")
    return "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1)


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

    scope = json.load(open(os.path.join(ROOT, "r3sw13_ruled_scope.json"), encoding="utf-8"))
    STRIP, SPECIALS = scope["strip"], scope["specials"]
    KEEP_OPTS, ROUTED = scope["keep_options"], scope["routed_untouched"]
    assert sum(len(v) for v in STRIP.values()) == 62 and len(SPECIALS) == 3
    touched = sorted(set(STRIP) | set(SPECIALS))

    c = sqlite3.connect(a.db)

    # ---- diagnose: exact counts + seed-only + keeps snapshot ----
    plan, del_total = [], 0
    for qid, ents in sorted(STRIP.items()):
        typ, oj = c.execute("SELECT type, options_json FROM questions WHERE id=? AND status='active'", (qid,)).fetchone()
        labels = [o["label"] for o in json.loads(oj)]
        for e in ents:
            assert e["label"] in labels, (qid, e["label"])
            n = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (qid, e["label"])).fetchone()[0]
            if typ == "multi_select" and n == 0:
                tok = sum(1 for (v,) in c.execute("SELECT value FROM answers WHERE question_id=?", (qid,))
                          if e["label"] in (t.strip() for t in (v or "").split(";")))
                assert tok == 0, "multi-select %s carries DK tokens (%d) — token-strip not in ruled scope" % (qid, tok)
            assert n == e["expected_n"], "count moved on %s %r: %d vs ruled %d — re-diagnose" % (qid, e["label"], n, e["expected_n"])
            plan.append((qid, e["label"], n, "strip")); del_total += n
    for qid, s in sorted(SPECIALS.items()):
        n = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (qid, s["old"])).fetchone()[0]
        assert n == s["expected_n"], (qid, n, s["expected_n"])
        plan.append((qid, s["old"], n, "replace->" + s["new"])); del_total += n
    assert del_total == scope["_totals"]["deletions"] == 629, del_total
    del_orgs = {o for qid, lab, n, _ in plan if n for (o,) in
                c.execute("SELECT org_id FROM answers WHERE question_id=? AND value=?", (qid, lab))}
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(del_orgs)), sorted(del_orgs))} if del_orgs else {"seed"}
    assert src == {"seed"}, "non-seed org in deletion set: %s" % src
    # The keep ruling protects the OPTION, not the metric — a keep metric may also carry a
    # ruled strip option (PROP_e1d1e604). Snapshot the kept option dict + its answer count.
    keep_snap = {}
    for q, lab in KEEP_OPTS.items():
        od = [o for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0])
              if o["label"] == lab]
        assert len(od) == 1, (q, lab)
        keep_snap[q] = ({k: od[0][k] for k in ("label", "code", "is_na")},
                        c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (q, lab)).fetchone()[0])
    routed_snap = {q: (c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0],
                       c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (q,)).fetchone()[0])
                   for q in ROUTED}

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    assert n_before == 232490, n_before
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  %d strip options (%d with answers) + 3 specials | deletions %d | answers %d -> %d"
          % (62, sum(1 for p in plan if p[3] == "strip" and p[2]), del_total, n_before, n_before - del_total))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c, touched)
    cur = c.cursor()
    manifest = []

    def snap_delete(qid, label):
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND value=?""", (STAMP + " r3sw13 pre-strip", qid, label))
        cur.execute("DELETE FROM answers WHERE question_id=? AND value=?", (qid, label))

    def edit_bank(qid, remove=None, replace=None):
        row = c.execute("SELECT options_json, scoring_config_json, question_version FROM questions WHERE id=?",
                        (qid,)).fetchone()
        opts = json.loads(row[0]); sc = json.loads(row[1] or "{}")
        code_of = lambda l: re.sub(r"[^A-Z0-9]+", "_", l.upper()).strip("_")
        gone_codes = []
        if remove is not None:
            gone_codes = [o["code"] for o in opts if o["label"] == remove]
            opts = [o for o in opts if o["label"] != remove]
        if replace is not None:
            for o in opts:
                if o["label"] == replace["old"]:
                    gone_codes.append(o["code"])
                    o["label"] = replace["new"]; o["code"] = code_of(replace["new"]); o["is_na"] = replace["new_is_na"]
        for i, o in enumerate(opts):
            o["order"] = i + 1
        assert len({o["code"] for o in opts}) == len(opts), (qid, "code collision")
        for g in gone_codes:
            (sc.get("option_scores") or {}).pop(g, None)
            if g in (sc.get("na_codes") or []):
                sc["na_codes"] = [x for x in sc["na_codes"] if x != g]
        cur.execute("UPDATE questions SET options_json=?, scoring_config_json=?, question_version=? WHERE id=?",
                    (json.dumps(opts), json.dumps(sc), bump(row[2]), qid))

    for qid, ents in sorted(STRIP.items()):
        for e in ents:
            if e["expected_n"]:
                snap_delete(qid, e["label"])
            edit_bank(qid, remove=e["label"])
            manifest.append([qid, "strip", e["label"], e["expected_n"]])
    for qid, s in sorted(SPECIALS.items()):
        snap_delete(qid, s["old"])
        edit_bank(qid, replace=s)
        manifest.append([qid, "replace->" + s["new"], s["old"], s["expected_n"]])

    # ---- post-asserts BEFORE commit ----
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before - del_total == 231861
    assert book_hash(c, touched) == pre_hash, "NON-TARGET BOOK CHANGED"
    for qid, lab, n, act in plan:
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (qid, lab)).fetchone()[0] == 0
    for qid, text, oj in c.execute("SELECT id, text, options_json FROM questions WHERE status='active' AND superpower='Reward'"):
        if not oj or qid in ROUTED:
            continue
        allowed = {KEEP_OPTS[qid]} if qid in KEEP_OPTS else set()
        dk = [o["label"] for o in json.loads(oj) if DK_PAT.search(o.get("label", "")) and o["label"] not in allowed]
        assert not dk, "DK-type label survives outside ruled exceptions: %s %s" % (qid, dk)
    for q, (od, cnt) in keep_snap.items():
        now = [o for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0])
               if o["label"] == od["label"]]
        assert len(now) == 1 and {k: now[0][k] for k in ("label", "code", "is_na")} == od, (q, "kept option changed")
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?",
                         (q, od["label"])).fetchone()[0] == cnt, (q, "kept option answers changed")
    for q, (oj, cnt) in routed_snap.items():
        assert c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0] == oj, q
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (q,)).fetchone()[0] == cnt, q

    # ---- config: RED_NOTICE_01 declaration relabel, validated pre-commit ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    decl = cfg["metrics"]["RED_NOTICE_01"]
    assert decl["na_options"] == ["Not applicable / Don't know"], decl["na_options"]
    decl["na_options"] = ["Not applicable"]
    decl["_r3sw13"] = "merged option relabelled to plain 'Not applicable' (DK half retired platform-wide); declaration relabelled atomically"
    new_labels = {o["label"] for o in json.loads(c.execute(
        "SELECT options_json FROM questions WHERE id='RED_NOTICE_01'").fetchone()[0])}
    assert set(decl["na_options"]) <= new_labels, "declaration would not survive the relabel"
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)

    c.commit()

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw13_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric_id", "action", "option_label", "deleted_n"]); w.writerows(manifest)
    print(json.dumps({"applied": True, "strip_options": 62, "specials": 3, "deleted": del_total,
                      "answers_after": n_before - del_total, "bank_dk_free_outside_exceptions": True,
                      "declaration_relabelled": "RED_NOTICE_01 -> ['Not applicable'] (valid, asserted)",
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
