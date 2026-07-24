# -*- coding: utf-8 -*-
"""migrate_batch3.py — Round-2 batch-3 (David 2026-07-24, "confirm all, b via batch-3, A-then-B").
SEED-DATA class, three moves, one apply:

  1.1 GAP_012 headline reshape: promote "Yes – occasionally" -> "Yes – at least annually" until
      annually = TARGET_GAP (under-peak vs the 26% grade-A anchor). Occasionally-only pool keeps
      any-Yes at 26.0% (gm marginal + modal untouched — the FINWELL263/Ad-hoc-first trick).
  1.2 BEN_112 SHAPE reshape (new class): tail-fattening by WHOLE-GRID UNIFORM UPLIFT. Design note:
      single-cell frontline promotion is IMPOSSIBLE without inversions (the inversion-safe pool is 0 —
      every in-band org has a non-frontline level below 7), so a promoted org's ENTIRE level grid
      shifts by delta = new_frontline - old_frontline. Preserves internal differentials exactly ->
      no inversion can be introduced (asserted). Target: frontline in-band 3-6 falls 96.8% -> 80.0%
      (Aon spread 68%; grade-B caution -> land well short of full fit). New frontline drawn from
      {7,8} by stable hash (7 weighted 3:1 — the observed up-tail is 7s). Implausibility cap:
      orgs whose max level would exceed 25 after the shift are excluded from the pool (reported).
  1.3 Residual-26 NIC repair (ruled coherence side-scope): SALSAC=Yes ∧ NIC='No sal-sac scheme' ->
      NIC='No'. Class count ASSERTED pre-apply: exactly 26 = 22 unclassified + 4 SME + 0 large.

Fixtures (5e67fa8c…, 833beedb…) excluded from every draw, answers byte-held (asserted). Only the
three questions' answers may change (book-hash on the rest). SALSAC untouched by construction (its
fresh freeze cannot be grazed). Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, re, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
GAP, B112, NIC, SAL = "EXT_REW_GAP_012", "REW_BEN_112", "REW264_PEN_NICSHARING", "REW26_BEN_SALSAC"
TARGET_GAP = 40      # annually 40/173 = 23.1% — under-peak of the 26% anchor (~89%)
TARGET_B112_INBAND = 176   # frontline 3-6: 213 -> 176 of 220 = 80.0% (Aon 68%; grade-B short-landing)
GRID_CAP = 25.0      # implausibility cap on any post-shift level cell
STAMP = "2026-07-24 batch3"
FRONT = "frontline_individual_contributor"


def h(tag, org):
    return hashlib.sha256(("b3::%s::%s" % (tag, org)).encode()).hexdigest()


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
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row

    def sz(o):
        b = c.execute("SELECT fte_band FROM orgs WHERE org_id=?", (o,)).fetchone()[0]
        if not b: return "unclassified"
        m = re.match(r"(\d[\d,]*)", b.replace(",", ""))
        return "large" if (m and int(m.group(1)) >= 250) else "sme"

    # ---- 1.1 GAP_012 ----
    g = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (GAP,))}
    ann = sum(1 for v in g.values() if v == "Yes – at least annually")
    gap_pool = sorted((o for o, v in g.items() if v == "Yes – occasionally" and o not in FIX), key=lambda o: h("gap", o))
    gap_k = TARGET_GAP - ann
    assert 0 <= gap_k <= len(gap_pool), "GAP pool short: need %d have %d" % (gap_k, len(gap_pool))
    gap_take = gap_pool[:gap_k]

    # ---- 1.2 BEN_112 shape ----
    grids = {}
    for r in c.execute("SELECT org_id,COALESCE(matrix_row_id,'') rk,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (B112,)):
        try: grids.setdefault(r["org_id"], {})[r["rk"]] = float(r["value"])
        except ValueError: pass
    inband = [o for o, v in grids.items() if v.get(FRONT) is not None and 3 <= v[FRONT] <= 6]
    n112 = len(grids)
    b112_k = len(inband) - TARGET_B112_INBAND
    def newfront(o):
        return 7.0 if int(h("b112f", o)[:8], 16) % 4 else 8.0     # 7 weighted 3:1
    pool = []
    capped = 0
    for o in sorted(inband, key=lambda o: h("b112", o)):
        if o in FIX: continue
        delta = newfront(o) - grids[o][FRONT]
        if max(grids[o].values()) + delta > GRID_CAP:
            capped += 1; continue
        pool.append(o)
    assert b112_k <= len(pool), "B112 pool short after cap: need %d have %d (capped %d)" % (b112_k, len(pool), capped)
    b112_take = pool[:b112_k]

    # ---- 1.3 NIC repair (class asserted) ----
    sal = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (SAL,))}
    nic = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (NIC,))}
    contra = sorted(o for o in sal if sal[o] == "Yes" and nic.get(o) == "No sal-sac scheme")
    cls = Counter(sz(o) for o in contra)
    assert len(contra) == 26 and cls.get("unclassified") == 22 and cls.get("sme") == 4 and cls.get("large", 0) == 0, \
        "26-CLASS ASSERT FAILED: %d %s" % (len(contra), dict(cls))
    assert not (set(contra) & set(FIX)), "fixture in the 26-class"

    print("batch-3 %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  1.1 GAP_012: annually %d -> %d (+%d from occasionally-only; any-Yes held 26.0%%) = %.1f%% (anchor 26%%)"
          % (ann, TARGET_GAP, gap_k, 100 * TARGET_GAP / len(g)))
    print("  1.2 BEN_112: in-band %d -> %d of %d (%.1f%% -> %.1f%%; Aon 68%%) — %d whole-grid uplifts, cap-excluded %d"
          % (len(inband), TARGET_B112_INBAND, n112, 100 * len(inband) / n112, 100 * TARGET_B112_INBAND / n112, b112_k, capped))
    print("  1.3 NIC-26: class asserted 26 (22 uncl + 4 SME + 0 large) -> NIC='No'")
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_book = book_excl(c, [GAP, B112, NIC])
    fixpre = {(q, o): c.execute("SELECT COALESCE(matrix_row_id,''),value FROM answers WHERE question_id=? AND org_id=? ORDER BY 1", (q, o)).fetchall()
              for q in (GAP, B112, NIC, SAL) for o in FIX}
    npre = {q: c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] for q in (GAP, B112, NIC)}
    salpre = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value='Yes'", (SAL,)).fetchone()[0]
    # headlines that must NOT move
    def emax_headline():
        d = {}
        for r in c.execute("SELECT org_id,COALESCE(matrix_row_id,'') rk,value FROM answers WHERE question_id='REW_BEN_PENS_EMP_MAX_01' AND COALESCE(value,'')!=''"):
            try: d.setdefault(r["org_id"], []).append(float(r["value"]))
            except ValueError: pass
        return sum(1 for v in d.values() if max(v) >= 9)
    def match_headline():
        return c.execute("SELECT COUNT(*) FROM answers WHERE question_id='REW26_BEN_PENSION_MATCH' AND value!='None' AND COALESCE(value,'')!=''").fetchone()[0]
    emax_pre, match_pre = emax_headline(), match_headline()

    cur = c.cursor()
    for o in gap_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " gap012", GAP, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", ("Yes – at least annually", GAP, o))
    for o in b112_take:
        delta = newfront(o) - grids[o][FRONT]
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " b112 shape (uniform uplift +%g)" % delta, B112, o))
        for rk, val in grids[o].items():
            nv = val + delta
            cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND COALESCE(matrix_row_id,'')=?",
                        ("%g" % nv, B112, o, rk))
    for o in contra:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " nic26 repair", NIC, o))
        cur.execute("UPDATE answers SET value='No' WHERE question_id=? AND org_id=?", (NIC, o))

    # ---- asserts before commit ----
    assert book_excl(c, [GAP, B112, NIC]) == pre_book, "NON-BATCH ANSWERS CHANGED"
    for q in (GAP, B112, NIC):
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] == npre[q], "n changed on %s" % q
    for (q, o), v in fixpre.items():
        assert c.execute("SELECT COALESCE(matrix_row_id,''),value FROM answers WHERE question_id=? AND org_id=? ORDER BY 1", (q, o)).fetchall() == v, "FIXTURE MOVED %s/%s" % (q, o)
    ann2 = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value='Yes – at least annually'", (GAP,)).fetchone()[0]
    anyy = c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value LIKE 'Yes%'", (GAP,)).fetchone()[0]
    assert ann2 == TARGET_GAP and anyy == 45, (ann2, anyy)
    g2 = {}
    for r in c.execute("SELECT org_id,COALESCE(matrix_row_id,'') rk,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (B112,)):
        g2.setdefault(r["org_id"], {})[r["rk"]] = float(r["value"])
    inband2 = sum(1 for v in g2.values() if v.get(FRONT) is not None and 3 <= v[FRONT] <= 6)
    inv2 = sum(1 for v in g2.values() if v.get(FRONT) is not None and len(v) > 1 and v[FRONT] > min(x for k, x in v.items() if k != FRONT))
    capv = max(max(v.values()) for v in g2.values())
    assert inband2 == TARGET_B112_INBAND and inv2 == 0 and capv <= GRID_CAP, (inband2, inv2, capv)
    contra2 = [o for o in sal if sal[o] == "Yes" and
               (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (NIC, o)).fetchone() or [""])[0] == "No sal-sac scheme"]
    assert len(contra2) == 0, "contradictions remain: %d" % len(contra2)
    assert emax_headline() == emax_pre and match_headline() == match_pre, "PENS_EMP_MAX/PENSION_MATCH headline moved"
    assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value='Yes'", (SAL,)).fetchone()[0] == salpre, "SALSAC grazed"
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "gap_promoted": gap_k, "b112_uplifted": b112_k,
                      "b112_cap_excluded": capped, "nic_repaired": len(contra), "contradictions_after": 0,
                      "inversions": 0, "fixtures": "byte-held", "non_batch_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
