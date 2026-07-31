#!/usr/bin/env python3
"""Step 4b (D11 OVERTURNED on measurement, ruled 31 July 2026): delete the write-only
reward-side meta key `registry_only_orgs`.

Grounds, both measured rather than assumed:
  * write-only — the count the API serves comes from meta.reconciliation (app.py reads
    recon["registry_only_orgs"]; pages.js renders it). Nothing reads the standalone key.
  * synthetic — all 52 names appear in data/seeded_orgs.json (210 entries = 158 matched
    + 52 unmatched); zero match any live org, member or staff.
Moving them identity-side would have put non-PII into the store whose retain-1 backup rule
is justified on it being a pure PII concentrate. Nothing is lost: the count survives in
meta.reconciliation, the names in a git-tracked file.

Guarded: rehearses unless BOTH --write AND --confirmed-by-david are passed.
"""
import json, os, sqlite3, sys

DB = os.environ.get("LUMI_DB", "lumi.db")
KEY = "registry_only_orgs"
write_mode = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

conn = sqlite3.connect(DB)
before = {k: v for k, v in conn.execute("SELECT key, value_json FROM meta")}
assert KEY in before, "key already absent — nothing to do"
names = json.loads(before[KEY])
recon_before = json.loads(before["reconciliation"])
print("[4b] db=%s | meta keys=%d | %s holds %d names | reconciliation count=%s"
      % (DB, len(before), KEY, len(names), recon_before.get(KEY)))
matching = [k for k in before if k == KEY]
assert len(matching) == 1, matching

if not write_mode:
    print("[4b] DRY RUN — would delete exactly 1 meta row (%r); every other key untouched." % KEY)
    sys.exit(0)

cur = conn.cursor()
cur.execute("DELETE FROM meta WHERE key=?", (KEY,))
assert cur.rowcount == 1, cur.rowcount
conn.commit()

after = {k: v for k, v in conn.execute("SELECT key, value_json FROM meta")}
assert KEY not in after
assert set(before) - set(after) == {KEY}, "more than the one key changed"
assert all(after[k] == before[k] for k in after), "a surviving key's value moved"
recon_after = json.loads(after["reconciliation"])
assert recon_after == recon_before and recon_after.get(KEY) == 52
print("[4b] POST: meta keys %d -> %d | removed exactly: %s" % (len(before), len(after), sorted(set(before)-set(after))))
print("[4b] POST: every surviving key byte-identical: True | reconciliation count still %s" % recon_after.get(KEY))
print("[4b] PASS")
