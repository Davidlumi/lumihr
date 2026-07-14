#!/usr/bin/env python3
"""Release 2026.5 seed kit — 54 REW265_* questions, 220 non-Tester orgs.
Diff 6, approved 2026-07-14 with three riders. Same discipline as the 2026_4 kit:
BASELINES built programmatically, every distribution inspectable in the manifest.

Two tiers (the anchor register's status column IS the tier authority):
  - verify-queued (27) -> conservative-haircut: directional prior from real_anchor,
    x0.75 haircut, HARD CEILING at the named figure (rider-3 wave-1 standard).
  - estimate-flag (27) -> unanchored-conservative: modal No/None/Statutory-only.
Near-floor by design: GRANDPARENT, UNLIMITEDAL, LEAVEDONATE, EOT (positive mass 0.06 —
pools sit at/under the suppression floor deliberately; verify shows live suppression).
Sector tilts: EVCHARGE office/industrial up; SEASONAL substantive retail/hospitality/
logistics (others NA-ish via 'None'); COMMCAP substantive sales-heavy, NA elsewhere;
EIA + ACTINGUP public-sector uplift; PENBRIDGE DB-heritage uplift.

RIDER 1: GPGNAMING's "Not in scope (under 250 employees)" is DERIVED from each org's
FTE band (orgs.fte_band, org-profiles FTE_Band fallback; unknown -> in-scope, the
2026_3 ruling-2 precedent). No global rate exists for it.
RIDER 2: SIPELEM carries an explicit NO_SIP_SHARE among parent-positive orgs (0.40)
— SAYE-only plans are real; the manifest shows the share.
Wired trio (D2 pattern): SAYEDISC / SHAREPART / SIPELEM condition on the LIVE
REW264_INC_SHAREPLAN answer; parent-negative = {"Neither", "Not applicable (no shares)"}.
"""
import csv
import hashlib
import random
import re

SEED_DATE = "2026-07-14"
RELEASE_CSV = "lumi_release_2026_5_questions.csv"
HELP_CSV = "lumi_2026_5_member_help_text.csv"
ANCHOR_CSV = "lumi_2026_5_anchor_register.csv"
REGISTER_CSV = "lumi_master_metric_register_v8.csv"

SPO = {"Pay": 1, "Pensions & Savings": 2, "Health & Protection": 3, "Benefits & Lifestyle": 4,
       "Time Off & Family": 5, "Incentives & Recognition": 6, "Wellbeing": 7,
       "Governance & Transparency": 8}

SHAREPLAN_PARENT = "REW264_INC_SHAREPLAN"
SHAREPLAN_NEGATIVE = {"Neither", "Not applicable (no shares)"}
WIRED = {"REW265_INC_SAYEDISC", "REW265_INC_SHAREPART", "REW265_INC_SIPELEM"}
NO_SIP_SHARE = 0.40                      # rider 2 — explicit, manifest-visible
SELF_NA_PRIOR = {                        # scope-out option IS the NA form
    "REW265_GOV_AIDISCLOSE": 0.30,
    "REW265_INC_COMMCAP": None,          # sector-driven (sales-heavy substantive, NA elsewhere)
    "REW265_PAY_EARLYCAREER": 0.25,
    "REW265_BEN_ENHANCEDVR": 0.35,
    "REW265_GOV_GPGNAMING": "FTE",       # rider 1 — derived from the org's FTE band
}
NEAR_FLOOR = {"REW265_TIME_GRANDPARENT", "REW265_TIME_UNLIMITEDAL",
              "REW265_TIME_LEAVEDONATE", "REW265_INC_EOT"}
TILTS = {   # qid -> (sector substrings, positive-mass delta)
    "REW265_BEN_EVCHARGE": (("office", "professional", "financ", "tech", "industrial", "manufact"), +0.15),
    "REW265_PAY_SEASONAL": (("retail", "hospitality", "leisure", "logistic", "transport"), +0.30),
    "REW265_GOV_EIA": (("public", "government", "education", "health"), +0.20),
    "REW265_PAY_ACTINGUP": (("public", "government", "education", "health"), +0.20),
    "REW265_PEN_PENBRIDGE": (("public", "utilit", "financ", "engineering", "manufact"), +0.12),
}
SALES_HEAVY = ("retail", "sales", "recruit", "media", "financ", "insurance", "estate")
LEAN_RE = re.compile(r"^(no\b|not |none\b|neither\b|statutory only|no plans|not offered|not started|not reviewed)", re.I)


def org_rng(qid, org_id):
    return random.Random(hashlib.sha256(f"{qid}|{SEED_DATE}|{org_id}".encode()).hexdigest())


def load_rows():
    rel = {r["id_hint"]: r for r in csv.DictReader(open(RELEASE_CSV))}
    hlp = {r["id_hint"]: r["help_text"] for r in csv.DictReader(open(HELP_CSV))}
    anc = {r["id_hint"]: r for r in csv.DictReader(open(ANCHOR_CSV))}
    reg = {r["metric_id"]: r for r in csv.DictReader(open(REGISTER_CSV))}
    return rel, hlp, anc, reg


def split_options(r):
    return [o.strip() for o in r["options"].split(";") if o.strip()]


def is_na_label(label):
    l = label.lower()
    return l.startswith("not applicable") or l.startswith("not in scope") or label == "No SIP operated"


def anchor_pct(a):
    """A numeric prior exists only when the anchor is an ORG-PREVALENCE figure. VALUE
    anchors (a participation band, a median increase size — "25-40% band", "8-10%
    region") describe the answer's magnitude, not how many orgs hold it: no prior, no
    ceiling; the row seeds on the 0.30 conservative default and the manifest marks it
    value-anchor. (SHAREPART/PROMOPAY, caught by the first-verify ceiling assert.)"""
    text = (a or {}).get("real_anchor") or ""
    if re.search(r"\d+\s*[\u2013-]\s*\d+\s*%", text) or re.search(r"\bband\b|\bmedian\b|\bregion\b", text, re.I):
        return None
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*%", text)
    return float(m.group(1)) / 100.0 if m else None


def build_dist(qid, r, a):
    opts = [o for o in split_options(r) if not is_na_label(o)]
    tier = (a or {}).get("status")
    pct = anchor_pct(a)
    if qid in NEAR_FLOOR:
        pos = 0.06
    elif tier == "verify-queued":
        pos = min((pct * 0.75) if pct is not None else 0.30, pct if pct is not None else 0.30)
    else:
        pos = 0.25
    pos = max(0.02, min(0.85, pos))
    # options are BEST-FIRST in the 2026_5 CSV (spec) — when no "No…"-style label
    # exists, the conservative pole is the LAST option, never the first (the wave-1
    # kit assumed lean-first ordering; caught by the ceiling assert on first verify)
    lean = [o for o in opts if LEAN_RE.match(o)] or [opts[-1]]
    lean = lean[:1]
    # taper anchored at the LEAN pole: the positive rung nearest lean takes the
    # heaviest weight (best-first CSVs put the richest option first — un-anchored
    # tapering handed it the majority of the positive mass; first-verify catch)
    rungs = sorted([o for o in opts if o not in lean], key=lambda o: abs(opts.index(o) - opts.index(lean[0])))
    if not rungs:
        return {opts[0]: 1.0}
    w = [0.5 ** i for i in range(len(rungs))]
    tw = sum(w)
    dist = {lean[0]: round(1.0 - pos, 4)}
    for o, wi in zip(rungs, w):
        dist[o] = round(pos * wi / tw, 4)
    dist[lean[0]] = round(dist[lean[0]] + (1.0 - sum(dist.values())), 4)
    return dist


def tilt(dist, delta):
    d = dict(dist)
    lean = max(d, key=lambda o: d[o] if LEAN_RE.match(o) else -1)
    move = min(delta, max(0.0, d[lean] - 0.05))
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
