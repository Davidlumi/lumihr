#!/usr/bin/env python3
"""Identity/reward reconciliation (D6's orphan assertion, first standalone form;
joins the gate suite properly at step 7 — deliberately NOT qa_-prefixed until then,
so the gate-roster derivation is unchanged).

Reads both stores read-only. For each dual-written table: rows present reward-side
with no identity counterpart, and the reverse, plus a content-drift count (rows
present both sides whose column tuples differ). Drift is FATAL (nonzero exit) per
the 1a sequencing ruling, whose condition — the 1b mutation mirror and 1c delete
mirror both landed — was met at b8aa490.

P2, THE NARROWING. Step 5 removes the identity-bearing columns from the reward
store, so a fixed comparison set that included them would, post-step-5, compare
real values against nothing and report drift on every row — a safety net failing
by construction and reporting a catastrophe that is entirely its own instrument.
This is the fourth equality check this build aimed at something designed to change
(the whole-file sha, the session-count echo, D9's row-count assertion, now this).
The pattern: AN EQUALITY CHECK MUST NEVER BE AIMED AT A VALUE THE PLAN INTENDS TO
CHANGE — assert on what is invariant, and make the intended change itself the thing
that is detected.

So the comparison set is resolved AT RUN TIME, per column, from the reward store's
actual state. Correct in all three worlds, without a flag to remember:

  ABSENT     column gone reward-side (step 5 dropped it) -> out of the drift set
  EMPTY      present, every row NULL (step 5 nulled it)  -> out of the drift set
  POPULATED  present, no row NULL (pre-step-5)           -> IN the drift set, as today
  PARTIAL    present, some rows NULL and some not        -> FATAL

PARTIAL is the load-bearing addition: it catches a half-run step 5 and a writer
re-populating a column that should stay empty. It is strictly more than the old
fixed set could detect.

WHAT THIS CANNOT DETECT, stated plainly: a COMPLETE restore of lumi.db from a
pre-step-5 backup looks identical to the pre-step-5 world — every row populated,
consistently. Data alone cannot separate the two. Catching that needs a marker
held OUTSIDE the reward store (identity.db or a tracked file), which is step 5's
own commit to design, once step 5's mechanism is ruled. Recorded, not papered over.

Sessions are excluded: since Seam-B they are written ONLY identity-side. The
reward-side sessions table is a vestige of the pre-cutover world, still holding
its old rows and receiving no new ones, so comparing the two stores for sessions
compares a live table against a dead one — before step 5 and after it alike.

Counts only — no names, emails, or tokens. Exit 0 iff both orphan directions AND
drift are 0 for every table, and no column is PARTIAL.
"""
import json, os, sqlite3, sys

REWARD = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identity

r = sqlite3.connect("file:%s?mode=ro" % REWARD, uri=True)
i = sqlite3.connect("file:%s?mode=ro" % identity._resolve_identity_db_path(), uri=True)

# Columns step 5 removes from the REWARD store. This constant is the operative
# definition of that list: the spec says "the moved columns" (S6 step 5) and the
# record says "the identity-bearing columns" (DECISIONS, step-5 pre-flight), and
# neither enumerates them. Recorded at P2 as a finding — step 5 must pin its own
# list before it runs, and this constant is what the safety net assumes until it does.
STEP5_REMOVED = {
    "orgs":            ("name", "normalized_name"),
    "users":           ("email", "pw_hash", "display_name"),
    "invites":         ("email",),
    "password_resets": (),
}

PAIRS = [
    # (label, reward table, identity table, key column, invariant compared columns)
    ("orgs<->org_register", "orgs", "org_register", "org_id",
     ("org_id",)),
    ("users (5-col shared set; S4.2 split)", "users", "users", "user_id",
     ("user_id", "org_id")),
    ("invites", "invites", "invites", "token",
     ("token", "org_id", "role", "created_by", "expires_at", "used_at")),
    ("password_resets", "password_resets", "password_resets", "token",
     ("token", "user_id", "expires_at", "used_at")),
]


def classify(table, col):
    """Reward-side state of a column step 5 removes."""
    cols = [x[1] for x in r.execute("PRAGMA table_info(%s)" % table)]
    if col not in cols:
        return "ABSENT"
    n = r.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
    if n == 0:
        return "NO ROWS"
    nulls = r.execute("SELECT COUNT(*) FROM %s WHERE %s IS NULL" % (table, col)).fetchone()[0]
    if nulls == 0:
        return "POPULATED"
    if nulls == n:
        return "EMPTY"
    return "PARTIAL"


MARKER = identity.step5_marker()
if MARKER is None:
    print("step-5 marker: ABSENT (identity.meta has no row) — pre-step-5 expected state")
else:
    print("step-5 marker: %s (mechanism %s, completed_at %s)"
          % (MARKER["step5_state"], MARKER["step5_mechanism"], MARKER["step5_completed_at"]))

ok = True
for label, rt, it, key, invariant in PAIRS:
    states = {c: classify(rt, c) for c in STEP5_REMOVED[rt]}
    partial = [c for c, s in states.items() if s == "PARTIAL"]
    compared = list(invariant) + [c for c, s in states.items() if s == "POPULATED"]

    ki = compared.index(key)
    rrows = {row[ki]: row for row in r.execute(
        "SELECT %s FROM %s ORDER BY %s" % (", ".join(compared), rt, key))}
    irows = {row[ki]: row for row in i.execute(
        "SELECT %s FROM %s ORDER BY %s" % (", ".join(compared), it, key))}
    only_reward = len(set(rrows) - set(irows))
    only_identity = len(set(irows) - set(rrows))
    drift = sum(1 for k in set(rrows) & set(irows) if rrows[k] != irows[k])

    print("%s: reward=%d identity=%d | reward-only (identity orphan missing)=%d | "
          "identity-only (reverse orphan)=%d | content-drift=%d"
          % (label, len(rrows), len(irows), only_reward, only_identity, drift))
    # Orphan KEYS (PH-PROV-1 Stage 3 §1: an operator must be able to act on a
    # detection, so the finding names the row). Keys only — org_ids and tokens are
    # opaque identifiers, so the counts-only privacy posture (no names, emails)
    # is preserved. Bounded at 5 per direction.
    if only_reward:
        print("    reward-only keys (first 5): %s" % sorted(set(rrows) - set(irows))[:5])
    if only_identity:
        print("    identity-only keys (first 5): %s" % sorted(set(irows) - set(rrows))[:5])
    print("    compared: %s" % ", ".join(compared))
    if states:
        print("    step-5 columns: %s" % "; ".join("%s=%s" % (c, s) for c, s in states.items()))
        if not [c for c, s in states.items() if s == "POPULATED"]:
            print("    NOTE: no step-5 column is still populated reward-side, so for this table "
                  "the drift check\n          covers only the invariant columns above; "
                  "membership is what it still proves.")
    # --- the marker/column classifier (D.2's table) ------------------------------
    state = MARKER["step5_state"] if MARKER else None
    empty = [c for c, v in states.items() if v in ("EMPTY", "ABSENT")]
    populated = [c for c, v in states.items() if v == "POPULATED"]
    fatal = False
    if partial:
        if state == "in_progress":
            print("    PARTIAL (%s) TOLERATED: the marker says step 5 is in_progress, so a mix of\n"
                  "        NULL and populated rows is the expected migration window, not a defect."
                  % ", ".join(partial))
        else:
            print("    *** PARTIAL: %s — some rows NULL, some not. A half-run step 5, or a writer "
                  "re-populating\n        a column that should stay empty. FATAL." % ", ".join(partial))
            fatal = True
    if state == "complete" and populated:
        print("    *** CONTRADICTION: identity.meta says step 5 COMPLETED at %s (mechanism %s,\n"
              "        %s columns); reward-side %s still holds values. Either lumi.db was restored\n"
              "        from a pre-step-5 backup, or a writer was missed. This is NOT drift."
              % (MARKER["step5_completed_at"], MARKER["step5_mechanism"],
                 len(json.loads(MARKER["step5_columns"])), ", ".join(populated)))
        fatal = True
    if state is None and empty:
        # D.2's self-introduced gap, closed here. Before step 5 this combination is
        # impossible (the columns are populated); after step 5 with a healthy marker it is
        # also impossible. It fires only when the marker has been LOST — an identity.db
        # restored to a pre-marker state against a migrated reward store, which is the
        # restore direction the marker exists to catch. FATAL, on the bbbb98b ground: a
        # safety net that reports the one state it cannot explain is worth more than one
        # that stays silent through it.
        print("    *** NO MARKER but reward-side %s is empty/absent. identity.meta carries no\n"
              "        step-5 row, yet the reward store looks migrated. Either identity.db was\n"
              "        restored to a pre-marker state, or step 5 ran without writing its marker.\n"
              "        FATAL — this combination is impossible in a healthy store."
              % ", ".join(empty))
        fatal = True
    ok &= (only_reward == 0 and only_identity == 0 and drift == 0 and not fatal)

print("sessions: EXCLUDED — written identity-side only since Seam-B; the reward-side table is a\n"
      "          pre-cutover vestige receiving no new rows, so the comparison would put a live\n"
      "          table against a dead one, before step 5 and after it alike")
print("RECONCILIATION: %s" % ("PASS — 0 orphans in both directions, 0 drift, marker consistent"
                              if ok else "FAIL — orphans, drift, or a marker/column contradiction"))
sys.exit(0 if ok else 2)
