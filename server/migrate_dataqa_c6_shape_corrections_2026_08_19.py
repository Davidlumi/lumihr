#!/usr/bin/env python3
"""Data QA class 6 — the distribution shapes David called out by eye (2026-08-19).

The seven remaining annotations from his review, each a marginal that is possible but not
believable. None of these seven is anchored: checked against frozen_targets.json and the
qa_plausibility register before a value was moved, which is the check I failed to do earlier
today on REW_BEN_REM_PAY_001.

  REW_PAY_020   "Allowances pensionability by level" — David: "very odd the same and the
                same at every level". EVERY one of the seven levels sat at exactly 27/243.
                A seniority ladder that is flat to the unit is a generator artefact, not a
                finding. Given a gentle gradient: pensionable allowances are somewhat more
                common at the top, but uncommon everywhere.

  REW_PAY_109   "Role levels eligible for a status car allowance" — David: "numbers look too
                low for yes at the higher levels". Board, Director and Head of were all
                identical at 44.4%, and a status car is far more common at board level than
                that. Given a real ladder, 72% down to 1%.

  RED_PROC_01   "Documented redundancy process" — David: "would have thought yes was higher".
                39% saying No is not credible: a documented process is basic employment-law
                hygiene for an employer of any size. 56% -> 78% yes.

  REW_BEN_039   "Flexible benefits platform" — David: "no way a third is in development".
                35/32/33 is a three-way split, and "in development" is the least believable
                third of it. 33% -> 12%, with the difference going to No.

  REW_BEN_HOL_004  "Additional annual leave by length of service" — David: "yes is way too
                high". 75.5% yes. Service-related leave is common, not near-universal.
                -> 44%.

  REW_BEN_HOL_003  "Annual leave buy/sell" — David: "few companies allow to sell holiday,
                more allow to buy". 27.5% could sell, which is not "few". Buy-only rises,
                both falls, sell-only stays rare.

  REW265_TIME_FLEXPATTERN  "Compressed hours or core-hours flexibility as standard" —
                David: "seems high". Only 13.9% offered NOTHING, i.e. 86% offered some
                flexible pattern AS STANDARD. -> 32% none, which pulls every other option
                down proportionally.

All changes are count-conserving within their question, deterministic, and history-appending.
Modelled on UK practice, not measured — same basis as the rest of this seeded bank.

Run aggregate.run_snapshot(1) afterwards.
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

# matrix yes/no ladders: {qid: {row_id: target Yes count}}
LADDERS = {
    "REW_PAY_020": {"board_executive": 46, "director": 41, "head_of": 35, "senior_manager": 30,
                    "manager": 24, "supervisor_team_leader": 19,
                    "frontline_individual_contributor": 16},
    "REW_PAY_109": {"board_executive": 194, "director": 167, "head_of": 122, "senior_manager": 68,
                    "manager": 22, "supervisor_team_leader": 5,
                    "frontline_individual_contributor": 3},
}

# single-select reshapes: {qid: {label: target count}} — must sum to the current total
SINGLES = {
    # "Partially" is is_na=True — raising it would shrink the scored base, so it is held at 11
    # and only the Yes/No pair is reshaped. Yes = 200 of the 251 scored (79.7%).
    "RED_PROC_01": {"Yes": 200, "No": 51, "Partially (varies by region/business unit)": 11},
    "REW_BEN_039": {"Yes": 108, "No": 130, "In development": 32},
    "REW_BEN_HOL_004": {"Yes": 113, "No": 144},
    "REW_BEN_HOL_003": {"No": 124, "Yes - buy only": 98,
                        "Yes - both buy and sell options are available": 31,
                        "Yes - sell only": 5},
}

# multi-select: make this token exclusive on enough organisations to hit the target count
MULTI_EXCLUSIVE = {"REW265_TIME_FLEXPATTERN": ("None", 85)}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)
    moves = 0

    print("-- matrix ladders (per level, Yes/No) --")
    for qid, targets in LADDERS.items():
        for row_id, want_yes in targets.items():
            rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                                "AND matrix_row_id=? ORDER BY org_id", (qid, row_id)).fetchall()
            if not rows:
                print("   SKIP %s/%s — no answers" % (qid, row_id))
                continue
            yes = [r["org_id"] for r in rows if r["value"] == "Yes"]
            no = [r["org_id"] for r in rows if r["value"] == "No"]
            delta = want_yes - len(yes)
            src, dst, pool = ("No", "Yes", no) if delta > 0 else ("Yes", "No", yes)
            k = abs(delta)
            if k == 0:
                continue
            if len(pool) < k:
                print("   REFUSE %s/%s — need %d from %r, only %d" % (qid, row_id, k, src, len(pool)))
                continue
            pick = rnd.sample(pool, k)
            print("   %-14s %-32s Yes %3d -> %3d  (%.0f%% of %d)"
                  % (qid, row_id, len(yes), want_yes, 100.0 * want_yes / len(rows), len(rows)))
            if WRITE:
                for org in pick:
                    conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                                 "AND snapshot_id=1 AND matrix_row_id=?", (dst, org, qid, row_id))
                    conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                                 "matrix_row_id,value,recorded_at) VALUES (?,1,?,?,?,datetime('now'))",
                                 (org, qid, row_id, dst))
            moves += k

    print("\n-- single-select reshapes --")
    for qid, targets in SINGLES.items():
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        total = len(rows)
        if sum(targets.values()) != total:
            print("   REFUSE %-22s targets sum to %d but %d answered — would not conserve n"
                  % (qid, sum(targets.values()), total))
            continue
        have = {}
        for r in rows:
            have.setdefault(r["value"], []).append(r["org_id"])
        surplus, deficit = [], []
        for lab, want in targets.items():
            got = len(have.get(lab, []))
            if got > want:
                surplus.extend((lab, o) for o in rnd.sample(have[lab], got - want))
            elif got < want:
                deficit.extend([lab] * (want - got))
        rnd.shuffle(surplus)
        print("   %-22s n=%-4s %s" % (qid, total,
              " · ".join("%s %d->%d" % (l[:18], len(have.get(l, [])), w) for l, w in targets.items())))
        if WRITE:
            for (_src, org), dst in zip(surplus, deficit):
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (dst, org, qid))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, qid, dst))
        moves += len(deficit)

    print("\n-- multi-select: raise the 'nothing offered' share --")
    for qid, (token, want) in MULTI_EXCLUSIVE.items():
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        cur = [r for r in rows if (r["value"] or "").strip() == token]
        oth = [r for r in rows if (r["value"] or "").strip() != token]
        k = want - len(cur)
        if k <= 0 or len(oth) < k:
            print("   SKIP %s — already at %d of %d" % (qid, len(cur), len(rows)))
            continue
        pick = rnd.sample(oth, k)
        print("   %-24s %r %d -> %d of %d  (%.0f%% -> %.0f%%)"
              % (qid, token, len(cur), want, len(rows),
                 100.0 * len(cur) / len(rows), 100.0 * want / len(rows)))
        if WRITE:
            for r in pick:
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (token, r["org_id"], qid))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (r["org_id"], qid, token))
        moves += k

    # Housekeeping, not a David finding: migrate_dataqa_c4a wrote REW265_BEN_PMICOMP with a
    # "; " join. Every aggregate split site strips, so the counts are right and nothing on the
    # card is wrong — but it is the only question in the bank stored that way, and an exact-match
    # query would silently miss those 180 rows. Normalised to the bank's ";" separator.
    print("\n-- normalise the multi-select separator on REW265_BEN_PMICOMP --")
    odd = conn.execute("SELECT org_id, value FROM answers WHERE question_id='REW265_BEN_PMICOMP' "
                       "AND snapshot_id=1 AND matrix_row_id='' AND value LIKE '%; %'").fetchall()
    print("   %d rows use '; ' — the rest of the bank uses ';'" % len(odd))
    if WRITE:
        for r in odd:
            conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id="
                         "'REW265_BEN_PMICOMP' AND snapshot_id=1 AND matrix_row_id=''",
                         (r["value"].replace("; ", ";"), r["org_id"]))

    print("\n%d answers would move" % moves if not WRITE else "\n%d answers moved" % moves)
    if WRITE:
        conn.commit()
        print("committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
