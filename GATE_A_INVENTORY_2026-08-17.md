# Gate A — full check inventory

`server/qa_strategy_doc.py` at `e2beec6`. Recipe:

```bash
LUMI_DB=<throwaway.db> python3 server/qa_strategy_doc.py --pdf <render.pdf>
```

**66 static call sites — 52 blocking, 14 advisory.** 65 execute under the recipe above;
one is the unreachable half of an if/else pair (noted below).

| # | check | owns | predicate | blocking | admitted | exercised |
|---|-------|------|-----------|----------|----------|-----------|
| 1 | `A4.5 one word for the grouping — no 'domain' in document prose` | D020 | `not bad_domain` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 2 | `A4.7 typography — no stray terminals, doubled punctuation or spaces` | D025 | `not typos` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 3 | `A2.4 cover carries no vendor logo` | D004 | `'LUMI_LOGO_SVG' not in cover` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 4 | `A2.4 cover carries no 'Prepared by lumi' byline` | D004 | `not re.search('Prepared by[^<]{0,40}lumi', cover)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 5 | `A4.2 the Part A prose builders were located` | D-voice | `len(part_a_builders) > 200 and len(part_a_builders) < 6000` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 6 | `A4.2 Part A deterministic prose never names lumi` | D-voice | `not re.search('\\blumi\\b', ' '.join(prose_strings(part_a_builders)), re.I)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 7 | `A1.5 the ask is single-sourced — no surface reads the raw row count` | D014 | `raw_uses <= 2` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 8 | `A1.5 the shared ask shape exists` | D014 | `'const askActs' in SRC and 'const askTwoPart' in SRC` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 9 | `A1.1 exec conclusions count commitments, not domain alignments` | D001 | `'commitments.filter(c => c.kind === "position")' in concl and (not re.search('domains\\.filter\\([^)]*alignment', concl))` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 10 | `A1.4 no arithmetic on commitment counts in the template` | A1.4 | `not count_math` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 11 | `A5.1 the market band comes from the payload, not a literal` | A5.1 | `'al.market_band' in SRC` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 12 | `A3.1 the suppression floor is not hardcoded in the document` | D019 | `not re.search('fewer than\\s*5\\s*organisation', SRC)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 13 | `A3.1 the suppression floor renders from the payload` | D019 | `'al.suppression_floor' in SRC` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 14 | `A2.1 the ruled pool line renders on the cover and in the foot` | D002 | `SRC.count('al.pool_footer') >= 2` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 15 | `A8.4 verifier FOOT_RE matches the document's own page mark` | verifier-lockstep | `ok_lock` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 16 | `A1.5 the plan renders lever descriptions from the live library` | D032 | `'descOf[a.title]' in SRC` | **blocking** | 2026-08-16 v3.1 | yes |
| 17 | `A1.5 the stored plan prose is not rendered beside the library description` | D068 | `'if (!inLib) return html' in SRC and 'planFirstOfGap' in SRC` | **blocking** | 2026-08-16 v3.2 | yes |
| 18 | `A4.7 no template expression opens a line directly after a sentence` | D039/htm | `not newline_expr` | **blocking** | 2026-08-16 v3.1 | yes |
| 19 | `A6 the 'options follow below' clause is gated on the options branch` | D027 | `'_allLev.length ? ", and the options against them follow below."' in SRC` | **blocking** | 2026-08-16 v3.1 | yes |
| 20 | `A6 the 'Options above…' caption is gated on options existing` | D026 | `re.search('findings \\\|\\\| \\[\\]\\)\\.some\\(f =>', SRC) is not None` | **blocking** | 2026-08-16 v3.1 | yes |
| 21 | `D037 the cover addressee is derived, never defaulted` | D037 | `'ver.approver_body' in cover and '"The Board"' not in cover` | **blocking** | 2026-08-16 v3.1 | yes |
| 22 | `D047 empty principles/constraints render as a line, not as cards` | D047 | `'(doc.principles \|\| []).length ? html`' in SRC` | **blocking** | 2026-08-16 v3.1 | yes |
| 23 | `A5.3 ordinal aim renders as a bracket from the band edge, not a point` | D005 | `'RR_AIM_BRACKET' in SRC` | advisory | 2026-08-16 QA-2 (Gate A born) | yes |
| 24 | `A4.1 no directive language in the lever/rule libraries` | D016 | `not directive_hits` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 25 | `A4.1 no legal adjudication in the lever/rule libraries` | D016 | `not legal_hits` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 26 | `A4.6 one lever name renders one description` | D015 | `not dupes` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 27 | `A4.4 no vendor or provider names in the libraries` | — | `not vendor_hits` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 28 | `A4.3 forward-looking claims carry a date and a source` | D017 | `not fc` | advisory | 2026-08-16 QA-2 (Gate A born) | yes |
| 29 | `A4 every lever states a trade-off` | — | `not no_trade` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 30 | `A2.3 the stated pool size equals the live answering-org count` | D002 | `stated == live` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 31 | `A3.1 the suppression floor is a single derived constant` | D019 | `isinstance(SUPPRESSION_FLOOR, int) and SUPPRESSION_FLOOR >= 3` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 32 | `A2.1 the ruled provenance sentence appears verbatim` | D002 | `bool(ruled)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 33 | `A2.1 the pool fact also appears on the cover` | D002 | `'UK organisation profiles' in pages[0]` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 34 | `A2.4 the cover names no vendor` | D004 | `not re.search('\\blumi\\b', pages[0], re.I)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 35 | `A4.5 'domain' appears nowhere in the artefact` | D020 | `not re.search('\\bdomains?\\b', text, re.I)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 36 | `A4.7 no sentence terminal before an em-dash` | D025 | `not re.search('\\.\\s+—', text)` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 37 | `A1.3 the status tally closes: off + holding == total` | D001 | `off + holdn == total` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 38 | `A1.2 the register enumerates every commitment it claims` | D001 | `rows == total` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 39 | `A1.1 the exec summary states the commitment frame` | D001 | `False` | **blocking** | 2026-08-16 QA-2 (Gate A born) | **NO** |
| 40 | `A1.5 the banner's count equals the stat card's count` | D014 | `got == int(stat.group(1))` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 41 | `A1.5 a two-part ask is two-part in the body too` | D014 | `not two_part or re.search('asked for two decisions', ask_pg) is not None` | **blocking** | 2026-08-16 QA-2 (Gate A born) | yes |
| 42 | `D033 no 'one of 1' grammar leak` | D033 | `not re.search('one of 1\\b', text)` | **blocking** | 2026-08-16 v3.1 | yes |
| 43 | `D066 no unevidenced 'self-funding' claim` | D066 | `'self-funding' not in text` | **blocking** | 2026-08-16 v3.1 | yes |
| 44 | `D029 no signal name repeated inside its own detail` | D029 | `not dupes` | **blocking** | 2026-08-16 v3.1 | yes |
| 45 | `D068 no superseded lever description survives anywhere in the artefact` | D068 | `not ghosts` | **blocking** | 2026-08-16 v3.2 | yes |
| 46 | `D069 no rendered sentence opens lowercase` | D069 | `not lowers` | **blocking** | 2026-08-16 v3.2 | yes |
| 47 | `D072 the signal note's number agrees with the rows the exhibit shows` | D072 | `not d72` | **blocking** | 2026-08-17 P0-7f | yes |
| 48 | `D075 one noun for the per-metric base` | D075 | `len(base_nouns) <= 1` | **blocking** | 2026-08-16 v3.2 | yes |
| 49 | `D028 no comparator-less peer-median comparison` | D028 | `not bare` | **blocking** | 2026-08-16 v3.1 | yes |
| 50 | `D052 the cover says the stated peer group is not the basis` | D052 | `'not the basis for the reads' in pages[0] if 'Stated peer group' in pages[0] else True` | **blocking** | 2026-08-16 v3.1 | yes |
| 51 | `D042 area order is the stored taxonomy order` | D042 | `'_q_all.values() if q.sub_power' in open(os.path.join(HERE, 'app.py')).read()` | **blocking** | 2026-08-16 v3.1 | yes |
| 52 | `G53 no respondent verb is bound to the comparison pool` | D076 | `not g53` | advisory | 2026-08-16 v3.3 red-first | yes |
| 53 | `G54 against-aim read <-> register position row, per area` | D077 | `not g54` | advisory | 2026-08-16 v3.3 red-first | yes |
| 54 | `G55 the Exhibit 2 note's basis reproduces the register's position count` | D077 | `g55_ok` | advisory | 2026-08-16 v3.3 red-first | yes |
| 55 | `G56 a single-option approval surface names its alternatives` | D078 | `g56_ok and 'chosen over' in ask_pg.lower()` | advisory | 2026-08-16 v3.3 red-first | yes |
| 56 | `G57 every benchmarked area falls in a Findings bucket` | D079 | `not g57` | advisory | 2026-08-16 v3.3 red-first | yes |
| 57 | `G58 a priced gap is acted on this cycle or its absence is stated` | D080 | `g58_ok` | advisory | 2026-08-16 v3.3 red-first | yes |
| 58 | `G59 every gap count carries or accompanies the shortfall/overshoot split` | D081 | `not bare` | advisory | 2026-08-16 v3.3 red-first | yes |
| 59 | `G60 Part C's per-gap option count matches Part B's mapped options` | D082 | `not m_c` | advisory | 2026-08-16 v3.3 red-first | yes |
| 60 | `G62 a past-aim area renders no options exhibit` | D084 | `not g62` | advisory | 2026-08-16 v3.3 red-first | yes |
| 61 | `G63 every 'Your stated answers' row cites a response` | D085 | `not g63` | advisory | 2026-08-16 v3.3 red-first | yes |
| 62 | `A6.5 approvers render as a person, not an account identifier` | D036 | `not re.search('Approved by [\\w.]+@', text)` | advisory | 2026-08-16 QA-2 (Gate A born) | yes |
| 63 | `D034 the schedule's gap count matches the register's off-strategy count` | D034 | `False` | advisory | 2026-08-16 v3.1 | yes |
| 64 | `G64 the alignment endpoint resolves twin blocks through pos.block_for` | P0-7f | `bool(_align_bs) and 'pos.block_for' in _resolver and (not re.search('\\btb\\s*\\(', _resolver))` | **blocking** | 2026-08-17 P0-7f | yes |
| 65 | `G65 a signal-builder failure fails the request, it does not blank every area` | P1-B | `bool(_bs_try) and 'raise' in _exc_body and (not re.search('_all_sigs\\s*=\\s*\\[\\]', _exc_body))` | **blocking** | 2026-08-17 P1-B | yes |
| 66 | `G65b the failure log names the org and the cut` | P1-B | `all((s in _exc_body for s in ('org=%s', 'cut=%s', 'cut.get("dim")')))` | **blocking** | 2026-08-17 P1-B | yes |
