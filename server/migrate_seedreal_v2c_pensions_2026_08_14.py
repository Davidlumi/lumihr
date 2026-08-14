#!/usr/bin/env python3
"""V2-C seed-realism — sector pension fingerprints, frozen-conserving (2026-08-14).

The sector-persona QA found DB/hybrid pensions entirely absent from the sectors that carry the
UK's DB legacy — Manufacturing & Engineering (0/28), Energy/Utilities (0/10) — while a few DB/hybrid
records sat in sectors that would not have them (Media, Hospitality, Retail). REW26_BEN_PENSION_TYPE
is a FROZEN anchor (25 DB / 4 Hybrid / 241 DC at n=270), so this is a pure REALLOCATION — each org
turned into DB/Hybrid is paired with one turned out, holding every per-value count exactly (the same
count-conserving swap the original B4 batch used for Education).

Target within the frozen cap:  Public 17 DB · Education 4 DB · Energy 2 DB · Manufacturing 1 DB + 3
Hybrid · FS 1 DB · Logistics 1 Hybrid.  Cascade per B4: a DB org has no member DC fund, so clear the
DC-only children (REW264_PEN_AEDEFAULT / GREENDEFAULT — coherence pairs require parent != DB) and set
REW_BEN_112 to a TPS/LGPS-style flat rate; a de-DB'd org drops to a modest DC ladder. Hybrid keeps a
DC section, so its DC children stay substantive and REW_BEN_112 takes a blended rate.

LUMI_DB-aware. Dry-run default; apply with --write --confirmed-by-david. Deterministic. Re-records
data/book_baseline.json. After --write, re-aggregate:
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]
DC_LADDER = ["8", "7", "6", "5", "5", "4", "4"]
# metrics that live in a CSV response file (not DB-origin wave metrics) need lockstep CSV edits
CSV_LOCKED = {"REW_BEN_112"}


def csv_path(o):
    h = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return h[0] if h else None


def csv_edit(o, q, mr, v):
    p = csv_path(o)
    if not p: return 0
    rows = list(csv.reader(open(p))); hdr = rows[0]
    qi, mi, ai = hdr.index("question_id"), hdr.index("matrix_row_id"), hdr.index("your_answer")
    n = 0
    for r in rows[1:]:
        if len(r) > ai and r[qi] == q and (r[mi] or "") == mr:
            r[ai] = v; n += 1
    if n:
        with open(p, "w", newline="") as f: csv.writer(f).writerows(rows)
    return n


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int); csv_hits = [0]

    def rows(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, row, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, q, row)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (new, org, q, row))
            if q in CSV_LOCKED: csv_hits[0] += csv_edit(org, q, row, new)

    pt = rows("REW26_BEN_PENSION_TYPE")
    inS = lambda o, *ss: any(s in str(ind.get(o, "")) for s in ss)
    # recipients: DC orgs in the DB-heartland sectors, largest first (legacy DB concentrates at scale)
    big = ("10,000+", "5,000-9,999", "1,000-4,999")
    def dc_in(*ss):
        return sorted((o for o, v in pt.items() if v == "DC" and inS(o, *ss)),
                      key=lambda o: (0 if fte.get(o) in big else 1, o))
    energy = dc_in("Energy"); manu = dc_in("Manufacturing"); edu = dc_in("Education")
    # donors: DB/Hybrid records in sectors that would not hold them (+ over-weighted Logistics/FS)
    db_don = sorted(o for o, v in pt.items() if v == "DB" and inS(o, "Media", "Hospitality", "Financial Services", "Logistics"))
    hy_don = sorted(o for o, v in pt.items() if v == "Hybrid" and inS(o, "Retail", "Logistics"))

    def to_db(o):
        setv("REW26_BEN_PENSION_TYPE", o, "", "DB")
        setv("REW264_PEN_AEDEFAULT", o, "", "Not applicable (no DC scheme)")
        setv("REW264_PEN_GREENDEFAULT", o, "", "Not applicable (no DC default fund)")
        for lvl in LEVELS: setv("REW_BEN_112", o, lvl, "23")     # TPS/LGPS-style flat employer rate

    def to_hybrid(o):
        setv("REW26_BEN_PENSION_TYPE", o, "", "Hybrid")          # keeps a DC section -> DC children stay
        for lvl in LEVELS: setv("REW_BEN_112", o, lvl, "15")     # blended DB+DC employer rate

    def to_dc(o):
        setv("REW26_BEN_PENSION_TYPE", o, "", "DC")
        for lvl, r in zip(LEVELS, DC_LADDER): setv("REW_BEN_112", o, lvl, r)

    # ---- DB reallocations (4): Energy x2, Manufacturing x1, Education x1 <- stray/over-weighted DB ----
    db_recips = (energy[:2] + manu[:1] + edu[:1])
    for r, d in zip(db_recips, db_don):
        to_db(r); to_dc(d)
    # ---- Hybrid reallocations (3): Manufacturing <- Retail/Logistics hybrids ----
    hy_recips = manu[1:4]
    for r, d in zip(hy_recips, hy_don):
        to_hybrid(r); to_dc(d)

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  CSV rows updated:", csv_hits[0])
    npt = rows("REW26_BEN_PENSION_TYPE")
    print("  PENSION_TYPE global (must stay 25 DB / 4 Hybrid / 241 DC):", dict(Counter(npt.values())))
    bysec = defaultdict(Counter)
    for o, v in npt.items():
        if v in ("DB", "Hybrid"): bysec[ind.get(o)][v] += 1
    for s in sorted(bysec): print("   ", s[:34], dict(bysec[s]))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
