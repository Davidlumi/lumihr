#!/usr/bin/env python3
"""First-class identity backup (step 5 commit 2; D9, F.1, F.3).

identity.db is the SOLE rollback path for step 5 — every nulled column restores
from it and from nothing else — so this script is a precondition, not a
convenience. Retain-1 per backup_policy.md's identity class, CONDITIONAL on the
two assertions below; a copy that fails either is DELETED (an unvouchable PII
concentrate is exposure without value) and the predecessor, if any, is kept —
in that state the class sits at retain-2 by the policy's own terms.

D6: the live store is opened through identity.get_conn() only. The copy is made
with the SQLite backup API (never cp), after a checkpoint that is a no-op on
this store's delete-mode journal but keeps the ritual identical to the reward
side's. sessions is EXCLUDED from the row-count assertion (F.3): it changes on
every login, and asserting equality on it would fail spuriously — the same
class as the whole-file sha and the session-count echo, both already ruled.
"""
import glob, hashlib, os, re, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identity

ASSERTED = ("org_register", "users", "invites", "password_resets")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# --- rotation delete-safety (PH-BAK-3) ---------------------------------------
# THE naming convention, anchored: tag + _YYYYMMDD_HHMMSS, full-string match.
# No live store path can satisfy it, and anything glob-caught that this regex
# rejects (a -wal straggler, a renamed copy, a directory) ABORTS the rotation.
BAK_RE = re.compile(r"^identity\.db\.bak_pre_[A-Za-z0-9]+_(\d{8}_\d{6})$")
# data/backup_policy.md, identity class: "retain the last 1" — THE retain
# constant; total copies kept INCLUDING the one just created. No other literal.
RETAIN = 1
LIVE_STORES = ("identity.db", "lumi.db")


def rotation_candidates(root):
    return sorted(glob.glob(os.path.join(root, "identity.db.bak_pre_*")))


def deletion_violation(p, root):
    """Positive assertions before any unlink (PH-BAK-3 §2) — returns the reason
    this path must NOT be deleted, or None if every assertion passes. ALL of:
    convention-anchored basename; not a symlink (doctrine depth — an unlink on
    a link is benign to the target, but a link is not a backup); a regular
    file; realpath is neither live store."""
    name = os.path.basename(p)
    if not BAK_RE.match(name):
        return "basename does not match the backup naming convention"
    if os.path.islink(p):
        return "is a symlink — not a backup, never unlinked"
    if not os.path.isfile(p):
        return "not a regular file"
    rp = os.path.realpath(p)
    for live in LIVE_STORES:
        if rp == os.path.realpath(os.path.join(root, live)):
            return "resolves to the LIVE store %s" % live
    return None


def rotate_previous(root, prev, write):
    """FAIL-CLOSED rotation: every candidate is validated before ANY is
    deleted; one failure aborts the whole rotation with nothing removed and
    the offending path named — a rotation that meets something it does not
    understand stops, it does not proceed carefully. Ordering is derived from
    the FILENAME timestamp, never mtime (mtime is mutated by any copy
    operation); the convention regex guarantees the timestamp parses, so a
    candidate that reaches ordering cannot fail it. Returns True iff the
    rotation completed (or had nothing to do)."""
    bad = [(p, v) for p in prev for v in [deletion_violation(p, root)] if v]
    if bad:
        for p, v in bad:
            print("[idbak] ROTATION ABORTED — %s: %s" % (p, v))
        print("[idbak] fail-closed: NOTHING deleted (the just-created copy stands; "
              "the class sits above retain-%d until this is resolved by hand)." % RETAIN)
        return False
    keep_prev = max(0, RETAIN - 1)   # the new copy is survivor #1
    by_ts = sorted(prev, key=lambda p: BAK_RE.match(os.path.basename(p)).group(1))
    doomed = by_ts[:len(by_ts) - keep_prev] if keep_prev else by_ts
    for p in doomed:
        if write:
            os.remove(p)
        print("[idbak] rotation: previous copy %s %s (retain-%d, creation-time doctrine)"
              % (os.path.basename(p), "deleted" if write else "WOULD be deleted", RETAIN))
    return True

def table_hash(conn, t):
    h = hashlib.sha256()
    cols = [x[1] for x in conn.execute("PRAGMA table_info(%s)" % t)]
    for row in conn.execute("SELECT %s FROM %s ORDER BY %s" % (",".join(cols), t, cols[0])):
        h.update(("|".join("" if v is None else str(v) for v in row)).encode())
    return h.hexdigest()[:16]

def main():
    write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
    tag = next((a.split("=",1)[1] for a in sys.argv if a.startswith("--tag=")), "step5")
    src = identity.get_conn()                       # D6: the only sanctioned open
    live = {t: (src.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0], table_hash(src, t))
            for t in ASSERTED}
    sess = src.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print("[idbak] live census: %s | sessions=%d (EXCLUDED from the assertion — changes on"
          % ({t: c for t,(c,_) in live.items()}, sess))
    print("        every login; equality on it fails spuriously. F.3, ruled.)")
    prev = rotation_candidates(ROOT)
    if not write:
        print("[idbak] DRY RUN — would create identity.db.bak_pre_%s_<ts>; previous copies: %d"
              % (tag, len(prev)))
        rotate_previous(ROOT, prev, write=False)   # §3.7: report what rotation WOULD do
        return 0
    ts = time.strftime("%Y%m%d_%H%M%S")
    dstp = os.path.join(ROOT, "identity.db.bak_pre_%s_%s" % (tag, ts))
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst = sqlite3.connect(dstp)
    src.backup(dst)
    ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    copy = {t: (dst.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0], table_hash(dst, t))
            for t in ASSERTED}
    dst.close()
    print("[idbak] ASSERTION 1 integrity_check: %s | per-table content hashes: %s"
          % (ok, "MATCH" if all(copy[t][1] == live[t][1] for t in ASSERTED) else "MISMATCH"))
    print("[idbak] ASSERTION 2 row-counts copy==live over %s: %s (sessions EXCLUDED)"
          % (",".join(ASSERTED), "MATCH" if all(copy[t][0] == live[t][0] for t in ASSERTED) else "MISMATCH"))
    if ok != "ok" or any(copy[t] != live[t] for t in ASSERTED):
        os.remove(dstp)
        print("[idbak] FAILED — copy deleted (unvouchable PII is exposure without value); "
              "predecessor retained; class at retain-2 until a passing copy exists.")
        return 2
    if not rotate_previous(ROOT, prev, write=True):
        print("[idbak] PASS %s — but rotation ABORTED; resolve the named path, then "
              "rotate by hand or re-run." % os.path.basename(dstp))
        return 3
    if not prev:
        print("[idbak] first backup — no previous copy to rotate")
    print("[idbak] PASS %s (%d bytes, sha16 %s)" % (os.path.basename(dstp),
          os.path.getsize(dstp), hashlib.sha256(open(dstp,"rb").read()).hexdigest()[:16]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
