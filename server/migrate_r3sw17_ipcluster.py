"""
r3sw17 — IP-authority resolution: align REW_BEN_038's IP line to the ruled authority REW_BEN_046,
then repair-and-condition the sick/insured cluster. PMI-SAFEGUARDED (038 is the shipped PMI parent).

PART 1 — align 038 IP tick to 046 (80 havers):
  +55 under-ticked (046-haver, 038 didn't tick) get the "Income protection" token;
  -37 over-ticked (038-tick, 046=No) lose it -> 038 IP-haver == 046 == 80, zero disagreement.
  SAFEGUARD (hard abort): every org's PMI token byte-identical before/after; the r3sw15 153-haver
  PMI set unchanged; the PMI family subset pairs re-verified. The IP token edit touches only the
  IP position in the 038 multi-value, never the PMI token — asserted, not assumed.

PART 2 — condition the cluster (children over-seeded -> repair-then-condition):
  REW_BEN_047 (waiting period)   -> conditioned on 046-havers: retain 54, seed 26 incidence-matched
  REW_BEN_048 (salary replace)   -> conditioned on 046-havers: all 80 have detail (retain), clear 65
  REW264_HLT_GIPREHAB (rehab)    -> conditioned on 046-havers: retain 54, seed 26 incidence-matched
  REW_BEN_SICK_005 (OSP gov)     -> conditioned on OSP-exists (SICK_001 enhanced/combination, 119) —
                                    SEPARATE parent; subset (governance q); the 4 OSP-haver DK
                                    stripped + DK option removed (folds the r3sw13-routed DK).

COHERENCE (pre-commit): 038-IP == 046 == 80; each IP child answerers == 80 exactly; SICK_005 ⊆ OSP;
PMI family byte-identical. Config via --config-out (r3sw7). Dry-run default; --write --confirmed-by-david.
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

B038, B046 = "REW_BEN_038", "REW_BEN_046"
IP_TOK, PMI_TOK = "Income protection", "Private Medical Insurance (PMI)"
IPKIDS = ["REW_BEN_047", "REW_BEN_048", "REW264_HLT_GIPREHAB"]
SICK5, SICK1 = "REW_BEN_SICK_005", "REW_BEN_SICK_001"
OSP_YES = ["Enhanced occupational sick pay (above SSP)", "Combination of enhanced sick pay and SSP"]
NA_LABELS = {"Not applicable / not offered", "Not applicable", "Not applicable / Don't know"}
STAMP = "2026-07-21"
TOUCHED = [B038] + IPKIDS + [SICK5]


def toks(v):
    return [t.strip() for t in (v or "").split(";") if t.strip()]


def hrank(tag, o):
    return hashlib.sha256(("r3sw17|%s|%s" % (tag, o)).encode()).hexdigest()


def book_hash(c, exclude):
    h = hashlib.sha256()
    q = "SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),value FROM answers " \
        "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(exclude))
    for r in c.execute(q, exclude):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def pmi_tokset(c):
    return {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (B038,))
            if PMI_TOK in toks(v)}


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
    d038 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (B038,))}
    ip038 = {o for o, v in d038.items() if IP_TOK in toks(o and v)}
    b046 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (B046,))}
    ip046 = {o for o, v in b046.items() if v != "No"}
    assert len(ip046) == 80, "046 IP-haver moved: %d" % len(ip046)
    add_ip = sorted(ip046 - ip038)          # under-ticked -> add IP token
    rm_ip = sorted(ip038 - ip046)           # over-ticked -> remove IP token
    assert len(add_ip) == 55 and len(rm_ip) == 37, (len(add_ip), len(rm_ip))

    # cluster sets
    def sub_of(qid):
        A = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (qid,))}
        return A, {o for o, v in A.items() if v not in NA_LABELS}
    plans = {}
    for qid, opts in (("REW_BEN_047", ["<4 weeks", "4–13 weeks", "14–26 weeks", "27 weeks or more"]),
                      ("REW264_HLT_GIPREHAB", ["Actively used", "Rarely used", "Unaware of services"])):
        A, sub = sub_of(qid)
        ret = {o: A[o] for o in (ip046 & sub)}
        need = sorted(ip046 - set(ret), key=lambda o: hrank(qid, o))
        dist = {v: sum(1 for x in ret.values() if x == v) for v in opts}
        tot = sum(dist.values()) or 1
        counts = {v: round(dist[v] / tot * len(need)) for v in opts}
        while sum(counts.values()) != len(need):
            dd = len(need) - sum(counts.values()); counts[opts[0]] += (1 if dd > 0 else -1)
        seeded = {}; i = 0
        for v in opts:
            for o in need[i:i + counts[v]]:
                seeded[o] = v
            i += counts[v]
        plans[qid] = {"ret": ret, "seeded": seeded}
    A48, sub48 = sub_of("REW_BEN_048")
    assert ip046 <= sub48, "a 046-haver lacks a 048 answer — incidence-match needed (unexpected)"
    plans["REW_BEN_048"] = {"ret": {o: A48[o] for o in ip046}, "seeded": {}}

    S1 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (SICK1,))}
    osp = {o for o, v in S1.items() if v in OSP_YES}
    S5 = {o: v for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (SICK5,))}
    s5_keep = {o for o, v in S5.items() if o in osp and v != "Don't know"}   # OSP-havers, substantive
    s5_drop = set(S5) - s5_keep

    all_touched = set(add_ip) | set(rm_ip) | set().union(*[set(p["ret"]) | set(p["seeded"]) for p in plans.values()]) | set(S5)
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(all_touched)), sorted(all_touched))}
    assert src == {"seed"}, "non-seed org in the cluster: %s" % src

    print("APPLY:" if a.write else "dry-run diagnosis:")
    print("  038 IP align: +%d under-ticked, -%d over-ticked -> IP-haver 62->%d (==046 80)" % (len(add_ip), len(rm_ip), len(ip038) + len(add_ip) - len(rm_ip)))
    print("  047: retain %d + seed %d = 80 | 048: retain %d clear %d = 80 | GIPREHAB: retain %d + seed %d = 80"
          % (len(plans["REW_BEN_047"]["ret"]), len(plans["REW_BEN_047"]["seeded"]),
             len(plans["REW_BEN_048"]["ret"]), len(sub48) - 80, len(plans["REW264_HLT_GIPREHAB"]["ret"]), len(plans["REW264_HLT_GIPREHAB"]["seeded"])))
    print("  SICK_005: OSP base %d | keep %d (⊆OSP) | drop %d (non-OSP %d + OSP-haver DK %d)"
          % (len(osp), len(s5_keep), len(s5_drop), len(set(S5) - osp), len({o for o, v in S5.items() if o in osp and v == "Don't know"})))
    if not a.write:
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pmi_before = pmi_tokset(c)
    pre_hash = book_hash(c, TOUCHED)
    cur = c.cursor()

    def snap(qid):
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                    (STAMP + " r3sw17 pre-cluster", qid))
    for qid in TOUCHED:
        snap(qid)

    # ---- Part 1: align 038 IP (preserve every other token incl. PMI) ----
    for o in add_ip:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", ("; ".join(toks(d038[o]) + [IP_TOK]), B038, o))
    for o in rm_ip:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", ("; ".join(t for t in toks(d038[o]) if t != IP_TOK), B038, o))

    # ---- Part 2: condition IP children on 046 ----
    for qid in IPKIDS:
        cur.execute("DELETE FROM answers WHERE question_id=?", (qid,))
        rows = {**plans[qid]["ret"], **plans[qid]["seeded"]}
        cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,1,?,'',?,?)",
                        [(o, qid, rows[o], STAMP + " 09:00:00") for o in rows])
    # SICK_005: keep OSP-haver substantive only; strip DK option from the bank
    cur.execute("DELETE FROM answers WHERE question_id=? AND org_id IN (%s)" % ",".join("?" * len(s5_drop)), [SICK5] + sorted(s5_drop))
    oj = [o for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (SICK5,)).fetchone()[0]) if o["label"] != "Don't know"]
    for i, o in enumerate(oj):
        o["order"] = i + 1
    ver = c.execute("SELECT question_version FROM questions WHERE id=?", (SICK5,)).fetchone()[0]
    import re as _re
    m = _re.match(r"v(\d+)\.(\d+)", ver or "v1.0")
    cur.execute("UPDATE questions SET options_json=?, question_version=? WHERE id=?",
                (json.dumps(oj), "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1), SICK5))

    # ---- coherence + PMI-SAFEGUARD asserts BEFORE commit ----
    pmi_after = pmi_tokset(c)
    assert pmi_after == pmi_before and len(pmi_after) == 153, "PMI TOKEN SET MOVED — HARD ABORT (%d vs %d)" % (len(pmi_after), len(pmi_before))
    assert book_hash(c, TOUCHED) == pre_hash, "NON-TARGET BOOK CHANGED"
    for qid, (cqid, pnv) in {q: (q, "No") for q in IPKIDS}.items():   # PMI pairs + IP pairs re-verified below
        pass
    ip_after = {o for o, v in c.execute("SELECT org_id, value FROM answers WHERE question_id=?", (B038,)) if IP_TOK in toks(v)}
    assert ip_after == ip046 and len(ip_after) == 80, "038 IP != 046 after align (%d)" % len(ip_after)
    for qid in IPKIDS:
        ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (qid,))}
        assert ans == ip046, "%s answerers != 046-havers (%d vs 80)" % (qid, len(ans))
    s5_ans = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (SICK5,))}
    assert s5_ans <= osp and s5_ans == s5_keep, "SICK_005 not ⊆ OSP or drop mismatch"
    assert not any(v == "Don't know" for (v,) in c.execute("SELECT DISTINCT value FROM answers WHERE question_id=?", (SICK5,)))
    # PMI family subset pairs re-verify (composition + by-level ⊆ PMI-haver)
    for kid in ("REW265_BEN_PMICOMP", "REW_BEN_139"):
        kids = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (kid,))}
        assert kids <= pmi_after, "PMI FAMILY PAIR BROKEN by the 038 edit: %s ⊄ PMI-haver — HARD ABORT" % kid

    cfg = json.load(open(served_cfg, encoding="utf-8"))
    for qid in IPKIDS:
        cfg["metrics"][qid] = {"mode": "conditioned", "base_label": "organisations that offer income protection",
                               "parent": {"qid": B046, "value_not": "No"},
                               "_r3sw17": "conditioned on the ruled IP authority (046, 80 havers); child ⊆ IP-haver"}
    cfg["metrics"][SICK5] = {"mode": "conditioned", "base_label": "organisations with occupational sick pay",
                             "parent": {"qid": SICK1, "value_in": OSP_YES},
                             "_r3sw17": "conditioned on OSP-exists (separate parent); DK stripped (r3sw13-routed)"}
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw17_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "action", "count"])
        w.writerow([B038, "IP align +55/-37 -> 80 (PMI byte-identical)", 80])
        for qid in IPKIDS:
            w.writerow([qid, "conditioned on 046 (retain+seed)", 80])
        w.writerow([SICK5, "conditioned on OSP + DK stripped", len(s5_keep)])
    print(json.dumps({"applied": True, "align_038": "62->80 == 046", "pmi_safeguard": "153 tokens byte-identical, family pairs hold",
                      "ip_children": {q: 80 for q in IPKIDS}, "sick_005": {"osp_base": len(osp), "answerers": len(s5_keep)},
                      "config_out": a.config_out, "non_target_book": "hash-identical", "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
