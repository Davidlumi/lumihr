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

This is a RATCHET: the three faults known today are allow-listed with their
reason + fix owner (David). The gate FAILS on any NEW backwards ladder, and also
flags a stale allow-list entry once its metric is fixed (so the debt list can't
rot). Pure library/aggregate — no server needed.

Scope: reward, active, scored single_select / yes_no (the choice metrics the
signal system's ordered mechanisms read). Banded-numeric ladders carry no
affirmative/negative language and are governed by polarity, not this check.
"""
import sys
from library import load_questions
from aggregate import score_answer, _AFF, _NEG

# Known backwards ladders — each is a DATA fix David owns. Re-add to the relevant
# lens map only after the fix. The gate asserts each still actually violates, so
# fixing the data forces the entry to be removed (no silent rot).
KNOWN_BACKWARDS = {
    "REW_BEN_SICK_001": "non-monotonic option order: 'Statutory sick pay only' scores above "
                        "'Enhanced'/'Combination'. Held from position_lenses (Phase 1). "
                        "FIX: reorder options worst->best (none < statutory < enhanced < combination).",
    "REW_FAI_079": "polarity=lower_is_better is wrong — conducting gender pay gap ANALYSIS is good. "
                   "'Yes' scores 0. Prevalence signal is unaffected (practice_status is label-based), "
                   "but the card percentile/maturity read backwards. FIX: polarity -> higher_is_better.",
    "REW_INC_070": "polarity=lower_is_better is wrong — malus provisions are a governance control. "
                   "'Yes' scores 0. Same blast radius as REW_FAI_079. FIX: polarity -> higher_is_better.",
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

    print("\n  KNOWN backwards ladders (pending David's data fix):")
    for qid, why in KNOWN_BACKWARDS.items():
        print("    - %s: %s" % (qid, why))

    print("\n== SCORE-LADDER GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
