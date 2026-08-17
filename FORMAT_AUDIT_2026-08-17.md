# Format audit — Total Reward Strategy & Plan

**Read-only. No fixes, no CSS, no ruling on which convention wins.** This establishes what
is inconsistent; the target convention is David's to rule (R-h).

**Artefacts audited**

| | path | sha256 | pages |
|---|---|---|---|
| all-peers | `artefacts/total_reward_strategy_and_plan.pdf` | `1c8593de…a117ef8` | 40 |
| group cut | `p07f_group.pdf` (scratch, from the same live plan on `?cut=group`) | — | 41 |

Both rendered from the **live stored plan**, `built_at 2026-08-15 14:35:32`, `REBUILD_PLAN`
unset. Recipes:

```bash
shasum -a 256 artefacts/total_reward_strategy_and_plan.pdf
python3 -c "import pymupdf;d=pymupdf.open('<pdf>');print(d.page_count, d.metadata)"
python3 -c "import pymupdf;pymupdf.open('<pdf>')[14].get_pixmap(dpi=110).save('p15.png')"
```

**Method.** Every dimension was checked against **rasterised page images**, not extraction,
per Phase 2 §6.3. Where a count is quoted it comes from the text layer and is stated as
such. One correction to the premise: this artefact's Type 3 fonts **are** extractable by
PyMuPDF — the 32 artefact checks in Gate A depend on it, and p15 yields 1,480 correct
characters. No other extractor is installed on this machine (`pdftotext`, `mutool`,
`qpdf` all absent), so I cannot speak for other consumers, and the PDF/UA and PDF/A
eligibility arguments in §6.2 stand independently of extraction.

---

## Defects

| ID | Dim | Page | Defect | Convention breached | Cut-dependent |
|---|---|---|---|---|---|
| **F-000** | F-D | group p28–29 | 41 physical pages against a footer claim of 40; §16 Governance & transparency runs past A4 and its footer lands on a sheet of its own; three contents entries mis-target from there | A footer total is a claim the document must be able to keep | **YES — group only** |
| **F-001** | F-A | throughout | **Four continuation conventions in one document**: `(cont.)` ×1 (§03), `(N of M)` ×22 (§07, §08, §12, §17, §18), `— what follows` ×7 (§09–§16), and `(continued)` ×0 — the one convention that is never used | One continuation convention per document | no |
| **F-002** | F-A | 11–12, 21–22, 33–34 | **Three single tables consume two exhibit numbers each**: Exhibits 3/4 (*Every commitment, its status and its evidence*), 10/11 (*Options against the …*), 18/19 (*Planned actions by horizon*). 22 exhibit numbers for 19 exhibits | One exhibit, one number, `(continued)` on the carry | no |
| **F-003** | F-B | 5–34 | **Ten section numbers head two pages each, one heads three.** §03, §07, §08, §09, §10, §14, §15, §16, §17, §18 ×2; **§12 ×3** (Benefits & lifestyle, — what follows (1, — what follows (2). Contents lists one page per number, so "§09" is ambiguous in a minute | A section number resolves to one location | no |
| **F-004** | F-C | 40 of 40 | **Basis of preparation is §23, the last page.** The provenance line, the suppression floor, the stated-peer-group caveat and *"an order of magnitude for a board discussion, not a budget"* all sit past every screenshot crop | Board convention: important notice / basis immediately after contents | no |
| **F-005** | F-E | 35 | Exhibit 20's metric sub-caption (*"summed level by level: the gap to the peer rate × median salary × the FTE in that level"*) **wraps out of the METRIC column and runs under AREA**, whose own value has wrapped to two lines. The two columns interleave | A cell's content stays inside its column | no |
| **F-006** | F-E | 15 | Exhibit 5's YOURS column mixes types — `30th percentile` (a statistic) above `Utility costs` (an option label, repeating the row's own SIGNAL value). Left-aligned, so nothing aligns on a decimal or a unit | One value type per column; numerals align on their unit | no |
| **F-007** | F-F | 1 | **Two range dashes on the cover.** `50–249 FTE` (en dash) and `1,000-4,999 FTE` (hyphen), eight lines apart. All 12 other numeric ranges in the document use an en dash; the hyphen appears twice, both times in the stated-peer-group string | One range glyph | no |
| **F-008** | F-F | 1 | **Two date formats on the cover.** `17 Aug 2026`, `15 Aug 2026`, `17 Jun 2026` (human) beside `2026 H1 · 2026-06-11` (ISO) | One date format in the reader-facing layer | no |
| **F-009** | F-F | ×12 | `/100` renders 12 times (`0/100`, `25/100`, `50/100`, `100/100`) — a score scale in a document that states it never scores | **A2 / BQ3 — substantive, flagged here, fixed there** | no |
| **F-010** | F-H | 35 | §19's INDICATIVE SAVING tile reads **`—`**. The sub-label *"where you sit above it"* names the condition but the tile never says the saving is nil, or unpriced, or not applicable | An empty state states why it is empty | no |
| **F-011** | F-I | metadata | **PDF title is `Overview · lumi`** — the app's browser-tab title, not the document's. `author`, `subject`, `keywords` all empty. `creator` leaks the full HeadlessChrome user-agent string. This is what a document-management system files it under and what an email client previews | Title is the document; producer strings are not shipped identity | no |
| **F-012** | F-I | 3–4 | **No PDF outline.** `get_toc()` returns 0 entries against a 23-entry printed contents. A 40-page board paper opens with no navigation pane | A contents page implies bookmarks | no |
| **F-013** | F-I | 10 | Exhibit 2 is drawn as vector with **0 embedded raster images**, so there is no object to carry alt text. `MarkInfo/Marked true` and `Lang en-GB` **are** present — the file is partially tagged already, which is better than assumed | Charts carry a text alternative | no |
| **F-014** | F-J | 10 | **The dot-colour contradiction survives.** Exhibit 2's legend calls the green band *"the range lumi reads as on market"*, and green *"verdict: on market"* dots are plotted **outside** it — Governance & transparency sits left of the band's left edge in green, at the same horizontal position as Wellbeing's brown *below market* dot. The caption explains the mechanism (depth percentile vs a verdict weighing every metric); the picture still asserts two incompatible things | A legend and its marks agree, or the chart carries two scales explicitly | no |
| **F-015** | F-J | 10 | Exhibit 2 has **two gridline colours** — tan at the 25th and 75th, grey at the 10th, median and 90th — with no legend entry for either | Every visual encoding is either legended or decorative, not half of each |no |
| **F-016** | F-J | 1, 15, 35 | Stat cards carry an **identical orange top rule** whether the value is neutral (`46 METRICS BENCHMARKED`), positive (`on market`, green) or adverse (`above strategy`, maroon). Colour is semantic in the text and decorative in the rule, in the same component | One colour system per component |no |
| **F-017** | F-K | 1 | Cover carries ORGANISATION, DATE OF ISSUE, DOCUMENT STATUS, BENCHMARK BASIS, COMPARISON POOL, DATA COLLECTION, STATED PEER GROUP, PRIMARY OBJECTIVE, CLASSIFICATION. **Missing: prepared for, prepared by, distribution list, version history.** §22 carries an approval record; the four front-matter fields are not the same thing | Board front matter carries all four | no |

## Checked, nothing found

**F-G — canonical names.** Every area renders in one form throughout (`Pensions & savings`,
`Time off & family`, sentence case on the second word), including in exhibit captions and
cross-references. My first pass appeared to find drift; it was the regex catching adjacent
text, not the document. **No F number issued.** This remains unverified against the R12 /
Q15 terminology ruling, which has not landed — when it does, this dimension needs re-running
against it rather than against internal consistency.

## Cut-dependence

Only **F-000** is cut-dependent, and it is a blocker on any cut other than all-peers
shipping. Everything else reproduces identically in both artefacts. The group cut was not
"previously clean": pre-P0-7f it verified at 40 pages with 0 failures **because it carried
zero signals in all eight areas**, so no layout could break on it. F-000 is a latent
constraint the repair exposed, not one it introduced.

## Not audited

Rule weights and cell padding measured in absolute units, and header-row treatment across
all 22 exhibits, would need a systematic crop of every table rather than the six pages
rasterised here. Flagging the gap rather than implying coverage.
