# -*- coding: utf-8 -*-
"""migrate_r3s4_tips_scope.py — sector-scope pilot: tips answer-data clean + reseed.

data/sector_scopes.json declares tips hospitality-only (the app layer hides it).
This migration fixes the DATA: the 199 out-of-scope answers (the impossible
67.5% all-org yes) are DELETED (absence, never NA), and the in-scope hospitality
orgs are reseeded 80/20 yes/no (EST, D. Whitfield), largest-remainder,
hash-deterministic. Non-hospitality orgs leave the peer base entirely: n -> 15.
Dry-run default; --write requires --confirmed-by-david. Emits r3s4_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QID = "REW_PAY_TIPS_EXIST_7c80c508"
SCOPE = set(json.load(open(os.path.join(ROOT, "data", "sector_scopes.json")))["scopes"][QID]["sectors"])
DIST = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["ruled_distributions"][QID]["distribution"]
STAMP = "2026-07-18 r3s4 tips scope"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()

    ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                        WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (QID,)).fetchone()[0]
    assert ns == 0, "non-seed answers on tips — ABORT"
    in_scope = [o for (o,) in cur.execute(
        "SELECT org_id FROM orgs WHERE industry IN (%s) AND org_id IN (SELECT DISTINCT org_id FROM answers)"
        % ",".join("?" * len(SCOPE)), sorted(SCOPE))]
    out_rows = cur.execute("""SELECT COUNT(*) FROM answers a JOIN orgs o ON o.org_id=a.org_id
                              WHERE a.question_id=? AND o.industry NOT IN (%s)"""
                           % ",".join("?" * len(SCOPE)), [QID] + sorted(SCOPE)).fetchone()[0]
    before = Counter(v for (v,) in cur.execute(
        "SELECT value FROM answers WHERE question_id=? AND value!=''", (QID,)))
    # in-scope target: every hospitality org answers, largest-remainder over DIST
    ranked = sorted(in_scope, key=lambda o: hashlib.sha256((QID + "|" + o).encode()).hexdigest())
    raw = {lbl: pct * len(ranked) / 100.0 for lbl, pct in DIST.items()}
    fl = {lbl: int(raw[lbl]) for lbl in raw}
    for lbl in sorted(raw, key=lambda l: -(raw[l] - fl[l]))[: len(ranked) - sum(fl.values())]:
        fl[lbl] += 1
    newmap = {}
    i = 0
    for lbl in DIST:
        for _ in range(fl[lbl]):
            newmap[ranked[i]] = lbl; i += 1
    print("%s: in-scope orgs %d | out-of-scope answers to DELETE %d | before %s | after %s"
          % ("APPLY" if a.write else "dry-run", len(in_scope), out_rows, dict(before), fl))
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, QID))
    cur.execute("DELETE FROM answers WHERE question_id=?", (QID,))
    for o, lbl in newmap.items():
        cur.execute("""INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at)
                       VALUES (?,1,?,'',?,?)""", (o, QID, lbl, STAMP))
    c.commit()

    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id!=? ORDER BY 1,2,3,4", (QID,)))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    got = dict(cur.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (QID,)))
    assert got == fl, (got, fl)
    stray = cur.execute("""SELECT COUNT(*) FROM answers a JOIN orgs o ON o.org_id=a.org_id
                           WHERE a.question_id=? AND o.industry NOT IN (%s)"""
                        % ",".join("?" * len(SCOPE)), [QID] + sorted(SCOPE)).fetchone()[0]
    assert stray == 0, "out-of-scope answers survive"
    with open(os.path.join(ROOT, "r3s4_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader()
        w.writerow({"metric_id": QID, "action": "sector-scope clean + reseed (hospitality only)",
                    "before": json.dumps(dict(before)), "after": json.dumps(fl)})
    print(json.dumps({"applied": True, "n_in_scope": len(newmap), "out_of_scope_deleted": out_rows,
                      "non_target_book": "hash-identical", "stray_out_of_scope": 0,
                      "manifest": "r3s4_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
