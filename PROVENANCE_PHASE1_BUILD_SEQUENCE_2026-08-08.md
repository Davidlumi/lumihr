# Provenance surfacing — Phase 1 build sequence (drafted 2026-08-08)

Drafted by Claude against R-P1..R-P10 (ruled 2026-08-08) and the Phase 0
diagnostic. **Nothing below is operative unless the approval line is present:**

```
APPROVED_BY_DAVID = 2026-08-08 — approved AGAINST THE AMENDED SEQUENCE ONLY
                    (amendment of 2026-08-08: Commit 0; ordering P1-AB -> P1-F
                    -> P1-C -> P1-D -> P1-E). The original ordering was never
                    authorised.
```

Standing conditions: every lettered diff is its own commit and DECISIONS entry;
derive don't hardcode; state which case obtains with counts where a check could
pass vacuously; rehearse writes on a throwaway; suite green between diffs.
R-P10 already shipped (`f1a8a72`) and is not re-opened here.

---

## Diff P1-AB — composition enters the engine (R-P5 + n_real, ONE diff — amended)

**Why merged (amendment 0.2, recorded so nobody later splits them back on
diff-size grounds):** A and B are one fix class — composition entering the
engine — not two. Same function, same loop, same 15,260 n-blocks. Split, the
floor half becomes subset-aware while no caller passes a subset, so its only
available verification is STRUCTURAL — reading the code and agreeing with it,
the proof family this programme has learned to distrust (nine failures on
record). Merged, the verification is an EXERCISE: hand the function a filtered
org set and watch the floor bite.

Content: `real_org_ids(conn)` as THE one partition helper (`source NOT IN
('seed','staff','demo') AND submission_complete=1` — 'demo' from the start so
the rule is never edited twice); `aggregate_question_for_orgs` computes
`n_real` per block (intersection with the real set, same pass) and its floor
is proven subset-safe against the org set it was handed.

**Compensating rehearsal (amendment 0.4) — the merged diff gets a STRONGER
rehearsal, not a smaller diff.** On the throwaway, before any live write:
compare ALL 15,260 n-scalars across ALL 344 payloads before/after; assert `n`
byte-identical everywhere (`n_real` purely additive); a single moved total-n is
a STOP-and-report finding, wanted before the write; exercise the subset path
explicitly — a filtered org set below the floor must be suppressed by the
mechanism itself, fail-closed, not by a caller remembering to check.

## Diff P1-F — the signal composition-epoch seam (R-P6, seam only — SECOND, amended)

**Why second (amendment 0.3):** the marker must exist before `n_real` moves any
served figure — not before the taper ships. The nightly sweep diffs signal sets
recomputed from current served payloads with no composition awareness; the
moment a payload shifts for a composition reason, the digest mails "moved
against your peers". Today that reaches nobody — which is precisely why the
marker is free now and an incident after first provisioning. Ordering, not
content, is the whole point of the move.

`signal_state` gains `composition_epoch`; the sweep rebaselines (record_baseline
idiom, app.py:2300) instead of diffing when an org's stored epoch differs from
the current one. The epoch value only ever changes when a future taper diff
changes composition — at launch it is constant, so behaviour is unchanged
(stated, not assumed: the sweep's event counts before/after must be identical on
the throwaway). The taper MECHANISM stays deferred per the ruling.


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

**Exit criterion (amendment 0.5): not "the sites were updated" — "NO SITE WAS
MISSED."** Twenty-three emission and render points from the census, plus the
board-pack CSV, plus the chart image with n baked into the pixels, plus the
digest subject line. Closed by a SEARCH AGAINST LIVE proving no n reaches any
surface without composition beside it — never a list of the sites changed. The
Commit-E discipline: assert against the world, not this commit's claims.

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
`_insert_member_org` takes the class; 'demo' excluded from the partition (P1-AB
already wrote the rule), from lifecycle (renders as provenance like seed/staff),
and from real-contributor counts. qa_backoffice: provisioning a demo org must
not move any real-n; B3's derived floor unaffected (demo orgs are outside the
expected-world set by construction — state which case obtains).

## Ordering and gates

**RULED ORDERING (amendment 0.1): P1-AB → P1-F → P1-C → P1-D → P1-E.**
AB and F are engine diffs (full suite after each; F proves sweep event counts
identical before/after on the throwaway since the epoch is constant at launch);
C is web+server surface closed by search-against-live; D gates R8; E stays last
and genuinely independent (its only timing constraint is the first
console-provisioned demo org, which has not happened). After D: the checklist's
R8 entry flips from "blocked on R-P7" to "blocked on David's production flip
only".

## Not in this sequence

The taper mechanism (R-P6 deferred). Any change to verdict vocabulary. Any
member-only statistic surface (R-P5 floors them structurally; building one is
its own future decision). The deploy/D2/solicitor/AI-flip items — unchanged.
