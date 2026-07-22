"""
r3sw23 — dental cover sector-gate + funding conditioning (Design B: 038 Dental-tick as parent).

Two mis-seeded dental signals disagreed: REW_BEN_038 "Dental cover" tick (42, cost-heavy) and the
REW263_BEN_DENTAL funding metric (32, cost-heavy), 9 overlap. Dental is a RARE, sector-specific
perk. Sector-gate the 038 Dental-tick (the parent, like PMI) to ~11 perk-concentrated, condition
the funding metric on it, aligning both signals. EST/grade-C (direction sourced — CIPD
private-2.5x-public + LaingBuisson small insured base; the CIPD 24% is dental CASH PLANS, the
wrong product — rates estimated). Verdict EST-SUPPRESSED.

  PART 1  re-gate REW_BEN_038 "Dental cover": KEEP the 11 (perk 8 / cost 2 / media 1, all current
          tickers, prefer coherent-then-latent); REMOVE the token from the other 31. PMI-SAFEGUARD
          (038 is the PMI parent): PMI-tick set 154 byte-identical + PMI family bases unmoved
          (HARD ABORT). Dental token orthogonal to PMI.
  PART 2  condition REW263_BEN_DENTAL (funding) on the 11: DELETE all 220 rows, INSERT 11 with the
          funding split Voluntary 7 / Employer-paid 4 (~65/35 EST). Collapses "Not offered" +
          "Not applicable" (both no-dental) by deletion — non-tickers hold no row.
  PART 3  applicable_bases conditioned (parent 038 Dental cover, caption "of organisations with
          dental cover"); mp unbenchmarked=True; subset pair funding ⊆ 038 Dental-tick; the flat
          offer marginal retired. Thin base 11 accepted (rare benefit, above n<5, suppressed).
Dual-config atomic (r3sw7). Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # noqa: E402

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    try:
        PROF.update(json.load(open(os.path.join(ROOT, _p), encoding="utf-8")))
    except FileNotFoundError:
        pass

P038, DTOK, PMITOK = "REW_BEN_038", "Dental cover", "Private Medical Insurance (PMI)"
FUND = "REW263_BEN_DENTAL"
PERK = {"Professional Services", "Financial Services", "Technology, Software & Digital", "Healthcare & Life Sciences"}
TARGET = {"perk": 8, "cost": 2, "media": 1}
FUND_SPLIT = [("Voluntary (employee-funded)", 7), ("Employer-paid", 4)]
STAMP = "2026-07-21"
TOUCHED = [P038, FUND]
PMI_CHILDREN = ["REW265_BEN_PMICOMP", "REW_BEN_139", "REW_BEN_044", "3faf1f0c-f753-497f-a395-384bba38c5e3",
                "REW263_BEN_PMIEXCESS"]


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def bucket(ind):
    return "perk" if ind in PERK else ("media" if ind.startswith("Media") else "cost")


def hrank(tag, o):
    return hashlib.sha256(("r3sw23|%s|%s" % (tag, o)).encode()).hexdigest()


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    ap.add_argument("--mp-config-out", dest="mp_out", default=None)
    a = ap.parse_args()
    served_db = os.path.join(ROOT, "lumi.db")
    served_ab = os.path.join(ROOT, "data", "applicable_bases.json")
    served_mp = os.path.join(ROOT, "data", "market_position_config.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            a.config_out = served_ab if is_live else sys.exit("REFUSED: throwaway needs --config-out (r3sw7)")
        if a.mp_out is None:
            a.mp_out = served_mp if is_live else sys.exit("REFUSED: throwaway needs --mp-config-out (r3sw7)")
        if not is_live and (os.path.abspath(a.config_out) == served_ab or os.path.abspath(a.mp_out) == served_mp):
            sys.exit("REFUSED: throwaway may not target a served config (r3sw7)")

    c = sqlite3.connect(a.db)
    orgs = {r[0]: (r[1] or "") for r in c.execute("SELECT org_id, industry FROM orgs")}
    p038 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,))}
    pmi_pre = {o for o, v in p038.items() if PMITOK in toks(v)}
    assert len(pmi_pre) == 154, "PMI-haver set != 154 (%d)" % len(pmi_pre)
    dtick = {o for o, v in p038.items() if DTOK in toks(v)}
    assert len(dtick) == 42, "038 Dental-tick moved: %d" % len(dtick)
    NAV = {"Not applicable", "Not offered"}
    fund_hav = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (FUND,))
                if v not in NAV}

    # ---- select the 11 (all current tickers; prefer coherent then latent) ----
    byb = {}
    for o in dtick:
        byb.setdefault(bucket(orgs[o]), []).append(o)
    keep = set()
    for bk, k in TARGET.items():
        ranked = sorted(byb.get(bk, []), key=lambda o: (o not in fund_hav, -latent(o, PROF), hrank("pick", o)))
        keep |= set(ranked[:k])
    assert len(keep) == 11 and keep <= dtick
    drop = sorted(dtick - keep)
    assert len(drop) == 31
    allt = sorted(keep | set(drop))
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(allt)), allt)}
    assert src == {"seed"}, "non-seed org in the dental set: %s" % src

    fund_seed, i = {}, 0
    ranked_keep = sorted(keep, key=lambda o: hrank("fund", o))
    for lab, k in FUND_SPLIT:
        for o in ranked_keep[i:i + k]:
            fund_seed[o] = lab
        i += k
    assert len(fund_seed) == 11

    base_pre = {q: {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))}
                for q in PMI_CHILDREN}
    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  038 Dental-tick 42 -> 11 (perk 8 / cost 2 / media 1); remove token from 31 (PMI preserved)")
    print("  funding conditioned on 11: Voluntary 7 / Employer-paid 4 (~65/35 EST); non-tickers -> no row (collapse)")
    print("  answers %d -> %d (038 value-only; funding 220 rows -> 11)" % (n_before, n_before - 209))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    for o in drop:
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw23 pre-dental-degate", P038, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                    ("; ".join(t for t in toks(p038[o]) if t != DTOK), P038, o))
    cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                   SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                (STAMP + " r3sw23 pre-recondition", FUND))
    cur.execute("DELETE FROM answers WHERE question_id=?", (FUND,))
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,'',?,?)", [(o, FUND, fund_seed[o], STAMP + " 09:00:00") for o in keep])

    # ---- coherence + PMI-safeguard asserts BEFORE commit ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    pmi_post = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,))
                if PMITOK in toks(v)}
    assert pmi_post == pmi_pre and len(pmi_post) == 154, "PMI-TICK SET MOVED — HARD ABORT"
    for q, s in base_pre.items():
        assert {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (q,))} == s, \
            "PMI child %s base MOVED" % q
    dtick2 = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (P038,))
              if DTOK in toks(v)}
    assert dtick2 == keep and len(dtick2) == 11, "038 Dental-tick != 11"
    fnow = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (FUND,))}
    assert set(fnow) == keep, "funding-answerers != the 11 tickers"
    assert all(v in ("Voluntary (employee-funded)", "Employer-paid") for v in fnow.values()), "non-funding value survived"
    got = {lab: sum(1 for v in fnow.values() if v == lab) for lab, _ in FUND_SPLIT}
    assert got == {"Voluntary (employee-funded)": 7, "Employer-paid": 4}, got

    ab = json.load(open(served_ab, encoding="utf-8"))
    ab["metrics"][FUND] = {"mode": "conditioned", "base_label": "organisations with dental cover",
                           "parent": {"qid": P038, "contains": DTOK},
                           "_r3sw23": "sector-gated (038 Dental-tick 42->11 perk-concentrated) + funding conditioned; EST grade-C (cash-plan-vs-cover product finding); verdict suppressed; thin base 11"}
    ab_text = json.dumps(ab, indent=1, ensure_ascii=False)
    mp = json.load(open(served_mp, encoding="utf-8"))
    mp["metrics"][FUND]["unbenchmarked"] = True
    mp["metrics"][FUND]["_r3sw23"] = "verdict SUPPRESSED — EST grade-C dental (no free insurance-product sector data) + thin base"
    mp_text = json.dumps(mp, indent=2, ensure_ascii=False)
    c.commit()
    for path, text in ((a.config_out, ab_text), (a.mp_out, mp_text)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    with open(os.path.join(man_dir, "r3sw23_seed_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "detail"])
        w.writerow([P038, "Dental-tick 42->11 (perk-concentrated); PMI preserved", "removed from 31"])
        w.writerow([FUND, "conditioned on 11; collapse N/A+Not-offered", json.dumps(got)])
    print(json.dumps({"applied": True, "dental_tick": "42 -> 11 (perk 8 / cost 2 / media 1)",
                      "funding": got, "pmi_safeguard": "PMI 154 byte-identical + 5 children unmoved (asserted)",
                      "conditioning": "funding-answerers == 11 == 038 Dental-tick", "answers": n_before - 209,
                      "config": "conditioned + suppressed", "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
