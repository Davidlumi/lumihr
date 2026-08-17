# Phase 1-B — report

**Basis:** `e2beec6` (P1-B) on top of `4db83ce` (P0-7f). Everything below was measured on
a throwaway pair made with the SQLite backup API, never on `lumi.db`.

**Rig recipe, used for every figure in §2 and §5:**

```bash
python3 - <<'PY'
import sqlite3
c=sqlite3.connect("file:/Applications/Lumi Project/lumi.db?mode=ro",uri=True)
o=sqlite3.connect("<scratch>/ai_lumi.db"); c.backup(o); o.close(); c.close()
PY
```

Server: launch config `lumi-throwaway-ai` (:8071, `LUMI_DB=<scratch>/ai_lumi.db`).
BEFORE runs use `git show 4db83ce~1:server/app.py`; AFTER runs use the committed file.
Nothing else differs between the two — same DB copy, same client, same harness.
Renders: `python3 server/verify_report_pdf.py --url http://localhost:8073/harness_full.html`,
payloads captured with **`REBUILD_PLAN` unset**.

Live stored plan behind every render: **`built_at 2026-08-15 14:35:32`**, four actions,
all Benefits & Lifestyle — Flexible benefits allowance (multi-cycle), Salary-sacrifice
arrangements (next cycle), Group risk bundle (next cycle), Voluntary benefits platform
(this cycle). Read read-only from `lumi.db`:

```bash
python3 -c "import sqlite3,json;c=sqlite3.connect('file:/Applications/Lumi Project/lumi.db?mode=ro',uri=True);c.row_factory=sqlite3.Row;print(json.loads(c.execute('SELECT action_plan_json FROM org_strategy WHERE org_id=?',('5e67fa8c-84b2-4be7-9f59-8556bbd6b6e7',)).fetchone()['action_plan_json'])['built_at'])"
```

---

## §2.1 Caveat blast radius, per area

The caveat is the note that follows a signals exhibit when **no shown signal reads the
same way the area does**. Its condition is
`pos.verdict && sigShown.length && !sigShown.some(x => x.position === pos.verdict)`
(`web/js/report.js:1897`).

| area | exhibit before | exhibit after | caveat |
|---|---|---|---|
| Pay | 2 of 5 | 2 of 9 | prints both, **wording identical** |
| Pensions & Savings | 2 of 7 | 2 of 9 | not printed either side |
| Health & Protection | no exhibit | no exhibit | not printed either side |
| Benefits & Lifestyle | 2 of 5 | 2 of 9 | not printed either side |
| Time Off & Family | fold line, 3 | fold line, 9 | not printed either side (zero-room rule) |
| Incentives & Recognition | 2 of 2 | 2 of 4 | not printed either side |
| **Wellbeing** | 1 of 1 | 2 of 5 | **printed before, gone after** |
| Governance & Transparency | 2 of 2 | 2 of 10 | prints both, **wording identical** |

Two areas print it, and in both the wording is byte-identical before and after:

> The signals above are the most material in Pay, which is not the same as the most
> representative: none of them happens to read on market, while the area overall does.
> The split at the top of this page is the fuller picture.

Same sentence for Governance & transparency. Both areas read **on market** while none of
their shown signals does — that is a true statement in both states, and the fix did not
touch it.

**Wellbeing is the one that moved, and it moved the right way.** Before:

> The signal above is the most material in Wellbeing, which is not the same as the most
> representative: it does not read below market, while the area overall does.

Wellbeing's verdict is **below**. Pre-fix its *only* signal was `Wellbeing budget per
employee`, reading **above** — so the document had to print a caveat explaining that its
single piece of evidence contradicted the area's own verdict. Post-fix the area carries
five signals, of which three read **below** (`Employee assistance programme`, `Financial
wellbeing programme`, `Wellbeing strategy`); the shown rows now agree with the verdict
and the caveat correctly stands down.

That caveat was not decoration. It was the document telling the reader, in print, that
the evidence under a heading disagreed with the heading — and it was there because five
of eight signal mechanisms were dark. **S5's "four of eight" claim should be read against
this**: the caveat's disappearance is not lost information, it is a contradiction that no
longer exists.

## §2.2 Stop-and-report confirmation

Compared field by field across all eight areas and at document level, pre- vs post-fix,
on the same DB copy:

**area verdict · percentile · below/at/above split · metric count · polarised count ·
practice count · comparable pool · peer n · strict flag · aim stance · alignment ·
per-area commitment register (id + status) · per-area gaps · per-area option count ·
document commitment register · the ask · counts · money priced · money investment ·
schedule length · risks length · plan identity · plan action titles · pool footer ·
suppression floor · cut label**

> **0 fields moved. CONFIRMED UNCHANGED.**

Signals feed nothing but the signals surface. This is the statement, not the suite
result — the suite would pass whether or not this held.

## §2.3 Signal identity, per area

Payload array (capped at 4 — see §5.1). `signal_count` in brackets.

| area | before | after |
|---|---|---|
| **Pay** (5→9) | Salary increase budget *(below)*; Hourly shift pay multipliers, Evening *(below)*; Total allowance payment, Night premium *(below)*; Hourly shift pay multipliers, Late night *(below)* | Salary increase budget *(below)*; **Utility costs *(differs)* — NEW**; Hourly shift pay multipliers, Evening *(below)*; Total allowance payment, Night premium *(below)* |
| **Pensions & Savings** (7→9) | Employer pension, Board/Exec *(below)*; Typical employer pension rate, Board/Exec *(below)*; Employer pension cost share *(below)*; employee pension contribution, Board/Exec *(differs)* | Employer pension, Board/Exec *(below)*; Typical employer pension rate, Board/Exec *(below)*; Employer pension cost share *(below)*; **Employer pension contribution *(below)* — NEW** |
| **Health & Protection** (0→0) | none | none |
| **Benefits & Lifestyle** (5→9) | Flexible benefits allowance, Board/Exec *(below)*; Benefits participation *(below)*; Outplacement support *(below)*; Relocation support *(below)* | identical four |
| **Time Off & Family** (3→9) | Maternity & adoption pay approach *(below)*; Enhanced maternity & adoption pay *(below)*; Enhanced occupational sick pay *(below)* | those three, plus **Bank holiday working premium *(below)* — NEW** |
| **Incentives & Recognition** (2→4) | Long-service award value *(below)*; Individual recognition award value *(below)* | those two, plus **Bonus eligibility rate *(below)* — NEW**, **Long-service award scheme *(below)* — NEW** |
| **Wellbeing** (1→5) | Wellbeing budget per employee *(above)* | **Employee assistance programme *(below)* — NEW**; **Financial wellbeing programme *(below)* — NEW**; **Wellbeing strategy *(below)* — NEW**; Wellbeing budget per employee *(above)* |
| **Governance & Transparency** (2→10) | Maximum promotion increase *(below)*; Promotion decision governance *(above)* | those two, plus **Gender pay-gap analysis *(below)* — NEW**, **Pay ranges linked to job evaluation *(below)* — NEW** |

Nothing was removed. Every pre-fix signal survives; the fix is purely additive, and the
new entries are the mechanisms the broken resolver had disabled — `prevalence` and
`rare` reads (Utility costs, Wellbeing strategy, Gender pay-gap analysis) and the
`outlier` reads that need a block to compute.

## §2.4 Call sites enumerated

Every site passing a resolver to `build_signals`, with the binding each name resolves to:

| site | argument | binding |
|---|---|---|
| `server/app.py:2417` | `sig_get_block` | `:2405` → `pos.block_for(payloads().get(qid) or {}, sig_cut, (sig_tb or {}).get(qid))[0]` ✓ |
| `server/app.py:2426` | `sig_get_block` | same binding ✓ |
| `server/app.py:2816` | `get_block` | `:2797` → `pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0]` ✓ |
| `server/app.py:4410` | `_get_block` | `:4409` → `pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0]` ✓ |
| `server/app.py:5957` | `_sig_block` | `:5948` → `pos.block_for(payloads().get(qid) or {}, cut, (tb or {}).get(qid))[0]` ✓ **(the repaired site)** |
| `server/qa_overview.py:73` | `get_block` | gate-side reference: `pos.block_for(pls.get(qid) or {}, cut, **None**)[0]` — deliberate, the gate runs all-peers |

Five live sites, all reaching `pos.block_for`. The sixth is the gate's own reference
implementation; it hard-codes `None` for the twin block, which means **the overview gate
cannot exercise the twin/group path at all**. That is not a defect in the gate's own
terms, but it is why no gate caught P0-7f, and it belongs on the §4 sweep's ledger as a
population that is empty by construction.

---

## §5.1 — 20, 25, or 55?

Three different populations, all real, all named in code:

| | what it is | where | Pay | total before → after |
|---|---|---|---|---|
| **`signal_count`** | every signal the area flags | `app.py:6020` | 5 → 9 | **25 → 55** |
| payload array | `signal_count` **capped at 4** | `app.py:6025` — `_sigs[:4]` | 4 → 4 | 20 → 28 |
| printed rows | array capped again by print room | `report.js:1804` — `_room = inlineFollow ? 0 : 2 - (cntStrictFalse ? 1 : 0)` | 2 → 2 | — |

**Your 25 is right and mine understated the change.** My P0-7f table counted the payload
array, which is capped at four per area, so it could not show movement in any area that
already had four. The authoritative figure for a reader is the exhibit header's *M* — the
uncapped `signal_count` — and on that measure the fix took the document from **25 to 55**,
not 20 to 28. The deltas looked internally consistent (20+8=28) precisely because the cap
was absorbing the difference.

Per area, `signal_count` before → after: Pay 5→9, Pensions & Savings 7→9, Health &
Protection 0→0, Benefits & Lifestyle 5→9, Time Off & Family 3→9, Incentives &
Recognition 2→4, Wellbeing 1→5, Governance & Transparency 2→10.

The Time off & family zero-room rule is the third population at work: it has nine
signals, four on the payload, and **zero printed**, because its sheet also carries the
follow-up inline. The reader is told the count in prose instead
(`report.js:1873`) — "Time off & family is flagging 9 signals; they are set out in full
under Time off & family in the app."

I will use `signal_count` as the reported figure from here on, and name the population
whenever a count appears.

## §5.2 — Gate A's arithmetic

Full inventory: **`GATE_A_INVENTORY_2026-08-17.md`** (66 rows: id, owner, predicate,
blocking/advisory, admission date and commit, and whether it was exercised).

Static `check()` call sites by commit, counted with
`git show <c>:server/qa_strategy_doc.py | grep -cE '^[ \t]*check\('`:

| commit | | sites | advisory=True |
|---|---|---|---|
| `18a71b9` | Gate A born (QA-2) | 35 | 3 |
| `85a0c82` | v3.1 | 48 (+13) | 4 |
| `28c8e38` | v3.2 | 53 (+5) | 4 |
| `76e406f` | v3.3 red-first | 64 (+11) | 15 |
| `d662982` | v3.3-A | 63 (−1) | 14 |
| `4db83ce` | P0-7f | 64 (+1) | 14 |
| `e2beec6` | P1-B | 66 (+2) | 14 |

**The advisory movement is fully explained**: v3.3 added eleven advisory checks
(G53–G63), v3.3-A removed one when G61 was downgraded from a check to a candidate-
surfacer that returns no verdict at all. 4 + 11 − 1 = **14**. Your "moved by ten" is
exactly right.

**The 52 → 61 gap was a measurement-condition mismatch, not arithmetic.** Gate A's A2/A3
block reads the live figures through `db.get_conn()`, which **refuses to open the live
database from a gate process** and prints `SKIP` unless `LUMI_DB` points at a throwaway.
Two checks live in that block. So:

```bash
# without LUMI_DB — the A2/A3 block SKIPs
python3 server/qa_strategy_doc.py --pdf <render>            # -> 63 checks
# the way run_gates.sh invokes it
LUMI_DB=<throwaway.db> python3 server/qa_strategy_doc.py --pdf <render>   # -> 65 checks
```

The 52 was reported from a `run_gates.sh` run; the 61 from a standalone one. Two numbers,
two populations, no missing checks. Today's figures under the `run_gates.sh` condition are
**65 executed, 52 blocking, 14 advisory** — and I will state the invocation next to any
check count from now on.

One check in the inventory is marked **not exercised**: `A1.1 the exec summary states the
commitment frame`. It is the `else` half of an if/else — it exists to fail when the
register's anchor sentence cannot be found, so it running would itself be the alarm. That
is a mutually exclusive branch, not vacuity. It is the only one of the 66 that does not
execute, and the arithmetic above already excludes it.

## §5.3 — Health & Protection, and a bigger finding on the group cut

**Direct answer: the section and its exhibit cannot disagree.** Both the exhibit and the
prose fold-line hang off the same guard (`sigShown.length` / `b.signal_count`,
`report.js:1873` and `:1878`), so a section cannot stand down over an exhibit that is
present. §11 prints its heading, stats, chart and "How this reads" commentary in every
state; what folds is the **signals surface inside it**.

But the fold *is* cut-dependent, and the answer to "before any other cut ships" is worse
than the question assumed:

| | All peers | group cut (`5 sectors · 10,000+, 1,000–4,999 FTE`) |
|---|---|---|
| Health & Protection, pre-fix | 0 signals, no surface | 0 signals, no surface |
| Health & Protection, post-fix | 0 signals, no surface | **1 signal — Private medical insurance premium (Single) — full exhibit, Exhibit 9, page 19** |

**The group cut's printed document does not currently verify.** Rendered from the live
stored plan, post-fix:

```
python3 server/verify_report_pdf.py --pdf <group render>
PDF: p07f_group.pdf — 41 pages
  FAIL: the document says 40 pages and produced 41 — a section has split
  FAIL: page 28 carries no footer — it is a spill from the sheet before it
  FAIL: physical page 29 prints the number 28
  FAIL: contents sends 'The plan' to page 33, which is not that section
  FAIL: contents sends 'What it costs' to page 35, which is not that section
  FAIL: contents sends 'What a point is worth' to page 36, which is not that section
6 failure(s)
```

The split is **§16 Governance & transparency**: its content runs past A4 and pushes the
footer onto a sheet of its own, and every contents reference after it is wrong.

The pre-fix group cut verified clean at 40 pages, **0 failures — because it was empty**.
Zero signals in all eight areas is less content than any layout can break on. So the
group cut was never proven; it was vacuous, in precisely the sense §4 is about. The fix
did not introduce this defect, it made the cut render enough to expose it.

This is a layout/exhibit-design fix class and is **not authorised in this phase**. It is
reported, not touched. The All-peers document — the one that ships — still verifies at
40 pages, contiguous footers, 23 contents entries landing, 0 failures.

---

## §6 — the orphaned WAL/SHM pair

Reported on its own line, with its path, as asked.

**Path:** `/private/tmp/claude-501/-Applications-Lumi-Project/eab138a8-46d2-40c2-9324-b262e4a7efba/scratchpad/q3/`

**What was there:**

```
-rw-r--r--  4224 Aug 16 15:45  depth_probe.py
-rw-r--r-- 32768 Aug 16 15:46  lumi_copy.db-shm
-rw-r--r--     0 Aug 16 15:45  lumi_copy.db-wal
```

**Was a `.db` beside it?** **No.** `lumi_copy.db` did not exist — an earlier session's
teardown had removed the main file and left the two sidecars. That is why they were
orphaned rather than live.

**Checkpointed or removed?** **Removed** — `rm -rf` on the `q3` directory. Not
checkpointed.

**Could committed transactions have been discarded?** No, and it is worth stating why
rather than asserting it: the WAL was **0 bytes**, so it held no frames; the `-shm` is a
fixed-size shared-memory index that carries no data of its own. There was also no main
database for the frames to belong to. The scratchpad was a throwaway tree, and the
teardown it belonged to had already verified zero DB copies.

**On the reporting point — you are right and I accept the correction.** I put the
deletion in a parenthetical at the end of a sentence about the teardown. That is exactly
the shape that lets a deletion pass unreviewed: the reader's attention is on the clause,
not the object. A deletion gets its own line, its own path, and its state before removal.
Adopted from here.

**Two practices adopted with it**, both from your note rather than from this incident:
`PRAGMA wal_checkpoint(TRUNCATE)` before any copy that is not the backup API, and
delete-by-pattern resolves its paths and prints them before removing anything.

---

## §4 — the vacuity sweep

**Read-only. Nothing was fixed.** Full per-check table: `VACUITY_SWEEP_2026-08-17.md`.

### The classification

735 checks across the fifteen check-based gates (`qa_plausibility` is a root-dir freeze
gate with a different shape; it is not in this count).

| gate | checks | existential | universal | scalar | Arm A | Arm B |
|---|---|---|---|---|---|---|
| qa_strategy.py | 107 | 10 | 11 | 73 | 6 | 14 |
| qa_backoffice.py | 108 | 31 | 19 | 54 | 5 | 12 |
| qa_strategy_align.py | 77 | 8 | 43 | 23 | 1 | 24 |
| qa_strategy_doc.py | 64 | 17 | 36 | 6 | **14** | 24 |
| qa_hero.py | 54 | 3 | 33 | 14 | 2 | 25 |
| qa_pulse.py | 52 | 11 | 13 | 22 | 8 | 5 |
| qa_engine_audit.py | 48 | 4 | 35 | 4 | 3 | **33** |
| qa_commentary.py | 45 | 6 | 16 | 6 | 2 | 10 |
| qa_refresh.py | 40 | 0 | 7 | 30 | 0 | 4 |
| qa_focus.py | 36 | 2 | 17 | 15 | 1 | 14 |
| qa_overview.py | 31 | 7 | 15 | 8 | 1 | 9 |
| qa_release.py | 25 | 7 | 7 | 10 | 3 | 7 |
| qa_domain_summary.py | 21 | 13 | 5 | 1 | 1 | 3 |
| qa_signals_system.py | 15 | 2 | 10 | 3 | 1 | 7 |
| identity_recon.py | 12 | 0 | 9 | 1 | 0 | 9 |
| **total** | **735** | **121** | **276** | **270** | **48** | **200** |

**Two hundred Arm B candidates is not a scandal, it is a house idiom.** The dominant way
this suite asserts anything is `all(...)` or `not [x for x in P if wrong(x)]`, and every
one of those is `True` when `P` is empty. It is a good idiom — it reports *which* member
failed — and it has this one property. The count is large because the style is
consistent, not because the gates are careless.

I read a sample against the source myself rather than taking the classification on
trust — `qa_focus.py:103` (`bad = [s for s in mv["layout"] if …]`, empty layout ⇒ empty
`bad` ⇒ pass) and `qa_signals_system.py:181` (`all(… for s in sigs)`, `sigs == []` ⇒
pass). Both hold. But **48 + 200 flagged is a classification, not a set of confirmations.**
Below is what I actually confirmed.

### Confirmed

**1 — Arm B at block level, in Gate A itself. Measured, not inferred.**

`run_gates.sh:209` invokes `run_gate qa_strategy_doc` with **no `--pdf`**. Same gate,
three invocations, same source and same throwaway:

```bash
LUMI_DB=<throwaway.db> python3 server/qa_strategy_doc.py                    # 34 checks — what the SUITE runs
python3 server/qa_strategy_doc.py --pdf <render>                            # 63 checks
LUMI_DB=<throwaway.db> python3 server/qa_strategy_doc.py --pdf <render>     # 65 checks
```

**Every "16/16 ALL GATES GREEN" in this project's history ran 34 of Gate A's 66 checks.**
The thirty-one that read the printed artefact — the ones that own D001, D019, D028, D052,
G53–G64, the whole red-first block — did not run, and the suite printed `PASS
qa_strategy_doc`. The file's own comment (`run_gates.sh:207`) says the artefact half runs
separately before a release, so this is a designed split, not an accident. The defect is
that **the result does not say so.** This is R-e's strongest evidence.

**2 — G62, your named reference, confirmed by fixture.**

Its population is areas whose printed statement matches `You aim … on <area>; the live
read sits past it`. On the real artefact the population is two (Pay, Time off & family)
and the check **fires** — `WARN … past-aim areas still offering levers: ['Pay']`. I built
an artefact with the population emptied (the past-aim commitments' `direction` and
`statement` rewritten to the short-of-aim form in `canned.json`, then rendered through the
same harness) and the same check reports:

```
PASS G62 a past-aim area renders no options exhibit  [D084]
```

Green, having examined nothing. Exactly your Arm B.

**3 — D072's old form, Arm A, already on the record** at `4db83ce`: `plural present ⟹
singular present somewhere` held only because one area happened to show one row.

**4 — the reason no gate could have caught P0-7f.** `qa_overview.py:73` builds its own
resolver as `pos.block_for(pls.get(qid) or {}, cut, **None**)` — the twin block is
hard-coded absent. The gate's twin/group population is **empty by construction**, so the
one code path where the broken resolver raised `TypeError` was unreachable from any gate.
This is Arm B in its purest form: not a population that happens to be empty for this
organisation, but one the harness can never fill.

### Not confirmed

The remaining **47 Arm A** and **197 Arm B** candidates are classified and listed with
their emptying scenario, and have **not** been individually fixture-confirmed. Confirming
200 candidates is 200 fixtures; that is its own phase, and you asked to see the count
first. The table is ordered so the ones whose population empties for an *ordinary* org —
a fresh org with no answers, a small org where the n≥5 floor suppresses everything, an org
with no gaps — are identifiable by their `Empties when:` clause. 165 of the 200 carry one.

### One observation for whoever takes the fix

The fix for Arm B is not 200 restatements. Every one of these checks already computes its
population before asserting over it; what is missing is that the population is not passed
to `check()`. A second signature — `check(name, ok, detail, over=P)` — that reports
**`NOT EXERCISED`** when `P` is empty, plus a suite line reading
`N passed, M failed, K not exercised`, converts the entire class in one diff per gate
without restating a single predicate. That is R-e as code rather than as discipline, and
it is what I would propose when a fix is authorised.

---

## Rulings

**R-e — not exercised is not pass.** Supported by the evidence above, and I would go
further than the draft: the suite summary line should carry the exercised count, because
the failure mode is not a reader misreading one check, it is `ALL GATES GREEN` over a gate
that ran half of itself.

**R-f — checks assert on bindings, not strings.** Already applied in both commits this
phase: G64 follows the resolver argument to its binding; G65 reads the `except` body
rather than matching the word `except`. Recorded in DECISIONS.md at `e2beec6`.

Both remain **drafted, not adopted** — yours to rule.

## Still owed

V1 (`3035ef7` and its DECISIONS entry) and V2 (entry 8078, ASHE scope) from Phase 1 §4.
Neither was in this phase's authorised scope and neither has moved.

---

## §4 addendum — the adversarial pass

The four highest-risk gate files got a second, independent read whose only brief was to
find what the first pass missed. It missed a great deal: **51 further candidates across
four files, and none of the four first passes was complete.** Everything below I verified
myself before recording it; the ones I could not verify cheaply are marked as reported.

### The one that matters most: G65 was mine, and it was vacuous

`G65`, committed at `e2beec6` four hours earlier, asked `"raise" in <except body text>`.
The body's own comment says "…the twin/group path is what **raised** here before P0-7f".
The substring was satisfied by prose. **Proven by mutation** — with the `raise` deleted
and replaced by an assignment that returns a blank document to the board:

```
PASS G65 a signal-builder failure fails the request, it does not blank every area  [P1-B]
```

Red-first did not catch it because G65 is a conjunction and the red I demonstrated came
from the *other* clause (`_all_sigs = []` restored). **Red-first is per-clause, not
per-check.** That is the discipline failure, and it is mine.

Fixed at `8f13415`: both checks now read app.py's syntax tree — G65 requires a `Raise`
node in the handler wrapping the `build_signals` call and no `Assign` to `_all_sigs`;
G65b walks the handler's `log.*` call and asserts the org and both cut components are
passed **as arguments**, not merely named in a format string. Comments do not exist in a
tree. Admitted by a mutation battery in which each mutant is caught by its owning check
and by no other. **G64 was put through the same battery and holds**, including a mutant
that restores the broken resolver with `# resolves via pos.block_for` planted beside it.

### Confirmed, verified by me

**`qa_hero.py:284` — a guard that has never been able to fail.** It asserts
`"your maturity" not in commercial.js`. `grep -rni "your maturity" web/` returns **0**
hits across the entire web tree. The string it forbids has never existed anywhere, in any
file, so the check has been green since the day it was written for a reason unrelated to
what it claims to protect.

**`qa_strategy_align.py:186` — a tautology.** `all(o["framing"] == sa.OPTIONS_FRAMING
for o in OB)` compares each block's framing against the module constant that
`options_for` itself writes into every block (`strategy_align.py:115` and `:137`). The
check asserts that an assignment assigned.

**`qa_strategy_align.py:360` — "every derivable risk" cannot reach the eighth.**
`wage_floor` (`strategy_align.py:485`) is gated on `derive_risks(..., sector=…)`.
`grep 'sector=' server/qa_strategy_align.py` → **0**: no gate ever passes a sector.
Adding `sector="Retail"` to the same fixture yields `wage_floor` and nothing else
changes. The live endpoint **does** pass it (`app.py:6141`,
`sector=org.get("industry")`), so this is a production risk class with zero gate
coverage, behind a check whose name claims to cover all of them.

**The amplifier, in two places.** `run_gates.sh:74-82`: `run_gate` captures the whole
gate output to a file, echoes only `tail -4`, and decides PASS/FAIL **purely on exit
code**. A gate that skips half of itself exits 0 and prints PASS.
`qa_strategy_align.py:403-408`: `passed = sum(1 for _, ok in R if ok)` and
`if passed == len(R): print("GATE CLEAN")` — `R` only grows when `check()` runs, so
every skipped check is invisible to both the tally and the verdict. Together these are
why finding 3 in §5 could sit undetected: nothing in the chain can tell "everything
passed" from "less ran than you think".

### Reported, not independently verified

The adversarial pass raised a further set I have not confirmed and am not asserting:
`qa_hero.py` aborts (unguarded `api()` with no status check, an unguarded division at
`:127` that raises on a day-one org, `dm["Wellbeing"]` as a hardcoded key, five bare
`open()` calls, a per-signal API call inside a loop) — any of which ends the run partway
with the earlier PASS lines already printed; `qa_signals_system.py`'s snooze block being
four tautologies over the test's own SQL rather than any app path; and its
`try/finally` with no `except` around the firing half. These are in
`VACUITY_SWEEP_2026-08-17.md` with the auditor's reasoning and line numbers, flagged as
unverified.

### What this changes about the sweep's numbers

The classification counted 48 Arm A and 200 Arm B. The adversarial pass found 51 more in
four files alone and judged **every one of those four first passes incomplete**. So the
honest statement is not "248 candidates" but: **the true count is higher than 248 and
this sweep has not established it.** One pass over a suite this size finds a floor, not a
total. That is worth knowing before anyone scopes the fix.
