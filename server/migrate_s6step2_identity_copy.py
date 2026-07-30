#!/usr/bin/env python3
"""S6 step 2 (DECISIONS c3df1d3; spec S4.2): COPY identity into identity.db.

A COPY, not a move — the reward store is opened READ-ONLY (mode=ro URI) and must be
byte-identical afterwards. Rollback: delete identity.db, re-run init_identity_db.

Tables: org_register (223 from orgs: org_id/name/normalized_name + the two registry
identity keys parsed from registry_json, NULL for the 65 blob-less rows);
users / password_resets / invites whole, verbatim; sessions per the ruled
--sessions=copy|skip flag (D10 transmission §2.3 — David's call, expressed in the
invocation, never defaulted).

Deterministic: every extract ORDER BY its primary key. FK-constrained insert order:
org_register, users, then sessions/password_resets/invites (users first — token
tables FK users; invites.created_by FKs users; org_id columns are plain attachments
per D6). Guarded: rehearses (dry-run) unless BOTH --write AND --confirmed-by-david.
"""
import hashlib, json, os, sys, sqlite3

_here = os.path.dirname(os.path.abspath(__file__))
for _cand in (_here, os.path.join(os.getcwd(), "server")):
    if os.path.isfile(os.path.join(_cand, "identity.py")):
        sys.path.insert(0, _cand)
        break
import identity

SRC = os.environ.get("LUMI_DB", "lumi.db")
write_mode = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
sess_arg = [a for a in sys.argv if a.startswith("--sessions=")]
assert sess_arg, "state the sessions ruling explicitly: --sessions=copy or --sessions=skip"
SESSIONS_MODE = sess_arg[0].split("=", 1)[1]
assert SESSIONS_MODE in ("copy", "skip")

src = sqlite3.connect("file:%s?mode=ro" % SRC, uri=True)   # READ-ONLY, asserted by mode
src.row_factory = sqlite3.Row

AUTH_TABLES = [("users", "user_id"), ("sessions", "token"),
               ("password_resets", "token"), ("invites", "token")]


def _cols(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def _row_digest(rows):
    h = hashlib.sha256()
    for r in rows:
        h.update(("|".join("" if v is None else str(v) for v in r)).encode())
    return h.hexdigest()[:16]


# --- extraction (deterministic, ordered by PK) ------------------------------------
orgs_rows = src.execute(
    "SELECT org_id, name, normalized_name, registry_json FROM orgs ORDER BY org_id").fetchall()
org_register_rows = []
for r in orgs_rows:
    if r["registry_json"] is None:
        cn, xid = None, None
    else:
        reg = json.loads(r["registry_json"])
        cn, xid = reg.get("Company_Name"), reg.get("Org_ID")
    org_register_rows.append((r["org_id"], r["name"], r["normalized_name"], cn, xid))

auth_extract = {}
for table, pk in AUTH_TABLES:
    if table == "sessions" and SESSIONS_MODE == "skip":
        auth_extract[table] = None
        continue
    cols = _cols(src, table)
    auth_extract[table] = (cols, src.execute(
        "SELECT %s FROM %s ORDER BY %s" % (", ".join(cols), table, pk)).fetchall())

print("[s6s2] source=%s | sessions-mode=%s" % (SRC, SESSIONS_MODE))
print("[s6s2] extract: org_register=%d (registry-parsed=%d, blob-less NULL=%d)" %
      (len(org_register_rows),
       sum(1 for t in org_register_rows if t[3] is not None),
       sum(1 for t in org_register_rows if t[3] is None)))
for table, pk in AUTH_TABLES:
    v = auth_extract[table]
    print("[s6s2] extract: %s=%s" % (table, "SKIPPED (ruled)" if v is None else len(v[1])))

if not write_mode:
    print("[s6s2] DRY RUN — no write.")
    sys.exit(0)

# --- insert (FK order: org_register, users, then the token tables) ----------------
dst = identity.get_conn()
cur = dst.cursor()
for t in org_register_rows:
    cur.execute("INSERT INTO org_register(org_id, name, normalized_name, company_name, "
                "external_registry_id) VALUES (?,?,?,?,?)", t)
for table, pk in AUTH_TABLES:
    v = auth_extract[table]
    if v is None:
        continue
    cols, rows = v
    stmt = "INSERT INTO %s(%s) VALUES (%s)" % (table, ", ".join(cols), ",".join("?" * len(cols)))
    for r in rows:
        cur.execute(stmt, tuple(r))
dst.commit()

# --- parity census (counts, key-membership, digests — no values) ------------------
print("=== PARITY CENSUS ===")
ok = True

got = dst.execute("SELECT org_id, name, normalized_name, company_name, external_registry_id "
                  "FROM org_register ORDER BY org_id").fetchall()
src_dig = _row_digest(org_register_rows)
dst_dig = _row_digest([tuple(r) for r in got])
cn_nonnull = sum(1 for r in got if r["company_name"] is not None)
print("org_register: live-derived=%d copy=%d | row-digest equal: %s | company_name non-null=%d null=%d"
      % (len(org_register_rows), len(got), src_dig == dst_dig, cn_nonnull, len(got) - cn_nonnull))
ok &= (len(got) == len(org_register_rows) == 223) and src_dig == dst_dig and cn_nonnull == 158

for table, pk in AUTH_TABLES:
    v = auth_extract[table]
    if v is None:
        c = dst.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        print("sessions: SKIPPED by ruling | copy count=%d (expect 0)" % c)
        ok &= c == 0
        continue
    cols, rows = v
    got = dst.execute("SELECT %s FROM %s ORDER BY %s" % (", ".join(cols), table, pk)).fetchall()
    sdig, ddig = _row_digest([tuple(r) for r in rows]), _row_digest([tuple(r) for r in got])
    src_keys = {r[0] for r in src.execute("SELECT %s FROM %s" % (pk, table))}
    dst_keys = {r[0] for r in dst.execute("SELECT %s FROM %s" % (pk, table))}
    missing = len(src_keys - dst_keys) if table != "sessions" else len(dst_keys - src_keys)
    label = ("every source pk present in copy, missing=%d" if table != "sessions"
             else "every copied pk present live (<= rule), extra-in-copy=%d")
    print("%s: live=%d copy=%d | row-digest equal: %s | %s"
          % (table, len(rows), len(got), sdig == ddig, label % missing))
    ok &= (len(rows) == len(got)) and sdig == ddig and missing == 0

print("PARITY: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 2)
