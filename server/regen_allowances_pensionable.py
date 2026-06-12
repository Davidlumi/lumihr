# -*- coding: utf-8 -*-
"""PREPARED JOINT REGENERATION (DRY-RUN ONLY) — allowance pensionability:
ALLOW_03 "Are allowances pensionable?" (single_select, 220 orgs) and
REW_PAY_020 "Allowances pensionability by level" (Yes/No matrix, 220 orgs).

STATUS: BASELINES SIGNED BY DAVID (2026-06-12) — constants below are the signed values. Per the plausibility-review
brief the pensionability prior is the expert's to set — this script documents
the PROPOSED baseline and prints the dry-run result, and the write path is
double-guarded (--write AND --confirmed-by-david) so it cannot run by accident.

WHY FLAGGED (verified against live data, 2026-06-12):
1. ALLOW_03 says 81.8%% of orgs pension some/all allowances (modal "Yes – some
   allowances only" 57.7%%). Expert prior: most UK DC schemes pension base
   salary only; some/most-allowances pensioning is a minority practice
   (~25-30%% of orgs), concentrated in DB-legacy cultures (public sector,
   mutuals, older PLCs).
2. REW_PAY_020 is internally consistent (220/220 orgs uniform across levels)
   but a flat 20.0%% Yes at EVERY level — no seniority texture at all.
3. THE TWO CONTRADICT EACH OTHER for 152/220 orgs: 144 orgs answer
   "Yes – some/all" in ALLOW_03 yet all-No at every level in REW_PAY_020;
   8 orgs the reverse. The same fact is asked twice and disagrees.
Defect 3 is why this is a JOINT regeneration: drawing either question alone
would leave the contradiction in place. One org-level latent (does this org's
scheme pension allowances, and how broadly?) must drive both answers.

PROPOSED BASELINE (for David to confirm or amend — constants block below):
    org pensioning posture after ownership tilts: none ~70%% / some
    allowances ~20%% / all ~10%% (dry-run lands ALLOW_03 at No 68.6%% /
    some 19.5%% / all 10.0%%; matrix Yes 25.5%% frontline → 30.5%% senior),
    tilted up for Public Sector Body / Mutual / PLC (DB-legacy), down for
    PE/VC/founder-led. Matrix derivation: "all" → Yes at every level;
    "some" → mostly Yes at every level (a scheme rule), with ~25%% of those
    orgs senior-only; "none" → No everywhere. ALLOW_03 derivation: same
    latent, plus small Varies/Don't-know noise (~4%%).

FIREWALL: whole-metric for BOTH questions in one transaction, seeded
("ALLOW_PENS_JOINT|2026-06-12|" + org_id), org-blind (firmographics only),
participation preserved per question, watch-org answers pasted before/after.
"""
import json
import os
import random
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regenerate import Profile, clamp
from library import load_questions

QID_SELECT = "ALLOW_03"
QID_MATRIX = "REW_PAY_020"
SEED_NS = "ALLOW_PENS_JOINT|2026-06-12|"
SENIOR = {"board_executive", "director", "head_of"}

# ---- the tunable baseline block (David adjusts here) ------------------------
BASE_SOME = 0.186            # SIGNED (David, 2026-06-12): ~20% pension SOME
BASE_ALL = 0.053             # SIGNED: ~8% pension ALL/most (implied No ~72%)
OWN_TILT = {                # DB-legacy scheme cultures pension more
    "Public Sector Body": 0.30, "Mutual / Co-operative": 0.18,
    "Public Listed (PLC)": 0.10, "Charity / Non-profit": 0.08,
    "Subsidiary of Global Group": 0.04, "Private (UK-owned)": 0.0,
    "Partnership / LLP": 0.0, "PE-backed": -0.08,
    "Founder-led (Private)": -0.08, "VC-backed (Private)": -0.10,
}
SENIOR_ONLY_SHARE = 0.0     # SIGNED: flat within org — NO seniority carve-outs
NOISE_VARIES = 0.025        # ALLOW_03 "Varies by allowance/contract"
NOISE_DONT_KNOW = 0.02      # ALLOW_03 "Don't know"
# -----------------------------------------------------------------------------

qs = load_questions()
q_sel, q_mat = qs[QID_SELECT], qs[QID_MATRIX]
SEL_OPTIONS = [o["label"] for o in q_sel.options]
assert SEL_OPTIONS == ["Yes – all allowances", "Yes – some allowances only",
                       "No – non-pensionable", "Varies by allowance/contract", "Don't know"], SEL_OPTIONS
ROWS = [rid for rid, _ in q_mat.matrix_row_defs()]

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
ans_sel = [r["org_id"] for r in conn.execute(
    "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND snapshot_id=1 ORDER BY org_id", (QID_SELECT,))]
ans_mat = [r["org_id"] for r in conn.execute(
    "SELECT DISTINCT org_id FROM answers WHERE question_id=? AND snapshot_id=1 ORDER BY org_id", (QID_MATRIX,))]
orgs = {r["org_id"]: r for r in conn.execute("SELECT * FROM orgs")}
demo = conn.execute("SELECT org_id FROM orgs WHERE normalized_name LIKE 'thornbridgeretail%'").fetchone()["org_id"]
all_ans = sorted(set(ans_sel) | set(ans_mat))
watch = ([demo] if demo in all_ans else []) + [o for o in all_ans if o != demo][:2]

print("answering orgs: %s %d | %s %d" % (QID_SELECT, len(ans_sel), QID_MATRIX, len(ans_mat)))
print("\nBEFORE (watch orgs by fixed rule):")
before = {}
for oid in watch:
    sel = conn.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1",
                       (oid, QID_SELECT)).fetchone()
    mat = {r["matrix_row_id"]: r["value"] for r in conn.execute(
        "SELECT matrix_row_id, value FROM answers WHERE org_id=? AND question_id=? AND snapshot_id=1",
        (oid, QID_MATRIX))}
    before[oid] = (sel and sel["value"], mat)
    print("  %s%s: %s=%r | %s=%s" % (oid[:8], " (demo)" if oid == demo else "",
                                     QID_SELECT, before[oid][0], QID_MATRIX, dict(sorted(mat.items()))))

drawn_sel, drawn_mat = {}, {}
dist_sel = {o: 0 for o in SEL_OPTIONS}
yes_by_row = {r: 0 for r in ROWS}
coherent = 0
for oid in all_ans:
    org = orgs[oid]
    reg = json.loads(org["registry_json"]) if org["registry_json"] else {}
    rng = random.Random(SEED_NS + oid)
    p = Profile(reg or None, rng)
    tilt = OWN_TILT.get(org["ownership_type"] or reg.get("Ownership_Type") or "", 0.0)
    # one org-level latent: pensioning posture (none / some / all)
    p_some = clamp(BASE_SOME + 0.6 * tilt + rng.gauss(0, 0.03), 0.02, 0.55)  # ownership-only (signed)
    p_all = clamp(BASE_ALL + 0.4 * tilt + rng.gauss(0, 0.02), 0.01, 0.35)
    r = rng.random()
    posture = "all" if r < p_all else ("some" if r < p_all + p_some else "none")
    senior_only = posture == "some" and rng.random() < SENIOR_ONLY_SHARE

    if oid in ans_mat:
        if posture == "none":
            row_vals = {rid: "No" for rid in ROWS}
        elif senior_only:
            row_vals = {rid: ("Yes" if rid in SENIOR else "No") for rid in ROWS}
        else:
            row_vals = {rid: "Yes" for rid in ROWS}
        drawn_mat[oid] = row_vals
        for rid in ROWS:
            if row_vals[rid] == "Yes":
                yes_by_row[rid] += 1
    if oid in ans_sel:
        nr = rng.random()
        if nr < NOISE_DONT_KNOW:
            label = "Don't know"
        elif nr < NOISE_DONT_KNOW + NOISE_VARIES and posture == "some":
            label = "Varies by allowance/contract"
        else:
            label = {"all": "Yes – all allowances", "some": "Yes – some allowances only",
                     "none": "No – non-pensionable"}[posture]
        drawn_sel[oid] = label
        dist_sel[label] += 1
    if oid in ans_sel and oid in ans_mat:
        sel_yes = drawn_sel[oid].startswith("Yes") or drawn_sel[oid].startswith("Varies")
        mat_yes = any(v == "Yes" for v in drawn_mat[oid].values())
        if sel_yes == mat_yes or drawn_sel[oid] == "Don't know":
            coherent += 1

print("\nPROPOSED %s (%d orgs):" % (QID_SELECT, len(ans_sel)))
for o in SEL_OPTIONS:
    print("  %-34s %3d (%.1f%%)" % (o, dist_sel[o], 100.0 * dist_sel[o] / len(ans_sel)))
print("\nPROPOSED %s per-level Yes (%d orgs):" % (QID_MATRIX, len(ans_mat)))
for rid in ROWS:
    print("  %-34s Yes %5.1f%%" % (rid, 100.0 * yes_by_row[rid] / len(ans_mat)))
both = len(set(ans_sel) & set(ans_mat))
print("\ncross-question coherence: %d/%d orgs (was 68/220; 152 contradictory)" % (coherent, both))

if "--write" not in sys.argv or "--confirmed-by-david" not in sys.argv:
    print("\nDRY RUN — requires BOTH --write AND --confirmed-by-david.")
    print("David: confirm/amend BASE_SOME, BASE_ALL, OWN_TILT, SENIOR_ONLY_SHARE first.")
    sys.exit(0)

cur = conn.cursor()
cur.execute("DELETE FROM answers WHERE question_id IN (?,?) AND snapshot_id=1", (QID_SELECT, QID_MATRIX))
for oid, label in drawn_sel.items():
    for table in ("answers", "answers_history"):
        cur.execute("INSERT INTO %s(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?, '', ?)" % table,
                    (oid, QID_SELECT, label))
for oid, row_vals in drawn_mat.items():
    for rid, v in row_vals.items():
        for table in ("answers", "answers_history"):
            cur.execute("INSERT INTO %s(org_id, snapshot_id, question_id, matrix_row_id, value) VALUES (?,1,?,?,?)" % table,
                        (oid, QID_MATRIX, rid, v))
conn.commit()
print("\nwritten (both questions, one transaction)")
print("\nAFTER (watch orgs):")
for oid in watch:
    print("  %s%s: %s=%r | %s=%s   [was %r | %s]" % (
        oid[:8], " (demo)" if oid == demo else "", QID_SELECT, drawn_sel.get(oid),
        QID_MATRIX, dict(sorted(drawn_mat.get(oid, {}).items())),
        before[oid][0], dict(sorted(before[oid][1].items()))))
