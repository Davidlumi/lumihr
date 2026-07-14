#!/usr/bin/env python3
"""Release 2026.4 seed kit — 45 REW264_* questions, 220 non-Tester orgs.
Diff 5, ratified 2026-07-14 (DECISIONS: scope + seeding entry, rulings D1-D5).

Same firewall discipline as seed_release_2026_3.py, with the BASELINES built
PROGRAMMATICALLY from the ratified plan rules instead of a hand-typed constants
block — every derived distribution lands in diff5_seed_manifest.csv (target vs
anchor vs seeded), which is the signed record David's "apply" ratified:
  - track-anchor (grade A/B, 13): the anchor %% is the positive-side mass, split
    across the positive rungs tapering toward the top; remainder on the lean pole.
  - conservative-haircut (grade E, 17): as above with the anchor %% x0.75, and
    where no numeric anchor exists a 0.30 positive-side prior; estimate-flagged
    in the manifest.
  - unanchored-conservative (grade '-', 15): positive side 0.35, majority lean.
  - MEALS: sector tilt (hospitality/retail/leisure +0.25 positive) per the anchor
    register note.
  - NA routing (the ratified 13-row table): SEVEN WIRED rows condition on the
    PARENT's actual per-org answer (sal-sac trio -> REW26_BEN_SALSAC='No'-family;
    FERTROUTE -> REW263_TIME_IVF='None'; GIPREHAB -> REW_BEN_046='No'; the EWA
    pair -> this wave's own REW264_WEL_EWA, seeded FIRST — apply-order tolerance
    per D2). SIX SELF-DECLARED rows take documented NA priors below.
  - Per-org reproducible rng: sha256(f"{qid}|2026-07-14|{org_id}").
Nothing here writes; apply_2026_4.py is double-guarded (--write --confirmed-by-david).
"""
import csv
import hashlib
import random
import re

SEED_DATE = "2026-07-14"
RELEASE_CSV = "lumi_release_2026_4_questions.csv"
HELP_CSV = "lumi_2026_4_member_help_text.csv"
ANCHOR_CSV = "lumi_2026_4_anchor_register.csv"

# ratified 8-domain order (Diff 1)
SPO = {"Pay": 1, "Pensions & Savings": 2, "Health & Protection": 3, "Benefits & Lifestyle": 4,
       "Time Off & Family": 5, "Incentives & Recognition": 6, "Wellbeing": 7,
       "Governance & Transparency": 8}

# the ratified 13-row conditional table (D2)
WIRED = {  # child -> (parent qid, NA-triggering parent values; intra-wave parents allowed)
    "REW264_PEN_SALSACIMPACT": ("REW26_BEN_SALSAC", {"No"}),
    "REW264_PEN_SALSACRESPONSE": ("REW26_BEN_SALSAC", {"No"}),
    "REW264_PEN_NICSHARING": ("REW26_BEN_SALSAC", {"No"}),
    "REW264_WEL_EWAFEES": ("REW264_WEL_EWA", {"Not offered", "No"}),
    "REW264_WEL_EWACAP": ("REW264_WEL_EWA", {"Not offered", "No"}),
    "REW264_HLT_FERTROUTE": ("REW263_TIME_IVF", {"None", "Not applicable"}),
    "REW264_HLT_GIPREHAB": ("REW_BEN_046", {"No"}),
}
SELF_NA_PRIOR = {  # documented conservative priors; manifest-visible
    "REW264_PEN_CONTRIBTIER": 0.08,
    "REW264_PEN_AEDEFAULT": 0.06,      # no DC scheme
    "REW264_PEN_GREENDEFAULT": 0.10,   # no DC default fund
    "REW264_INC_SHAREPLAN": 0.45,      # no listed shares / no plan vehicle
    "REW264_INC_EMICSOP": 0.40,        # no share capital
    "REW264_BEN_EVSALSAC": 0.55,       # no sal-sac car scheme (option-level parent, self-declared)
}
LEAN_RE = re.compile(r"^(no\b|not |none\b|neither\b|statutory only|no plans|not offered|not reviewed|not started)", re.I)
MEALS_TILT_SECTORS = ("hospitality", "retail", "leisure", "travel", "food")


def org_rng(qid, org_id):
    return random.Random(hashlib.sha256(f"{qid}|{SEED_DATE}|{org_id}".encode()).hexdigest())


def load_rows():
    rel = {r["id_hint"]: r for r in csv.DictReader(open(RELEASE_CSV))}
    hlp = {r["id_hint"]: r["help_text"] for r in csv.DictReader(open(HELP_CSV))}
    anc = {r["id_hint"]: r for r in csv.DictReader(open(ANCHOR_CSV))}
    return rel, hlp, anc


def split_options(r):
    return [o.strip() for o in r["options"].split(";") if o.strip()]


def is_na_label(label):
    return label.lower().startswith("not applicable") or label == "No sal-sac scheme"


def anchor_pct(anchor_row):
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*%", anchor_row.get("real_anchor") or "")
    return float(m.group(1)) / 100.0 if m else None


def build_dist(qid, r, anchor_row):
    """Positive-mass rule over the non-NA options. Lean pole found by label; positive
    rungs taper toward the top so the seeded ladder reads believably conservative."""
    opts = [o for o in split_options(r) if not is_na_label(o)]
    grade = (anchor_row or {}).get("grade", "—")
    pct = anchor_pct(anchor_row or {})
    if grade in ("A", "B") and pct is not None:
        pos_mass = pct
    elif grade == "E":
        pos_mass = (pct * 0.75) if pct is not None else 0.30
    else:
        pos_mass = 0.35
    pos_mass = max(0.05, min(0.90, pos_mass))
    lean = [o for o in opts if LEAN_RE.match(o)] or [opts[-1] if LEAN_RE.match(opts[-1]) else opts[0]]
    lean = lean[:1]
    rungs = [o for o in opts if o not in lean]
    if not rungs:
        return {opts[0]: 1.0}
    # taper: first positive rung heaviest, halving up the ladder
    w = [0.5 ** i for i in range(len(rungs))]
    tw = sum(w)
    dist = {lean[0]: round(1.0 - pos_mass, 4)}
    for o, wi in zip(rungs, w):
        dist[o] = round(pos_mass * wi / tw, 4)
    # normalise residue onto the lean pole
    resid = 1.0 - sum(dist.values())
    dist[lean[0]] = round(dist[lean[0]] + resid, 4)
    return dist


def meals_tilt(dist, sector):
    if not sector or not any(s in sector.lower() for s in MEALS_TILT_SECTORS):
        return dist
    d = dict(dist)
    lean = max(d, key=lambda o: d[o] if LEAN_RE.match(o) else -1)
    move = min(0.25, d[lean] - 0.05)
    d[lean] = round(d[lean] - move, 4)
    rest = [o for o in d if o != lean]
    for o in rest:
        d[o] = round(d[o] + move / len(rest), 4)
    return d


def largest_remainder(dist, m):
    raw = {o: dist[o] * m for o in dist}
    base = {o: int(raw[o]) for o in dist}
    for o in sorted(dist, key=lambda o: -(raw[o] - base[o]))[: m - sum(base.values())]:
        base[o] += 1
    return base
