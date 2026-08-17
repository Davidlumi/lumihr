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
import ast
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

# --- A1.5 the plan renders the LIBRARY's description, never stored prose (D032/D068)
# The v3.1 form of this check was VACUOUS: it asserted the library description was
# rendered, which stayed true while the stored prose rendered beside it. A check that
# can pass while the printed page contradicts itself proves nothing. It now asserts the
# stored `why` is not rendered at all for a library-matched action — composition is the
# only path, not the first of two — and the PDF half (below) asserts absence in the text.
check("A1.5 the plan renders lever descriptions from the live library",
      "descOf[a.title]" in SRC, owner="D032")
check("A1.5 the stored plan prose is not rendered beside the library description",
      "if (!inLib) return html" in SRC and "planFirstOfGap" in SRC,
      "the renderer still emits the stored why for a library-matched action, so a stale "
      "plan prints both descriptions three lines apart", owner="D068")

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

# --- G61 (v3.3) no two library entries share an action signature (D083) -----
# D068's class at LIBRARY scope: two entries describing one action will contradict
# the moment either is edited. Signature = the content words of what_it_is, so a
# paraphrase collides with its twin. ADVISORY: merging is a library-content change
# and David owns that file — the check exists to hold the finding, not to force it.
_STOP = set("a an the and or of to in on for with by is are be that where it its your you"
            " from as at not no this those these their them they we our".split())


def _sig(s):
    return frozenset(w for w in re.findall(r"[a-z]+", (s or "").lower()) if w not in _STOP)


_sigs = {}
_collide = []
for l in levers:
    s = _sig(l.get("what_it_is"))
    if not s:
        continue
    for other, osig in _sigs.items():
        inter = len(s & osig)
        if inter and inter / float(min(len(s), len(osig))) >= 0.6:
            _collide.append((other, l["lever_id"]))
    _sigs[l["lever_id"]] = s
# v3.3-A §4: DOWNGRADED FROM CHECK TO CANDIDATE-SURFACER. It cannot distinguish
# "shares vocabulary" from "is the same lever", so it must neither block nor clear —
# whether two entries name one action is David's judgement. It emits a ranked list
# for his review and returns no verdict. NCHECK is not incremented; nothing here can
# pass or fail. (It earned its place: it found WEL-FRAMEWORK / BEN-BENEFITS-FRAMEWORK,
# a real duplicate the review had not named, and it does NOT find PAY-BANDS /
# GOV-RANGES-INTERNAL, which the review did — precisely the limitation above.)
if _collide:
    print("\n  -- G61 candidate-surfacer (no verdict): near-duplicate library pairs --")
    for a, b in sorted(_collide, key=lambda p: (p[0], p[1])):
        _ov = len(_sigs[a] & _sigs[b]) / float(min(len(_sigs[a]), len(_sigs[b])))
        print("     %.0f%% shared vocabulary  %s  <->  %s" % (_ov * 100, a, b))
    print("     Judgement, not a finding — for the D083 pack. David rules the merge.")

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
    # D029 a signal's own name is not repeated inside its detail. The v3.1 regex
    # required "LABEL — (LABEL" adjacently and the live form is
    # "LABEL — 93rd percentile (LABEL — 100/100 …)" — so the check reported green over
    # the defect on p15. Match the label, then its own repeat anywhere in the same
    # parenthetical, which is what a reader actually sees.
    dupes = [m.group(1) for m in re.finditer(r"([A-Z][a-z]+(?: [a-z]+){1,5}) — [^()]{0,80}\(\1\b", text)]
    check("D029 no signal name repeated inside its own detail", not dupes, dupes[:2], owner="D029")

    # D068 — the assertion that owns the regression, on the RENDERED TEXT. A field-level
    # equality cannot see a render-level duplication: the corpus is every superseded
    # description this library has carried, asserted absent anywhere in the document.
    SUPERSEDED = [
        # pre-OpRA salary sacrifice, repaired 2026-08-16; carried into a board paper by a
        # stored plan built before the repair (v3.2 D068)
        "pension, cars, technology",
    ]
    ghosts = [g for g in SUPERSEDED if g.lower() in text.lower()]
    check("D068 no superseded lever description survives anywhere in the artefact",
          not ghosts, ghosts, owner="D068")

    # D069 — every rendered sentence starts uppercase (the check the v3.1 fix needed)
    lowers = [s[:60] for p in pages for s in re.split(r"(?<=[.!?]) +", p)
              if re.match(r"^(no|the|a|an|and|but|it|they|this|that|every|each) [a-z]", s)
              and len(s) > 45]
    check("D069 no rendered sentence opens lowercase", not lowers, lowers[:2], owner="D069")

    # D072 — plural set-cardinality copy against a single-row exhibit.
    # RESTATED (P0-7f): the old form was `plural present ⟹ singular present somewhere`,
    # which is satisfied by ANY area happening to show one row and fails on a document
    # where every area correctly shows several. It passed for months on that accident
    # and fired the moment the signal resolver was repaired. The invariant is per-area
    # number agreement, and the exhibit header states the shown count — "(2 of 9)".
    d72 = []
    for m in re.finditer(r"What ([A-Z][\w&' ]+?) is flagging \((\d+)(?: of \d+)?\)", text):
        seg = text[m.end():m.end() + 700]
        sing = "The signal above is the most material" in seg
        plur = "The signals above are the most material" in seg
        if not (sing or plur):
            continue                       # this area prints no cardinality note at all
        if (int(m.group(2)) == 1) != sing:
            d72.append("%s shows %s row(s) under the %s wording"
                       % (m.group(1), m.group(2), "singular" if sing else "plural"))
    check("D072 the signal note's number agrees with the rows the exhibit shows",
          not d72, "; ".join(d72), owner="D072", advisory=False)

    # D075 — one noun for the per-metric base wherever a base is counted
    base_nouns = set()
    if re.search(r"\d+ peers each", text): base_nouns.add("peers")
    if re.search(r"\d+ comparable organisations", text): base_nouns.add("comparable organisations")
    if re.search(r"\d+ organisations that answered", text): base_nouns.add("organisations that answered")
    check("D075 one noun for the per-metric base", len(base_nouns) <= 1,
          sorted(base_nouns), owner="D075")
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

    # ================================================== v3.3 · RED-FIRST BLOCK ==
    # G53-G63. These own defects whose FIXES ARE NOT AUTHORISED — the v3.3 review's
    # §0.1 reserves them to David, and D077 has two branches only he can pick. They
    # are added NOW, before any fix, because that review's §0.5 is right: "a check
    # first seen green is not a proof", and Gate A reported 52/0 over three blockers.
    #
    # So each one is expected RED today. They run advisory (they must not fail a
    # suite over unauthorised work) and each names the defect it owns and the ruling
    # it waits on. AS EACH FIX LANDS ITS CHECK FLIPS TO BLOCKING — that flip is the
    # deliverable, not the check's existence.
    print("\n  -- v3.3 red-first block: expected RED until the fixes are ruled --")

    # G53 — no respondent verb bound to the comparison pool (D076)
    RESPONDENT = [r"\banswered it\b", r"\bthat answered\b", r"\bcollection window\b",
                  r"\blast saved\b", r"\bsubmitted\b", r"\bresponded\b",
                  r"organisations that answered"]
    g53 = [m.group(0) for pat in RESPONDENT for m in re.finditer(pat, text, re.I)]
    check("G53 no respondent verb is bound to the comparison pool",
          not g53, "%d hit(s): %s" % (len(g53), sorted(set(g53))[:6]),
          owner="D076", advisory=True)

    # G54 — an against-aim sentence implies a position commitment row, and back (D077)
    AREAS = ["Pay", "Pensions & savings", "Health & protection", "Benefits & lifestyle",
             "Time off & family", "Incentives & recognition", "Wellbeing",
             "Governance & transparency"]
    aim_read, reg_row = set(), set()
    for a in AREAS:
        # the read renderer's sentence sits inside that area's own section.
        #
        # v3.3-A §3: the first implementation matched only DIVERGENT reads ("sits short
        # of / past that aim") and therefore flagged Health & protection — which renders
        # "the live read matches that aim" and holds a register row, i.e. satisfies the
        # spec predicate. That was a check firing on correct behaviour: the mirror image
        # of a check passing over a defect, and more corrosive, because the false
        # positive gets "fixed" by breaking something that works. As written it would
        # have fired on every Holding area in every organisation, forever.
        #
        # The spec predicate is: an area RENDERS AN AIM READ <=> it holds a position
        # commitment row. "matches that aim" is an aim read.
        sec = next((p for p in pages if re.search(r"\d+ " + re.escape(a) + r"\b", p)
                    and "How this reads" in p), "")
        if re.search(r"the live read (sits (short of|past)|matches) that aim", sec):
            aim_read.add(a)
        if re.search(r"You aim [a-z ]+ on " + re.escape(a) + r";", text):
            reg_row.add(a)
    g54 = sorted((aim_read | reg_row) - (aim_read & reg_row))
    check("G54 against-aim read <-> register position row, per area",
          not g54, "asymmetric: %s (read-only: %s | row-only: %s)"
          % (g54, sorted(aim_read - reg_row), sorted(reg_row - aim_read)),
          owner="D077", advisory=True)

    # G55 — the Exhibit 2 note's stated basis reproduces the register total (D077)
    m_note = re.search(r"chart above covers the (\d+) areas", text)
    m_reg = re.search(r"(\d+) in all, listed[^.]*The commitments in full", text)
    m_pos = re.search(r"position for (\d+) of the (\d+) benchmarked areas", text)
    g55_ok = bool(m_note and m_pos) and (m_pos.group(1) == m_note.group(1))
    check("G55 the Exhibit 2 note's basis reproduces the register's position count",
          g55_ok,
          "note counts %s areas; the register holds %s position rows"
          % (m_note.group(1) if m_note else "?", m_pos.group(1) if m_pos else "?"),
          owner="D077", advisory=True)

    # G56 — a single-option approval surface discloses the alternatives (D078)
    ask_pg = next((p for p in pages if "What approval covers" in p), "")
    singles = [ln for ln in re.findall(r"[A-Z][a-z][^·\n]{8,60}", ask_pg)] if ask_pg else []
    g56_ok = ("One of:" in ask_pg) or ("alternatives" in ask_pg.lower())
    check("G56 a single-option approval surface names its alternatives",
          g56_ok and "chosen over" in ask_pg.lower(),
          "the approval page presents options without naming what they were selected "
          "over — the either/or convention exists and is applied only to options that "
          "reached the schedule", owner="D078", advisory=True)

    # G57 — the Findings BUCKET union equals the benchmarked area set (D079).
    # First form of this check asked only whether an area's NAME occurred anywhere in
    # the section, which an above-market card or a passing mention satisfies — it went
    # green over the defect. Bucket membership is what the check is about, so it now
    # reads the three bucket sentences the section actually emits.
    fnd = " ".join(p for p in pages if re.search(r"\d+ Findings", p))
    bucketed = set()
    for a in AREAS:
        if not fnd:
            continue
        in_card = re.search(re.escape(a) + r"[^.]{0,120}(below market|short of|against an?)", fnd, re.I)
        in_track = re.search(r"([^.]*?)\bis tracking with the stated intent|are tracking with the stated intent", fnd)
        in_past = re.search(r"([^.]*?)sits? above a deliberately lower aim", fnd)
        if in_card or (in_track and a.lower() in (in_track.group(0) or "").lower()) \
                or (in_past and a.lower() in (in_past.group(0) or "").lower()):
            bucketed.add(a)
    g57 = [a for a in AREAS if a not in bucketed]
    check("G57 every benchmarked area falls in a Findings bucket",
          not g57, "no bucket carries: %s" % g57, owner="D079", advisory=True)

    # G58 — a priced gap is acted on THIS CYCLE, or its absence is stated (D080).
    # First form accepted the area appearing under any horizon, which "next cycle"
    # satisfies — green over the defect. The finding is that the one number a board
    # can act on has nothing attached to it in the cycle being approved.
    priced_area = "Pensions & savings" if re.search(
        r"Employer pension contribution", text) else None
    now_block = ""
    for p in pages:
        if "Planned actions by horizon" in p:
            m = re.search(r"This cycle(.*?)(Next cycle|Multi-cycle|Generated )", p, re.S)
            if m:
                now_block += " " + m.group(1)
    g58_ok = (not priced_area) or (priced_area.lower() in now_block.lower()) \
        or bool(re.search(r"priced gap[^.]{0,90}(no scheduled action|not scheduled|no action)", text, re.I))
    check("G58 a priced gap is acted on this cycle or its absence is stated",
          g58_ok, "the only priced gap (%s) carries no THIS-CYCLE action and the "
          "document does not say so" % priced_area, owner="D080", advisory=True)

    # G59 — every gap count is split, or accompanied by the split (D081)
    bare = re.findall(r"\b(?:the )?(\d+) gaps?\b(?![^.]{0,60}(?:short or contradicted|past a deliberately))", text)
    check("G59 every gap count carries or accompanies the shortfall/overshoot split",
          not bare, "%d unsplit gap count(s): %s" % (len(bare), bare[:5]),
          owner="D081", advisory=True)

    # G60 — Part C's per-gap option count equals Part B's mapped options (D082)
    m_c = re.search(r"one of (\d+) options against this gap", text)
    partb_opts = len(re.findall(r"\b(?:Flexible benefits allowance|Salary-sacrifice arrangements"
                                r"|Group risk bundle|Voluntary benefits platform"
                                r"|A stated benefits position|Benefits communication and take-up)\b",
                                text))
    check("G60 Part C's per-gap option count matches Part B's mapped options",
          not m_c, "Part C claims %s options against one gap while Part B's exhibit for "
          "that area carries no gap mapping to check it against"
          % (m_c.group(1) if m_c else "?"), owner="D082", advisory=True)

    # G62 — a past-aim area renders no options exhibit (D084)
    past_areas = [a for a in AREAS
                  if re.search(r"You aim [a-z ]+ on " + re.escape(a)
                               + r"; the live read sits past it", text)]
    g62 = []
    for a in past_areas:
        sec = " ".join(p for p in pages if re.search(r"\d+ " + re.escape(a) + r" — what follows", p))
        if sec and re.search(r"Options against the " + re.escape(a) + " gaps", sec, re.I):
            g62.append(a)
    check("G62 a past-aim area renders no options exhibit",
          not g62, "past-aim areas still offering levers: %s (past-aim set: %s)"
          % (g62, past_areas), owner="D084", advisory=True)

    # G63 — every "Your stated answers" row cites a response token (D085)
    rows = re.findall(r"([^|]{0,140}?)Your stated answers", text)
    g63 = [r.strip()[-90:] for r in rows if "your response" not in r.lower()]
    check("G63 every 'Your stated answers' row cites a response",
          not g63, "%d row(s) claim answer-provenance without citing one: %s"
          % (len(g63), g63[:2]), owner="D085", advisory=True)

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


# ============================================ G64 · the signal resolver (P0-7f) ==
# Every other build_signals call site resolves a twin block through pos.block_for.
# The alignment endpoint — the one the strategy document renders from — passed
# `lambda qid: tb and tb(qid)`, and tb is a dict. On all/industry/fte_band cuts the
# expression is falsy for every qid, so five of eight signal mechanisms go dark; on
# twin/group cuts it raises TypeError into a bare except, so the document renders
# with ZERO signals in every area. The demo org's own default_cut is a group.
# This is a source check on purpose: the failure is silent in the artefact — a
# document with no signals looks like an org with nothing to say.
_APP = open(os.path.join(HERE, "app.py")).read()
_align_bs = re.search(r"_all_sigs = signals_mod\.build_signals\((.{0,400}?)\)\n", _APP, re.S)
_args = [a.strip() for a in re.split(r",(?![^()\[\]{}]*[)\]}])",
                                     (_align_bs.group(1) if _align_bs else ""))]
_arg4 = _args[3] if len(_args) > 3 else ""
# the resolver may be inline or bound to a name — follow it either way, so the
# check asserts what the builder RECEIVES, not what this one line happens to read.
_resolver = _arg4
if re.fullmatch(r"[A-Za-z_]\w*", _arg4):
    _bind = re.search(r"\n\s*%s\s*=\s*(.{0,400}?)\n\s*(?:try:|\w+\s*=)" % re.escape(_arg4), _APP, re.S)
    _resolver = _bind.group(1) if _bind else "<%s: gate cannot find its binding>" % _arg4
check("G64 the alignment endpoint resolves twin blocks through pos.block_for",
      bool(_align_bs) and "pos.block_for" in _resolver and not re.search(r"\btb\s*\(", _resolver),
      "the per-domain signal call's resolver is %s — a dict is not callable, and a "
      "falsy resolver silently drops the prevalence/rare mechanisms"
      % " ".join(_resolver.split())[:120],
      owner="P0-7f")

# ====================================== G65 · the swallowed exception (P1-B) ==
# The same try/except absorbed a raised builder failure into `_all_sigs = []` and let
# the document render — eight areas silently flagging nothing, over one warning line.
# The catch may still exist (it names the org and the cut, which the last-resort
# handler cannot), but it must END IN A RAISE, not an empty list.
#
# READ THE TREE, NOT THE TEXT (2026-08-17, and this check is its own cautionary tale).
# The first form of G65 asked `"raise" in <except body text>`. The body's own comment
# says "...the twin/group path is what raised here before P0-7f" — so the substring was
# satisfied by prose, and a mutant that deleted the raise and returned a blank document
# still went green. The word appearing near the code is not the code. Parsing app.py
# means comments do not exist as far as this check is concerned, and the handler either
# contains a Raise statement or it does not.
_APP_AST = ast.parse(_APP)
_handlers, _sig_try = [], None
for _n in ast.walk(_APP_AST):
    if isinstance(_n, ast.Try) and "signals_mod.build_signals" in ast.unparse(_n.body):
        _sig_try, _handlers = _n, _n.handlers
_h_body = _handlers[0].body if _handlers else []
_raises = [s for h in _handlers for s in ast.walk(ast.Module(body=h.body, type_ignores=[]))
           if isinstance(s, ast.Raise)]
_blanks = [s for h in _handlers for s in ast.walk(ast.Module(body=h.body, type_ignores=[]))
           if isinstance(s, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == "_all_sigs" for t in s.targets)]
check("G65 a signal-builder failure fails the request, it does not blank every area",
      bool(_sig_try) and bool(_raises) and not _blanks,
      "the handler %s" % ("could not be located in app.py's tree" if not _sig_try
                          else "assigns _all_sigs (%s) and returns a document"
                               % "; ".join(ast.unparse(b) for b in _blanks) if _blanks
                          else "contains no raise statement"),
      owner="P1-B")
# and the log must pass the org and the cut AS ARGUMENTS — a format string mentioning
# them, with nothing supplied, reads identically to the gate and tells the operator
# nothing. So: walk the handler's log call and read what it actually hands over.
_log_args = []
for _h in _handlers:
    for _s in ast.walk(ast.Module(body=_h.body, type_ignores=[])):
        if (isinstance(_s, ast.Call) and isinstance(_s.func, ast.Attribute)
                and isinstance(_s.func.value, ast.Name) and _s.func.value.id == "log"):
            # args[0] is the format string; everything after it is what the operator
            # actually gets. ast.unparse normalises quoting, so compare unquoted.
            _log_args += [ast.unparse(a).replace('"', "'") for a in _s.args[1:]]
_want = {"org": "org['org_id']", "cut dim": "cut.get('dim')", "cut value": "cut.get('value')"}
_missing = [k for k, v in _want.items() if not any(v in a for a in _log_args)]
check("G65b the failure log is passed the org and the cut as arguments",
      bool(_handlers) and not _missing,
      "the handler's log call does not receive: %s (it passes %s) — a cut-shaped failure "
      "logged without its cut is not reproducible" % (", ".join(_missing) or "—", _log_args),
      owner="P1-B")


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
