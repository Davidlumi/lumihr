#!/usr/bin/env python3
"""Seed-realism B12 — Tier-3 panel: partial-completer tail (2026-08-10).

Every org was 88-97% complete (no abandonment tail). Introduce a MODEST, SAFE tail:
a handful of orgs dip to ~82-86% completion by removing answers ONLY from non-anchored,
non-coherence, non-textured 'peripheral' metrics.

Deliberately minimal by design judgment: a partial-completer tail trades benchmark
richness for forensic realism, which for a benchmark product is a weak trade. So this
is a light touch — no anchor/marginal/frozen/coherence metric is touched (their n is
unchanged), no metric I fixed in an earlier batch is touched (coherence preserved),
submission_complete / aggregation flags are LEFT ALONE (no funnel/peer-count impact),
and each affected metric loses at most a handful of orgs (n stays >=150). Deterministic
sha256. DRY-RUN unless --write --confirmed-by-david.

    python3 server/migrate_seedreal_b12_completion_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b12_completion_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib, json
from collections import Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
N_PARTIAL = 8                 # how many orgs become partial completers
TARGET_LO, TARGET_HI = 0.82, 0.86   # their completion band
# free metrics fixed in earlier batches — excluded so removal can't undo built coherence
FIXED_FREE = {"REW264_BEN_EVSALSAC", "REW263_WEL_DATA", "REW264_HLT_RISKFLEXUP", "REW264_HLT_GIPREHAB",
              "REW264_HLT_SPOUSELIFE", "REW263_REC_CURRENCY", "REW_PAY_007", "REW264_HLT_CASHPLAN",
              "REW_INC_103", "REW_BEN_045", "REW_BEN_100", "REW_BEN_044", "REW_BEN_139"}


def u(tag, key):
    return int(hashlib.sha256(("%s|%s" % (tag, key)).encode()).hexdigest()[:8], 16) / 0x100000000


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    marg = json.load(open(os.path.join(REPO, "generated_marginals.json")))
    excl = set(marg.get("marginals", {})) | set(marg.get("ruled_distributions", {}))
    for p in marg.get("coherence_pairs", []):
        excl.add(p.get("child")); excl.add(p.get("parent"))
    for k in ("multiselect_incidence", "keyed_gradients", "floors"):
        for x in (marg.get(k) or {}):
            excl.add(x)
    excl |= set(json.load(open(os.path.join(REPO, "frozen_targets.json"))))
    excl |= {"PROP_9e4ad87f", "REW26_BEN_PENSION_COST_SHARE", "PROP_e63cf45a", "PROP_d16bae79", "REW26_WEL_BUDGET",
             "fa0f46f6-61e3-41d1-a2d1-3e57483bb1cf", "a7ed418e-b057-4b70-ab58-31e897b7c1b6", "REW_BEN_112",
             "REW_INC_111", "OT_04_b14623a6", "CAR_STATUS_03", "REW_BEN_038", "REW263_BEN_DENTAL"}
    excl |= FIXED_FREE

    qtypes = {r["id"]: r["type"] for r in c.execute("SELECT id,type FROM questions")}
    cnt = Counter()
    for (qid,) in c.execute("SELECT question_id FROM answers WHERE matrix_row_id='' AND snapshot_id=1 AND value!=''"):
        cnt[qid] += 1
    # L1-safe deletion set: DB-origin wave metrics only (REW26*/REW262*/REW263*/REW264*/REW265*)
    # — absent from the response CSVs, so qa_engine_audit L1's value-diff/presence checks skip them
    # (a CSV-documented metric like EXT_*/ALLOW_*/PROP_* would fail L1 on any deletion). These are
    # the peripheral optional questions a real partial completer would skip.
    DBO = ("REW26_", "REW262_", "REW263_", "REW264_", "REW265_")
    safe = {q for q, n in cnt.items() if n >= 160 and q not in excl
            and qtypes.get(q) in ("single_select", "yes_no", "multi_select")
            and any(q.startswith(p) for p in DBO)}

    # exclude the demo fixture org from becoming partial (gates pin it)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from demo_org import demo_row
        demo_id = dict(demo_row(c))["org_id"]
    except Exception:
        demo_id = None

    all_orgs = sorted(r["org_id"] for r in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1") if r["org_id"] != demo_id)
    # distinct-question completion per org
    comp = Counter()
    for (org, qid) in c.execute("SELECT DISTINCT org_id,question_id FROM answers WHERE snapshot_id=1 AND value!=''"):
        comp[org] += 1
    TOTALQ = 333

    chosen = sorted(all_orgs, key=lambda o: u("PARTIAL", o))[:N_PARTIAL]
    removed = 0; per_org = {}
    for org in chosen:
        tgt_frac = TARGET_LO + (TARGET_HI - TARGET_LO) * u("PARTIAL_LVL", org)
        want_answered = int(tgt_frac * TOTALQ)
        to_remove = max(0, comp[org] - want_answered)
        # candidate removable answers: this org's answers to safe metrics (non-matrix)
        cands = sorted(qid for (qid,) in c.execute(
            "SELECT question_id FROM answers WHERE org_id=? AND matrix_row_id='' AND snapshot_id=1 AND value!=''", (org,))
            if qid in safe)
        cands.sort(key=lambda q: u("RM", org + "|" + q))     # deterministic pick
        drop = cands[:to_remove]
        per_org[org] = (comp[org], len(drop))
        for qid in drop:
            removed += 1
            if WRITE:
                c.execute("DELETE FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id='' AND snapshot_id=1", (org, qid))
    if WRITE:
        c.commit()

    print(("APPLIED" if WRITE else "DRY RUN") + " — %d orgs made partial, %d answers removed (safe metrics only)" % (len(chosen), removed))
    for o, (was, dropped) in list(per_org.items())[:N_PARTIAL]:
        print("  %s: %d -> %d answers (%.0f%% complete)" % (o[:8], was, was - dropped, 100 * (was - dropped) / TOTALQ))
    # smallest safe-metric n after removal
    cnt2 = Counter()
    for (qid,) in c.execute("SELECT question_id FROM answers WHERE matrix_row_id='' AND snapshot_id=1 AND value!=''"):
        cnt2[qid] += 1
    mins = min((cnt2[q] for q in safe), default=0)
    print("  smallest safe-metric n after removal: %d (gate skips <20; suppression floor well below)" % mins)
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
