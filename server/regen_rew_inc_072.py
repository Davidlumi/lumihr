# -*- coding: utf-8 -*-
"""WHOLE-METRIC REGENERATION — REW_INC_072 "Sign-on bonuses used for any roles".

WHY (integrity review, Phase B): the live distribution was 219/220 "Not used"
(99.5%). The 2026 seed-regeneration pass SKIPPED this question, leaving
import-era data. A reward professional would call near-universal non-use
indefensible: UK practice surveys since the 2021-22 labour market (CIPD
resourcing & talent planning reports; recruiter market data) consistently put
*some* use of sign-on payments at roughly a quarter to a third of
organisations, concentrated in hard-to-fill technical/clinical/driver roles,
with systematic "strategic" use rare.

BASELINE PRIOR (documented, reward-sensible, cross-sector):
    Not used                                        ~60%
    Used rarely in exceptional cases                ~18%
    Used for specific hard-to-fill roles            ~17%
    Used strategically as part of attraction        ~5%
conditioned per org on firmographics ONLY (never on benchmark standing):
    usage propensity rises with resources (latent R from the existing Profile
    machinery), the registry's Talent_Competition, and size; within users,
    strategic use tilts with resources. Same Profile class, same TRI mapping,
    as the documented 2026 regeneration.

FIREWALL COMPLIANCE:
- Whole-metric redraw across ALL contributing orgs at once (never selective).
- Seeded + reproducible: rng = Random("REW_INC_072|2026-06-11|" + org_id).
- Org-blind: inputs are firmographics only; the script never reads any org's
  benchmark position, and the demo org gets no special handling of any kind.
- Before/after positions for the demo org + the first two org_ids
  (lexicographic — fixed rule, not cherry-picked) are printed for the record.
"""
import json
import os
import random
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regenerate import Profile, TRI, clamp   # the documented 2026 machinery
from library import load_questions

QID = "REW_INC_072"
SEED_NS = "REW_INC_072|2026-06-11|"

OPTIONS = ["Not used", "Used rarely in exceptional cases",
           "Used for specific hard-to-fill roles",
           "Used strategically as part of attraction strategy"]

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

q = load_questions()[QID]
labels = [o["label"] for o in q.options]
assert labels == OPTIONS, "option set changed: %r" % labels

orgs = conn.execute("SELECT * FROM orgs WHERE submission_complete=1 ORDER BY org_id").fetchall()
demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]
watch = [demo] + [o["org_id"] for o in orgs if o["org_id"] != demo][:2]


def share(value):
    n = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND snapshot_id=1", (QID,)).fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM answers WHERE question_id=? AND snapshot_id=1 AND value=?",
                     (QID, value)).fetchone()[0]
    return c, n


print("BEFORE (for the record — watch orgs chosen by fixed rule):")
before = {}
for oid in watch:
    v = conn.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1",
                     (oid, QID)).fetchone()
    v = v and v["value"]
    c, n = share(v) if v else (0, 0)
    before[oid] = (v, c, n)
    print("  %s%s: %r (shared by %d/%d)" % (oid[:8], " (demo)" if oid == demo else "", v, c, n))

drawn = {}
dist = {o: 0 for o in OPTIONS}
for org in orgs:
    reg = json.loads(org["registry_json"]) if org["registry_json"] else None
    rng = random.Random(SEED_NS + org["org_id"])
    p = Profile(reg, rng)
    talent = TRI.get((reg or {}).get("Talent_Competition"), 0.5)
    # usage propensity: resources + talent pressure + size, noise; firmographics only
    u = clamp(0.12 + 0.22 * p.R + 0.16 * talent + 0.07 * p.size + rng.gauss(0, 0.05), 0.02, 0.70)
    if rng.random() >= u:
        label = OPTIONS[0]
    else:
        strategic = clamp(0.08 + 0.14 * p.R, 0.04, 0.26)
        r = rng.random()
        if r < strategic:
            label = OPTIONS[3]
        elif r < strategic + 0.42:
            label = OPTIONS[2]
        else:
            label = OPTIONS[1]
    drawn[org["org_id"]] = label
    dist[label] += 1

print("\nNEW DISTRIBUTION (whole metric, %d orgs):" % len(orgs))
for o in OPTIONS:
    print("  %-50s %3d (%.1f%%)" % (o, dist[o], 100.0 * dist[o] / len(orgs)))

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
print("\nwritten: %d rows (old rows for this metric removed in the same transaction)" % len(drawn))

print("\nAFTER:")
for oid in watch:
    v = drawn.get(oid)
    c, n = share(v)
    b = before[oid]
    print("  %s%s: %r (shared by %d/%d)   [was %r, %d/%d]" % (
        oid[:8], " (demo)" if oid == demo else "", v, c, n, b[0], b[1], b[2]))
