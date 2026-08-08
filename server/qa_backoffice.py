# -*- coding: utf-8 -*-
"""Back-office gate: the staff console's full surface — auth matrix, provisioning
(PH-PROV-1: atomic org+founding-invite, four firmographics, collision classes),
support actions, soft-deactivate, audit coverage, and secret/PII hygiene.

MUST run against a THROWAWAY: it creates orgs/users, deactivates accounts and
flips a platform_admin flag. Refuses to start without LUMI_DB set (gate-safety),
and aborts if the server on BASE turns out not to be reading the same DB file
(the canary check in section D). The atomicity check (D-seam) needs the server
launched with LUMI_QA_SEAMS=on (run_gates does this for srv_backoffice); it
degrades to a reported SKIP without it. Registration checks assume the server
runs with the production default (LUMI_OPEN_REGISTRATION unset -> closed).

Usage (the documented gate procedure — throwaway server ON :8060):
  LUMI_DB=... LUMI_IDENTITY_DB=... python3 qa_backoffice.py
"""
import hashlib, json, os, secrets, sqlite3, sys, urllib.request, urllib.error, http.cookiejar

BASE = os.environ.get("LUMI_QA_BASE", "http://localhost:8060")
DB = os.environ.get("LUMI_DB")
IDB = os.environ.get("LUMI_IDENTITY_DB")
if not DB:
    print("qa_backoffice: REFUSING to run without LUMI_DB (this gate writes orgs/users "
          "and deactivates accounts — throwaway only).")
    sys.exit(2)

PASS, FAIL, SKIP = [], [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  [" + str(detail)[:110] + "]") if detail else ""))

def skip(name, why):
    SKIP.append((name, why))
    print("  SKIP %s  [%s]" % (name, why))

def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def api(opener, path, method="GET", body=None, base=None):
    r = urllib.request.Request((base or BASE) + path, method=method)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(r, data=data, timeout=120)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"_http_status": e.code}

def book_fingerprint(db_path):
    """The canonical recipe, inlined from server/dbsnapshot.table_fingerprint and
    pinned by data/book_baseline.json — sha256, PK-ordered rows, first 16 hex."""
    import hashlib
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    h = hashlib.sha256(); n = 0
    for row in conn.execute(
            "SELECT org_id, snapshot_id, question_id, matrix_row_id, value, submitted_at "
            "FROM answers ORDER BY org_id, snapshot_id, question_id, matrix_row_id"):
        h.update(("\x1f".join("\x00" if v is None else str(v) for v in row) + "\x1e")
                 .encode("utf-8", "surrogatepass"))
        n += 1
    conn.close()
    return n, h.hexdigest()[:16]

STAFF = ("david@lumihr.co.uk", "lumi-demo-2026")
ORG_ADMIN = ("director@thornbridge.example", "lumi-demo-2026")
VIEWER = ("ceo@thornbridge.example", "lumi-view-2026")
TAG = secrets.token_hex(4)

BOOK_BEFORE = book_fingerprint(DB)
try:
    _bl = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "data", "book_baseline.json")))
    BASELINE = (_bl["rows"], _bl["hash16"])
except Exception:
    BASELINE = None

staff, tenant, anon = client(), client(), client()
st, _ = api(staff, "/api/auth/login", "POST", {"email": STAFF[0], "password": STAFF[1]})
assert st == 200, "staff login failed — is the throwaway server up on %s?" % BASE
api(tenant, "/api/auth/login", "POST", {"email": ORG_ADMIN[0], "password": ORG_ADMIN[1]})

# ---- A. gate matrix: every admin endpoint refuses anon (401) and tenant admin (403)
print("\n-- A. gate matrix --")
ADMIN_GETS = ["/api/admin/orgs", "/api/admin/suggestions", "/api/admin/pulses",
              "/api/admin/pulse-reviews", "/api/admin/backlog", "/api/admin/health",
              "/api/admin/config", "/api/admin/terms", "/api/admin/orders",
              "/api/admin/audit", "/api/admin/users/lookup?email=x@y.zz"]
a_bad = [(p, api(anon, p)[0]) for p in ADMIN_GETS]
check("A1 anon -> 401 on every admin GET", all(s == 401 for _, s in a_bad),
      [x for x in a_bad if x[1] != 401])
t_bad = [(p, api(tenant, p)[0]) for p in ADMIN_GETS]
check("A2 tenant admin -> 403 on every admin GET", all(s == 403 for _, s in t_bad),
      [x for x in t_bad if x[1] != 403])
ADMIN_POSTS = ["/api/admin/orgs", "/api/admin/pulses", "/api/admin/metrics/draft",
               "/api/admin/users/no-such-user/logout", "/api/admin/users/no-such-user/deactivate",
               "/api/admin/orgs/no-such-org/deactivate", "/api/admin/invites/no-such-token/revoke",
               "/api/notifications/run-sweep"]
t_post = [(p, api(tenant, p, "POST", {})[0]) for p in ADMIN_POSTS]
check("A3 tenant admin -> 403 on every admin POST (gate before validation)",
      all(s == 403 for _, s in t_post), [x for x in t_post if x[1] != 403])

# the pin: a platform_admin flag on a NON-allowlisted email must still be refused
raw = sqlite3.connect(DB); raw.row_factory = sqlite3.Row
vid = raw.execute("SELECT user_id FROM users WHERE role='viewer' LIMIT 1").fetchone()["user_id"]
raw.execute("UPDATE users SET platform_admin=1 WHERE user_id=?", (vid,)); raw.commit()
flipped = client()
api(flipped, "/api/auth/login", "POST", {"email": VIEWER[0], "password": VIEWER[1]})
st, _ = api(flipped, "/api/admin/health")
check("A4 flag WITHOUT allowlist email -> 403 (the pin holds)", st == 403, st)
raw.execute("UPDATE users SET platform_admin=0 WHERE user_id=?", (vid,)); raw.commit()

# ---- B. staff basics + response shapes
print("\n-- B. staff surface --")
st, me = api(staff, "/api/me")
check("B1 staff /api/me carries platform_admin", st == 200 and bool(me["user"].get("platform_admin")),
      me["user"].get("platform_admin"))
st, h = api(staff, "/api/admin/health")
check("B2 health: counts+storage+modes present", st == 200 and
      all(k in h for k in ("counts", "storage", "modes", "uptime_seconds")), list(h))
# Commit K (ruled 2026-08-08): the users floor DERIVES from the expected world —
# the staff org's users + the Thornbridge demo org's users, COUNTED LIVE at gate
# start. >=8 became >=4 when fixtures were deleted; a threshold hand-edited
# downward at every deletion eventually asserts nothing. Derived, the next
# deletion of anything OUTSIDE the expected set passes honestly, and deleting a
# demo or staff account fails loudly.
_idc = sqlite3.connect("file:%s?mode=ro" % IDB, uri=True); _idc.row_factory = sqlite3.Row
_demo = _idc.execute("SELECT org_id FROM users WHERE email=?", (ORG_ADMIN[0],)).fetchone()
_idc.close()
if _demo is None:
    check("B3 expected-world derivation (demo admin resolvable identity-side)", False,
          ORG_ADMIN[0])
    EXPECTED_MIN_USERS = 10**9   # force B3 to fail loudly rather than assert nothing
else:
    EXPECTED_MIN_USERS = raw.execute(
        "SELECT COUNT(*) c FROM users WHERE org_id=? OR org_id IN "
        "(SELECT org_id FROM orgs WHERE source='staff')", (_demo["org_id"],)).fetchone()["c"]
check("B3 health counts sane (orgs>=220, users>=derived %d, questions>0)" % EXPECTED_MIN_USERS,
      h["counts"]["orgs_total"] >= 220 and h["counts"]["users"] >= EXPECTED_MIN_USERS
      and h["counts"]["questions_active"] > 0,
      dict(h["counts"], derived_floor=EXPECTED_MIN_USERS))
st, cfg = api(staff, "/api/admin/config")
check("B4 config inventory served", st == 200 and len(cfg["config"]) >= 20, len(cfg.get("config", [])))

# ---- C. secret / PII hygiene
print("\n-- C. hygiene --")
check("C1 config: secret values NEVER serialised", all(
    v["value"] is None for v in cfg["config"] if v["kind"] == "secret"),
    [v["name"] for v in cfg["config"] if v["kind"] == "secret" and v["value"] is not None])
st, orders = api(staff, "/api/admin/orders")
check("C2 orders: no stripe session ids in the payload",
      "stripe_session_id" not in json.dumps(orders), )
st, terms = api(staff, "/api/admin/terms")
check("C3 platform-wide terms log carries NO emails (org-scoped only, by design)",
      "email" not in json.dumps([list(a.keys()) for a in terms["acceptances"]])
      and "@" not in json.dumps([a.get("org_name") or "" for a in terms["acceptances"]]))
st, lk = api(staff, "/api/admin/users/lookup?email=" + ORG_ADMIN[0])
check("C4 lookup: found, correct org, and NO pw_hash / tokens in payload",
      lk.get("found") and "pw_hash" not in json.dumps(lk) and "token" not in json.dumps(lk.get("user", {}).get("sessions", [])),
      list(lk.get("user", {})))

# ---- D. provisioning (PH-PROV-1: atomic org + founding-admin invite) --------
print("\n-- D. provisioning --")
# choices from the SAME accessor the member form uses (profile_choices via the API)
st, prof = api(staff, "/api/org-profile")
CH = prof["choices"]
FIRMO = {"industry": CH["industry"][0], "fte_band": CH["fte_band"][0],
         "hq_region": CH["hq_region"][0], "ownership_type": CH["ownership_type"][0]}
ORG_NAME = "QA Probe Org %s" % TAG
FOUNDER = "qa-founder-%s@probe.example" % TAG

st, _ = api(staff, "/api/admin/orgs", "POST",
            dict(FIRMO, org_name=ORG_NAME, admin_email="not-an-email"))
check("D1 bad admin_email refused", st == 400, st)
missing = dict(FIRMO, org_name=ORG_NAME, admin_email=FOUNDER); missing.pop("ownership_type")
st, r = api(staff, "/api/admin/orgs", "POST", missing)
check("D2 missing firmographic refused (all four required)", st == 400 and "ownership_type" in r.get("detail", ""), r)
st, r = api(staff, "/api/admin/orgs", "POST",
            dict(FIRMO, org_name=ORG_NAME, admin_email=FOUNDER, industry="Not A Real Industry"))
check("D3 non-registry industry refused via profile_choices", st == 400, r)
st, _ = api(staff, "/api/admin/orgs", "POST", dict(FIRMO, org_name="   ", admin_email=FOUNDER))
check("D4 blank name refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs", "POST",
            dict(FIRMO, org_name=ORG_NAME, admin_email=STAFF[0]))
check("D5 admin_email with an existing account refused", st == 400, st)

# the real provision — deliberately carrying BOTH seam flags (Stage 3 §2.1): this
# gate's main server runs the PRODUCTION posture (LUMI_QA_SEAMS unset), so the
# injection branches must be no-ops and the call must complete fully. Behaviour
# asserted, not the env read: a seams-on server would 500 here instead.
st, created = api(staff, "/api/admin/orgs", "POST",
                  dict(FIRMO, org_name=ORG_NAME, admin_email=FOUNDER,
                       _qa_fail_after_org=True, _qa_fail_identity=True))
# details deliberately EXCLUDE the response body: invite_link is a bearer token
# and this gate's stdout lands in the suite log (PH-PROV-1d — same defect class
# as recon's key printing; a throwaway token in a log is still a token in a log).
check("D6 seam INERT by default: provision with both injection flags completes normally",
      st == 200 and created.get("ok"), (st, created.get("org_id")))
check("D7 provision ok: org + invite link + expiry in one call",
      st == 200 and created.get("ok") and "/app#/invite/" in created.get("invite_link", "")
      and created.get("expires_days"), (st, created.get("org_id"), created.get("expires_days")))
if IDB and os.path.exists(IDB) and st == 200:
    _idc = sqlite3.connect("file:%s?mode=ro" % IDB, uri=True)
    _reg = _idc.execute("SELECT COUNT(*) FROM org_register WHERE org_id=?",
                        (created["org_id"],)).fetchone()[0]
    _inv = _idc.execute("SELECT COUNT(*) FROM invites WHERE org_id=?",
                        (created["org_id"],)).fetchone()[0]
    _idc.close()
    check("D6b inert proof completes IDENTITY-side too (org_register + invite twin written)",
          _reg == 1 and _inv == 1, (_reg, _inv))
else:
    skip("D6b identity-side inert proof", "LUMI_IDENTITY_DB unset")
POID = created.get("org_id")
row = raw.execute("SELECT * FROM orgs WHERE org_id=?", (POID,)).fetchone()
if row is None:
    print("qa_backoffice: ABORT — the server on %s is NOT reading LUMI_DB=%s "
          "(canary org missing). Wrong server/DB pairing." % (BASE, DB))
    sys.exit(2)
check("D8 org row: source=signup, full tier, clock NULL, submission 0",
      row["source"] == "signup" and row["tier_entitlement"] == "full"
      and row["clock_start"] is None and row["submission_complete"] == 0, dict(row))
check("D9 classified=1 DERIVED from four populated PROFILE_CORE fields",
      row["classified"] == 1 and all(row[f] == FIRMO[f] for f in FIRMO),
      {f: row[f] for f in FIRMO})
check("D10 re-pollution guard: orgs.name / orgs.normalized_name NOT written",
      row["name"] is None and row["normalized_name"] is None)
irow = raw.execute("SELECT role, created_by, used_at FROM invites WHERE org_id=?", (POID,)).fetchone()
check("D11 invite row in the SAME transaction: role=admin, staff-created, unused",
      irow is not None and irow["role"] == "admin" and irow["used_at"] is None, dict(irow) if irow else None)

# ---- PH-PROV-1g: at most one live admin invite per org -----------------------
itok = created["invite_link"].rsplit("/", 1)[-1]
api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
    {"email": "qa-cv-%s@probe.example" % TAG, "role": "contributor"})
api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
    {"email": "qa-vv-%s@probe.example" % TAG, "role": "viewer"})
st, re1 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
              {"email": FOUNDER, "role": "admin"})
itok2 = re1.get("link", "").rsplit("/", 1)[-1]
n_admin_live = raw.execute("SELECT COUNT(*) FROM invites WHERE org_id=? AND role='admin' "
                           "AND used_at IS NULL", (POID,)).fetchone()[0]
check("G1 reissue supersedes the prior: exactly ONE live admin invite",
      st == 200 and n_admin_live == 1 and itok2 and itok2 != itok, (st, n_admin_live))
st, _ = api(anon, "/api/invite/" + itok)
check("G2a superseded token: invite-info 404", st == 404, st)
st, _ = api(anon, "/api/auth/accept-invite", "POST",
            {"token": itok, "password": "should-never-work-1", "accept_platform_terms": True})
check("G2b superseded token REFUSED at accept — the credential is dead, not just a column",
      st == 400, st)
n_team = raw.execute("SELECT COUNT(*) FROM invites WHERE org_id=? AND "
                     "role IN ('contributor','viewer') AND used_at IS NULL", (POID,)).fetchone()[0]
check("G3 contributor + viewer invites untouched by the admin reissue", n_team == 2, n_team)
st, aud_g = api(staff, "/api/admin/audit?limit=3")
dig_old = hashlib.sha256(itok.encode()).hexdigest()[:12]
check("G4 audit records the supersession by sha256[:12] digest, never the bearer",
      any(e["action"] == "org.invite" and e.get("detail_json")
          and dig_old in e["detail_json"] and "superseded" in e["detail_json"]
          for e in aud_g["entries"])
      and itok not in json.dumps(aud_g["entries"]))
itok = itok2   # the accept below joins on the LIVE (reissued) invite

# collision classes (ruling §6: classify via org_register hit -> reward source)
seed_name = None
if IDB and os.path.exists(IDB):
    idraw = sqlite3.connect("file:%s?mode=ro" % IDB, uri=True); idraw.row_factory = sqlite3.Row
    seed_ids = {r[0] for r in raw.execute("SELECT org_id FROM orgs WHERE source='seed'")}
    for r in idraw.execute("SELECT org_id, name FROM org_register"):
        if r["org_id"] in seed_ids:
            seed_name = r["name"]; break
    idraw.close()
if seed_name:
    st, r = api(staff, "/api/admin/orgs", "POST",
                dict(FIRMO, org_name=seed_name, admin_email="qa-x-%s@probe.example" % TAG))
    check("D12 collision vs SEED org names the class", st == 400 and "seed" in r.get("detail", ""), r)
else:
    skip("D12 collision vs seed", "LUMI_IDENTITY_DB unset or no seed name resolvable")
st, r = api(staff, "/api/admin/orgs", "POST",
            dict(FIRMO, org_name=ORG_NAME.upper() + "!!", admin_email="qa-y-%s@probe.example" % TAG))
check("D13 collision vs MEMBER org (normalized) names the class",
      st == 400 and "member" in r.get("detail", ""), r)

# the founding admin joins through the standard accept path — via the LIVE
# (reissued) token, which the G-block above left in `itok`
FPW = "qa-probe-pass-%s" % TAG
st, _ = api(anon, "/api/auth/accept-invite", "POST",
            {"token": itok, "password": FPW, "accept_platform_terms": True, "display_name": "QA Founder"})
check("D14 founding admin joins (own password + terms)", st == 200, st)
st, d = api(staff, "/api/admin/orgs/" + POID)
check("D15 member (role=admin) + platform-terms row now on the org",
      any(u["email"] == FOUNDER and u["role"] == "admin" for u in d["users"]) and
      any(t["kind"] == "platform" and t["email"] == FOUNDER for t in d["terms"]))
FUID = next(u["user_id"] for u in d["users"] if u["email"] == FOUNDER)
# PH-PROV-1g §2.2 — the boundary of the carve-out: once an Admin is ACTIVE,
# admin invites refuse and point at promotion.
st, r = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
            {"email": "qa-second-admin-%s@probe.example" % TAG, "role": "admin"})
check("G5 with an ACTIVE Admin, admin invite refused pointing at promotion",
      st == 400 and "promotion" in r.get("detail", ""), (st, r.get("detail", "")[:70]))
# reissue path survives alongside creation (ruling §3)
st, inv2 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
               {"email": "qa-temp-%s@probe.example" % TAG, "role": "viewer"})
tok2 = inv2.get("link", "").rsplit("/", 1)[-1]
check("D16 reissue route still mints invites post-creation", st == 200 and tok2, st)
st, _ = api(staff, "/api/admin/invites/%s/revoke" % tok2, "POST", {})
check("D17 revoke ok", st == 200, st)
st, _ = api(anon, "/api/invite/" + tok2)
check("D18 revoked invite link dead (404)", st == 404, st)
st, _ = api(staff, "/api/admin/invites/%s/revoke" % tok2, "POST", {})
check("D19 double-revoke refused", st == 400, st)

# ---- L. lifecycle derivation (PH-PROV-2b §1) — every state fixtured ----------
print("\n-- L. lifecycle --")
st, lr = api(staff, "/api/admin/orgs", "POST",
             dict(FIRMO, org_name="QA Lifecycle Org %s" % TAG,
                  admin_email="qa-lc-%s@probe.example" % TAG))
LOID = lr["org_id"]

def _lc(oid):
    _, d0 = api(staff, "/api/admin/orgs")
    return next(o["lifecycle"] for o in d0["orgs"] if o["org_id"] == oid)

lc = _lc(LOID)
check("L1 provisioned + live invite (expiry present)",
      lc and lc["state"] == "provisioned" and lc["invite_live"] and lc["invite_expires_at"], lc)
# age the invite in BOTH stores — expires_at is an invariant compared column in
# identity_recon's invites pair; a reward-only fixture edit IS the drift the net
# exists to catch (it did, on this gate's first run — kept honest here).
raw.execute("UPDATE invites SET expires_at=datetime('now','-1 day') WHERE org_id=?", (LOID,))
raw.commit()
if IDB and os.path.exists(IDB):
    _aged = raw.execute("SELECT token, expires_at FROM invites WHERE org_id=?", (LOID,)).fetchall()
    _idw = sqlite3.connect(IDB)
    for _r in _aged:
        _idw.execute("UPDATE invites SET expires_at=? WHERE token=?", (_r["expires_at"], _r["token"]))
    _idw.commit()
    _idw.close()
lc = _lc(LOID)
check("L2 provisioned + NO LIVE INVITE — the attention state",
      lc and lc["state"] == "provisioned" and not lc["invite_live"], lc)
st, dd = api(staff, "/api/admin/orgs/" + LOID)
check("L2b detail lists the expired invite distinctly (expired=true, still visible)",
      any(i.get("expired") for i in dd.get("invites", [])), dd.get("invites"))
check("L3 activated — a users row exists (the accept minted it)",
      _lc(POID)["state"] == "activated", _lc(POID))
raw.execute("UPDATE orgs SET clock_start=datetime('now') WHERE org_id=?", (LOID,)); raw.commit()
check("L4 contributing — clock started", _lc(LOID)["state"] == "contributing")
raw.execute("UPDATE orgs SET submission_complete=1 WHERE org_id=?", (LOID,)); raw.commit()
check("L5 complete — and it outranks contributing", _lc(LOID)["state"] == "complete")
_, d0 = api(staff, "/api/admin/orgs")
check("L6 seed orgs NEVER receive a member-lifecycle label",
      all(o["lifecycle"] is None for o in d0["orgs"] if o["source"] == "seed"))
check("L7 the staff org carries no member lifecycle",
      all(o["lifecycle"] is None for o in d0["orgs"] if o["source"] == "staff"))
api(staff, "/api/admin/orgs/%s/deactivate" % LOID, "POST", {"reason": "L8 overlay probe"})
_, d0 = api(staff, "/api/admin/orgs")
row0 = next(o for o in d0["orgs"] if o["org_id"] == LOID)
check("L8 deactivation is an OVERLAY: flag true, lifecycle still 'complete'",
      row0["deactivated"] and row0["lifecycle"] and row0["lifecycle"]["state"] == "complete",
      row0.get("lifecycle"))
api(staff, "/api/admin/orgs/%s/reactivate" % LOID, "POST", {})

# ---- S. fault injection (Stage 3 §1, Outcome A): a SHORT-LIVED second server
# ---- with LUMI_QA_SEAMS=on — the main server stays production-postured -------
print("\n-- S. seams (fault injection on :8061) --")
import subprocess, time
SRV_DIR = os.path.dirname(os.path.abspath(__file__))
BASE2 = "http://localhost:8061"
seam_env = dict(os.environ, LUMI_QA_SEAMS="on", ANTHROPIC_API_KEY="", ANTHROPIC_AUTH_TOKEN="")
# PH-LOG-1: server logs carry console-emailed links — 0600 explicitly, so a
# standalone run (no run_gates umask) is just as contained.
_seam_log = os.path.join(os.environ.get("TMPDIR", "/tmp"), "qa_backoffice_seam_8061.log")
seam_proc = subprocess.Popen(
    [sys.executable, "-u", "-m", "uvicorn", "app:app", "--port", "8061"],   # -u: S7 reads the log live
    cwd=SRV_DIR, env=seam_env,
    stdout=os.fdopen(os.open(_seam_log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"),
    stderr=subprocess.STDOUT)
try:
    up = False
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE2 + "/api/legal", timeout=2); up = True; break
        except Exception:
            time.sleep(0.5)
    if not up:
        check("S0 seam server (:8061) came up", False, "did not answer /api/legal in 30s")
    else:
        seam = client()
        st, _ = api(seam, "/api/auth/login", "POST",
                    {"email": STAFF[0], "password": STAFF[1]}, base=BASE2)
        check("S0 seam server up + staff login", st == 200, st)
        # S1: §7.7 — forced failure BETWEEN the two reward inserts rolls back whole
        n_before = raw.execute("SELECT COUNT(*) FROM orgs").fetchone()[0]
        st, r = api(seam, "/api/admin/orgs", "POST",
                    dict(FIRMO, org_name="QA Seam Rollback %s" % TAG,
                         admin_email="qa-seam-%s@probe.example" % TAG,
                         _qa_fail_after_org=True), base=BASE2)
        n_after = raw.execute("SELECT COUNT(*) FROM orgs").fetchone()[0]
        check("S1 forced failure after org insert -> 500 + rollback (no orphan org)",
              st == 500 and "nothing was created" in r.get("detail", "") and n_before == n_after,
              (st, n_before, n_after))
        # S2: the post-reward-commit identity failure — the SILENT orphan — and the
        # net that must catch it, naming the org_id (Stage 3 §1 Outcome A).
        st, r = api(seam, "/api/admin/orgs", "POST",
                    dict(FIRMO, org_name="QA Seam Orphan %s" % TAG,
                         admin_email="qa-orphan-%s@probe.example" % TAG,
                         _qa_fail_identity=True), base=BASE2)
        check("S2a identity-failure seam: response is the silent 200",
              st == 200 and r.get("ok"), (st, r.get("org_id")))
        ORPH = r.get("org_id")
        ORPH_TOK = r.get("invite_link", "").rsplit("/", 1)[-1]
        orow = raw.execute("SELECT COUNT(*) FROM orgs WHERE org_id=?", (ORPH,)).fetchone()[0]
        if IDB and os.path.exists(IDB):
            _idc = sqlite3.connect("file:%s?mode=ro" % IDB, uri=True)
            ireg = _idc.execute("SELECT COUNT(*) FROM org_register WHERE org_id=?", (ORPH,)).fetchone()[0]
            _idc.close()
            check("S2b the orphan exists: reward org row present, org_register twin MISSING",
                  orow == 1 and ireg == 0, (orow, ireg))
            rec = subprocess.run([sys.executable, "identity_recon.py"], cwd=SRV_DIR,
                                 env=dict(os.environ), capture_output=True, text=True)
            check("S2c identity_recon FAILS (nonzero exit) on the orphan",
                  rec.returncode != 0 and "FAIL" in rec.stdout, rec.returncode)
            check("S2d recon output NAMES the orphan org_id and both orphan rows",
                  ORPH in rec.stdout
                  and "reward-only (identity orphan missing)=1" in rec.stdout.split("orgs<->org_register")[1].split("\n")[0]
                  and "reward-only (identity orphan missing)=1" in rec.stdout.split("invites:")[1].split("\n")[0],
                  [l for l in rec.stdout.splitlines() if "reward-only" in l and "=1" in l])
            # PH-PROV-1d: the BEARER never appears; the labelled digest does; and the
            # printed locator (org_id) suffices to find the row — the operator query.
            dig = hashlib.sha256(ORPH_TOK.encode()).hexdigest()[:12]
            check("S2e recon output contains NO substring of the real invite token",
                  bool(ORPH_TOK) and ORPH_TOK not in rec.stdout)
            check("S2f recon output carries the labelled digest instead",
                  ("token_sha256[:12]=%s" % dig) in rec.stdout, dig)
            loc = raw.execute("SELECT token FROM invites WHERE org_id=?", (ORPH,)).fetchone()
            check("S2g operator lookup: printed org_id locates the row; its token hashes to the digest",
                  loc is not None and hashlib.sha256(loc["token"].encode()).hexdigest()[:12] == dig)
            # S3: remove the manufactured orphan; the net must read clean again
            raw.execute("DELETE FROM invites WHERE org_id=?", (ORPH,))
            raw.execute("DELETE FROM orgs WHERE org_id=?", (ORPH,))
            raw.commit()
            rec2 = subprocess.run([sys.executable, "identity_recon.py"], cwd=SRV_DIR,
                                  env=dict(os.environ), capture_output=True, text=True)
            check("S3 orphan removed -> identity_recon PASS again (rc 0)",
                  rec2.returncode == 0 and "PASS" in rec2.stdout, rec2.returncode)
        else:
            skip("S2b-S3 orphan + recon assertions", "LUMI_IDENTITY_DB unset")
        # S5: PH-PROV-1g §2.3 — the creation-time anomaly assertion is provably
        # live: plant a pre-existing admin invite mid-transaction, fail closed.
        n_orgs0 = raw.execute("SELECT COUNT(*) FROM orgs").fetchone()[0]
        st, r = api(seam, "/api/admin/orgs", "POST",
                    dict(FIRMO, org_name="QA Seam Anomaly %s" % TAG,
                         admin_email="qa-anom-%s@probe.example" % TAG,
                         _qa_inject_prior_invite=True), base=BASE2)
        check("S5 creation meeting a pre-existing admin invite fails closed (no org row survives)",
              st == 500 and "anomaly" in r.get("detail", "")
              and raw.execute("SELECT COUNT(*) FROM orgs").fetchone()[0] == n_orgs0,
              (st, r.get("detail", "")[:60]))
        # S6: PH-PROV-1g §3.6 — reissue atomicity: a failure between invalidate
        # and insert changes NOTHING (prior invite still live, no new row).
        st, ry = api(seam, "/api/admin/orgs", "POST",
                     dict(FIRMO, org_name="QA Seam Reissue %s" % TAG,
                          admin_email="qa-ry-%s@probe.example" % TAG), base=BASE2)
        YOID = ry.get("org_id")
        ytok = ry.get("invite_link", "").rsplit("/", 1)[-1]
        st, r = api(seam, "/api/admin/orgs/%s/invite" % YOID, "POST",
                    {"email": "qa-ry2-%s@probe.example" % TAG, "role": "admin",
                     "_qa_fail_after_invalidate": True}, base=BASE2)
        yrow = raw.execute("SELECT used_at FROM invites WHERE token=?", (ytok,)).fetchone()
        ycount = raw.execute("SELECT COUNT(*) FROM invites WHERE org_id=? AND role='admin'",
                             (YOID,)).fetchone()[0]
        check("S6 forced failure between invalidate and insert -> 500, prior invite STILL LIVE, no new row",
              st == 500 and "nothing changed" in r.get("detail", "")
              and yrow is not None and yrow["used_at"] is None and ycount == 1, (st, ycount))
        # S7 (PH-PROV-1f): the provisioning invite's console-email fallback logs
        # a DIGEST, never the bearer — the API response already hands the
        # operator the link. Asserted on the seam server's CAPTURED stdout.
        st, r1f = api(seam, "/api/admin/orgs/%s/invite" % YOID, "POST",
                      {"email": "qa-1f-%s@probe.example" % TAG, "role": "viewer"}, base=BASE2)
        tok1f = r1f.get("link", "").rsplit("/", 1)[-1]
        time.sleep(1.0)   # child runs -u; a beat for the print to land
        logtxt = open(_seam_log, errors="replace").read()
        dig1f = hashlib.sha256(tok1f.encode()).hexdigest()[:12]
        check("S7a (1f) provisioning invite bearer appears NOWHERE in the server log",
              st == 200 and bool(tok1f) and tok1f not in logtxt, st)
        check("S7b (1f) the log carries the labelled digest instead",
              ("token sha256[:12]=%s" % dig1f) in logtxt, dig1f)
finally:
    seam_proc.terminate()
    try:
        seam_proc.wait(timeout=10)
    except Exception:
        seam_proc.kill()

# S4: the REVERSE direction (identity-only orphan) — no seam needed: a normally
# dual-written invite has its reward row deleted, leaving the identity twin.
if IDB and os.path.exists(IDB):
    st, inv4 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
                   {"email": "qa-rev-%s@probe.example" % TAG, "role": "viewer"})
    TOK4 = inv4.get("link", "").rsplit("/", 1)[-1]
    raw.execute("DELETE FROM invites WHERE token=?", (TOK4,)); raw.commit()
    rec3 = subprocess.run([sys.executable, "identity_recon.py"], cwd=SRV_DIR,
                          env=dict(os.environ), capture_output=True, text=True)
    dig4 = hashlib.sha256(TOK4.encode()).hexdigest()[:12]
    check("S4a reverse orphan detected (identity-only=1 on invites)",
          rec3.returncode != 0 and
          "identity-only (reverse orphan)=1" in rec3.stdout.split("invites:")[1].split("\n")[0])
    check("S4b reverse direction: real token absent, labelled digest present",
          TOK4 not in rec3.stdout and ("token_sha256[:12]=%s" % dig4) in rec3.stdout, dig4)
    idw = sqlite3.connect(IDB)
    idw.execute("DELETE FROM invites WHERE token=?", (TOK4,)); idw.commit(); idw.close()
    rec4 = subprocess.run([sys.executable, "identity_recon.py"], cwd=SRV_DIR,
                          env=dict(os.environ), capture_output=True, text=True)
    check("S4c cleanup -> recon PASS again (rc 0)", rec4.returncode == 0, rec4.returncode)
else:
    skip("S4 reverse-direction orphan", "LUMI_IDENTITY_DB unset")

# ---- R. registration + tenant-invite guards (PH-PROV-1 §2.2/§2.3) -----------
print("\n-- R. registration & carve-out --")
st, r = api(anon, "/api/auth/register", "POST",
            {"org_name": "QA Reg Probe %s" % TAG, "email": "qa-reg-%s@probe.example" % TAG,
             "password": "long-enough-pass", "accept_platform_terms": True})
check("R1 self-serve register -> 403 with enquiry pointer (default closed)",
      st == 403 and "hello@lumihr.co.uk" in r.get("detail", ""), r)
# PH-PROV-1b (built 2026-08-08): tenant invite role=admin is an EXPLICIT 400
# pointing at promotion — no invite row is minted for the attempt.
n_inv0 = raw.execute("SELECT COUNT(*) c FROM invites").fetchone()["c"]
st, tinv = api(tenant, "/api/team/invite", "POST",
               {"email": "qa-coerce-%s@probe.example" % TAG, "role": "admin"})
n_inv1 = raw.execute("SELECT COUNT(*) c FROM invites").fetchone()["c"]
check("R2 (1b) /api/team/invite role=admin -> explicit 400 pointing at promotion",
      st == 400 and "promotion" in tinv.get("detail", ""), (st, tinv.get("detail", "")[:60]))
check("R2b (1b) the refused attempt minted NO invite row", n_inv1 == n_inv0, (n_inv0, n_inv1))

# ---- E. support actions
print("\n-- E. support --")
st, r = api(staff, "/api/admin/users/%s/reset-link" % FUID, "POST", {})
check("E1 staff reset link minted (2h)", st == 200 and "/app#/reset/" in r.get("link", "")
      and r.get("expires_in_hours") == 2, (st, r.get("expires_in_hours")))   # link redacted: bearer
founder = client()
st, _ = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 1
check("E2 probe member can sign in", st == 200, st)
st, r = api(staff, "/api/admin/users/%s/logout" % FUID, "POST", {})
check("E3 force sign-out revokes >=1 session", st == 200 and r.get("sessions_revoked", 0) >= 1, r)
st, _ = api(founder, "/api/me")
check("E4 their session is dead", st == 401, st)
st, _ = api(staff, "/api/admin/users/no-such-user/reset-link", "POST", {})
check("E5 reset-link for unknown user -> 404", st == 404, st)

# ---- F. soft-deactivate matrix
print("\n-- F. soft-deactivate --")
api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})           # login 2
# PH-PAY-3: a suspension always carries WHY — reasonless deactivation refused
st, r = api(staff, "/api/admin/users/%s/deactivate" % FUID, "POST", {})
check("F0 (PAY-3) user deactivate WITHOUT a reason -> 400 with the operator hint",
      st == 400 and "reason" in r.get("detail", "").lower(), r.get("detail", "")[:60])
st, r = api(staff, "/api/admin/users/%s/deactivate" % FUID, "POST",
            {"reason": "sole-admin recovery in progress"})
check("F1 deactivate user (with reason)", st == 200, r)
st, _ = api(founder, "/api/me")
check("F2 live session dies at deactivation", st == 401, st)
st, r = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 3
check("F3 relogin 403 with the honest message", st == 403 and "deactivated" in r.get("detail", ""), r)
st, _ = api(staff, "/api/admin/users/%s/deactivate" % FUID, "POST",
            {"reason": "double-deactivate probe"})
check("F4 double-deactivate refused", st == 400, st)
st, lk = api(staff, "/api/admin/users/lookup?email=" + FOUNDER)
check("F5 lookup shows disabled_at", bool(lk["user"].get("disabled_at")), lk["user"].get("disabled_at"))
check("F5b (PAY-3) lookup shows the suspension reason",
      lk["user"].get("disabled_reason") == "sole-admin recovery in progress",
      lk["user"].get("disabled_reason"))
st, _ = api(staff, "/api/admin/users/%s/reactivate" % FUID, "POST", {})
check("F6 reactivate", st == 200, st)
st, lk = api(staff, "/api/admin/users/lookup?email=" + FOUNDER)
check("F6b (PAY-3) reactivation clears the reason (audit keeps history)",
      lk["user"].get("disabled_reason") is None, lk["user"].get("disabled_reason"))
st, _ = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 4
check("F7 relogin works after reactivate", st == 200, st)
# org level — mint a fresh invite first so the accept-during-deactivation path is testable
st, inv3 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
               {"email": "qa-second-%s@probe.example" % TAG, "role": "viewer"})
tok3 = inv3["link"].rsplit("/", 1)[-1]
st, r = api(staff, "/api/admin/orgs/%s/deactivate" % POID, "POST", {})
check("F7b (PAY-3) org deactivate WITHOUT a reason -> 400", st == 400, st)
st, r = api(staff, "/api/admin/orgs/%s/deactivate" % POID, "POST", {"reason": "unpaid invoice"})
check("F8 deactivate org (revokes member sessions)", st == 200 and r.get("sessions_revoked", 0) >= 1, r)
st, _ = api(founder, "/api/me")
check("F9 member context gone (401)", st == 401, st)
st, r = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 5
check("F10 member login 403 with the org message", st == 403 and "organisation" in r.get("detail", ""), r)
st, _ = api(anon, "/api/auth/accept-invite", "POST",
            {"token": tok3, "password": "irrelevant-123", "accept_platform_terms": True})
check("F11 accept-invite into a deactivated org refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
            {"email": "qa-third-%s@probe.example" % TAG, "role": "viewer"})
check("F12 staff invite into a deactivated org refused", st == 400, st)
st, orgs = api(staff, "/api/admin/orgs")
check("F13 orgs list flags it deactivated",
      any(o["org_id"] == POID and o.get("deactivated") for o in orgs["orgs"]))
check("F13b (PAY-3) the list carries the suspension reason",
      any(o["org_id"] == POID and o.get("deactivated_reason") == "unpaid invoice"
          for o in orgs["orgs"]))
st, _ = api(staff, "/api/admin/orgs/%s/reactivate" % POID, "POST", {})
check("F14 reactivate org", st == 200, st)
st, orgs = api(staff, "/api/admin/orgs")
check("F14b (PAY-3) reactivation clears the org reason",
      any(o["org_id"] == POID and o.get("deactivated_reason") is None for o in orgs["orgs"]))
st, _ = api(anon, "/api/auth/accept-invite", "POST",
            {"token": tok3, "password": "qa-second-pass-1", "accept_platform_terms": True})
check("F15 the held invite completes after reactivation", st == 200, st)
# guards
soid = raw.execute("SELECT org_id FROM orgs WHERE source='staff'").fetchone()["org_id"]
st, _ = api(staff, "/api/admin/orgs/%s/deactivate" % soid, "POST", {})
check("F16 staff org refuses deactivation", st == 400, st)
suid = raw.execute("SELECT user_id FROM users WHERE platform_admin=1").fetchone()["user_id"]
st, _ = api(staff, "/api/admin/users/%s/deactivate" % suid, "POST", {})
check("F17 platform-admin account refuses deactivation", st == 400, st)

# ---- G. audit coverage + hygiene
print("\n-- G. audit --")
st, aud = api(staff, "/api/admin/audit?limit=500")
acts = [e["action"] for e in aud["entries"]]
NEED = ["org.create", "org.invite", "org.invite_revoke", "user.reset_link", "user.force_logout",
        "user.deactivate", "user.reactivate", "org.deactivate", "org.reactivate"]
check("G1 every action class from this run is on the trail",
      all(a in acts for a in NEED), [a for a in NEED if a not in acts])
check("G2 every entry attributes the staff actor",
      all(e.get("actor_email") == STAFF[0] for e in aud["entries"]),
      {e.get("actor_email") for e in aud["entries"]})
check("G3 no emails and no org names in stored audit detail (split doctrine)",
      "@" not in json.dumps([e.get("detail_json") for e in aud["entries"]])
      and ORG_NAME not in json.dumps([e.get("detail_json") for e in aud["entries"]]))
st, aud2 = api(staff, "/api/admin/audit?limit=notanumber")
check("G4 garbage limit falls back cleanly", st == 200 and len(aud2["entries"]) <= 200, st)
st, aud3 = api(staff, "/api/admin/audit?limit=999999")
check("G5 limit clamped to 1000", st == 200 and len(aud3["entries"]) <= 1000, len(aud3.get("entries", [])))

# ---- I. invariants: the book and the six identity columns -------------------
print("\n-- I. invariants --")
BOOK_AFTER = book_fingerprint(DB)
check("I1 answer book untouched by this gate (before == after)",
      BOOK_BEFORE == BOOK_AFTER, (BOOK_BEFORE, BOOK_AFTER))
if BASELINE:
    if BOOK_BEFORE != tuple(BASELINE):
        print("  NOTE I2: gate-start book %s differs from data/book_baseline.json %s — "
              "an earlier suite gate touched answers on THIS throwaway, or the baseline "
              "needs a re-record against live. Informational here; the live assertion "
              "belongs to the §7 verification." % (BOOK_BEFORE, tuple(BASELINE)))
    else:
        print("  NOTE I2: gate-start book matches data/book_baseline.json ✓")
six = raw.execute(
    "SELECT SUM(name IS NOT NULL AND name != '') + SUM(normalized_name IS NOT NULL AND normalized_name != '') FROM orgs").fetchone()[0]
six += raw.execute(
    "SELECT SUM(email IS NOT NULL AND email != '') + SUM(pw_hash IS NOT NULL AND pw_hash != '') + SUM(display_name IS NOT NULL AND display_name != '') FROM users").fetchone()[0]
six += raw.execute("SELECT COALESCE(SUM(email IS NOT NULL AND email != ''), 0) FROM invites").fetchone()[0]
check("I3 six identity columns in the reward store: 100% empty after all provisioning", six == 0, six)

# ---- H. member-surface regression (the middleware/auth changes must not touch tenants)
print("\n-- H. tenant regression --")
st, tme = api(tenant, "/api/me")
check("H1 tenant admin session fine through the new middleware", st == 200 and tme["user"]["role"] == "admin", st)
st, tt = api(tenant, "/api/team")
check("H2 /api/team serves users+invites", st == 200 and len(tt.get("users", [])) >= 3, st)
st, _ = api(staff, "/api/admin/pulses")
check("H3 legacy console module (pulses) intact", st == 200, st)
st, _ = api(staff, "/api/admin/backlog")
check("H4 legacy console module (backlog) intact", st == 200, st)

raw.close()
print("\n== BACK-OFFICE GATE: %d passed, %d failed, %d skipped ==" % (len(PASS), len(FAIL), len(SKIP)))
for n, dd in FAIL:
    print("  FAILED:", n, dd)
for n, dd in SKIP:
    print("  SKIPPED:", n, dd)
sys.exit(1 if FAIL else 0)
