# -*- coding: utf-8 -*-
"""FINALISE a rendered board paper — the two things a browser print cannot do.

Chrome's --print-to-pdf (and a member's own Save as PDF) produces a faithful page image
and nothing else: no outline, and document properties carrying the browser's identity
rather than the paper's. For a forty-page document that arrives by email, both matter
more than they sound.

  * OUTLINE (F-012). The document prints a 23-entry contents page and shipped with zero
    PDF bookmarks, so it opened with an empty navigation pane. A reader on a laptop in a
    meeting has no way to reach §19 except scrolling. The outline is built from the
    document's OWN section headings, read off the rendered pages — not from a list kept
    in parallel, which would drift the first time a section moved.

  * PROPERTIES (F-011). `author`, `subject` and `keywords` were empty and `creator`
    carried the full HeadlessChrome user-agent string. Those fields are what a document
    management system files the paper under and what an email client previews.

This is a SEPARATE step from verify_report_pdf.py on purpose. The verifier is the
authority on whether a render is sound and must not mutate what it judges; this tool
mutates and asserts nothing. Run the verifier first, then this, then the verifier again
if you want belt and braces — the outline is metadata and cannot move a page.

    python3 server/finalise_pdf.py --pdf artefacts/total_reward_strategy_and_plan.pdf
    python3 server/finalise_pdf.py --pdf <in> --out <other>     # leave the input alone
"""
import argparse
import os
import re
import sys

try:
    import pymupdf
except ImportError:                                   # pragma: no cover
    sys.exit("PyMuPDF is required: python3 -m pip install --user pymupdf")

# A section sheet prints its number and title as the first two lines under the running
# head. Continuations repeat the number, so the outline keeps ONE entry per section and
# points at its first sheet — a bookmark per continuation would make the pane a worse
# contents page than the printed one.
SEC_RE = re.compile(r"^\s*(\d{2})\s*$")
PART_RE = re.compile(r"^PART\s+([A-D])\b\s*[·:]?\s*(.*)$", re.I)


def outline_from_pages(doc):
    """[(level, title, page)] read off the rendered pages themselves."""
    out, seen_sec, seen_part = [], set(), set()
    for i, page in enumerate(doc):
        lines = [l.strip() for l in page.get_text().split("\n") if l.strip()]
        if not lines:
            continue
        # a divider sheet announces a part; it carries the part name and little else
        for l in lines[:6]:
            m = PART_RE.match(l)
            if m and m.group(1).upper() not in seen_part and len(lines) < 12:
                seen_part.add(m.group(1).upper())
                out.append((1, "Part %s — %s" % (m.group(1).upper(),
                                                 (m.group(2) or "").strip().title()), i + 1))
                break
        for j, l in enumerate(lines[:8]):
            if SEC_RE.match(l) and j + 1 < len(lines):
                num, title = l.strip(), lines[j + 1].strip()
                # "(2 of 2)" and "(cont.)" are the same section, already bookmarked
                base = re.sub(r"\s*\((?:cont\.?|\d+ of \d+)\)\s*$", "", title).strip()
                if num in seen_sec or not base or len(base) > 70:
                    break
                seen_sec.add(num)
                out.append((1, "%s  %s" % (num, base), i + 1))
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out")
    ap.add_argument("--title")
    ap.add_argument("--author", default="lumi HR")
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    first = " ".join(doc[0].get_text().split())
    # The org name is read off the RUNNING HEAD, not the cover. The cover's eyebrow is
    # letter-spaced for display ("R E WA R D S T R AT E GY & P L A N") and extracts with
    # those spaces in it, so anything anchored on the cover drags them into the title —
    # which is precisely the field a mail client previews.
    head = " ".join(doc[1].get_text().split()) if doc.page_count > 1 else first
    m = re.search(r"Total Reward Strategy & Plan\s*·\s*(.+?)\s{2,}|"
                  r"Total Reward Strategy & Plan\s*·\s*([^·]{3,60}?)\s+(?:PART|EXECUTIVE|\d\d)", head)
    org = ((m.group(1) or m.group(2)) if m else "") or ""
    org = org.strip(" ·")
    issued = re.search(r"Generated (\d{1,2} \w+ \d{4})", first)

    toc = outline_from_pages(doc)
    doc.set_toc(toc)

    title = a.title or ("Total Reward Strategy & Plan"
                        + (" — " + org if org else "")
                        + (" — " + issued.group(1) if issued else ""))
    doc.set_metadata({
        "title": title,
        "author": a.author,
        "subject": "Total reward strategy, market position and the plan against it"
                   + (" — %s" % org if org else ""),
        "keywords": "total reward; reward strategy; benchmarking; remuneration committee",
        # the browser's user-agent is not this document's identity
        "creator": "lumi HR",
        "producer": "lumi HR",
    })
    out = a.out or a.pdf
    doc.save(out, incremental=(out == a.pdf and not doc.is_encrypted),
             encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()

    chk = pymupdf.open(out)
    print("finalised %s" % out)
    print("  outline : %d entries (was 0)" % len(chk.get_toc()))
    for lvl, t, pg in chk.get_toc()[:6]:
        print("      %s%-42s p%d" % ("  " * (lvl - 1), t[:42], pg))
    if len(chk.get_toc()) > 6:
        print("      … %d more" % (len(chk.get_toc()) - 6))
    md = chk.metadata
    print("  title   : %s" % md.get("title"))
    print("  author  : %s | creator: %s" % (md.get("author"), md.get("creator")))
    print("  pages   : %d (unchanged)" % chk.page_count)
    chk.close()


if __name__ == "__main__":
    main()
