# -*- coding: utf-8 -*-
"""Seed-data regeneration: realistic, profile-driven synthetic answers.

Reads the 220 existing response files (structure only), the question library
and the org registry, and rewrites every file with answers sampled from
realistic priors (regen_priors.py) conditioned on each organisation's own
registry profile. Questions with no defensible baseline are SKIPPED — their
existing generic answers are preserved unchanged — and logged for later hand
curation.

Run:  python3 regenerate.py            (writes data/responses/*.csv in place,
                                        backs up originals to data/responses_orig/)
"""
import csv
import json
import math
import os
import random
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, uj
from aggregate import score_direction
from library import load_questions
from regen_priors import (SELECT_PRIORS, MULTI_PRIORS, MATRIX_DRIVERS,
                          NUMERIC_DRIVERS, LEVELS)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

INDUSTRIAL = {"Logistics, Transport & Distribution", "Manufacturing & Engineering",
              "Construction & Infrastructure", "Energy, Utilities & Environmental Services"}
HOSPITALITY = "Hospitality, Leisure & Travel"
PUBLICISH = {"Public Sector & Government", "Education (Public & Private)",
             "Charity, Non-Profit & Social Enterprise"}


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ================================================================ profile ====

SIZE_FRAC = {"50-249": 0.1, "250-999": 0.3, "1,000-4,999": 0.5, "5,000-9,999": 0.7, "10,000+": 0.9}
HRM = {"Basic": 0.12, "Developing": 0.5, "Advanced": 0.85}
SYS = {"Spreadsheets": 0.05, "Core HRIS": 0.35, "HRIS + ATS": 0.55,
       "HRIS + ATS + LMS": 0.72, "Integrated suite": 0.92}
OWN_F = {"Public Listed (PLC)": 0.8, "PE-backed": 0.72, "Subsidiary of Global Group": 0.7,
         "Public Sector Body": 0.68, "Mutual / Co-operative": 0.55, "Charity / Non-profit": 0.5,
         "Private (UK-owned)": 0.45, "Partnership / LLP": 0.45, "VC-backed (Private)": 0.35,
         "Founder-led (Private)": 0.28}
BUDGET = {"Tight": 0.2, "Managed": 0.5, "Flexible": 0.85}
TRI = {"Weak": 0.2, "Low": 0.25, "Average": 0.5, "Moderate": 0.5, "Medium": 0.5,
       "Strong": 0.8, "High": 0.8, "Mixed": 0.45}


class Profile(object):
    def __init__(self, reg, rng):
        self.matched = reg is not None
        self.reg = reg or {}
        g = self.reg.get
        if self.matched:
            base = (0.40 * HRM.get(g("HR_Maturity"), 0.5)
                    + 0.28 * SYS.get(g("HR_Systems_Maturity"), 0.5)
                    + 0.20 * SIZE_FRAC.get(g("FTE_Band"), 0.5)
                    + 0.12 * OWN_F.get(g("Ownership_Type"), 0.5))
            self.F = clamp(base + rng.gauss(0, 0.06), 0.03, 0.97)
            self.R = clamp(0.45 * BUDGET.get(g("Budget_Flexibility"), 0.5)
                           + 0.35 * SIZE_FRAC.get(g("FTE_Band"), 0.5)
                           + 0.20 * OWN_F.get(g("Ownership_Type"), 0.5)
                           + rng.gauss(0, 0.06), 0.05, 0.95)
        else:
            # no registry profile: baseline-only generation, mid-spread latent
            self.F = clamp(rng.betavariate(2.4, 2.4), 0.05, 0.95)
            self.R = clamp(rng.betavariate(2.4, 2.4), 0.05, 0.95)
        self.size = SIZE_FRAC.get(g("FTE_Band"), 0.5)
        self.fte_band = g("FTE_Band")
        self.own = g("Ownership_Type") or ""
        self.industry = g("Industry") or ""
        self.region = g("HQ_Region") or ""
        self.frontline = (g("Workforce_Frontline_%") or 45) / 100.0
        self.shift = (g("Workforce_Shift_%") or 30) / 100.0
        self.union = (g("Workforce_Unionised_%") or 12) / 100.0
        self.public = self.own == "Public Sector Body"
        self.charity = self.own == "Charity / Non-profit"
        self.plc_pe = self.own in ("Public Listed (PLC)", "PE-backed")
        self.brand = TRI.get(g("Employer_Brand_Strength"), 0.5)
        self.voice = TRI.get(g("Employee_Voice"), 0.5)
        self.advocacy = TRI.get(g("Employee_Advocacy"), 0.5)
        self.budgetF = BUDGET.get(g("Budget_Flexibility"), 0.5)
        self.talent_hot = g("Talent_Competition") == "High"
        tb = g("Turnover_Band")
        if tb == "<10%":
            self.turnover = rng.uniform(4, 9.5)
        elif tb == "10–20%":
            self.turnover = rng.uniform(10, 19.5)
        elif tb == "20%+":
            self.turnover = rng.uniform(20, 34)
        else:
            self.turnover = rng.uniform(8, 22)
        # change intensity C: orgs in active transformation exercise (and so
        # report) far more change-management practice than stable ones —
        # Archetype / Business_Maturity / Direction_of_Travel / Recent_Shock
        # / Change_Frequency drive the Change-superpower questions.
        if self.matched:
            freq = {"Minimal": 0.1, "Incremental": 0.35, "Major": 0.7, "Constant": 0.85}.get(
                g("Change_Frequency"), 0.45)
            arch = 0.85 if g("Archetype") == "Turnaround / Transformation" else \
                0.7 if g("Archetype") == "High-Growth PE-Backed" else \
                0.3 if g("Archetype") in ("Mature Enterprise", "Established Commercial") else 0.5
            shock = 0.2 if (g("Recent_Shock") or "").startswith("None") else 0.7
            dot = {"Stable": 0.35, "Improving": 0.55, "Deteriorating": 0.65}.get(
                g("Direction_of_Travel"), 0.5)
            self.change = clamp(0.4 * freq + 0.3 * arch + 0.2 * shock + 0.1 * dot
                                + rng.gauss(0, 0.06), 0.05, 0.95)
        else:
            self.change = clamp(rng.betavariate(2.4, 2.4), 0.05, 0.95)
        self.pmc = TRI.get(g("People_Manager_Capability"), 0.5)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ============================================================ select engine ==

def resolve_weights(q, spec):
    """Pattern weights -> {label: weight}; unmatched options get spec['rest']."""
    labels = [o["label"] for o in (q.options or [])]
    out = {}
    for lbl in labels:
        out[lbl] = None
    for pat, w in spec["w"].items():
        rx = re.compile(pat, re.I)
        hit = False
        for lbl in labels:
            if rx.search(lbl):
                if out[lbl] is None:
                    out[lbl] = w
                hit = True
        if not hit:
            raise ValueError("prior pattern %r matched no option of %s (%s)" % (pat, q.id, labels))
    rest = spec.get("rest", 0.01)
    for lbl in labels:
        if out[lbl] is None:
            out[lbl] = rest
    return out


def option_points(q):
    """{label: direction-corrected maturity points 0-100 (higher = better)}.
    None when the option ladder's direction can't be determined safely."""
    cfg = q.scoring_config or {}
    scores = cfg.get("option_scores") or {}
    d = score_direction(q)
    if d == 0:
        return None
    return {o["label"]: (100.0 - float(scores[o["code"]])) if d == -1 else float(scores[o["code"]])
            for o in (q.options or []) if o["code"] in scores}


def tilt_by_score(q, weights, F, k):
    """Generic formality tilt over direction-corrected points: high-F orgs
    drift toward the genuinely better-practice options."""
    pts = option_points(q)
    if pts is None:
        return weights
    out = {}
    for lbl, w in weights.items():
        s = pts.get(lbl)
        if s is None:
            out[lbl] = w
        else:
            out[lbl] = w * math.exp(k * (s / 100.0 - 0.5) * (F - 0.5) * 4)
    return out


def sample_label(weights, rng):
    total = sum(weights.values())
    r = rng.random() * total
    acc = 0.0
    for lbl, w in weights.items():
        acc += w
        if r <= acc:
            return lbl
    return list(weights)[-1]


def find_opt(q, pattern):
    rx = re.compile(pattern, re.I)
    for o in (q.options or []):
        if rx.search(o["label"]):
            return o["label"]
    return None


def force(q, pattern, weights, p=0.95, dk=0.05):
    """Concentrate mass on the option matching pattern."""
    tgt = find_opt(q, pattern)
    out = {lbl: 0.0001 for lbl in weights}
    if tgt:
        out[tgt] = p
    dkl = find_opt(q, "Don't know|Not applicable")
    if dkl and dkl != tgt:
        out[dkl] = dk
    return out


def scale_pat(q, weights, pattern, factor):
    rx = re.compile(pattern, re.I)
    return {lbl: (w * factor if rx.search(lbl) else w) for lbl, w in weights.items()}


def band_pick(q, value, band_edges, rng):
    """Map a latent value onto banded options. band_edges: [(pattern, lo, hi)]."""
    for pat, lo, hi in band_edges:
        if lo <= value < hi:
            tgt = find_opt(q, pat)
            if tgt:
                return tgt
    return None


# ---- anchors: per-question profile modulation ----

def anchors(name, q, w, prof, state, rng):
    p = prof
    if not p.matched and name not in ("osp_consistency", "osp_consistency_dur",
                                      "osp_consistency_wait", "buy_leave_consistency",
                                      "buy_leave_consistency2", "maternity_consistency",
                                      "tronc_sector_dep", "pmi_consistency",
                                      "pension_band", "absence_profile",
                                      "turnover_registry", "early_attrition", "early_attrition90"):
        return w  # baseline-only orgs: no profile shifts (state-dependent ones still apply)

    if name == "pay_rise_budget":
        w = scale_pat(q, w, "95%–100%", 0.6 + 1.2 * p.budgetF + (0.8 if (p.public or p.union > 0.4) else 0))
        w = scale_pat(q, w, "^0%$|1%–24%", 1.6 - 1.2 * p.budgetF)
    elif name == "offcycle_turnover":
        hot = (p.turnover > 20) or p.talent_hot
        if hot:
            w = scale_pat(q, w, "11%–20%|21–30%|21%–30%", 1.7)
            w = scale_pat(q, w, "0–5%", 0.6)
    elif name == "pension_band":
        v = pension_latent(p, state, rng)
        edges = [("<3%", 0, 3), ("3%–4%", 3, 5), ("5%–7%", 5, 8), ("8%–10%", 8, 11), ("11%\\+", 11, 99)]
        tgt = band_pick(q, v, edges, rng)
        if tgt:
            w = force(q, re.escape(tgt), w, p=0.9, dk=0.04)
    elif name == "osp_offer":
        py = clamp(0.40 + 0.40 * p.F + (0.12 if (p.public or p.charity) else 0)
                   - (0.18 if (p.industry == HOSPITALITY and p.frontline > 0.5) else 0), 0.12, 0.96)
        w = {find_opt(q, "^Yes") or "Yes": py, find_opt(q, "^No") or "No": 1 - py}
        state["osp"] = None  # decided at sample time by caller
    elif name == "osp_consistency":
        if state.get("osp") is False:
            w = force(q, "Statutory sick pay only", w, p=0.94)
        else:
            w = scale_pat(q, w, "Statutory sick pay only", 0.1)
    elif name == "osp_consistency_dur":
        if state.get("osp") is False:
            w = force(q, "None", w, p=0.94)
        else:
            w = scale_pat(q, w, "^None", 0.08)
            w = scale_pat(q, w, "13-26|More than 26", 0.5 + 1.4 * (p.size + (0.3 if p.public else 0)))
    elif name == "osp_consistency_wait":
        if state.get("osp") is False:
            w = force(q, "Not applicable", w, p=0.92)
        else:
            w = scale_pat(q, w, "Not applicable", 0.06)
            w = scale_pat(q, w, "up to 3 days|more than 3 days", 0.6 + 1.1 * p.frontline)
    elif name == "gpg_250":
        if p.fte_band and p.fte_band != "50-249":
            w = {find_opt(q, "^Yes"): 0.93, find_opt(q, "In development"): 0.05, find_opt(q, "^No"): 0.02}
        elif p.fte_band == "50-249":
            w = {find_opt(q, "^Yes"): 0.22, find_opt(q, "In development"): 0.14, find_opt(q, "^No"): 0.64}
    elif name == "leave_days":
        if p.public or p.charity:
            w = scale_pat(q, w, "28-30|More than 30", 2.6)
            w = scale_pat(q, w, "Statutory|21-24", 0.4)
        elif p.size < 0.2 and p.budgetF < 0.4:
            w = scale_pat(q, w, "Statutory|21-24", 1.8)
    elif name == "buy_leave_consistency":
        if state.get("buy_leave"):
            w = scale_pat(q, w, "Not applicable", 0.02)
        else:
            w = force(q, "Not applicable", w, p=0.96, dk=0.02)
    elif name == "buy_leave_consistency2":
        if state.get("buy_leave"):
            w = scale_pat(q, w, "Not offered", 0.02)
        else:
            w = force(q, "Not offered", w, p=0.97, dk=0.0)
    elif name == "shutdown_sector":
        if p.industry in ("Manufacturing & Engineering", "Construction & Infrastructure"):
            w = scale_pat(q, w, "mandatory|some parts", 3.0)
    elif name == "bonus_eligibility":
        if p.public or p.charity or p.own == "Mutual / Co-operative":
            w = scale_pat(q, w, "None", 5.0)
            w = scale_pat(q, w, "75%\\+|50–74%", 0.25)
        elif p.plc_pe:
            w = scale_pat(q, w, "75%\\+", 1.8)
            w = scale_pat(q, w, "None", 0.25)
    elif name == "richness_updown":
        neg = "Not offered|Statutory pay only|statutory unpaid only|^No$"
        w = scale_pat(q, w, neg, 1.7 - 1.3 * p.R)
    elif name == "advert_ranges_public":
        if p.public or p.charity:
            w = {find_opt(q, "All roles"): 0.58, find_opt(q, "Some roles"): 0.25, find_opt(q, "^No"): 0.17}
    elif name in ("union_bargaining", "union_bargaining2"):
        u = p.union
        if name == "union_bargaining":
            if u > 0.4:
                w = {find_opt(q, "pay and core"): 0.82, find_opt(q, "limited"): 0.08, find_opt(q, "^No"): 0.10}
            elif u > 0.1:
                w = {find_opt(q, "pay and core"): 0.35, find_opt(q, "limited"): 0.15, find_opt(q, "^No"): 0.50}
            else:
                w = {find_opt(q, "pay and core"): 0.03, find_opt(q, "limited"): 0.05, find_opt(q, "^No"): 0.92}
        else:
            if u > 0.4:
                w = force(q, "^Yes", w, p=0.85, dk=0.03)
            elif u > 0.1:
                w = scale_pat(q, w, "^Yes", 1.2)
            else:
                w = {find_opt(q, "^Yes"): 0.02, find_opt(q, "^No"): 0.55,
                     find_opt(q, "Not applicable"): 0.41, find_opt(q, "Don't know"): 0.02}
    elif name == "absence_profile":
        a = absence_latent(p, state, rng)
        if q.id == "MET_1fa3fa15":
            edges = [("^0%$", 0, 0.5), ("1%–2%", 0.5, 2), ("2%–3%", 2, 3), ("3%–4%", 3, 4),
                     ("4%–5%", 4, 5), ("5%–6%", 5, 6), ("6%–8%", 6, 8), ("8%–10%", 8, 10), ("Over 10%", 10, 99)]
        else:
            edges = [("<2%", 0, 2), ("2–3%", 2, 3), ("3–4%", 3, 4), ("4–6%", 4, 6), ("6%\\+", 6, 99)]
        tgt = band_pick(q, a, edges, rng)
        if tgt:
            w = force(q, re.escape(tgt), w, p=0.88, dk=0.05)
    elif name == "turnover_registry":
        t = p.turnover
        edges = [("^0%$", 0, 0.5), ("1%–5%", 0.5, 5), ("5%–10%", 5, 10), ("10%–15%", 10, 15),
                 ("15%–20%", 15, 20), ("20%–25%", 20, 25), ("25%–30%", 25, 30), ("Over 30%", 30, 99)]
        tgt = band_pick(q, t, edges, rng)
        if tgt:
            w = force(q, re.escape(tgt), w, p=0.9, dk=0.0)
    elif name == "early_attrition":
        e = clamp(p.turnover * 1.25 + rng.gauss(0, 2.5), 1, 45)
        edges = [("0%–2%", 0, 2), ("2.1%–5%", 2, 5), ("5.1%–10%", 5, 10), ("10.1%–15%", 10, 15),
                 ("15.1%–25%", 15, 25), ("More than 25%", 25, 99)]
        tgt = band_pick(q, e, edges, rng)
        if tgt:
            w = force(q, re.escape(tgt), w, p=0.85, dk=0.05)
    elif name == "early_attrition90":
        e = clamp(p.turnover * 0.35 + rng.gauss(0, 1.2), 0, 30)
        edges = [("0–2%", 0, 2.5), ("3–5%", 2.5, 5.5), ("6–10%", 5.5, 10.5), ("11–15%", 10.5, 15.5),
                 ("16–20%", 15.5, 20.5), ("20%\\+", 20.5, 99)]
        tgt = band_pick(q, e, edges, rng)
        if tgt:
            w = force(q, re.escape(tgt), w, p=0.85, dk=0.05)
    elif name == "flex_frontline":
        if p.frontline > 0.55:
            w = scale_pat(q, w, "Some roles", 2.2)
            w = scale_pat(q, w, "^Yes", 0.4)
    elif name == "overtime_frontline":
        if p.shift > 0.35 or p.frontline > 0.6:
            w = {find_opt(q, "^Yes"): 0.90, find_opt(q, "^No"): 0.07, find_opt(q, "Not applicable"): 0.03}
        elif p.frontline < 0.25:
            w = {find_opt(q, "^Yes"): 0.28, find_opt(q, "^No"): 0.52, find_opt(q, "Not applicable"): 0.20}
    elif name == "toil_public":
        if p.public or p.charity:
            w = scale_pat(q, w, "^Yes", 1.8)
    elif name == "maternity_consistency":
        if state.get("maternity_enhanced") is False:
            w = force(q, "^None", w, p=0.95)
        else:
            w = scale_pat(q, w, "^None", 0.05)
    elif name == "salsac_size":
        w = scale_pat(q, w, "Not offered", 1.8 - 1.6 * p.size)
        w = scale_pat(q, w, "25–49%|50%\\+", 0.5 + 1.2 * p.size)
    elif name == "tronc_sector":
        if p.industry == HOSPITALITY:
            w = {find_opt(q, "^Yes"): 0.72, find_opt(q, "^No"): 0.18, find_opt(q, "Not applicable"): 0.10}
        else:
            w = {find_opt(q, "^Yes"): 0.005, find_opt(q, "^No"): 0.03, find_opt(q, "Not applicable"): 0.965}
    elif name == "tronc_sector_dep":
        if not state.get("tronc"):
            w = force(q, "Not applicable", w, p=0.97, dk=0.0)
        else:
            w = scale_pat(q, w, "Not applicable", 0.03)
    elif name == "pmi_consistency":
        if not state.get("pmi"):
            w = force(q, "Not offered", w, p=0.96, dk=0.0)
        else:
            w = scale_pat(q, w, "Not offered", 0.02)
    return {k: v for k, v in w.items() if k is not None}


def pension_latent(p, state, rng):
    if "pension" not in state:
        if p.public:
            v = rng.uniform(16, 26)
        elif p.charity:
            v = clamp(rng.gauss(6.5, 2.0), 3, 14)
        else:
            v = clamp(3.2 + 6.5 * p.R + rng.gauss(0, 1.6), 3, 15)
        state["pension"] = v
    return state["pension"]


def absence_latent(p, state, rng):
    if "absence" not in state:
        a = 1.7 + 2.4 * p.frontline + (1.0 if p.public else 0) + \
            (0.5 if p.industry in ("Healthcare & Life Sciences",) else 0) + rng.gauss(0, 0.55)
        state["absence"] = clamp(a, 0.8, 9.5)
    return state["absence"]


# ------------------------------------------------- template (pattern) tier --

def template_weights(q, prof, rng):
    """Score-ladder kernel: realistic adoption curve conditioned on the org's
    latent maturity F, blended with the domain-specific registry signal:
      Change questions       -> change intensity (Archetype/Recent_Shock/etc.)
      manager-practice qs    -> People_Manager_Capability
      voice/listening qs     -> Employee_Voice
      benefit questions      -> richness R
    """
    cfg = q.scoring_config or {}
    pts_by_label = option_points(q)
    if pts_by_label is None:
        return None   # no safe direction reading -> question is skipped
    na_codes = set(cfg.get("na_codes") or [])
    base = prof.F
    if q.category == "benefit":
        base = prof.R
    elif q.superpower == "Change":
        base = clamp(0.55 * prof.F + 0.45 * prof.change, 0.02, 0.98)
    elif re.search(r"\bmanagers?\b", (q.text or ""), re.I) and q.superpower in ("Leadership", "Capability", "Growth"):
        base = clamp(0.65 * prof.F + 0.35 * prof.pmc, 0.02, 0.98)
    elif re.search(r"voice|listening|survey|feedback|forum", (q.text or ""), re.I) and q.superpower in ("Purpose", "Wellbeing", "Inclusivity"):
        base = clamp(0.65 * prof.F + 0.35 * prof.voice, 0.02, 0.98)
    Fq = clamp(base + rng.gauss(0, 0.16), 0.02, 0.98)
    if q.category == "metric":
        t, sig = 30 + 40 * Fq, 30.0   # weak coupling for banded metrics
    else:
        t, sig = 16 + 66 * Fq, 23.0
    weights = {}
    subst = []
    for o in (q.options or []):
        s = pts_by_label.get(o["label"])
        if o["code"] in na_codes or s is None:
            weights[o["label"]] = None  # NA fill below
        else:
            subst.append((o["label"], s))
    if not subst:
        return None
    for lbl, s in subst:
        weights[lbl] = math.exp(-((s - t) ** 2) / (2 * sig * sig)) + 0.05
    na_labels = [l for l, w in weights.items() if w is None]
    tot = sum(w for w in weights.values() if w)
    for l in na_labels:
        weights[l] = 0.06 * tot / max(len(na_labels), 1)
    return weights


# ============================================================ multi engine ==

CANON_ALLOW = [
    ("car", "car allowance"), ("shift", "shift allowance"), ("oncall", "on-call"),
    ("location", "london weighting|location|cost-of-living"), ("travel", "travel"),
    ("mobile", "mobile|phone"), ("meal", "meal"), ("homework", "home-?work"),
    ("firstaid", "first aid|first-aid"), ("night", "night premium"),
    ("weekend", "weekend premium"), ("bankhol", "bank holiday"), ("standby", "standby"),
    ("callout", "call-?out allowance"), ("tool", "tool"), ("uniform", "uniform|clothing"),
    ("firewarden", "warden"), ("other", "^other"),
]


def allowance_state(prof, state, rng):
    if "allow" in state:
        return state["allow"]
    p = prof
    s = p.shift if p.matched else 0.3
    fr = p.frontline if p.matched else 0.45
    london = p.region == "London"
    prev = {
        "shift": clamp(0.05 + 1.15 * s, 0.02, 0.93),
        "night": clamp(0.02 + 0.95 * s, 0.01, 0.85),
        "weekend": clamp(0.02 + 0.85 * s, 0.01, 0.8),
        "bankhol": clamp(0.05 + 0.85 * s, 0.02, 0.85),
        "oncall": clamp(0.12 + 0.55 * s + (0.22 if p.industry in ("Technology, Software & Digital",
                  "Energy, Utilities & Environmental Services", "Healthcare & Life Sciences") else 0), 0.05, 0.9),
        "standby": clamp(0.05 + 0.35 * s, 0.02, 0.6),
        "callout": clamp(0.06 + 0.45 * s, 0.02, 0.7),
        "car": clamp(0.15 + 0.35 * (1 - fr) + 0.15 * p.R, 0.05, 0.75),
        "location": 0.5 if london else 0.08,
        "travel": 0.22, "mobile": clamp(0.2 + 0.25 * (1 - fr), 0.1, 0.6),
        "meal": 0.18 if p.industry == HOSPITALITY else 0.08,
        "homework": clamp(0.05 + 0.25 * (1 - fr), 0.03, 0.4),
        "firstaid": clamp(0.12 + 0.3 * fr, 0.05, 0.5),
        "tool": 0.25 if p.industry in ("Construction & Infrastructure", "Manufacturing & Engineering") else 0.03,
        "uniform": clamp(0.04 + 0.2 * fr, 0.02, 0.35),
        "firewarden": clamp(0.06 + 0.12 * fr, 0.02, 0.25),
        "other": 0.07,
    }
    state["allow"] = {k: (rng.random() < v) for k, v in prev.items()}
    return state["allow"]


def canon_of(label):
    for key, pat in CANON_ALLOW:
        if re.search(pat, label, re.I):
            return key
    return None


def sample_multi(qid, q, spec, prof, state, rng):
    labels = [o["label"] for o in (q.options or [])]
    anchor = spec.get("anchor")
    chosen = []

    if anchor == "allowances_profile":
        allow = allowance_state(prof, state, rng)
        for lbl in labels:
            ck = canon_of(lbl)
            if ck and allow.get(ck):
                chosen.append(lbl)
    elif anchor == "union_scope":
        u = prof.union if prof.matched else 0.12
        if u < 0.08:
            none = next((l for l in labels if re.search(spec["none_pattern"], l, re.I)), labels[0])
            return none
        plan = [("Frontline|hourly", 0.85), ("Operations|manufacturing|logistics",
                 0.6 if prof.industry in INDUSTRIAL else 0.25),
                ("Professional|office", 0.6 if prof.public else 0.2),
                ("Engineering|technical|Specialist", 0.3), ("Management", 0.07),
                ("All employees", 0.5 if u > 0.6 else 0.05), ("Other", 0.05)]
        for pat, pr in plan:
            for lbl in labels:
                if re.search(pat, lbl, re.I) and lbl not in chosen and rng.random() < pr:
                    chosen.append(lbl)
    else:
        # generic per-option prevalence with anchor adjustments
        for lbl in labels:
            if spec.get("none_pattern") and re.search(spec["none_pattern"], lbl, re.I):
                continue
            base = spec.get("rest", 0.08)
            for pat, pv in spec["opts"].items():
                if re.search(pat, lbl, re.I):
                    base = pv
                    break
            base = adjust_multi(anchor, qid, lbl, base, prof, state, rng)
            if base is None:
                return "__BLANK__"
            if rng.random() < base:
                chosen.append(lbl)

    if not chosen:
        none = next((l for l in labels if spec.get("none_pattern") and re.search(spec["none_pattern"], l, re.I)), None)
        return none if none else "__BLANK__"
    # post-state for dependents
    if qid == "REW_BEN_038":
        state["pmi"] = any(re.search("Private Medical", l, re.I) for l in chosen)
    return "; ".join(chosen)


def adjust_multi(anchor, qid, lbl, base, p, state, rng):
    if anchor == "benefits_richness":
        base = clamp(base * (0.55 + 0.9 * p.R), 0.02, 0.97)
        if re.search("Private Medical", lbl, re.I):
            base = clamp(base + 0.25 * p.size - (0.35 if p.public else 0), 0.03, 0.9)
    elif anchor == "longservice_dep":
        if not state.get("longservice"):
            return None  # whole answer collapses to NA via none_pattern
    elif anchor == "homework_lowfrontline":
        if p.matched and p.frontline > 0.65 and not re.search("None", lbl, re.I):
            base *= 0.4
    elif anchor == "outsourcing_size":
        if re.search("Payroll", lbl, re.I):
            base = 0.68 - 0.4 * p.size
    elif anchor == "bonus_measures_dep":
        if state.get("bonus_none"):
            return None
        if re.search("Revenue|sales", lbl, re.I) and p.industry in PUBLICISH:
            base *= 0.3
    elif anchor == "paybudget_profile":
        if re.search("National Living Wage", lbl, re.I):
            base = 0.12 + 0.7 * p.frontline if p.matched else base
        if re.search("Union|collective", lbl, re.I):
            base = clamp(0.05 + 1.1 * p.union, 0.03, 0.85) if p.matched else base
    elif anchor == "checks_sector":
        if re.search("Criminal", lbl, re.I):
            base = 0.85 if p.industry in ("Healthcare & Life Sciences", "Education (Public & Private)",
                                          "Charity, Non-Profit & Social Enterprise",
                                          "Public Sector & Government") else 0.25
        if re.search("Credit|financial", lbl, re.I):
            base = 0.6 if p.industry == "Financial Services" else 0.06
    elif anchor == "salsac_size":
        if re.search("Pension", lbl, re.I):
            base = 0.22 + 0.6 * p.size
    return base


# =========================================================== matrix engine ==

def lad(rng, tops, noise=0.12, lo=0.0):
    """Ladder values for the 7 standard levels with multiplicative noise."""
    return [max(lo, t * math.exp(rng.gauss(0, noise))) for t in tops]


def by_level(rows, values, blank_below=None):
    out = {}
    idx = {rid: i for i, rid in enumerate(LEVELS)}
    for rid, _lbl in rows:
        i = idx.get(rid)
        out[rid] = None if i is None else values[i]
    return out


def matrix_generators(state, prof, rng, vocab):
    p = prof

    def bonus_levels():
        elig = state.get("bonus_elig") or ""
        if "None" in elig or state.get("bonus_none"):
            return None
        depth = {"75%+": 7, "50–74%": 6, "25–49%": 5, "10–24%": 4, "<10%": 3}.get(elig, 5)
        scale = {"Public Listed (PLC)": 1.35, "PE-backed": 1.25, "Subsidiary of Global Group": 1.1,
                 "Mutual / Co-operative": 0.6, "Public Sector Body": 0.45,
                 "Charity / Non-profit": 0.45}.get(p.own, 0.95)
        return depth, scale

    def g_bonus_max(q, rows):
        bl = bonus_levels()
        if not bl:
            return {rid: None for rid, _ in rows}
        depth, scale = bl
        vals = lad(rng, [65, 42, 30, 25, 18, 10, 7], 0.18)
        vals = [round(v * scale / 5) * 5 if i < depth else None for i, v in enumerate(vals)]
        vals = [max(5, v) if v is not None else None for v in vals]
        state["bonus_max"] = vals
        return by_level(rows, vals)

    def g_bonus_target(q, rows):
        mx = state.get("bonus_max")
        if not mx:
            bl = bonus_levels()
            if not bl:
                return {rid: None for rid, _ in rows}
            g_bonus_max(q, rows)
            mx = state["bonus_max"]
        vals = [None if v is None else max(5, round(v * rng.uniform(0.45, 0.65) / 5) * 5) for v in mx]
        return by_level(rows, vals)

    def g_lti_elig(q, rows):
        if p.own == "Public Listed (PLC)":
            probs = [0.97, 0.85, 0.35, 0.12, 0.03, 0.0, 0.0]
        elif p.own == "PE-backed":
            probs = [0.95, 0.75, 0.3, 0.1, 0.02, 0.0, 0.0]
        elif p.own in ("VC-backed (Private)",):
            probs = [0.9, 0.7, 0.5, 0.35, 0.25, 0.1, 0.08]  # equity culture
        elif p.own in ("Subsidiary of Global Group", "Private (UK-owned)", "Partnership / LLP"):
            probs = [0.5, 0.3, 0.1, 0.03, 0.0, 0.0, 0.0]
        else:
            probs = [0.05, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0]
        vals = ["Yes" if rng.random() < pr else "No" for pr in probs]
        state["lti"] = vals
        return by_level(rows, vals)

    def g_lti_max(q, rows):
        lti = state.get("lti") or ["No"] * 7
        base = lad(rng, [120, 70, 40, 25, 15, 10, 10], 0.25)
        vals = [round(b / 5) * 5 if lti[i] == "Yes" else None for i, b in enumerate(base)]
        state["lti_max"] = vals
        return by_level(rows, vals)

    def g_lti_typ(q, rows):
        mx = state.get("lti_max") or [None] * 7
        vals = [None if v is None else max(5, round(v * rng.uniform(0.4, 0.6) / 5) * 5) for v in mx]
        return by_level(rows, vals)

    def g_pension_typ(q, rows):
        v = pension_latent(p, state, rng)
        if p.public:
            vals = [round(clamp(v + rng.gauss(0, 0.8), 12, 30), 1) for _ in range(7)]
        else:
            uplift = [3.0, 2.0, 1.2, 0.8, 0.4, 0.0, 0.0]
            vals = [round(clamp(v + u + rng.gauss(0, 0.5), 3, 25)) for u in uplift]
        return by_level(rows, vals)

    def g_pension_max(q, rows):
        v = pension_latent(p, state, rng)
        if p.public:
            vals = [round(clamp(v + rng.gauss(0, 0.8), 12, 30)) for _ in range(7)]
        else:
            uplift = [4.5, 3.5, 2.5, 2.0, 1.5, 1.0, 1.0]
            vals = [round(clamp(v + u + rng.gauss(0, 0.7), 3, 28)) for u in uplift]
        return by_level(rows, vals)

    def g_pension_ee_max(q, rows):
        base = clamp(6 + 8 * p.R + rng.gauss(0, 1.5), 4, 20)
        vals = [round(clamp(base + u, 4, 25)) for u in [3, 2, 1, 1, 0, 0, 0]]
        return by_level(rows, vals)

    def g_pmi_premium(q, rows):
        if not state.get("pmi"):
            return {rid: None for rid, _ in rows}
        single = round(rng.uniform(650, 1450) / 10) * 10
        mult = {"single": 1.0, "partner": rng.uniform(1.7, 2.0), "family": rng.uniform(2.3, 2.9)}
        return {rid: round(single * mult.get(rid, 1.0) / 10) * 10 for rid, _ in rows}

    def g_pmi_elig(q, rows):
        if not state.get("pmi"):
            return {rid: "No" for rid, _ in rows}
        rule = state.get("pmi_rule") or ""
        if re.search("All employees|Post-probation|Contract|Service", rule, re.I):
            depth = 7
        else:  # grade-restricted or unknown
            depth = rng.choice([3, 4, 4, 5])
        vals = ["Yes" if i < depth else "No" for i in range(7)]
        return by_level(rows, vals)

    def g_car_amount(q, rows):
        if not state.get("allow", {}).get("car"):
            return {rid: None for rid, _ in rows}
        tops = lad(rng, [11000, 8000, 6500, 5500, 4500, 0, 0], 0.15)
        vals = [round(v / 250) * 250 if v > 1000 else None for v in tops]
        return by_level(rows, vals)

    def g_car_elig(q, rows):
        has = state.get("allow", {}).get("car")
        depth = rng.choice([3, 4, 4, 5]) if has else 0
        return by_level(rows, ["Yes" if i < depth else "No" for i in range(7)])

    def g_agency(q, rows):
        s = p.shift if p.matched else 0.3
        base = lad(rng, [1, 2, 3, 4.5, 6, 9, 14], 0.3)
        vals = [round(clamp(v * (0.6 + 1.3 * s), 0, 45), 1) for v in base]
        return by_level(rows, vals)

    def g_cph(q, rows):
        vals = [round(v) for v in lad(rng, [30, 25, 20, 16, 12, 8, 6], 0.2)]
        return by_level(rows, vals)

    def g_replace(q, rows):
        vals = [round(v) for v in lad(rng, [95, 80, 65, 50, 40, 30, 24], 0.18)]
        return by_level(rows, vals)

    def g_regret(q, rows):
        t = p.turnover
        base = [0.15, 0.2, 0.25, 0.3, 0.35, 0.42, 0.5]
        vals = [round(clamp(t * b * math.exp(rng.gauss(0, 0.25)), 0.5, 30), 1) for b in base]
        return by_level(rows, vals)

    def g_tth(q, rows):
        vals = [round(v) for v in lad(rng, [88, 66, 55, 43, 34, 25, 19], 0.16)]
        return by_level(rows, vals)

    def g_internal_fill(q, rows):
        vals = [round(clamp(v, 5, 80)) for v in lad(rng, [34, 40, 44, 46, 40, 30, 18], 0.2)]
        return by_level(rows, vals)

    def g_ld_spend(q, rows):
        base = clamp(0.6 + 2.0 * p.F + rng.gauss(0, 0.3), 0.3, 4.0)
        vals = [round(clamp(base * m * math.exp(rng.gauss(0, 0.1)), 0.2, 5.0), 1)
                for m in [1.5, 1.35, 1.2, 1.1, 1.0, 0.85, 0.7]]
        return by_level(rows, vals)

    def g_succession(q, rows):
        if p.F < 0.22 and rng.random() < 0.45:
            return by_level(rows, ["No"] * 7)
        depth = int(round(1 + p.F * 4.6 + rng.gauss(0, 0.6)))
        depth = max(1, min(6, depth))
        return by_level(rows, ["Yes" if i < depth else "No" for i in range(7)])

    def g_representation(q, rows):
        women_by_sector = {
            "Construction & Infrastructure": 18, "Logistics, Transport & Distribution": 27,
            "Manufacturing & Engineering": 29, "Energy, Utilities & Environmental Services": 31,
            "Technology, Software & Digital": 34, "Media, Communications & Creative Industries": 48,
            "Financial Services": 48, "Professional Services": 50, "Retail & Consumer Goods": 53,
            "Hospitality, Leisure & Travel": 52, "Public Sector & Government": 56,
            "Charity, Non-Profit & Social Enterprise": 63, "Education (Public & Private)": 68,
            "Healthcare & Life Sciences": 72,
        }
        women = clamp(women_by_sector.get(p.industry, 48) + rng.gauss(0, 4), 8, 85)
        ethnic = clamp((24 if p.region == "London" else 11) + rng.gauss(0, 4), 2, 50)
        vals = {
            "women": round(women), "ethnic_background": round(ethnic),
            "employees_aged_55": round(clamp(rng.gauss(19, 5), 5, 40)),
            "identify_as_disabled": round(clamp(rng.gauss(7, 2.5), 1, 20)),
            "identify_as_lgbtq": round(clamp(rng.gauss(4.5, 1.5), 1, 12)),
            "lower_socio_economic_background": round(clamp(rng.gauss(32, 8), 8, 60)),
            "higher_socio_economic_background": round(clamp(rng.gauss(36, 8), 10, 65)),
            "free_school_meals_at_school_age": round(clamp(rng.gauss(15, 5), 3, 35)),
        }
        return {rid: vals.get(rid) for rid, _ in rows}

    def notice_pick(weeks):
        v = vocab.get("b1785613-96ed-4a64-9fd7-762d0ac65f19") or \
            ["1 week", "2 weeks", "4 weeks", "8 weeks", "12 weeks", "16 weeks", "More than 16 weeks"]
        best = min(v, key=lambda lbl: abs(_weeks_of(lbl) - weeks))
        return best

    def g_notice_ee(q, rows):
        base = [13, 12, 9, 8, 5, 3.5, 2.5]
        f_adj = 1.0 + 0.4 * (p.F - 0.5)
        vals = [notice_pick(b * f_adj * math.exp(rng.gauss(0, 0.18))) for b in base]
        state["notice"] = vals
        return by_level(rows, vals)

    def g_notice_er(q, rows):
        ee = state.get("notice")
        if not ee:
            g_notice_ee(q, rows)
            ee = state["notice"]
        # employer notice the same or one band longer
        v = vocab.get("b1785613-96ed-4a64-9fd7-762d0ac65f19") or []
        vals = []
        for lbl in ee:
            wk = _weeks_of(lbl)
            vals.append(notice_pick(wk * (1.0 if rng.random() < 0.7 else 1.5)))
        return by_level(rows, vals)

    def g_overtime_mult(q, rows):
        if state.get("overtime") is False:
            return {rid: None for rid, _ in rows}
        v = vocab.get(q.id) or ["1x", "1.5x", "2x", "2.5x"]
        def pick(want):
            return min(v, key=lambda lbl: abs(float(lbl.replace("x", "")) - want))
        plan = {"day": 1.0 if rng.random() < 0.6 else 1.5, "early": 1.25 if "1.25x" in v else 1.5,
                "evening": 1.5, "night": 1.5, "weekend": 1.5 if rng.random() < 0.6 else 2.0,
                "bank_holiday": 2.0 if rng.random() < 0.7 else 2.5}
        return {rid: pick(plan.get(rid, 1.5)) for rid, _ in rows}

    def g_pay_mult(q, rows):
        if (p.matched and p.shift < 0.12):
            return {rid: None for rid, _ in rows}
        v = vocab.get(q.id) or ["1.0x", "1.25x", "1.5x", "2.0x"]
        def pick(want):
            return min(v, key=lambda lbl: abs(float(lbl.replace("x", "")) - want))
        plan = {"standard_daytime": 1.0, "early_morning": 1.0 if rng.random() < 0.5 else 1.25,
                "evening": 1.0 if rng.random() < 0.4 else 1.25,
                "late_night": 1.25 if rng.random() < 0.5 else 1.5,
                "weekend": 1.25 if rng.random() < 0.5 else 1.5,
                "bank_holiday": 1.5 if rng.random() < 0.6 else 2.0}
        return {rid: pick(plan.get(rid, 1.0)) for rid, _ in rows}

    def g_span(q, rows):
        v = vocab.get(q.id) or ["1–4 direct reports", "5–8 direct reports", "9–12 direct reports", "13+ direct reports"]
        def has(pat):
            return next((x for x in v if re.search(pat, x)), v[0])
        wide = p.frontline > 0.55
        plan = {
            "board_executive": has("5–8"), "director": has("5–8"),
            "head_of": has("5–8") if rng.random() < 0.6 else has("9–12"),
            "senior_manager": has("5–8") if rng.random() < 0.5 else has("9–12"),
            "manager": has("9–12") if rng.random() < 0.6 else has("5–8"),
            "supervisor_team_leader": has("13\\+") if wide and rng.random() < 0.6 else has("9–12"),
            "frontline_individual_contributor": has("1–4") if rng.random() < 0.6 else has("Varies"),
        }
        return {rid: plan.get(rid) for rid, _ in rows}

    def g_pensionability(q, rows):
        yes_p = 0.45 if p.public else 0.15
        same = "Yes" if rng.random() < yes_p else "No"
        return {rid: same for rid, _ in rows}

    def g_allow_values(q, rows):
        allow = state.get("allow") or allowance_state(prof, state, rng)
        ranges = {"london_weighting_location_allowance": (1500, 5000, "location"),
                  "shift_allowance": (1200, 4000, "shift"), "night_premium": (800, 3000, "night"),
                  "weekend_premium": (600, 2500, "weekend"), "bank_holiday_premium": (300, 1500, "bankhol"),
                  "on_call_allowance": (1200, 4200, "oncall"), "standby_allowance": (800, 2500, "standby"),
                  "call_out_allowance": (500, 2000, "callout"), "tool_allowance": (200, 700, "tool")}
        out = {}
        for rid, _lbl in rows:
            lo, hi, key = ranges.get(rid, (300, 1500, None))
            if key and allow.get(key):
                out[rid] = round(rng.uniform(lo, hi) / 50) * 50
            else:
                out[rid] = None
        return out

    def g_tronc_groups(q, rows):
        if not state.get("tronc"):
            return {rid: None for rid, _ in rows}
        plan = {"frontline_individual_contributor": "Yes", "supervisor_team_leader": "Yes",
                "manager": "Yes" if rng.random() < 0.5 else "No"}
        return {rid: plan.get(rid, "No") for rid, _ in rows}

    return {
        "323ffcf1-749b-43f3-bf34-1de6b8b1ca67": g_bonus_max,
        "REW_INC_111": g_bonus_target,
        "REW_INC_133": g_lti_elig,
        "REW_INC_LTI_MAX_01": g_lti_max,
        "REW_INC_LTI_VALUE_TYP_01": g_lti_typ,
        "REW_BEN_112": g_pension_typ,
        "REW_BEN_PENS_EMP_MAX_01": g_pension_max,
        "REW_BEN_PENS_EE_MAX_01": g_pension_ee_max,
        "3faf1f0c-f753-497f-a395-384bba38c5e3": g_pmi_premium,
        "REW_BEN_139": g_pmi_elig,
        "fa0f46f6-61e3-41d1-a2d1-3e57483bb1cf": g_car_amount,
        "REW_PAY_109": g_car_elig,
        "ATT_HIR_AGENCY_RATE_01": g_agency,
        "ATT_HIR_CPH_01": g_cph,
        "ATT_HIR_REPLACE_COST_01": g_replace,
        "ATT_OBO_REGRET_ATTR_01": g_regret,
        "MET_cd8efe96": g_tth,
        "GRO_CAR_042": g_internal_fill,
        "GRO_LEA_LD_SPEND_01": g_ld_spend,
        "GRO_POT_041": g_succession,
        "INC_Q308527": g_representation,
        "b1785613-96ed-4a64-9fd7-762d0ac65f19": g_notice_ee,
        "REW_Q524161": g_notice_er,
        "REW_Q528801": g_overtime_mult,
        "REW_Q534581": g_pay_mult,
        "PROP_168eb098": g_span,
        "REW_PAY_020": g_pensionability,
        "a7ed418e-b057-4b70-ab58-31e897b7c1b6": g_allow_values,
        "REW_FAI_TRONC_GROUPS_e5639ac2": g_tronc_groups,
    }


def _weeks_of(lbl):
    m = re.search(r"(\d+)", lbl)
    n = float(m.group(1)) if m else 1
    return n + (4 if "More" in lbl else 0)


# ========================================================== numeric engine ==

SECTOR_REV = {"Retail & Consumer Goods": 180, "Hospitality, Leisure & Travel": 90,
              "Logistics, Transport & Distribution": 160, "Manufacturing & Engineering": 220,
              "Construction & Infrastructure": 250, "Professional Services": 140,
              "Financial Services": 320, "Technology, Software & Digital": 200,
              "Healthcare & Life Sciences": 110, "Public Sector & Government": 85,
              "Education (Public & Private)": 70, "Charity, Non-Profit & Social Enterprise": 75,
              "Energy, Utilities & Environmental Services": 380,
              "Media, Communications & Creative Industries": 160}
SECTOR_WCR = {"Retail & Consumer Goods": 19, "Hospitality, Leisure & Travel": 33,
              "Logistics, Transport & Distribution": 28, "Manufacturing & Engineering": 24,
              "Construction & Infrastructure": 22, "Professional Services": 55,
              "Financial Services": 38, "Technology, Software & Digital": 45,
              "Healthcare & Life Sciences": 60, "Public Sector & Government": 62,
              "Education (Public & Private)": 68, "Charity, Non-Profit & Social Enterprise": 58,
              "Energy, Utilities & Environmental Services": 15,
              "Media, Communications & Creative Industries": 45}
SECTOR_WCPF = {"Professional Services": 60, "Financial Services": 65, "Technology, Software & Digital": 62,
               "Public Sector & Government": 44, "Education (Public & Private)": 40,
               "Healthcare & Life Sciences": 42, "Retail & Consumer Goods": 31,
               "Hospitality, Leisure & Travel": 29, "Logistics, Transport & Distribution": 36,
               "Manufacturing & Engineering": 44, "Construction & Infrastructure": 48,
               "Charity, Non-Profit & Social Enterprise": 36,
               "Energy, Utilities & Environmental Services": 55,
               "Media, Communications & Creative Industries": 48}


def numeric_generators(state, prof, rng):
    p = prof

    def Fq():
        return clamp(p.F + rng.gauss(0, 0.12), 0.02, 0.98)

    def rev_fte():
        if "rev_fte" not in state:
            base = SECTOR_REV.get(p.industry, 150) * 1000
            state["rev_fte"] = base * math.exp(rng.gauss(0, 0.3))
        return state["rev_fte"]

    gens = {
        "PROP_db35137e": lambda: round(clamp(52 + 34 * Fq() + rng.gauss(0, 5), 30, 95)),
        "PROP_8153af15": lambda: round(clamp(1 + 9 * (1 - Fq()) + rng.gauss(0, 1.2), 1, 18)),
        "PROP_b799860a": lambda: round(clamp(72 + 20 * (0.4 * p.brand + 0.6 * Fq()) + rng.gauss(0, 4), 55, 98)),
        "PROP_e91c054c": lambda: round(clamp(rng.lognormvariate(math.log(13), 0.5), 2, 45)),
        "PROP_94199ca7": lambda: round(clamp(3 + 22 * p.shift + (6 if p.industry == "Construction & Infrastructure" else 0) + rng.gauss(0, 3), 1, 45)),
        "PROP_3cb02f77": lambda: round(rev_fte() / 1000) * 1000,
        "PROP_d4b98d24": lambda: round(rev_fte() * (clamp(rng.gauss(0.02, 0.012), 0.0, 0.05) if (p.public or p.charity) else clamp(rng.gauss(0.10, 0.05), 0.01, 0.28)) / 500) * 500,
        "PROP_e63cf45a": lambda: round(clamp(SECTOR_WCR.get(p.industry, 40) + rng.gauss(0, 6), 8, 85)),
        "PROP_d16bae79": lambda: round(clamp(SECTOR_WCPF.get(p.industry, 45) * 1000 * math.exp(rng.gauss(0, 0.12)), 24000, 95000) / 500) * 500,
        "PROP_9620d380": lambda: round(clamp(1550 - 950 * p.size + rng.gauss(0, 180), 450, 2200) / 10) * 10,
        "PROP_8d9d9ac5": lambda: round(clamp(1.0 + 2.4 * (1 - p.size) + rng.gauss(0, 0.4), 0.7, 5.0), 1),
        "PROP_acdc8dd9": lambda: round(clamp(35 + 320 * SYS.get(p.reg.get("HR_Systems_Maturity"), 0.5) + rng.gauss(0, 40), 20, 600) / 5) * 5,
        "PROP_3315e16b": lambda: round(clamp(7 + 36 * Fq() + rng.gauss(0, 5), 2, 60)),
        "PROP_9e3b1d18": lambda: round(clamp(p.turnover * 1.3 + rng.gauss(0, 2.5), 1.5, 45), 1),
        "PROP_02c9eb9e": lambda: round(clamp(54 + 28 * (0.6 * p.voice + 0.4 * p.advocacy) + rng.gauss(0, 4), 35, 92)),
        "PROP_30ae24e7": lambda: round(clamp(4 + 48 * p.advocacy + rng.gauss(0, 9), 0, 75)),
        "PROP_9e4ad87f": lambda: round(clamp(2.7 + 2.3 * p.budgetF + rng.gauss(0, 0.4), 2.0, 6.5), 1),
    }
    return gens


# ============================================================== main run ====

def collect_vocab(files_dir, qids):
    """Distinct categorical answers per matrix question across original files."""
    vocab = defaultdict(set)
    for fn in os.listdir(files_dir):
        if not fn.endswith(".csv"):
            continue
        for r in csv.DictReader(open(os.path.join(files_dir, fn), encoding="utf-8-sig")):
            if r["question_id"] in qids and r["your_answer"].strip():
                vocab[r["question_id"]].add(r["your_answer"].strip())
    return {q: sorted(v) for q, v in vocab.items()}


CONTROLLER_ORDER = ["SICK_01_88ce3d5c", "REW_INC_103", "REW_BEN_HOL_003", "REW_BEN_FAM_001",
                    "REW_PAY_TRONC_6db81475", "REW_PAY_011", "PRO_COLLBARG_0a071dd7"]


def run():
    conn = get_conn()
    questions = load_questions()
    registry = json.load(open(os.path.join(DATA, "seeded_orgs.json")))
    reg_by_norm = {norm_name(r["Company_Name"]): r for r in registry}

    resp_dir = os.path.join(DATA, "responses")
    orig_dir = os.path.join(DATA, "responses_orig")
    if not os.path.isdir(orig_dir):
        shutil.copytree(resp_dir, orig_dir)
        print("Backed up originals to data/responses_orig/")

    # dynamic curated additions resolved by text (long-service scheme)
    ls_q = next((q for q in questions.values()
                 if re.search("long service award", (q.text or "") + (q.benchmark_display or ""), re.I)
                 and q.type in ("single_select", "yes_no")), None)

    cat_vocab = collect_vocab(orig_dir, {"b1785613-96ed-4a64-9fd7-762d0ac65f19", "REW_Q524161",
                                         "REW_Q528801", "REW_Q534581", "PROP_168eb098"})

    curated_select_ids = set(SELECT_PRIORS)
    if ls_q:
        curated_select_ids.add(ls_q.id)
    curated_multi_ids = set(MULTI_PRIORS)
    curated_matrix_ids = set(MATRIX_DRIVERS)
    curated_numeric_ids = set(NUMERIC_DRIVERS)

    # classification for reporting
    skipped, pattern_ids = set(), set()
    for qid, q in questions.items():
        if qid in curated_select_ids or qid in curated_multi_ids or \
           qid in curated_matrix_ids or qid in curated_numeric_ids:
            continue
        cfg = q.scoring_config or {}
        laddered = (q.type in ("single_select", "yes_no") and cfg.get("polarity") != "neutral"
                    and len(set((cfg.get("option_scores") or {}).values())) >= 2)
        if laddered:
            pattern_ids.add(qid)
        else:
            skipped.add(qid)

    files = sorted(fn for fn in os.listdir(orig_dir) if fn.endswith(".csv"))
    matched_n, baseline_n = 0, 0

    for fn in files:
        rows = list(csv.DictReader(open(os.path.join(orig_dir, fn), encoding="utf-8-sig")))
        if not rows:
            continue
        org_id, org_name = rows[0]["org_id"], rows[0]["org_name"]
        reg = reg_by_norm.get(norm_name(org_name))
        rng = random.Random("lumi-regen::" + org_id)
        prof = Profile(reg, rng)
        if prof.matched:
            matched_n += 1
        else:
            baseline_n += 1
        state = {}
        mgens = matrix_generators(state, prof, rng, cat_vocab)
        ngens = numeric_generators(state, prof, rng)

        # group original rows per question
        by_q = defaultdict(list)
        for r in rows:
            by_q[r["question_id"]].append(r)

        answers = {}  # qid -> {"": val} or {row_id: val}; "__SKIP__" keeps original

        def gen_select(qid):
            q = questions.get(qid)
            if q is None:
                return
            if qid == (ls_q.id if ls_q else None):
                spec = {"w": {"^Yes": 0.40 + 0.35 * prof.R, "^No": 0.57 - 0.35 * prof.R, "Don't know": 0.03}}
            else:
                spec = SELECT_PRIORS[qid]
            w = resolve_weights(q, spec) if "w" in spec else {}
            if spec.get("tilt"):
                w = tilt_by_score(q, w, prof.F, spec["tilt"])
            if spec.get("anchor"):
                w = anchors(spec["anchor"], q, w, prof, state, rng)
            lbl = sample_label({k: v for k, v in w.items() if k}, rng)
            # light non-response
            if not q.is_required and rng.random() < 0.02:
                lbl = ""
            answers[qid] = {"": lbl}
            # state updates
            if qid == "SICK_01_88ce3d5c":
                state["osp"] = lbl.startswith("Yes")
            elif qid == "REW_INC_103":
                state["bonus_elig"] = lbl
                state["bonus_none"] = (lbl == "None" or lbl == "")
            elif qid == "REW_BEN_HOL_003":
                state["buy_leave"] = bool(re.search("buy", lbl, re.I))
            elif qid == "REW_BEN_FAM_001":
                state["maternity_enhanced"] = not re.search("Statutory pay only|Don't know", lbl or "x", re.I)
            elif qid == "REW_PAY_TRONC_6db81475":
                state["tronc"] = lbl == "Yes"
            elif qid == "REW_PAY_011":
                state["overtime"] = lbl == "Yes"
            elif ls_q and qid == ls_q.id:
                state["longservice"] = lbl == "Yes"
            elif qid == "REW_BEN_044":
                state["pmi_rule"] = lbl

        # pass 1: controllers
        for qid in CONTROLLER_ORDER + ([ls_q.id] if ls_q else []):
            if qid in by_q and qid in curated_select_ids:
                gen_select(qid)
        # pass 2: curated multis (REW_BEN_038 before REW_BEN_044)
        for qid in MULTI_PRIORS:
            if qid not in by_q:
                continue
            q = questions.get(qid)
            val = sample_multi(qid, q, MULTI_PRIORS[qid], prof, state, rng)
            if val == "__BLANK__":
                answers[qid] = {"": ""}
            else:
                if not q.is_required and rng.random() < 0.03:
                    val = ""
                answers[qid] = {"": val}
        # pass 3: remaining curated selects
        for qid in curated_select_ids:
            if qid in by_q and qid not in answers:
                gen_select(qid)
        # pass 4: pattern-template selects
        for qid in pattern_ids:
            if qid not in by_q:
                continue
            q = questions[qid]
            w = template_weights(q, prof, rng)
            if w is None:
                skipped.add(qid)
                continue
            lbl = sample_label(w, rng)
            if not q.is_required and rng.random() < 0.025:
                lbl = ""
            answers[qid] = {"": lbl}
        # pass 5: curated matrices
        for qid, gen in mgens.items():
            if qid not in by_q:
                continue
            q = questions[qid]
            row_pairs = [(r["matrix_row_id"], r["matrix_row_label"]) for r in by_q[qid]]
            if rng.random() < 0.03 and not q.is_required:
                answers[qid] = {rid: "" for rid, _ in row_pairs}
                continue
            vals = gen(q, row_pairs)
            answers[qid] = {rid: ("" if v is None else str(v)) for rid, v in vals.items()}
        # pass 6: curated numerics
        for qid, gen in ngens.items():
            if qid not in by_q:
                continue
            q = questions[qid]
            if not q.is_required and rng.random() < 0.08:
                answers[qid] = {"": ""}
            else:
                answers[qid] = {"": str(gen())}

        # required questions must be answered: backfill skipped+required blanks
        for qid in skipped:
            q = questions.get(qid)
            if q is None or qid not in by_q or not q.is_required:
                continue
            for r in by_q[qid]:
                if not r["your_answer"].strip() and q.options:
                    subs = [o["label"] for o in q.options if not o.get("is_na")]
                    if subs:
                        r["your_answer"] = rng.choice(subs)

        # write file
        out_path = os.path.join(resp_dir, fn)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wtr.writeheader()
            for r in rows:
                qid = r["question_id"]
                if qid in answers:
                    amap = answers[qid]
                    key = r["matrix_row_id"] or ""
                    if key in amap:
                        r = dict(r)
                        r["your_answer"] = amap[key]
                wtr.writerow(r)

    # ------------------------------------------------------------- report ---
    report = {
        "orgs_profile_driven": matched_n,
        "orgs_baseline_only": baseline_n,
        "curated_selects": sorted(curated_select_ids),
        "curated_multis": sorted(curated_multi_ids),
        "curated_matrices": sorted(curated_matrix_ids),
        "curated_numerics": sorted(curated_numeric_ids),
        "pattern_template_selects": sorted(pattern_ids),
        "skipped": sorted(skipped),
        "counts": {
            "curated": len(curated_select_ids) + len(curated_multi_ids)
                       + len(curated_matrix_ids) + len(curated_numeric_ids),
            "pattern": len(pattern_ids),
            "skipped": len(skipped),
        },
        "rationales": {qid: {"rationale": s.get("rationale"), "source": s.get("source"),
                             "drivers": s.get("drivers")} for qid, s in SELECT_PRIORS.items()},
        "multi_rationales": {qid: {"rationale": s.get("rationale"), "source": s.get("source"),
                                   "drivers": s.get("drivers")} for qid, s in MULTI_PRIORS.items()},
        "matrix_drivers": MATRIX_DRIVERS,
        "numeric_drivers": NUMERIC_DRIVERS,
    }
    with open(os.path.join(DATA, "regen_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("Regenerated %d files. Profile-driven orgs: %d; baseline-only: %d"
          % (len(files), matched_n, baseline_n))
    print("Curated: %(curated)d questions  Pattern-template: %(pattern)d  Skipped: %(skipped)d"
          % report["counts"])
    print("Report written to data/regen_report.json")
    skipped_titles = [(qid, (questions[qid].display_title or "")[:70]) for qid in sorted(skipped) if qid in questions]
    print("\nSKIPPED (left generic for hand-curation) — first 40 of %d:" % len(skipped_titles))
    for qid, t in skipped_titles[:40]:
        print("  ", qid, "|", t)
    return report


if __name__ == "__main__":
    run()
