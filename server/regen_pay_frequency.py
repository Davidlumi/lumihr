# -*- coding: utf-8 -*-
"""WHOLE-METRIC REGENERATION — EXT_REW_GAP_013 "How often employees are
typically paid" (pay frequency).

WHY (expert plausibility review): the live distribution was Fortnightly 35.2%
modal / Monthly 30.2% / Weekly 14.5% / Mixed 12.3% / Don't know 7.8% —
backwards for the UK. Monthly pay dominates UK payroll by a wide margin
(ONS/ASHE payroll patterns and CIPP payroll industry data put the large
majority of UK employees on monthly pay); weekly pay persists as a meaningful
minority concentrated in hospitality, retail, construction, manufacturing and
logistics frontline populations; FORTNIGHTLY is rare in the UK (it is an
US/Australian pattern); "mixed" appears in large multi-population employers.

BASELINE (documented, org-level "typically paid", cross-sector):
    Monthly                  ~76%
    Weekly                   ~11%
    Mixed (varies by role)   ~7%
    Fortnightly              ~3%
    Don't know               ~3%
NOTE FOR DAVID: the exact split is one constants block below — tune and
re-run; the script is seeded and reproducible. Direction (monthly clearly
dominant) is settled; the decimals are yours to adjust.

CONDITIONING (firmographics only, never standing):
    weekly/mixed propensity rises with the registry's Workforce_Shift_% and
    Workforce_Frontline_% and with the weekly-leaning sectors; mixed rises
    with size. Same Profile machinery as the documented 2026 regeneration.

FIREWALL COMPLIANCE:
- Whole-metric redraw across ALL orgs that answered (179) at once. Orgs that
  did not answer stay unanswered — participation is preserved, never invented.
- Seeded + reproducible: rng = Random("EXT_REW_GAP_013|2026-06-12|" + org_id).
- Org-blind: no org gets special handling; the demo org is redrawn by the
  same process. Pay frequency is a NEUTRAL-polarity practice metric — there
  is no "favourable" side to steer toward — and the watch orgs' raw answers
  are pasted before/after for the record regardless.
"""
import json
import os
import random
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regenerate import Profile, clamp
from library import load_questions

QID = "EXT_REW_GAP_013"
SEED_NS = "EXT_REW_GAP_013|2026-06-12|"
OPTIONS = ["Weekly", "Fortnightly", "Monthly", "Mixed (varies by role)", "Don't know"]

# ---- the tunable baseline block (David adjusts here) ------------------------
BASE_WEEKLY = 0.06          # floor weekly share before frontline/sector tilt
BASE_MIXED = 0.04
BASE_FORTNIGHTLY = 0.03
BASE_DONT_KNOW = 0.03
WEEKLY_SECTORS = {"Hospitality, Leisure & Travel", "Retail & Consumer Goods",
                  "Construction & Infrastructure", "Manufacturing & Engineering",
                  "Logistics, Transport & Distribution"}
SECTOR_TILT = 0.07
# -----------------------------------------------------------------------------

q = load_questions()[QID]
assert [o["label"] for o in q.options] == OPTIONS, [o["label"] for o in q.options]

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

answered = [r["org_id"] for r in conn.execute(
    "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND snapshot_id=1 ORDER BY org_id", (QID,))]
orgs = {r["org_id"]: r for r in conn.execute("SELECT * FROM orgs")}
demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]
watch = ([demo] if demo in answered else []) + [o for o in answered if o != demo][:2]

print("BEFORE (watch orgs by fixed rule; neutral-polarity metric — no favourable side exists):")
before = {}
for oid in watch:
    v = conn.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1",
                     (oid, QID)).fetchone()
    before[oid] = v and v["value"]
    print("  %s%s: %r" % (oid[:8], " (demo)" if oid == demo else "", before[oid]))

drawn, dist = {}, {o: 0 for o in OPTIONS}
for oid in answered:
    org = orgs[oid]
    reg = json.loads(org["registry_json"]) if org["registry_json"] else {}
    rng = random.Random(SEED_NS + oid)
    p = Profile(reg or None, rng)
    frontline = (reg.get("Workforce_Frontline_%") or 35) / 100.0
    shift = (reg.get("Workforce_Shift_%") or 15) / 100.0
    sector_tilt = SECTOR_TILT if (org["industry"] in WEEKLY_SECTORS) else 0.0
    w_weekly = clamp(BASE_WEEKLY + 0.07 * frontline + 0.09 * shift + sector_tilt + rng.gauss(0, 0.02), 0.0, 0.40)
    w_mixed = clamp(BASE_MIXED + 0.05 * p.size + 0.06 * shift + (0.03 if sector_tilt else 0) + rng.gauss(0, 0.015), 0.0, 0.25)
    w_fort = clamp(BASE_FORTNIGHTLY + rng.gauss(0, 0.01), 0.0, 0.08)
    w_dk = clamp(BASE_DONT_KNOW + (0.02 if p.F < 0.25 else 0) + rng.gauss(0, 0.01), 0.0, 0.08)
    w_monthly = max(0.05, 1.0 - w_weekly - w_mixed - w_fort - w_dk)
    weights = {"Weekly": w_weekly, "Fortnightly": w_fort, "Monthly": w_monthly,
               "Mixed (varies by role)": w_mixed, "Don't know": w_dk}
    r = rng.random() * sum(weights.values())
    acc = 0.0
    for label in OPTIONS:
        acc += weights[label]
        if r <= acc:
            drawn[oid] = label
            break
    dist[drawn[oid]] += 1

print("\nNEW DISTRIBUTION (%d answering orgs — participation preserved):" % len(answered))
for o in OPTIONS:
    print("  %-26s %3d (%.1f%%)" % (o, dist[o], 100.0 * dist[o] / len(answered)))

if "--write" not in sys.argv:
    print("\nDRY RUN — pass --write to apply.")
    sys.exit(0)

cur = conn.cursor()
cur.execute("DELETE FROM answers WHERE question_id=? AND snapshot_id=1", (QID,))
for oid, label in drawn.items():
    cur.execute("INSERT INTO answers(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?, '', ?)",
                (oid, QID, label))
    cur.execute("INSERT INTO answers_history(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?, '', ?)",
                (oid, QID, label))
conn.commit()
print("\nwritten: %d rows" % len(drawn))
print("\nAFTER:")
for oid in watch:
    print("  %s%s: %r   [was %r]" % (oid[:8], " (demo)" if oid == demo else "", drawn.get(oid), before[oid]))
