#!/usr/bin/env python3
"""Batch 3 — over-tilted sector deflations toward the UK norm (2026-08-14, grounding review).

Sectors seeded ABOVE the real UK prevalence on a lever they shouldn't lead. Deflate the over-indexed
sector by demoting its least-plausible (smallest-first) orgs to the floor value, so large flagship
orgs keep the practice. All leaf metrics (no coherence children — verified against coherence_pairs).

  - REW_BEN_046 (income protection): Media 86% is not a UK GIP-heavy sector. Register marginal ->
    count-conserving swap: demote small Media (any cover -> No), raise FS/Energy who actually
    under-index on a product their sector holds/sells. [MARG, CSV lockstep]
  - REW264_INC_SHAREPLAN (all-employee SAYE/SIP): UK Media is overwhelmingly private/PE-owned; an
    all-employee tax-advantaged share plan needs a listing. 50% -> ~21%. [free, DB-only]
  - REW264_HLT_CANCERPATH (dedicated cancer pathway): a large-employer/PMI-scale benefit; Media 57%
    over-indexes -> ~36%. [free, DB-only]
  - REW265_INC_ESGINCENT (ESG measures IN incentive plan): a big-corporate/Energy governance device,
    not a Tech signature. Tech 67% -> ~33% (reallocated to Mfg/Construction/Energy in Batch 2a). [free, DB-only]
  - REW_BEN_039 (flex-benefits platform): flex platforms are expensive HR tech; small charities can't
    run them. Charity 80% -> ~40%. [free, CSV lockstep]

Subset-coherence cascades (r3sw11/r3sw17/r3sw24, enforced by qa_plausibility not coherence_pairs-as-dict):
  * SHAREPLAN->"Neither" resets the plan-operator children SHAREPART/SAYEDISC->"Not applicable",
    SIPELEM->"No SIP operated" (EMICSOP kept — "Neither" is still a share-capital org). DB-only.
  * REW_BEN_046->"No" removes IP-conditioned children 047/048 (DB+CSV) + GIPREHAB (DB), and excludes
    038 Critical-illness donors so the group-risk bundle lock holds.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG = ("10,000+", "5,000-9,999", "1,000-4,999", "250-999")
DBO = {"REW264_INC_SHAREPLAN", "REW264_HLT_CANCERPATH", "REW265_INC_ESGINCENT"}  # DB-only; rest CSV-locked


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_set(o, q, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]; qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (r[mi] or "") == "":
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def csv_del(o, qids):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]; qi = hdr.index("question_id")
    keep = [rows[0]] + [r for r in rows[1:] if not (len(r) > qi and r[qi] in qids)]
    n = len(rows) - len(keep)
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(keep)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int); csv_rows = [0]
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)

    def rows(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (new, o, q))
            if q not in DBO: csv_rows[0] += csv_set(o, q, new)

    # --- free-leaf deflations: demote smallest-first so flagship large orgs keep the practice ---
    def deflate(q, is_pos, neg_val, sector, count):
        d = rows(q)
        cands = sorted((o for o, v in d.items() if o in ind and inS(o, sector) and is_pos(v)),
                       key=lambda o: (0 if fte.get(o) not in BIG else 1, o))  # small first
        for o in cands[:count]: setv(q, o, neg_val)
        return min(count, len(cands))

    # r3sw11 subset children of the share-plan operator set — when a plan operator is demoted to
    # "Neither" its participation/discount/element children must fall back to their N/A label (they
    # are answered only by plan operators). EMICSOP is NOT reset: "Neither" is still a share-capital
    # org (parent_value_not is "Not applicable (no shares)"), so EMI/CSOP may legitimately remain.
    SHARE_CHILD = {"REW265_INC_SHAREPART": "Not applicable", "REW265_INC_SAYEDISC": "Not applicable",
                   "REW265_INC_SIPELEM": "No SIP operated"}   # all DB-origin -> DB-only

    def deflate_shareplan(count):
        d = rows("REW264_INC_SHAREPLAN")
        cands = sorted((o for o, v in d.items() if o in ind and inS(o, "Media")
                        and v not in ("Neither", "Not applicable (no shares)")),
                       key=lambda o: (0 if fte.get(o) not in BIG else 1, o))
        for o in cands[:count]:
            setv("REW264_INC_SHAREPLAN", o, "Neither")
            for ch, na in SHARE_CHILD.items(): setv(ch, o, na)
        return min(count, len(cands))

    ks = {}
    ks["SHAREPLAN"] = deflate_shareplan(4)
    ks["CANCERPATH"] = deflate("REW264_HLT_CANCERPATH", lambda v: v != "No", "No", "Media", 3)
    ks["ESGINCENT"] = deflate("REW265_INC_ESGINCENT", lambda v: v != "No", "No", "Technology", 5)
    ks["FLEX039"] = deflate("REW_BEN_039", lambda v: v in ("Yes", "In development"), "No", "Charity", 4)

    # --- REW_BEN_046 income protection: count-conserving swap (marginal held to the org) ---
    # r3sw17/r3sw24 subset children conditioned on IP-exists: when a donor loses IP, its waiting-period
    # (047), salary-replacement (048) and group-IP rehab (GIPREHAB) answers must be REMOVED, and it must
    # not be a Critical-illness holder in the 038 group-risk bundle (038 CI ⊆ IP-havers) — so exclude
    # CI-bundle donors rather than strip the bundle. 047/048 are CSV-locked; GIPREHAB is DB-origin.
    q = "REW_BEN_046"
    IP_CHILD_DEL = ["REW_BEN_047", "REW_BEN_048", "REW264_HLT_GIPREHAB"]
    IP_CHILD_CSV = {"REW_BEN_047", "REW_BEN_048"}
    ci = {o for (o, v) in c.execute("SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND matrix_row_id='' AND snapshot_id=1")
          if "Critical illness cover" in (t.strip() for t in (v or "").split(";"))}
    d = rows(q)
    donors = sorted((o for o, v in d.items() if o in ind and inS(o, "Media") and v != "No" and o not in ci),
                    key=lambda o: (0 if fte.get(o) not in BIG else 1, o))          # demote small Media (non-CI)
    recips = sorted((o for o, v in d.items() if o in ind and v == "No"
                     and (inS(o, "Financial Services", "Energy") or (inS(o, "Manufacturing") and fte.get(o) in ("10,000+", "5,000-9,999")))),
                    key=lambda o: (0 if fte.get(o) in BIG else 1, o))              # raise large FS/Energy/big Mfg
    k = min(len(donors), len(recips), 5)
    for o in donors[:k]:
        setv(q, o, "No")
        for ch in IP_CHILD_DEL:
            gone = c.execute("SELECT 1 FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1 AND value!=''", (o, ch)).fetchone()
            if gone:
                changes[ch] += 1
                if WRITE:
                    c.execute("DELETE FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1", (o, ch))
                    if ch in IP_CHILD_CSV: csv_rows[0] += csv_del(o, {ch})
    for o in recips[:k]: setv(q, o, "Long-term only")
    ks["INCPROT_pairs"] = k

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — moves: " + str(ks))
    print("  cell changes: " + str(dict(changes)) + " | CSV rows: %d" % csv_rows[0])
    print("  REW_BEN_046 presence (marginal, hold):",
          sum(1 for v in rows(q).values() if v != "No"), "/", len(rows(q)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
