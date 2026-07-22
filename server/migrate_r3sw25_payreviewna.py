"""
r3sw25 — Master N/A sweep v2: the sole batch-safe (A) declaration.

Of the 27 remaining "Not applicable"-bar metrics, verification (workflow wqwrd2k01,
4 parallel DB verifiers) found exactly ONE clean batch-safe case — the r3sw10 (b)-class
having already exhausted the no-parent re-percentage set. Every other metric has a
verified parent (19 -> B), a disagreeing second signal (4 -> C), or is a genuine
substantive N/A (3 -> D); all flagged for individual ruling, none auto-conditioned.

  PROP_8e0b6316 "How often is the main pay review cycle conducted?" (Pay, single-select).
  N/A option "Not applicable (no pay review)" is the ABSENCE of the measured frequency,
  not a point on the frequency scale — it distorts the chart. No parent-exists metric
  (the cadence question is top-level; the pay-review-process siblings all presume a
  review exists, none gates existence). No REW_BEN_038 tick / second signal (all three
  038 word-matches spurious). Verdict already suppressed (mp unbenchmarked=True).

  FIX  declare answerer_only: the 9 "Not applicable (no pay review)" answers leave the
       block at aggregation (graph AND n), re-percentaging over the 203 answerers.
       RENDER-ONLY — zero `answers` rows touched (asserted); the DB is opened READ-ONLY
       for pre-state verification and never mutated. Config write is atomic (tempfile +
       os.replace). Dual-config guard (r3sw7): a staged (throwaway) run must target a
       config path OTHER than the served one; a live write to the served config requires
       --confirmed-by-david.

Dry-run default; --write to apply; --confirmed-by-david required for the served config.
"""
import argparse, csv, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = "PROP_8e0b6316"
NA_LABEL = "Not applicable (no pay review)"
BASE_LABEL = "organisations that run a pay review"
# pre-state the ruling was based on (216 -> answers; base 212 answering, 9 N/A -> 203)
EXPECT = {"Annually": 172, "Twice a year": 14, "No regular cycle (ad hoc)": 11,
          NA_LABEL: 9, "Quarterly": 6}
DECL = {
    "mode": "answerer_only",
    "base_label": BASE_LABEL,
    "na_options": [NA_LABEL],
    "_r3sw25": ("master N/A sweep v2 — sole batch-safe (A) of 27 (the clean no-parent class "
                "was exhausted by r3sw10); no parent-exists metric, no 038/second signal; "
                "N/A = absence of the measured frequency. Render-only re-percentage "
                "(answers byte-identical); verdict already suppressed (mp unbenchmarked)."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"), help="DB for pre-state assert (read-only)")
    ap.add_argument("--config-in", dest="cin", default=None, help="base config to merge into (default: served)")
    ap.add_argument("--config-out", dest="cout", default=None, help="where to write (default: served = live)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()

    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    cin = a.cin or served_ab
    cout = a.cout or served_ab
    is_live = os.path.abspath(cout) == served_ab

    # ---- pre-state assertion (plain read connection; NEVER written — URI ro-mode
    #      breaks on the space in the served path, so the house uses plain connects) ----
    c = sqlite3.connect(a.db)
    try:
        dist = dict(c.execute(
            "SELECT value, COUNT(DISTINCT org_id) FROM answers WHERE question_id=? GROUP BY value", (Q,)))
        n_ans_rows_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
        prop_rows_before = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (Q,)).fetchone()[0]
        opts = json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (Q,)).fetchone()[0])
    finally:
        c.close()
    assert dist == EXPECT, "PROP_8e0b6316 distribution drifted from the ruled pre-state:\n  got %s\n  exp %s" % (dist, EXPECT)
    base_before = sum(dist.values())                        # 212 answering orgs
    base_after = base_before - dist[NA_LABEL]               # 203
    assert base_before == 212 and base_after == 203, (base_before, base_after)
    # option label must exist EXACTLY on the question, and be flagged is_na
    na_opt = [o for o in opts if o["label"] == NA_LABEL]
    assert na_opt and na_opt[0].get("is_na") is True, "na_option label/flag mismatch on the question schema"

    base = json.load(open(cin, encoding="utf-8"))
    already = Q in (base.get("metrics") or {})

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  metric        : %s  (%s)" % (Q, "single_select, Pay"))
    print("  declaration   : answerer_only, drop %r -> base %d -> %d, excluded_na=%d"
          % (NA_LABEL, base_before, base_after, dist[NA_LABEL]))
    print("  before (n=%d) : %s" % (base_before,
          {k: "%.1f%%" % (100.0 * v / base_before) for k, v in EXPECT.items()}))
    real = {k: v for k, v in EXPECT.items() if k != NA_LABEL}
    print("  after  (n=%d) : %s  (N/A bar removed)" % (base_after,
          {k: "%.1f%%" % (100.0 * v / base_after) for k, v in real.items()}))
    print("  answers rows  : %d (UNCHANGED — render-only); PROP rows %d" % (n_ans_rows_before, prop_rows_before))
    print("  config in/out : %s -> %s  (%s)" % (os.path.relpath(cin, ROOT), os.path.relpath(cout, ROOT),
                                                "LIVE/served" if is_live else "staged/throwaway"))
    print("  already there : %s" % already)

    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david for the served config)")
        return
    if is_live and not a.confirmed:
        print("REFUSED: live write to the served config needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    if already:
        print("REFUSED: %s already declared in %s — refusing to overwrite" % (Q, os.path.relpath(cin, ROOT))); sys.exit(2)

    base.setdefault("metrics", {})[Q] = DECL
    text = json.dumps(base, indent=1, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(cout)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, cout)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(cout))
    with open(os.path.join(man_dir, "r3sw25_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([Q, "declare answerer_only (A batch-safe); render-only, 0 DB rows",
                    json.dumps({"drop": NA_LABEL, "base": "%d->%d" % (base_before, base_after),
                                "excluded_na": dist[NA_LABEL]})])
    print(json.dumps({"applied": True, "metric": Q, "mode": "answerer_only",
                      "base": "%d -> %d" % (base_before, base_after), "excluded_na": dist[NA_LABEL],
                      "answers_rows": "%d (unchanged)" % n_ans_rows_before,
                      "config": os.path.relpath(cout, ROOT), "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
