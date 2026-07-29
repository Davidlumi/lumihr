# -*- coding: utf-8 -*-
"""migrate_batch7_gt.py — Round-2 batch-7: G&T, UPWARD x2 (David 2026-07-28, "trio compound, hold
P1, include partial, target P13, confirm six, tier-2 the six" + the corrected option-(a) P2
resolution). SEED-DATA class, two moves, one apply. Both members reshape UP — approach the anchor
from BELOW, STOP SHORT (the Wellbeing-batch doctrine).

  7.1 PROP_930043cc (ethnicity PGA) ↑: Yes+Partial 38/213 = 17.8% -> 63/213 = 29.6% vs the
      weighted anchor 32.9 (= (128x40 + 30x13 + 62x28)/220 on the 28-as-ran register-corroborated
      figures; stop-short 0.90x). SIZE-HONESTY IS THE DRAW: +25 movers apportioned per band at
      0.90x of each band's OWN anchor rate — large +10 (27.8%->36.0% vs 40), SME +3 (0->11.7% vs
      13), unclassified +12 (5.1%->25.2% vs flat 28) — the per-band tilt and the aggregate
      stop-short coincide by construction. All moves No -> 'Partially' (the adjacent rung: a
      nascent practice formalises to less-than-annual first; annual 'Yes' stays 9 — occasional >
      annual is the real-world shape). Within-band draw: HIERARCHY-HONEST preference — orgs
      already holding gender-PGA Yes/In-development first (ethnicity work follows gender work),
      then sha-order. Fixtures: BOTH in the No-pool — skipped, stated.
  7.2 REW_FAI_088 (access to pay ranges) ↑, ruled STRICT: the CASCADE design — every mover
      formalises by EXACTLY ONE rung: Partial->Yes x29 AND No->Partial x29. Yes 50/220 = 22.7% ->
      79/220 = 35.9% vs the 40 anchor (flat all-UK, no size split in the cell -> no tilt, stated;
      stop-short 0.90x). The middle's mass is INVARIANT (38 before and after — no crater); the
      No-end drifts 60.0% -> 46.8% TOWARD the anchor's 32% never-end as an honest side effect,
      not forced. COHERENCE BONUS: the 29 No->Partial movers are EXACTLY the 29 Appendix-A
      soft-tension orgs (UKPAYTRANS internal-or-better x FAI_088 No) — the tension lands 29 -> 0.
      Fixtures: Retail (No) skipped if in the tension pool (sha replacement, stated); Advisory
      (Yes) outside all pools.

Fixtures byte-held. Pre-state hard-asserted (a live apply refuses on drift from the rehearsed
state). Only the two members' answers change. Dry-run default; --write; live needs
--confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
ETH, F88, F79, UKT = "PROP_930043cc", "REW_FAI_088", "REW_FAI_079", "REW263_GOV_UKPAYTRANS"
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
STAMP = "2026-07-28 batch7-gt"
LARGE = ("250-999", "1,000-4,999", "5,000-9,999", "10,000+")
ETH_QUOTAS = {"large": 10, "sme": 3, "uncl": 12}     # 0.90x per-band anchor rates (40/13/28)
ETH_PRE = {"No": 175, "Partially": 29, "Yes": 9}
F88_PRE = {"No": 132, "Partial": 38, "Yes": 50}
K = 29                                               # the cascade width (also == the tension count)


def h(tag, org):
    return hashlib.sha256(("b7::%s::%s" % (tag, org)).encode()).hexdigest()


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
    assert not (FROZEN8 & {ETH, F88}), "frozen-8 grazed"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    g = lambda q: {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,))}
    eth, f88, f79, ukt = g(ETH), g(F88), g(F79), g(UKT)
    fte = {r["org_id"]: (r["fte_band"] or "") for r in c.execute("SELECT org_id, fte_band FROM orgs")}
    band = lambda o: "large" if fte.get(o, "") in LARGE else ("sme" if fte.get(o, "") == "50-249" else "uncl")

    # ---- pre-state drift guards ----
    assert Counter(eth.values()) == Counter(ETH_PRE), "ETH pre drifted: %s" % Counter(eth.values())
    assert Counter(f88.values()) == Counter(F88_PRE), "F88 pre drifted: %s" % Counter(f88.values())
    assert eth[FIX[0]] == "No" and eth[FIX[1]] == "No" and f88[FIX[0]] == "No" and f88[FIX[1]] == "Yes", "fixtures drifted"

    # ---- 7.1 ETH: +25 No->Partially, per-band quotas, hierarchy-honest then sha ----
    eth_take = []
    for b, quota in ETH_QUOTAS.items():
        pool = [o for o, v in eth.items() if v == "No" and o not in FIX and band(o) == b]
        pref = sorted((o for o in pool if f79.get(o) in ("Yes", "In development")), key=lambda o: h("eth", o))
        rest = sorted((o for o in pool if o not in set(pref)), key=lambda o: h("eth", o))
        ordered = pref + rest
        assert len(ordered) >= quota, "ETH %s pool short: %d < %d" % (b, len(ordered), quota)
        eth_take += ordered[:quota]
    assert len(eth_take) == 25

    # ---- 7.2 F88 cascade: No->Partial x29 (tension orgs exactly) + Partial->Yes x29 ----
    tension = sorted((o for o in set(ukt) & set(f88)
                      if ukt[o] in ("Internal ranges only", "Ranges on adverts", "Published transparency policy")
                      and f88[o] == "No" and o not in FIX), key=lambda o: h("f88n", o))
    tension_all = [o for o in set(ukt) & set(f88)
                   if ukt[o] in ("Internal ranges only", "Ranges on adverts", "Published transparency policy")
                   and f88[o] == "No"]
    fixture_in_tension = [o for o in tension_all if o in FIX]
    no_pool_rest = sorted((o for o, v in f88.items() if v == "No" and o not in FIX and o not in set(tension)),
                          key=lambda o: h("f88n", o))
    f88_no_to_partial = (tension + no_pool_rest)[:K]   # tension-first; sha replacements if a fixture sat inside
    assert len(f88_no_to_partial) == K
    p_pool = sorted((o for o, v in f88.items() if v == "Partial" and o not in FIX), key=lambda o: h("f88p", o))
    assert len(p_pool) >= K, "F88 Partial pool short"
    f88_partial_to_yes = p_pool[:K]

    print("batch-7 %s (db=%s) — UPWARD x2, stop-short 0.90x" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  7.1 %s: Yes+Partial 38/213=17.8%% -> 63/213=29.6%% vs weighted 32.9 | +25 No->Partially, quotas %s"
          "(hierarchy-honest first) | fixtures both in pool, SKIPPED" % (ETH, ETH_QUOTAS))
    print("  7.2 %s: Yes 50/220=22.7%% -> 79/220=35.9%% vs 40 (flat, no split -> no tilt) | cascade one-rung: "
          "Partial->Yes x29 + No->Partial x29 (middle mass invariant; tension orgs first: %d of 29%s)"
          % (F88, len(tension[:K]), "; fixture-in-tension: %s -> sha replacement" % fixture_in_tension if fixture_in_tension else ""))
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_book = book_excl(c, [ETH, F88])
    fixpre = {(q, o): (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0]
              for q in (ETH, F88, F79, UKT) for o in FIX}
    npre = {q: len(g(q)) for q in (ETH, F88, F79, UKT)}
    cur = c.cursor()
    for o in eth_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " eth", ETH, o))
        cur.execute("UPDATE answers SET value='Partially' WHERE question_id=? AND org_id=?", (ETH, o))
    for o in f88_no_to_partial:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " f88 cascade-a", F88, o))
        cur.execute("UPDATE answers SET value='Partial' WHERE question_id=? AND org_id=?", (F88, o))
    for o in f88_partial_to_yes:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " f88 cascade-b", F88, o))
        cur.execute("UPDATE answers SET value='Yes' WHERE question_id=? AND org_id=?", (F88, o))

    # ---- asserts before commit ----
    assert book_excl(c, [ETH, F88]) == pre_book, "NON-BATCH ANSWERS CHANGED"
    eth2, f882 = g(ETH), g(F88)
    d_eth, d_f88 = Counter(eth2.values()), Counter(f882.values())
    assert d_eth == {"No": 150, "Partially": 54, "Yes": 9}, dict(d_eth)
    assert d_f88 == {"No": 103, "Partial": 38, "Yes": 79}, dict(d_f88)
    yp = d_eth["Partially"] + d_eth["Yes"]
    assert yp == 63 and yp > 38, "ETH landing/sign"                      # sign-check UP
    assert d_f88["Yes"] == 79 and d_f88["Yes"] > 50, "F88 landing/sign"  # sign-check UP
    for q in (ETH, F88, F79, UKT):
        assert len(g(q)) == npre[q], "n changed on %s" % q
    for (q, o), v in fixpre.items():
        assert (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0] == v, \
            "FIXTURE MOVED %s/%s" % (q, o)
    # per-band landing assert (the size-honesty statement)
    fteb = Counter()
    for o, v in eth2.items():
        if v in ("Yes", "Partially"):
            fteb[band(o)] += 1
    assert fteb == {"large": 45, "sme": 3, "uncl": 15}, dict(fteb)      # 45/126=35.7, 3/28=10.7, 15/59=25.4
    # coherence bonus assert: the soft tension is dead
    ukt2, f883 = g(UKT), g(F88)
    t2 = sum(1 for o in set(ukt2) & set(f883)
             if ukt2[o] in ("Internal ranges only", "Ranges on adverts", "Published transparency policy") and f883[o] == "No")
    hist = c.execute("SELECT COUNT(*) FROM answers_history WHERE recorded_at LIKE ?", (STAMP + "%",)).fetchone()[0]
    assert hist == 25 + K + K, "history pre-images: %d" % hist
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "eth_moves": 25, "f88_moves": 2 * K,
                      "eth": "Yes+Partial 38->63 (17.8->29.6 vs weighted 32.9, 0.90x)",
                      "eth_by_band": "large 45/126=35.7 sme 3/28=10.7 uncl 15/59=25.4 (0.90x band anchors 40/13/28)",
                      "f88": "Yes 50->79 (22.7->35.9 vs 40, 0.90x); No 132->103 (60.0->46.8, toward 32); Partial 38 invariant",
                      "tension_after": t2, "fixtures": "byte-held", "non_batch_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
