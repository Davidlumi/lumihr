# -*- coding: utf-8 -*-
"""Verify the reward document as a PDF — the artefact a member actually receives.

WHY THIS EXISTS (2026-08-16). Page fitting was verified for weeks by measuring the
SCREEN render against A4 and reporting "none over A4". That was true of a rendering
nobody receives: @media print changes both variables that decide pagination —

    .pack-page                        { min-height: 296mm }   /* screen: 285mm */
    .pack-page p, li, td, th          { font-size: 10.5pt }   /* different type size */

so the printed document paginates differently from the one being measured. It went
unnoticed until David exported a PDF and it ran to 41 physical pages while its own
footers said "of 40" — the last section had split, and every page reference after it
was wrong. A contents that points at the wrong page is the one defect a consultancy
document cannot survive.

This renders the real thing through headless Chrome (the same Skia/PDF pipeline the
member's Save-as-PDF uses) and asserts what the screen cannot tell you:

  * the physical page count equals the count the footers claim
  * footer indices run 1..N with no gap, repeat or missing footer
  * no page is a widow — content that spilled off the sheet before it
  * every contents entry points at a page whose heading matches

    python3 server/verify_report_pdf.py --url http://localhost:8073/harness.html
    python3 server/verify_report_pdf.py --pdf /path/to/exported.pdf   # check an export
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/Applications/Chromium.app/Contents/MacOS/Chromium",
          "/usr/bin/chromium", "/usr/bin/google-chrome")

FOOT_RE = re.compile(r"lumi\s*·\s*(\d+)\s*of\s*(\d+)")


def find_chrome():
    for c in CHROME:
        if os.path.exists(c):
            return c
    return None


def render(url, out):
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("no Chrome/Chromium found — cannot render the real PDF")
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=8000", "--print-to-pdf=" + out, url],
                   check=True, capture_output=True)
    return out


def check(pdf):
    try:
        import fitz
    except ImportError:
        raise SystemExit("PyMuPDF not available — cannot inspect the PDF")
    d = fitz.open(pdf)
    fails, notes = [], []
    pages = [d[i].get_text() for i in range(d.page_count)]

    # 1. does the document's own page count match the paper it produced?
    claimed = None
    for t in pages:
        m = FOOT_RE.search(t)
        if m:
            claimed = int(m.group(2))
            break
    if claimed is None:
        fails.append("no page footer found at all — the running foot is not printing")
    elif claimed != d.page_count:
        fails.append("the document says %d pages and produced %d — a section has split, "
                     "and every contents reference past the split is wrong"
                     % (claimed, d.page_count))

    # 2. footers must run 1..N: a missing one is a page that overflowed its sheet
    seen = []
    for i, t in enumerate(pages):
        m = FOOT_RE.search(t)
        if not m:
            fails.append("page %d carries no footer — it is a spill from the sheet before it"
                         % (i + 1))
            continue
        seen.append((i + 1, int(m.group(1))))
    for phys, printed in seen:
        if phys != printed:
            fails.append("physical page %d prints the number %d" % (phys, printed))
            break

    # 3. page size really is A4
    r = d[0].rect
    mm = (round(r.width / 72 * 25.4), round(r.height / 72 * 25.4))
    if mm != (210, 297):
        fails.append("page size is %dx%dmm, not A4" % mm)

    # 4. contents entries must point at the page whose heading matches.
    # PyMuPDF splits a contents row across text lines ("02 What we're asking the
    # board to" / "approve" / "3"), so a numbered title accumulates until a bare
    # page-number line closes it; the old single-line form still matches first.
    # This parser once went silently vacuous on that layout change — "0 contents
    # entries checked" read as a pass — so finding too few rows is now a FAILURE,
    # not a note (the silent-skip lesson, 2026-08-16).
    toc = []
    cur = None
    for line in pages[1].split("\n"):
        s = line.strip()
        m = re.match(r"^(\d{2})\s+(.{3,60}?)\s+(\d{1,3})$", s)
        if m:
            toc.append((m.group(2).strip(), int(m.group(3))))
            cur = None
            continue
        m = re.match(r"^(\d{2})\s+(\D.{2,})$", s)
        if m:
            cur = m.group(2).strip()
            continue
        if cur and re.match(r"^\d{1,3}$", s):
            toc.append((cur, int(s)))
            cur = None
            continue
        if cur and s and not re.match(r"^\d", s):
            cur += " " + s
    if len(toc) < 3:
        fails.append("contents parser matched only %d row(s) — the contents check is "
                     "not actually running against this layout" % len(toc))
    bad = 0
    for title, page in toc:
        if 1 <= page <= d.page_count:
            # the WHOLE page, not its first 400 chars: two sections legitimately share
            # a sheet (body2), so the second section's heading sits mid-page
            head = " ".join(pages[page - 1].split()).lower()
            key = title.lower()[:18]
            if key and key not in head:
                bad += 1
                if bad <= 3:
                    fails.append("contents sends '%s' to page %d, which is not that section"
                                 % (title, page))
    notes.append("%d contents entries checked" % len(toc))

    # 5. how much of each page is used — a half-empty page reads as unfinished
    thin = []
    for i in range(d.page_count):
        blocks = [b for b in d[i].get_text("blocks") if b[4].strip()
                  and b[3] < d[i].rect.height - 90]
        if not blocks:
            continue
        bottom = max(b[3] for b in blocks)
        pct = (bottom - 60) / (d[i].rect.height - 90 - 60) * 100
        if pct < 55:
            thin.append((i + 1, round(pct)))
    notes.append("pages under 55%% full: %d of %d %s"
                 % (len(thin), d.page_count, [p for p, _ in thin][:12]))
    return fails, notes, d.page_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--pdf")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    if not (a.url or a.pdf):
        raise SystemExit("give --url to render one, or --pdf to check an export")
    path = a.pdf
    tmp = None
    if a.url:
        tmp = os.path.join(tempfile.gettempdir(), "lumi_report_check.pdf")
        path = render(a.url, tmp)
    fails, notes, n = check(path)
    print("PDF: %s — %d pages" % (os.path.basename(path), n))
    for note in notes:
        print("  note: " + note)
    for f in fails:
        print("  FAIL: " + f)
    if tmp and not a.keep:
        pass                      # left in place; it is the evidence for the run
    print("%d failure(s)" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
