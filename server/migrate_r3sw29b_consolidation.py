"""
r3sw29b — allowance consolidation (REW_PAY_019): clear 5 no-inventory CICOVER + remap 67 governance-N/A
to "Never", self-condition on allowances-exist.

Ruling B (David): TWO distinguishable operations landing together.
  (i)  CLEAR the 5 no-inventory CICOVER (answered a consolidation frequency but pay NO allowances — no
       REW_PAY_016 row) -> "Not applicable". A non-allowance org has nothing to consolidate.
  (ii) REMAP the 67 allowance-paying "Not applicable" -> "Never" (governance N/A reads "Never" where the
       org demonstrably pays allowances; N/A is a mislabel — they simply never consolidate). Fixes the
       implausible Never=3.
Then self-condition (answerer_only) on the child's own NA -> base 215 (= the allowances-payers). Descriptive-
with-floor: the "Never" option IS the governance floor, which is why the remap is legitimate (not fabrication).

EXACT after-distribution (surfaced, deviates slightly from the ruling's stated 82/68/70): the 5 CICOVER
cleared were 2×Always + 3×Sometimes, so Always 82->80, Sometimes 68->65, Never 3->70, N/A 67->5. Base 215.

BUILD SHAPE (b) SELF-CONDITION via own NA (SALSAC precedent): NO external subset pair (any-allowance is a
multi-select parent, awkward to express single-token; and REW_PAY_016 is a queued reseed item). NO
structured_bases/generated_marginals change. Data = UPDATE-only, config = applicable_bases only. 8 frozen
targets asserted byte-identical. Dual-config (r3sw7); dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = "REW_PAY_019"
NA, NEVER = "Not applicable", "Never"
P16 = "REW_PAY_016"
TOUCHED = [CHILD]
STAMP = "2026-07-23"
BASE = 215
BASE_LABEL = "organisations that pay allowances"
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
    any_allow = {o for o, v in p16.items() if v and "None" not in toks(v)}
    p19 = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (CHILD,))}
    cico = sorted(o for o, v in p19.items() if v and v != NA and o not in any_allow)   # non-allowance substantive -> NA
    defr = sorted(o for o, v in p19.items() if v == NA and o in any_allow)             # allowance N/A -> Never
    assert len(cico) == 5, "CICOVER != 5 (%d)" % len(cico)
    assert len(defr) == 67, "DEFERRAL != 67 (%d)" % len(defr)
    edit_orgs = sorted(set(cico) | set(defr))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(edit_orgs)), edit_orgs)}
    assert src <= {"seed"}, "non-seed org in edit set: %s" % src
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)
    from collections import Counter
    before = dict(Counter(p19.values()))

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  (i)  CLEAR %d no-inventory CICOVER -> %r (values: %s)" % (len(cico), NA, [p19[o] for o in cico]))
    print("  (ii) REMAP %d allowance-paying N/A -> %r" % (len(defr), NEVER))
    after = Counter(p19.values())
    for o in cico: after[p19[o]] -= 1; after[NA] += 1
    for o in defr: after[NA] -= 1; after[NEVER] += 1
    print("  BEFORE:", before)
    print("  AFTER :", dict(after), "-> base(drop NA) =", sum(v for k, v in after.items() if k != NA))
    print("  build shape (b): self-condition via own NA, NO pair, NO engine change")
    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david + --config-out for throwaway)")
        c.close(); return

    pre_hash = book_hash(c); cur = c.cursor()
    for o in edit_orgs:
        cur.execute("""INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw29b pre-edit", CHILD, o))
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NA, CHILD, o) for o in cico])
    cur.executemany("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", [(NEVER, CHILD, o) for o in defr])

    # ---- asserts ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before, "ROW COUNT CHANGED"
    assert frozen_snap(c) == frozen_pre, "A FROZEN TARGET METRIC MOVED — HARD ABORT"
    now = {o: (v or "") for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (CHILD,))}
    now_sub = {o for o, v in now.items() if v and v != NA}
    now_na = {o for o, v in now.items() if v == NA}
    assert now_sub == any_allow and len(now_sub) == BASE, "post substantive != allowances-payers (%d)" % len(now_sub)
    assert not (now_na & any_allow), "an allowance-org still N/A after remap"

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab.setdefault("metrics", {})[CHILD] = {"mode": "answerer_only", "base_label": BASE_LABEL, "na_options": [NA],
        "_r3sw29b": "consolidation conditioned on allowances-exist (215); 5 no-inventory CICOVER cleared; 67 governance-N/A remapped to Never (org pays allowances, never consolidates); self-conditioning via own NA (no pair)"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.cout)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ab_text)
    os.replace(tmp, a.cout)
    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw29b_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([CHILD, "clear 5 no-inventory CICOVER -> NA", "distinguishable op (i)"])
        w.writerow([CHILD, "remap 67 allowance N/A -> Never", "distinguishable op (ii)"])
        w.writerow([CHILD, "answerer_only self-condition", "base %d" % BASE])
    print(json.dumps({"applied": True, "cleared": len(cico), "remapped": len(defr), "base": BASE,
                      "after": dict(after), "frozen8": "byte-identical",
                      "row_count": "%d (unchanged)" % n_before, "pair": "NONE", "live": is_live}, indent=2))


if __name__ == "__main__":
    main()
