#!/usr/bin/env python3
"""P0-a — re-tilt EAP by sector, fixing a V2-I regression (2026-08-14, grounding review).

V2-I's PMI->EAP bundling swap pulled EAP from "lean non-PMI" orgs to give it to PMI-offerers. But
public bodies, charities and education orgs ARE non-PMI (they use the NHS, not private medical), so
they lost their EAP and dropped to 28/30/33% — inverted, since EAP (cheap, values-aligned, near-
universal) is a strength of exactly those sectors. REW26_WEL_EAP is FROZEN (195 Yes / 75 No), so this
is a per-sector Yes-count reset holding the global exactly (OT_04/B4 pattern): EAP high in
Public/Charity/Education/Construction and large orgs; the 75 "No" concentrated in lean frontline SMEs.
Within a sector, large orgs keep/get EAP and SMEs carry the "No". DB-origin -> DB-only.
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
Q = "REW26_WEL_EAP"
BIG = ("10,000+", "5,000-9,999", "1,000-4,999")
# per-sector Yes target — sums to 195 = frozen Yes-total (global held exactly)
TARGET = {
    "Public Sector & Government": 17, "Charity, Non-Profit & Social Enterprise": 9,
    "Education (Public & Private)": 11, "Construction & Infrastructure": 26,
    "Energy, Utilities & Environmental Services": 9, "Financial Services": 11,
    "Technology, Software & Digital": 11, "Professional Services": 11,
    "Media, Communications & Creative Industries": 13, "Healthcare & Life Sciences": 7,
    "Manufacturing & Engineering": 20, "Logistics, Transport & Distribution": 22,
    "Retail & Consumer Goods": 14, "Hospitality, Leisure & Travel": 14,
}


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = [0]

    def rows():
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (Q,))}

    def setv(o, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (o, Q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[0] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, o, Q))

    d = rows(); bysec = defaultdict(list)
    for o in d:
        if o in ind: bysec[ind[o]].append(o)
    for sec, orgs in bysec.items():
        tgt = TARGET.get(sec)
        if tgt is None: continue
        # large orgs first get "Yes"; SMEs carry the "No" tail
        orgs = sorted(orgs, key=lambda o: (0 if fte.get(o) in BIG else 1, o))
        for i, o in enumerate(orgs):
            setv(o, "Yes" if i < tgt else "No")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    nd = rows(); cnt = Counter(nd.values())
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d cell changes | EAP global (frozen, hold 195/75): %s"
          % (changes[0], dict(cnt)))
    for s in ("Public Sector & Government", "Charity, Non-Profit & Social Enterprise",
              "Education (Public & Private)", "Retail & Consumer Goods", "Hospitality, Leisure & Travel"):
        orgs = bysec.get(s, [])
        print("  %s: %d/%d Yes" % (s[:30], sum(1 for o in orgs if nd.get(o) == "Yes"), len(orgs)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
