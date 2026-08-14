#!/usr/bin/env python3
"""V2-I seed-realism — within-org generosity bundling (2026-08-14, realism review).

Real employers BUNDLE benefits: a firm that buys private medical almost always also has the cheap,
near-universal stuff. The review found PMI-offering orgs that don't hang together:
  - 31 offer PMI but no life assurance (normally bundled) -> REW_BEN_045 = 2x salary. [free; CSV]
  - 43 offer PMI but no EAP (the cheapest wellbeing benefit) -> EAP = Yes. EAP is FROZEN, so this is
    a count-conserving swap: give PMI-orgs EAP, take it from lean non-PMI EAP-holders (SME-first,
    excluding the Construction/Energy orgs V2-G/G just raised). [frozen; DB-only]
  (The 70 PMI + statutory-only-sick-pay orgs ride with the deferred REW_BEN_SICK_001 cascade.)

LUMI_DB-aware. Dry-run default; --write --confirmed-by-david. Deterministic. Re-records book_baseline.
    (cd server && python3 -c "from aggregate import run_snapshot; run_snapshot(1)")
"""
import os, sys, csv, json, sqlite3, hashlib, glob
from collections import defaultdict, Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
RESP = os.path.join(ROOT, "data", "responses")
BOOK = os.path.join(ROOT, "data", "book_baseline.json")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
CSV_LOCKED = {"REW_BEN_045"}
SME = ("50-249", "250-999")


def csv_path(o):
    hits = glob.glob(os.path.join(RESP, "*_%s.csv" % o)); return hits[0] if hits else None


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

    def hl(q):
        return {r["org_id"]: r["value"] for r in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (q,))}

    def setv(q, org, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (org, q)).fetchone()
        if cur is None or (cur["value"] or "") == new: return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, org, q))
            if q in CSV_LOCKED: csv_hits[0] += csv_edit(org, q, "", new)

    pmi = set(o for o, v in hl("REW_BEN_044").items() if v not in ("Not offered", "No"))

    # 1) life assurance for PMI-offerers missing it
    for o, v in hl("REW_BEN_045").items():
        if o in pmi and v in ("Not offered", "No"):
            setv("REW_BEN_045", o, "2×")

    # 2) EAP frozen-conserving swap: PMI-orgs get EAP <- lean non-PMI EAP-holders
    eap = hl("REW26_WEL_EAP")
    recips = sorted(o for o, v in eap.items() if v == "No" and o in pmi)
    donors = sorted((o for o, v in eap.items() if v == "Yes" and o not in pmi
                     and not any(s in str(ind.get(o, "")) for s in ("Construction", "Energy"))),
                    key=lambda o: (0 if fte.get(o) in SME else 1, o))   # lean SMEs give it up first
    k = min(len(recips), len(donors))
    for o in recips[:k]: setv("REW26_WEL_EAP", o, "Yes")
    for o in donors[:k]: setv("REW26_WEL_EAP", o, "No")

    if WRITE:
        c.commit()
        rws = c.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers WHERE snapshot_id=1 "
                        "ORDER BY org_id, question_id, matrix_row_id").fetchall()
        digest = hashlib.sha256("\n".join("%s|%s|%s|%s" % (r[0], r[1], r[2], r[3]) for r in rws).encode()).hexdigest()[:16]
        book = json.load(open(BOOK)) if os.path.exists(BOOK) else {}
        book["rows"] = len(rws); book["hash16"] = digest
        json.dump(book, open(BOOK, "w"), indent=2)

    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  CSV rows updated:", csv_hits[0], "| EAP pairs swapped:", k)
    ne = hl("REW26_WEL_EAP")
    print("  EAP global (frozen — must be unchanged):", dict(Counter(ne.values())))
    print("  PMI-orgs still missing EAP:", sum(1 for o in pmi if ne.get(o) == "No"),
          "| PMI-orgs still no life:", sum(1 for o in pmi if hl("REW_BEN_045").get(o) in ("Not offered", "No")))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
