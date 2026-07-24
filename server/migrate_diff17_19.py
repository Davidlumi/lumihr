# -*- coding: utf-8 -*-
"""migrate_diff17_19.py — the ruled Go-Order A/B applies (David 2026-07-24), scoped so each FIX CLASS
commits separately (--scope). NEVER apply >1 scope in a live commit.

  --scope score17     DIFF 17 (scoring only): is_scored=1 + equal-weight multi_select_count option_scores
                      on the 10 ruled multi-selects. None=0 (substantive, positions — NOT na). MH_SUPPORT
                      frozen-8 gated by the CALLER (rehearsal verifies its answer distribution is unshifted).
  --scope paycomms    CLASSIFICATION: REW265_PAY_PAYCOMMS config class=Practice, direction=null (-> approach).
  --scope decl19a     QUESTION-BANK DATA: na_codes declarations on the 5 ruled metrics (cited verbatim).
  --scope pmiexcess19b SEED + CLASSIFICATION: PMIEXCESS config class=Practice/direction=null + DB polarity
                      neutralised (mini-reversal of its Diff-15 restore — backwards ladder), AND the
                      parent/child seed reconcile: the 84 orgs with PMI but PMIEXCESS='Not applicable' get a
                      substantive excess drawn (deterministic quota) from the observed PMI-haver distribution.

Guards: dry-run default; live needs --write --confirmed-by-david; throwaway needs --db <copy> and
--mp-out <staged config> for the config-touching scopes (paycomms, pmiexcess19b). Post-asserts per scope.
"""
import argparse, hashlib, json, os, sqlite3, sys, tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
LIVE_MP = os.path.join(ROOT, "data", "market_position_config.json")
FROZEN8 = ["REW26_WEL_EAP", "REW26_WEL_MH_SUPPORT", "REW26_WEL_FINWELL", "REW26_WEL_STRATEGY",
           "REW26_BEN_PENSION_TYPE", "REW26_BEN_PENSION_MATCH", "REW26_BEN_SALSAC", "REW262_TIME_SICKDAYONE"]

SCORE10 = ["REW26_WEL_MH_SUPPORT", "REW264_TIME_CHILDCARE", "REW265_TIME_FLEXPATTERN", "REW265_TIME_EXTRADAYS",
           "REW262_GOV_ACTIONPLAN", "REW265_GOV_VOLGAPS", "REW264_HLT_BEREAVESUPPORT", "REW264_PEN_SIDECAR",
           "REW264_WEL_COLACTION", "REW265_BEN_GREENBEN"]
DECL = {"REW265_INC_COMMCAP": "NOT_APPLICABLE_NO_COMMISSION_PLANS", "REW264_PEN_NICSHARING": "NO_SAL_SAC_SCHEME",
        "REW263_GOV_ETHDISREADY": "NOT_APPLICABLE", "REW265_GOV_GPGNAMING": "NOT_IN_SCOPE_UNDER_250_EMPLOYEES",
        "REW264_HLT_FERTROUTE": "NOT_APPLICABLE"}
PAYCOMMS = "REW265_PAY_PAYCOMMS"
PMIEXCESS = "REW263_BEN_PMIEXCESS"
STAMP = "2026-07-24 diff19b"


def book(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True, choices=["score17", "paycomms", "decl19a", "pmiexcess19b"])
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--mp-out", dest="mp_out", default=None)
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    touches_cfg = a.scope in ("paycomms", "pmiexcess19b")
    if a.write:
        if is_live:
            if not a.confirmed:
                print("REFUSED: live needs --confirmed-by-david"); sys.exit(2)
            a.mp_out = LIVE_MP
        elif touches_cfg and (a.mp_out is None or os.path.abspath(a.mp_out) == LIVE_MP):
            print("REFUSED: throwaway config scope needs --mp-out (not live)"); sys.exit(2)
    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    print("scope=%s %s (db=%s)" % (a.scope, "APPLY" if a.write else "dry-run", os.path.basename(a.db)))

    if not a.write:
        print("dry-run — pass --write (+ --confirmed-by-david live, + --mp-out throwaway-cfg)"); c.close(); return
    pre = book(c)
    cur = c.cursor()

    if a.scope == "score17":
        for q in SCORE10:
            opts = json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0])
            osc = {o["code"]: (0 if o["label"].strip().lower() in ("none", "no provision") else 1) for o in opts}
            sc = {"scoring_method": "multi_select_count", "option_scores": osc}
            cur.execute("UPDATE questions SET is_scored=1, scoring_config_json=? WHERE id=?", (json.dumps(sc), q))
        assert book(c) == pre, "answers changed (scoring must not touch answers)"
        assert all(c.execute("SELECT is_scored FROM questions WHERE id=?", (q,)).fetchone()[0] == 1 for q in SCORE10)
        c.commit()
        print(json.dumps({"applied": True, "scope": "score17", "scored": len(SCORE10), "answers": "unchanged"}))

    elif a.scope == "decl19a":
        for q, code in DECL.items():
            row = c.execute("SELECT COALESCE(scoring_config_json,'') FROM questions WHERE id=?", (q,)).fetchone()[0]
            sc = json.loads(row) if row else {}
            labels = {o["code"] for o in json.loads(c.execute("SELECT options_json FROM questions WHERE id=?", (q,)).fetchone()[0])}
            assert code in labels, "na_code %s not a live option of %s (stale)" % (code, q)
            sc["na_codes"] = sorted(set(sc.get("na_codes") or []) | {code})
            cur.execute("UPDATE questions SET scoring_config_json=? WHERE id=?", (json.dumps(sc), q))
        assert book(c) == pre, "answers changed (declaration must not touch answers)"
        c.commit()
        print(json.dumps({"applied": True, "scope": "decl19a", "declared": list(DECL)}))

    elif a.scope in ("paycomms", "pmiexcess19b"):
        # read the ACCUMULATING config: on a throwaway the staged --mp-out carries prior scopes' edits;
        # live reads (and rewrites) LIVE_MP in place across the separate live commits.
        cfg_src = a.mp_out if (a.mp_out and os.path.exists(a.mp_out) and os.path.abspath(a.mp_out) != LIVE_MP) else LIVE_MP
        raw = open(cfg_src, "rb").read(); cfg = json.loads(raw); M = cfg["metrics"]
        if a.scope == "paycomms":
            b = dict(M[PAYCOMMS]); M[PAYCOMMS]["class"] = "Practice"; M[PAYCOMMS]["direction"] = None
            M[PAYCOMMS]["_diff17_paycomms"] = "ruled PRACTICE (contested direction; neutral-17 precedent) — Diff 17 reclass"
            assert book(c) == pre, "answers changed"
            n_changed = 0
        else:  # pmiexcess19b
            b = dict(M[PMIEXCESS]); M[PMIEXCESS]["class"] = "Practice"; M[PMIEXCESS]["direction"] = None
            M[PMIEXCESS]["_diff19b"] = ("ruled PRACTICE — excess ladder runs no-excess->high-excess so higher_is_better "
                                        "fires BACKWARDS; supersedes the Diff-15 higher_is_better restore (mini-reversal)")
            cur.execute("UPDATE questions SET polarity='neutral' WHERE id=?", (PMIEXCESS,))
            # seed reconcile: 84 orgs with PMI but PMIEXCESS='Not applicable' -> substantive, deterministic quota
            pmi = set(o for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND COALESCE(value,'')!=''")
                      if "Private Medical Insurance" in v or "PMI" in v)
            pxe = {o: v for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (PMIEXCESS,))}
            contra = sorted(o for o in pmi if pxe.get(o) == "Not applicable")
            # observed substantive distribution among PMI-havers
            subs = Counter(v for o, v in pxe.items() if o in pmi and v != "Not applicable")
            labels = sorted(subs, key=lambda k: -subs[k]); tot = sum(subs.values())
            quota = {lab: int(round(subs[lab] / tot * len(contra))) for lab in labels}
            # fix rounding to exactly len(contra)
            while sum(quota.values()) < len(contra): quota[labels[0]] += 1
            while sum(quota.values()) > len(contra): quota[labels[-1]] -= 1
            ranked = sorted(contra, key=lambda o: hashlib.sha256(("diff19b::%s" % o).encode()).hexdigest())
            assign = {}; i = 0
            for lab in labels:
                for o in ranked[i:i + quota[lab]]: assign[o] = lab
                i += quota[lab]
            for o, lab in assign.items():
                cur.execute("INSERT INTO answers_history(org_id,snapshot_id,question_id,matrix_row_id,value,recorded_at) "
                            "SELECT org_id,snapshot_id,question_id,matrix_row_id,value,? FROM answers WHERE question_id=? AND org_id=?",
                            (STAMP + " pre-reconcile", PMIEXCESS, o))
                cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=?", (lab, PMIEXCESS, o))
            n_changed = len(assign)
            # coherence assert: 0 remaining contradictions
            pxe2 = {o: v for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND COALESCE(value,'')!=''", (PMIEXCESS,))}
            assert not [o for o in pmi if pxe2.get(o) == "Not applicable"], "contradictions remain post-reconcile"
        # config assert: only the ruled metric's class/direction/tag changed
        new_raw = json.dumps(cfg, indent=2, ensure_ascii=False).encode()
        before_cfg = json.loads(raw)["metrics"]
        tgt = PAYCOMMS if a.scope == "paycomms" else PMIEXCESS
        for qid in before_cfg:
            if qid == tgt: continue
            assert before_cfg[qid] == M[qid], "non-target config changed: %s" % qid
        assert {q: c.execute("SELECT polarity FROM questions WHERE id=?", (q,)).fetchone()["polarity"] for q in FROZEN8}, "frozen read ok"
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(a.mp_out)), suffix=".tmp")
        with os.fdopen(fd, "wb") as f: f.write(new_raw)
        c.commit(); os.replace(tmp, a.mp_out)
        print(json.dumps({"applied": True, "scope": a.scope, "reconciled_orgs": n_changed,
                          "config_out": os.path.basename(a.mp_out)}))
    c.close()


if __name__ == "__main__":
    main()
