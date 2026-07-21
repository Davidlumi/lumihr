"""
r3sw18 — PROP_634adacd option relabel: "Not measured / varies widely" -> "Not measured"
(harmonise to the canonical not-measured label; kept option per r3sw13).

Bank stores answers by LABEL (verified), so a relabel MUST retag the 2 answer rows to keep them
mapped — distribution unchanged, mapping preserved, but NOT answers-byte-identical (ruled, David
21 Jul 2026). Option CODE (NOT_MEASURED_VARIES_WIDELY) + is_na + order unchanged; question_version
bumped. Non-target book hash-identical. Dry-run default; --write --confirmed-by-david.
"""
import argparse, hashlib, json, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QID, CODE = "PROP_634adacd", "NOT_MEASURED_VARIES_WIDELY"
OLD, NEW = "Not measured / varies widely", "Not measured"
STAMP = "2026-07-21"


def dist_by_code(c):
    lab2code = {o["label"]: o["code"] for o in json.loads(
        c.execute("SELECT options_json FROM questions WHERE id=?", (QID,)).fetchone()[0])}
    d = {}
    for v, n in c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? AND value!='' GROUP BY 1", (QID,)):
        d[lab2code.get(v, "UNMATCHED:" + v)] = n
    return d


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
    a = ap.parse_args()
    c = sqlite3.connect(a.db)

    oj = json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (QID,)).fetchone()[0])
    assert any(o["code"] == CODE and o["label"] == OLD for o in oj), "target option not in expected state"
    n2 = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (QID, OLD)).fetchone()[0]
    assert n2 == 2, "answerers moved: %d (expected 2)" % n2
    src = {r[0] for r in c.execute("SELECT COALESCE(o.source,'x') FROM answers x JOIN orgs o ON o.org_id=x.org_id "
                                   "WHERE x.question_id=? AND x.value=?", (QID, OLD))}
    assert src == {"seed"}, "non-seed answerer: %s" % src
    dist_before = dist_by_code(c)

    print("dry-run diagnosis:" if not a.write else "APPLY:")
    print("  relabel %r: %r -> %r (code %s unchanged) | retag 2 answers | distribution unchanged"
          % (QID, OLD, NEW, CODE))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                   WHERE question_id=? AND value=?""", (STAMP + " r3sw18 pre-relabel", QID, OLD))
    for o in oj:
        if o["code"] == CODE:
            o["label"] = NEW
    ver = c.execute("SELECT question_version FROM questions WHERE id=?", (QID,)).fetchone()[0]
    m = re.match(r"v(\d+)\.(\d+)", ver or "v1.0")
    cur.execute("UPDATE questions SET options_json=?, question_version=? WHERE id=?",
                (json.dumps(oj), "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1), QID))
    cur.execute("UPDATE answers SET value=? WHERE question_id=? AND value=?", (NEW, QID, OLD))

    # ---- asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    assert dist_by_code(c) == dist_before, "DISTRIBUTION CHANGED (by code)"
    lab = {o["code"]: o["label"] for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (QID,)).fetchone()[0])}
    assert lab[CODE] == NEW and OLD not in lab.values()
    assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (QID, NEW)).fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (QID, OLD)).fetchone()[0] == 0
    c.commit()
    print(json.dumps({"applied": True, "relabelled": "%r -> %r" % (OLD, NEW), "code_unchanged": CODE,
                      "answers_retagged": 2, "distribution": "byte-identical by code (%s)" % dist_before,
                      "non_target_book": "hash-identical", "version": "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1)}, indent=2))


if __name__ == "__main__":
    main()
