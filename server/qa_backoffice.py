# -*- coding: utf-8 -*-
"""Back-office gate: the staff console's full surface — auth matrix, provisioning,
support actions, soft-deactivate, audit coverage, and secret/PII hygiene.

MUST run against a THROWAWAY: it creates orgs/users, deactivates accounts and
flips a platform_admin flag. Refuses to start without LUMI_DB set (gate-safety),
and aborts if the server on BASE turns out not to be reading the same DB file
(the canary write in section D).

Usage (the documented gate procedure — throwaway server ON :8060):
  LUMI_DB=... LUMI_IDENTITY_DB=... python3 qa_backoffice.py
"""
import json, os, secrets, sqlite3, sys, urllib.request, urllib.error, http.cookiejar

BASE = os.environ.get("LUMI_QA_BASE", "http://localhost:8060")
DB = os.environ.get("LUMI_DB")
if not DB:
    print("qa_backoffice: REFUSING to run without LUMI_DB (this gate writes orgs/users "
          "and deactivates accounts — throwaway only).")
    sys.exit(2)

PASS, FAIL = [], []
def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  [" + str(detail)[:110] + "]") if detail else ""))

def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def api(opener, path, method="GET", body=None):
    r = urllib.request.Request(BASE + path, method=method)
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

STAFF = ("david@lumihr.co.uk", "lumi-demo-2026")
ORG_ADMIN = ("director@thornbridge.example", "lumi-demo-2026")
VIEWER = ("ceo@thornbridge.example", "lumi-view-2026")
TAG = secrets.token_hex(4)

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
check("B1 staff /api/me carries platform_admin", st == 200 and me["user"].get("platform_admin") == 1
      or me["user"].get("platform_admin") is True, me["user"].get("platform_admin"))
st, h = api(staff, "/api/admin/health")
check("B2 health: counts+storage+modes present", st == 200 and
      all(k in h for k in ("counts", "storage", "modes", "uptime_seconds")), list(h))
check("B3 health counts sane (orgs>=220, users>=8, questions>0)",
      h["counts"]["orgs_total"] >= 220 and h["counts"]["users"] >= 8
      and h["counts"]["questions_active"] > 0, h["counts"])
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

# ---- D. provisioning lifecycle (with the server/DB alignment canary)
print("\n-- D. provisioning --")
ORG_NAME = "QA Probe Org %s" % TAG
st, created = api(staff, "/api/admin/orgs", "POST", {"name": ORG_NAME})
check("D1 create org", st == 200 and created.get("ok"), created)
POID = created.get("org_id")
row = raw.execute("SELECT source, tier_entitlement FROM orgs WHERE org_id=?", (POID,)).fetchone()
if row is None:
    print("qa_backoffice: ABORT — the server on %s is NOT reading LUMI_DB=%s "
          "(canary org missing). Wrong server/DB pairing." % (BASE, DB))
    sys.exit(2)
check("D2 canary: server writes land in LUMI_DB; source=signup, full tier",
      row["source"] == "signup" and row["tier_entitlement"] == "full", dict(row))
st, _ = api(staff, "/api/admin/orgs", "POST", {"name": ORG_NAME})
check("D3 duplicate name refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs", "POST", {"name": "   "})
check("D4 blank name refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs", "POST", {"name": "!!! ***"})
check("D5 symbols-only name refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST", {"email": "not-an-email", "role": "admin"})
check("D6 bad invite email refused", st == 400, st)
st, _ = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST", {"email": STAFF[0], "role": "admin"})
check("D7 invite to an existing account refused", st == 400, st)
FOUNDER = "qa-founder-%s@probe.example" % TAG
st, inv = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST", {"email": FOUNDER, "role": "admin"})
check("D8 founding-admin invite minted", st == 200 and "/app#/invite/" in inv.get("link", ""), inv)
itok = inv["link"].rsplit("/", 1)[-1]
st, d = api(staff, "/api/admin/orgs/" + POID)
check("D9 org detail lists the pending invite (email, role=admin, link)",
      any(i.get("email") == FOUNDER and i["role"] == "admin" and i.get("link") for i in d.get("invites", [])),
      d.get("invites"))
# revoke a second invite; the first stays live for the accept test
st, inv2 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
               {"email": "qa-temp-%s@probe.example" % TAG, "role": "viewer"})
tok2 = inv2["link"].rsplit("/", 1)[-1]
st, _ = api(staff, "/api/admin/invites/%s/revoke" % tok2, "POST", {})
check("D10 revoke ok", st == 200, st)
st, _ = api(anon, "/api/invite/" + tok2)
check("D11 revoked invite link dead (404)", st == 404, st)
st, _ = api(staff, "/api/admin/invites/%s/revoke" % tok2, "POST", {})
check("D12 double-revoke refused", st == 400, st)
FPW = "qa-probe-pass-%s" % TAG
st, _ = api(anon, "/api/auth/accept-invite", "POST",
            {"token": itok, "password": FPW, "accept_platform_terms": True, "display_name": "QA Founder"})
check("D13 invitee joins (own password + terms)", st == 200, st)
st, d = api(staff, "/api/admin/orgs/" + POID)
check("D14 member (admin) + platform-terms row now on the org",
      any(u["email"] == FOUNDER and u["role"] == "admin" for u in d["users"]) and
      any(t["kind"] == "platform" and t["email"] == FOUNDER for t in d["terms"]),
      (d["users"], d["terms"]))
FUID = next(u["user_id"] for u in d["users"] if u["email"] == FOUNDER)

# ---- E. support actions
print("\n-- E. support --")
st, r = api(staff, "/api/admin/users/%s/reset-link" % FUID, "POST", {})
check("E1 staff reset link minted (2h)", st == 200 and "/app#/reset/" in r.get("link", "")
      and r.get("expires_in_hours") == 2, r)
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
st, r = api(staff, "/api/admin/users/%s/deactivate" % FUID, "POST", {})
check("F1 deactivate user", st == 200, r)
st, _ = api(founder, "/api/me")
check("F2 live session dies at deactivation", st == 401, st)
st, r = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 3
check("F3 relogin 403 with the honest message", st == 403 and "deactivated" in r.get("detail", ""), r)
st, _ = api(staff, "/api/admin/users/%s/deactivate" % FUID, "POST", {})
check("F4 double-deactivate refused", st == 400, st)
st, lk = api(staff, "/api/admin/users/lookup?email=" + FOUNDER)
check("F5 lookup shows disabled_at", bool(lk["user"].get("disabled_at")), lk["user"].get("disabled_at"))
st, _ = api(staff, "/api/admin/users/%s/reactivate" % FUID, "POST", {})
check("F6 reactivate", st == 200, st)
st, _ = api(founder, "/api/auth/login", "POST", {"email": FOUNDER, "password": FPW})   # login 4
check("F7 relogin works after reactivate", st == 200, st)
# org level — mint a fresh invite first so the accept-during-deactivation path is testable
st, inv3 = api(staff, "/api/admin/orgs/%s/invite" % POID, "POST",
               {"email": "qa-second-%s@probe.example" % TAG, "role": "viewer"})
tok3 = inv3["link"].rsplit("/", 1)[-1]
st, r = api(staff, "/api/admin/orgs/%s/deactivate" % POID, "POST", {})
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
st, _ = api(staff, "/api/admin/orgs/%s/reactivate" % POID, "POST", {})
check("F14 reactivate org", st == 200, st)
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
print("\n== BACK-OFFICE GATE: %d passed, %d failed ==" % (len(PASS), len(FAIL)))
for n, dd in FAIL:
    print("  FAILED:", n, dd)
sys.exit(1 if FAIL else 0)
