# -*- coding: utf-8 -*-
"""migrate_m1_sickchain.py — Phase 2 · M1 STEP 1: the conservative draw (SEED-DATA class;
David-ruled 2026-07-30, "ADMIT the 8 unknowns … draw the zero-option as the book gives it").

REW_BEN_SICK_004's anchor declares a conditioned base ("orgs with OSP") and structured_bases states
it imperatively — "generator must condition on the OSP parent" — but no applicable_bases declaration
and no guarded coherence pair ever existed, so the engine counted the full base. The target passed at
+0.3pp on a base the anchor excludes: of 122 in-scope answers only 66 were verified OSP-holders.

TWO REPAIRS, 88 of the 177 open flags (r3sw25, DECISIONS 8885):
  B  48 no-OSP orgs stating a waiting rule      -> 'Not applicable (statutory only)'   (leave scope)
  D  40 OSP-holders stating 'Not applicable'    -> 'Yes - up to 3 days'                (enter scope)

THE CONSERVATIVE DRAW, ruled: a repaired 'not applicable' OSP-holder receives a WAITING PERIOD, never
day-one. An org answering "not applicable" is not claiming day-one eligibility — that is the
substantive reading. The distribution-preserving alternative would manufacture generous answers to
protect a target the incoherence was propping up. Gate agreement is corroboration, never the reason.

THE DESTINATION IS BOOK-DERIVED, not legislated (the batch-6 native-texture doctrine): among the 66
VERIFIED OSP-holders the waiting-rule mix is 30 'up to 3 days' / 0 'more than 3 days' / 36 day-one.
Genuine OSP-holders in this book never state a >3-day waiting period — all 23 orgs on that rung are
no-OSP (22) or unknown (1), i.e. they ARE the incoherence. So all 40 go to 'Yes - up to 3 days'.
NAMED ANCHOR-QUEUE FINDING (ruled, not a data fix): that leaves '>3 days' at exactly 1 org in the
repaired OSP base. NOTE the gate's zero-opt triage does NOT fire (the threshold is 0, not 1) —
rehearsed and corrected; this finding stands on its merits, not on a gate flag. If >3-day waiting
periods are real in the UK market the REGISTER should say so and the seed should follow — a source
read, not a draw.

NOT REPAIRED HERE, stated plainly: categories A (48 no-OSP stating an enhanced-pay duration) and
C (41 OSP-holders stating 'None (statutory only)') are SICK_002 flags. T8 stays HELD; SICK_002's
coherence pair ships with its own repair, not this one.
SICK_001 is NOT TOUCHED — T7's any-OSP fork re-derives after this repair, never during.

Dry-run default; --write; live needs --confirmed-by-david.
"""
import argparse, hashlib, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_DB = os.path.join(ROOT, "lumi.db")
SICK1, SICK4 = "REW_BEN_SICK_001", "REW_BEN_SICK_004"
NOOSP = {"Statutory sick pay only", "No sick pay provided"}
NA = "Not applicable (statutory only)"
SCOPE = {"Yes - more than 3 days", "Yes - up to 3 days", "No waiting period"}
DEST = "Yes - up to 3 days"
FIXTURES = ("5e67fa8c", "833beedb")   # Thornbridge Retail / Advisory


def book_hash(c):
    h = hashlib.sha256()
    for r in c.execute("SELECT org_id,snapshot_id,question_id,COALESCE(matrix_row_id,''),COALESCE(value,'') "
                       "FROM answers ORDER BY 1,2,3,4"):
        h.update(("|".join(str(x) for x in r)).encode())
    return h.hexdigest()


def answers(c, qid):
    return {o: v for o, v in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id=? AND snapshot_id=1 AND matrix_row_id='' "
        "AND value!=''", (qid,))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--confirmed-by-david", dest="confirmed", action="store_true")
    ap.add_argument("--hold-fixtures", action="store_true",
                    help="byte-hold the Thornbridge fixtures (the standing statistical-redraw doctrine)")
    a = ap.parse_args()
    is_live = os.path.abspath(a.db) == LIVE_DB
    if a.write and is_live and not a.confirmed:
        print("REFUSED: live write needs --confirmed-by-david (r3sw7)"); sys.exit(2)

    c = sqlite3.connect(a.db); c.row_factory = sqlite3.Row
    pre_book = book_hash(c)
    s1, s4 = answers(c, SICK1), answers(c, SICK4)
    osp = {o for o, v in s1.items() if v not in NOOSP}
    noosp = {o for o, v in s1.items() if v in NOOSP}

    # ---- PRE-STATE FINGERPRINTS (batch-6 discipline: permanent, in-script) ----
    assert len(s1) == 209 and len(s4) == 204, ("pre-state drift", len(s1), len(s4))
    assert len(osp) == 119 and len(noosp) == 90, ("OSP partition drift", len(osp), len(noosp))
    d4 = {}
    for v in s4.values():
        d4[v] = d4.get(v, 0) + 1
    assert d4 == {NA: 82, "Yes - up to 3 days": 62, "No waiting period": 37,
                  "Yes - more than 3 days": 23}, ("SICK_004 pre-dist drift", d4)
    verified = {o: s4[o] for o in s4 if o in osp and s4[o] != NA}
    assert len(verified) == 66, ("verified in-scope drift", len(verified))
    assert sum(1 for v in verified.values() if v == "Yes - more than 3 days") == 0, \
        "TEXTURE GUARD: a verified OSP-holder now states >3 days — the draw's donor shape has changed"
    assert sum(1 for v in verified.values() if v == "No waiting period") == 36, "day-one count drift"

    B = sorted(o for o in noosp if s4.get(o) in SCOPE)          # leave scope
    D = sorted(o for o in osp if s4.get(o) == NA)               # enter scope, conservative
    assert len(B) == 48 and len(D) == 40, ("repair-set drift", len(B), len(D))
    held = []
    if a.hold_fixtures:
        held = [o for o in B + D if o.startswith(FIXTURES)]
        B = [o for o in B if not o.startswith(FIXTURES)]
        D = [o for o in D if not o.startswith(FIXTURES)]

    print("M1 sick chain %s (db=%s)" % ("APPLY" if a.write else "dry-run", os.path.basename(a.db)))
    print("  B  %d no-OSP stating a waiting rule   -> %r" % (len(B), NA))
    print("  C  (SICK_002, 41) NOT repaired here — T8 held")
    print("  D  %d OSP-holders on 'Not applicable' -> %r  [conservative; book texture = 100%% up-to-3]"
          % (len(D), DEST))
    print("  A  (SICK_002, 48) NOT repaired here — T8 held")
    print("  fixtures: %s" % ("BYTE-HELD, skipped: %s" % [o[:8] for o in held] if held
                              else "repaired with the rest (coherence repair, not a statistical redraw)"))
    print("  total answer writes: %d" % (len(B) + len(D)))

    # ---- projected post-state ----
    post = dict(s4)
    for o in B:
        post[o] = NA
    for o in D:
        post[o] = DEST
    ins = {o: v for o, v in post.items() if v in SCOPE}
    pos = sum(1 for v in ins.values() if v == "No waiting period")
    print("  POST-REPAIR in-scope base %d | day-one %d | achieved %.4f vs target 0.30 -> %+.2fpp"
          % (len(ins), pos, pos / len(ins), (pos / len(ins) - 0.30) * 100))
    gt3 = sum(1 for v in ins.values() if v == "Yes - more than 3 days")
    print("  '>3 days' in the repaired base: %d  <- the NAMED ANCHOR-QUEUE FINDING (no zero-opt flag: threshold is 0)" % gt3)
    if not a.write:
        print("dry-run complete"); c.close(); return

    cur = c.cursor()
    for o in B:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND snapshot_id=1 "
                    "AND matrix_row_id=''", (NA, SICK4, o))
    for o in D:
        cur.execute("UPDATE answers SET value=? WHERE question_id=? AND org_id=? AND snapshot_id=1 "
                    "AND matrix_row_id=''", (DEST, SICK4, o))
    # ---- POST-WRITE ASSERTS ----
    s1b = answers(c, SICK1)
    assert s1b == s1, "SICK_001 MOVED — it is ruled untouched (T7 re-derives after, never during)"
    s2b = {r["org_id"]: r["value"] for r in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_SICK_002' AND snapshot_id=1 "
        "AND matrix_row_id='' AND value!=''")}
    assert len(s2b) == 205, "SICK_002 row count moved — categories A/C are not in this diff"
    s4b = answers(c, SICK4)
    assert s4b == post, "post-state does not match the projection"
    assert len(s4b) == len(s4), "SICK_004 answer count changed — this diff re-values, never adds or drops"
    for o in held:
        assert s4b[o] == s4[o], "held fixture moved: %s" % o
    n_changed = sum(1 for o in s4 if s4[o] != s4b[o])
    assert n_changed == len(B) + len(D), ("changed-count mismatch", n_changed)
    c.commit()
    print(json.dumps({"applied": True, "live": is_live, "writes": n_changed,
                      "B_to_na": len(B), "D_to_waiting": len(D), "fixtures_held": [o[:8] for o in held],
                      "post_in_scope": len(ins), "post_achieved": round(pos / len(ins), 4),
                      "book_before": pre_book[:16], "book_after": book_hash(c)[:16]}, indent=1))
    c.close()


if __name__ == "__main__":
    main()
