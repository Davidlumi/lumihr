#!/usr/bin/env python3
"""Seed-realism B6 — David-ruled marginal moves (2026-08-10).

Three register marginals David ruled should move (data + anchor together). This
script changes the DATA and prints the new achieved positive share for each; the
matching target_share in generated_marginals.json is updated alongside (see the
companion edit / DECISIONS entry). LUMI_DB-aware; DRY-RUN unless
--write --confirmed-by-david.

- REW_BEN_FAM_002 (enhanced maternity weeks): ruling = "give them enhanced weeks".
  The 25 orgs with FAM_001 enhanced-pay but FAM_002='None' get a weeks band
  (proportional to the existing 1-12 / 13-26 split). Raises enhanced-any from ~54%
  toward ~66% to match the FAM_001 'enhanced pay' anchor.
- REW_FAI_079 (gender-pay-gap reporting): ruling = "raise 250+ to ~92% Yes". All
  classified 250+ orgs -> Yes, with an ~8% 'In development' tail; <250 left as-is
  (not statutory). Positive = Yes + In development.
- REW263_WEL_FINWELL: ruling = "align provision to programme". The 141 orgs whose
  frozen REW26_WEL_FINWELL programme flag = 'Yes' get substantive provision (~60%
  'Documented strategy' / ~40% 'Ad hoc provision'); non-programme orgs stay 'No'.
  Resolves the 108-org contradiction; positive_from='Documented strategy'.

    python3 server/migrate_seedreal_b6_ruled_marginals_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b6_ruled_marginals_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
BIG = ("250-999", "1,000-4,999", "5,000-9,999", "10,000+")


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    changes = defaultdict(int)

    def g1(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                        (org, q)).fetchone()
        if cur is None or (cur["value"] or "") == new:
            return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1",
                      (new, org, q))

    # ---- FAM_002: give the enhanced-pay/None orgs weeks ----
    f1 = g1("REW_BEN_FAM_001"); f2 = g1("REW_BEN_FAM_002")
    ENH = {"Enhanced pay (above statutory)", "Combination of enhanced leave and pay"}
    n25 = sorted(o for o in f1 if f1.get(o) in ENH and f2.get(o) == "None (statutory only)")
    for i, o in enumerate(n25):
        setv("REW_BEN_FAM_002", o, "1-12 weeks" if i < round(0.46 * len(n25)) else "13-26 weeks")

    # ---- FAI_079: 250+ -> ~92% Yes, ~8% In development ----
    fai = g1("REW_FAI_079")
    big_orgs = sorted(o for o in fai if fte.get(o) in BIG)
    yes_n = round(0.92 * len(big_orgs))
    for i, o in enumerate(big_orgs):
        setv("REW_FAI_079", o, "Yes" if i < yes_n else "In development")

    # ---- FINWELL: align provision to the frozen programme flag ----
    prog = g1("REW26_WEL_FINWELL"); fw = g1("REW263_WEL_FINWELL")
    prog_yes = sorted(o for o, v in prog.items() if v == "Yes")
    # keep those already substantive; the rest (currently 'No') split doc/ad-hoc
    need = [o for o in prog_yes if fw.get(o) in (None, "", "No")]
    for i, o in enumerate(need):
        setv("REW263_WEL_FINWELL", o, "Documented strategy" if i < round(0.60 * len(need)) else "Ad hoc provision")
    for o, v in prog.items():        # non-programme orgs must read 'No'
        if v != "Yes" and fw.get(o) not in (None, "", "No"):
            setv("REW263_WEL_FINWELL", o, "No")

    if WRITE:
        c.commit()

    # ---- achieved positive shares (to set target_share in generated_marginals.json) ----
    def share(q, positive_pred):
        d = g1(q); vals = [v for v in d.values() if v]
        return sum(1 for v in vals if positive_pred(v)) / len(vals), len(vals)
    fam_pos, fam_n = share("REW_BEN_FAM_002", lambda v: v != "None (statutory only)")
    fai_pos, fai_n = share("REW_FAI_079", lambda v: v in ("Yes", "In development"))
    fw_pos, fw_n = share("REW263_WEL_FINWELL", lambda v: v == "Documented strategy")
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    print("  >>> set generated_marginals.json target_share:")
    print("      REW_BEN_FAM_002    -> %.4f  (enhanced-any, n=%d)" % (fam_pos, fam_n))
    print("      REW_FAI_079        -> %.4f  (Yes+In development, n=%d)" % (fai_pos, fai_n))
    print("      REW263_WEL_FINWELL -> %.4f  (Documented strategy, n=%d)" % (fw_pos, fw_n))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
