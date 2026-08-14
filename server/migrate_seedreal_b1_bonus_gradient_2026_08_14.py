#!/usr/bin/env python3
"""Batch 1 — frontline & no-bonus REW_INC_103 gradient (2026-08-14, grounding review).

REW_INC_103 (bonus-scheme eligibility) is Industry-keyed, but only Charity/Public had a bonus-light
band — everyone else inherited the bonus-heavy _default (75%+ dominant). The review found this wrong
for Retail/Hospitality/Logistics (frontline: mostly low/no eligibility) and Education (national spine
pay, no discretionary bonus). New band_distributions were added to generated_marginals.json:
Retail/Hospitality/Logistics = frontline (None 25%, 75%+ 30%); Education = no-bonus (None 80%).

This migration reallocates each sector's orgs to its new band (monotonic by current generosity, so
minimal churn and no None->bonus moves), and — for orgs newly set to "None" — CASCADES the coherence
children to their no-bonus values (REW_INC_069='No deferral', the rest 'Not applicable') and deletes
the bonus-opportunity/LTI ladders (323ffcf1, REW_INC_111, REW_INC_LTI_MAX_01). Orgs never move OUT of
None, so no reverse-cascade is needed. REW_INC_103 is Diff-3 (DB-only); the single-select children are
CSV-lineage-locked (DB+CSV lockstep) except POOLFUND (DB-origin); the ladders are deleted DB+CSV.
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from reseed_engine import canon_industry

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW_INC_103"
BANDS = ["None", "<10%", "10–24%", "25–49%", "50–74%", "75%+"]
ORD = {b: i for i, b in enumerate(BANDS)}
SECTORS = ["Retail & Consumer Goods", "Hospitality, Leisure & Travel",
           "Logistics, Transport & Distribution", "Education (Public & Private)"]
CHILD = {"REW_INC_069": "No deferral", "REW_INC_071": "Not applicable", "REW263_INC_POOLFUND": "Not applicable",
         "REW_INC_065": "Not applicable", "REW_INC_104": "Not applicable", "REW_INC_070": "Not applicable",
         "REW_INC_060": "Not applicable"}
CHILD_CSV = {k for k in CHILD if not k.startswith(("REW26", "REW263", "REW264", "REW265"))}   # CSV-locked children
LADDERS = ["323ffcf1-749b-43f3-bf34-1de6b8b1ca67", "REW_INC_111", "REW_INC_LTI_MAX_01"]


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
    bd = json.load(open(os.path.join(ROOT, "generated_marginals.json")))["maturity_gradients"][Q]["band_distributions"]
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = defaultdict(int); csv_rows = [0]

    def val(o, q):
        r = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (o, q)).fetchone()
        return r["value"] if r else None

    def setv(o, q, v, csv_locked):
        if (val(o, q) or "") == v: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (v, o, q))
            if csv_locked: csv_rows[0] += csv_set(o, q, v)

    def cascade_none(o):
        for ch, v in CHILD.items(): setv(o, ch, v, ch in CHILD_CSV)
        if WRITE:
            qm = ",".join("?" * len(LADDERS))
            c.execute("DELETE FROM answers WHERE org_id=? AND question_id IN (%s) AND snapshot_id=1 AND matrix_row_id!=''" % qm, [o] + LADDERS)
            # REW263_INC_DEFERRAL (deferral period/vehicle) has no 'Not applicable' value and is
            # conditioned on REW_INC_069 deferring -> remove it entirely once 069='No deferral'.
            c.execute("DELETE FROM answers WHERE org_id=? AND question_id='REW263_INC_DEFERRAL' AND snapshot_id=1", (o,))
            csv_rows[0] += csv_del(o, set(LADDERS) | {"REW263_INC_DEFERRAL"})

    cur = {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (Q,))}
    for sec in SECTORS:
        orgs = sorted((o for o in cur if ind.get(o) == sec), key=lambda o: (ORD.get(cur[o], 9), o))
        n = len(orgs)
        dist = bd[canon_industry(sec)]
        quota = {b: dist[b] / 100.0 * n for b in BANDS}
        cnt = {b: int(quota[b]) for b in BANDS}
        r = n - sum(cnt.values())
        for b in sorted(BANDS, key=lambda x: -(quota[x] - int(quota[x])))[:max(0, r)]: cnt[b] += 1
        # assign monotonically (orgs sorted low->high generosity) so None gets the lowest current bands
        seq = []
        for b in BANDS:
            seq += [b] * cnt[b]
        for o, b in zip(orgs, seq):
            was_none = cur[o] == "None"
            setv(o, Q, b, csv_locked=False)   # REW_INC_103 is Diff-3 -> DB-only
            if b == "None" and not was_none:
                cascade_none(o)

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str({k[:20]: v for k, v in changes.items()}))
    print("  CSV rows touched:", csv_rows[0])
    nd = {r["org_id"]: r["value"] for r in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (Q,))}
    for sec in SECTORS:
        print("  %s: %s" % (canon_industry(sec)[:22], dict(Counter(nd.get(o) for o in cur if ind.get(o) == sec))))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
