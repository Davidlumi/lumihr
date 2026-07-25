# -*- coding: utf-8 -*-
"""migrate_regfollowup2_tags.py — register follow-up 2 (CONFIG class, 2026-07-25): lift the stale
`unbenchmarked` tags on the FIVE tranche-1 metrics whose register rows are now verified anchors
(grade-A CIPD / statutory, register v2026-07-24). HOLPAYMETHOD verified NO-CHANGE (untagged +
Practice-class; its bound/statutory row implies no distribution-authority tag — recorded, untouched).

Effect (disclosure layer ONLY — re-verified: unbenchmarked is consumed only by the card layer
[_item flag -> app.py readout/pill suppression -> charts.js EST note], never by routing): the five
metrics' cards BEGIN showing peer comparisons (P-pill, readout, position pill) — the intended
promotion. The allocation ladder must be BYTE-IDENTICAL before/after (asserted by the caller).

Per metric: delete `unbenchmarked` (absent == benchmarked, the Diff-14 census semantics) + add a
`_regfollowup2` note citing the register row. FLEXPATTERN's note carries the PARTIAL anchoring
(prose-verified only; Figure-1 per-arm + annualised remain David's hold) — the tag vocabulary has
no partial state, so the note field expresses it (as ruled).
"""
import argparse, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
NOTES = {
    "REW264_HLT_CASHPLAN": "anchored at register v2026-07-24 (grade A, CIPD RM 2022: 23% all / 27% all-or-some + size splits) — unbenchmarked lifted (follow-up 2)",
    "REW264_HLT_OPTICAL": "anchored at register v2026-07-24 (grade A, CIPD RM 2022: 63/72 + size splits) — unbenchmarked lifted (follow-up 2)",
    "REW264_WEL_EWA": "anchored at register v2026-07-24 (grade A, CIPD RM 2022: 11% all / 14% all-or-some, source-corrected) — unbenchmarked lifted (follow-up 2)",
    "REW264_WEL_SEASONTICKET": "anchored at register v2026-07-24 (grade A, CIPD RM 2022: 25+5=30% + size splits) — unbenchmarked lifted (follow-up 2)",
    "REW265_TIME_FLEXPATTERN": "PARTIALLY anchored at register v2026-07-24 (grade A, CIPD Flexible & hybrid 2025, PROSE-VERIFIED quantities only — Figure-1 per-arm + annualised remain David's hold) — unbenchmarked lifted (follow-up 2)",
}
VERIFIED_NOCHANGE = "REW264_PAY_HOLPAYMETHOD"   # untagged + Practice-class; statutory bound row -> correct as-is


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--mp-out", dest="mp_out", default=None)
    a = ap.parse_args()
    live_target = a.mp_out is None
    if a.write:
        if live_target and not a.confirmed:
            print("REFUSED: live config write needs --confirmed-by-david (r3sw7)"); sys.exit(2)
        if not live_target and os.path.abspath(a.mp_out) == LIVE_MP:
            print("REFUSED: --mp-out must not be the live config"); sys.exit(2)
    raw = open(LIVE_MP, "rb").read()
    cfg = json.loads(raw); M = cfg["metrics"]
    for q in NOTES:
        assert M[q].get("unbenchmarked") is True, "%s not currently unbenchmarked=True — state drifted" % q
    assert M[VERIFIED_NOCHANGE].get("unbenchmarked") is None, "HOLPAYMETHOD unexpectedly tagged"
    print("regfollowup2 %s — 5 lifts + 1 verified-no-change (%s)" % ("APPLY" if a.write else "dry-run", VERIFIED_NOCHANGE))
    if not a.write:
        for q in NOTES: print("  %-26s unbenchmarked True -> (absent) + note" % q)
        return
    import copy
    before = copy.deepcopy(M)
    for q, note in NOTES.items():
        del M[q]["unbenchmarked"]
        M[q]["_regfollowup2"] = note
    for qid in before:
        if qid in NOTES: continue
        assert before[qid] == M[qid], "non-target config entry changed: %s" % qid
    for q in NOTES:
        b = before[q]
        assert all(M[q].get(k) == b.get(k) for k in b if k not in ("unbenchmarked", "_regfollowup2")), "extra field moved on %s" % q
    new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()
    dst = LIVE_MP if live_target else a.mp_out
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dst)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(new_raw)
    os.replace(tmp, dst)
    print(json.dumps({"applied": True, "target": os.path.basename(dst), "lifted": sorted(NOTES),
                      "verified_no_change": VERIFIED_NOCHANGE}, indent=1))


if __name__ == "__main__":
    main()
