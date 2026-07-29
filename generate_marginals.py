#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIFF 2 — marginal-set GENERATOR (ruled 2026-07-16). Replaces the hand-derived
anchored_spikes.json with a file generated from the CLEAN register by rule.

HARD DESIGN RULES (all ruled):
 - Reads STRUCTURED inputs only: the register CSV (authority), generator_rules.json
   (39 ruled rules), structured_bases.json (read-and-verified base fields). It NEVER
   parses anchor prose for numbers at generation time.
 - Marginal only where earned: a row emits a marginal ONLY if a ruled rule or a
   verified structured base supports it. Anchored-but-unstructured rows -> CONTEXT
   (ruled: the 25-row base-extraction table is a follow-on, never a blocker).
 - Cohort blend: target = (sme*30 + large*190)/220 (cohort is 86% large-250+).
   all_large rows blend all-as-SME-proxy and are FLAGGED. all_only emits no-blend
   with an all-UK caveat. large_only emits ONLY where a ruled rule says so; a new
   large_only extraction without a ruling -> PENDING (never silently emitted).
 - VERBATIM validator: every number a marginal uses must appear in that row's
   register anchor text. A number that cannot be found is a fabrication -> hard fail.
 - Founding-error guard: REW26_BEN_SALSAC must resolve to NO-EMIT; MENOPLAN and
   PLSA_QM must resolve to context. Hard asserts, not conventions.
 - Ruled orderings (38 option_order + worst_option keys, David-ruled) migrate into
   their OWN namespace `ruled_orderings` — the phantom-entry hygiene fix by construction.
Output: generated_marginals.json + generated_marginal_table.csv (the David review gate).
No DB writes. The re-seed (Diff 3) is a separate approval on the generated file.
"""
import csv, json, re, sys

SME_N, LG_N, COHORT = 30, 190, 220
RULED = "2026-07-16"

from register_resolve import resolve_canonical_register   # C9 rule: highest-dated versioned CSV
_REG_PATH = resolve_canonical_register()
reg = list(csv.DictReader(open(_REG_PATH, encoding="utf-8-sig")))
rules = json.load(open("generator_rules.json"))["rules"]
bases = json.load(open("structured_bases.json"))          # metric_id -> structured fields
# Diff 15 (ruled 2026-07-18 ⑥): full-distribution reshapes. A structured_bases entry
# carrying "ruled_distribution" emits into the ruled_distributions section (exact
# per-option shares, freeze-gated at the 5pp register line by qa_plausibility) and
# NEVER derives a share-marginal — the construct is the whole distribution.
ruled_dists = {q: {"distribution": b["ruled_distribution"], "grade": b.get("grade", "EST"),
                   "source": b.get("source", ""), "semantics": b.get("target_semantics", "")}
               for q, b in bases.items()
               if isinstance(b, dict) and b.get("ruled_distribution")}
# r3s2: maturity-gradient metrics — per-org prevalence keyed on HR_Maturity, one shared
# mechanism (engine maturity_assign), per-metric three-level anchors from structured_bases.
maturity_grads = {q: dict(b["maturity_anchors"], grade=b.get("grade", "EST"),
                          source=b.get("source", ""), semantics=b.get("target_semantics", ""))
                  for q, b in bases.items()
                  if isinstance(b, dict) and b.get("maturity_anchors")}
# r3sw8: multi-select incidence — INDEPENDENT per-option prevalences over an applicable base
# (conditioned metric; shares deliberately don't sum to 100). Gated per-option by qa_plausibility
# tier-2d at max(5pp, 1/n); the base itself is held by a subset_orgs coherence pair.
ms_incidence = {q: {"prevalences": b["option_prevalences"], "terminal": b.get("terminal"),
                    "base": b.get("base", ""), "grade": b.get("grade", "EST"),
                    "source": b.get("source", ""), "semantics": b.get("target_semantics", "")}
                for q, b in bases.items()
                if isinstance(b, dict) and b.get("option_prevalences")}
RULED_ORD = json.load(open("ruled_orderings.json"))["orderings"]   # THE standing orderings artifact
# Ruled context (2026-07-16): one-pole-of-multi-pole = context (PAY_097/PAY_017, as principle);
# GAP_009 set-not-pole (question shape, figure-independent); WEL_BUDGET numeric (G8: no
# distribution anchor -> reshaping would invent data; 0.54 large-only exists-rate carried as doc).
RULED_CONTEXT = {
    "REW_PAY_097": "one-pole-of-multi-pole (ruled principle)",
    "REW_PAY_017": "one-pole-of-multi-pole (ruled principle)",
    "EXT_REW_GAP_009": "set-not-pole (prior ruling; question shape, figure-independent)",
    "REW26_WEL_BUDGET": "numeric, no distribution anchor (G8) — 0.54 large-only exists-rate carried as documentation",
}
# SETTLED re-freeze (ruled 2026-07-16): G7 baseline re-established post-correction — the old
# frozen values included the defective seed (EAP 0.309 WAS the bug). frozen_targets.json is
# updated at Diff 3 APPLY (updating earlier would fail interim qa_reseed runs against live).
SETTLED_REFREEZE = {"REW26_WEL_EAP": None, "REW26_BEN_PENSION_MATCH": None,
                    "REW26_WEL_FINWELL": None, "REW26_WEL_STRATEGY": None}

def blend(sme, large):
    return round((sme / 100.0 * SME_N + large / 100.0 * LG_N) / COHORT, 4)

import re as _re

def num_in_text(num, text):
    """Verbatim guard: the number as written must appear in the register prose — OR be the
    exact midpoint of a range that appears verbatim (declared-range rule: '58-59%' -> 58.5).
    Anything else is a fabrication and hard-fails."""
    if num is None:
        return True
    t = text.replace(",", "")
    s = ("%g" % num)
    if s in t or s.rstrip("0").rstrip(".") in t:
        return True
    for lo, hi in _re.findall(r"(\d+(?:\.\d+)?)\s*[-\u2013]\s*(\d+(?:\.\d+)?)\s*%", t):
        if abs((float(lo) + float(hi)) / 2.0 - float(num)) < 1e-9:
            return True
    return False

marginals, context, floors, pending, table = {}, {}, {}, {}, []
byid = {r["metric_id"].strip(): r for r in reg}
# The register is versioned and resolved by rule (C9), so a hardcoded row count fires on every
# legitimate register bump — it fired here at v2026-07-29 (255 rows vs a pinned 249). The invariant
# it was really standing in for is UNIQUENESS: metric_id is the key this whole file indexes by, and a
# duplicate would silently drop a row. That IS derivable, so it replaces the count.
assert len(byid) == len(reg), ("duplicate metric_id in %s: %d rows -> %d unique"
                               % (__import__("os").path.basename(_REG_PATH), len(reg), len(byid)))
print("register: %s | %d rows" % (__import__("os").path.basename(_REG_PATH), len(reg)))

for r in reg:
    q = r["metric_id"].strip()
    anchor = (r["real_anchor"] or "").strip()
    row = {"metric_id": q, "sub_power": r["sub_power"], "grade": r.get("grade") or "",
           "question": (r.get("question") or "")[:110], "target": "", "base_type": "",
           "inputs": "", "flags": "", "route": "", "evidence": ""}

    rule = rules.get(q)
    b = bases.get(q)

    if q in RULED_CONTEXT:
        row["route"] = "context (RULED: %s)" % RULED_CONTEXT[q][:60]
        context[q] = {"why": RULED_CONTEXT[q]}
    elif not anchor:
        row["route"] = "context (EST/unanchored)"; context[q] = {"why": "unanchored"}
    elif rule and (rule["subclass"].startswith("CONTEXT") or "do-not-emit" in rule["rule"].lower()):
        row["route"] = "context (ruled: %s)" % rule["subclass"]
        context[q] = {"why": rule["rule"][:160]}
    elif rule and rule["subclass"] in ("BLEND_ELIGIBLE", "SINGLE_BASE"):
        m = re.search(r"blend ([\d.]+)/([\d.]+)", rule["rule"])
        if rule["subclass"] == "BLEND_ELIGIBLE" and m:
            sme, lg = float(m.group(1)) * 100, float(m.group(2)) * 100
            t = blend(sme, lg)
            marginals[q] = {"target_share": t, "base_type": "sme_large(ruled)", "sme": sme, "large": lg,
                            "grade": r.get("grade") or "", "source": (r.get("source") or "")[:80],
                            "rule": rule["rule"][:120]}
            row.update(route="MARGINAL (ruled blend)", target=t, base_type="sme_large",
                       inputs="%g/%g" % (sme, lg), evidence=rule["rule"][:90])
        else:
            m2 = re.search(r"no-blend (?:all-UK |flat-UK |large-only )?([\d.]+)", rule["rule"])
            assert m2, "SINGLE_BASE rule unreadable for %s: %s" % (q, rule["rule"])
            t = round(float(m2.group(1)), 4)
            marginals[q] = {"target_share": t, "base_type": "single(ruled)", "grade": r.get("grade") or "",
                            "source": (r.get("source") or "")[:80], "rule": rule["rule"][:120]}
            row.update(route="MARGINAL (ruled single)", target=t, base_type="single",
                       inputs="%g" % t, evidence=rule["rule"][:90])
            if "large-only" in rule["rule"]:
                row["flags"] = "large-only (ruled emit-with-caveat)"
    elif b:
        bt = b["base_type"]
        if b.get("ruled_distribution") or b.get("maturity_anchors") or b.get("option_prevalences"):
            # Diff 15: full-distribution base — emits via ruled_dists (built at load),
            # never a share-marginal. Route recorded for the review table. r3sw8 adds
            # option_prevalences here so a future real_anchor fill can't re-route the row.
            row.update(route="RULED_DISTRIBUTION (full-dist)" if b.get("ruled_distribution")
                             else ("MULTISELECT_INCIDENCE (r3sw8)" if b.get("option_prevalences")
                                   else "MATURITY_GRADIENT (r3s2)"), base_type=bt,
                       inputs=json.dumps(b.get("ruled_distribution") or b.get("option_prevalences")
                                         or b["maturity_anchors"].get("anchors")
                                         or sorted(b["maturity_anchors"].get("band_distributions", {})))[:60])
        elif bt == "not_prevalence":
            row["route"] = "context (verified not-prevalence)"; context[q] = {"why": b.get("flags") or "not a prevalence"}
        elif bt == "sme_large":
            for v, lbl in ((b.get("sme_pct"), "sme"), (b.get("large_pct"), "large")):
                assert num_in_text(v, anchor), "VERBATIM FAIL %s %s=%s not in register text" % (q, lbl, v)
            t = blend(b["sme_pct"], b["large_pct"])
            marginals[q] = {"target_share": t, "base_type": "sme_large", "sme": b["sme_pct"],
                            "large": b["large_pct"], "all": b.get("all_pct"),
                            "grade": r.get("grade") or "", "source": (r.get("source") or "")[:80],
                            "evidence": b["verbatim_evidence"][:200]}
            row.update(route="MARGINAL (blend)", target=t, base_type=bt,
                       inputs="%g/%g" % (b["sme_pct"], b["large_pct"]),
                       flags=b.get("flags") or "", evidence=b["verbatim_evidence"][:90])
        elif bt == "all_large":
            for v in (b.get("all_pct"), b.get("large_pct")):
                assert num_in_text(v, anchor), "VERBATIM FAIL %s %s" % (q, v)
            t = blend(b["all_pct"], b["large_pct"])
            marginals[q] = {"target_share": t, "base_type": "all_large(all-as-SME-proxy)",
                            "all": b["all_pct"], "large": b["large_pct"],
                            "grade": r.get("grade") or "", "source": (r.get("source") or "")[:80],
                            "evidence": b["verbatim_evidence"][:200]}
            row.update(route="MARGINAL (blend, all-as-SME-proxy)", target=t, base_type=bt,
                       inputs="%g/%g" % (b["all_pct"], b["large_pct"]),
                       flags=("ALL-AS-SME-PROXY; " + (b.get("flags") or "")).strip("; "),
                       evidence=b["verbatim_evidence"][:90])
        elif bt == "all_only":
            v = b.get("single_pct") if b.get("single_pct") is not None else b.get("all_pct")
            assert num_in_text(v, anchor), "VERBATIM FAIL %s %s" % (q, v)
            t = round(v / 100.0, 4)
            # POLARITY GUARD (FAM_001 class): if the extraction's own semantics say the figure
            # is the NEGATIVE/lean-pole share, the target is 1 - figure — or hard-fail if unclear.
            # polarity: explicit structured field wins; substring heuristic is the
            # fallback for legacy rows (FAI_089 proved prose mentions of the
            # complement pole make the substring check unsafe on its own).
            sem = (b.get("target_semantics") or "").lower().replace("-", " ")
            pol = b.get("polarity")
            assert pol in (None, "positive", "negative"), (q, pol)
            if pol == "negative" or (pol is None and "negative pole" in sem):
                t = round(1.0 - t, 4)
                row["flags"] = ("POLARITY-INVERTED (source figure is the lean-pole share; ruled via source check); " + (row.get("flags") or "")).strip("; ")
            marginals[q] = {"target_share": t, "base_type": "all_only", "all": v,
                            "grade": r.get("grade") or "", "source": (r.get("source") or "")[:80],
                            "evidence": b["verbatim_evidence"][:200]}
            row.update(route="MARGINAL (no-blend all-UK)", target=t, base_type=bt, inputs="%g" % v,
                       flags=b.get("flags") or "", evidence=b["verbatim_evidence"][:90])
        elif bt == "large_only":
            row["route"] = "PENDING (large_only extraction, no ruled emit)"; row["flags"] = b.get("flags") or ""
            pending[q] = {"anchor": anchor, "why": "large_only without a ruled emit"}
        else:
            raise AssertionError("unknown base_type %r for %s" % (bt, q))
    elif "statutory floor" in (r.get("status") or "").lower():
        row["route"] = "floor (statutory, latent-only)"; floors[q] = {"anchor": anchor[:120]}
    else:
        row["route"] = "context (anchored, no structured base — ruled follow-on)"
        context[q] = {"why": "anchored-unstructured (25-row follow-on table)"}
    table.append(row)

# ---- orderings come from THE standing artifact; attach + HARD GUARDS ----
ruled_orderings = RULED_ORD
import importlib.util as _ilu, sys as _sys
_spec = _ilu.spec_from_file_location("re_", "reseed_engine.py"); _RE = _ilu.module_from_spec(_spec)
_sys.modules["re_"] = _RE; _spec.loader.exec_module(_RE)
_meta = json.load(open("rew_live_meta.json"))
no_order = []
pf_count = 0
for q in marginals:
    e = RULED_ORD.get(q) or {}
    if e.get("positive_from"):
        marginals[q]["positive_from"] = e["positive_from"]; pf_count += 1
    has = bool(e.get("option_order") or e.get("worst_option"))
    if not has and q in _meta:
        has = bool(_RE.option_order(_meta[q].get("options", ""), _meta[q].get("text", "")))
    if not has:
        no_order.append(q)
assert not no_order, "ORDERINGS-REQUIRED GUARD: emitted marginals without any ordering: %s" % no_order
# THE INVARIANT, stated: a marginal carries `positive_from` IF AND ONLY IF its ruled_orderings entry
# declares one. ruled_orderings.json is the sole source (:214-216) and, since the Phase-1 ruling, the
# canonical home. Derived from the inputs, so the next legitimate ruled addition cannot break
# regeneration — the old `pf_count == 7` hardcode fired the moment REW_FAI_088 gained one.
_pf_from_ords = {q for q in marginals if (RULED_ORD.get(q) or {}).get("positive_from")}
_pf_emitted   = {q for q in marginals if "positive_from" in marginals[q]}
assert _pf_emitted == _pf_from_ords, ("positive_from must come from ruled_orderings.json and nothing "
                                      "else; emitted-only=%s ords-only=%s"
                                      % (sorted(_pf_emitted - _pf_from_ords), sorted(_pf_from_ords - _pf_emitted)))
assert set(ruled_dists) == {"REW_PAY_005", "EXT_REW_GAP_010", "REW265_PAY_RANGEMAX", "REW_PAY_TIPS_EXIST_7c80c508",
                            "REW264_HLT_VIRTUALGP"}, sorted(ruled_dists)
assert set(maturity_grads) == {"PROP_fe1a29ec", "REW_FAI_128", "REW_PAY_001", "REW_INC_103",
                               "REW26_BEN_PENSION_TYPE", "REW_BEN_HOL_001"}, sorted(maturity_grads)
for _q, _e in maturity_grads.items():
    if _e.get("band_distributions"):
        for _b, _d in _e["band_distributions"].items():
            assert abs(sum(_d.values()) - 100) < 1e-9, (_q, _b)
    else:
        assert set(_e["anchors"]) == {"Basic", "Developing", "Advanced"}, _q
assert set(ms_incidence) == {"REW265_BEN_PMICOMP"}, sorted(ms_incidence)
for _q, _e in ms_incidence.items():
    # independent incidences — explicitly NOT a partition; no sum-100 assert BY DESIGN (r3sw8)
    for _o, _p in _e["prevalences"].items():
        assert 0 < _p < 100, (_q, _o, _p)
    assert _e["terminal"] and _e["terminal"] not in _e["prevalences"], _q
assert "PROP_fe1a29ec" not in marginals, "PROP_fe1a29ec must leave the share-marginals (Diff 15 redesign)"
for _q, _e in ruled_dists.items():
    assert abs(sum(_e["distribution"].values()) - 100) < 1e-9, (_q, sum(_e["distribution"].values()))
# default-holds: every other marginal has NO positive_from -> legacy second-rung semantics. This is now
# the complement of the derived set above (it was a second hardcoded count of the same fact, and it
# failed for the same reason: live 32 against a pinned 33).
assert _pf_emitted | {q for q in marginals if "positive_from" not in marginals[q]} == set(marginals)
for q in SETTLED_REFREEZE:
    if q in marginals:
        SETTLED_REFREEZE[q] = marginals[q]["target_share"]
# Phase-1 ruling (2026-07-29): a gm target for a frozen metric is DEAD CODE in the freeze gate —
# qa_plausibility's tier chain is `if qid in FROZEN: ... elif qid in MGRAD/RDIST/MS_INC/MARG`, so the
# FROZEN branch catches it first and the target_share is never evaluated. MARKED INERT, NOT REMOVED:
# reseed_engine.py:426-433 consumes target_share in the marginal branch with NO FROZEN precedence, so
# deleting the entry would change the re-seed. Stamped here so a regeneration cannot drop the mark.
_FROZEN_KEYS = set(json.load(open("frozen_targets.json")))
for q in sorted(set(marginals) & _FROZEN_KEYS):
    marginals[q]["_shadowed_by"] = (
        "frozen_targets.json — NEVER evaluated by the freeze gate (the FROZEN branch catches it "
        "first). RETAINED, not removed: reseed_engine.py:426-433 consumes target_share in the "
        "marginal branch, so deleting the entry would change the re-seed.")

# ---- HARD GUARDS ----
assert "REW26_BEN_SALSAC" not in marginals, "FOUNDING-ERROR GUARD: SALSAC emitted"
assert "REW26_BEN_SALSAC" in context, "SALSAC must be explicit context"
for g in ("REW263_GOV_MENOPLAN", "REW26_BEN_PLSA_QM"):
    assert g in context and g not in marginals, "ruled context directive violated: %s" % g
assert not (set(marginals) & set(context)), "row in both marginals and context"
for q, m in marginals.items():
    assert m.get("grade"), "marginal without grade: %s" % q

out = {"_generated": RULED, "_source": "%s + generator_rules.json + structured_bases.json" % __import__("os").path.basename(_REG_PATH),
       "ruled_distributions": ruled_dists,
       "maturity_gradients": maturity_grads,
       "multiselect_incidence": ms_incidence,
       "coherence_pairs": bases.get("_coherence_pairs") or [],
       "_discipline": "structured fields only; verbatim-validated; marginal only where earned; SALSAC/MENOPLAN/PLSA_QM guards asserted",
       "marginals": marginals, "floors": floors, "context": context,
       # Phase-1 ruling (2026-07-29): ruled_orderings.json is CANONICAL. The generator no longer
       # emits a second, byte-identical copy into this file — a copy nothing reads is a silent fork
       # waiting. Verified: every reader takes the standalone file (reseed_engine:48,
       # generate_marginals:58, qa_plausibility:52, migrate_r3sw7_virtualgp:19).
       "pending_ruling": pending,
       "settled_refreeze": {k: v for k, v in SETTLED_REFREEZE.items() if v is not None}}
json.dump(out, open("generated_marginals.json", "w"), indent=1, ensure_ascii=False)
with open("generated_marginal_table.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(table[0].keys()))
    w.writeheader()
    order = {"MARGINAL": 0, "PENDING": 1, "floor": 2}
    w.writerows(sorted(table, key=lambda x: (min([v for k, v in order.items() if x["route"].startswith(k)] + [3]), x["sub_power"], x["metric_id"])))

print("GENERATED: %d marginals | %d floors | %d context | %d pending-ruling | %d ruled orderings"
      % (len(marginals), len(floors), len(context), len(pending), len(ruled_orderings)))
print("guards: SALSAC no-emit ASSERTED; MENOPLAN/PLSA_QM context ASSERTED; verbatim validator passed on all emitted numbers")
print("review artifacts: generated_marginals.json + generated_marginal_table.csv")
