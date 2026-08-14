#!/usr/bin/env python3
"""Add 50 new synthetic companies to the seed pool (2026-08-14, David) — full lineage.

Grows the benchmark pool 220 -> 270 so sector/size sample searches are richer.

Each new org's GATED closures (every coherence-closure touching a register marginal, keyed
gradient, ruled distribution, multi-select incidence or settled-frozen metric) are filled by
CLONING a real donor org's whole closure answer-set — the donor MIX is chosen (donor_mix, IPF at
the contingency level) so every anchored marginal lands on its target and the joint stays coherent
by construction. There is deliberately NO complete-tuple requirement: the naive joint-tuple
replicator only used orgs answering EVERY metric in a closure, which biased a 12-metric health
closure toward large fully-completing orgs and pushed the size-conditioned marginals (sick pay,
income protection) to the large-firm rate. Keyed gradients are matched to their _default band,
because new orgs carry no org_profiles row and the gate bands them '?' -> _default. FREE metrics
are block-shuffled from same-cell donors with numeric jitter, so no two orgs share an answer vector.

Adding orgs necessarily perturbs the 8 settled-frozen SHARE anchors by up to ~0.2pp (0.1pp is
0.27 of one org at n=270 — a "don't touch" guard, not a data threshold), so this batch RE-RATIFIES
frozen_targets.json to the 270-org store (David-approved 2026-08-14). Register marginals (5pp) and
keyed gradients hold by construction.

Extends the WHOLE provenance chain so all gates stay green:
  * lumi.db  — orgs rows + answers
  * data/responses/*.csv  — 50 new response files (L1 ground truth)
  * data/book_baseline.json  — re-recorded row hash
  * identity.db org_register — 50 twin rows (identity_recon)
  * frozen_targets.json      — settled anchors re-ratified at n=270 (separate, David-signed edit)

Deterministic sha256. INSERT-only. After --write, re-aggregate:
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")

    python3 server/migrate_add50_orgs_2026_08_14.py                          # dry run
    python3 server/migrate_add50_orgs_2026_08_14.py --write --confirmed-by-david
"""
import os, sys, json, csv, sqlite3, hashlib, uuid, re
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
IDB = os.environ.get("LUMI_IDENTITY_DB") or os.path.join(ROOT, "identity.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
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

    # ---- donors: registry-matched classified 158, with full answers ----
    donors = [dict(r) for r in c.execute(
        "SELECT org_id, industry, subsector, fte_band, hq_region, similarity_vector_json "
        "FROM orgs WHERE classified=1 AND registry_json IS NOT NULL AND registry_json!=''")]
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

    # ---- assemble answers ----
    NUMERIC = {"numeric", "number", "currency", "percent", "percentage"}
    na = {}    # oid -> {qid: [[mr,val,sub],...]}
    for o in new:
        oid, ind, fte, base = o["org_id"], o["industry"], o["fte_band"], o["base"]
        rows = {}
        # FREE metrics (not in any gated closure): clone from a same-cell donor + jitter numerics -> novelty
        for root in free_roots:
            pool = by_cell.get((ind, fte)) or by_ind.get(ind) or list(dset)
            donor = pick(pool, "free", oid, root)
            for qid in closure[root]:
                if qid in ans[donor]:
                    cp = [list(x) for x in ans[donor][qid]]
                    if qtype.get(qid) in NUMERIC:
                        for row in cp:
                            m = re.match(r"^\s*([-+]?\d*\.?\d+)(.*)$", row[1] or "")
                            if m:
                                v = float(m.group(1)); j = ((h("jit", oid, qid, row[0]) % 7) - 3)
                                nv = v + j if v > 20 else round(v + j * 0.1, 2)
                                if nv > 0: row[1] = (("%d" % nv) if float(nv).is_integer() else ("%.2f" % nv)) + m.group(2)
                    rows[qid] = cp
        na[oid] = rows

    # ---- GATED CLOSURES: clone a REAL donor org's whole closure answer-set into each new org,
    #      choosing the donor MIX (IPF over donor weights) so every register marginal, keyed
    #      gradient, ruled distribution and settled-frozen dist lands on its target. Coherence
    #      holds by construction — each donor is a real, internally-consistent org. There is NO
    #      complete-tuple requirement: the old joint-tuple replicator only used orgs that had
    #      answered EVERY metric in the closure, which biased a 12-metric health closure toward
    #      large, fully-completing orgs and pushed size-conditioned marginals (sick pay, income
    #      protection) up to the large-firm rate. Cloning a real org's partial set avoids that. ----
    fixed = {}
    org_ans = defaultdict(lambda: defaultdict(list))
    for r in c.execute("SELECT org_id, question_id, matrix_row_id, value, submitted_at FROM answers "
                        "WHERE snapshot_id=1 AND value!=''"):
        org_ans[r["org_id"]][r["question_id"]].append([r["matrix_row_id"], r["value"], r["submitted_at"]])
    org_ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id, industry FROM orgs")}
    resp_by_ind = defaultdict(list)
    for oid in org_ans: resp_by_ind[org_ind.get(oid)].append(oid)
    all_resp = sorted(org_ans)
    all_new = [o["org_id"] for o in sorted(new, key=lambda x: h("gid", x["org_id"]))]

    def _val(oid, qid):
        lst = org_ans[oid].get(qid)
        if not lst: return None
        return next((x[1].strip() for x in lst if x[0] == ""), lst[0][1].strip())

    def _marg_cell(qid, val):
        o = (ORDS.get(qid) or {}).get("option_order"); wo = (ORDS.get(qid) or {}).get("worst_option")
        if o:
            pf = MARGENT[qid].get("positive_from"); cut = o.index(pf) if pf in o else 1
            if val not in o: return "out"
            return "lean" if val in set(o[:cut]) else "pos"
        if wo:
            return "lean" if str(val).strip().lower() == str(wo).strip().lower() else "pos"
        return None

    def donor_mix(qs, cands, N, band=None, tiek="_"):
        """N donor org_ids (with repetition) from `cands`, mixed so every anchored marginal in
        the closure lands on its target. Works at the CONTINGENCY level: donors are grouped by
        their tuple of target cells (pos/lean/out per marginal; value per ruled/frozen dist), the
        joint cell-distribution is IPF-fitted to every marginal target, N is apportioned across
        cell-tuples by largest remainder (quotas are >=1 there, so LR is a true proportional split
        — NOT the degenerate top-N it becomes over 220 single donors), and real donors are drawn
        within each cell. Cloning a real donor keeps the whole closure internally coherent."""
        specs = []
        for m in qs:
            if m in MARGENT and (MARGENT[m].get("target_share") is not None or MARGENT[m].get("target_range")):
                if not ((ORDS.get(m) or {}).get("option_order") or (ORDS.get(m) or {}).get("worst_option")):
                    continue
                e = MARGENT[m]; t = e.get("target_share")
                if t is None: r = e["target_range"]; t = (float(r[0]) + float(r[1])) / 2.0
                specs.append((m, (lambda v, m=m: _marg_cell(m, v)), ("marg", float(t))))
            elif m in MGRADENT and MGRADENT[m].get("band_distributions"):
                # New orgs carry no org_profiles row, so qa_plausibility bands them '?' and falls
                # through to the gradient's _default distribution. Match _default globally so the
                # '?' band lands on the ruled shape. (anchors-type gradients declare no '?' band,
                # so the gate never evaluates the new orgs against them — no spec needed.)
                bd = MGRADENT[m]["band_distributions"].get("_default")
                if bd: specs.append((m, (lambda v: v), ("dist", {k: p / 100.0 for k, p in bd.items()})))
            elif m in RDISTENT:
                specs.append((m, (lambda v: v), ("dist", {k: p / 100.0 for k, p in RDISTENT[m]["distribution"].items()})))
            elif m in FROZDICT:
                specs.append((m, (lambda v: v), ("dist", dict(FROZDICT[m]["dist"]))))

        def lr(quota, n, keyfn):     # largest-remainder integer allocation of n over a quota dict
            alloc = {k: int(v) for k, v in quota.items()}
            r = n - sum(alloc.values())
            if r > 0:
                for k in sorted(quota, key=lambda x: (-(quota[x] - int(quota[x])), keyfn(x)))[:r]: alloc[k] += 1
            return alloc

        if not specs:                # no anchored metric -> proportional draw by hash
            picks = sorted(cands, key=lambda x: h("mix", tiek, band or "_", x))
            return [picks[i % len(picks)] for i in range(N)] if picks else []

        dc = {m: {d: cf(_val(d, m)) for d in cands if _val(d, m) is not None} for (m, cf, _) in specs}
        full = [d for d in cands if all(d in dc[m] for (m, _, _) in specs)]
        if not full: full = list(cands)
        tup = {d: tuple(dc[m].get(d) for (m, _, _) in specs) for d in full}
        w = {ct: cnt / len(full) for ct, cnt in Counter(tup.values()).items()}

        def spec_target(spec, cur):
            if spec[0] == "marg":
                t = spec[1]; po = cur.get("out", 0.0)
                return {"out": po, "pos": (1 - po) * t, "lean": (1 - po) * (1 - t)}
            if spec[0] == "marg2":
                return {"pos": spec[1], "neg": 1 - spec[1]}
            return dict(spec[1])

        for _ in range(60):          # IPF the joint cell-distribution onto every marginal target
            for i, (m, cf, spec) in enumerate(specs):
                cur = defaultdict(float)
                for ct, wv in w.items(): cur[ct[i]] += wv
                tgt = spec_target(spec, cur)
                for ct in list(w):
                    cell = ct[i]
                    if cell not in tgt: w[ct] = 0.0
                    elif cur[cell] > 0 and tgt[cell] > 0: w[ct] *= tgt[cell] / cur[cell]
            s = sum(w.values())
            if s > 0:
                for ct in w: w[ct] /= s

        quota = {ct: w[ct] * N for ct in w}
        alloc = lr(quota, N, lambda ct: h("ct", tiek, band or "_", str(ct)))
        seq = []
        for ct, n_ in alloc.items():
            pool = sorted([d for d in full if tup[d] == ct], key=lambda x: h("pick", tiek, band or "_", x))
            for j in range(n_):
                if pool: seq.append(pool[j % len(pool)])
        while len(seq) < N and full:  # top up any largest-remainder shortfall
            pad = sorted(full, key=lambda x: h("pad", tiek, x))
            seq.append(pad[len(seq) % len(pad)])
        return seq[:N]

    for root in gated_roots:
        qs = sorted(closure[root])
        # Draw globally over the whole responding pool. Keyed gradients are matched to their
        # _default band inside donor_mix (new orgs have no profile row -> the gate bands them '?'
        # -> _default), so per-industry keying would aim at the wrong target.
        cands = [d for d in all_resp if any(qid in org_ans[d] for qid in qs)]
        if not cands: continue
        seq = donor_mix(qs, cands, len(all_new), band=None, tiek=root[:8])
        for oid, src in zip(all_new, seq):
            for qid in qs:
                if org_ans[src].get(qid):
                    na[oid][qid] = [list(x) for x in org_ans[src][qid]]
        fixed["closure@%s" % root[:10]] = len(qs)

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
    print("  WROTE: 50 orgs + answers, 50 CSVs, book_baseline (%d rows, %s), 50 org_register twins" % (len(rows), digest))


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute("PRAGMA table_info(%s)" % table))


if __name__ == "__main__":
    sys.exit(main() or 0)
