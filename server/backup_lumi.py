#!/usr/bin/env python3
"""On-box rotation of the reward store (lumi.db) — DB class, retain-3.

The off-box S3 copy (deploy/offbox_backup.sh) and DLM EBS snapshots are the
disaster-recovery layers; this is the fast LOCAL rollback taken before a risky
change (a migration, a bulk edit). data/backup_policy.md DB class: "retain the
last 3 pre-diff backups". Naming convention, anchored:
lumi.db.bak_pre_<tag>_<YYYYMMDD_HHMMSS>.

Doctrine mirrors backup_identity.py (the proven delete-safe rotation): the copy
is made with the SQLite backup API after a checkpoint (never cp — a cp of a WAL
db is a torn copy); it is integrity-checked and row-count-vouched before any
previous copy is rotated; and rotation is FAIL-CLOSED — every candidate is
validated before any is deleted, one failure aborts with nothing removed.

    python3 server/backup_lumi.py --tag pre_migration            # dry run
    python3 server/backup_lumi.py --tag pre_migration --write --confirmed-by-david
"""
import glob, hashlib, os, re, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402  (the sanctioned live-store open)

# lightweight vouch: integrity + row-count on core tables (a full content hash of a
# ~90MB store is impractical and unnecessary for a local rollback copy).
ASSERTED = ("orgs", "users", "answers")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BAK_RE = re.compile(r"^lumi\.db\.bak_pre_[A-Za-z0-9]+_(\d{8}_\d{6})$")
RETAIN = 3                       # data/backup_policy.md DB class
LIVE_STORES = ("identity.db", "lumi.db")


def rotation_candidates(root):
    return sorted(glob.glob(os.path.join(root, "lumi.db.bak_pre_*")))


def deletion_violation(p, root):
    """Reason this path must NOT be deleted, or None if every guard passes."""
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
    bad = [(p, v) for p in prev for v in [deletion_violation(p, root)] if v]
    if bad:
        for p, v in bad:
            print("[lumibak] ROTATION ABORTED — %s: %s" % (p, v))
        print("[lumibak] fail-closed: NOTHING deleted (the just-created copy stands).")
        return False
    keep_prev = max(0, RETAIN - 1)   # the new copy is survivor #1
    by_ts = sorted(prev, key=lambda p: BAK_RE.match(os.path.basename(p)).group(1))
    doomed = by_ts[:len(by_ts) - keep_prev] if len(by_ts) > keep_prev else []
    for p in doomed:
        if write:
            os.remove(p)
        print("[lumibak] rotation: previous copy %s %s (retain-%d, creation-time doctrine)"
              % (os.path.basename(p), "deleted" if write else "WOULD be deleted", RETAIN))
    return True


def counts(conn):
    return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ASSERTED}


def main():
    write = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
    tag = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")), "manual")
    src = db.get_conn()
    live = counts(src)
    print("[lumibak] live census: %s" % live)
    prev = rotation_candidates(ROOT)
    if not write:
        print("[lumibak] DRY RUN — would create lumi.db.bak_pre_%s_<ts>; previous copies: %d" % (tag, len(prev)))
        rotate_previous(ROOT, prev, write=False)
        return 0
    ts = time.strftime("%Y%m%d_%H%M%S")
    dstp = os.path.join(ROOT, "lumi.db.bak_pre_%s_%s" % (tag, ts))
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst = sqlite3.connect(dstp)
    src.backup(dst)
    ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    copy = counts(dst)
    dst.close()
    print("[lumibak] integrity_check: %s | row-counts copy==live: %s"
          % (ok, "MATCH" if copy == live else "MISMATCH %s" % copy))
    if ok != "ok" or copy != live:
        os.remove(dstp)
        print("[lumibak] FAILED — copy deleted; previous copies retained.")
        return 2
    if not rotate_previous(ROOT, prev, write=True):
        print("[lumibak] PASS %s — but rotation aborted; resolve the named path by hand." % os.path.basename(dstp))
        return 3
    print("[lumibak] PASS %s (%d bytes, sha16 %s)"
          % (os.path.basename(dstp), os.path.getsize(dstp),
             hashlib.sha256(open(dstp, "rb").read()).hexdigest()[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
