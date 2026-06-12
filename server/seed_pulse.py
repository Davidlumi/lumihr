# -*- coding: utf-8 -*-
"""Seed the launch pulse: "EU Pay Transparency readiness 2026".

THIS IS THE v1 CREATION AFFORDANCE (flagged in DECISIONS.md): pulses are a
lumi/superadmin action and the back-office console is unbuilt (D2), so
creation runs through this script + the pulses.py lifecycle functions.
Members can only join and respond.

Demo cohort: 12 seed organisations' pulse responses are generated with a
seeded RNG (synthetic, like the rest of the pool — the platform carries the
'illustrative sample data' label). Seeded + reproducible:
rng = Random("PULSE_PTD26|" + org_id). Idempotent: refuses to re-seed.

Questions: 3 core-library references (incl. a numeric and a matrix — the
same-engine proof) + 2 newly authored pulse-origin questions (a
multi-select and a yes/no — the historically broken types ride the same
engine path).
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from db import get_conn, uj
import pulses

conn = get_conn()
if conn.execute("SELECT 1 FROM pulses WHERE name LIKE 'EU Pay Transparency%'").fetchone():
    print("pulse already seeded — refusing to duplicate")
    sys.exit(0)

pid = pulses.create_pulse(
    "EU Pay Transparency readiness 2026",
    "Where UK reward teams actually are on the 2026 EU Pay Transparency Directive — "
    "disclosure practice, audits, and pay positioning. Two minutes; free to participants.",
    question_ids=[
        "REW26_GOV_EU_PTD_PREP",     # core single_select (also lives in the core — two cohorts, two numbers)
        "PROP_9e4ad87f",             # core numeric: 2026 salary increase budget (the separation-proof target)
        "REW_PAY_MKT_POS_01",        # core matrix-numeric: base salary vs market median by level
    ],
    new_questions=[
        {
            "id": "PULSE_PTD_DISCLOSURES",
            "title": "Pay-transparency disclosures already made",
            "text": "Which pay-transparency disclosures do you already make?",
            "help_text": "Tick everything in place today, however informal.",
            "type": "multi_select", "polarity": "higher_is_better",
            "options": [
                {"code": "ADVERT_RANGES", "label": "Salary ranges in job adverts", "order": 1, "is_na": False},
                {"code": "INTERNAL_BANDS", "label": "Internal pay bands published to employees", "order": 2, "is_na": False},
                {"code": "GPG_NARRATIVE", "label": "Gender pay gap narrative beyond the statutory minimum", "order": 3, "is_na": False},
                {"code": "EU_ENTITY", "label": "EU entity-level pay reporting", "order": 4, "is_na": False},
                {"code": "NONE", "label": "None of these", "order": 5, "is_na": False},
            ],
        },
        {
            "id": "PULSE_PTD_EQUITY_AUDIT",
            "title": "Pay-equity audit in the last 12 months",
            "text": "Have you run a pay-equity audit in the last 12 months?",
            "help_text": "Any structured equal-pay / pay-equity analysis counts.",
            "type": "yes_no", "polarity": "higher_is_better",
            "options": [
                {"code": "YES", "label": "Yes", "order": 1, "is_na": False},
                {"code": "NO", "label": "No", "order": 2, "is_na": False},
            ],
        },
    ],
    closes_at="2026-07-15 23:59:59",
)
pulses.open_pulse(pid, conn)
print("pulse created + opened:", pid)

# ---- demo cohort: 12 seed orgs, seeded-RNG responses (synthetic, labelled) --
orgs = [r["org_id"] for r in conn.execute(
    "SELECT org_id FROM orgs WHERE source='seed' AND classified=1 ORDER BY org_id LIMIT 12")]
PTD_OPTS = ["Not started", "Assessing", "Planning", "Implementing", "Compliant"]
DISC = ["Salary ranges in job adverts", "Internal pay bands published to employees",
        "Gender pay gap narrative beyond the statutory minimum", "EU entity-level pay reporting"]
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]
for oid in orgs:
    rng = random.Random("PULSE_PTD26|" + oid)
    pulses.join_pulse(pid, oid, conn)
    pulses.save_response(pid, oid, "REW26_GOV_EU_PTD_PREP", "",
                         rng.choices(PTD_OPTS, weights=[25, 35, 22, 13, 5])[0], conn)
    pulses.save_response(pid, oid, "PROP_9e4ad87f", "", "%.1f" % rng.uniform(2.5, 5.5), conn)
    base = rng.uniform(93, 104)
    for i, lvl in enumerate(LEVELS):
        pulses.save_response(pid, oid, "REW_PAY_MKT_POS_01", lvl, "%d" % (base + rng.uniform(-2, 2)), conn)
    picks = [d for d in DISC if rng.random() < (0.55 if d == DISC[2] else 0.3)]
    pulses.save_response(pid, oid, "PULSE_PTD_DISCLOSURES", "", "; ".join(picks) if picks else "None of these", conn)
    pulses.save_response(pid, oid, "PULSE_PTD_EQUITY_AUDIT", "", "Yes" if rng.random() < 0.45 else "No", conn)
    pulses.submit_pulse(pid, oid, conn)
print("seeded %d participating orgs (seeded RNG, synthetic demo cohort)" % len(orgs))
rep = pulses.pulse_report(pid, conn)
for q in rep["questions"]:
    blk = q["block"] or {}
    print("  %-28s n=%s %s" % (q["question_id"][:26], blk.get("n"),
                               "suppressed" if blk.get("suppressed") else "serving"))
