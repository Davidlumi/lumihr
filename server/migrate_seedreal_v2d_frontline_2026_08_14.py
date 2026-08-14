#!/usr/bin/env python3
"""V2-D seed-realism — frontline/office separation + signature benefits (2026-08-14, persona QA).

- OT_04_b14623a6 (shift premium for unsocial hours; REGISTER MARGINAL ~0.63): office/knowledge-
  worker sectors (Tech 50% / Prof Services 42% / FS 42% / Media 29%) implausibly report shift
  premiums — they have no shift-working population. RESET per-sector Yes-counts to a shift-operating
  profile that HOLDS the global Yes-total (170) — office down to ~1, frontline sectors up. Marginal-
  conserving reallocation (permitted for anchored metrics; same as B4).
- REW264_WEL_MEALS (free/subsidised staff meals): the signature hospitality benefit read 94% "No".
  Lift Hospitality to a majority Free/Subsidised (not anchored — a straight sector-realism raise).
- REW26_PAY_SKILLS_PAY (skills/capability-based pay): Manufacturing & Engineering — the archetypal
  skills-matrix sector — sat BELOW the pool. Lift Manufacturing Yes-rate (not anchored).

Deferred to a later pass (messier / coherence-linked): shift-differentiated overtime matrices in
office sectors (REW_Q528801/534581), retail staff-discount in the REW_BEN_038 checklist.

LUMI_DB-aware. Dry-run default; --write --confirmed-by-david. Deterministic. Re-records book_baseline.
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, json, sqlite3, hashlib
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

OT = "OT_04_b14623a6"
# per-sector Yes target — sums to 170 = current classified Yes-total, so the global marginal holds
OT_TARGET = {
    "Construction & Infrastructure": 26, "Logistics, Transport & Distribution": 29,
    "Manufacturing & Engineering": 24, "Hospitality, Leisure & Travel": 24,
    "Energy, Utilities & Environmental Services": 9, "Healthcare & Life Sciences": 8,
    "Public Sector & Government": 14, "Retail & Consumer Goods": 24,
    "Education (Public & Private)": 6, "Charity, Non-Profit & Social Enterprise": 2,
    "Technology, Software & Digital": 1, "Professional Services": 1,
    "Financial Services": 1, "Media, Communications & Creative Industries": 1,
}
N_HOSP_MEALS = 24     # of ~32 Hospitality orgs -> Free/Subsidised
N_MANU_SKILLS = 12    # of ~28 Manufacturing orgs -> skills-based pay = Yes


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int)

    def rows(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (org, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, org, q))

    # ---- OT_04: per-sector Yes-count reset (global conserved) ----
    ot = rows(OT); bysec = defaultdict(list)
    for o in sorted(ot):
        if o in ind: bysec[ind[o]].append(o)
    for sec, orgs in bysec.items():
        tgt = OT_TARGET.get(sec)
        if tgt is None: continue
        orgs = sorted(orgs, key=lambda o: (0 if str(ot[o]).strip() == "Yes" else 1, o))  # keep current Yes first
        for i, o in enumerate(orgs):
            setv(OT, o, "Yes" if i < tgt else "No")

    # ---- REW264_WEL_MEALS: Hospitality staff meals (signature benefit) ----
    ml = rows("REW264_WEL_MEALS")
    hosp = sorted(o for o in ml if "Hospitality" in str(ind.get(o, "")))
    for i, o in enumerate(hosp[:N_HOSP_MEALS]):
        setv("REW264_WEL_MEALS", o, "Free" if i % 3 == 0 else "Subsidised")   # ~1/3 free, 2/3 subsidised

    # ---- REW26_PAY_SKILLS_PAY: Manufacturing skills-based pay ----
    sk = rows("REW26_PAY_SKILLS_PAY")
    manu = sorted((o for o in sk if "Manufacturing" in str(ind.get(o, ""))),
                  key=lambda o: (0 if str(sk[o]).strip() == "Yes" else 1, o))
    for i, o in enumerate(manu):
        setv("REW26_PAY_SKILLS_PAY", o, "Yes" if i < N_MANU_SKILLS else (sk[o] or "No"))

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    ot2 = rows(OT)
    print("  OT_04 global Yes (hold 170):", sum(1 for v in ot2.values() if v == "Yes"))
    print("  OT_04 office sectors now:", {s: sum(1 for o in bysec[s] if ot2.get(o) == "Yes")
          for s in ("Technology, Software & Digital", "Professional Services", "Financial Services",
                    "Media, Communications & Creative Industries") if s in bysec})
    print("  MEALS Hospitality Free/Subs:", sum(1 for o in hosp if rows("REW264_WEL_MEALS").get(o) in ("Free", "Subsidised")))
    print("  SKILLS Manufacturing Yes:", sum(1 for o in manu if rows("REW26_PAY_SKILLS_PAY").get(o) == "Yes"))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
