# -*- coding: utf-8 -*-
"""DIFF 3 — Register hygiene, ratified 2026-07-14 (DECISIONS: Diff 3 scope + rulings).
One fix class: status flips + the three ruled corrections. ZERO answer writes
(content-hash asserted — ruling 2 left ALLOW_01 history under the deactivated id).

- Six status flips -> 'retired' (ruling 1, option a: the engine's sole terminal state),
  flavour stamped in release_retired as 2026-07-14-hygiene:<status_action-from-mapping>
  (date-based: release_retired carries NO release-number convention — the only existing
  value is the qa fixture stamp). Flavours read from domain_remap_mapping.csv (authority).
- REW_PAY_MKT_POS_01: VERIFY already retired; zero writes (its qa-fixture stamp stands).
- REW_PAY_023: in-place text edit to the ratified wording (ruling 3; no version bump,
  historical_comparability stays high).
- REW_PAY_016: +Homeworking allowance, +Mobile/phone allowance, +None (order-appended,
  house option shape {code,label,order,is_na}; addition is answer-safe).
- REW_INC_070: class=Practice, direction=None (sibling INC_069 mirror), KEEP type=binary
  (ruling 4); polarity -> neutral.
- Convergence gate POST-apply: visible_questions() == register v5 live set, 237/237,
  zero symmetric difference; cfg market-ness == register for every live id.
Double-guarded: --write --confirmed-by-david.
"""
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import app as A                      # noqa: E402
from db import get_conn              # noqa: E402

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
MAPPING = os.path.join(ROOT, "domain_remap_mapping.csv")
REGISTER = os.path.join(ROOT, "lumi_master_metric_register_FINAL_APPROVED.csv")
MP_CONFIG = os.path.join(ROOT, "data", "market_position_config.json")
QUESTIONS_CSV = os.path.join(ROOT, "data", "lumi_questions.csv")

PAY_023_TEXT = "Which factors inform your annual pay budget?"          # ruled verbatim
PAY_016_NEW = ["Homeworking allowance", "Mobile/phone allowance", "None"]
VERIFY_ONLY = "REW_PAY_MKT_POS_01"
STAMP = "2026-07-14-hygiene:%s"


def answers_hash(conn):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in conn.execute("SELECT org_id, question_id, matrix_row_id, value FROM %s "
                                "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


def main():
    conn = get_conn()
    mapping = {r["metric_id"]: r for r in csv.DictReader(open(MAPPING, encoding="utf-8-sig"))}
    flips = {qid: r["status_action"] for qid, r in mapping.items()
             if r["status_action"] != "active" and qid != VERIFY_ONLY}
    print("flips from mapping:", flips)
    assert len(flips) == 6, "expected exactly 6 flip rows"

    mk = conn.execute("SELECT status FROM questions WHERE id=?", (VERIFY_ONLY,)).fetchone()
    assert mk and mk["status"] == "retired", "%s must already be retired" % VERIFY_ONLY
    print("%s verified already-retired (no write)" % VERIFY_ONLY)

    if not WRITE:
        print("DRY RUN — pass --write --confirmed-by-david to execute")
        return

    h0 = answers_hash(conn)

    # 1. six flips with flavour stamps
    for qid, flavour in flips.items():
        n = conn.execute("UPDATE questions SET status='retired', release_retired=? WHERE id=? AND status='active'",
                         (STAMP % flavour, qid)).rowcount
        assert n == 1, "flip failed for %s" % qid
    print("6 status flips -> retired, stamped")

    # 2. REW_PAY_023 in-place reword
    n = conn.execute("UPDATE questions SET text=? WHERE id='REW_PAY_023'", (PAY_023_TEXT,)).rowcount
    assert n == 1
    print("REW_PAY_023 text -> ratified wording (in-place)")

    # 3. REW_PAY_016 option extension
    row = conn.execute("SELECT options_json FROM questions WHERE id='REW_PAY_016'").fetchone()
    opts = json.loads(row["options_json"])
    have = {o["label"] for o in opts}
    order = max(o.get("order", 0) for o in opts)
    for label in PAY_016_NEW:
        if label in have:
            continue
        order += 1
        code = "NONE" if label == "None" else label.upper().replace("/", "_").replace(" ", "_").replace("-", "_")
        code = "".join(c for c in code if c.isalnum() or c == "_")
        opts.append({"code": code, "label": label, "order": order, "is_na": False})
    conn.execute("UPDATE questions SET options_json=? WHERE id='REW_PAY_016'", (json.dumps(opts),))
    print("REW_PAY_016 options: %d (+%s)" % (len(opts), PAY_016_NEW))

    # 4. REW_INC_070 (ruling 4: class+direction mirror, type stays binary)
    cfg = json.load(open(MP_CONFIG))
    ent = dict(cfg["metrics"].get("REW_INC_070") or {})
    ent.update({"class": "Practice", "direction": None})
    cfg["metrics"]["REW_INC_070"] = ent
    json.dump(cfg, open(MP_CONFIG, "w"), indent=2, ensure_ascii=False)
    conn.execute("UPDATE questions SET polarity='neutral' WHERE id='REW_INC_070'")
    print("REW_INC_070: class=Practice direction=None (type stays %r), polarity=neutral" % ent.get("type"))
    conn.commit()

    # 5. lumi_questions.csv echoes (status/text/options/polarity for ids present)
    with open(QUESTIONS_CSV, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames
        rows = list(rdr)
    nc = 0
    for r in rows:
        qid = r.get("id")
        if qid in flips and "status" in r:
            r["status"] = "retired"; nc += 1
        if qid == "REW_PAY_023" and "text" in r:
            r["text"] = PAY_023_TEXT; nc += 1
        if qid == "REW_PAY_016" and "options" in r and r["options"]:
            parts = [p.strip() for p in r["options"].split(";")]
            for label in PAY_016_NEW:
                if label not in parts:
                    parts.append(label)
            r["options"] = ";".join(parts); nc += 1
        if qid == "REW_INC_070" and "polarity" in r:
            r["polarity"] = "neutral"; nc += 1
    with open(QUESTIONS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("lumi_questions.csv echoes:", nc)

    # 6. assertions: append-only + convergence gate
    assert answers_hash(conn) == h0, "ANSWER TABLES MOVED — restore from backup NOW"
    print("answers/answers_history content hash IDENTICAL")
    A.load_questions.cache_clear()
    vis = A.visible_questions()
    reg = {r["metric_id"]: r for r in csv.DictReader(open(REGISTER))}
    reg_live = {q for q, r in reg.items() if r["status"].startswith("live")}
    sym = set(vis) ^ reg_live
    assert not sym, "CONVERGENCE FAILED — symmetric difference: %s" % sorted(sym)[:6]
    cfg = json.load(open(MP_CONFIG))
    bad = []
    for qid in vis:
        want = {"market": True, "practice": False, "strategy-config": False}[reg[qid]["classification"]]
        got = (cfg["metrics"].get(qid) or {}).get("class") in ("Level", "Provision")
        if got != want:
            bad.append((qid, reg[qid]["classification"], got))
    assert not bad, "cfg vs register divergence: %s" % bad[:5]
    from collections import Counter
    per = Counter(vis[q].sub_power for q in vis)
    print("CONVERGENCE GATE: visible == register v5 live set, %d/%d, zero symmetric difference" % (len(vis), len(reg_live)))
    print("per-domain after:", dict(sorted(per.items())), "| sum:", sum(per.values()))


if __name__ == "__main__":
    main()
