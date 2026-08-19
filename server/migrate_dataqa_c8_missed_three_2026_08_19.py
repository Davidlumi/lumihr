#!/usr/bin/env python3
"""Data QA class 8 — the three annotations that were mapped but never actually fixed.

David asked whether classes 1-7 closed every annotation on his PDF. Extracting the text layer
off all 23 pages and ticking each one against the live data says no: three were carried as
"mapped" but no migration ever touched them. All three are real.

  REW_PAY_007 (p6/p7)  David: "Add job adverts and chatgot". The benchmark-sources list offers
                five options and omits the two sources most employers actually reach for first.
                Job adverts are the oldest informal benchmark there is, and AI assistants are
                now a routine (if unreliable) first pass. Without them the card cannot show how
                common either is, and a member using them can only answer "Other".
                Added: "Job adverts / published salary ranges" (54%) and "AI assistants
                (e.g. ChatGPT, Copilot)" (23%). Appended before "Other", so the catch-all stays
                last. Existing counts are untouched — this only adds.

                The heading was also broken English — "Sources do you use for external pay
                benchmarks" — so it is reworded to "Sources used for external pay benchmarks".

  REW_BEN_REM_PAY_004 (p5)  David: "Update quesiot text". The card heading was a sentence cut
                off mid-clause: "Pay decisions for remote roles reviewed to ensure". Ensure
                what? Class 3 fixed three headings of exactly this kind and missed this one.
                Now "How remote-role pay decisions are checked".

  REW263_BEN_DENTAL (p10)  David: "Numbers are wong". 67% voluntary against 33% employer-paid
                is the wrong way round. Among employers that offer dental cover at all, paying
                for it is the more common arrangement; voluntary employee-funded dental is the
                cheaper bolt-on and the minority. Flipped to 58% employer-paid / 42% voluntary
                — not a mirror image, because voluntary is genuinely common enough to stay
                substantial. n stays 103.

Neither REW_PAY_007 nor REW263_BEN_DENTAL is anchored: checked against frozen_targets.json and
the qa_plausibility register first.

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

SRC_QID = "REW_PAY_007"
SRC_CATCHALL = "Other"
SRC_NEW = [
    ("Job adverts / published salary ranges", "JOB_ADVERTS_PUBLISHED_SALARY_RANGES", 0.54),
    ("AI assistants (e.g. ChatGPT, Copilot)", "AI_ASSISTANTS_CHATGPT_COPILOT", 0.23),
]
SRC_HEADING = "Sources used for external pay benchmarks"

REM_QID = "REW_BEN_REM_PAY_004"
REM_HEADING = "How remote-role pay decisions are checked"

DENTAL_QID = "REW263_BEN_DENTAL"
DENTAL_TARGETS = {"Employer-paid": 60, "Voluntary (employee-funded)": 43}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    rnd = random.Random(SEED)

    print("-- %s: two missing benchmark sources --" % SRC_QID)
    r = conn.execute("SELECT options_json, short_description FROM questions WHERE id=?",
                     (SRC_QID,)).fetchone()
    opts = json.loads(r["options_json"] or "[]")
    have = {(o.get("label") or "").strip().lower() for o in opts}
    add = [(l, c, p) for l, c, p in SRC_NEW if l.strip().lower() not in have]
    if not add:
        print("   both already present")
    else:
        keep = [o for o in opts if (o.get("label") or "") != SRC_CATCHALL]
        tail = [o for o in opts if (o.get("label") or "") == SRC_CATCHALL]
        merged = keep + [{"code": c, "label": l, "order": 0, "is_na": False}
                         for l, c, _ in add] + tail
        for i, o in enumerate(merged, 1):
            o["order"] = i
        for l, c, _ in add:
            print("   + %-40s %s" % (l, c))
        print("   %d options -> %d (%r stays last)" % (len(opts), len(merged), SRC_CATCHALL))
        if WRITE:
            conn.execute("UPDATE questions SET options_json=? WHERE id=?",
                         (json.dumps(merged, ensure_ascii=False), SRC_QID))
    print("   heading %r" % r["short_description"])
    print("        -> %r" % SRC_HEADING)
    if WRITE:
        conn.execute("UPDATE questions SET short_description=?, benchmark_display=? WHERE id=?",
                     (SRC_HEADING, SRC_HEADING, SRC_QID))

    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (SRC_QID,)).fetchall()
    cur = {x["org_id"]: [t.strip() for t in (x["value"] or "").split(";") if t.strip()]
           for x in rows}
    n = len(rows)
    for lab, _code, pct in SRC_NEW:
        want = int(round(pct * n))
        cand = [o for o, ts in cur.items() if lab not in ts]
        k = want - (n - len(cand))
        if k <= 0 or len(cand) < k:
            print("   SKIP %-40s already at target" % lab)
            continue
        for o in rnd.sample(cand, k):
            cur[o].append(lab)
        print("   %-40s %3d of %d  (%.0f%%)" % (lab, want, n, 100.0 * want / n))
    if WRITE:
        for org, toks in cur.items():
            val = ";".join(toks)
            conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                         "AND snapshot_id=1 AND matrix_row_id=''", (val, org, SRC_QID))
            conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                         "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                         (org, SRC_QID, val))

    print("\n-- %s: a heading that stopped mid-sentence --" % REM_QID)
    r = conn.execute("SELECT short_description FROM questions WHERE id=?", (REM_QID,)).fetchone()
    print("   %r" % r["short_description"])
    print("-> %r" % REM_HEADING)
    if WRITE:
        conn.execute("UPDATE questions SET short_description=?, benchmark_display=? WHERE id=?",
                     (REM_HEADING, REM_HEADING, REM_QID))

    print("\n-- %s: employer-paid vs voluntary, the wrong way round --" % DENTAL_QID)
    rows = conn.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 "
                        "AND matrix_row_id='' ORDER BY org_id", (DENTAL_QID,)).fetchall()
    total = len(rows)
    if sum(DENTAL_TARGETS.values()) != total:
        print("   REFUSE — targets sum to %d but %d answered"
              % (sum(DENTAL_TARGETS.values()), total))
    else:
        held = {}
        for x in rows:
            held.setdefault(x["value"], []).append(x["org_id"])
        surplus, deficit = [], []
        for lab, want in DENTAL_TARGETS.items():
            got = len(held.get(lab, []))
            if got > want:
                surplus.extend(rnd.sample(held[lab], got - want))
            elif got < want:
                deficit.extend([lab] * (want - got))
        rnd.shuffle(surplus)
        for lab, want in DENTAL_TARGETS.items():
            print("   %-32s %3d -> %3d  (%.0f%% -> %.0f%%)"
                  % (lab, len(held.get(lab, [])), want,
                     100.0 * len(held.get(lab, [])) / total, 100.0 * want / total))
        if WRITE:
            for org, dst in zip(surplus, deficit):
                conn.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? "
                             "AND snapshot_id=1 AND matrix_row_id=''", (dst, org, DENTAL_QID))
                conn.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,"
                             "matrix_row_id,value,recorded_at) VALUES (?,1,?,'',?,datetime('now'))",
                             (org, DENTAL_QID, dst))

    if WRITE:
        conn.commit()
        print("\ncommitted. Now rebuild: python3 -c \"import aggregate; aggregate.run_snapshot(1)\"")
    else:
        print("\nRe-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
