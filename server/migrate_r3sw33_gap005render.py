"""
r3sw33 — EXT_REW_GAP_005 render fix: declare answerer_only so "Not applicable" leaves graph + denominator.

STANDING-RULE RENDER FIX ONLY (ruled David). GAP_005 (multi_select long-service milestones) currently renders
"Not applicable" as a graph bar (5 orgs whose ONLY selection is the is_na option) and counts them in the
denominator (n=119, not declared answerer_only). The standing rule: "Not applicable" must never appear as a
graph bar or in the denominator. Declare answerer_only -> the 5 N/A-only orgs leave graph + n. Base 119 -> 114.
The six milestone option counts are UNCHANGED; only the denominator moves.

DECLARATION-ONLY: touches applicable_bases.json, ZERO rows in `answers`. NOT a conditioning — does NOT condition
on GAP_004, does NOT clear the 30 contradictions (18 GAP_007-evidenced parent-errors + 12 child-impossible),
adds NO subset pair. The conditioning + the parent (GAP_004) seed-realism are DEFERRED so this metric isn't
touched twice. VERDICT-NEUTRAL: GAP_005 is polarity=neutral + unbenchmarked=True (Diff-14 suppressed) -> excluded
at positions.py:778; no verdict field. 8 frozen asserted byte-identical (trivially — no DB write). Dual-config
(r3sw7); dry-run default; --write --confirmed-by-david for served.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAP5, NA = "EXT_REW_GAP_005", "Not applicable"
BASE_LABEL = "organisations that recognise length-of-service milestones"
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]


def toks(v): return [t.strip() for t in (v or "").split(";") if t.strip()]


def frozen_hash(c):
    h = hashlib.sha256()
    for q in FROZEN8:
        for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? ORDER BY org_id", (q,)):
            h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


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
    assert not any(q in ft for q in ("EXT_REW_GAP_004", "EXT_REW_GAP_005", "EXT_REW_GAP_007")), "a GAP metric is unexpectedly frozen"
    g5 = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (GAP5,))}
    na_only = sorted(o for o, v in g5.items() if toks(v) and all(t == NA for t in toks(v)))
    mixed = [o for o, v in g5.items() if NA in toks(v) and any(t != NA for t in toks(v))]
    ms = {o for o, v in g5.items() if any(t != NA for t in toks(v))}
    # --- HARD ASSERTS ---
    assert len(na_only) == 5, "N/A-only set %d != 5 — HARD ABORT (cohort moved)" % len(na_only)
    assert not mixed, "%d orgs select N/A + a milestone — fix would change; STOP" % len(mixed)
    assert len(ms) == 114, "milestone-listers %d != 114" % len(ms)
    n_ans = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    fhash = frozen_hash(c)

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  DECLARE %s answerer_only, na_options=['%s'] -> base 119 -> 114 (5 N/A-only leave graph+denominator)" % (GAP5, NA))
    print("  DECLARATION-ONLY: 0 answer rows change; NO conditioning, NO pair; 30 contra untouched; 102 no-row unaffected")
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + --config-out for throwaway)")
        c.close(); return

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab.setdefault("metrics", {})[GAP5] = {"mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
        "_r3sw33": "render fix only: N/A off graph + out of denominator; NOT a conditioning — 30 GAP_004 contradictions (18 parent-error, 12 child-impossible) + union base deferred to GAP_004 seed-realism"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    # NO DB write. Assert the DB is untouched (config-only).
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_ans, "answers row count changed (must be 0 edits)"
    assert frozen_hash(c) == fhash, "frozen targets changed (impossible — no DB write)"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.cout)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ab_text)
    os.replace(tmp, a.cout)
    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw33_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([GAP5, "declare answerer_only (render fix)", "base 119->114; 0 answer edits; conditioning deferred"])
    print(json.dumps({"applied": True, "declared": GAP5, "na_dropped": len(na_only), "base": 114,
                      "answer_edits": 0, "answers_rowcount": "%d (unchanged)" % n_ans, "pair": "NONE",
                      "frozen8": "byte-identical (no DB write)", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
