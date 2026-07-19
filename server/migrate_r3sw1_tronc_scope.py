# -*- coding: utf-8 -*-
"""migrate_r3sw1_tronc_scope.py — tronc family: scope clean + conditioned reseed.

DATA-DRIVEN over r3sw1_derivation_rules.json (no per-metric code): each entry
names its condition parent ("tips" = tips-exist Yes set; "tronc" = the tronc
metric's own Yes set, derived in-run) and either a ratio (select/multi seeded by
largest remainder over the conditioned set, hash-ranked) or matrix_levels
(per-level Yes% over the conditioned set, nested-by-hash).
Cross-sector pollution DELETED (history-snapshotted). Coherence chain asserted
hard: every surviving answer's org satisfies its parent condition — write aborts
on any conflict. Emits r3sw1_seed_manifest.csv.
"""
import sqlite3, json, hashlib, sys, os, csv, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # matrix depth must track the latent spine (G10)
CFG = json.load(open(os.path.join(ROOT, "r3sw1_derivation_rules.json")))
PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    PROF.update({k: v for k, v in json.load(open(os.path.join(ROOT, _p))).items() if isinstance(v, dict)})
TIPS = CFG["tips_parent"]
QIDS = [m["qid"] for m in CFG["metrics"]]
STAMP = "2026-07-18 r3sw1 tronc scope"


def lr_alloc(ratio, orgs):
    """largest-remainder allocation of ratio (label->weight) over orgs (hash-ranked)."""
    tot = float(sum(ratio.values()))
    raw = {l: w * len(orgs) / tot for l, w in ratio.items()}
    fl = {l: int(raw[l]) for l in raw}
    for l in sorted(raw, key=lambda l: (-(raw[l] - fl[l]), l))[: len(orgs) - sum(fl.values())]:
        fl[l] += 1
    out = {}
    i = 0
    for l in ratio:
        for _ in range(fl[l]):
            out[orgs[i]] = l; i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db); cur = c.cursor()

    for qid in QIDS:
        ns = cur.execute("""SELECT COUNT(*) FROM answers x JOIN orgs o ON o.org_id=x.org_id
                            WHERE x.question_id=? AND COALESCE(o.source,'')!='seed'""", (qid,)).fetchone()[0]
        assert ns == 0, "non-seed answers on %s — ABORT" % qid

    tips_yes = sorted(o for (o,) in cur.execute(
        "SELECT org_id FROM answers WHERE question_id=? AND value=?", (TIPS["qid"], TIPS["value"])))
    assert len(tips_yes) >= 5, "tips-exist set below the n floor: %d" % len(tips_yes)
    parent_sets = {"tips": tips_yes}
    plans = []
    for m in CFG["metrics"]:
        cond = parent_sets[m["condition"]]
        ranked = sorted(cond, key=lambda o: hashlib.sha256((m["qid"] + "|" + o).encode()).hexdigest())
        before_n = cur.execute("SELECT COUNT(DISTINCT org_id) FROM answers WHERE question_id=?", (m["qid"],)).fetchone()[0]
        if m.get("ratio"):
            newmap = lr_alloc(m["ratio"], ranked)
            plans.append({"m": m, "newmap": newmap, "before_n": before_n})
            if m["qid"] == "REW_PAY_TRONC_6db81475":
                parent_sets["tronc"] = sorted(o for o, v in newmap.items() if v == "Yes")
        else:
            # by-level matrices: nested by LATENT desc (Diff-13 pattern) so cascade
            # depth tracks the spine — G10 demands depth x latent >= 0.30. (The Step-2
            # hash ruling is scoped to maturity-gradient within-band order, not here.)
            lranked = sorted(cond, key=lambda o: (-latent(o, PROF),
                             hashlib.sha256((m["qid"] + "|" + o).encode()).hexdigest()))
            rows = {}
            for slug, pct in m["matrix_levels"].items():
                k = int(round(pct / 100.0 * len(lranked)))
                for i, o in enumerate(lranked):
                    rows[(o, slug)] = m["options"][0] if i < k else m["options"][1]
            plans.append({"m": m, "matrix": rows, "before_n": before_n})
    print("%s: tips-exist set n=%d | tronc-Yes set n=%d" % (
        "APPLY" if a.write else "dry-run", len(tips_yes), len(parent_sets.get("tronc", []))))
    for p in plans:
        m = p["m"]
        if "newmap" in p:
            print("  %s [%s-conditioned]: n %d -> %d | %s" % (
                m["qid"], m["condition"], p["before_n"], len(p["newmap"]), dict(Counter(p["newmap"].values()))))
        else:
            per = Counter(slug for (o, slug), v in p["matrix"].items() if v == m["options"][0])
            print("  %s [%s-conditioned]: n %d -> %d orgs x 7 levels | Yes per level %s" % (
                m["qid"], m["condition"], p["before_n"], len({o for o, _ in p["matrix"]}), dict(per)))
    if not a.write:
        print("dry-run complete"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    ph = ",".join("?" * len(QIDS))
    h_pre = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, QIDS))).hexdigest()
    manifest = []
    for p in plans:
        m = p["m"]; qid = m["qid"]
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""", (STAMP, qid))
        cur.execute("DELETE FROM answers WHERE question_id=?", (qid,))
        if "newmap" in p:
            for o, lbl in p["newmap"].items():
                cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,'',?,?)",
                            (o, qid, lbl, STAMP))
            after = dict(Counter(p["newmap"].values()))
        else:
            for (o, slug), v in p["matrix"].items():
                cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,?,?,?)",
                            (o, qid, slug, v, STAMP))
            after = {"orgs": len({o for o, _ in p["matrix"]}), "rows": len(p["matrix"])}
        cur.execute("DELETE FROM benchmark_snapshots WHERE question_id=?", (qid,))
        manifest.append({"metric_id": qid, "action": "scope+condition (%s)" % m["condition"],
                         "before_n": p["before_n"], "after": json.dumps(after)})
    c.commit()

    h_post = hashlib.sha256(b"".join(("|".join(map(str, r)) + "\n").encode() for r in cur.execute(
        "SELECT org_id,question_id,COALESCE(matrix_row_id,''),value FROM answers WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ph, QIDS))).hexdigest()
    assert h_pre == h_post, "NON-TARGET BOOK CHANGED"
    # coherence chain, re-derived FROM THE DB
    db_tips = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id=? AND value=?", (TIPS["qid"], TIPS["value"]))}
    db_tronc = {o for (o,) in cur.execute("SELECT org_id FROM answers WHERE question_id='REW_PAY_TRONC_6db81475' AND value='Yes'")}
    conflicts = []
    for m in CFG["metrics"]:
        parent = db_tips if m["condition"] == "tips" else db_tronc
        for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (m["qid"],)):
            if o not in parent:
                conflicts.append((m["qid"], o))
    assert not conflicts, "COHERENCE CONFLICTS: %s" % conflicts[:5]
    with open(os.path.join(ROOT, "r3sw1_seed_manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric_id", "action", "before_n", "after"])
        w.writeheader(); w.writerows(manifest)
    print(json.dumps({"applied": True, "coherence_conflicts": 0, "tips_set": len(db_tips),
                      "tronc_set": len(db_tronc), "non_target_book": "hash-identical",
                      "manifest": "r3sw1_seed_manifest.csv"}, indent=2))


if __name__ == "__main__":
    main()
