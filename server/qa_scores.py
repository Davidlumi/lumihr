# -*- coding: utf-8 -*-
"""QA — score-ladder integrity (the durable guard from the sick-pay catch).

The engine derives a maturity score per option and a direction (score_direction)
from the option labels + polarity. A metric only scores correctly if its option
array is ordered consistently with that direction. When it isn't, a clearly-bad
answer can outscore a clearly-good one and any signal reading that ladder fires
BACKWARDS — silently. REW_BEN_SICK_001 was the first catch; this gate makes the
whole fault class loud.

FAULT SIGNATURE (automatable, uses the SAME _AFF/_NEG regexes the engine trusts):
  within one scored choice metric, a clearly-negative option (No / None / Not /
  "statutory only" / absence) receives a HIGHER direction-corrected score than a
  clearly-affirmative one (Yes / Enhanced / "within last" / …).

This is a RATCHET: the allow-list has been EMPTY since the AFF Tier-1 map diff
(2026-07-26 — the three historical faults were retired WITH their fixes; texts
preserved in _RETIRED_2026_07_26). The gate FAILS on any NEW backwards ladder,
flags a stale allow-list entry once its metric is fixed (so a debt list can't
rot), and — since the engine+gate diff (2026-07-27) — asserts the HEURISTIC
CENSUS: authored direction is law, and the label regex may decide direction for
exactly the ruled Tier-2 exception list and nothing else. Pure library/aggregate
— no server needed.

Scope: reward, active, scored single_select / yes_no (the choice metrics the
signal system's ordered mechanisms read). Banded-numeric ladders carry no
affirmative/negative language and are governed by polarity, not this check.
"""
import sys
from library import load_questions
from aggregate import score_answer, score_polarity, direction_source, _mp_class, _AFF, _NEG

# THE RULED HEURISTIC EXCEPTION LIST — EMPTY since the Tier-2 apply (David-ruled
# 2026-07-27, the joint pass: 13 PRACTICE re-routes + 5 CONFIRM pins + 1 AMEND +
# PAY_097 recorded): THE LABEL HEURISTIC IS RETIRED. No verdict-relevant metric may
# have its direction decided by the regex, ever; the census check below asserts zero
# unconditionally. Scope = where authority RENDERS (mp class not in Practice/Design,
# mirroring positions.py market routing — David's ruling: "Practice metrics leave the
# scored-select census"); Practice-scope selects that still resolve via the regex are
# rendering-inert and printed informationally, never tolerated silently.
RULED_HEURISTIC_HOLD = set()

# Known backwards ladders — each is a DATA fix David owns. Re-add to the relevant
# lens map only after the fix. The gate asserts each still actually violates, so
# fixing the data forces the entry to be removed (no silent rot).
KNOWN_BACKWARDS = {
    # EMPTY since the AFF Tier-1 map diff (David-ruled 2026-07-26): all three long-standing
    # entries RETIRED with their fixes — REW_BEN_SICK_001 + REW_FAI_079 corrected in Tier 1A,
    # REW_INC_070 corrected as the Tier-3 rider. The ratchet's purpose is temporary tolerance,
    # not permanent exception; any NEW backwards ladder fails check 1 (unexpected), as designed.
}
_RETIRED_2026_07_26 = {
    "REW_BEN_SICK_001": "non-monotonic option order: 'Statutory sick pay only' scores above "
                        "'Enhanced'/'Combination'. Held from position_lenses (Phase 1). "
                        "FIX: reorder options worst->best (none < statutory < enhanced < combination).",
    "REW_FAI_079": "polarity is higher_is_better and the authored map is YES:100/NO:50/IN_DEV:0 "
                   "(the old 'polarity=lower_is_better' note was stale — corrected 2026-07-25), but the "
                   "_AFF direction heuristic sees 'Yes' first-in-order and INVERTS: effective Yes 0 / "
                   "No 50 / In development 100 — the ladder still reads backwards. Prevalence signal "
                   "unaffected (practice_status is label-based); card percentile/maturity read backwards. "
                   "FIX pending David's queued _AFF-ladder audit: reconcile authored map with the heuristic.",
    "REW_INC_070": "polarity is NEUTRAL (already neutral pre-Diff-18; the old 'polarity=lower_is_better' "
                   "note was stale — corrected 2026-07-25), authored map YES:100/NO:0, but the _AFF "
                   "heuristic sees 'Yes' first and INVERTS: effective Yes 0 / No 100. Same _AFF pattern "
                   "as REW_FAI_079; FIX pending the same queued audit.",
}
# Verified best->worst orderings (good option at index 0) — must resolve via the
# direction heuristic, NOT trip the guard. Asserted explicitly per the brief.
MUST_PASS = ["PROP_cdff5737", "PROP_d65a16e9", "PROP_34ffb6e2", "PROP_8e0b6316"]

PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + str(detail)[:140] + "]") if detail else ""))


def violation(q):
    """Return the offending (neg_label, neg_score, aff_label, aff_score) or None."""
    aff, neg = [], []
    for o in sorted(q.options or [], key=lambda o: o.get("order", 0)):
        s = score_answer(q, o["label"])
        if s is None:
            continue
        if _AFF.search(o["label"]):
            aff.append((o["label"], s))
        elif _NEG.search(o["label"]):
            neg.append((o["label"], s))
    if aff and neg:
        worst_aff = min(aff, key=lambda x: x[1])
        best_neg = max(neg, key=lambda x: x[1])
        if best_neg[1] > worst_aff[1]:
            return (best_neg[0], best_neg[1], worst_aff[0], worst_aff[1])
    return None


def main():
    qs = load_questions()
    metrics = [q for q in qs.values() if q.superpower == "Reward" and q.status == "active"
               and q.type in ("single_select", "yes_no") and q.is_scored]
    print("score-ladder integrity — %d reward scored choice metrics\n" % len(metrics))

    found = {}
    for q in metrics:
        v = violation(q)
        if v:
            found[q.id] = v

    # 1) every backwards ladder must be a KNOWN, documented fault
    unexpected = sorted(set(found) - set(KNOWN_BACKWARDS))
    for qid in unexpected:
        v = found[qid]
        print("  -> NEW backwards ladder %s: %r(%.0f) outscores %r(%.0f)" % (qid, v[0], v[1], v[2], v[3]))
    check("no NEW backwards score ladders (a NEG option outscoring an AFF option)",
          not unexpected, unexpected)

    # 2) every allow-listed fault must still actually violate (else fixed -> remove it)
    stale = [qid for qid in KNOWN_BACKWARDS if qid not in found]
    check("allow-list is not stale (each known fault still violates; fixed ones must be removed)",
          not stale, ["%s appears FIXED — remove from KNOWN_BACKWARDS" % s for s in stale])

    # 3) the verified best->worst metrics must NOT trip the guard
    tripped = [qid for qid in MUST_PASS if qid in qs and violation(qs[qid])]
    check("verified best->worst metrics resolve correctly (PROP_cdff5737/d65a16e9/34ffb6e2/8e0b6316)",
          not tripped, tripped)

    # 4) HEURISTIC CENSUS (engine+gate diff 2026-07-27; RETIRED at the Tier-2 apply):
    # in the VERDICT scope (mp class not Practice/Design — where direction renders),
    # ZERO metrics may have their direction decided by the label regex. The exception
    # list is empty and stays empty; any flagged metric is a defect. Practice-scope
    # label-resolved selects are rendering-inert — printed, never gated.
    flagged = sorted(q.id for q in metrics
                     if _mp_class(q.id) not in ("Practice", "Design")
                     and direction_source(q) == "label_heuristic")
    check("THE RETIREMENT HOLDS: zero verdict-scope metrics heuristic-scored (ruled list EMPTY)",
          set(flagged) == RULED_HEURISTIC_HOLD,
          {"unruled_flagged": sorted(set(flagged) - RULED_HEURISTIC_HOLD),
           "ruled_but_not_flagged": sorted(RULED_HEURISTIC_HOLD - set(flagged))})
    inert = sorted(q.id for q in metrics
                   if _mp_class(q.id) in ("Practice", "Design")
                   and direction_source(q) == "label_heuristic")
    if inert:
        print("    (practice-scope, rendering-inert, label-resolved: %d — %s)" % (len(inert), ", ".join(inert)))

    # 5) THE PRACTICE SHIELD (David-ruled 2026-07-28, the retro-sweep invariant made permanent):
    # no Practice/Design-class metric may carry LIVE directionality, ever — the class that
    # produced CAR_STATUS_01, INC_070 and MERITMATRIX is structurally impossible. NO EXCEPTION
    # MECHANISM: a Practice metric with live directionality is always a defect; any future
    # ruling that needs one amends this gate explicitly. Derivation is LIVE each run (the
    # retro-census logic, never a hardcoded list), mirroring positions._item exactly:
    #   score stream    — pol = score_polarity(q), unbenchmarked flag -> neutral
    #                     (fires on the INC_070 absent-key case and the CAR_STATUS_01 case);
    #   practice/value  — pol = questions.polarity, flag -> neutral, multi_select excluded
    #                     (qa_hero: multi_select never produces a practice position)
    #                     (fires on the MERITMATRIX case).
    # Dormant directional residue (flag-shielded / is_scored=0 / multi) is PRINTED every run,
    # never silently tolerated — it fires the moment any config change makes it live.
    import os as _o, json as _j
    _mp_path = _o.environ.get("LUMI_MP_CONFIG") or _o.path.join(
        _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))), "data", "market_position_config.json")
    _mpm = _j.load(open(_mp_path)).get("metrics", {})
    shield_violations, dormant = [], []
    for q in qs.values():
        if q.status != "active" or _mp_class(q.id) not in ("Practice", "Design"):
            continue
        unbench = bool((_mpm.get(q.id) or {}).get("unbenchmarked"))
        sp = score_polarity(q) if q.is_scored else "neutral"
        if q.is_scored and sp != "neutral":
            (dormant if unbench else shield_violations).append(
                "%s: score-stream LIVE directionality (score_polarity=%s; scoring_config polarity=%r, direction=%r)%s"
                % (q.id, sp, (q.scoring_config or {}).get("polarity"), (q.scoring_config or {}).get("direction"),
                   " [flag-shielded]" if unbench else ""))
        if q.polarity in ("higher_is_better", "lower_is_better") and q.type != "multi_select":
            (dormant if unbench else shield_violations).append(
                "%s: practice/value-stream LIVE directionality (questions.polarity=%s)%s"
                % (q.id, q.polarity, " [flag-shielded]" if unbench else ""))
        elif q.polarity in ("higher_is_better", "lower_is_better") or \
                (q.is_scored and sp == "neutral" and (q.scoring_config or {}).get("polarity")
                 not in (None, "neutral")) or \
                (not q.is_scored and (q.scoring_config or {}).get("polarity") not in (None, "neutral")):
            dormant.append("%s: dormant directional field (db=%s cfg=%r type=%s is_scored=%s)"
                           % (q.id, q.polarity, (q.scoring_config or {}).get("polarity"), q.type, q.is_scored))
    check("PRACTICE SHIELD: no Practice/Design metric carries live directionality (no exceptions)",
          not shield_violations, shield_violations)
    if dormant:
        print("    (dormant directional residue, non-failing — fires the moment it goes live: %s)"
              % "; ".join(sorted(dormant)))

    if KNOWN_BACKWARDS:
        print("\n  KNOWN backwards ladders (pending David's data fix):")
        for qid, why in KNOWN_BACKWARDS.items():
            print("    - %s: %s" % (qid, why))
    else:
        print("\n  KNOWN backwards ladders: NONE — allow-list emptied 2026-07-26 (all three retired with their fixes)")

    print("\n== SCORE-LADDER GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
