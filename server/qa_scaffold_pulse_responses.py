#!/usr/bin/env python3
"""THROWAWAY-ONLY scaffolding: fill a live pulse with a realistic respondent cohort.

A pulse's report only exists above the 5-organisation floor, and the things worth QAing —
option ordering, long labels, suppression, the narrative, the chart at scale — only show
their problems at a hundred. The 270 seed organisations have no user accounts, so they
cannot answer through the UI; this writes their participation directly.

REFUSES TO RUN AGAINST THE LIVE STORE, on the same test as the account scaffolder: it
fabricates responses, and fabricated responses in the real store would be indistinguishable
from members' answers.

Answers are drawn per question type with a deliberate SHAPE rather than uniformly — a real
pulse has a modal answer and a tail, and a uniform sample hides exactly the rendering bugs
(ties, near-equal bars, a dominant option) that QA is looking for. Deterministic per
(pulse, org, question), so a re-run reproduces the same cohort.

    LUMI_DB=<throwaway> LUMI_IDENTITY_DB=<throwaway> \\
        python3 qa_scaffold_pulse_responses.py --count 120 [--pulse pulse-xxxx]
"""
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def _refuse_if_live():
    for label in ("LUMI_DB", "LUMI_IDENTITY_DB"):
        path = os.environ.get(label, "")
        if not path:
            sys.exit("REFUSING: %s is unset — this fabricates responses and must only run "
                     "against an explicit throwaway." % label)
        ap = os.path.abspath(path)
        if ap in (os.path.join(ROOT, "lumi.db"), os.path.join(ROOT, "identity.db")):
            sys.exit("REFUSING: %s points at the LIVE store." % label)
        if not ("/scratchpad" in ap or ap.startswith("/tmp") or ap.startswith("/private/tmp")):
            sys.exit("REFUSING: %s (%s) is not under a scratchpad or tmp directory." % (label, ap))


def _rng(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _weights(n, rnd):
    """A believable shape: one clear modal option, a runner-up, a thin tail. Uniform
    sampling produces near-equal bars, which is the one shape that hides layout bugs."""
    w = sorted((rnd.random() ** 2.2 for _ in range(n)), reverse=True)
    rnd.shuffle(w)
    total = sum(w) or 1.0
    return [x / total for x in w]


def main():
    _refuse_if_live()
    from db import get_conn
    import pulses as pulses_mod

    count = 120
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])
    only = None
    if "--pulse" in sys.argv:
        only = sys.argv[sys.argv.index("--pulse") + 1]

    conn = get_conn()
    rows = conn.execute("SELECT pulse_id, name, owner_org_id, status, launch_status "
                        "FROM pulses WHERE launch_status='paid'").fetchall()
    if only:
        rows = [r for r in rows if r["pulse_id"] == only]
    if not rows:
        sys.exit("No launched pulses to fill.")

    all_orgs = [r["org_id"] for r in conn.execute(
        "SELECT org_id FROM orgs WHERE source='seed' ORDER BY org_id")]

    for p_row in rows:
        pid = p_row["pulse_id"]
        p = pulses_mod.get_pulse(pid, conn)
        qs = pulses_mod.pulse_questions(p)
        # a pulse is open to the community, so the owner answers it too
        cohort = [o for o in all_orgs if o != p_row["owner_org_id"]][:count]
        print("\n== %s — %s" % (pid, p_row["name"][:58]))
        print("   %d questions · %d organisations" % (len(qs), len(cohort)))

        written = 0
        for org in cohort:
            conn.execute("INSERT OR IGNORE INTO pulse_participants(pulse_id, org_id) VALUES (?,?)",
                         (pid, org))
            answered = 0
            for qid, q in qs.items():
                rnd = _rng(pid, org, qid)
                # a real cohort has gaps: a few organisations skip a question rather than
                # guess, and blank must stay distinct from zero all the way to the report
                if rnd.random() < 0.06:
                    continue
                # library.Question is a __slots__ object, not a dict — attribute access
                qtype = getattr(q, "type", None)
                opts = [o.get("label") for o in (getattr(q, "options", None) or [])
                        if isinstance(o, dict) and o.get("label")]
                if qtype == "numeric":
                    lo, hi = 0.0, 20.0
                    val = str(round(abs(rnd.gauss((lo + hi) / 4, (hi - lo) / 6)), 1))
                elif qtype == "multi_select" and opts:
                    w = _weights(len(opts), _rng(pid, qid))
                    # a floor per option: without one the tail collapses to exactly 0.0%,
                    # which reads as a broken question rather than a rare practice
                    picked = [o for o, wt in zip(opts, w)
                              if rnd.random() < min(0.78, 0.09 + wt * 1.7)]
                    # "None of these" is exclusive — a cohort that ticks it alongside six
                    # premiums is not a fixture, it is a contradiction on the report
                    nones = [o for o in opts if o.strip().lower().startswith("none")]
                    real = [o for o in picked if o not in nones]
                    if nones and rnd.random() < 0.12:
                        picked = [nones[0]]
                    elif real:
                        picked = real
                    else:
                        picked = [next(o for o in opts if o not in nones)]
                    val = ";".join(picked)
                elif opts:
                    w = _weights(len(opts), _rng(pid, qid))
                    val = rnd.choices(opts, weights=w, k=1)[0]
                else:
                    continue
                conn.execute(
                    "INSERT INTO pulse_responses(pulse_id, org_id, question_id, matrix_row_id, value) "
                    "VALUES (?,?,?,'',?) ON CONFLICT(pulse_id, org_id, question_id, matrix_row_id) "
                    "DO UPDATE SET value=excluded.value", (pid, org, qid, val))
                answered += 1
                written += 1
            if answered:
                conn.execute("UPDATE pulse_participants SET submission_complete=1 "
                             "WHERE pulse_id=? AND org_id=?", (pid, org))
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM pulse_participants WHERE pulse_id=? AND "
                         "submission_complete=1", (pid,)).fetchone()[0]
        print("   %d answers written · %d organisations submitted" % (written, n))

    print("\nDone. Reports are live above the 5-organisation floor.")


if __name__ == "__main__":
    main()
