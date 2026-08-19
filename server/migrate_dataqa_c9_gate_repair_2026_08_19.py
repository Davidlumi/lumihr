#!/usr/bin/env python3
"""Data QA class 9 — repairing what classes 6-8 broke (2026-08-19).

Classes 6 and 7 were reported as 17/17 green. That report was WRONG. run_gates.sh:203 builds
its own throwaway from $ROOT/lumi.db unless LUMI_GATES_SRC is set, so the suite ran against
the live database as it stood BEFORE those migrations — it never saw the changes it was
supposed to be validating. The failures only surfaced once c6/c7 were live and a later run
copied them in. Three hard failures, all mine:

  1. PAIR-INCOHERENCE  REW263_BEN_DENTAL vs REW_BEN_038 — 43 organisations answering a
     question that is CONDITIONED on having dental cover at all (ruling r3sw23). Class 7 cut
     dental prevalence on REW_BEN_038 from 103 organisations to 60 because David said it
     looked high, but left all 103 answers standing on the funding follow-up. Cutting a
     parent without pruning its child is the bug; the prevalence cut itself was right.
     The 43 orphaned answers are deleted and the funding split is re-struck on the 60 that
     remain.

  2. MARGINAL-DRIFT  CAR_STATUS_01 — 0.420 achieved against a 0.350 register target, 7.0pp
     over a 5pp tolerance. David said 32.1% "looks low" and he was right, but only just: the
     register carries an EVIDENCED anchor for this one, grade C, sourced to the CIPD Reward
     Management Survey 2022 at ~35-37% of UK employers. 42% was my invention and it
     overshot a cited figure. Set to the register target exactly — 0.350, which still lifts
     the card the way David read it, by 3pp rather than 10.

     I missed this because my anchoring check read frozen_targets.json and qa_plausibility.py
     only. Register marginals live in generated_marginals.json under "marginals", a third
     source I never opened. Checked properly now: of everything classes 6-8 touched, only
     CAR_STATUS_01 and REW_BEN_HOL_003 are register marginals, and HOL_003 lands 4pp inside
     tolerance.

  3. REGEN-PIN  ALLOW_03 — I overrode a DAVID-SIGNED ruling. The pin records "2026-06-12,
     David-signed 72/20/8", and class 7 moved it to 76/17/6 to make it agree with the new
     REW_PAY_020 ladder. That is backwards: the signed whole-organisation figure is the
     anchor and the by-level matrix is what should have been aligned TO it. ALLOW_03 is
     restored to 187/51/27 exactly.

  4. REGEN-PIN  REW_PAY_020 — re-laddered against the restored ALLOW_03 instead. 78 of 267
     organisations (29.2%) say some or all allowances are pensionable, so a ladder that
     peaks near 27% at board and thins downward is what "aligned where ALLOW_03 says so"
     actually means. David's p8 complaint — the same figure at every level — still stands
     and is still fixed; only the height and the basis change.

     Its pin genuinely moves, so qa_engine_audit.py is updated with the ruling recorded
     against it. That is this codebase's own pattern for a ruled reseed (see the r3sw13 DK
     strip and the 2026-08-14 add50 re-record). ALLOW_03's pin needs no edit now.

Deterministic, history-appending. Run aggregate.run_snapshot(1) afterwards.
Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import os
import random
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SEED = 20260819

PARENT_QID, PARENT_TOKEN = "REW_BEN_038", "Dental cover"
CHILD_QID = "REW263_BEN_DENTAL"
CHILD_EMPLOYER_SHARE = 0.58        # employer-paid is the majority among those who offer it

CAR_QID = "CAR_STATUS_01"
CAR_TARGET = 0.350                 # generated_marginals.json -> marginals -> CAR_STATUS_01

# restored to the 2026-06-12 David-signed 72/20/8 recorded in the qa_engine_audit pin
ALLOW_QID = "ALLOW_03"
ALLOW_SIGNED = {"No – non-pensionable": 187, "Yes – some allowances only": 51,
                "Yes – all allowances": 27, "Varies by allowance/contract": 2}

# re-laddered against that restored anchor: 78 of 267 orgs (29.2%) have some pensionable
# allowance, concentrated at the top, thinning downward. Flat-at-every-level is still gone.
LADDER_QID = "REW_PAY_020"
LADDER = {"board_executive": 73, "director": 64, "head_of": 54, "senior_manager": 43,
          "manager": 32, "supervisor_team_leader": 22,
          "frontline_individual_contributor": 16}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)

    print("-- 1. dental: prune the child to the parent's population --")
    parents = {r["org_id"] for r in conn.execute(
        "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
        "AND matrix_row_id=''", (PARENT_QID,))
        if PARENT_TOKEN in [t.strip() for t in (r["value"] or "").split(";")]}
    kids = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (CHILD_QID,)).fetchall()
    orphans = [r["org_id"] for r in kids if r["org_id"] not in parents]
    keep = [r["org_id"] for r in kids if r["org_id"] in parents]
    print("   %s offers dental: %d organisations" % (PARENT_QID, len(parents)))
    print("   %s has answers  : %d  -> %d orphaned, %d kept"
          % (CHILD_QID, len(kids), len(orphans), len(keep)))
    if WRITE:
        for org in orphans:
            conn.execute("DELETE FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1 "
                         "AND matrix_row_id=''", (org, CHILD_QID))

    want_emp = int(round(CHILD_EMPLOYER_SHARE * len(keep)))
    order = sorted(keep)
    rnd.shuffle(order)
    emp, vol = order[:want_emp], order[want_emp:]
    print("   re-struck on the %d that remain: Employer-paid %d (%.0f%%) · Voluntary %d (%.0f%%)"
          % (len(keep), len(emp), 100.0 * len(emp) / max(1, len(keep)),
             len(vol), 100.0 * len(vol) / max(1, len(keep))))
    if WRITE:
        for orgs, lab in ((emp, "Employer-paid"), (vol, "Voluntary (employee-funded)")):
            for org in orgs:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (lab, org, CHILD_QID))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, CHILD_QID, lab))

    print("\n-- 2. %s back to the register's cited target --" % CAR_QID)
    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (CAR_QID,)).fetchall()
    total = len(rows)
    yes = [r["org_id"] for r in rows if r["value"] == "Yes"]
    no = [r["org_id"] for r in rows if r["value"] == "No"]
    want = int(round(CAR_TARGET * total))
    print("   Yes %d of %d (%.1f%%) -> %d (%.1f%%)  [register target %.3f, CIPD-sourced]"
          % (len(yes), total, 100.0 * len(yes) / total, want, 100.0 * want / total, CAR_TARGET))
    move = len(yes) - want
    if move > 0 and WRITE:
        for org in rnd.sample(yes, move):
            conn.execute("UPDATE answers SET value='No' WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (org, CAR_QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'','No',datetime('now'))",
                         (org, CAR_QID))
    elif move < 0 and WRITE:
        for org in rnd.sample(no, -move):
            conn.execute("UPDATE answers SET value='Yes' WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (org, CAR_QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'','Yes',datetime('now'))",
                         (org, CAR_QID))

    print("\n-- 3. %s restored to the David-signed 72/20/8 --" % ALLOW_QID)
    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (ALLOW_QID,)).fetchall()
    if sum(ALLOW_SIGNED.values()) != len(rows):
        print("   REFUSE — signed counts sum to %d but %d answered"
              % (sum(ALLOW_SIGNED.values()), len(rows)))
    else:
        held = {}
        for r in rows:
            held.setdefault(r["value"], []).append(r["org_id"])
        surplus, deficit = [], []
        for lab, want in ALLOW_SIGNED.items():
            got = len(held.get(lab, []))
            if got > want:
                surplus.extend(rnd.sample(held[lab], got - want))
            elif got < want:
                deficit.extend([lab] * (want - got))
        rnd.shuffle(surplus)
        for lab, want in ALLOW_SIGNED.items():
            print("   %-32s %3d -> %3d" % (lab, len(held.get(lab, [])), want))
        if WRITE:
            for org, dst in zip(surplus, deficit):
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (dst, org, ALLOW_QID))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, ALLOW_QID, dst))

    print("\n-- 4. %s re-laddered against that anchor --" % LADDER_QID)
    tot_yes = 0
    for row_id, want_yes in LADDER.items():
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND "
                            "snapshot_id=1 AND matrix_row_id=? ORDER BY org_id",
                            (LADDER_QID, row_id)).fetchall()
        yes = [r["org_id"] for r in rows if r["value"] == "Yes"]
        no = [r["org_id"] for r in rows if r["value"] == "No"]
        d = want_yes - len(yes)
        pool, dst = (no, "Yes") if d > 0 else (yes, "No")
        print("   %-34s Yes %3d -> %3d  (%.1f%% of %d)"
              % (row_id, len(yes), want_yes, 100.0 * want_yes / len(rows), len(rows)))
        tot_yes += want_yes
        if d and WRITE:
            for org in rnd.sample(pool, abs(d)):
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=?", (dst, org, LADDER_QID, row_id))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,?,?,datetime('now'))",
                             (org, LADDER_QID, row_id, dst))
    print("   pin becomes: {'No': %d, 'Yes': %d}" % (1890 - tot_yes, tot_yes))

    if WRITE:
        conn.commit()
        print("\ncommitted. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("\nRe-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
