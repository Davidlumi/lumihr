#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIFF 1 (register clean) — ruled 2026-07-16. Applies David's approved dispositions to
lumi_anchor_register_CLAUDECODE.csv: 19 rows clear to EST, 6 rows receive re-homed/relabelled
anchors, everything else asserted byte-identical. Registers are the ruled-authoritative source
the diff-2 generator will read; the spike file is superseded and dies at diff 2.
Rulings: 10 duplicate-clears (block-approved); PENSION_TYPE->PLSA_QM upper-bound proxy A->B;
MERITMATRIX->PAY_097; PAY_018->PAY_017; HOL_006 quantum-companion appended at HOL_004;
FAM_012 CIPD policy figure -> MENOPLAN as Grade-C proxy, GENERATOR CONTEXT-ONLY (Aon parks);
WEL_FINWELL relabel-not-rehome; 4 PARKs -> parked_anchors.md. No DB writes anywhere.
Run: python3 register_clean_diff1.py            (DRY: prints the ledger)
     python3 register_clean_diff1.py --write --confirmed-by-david
"""
import csv, io, shutil, sys

REG = "lumi_anchor_register_CLAUDECODE.csv"
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
RULED = "ruled 2026-07-16"

# 19 clears -> the register's own EST convention (113-row dominant form)
CLEARS = [
    # 10 duplicate-clears (figure already lives at home, same numbers/source)
    "REW_BEN_039", "REW_BEN_100", "REW_BEN_102", "REW263_BEN_PMIMH", "REW_BEN_139",
    "RED_NOTICE_01", "REW_BEN_055", "REW262_TIME_SICKDAYONE", "EXT_REW_GAP_010", "REW_INC_132",
    # movers' origins
    "REW26_BEN_PENSION_TYPE", "REW263_PAY_MERITMATRIX", "REW_PAY_018", "REW_BEN_HOL_006",
    "REW_BEN_FAM_012",
    # parks + audit-self-corrected composite
    "REW_BEN_SICK_005", "REW_BEN_FAM_005", "REW263_PAY_SSPALIGN", "PROP_8862fcad",
]

# receiving/edited rows: metric_id -> {field: new_value}; APPEND uses '+| ' prefix
RECEIVE = {
    "REW26_BEN_PLSA_QM": {
        "real_anchor": ("UPPER-BOUND PROXY (re-homed from REW26_BEN_PENSION_TYPE, %s): min employer "
            "contribution >=6%%: 29%% all / 47%% large / 28%% SME (CIPD Reward Feb 2026). CAVEAT: >=6%% "
            "employer is necessary but NOT sufficient for PQM (also requires 12%% total), so true PQM "
            "prevalence <=29%% all-UK — upper bound, not exact anchor. GENERATOR: bound-only -> context "
            "unless David rules to seed at the bound. NB 47%% (Fig24) vs 48%% (REW_BEN_038 table) "
            "transcription discrepancy to reconcile against the source PDF." % RULED),
        "grade": "B", "status": "ANCHORED (proxy, upper bound)",
    },
    "REW_PAY_097": {
        "real_anchor": ("Merit pay (permanent rises from individual performance assessment): 41%% of "
            "employers for MPT staff, 29%% other staff (private sector 48%%/33%%), CIPD PPT 2024. "
            "(Re-homed from REW263_PAY_MERITMATRIX, %s; the broader '60%% link pay/bonus to performance' "
            "clause is caveated context only, not an anchor.)" % RULED),
        "grade": "B", "status": "ANCHORED (sourced)", "source": "CIPD Pay, Performance & Transparency 2024",
    },
    "REW_PAY_017": {
        "real_anchor": ("64%% pay a call-out rate (Fixed-rate dominant; legacy detail Yes-Fixed 24 / "
            "Yes-%%hourly 2 / No 15, n=42). SHAPE CAVEAT: measures existence + form of call-out payment "
            "(supports the Per-call-out vs Not-offered axis), NOT the flat-per-period/per-day periodicity "
            "split. Legacy 2019-20 large-employer-skew base. (Re-homed from REW_PAY_018, %s.)" % RULED),
        "grade": "B", "status": "ANCHORED (sourced)",
    },
    "REW_BEN_HOL_004": {
        "real_anchor": ("+| QUANTUM COMPANION (re-homed from REW_BEN_HOL_006, %s): leave rises from "
            "~25 days (1yr) to ~28-29 days (5-15yr); typical service uplift 3-5 days (IDR Payline 2024). "
            "Complementary quantum to the prevalence figure; same source family." % RULED),
    },
    "REW263_GOV_MENOPLAN": {
        "real_anchor": ("PROXY-WITH-CAVEAT (re-homed from REW_BEN_FAM_012, %s): menopause POLICY "
            "prevalence — 24%% standalone / 16%% within wider policy (~40%% any) / 29%% planning "
            "(CIPD 2023). CAVEAT: a policy is NOT an ERA-2025 published action plan and the 2023 data "
            "predates the 2027 mandate. GENERATOR: CONTEXT ONLY, never a marginal (ruled)." % RULED),
        "grade": "C", "status": "ANCHORED (proxy, context-only)",
    },
    "REW26_WEL_FINWELL": {
        "real_anchor": ("64%% offer a financial wellbeing programme/activity (broad any-programme "
            "measure, CIPD S29). RELABELLED %s: previously mislabelled 'have financial wellbeing "
            "policy/strategy'; attachment ruled correct per the standing register reconciliation "
            "(audit mis-map OVERTURNED). Source wave to be tightened to the exact CIPD survey "
            "carrying S29." % RULED),
    },
}
EDIT_COLS = {"real_anchor", "grade", "status", "source", "anchor_source_flag"}

rows = list(csv.DictReader(open(REG, encoding="utf-8-sig")))
cols = list(rows[0].keys())
byid = {r["metric_id"].strip(): r for r in rows}
assert len(rows) == 243 and len(byid) == 243, "register shape moved"
for q in CLEARS + list(RECEIVE):
    assert q in byid, "unknown metric_id in ruling table: %s" % q
assert not (set(CLEARS) & set(RECEIVE)), "a row cannot both clear and receive"

before = {r["metric_id"]: dict(r) for r in rows}
ledger = []
for q in CLEARS:
    r = byid[q]
    old = (r["real_anchor"] or "").strip()
    assert old, "%s already blank — ruling table stale" % q
    r["real_anchor"] = ""; r["grade"] = ""; r["anchor_source_flag"] = ""
    r["status"] = "unanchored - needs research"
    ledger.append((q, "CLEAR->EST", old[:70]))
for q, edits in RECEIVE.items():
    r = byid[q]
    for f, v in edits.items():
        assert f in EDIT_COLS, f
        if v.startswith("+| "):
            r[f] = (r[f] or "").rstrip() + " | " + v[3:]
            ledger.append((q, "APPEND %s" % f, v[3:60]))
        else:
            ledger.append((q, "SET %s" % f, "%r -> %r" % ((before[q][f] or "")[:40], v[:40])))
            r[f] = v

# verify: only intended rows changed, only intended columns
changed = {r["metric_id"]: [c for c in cols if r[c] != before[r["metric_id"]][c]] for r in rows}
changed = {k: v for k, v in changed.items() if v}
intended = set(CLEARS) | set(RECEIVE)
assert set(changed) == intended, "unintended rows changed: %s" % (set(changed) ^ intended)
for q, cs in changed.items():
    bad = set(cs) - EDIT_COLS
    assert not bad, "unintended columns on %s: %s" % (q, bad)

print("DIFF 1 %s — %d rows change (%d clear, %d receive/edit); %d untouched"
      % ("WRITE" if WRITE else "DRY", len(changed), len(CLEARS), len(RECEIVE), 243 - len(changed)))
for q, op, d in ledger:
    print("  %-26s %-18s %s" % (q, op, d))

if WRITE:
    shutil.copy(REG, REG + ".bak_pre_diff1_regclean_20260716")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    open(REG, "w", encoding="utf-8", newline="").write(buf.getvalue())
    # re-read + re-assert
    rr = list(csv.DictReader(open(REG, encoding="utf-8-sig")))
    assert len(rr) == 243
    anchored = sum(1 for x in rr if (x["real_anchor"] or "").strip())
    print("APPLIED. backup: %s.bak_pre_diff1_regclean_20260716 | anchored rows now: %d (was 112: -19 clears, +2 newly anchored, +1 proxy-anchored on an in-substance-EST row)" % (REG, anchored))
