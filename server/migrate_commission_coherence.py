# -*- coding: utf-8 -*-
"""migrate_commission_coherence.py — the commission-family coherence diff (David 2026-07-25,
"confirm six, a, own diff, fix fixtures, hold prevalence"). SEED-COHERENCE class.

AUTHORITY: (a) existence governs — INC_135 is authoritative; details conform to it. The provenance
override is recorded in DECISIONS (details were the elder draw; disqualified on their own terms).
PHASE 1 (applied): for every org with INC_135='No':
    INC_136 substantive  -> 'Not applicable'                       (R1)
    COMMCAP substantive  -> 'Not applicable (no commission plans)' (R2, lands in the Diff-19a na_code)
  FIXTURES INCLUDED — ruled corrections (named per-org approval required before any live write).
PHASE 2 (enumerated, NOT applied): the residue after Phase 1 is the 2-org exceptions pair
  (INC_135='Yes' ∧ COMMCAP substantive ∧ INC_136='Not applicable') == the reverse case — repairing them
  means INVENTING a structure value, which ruling (a) does not license. Listed for David.
PREVALENCE HELD: INC_135's answers are NEVER touched — its per-org values asserted byte-identical.

Guards: dry-run default; --write; live needs --confirmed-by-david AND --fixtures-approved (the named
fixture yes is a separate, explicit flag — the write refuses without it).
"""
import argparse, hashlib, json, os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
I135, I136, CAP = "REW_INC_135", "REW_INC_136", "REW265_INC_COMMCAP"
NA136, NACAP = "Not applicable", "Not applicable (no commission plans)"
FIX = {"5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7": "Thornbridge Retail Group plc",
       "833beedb-c4c9-43aa-a6b3-3dbee9e76e99": "Thornbridge Advisory plc"}
FROZEN8 = {"REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"}
STAMP = "2026-07-25 commission-coherence"


def book_excl(c, excl):
    h = hashlib.sha256()
    q = ("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') FROM answers "
         "WHERE question_id NOT IN (%s) ORDER BY 1,2,3,4" % ",".join("?" * len(excl)))
    for r in c.execute(q, excl):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--fixtures-approved", dest="fixok", action="store_true",
                    help="David's NAMED per-org fixture approval (required for any write that touches a fixture)")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
    assert not (FROZEN8 & {I135, I136, CAP}), "frozen-8 grazed"
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row

    g = lambda q: {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,))}
    i135, i136, cap = g(I135), g(I136), g(CAP)
    no135 = {o for o, v in i135.items() if v == "No"}
    yes135 = {o for o, v in i135.items() if v == "Yes"}
    R1 = sorted({o for o, v in i136.items() if v != NA136} & no135)
    R2 = sorted({o for o, v in cap.items() if v != NACAP} & no135)
    exceptions = sorted(o for o in yes135 if cap.get(o) not in (None, NACAP) and i136.get(o) == NA136)
    logged = len(set(R1) | set(R2))
    fix_touch = [(o, FIX[o]) for o in FIX if o in R1 or o in R2]

    print("commission-coherence %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  logged class (R1∪R2): %d | R1=%d R2=%d | cells=%d (incl. %d fixture cells)"
          % (logged, len(R1), len(R2), len(R1) + len(R2), sum((o in R1) + (o in R2) for o in FIX)))
    print("  Phase-2/reverse exceptions (PROPOSED, not applied): %d %s" % (len(exceptions), [o[:8] for o in exceptions]))
    print("  fixtures touched: %s" % [n for _, n in fix_touch])
    print("  INC_135 headline (IMMOVABLE): Yes=%d/%d = %.1f%%" % (len(yes135), len(i135), 100 * len(yes135) / len(i135)))
    if not a.write:
        print("dry-run complete"); c.close(); return
    if fix_touch and not a.fixok:
        print("REFUSED: fixtures in scope — the write requires --fixtures-approved (David's NAMED yes)"); sys.exit(3)

    pre_book = book_excl(c, [I136, CAP])                 # INC_135 is OUTSIDE the touched set -> in this hash
    pre_135 = sorted(i135.items())
    npre = {q: c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] for q in (I135, I136, CAP)}
    cur = c.cursor()
    for o in R1:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " R1", I136, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (NA136, I136, o))
    for o in R2:
        cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                    "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                    (STAMP + " R2", CAP, o))
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (NACAP, CAP, o))

    # ---- asserts before commit ----
    assert book_excl(c, [I136, CAP]) == pre_book, "NON-FAMILY BOOK CHANGED (or INC_135 grazed)"
    assert sorted(g(I135).items()) == pre_135, "INC_135 ANSWERS MOVED — prevalence is immovable"
    for q in (I135, I136, CAP):
        assert c.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (q,)).fetchone()[0] == npre[q], "n changed on %s" % q
    i136b, capb = g(I136), g(CAP)
    R1b = {o for o, v in i136b.items() if v != NA136} & no135
    R2b = {o for o, v in capb.items() if v != NACAP} & no135
    R3a = [o for o in yes135 if i136b.get(o) not in (None, NA136) and capb.get(o) == NACAP]
    R3b = [o for o in yes135 if capb.get(o) not in (None, NACAP) and i136b.get(o) == NA136]
    assert not R1b and not R2b and not R3a, (len(R1b), len(R2b), len(R3a))
    assert sorted(R3b) == exceptions, "exceptions drifted: %s" % R3b
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "r1": len(R1), "r2": len(R2),
                      "cells": len(R1) + len(R2), "logged_class_after": 0, "r3a_after": 0,
                      "exceptions_r3b": len(R3b), "inc135": "byte-identical",
                      "fixtures_corrected": [n for _, n in fix_touch], "non_family_book": "unchanged"}, indent=2))
    c.close()


if __name__ == "__main__":
    main()
