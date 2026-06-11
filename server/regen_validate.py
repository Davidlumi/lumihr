# -*- coding: utf-8 -*-
"""Common-sense validation gate for the regenerated seed data.

Checks, per the regeneration brief:
  1. Plausibility heuristics on every single_select/yes_no distribution
     (modal-curated-answer at ~0%; near-uniform where central tendency is
     expected; NA/Don't-know dominating a mainstream question).
  2. Re-check of every curated question (table: question, top answer, %, flag).
  3. Profile-contradiction spot table for 20 orgs across the maturity spectrum
     (+ shift-allowance and gender-pay-gap hard checks).
  4. Before/after distributions for 10 headline questions.
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn
from library import load_questions
from regen_priors import SELECT_PRIORS, MULTI_PRIORS
from regenerate import Profile, norm_name
import random

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
NA_PAT = re.compile(r"don't know|not measured|not tracked|not applicable|not calculated|prefer not", re.I)

FLAGS = []


def load_answers(d):
    """{qid: {org: label}} for selects; multi kept raw."""
    out = defaultdict(dict)
    for fn in os.listdir(d):
        if not fn.endswith(".csv"):
            continue
        for r in csv.DictReader(open(os.path.join(d, fn), encoding="utf-8-sig")):
            if not r["matrix_row_id"]:
                out[r["question_id"]][r["org_id"]] = r["your_answer"].strip()
    return out


def dist(ans_map, qid):
    vals = [v for v in ans_map[qid].values() if v]
    c = Counter(vals)
    n = len(vals)
    return c, n


def main():
    questions = load_questions()
    new = load_answers(os.path.join(DATA, "responses"))
    old = load_answers(os.path.join(DATA, "responses_orig"))
    report = json.load(open(os.path.join(DATA, "regen_report.json")))
    curated = set(report["curated_selects"])
    pattern = set(report["pattern_template_selects"])
    skipped = set(report["skipped"])

    # ---------------------------------------------------- 1+2. distributions
    print("=" * 100)
    print("DISTRIBUTION CHECKS — curated questions (question | top answer | % | verdict)")
    print("=" * 100)
    curated_flags = 0
    for qid in sorted(curated):
        q = questions.get(qid)
        if q is None or q.type not in ("single_select", "yes_no"):
            continue
        c, n = dist(new, qid)
        if n == 0:
            FLAGS.append((qid, "no answers"))
            continue
        top, topn = c.most_common(1)[0]
        verdict = "pass"
        # (a) curated prior-modal option near zero
        spec = SELECT_PRIORS.get(qid)
        if spec:
            modal_pat = max(spec["w"].items(), key=lambda kv: kv[1])[0]
            modal_share = sum(v for k, v in c.items() if re.search(modal_pat, k, re.I)) / n
            if spec["w"][modal_pat] >= 0.3 and modal_share < 0.05 and not spec.get("anchor"):
                verdict = "FLAG modal-near-zero"
        # (c) NA domination
        na_share = sum(v for k, v in c.items() if NA_PAT.search(k)) / n
        if na_share > 0.35 and not (spec and spec.get("anchor") in
                                    ("tronc_sector", "tronc_sector_dep", "pmi_consistency",
                                     "buy_leave_consistency", "buy_leave_consistency2",
                                     "osp_consistency_wait", "union_bargaining2")):
            verdict = "FLAG na-dominates(%.0f%%)" % (na_share * 100)
        if verdict != "pass":
            curated_flags += 1
            FLAGS.append((qid, verdict))
        print("%-26s | %-46s | %4.1f%% | n=%3d | %s" %
              (qid, top[:46], 100.0 * topn / n, n, verdict))

    # pattern + skipped heuristics
    print("\nPattern/skipped heuristic flags:")
    moved_to_skip = []
    for qid in sorted(pattern):
        q = questions.get(qid)
        if q is None:
            continue
        c, n = dist(new, qid)
        if n < 30:
            continue
        shares = sorted((v / n for v in c.values()), reverse=True)
        na_share = sum(v for k, v in c.items() if NA_PAT.search(k)) / n
        subst = [s for k, s in ((k, v / n) for k, v in c.items()) if not NA_PAT.search(k)]
        near_uniform = len(subst) >= 4 and (max(subst) - min(subst)) < 0.08
        if na_share > 0.35:
            moved_to_skip.append((qid, "na-dominates %.0f%%" % (na_share * 100)))
        elif near_uniform:
            moved_to_skip.append((qid, "near-uniform"))
    for qid, why in moved_to_skip:
        print("  FLAG %-24s %s -> moved to skip list" % (qid, why))
    if not moved_to_skip:
        print("  (none)")

    # ------------------------------------------------- 3. profile spot table
    print("\n" + "=" * 100)
    print("PROFILE vs ANSWER SPOT TABLE — 20 orgs across the maturity spectrum")
    print("=" * 100)
    registry = json.load(open(os.path.join(DATA, "seeded_orgs.json")))
    reg_by_norm = {norm_name(r["Company_Name"]): r for r in registry}
    # org meta from files
    org_meta = {}
    for fn in os.listdir(os.path.join(DATA, "responses")):
        if fn.endswith(".csv"):
            with open(os.path.join(DATA, "responses", fn), encoding="utf-8-sig") as f:
                r0 = next(csv.DictReader(f))
                org_meta[r0["org_id"]] = r0["org_name"]

    # per-org mean practice score over pattern questions
    scores_by_org = defaultdict(list)
    qscore = {}
    for qid in pattern | curated:
        q = questions.get(qid)
        if not q or q.type not in ("single_select", "yes_no"):
            continue
        cfg = q.scoring_config or {}
        sc = cfg.get("option_scores") or {}
        by_label = {o["label"]: sc.get(o["code"]) for o in (q.options or [])}
        qscore[qid] = by_label
    for qid, omap in new.items():
        bl = qscore.get(qid)
        if not bl:
            continue
        for org, lbl in omap.items():
            s = bl.get(lbl)
            if s is not None:
                scores_by_org[org].append(s)

    profs = {}
    for oid, name in org_meta.items():
        reg = reg_by_norm.get(norm_name(name))
        profs[oid] = (reg, Profile(reg, random.Random("lumi-regen::" + oid)))
    matched = [(oid, reg, p) for oid, (reg, p) in profs.items() if reg]
    matched.sort(key=lambda t: t[2].F)
    sample = matched[:7] + matched[len(matched)//2 - 3: len(matched)//2 + 3] + matched[-7:]

    def shift_alw(oid):
        row = new.get("REW_PAY_016", {}).get(oid, "")
        return "shift✓" if re.search("Shift allowance", row or "") else "shift✗"

    def gpg(oid):
        return (new.get("REW_FAI_079", {}).get(oid) or "—")[:13]

    lo_scores, hi_scores = [], []
    print("%-34s %-9s %-10s %-18s %5s %8s %8s %9s %s" %
          ("Org", "FTE", "HR_Mat", "Systems", "F", "PracScr", "ShiftAlw", "GPG", "Shift%"))
    for oid, reg, p in sample:
        ms = sum(scores_by_org[oid]) / max(len(scores_by_org[oid]), 1)
        print("%-34s %-9s %-10s %-18s %5.2f %7.1f %9s %9s %5d%%" %
              (org_meta[oid][:33], reg["FTE_Band"], reg["HR_Maturity"][:9],
               reg["HR_Systems_Maturity"][:17], p.F, ms, shift_alw(oid), gpg(oid),
               reg.get("Workforce_Shift_%", 0)))
    for oid, reg, p in matched:
        ms = sum(scores_by_org[oid]) / max(len(scores_by_org[oid]), 1)
        if p.F < 0.3:
            lo_scores.append(ms)
        elif p.F > 0.7:
            hi_scores.append(ms)

    lo_m = sum(lo_scores) / max(len(lo_scores), 1)
    hi_m = sum(hi_scores) / max(len(hi_scores), 1)
    ok_sep = hi_m - lo_m > 15
    print("\nLatent-maturity separation: low-F mean practice score %.1f vs high-F %.1f -> %s"
          % (lo_m, hi_m, "PASS" if ok_sep else "FLAG"))
    if not ok_sep:
        FLAGS.append(("maturity-separation", "lo %.1f hi %.1f" % (lo_m, hi_m)))

    # shift allowance hard check
    hi_shift = [oid for oid, reg, p in matched if (reg.get("Workforce_Shift_%") or 0) >= 40]
    lo_shift = [oid for oid, reg, p in matched if (reg.get("Workforce_Shift_%") or 0) <= 12]
    def shift_rate(ids):
        sel = [1 for oid in ids if re.search("Shift allowance", new.get("REW_PAY_016", {}).get(oid) or "")]
        return len(sel) / max(len(ids), 1)
    hr, lr = shift_rate(hi_shift), shift_rate(lo_shift)
    ok = hr > 0.6 and lr < 0.3
    print("Shift allowance: high-shift orgs %.0f%% offer vs low-shift %.0f%% -> %s"
          % (hr * 100, lr * 100, "PASS" if ok else "FLAG"))
    if not ok:
        FLAGS.append(("shift-allowance", "hi %.2f lo %.2f" % (hr, lr)))

    # GPG hard check
    big = [oid for oid, reg, p in matched if reg["FTE_Band"] != "50-249"]
    yes = sum(1 for oid in big if (new.get("REW_FAI_079", {}).get(oid) or "").startswith("Yes"))
    rate = yes / max(len(big), 1)
    print("Gender pay gap analysis among 250+ orgs: %.0f%% Yes -> %s"
          % (rate * 100, "PASS" if rate > 0.85 else "FLAG"))
    if rate <= 0.85:
        FLAGS.append(("gpg-250", "%.2f" % rate))

    # contradiction: spreadsheets orgs vs top-maturity answers
    sheets = [oid for oid, reg, p in matched if reg["HR_Systems_Maturity"] == "Spreadsheets"
              and reg["HR_Maturity"] == "Basic"]
    bad = []
    for oid in sheets:
        ms = sum(scores_by_org[oid]) / max(len(scores_by_org[oid]), 1)
        if ms > 55:
            bad.append((org_meta[oid], ms))
    print("Basic/Spreadsheets orgs with top-maturity answer profiles: %s -> %s"
          % (bad if bad else "none", "PASS" if not bad else "FLAG"))
    if bad:
        FLAGS.append(("low-maturity-contradiction", str(bad)))

    # ------------------------------------------------ 4. before/after report
    print("\n" + "=" * 100)
    print("BEFORE / AFTER — 10 headline questions")
    print("=" * 100)
    show = ["PROP_8e0b6316", "PROP_dff9a2a5", "PROP_36b990f9", "REW_BEN_SICK_004",
            "REW_BEN_HOL_001", "REW_INC_103", "REW_FAI_079", "MET_7f79a965",
            "WEL_MEN_021", "CONT_01_7e020202"]
    for qid in show:
        q = questions.get(qid)
        co, no_ = dist(old, qid), dist(new, qid)
        print("\n%s — %s" % (qid, (q.text if q else "?")[:90]))
        order = [o["label"] for o in (q.options or [])]
        print("  %-38s %9s %9s" % ("option", "before", "after"))
        for lbl in order:
            b = 100.0 * co[0].get(lbl, 0) / max(co[1], 1)
            a = 100.0 * no_[0].get(lbl, 0) / max(no_[1], 1)
            print("  %-38s %8.1f%% %8.1f%%" % (lbl[:38], b, a))
        print("  %-38s %8d %9d" % ("(answered)", co[1], no_[1]))
    # ALLOW_01 option prevalence before/after
    print("\nALLOW_01 — allowances offered (%% of answering orgs selecting)")
    for d, tag in ((old, "before"), (new, "after")):
        vals = [v for v in d["ALLOW_01"].values() if v]
        n = len(vals)
        cnt = Counter()
        for v in vals:
            for tok in v.split(";"):
                cnt[tok.strip()] += 1
        tops = ", ".join("%s %.0f%%" % (k[:22], 100.0 * c / n) for k, c in cnt.most_common(6))
        print("  %s (n=%d): %s" % (tag, n, tops))

    # blanks
    def blank_rate(d):
        tot = blank = 0
        for qid, omap in d.items():
            for v in omap.values():
                tot += 1
                blank += (v == "")
        return 0  # selects only loaded non-blank; recompute below

    def blank_all(dirname):
        tot = blank = 0
        for fn in os.listdir(dirname):
            if not fn.endswith(".csv"):
                continue
            for r in csv.DictReader(open(os.path.join(dirname, fn), encoding="utf-8-sig")):
                tot += 1
                blank += (not r["your_answer"].strip())
        return blank, tot
    b0, t0 = blank_all(os.path.join(DATA, "responses_orig"))
    b1, t1 = blank_all(os.path.join(DATA, "responses"))
    print("\nBlank rate: before %.1f%%  after %.1f%%" % (100.0 * b0 / t0, 100.0 * b1 / t1))

    print("\n" + "=" * 100)
    print("FLAGS: %d curated, %d moved-to-skip, hard-check failures: %s"
          % (curated_flags, len(moved_to_skip),
             [f for f in FLAGS if f[0] in ("maturity-separation", "shift-allowance",
                                           "gpg-250", "low-maturity-contradiction")] or "none"))
    if moved_to_skip:
        rep = json.load(open(os.path.join(DATA, "regen_report.json")))
        rep["skipped"] = sorted(set(rep["skipped"]) | {q for q, _ in moved_to_skip})
        rep["moved_to_skip_by_validation"] = moved_to_skip
        json.dump(rep, open(os.path.join(DATA, "regen_report.json"), "w"), indent=1)
    return FLAGS


if __name__ == "__main__":
    main()
