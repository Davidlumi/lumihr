#!/usr/bin/env python3
"""Add 50 new synthetic companies to the seed pool (2026-08-14, David) — full lineage.

Grows the benchmark pool 220 -> 270 so sector/size sample searches are richer, with answers that
are FAITHFUL to each new org's sector and size (the launch-QA requirement).

Every coherence-closure — free and gated alike — is cloned from a real SAME-(industry, fte_band)
donor, a different donor per closure, so each new org is a mosaic that is sector- and size-faithful
(a large org clones a large donor; a public-sector org clones a public-sector donor -> DB pension,
not DC) and internally coherent (each closure is one real org's real joint answer). Proportional
same-cell cloning also preserves the register marginals: a size-conditioned metric (sick pay 17.5%
SME / 63% large) is reproduced because same-size donors are drawn in the new orgs' own size mix.
Donors are ALL 220 classified seed orgs (not the registry 158) so the aggregate matches the
full-pool targets. FREE numeric metrics get a small jitter; anchored values are cloned exactly.
Different donors per closure -> no two orgs share an answer vector.

Two targeted refinements sit on top of the same-cell base:
  * Industry-keyed band_distributions gradients (REW_INC_103, parent of the bonus-detail family)
    are RE-DRAWN per real industry to the band's ruled shape, because a 2-3-org industry drifts off
    that shape by same-cell sampling variance alone. Whole-closure clone keeps the subset coherence.
  * New orgs get an org_profiles_inferred.json row (Industry + FTE_Band) so the gate bands them by
    their real sector — HR_Maturity is omitted so the maturity-anchored gradients keep skipping them.

Adding orgs necessarily perturbs the 8 settled-frozen SHARE anchors by up to ~0.2pp (0.1pp is
0.27 of one org at n=270 — a "don't touch" guard, not a data threshold), so this batch RE-RATIFIES
frozen_targets.json to the 270-org store (David-approved 2026-08-14).

Extends the WHOLE provenance chain so all gates stay green:
  * lumi.db  — orgs rows + answers
  * data/responses/*.csv  — 50 new response files (L1 ground truth)
  * data/book_baseline.json  — re-recorded row hash
  * identity.db org_register — 50 twin rows (identity_recon)
  * org_profiles_inferred.json — 50 profile rows (Industry + FTE_Band) so keyed bands resolve
  * frozen_targets.json      — settled anchors re-ratified at n=270 (separate, David-signed edit)

Deterministic sha256. INSERT-only. After --write, re-aggregate:
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")

    python3 server/migrate_add50_orgs_2026_08_14.py                          # dry run
    python3 server/migrate_add50_orgs_2026_08_14.py --write --confirmed-by-david
"""
import os, sys, json, csv, sqlite3, hashlib, uuid, re
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(ROOT))
from reseed_engine import canon_industry   # same industry->band canon the freeze gate uses
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
IDB = os.environ.get("LUMI_IDENTITY_DB") or os.path.join(ROOT, "identity.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
PROF = os.path.join(ROOT, "org_profiles_inferred.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
N_NEW = 50

PLACE = ["Alder", "Brack", "Cald", "Dun", "Elder", "Fen", "Gild", "Haw", "Kes", "Lyn", "Mar", "Nor",
         "Oak", "Pen", "Quar", "Rye", "Stan", "Thor", "Vale", "Wren", "Ash", "Black", "Grey", "Red"]
PLACE2 = ["bridge", "ford", "wick", "worth", "mere", "dale", "field", "haven", "gate", "cross", "moor", "bourne"]
SECTORWORD = {"Retail & Consumer Goods": ["Retail", "Stores", "Brands", "Consumer"],
              "Logistics, Transport & Distribution": ["Logistics", "Freight", "Distribution", "Transport"],
              "Hospitality, Leisure & Travel": ["Leisure", "Hospitality", "Travel", "Hotels"],
              "Manufacturing & Engineering": ["Manufacturing", "Engineering", "Industries", "Works"],
              "Construction & Infrastructure": ["Construction", "Infrastructure", "Build", "Civils"],
              "Technology, Software & Digital": ["Technologies", "Digital", "Software", "Systems"],
              "Professional Services": ["Partners", "Advisory", "Consulting", "Services"],
              "Financial Services": ["Financial", "Capital", "Assurance", "Holdings"],
              "Healthcare & Life Sciences": ["Healthcare", "Care", "Health", "Sciences"],
              "Public Sector & Government": ["Authority", "Trust", "Council Services", "Agency"],
              "Education (Public & Private)": ["Education", "Learning", "Academies", "College Group"],
              "Media, Communications & Creative Industries": ["Media", "Communications", "Studios", "Creative"],
              "Energy, Utilities & Environmental Services": ["Energy", "Utilities", "Power", "Environmental"],
              "Charity, Non-Profit & Social Enterprise": ["Foundation", "Trust", "Community", "Care"]}
SUFFIX = ["Ltd", "plc", "Group", "Group plc", "Holdings Ltd", "UK Ltd", "& Co Ltd"]


def h(*p):
    return int(hashlib.sha256("|".join(str(x) for x in p).encode()).hexdigest()[:12], 16)


def pick(seq, *k):
    seq = list(seq)
    return seq[h(*k) % len(seq)] if seq else None


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def gen_name(industry, i, taken):
    words = SECTORWORD.get(industry, ["Group"])
    for attempt in range(20):
        nm = "%s%s %s %s" % (pick(PLACE, "p1", i, attempt), pick(PLACE2, "p2", i, attempt),
                             pick(words, "sw", i, attempt), pick(SUFFIX, "sfx", i, attempt))
        if norm(nm) not in taken:
            taken.add(norm(nm)); return nm
    nm = "%s%s Group %d Ltd" % (pick(PLACE, "p1", i), pick(PLACE2, "p2", i), i)
    taken.add(norm(nm)); return nm


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    qrows = {r["id"]: dict(r) for r in c.execute(
        "SELECT id, type, text, superpower, sub_power, category FROM questions")}
    qtype = {q: qrows[q]["type"] for q in qrows}

    gm = json.load(open(os.path.join(ROOT, "generated_marginals.json")))
    frozen = set(json.load(open(os.path.join(ROOT, "frozen_targets.json"))))
    # anchor tables for the marginal-matched donor mix (mirror qa_plausibility's checks)
    ORDS = json.load(open(os.path.join(ROOT, "ruled_orderings.json")))["orderings"]
    FROZDICT = json.load(open(os.path.join(ROOT, "frozen_targets.json")))
    MARGENT = gm["marginals"]; MGRADENT = gm.get("maturity_gradients", {})
    RDISTENT = gm.get("ruled_distributions", {})
    # GATED = anything the freeze / marginal / gradient / ruled machinery pins
    gated = set(frozen) | set(gm["marginals"]) | set(gm.get("maturity_gradients", {})) \
        | set(gm.get("ruled_distributions", {})) | set(gm.get("multiselect_incidence", {})) | set(gm.get("floors", {}))
    coh_metrics = set()
    for p in gm["coherence_pairs"]:
        if p.get("child"): coh_metrics.add(p["child"])
        if p.get("parent"): coh_metrics.add(p["parent"])
    # coherence-closure over pairs
    par = {}
    def find(x):
        par.setdefault(x, x)
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for q in qrows: par.setdefault(q, q)
    for p in gm["coherence_pairs"]:
        if p.get("child") and p.get("parent"): par[find(p["child"])] = find(p["parent"])
    # a metric is "protected" (comes from the single clone-base) if gated OR shares a closure with a gated metric
    closure = defaultdict(set)
    for q in qrows: closure[find(q)].add(q)
    protected = set()
    for root, members in closure.items():
        if members & gated or members & coh_metrics and (members & gated):
            protected |= members
    protected |= gated | coh_metrics     # keep every coherence-linked metric whole from the base too

    # ---- donors: ALL classified seed orgs (220 = 158 registry + 62 classified), with answers.
    #      The whole classified pool — not the registry-matched 158 — because a size/sector-
    #      conditioned register marginal is calibrated against the FULL pool; cloning from the
    #      registry subset alone pulls new orgs to the registry rate and drifts the aggregate.
    #      classified=0 is only the demo fixture, correctly excluded. ----
    donors = [dict(r) for r in c.execute(
        "SELECT org_id, industry, subsector, fte_band, hq_region, similarity_vector_json "
        "FROM orgs WHERE classified=1")]
    by_cell = defaultdict(list); by_ind = defaultdict(list); by_fte = defaultdict(list)
    for d in donors:
        by_cell[(d["industry"], d["fte_band"])].append(d["org_id"])
        by_ind[d["industry"]].append(d["org_id"]); by_fte[d["fte_band"]].append(d["org_id"])
    dset = {d["org_id"] for d in donors}; dmap = {d["org_id"]: d for d in donors}
    dinfo = {d["org_id"]: (d["industry"], d["fte_band"]) for d in donors}
    ans = defaultdict(lambda: defaultdict(list))
    qm = ",".join("?" * len(dset))
    for r in c.execute(f"SELECT org_id, question_id, matrix_row_id, value, submitted_at FROM answers "
                       f"WHERE snapshot_id=1 AND org_id IN ({qm})", list(dset)):
        ans[r["org_id"]][r["question_id"]].append([r["matrix_row_id"], r["value"], r["submitted_at"]])

    # free-block signal (sector vs size) for donor-pool choice on the shuffled blocks
    free_roots = [root for root, members in closure.items() if not (members & protected)]

    # gated closures: every coherence-closure that contains a gated metric (freeze/marginal/gradient/
    # ruled/coherence). Their joint answer-tuples are REPLICATED from the existing pool across the 50,
    # so every marginal + the coherence joint + multi-select incidence hold by construction.
    gated_roots = sorted({find(q) for q in (gated | coh_metrics)})
    gated_qids = set().union(*[closure[r] for r in gated_roots]) if gated_roots else set()

    # ---- assign 50 profiles mirroring the classified mix (proportional by industry) ----
    profs = [(d["industry"], d["subsector"], d["fte_band"], d["hq_region"], d["org_id"]) for d in donors]
    taken_names = {norm(r[0]) for r in c.execute("SELECT name FROM orgs WHERE name IS NOT NULL")}
    try:
        ic = sqlite3.connect(IDB); ic.row_factory = sqlite3.Row
        taken_names |= {r["normalized_name"] for r in ic.execute("SELECT normalized_name FROM org_register")}
    except Exception:
        ic = None
    # proportional-by-INDUSTRY allocation (largest remainder) so per-industry keyed metrics + overall
    # shares are both preserved when the gated closures are replicated within each industry.
    ind_counts = Counter(d["industry"] for d in donors)
    tot_don = sum(ind_counts.values())
    quota = {k: v / tot_don * N_NEW for k, v in ind_counts.items()}
    per_ind = {k: int(q) for k, q in quota.items()}
    rem = N_NEW - sum(per_ind.values())
    for k in sorted(quota, key=lambda x: -(quota[x] - int(quota[x])))[:rem]:
        per_ind[k] += 1
    ind_seq = []
    for k, n_ in per_ind.items():
        ind_seq += [k] * n_
    new = []
    for i in range(N_NEW):
        ind = ind_seq[i]
        _pi, sub, fte, reg, _pd = pick([p for p in profs if p[0] == ind], "prof", i)   # profile from same industry
        oid = str(uuid.UUID(int=h("uuid", i) << 68 | h("uuid2", i)))  # deterministic UUID
        base = pick(by_cell.get((ind, fte)) or by_ind.get(ind) or list(dset), "base", oid)
        new.append({"org_id": oid, "industry": ind, "subsector": sub, "fte_band": fte, "hq_region": reg,
                    "base": base, "name": gen_name(ind, i, taken_names)})

    # ---- assemble answers: clone EVERY coherence-closure (free + gated) from a SAME-(industry,
    #      fte_band) donor — a different donor per closure, so each new org is a mosaic that is
    #      sector- AND size-faithful (a large org clones a large donor; a public-sector org clones
    #      a public-sector donor -> DB pension, not DC) and internally coherent (each closure is
    #      one real org's real joint answer). Proportional same-cell cloning also preserves the
    #      register marginals: a size-conditioned metric (sick pay 17.5% SME / 63% large) is
    #      reproduced because same-size donors are drawn in the new orgs' own size mix — the reason
    #      an earlier global marginal-match was dropped (it hit the aggregate targets but sent
    #      public-sector orgs DC pensions and mid-large orgs off their governance cohort). FREE
    #      numeric metrics get a small jitter for novelty; anchored/gated values are cloned EXACTLY
    #      so the ruled distributions hold. Different donors per closure -> no shared answer vector.
    NUMERIC = {"numeric", "number", "currency", "percent", "percentage"}
    free_set = set(free_roots)
    na = {}    # oid -> {qid: [[mr,val,sub],...]}
    for o in new:
        oid, ind, fte = o["org_id"], o["industry"], o["fte_band"]
        pool0 = by_cell.get((ind, fte)) or by_ind.get(ind) or sorted(dset)
        rows = {}
        for root in sorted(closure):
            qs = closure[root]
            cand = [d for d in pool0 if any(qid in ans[d] for qid in qs)] \
                or [d for d in by_ind.get(ind, []) if any(qid in ans[d] for qid in qs)] \
                or [d for d in sorted(dset) if any(qid in ans[d] for qid in qs)]
            if not cand: continue
            donor = cand[h("clone", oid, root) % len(cand)]
            jit = root in free_set
            for qid in qs:
                if qid in ans[donor]:
                    cp = [list(x) for x in ans[donor][qid]]
                    if jit and qtype.get(qid) in NUMERIC:
                        for row in cp:
                            m = re.match(r"^\s*([-+]?\d*\.?\d+)(.*)$", row[1] or "")
                            if m:
                                v = float(m.group(1)); j = ((h("jit", oid, qid, row[0]) % 7) - 3)
                                nv = v + j if v > 20 else round(v + j * 0.1, 2)
                                if nv > 0: row[1] = (("%d" % nv) if float(nv).is_integer() else ("%.2f" % nv)) + m.group(2)
                    rows[qid] = cp
        na[oid] = rows
    fixed = {r: len(closure[r]) for r in gated_roots}   # gated closures now clone same-cell like the rest

    # ---- keyed-gradient correction (per REAL industry) --------------------------------------
    # A closure carrying an Industry-keyed band_distributions gradient (REW_INC_103, the parent
    # of the whole bonus-detail family) is checked by qa_plausibility per industry band vs the
    # ruled shape (special band for Charity / Public Sector, else _default). Same-cell random
    # cloning leaves small industries (2-3 new orgs) off that shape by sampling variance alone —
    # e.g. two new Energy orgs both landing '50-74%'. So for these closures we RE-DRAW per real
    # industry: apportion the industry's new orgs across the keyed values to the band target
    # (largest remainder), then clone a whole same-industry donor holding the apportioned value —
    # coherence-safe (one real org's real joint answer), and now on-shape by construction.
    keyed_bd = {q for q, e in gm.get("maturity_gradients", {}).items()
                if e.get("band_distributions") and e.get("key") == "Industry"}
    def _band_dist(qid, industry):
        # mirror the gate: bds.get(canon_industry(industry)) or bds.get("_default"); None -> band
        # not declared for this industry -> the gate skips it, so we skip it too.
        bds = gm["maturity_gradients"][qid]["band_distributions"]
        return bds.get(canon_industry(industry or "")) or bds.get("_default")
    new_by_realind = defaultdict(list)
    for o in new: new_by_realind[o["industry"]].append(o)
    for kq in keyed_bd:
        qs = closure[find(kq)]
        for industry, group in new_by_realind.items():
            dist = _band_dist(kq, industry)
            if not dist: continue
            quota = {l: dist[l] / 100.0 * len(group) for l in dist}
            alloc = {l: int(quota[l]) for l in dist}
            r = len(group) - sum(alloc.values())
            for l in sorted(dist, key=lambda x: (-(quota[x] - int(quota[x])), x))[:max(0, r)]: alloc[l] += 1
            seq = []
            for l, n_ in alloc.items(): seq += [l] * n_
            same_ind = by_ind.get(industry, [])
            for o, val in zip(group, seq):
                pool = [d for d in same_ind
                        if any(mr == "" and v.strip() == val for (mr, v, _s) in ans[d].get(kq, []))] \
                    or [d for d in sorted(dset)
                        if any(mr == "" and v.strip() == val for (mr, v, _s) in ans[d].get(kq, []))]
                if not pool: continue
                pref = [d for d in pool if dinfo.get(d, (None, None))[1] == o["fte_band"]] or pool
                donor = pref[h("keyed", o["org_id"], kq, val) % len(pref)]
                for qid in qs: na[o["org_id"]].pop(qid, None)   # replace the whole closure atomically
                for qid in qs:                                  # (a partial overwrite would mix two
                    if qid in ans[donor]:                       #  donors and break the bonus-family
                        na[o["org_id"]][qid] = [list(x) for x in ans[donor][qid]]   # subset coherence)


    total_answers = sum(len(l) for o in new for l in na[o["org_id"]].values())
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d new orgs, %d answers" % (N_NEW, total_answers))
    print("  protected(gated+coherence) metrics: %d | free shuffled: %d" % (len(protected), len(qrows) - len(protected)))
    print("  sector spread: " + ", ".join("%s=%d" % (k, v) for k, v in Counter(o["industry"] for o in new).most_common(5)))
    print("  fte spread:    " + ", ".join("%s=%d" % (k, v) for k, v in sorted(Counter(o["fte_band"] for o in new).items())))
    print("  gated closures replicated: %d (%d metrics)" % (len(fixed), sum(fixed.values())))
    print("  sample names: " + ", ".join(o["name"] for o in new[:4]))

    if not WRITE:
        c.close()
        if ic: ic.close()
        return

    # ---- write lumi.db ----
    for o in new:
        b = dmap[o["base"]]
        c.execute("INSERT INTO orgs(org_id,name,normalized_name,source,tier_entitlement,classified,"
                  "industry,subsector,fte_band,hq_region,similarity_vector_json,submission_complete,created_at) "
                  "VALUES(?,NULL,NULL,'seed','core',1,?,?,?,?,?,1,datetime('now'))",
                  (o["org_id"], o["industry"], o["subsector"], o["fte_band"], o["hq_region"], b["similarity_vector_json"]))
        for qid, lst in na[o["org_id"]].items():
            for (mr, val, sub) in lst:
                c.execute("INSERT INTO answers(org_id,question_id,matrix_row_id,value,submitted_at,snapshot_id) "
                          "VALUES(?,?,?,?,?,1)", (o["org_id"], qid, mr, val, sub))
    c.commit()

    # ---- write response CSV files (L1 ground truth) ----
    hdr = ["row_number", "org_id", "org_name", "question_id", "question_text", "superpower", "subpower",
           "type", "category", "matrix_row_id", "matrix_row_label", "acceptable_answers", "your_answer", "notes"]
    mrlabel = {(r["question_id"], r["matrix_row_id"]): r["matrix_row_label"] for r in
               c.execute("SELECT DISTINCT question_id, matrix_row_id, matrix_row_label FROM answers WHERE matrix_row_label!=''")} \
        if _has_col(c, "answers", "matrix_row_label") else {}
    for o in new:
        fn = "%s_%s.csv" % (re.sub(r'[^A-Za-z0-9]+', '_', o["name"]).strip("_"), o["org_id"])
        with open(os.path.join(RESP, fn), "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); rn = 0
            for qid in sorted(na[o["org_id"]]):
                q = qrows[qid]
                for (mr, val, sub) in na[o["org_id"]][qid]:
                    rn += 1
                    w.writerow([rn, o["org_id"], o["name"], qid, q["text"], q["superpower"] or "",
                                q["sub_power"] or "", q["type"], q["category"] or "", mr,
                                mrlabel.get((qid, mr), ""), "", val, ""])

    # ---- re-record book_baseline.json ----
    rows = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                     "ORDER BY org_id, question_id, matrix_row_id").fetchall()
    digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rows).encode()).hexdigest()[:16]
    book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
    book["rows"] = len(rows); book["hash16"] = digest
    json.dump(book, open(BOOK, "w"), indent=2)

    # ---- identity.db org_register twins ----
    if ic:
        for o in new:
            ic.execute("INSERT INTO org_register(org_id,name,normalized_name,company_name,external_registry_id) "
                       "VALUES(?,?,?,?,NULL)", (o["org_id"], o["name"], norm(o["name"]), o["name"]))
        ic.commit(); ic.close()
    c.close()

    # ---- org_profiles_inferred.json: Industry + FTE_Band only ----
    # The gate bands orgs by profile. Without a row a new org bands '?' -> _default on every keyed
    # gradient — which mis-scores the Industry-keyed REW_INC_103 (a sector-faithful public-sector
    # org has no bonus, but _default expects only 10% 'None'). Giving Industry+FTE_Band bands it by
    # its REAL sector, so the sector-faithful clone matches its own band. HR_Maturity is DELIBERATELY
    # omitted: the 3 HR_Maturity gradients are anchors-type over Basic/Developing/Advanced, and a
    # same-cell clone (drawn on industry+size, not maturity) would not honour a maturity anchor —
    # with no HR_Maturity the gate bands the new org None on those and skips it, as before.
    prof = json.load(open(PROF)) if os.path.exists(PROF) else {}
    for o in new:
        prof[o["org_id"]] = {"org_id": o["org_id"], "Company_Name": o["name"], "inferred": True,
                             "_add50": True, "Industry": o["industry"], "Subsector": o["subsector"],
                             "FTE_Band": o["fte_band"], "HQ_Region": o["hq_region"]}
    json.dump(prof, open(PROF, "w"), indent=1, ensure_ascii=False)
    print("  WROTE: 50 orgs + answers, 50 CSVs, book_baseline (%d rows, %s), 50 org_register twins, 50 profile rows"
          % (len(rows), digest))


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute("PRAGMA table_info(%s)" % table))


if __name__ == "__main__":
    sys.exit(main() or 0)
