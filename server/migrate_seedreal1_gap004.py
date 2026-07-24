"""
seedreal-1 — GAP_004 (long-service award) sector-tilt reseed. First & only application of the
governed SECTOR_TILT table (regen_priors.py). DATA reseed of EXT_REW_GAP_004 answers ONLY.

WHY a targeted reseed and not a full generator run: regenerate.py is a from-scratch CSV seed
builder that is NO LONGER RUNNABLE against the live DB (SELECT_PRIORS still reference DK options
r3sw13 stripped, and MULTI_PRIORS reference questions nonrew-2 deleted). So the SECTOR_TILT table
+ generator hook are wired for a future full regen, but TODAY the tilt is consumed HERE, on the
answers table directly (the r3sw pattern), touching GAP_004 and nothing else.

MECHANISM (from regen_priors.SECTOR_TILT['EXT_REW_GAP_004'], David-ruled 2026-07-24):
  per-org Yes-probability = sector target (JUDGEMENT) centred by an offset so the org-weighted
  mean == the anchored overall 0.56 (grade-2, the ONLY sourced number). Deterministic per-org rng
  -> Bernoulli Yes/No. Redistributes shape; holds the total. Replaces the sector-blind
  0.40+0.35*prof.R that produced the 76%/100%-white-collar bimodal shape.

GUARDS: overall within tol of 0.56; ONLY GAP_004 answers move (non-GAP_004 book byte-identical);
frozen-8 byte-identical; the 5 coherence-pair metrics (REW_BEN_044, SICK_001, SICK_005, INC_070,
INC_103) byte-identical; answering-org SET unchanged (redraw values, not membership). Dual-guard;
dry-run default; --write (+ --confirmed-by-david for live).
"""
import argparse, hashlib, json, os, random, sqlite3, sys, tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
from regen_priors import SECTOR_TILT
from regenerate import sector_tilt_prob, sector_tilt_offset, clamp   # the governed helpers

QID = "EXT_REW_GAP_004"
STAMP = "2026-07-24"
OVERALL_TOL = 0.04                                   # anchored overall 0.56 ± 4pp (grade-2, n≈198)
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]
COH5 = ["REW_BEN_044", "REW_BEN_SICK_001", "REW_BEN_SICK_005", "REW_INC_070", "REW_INC_103"]


def book_hash(c, exclude):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (exclude,)):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--gm-out", dest="gm_out", default=None, help="throwaway: staged generated_marginals path")
    a = ap.parse_args()
    live_gm = os.path.join(ROOT, "generated_marginals.json")
    is_live = os.path.abspath(a.db) == os.path.join(ROOT, "lumi.db")
    if a.write:
        if is_live:
            if not a.confirmed:
                print("REFUSED: live reseed needs --confirmed-by-david (r3sw7)"); sys.exit(2)
            a.gm_out = live_gm
        elif a.gm_out is None or os.path.abspath(a.gm_out) == live_gm:
            print("REFUSED: throwaway needs --gm-out (not the live config) (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db)
    cfg = SECTOR_TILT[QID]
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert QID not in ft, "GAP_004 unexpectedly frozen"

    # exact Yes/No option labels from the live question
    oj = c.execute("SELECT options_json FROM questions WHERE id=?", (QID,)).fetchone()[0]
    opts = [o["label"] for o in json.loads(oj)]
    yes_lbl = next(l for l in opts if l.lower().startswith("yes"))
    no_lbl = next(l for l in opts if l.lower().startswith("no"))

    # answering orgs (redraw VALUES for exactly these; membership unchanged) + their industry
    rows = c.execute("SELECT a.org_id, a.value, COALESCE(o.industry,'') FROM answers a JOIN orgs o "
                     "ON o.org_id=a.org_id WHERE a.question_id=? AND COALESCE(a.value,'')!=''", (QID,)).fetchall()
    n = len(rows)
    sector_counts = Counter(ind for _, _, ind in rows)
    offset = sector_tilt_offset(QID, sector_counts)

    before_yes = sum(1 for _, v, _ in rows if v == yes_lbl)
    # DETERMINISTIC PER-SECTOR QUOTA (ruled 2026-07-24): each sector gets round(centred_target * n)
    # Yes; within a sector, orgs ranked by a stable hash take the top-k. Trades within-sector variance
    # for FAITHFUL SHAPE — at n≈8-10 Bernoulli noise swamped the judgement (Tech landed 60% vs a 30%
    # target, inverting the intent). Holds the anchored 56% overall; expresses the ruled shape.
    by_sector = defaultdict(list)
    for org, _, ind in rows:
        by_sector[ind].append(org)
    new_vals = {}
    for ind, orgs in by_sector.items():
        p = sector_tilt_prob(QID, ind, offset)
        k = int(round(p * len(orgs)))
        ranked = sorted(orgs, key=lambda o: hashlib.sha256(("seedreal1::%s::%s" % (QID, o)).encode()).hexdigest())
        yes = set(ranked[:k])
        for o in orgs:
            new_vals[o] = yes_lbl if o in yes else no_lbl
    after_yes = sum(1 for v in new_vals.values() if v == yes_lbl)
    changed = sum(1 for org, v, _ in rows if new_vals[org] != v)

    # per-sector realised
    persec = {}
    for org, _, ind in rows:
        d = persec.setdefault(ind, [0, 0]); d[1] += 1
        if new_vals[org] == yes_lbl: d[0] += 1

    print("seedreal-1 GAP_004 sector-tilt — %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  answering orgs n=%d | centring offset=%+.3f (holds overall %.2f)" % (n, offset, cfg["overall_anchor"]))
    print("  overall Yes: %.1f%% -> %.1f%% (anchor %.0f%%, tol ±%.0fpp) | orgs changed: %d"
          % (100*before_yes/n, 100*after_yes/n, 100*cfg["overall_anchor"], 100*OVERALL_TOL, changed))
    print("  per-sector realised (target):")
    for s in sorted(persec):
        y, tn = persec[s]
        tgt = cfg["targets"].get(s, cfg.get("default"))
        print("    %-42s %2d/%-2d %5.0f%%  (target %.0f%%)" % (s[:42], y, tn, 100*y/tn, 100*tgt))

    # --- guards ---
    realised = after_yes / n
    assert abs(realised - cfg["overall_anchor"]) <= OVERALL_TOL, \
        "overall %.3f outside anchor %.2f ± %.2f" % (realised, cfg["overall_anchor"], OVERALL_TOL)

    if not a.write:
        print("dry-run complete — pass --write (+ --confirmed-by-david for live)")
        c.close(); return

    pre_book = book_hash(c, QID)
    frozen_pre = {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8}
    coh_pre = {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in COH5}
    n_ans = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    cur = c.cursor()
    for org, old_v, _ in rows:
        if new_vals[org] == old_v:
            continue
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers "
                    "WHERE question_id=? AND org_id=?", (STAMP + " seedreal1 pre-reseed", QID, org))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (new_vals[org], QID, org))

    # --- post asserts ---
    assert book_hash(c, QID) == pre_book, "NON-GAP_004 BOOK CHANGED — blast radius escaped"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_ans, "answers row count changed"
    assert {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8} == frozen_pre, "a frozen target moved"
    assert {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in COH5} == coh_pre, "a coherence-pair metric moved"
    now_yes = sum(1 for org, _, _ in rows if c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (QID, org)).fetchone()[0] == yes_lbl)
    assert now_yes == after_yes, "post-write Yes count mismatch"
    c.commit()

    # --- update the freeze-gate register marginal to the ruled anchor (dual-config: staged for
    #     throwaway via --gm-out, live repo on --write --confirmed). Was grade-B legacy 76%. ---
    gm = json.load(open(live_gm, encoding="utf-8"))
    gm["marginals"][QID].update({
        "target_share": cfg["overall_anchor"], "all": round(cfg["overall_anchor"] * 100), "grade": "2",
        "source": "grade-2 register 'Yes 56%' (seedreal-1 ruling, David 2026-07-24); supersedes grade-B legacy 76%",
        "evidence": "56% operate a long-service award scheme (grade-2 anchor); sector shape is JUDGEMENT"})
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.gm_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(gm, indent=1, ensure_ascii=False))
    os.replace(tmp, a.gm_out)
    print("  register marginal EXT_REW_GAP_004: target_share 0.76 -> %.2f (grade B legacy -> grade 2 anchor) -> %s"
          % (cfg["overall_anchor"], os.path.basename(a.gm_out)))

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "seedreal1_manifest.json"), "w") as f:
        json.dump({"metric": QID, "n": n, "overall_before": before_yes/n, "overall_after": realised,
                   "changed": changed, "offset": offset, "targets": cfg["targets"],
                   "shape_status": cfg["shape_status"], "anchor_status": cfg["anchor_status"]}, f, indent=1)
    print(json.dumps({"applied": True, "live": is_live, "metric": QID, "changed": changed,
                      "overall_after": round(realised, 3), "non_gap004_book": "byte-identical",
                      "frozen8": "byte-identical", "coherence5": "byte-identical",
                      "row_count": "%d (unchanged)" % n_ans}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
