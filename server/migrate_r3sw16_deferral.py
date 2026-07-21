"""
r3sw16 — DEFERRAL parent re-anchor (listing/FS gate) + child re-condition (ruled).

The parent REW_INC_069 claims 82% defer (182 orgs), provably FLAT across sector and size, with
36 orgs "deferring" that have no bonus scheme. Re-anchor to the sourced listing/FS-gated rate
(r3sw16 research): deferral is a LISTED-COMPANY / REGULATED-FS phenomenon — gated on
ownership_type + industry, NEVER on size.
  FS industry 70% (PRA/FCA anchor blended) · Listed PLC 90% (Deloitte FTSE, exec grain) ·
  PE-backed 35% (middle) · general (private/subsidiary/public/charity/mutual) 12% (EST).
Within each gate segment: PREFER orgs with real existing child vehicle detail (retain the
coherent), then latent-ranked — hits the segment target ~50 deferrers, concentrated listed/FS/PE.

SEQUENCE (one coherence-gated diff):
  1. parent re-seed: deferrer set -> parent-Yes flavour (narrow exec/senior-concentrated);
     everyone else (incl. the 36 no-bonus, forced) -> "No deferral"; Varies resolved by the gate.
  2. child re-condition (REW263_INC_DEFERRAL conditioned on the deferrer set): delete ALL current
     child rows; insert one per deferrer — retained keep their vehicle, new incidence-matched to
     the retained vehicle spread and SECTOR-PLACED (FS/listed skew shares/multi-year; fixes the
     child's FS blind-spot). Child declared conditioned in applicable_bases.
  3. two-level chain coherence (pre-commit): parent-Yes set == deferrer set; child answerers ==
     deferrer set; zero parent-Yes with no-bonus; zero Varies. Subset pairs: child ⊆ parent-Yes
     ⊆ has-bonus. Verdict status unchanged (both Practice — prevalence, no market verdict).
Config via --config-out (r3sw7). Dry-run default; apply needs --write --confirmed-by-david.
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

PARENT, CHILD, GRAND = "REW_INC_069", "REW263_INC_DEFERRAL", "REW_INC_103"
RATE = {"FS": 0.70, "listed": 0.90, "PE": 0.35, "general": 0.12}
YESVALS = ["Exec only", "Senior leadership only", "Wider population"]
FLAV_TGT = {"Exec only": 0.45, "Senior leadership only": 0.40, "Wider population": 0.15}  # narrow, exec-concentrated
VEHICLES = ["1yr cash", "Multi-year cash", "Shares/equity deferral"]
STAMP = "2026-07-21"


def segn(ind, own):
    if ind.startswith("Financial"): return "FS"
    if own == "Public Listed (PLC)": return "listed"
    if own == "PE-backed": return "PE"
    return "general"


def hrank(tag, o):
    return hashlib.sha256(("r3sw16|%s|%s" % (tag, o)).encode()).hexdigest()


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
    orgs = {r[0]: (r[1] or "", r[2] or "", r[3] or "")
            for r in c.execute("SELECT org_id, industry, fte_band, ownership_type FROM orgs")}
    P = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (PARENT,)))
    G = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (GRAND,)))
    Cur = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (CHILD,)))
    nobonus = {o for o, v in G.items() if v == "None"}
    havers = {o for o in P if o not in nobonus}
    csub = {o for o, v in Cur.items() if v in VEHICLES}
    assert len(P) == 220 and abs(sum(1 for v in P.values() if v in YESVALS) - 182) <= 2

    # ---- gate selection (GATE READS ownership+industry ONLY — size never enters) ----
    seg = {}
    for o in havers:
        seg.setdefault(segn(*[orgs[o][i] for i in (0, 2, 1)][:2]) if False else segn(orgs[o][0], orgs[o][2]), []).append(o)
    deferrers, retained, newveh = set(), set(), set()
    for s, members in seg.items():
        k = round(RATE[s] * len(members))
        ranked = sorted(members, key=lambda o: (o not in csub, -latent(o, PROF), hrank("pick", o)))
        pick = set(ranked[:k]); deferrers |= pick
        retained |= (pick & csub); newveh |= (pick - csub)
    non_def = set(P) - deferrers
    assert not (deferrers & nobonus), "a no-bonus org was selected as a deferrer"
    src = {r[0] for r in c.execute("SELECT DISTINCT COALESCE(source,'x') FROM orgs WHERE org_id IN (%s)"
                                   % ",".join("?" * len(P)), sorted(P))}
    assert src == {"seed"}, "non-seed org in the DEFERRAL set: %s" % src

    # ---- parent Yes-flavour: retain existing Yes flavour; assign the rest to the narrow target ----
    flav = {}
    need = {k: round(v * len(deferrers)) for k, v in FLAV_TGT.items()}
    # DETERMINISTIC order (never iterate the set directly — order must be reproducible
    # across throwaway and live for the post-write match to hold)
    for o in sorted(deferrers, key=lambda o: hrank("flavret", o)):  # retain existing Yes flavour
        if P.get(o) in YESVALS and need.get(P[o], 0) > 0:
            flav[o] = P[o]; need[P[o]] -= 1
    pool = sorted(deferrers - set(flav), key=lambda o: hrank("flav", o))
    for lab in YESVALS:
        for o in pool[:max(0, need[lab])]:
            flav[o] = lab
        pool = pool[max(0, need[lab]):]
    for o in pool:                            # rounding remainder
        flav[o] = "Senior leadership only"
    assert set(flav) == deferrers

    # ---- child vehicles: retained keep; new incidence-matched + sector-placed (rich to FS/listed) ----
    vspread = {v: sum(1 for o in retained if Cur[o] == v) for v in VEHICLES}
    tot = sum(vspread.values()) or 1
    veh = {o: Cur[o] for o in retained}
    new_sorted = sorted(newveh, key=lambda o: (segn(orgs[o][0], orgs[o][2]) not in ("FS", "listed"), hrank("veh", o)))
    counts = {v: round(vspread[v] / tot * len(newveh)) for v in VEHICLES}
    while sum(counts.values()) != len(newveh):
        d = len(newveh) - sum(counts.values()); counts["Shares/equity deferral"] += (1 if d > 0 else -1)
    i = 0
    for v in ("Shares/equity deferral", "Multi-year cash", "1yr cash"):   # rich vehicles to FS/listed first
        for o in new_sorted[i:i + counts[v]]:
            veh[o] = v
        i += counts[v]
    assert set(veh) == deferrers

    print("APPLY:" if a.write else "dry-run diagnosis:")
    for s in ("FS", "listed", "PE", "general"):
        print("  %-8s %3d havers x %.0f%% -> %d deferrers" % (s, len(seg[s]), RATE[s]*100, round(RATE[s]*len(seg[s]))))
    print("  DEFERRERS %d (from 182) | retained-vehicle %d | new-vehicle %d | no-bonus forced-No %d"
          % (len(deferrers), len(retained), len(newveh), len(nobonus)))
    if not a.write:
        pv = {o for o, v in P.items() if v == "Varies"}
        print("  Varies(15): Yes %d / No %d | FS deferrers %d (was 1) | flavour %s"
              % (len(pv & deferrers), len(pv - deferrers), sum(1 for o in deferrers if orgs[o][0].startswith("Financial")),
                 {k: sum(1 for x in flav.values() if x == k) for k in YESVALS}))
        print("dry-run complete — pass --write --confirmed-by-david to apply"); return
    if not a.confirmed:
        print("REFUSED: --write without --confirmed-by-david"); sys.exit(2)

    pre_hash = book_hash(c, [PARENT, CHILD])
    cur = c.cursor()

    def snap(qid):
        cur.execute("""INSERT INTO answers_history (org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at)
                       SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=?""",
                    (STAMP + " r3sw16 pre-reanchor", qid))
    snap(PARENT); snap(CHILD)
    for o in deferrers:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (flav[o], PARENT, o))
    for o in non_def:
        cur.execute("UPDATE answers SET value='No deferral' WHERE question_id=? AND org_id=?", (PARENT, o))
    cur.execute("DELETE FROM answers WHERE question_id=?", (CHILD,))
    cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                    "VALUES (?,1,?,'',?,?)", [(o, CHILD, veh[o], STAMP + " 09:00:00") for o in deferrers])

    # ---- coherence asserts BEFORE commit ----
    assert book_hash(c, [PARENT, CHILD]) == pre_hash, "NON-TARGET BOOK CHANGED"
    pnow = dict(c.execute("SELECT org_id, value FROM answers WHERE question_id=? AND value!=''", (PARENT,)))
    p_yes = {o for o, v in pnow.items() if v in YESVALS}
    assert p_yes == deferrers, "parent-Yes set != deferrer set"
    assert not any(v == "Varies" for v in pnow.values()), "Varies survived"
    assert not (p_yes & nobonus), "parent-Yes with no bonus (grandparent=None)"
    cnow = {o for (o,) in c.execute("SELECT DISTINCT org_id FROM answers WHERE question_id=?", (CHILD,))}
    assert cnow == deferrers, "child answerers != deferrer set (%d vs %d)" % (len(cnow), len(deferrers))
    assert all(v in VEHICLES for (v,) in c.execute("SELECT DISTINCT value FROM answers WHERE question_id=?", (CHILD,)))
    got_veh = {v: c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND value=?", (CHILD, v)).fetchone()[0] for v in VEHICLES}

    # ---- config: declare the child conditioned ----
    cfg = json.load(open(served_cfg, encoding="utf-8"))
    cfg["metrics"][CHILD] = {"mode": "conditioned", "base_label": "organisations that defer bonuses",
                             "parent": {"qid": PARENT, "value_in": YESVALS},
                             "_r3sw16": "conditioned on the listing/FS-gated deferrer set (~50); child ⊆ parent-Yes ⊆ has-bonus"}
    cfg_text = json.dumps(cfg, indent=1, ensure_ascii=False)
    c.commit()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.config_out)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cfg_text)
    os.replace(tmp, a.config_out)

    man_dir = ROOT if is_live else os.path.dirname(os.path.abspath(a.db))
    man_path = os.path.join(man_dir, "r3sw16_seed_manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["set", "count", "note"])
        w.writerow([PARENT + " defer", len(deferrers), "re-anchored from 182 (listing/FS gate)"])
        w.writerow([CHILD + " conditioned", len(deferrers), "retained %d + new-vehicle %d" % (len(retained), len(newveh))])
    print(json.dumps({"applied": True, "deferrers": len(deferrers), "from": 182,
                      "breakdown": {s: round(RATE[s]*len(seg[s])) for s in RATE},
                      "flavour": {k: sum(1 for x in flav.values() if x == k) for k in YESVALS},
                      "child_vehicles": got_veh, "no_bonus_forced_no": len(nobonus),
                      "coherence": "parent-Yes==child==%d, zero no-bonus-defer, zero Varies — chain locked" % len(deferrers),
                      "config_out": a.config_out, "non_target_book": "hash-identical",
                      "manifest": man_path}, indent=2))


if __name__ == "__main__":
    main()
