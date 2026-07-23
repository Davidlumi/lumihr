"""
nonrew-2 — HARD-DELETE all non-Reward questions and their attached rows. IRREVERSIBLE.

David ruled Reward-only IS the product. Every question with superpower != 'Reward' (600: 404 active,
196 proposed) and its attached rows are hard-deleted — NOT retired. This deliberately contradicts
releases.py:11 "retire, never delete" and app.py:172's flag-revivable architecture; after this,
re-showing any of the nine non-Reward areas requires a full reseed, not a flag flip.

THE FK FORK (the diagnostic's central hazard): db.py:24 sets PRAGMA foreign_keys=ON, but every r3sw
migration uses plain sqlite3.connect() (FK OFF). The FKs to questions(id) are ON DELETE NO ACTION.
Under FK-OFF this deletion would SILENTLY ORPHAN 141,038 answers with no error. This runner runs FK-ON
DELIBERATELY: an incomplete child cleanup aborts safely instead of orphaning. It proves the pragma is on.

MECHANISM: ONE atomic transaction, children before parents:
  pulse_responses -> benchmark_snapshots -> answers -> questions,
  plus filtering pulse-90a56a58's question_ids_json / question_snapshot_json to drop the 2 deleted
  Pulse-superpower qids (keeping its 3 Reward qids). Derive-don't-hardcode throughout.

GUARDS (all mandatory; abort + rollback on any failure):
  pre : frozen-8 present/Reward/not-in-set; coherence pairs 0 non-Reward (repo-root files); set==600;
        survivors==344; FK pragma==1; capture frozen-8 snapshot + survivor-answers hash.
  post: questions==344; answers==89321; every survivor superpower=='Reward'; ZERO orphans in any
        question_id-bearing table; frozen-8 snapshot byte-identical; whole answers-book == the
        pre-captured survivor hash (surviving Reward answers byte-identical); pulse JSON filtered to
        3 survivors, 0 deleted qids.

Dual-guard: dry-run default (report only, no DML). --write applies+asserts+commits (use --db <copy>
for the throwaway proof). Live (db==lumi.db) additionally requires --confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]
PULSE_ID = "pulse-90a56a58"
EXPECT_DEL, EXPECT_SURV = 600, 344
EXPECT_ANS_DEL, EXPECT_BS_DEL, EXPECT_PR_DEL = 141038, 600, 26
EXPECT_Q_AFTER, EXPECT_A_AFTER = 344, 89321


def frozen_snap(c):
    return {q: dict(c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (q,))) for q in FROZEN8}


def survivor_hash(c):
    """Hash of the answers that MUST survive (Reward questions), pre-delete. Post-delete the whole book
    must equal this — proving no surviving Reward answer moved and nothing collateral was touched."""
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers WHERE question_id IN (SELECT id FROM questions WHERE superpower='Reward') "
                       "ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def coherence_nonreward(del_ids, allids):
    def collect(o, acc):
        if isinstance(o, dict):
            for v in o.values(): collect(v, acc)
        elif isinstance(o, list):
            for v in o: collect(v, acc)
        elif isinstance(o, str): acc.add(o)
    bad = set()
    for path, key in [("structured_bases.json", "_coherence_pairs"), ("generated_marginals.json", "coherence_pairs")]:
        d = json.load(open(os.path.join(ROOT, path)))
        acc = set(); collect(d.get(key, []), acc)
        bad |= (acc & allids & del_ids)
    return sorted(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == os.path.join(ROOT, "lumi.db")
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live hard-delete needs --confirmed-by-david (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db)
    c.isolation_level = None                       # manual transaction control (FK pragma must be set outside a txn)
    c.execute("PRAGMA foreign_keys=ON")
    fk = c.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1, "PRAGMA foreign_keys is OFF (%r) — REFUSING (silent-orphan hazard)" % fk

    # ---------------- PRE-FLIGHT (read-only asserts) ----------------
    allids = {r[0] for r in c.execute("SELECT id FROM questions")}
    del_ids = sorted(r[0] for r in c.execute("SELECT id FROM questions WHERE COALESCE(superpower,'')!='Reward'"))
    surv = allids - set(del_ids)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    fsp = {r[0]: r[1] for r in c.execute("SELECT id,superpower FROM questions WHERE id IN (%s)" % ",".join("?" * 8), FROZEN8)}
    assert all(q in allids for q in FROZEN8) and set(fsp.values()) == {"Reward"}, "frozen-8 not all present & Reward"
    assert not (set(FROZEN8) & set(del_ids)), "a frozen target is in the deletion set — HARD ABORT"
    assert all(q in ft for q in FROZEN8), "a frozen target missing from frozen_targets.json"
    assert len(del_ids) == EXPECT_DEL, "deletion set %d != %d — SET MOVED, HARD ABORT" % (len(del_ids), EXPECT_DEL)
    assert len(surv) == EXPECT_SURV, "survivors %d != %d" % (len(surv), EXPECT_SURV)
    bad_coh = coherence_nonreward(set(del_ids), allids)
    assert not bad_coh, "coherence pair references a deletion-set qid: %s" % bad_coh

    def cnt(t):
        return c.execute("SELECT COUNT(*) FROM %s WHERE question_id IN (SELECT id FROM questions WHERE COALESCE(superpower,'')!='Reward')" % t).fetchone()[0]
    n_pr, n_bs, n_ans = cnt("pulse_responses"), cnt("benchmark_snapshots"), cnt("answers")
    assert (n_pr, n_bs, n_ans) == (EXPECT_PR_DEL, EXPECT_BS_DEL, EXPECT_ANS_DEL), \
        "attached counts moved: pr=%d bs=%d ans=%d" % (n_pr, n_bs, n_ans)
    q_before = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    a_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    frozen_pre = frozen_snap(c)
    surv_target = survivor_hash(c)                 # what the whole book must equal AFTER deletion

    # pulse JSON: derive the filtered blobs (drop del qids, keep survivors)
    prow = c.execute("SELECT question_ids_json,question_snapshot_json FROM pulses WHERE pulse_id=?", (PULSE_ID,)).fetchone()
    ids_old = json.loads(prow[0]) if prow[0] else []
    snap_old = json.loads(prow[1]) if prow[1] else {}
    ids_new = [q for q in ids_old if q not in set(del_ids)]
    snap_new = {k: v for k, v in snap_old.items() if k not in set(del_ids)} if isinstance(snap_old, dict) else snap_old
    ids_new_txt = json.dumps(ids_new, ensure_ascii=False)
    snap_new_txt = json.dumps(snap_new, ensure_ascii=False)

    print("nonrew-2 hard-delete — %s (db=%s, FK=%d)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db), fk))
    print("  deletion set = %d (survivors %d) | attached: pulse_responses=%d benchmark_snapshots=%d answers=%d"
          % (len(del_ids), len(surv), n_pr, n_bs, n_ans))
    print("  pulse %s: %d qids -> %d (drop %s)" % (PULSE_ID, len(ids_old), len(ids_new), [q for q in ids_old if q in set(del_ids)]))
    print("  EXPECT post: questions %d -> %d | answers %d -> %d" % (q_before, EXPECT_Q_AFTER, a_before, EXPECT_A_AFTER))
    if not a.write:
        print("dry-run complete — no DML. Run with --db <throwaway> --write (proof) or --write --confirmed-by-david (LIVE).")
        c.close(); return

    # ---------------- ATOMIC TRANSACTION (children before parents) ----------------
    marks = ",".join("?" * len(del_ids))
    try:
        c.execute("BEGIN")
        d_pr = c.execute("DELETE FROM pulse_responses WHERE question_id IN (%s)" % marks, del_ids).rowcount
        d_bs = c.execute("DELETE FROM benchmark_snapshots WHERE question_id IN (%s)" % marks, del_ids).rowcount
        d_an = c.execute("DELETE FROM answers WHERE question_id IN (%s)" % marks, del_ids).rowcount
        c.execute("UPDATE pulses SET question_ids_json=?, question_snapshot_json=? WHERE pulse_id=?",
                  (ids_new_txt, snap_new_txt, PULSE_ID))
        d_q = c.execute("DELETE FROM questions WHERE id IN (%s)" % marks, del_ids).rowcount

        # ---- delete-count asserts ----
        assert d_pr == EXPECT_PR_DEL, "pulse_responses deleted %d != %d" % (d_pr, EXPECT_PR_DEL)
        assert d_bs == EXPECT_BS_DEL, "benchmark_snapshots deleted %d != %d" % (d_bs, EXPECT_BS_DEL)
        assert d_an == EXPECT_ANS_DEL, "answers deleted %d != %d" % (d_an, EXPECT_ANS_DEL)
        assert d_q == EXPECT_DEL, "questions deleted %d != %d" % (d_q, EXPECT_DEL)

        # ---- post-state asserts ----
        q_after = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        a_after = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
        assert q_after == EXPECT_Q_AFTER, "questions after %d != %d" % (q_after, EXPECT_Q_AFTER)
        assert a_after == EXPECT_A_AFTER, "answers after %d != %d" % (a_after, EXPECT_A_AFTER)
        assert c.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(superpower,'')!='Reward'").fetchone()[0] == 0, \
            "a non-Reward question survived"
        # ZERO orphans CREATED by this deletion: no row references a DELETED qid (bare OR composite base).
        # A broad "NOT IN questions" check would false-flag pre-existing signal_actions composite keys
        # ("<reward_matrix_qid>::rowkey") that legitimately reference SURVIVING Reward questions — verified
        # 0 signal_actions/signal_state bases fall in the deletion set, so this deletion orphans none of them.
        dset = set(del_ids)
        orphans = {}
        for t in ("answers", "benchmark_snapshots", "pulse_responses", "answers_history",
                  "release_questions", "signal_state", "signal_actions", "core_changelog", "drafts"):
            bad = sum(1 for (qid,) in c.execute("SELECT question_id FROM %s WHERE question_id IS NOT NULL" % t)
                      if qid.split("::")[0] in dset)
            if bad: orphans[t] = bad
        assert not orphans, "DELETION ORPHANS (rows referencing a deleted qid, incl composite base): %s" % orphans
        # frozen-8 byte-identical
        assert frozen_snap(c) == frozen_pre, "a FROZEN target moved — HARD ABORT"
        # surviving Reward answers byte-identical: whole book now == pre-captured survivor hash
        bh = book_hash(c)
        assert bh == surv_target, "surviving answers NOT byte-identical to pre-delete Reward answers"
        # pulse JSON filtered correctly
        pr2 = c.execute("SELECT question_ids_json,question_snapshot_json FROM pulses WHERE pulse_id=?", (PULSE_ID,)).fetchone()
        ids2 = json.loads(pr2[0]); snap2 = json.loads(pr2[1])
        assert not (set(ids2) & set(del_ids)) and not (set(snap2) & set(del_ids)), "pulse JSON still references a deleted qid"
        assert len(ids2) == len(ids_new) and len(snap2) == len(snap_new), "pulse JSON length wrong"
    except Exception as e:
        c.execute("ROLLBACK")
        print("ROLLED BACK — assertion failed, DB unchanged: %s" % e)
        c.close(); raise

    c.execute("COMMIT")
    print(json.dumps({"applied": True, "live": is_live, "fk": fk,
                      "deleted": {"pulse_responses": d_pr, "benchmark_snapshots": d_bs, "answers": d_an, "questions": d_q},
                      "after": {"questions": q_after, "answers": a_after},
                      "orphans": "NONE", "frozen8": "byte-identical",
                      "survivor_answers": "byte-identical (book==%s…)" % bh[:12],
                      "pulse_qids": "%d -> %d" % (len(ids_old), len(ids2))}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
