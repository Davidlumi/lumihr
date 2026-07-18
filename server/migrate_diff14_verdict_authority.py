# -*- coding: utf-8 -*-
"""migrate_diff14_verdict_authority.py — Diff 14 DB side (ruled 2026-07-18).

Two actions, both derived from diff14_scope.json (no metric ids hardcoded):
  1. questions.polarity -> 'neutral' for the 220 suppress_flips (distribution has
     no ruled authority; verdict suppression layer b — layer a is the curated
     market_position_config.json edit, layer c the unbenchmarked card flag).
  2. Retire the 2 ruled deletes (PROP_dff9a2a5 fictional-practice award-rate;
     REW264_PEN_CONTRIBTIER legally-dead practice): status='retired',
     release_retired='2026.4', answers snapshotted to answers_history then
     DELETED (ruled: fictional-practice seeds, no reconstruction value),
     benchmark_snapshots payload rows deleted.

Guards: dry-run by default; --write requires --confirmed-by-david. Seed-org-only
deletion asserted (any signup/staff answer on a retiree aborts). Non-target book
content-hash asserted identical. Keeper polarity asserted untouched.
Usage: python3 migrate_diff14_verdict_authority.py [--db PATH] [--write --confirmed-by-david]
"""
import sqlite3, json, hashlib, sys, os, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = json.load(open(os.path.join(ROOT, "diff14_scope.json")))
FLIPS, RETIRE, KEEP = SCOPE["suppress_flips"], SCOPE["retire"], SCOPE["keep"]
assert len(FLIPS) == 220 and len(RETIRE) == 2 and len(KEEP) == 51, (len(FLIPS), len(RETIRE), len(KEEP))
STAMP = "2026-07-18 diff14"

def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY org_id,question_id,matrix_row_id,value" % ",".join("?"*len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(map(str, r)) + "\n").encode())
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row

    # ---- diagnose ----
    pol = {r["id"]: r["polarity"] for r in c.execute(
        "SELECT id,polarity FROM questions WHERE id IN (%s)" % ",".join("?"*len(FLIPS)), FLIPS)}
    assert len(pol) == 220, "flip target missing from questions table: %d found" % len(pol)
    to_flip = [q for q, p in pol.items() if p != "neutral"]
    keep_pol_before = {r["id"]: r["polarity"] for r in c.execute(
        "SELECT id,polarity FROM questions WHERE id IN (%s)" % ",".join("?"*len(KEEP)), KEEP)}
    ret_rows = {}
    for qid in RETIRE:
        src = dict(c.execute("""SELECT COALESCE(o.source,'(null)') s, COUNT(*) n FROM answers x
                                JOIN orgs o ON o.org_id=x.org_id WHERE x.question_id=? GROUP BY 1""", (qid,)))
        ret_rows[qid] = src
        assert set(src) <= {"seed"}, "NON-SEED answers on retiree %s: %s — ABORT" % (qid, src)
    pre_hash = book_hash(c, RETIRE)
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    del_n = sum(sum(v.values()) for v in ret_rows.values())
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  polarity flips needed: %d of 220 (already neutral: %d)" % (len(to_flip), 220 - len(to_flip)))
    print("  retiree answers (all seed, asserted): %s -> delete %d" % (
        {k: sum(v.values()) for k, v in ret_rows.items()}, del_n))
    print("  answers %d -> %d expected" % (n_before, n_before - del_n))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    # ---- apply ----
    cur = c.cursor()
    for qid in to_flip:
        cur.execute("UPDATE questions SET polarity='neutral' WHERE id=?", (qid,))
    for qid in RETIRE:
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                    (STAMP + " pre-retire snapshot", qid))
        cur.execute("DELETE FROM answers WHERE question_id=?", (qid,))
        cur.execute("UPDATE questions SET status='retired', release_retired='2026.4' WHERE id=?", (qid,))
        cur.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (qid,))
    c.commit()

    # ---- post-asserts ----
    assert book_hash(c, RETIRE) == pre_hash, "NON-TARGET BOOK CHANGED"
    n_after = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    assert n_after == n_before - del_n, (n_after, n_before, del_n)
    left = {r[0] for r in c.execute("SELECT DISTINCT polarity FROM questions WHERE id IN (%s)" % ",".join("?"*len(FLIPS)), FLIPS)}
    assert left == {"neutral"}, left
    keep_after = {r["id"]: r["polarity"] for r in c.execute(
        "SELECT id,polarity FROM questions WHERE id IN (%s)" % ",".join("?"*len(KEEP)), KEEP)}
    assert keep_after == keep_pol_before, "KEEPER POLARITY MOVED"
    for qid in RETIRE:
        st = c.execute("SELECT status,release_retired FROM questions WHERE id=?", (qid,)).fetchone()
        assert st["status"] == "retired" and st["release_retired"] == "2026.4", dict(st)
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=?", (qid,)).fetchone()[0] == 0
    hist = c.execute("SELECT COUNT(*) FROM answers_history WHERE recorded_at LIKE ?", (STAMP + "%",)).fetchone()[0]
    print(json.dumps({"applied": True, "polarity_flipped": len(to_flip), "answers_deleted": del_n,
                      "answers_after": n_after, "history_rows": hist,
                      "non_target_book": "hash-identical", "keepers": "polarity untouched"}, indent=2))

if __name__ == "__main__":
    main()
