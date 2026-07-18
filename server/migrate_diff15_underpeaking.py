# -*- coding: utf-8 -*-
"""migrate_diff15_underpeaking.py — Diff 15 DB side (six rulings, 2026-07-18).

Reads diff15_derivation_rules.json + generated_marginals.json (ruled_distributions)
+ frozen_targets.json (PENSION_TYPE re-freeze). No distributions hardcoded here.

  A. Option edits: strip Don't-know/NA (REW_PAY_005, EXT_REW_GAP_010), remove
     'None' from PENSION_TYPE (AE mandate), replace PROP_fe1a29ec's option set
     (+ scoring ladder re-map), PAYCOMMS single_select -> by-level matrix.
  B. Answer ops (history-snapshotted, seed orgs only — zero non-seed asserted):
     DK deletes; 5 exact reshapes (largest remainder, latent/hash-ranked);
     PAYCOMMS matrix rebuild (nested-by-latent conversation depth).
  C. Retire REW264_PEN_PENLEAVEGAP (+ payload row).
Emits diff15_seed_manifest.csv. Dry-run default; --write needs --confirmed-by-david.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # noqa: E402 (deterministic spine, no DB open at import)

CFG = json.load(open(os.path.join(ROOT, "diff15_derivation_rules.json")))
GEN = json.load(open(os.path.join(ROOT, "generated_marginals.json")))
RDIST = GEN["ruled_distributions"]
FROZ = json.load(open(os.path.join(ROOT, "frozen_targets.json")))["REW26_BEN_PENSION_TYPE"]["dist"]
PAY = CFG["paycomms_redesign"]
RETIRE = list(CFG["retire"])
STAMP = "2026-07-18 diff15"
TOUCHED = ["REW_PAY_005", "EXT_REW_GAP_010", "REW265_PAY_RANGEMAX", "REW26_BEN_PENSION_TYPE",
           "PROP_fe1a29ec", "REW265_PAY_PAYCOMMS"] + RETIRE

PROF = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update(json.load(open(os.path.join(ROOT, p))))


def lr_counts(shares, n):
    """largest-remainder integer counts for {label: pct} over n."""
    raw = {k: v * n / 100.0 for k, v in shares.items()}
    fl = {k: int(raw[k]) for k in raw}
    for k in sorted(raw, key=lambda k: -(raw[k] - fl[k]))[: n - sum(fl.values())]:
        fl[k] += 1
    return fl


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(map(str, r)) + "\n").encode())
    return h.hexdigest()


def ranked_orgs(c, qid, orgs, ordered):
    """orgs sorted for assignment: latent desc when the metric is ordered
    (generous pole to high-latent), else stable hash (nominal — no spine pole)."""
    if ordered:
        return sorted(orgs, key=lambda o: (-latent(o, PROF), hashlib.sha256((qid + "|" + o).encode()).hexdigest()))
    return sorted(orgs, key=lambda o: hashlib.sha256((qid + "|" + o).encode()).hexdigest())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    cur = c.cursor()

    for qid in TOUCHED:
        ns = c.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                          WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (qid,)).fetchone()[0]
        assert ns == 0, "NON-SEED answers on %s: %d — ABORT" % (qid, ns)
    pre_hash = book_hash(c)
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    # ---------- plan (shared by dry-run and apply) ----------
    plan = {}   # qid -> {"before": {..}, "after_counts": {..}, "note": str}
    # DK deletes
    dk_del = {}
    for qid, labels in CFG["dk_answer_deletes"].items():
        nn = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value IN (%s)"
                       % ",".join("?" * len(labels)), [qid] + labels).fetchone()[0]
        dk_del[qid] = nn
    # reshapes: the 4 ruled dists + PENSION_TYPE (frozen, shares in fractions)
    reshape = {q: e["distribution"] for q, e in RDIST.items()}
    reshape["REW26_BEN_PENSION_TYPE"] = {k: v * 100 for k, v in FROZ.items()}
    ORDERED = {"REW_PAY_005": ["Below Market", "Slightly Below", "On Market", "Slightly Above", "Above Market"],
               "PROP_fe1a29ec": ["No benchmarking at all",
                                 "Informally only (job adverts, ad hoc, online, ChatGPT)",
                                 "Yes - formal/structured (survey data, provider, market analysis)"]}
    for qid, shares in reshape.items():
        rows = [(o, v) for o, v in c.execute(
            "SELECT org_id, value FROM answers WHERE question_id=? AND matrix_row_id=''", (qid,))]
        keep = [o for o, v in rows if v not in (CFG["dk_answer_deletes"].get(qid) or [])]
        counts = lr_counts(shares, len(keep))
        before = {}
        for _, v in rows: before[v] = before.get(v, 0) + 1
        plan[qid] = {"before": before, "after_counts": counts,
                     "orgs": keep, "ordered": qid in ORDERED, "order": ORDERED.get(qid)}
    # paycomms
    pc_orgs = [o for (o,) in c.execute("SELECT org_id FROM answers WHERE question_id=? AND matrix_row_id=''", (PAY["qid"],))]
    pc_counts = [int(round(p * len(pc_orgs) / 100.0)) for p in PAY["pct_letter_conversation"]]

    n_expected = (n_before - sum(dk_del.values()) - 220  # PENLEAVEGAP
                  - len(pc_orgs) + len(pc_orgs) * 7)
    print("%s: DK deletes %s | paycomms %d orgs -> %d matrix rows (conv counts %s) | retire %s | answers %d -> %d"
          % ("APPLY" if a.write else "dry-run", dk_del, len(pc_orgs), len(pc_orgs) * 7, pc_counts, RETIRE, n_before, n_expected))
    for qid, p in plan.items():
        print("  %s: %s -> %s" % (qid, p["before"], p["after_counts"]))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    def snapshot(qid):
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                    (STAMP, qid))

    # ---------- A. option edits ----------
    for qid, e in CFG["option_edits"].items():
        row = c.execute("SELECT options_json, scoring_config_json FROM questions WHERE id=?", (qid,)).fetchone()
        opts = json.loads(row["options_json"])
        sc = json.loads(row["scoring_config_json"] or "{}")
        if e.get("replace_options"):
            opts = e["replace_options"]
            sc["option_scores"] = e["option_scores"]
            cur.execute("UPDATE questions SET question_version=? WHERE id=?", (e["version_bump"], qid))
        else:
            opts = [o for o in opts if o["code"] not in e["remove_codes"]]
            if sc.get("option_scores"):
                for k in e["remove_codes"]: sc["option_scores"].pop(k, None)
            if sc.get("na_codes") and e.get("remove_na_codes"):
                sc["na_codes"] = [k for k in sc["na_codes"] if k not in e["remove_na_codes"]]
        cur.execute("UPDATE questions SET options_json=? , scoring_config_json=? WHERE id=?",
                    (json.dumps(opts), json.dumps(sc), qid))
    # paycomms question surgery
    cur.execute("""UPDATE questions SET type='matrix', options_json=?, matrix_rows_json=?,
                   question_version=?, default_chart_type='bar' WHERE id=?""",
                (json.dumps(PAY["options"]), json.dumps(PAY["matrix_rows"]), PAY["version_bump"], PAY["qid"]))

    # ---------- B. answers ----------
    manifest = []
    for qid, labels in CFG["dk_answer_deletes"].items():
        snapshot(qid)
        cur.execute("DELETE FROM answers WHERE question_id=? AND value IN (%s)" % ",".join("?" * len(labels)),
                    [qid] + labels)
    for qid, p in plan.items():
        if qid not in CFG["dk_answer_deletes"]: snapshot(qid)
        order = p["order"] or list(p["after_counts"])
        ranked = ranked_orgs(c, qid, p["orgs"], p["ordered"])
        # generous pole last in `order`; hand the top of the ranked list the top rung
        newmap = {}
        i = 0
        for lbl in reversed(order):
            for _ in range(p["after_counts"].get(lbl, 0)):
                newmap[ranked[i]] = lbl; i += 1
        assert i == len(ranked), (qid, i, len(ranked))
        for org, lbl in newmap.items():
            cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=''",
                        (lbl, qid, org))
        manifest.append({"metric_id": qid, "action": "reshape",
                         "before": json.dumps(p["before"]), "after": json.dumps(p["after_counts"])})
    # paycomms rebuild
    snapshot(PAY["qid"])
    cur.execute("DELETE FROM answers WHERE question_id=?", (PAY["qid"],))
    ranked = sorted(pc_orgs, key=lambda o: (-latent(o, PROF), hashlib.sha256((PAY["qid"] + "|" + o).encode()).hexdigest()))
    conv_lbl = PAY["options"][0]["label"]; letter_lbl = PAY["options"][1]["label"]
    for li, slug in enumerate(PAY["row_slugs"]):
        k = pc_counts[li]
        for ri, org in enumerate(ranked):
            cur.execute("""INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at)
                           VALUES (?,?,?,?,?,?)""",
                        (org, 1, PAY["qid"], slug, conv_lbl if ri < k else letter_lbl, STAMP))
    manifest.append({"metric_id": PAY["qid"], "action": "matrix-rebuild",
                     "before": json.dumps({"single_select_answers": len(pc_orgs)}),
                     "after": json.dumps({"matrix_rows": len(pc_orgs) * 7, "conv_counts": pc_counts})})
    # ---------- C. retire ----------
    for qid in RETIRE:
        snapshot(qid)
        cur.execute("DELETE FROM answers WHERE question_id=?", (qid,))
        cur.execute("UPDATE questions SET status='retired', release_retired='2026.4' WHERE id=?", (qid,))
        cur.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (qid,))
        manifest.append({"metric_id": qid, "action": "retire", "before": "220 seed answers", "after": "0"})
    c.commit()

    # ---------- asserts ----------
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    n_after = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    assert n_after == n_expected, (n_after, n_expected)
    for qid, p in plan.items():
        got = dict(c.execute("SELECT value, COUNT(*) FROM answers WHERE question_id=? GROUP BY 1", (qid,)))
        assert got == p["after_counts"], (qid, got, p["after_counts"])
    for li, slug in enumerate(PAY["row_slugs"]):
        k = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND matrix_row_id=? AND value=?",
                      (PAY["qid"], slug, conv_lbl)).fetchone()[0]
        assert k == pc_counts[li], (slug, k, pc_counts[li])
    # nested depth: conversation set at each level must contain the next level's set
    prev = None
    for slug in PAY["row_slugs"]:
        s = {o for (o,) in c.execute("SELECT org_id FROM answers WHERE question_id=? AND matrix_row_id=? AND value=?",
                                     (PAY["qid"], slug, conv_lbl))}
        assert prev is None or s <= prev, "nesting broken at %s" % slug
        prev = s
    with open(os.path.join(ROOT, "diff15_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before", "after"])
        w.writeheader(); w.writerows(manifest)
    print(json.dumps({"applied": True, "answers_after": n_after,
                      "history_rows": c.execute("SELECT COUNT(*) FROM answers_history WHERE recorded_at=?", (STAMP,)).fetchone()[0],
                      "non_target_book": "hash-identical", "dists": "exact (asserted)",
                      "paycomms_nesting": "asserted", "manifest": "diff15_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
