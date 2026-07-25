# -*- coding: utf-8 -*-
"""migrate_batch5_hp.py — Round-2 batch-5: H&P, the FIRST DOWNWARD headline batch (David 2026-07-25,
"confirm all, i, target three / Batch-5 ships"). SEED-DATA class, three moves, one apply.

DOWNWARD DOCTRINE (same doctrine, opposite sign): approach the anchor FROM ABOVE, STOP SHORT — land
above the anchor, not on it.

  5.1 CASHPLAN ↓ (definition (i), any-provision): 84 -> TARGET_CP of 220 (weighted anchor 28.2%,
      grade A; stop-short ~1.10x -> 30.9%). Flips provision->'No', PROPORTIONAL across the three
      provision arms (preserves the funding mix — the mix has no anchor, so no mix-shift is invented).
      Draw pool CONSTRAINED to orgs holding a BEN_038 PMI tick, so PROP_11a83d52's "has a health plan"
      base stays true for every flipped org (its 'health plan' concept is broader than cash plans —
      199 substantive vs 84 cash-plan — but the constraint removes even the semantic risk).
  5.2 OPTICAL ↓: 168 -> TARGET_OPT of 220 (weighted 67.1%; stop-short ~1.05x -> 70.5%; the bound-honesty
      note — even the landed value may overstate — is recorded in DECISIONS). Flips Yes->'Statutory DSE only'.
  5.3 BEN_048 SHAPE (BEN_112 doctrine + the IP-pool HARD CONSTRAINT): bands 50-65/66-75/76+ move
      16/44/20 -> 32/32/16 (co-modal tie = grade-B short-landing toward the anchor's 50-59 most-common
      claim). Moves: 16x '66–75%'->'50–65%', 4x '76%+'->'66–75%'. VALUES ONLY — pool membership
      untouched; BEN_046 asserted byte-identical; 80=80 identity asserted.

Fixtures skipped in every pool (both sit inside pools — the skips are stated): Advisory in
CASHPLAN-voluntary + BEN_048-66-75; Retail in OPTICAL-Yes. Dry-run default; --write; live needs
--confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
CP, OPT, B48, B46, B38 = ("REW264_HLT_CASHPLAN", "REW264_HLT_OPTICAL", "REW_BEN_048", "REW_BEN_046", "REW_BEN_038")
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
TARGET_CP = 68     # any-provision 68/220 = 30.9% — stop-short above the 28.2% weighted anchor (~1.10x)
TARGET_OPT = 155   # Yes 155/220 = 70.5% — stop-short above 67.1% (~1.05x); bound-honesty recorded
B48_MOVES = (16, 4)  # 16x 66-75 -> 50-65 ; 4x 76+ -> 66-75  => bands 32/32/16 (co-modal short-landing)
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
STAMP = "2026-07-25 batch5-hp"


def h(tag, org):
    return hashlib.sha256(("b5::%s::%s" % (tag, org)).encode()).hexdigest()


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
    assert not (FROZEN8 & {CP, OPT, B48}), "frozen-8 grazed"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    g = lambda q: {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,))}
    cp, opt, b48, b46 = g(CP), g(OPT), g(B48), g(B46)
    pmi = {o for o, v in g(B38).items() if "Private Medical Insurance" in v or "PMI" in v}

    # ---- 5.1 CASHPLAN: proportional flips, PMI-constrained, fixtures skipped ----
    arms = {"Employer-paid all": [], "Employer-paid some": [], "Voluntary only": []}
    for o, v in cp.items():
        if v in arms and o not in FIX and o in pmi:
            arms[v].append(o)
    prov_now = sum(1 for v in cp.values() if v != "No")
    cp_k = prov_now - TARGET_CP
    sizes = {k: len([o for o, v in cp.items() if v == k]) for k in arms}
    quota = {k: int(round(cp_k * sizes[k] / prov_now)) for k in arms}
    while sum(quota.values()) < cp_k: quota[max(arms, key=lambda k: sizes[k])] += 1
    while sum(quota.values()) > cp_k: quota[min((k for k in arms if quota[k] > 0), key=lambda k: sizes[k])] -= 1
    cp_take = []
    for k in arms:
        pool = sorted(arms[k], key=lambda o: h("cp", o))
        assert quota[k] <= len(pool), "CASHPLAN %s pool short (PMI-constrained): need %d have %d" % (k, quota[k], len(pool))
        cp_take += [(o, k) for o in pool[:quota[k]]]

    # ---- 5.2 OPTICAL ----
    opt_pool = sorted((o for o, v in opt.items() if v == "Yes" and o not in FIX), key=lambda o: h("opt", o))
    opt_k = sum(1 for v in opt.values() if v == "Yes") - TARGET_OPT
    assert 0 <= opt_k <= len(opt_pool), "OPTICAL pool short"
    opt_take = opt_pool[:opt_k]

    # ---- 5.3 BEN_048 shape ----
    m1, m2 = B48_MOVES
    p6675 = sorted((o for o, v in b48.items() if v == "66–75%" and o not in FIX), key=lambda o: h("b48a", o))
    p76 = sorted((o for o, v in b48.items() if v == "76%+" and o not in FIX), key=lambda o: h("b48b", o))
    assert m1 <= len(p6675) and m2 <= len(p76), "BEN_048 pools short"
    b48_take = [(o, "50–65%") for o in p6675[:m1]] + [(o, "66–75%") for o in p76[:m2]]

    print("batch-5 %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  5.1 CASHPLAN: any-provision %d -> %d (%.1f%% -> %.1f%%; weighted anchor 28.2%%) | flips %s (PMI-constrained; Advisory skipped)"
          % (prov_now, TARGET_CP, 100 * prov_now / 220, 100 * TARGET_CP / 220, quota))
    print("  5.2 OPTICAL: Yes %d -> %d (%.1f%% -> %.1f%%; weighted 67.1%%; bound-honesty noted) | Retail skipped"
          % (prov_now2 := sum(1 for v in opt.values() if v == "Yes"), TARGET_OPT, 100 * prov_now2 / 220, 100 * TARGET_OPT / 220))
    b = Counter(b48.values())
    print("  5.3 BEN_048 bands: 50-65 %d / 66-75 %d / 76+ %d -> 32/32/16 (co-modal short-landing; Advisory skipped)"
          % (b.get("50–65%", 0), b.get("66–75%", 0), b.get("76%+", 0)))
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_book = book_excl(c, [CP, OPT, B48])
    pre_b46 = sorted(b46.items())
    fixpre = {(q, o): (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0]
              for q in (CP, OPT, B48, B46) for o in FIX}
    npre = {q: c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] for q in (CP, OPT, B48)}
    cur = c.cursor()
    for o, arm in cp_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " cashplan", CP, o))
        cur.execute("UPDATE answers SET value='No' WHERE question_id=? AND org_id=?", (CP, o))
    for o in opt_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " optical", OPT, o))
        cur.execute("UPDATE answers SET value='Statutory DSE only' WHERE question_id=? AND org_id=?", (OPT, o))
    for o, nv in b48_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " b48 shape", B48, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (nv, B48, o))

    # ---- asserts before commit ----
    assert book_excl(c, [CP, OPT, B48]) == pre_book, "NON-BATCH ANSWERS CHANGED"
    assert sorted(g(B46).items()) == pre_b46, "BEN_046 PARENT MOVED — the pool constraint is absolute"
    for q in (CP, OPT, B48):
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] == npre[q], "n changed on %s" % q
    for (q, o), v in fixpre.items():
        assert (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0] == v, "FIXTURE MOVED %s/%s" % (q, o)
    cp2, opt2, b482 = g(CP), g(OPT), g(B48)
    prov2 = sum(1 for v in cp2.values() if v != "No")
    yes2 = sum(1 for v in opt2.values() if v == "Yes")
    b2 = Counter(b482.values())
    assert prov2 == TARGET_CP and yes2 == TARGET_OPT, (prov2, yes2)
    assert b2.get("50–65%") == 32 and b2.get("66–75%") == 32 and b2.get("76%+") == 16, dict(b2)
    ip_pool = {o for o, v in b482.items() if not str(v).startswith("Not applicable")}
    b46_ip = {o for o, v in g(B46).items() if v != "No"}
    assert len(ip_pool) == 80 and ip_pool == b46_ip, "80=80 pool identity broken"
    # direction sign checks: all three moved DOWN toward their anchors from above
    assert prov2 < prov_now and yes2 < 168 and b2.get("66–75%") < 44, "direction sign check failed"
    empii = sum(1 for v in cp2.values() if v in ("Employer-paid all", "Employer-paid some"))
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "cp_flips": len(cp_take), "opt_flips": len(opt_take),
                      "b48_moves": len(b48_take), "cp_def_ii_after": "%d/220=%.1f%%" % (empii, 100 * empii / 220),
                      "pool_80_identity": "held", "ben046": "byte-identical", "fixtures": "byte-held",
                      "non_batch_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
