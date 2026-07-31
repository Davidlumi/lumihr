#!/usr/bin/env python3
"""Step 4a (D3, ruled at c3df1d3): strip the two IDENTITY keys — Company_Name and
Org_ID — from all 158 orgs.registry_json blobs. The 42 firmographic keys stay
(storage form (i): registry_json remains a reward-side attribute blob).

Both keys already exist identity-side (org_register.company_name /
.external_registry_id, 158/158 value-matched at step 2), so this is PURE REMOVAL
and reversible by construction — see the --verify-reversible mode.

SERIALISATION FIDELITY: the store holds two forms — 157 rows written by
seed_import's j() (ensure_ascii=False, literal non-ASCII) and 1 row rewritten by
put_strategy's plain json.dumps (ensure_ascii=True, escaped). This script detects
each row's own form and re-serialises in it, so the surviving keys are byte-identical
to their original serialisation, not normalised to one house style.

Deterministic: rows selected and updated by explicit org_id, ordered.
Guarded: rehearses unless BOTH --write AND --confirmed-by-david are passed.
"""
import json, os, sqlite3, sys

DB = os.environ.get("LUMI_DB", "lumi.db")
IDENTITY_KEYS = ("Company_Name", "Org_ID")
write_mode = "--write" in sys.argv and "--confirmed-by-david" in sys.argv


def form_of(parsed, original):
    """Which ensure_ascii setting reproduces this row's stored bytes."""
    if json.dumps(parsed, ensure_ascii=False) == original:
        return False
    if json.dumps(parsed, ensure_ascii=True) == original:
        return True
    return None            # neither → do not touch this row; report it


conn = sqlite3.connect(DB)
rows = conn.execute("SELECT org_id, registry_json FROM orgs "
                    "WHERE registry_json IS NOT NULL ORDER BY org_id").fetchall()
print("[4a] db=%s | blobs=%d" % (DB, len(rows)))

plan, unknown_form, missing_key = [], [], []
for org_id, rj in rows:
    d = json.loads(rj)
    if not all(k in d for k in IDENTITY_KEYS):
        missing_key.append(org_id); continue
    ea = form_of(d, rj)
    if ea is None:
        unknown_form.append(org_id); continue
    kept = {k: v for k, v in d.items() if k not in IDENTITY_KEYS}
    assert len(kept) == len(d) - 2
    plan.append((org_id, json.dumps(kept, ensure_ascii=ea), d, ea))

print("[4a] plan: %d rows to strip | rows missing a key: %d | rows of unknown serialisation: %d"
      % (len(plan), len(missing_key), len(unknown_form)))
assert not missing_key and not unknown_form, "refusing to run on an unexpected row shape"
assert len(plan) == len(rows)

if not write_mode:
    print("[4a] DRY RUN — no write.")
    sys.exit(0)

cur = conn.cursor()
for org_id, new_json, _orig, _ea in plan:
    cur.execute("UPDATE orgs SET registry_json=? WHERE org_id=?", (new_json, org_id))
    assert cur.rowcount == 1, org_id
conn.commit()

# --- post-write assertions -------------------------------------------------------
after = conn.execute("SELECT org_id, registry_json FROM orgs "
                     "WHERE registry_json IS NOT NULL ORDER BY org_id").fetchall()
assert len(after) == len(rows), "blob count changed"
ident_left = 0
content_ok = 0
by_id = {oid: (orig, ea) for oid, _n, orig, ea in plan}
for org_id, rj in after:
    d = json.loads(rj)
    ident_left += sum(1 for k in IDENTITY_KEYS if k in d)
    orig, ea = by_id[org_id]
    expected = {k: v for k, v in orig.items() if k not in IDENTITY_KEYS}
    if d == expected and json.dumps(d, ensure_ascii=ea) == rj:
        content_ok += 1
nulls = conn.execute("SELECT COUNT(*) FROM orgs WHERE registry_json IS NULL").fetchone()[0]
print("[4a] POST: identity keys remaining across all blobs: %d (expect 0)" % ident_left)
print("[4a] POST: surviving keys content- AND byte-faithful: %d/%d" % (content_ok, len(after)))
print("[4a] POST: null blobs untouched: %d (expect 65)" % nulls)
assert ident_left == 0 and content_ok == len(after) and nulls == 65
print("[4a] PASS")
