# THE NEW-USER JOURNEY, on a throwaway, end to end.
# Every prior verification in this engagement ran on one mature org with complete data.
# This provisions a genuinely new one and walks it: staff creates the org, the founding
# admin joins, accepts terms, states a strategy, answers questions, and asks for the
# document at each stage. What it reports is what a customer would actually see.
import json, re, sys, urllib.error, urllib.request, http.cookiejar, uuid

B = "http://localhost:8071"


def client():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(op, path, body=None, method=None, quiet=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method or ("POST" if body is not None else "GET"),
                               headers={"Content-Type": "application/json"})
    try:
        return json.loads(op.open(r, timeout=900).read() or b"{}"), 200
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        if not quiet:
            print("      HTTP %d %s -> %s" % (e.code, path, body[:160]))
        try:
            return json.loads(body), e.code
        except Exception:
            return {"_raw": body}, e.code


STEP = [0]
def step(t):
    STEP[0] += 1
    print("\n--- %d. %s" % (STEP[0], t))


# ---------------------------------------------------------------- staff creates the org
staff = client()
r, c = call(staff, "/api/auth/login", {"email": "david@lumihr.co.uk", "password": "lumi-demo-2026"})
step("staff signs in to the console")
print("      ok=%s platform_admin path available=%s" % (r.get("ok"), c == 200))

tag = uuid.uuid4().hex[:6]
org_name = "Northwind Foods Ltd %s" % tag
admin_email = "reward.director+%s@northwind.example" % tag
step("staff provisions a new organisation + founding admin invite")
prov, c = call(staff, "/api/admin/orgs", {
    "org_name": org_name, "admin_email": admin_email,
    "industry": "Retail & Consumer Goods", "fte_band": "250-999",
    "hq_region": "North West", "ownership_type": "Private (UK-owned)",
})
print("      status=%s org=%s" % (c, (prov.get("org") or {}).get("org_id", prov)[:40] if isinstance(prov.get("org"), dict) or prov.get("org") else prov))
org_id = ((prov.get("org") or {}).get("org_id") if isinstance(prov.get("org"), dict) else None) or prov.get("org_id")
# the API returns the LINK; the token is its last path segment (PH-PROV-1f keeps the
# bearer out of logs, so the link is where it lives)
_m = re.search(r"/invite/([A-Za-z0-9_-]+)", prov.get("invite_link") or "")
token = _m.group(1) if _m else None
print("      invite token present: %s" % bool(token))
if not token:
    print("      PROVISIONING RESPONSE:", json.dumps(prov)[:400])
    sys.exit("cannot continue without an invite token")

# ---------------------------------------------------------------- the customer joins
user = client()
step("the founding admin accepts the invite and sets a password")
acc, c = call(user, "/api/auth/accept-invite",
              {"token": token, "display_name": "A. Director",
               "password": "Northwind!2026pass", "accept_platform_terms": True})
print("      status=%s ok=%s" % (c, acc.get("ok")))

me, c = call(user, "/api/me")
print("      signed in as: %s | org: %s" % ((me.get("user") or {}).get("email"), (me.get("org") or {}).get("name")))

step("THE DOCUMENT, before anything is stated or answered")
al, c = call(user, "/api/strategy/alignment", quiet=True)
print("      /api/strategy/alignment -> %s  ok=%s reason=%s" % (c, al.get("ok"), al.get("reason")))

step("terms")
t, c = call(user, "/api/terms/accept-data", {"accept": True}, quiet=True)
print("      data-contribution terms -> %s %s   (platform terms accepted at join)"
      % (c, t.get("ok", t.get("detail", ""))))

step("the strategy: the minimum a customer must state")
strat = {"market_position": "match", "primary_objective": "attract", "budget_direction": "flat",
         "reward_mix": "balanced", "pay_for_performance": "moderate", "transparency": "ranges",
         "location_approach": "national", "benefits_lead": ["physical"], "family_position": "market",
         "risk_appetite": "follow", "acute_pressure": "bau"}
s1, c = call(user, "/api/strategy", {"strategy": strat, "complete": True},
             method="PUT", quiet=True)
print("      PUT /api/strategy (complete=True) -> %s %s" % (c, json.dumps(s1)[:150]))

step("THE DOCUMENT, strategy stated, no benchmark answers yet")
al, c = call(user, "/api/strategy/alignment", quiet=True)
print("      -> %s ok=%s reason=%s" % (c, al.get("ok"), al.get("reason")))
if al.get("ok") is not False:
    ds = al.get("data_state") or {}
    print("      data_state: unlocked=%s core_pct=%s answered=%s/%s positioned=%s"
          % (ds.get("unlocked"), ds.get("core_pct"), ds.get("answered"), ds.get("basis_total"),
             ds.get("positioned")))
    print("      domain_blocks=%d commitments=%d plan=%s"
          % (len(al.get("domain_blocks") or []), len(al.get("commitments") or []), bool(al.get("plan"))))

step("what the customer is asked to answer")
q, c = call(user, "/api/questions", quiet=True)
qs = q.get("questions") or q.get("items") or []
req = [x for x in qs if x.get("is_required")]
print("      visible questions: %d | required for the insight gate: %d" % (len(qs), len(req)))
json.dump({"org_id": org_id, "email": admin_email, "n_required": len(req),
           "required_ids": [x.get("question_id") for x in req]},
          open("/private/tmp/claude-501/-Applications-Lumi-Project/eab138a8-46d2-40c2-9324-b262e4a7efba/scratchpad/newuser.json", "w"))
print("\n(org + required-question list saved for the answering pass)")


# ------------------------------------------------- the answering pass, to the unlock gate
step("answering the benchmark questions to the insight gate")
basis = [x for x in qs if x.get("is_basis") or x.get("required_for_basis") or x.get("is_required")]
if not basis:
    basis = [x for x in qs if x.get("scored") or x.get("is_scored")][:120]
print("      basis questions the client would prompt for: %d" % len(basis))
answered = 0
for x in basis:
    opts = x.get("options") or []
    val = (opts[0].get("code") or opts[0].get("value") or opts[0].get("label")) if opts else None
    if val is None:
        continue
    _, cc = call(user, "/api/answers", {"question_id": x.get("question_id"), "value": val}, quiet=True)
    if cc == 200:
        answered += 1
print("      answers accepted: %d" % answered)

step("THE DOCUMENT, after answering")
al, c = call(user, "/api/strategy/alignment", quiet=True)
ds = (al or {}).get("data_state") or {}
print("      -> %s ok=%s unlocked=%s core_pct=%s answered=%s/%s positioned=%s"
      % (c, al.get("ok"), ds.get("unlocked"), ds.get("core_pct"), ds.get("answered"),
         ds.get("basis_total"), ds.get("positioned")))
print("      domain_blocks=%d commitments=%d plan=%s signals=%s"
      % (len(al.get("domain_blocks") or []), len(al.get("commitments") or []), bool(al.get("plan")),
         sum((b.get("signal_count") or 0) for b in (al.get("domain_blocks") or []))))
json.dump(al, open("/private/tmp/claude-501/-Applications-Lumi-Project/eab138a8-46d2-40c2-9324-b262e4a7efba/scratchpad/newuser_alignment.json","w"))
