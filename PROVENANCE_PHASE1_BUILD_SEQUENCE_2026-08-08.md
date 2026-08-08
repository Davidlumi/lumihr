# Provenance surfacing — Phase 1 build sequence (drafted 2026-08-08)

Drafted by Claude against R-P1..R-P10 (ruled 2026-08-08) and the Phase 0
diagnostic. **Nothing below is operative unless the approval line is present:**

```
APPROVED_BY_DAVID = ____________________   # date + "all" or a list of diff ids
```

If blank: stop and say so. A build sequence is not an authorisation.

Standing conditions: every lettered diff is its own commit and DECISIONS entry;
derive don't hardcode; state which case obtains with counts where a check could
pass vacuously; rehearse writes on a throwaway; suite green between diffs.
R-P10 already shipped (`f1a8a72`) and is not re-opened here.

---

## Diff P1-A — the partition, structural (R-P5's seam first)

The floor moves INSIDE `aggregate_question_for_orgs`: the function floors
against the org set it was handed, and the seven external comparison sites
become consumers of blocks that arrive already-floored. Add `real_org_ids(conn)`
as THE one partition helper (rule: `source NOT IN ('seed','staff','demo') AND
submission_complete=1` — 'demo' included ahead of P1-E so the rule never needs a
second edit). No behaviour change yet at real n = 0 — this diff is the seam.
Gate: extend qa_engine_audit with a subset-floor check (a 4-org subset must
suppress regardless of total n).

## Diff P1-B — n_real beside n, same pass (R-P2's data)

`aggregate_question_for_orgs` computes `n_real` per block from the intersection
with `real_org_ids` (measured cost: one set intersection × 15,260 blocks,
~+4.6% payload). Every block gains `n_real`; matrix rows and presence blocks
included. Freeze-gate note: payload shape changes — qa_plausibility compares
values not shapes, but qa_domain_summary's 143 checks and qa_hero must be run
and any shape assertions updated honestly (report which, with counts).

## Diff P1-C — the composition chip (R-P1/R-P2/R-P3/R-P4)

One shared renderer (`compositionLabel(n, n_real)`) with the ruled progression:
real 0 → "N · reference panel"; mixed → "N · R members + panel"; all real →
"N members". First use per surface carries the R-P1 description (tooltip/aria on
chips; prose on pages). Applied at every render site from the Phase 0 census:
card chip + aria + sentences (card.js:112/84/287/350), exported chart footer
(charts.js:574 — the label is baked into shared pixels), board-pack ruler subs +
CSV columns (app.py:3318/3052/3070 — CSV gains n_real column), share views
(app.py:3415), signals/briefing n cites (pages.js:1483/2044), practice rows,
digest bodies (notifications.py — "against your peers" phrasing keys off
composition), print header (replaces R-P10's static label). Panel-only cuts
render labelled, never suppressed (R-P3); no new threshold anywhere (R-P4);
ConfidenceChip untouched (R-P9).

## Diff P1-D — the AI three-part fix (R-P7, all or none; unblocks R8)

(a) `build_commentary_payload` + pack payload carry `n_real` + composition
label; (b) the prompt templates stop teaching "All peers, n=140" — the taught
register becomes composition-carrying; (c) `validate_commentary` (and the pack
validator) REJECT outputs describing the pool as employers/peers/organisations-
reporting where the payload's real n = 0 — with a deterministic-fallback path
that is itself composition-correct. qa_commentary extended: a real-n=0 payload
whose draft says "peers report" must be rejected (non-vacuous: assert the
rejection fires, not just that good output passes).

## Diff P1-E — source='demo' (R-P8)

Console provisioning form gains the explicit class choice (member | demo);
`_insert_member_org` takes the class; 'demo' excluded from the partition (P1-A
already wrote the rule), from lifecycle (renders as provenance like seed/staff),
and from real-contributor counts. qa_backoffice: provisioning a demo org must
not move any real-n; B3's derived floor unaffected (demo orgs are outside the
expected-world set by construction — state which case obtains).

## Diff P1-F — the signal composition-epoch seam (R-P6, seam only)

`signal_state` gains `composition_epoch`; the sweep rebaselines (record_baseline
idiom, app.py:2300) instead of diffing when an org's stored epoch differs from
the current one. The epoch value only ever changes when a future taper diff
changes composition — at launch it is constant, so behaviour is unchanged
(stated, not assumed: the sweep's event counts before/after must be identical on
the throwaway). The taper MECHANISM stays deferred per the ruling.

## Ordering and gates

A → B → C → D → E → F. A/B are engine diffs (full suite after each); C is
web+server surface (suite + browser verification of each census site); D gates
R8; E before any console demo provisioning; F closes the ruled seam. After F:
the checklist's R8 entry flips from "blocked on R-P7" to "blocked on David's
production flip only".

## Not in this sequence

The taper mechanism (R-P6 deferred). Any change to verdict vocabulary. Any
member-only statistic surface (R-P5 floors them structurally; building one is
its own future decision). The deploy/D2/solicitor/AI-flip items — unchanged.
