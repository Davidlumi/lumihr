#!/usr/bin/env python3
"""Data QA class 7 — the annotations on the pages I had not yet mapped (2026-08-19).

Reading the last eight pages of David's PDF turned up five more findings. Two of the pages
(p18, p19 — the redundancy multiple and weeks ladders) were already closed by class 2, and
p11 (critical illness "Not offered" at 0%) by class 1, so they are not repeated here.

None of these five is anchored: checked against frozen_targets.json and qa_plausibility first.

  REW265_PAY_ACTINGUP (p4)  David: "Would of thought this would of be higher for the other
                options". 74.2% had NO documented acting-up or secondment pay policy. An
                employer that ever asks someone to act up handles the pay somehow — usually
                case-by-case, often by formal uplift. "No policy at all" as the answer for
                three quarters of the market is not credible.
                No 74.2% -> 36%, case-by-case 15% -> 39%, formal 10.9% -> 25%.

  REW_BEN_038 (p15)  David: "cycle to 2 work look low and dental looks high". Both are right.
                Cycle-to-work is a near-default salary-sacrifice scheme at this employer size;
                dental is a bolt-on that far fewer buy. Cycle to work 50.0% -> 64.1%,
                dental cover 38.1% -> 22.2%. Nothing else on the list moves.

  CAR_STATUS_01 (p15)  David: "Check 32% looks low". Raised 32.1% -> 42.0%. This stays
                coherent with the REW_PAY_109 allowance ladder in class 6: a status car and a
                cash allowance are alternatives offered side by side, which is exactly what
                CAR_STATUS_03 asks about, so both being common is the expected picture.

  REW_BEN_FLEX_ALLOW_01 (p13)  David: "Number do not look right". He is right twice over. The
                medians ran 2.1%–2.7% of base across all seven levels: too LOW for a real flex
                allowance, and too FLAT to be a by-level question at all — a 0.6pp spread from
                frontline to board is not a ladder. Rescaled per level onto a genuine one:

                    board 9.0 · director 8.0 · head of 6.5 · senior manager 5.5
                    manager 4.5 · supervisor 3.8 · frontline 3.2   (% of base)

                Each organisation is rescaled MULTIPLICATIVELY within its level, so every
                organisation keeps its rank and its own cross-level shape; only the scale
                moves. n stays 196.

  RED_COST_01 (p14)  David: "Double check this". The distribution is fine. The LABELLING is
                the defect, and it is a real one:
                  - unit was 'GBP' on a question whose options are pay multiples, so anything
                    keying off unit would format a multiple as a currency;
                  - the definition said "shown as a pay multiple" without ever saying a
                    multiple of WHAT. Weekly, monthly and annual pay differ by 50x here.
                Unit corrected to a multiple, and the text now says monthly base salary, which
                is the basis the existing distribution is drawn on (a 3x–4x mode is a few
                months' pay — the right order for an average UK redundancy).

Also carried here, from David's p9 note "Double check we have no overlaps in questions for
pension contributions and caps etc": the sweep found two genuinely overlapping PAIRS, and one
of them was actively contradicting itself on screen —

    ALLOW_03       "Are allowances pensionable?"            whole-organisation, single
    REW_PAY_020    "Allowances pensionability by level"     the same thing, per level

ALLOW_03 said 30% of employers have some pensionable allowances while REW_PAY_020 said 10% at
every level. Class 6 gives REW_PAY_020 a 6%–17% ladder; ALLOW_03 is aligned to it here so the
two cards agree (any-level-yes = 24%). The second pair — PROP_36b990f9 (banded, whole-org)
against REW_BEN_112 (by level) — is left alone: retiring a question changes the register, the
scoring and what members see, so it is David's ruling, not a data fix. It is written up in
DATA_ISSUES_2026-08-19.md for him.

Deterministic, count-conserving, history-appending. Run aggregate.run_snapshot(1) afterwards.
Dry-run by default. Writes only with:  --write --confirmed-by-david
"""
import json
import os
import random
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
SEED = 20260819

SINGLES = {
    "REW265_PAY_ACTINGUP": {"No": 96, "Case-by-case": 104,
                            "Formal allowance or uplift policy": 67},
    "CAR_STATUS_01": {"Yes": 110, "No": 152},
    # aligned to the REW_PAY_020 ladder that class 6 installs (any-level-yes ~24%)
    "ALLOW_03": {"No – non-pensionable": 203, "Yes – some allowances only": 45,
                 "Yes – all allowances": 17, "Varies by allowance/contract": 2},
}

# multi-select token prevalence: {qid: {token: target count}}
MULTI = {"REW_BEN_038": {"Cycle to work": 173, "Dental cover": 60}}

# numeric matrix: {qid: {row_id: target median}}
MEDIANS = {"REW_BEN_FLEX_ALLOW_01": {
    "board_executive": 9.0, "director": 8.0, "head_of": 6.5, "senior_manager": 5.5,
    "manager": 4.5, "supervisor_team_leader": 3.8, "frontline_individual_contributor": 3.2}}

# metadata-only repair
RED = {
    "id": "RED_COST_01",
    "unit": "x", "unit_display_name": "x monthly salary", "unit_type": "multiple",
    "definition": "Average total cost of one redundancy over the last completed year, as a "
                  "multiple of the employee's MONTHLY base salary. Include statutory and "
                  "enhanced redundancy pay, pay in lieu of notice and settlement sums.",
    "help_text": "As a multiple of monthly base salary — so 3x means the average redundancy "
                 "cost about three months' pay. Include enhanced terms, PILON and settlements.",
}


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)
    moves = 0

    print("-- single-select reshapes --")
    for qid, targets in SINGLES.items():
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        total = len(rows)
        if sum(targets.values()) != total:
            print("   REFUSE %-22s targets sum to %d but %d answered"
                  % (qid, sum(targets.values()), total))
            continue
        have = {}
        for r in rows:
            have.setdefault(r["value"], []).append(r["org_id"])
        unknown = set(targets) - set(have)
        if unknown:
            print("   REFUSE %-22s labels not in the data: %s" % (qid, sorted(unknown)))
            continue
        surplus, deficit = [], []
        for lab, want in targets.items():
            got = len(have.get(lab, []))
            if got > want:
                surplus.extend(rnd.sample(have[lab], got - want))
            elif got < want:
                deficit.extend([lab] * (want - got))
        rnd.shuffle(surplus)
        print("   %-22s n=%-4s %s" % (qid, total,
              " · ".join("%s %d->%d" % (l[:20], len(have.get(l, [])), w) for l, w in targets.items())))
        if WRITE:
            for org, dst in zip(surplus, deficit):
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (dst, org, qid))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, qid, dst))
        moves += len(deficit)

    print("\n-- multi-select token prevalence --")
    for qid, targets in MULTI.items():
        rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                            "AND matrix_row_id='' ORDER BY org_id", (qid,)).fetchall()
        cur = {r["org_id"]: [t.strip() for t in (r["value"] or "").split(";") if t.strip()]
               for r in rows}
        n = len(rows)
        for tok, want in targets.items():
            has = [o for o, ts in cur.items() if tok in ts]
            # never add a benefit to an organisation that answered "None"
            hasnt = [o for o, ts in cur.items() if tok not in ts and "None" not in ts]
            d = want - len(has)
            if d > 0:
                if len(hasnt) < d:
                    print("   REFUSE %s/%s — need %d, only %d eligible" % (qid, tok, d, len(hasnt)))
                    continue
                for o in rnd.sample(hasnt, d):
                    cur[o].append(tok)
            elif d < 0:
                for o in rnd.sample(has, -d):
                    cur[o].remove(tok)
            print("   %-14s %-22s %3d -> %3d of %d  (%.1f%% -> %.1f%%)"
                  % (qid, tok, len(has), want, n, 100.0 * len(has) / n, 100.0 * want / n))
            moves += abs(d)
        if WRITE:
            for org, toks in cur.items():
                val = ";".join(toks)
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (val, org, qid))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, qid, val))

    print("\n-- numeric matrix rescale (multiplicative: every organisation keeps its rank) --")
    for qid, targets in MEDIANS.items():
        for row_id, want in targets.items():
            rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND "
                                "snapshot_id=1 AND matrix_row_id=? ORDER BY org_id",
                                (qid, row_id)).fetchall()
            vals = []
            for r in rows:
                try:
                    vals.append((r["org_id"], float(r["value"])))
                except (TypeError, ValueError):
                    pass
            if not vals:
                print("   SKIP %s/%s — no numeric answers" % (qid, row_id))
                continue
            cur = median([v for _, v in vals])
            if cur <= 0:
                print("   REFUSE %s/%s — current median is %s" % (qid, row_id, cur))
                continue
            f = want / cur
            new = [(o, round(v * f, 1)) for o, v in vals]
            print("   %-24s median %.2f -> %.2f  (x%.2f)  range %.1f–%.1f  n=%d"
                  % (row_id, cur, median([v for _, v in new]), f,
                     min(v for _, v in new), max(v for _, v in new), len(new)))
            if WRITE:
                for org, v in new:
                    conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                                 "AND snapshot_id=1 AND matrix_row_id=?", (str(v), org, qid, row_id))
                    conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                                 "matrix_row_id,value,recorded_at) VALUES (?,1,?,?,?,datetime('now'))",
                                 (org, qid, row_id, str(v)))
            moves += len(new)

    print("\n-- RED_COST_01 metadata (a multiple was carrying unit 'GBP') --")
    r = conn.execute("SELECT unit, unit_type, definition FROM questions WHERE id=?",
                     (RED["id"],)).fetchone()
    print("   unit       %r -> %r" % (r["unit"], RED["unit"]))
    print("   unit_type  %r -> %r" % (r["unit_type"], RED["unit_type"]))
    print("   definition now states the multiple is of MONTHLY base salary")
    if WRITE:
        tol = json.loads(conn.execute("SELECT tolerance_json FROM questions WHERE id=?",
                                      (RED["id"],)).fetchone()[0] or "{}")
        tol["unit"] = RED["unit"]          # tolerance carried 'GBP' as well
        conn.execute("UPDATE questions SET unit=?, unit_display_name=?, unit_type=?, "
                     "definition=?, help_text=?, tolerance_json=? WHERE id=?",
                     (RED["unit"], RED["unit_display_name"], RED["unit_type"],
                      RED["definition"], RED["help_text"],
                      json.dumps(tol), RED["id"]))

    print("\n%d answers would move" % moves if not WRITE else "\n%d answers moved" % moves)
    if WRITE:
        conn.commit()
        print("committed. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
