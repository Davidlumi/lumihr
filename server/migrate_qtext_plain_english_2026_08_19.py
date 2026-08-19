#!/usr/bin/env python3
"""Plain-English review of every QUESTION TEXT (2026-08-19, David: "some are ambiguous, even
I did not know what they are asking — plain English always").

All 332 active question texts read. The 2026-08-10 pass rewrote metric DEFINITIONS and left
question text alone by design, so this field had never had a pass.

Structurally the bank is in good shape — one text not phrased as a question, no truncated
headings left. The problems are semantic, and they cluster into four kinds:

  1. NO UNIT OR BASIS. The reader cannot answer because the question never says in what.
     "Average redundancy cost per employee" against options reading 1x-2x — a multiple of
     what? Weekly, monthly and annual pay differ by ~50x. Same for max bonus "%" (of base
     salary), LTI "%" (of base salary), hourly "multipliers" (of the standard hourly rate)
     and allowance totals (per receiving employee, not organisation-wide — confirmed against
     the seeded values, which run £1,275-£2,000).

  2. AMBIGUOUS REFERENT. "What is the employer notice period?" and "What is the employee
     notice period?" sit next to each other, and neither says who gives notice to whom. Both
     are seeded with identical values, which is its own finding (see the report).

  3. WHICH SIDE IS THE NUMBER? REW_INC_061 asked for "the typical individual/business % split"
     and the answer is a single percentage — of which half? Checked against the data before
     rewriting: board 81-90%, manager 51-60%, frontline 21-30%, decreasing down the
     organisation. That is the BUSINESS share. Reading it as the individual share, which is
     the more natural reading of the old wording, would have inverted every card.

  4. JARGON WITH NO PLAIN EQUIVALENT ON SCREEN. "re-broke", "mid-life MOT", "compa-ratio",
     "referral SLA", "pillars", "categories of equal value". Each is correct trade language
     and each is now said in words a non-specialist can act on.

Every rewrite preserves the metric's meaning exactly — nothing here changes what is being
measured, so no seeded answer becomes wrong. Where the meaning was genuinely unclear it was
resolved against the DATA, not guessed.

One help_text bug fixed in passing: REW265_PAY_PAYCOMMS's help explains an option
("Statement with rationale") that does not exist on the question — it has two.

Text-only: text, short_description/benchmark_display and help_text. No option, type, unit or
value is touched. LUMI_DB-aware. Dry-run unless --write --confirmed-by-david.
"""
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

# qid -> (new text, new help_text or None to leave)
TEXT = {
    # --- 1. no unit or basis -------------------------------------------------------------
    "RED_COST_01": (
        "What did an average redundancy cost last year, as a multiple of monthly base salary?",
        None),
    "REW_PRO_098": (
        "What is the largest pay increase you would normally give on promotion, "
        "as a % of base salary?",
        "The usual ceiling, not the average. Choose 'Not capped' if there is no set limit."),
    "REW26_BEN_PENSION_COST_SHARE": (
        "What do employer pension contributions cost, as a % of your total reward spend?",
        None),
    "a7ed418e-b057-4b70-ab58-31e897b7c1b6": (
        "For each allowance you pay, what does a typical employee who receives it get in a "
        "year (£)?",
        "The amount ONE receiving employee gets over a year — not what the allowance costs "
        "the organisation in total. Leave a row blank if you do not pay it."),
    "REW_PAY_014": (
        "What premium is normally paid for working a UK bank holiday?",
        None),
    "323ffcf1-749b-43f3-bf34-1de6b8b1ca67": (
        "What is the maximum bonus someone can earn at each level, as a % of base salary?",
        "The most that can be earned at full payout, not the target."),
    "REW_INC_LTI_MAX_01": (
        "What is the maximum annual long-term incentive (LTI) award at each level, "
        "as a % of base salary?",
        None),
    "REW_INC_LTI_VALUE_TYP_01": (
        "What is the target annual long-term incentive (LTI) award at each level, "
        "as a % of base salary?",
        None),
    "REW_Q534581": (
        "For hourly-paid roles, what multiple of the standard hourly rate is paid at each "
        "time of day or week?",
        "1.0x means the standard rate with no uplift. Complete every row."),
    "REW26_WEL_BUDGET": (
        "What is your annual wellbeing budget per employee (£)?",
        None),

    # --- 2. ambiguous referent -----------------------------------------------------------
    "REW_Q524161": (
        "How much notice must the organisation give an employee to end their employment, "
        "at each level?",
        "Notice the EMPLOYER gives. The notice an employee must give to resign is a "
        "separate question."),
    "b1785613-96ed-4a64-9fd7-762d0ac65f19": (
        "How much notice must an employee give to resign, at each level?",
        "Notice the EMPLOYEE gives. The notice the organisation must give is a separate "
        "question."),
    "REW_PAY_020": (
        "At each level, do allowances count towards pensionable pay?",
        None),

    # --- 3. which side is the number -----------------------------------------------------
    "REW_INC_061": (
        "In your main bonus scheme, what share of the award is driven by BUSINESS "
        "performance at each level?",
        "The business/company-performance share. Whatever is left is individual "
        "performance — so 70% here means 70% business, 30% individual."),

    # --- 4. jargon with no plain equivalent on screen ------------------------------------
    "REW265_GOV_REBROKE": (
        "How often do you take your main benefits back out to market to test cost and cover?",
        None),
    "REW264_PEN_MIDLIFEMOT": (
        "Do you offer structured retirement or mid-career financial planning support?",
        None),
    "REW263_PAY_COMPARATIO": (
        "Where in the pay range do you aim to pay someone who is fully competent in "
        "their role?",
        None),
    "REW263_WEL_OH": (
        "Do employees have access to occupational health, and how quickly are referrals "
        "usually seen?",
        None),
    "PROP_216f7323": (
        "Which elements does your total reward strategy explicitly cover?",
        None),
    "REW262_GOV_EQUALVALUE": (
        "Have you grouped roles into 'work of equal value' categories — by skill, effort, "
        "responsibility and working conditions — as equal pay law defines them?",
        None),
    "REW263_GOV_UKPAYTRANS": (
        "How open is your organisation about pay, in adverts, internal ranges and "
        "published policy?",
        None),
    "REW264_HLT_GIPREHAB": (
        "If you offer group income protection, do you actively use the rehabilitation and "
        "early-intervention services included in it?",
        None),
    "REW263_BEN_NEURO": (
        "How do you handle reasonable-adjustment requests so employees — including "
        "neurodivergent employees — can access and use their benefits?",
        None),
    "REW264_PEN_SALSACRESPONSE": (
        "What do you intend to do about the £2,000 cap on pension salary sacrifice "
        "starting April 2029?",
        None),
    "REW_PAY_005": (
        "Where do you aim to sit against the market on base pay?",
        None),
}

# help_text-only corrections
HELP_ONLY = {
    "REW265_PAY_PAYCOMMS": "How individual pay review outcomes are communicated at each level.",
}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("DB: %s" % DB)
    print("MODE: %s\n" % ("WRITE" if WRITE else "DRY RUN — nothing will be changed"))
    n = 0

    for qid, (new_text, new_help) in TEXT.items():
        r = conn.execute("SELECT id, text, help_text FROM questions WHERE id=? AND "
                         "status='active'", (qid,)).fetchone()
        if not r:
            print("   SKIP %s — not an active question" % qid)
            continue
        if (r["text"] or "").strip() == new_text:
            continue
        print("%s" % qid)
        print("   was: %s" % (r["text"] or "").strip())
        print("   now: %s" % new_text)
        if new_help:
            print("   help: %s" % new_help)
        print()
        n += 1
        if WRITE:
            if new_help:
                conn.execute("UPDATE questions SET text=?, help_text=? WHERE id=?",
                             (new_text, new_help, qid))
            else:
                conn.execute("UPDATE questions SET text=? WHERE id=?", (new_text, qid))

    for qid, new_help in HELP_ONLY.items():
        r = conn.execute("SELECT help_text FROM questions WHERE id=?", (qid,)).fetchone()
        if not r or (r["help_text"] or "").strip() == new_help:
            continue
        print("%s  (help only — it described an option the question does not have)" % qid)
        print("   was: %s" % (r["help_text"] or "").strip())
        print("   now: %s\n" % new_help)
        n += 1
        if WRITE:
            conn.execute("UPDATE questions SET help_text=? WHERE id=?", (new_help, qid))

    print("%d question texts %s" % (n, "rewritten" if WRITE else "would be rewritten"))
    if WRITE:
        conn.commit()
        print("committed. Restart the server — library caches question metadata.")
    else:
        print("Re-run with --write --confirmed-by-david to apply.")
    conn.close()


if __name__ == "__main__":
    main()
