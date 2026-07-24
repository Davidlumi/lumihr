# -*- coding: utf-8 -*-
"""migrate_batch2_wellbeing.py — Round-2 batch-2: Wellbeing reshape (David 2026-07-24, "A, target,
unfreeze"). SEED-DATA class ONLY — three metrics' answers, nothing else. frozen_targets.json is
handled OUTSIDE this script (unfreeze before rehearsal, re-freeze at close-out; separate commit).

  FINWELL263 (REW263_WEL_FINWELL, up): promote Ad-hoc->Documented until Documented = TARGET_FIN
    (under-peak vs the 15% grade-A anchor). Pool: Ad hoc, non-fixture, FINWELL26=Yes (all are).
    Ad-hoc-only promotion keeps the beyond-No share at 15.0% (gm marginal + modal untouched).
  WEL_BUDGET (REW26_WEL_BUDGET, up): promote large-org zero/N-A -> positive until large positives =
    TARGET_BUD (under-peak vs the 54% grade-B large-only anchor). Values sampled DETERMINISTICALLY
    from the observed large-org positive values (shape-preserving). SME + unclassified UNTOUCHED.
  SALSAC (REW26_BEN_SALSAC, down): flip large Yes->No until large Yes = TARGET_SAL (approach the 54%
    large "offer" anchor from above, stop short — live measures "by default" ⊆ offer, so the
    over-statement is >= +15.5pp). Flips drawn FIRST from the pre-existing SALSAC=Yes ∧
    NICSHARING='No sal-sac scheme' contradiction class (repairs bank incoherence as a side effect;
    SALSAC=No is compatible with every NIC value, so flips can never CREATE a contradiction).

Fixtures EXCLUDED from all draws (answers byte-held): Thornbridge Retail 5e67fa8c…, Advisory 833beedb….
Dry-run default; --write; live needs --confirmed-by-david (r3sw7 double-guard).
"""
import argparse, hashlib, json, os, re, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
FIN, BUD, SAL, NIC, FW26 = ("REW263_WEL_FINWELL", "REW26_WEL_BUDGET", "REW26_BEN_SALSAC",
                            "REW264_PEN_NICSHARING", "REW26_WEL_FINWELL")
TARGET_FIN = 30    # Documented 30/220 = 13.6% — under-peak of the 15% anchor (~91%)
TARGET_BUD = 66    # large positives 66/128 = 51.6% — under-peak of 54% large (grade B -> land shorter)
TARGET_SAL = 73    # large Yes 73/128 = 57.0% — approach 54% from above, stop short
STAMP = "2026-07-24 batch2-wellbeing"


def h(tag, org):
    return hashlib.sha256(("b2::%s::%s" % (tag, org)).encode()).hexdigest()


def book_excl(c, excl):
    hh = hashlib.sha256()
    q = ("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers "
         "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(excl)))
    for r in c.execute(q, excl):
        hh.update(("|".join(str(x) for x in r)).encode())
    return hh.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    # the freeze must be suspended before any SALSAC reshape (order asserted here)
    ft = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    assert SAL not in ft, "SALSAC still frozen — run the unfreeze edit first (no reshape under an armed gate)"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row

    def islarge(o):
        b = c.execute("SELECT fte_band FROM orgs WHERE org_id=?", (o,)).fetchone()[0]
        m = re.match(r"(\d[\d,]*)", (b or "").replace(",", ""))
        return bool(m) and int(m.group(1)) >= 250

    def posval(v):
        s = re.sub(r"[^\d.]", "", str(v)); return float(s) if s else 0.0

    # ---- current state + draws (all derived live) ----
    fin = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (FIN,))}
    fw = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (FW26,))}
    bud = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (BUD,))}
    sal = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (SAL,))}
    nic = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (NIC,))}

    fin_doc = sum(1 for v in fin.values() if v == "Documented strategy")
    fin_pool = sorted((o for o, v in fin.items() if v == "Ad hoc provision" and o not in FIX
                       and str(fw.get(o, "")).startswith("Yes")), key=lambda o: h("fin", o))
    fin_k = TARGET_FIN - fin_doc
    assert 0 <= fin_k <= len(fin_pool), "FIN pool short: need %d, have %d" % (fin_k, len(fin_pool))
    fin_take = fin_pool[:fin_k]

    bud_large_pos = sorted(posval(v) for o, v in bud.items() if islarge(o) and posval(v) > 0)
    bud_pool = sorted((o for o, v in bud.items() if islarge(o) and posval(v) == 0 and o not in FIX),
                      key=lambda o: h("bud", o))
    bud_k = TARGET_BUD - len(bud_large_pos)
    assert 0 <= bud_k <= len(bud_pool), "BUD pool short"
    bud_take = bud_pool[:bud_k]
    bud_vals = {o: bud_large_pos[int(h("budval", o)[:8], 16) % len(bud_large_pos)] for o in bud_take}

    sal_large_yes = [o for o, v in sal.items() if v == "Yes" and islarge(o)]
    contra_large = set(o for o in sal_large_yes if nic.get(o) == "No sal-sac scheme" and o not in FIX)
    sal_pool = sorted((o for o in sal_large_yes if o not in FIX),
                      key=lambda o: (o not in contra_large, h("sal", o)))   # contradiction class FIRST
    sal_k = len(sal_large_yes) - TARGET_SAL
    assert 0 <= sal_k <= len(sal_pool), "SAL pool short"
    sal_take = sal_pool[:sal_k]
    contra_before = sum(1 for o in sal if sal[o] == "Yes" and nic.get(o) == "No sal-sac scheme")

    n220 = {q: c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0]
            for q in (FIN, BUD, SAL)}
    print("batch-2 %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  FIN: Documented %d -> %d (+%d from Ad hoc, all FINWELL26=Yes) = %.1f%% (anchor 15%%)"
          % (fin_doc, TARGET_FIN, fin_k, 100 * TARGET_FIN / n220[FIN]))
    print("  BUD: large positives %d -> %d (+%d of %d pool) = %.1f%% large (anchor 54%%)"
          % (len(bud_large_pos), TARGET_BUD, bud_k, len(bud_pool), 100 * TARGET_BUD / 128))
    print("  SAL: large Yes %d -> %d (-%d; %d drawn from the %d-strong large contradiction class) = %.1f%% large (anchor 54%% 'offer')"
          % (len(sal_large_yes), TARGET_SAL, sal_k, len(set(sal_take) & contra_large), len(contra_large), 100 * TARGET_SAL / 128))
    print("  SAL all-cohort headline: %.1f%% -> %.1f%% | SALSACxNIC contradictions %d -> %d"
          % (100 * sum(1 for v in sal.values() if v == "Yes") / n220[SAL],
             100 * (sum(1 for v in sal.values() if v == "Yes") - sal_k) / n220[SAL],
             contra_before, contra_before - len(set(sal_take) & contra_large)))
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_book = book_excl(c, [FIN, BUD, SAL])
    fixpre = {(q, o): c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone()
              for q in (FIN, BUD, SAL) for o in FIX}
    cur = c.cursor()
    for q, orgs, val in ((FIN, fin_take, lambda o: "Documented strategy"),
                         (BUD, bud_take, lambda o: str(bud_vals[o])),
                         (SAL, sal_take, lambda o: "No")):
        for o in orgs:
            cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                        "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                        (STAMP + " pre-reshape", q, o))
            cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (val(o), q, o))

    # ---- asserts (before commit) ----
    assert book_excl(c, [FIN, BUD, SAL]) == pre_book, "NON-BATCH ANSWERS CHANGED"
    for q in (FIN, BUD, SAL):
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] == n220[q], "n changed on %s" % q
    for (q, o), v in fixpre.items():
        assert c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() == v, "FIXTURE MOVED: %s/%s" % (q, o)
    fin2 = sum(1 for (v,) in c.execute("SELECT value FROM answers WHERE question_id=?", (FIN,)) if v == "Documented strategy")
    sal2y = [r["org_id"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value='Yes'", (SAL,))]
    bud2 = sum(1 for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=?", (BUD,)) if islarge(r["org_id"]) and posval(r["value"]) > 0)
    assert fin2 == TARGET_FIN and bud2 == TARGET_BUD and sum(1 for o in sal2y if islarge(o)) == TARGET_SAL, (fin2, bud2, len(sal2y))
    # direction signs: FIN up, BUD up, SAL down (asserted by construction of the takes)
    nic2 = dict(nic)
    contra_after = sum(1 for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND value='Yes'", (SAL,))
                       if nic2.get(r["org_id"]) == "No sal-sac scheme")
    assert contra_after <= contra_before, "coherence worsened"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "fin_promoted": fin_k, "bud_promoted": bud_k,
                      "sal_flipped": sal_k, "contra_before": contra_before, "contra_after": contra_after,
                      "fixtures": "byte-held", "non_batch_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
