"""
r3sw8 — PMI coverage-composition redesign (structural replace + N/A-exclusion pilot).

RETIRE  REW263_BEN_PMIMH   single-select MH/DGP — its N/A bar (56.8%) distorted the graph and
                           55.7% of premium-matrix answerers simultaneously called it N/A.
CREATE  REW265_BEN_PMICOMP multi-select, 6 benchmarked options + derived-exclusive terminal;
                           4 universals stated in help_text as assumed-standard, NOT options.
SEED    the 130 REW_BEN_038 'Private Medical Insurance (PMI)' tickers ONLY (the r3sw6
        premium-matrix conditioning set) — exact-count per-option incidence, diff8 pattern
        (NOT Bernoulli — the small-base TOL lesson). Non-PMI orgs get NO row: the applicable
        base IS the graph and the denominator (N/A-not-on-graph pilot).
CONFIG  staged atomically with the data write (r3sw6 standing process): old mp entry REMOVED,
        new Practice entry (unbenchmarked: EST incidence) added. Path-isolated per the r3sw7
        LUMI_MP_CONFIG doctrine: a throwaway --write MUST name a staged --config-out (the
        script refuses the served path); only the approved live write (default --db) may
        touch data/market_position_config.json.

Ordering (adversarial-review hardened): DB changes -> ALL DB post-asserts pre-commit (any
failure = full rollback, never a half-migration) -> config serialized+validated -> commit ->
atomic config write (temp + os.replace) -> re-read verify -> manifest. Targets are read from
generated_marginals.json[multiselect_incidence] — never hardcoded.
Dry-run default; apply needs --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, re, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "REW263_BEN_PMIMH", "REW265_BEN_PMICOMP"
PARENT, TOKEN = "REW_BEN_038", "Private Medical Insurance (PMI)"
RELEASE, STAMP = "2026.5", "2026-07-19"
TEXT = "Which of the following does your PMI scheme include beyond standard cover?"
HELP = ("Asked only of organisations offering PMI — each share is the percentage of "
        "PMI-holding organisations whose scheme includes that element, so the bars won't "
        "sum to 100. In-patient treatment, digital GP access, cancer cover and a basic "
        "mental-health support line are treated as standard PMI features — assumed "
        "included, not benchmarked here.")
CFG_NEW = {"class": "Practice", "type": "categorical", "direction": None, "lens": "retain",
           "weight": 1, "unbenchmarked": True,
           "_r3sw8": "EST incidence over PMI-havers — verdict suppressed; structure grade B "
                     "(insurer product lines); per-option re-earn when by-option incidence sourced"}

code_of = lambda l: re.sub(r"[^A-Z0-9]+", "_", l.upper()).strip("_")


def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def rank_key(opt, org):
    return hashlib.sha256(("r3sw8|%s|%s" % (opt, org)).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None,
                    help="REQUIRED (staged path) for a throwaway --write; omitted on the live "
                         "write it resolves to the served config. The served file is refused "
                         "for any non-live --db (r3sw7 LUMI_MP_CONFIG doctrine).")
    a = ap.parse_args()

    served_db = os.path.join(ROOT, "lumi.db")
    served_cfg = os.path.join(ROOT, "data", "market_position_config.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            if is_live:
                a.config_out = served_cfg
            else:
                sys.exit("REFUSED: throwaway --write needs an explicit staged --config-out — "
                         "the served config is immutable until the approved live write (r3sw7 doctrine)")
        elif not is_live and os.path.abspath(a.config_out) == served_cfg:
            sys.exit("REFUSED: a throwaway --write may not target the served config (r3sw7 doctrine)")

    gen = json.load(open(os.path.join(ROOT, "generated_marginals.json"),
                         encoding="utf-8"))["multiselect_incidence"][NEW]
    prev, terminal = gen["prevalences"], gen["terminal"]

    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row

    # ---- diagnose ----
    assert c.execute("SELECT COUNT(*) FROM questions WHERE id=?", (NEW,)).fetchone()[0] == 0, \
        "%s already exists — refusing" % NEW
    old_q = c.execute("SELECT status FROM questions WHERE id=?", (OLD,)).fetchone()
    assert old_q and old_q["status"] == "active", "retire target not active: %r" % (old_q and dict(old_q))
    src = dict(c.execute("""SELECT COALESCE(o.source,'(null)'), COUNT(*) FROM answers x
                            JOIN orgs o ON o.org_id=x.org_id WHERE x.question_id=? GROUP BY 1""", (OLD,)))
    assert set(src) <= {"seed"}, "NON-SEED answers on retiree %s: %s — ABORT" % (OLD, src)
    before_dist = dict(c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (OLD,)))
    del_n = sum(before_dist.values())
    assert del_n == 220, "retiree book moved: %d answers (expected 220) — re-diagnose" % del_n

    tickers = sorted({r["org_id"] for r in c.execute(
        "SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
        if TOKEN in (t.strip() for t in (r["value"] or "").split(";"))})
    assert len(tickers) == 130, "PMI-haver set moved: %d (expected 130) — re-diagnose before writing" % len(tickers)
    tsrc = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'(null)') FROM orgs WHERE org_id IN (%s)"
                                    % ",".join("?" * len(tickers)), tickers)}
    assert tsrc == {"seed"}, "non-seed org in the conditioning set: %s — ABORT" % tsrc

    # exact-count per-option incidence over the conditioned base (diff8 pattern)
    labels = list(prev)                      # canonical option order = declared order
    codes = [code_of(l) for l in labels + [terminal]]
    assert len(set(codes)) == len(codes), "option codes collide: %s" % codes
    plan, pick = {}, {o: [] for o in tickers}
    for opt in labels:
        k = round(prev[opt] / 100.0 * len(tickers))
        plan[opt] = k
        for o in sorted(tickers, key=lambda o: rank_key(opt, o))[:k]:
            pick[o].append(opt)
    values = {o: "; ".join(l for l in labels if l in pick[o]) or terminal for o in tickers}
    none_n = sum(1 for v in values.values() if v == terminal)

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  retire %s: %d answers (all seed, asserted) incl. N/A %d" % (OLD, del_n, before_dist.get("Not applicable", 0)))
    print("  seed %s over %d PMI-havers (REW_BEN_038 tickers): %s | terminal '%s' -> %d org(s)"
          % (NEW, len(tickers), {l[:24]: k for l, k in plan.items()}, terminal[:24], none_n))
    print("  answers %d -> %d expected" % (n_before, n_before - del_n + len(tickers)))
    print("  config-out: %s" % (a.config_out if a.write else "(resolved at --write; served path only when --db is the live book)"))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c, [OLD, NEW])
    cur = c.cursor()

    # ---- 1. retire the old single-select (Diff-14 pattern, + replaced_by wiring) ----
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                (STAMP + " r3sw8 pre-retire snapshot", OLD))
    cur.execute("DELETE FROM answers WHERE question_id=?", (OLD,))
    cur.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (OLD,))
    cur.execute("UPDATE questions SET status='retired', release_retired=?, replaced_by=? WHERE id=?",
                (RELEASE, NEW, OLD))

    # ---- 2. create the multi-select (apply_2026_5 column pattern) ----
    oj = [{"code": code_of(l), "label": l, "order": i + 1, "is_na": False}
          for i, l in enumerate(labels + [terminal])]
    qo = (c.execute("SELECT MAX(question_order) FROM questions").fetchone()[0] or 950) + 1
    cur.execute("""INSERT INTO questions
      (id,text,short_description,help_text,definition,superpower,sub_power,sub_power_order,type,category,
       options_json,default_chart_type,data_display_type,polarity,unit_type,lumi_tier,na_handling_json,
       benchmark_display,is_scored,scoring_config_json,is_required,question_order,question_version,
       historical_comparability,status,release_entered)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (NEW, TEXT, TEXT[:120], HELP, TEXT, "Reward", "Health & Protection", 3, "multi_select", "practice",
       json.dumps(oj), "bar", "percentage_distribution", "neutral", "none", "Core",
       json.dumps({"exclude_from_scoring": True, "exclude_from_benchmarking": False, "na_codes": []}),
       TEXT, 0, json.dumps({"scoring_method": "multi_select_count", "polarity": "neutral"}),
       0, qo, "v1.0", "n/a", "active", RELEASE))
    for ct, qid, detail in (("retired", OLD, "r3sw8: the N/A bar (56.8) distorted the graph; replaced by " + NEW),
                            ("added", NEW, "r3sw8: PMI coverage composition — conditioned on PMI-exists, "
                                           "EST incidence, verdict-suppressed; N/A-exclusion pilot")):
        cur.execute("""INSERT INTO core_changelog (release_id,lane,change_type,question_id,detail,signed_off_by,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (RELEASE, "release", ct, qid, detail,
                     "David Whitfield (r3sw8 PMI composition redesign approval)", STAMP))

    # ---- 3. seed the conditioned base only ----
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,'',?,?)",
                    [(o, NEW, values[o], STAMP + " 09:00:00") for o in tickers])

    # ---- 4. ALL DB post-asserts BEFORE commit (any failure = full rollback) ----
    assert book_hash(c, [OLD, NEW]) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before - del_n + len(tickers)
    st = c.execute("SELECT status, release_retired, replaced_by FROM questions WHERE id=?", (OLD,)).fetchone()
    assert (st["status"], st["release_retired"], st["replaced_by"]) == ("retired", RELEASE, NEW), dict(st)
    assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (OLD,)).fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM benchmark_snapshots WHERE question_id=?", (OLD,)).fetchone()[0] == 0
    rows = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (NEW,))}
    assert set(rows) == set(tickers), "answerer set != conditioning set (%d vs %d)" % (len(rows), len(tickers))
    got, allowed = {}, set(labels) | {terminal}
    for v in rows.values():
        toks = [t.strip() for t in v.split(";") if t.strip()]
        assert toks and set(toks) <= allowed, "alien token in %r" % v
        assert terminal not in toks or toks == [terminal], "terminal co-occurs: %r" % v
        for t in toks:
            got[t] = got.get(t, 0) + 1
    for opt in labels:
        assert got.get(opt, 0) == plan[opt], (opt, got.get(opt, 0), plan[opt])
    assert got.get(terminal, 0) == none_n

    # ---- 5. config: serialize + validate BEFORE commit; write atomically AFTER ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    assert OLD in cfg["metrics"] and NEW not in cfg["metrics"]
    del cfg["metrics"][OLD]
    cfg["metrics"][NEW] = CFG_NEW
    cfg_text = json.dumps(cfg, indent=2, ensure_ascii=False)
    chk = json.loads(cfg_text)["metrics"]
    assert OLD not in chk and chk[NEW]["unbenchmarked"] is True

    c.commit()

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)
    out_cfg = json.load(open(a.config_out, encoding="utf-8"))["metrics"]
    assert OLD not in out_cfg and out_cfg[NEW]["unbenchmarked"] is True

    # ---- 6. manifest (repo root ONLY on the live write; beside the throwaway db otherwise) ----
    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw8_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric_id", "action", "before", "after"])
        w.writerow([OLD, "retired — replaced by %s (r3sw8)" % NEW, json.dumps(before_dist), "{}"])
        w.writerow([NEW, "seeded — exact-count per-option incidence over %d PMI-havers (r3sw8)" % len(tickers),
                    "{}", json.dumps(dict(got))])
    print(json.dumps({"applied": True, "retired": OLD, "created": NEW,
                      "answers_after": n_before - del_n + len(tickers),
                      "per_option": {l[:28]: got.get(l, 0) for l in labels}, "terminal_n": none_n,
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
