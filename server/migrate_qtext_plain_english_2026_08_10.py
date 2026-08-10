#!/usr/bin/env python3
"""Plain-English review of metric question text (2026-08-10).

Reviewed all 333 active question texts (parallel review + meaning-preservation verify).
13 needed changing — each PRESERVES the metric's meaning and answerability by its
EXISTING options; most fix a stem that did not match its own answer set (yes/no stems
on maturity-ladder / multi-select / numeric fields, or a stem measuring a different
thing than the options). Text-only (no options/type/values/data touched). The DB is
the live source the app serves; the master-register CSVs are historical lineage and
are not reloaded at runtime. LUMI_DB-aware; DRY-RUN unless --write --confirmed-by-david.

    python3 server/migrate_qtext_plain_english_2026_08_10.py                        # dry run
    python3 server/migrate_qtext_plain_english_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

REWRITES = {
    "REW263_BEN_NEURO": "What level of reasonable-adjustments and neurodiversity support do you provide for reward/benefits access?",
    "REW263_GOV_FIREREHIRE": "When you change pay, pension or benefit terms, what is your policy on avoiding dismiss-and-rehire (fire-and-rehire, restricted from Jan 2027)?",
    "REW263_GOV_REWTEAM": "How large is your dedicated reward team (in FTE)?",
    "REW265_GOV_TRS": "What proportion of employees receive a total reward statement (TRS)?",
    "REW_PRO_035": "Outside the annual review and promotions, what is pay progression based on?",
    "REW264_HLT_MENSHEALTH": "Do you provide men's health support (e.g. screening, prostate/testicular pathways, targeted mental health support)?",
    "REW_FAI_128": "After pay reviews, does your organisation check whether top performers are paid above the market median?",
    "REW_PAY_018": "Is there a minimum payment for call-outs (e.g., minimum hours paid)?",
    "REW265_TIME_EXTRADAYS": "Which additional discretionary days off do you offer? (Volunteering leave is covered by a separate question.)",
    "REW265_TIME_FLEXPATTERN": "Which flexible-working patterns do you operate as standard?",
    "REW265_TIME_WORKATION": "What is your policy on remote working abroad ('workation')?",
    "REW264_WEL_COLACTION": "Which cost-of-living interventions have you made in the last 24 months?",
    "REW26_WEL_BUDGET": "What is the annual wellbeing budget per employee?",
}


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    changed = 0
    for qid, new in REWRITES.items():
        cur = c.execute("SELECT text FROM questions WHERE id=?", (qid,)).fetchone()
        if cur is None:
            print("  MISSING:", qid); continue
        if (cur["text"] or "") == new:
            continue
        changed += 1
        if WRITE:
            c.execute("UPDATE questions SET text=? WHERE id=?", (new, qid))
    if WRITE:
        c.commit()
    print(("APPLIED" if WRITE else "DRY RUN") + " — %d/%d question texts updated" % (changed, len(REWRITES)))
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
