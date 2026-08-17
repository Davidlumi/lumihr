# -*- coding: utf-8 -*-
"""VERIFY THE DOCUMENT ON EVERY CUT SHAPE, not just the one it is usually read on.

The print verifier has only ever been pointed at the all-peers render, because that is
what the harness captures. F-000 was found by hand-rendering a group cut and noticing 41
physical pages behind a footer claiming 40 — and the scoping pass then reported the
industry cut failing too. Neither was measured by anything that runs on its own.

This is that measurement. For each cut shape it captures the live payloads, writes the
harness fixture, renders through the same headless-Chrome path as verify_report_pdf.py,
and verifies. A cut that cannot be rendered is reported, never skipped silently.

    python3 server/verify_cuts.py --base http://localhost:8071 --harness http://localhost:8073/harness_full.html

It needs a throwaway server (payloads) and a harness server (the page). It NEVER touches
the live database: the caller points --base at the throwaway, exactly as the rig does.

Deliberately a separate tool. run_gates.sh runs without a browser today, which is why
Gate A's artefact half is invoked with --pdf outside the suite; wiring a Chrome render
into the suite is its own decision, and this tool is what that decision would call.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))

# Every shape parse_cut accepts (app.py:786-808). "twin" and "group" are the two the
# whole gate suite never exercises — the Arm C finding — so they are the point of this.
SHAPES = [
    ("all", {}),
    ("industry", {"cut": "industry"}),
    ("fte_band", {"cut": "fte_band"}),
    ("twin", {"cut": "twin"}),
    ("group", {"cut": "group"}),          # cut_value filled from the org's own groups
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="throwaway API server, e.g. http://localhost:8071")
    ap.add_argument("--harness", required=True, help="harness page URL")
    ap.add_argument("--fixture", required=True, help="canned.json the harness reads")
    ap.add_argument("--email", default="director@thornbridge.example")
    ap.add_argument("--password", default="lumi-demo-2026")
    a = ap.parse_args()

    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def call(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(a.base + path, data=data,
                                   headers={"Content-Type": "application/json"})
        return json.loads(op.open(r, timeout=900).read())

    call("/api/auth/login", {"email": a.email, "password": a.password})
    groups = []
    try:
        groups = [g for g in (call("/api/peer-groups") or {}).get("groups", []) if g.get("group_id")]
    except Exception:
        pass

    base_fixture = json.load(open(a.fixture))
    results, worst = [], 0

    for name, qp in SHAPES:
        q = dict(qp)
        if name == "group":
            if not groups:
                results.append((name, "NO GROUP", "the org has no peer group to render"))
                continue
            q["cut_value"] = groups[0]["group_id"]
        qs = "&".join("%s=%s" % (k, v) for k, v in q.items())
        try:
            al = call("/api/strategy/alignment" + ("?" + qs if qs else ""))
        except urllib.error.HTTPError as e:
            # P1-B makes a signals failure a 500 rather than a blank document — a cut
            # that cannot build is a finding, not an absence
            results.append((name, "HTTP %d" % e.code, "the endpoint refused this cut"))
            worst = max(worst, 2)
            continue
        if al.get("ok") is False:
            results.append((name, "no strategy", al.get("reason", "")))
            continue

        fx = dict(base_fixture)
        fx["alignment"] = al
        json.dump(fx, open(a.fixture, "w"))

        out = subprocess.run([sys.executable, os.path.join(HERE, "verify_report_pdf.py"),
                              "--url", a.harness], capture_output=True, text=True)
        tail = [l for l in out.stdout.split("\n") if l.strip()]
        fails = [l.strip() for l in tail if l.strip().startswith("FAIL")]
        pages = next((l.split("—")[-1].strip() for l in tail if l.startswith("PDF:")), "?")
        label = al.get("cut_label", name)
        results.append((name, ("%d FAILURE(S)" % len(fails)) if fails else "clean",
                        "%s · %s%s" % (pages, label[:34],
                                       ("\n        " + "\n        ".join(fails[:6])) if fails else "")))
        worst = max(worst, 2 if fails else 0)

    json.dump(base_fixture, open(a.fixture, "w"))     # leave the fixture as we found it

    print("\n=== the document, on every cut shape ===")
    for name, verdict, detail in results:
        print("  %-9s %-14s %s" % (name, verdict, detail))
    bad = [r for r in results if "FAIL" in r[1] or "HTTP" in r[1]]
    print("\n%d of %d cut shapes render a document that verifies."
          % (len(results) - len(bad), len(results)))
    if bad:
        print("F-000 is not group-only." if len(bad) > 1 else "One cut shape fails.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
