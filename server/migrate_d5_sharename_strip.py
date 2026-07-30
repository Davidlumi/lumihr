#!/usr/bin/env python3
"""D5 (ruled at c3df1d3, S7 rulings): strip the redundant own-name key from the 5
shares.config_json rows carrying it. Keyed on explicit rowids with asserted
preconditions — the script embeds no tokens. Guarded: rehearses (dry-run) unless
BOTH --write AND --confirmed-by-david are passed. DB from LUMI_DB (default lumi.db).

The client half of the class (web/js/pages.js — stop sending the key) ships in the
same commit; stripping at rest without stopping the source un-sticks on the next share.
"""
import hashlib, json, os, sys, sqlite3

DB = os.environ.get("LUMI_DB", "lumi.db")
ROWIDS = [92, 93, 97, 98, 118]          # ascending, explicit — no unordered iteration
write_mode = "--write" in sys.argv and "--confirmed-by-david" in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

total_before = conn.execute("SELECT COUNT(*) FROM shares").fetchone()[0]
namekey_before = sum(1 for (c,) in conn.execute("SELECT config_json FROM shares")
                     if "name" in (json.loads(c) if c else {}))
nontarget_hash_before = {r["rowid"]: hashlib.sha256((r["config_json"] or "").encode()).hexdigest()
                         for r in conn.execute("SELECT rowid, config_json FROM shares ORDER BY rowid")
                         if r["rowid"] not in ROWIDS}

# preconditions, asserted per named row
updates = []
for rid in ROWIDS:
    r = conn.execute("SELECT rowid, org_id, config_json FROM shares WHERE rowid=?", (rid,)).fetchone()
    assert r is not None, "rowid %d missing" % rid
    cfg = json.loads(r["config_json"])
    assert sorted(cfg) == ["cut", "cut_value", "name"], "rowid %d unexpected keys %s" % (rid, sorted(cfg))
    own = conn.execute("SELECT name FROM orgs WHERE org_id=?", (r["org_id"],)).fetchone()
    assert own is not None and cfg["name"] == own[0], "rowid %d name is not the share's own org name" % rid
    after = {k: v for k, v in cfg.items() if k != "name"}
    updates.append((rid, json.dumps(after, ensure_ascii=False)))

print("[d5] db=%s | shares total=%d | name-key rows=%d | targets=%s"
      % (DB, total_before, namekey_before, ROWIDS))
assert namekey_before == 5 and total_before == 122

if not write_mode:
    print("[d5] DRY RUN — no write. Would update %d rows by explicit rowid; key sets "
          "['cut','cut_value','name'] -> ['cut','cut_value']; all other rows untouched." % len(updates))
    sys.exit(0)

cur = conn.cursor()
for rid, new_cfg in updates:
    cur.execute("UPDATE shares SET config_json=? WHERE rowid=?", (new_cfg, rid))
    assert cur.rowcount == 1, "rowid %d: rowcount %d" % (rid, cur.rowcount)
conn.commit()

# post-write assertions
total_after = conn.execute("SELECT COUNT(*) FROM shares").fetchone()[0]
namekey_after = sum(1 for (c,) in conn.execute("SELECT config_json FROM shares")
                    if "name" in (json.loads(c) if c else {}))
assert total_after == 122, "row count moved: %d" % total_after
assert namekey_after == 0, "name keys remain: %d" % namekey_after
for rid in ROWIDS:
    cfg = json.loads(conn.execute("SELECT config_json FROM shares WHERE rowid=?", (rid,)).fetchone()[0])
    assert sorted(cfg) == ["cut", "cut_value"], "rowid %d post keys %s" % (rid, sorted(cfg))
nontarget_hash_after = {r["rowid"]: hashlib.sha256((r["config_json"] or "").encode()).hexdigest()
                        for r in conn.execute("SELECT rowid, config_json FROM shares ORDER BY rowid")
                        if r["rowid"] not in ROWIDS}
assert nontarget_hash_after == nontarget_hash_before, "a non-target row moved"
print("[d5] WRITE OK: 5 rows updated | shares=%d | name-key rows=%d | %d non-target rows byte-identical"
      % (total_after, namekey_after, len(nontarget_hash_after)))
