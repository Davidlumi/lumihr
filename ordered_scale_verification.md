# Ordered-scale verification — RESULTS (the backwards-firing check)

Verified all 55 ordered-scale metrics against their actual option order + polarity.
**This check caught signals that would have fired backwards. Do not skip.**

## Re-split (the set is NOT uniform)
- **30 → behind-percentile.** polarity=higher_is_better, options run worst→best. Safe: "you're behind peers" is a true read. Build as-is on existing behind logic.
- **22 → ordered-OUTLIER (NEW treatment).** polarity=neutral — there is NO better end. Firing these as "behind" invents a verdict. They must fire at **both tails** ("you sit at the high/low end vs peers") and carry **no verdict** — the user judges if their end is good/bad. e.g. life-cover multiple, market position, bonus split, pension %, IP terms, bank-holiday premium, the %-band metrics.
- **3 → ANCHOR-DIRECTION RISK. BLOCK until fixed.** Option order is descending or the "good" end is position 1, inconsistent with the rest of the set. If the engine assumes index-ascending = better, these fire backwards (a generous org reads as 'behind'):
  - REW_Q049530 (car mileage: 11k+ listed first, but a LOW bar is the generous end)
  - REW_PAY_003 / PROP_8e0b6316 (review frequency: Quarterly listed first = most frequent = 'best', opposite anchor to the worst→best metrics)

## Build requirement this surfaces
Every ordered metric needs an **explicit direction anchor** in config — do not infer rank direction
from option array position. Store, per metric: `direction = higher_is_better | lower_is_better | neutral_outlier`.
qa_hero assertion: no behind signal fires on a polarity=neutral metric; the 3 anchor-risk IDs have an
explicit lower_is_better/direction set before they can fire.
