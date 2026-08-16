# -*- coding: utf-8 -*-
"""GATE A — the reward DOCUMENT's own gate (2026-08-16, from the external QA spec v2).

WHY THIS EXISTS. Every defect the two external reviews found in this artefact was
fixed by hand, and three of them were *introduced* by the previous hand-fix — a
stray terminal on the cover, an "actions" count that drifted from the ask it sits
beside, an engine word leaking into a document that says "area". The spec's thesis
is the right one: **a defect without an owning assertion can return.** So every
check below cites the defect it owns (D0NN), and the ones no test can honestly
catch are named as judgment rather than faked.

SCOPE. The generated document artefact only — engine correctness stays with
qa_hero / qa_engine_audit / qa_focus / qa_strategy_align / qa_commentary.

    python3 server/qa_strategy_doc.py                  # source + data + DB (every build)
    python3 server/qa_strategy_doc.py --pdf out.pdf    # + the rendered artefact

The no-PDF form is what run_gates.sh runs: it needs no browser and no server, and
it still owns the whole class of defect that actually shipped. The --pdf form is
the pre-release run, alongside verify_report_pdf.py (which owns pagination).

BLOCKING vs ADVISORY. Checks marked ADVISORY print but never fail the gate: they
either encode a design ruling David has not made (the aim-bracket question), or
they are warn-level by nature (forecast language). Everything else blocks. The
split is deliberate and is on the ruling sheet — an advisory gate is a skipped
gate, so the list is kept short.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)

REPORT_JS = os.path.join(ROOT, "web", "js", "report.js")
LEVERS = os.path.join(ROOT, "data", "reward_levers.json")
RULES = os.path.join(ROOT, "data", "strategy_coherence_rules.json")
VERIFIER = os.path.join(HERE, "verify_report_pdf.py")

FAILS, WARNS, NCHECK = [], [], [0]


def check(name, ok, detail="", owner="", advisory=False):
    NCHECK[0] += 1
    tag = "PASS" if ok else ("WARN" if advisory else "FAIL")
    print("  %s %s%s%s" % (tag, name, ("  [%s]" % owner) if owner else "",
                           ("  — " + str(detail)[:220]) if (detail and not ok) else ""))
    if not ok:
        (WARNS if advisory else FAILS).append((name, detail))


# ---------------------------------------------------------------- helpers ----
def js_strings(src):
    """Every single/double-quoted literal in the file. Deliberately NOT template
    literals: htm templates carry markup, and their prose reaches the page through
    the quoted strings concatenated into them. Comments are stripped first so a
    note *about* a defect never trips the check for the defect."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)
    out = []
    for m in re.finditer(r"""(?<![\\\w])"((?:[^"\\\n]|\\.)*)"|(?<![\\\w])'((?:[^'\\\n]|\\.)*)'""", src):
        out.append(m.group(1) if m.group(1) is not None else m.group(2))
    return out


# Fragments that only ever occur in CODE, never in the document's prose. A naive
# quoted-literal scan also captures regex bodies and replacement patterns (the
# apostrophe inside /(\w)'(\w)/g opens a "string" that runs to the next quote), and
# those false positives would train a reader to ignore this gate.
CODE_SHAPED = ("$1", "$2", "\\", "=>", "${", "/g", "/i", "//", "px", "!important")


def prose_strings(src):
    """Quoted literals that read as prose — two or more words, no code shapes.
    Keys, ids, class names and enum values are single tokens and add only noise."""
    return [s for s in js_strings(src)
            if len(s.split()) >= 2 and not any(c in s for c in CODE_SHAPED)]


def uncommented(src):
    """Source with comments removed — a note ABOUT a defect must never trip the
    check FOR the defect (the cover's own 'no Prepared by lumi row' comment did)."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def section_of(src, start_marker, end_marker):
    i = src.find(start_marker)
    if i < 0:
        return ""
    j = src.find(end_marker, i + len(start_marker))
    return src[i:j if j > 0 else len(src)]


# =============================================================== A4 · SOURCE ==
print("\n=== A4/A2 · the document's own source (web/js/report.js) ===")
SRC = open(REPORT_JS).read()
PROSE = prose_strings(SRC)

# --- A4.5 one word for the grouping (D020) ---------------------------------
# The document says AREA. "domain" is engine vocabulary and leaked into the plan
# intro; one leak reads as a different document. Code identifiers (domainLabel,
# domain_blocks, "domain:<Cat>" keys) are not prose and are excluded by shape.
bad_domain = [s for s in PROSE if re.search(r"\bdomains?\b", s)
              and not s.startswith("domain:")]
check("A4.5 one word for the grouping — no 'domain' in document prose",
      not bad_domain, bad_domain[:3], owner="D020")

# --- A4.7 typographic pass (D025) ------------------------------------------
# The cover shipped "…profiles. — lumihr.co.uk": a naive replace left the sentence
# terminal in front of an em-dash. Scan assembled prose for the shapes a proof
# reader catches and a generator does not.
TYPO = [(r"\.\s+—", "sentence terminal before an em-dash"),
        (r"\s+[,;.]", "space before punctuation"),
        (r"[,;]\s*[.]", "doubled terminal"),
        (r"\S {2,}\S", "doubled space")]
typos = [(s[:70], why) for s in PROSE for pat, why in TYPO if re.search(pat, s)]
check("A4.7 typography — no stray terminals, doubled punctuation or spaces",
      not typos, typos[:3], owner="D025")

# --- A2.4 no vendor mark outside the method + provenance line (D004) --------
cover = uncommented(section_of(SRC, 'kindOf === "cover"', 'kindOf === "divider"'))
check("A2.4 cover carries no vendor logo",
      "LUMI_LOGO_SVG" not in cover, "cover branch references a lumi logo", owner="D004")
check("A2.4 cover carries no 'Prepared by lumi' byline",
      not re.search(r"Prepared by[^<]{0,40}lumi", cover), owner="D004")

# --- A4.2 Part A purity: the member's voice, not the vendor's ---------------
# Part A is the member's own strategy statement. Deterministic prose that renders
# INSIDE it may not narrate lumi's behaviour ("lumi orders what it shows you").
# Bound the slice at the bodies marker: an unfound end marker would silently widen
# this to the whole file, and a check that scans everything proves nothing.
part_a_builders = section_of(SRC, "const tensionPre", "------------------ bodies")
check("A4.2 the Part A prose builders were located",
      len(part_a_builders) > 200 and len(part_a_builders) < 6000,
      "slice is %d chars — the markers have moved" % len(part_a_builders), owner="D-voice")
check("A4.2 Part A deterministic prose never names lumi",
      not re.search(r"\blumi\b", " ".join(prose_strings(part_a_builders)), re.I),
      "a Part A prose builder names lumi", owner="D-voice")

# --- A1.5 the ask is single-sourced (D014) ---------------------------------
# The banner, both stat cards, the lede and the flow strip must render from one
# shape. They drifted: the banner said "approve the 3 actions" while the cards
# counted 4 option ROWS. actions_this_cycle may now appear ONLY in the fallback
# inside that shared shape's definition.
raw_uses = len(re.findall(r"theAsk\.actions_this_cycle", SRC))
check("A1.5 the ask is single-sourced — no surface reads the raw row count",
      raw_uses <= 2, "%d raw reads of theAsk.actions_this_cycle (expected <= 2, "
      "both inside the askActs/askRows fallback)" % raw_uses, owner="D014")
check("A1.5 the shared ask shape exists",
      "const askActs" in SRC and "const askTwoPart" in SRC, owner="D014")

# --- A1.1 the executive summary counts the register's objects (D001) -------
# It counted the eight domains' engine alignments while the register enumerated
# six position commitments, so "5 sit below" could not be reconciled against the
# rows. Commitments are the countable thing; areas are coverage.
concl = section_of(SRC, 'label="What this paper concludes"', "</${RrCard}>")
concl = concl or section_of(SRC, 'label="What this paper concludes"', "rr-toc")
check("A1.1 exec conclusions count commitments, not domain alignments",
      'commitments.filter(c => c.kind === "position")' in concl
      and not re.search(r"domains\.filter\([^)]*alignment", concl),
      "the conclusions card still counts domains by alignment", owner="D001")

# --- A1.4 the template contains no arithmetic in count contexts ------------
# Counts are read-only from the commitments array. A "+ 1" or "- 2" against a
# count in the template is a second derivation path and will drift from the
# register. (Subtraction to compute a REMAINDER is legitimate and named.)
count_math = re.findall(r"(?:commitments|gaps|holding|unevid)\.length\s*[-+*/]\s*\d", SRC)
check("A1.4 no arithmetic on commitment counts in the template",
      not count_math, count_math[:3], owner="A1.4")

# --- A5.1 chart constants derive from config, never literals ---------------
check("A5.1 the market band comes from the payload, not a literal",
      "al.market_band" in SRC, "chart band is not payload-derived", owner="A5.1")

# --- A3.1 the suppression floor is derived, never restated (D019) ----------
check("A3.1 the suppression floor is not hardcoded in the document",
      not re.search(r"fewer than\s*5\s*organisation", SRC),
      "the floor's value is written as a literal", owner="D019")
check("A3.1 the suppression floor renders from the payload",
      "al.suppression_floor" in SRC, owner="D019")

# --- A2.1 the ruled provenance line reaches the artefact (D002) ------------
check("A2.1 the ruled pool line renders on the cover and in the foot",
      SRC.count("al.pool_footer") >= 2,
      "pool_footer renders %d time(s); the ruling wants cover + foot" % SRC.count("al.pool_footer"),
      owner="D002")

# --- FOOT_RE lockstep: the verifier must match the footer it verifies ------
# Renaming the page mark ("lumi · N of M" -> "Page N of M") silently blinded the
# pagination verifier once; the two forms are now asserted together.
VSRC = open(VERIFIER).read()
foot_re = re.search(r"FOOT_RE\s*=\s*re\.compile\(r\"(.+?)\"\)", VSRC)
page_mark = re.search(r'class="pack-pageno">([^<$]*)\$\{page\}([^<$]*)\$\{total\}', SRC)
ok_lock = False
if foot_re and page_mark:
    probe = (page_mark.group(1) + "7" + page_mark.group(2) + "9").strip()
    ok_lock = re.search(foot_re.group(1), probe) is not None
check("A8.4 verifier FOOT_RE matches the document's own page mark",
      ok_lock, "footer form and verifier regex have drifted apart", owner="verifier-lockstep")

# ---------------------------------------------------------- v3.1 additions --
# Each owns a defect the v3.1 review found in the shipped build. Where a check
# would encode a ruling David has not made, it is advisory and says which ruling.

# --- A1.5 the plan renders the LIBRARY's description, never stored prose (D032)
check("A1.5 the plan renders lever descriptions from the live library",
      "descOf[a.title]" in SRC,
      "the plan still prints the stored action prose as the lever's description — a plan "
      "built before a library repair then carries superseded reward content", owner="D032")

# --- A4.7 the htm newline trap, which is a typography defect in disguise ----
# `${` on its own line after a word collapses to "the area.Written commentary".
newline_expr = re.findall(r"[a-z]\.\s*\n\s*\$\{_?[a-zA-Z]", SRC)
check("A4.7 no template expression opens a line directly after a sentence",
      not newline_expr, newline_expr[:2], owner="D039/htm")

# --- A6 no dangling promise of options (D026, D027) ------------------------
check("A6 the 'options follow below' clause is gated on the options branch",
      "_allLev.length ? \", and the options against them follow below.\"" in SRC,
      "the clause is unconditional", owner="D027")
check("A6 the 'Options above…' caption is gated on options existing",
      re.search(r"findings \|\| \[\]\)\.some\(f =>", SRC) is not None,
      "the caption renders unconditionally", owner="D026")

# --- D037 the cover addressee claims nothing unless a body was named --------
check("D037 the cover addressee is derived, never defaulted",
      "ver.approver_body" in cover and '"The Board"' not in cover,
      "the cover still falls back to an addressee the approval record contradicts",
      owner="D037")

# --- D047 empty Part A boxes are suppressed, not printed --------------------
check("D047 empty principles/constraints render as a line, not as cards",
      "(doc.principles || []).length ? html`" in SRC, owner="D047")

# --- A5.3 ordinal aims as a bracket — ADVISORY, pending David's ruling -----
check("A5.3 ordinal aim renders as a bracket from the band edge, not a point",
      "RR_AIM_BRACKET" in SRC,
      "still plots a three-point stance as a percentile point (lead -> P82.5). "
      "PENDING RULING R-B on the review sheet — advisory until ruled.",
      owner="D005", advisory=True)


# ================================================================ A4 · DATA ==
print("\n=== A4 · the content libraries (David-owned JSON) ===")
levers = json.load(open(LEVERS))["levers"]
rules = json.load(open(RULES))["rules"]

try:
    import claude_api
    DIRECTIVE_RE, LEGAL_RE = claude_api.DIRECTIVE_RE, claude_api.LEGAL_RE
except Exception as e:                              # pragma: no cover - import guard
    print("  SKIP  language guards — claude_api did not import (%s)" % e)
    DIRECTIVE_RE = LEGAL_RE = None

LEVER_TEXT_FIELDS = ("name", "what_it_is", "typical_shape", "trade_off")


def lever_strings():
    for l in levers:
        for f in LEVER_TEXT_FIELDS:
            if l.get(f):
                yield l["lever_id"], f, l[f]
    for r in rules:
        for f in ("commitment", "statement", "rationale"):
            if r.get(f):
                yield r["rule_id"], f, r[f]


# --- A4.1 the language guards cover the library, not just model output ------
# DIRECTIVE_RE guards eight model validators and covered none of the lever text
# that prints verbatim in the document's biggest tables.
if DIRECTIVE_RE is not None:
    directive_hits = [(i, f, s[:60]) for i, f, s in lever_strings() if DIRECTIVE_RE.search(s)]
    legal_hits = [(i, f, s[:60]) for i, f, s in lever_strings() if LEGAL_RE.search(s)]
    check("A4.1 no directive language in the lever/rule libraries",
          not directive_hits, directive_hits[:3], owner="D016")
    check("A4.1 no legal adjudication in the lever/rule libraries",
          not legal_hits, legal_hits[:3], owner="D016")

# --- A4.6 one lever, one description (D015) --------------------------------
by_name = {}
for l in levers:
    by_name.setdefault(l["name"].strip().lower(), set()).add((l.get("what_it_is") or "").strip())
dupes = {n: v for n, v in by_name.items() if len(v) > 1}
check("A4.6 one lever name renders one description",
      not dupes, list(dupes)[:3], owner="D015")

# --- A4.4 no vendor, product or provider names ------------------------------
VENDORS = ("aviva", "legal & general", "bupa", "vitality", "unum", "peppy", "headspace",
           "calm", "smart pension", "nest", "cushon", "workday", "sap", "oracle")
# word-boundaried: "sap" matched inside "disappoints" and a gate that cries wolf
# gets muted, which is the failure mode this whole file exists to prevent
vendor_hits = [(i, f, v) for i, f, s in lever_strings() for v in VENDORS
               if re.search(r"\b%s\b" % re.escape(v), s, re.I)]
check("A4.4 no vendor or provider names in the libraries", not vendor_hits, vendor_hits[:3])

# --- A4.3 forecast language — ADVISORY (D017) ------------------------------
FORECAST = re.compile(r"\b(will\s+\w+|may\s+\w+\s+in\s+future|expected to|announced\s+\w+\s+changes"
                      r"|from\s+April)\b", re.I)
fc = [(i, f, s[:70]) for i, f, s in lever_strings() if FORECAST.search(s)]
check("A4.3 forward-looking claims carry a date and a source",
      not fc, "%d unsourced forecast phrase(s): %s" % (len(fc), fc[:2]),
      owner="D017", advisory=True)

# --- every lever states its downside (the trade-off column is the doctrine) --
no_trade = [l["lever_id"] for l in levers if not (l.get("trade_off") or "").strip()]
check("A4 every lever states a trade-off", not no_trade, no_trade[:5])


# ================================================================== A2 · DB ==
print("\n=== A2/A3 · live figures (LUMI_DB) ===")
try:
    import app as A
    from aggregate import SUPPRESSION_FLOOR
    conn = A.get_conn()
    pool = A.get_meta("peer_pool", {}) or {}
    stated = pool.get("responding_orgs") or 0
    live = conn.execute("SELECT COUNT(DISTINCT org_id) FROM answers").fetchone()[0]
    # A2.3 — the pool figure the artefact prints must be the pool that exists.
    # "220" outlived the pool's growth to 270 on every stale surface in the estate.
    check("A2.3 the stated pool size equals the live answering-org count",
          stated == live, "meta says %s, DB has %s" % (stated, live), owner="D002")
    check("A3.1 the suppression floor is a single derived constant",
          isinstance(SUPPRESSION_FLOOR, int) and SUPPRESSION_FLOOR >= 3,
          SUPPRESSION_FLOOR, owner="D019")
except Exception as e:
    print("  SKIP  live-figure checks — %s" % e)


# ================================================================= A1 · PDF ==
# Only with --pdf. These are the reconciliation assertions the spec puts first:
# they read the artefact a member receives, not the code that made it.
if "--pdf" in sys.argv:
    path = sys.argv[sys.argv.index("--pdf") + 1]
    print("\n=== A1/A2 · the rendered artefact (%s) ===" % os.path.basename(path))
    import fitz
    doc = fitz.open(path)
    pages = [" ".join(doc[i].get_text().split()) for i in range(doc.page_count)]
    text = " ".join(pages)

    # A2.1 — the ruled line, verbatim, on the cover AND in the running foot
    ruled = re.search(r"Comparison pool: (\d+) UK organisation profiles\. "
                      r"See lumihr\.co\.uk methodology for sources\.", text)
    check("A2.1 the ruled provenance sentence appears verbatim", bool(ruled), owner="D002")
    check("A2.1 the pool fact also appears on the cover",
          "UK organisation profiles" in pages[0], owner="D002")

    # A2.4 — no vendor mark on the member's own cover
    check("A2.4 the cover names no vendor",
          not re.search(r"\blumi\b", pages[0], re.I), owner="D004")

    # A4.5 / A4.7 — the leaks that shipped twice
    check("A4.5 'domain' appears nowhere in the artefact",
          not re.search(r"\bdomains?\b", text, re.I), owner="D020")
    check("A4.7 no sentence terminal before an em-dash",
          not re.search(r"\.\s+—", text), re.findall(r"\S+\.\s+—\s+\S+", text)[:2], owner="D025")

    # A1.1/A1.2/A1.3 — the register IS the reconciliation
    # anchored on the register's NAME, not on the sentence's adjectives — the frame
    # sentence is editable prose and a brittle anchor turns an edit into a red gate
    m_tot = re.search(r"(\d+) in all, listed[^.]*The commitments in full", text)
    m_off = re.search(r"The commitments in full\. (\d+) (?:is|are) off strategy", text)
    if m_tot and m_off:
        total, off = int(m_tot.group(1)), int(m_off.group(1))
        hold = re.search(r"; (\d+) hold", text)
        holdn = int(hold.group(1)) if hold else -1
        check("A1.3 the status tally closes: off + holding == total",
              off + holdn == total, "%d + %d != %d" % (off, holdn, total), owner="D001")
        rows = len(re.findall(r"(?:Short of the stated aim|Past the stated aim|Contradicted"
                              r"|Holding|Awaiting evidence)", text))
        check("A1.2 the register enumerates every commitment it claims",
              rows == total, "%d status rows for %d commitments" % (rows, total), owner="D001")
    else:
        check("A1.1 the exec summary states the commitment frame", False,
              "could not locate the reconciling sentence", owner="D001")

    # A1.5 — the ask says the same thing in all three places
    ask_pg = next((p for p in pages if "DECISION SOUGHT" in p), "")
    banner = re.search(r"DECISION SOUGHT (.{0,180}?) (?:\d+ ACTION|The board)", ask_pg)
    stat = re.search(r"(\d+) ACTIONS? THIS CYCLE", ask_pg)
    if banner and stat:
        # the banner renders "the 3 actions" or, at one, "the action" — a numeral-only
        # parser failed a document that was telling the truth, which is the exact
        # failure mode the spec's v1 post-mortem warns about
        n_banner = re.search(r"approve the (\d+|one) actions?\b", banner.group(1))
        got = None if not n_banner else (1 if n_banner.group(1) in ("one",) else int(n_banner.group(1)))
        if got is None and re.search(r"approve the action\b", banner.group(1)):
            got = 1
        check("A1.5 the banner's count equals the stat card's count",
              got == int(stat.group(1)),
              "banner %r vs card %s" % (banner.group(1)[-45:], stat.group(1)), owner="D014")
        two_part = "Re-approve" in banner.group(1) or "re-approve" in banner.group(1)
        check("A1.5 a two-part ask is two-part in the body too",
              (not two_part) or re.search(r"asked for two decisions", ask_pg) is not None,
              "banner seeks re-approval; the body states one ask", owner="D014")

    # --- v3.1 artefact-level checks ---------------------------------------
    # D033 the singular grammar leak
    check("D033 no 'one of 1' grammar leak", not re.search(r"one of 1\b", text), owner="D033")
    # D066 no tag the library does not carry
    check("D066 no unevidenced 'self-funding' claim",
          "self-funding" not in text, owner="D066")
    # D029 a signal's own name is not repeated inside its detail
    dupes = re.findall(r"([A-Z][a-z]+(?: [a-z]+){1,4}) — \(\1", text)
    check("D029 no signal name repeated inside its own detail", not dupes, dupes[:2], owner="D029")
    # D028 every peer-median comparison carries both sides
    bare = re.findall(r"vs the peer median", text)
    check("D028 no comparator-less peer-median comparison", not bare,
          "%d signal detail(s) print 'vs the peer median' with no number" % len(bare), owner="D028")
    # D052 the cover states the divergence where it asserts both labels
    check("D052 the cover says the stated peer group is not the basis",
          ("not the basis for the reads" in pages[0]) if "Stated peer group" in pages[0] else True,
          owner="D052")
    # D042 one canonical area order — the contents and the chart agree
    check("D042 area order is the stored taxonomy order",
          "_q_all.values() if q.sub_power" in open(os.path.join(HERE, "app.py")).read(),
          "the alignment endpoint still orders areas by first appearance", owner="D042")

    # A6.5 — people, not logins. ADVISORY: the record IS an account today, and
    # rendering a name needs a captured field. Held for David (R-U).
    check("A6.5 approvers render as a person, not an account identifier",
          not re.search(r"Approved by [\w.]+@", text),
          "the approval record still shows a login", owner="D036", advisory=True)
    # D034 — ADVISORY pending R-V/engine work: gap attribution is lost because the
    # plan drops alt_group and candidates dedupe globally by (category, lever_id).
    check("D034 the schedule's gap count matches the register's off-strategy count",
          False,
          "plan actions carry no gap key (alt_group is dropped by both plan builders), "
          "so per-area gap counts are re-derived from lever names and collapse to one. "
          "Engine change — held with the diagnostic on the ruling sheet.",
          owner="D034", advisory=True)


# ================================================================== verdict ==
print("\n--- judgment, not assertion ---")
for d, why in (("D011", "a cover metric that needs two disclaimers — editorial"),
               ("D022", "eight areas landing 29th-39th — engine investigation, ruling R-C"),
               ("D023", "the plan's speed-vs-value ordering — editorial ruling R-F")):
    print("  NOTE  %s: %s" % (d, why))

print("\n%d checks, %d failure(s), %d advisory" % (NCHECK[0], len(FAILS), len(WARNS)))
for n, d in FAILS:
    print("  FAIL %s — %s" % (n, str(d)[:200]))
sys.exit(1 if FAILS else 0)
