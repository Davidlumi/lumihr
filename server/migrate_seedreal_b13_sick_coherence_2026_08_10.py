#!/usr/bin/env python3
"""Seed-realism B13 — SICK_005/SICK_001 coherence repair (2026-08-10).

M1 flipped 3 orgs' REW_BEN_SICK_001 'No sick pay provided' -> 'Statutory sick pay only'
without checking REW_BEN_SICK_005 (OSP eligibility-rules), which is a coherence child
that requires SICK_001 to be OSP-exists ('Enhanced occupational sick pay' or
'Combination of enhanced sick pay and SSP'). One org — the demo fixture (Thornbridge)
— carries SICK_005='Yes' with a non-OSP SICK_001, so it violates the pair. Repair:
any org whose SICK_005 is substantive but SICK_001 is statutory-only/no-pay is given
SICK_001='Combination of enhanced sick pay and SSP' (it demonstrably offers OSP). Tiny
marginal shift (well within tolerance). Deterministic; DRY-RUN unless --write
--confirmed-by-david.

    python3 server/migrate_seedreal_b13_sick_coherence_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b13_sick_coherence_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
NON_OSP = ("Statutory sick pay only", "No sick pay provided", "", None)


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    s1 = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_SICK_001' AND matrix_row_id='' AND snapshot_id=1")}
    s5 = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_SICK_005' AND matrix_row_id='' AND snapshot_id=1")}
    fixed = 0
    for org, v5 in s5.items():
        if v5 and s1.get(org) in NON_OSP:
            fixed += 1
            if WRITE:
                c.execute("UPDATE answers SET value='Combination of enhanced sick pay and SSP' "
                          "WHERE org_id=? AND question_id='REW_BEN_SICK_001' AND matrix_row_id='' AND snapshot_id=1", (org,))
    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — SICK_001 OSP-repaired for %d org(s)" % fixed)
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
