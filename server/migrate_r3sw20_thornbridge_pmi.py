"""
r3sw20 — Thornbridge PMI-tick cleanup: tick the demo org into the PMI-haver set + re-condition
the PMI family 153 -> 154 (ruled). This MOVES the parent (not orthogonal — the family bases change).

Thornbridge (director@thornbridge.example, Retail/PLC/50-249) holds GENUINE PMI premium entries
(£680/£1,200/£1,600) but never ticked "offers PMI" in REW_BEN_038 — premiums without the scheme,
an incoherence carried since r3sw6 as the "documented exception". Fix: tick it (153 -> 154), seed
its family child answers (equality-conditioned children MUST answer), premium already genuine.

  PART 1  add the PMI token to Thornbridge's REW_BEN_038 (other 6 benefit ticks preserved).
  PART 2  seed Thornbridge on the equality-conditioned children (a plausible Retail/PLC mid-market
          PMI, internally consistent): elig-rules "Grade/level restricted"; by-level depth-4
          (board/director/head-of/senior-manager eligible — grade-restricted, monotone prefix);
          composition out-patient + physio (the two most common elements). Premium UNTOUCHED
          (genuine) — its base is now cleanly 154 (the documented-exception note retired).
  PART 3  coherence-gate against 154: every family child base == 154; all 4 pairs (incl. the new
          premium pair) ⊆ 154. Parent-move — the family-set assert is 154, not 153.
Book hash excludes the touched metrics; premium is UNTOUCHED (stays in the hash). Verdict statuses
unchanged. Dry-run default; --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT, TOKEN = "REW_BEN_038", "Private Medical Insurance (PMI)"
COMP, BYLEV, ELIG, PREM = ("REW265_BEN_PMICOMP", "REW_BEN_139", "REW_BEN_044",
                           "3faf1f0c-f753-497f-a395-384bba38c5e3")
LEVELS = ["board_executive", "director", "head_of", "senior_manager",
          "manager", "supervisor_team_leader", "frontline_individual_contributor"]
STAMP = "2026-07-21"
T_COMP = "Out-patient cover (consultations, diagnostics, scans); Physiotherapy / MSK / therapies"
T_ELIG = "Grade/level restricted"
T_DEPTH = 4  # grade-restricted: top 4 levels eligible
TOUCHED = [PARENT, COMP, BYLEV, ELIG]


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def book_hash(c):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(TOUCHED))
    for r in c.execute(q, TOUCHED):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def havers(c):
    return {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
            if TOKEN in toks(v)}


def base(c, qid):
    return {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (qid,))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(a.db)
    tid = c.execute("SELECT org_id FROM users WHERE email='director@thornbridge.example'").fetchone()[0]
    src = c.execute("SELECT source FROM orgs WHERE org_id=?", (tid,)).fetchone()[0]
    assert src == "seed", "Thornbridge is not a seed org: %s" % src

    hv = havers(c)
    assert len(hv) == 153 and tid not in hv, "unexpected haver state: %d / thorn-in=%s" % (len(hv), tid in hv)
    v038 = c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (PARENT, tid)).fetchone()[0]
    assert TOKEN not in toks(v038), "Thornbridge already ticks PMI"
    for kid in (COMP, BYLEV, ELIG):
        assert base(c, kid) == hv, "%s base != 153 havers pre-write" % kid
        assert not c.execute("SELECT 1 FROM answers WHERE question_id=? AND org_id=? LIMIT 1", (kid, tid)).fetchone(), \
            "Thornbridge already answers %s" % kid
    prem = base(c, PREM)
    assert prem == hv | {tid}, "premium base != 153 havers + Thornbridge (%d)" % len(prem)   # the documented exception
    prem_vals = dict(c.execute("SELECT matrix_row_id, value FROM answers WHERE question_id=? AND org_id=?", (PREM, tid)))
    assert prem_vals == {"single": "680", "partner": "1200", "family": "1600"}, "genuine premium moved: %s" % prem_vals

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  tick Thornbridge PMI in REW_BEN_038 (153 -> 154 havers; commercial 144 -> 145)")
    print("  seed elig-rules=%r, by-level depth-%d, composition=out-patient+physio | premium genuine (kept)"
          % (T_ELIG, T_DEPTH))
    print("  answers %d -> %d (+9: 1 comp + 7 by-level + 1 elig; parent value-only; premium untouched)"
          % (n_before, n_before + 9))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c)
    cur = c.cursor()
    for qid in TOUCHED:
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw20 pre-tick", qid, tid))
    cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?",
                ("; ".join(toks(v038) + [TOKEN]), PARENT, tid))
    cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                "VALUES (?,1,?,'',?,?)", (tid, COMP, T_COMP, STAMP + " 09:00:00"))
    cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                "VALUES (?,1,?,'',?,?)", (tid, ELIG, T_ELIG, STAMP + " 09:00:00"))
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,?,?,?)",
                    [(tid, BYLEV, L, "Yes" if j < T_DEPTH else "No", STAMP + " 09:00:00") for j, L in enumerate(LEVELS)])

    # ---- coherence-gate against 154 (pre-commit) ----
    assert book_hash(c) == pre_hash, "NON-TARGET BOOK CHANGED"
    hv2 = havers(c)
    assert hv2 == hv | {tid} and len(hv2) == 154, "PMI-haver set != 154"
    for kid in (COMP, BYLEV, ELIG):
        assert base(c, kid) == hv2, "%s base != 154 (%d)" % (kid, len(base(c, kid)))
    assert base(c, PREM) == hv2, "premium base != 154 (Thornbridge now a real haver)"  # exception retired
    # by-level monotone prefix for Thornbridge
    tbl = dict(c.execute("SELECT matrix_row_id, value FROM answers WHERE question_id=? AND org_id=?", (BYLEV, tid)))
    seq = [tbl[L] for L in LEVELS]
    assert seq == ["Yes"] * T_DEPTH + ["No"] * (7 - T_DEPTH), seq
    assert c.execute("SELECT value FROM answers WHERE question_id=? AND org_id=?", (ELIG, tid)).fetchone()[0] == T_ELIG
    assert dict(c.execute("SELECT matrix_row_id, value FROM answers WHERE question_id=? AND org_id=?", (PREM, tid))) == prem_vals

    c.commit()
    with open(os.path.join(ROOT if os.path.abspath(a.db) == os.path.join(ROOT, "lumi.db")
                           else os.path.dirname(os.path.abspath(a.db)), "r3sw20_seed_manifest.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "thornbridge_value", "note"])
        w.writerow([PARENT, "+PMI tick", "153 -> 154 havers"])
        w.writerow([ELIG, T_ELIG, "seeded (equality-conditioned)"])
        w.writerow([BYLEV, "depth-4 (grade-restricted)", "seeded (equality-conditioned)"])
        w.writerow([COMP, T_COMP, "seeded (equality-conditioned)"])
        w.writerow([PREM, "680/1200/1600", "GENUINE — kept; exception retired, now a real haver"])
    print(json.dumps({"applied": True, "pmi_havers": "153 -> 154", "commercial": "144 -> 145",
                      "thornbridge": {"elig": T_ELIG, "by_level": "depth-4", "composition": "out-patient+physio",
                                      "premium": "680/1200/1600 (genuine, kept)"},
                      "family_bases": {"composition": len(base(c, COMP)), "by_level": len(base(c, BYLEV)),
                                       "elig_rules": len(base(c, ELIG)), "premium": len(base(c, PREM))},
                      "answers": n_before + 9, "non_target_book": "hash-identical"}, indent=2))


if __name__ == "__main__":
    main()
