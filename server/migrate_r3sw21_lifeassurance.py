"""
r3sw21 — life-assurance multiple redesign (REW_BEN_045): nudge offer rate cohort-matched ~62%,
fix the 1x=0 defect, condition the multiples on offerers (answerer_only), EST-suppress.

REW_BEN_045 "life assurance for the main population (multiple of salary)" showed "Not offered"
44% distorting the multiples, and 1x=0 (a defect — 1x is a small-but-real minority). PREMISE
CORRECTION (r3sw21 research): the "~85% offer" intuition is LIVES-covered (~85% of employees),
NOT employers-offering (~62%, CIPD Reward Feb 2026 large, grade B) — so the offer-rate fix is a
MINOR nudge, not a rescue.
  FIX 1  offer rate 56% -> cohort-matched ~62%: the 9 highest-latent "Not offered" orgs (all
         large) -> offering; offerer set 123 -> 132 (60%), "Not offered" 97 -> 88 (40%).
  FIX 2  multiples re-seeded EST 10/30/30/30 among the 132 offerers (fixes 1x=0; flat core, no
         false modal since the split is paywalled/unsourced — centre 3-4x as the research found).
  FIX 3  condition on offerers: applicable_bases answerer_only excludes "Not offered" — the
         multiples render over offerers only, "Not offered" becomes offer-rate context. NO
         external subset pair: REW_BEN_045 is single-select, so "no non-offerer has a multiple"
         is STRUCTURALLY guaranteed (an org is "Not offered" XOR a multiple) — unlike PMI where
         offer-exists was a separate parent. Verdict EST-SUPPRESSED (unbenchmarked=True; was
         higher_is_better). The flat offer marginal is RETIRED (generator_rules) — superseded.
NOTE: the 4-org REW_BEN_038-life-tick(119)-vs-REW_BEN_045-offer discrepancy is left unfixed
(tiny, documented). Dual-config atomic (r3sw7). Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, json, hashlib, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # noqa: E402

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    try:
        PROF.update(json.load(open(os.path.join(ROOT, _p), encoding="utf-8")))
    except FileNotFoundError:
        pass

QID = "REW_BEN_045"
MULT = ["1×", "2×", "3×", "4× or more"]
WEIGHT = [0.10, 0.30, 0.30, 0.30]
NOT_OFFERED = "Not offered"
TARGET_OFFERERS = 132   # cohort-matched ~62% (123 current + 9 highest-latent Not-offered, all large)
STAMP = "2026-07-21"


def hrank(tag, o):
    return hashlib.sha256(("r3sw21|%s|%s" % (tag, o)).encode()).hexdigest()


def book_hash(c):
    import hashlib as _h
    h = _h.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
                       "WHERE question_id != ? ORDER BY 1,2,3,4", (QID,)):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def largest_remainder(n, weights):
    raw = [n * w for w in weights]
    base = [int(x) for x in raw]
    rem = n - sum(base)
    order = sorted(range(len(weights)), key=lambda i: -(raw[i] - base[i]))
    for i in order[:rem]:
        base[i] += 1
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    ap.add_argument("--mp-config-out", dest="mp_out", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    served_mp = os.path.join(ROOT, "data", "market_position_config.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            a.config_out = served_ab if is_live else sys.exit("REFUSED: throwaway needs --config-out (r3sw7)")
        if a.mp_out is None:
            a.mp_out = served_mp if is_live else sys.exit("REFUSED: throwaway needs --mp-config-out (r3sw7)")
        if not is_live and (os.path.abspath(a.config_out) == served_ab or os.path.abspath(a.mp_out) == served_mp):
            sys.exit("REFUSED: throwaway may not target a served config (r3sw7)")

    c = sqlite3.connect(a.db)
    A = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (QID,))}
    assert len(A) == 220, "REW_BEN_045 answerer count moved: %d" % len(A)
    cur_off = {o for o, v in A.items() if v != NOT_OFFERED}
    cur_no = {o for o, v in A.items() if v == NOT_OFFERED}
    assert len(cur_off) == 123 and len(cur_no) == 97, (len(cur_off), len(cur_no))
    # genuine-entry guard (like the PMI premium): preserve any non-seed org's answer
    genuine = {o for o in A if c.execute("SELECT source FROM orgs WHERE org_id=?", (o,)).fetchone()[0] != "seed"}
    assert not genuine, "unexpected non-seed REW_BEN_045 answer(s): %s" % genuine

    # FIX 1 — nudge: add the 9 highest-latent "Not offered" -> offering
    add = sorted(cur_no, key=lambda o: (-latent(o, PROF), hrank("add", o)))[:TARGET_OFFERERS - len(cur_off)]
    offerers = sorted(cur_off | set(add))
    not_off = sorted(cur_no - set(add))
    assert len(offerers) == 132 and len(not_off) == 88

    # FIX 2 — re-seed all 132 offerers to 10/30/30/30 (hash-ranked, exact counts)
    counts = largest_remainder(132, WEIGHT)
    assert sum(counts) == 132
    ranked = sorted(offerers, key=lambda o: hrank("mult", o))
    seed = {}
    i = 0
    for lab, k in zip(MULT, counts):
        for o in ranked[i:i + k]:
            seed[o] = lab
        i += k
    assert len(seed) == 132

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  offer nudge: offerers 123 -> 132 (56%% -> 60%%); 'Not offered' 97 -> 88 (44%% -> 40%%); +%d (highest-latent, large)" % len(add))
    print("  multiples re-seeded 10/30/30/30: %s (fixes 1x=0)" % dict(zip(MULT, counts)))
    print("  condition: answerer_only excludes 'Not offered' | verdict EST-suppressed | answers unchanged %d" % n_before)
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                (STAMP + " r3sw21 pre-redesign", QID))
    for o in offerers:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (seed[o], QID, o))
    for o in not_off:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (NOT_OFFERED, QID, o))

    # ---- coherence asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    now = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (QID,))}
    assert len(now) == 220
    off_now = {o for o, v in now.items() if v != NOT_OFFERED}
    assert off_now == set(offerers) and len(off_now) == 132, "offerer set wrong"
    assert not any(v not in MULT + [NOT_OFFERED] for v in now.values()), "alien value"
    got = {lab: sum(1 for v in now.values() if v == lab) for lab in MULT}
    assert got == dict(zip(MULT, counts)), (got, counts)
    # structural coherence: single-select => no org is both "Not offered" and a multiple (inherent)

    # ---- dual config: answerer_only (condition) + mp (suppress) ----
    ab = json.load(open(served_ab, encoding="utf-8"))
    ab["metrics"][QID] = {"mode": "answerer_only", "base_label": "organisations offering life assurance",
                          "na_options": [NOT_OFFERED],
                          "_r3sw21": "multiples render over offerers (~62%% cohort-matched); 'Not offered' = offer-rate context; EST grade-C"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    mp = json.load(open(served_mp, encoding="utf-8"))
    mp["metrics"][QID]["unbenchmarked"] = True
    mp["metrics"][QID]["_r3sw21"] = "verdict SUPPRESSED — EST grade-C multiple weighting (no free 1x/2x/3x/4x split)"
    mp_text = json.dumps(mp, indent=2, ensure_ascii=False)

    c.commit()
    for path, text in ((a.config_out, ab_text), (a.mp_out, mp_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw21_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([QID, "offer 123->132 + multiples 10/30/30/30 + answerer_only + EST-suppress", json.dumps(dict(zip(MULT, counts)))])
    print(json.dumps({"applied": True, "offerers": "123 -> 132 (60%)", "not_offered": "97 -> 88 (40%)",
                      "added_offerers": len(add), "multiples": dict(zip(MULT, counts)),
                      "conditioning": "answerer_only excludes 'Not offered' (no external pair — single-select structural)",
                      "verdict": "suppressed", "answers": n_before, "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
