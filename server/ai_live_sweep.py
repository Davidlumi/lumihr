#!/usr/bin/env python3
"""Which AI surfaces actually reach the model? — the live-key sweep.

NOT a gate, and deliberately outside the qa_ namespace: it spends real money on David's
key, so it must never join run_gates.sh (which runs every gate with ANTHROPIC_API_KEY='').

It exists because the AI firewall makes a broken model path invisible. Every generator in
claude_api falls back to a deterministic floor and returns 200 with plausible prose, so a
surface that has NEVER once used the model reads exactly like a healthy one from outside.
Three surfaces were in that state on 2026-08-20 — the board pack and pulse narrative for
their entire lives (array constraints the structured-output API refuses), and the strategy
statement two generations in three.

Each call forces past the cache and prints the `source` the route publishes. Anything
reading `deterministic` against a live key is a broken path, not a design choice — except
domain summary, which is off by David's standing ruling (LUMI_AI_DOMAIN_SUMMARY) and is
reported as such rather than as a failure.

    python3 ai_live_sweep.py [base_url]        # default http://localhost:8071

Exit 0 only when every surface that should reach the model did.
"""
import sys

import requests

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8071"
DEMO = ("director@thornbridge.example", "lumi-demo-2026")
DOMAIN = "Pay"                      # a real sub_power, so the payload is not the thin path

# off by ruling, not broken — reported, never counted as a failure
BY_RULING = {"domain summary": "LUMI_AI_DOMAIN_SUMMARY is off pending the compliance track"}


def main():
    s = requests.Session()
    r = s.post(B + "/api/auth/login", json={"email": DEMO[0], "password": DEMO[1]}, timeout=30)
    if r.status_code != 200:
        sys.exit("login failed (%s) — is the AI rig running on %s?" % (r.status_code, B))

    # a real answered question, so metric commentary runs on a full payload
    qid = None
    rows = s.get(B + "/api/benchmarks/Reward", timeout=90).json()
    for row in (rows.get("questions") or rows.get("rows") or rows.get("cards") or []):
        if row.get("you") is not None:
            qid = row.get("question_id") or row.get("id")
            break
    if not qid:
        print("!! no answered question found — metric commentary will run on a thin payload")

    # a launched pulse with a report, for the two pulse surfaces
    pid = None
    for p in (s.get(B + "/api/pulses", timeout=30).json().get("pulses") or []):
        if p.get("report_available") or p.get("status") in ("closed", "archived"):
            pid = p.get("pulse_id")
            break

    calls = [
        ("metric commentary",   "/api/metric-commentary",   {"question_id": qid, "cut": "all", "force": 1}),
        ("domain summary",      "/api/domain-summary",      {"domain": DOMAIN, "cut": "all", "force": 1}),
        ("strategy statement",  "/api/strategy/statement",  {"force": 1}),
        ("strategy commentary", "/api/strategy/commentary", {"force": 1}),
        ("strategy diagnosis",  "/api/strategy-diagnosis",  {"force": 1}),
        ("action plan",         "/api/strategy/plan",       {"force": 1}),
    ]
    if pid:
        blocks = ((s.get(B + "/api/pulses/%s" % pid, timeout=30).json().get("report")
                   or {}).get("questions") or [])
        first_q = (blocks[0].get("question_id") or blocks[0].get("id")) if blocks else None
        calls += [("pulse commentary", "/api/pulses/%s/commentary" % pid,
                   {"question_id": first_q, "force": 1}),
                  ("pulse narrative", "/api/pulses/%s/narrative" % pid, {"force": 1})]
    else:
        print("!! no pulse with an available report — the two pulse surfaces are not covered")

    print("%-22s %-6s %-14s %s" % ("SURFACE", "HTTP", "SOURCE", "NOTE"))
    print("-" * 78)
    broken = []
    for label, path, body in calls:
        try:
            r = s.post(B + path, json=body, timeout=300)
        except Exception as e:
            print("%-22s %-6s %-14s %s" % (label, "ERR", "-", str(e)[:34]))
            broken.append(label)
            continue
        src, note = "-", ""
        if r.status_code == 200:
            d = r.json()
            src = d.get("source") or (d.get("plan") or {}).get("source") or "-"
        else:
            note = r.text[:60]
        if src != "model":
            if label in BY_RULING:
                note = note or ("by ruling — %s" % BY_RULING[label])
            else:
                broken.append(label)
                note = note or "check the server log for the fallback reason"
        print("%-22s %-6s %-14s %s" % (label, r.status_code, src, note))

    # the board pack reports provenance as a boolean rather than a source string
    r = s.post(B + "/api/boardpack/generate", json={"cut": "all"}, timeout=300)
    ai = r.status_code == 200 and bool(r.json().get("ai"))
    print("%-22s %-6s %-14s %s" % ("board pack", r.status_code, "model" if ai else "deterministic",
                                   "" if ai else "check the server log for the fallback reason"))
    if not ai:
        broken.append("board pack")

    if broken:
        print("\nFELL BACK: %s" % ", ".join(broken))
        print("Each one served its deterministic floor. The server log names the reason.")
        return 1
    print("\nEvery surface that should reach the model did.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
