# -*- coding: utf-8 -*-
"""DIFF 1 — Domain taxonomy remap (metadata only), ratified 2026-07-14 (Option B',
7 -> 8 domains). Row-level authority: domain_remap_mapping.csv (244 rows; the one id
not in the live set, REW_PAY_MKT_POS_01, is already retired in the DB and remaps
inertly). Ruling 4 (2026-07-14): opens with a row-level reconciliation against
visible_questions() and refuses to write on ANY discrepancy.

Writes (metadata only):
  - questions.sub_power + sub_power_order (new domain + its rank)
  - data/lumi_questions.csv sub_power / sub_power_code / sub_power_order columns
  - data/market_position_config.json _domains -> the 8 flags EXACTLY per the recorded
    ruling (G&T stays FALSE; its TRUE flip is a Diff 2 question)
NEVER writes answers / answers_history — asserted by content hash before/after.

Double-guarded: refuses without --write --confirmed-by-david (house rule).
"""
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAPPING = os.path.join(ROOT, "domain_remap_mapping.csv")
QUESTIONS_CSV = os.path.join(ROOT, "data", "lumi_questions.csv")
MP_CONFIG = os.path.join(ROOT, "data", "market_position_config.json")

sys.path.insert(0, HERE)
import app as A                      # noqa: E402  (engine import = the reconciliation authority)
from db import get_conn              # noqa: E402

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

# DECISIONS 2026-07-14 (Option B'): the ratified listing order IS the display order.
DOMAIN_ORDER = ["Pay", "Pensions & Savings", "Health & Protection", "Benefits & Lifestyle",
                "Time Off & Family", "Incentives & Recognition", "Wellbeing",
                "Governance & Transparency"]
DOMAIN_RANK = {d: i + 1 for i, d in enumerate(DOMAIN_ORDER)}
DOMAIN_CODE = {d: "REW_" + d.upper().replace(" & ", "_").replace(" ", "_") for d in DOMAIN_ORDER}
# DECISIONS 2026-07-14 (competitiveness flags, Diff 1 scope) — verdict-neutral carry-over.
DOMAIN_FLAGS = {d: {"competitiveness": d != "Governance & Transparency"} for d in DOMAIN_ORDER}

INERT_EXTRA = "REW_PAY_MKT_POS_01"   # ruled 2026-07-14: already retired; remap inert, verify only


def answers_hash(conn):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in conn.execute(
                "SELECT org_id, question_id, matrix_row_id, value FROM %s "
                "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


def main():
    mapping = {r["metric_id"]: r for r in csv.DictReader(open(MAPPING, encoding="utf-8-sig"))}
    vis = A.visible_questions()
    conn = get_conn()

    # ---- ruling-4 reconciliation gate: refuse on ANY discrepancy --------------
    only_db = sorted(set(vis) - set(mapping))
    only_map = sorted(set(mapping) - set(vis))
    if only_db:
        sys.exit("REFUSED: visible metrics missing from mapping: %s" % only_db)
    if only_map != [INERT_EXTRA]:
        sys.exit("REFUSED: unexpected mapping extras: %s" % only_map)
    inert = conn.execute("SELECT status FROM questions WHERE id=?", (INERT_EXTRA,)).fetchone()
    if inert is None or inert["status"] != "retired":
        sys.exit("REFUSED: %s expected retired in DB, found %r" % (INERT_EXTRA, inert and inert["status"]))
    bad_dom = sorted({r["new_domain"] for r in mapping.values()} - set(DOMAIN_ORDER))
    if bad_dom:
        sys.exit("REFUSED: mapping carries unknown destination domains: %s" % bad_dom)
    mism = [(q, vis[q].sub_power, mapping[q]["old_sub_power"]) for q in vis
            if vis[q].sub_power != mapping[q]["old_sub_power"]]
    if mism:
        sys.exit("REFUSED: old_sub_power disagreements: %s" % mism[:5])

    before = {}
    for r in conn.execute("SELECT sub_power, COUNT(*) c FROM questions WHERE id IN (%s) "
                          "GROUP BY sub_power" % ",".join("?" * len(vis)), list(vis)):
        before[r["sub_power"]] = r["c"]
    after = {}
    for q in vis:
        after[mapping[q]["new_domain"]] = after.get(mapping[q]["new_domain"], 0) + 1
    print("before (live 243):", dict(sorted(before.items())))
    print("after  (live 243):", dict(sorted(after.items())), "| sum:", sum(after.values()))

    if not WRITE:
        print("DRY RUN — pass --write --confirmed-by-david to execute")
        return

    h0 = answers_hash(conn)

    # ---- 1. DB: questions.sub_power + sub_power_order (mapped rows only) ------
    n_db = 0
    for qid, row in mapping.items():
        nd = row["new_domain"]
        cur = conn.execute(
            "UPDATE questions SET sub_power=?, sub_power_order=? WHERE id=?",
            (nd, DOMAIN_RANK[nd], qid))
        n_db += cur.rowcount
    conn.commit()
    print("DB rows updated:", n_db, "(244 mapped incl. the inert retired row)")

    # ---- 2. lumi_questions.csv (seed source; utf-8-sig preserved) -------------
    with open(QUESTIONS_CSV, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames
        rows = list(rdr)
    n_csv = 0
    for r in rows:
        m = mapping.get(r.get("id"))
        if m:
            nd = m["new_domain"]
            r["sub_power"], r["sub_power_code"], r["sub_power_order"] = nd, DOMAIN_CODE[nd], str(DOMAIN_RANK[nd])
            n_csv += 1
    with open(QUESTIONS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("lumi_questions.csv rows updated:", n_csv)

    # ---- 3. market_position_config.json _domains (8 flags per ruling) ---------
    cfg = json.load(open(MP_CONFIG))
    cfg["_domains"] = DOMAIN_FLAGS
    json.dump(cfg, open(MP_CONFIG, "w"), indent=2, ensure_ascii=False)
    print("mp_config _domains -> 8 flags (G&T competitiveness=false per ruling)")

    # ---- 4. append-only assertion ---------------------------------------------
    h1 = answers_hash(conn)
    assert h0 == h1, "ANSWER TABLES MOVED — restore from backup NOW"
    print("answers/answers_history content hash IDENTICAL:", h0[:16])

    # re-derive from DB as final proof
    final = {}
    for r in conn.execute("SELECT sub_power, COUNT(*) c FROM questions WHERE id IN (%s) "
                          "GROUP BY sub_power" % ",".join("?" * len(vis)), list(vis)):
        final[r["sub_power"]] = r["c"]
    assert final == after, "DB-derived counts diverge from mapping-derived: %s" % final
    print("DB re-derived per-domain counts MATCH mapping derivation exactly.")


if __name__ == "__main__":
    main()
