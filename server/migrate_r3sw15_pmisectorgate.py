"""
r3sw15 — PMI sector-gate: parent re-gate REW_BEN_038 + atomic family re-condition (ruled).

Sector rates (ruled, on the PMI tick of REW_BEN_038 = "offers PMI in some form"):
  Commercial 77% (CIPD large-private 250+, cohort-matched — NOT all-private 61%)
  Charity 24% · Public 17% (CIPD H&W 2025 + 2022 + gov frameworks) · Education 40% (EST).
SELECTION (additive, latent-ranked, matches "gated IN/OUT"): commercial keeps all current
havers + adds the highest-latent non-havers to the target; tails trim the lowest-latent havers.
  commercial 117 -> 144 (+27) · charity 5 -> 2 (-3) · public 4 -> 3 (-1) · education 4 (0).
  HAVER SET 130 -> 153 (flat-77% commercial reaches 144; this is the ruled rate, above the
  ~139 blend headline).

FAMILY (all atomic, all conditioned on REW_BEN_038):
  composition REW265_BEN_PMICOMP  (r3sw8)  — additive: retain 126, delete 4, add 27 incidence-
                                             matched to the ruled prevalences (diff8, no spike)
  by-level    REW_BEN_139          (r3sw14) — additive: retain 126 depths, delete 4, add 27 on
                                             the ruled cliff 95/90/80/70/20/2/0 (depth hist
                                             scaled to 27, monotone prefixes, latent-ranked)
  premium     3faf1f0c...          (r3sw6)  — additive: retain 126 + Thornbridge (GENUINE entries
                                             preserved), delete 4, add 27 with latent-spread
                                             multipliers (medians 800/1600/2000 preserved)

COHERENCE GATE (pre-commit, the critical requirement): composition & by-level answerer sets ==
the new 153 haver set EXACTLY; premium == 153 havers ∪ {Thornbridge} (the documented non-haver
with genuine entries, demo-cleanup queued). Zero count-matched-but-set-mismatched. Verdict
statuses UNTOUCHED (composition/by-level unbenchmarked EST; premium split-verdict). Config staged
via --config-out (r3sw7). Dry-run default; apply needs --write --confirmed-by-david.
"""
import argparse, csv, hashlib, json, os, statistics, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reseed_engine import latent  # noqa: E402

PROF = {}
for _p in ("org_profiles.json", "org_profiles_inferred.json"):
    try:
        PROF.update(json.load(open(os.path.join(ROOT, _p), encoding="utf-8")))
    except FileNotFoundError:
        pass

PARENT, TOKEN = "REW_BEN_038", "Private Medical Insurance (PMI)"
COMP, BYLEV, PREM = "REW265_BEN_PMICOMP", "REW_BEN_139", "3faf1f0c-f753-497f-a395-384bba38c5e3"
RATE = {"commercial": 0.77, "charity": 0.24, "public": 0.17, "education": 0.40}
STAMP = "2026-07-20"
LEVELS = ["board_executive", "director", "head_of", "senior_manager",
          "manager", "supervisor_team_leader", "frontline_individual_contributor"]
CLIFF = [95, 90, 80, 70, 20, 2, 0]
COMP_OPTS = ["Out-patient cover (consultations, diagnostics, scans)",
             "Full mental health cover (in- and out-patient psychiatric care and therapy)",
             "Physiotherapy / MSK / therapies", "Health screening / assessments",
             "Dental & optical", "Overseas / worldwide cover"]
COMP_RATE = [0.777, 0.500, 0.600, 0.423, 0.277, 0.223]   # ruled prevalences (order = options_json)
COMP_TERM = "None of these — core cover only"
PREM_MED = {"single": 800, "partner": 1600, "family": 2000}


def sector(ind):
    if ind.startswith("Charity"): return "charity"
    if ind.startswith("Public Sector"): return "public"
    if ind.startswith("Education"): return "education"
    return "commercial"


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def hrank(tag, o):
    return hashlib.sha256(("r3sw15|%s|%s" % (tag, o)).encode()).hexdigest()


def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "lumi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--config-out", default=None)
    a = ap.parse_args()

    served_db = os.path.join(ROOT, "lumi.db")
    served_cfg = os.path.join(ROOT, "data", "applicable_bases.json")
    is_live = os.path.abspath(a.db) == served_db
    if a.write:
        if a.config_out is None:
            a.config_out = served_cfg if is_live else sys.exit(
                "REFUSED: throwaway --write needs an explicit staged --config-out (r3sw7 doctrine)")
        elif not is_live and os.path.abspath(a.config_out) == served_cfg:
            sys.exit("REFUSED: a throwaway --write may not target the served config (r3sw7 doctrine)")

    c = sqlite3.connect(a.db)
    orgs = {r[0]: (r[1] or "", r[2] or "") for r in c.execute("SELECT org_id, industry, fte_band FROM orgs")}
    p038 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))}
    haver = {o for o, v in p038.items() if TOKEN in toks(v)}
    assert len(haver) == 130, "haver set moved: %d — re-diagnose" % len(haver)
    thorn = c.execute("SELECT org_id FROM users WHERE email='director@thornbridge.example'").fetchone()[0]

    # ---- selection ----
    bysec = {}
    for o in p038:
        bysec.setdefault(sector(orgs[o][0]), []).append(o)
    added, trimmed, new_haver = [], [], set()
    for s, members in bysec.items():
        cur = [o for o in members if o in haver]
        tgt = round(RATE[s] * len(members))
        if tgt >= len(cur):
            nonh = sorted([o for o in members if o not in haver], key=lambda o: (-latent(o, PROF), hrank("add", o)))
            add = nonh[:tgt - len(cur)]
            new_haver |= set(cur) | set(add); added += add
        else:
            keep = sorted(cur, key=lambda o: (-latent(o, PROF), hrank("keep", o)))[:tgt]
            new_haver |= set(keep); trimmed += [o for o in cur if o not in keep]
    assert len(new_haver) == 153 and len(added) == 27 and len(trimmed) == 4, \
        (len(new_haver), len(added), len(trimmed))
    retained = haver & new_haver
    assert len(retained) == 126 and not (set(added) & haver) and set(trimmed) <= haver
    touched_orgs = set(added) | set(trimmed) | retained | {thorn}
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(touched_orgs)), sorted(touched_orgs))}
    assert src == {"seed"}, "non-seed org in the family set: %s" % src
    # newly-added must currently hold ZERO child rows (they were non-havers)
    for qid in (COMP, BYLEV, PREM):
        stray = [o for o in added if c.execute(
            "SELECT 1 FROM answers WHERE question_id=? AND org_id=? LIMIT 1", (qid, o)).fetchone()]
        assert not stray, "newly-added org already holds %s rows: %s" % (qid, stray)

    n_before = c.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    print("dry-run diagnosis:" if not a.write else "APPLY:")
    for s in ("commercial", "charity", "public", "education"):
        cur = sum(1 for o in bysec[s] if o in haver)
        print("  %-11s %3d orgs: %3d -> %3d (%.0f%%)" % (s, len(bysec[s]), cur, round(RATE[s]*len(bysec[s])), RATE[s]*100))
    print("  HAVER 130 -> 153 | +27 commercial / -3 charity / -1 public | retained 126")

    # ---- child seed plans (deterministic) ----
    # composition: incidence-matched over the 27 added (diff8)
    comp_plan = {o: [] for o in added}
    for opt, rt in zip(COMP_OPTS, COMP_RATE):
        k = round(rt * 27)
        for o in sorted(added, key=lambda o: hrank("comp|" + opt, o))[:k]:
            comp_plan[o].append(opt)
    comp_vals = {o: "; ".join(x for x in COMP_OPTS if x in comp_plan[o]) or COMP_TERM for o in added}
    # by-level: depth histogram over the 130-cliff, scaled to 27, latent-ranked prefixes
    yc130 = [round(p / 100.0 * 130) for p in CLIFF]
    hist130 = {k: (130 if k == 0 else yc130[k - 1]) - (yc130[k] if k < 7 else 0) for k in range(8)}
    hist27 = {k: round(27 * hist130[k] / 130.0) for k in range(8)}
    # fix rounding to sum 27, biasing the modal band
    while sum(hist27.values()) != 27:
        d = 27 - sum(hist27.values()); hist27[4] += (1 if d > 0 else -1)
    add_ranked = sorted(added, key=lambda o: (-latent(o, PROF), hrank("bylev", o)))
    depths = {}; i = 0
    for k in range(7, -1, -1):
        for o in add_ranked[i:i + hist27[k]]:
            depths[o] = k
        i += hist27[k]
    assert i == 27
    # premium: the r3sw6 multiplier ladder RE-DERIVED over the full 153 havers (uniform [0.5,1.5]
    # latent-ranked desc, £10-rounded) so the ruled medians 800/1600/2000 and P25/P75 at 1.25/0.75x
    # are preserved EXACTLY on the corrected base — Single renders a verdict, its anchor must not
    # drift. Retained premium values re-derive (all seed); Thornbridge (non-haver) is untouched.
    full_ranked = sorted(new_haver, key=lambda o: (-latent(o, PROF), hrank("prem", o)))
    m_of = {o: round((1.5 - (r / (len(full_ranked) - 1))) * 100) / 100.0 for r, o in enumerate(full_ranked)}
    prem_vals = {o: {t: str(int(round(PREM_MED[t] * m_of[o] / 10.0) * 10)) for t in PREM_MED} for o in new_haver}

    if not a.write:
        print("  composition adds: %s (terminal %d)" % (
            {opt[:14]: sum(1 for o in added if opt in comp_plan[o]) for opt in COMP_OPTS},
            sum(1 for o in added if not comp_plan[o])))
        print("  by-level add depth hist: %s" % {k: v for k, v in hist27.items() if v})
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c, [PARENT, COMP, BYLEV, PREM])
    cur = c.cursor()
    man = []

    def hist_snap(qid, org):
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers
                       WHERE question_id=? AND org_id=?""", (STAMP + " r3sw15 pre-regate", qid, org))

    # ---- 1. parent re-gate ----
    for o in added:
        hist_snap(PARENT, o)
        nv = "; ".join(toks(p038[o]) + [TOKEN])
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (nv, PARENT, o))
        man.append([PARENT, o, "add-PMI-tick", ""])
    for o in trimmed:
        hist_snap(PARENT, o)
        nv = "; ".join(t for t in toks(p038[o]) if t != TOKEN)
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (nv, PARENT, o))
        man.append([PARENT, o, "remove-PMI-tick", ""])

    # ---- 2. children: delete trimmed rows, insert newly-added ----
    for o in trimmed:
        for qid in (COMP, BYLEV, PREM):
            hist_snap(qid, o)
            cur.execute("DELETE FROM answers WHERE question_id=? AND org_id=?", (qid, o))
    for o in added:
        cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,'',?,?)", (o, COMP, comp_vals[o], STAMP + " 09:00:00"))
        for j, L in enumerate(LEVELS):
            cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                        "VALUES (?,1,?,?,?,?)", (o, BYLEV, L, "Yes" if j < depths[o] else "No", STAMP + " 09:00:00"))
        for t in ("single", "partner", "family"):
            cur.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                        "VALUES (?,1,?,?,?,?)", (o, PREM, t, prem_vals[o][t], STAMP + " 09:00:00"))
    # premium ladder re-derived over the full 153 — UPDATE retained rows to keep medians exact
    for o in retained:
        hist_snap(PREM, o)
        for t in ("single", "partner", "family"):
            cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND matrix_row_id=?",
                        (prem_vals[o][t], PREM, o, t))
    man.append(["family", "", "added %d / trimmed %d / premium re-derived over 153" % (len(added), len(trimmed)), ""])

    # ---- 3. coherence asserts BEFORE commit ----
    assert book_hash(c, [PARENT, COMP, BYLEV, PREM]) == pre_hash, "NON-TARGET BOOK CHANGED"
    nh = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (PARENT,))
          if TOKEN in toks(v)}
    assert nh == new_haver, "parent tick-set != computed new haver set"
    comp_ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (COMP,))}
    bylev_ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (BYLEV,))}
    prem_ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (PREM,))}
    assert comp_ans == new_haver, "composition answerers != new haver set (%d vs 153)" % len(comp_ans)
    assert bylev_ans == new_haver, "by-level answerers != new haver set (%d vs 153)" % len(bylev_ans)
    assert prem_ans == new_haver | {thorn}, "premium answerers != havers+Thornbridge (%d)" % len(prem_ans)
    # by-level monotone prefixes for every org
    bl = {}
    for o, rid, v in c.execute("SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=?", (BYLEV,)):
        bl.setdefault(o, {})[rid] = v
    for o, r in bl.items():
        seq = [r[L] for L in LEVELS]; k = seq.count("Yes")
        assert seq == ["Yes"] * k + ["No"] * (7 - k), (o, seq)
    served = [round(100.0 * sum(1 for o in bl if bl[o][L] == "Yes") / 153, 1) for L in LEVELS]
    # composition + premium sanity (report, not hard-pin — additive keeps ≈ ruled)
    cv = [v for (v,) in c.execute("SELECT value FROM answers WHERE question_id=?", (COMP,))]
    comp_now = {opt: round(100.0 * sum(1 for v in cv if opt in toks(v)) / 153, 1) for opt in COMP_OPTS}
    prem_now = {}
    pr_hav = {}   # havers only (the re-derived ladder — must be exact); pr_all incl. Thornbridge
    pr_all = {}
    for o, rid, v in c.execute("SELECT org_id, matrix_row_id, value FROM answers WHERE question_id=?", (PREM,)):
        pr_all.setdefault(rid, []).append(float(v))
        if o != thorn:
            pr_hav.setdefault(rid, []).append(float(v))
    hav_med = {t: int(statistics.median(pr_hav[t])) for t in ("single", "partner", "family")}
    assert hav_med == {"single": 800, "partner": 1600, "family": 2000}, \
        "haver premium ladder drifted off the ruled anchor: %s" % hav_med
    prem_now = {t: int(statistics.median(pr_all[t])) for t in ("single", "partner", "family")}  # served (incl. Thornbridge)

    # ---- 4. config: refresh the two conditioned base captions (n moved), atomic ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    for qid in (COMP, BYLEV):
        cfg["metrics"][qid]["_r3sw15"] = "base re-gated to 153 PMI-havers (sector-gated parent)"
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw15_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric_id", "org_id", "action", "note"]); w.writerows(man)
    print(json.dumps({"applied": True, "haver": "130 -> 153 (+27 commercial / -3 charity / -1 public)",
                      "answers": c.execute("SELECT COUNT(*) FROM answers").fetchone()[0],
                      "coherence": "composition==153, by-level==153, premium==153+Thornbridge — ALL EXACT",
                      "bylevel_served_cliff": dict(zip([L[:5] for L in LEVELS], served)),
                      "composition_served": comp_now, "premium_medians": prem_now,
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
