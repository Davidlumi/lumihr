"""
r3sw14 — PMI eligibility-by-level: PMI-havers conditioning + ruled re-steepen (both ruled).

COHERENCE GATE FINDINGS (diagnosed, pinned here): the old seed's any-Yes set (130) matched the
haver COUNT but not the haver SET — 48 CICOVER-class (any-Yes non-havers) + 48 DEFERRAL-class
(havers all-No). The ruled re-seed over the REW_BEN_038 PMI-haver set IS the align-to-PMI-exists
repair: both contradiction classes vanish by construction.

RE-SEED (ruled cliff, EST, verdict stays suppressed): Board 95 / Director 90 / Head-of 80 /
SrMgr 70 / Manager 20 / Supervisor 2 / Frontline 0 (% of the 130 havers) -> per-level Yes counts
124/117/104/91/26/3/0. Implemented as TOP-DOWN PREFIX DEPTHS (an org eligible at a level is
eligible at every level above), latent-ranked descending (deeper = higher latent) — G10's
monotonicity and depth-latent gates hold by construction. Non-havers get NO rows (conditioned
mode, r3sw8 pilot pattern): the applicable base IS the graph and the denominator.
NOTE (arithmetic consequence of the ruled 95% Board line): 6 havers carry all-No — "offers PMI,
no standard level-eligibility" — disclosed in the presentation.

Answers 231,861 -> 231,231 (-1,540 +910). Config: conditioned declaration staged via
--config-out (r3sw7 doctrine). Subset pair (child_any_answer ⊆ REW_BEN_038 PMI tick) lives in
structured_bases/generated_marginals. Dry-run default; apply needs --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # noqa: E402  (Diff-15 precedent: matrices nest by latent)

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    try:
        PROF.update(json.load(open(os.path.join(ROOT, _p), encoding="utf-8")))
    except FileNotFoundError:
        pass

QID, PARENT, TOKEN = "REW_BEN_139", "REW_BEN_038", "Private Medical Insurance (PMI)"
LEVELS = ["board_executive", "director", "head_of", "senior_manager",
          "manager", "supervisor_team_leader", "frontline_individual_contributor"]
RULED_PCT = [95, 90, 80, 70, 20, 2, 0]
STAMP = "2026-07-20"
DECL = {"mode": "conditioned", "base_label": "PMI-holding organisations",
        "parent": {"qid": PARENT, "contains": TOKEN},
        "_r3sw14": "by-level eligibility conditioned on PMI-havers (n=130) + ruled EST cliff "
                   "95/90/80/70/20/2/0; verdict stays suppressed (Diff-14 flag untouched)"}


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers "
                       "WHERE question_id != ? ORDER BY 1,2,3,4", (QID,)):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


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

    c = sqlite3.connect(a.db)

    # ---- diagnose + pin the coherence-gate findings ----
    havers = sorted({o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
                     if TOKEN in (t.strip() for t in (v or "").split(";"))})
    assert len(havers) == 130, "PMI-haver set moved: %d — re-diagnose" % len(havers)
    comp = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id='REW265_BEN_PMICOMP'")}
    assert comp == set(havers), "family-set mismatch: composition base != REW_BEN_038 havers"
    byorg = {}
    for o, rid, v in c.execute("SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=?", (QID,)):
        byorg.setdefault(o, {})[rid] = v
    assert len(byorg) == 220 and all(len(r) == 7 for r in byorg.values()), "matrix shape moved"
    any_yes = {o for o, r in byorg.items() if any(v == "Yes" for v in r.values())}
    cic = any_yes - set(havers); deff = set(havers) - any_yes
    assert len(cic) == 48 and len(deff) == 48, "contradiction counts moved: %d/%d" % (len(cic), len(deff))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(byorg)), sorted(byorg))}
    assert src == {"seed"}, "non-seed org holds %s rows: %s — ABORT" % (QID, src)
    mp = json.load(open(os.path.join(ROOT, "data", "market_position_config.json"), encoding="utf-8"))["metrics"][QID]
    assert mp.get("unbenchmarked") is True, "verdict suppression flag missing — constraint violated"

    # ---- ruled depth design ----
    yes_counts = [round(p / 100.0 * 130) for p in RULED_PCT]        # 124,117,104,91,26,3,0
    assert yes_counts == [124, 117, 104, 91, 26, 3, 0]
    assert all(a_ >= b_ for a_, b_ in zip(yes_counts, yes_counts[1:])), "targets must be monotone"
    depth_hist = {}                                                  # depth k = top-k levels eligible
    prev = 130
    for k in range(7, 0, -1):
        pass
    counts_ge = yes_counts + [0]
    for k in range(0, 8):
        n_ge_k = 130 if k == 0 else counts_ge[k - 1]
        n_ge_k1 = counts_ge[k] if k < 7 else 0
        depth_hist[k] = n_ge_k - n_ge_k1
    assert sum(depth_hist.values()) == 130 and depth_hist[7] == 0
    ranked = sorted(havers, key=lambda o: (-latent(o, PROF),         # deepest depth to top latent
                                           hashlib.sha256((QID + "|" + o).encode()).hexdigest()))
    depths = {}
    i = 0
    for k in range(7, -1, -1):
        for o in ranked[i:i + depth_hist[k]]:
            depths[o] = k
        i += depth_hist[k]
    assert i == 130

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    old_rows = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (QID,)).fetchone()[0]
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  coherence gate: CICOVER 48 / DEFERRAL 48 (pinned) — subsumed by the ruled haver re-seed")
    print("  re-seed: 130 havers, depth hist %s -> per-level Yes %s" % (depth_hist, yes_counts))
    print("  answers %d -> %d (-%d +910) | all-No havers by ruled arithmetic: %d"
          % (n_before, n_before - old_rows + 910, old_rows, depth_hist[0]))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                (STAMP + " r3sw14 pre-reseed snapshot", QID))
    cur.execute("DELETE FROM answers WHERE question_id=?", (QID,))
    ins = [(o, QID, LEVELS[j], "Yes" if j < depths[o] else "No", STAMP + " 09:00:00")
           for o in havers for j in range(7)]
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,?,?,?)", ins)

    # ---- post-asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == n_before - old_rows + 910 == 231231
    new = {}
    for o, rid, v in c.execute("SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=?", (QID,)):
        new.setdefault(o, {})[rid] = v
    assert set(new) == set(havers), "answerer set != haver set"
    got = [sum(1 for o in new if new[o][L] == "Yes") for L in LEVELS]
    assert got == yes_counts, (got, yes_counts)
    for o, r in new.items():                                         # perfect top-down prefix
        seq = [r[L] for L in LEVELS]
        k = seq.count("Yes")
        assert seq == ["Yes"] * k + ["No"] * (7 - k), (o, seq)
    any_yes2 = {o for o, r in new.items() if any(v == "Yes" for v in r.values())}
    assert not (any_yes2 - set(havers)) and len(set(havers) - any_yes2) == depth_hist[0]

    # ---- config: conditioned declaration, atomic after commit ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    assert QID not in cfg["metrics"]
    cfg["metrics"][QID] = DECL
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)

    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw14_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric_id", "level", "before_yes_pct_of_220", "after_yes_n_of_130", "after_yes_pct"])
        before = {"board_executive": 59.1, "director": 59.1, "head_of": 59.1, "senior_manager": 55.9,
                  "manager": 42.3, "supervisor_team_leader": 34.5, "frontline_individual_contributor": 34.5}
        for L, n_yes in zip(LEVELS, yes_counts):
            w.writerow([QID, L, before[L], n_yes, round(100.0 * n_yes / 130, 1)])
    print(json.dumps({"applied": True, "answers_after": n_before - old_rows + 910,
                      "per_level_yes": dict(zip(LEVELS, yes_counts)), "all_no_havers": depth_hist[0],
                      "coherence": "CICOVER 0 / DEFERRAL residual = the ruled 6 (all-No by arithmetic)",
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
