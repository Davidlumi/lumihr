# -*- coding: utf-8 -*-
"""migrate_batch6_pay.py — Round-2 batch-6: PAY (David 2026-07-25, "confirm five, target two,
hold OT pair"; 6.2 AMENDED per the 2026-07-25 gate-reconciliation ruling 3: increment set =
the book's NATIVE TENTHS — answer-texture is a property of the book, DERIVED from it, never
legislated into a design note). SEED-DATA class, two moves, one apply. Both DOWNWARD
(approach the anchor FROM ABOVE, STOP SHORT).

  6.1 GAP_009 headline ↓ (UNCHANGED from the verified first rehearsal): weekly arms
      150/206 = 72.8% -> 140/206 = 68.0% vs the 65% grade-A anchor (stop-short x1.046).
      K_GAP=10, all '1–2 days per week' -> 'Less than once a month' (adjacent notch; both
      structural bonuses asserted: intra-weekly mix 80/70 -> 70/70 toward the anchor's ~40/60;
      any-minimum reading INVARIANT at 158/206).
  6.2 PROP_9e4ad87f NUMERIC shape ↓, redesigned on NATIVE TENTHS:
      - DONORS drawn DIFFUSELY across 3.5–3.9 (no crater): quotas by CAPPED largest-remainder
        proportional to each layer's total population (11/14/11/15/21, sum 72), caps = the
        floor-rule-eligible pools (8/10/6/5/11); over-cap layers are clamped and the remainder
        RE-APPORTIONED among the rest (ties broken remainder-desc then layer-asc)
        -> {3.5:5, 3.6:7, 3.7:5, 3.8:5, 3.9:10} = 32. Layer retentions
        .545/.500/.545/.667/.524 vs region average .556 (min .500 — no preferential shave);
        the 3.4 shoulder is untouched (11).
      - DESTINATIONS on tenths 2.1–2.9 mirroring the live band texture (rising toward the
        band top, as the live 2-band and 3-band both do): additions 2.1:1 2.2:1 2.3:2 2.4:2
        2.5:3 2.6:4 2.7:5 2.8:6 2.9:8 -> post 2-band 1/1/1/2/4/4/7/8/11/15 (max adjacent
        ratio 2.0 vs the live book's own 3.0 precedent at 2.5->2.6; top count 15 < the live
        3.9's 21). Rank-preserving map: movers sorted (-value, sha) onto the descending
        destination list; per-org drop 1.0–1.4pp.
      - LANDINGS: median 3.70 -> 3.40 EXACT (3.30 is arithmetically unreachable at k=32:
        cum<=3.3 = 59 + movers-from->=3.4, so 3.30 needs >=42 such movers -> band 39% breaches
        the 40% anchor floor — the band floor binds, not the floor rule); band 3-3.99
        120 -> 88 = 44.0% (stop-short x1.10 above 40%).
      - THE FOUR FINGERPRINT GROUNDS FROM THE ADVERSARIAL REVIEW ARE EXPLICIT ASSERTS
        (absolute): (i) no value-string class unique to redrawn rows; (ii) no decimal-
        precision outlier; (iii) no heaping without in-book precedent; (iv) no donor crater
        (quantified vs shoulders).
      - Consistency floor-rule held per org (destinations 2.1–2.9 all >= the max band floor
        2.0); range: min 2.00 / max 5.30 unchanged.

Fixtures byte-held, skips stated: Retail + Advisory both sit in GAP_009's '1–2 days' draw arm;
Retail (3.1) is in PROP's modal band but below the 3.5–3.9 donor region; Advisory (4.1) is
out-of-band. Pre-state hard-asserted (live apply refuses on drift from the rehearsed state).
Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, re, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
GAP, PROP, INCR = "EXT_REW_GAP_009", "PROP_9e4ad87f", "PROP_634adacd"
FIX = ("5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7", "833beedb-c4c9-43aa-a6b3-3dbee9e76e99")
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
STAMP = "2026-07-25 batch6-pay"

K_GAP = 10
ARM_12, ARM_3P, ARM_LTM = "1–2 days per week", "3 or more days per week", "Less than once a month"
GAP_PRE = {ARM_12: 80, ARM_3P: 70, "Attendance varies widely": 39, "Fully remote": 9, ARM_LTM: 8}

OK_INCR = ("0%", "0.1%–1.9%", "2.0%–2.9%", "Not measured")   # floor-rule bands (+ no-answer)
DONOR_LAYERS = (3.5, 3.6, 3.7, 3.8, 3.9)
QUOTAS_EXPECTED = {3.5: 5, 3.6: 7, 3.7: 5, 3.8: 5, 3.9: 10}   # the design-note numbers David rules on
DEST = ["2.9"] * 8 + ["2.8"] * 6 + ["2.7"] * 5 + ["2.6"] * 4 + ["2.5"] * 3 \
     + ["2.4"] * 2 + ["2.3"] * 2 + ["2.2"] * 1 + ["2.1"] * 1   # 32, descending, native tenths
PROP_PRE = {"n": 200, "median": 3.70, "bands": (0, 0, 22, 120, 52, 6), "vmin": 2.0, "vmax": 5.3}
PROP_POST = {"median": 3.40, "bands": (0, 0, 54, 88, 52, 6)}
POST_2BAND = {2.0: 1, 2.1: 1, 2.2: 1, 2.3: 2, 2.4: 4, 2.5: 4, 2.6: 7, 2.7: 8, 2.8: 11, 2.9: 15}


def h(tag, org):
    return hashlib.sha256(("b6::%s::%s" % (tag, org)).encode()).hexdigest()


def book_excl(c, excl):
    hh = hashlib.sha256()
    q = ("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers "
         "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(excl)))
    for r in c.execute(q, excl):
        hh.update(("|".join(str(x) for x in r)).encode())
    return hh.hexdigest()


def band_ix(x):
    return 0 if x < 1 else 1 if x < 2 else 2 if x < 3 else 3 if x < 4 else 4 if x < 5 else 5


def median200(vals):
    s = sorted(vals)
    return (s[99] + s[100]) / 2.0


def adj_ratios(hist):
    """max count-ratio between consecutive POPULATED tenths of a {value: count} histogram."""
    ks = sorted(hist)
    out = []
    for a, b in zip(ks, ks[1:]):
        if round(b - a, 2) == 0.1 and hist[a] and hist[b]:
            out.append(max(hist[a], hist[b]) / min(hist[a], hist[b]))
    return max(out) if out else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    assert not (FROZEN8 & {GAP, PROP, INCR}), "frozen-8 grazed"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    g = lambda q: {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,))}
    gap, prop, incr = g(GAP), g(PROP), g(INCR)

    # ---- pre-state drift guards ----
    assert Counter(gap.values()) == Counter(GAP_PRE), "GAP_009 pre-state drifted: %s" % Counter(gap.values())
    vals = {o: float(v) for o, v in prop.items()}
    bc = Counter(band_ix(x) for x in vals.values())
    assert (len(vals), round(median200(vals.values()), 2)) == (PROP_PRE["n"], PROP_PRE["median"]), "PROP pre-median drifted"
    assert tuple(bc.get(i, 0) for i in range(6)) == PROP_PRE["bands"], "PROP pre-bands drifted"
    assert (min(vals.values()), max(vals.values())) == (PROP_PRE["vmin"], PROP_PRE["vmax"]), "PROP range drifted"
    assert gap[FIX[0]] == ARM_12 and gap[FIX[1]] == ARM_12, "fixture GAP arm drifted"
    assert prop[FIX[0]] == "3.1" and prop[FIX[1]] == "4.1", "fixture PROP value drifted"

    # ---- 6.1 GAP_009 (unchanged from the verified first rehearsal) ----
    pool12 = sorted((o for o, v in gap.items() if v == ARM_12 and o not in FIX), key=lambda o: h("gap9", o))
    assert len(pool12) == 78 and K_GAP <= len(pool12), "GAP pool drifted"
    gap_take = pool12[:K_GAP]

    # ---- 6.2 PROP: diffuse donors on native tenths ----
    def eligible(o):
        b = incr.get(o)
        return (b is None or b in OK_INCR) and o not in FIX
    elig_by_layer = {L: sorted((o for o in vals if round(vals[o], 2) == L and eligible(o)),
                               key=lambda o: h("prop", o)) for L in DONOR_LAYERS}
    totals = {L: sum(1 for x in vals.values() if round(x, 2) == L) for L in DONOR_LAYERS}
    caps = {L: len(elig_by_layer[L]) for L in DONOR_LAYERS}
    assert totals == {3.5: 11, 3.6: 14, 3.7: 11, 3.8: 15, 3.9: 21} and \
           caps == {3.5: 8, 3.6: 10, 3.7: 6, 3.8: 5, 3.9: 11}, "donor pools drifted: %s %s" % (totals, caps)
    # CAPPED largest-remainder: clamp over-cap layers, re-apportion the remainder among the
    # rest (standard constrained apportionment; ties remainder-desc then layer-asc)
    tot = sum(totals.values())

    def apportion(seats, weights):
        fixed = {}
        while True:
            free = [L for L in weights if L not in fixed]
            w = sum(weights[L] for L in free)
            s = seats - sum(fixed.values())
            qf = {L: s * weights[L] / w for L in free}
            q = {L: int(qf[L]) for L in free}
            for L in sorted(free, key=lambda L: (-(qf[L] - q[L]), L))[: s - sum(q.values())]:
                q[L] += 1
            over = [L for L in free if q[L] > caps[L]]
            if not over:
                return {**fixed, **q}
            for L in over:
                fixed[L] = caps[L]

    quotas = apportion(32, totals)
    assert quotas == QUOTAS_EXPECTED and sum(quotas.values()) == 32, "quota derivation drifted: %s" % quotas
    movers = [o for L in DONOR_LAYERS for o in elig_by_layer[L][:quotas[L]]]
    movers = sorted(movers, key=lambda o: (-vals[o], h("prop", o)))
    assert len(movers) == len(DEST) == 32
    prop_take = list(zip(movers, DEST))
    for o, nv in prop_take:   # consistency floor-rule re-proved per org; rank preservation
        b = incr.get(o)
        floor = {"0%": 0.0, "0.1%–1.9%": 0.1, "2.0%–2.9%": 2.0, "Not measured": 0.0}.get(b, 0.0)
        assert float(nv) >= floor, "floor-rule breach %s: %s -> %s" % (o, b, nv)
    assert all(float(a[1]) >= float(b[1]) for a, b in zip(prop_take, prop_take[1:])), "mapping not rank-preserving"

    print("batch-6 re-run %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  6.1 GAP_009 (unchanged): weekly 150 -> 140 (72.8%% -> 68.0%%; anchor 65%%, x1.046) | 10x '1–2d' -> '<monthly' | fixtures skipped")
    print("  6.2 PROP (native tenths): median 3.70 -> 3.40 (anchor 3.0); band 120 (60%%) -> 88 (44.0%%; anchor 40%%, x1.10)")
    print("      donors %s of layers %s (caps %s) | dests 2.1–2.9 additions %s" %
          (quotas, totals, caps, dict(Counter(DEST))))
    if not a.write:
        print("dry-run complete"); c.close(); return

    pre_book = book_excl(c, [GAP, PROP])
    fixpre = {(q, o): (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0]
              for q in (GAP, PROP, INCR) for o in FIX}
    npre = {q: len(g(q)) for q in (GAP, PROP, INCR)}
    incr_pre = sorted(incr.items())
    live_kept_formats = {len(v.split(".")[-1]) for o, v in prop.items() if o not in {m for m, _ in prop_take}}
    live_max_adj = adj_ratios({v: n for v, n in Counter(vals.values()).items() if 2.0 <= v < 5.0})
    live_max_count = max(Counter(vals.values()).values())          # 21 @ 3.9
    cur = c.cursor()
    for o in gap_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " gap009", GAP, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (ARM_LTM, GAP, o))
    for o, nv in prop_take:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " prop numeric-shape", PROP, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (nv, PROP, o))

    # ---- asserts before commit ----
    assert book_excl(c, [GAP, PROP]) == pre_book, "NON-BATCH ANSWERS CHANGED"
    gap2, prop2 = g(GAP), g(PROP)
    assert sorted(g(INCR).items()) == incr_pre, "PROP_634adacd (consistency parent) MOVED"
    for q in (GAP, PROP, INCR):
        assert len(g(q)) == npre[q], "n changed on %s" % q
    for (q, o), v in fixpre.items():
        assert (c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (q, o)).fetchone() or [None])[0] == v, \
            "FIXTURE MOVED %s/%s" % (q, o)
    d2 = Counter(gap2.values())
    assert d2 == {ARM_12: 70, ARM_3P: 70, "Attendance varies widely": 39, ARM_LTM: 18, "Fully remote": 9}, dict(d2)
    assert d2[ARM_12] + d2[ARM_3P] == 140 and d2[ARM_12] + d2[ARM_3P] + d2[ARM_LTM] == 158, "GAP landings/invariant wrong"
    vals2 = {o: float(v) for o, v in prop2.items()}
    med2 = round(median200(vals2.values()), 2)
    bc2 = Counter(band_ix(x) for x in vals2.values())
    assert med2 == PROP_POST["median"], "median landed %.2f != 3.40" % med2
    assert tuple(bc2.get(i, 0) for i in range(6)) == PROP_POST["bands"], dict(bc2)
    assert (min(vals2.values()), max(vals2.values())) == (2.0, 5.3), "range sanity broken"
    h2 = {v: n for v, n in Counter(vals2.values()).items() if 2.0 <= v < 3.0}
    assert h2 == POST_2BAND, "post 2-band histogram drifted: %s" % h2

    # ---- THE FOUR FINGERPRINT ASSERTS (absolute; the adversarial-review grounds inverted) ----
    redrawn = {o: prop2[o] for o, _ in prop_take}
    # (i) no value-string class unique to redrawn rows (format class + no quarter-endings)
    assert all(re.match(r"^\d\.\d$", v) for v in redrawn.values()), "redrawn value-string class not book-native"
    assert {len(v.split(".")[-1]) for v in redrawn.values()} <= live_kept_formats, "redrawn format class unique"
    assert not any(v.endswith((".25", ".75")) for v in redrawn.values()), "quarter-grid endings reintroduced"
    # (ii) no decimal-precision outlier anywhere in the post book
    assert all(re.match(r"^\d+\.\d$", v) for v in prop2.values()), "decimal-precision outlier in post book"
    # (iii) no heaping without in-book precedent
    assert adj_ratios(h2) <= live_max_adj, "post 2-band adjacent ratio %.2f exceeds live precedent %.2f" % (adj_ratios(h2), live_max_adj)
    assert max(h2.values()) <= live_max_count, "post 2-band top count exceeds the live book's max layer"
    # (iv) no donor crater, quantified vs shoulders
    post_layers = {L: sum(1 for x in vals2.values() if round(x, 2) == L) for L in DONOR_LAYERS}
    rets = {L: post_layers[L] / totals[L] for L in DONOR_LAYERS}
    assert min(rets.values()) >= 0.45, "donor-layer retention cratered: %s (region avg %.3f)" % (rets, (tot - 32) / tot)
    h3 = {round(3.0 + i / 10, 1): sum(1 for x in vals2.values() if round(x, 2) == round(3.0 + i / 10, 1)) for i in range(10)}
    for v in [round(3.1 + i / 10, 1) for i in range(8)]:
        lo, hi = h3[round(v - 0.1, 1)], h3[round(v + 0.1, 1)]
        assert not (h3[v] * 2 < lo and h3[v] * 2 < hi), "interior crater at %.1f: %d between %d/%d" % (v, h3[v], lo, hi)
    assert h3[3.4] == 11, "the 3.4 shoulder moved"
    # direction sign checks: both DOWN toward their anchors from above
    assert d2[ARM_12] + d2[ARM_3P] < 150 and bc2[3] < 120 and med2 < 3.70, "direction sign check failed"
    hist_n = c.execute("SELECT COUNT(*) FROM answers_history WHERE recorded_at LIKE ?", (STAMP + "%",)).fetchone()[0]
    assert hist_n == K_GAP + 32, "history pre-images: %d != 42" % hist_n
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "gap_moves": K_GAP, "prop_moves": 32,
                      "gap_weekly": "140/206=68.0% (anchor 65)", "any_minimum_invariant": "158 held",
                      "prop_median": "3.70 -> %.2f (anchor 3.0)" % med2,
                      "prop_band3": "120 -> %d (44.0%%; anchor 40)" % bc2[3],
                      "donor_quotas": {str(k): v for k, v in quotas.items()},
                      "donor_retentions": {str(k): round(v, 3) for k, v in rets.items()},
                      "dest_histogram": dict(Counter(DEST)),
                      "fingerprint_asserts": "all four PASSED",
                      "fixtures": "byte-held", "non_batch_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
