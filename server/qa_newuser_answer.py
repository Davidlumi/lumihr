# THE ANSWERING PASS — drive the new org to the insight gate and render its document.
# The basis set is is_required over visible_questions (app.py:4788-4796). The /api/questions
# payload does not surface that flag, so the set is read from the question bank itself and
# answered through the API exactly as a customer's client would.
import json, os, re, sqlite3, sys, urllib.error, urllib.request, http.cookiejar

SP = "/private/tmp/claude-501/-Applications-Lumi-Project/eab138a8-46d2-40c2-9324-b262e4a7efba/scratchpad"
B = "http://localhost:8071"
st = json.load(open(SP + "/newuser.json"))
ORG, EMAIL = st["org_id"], st["email"]

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(path, body=None, method=None, quiet=True):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method or ("POST" if body is not None else "GET"),
                               headers={"Content-Type": "application/json"})
    try:
        return json.loads(op.open(r, timeout=900).read() or b"{}"), 200
    except urllib.error.HTTPError as e:
        b = e.read().decode()[:200]
        if not quiet:
            print("   HTTP %d %s %s" % (e.code, path, b[:120]))
        try:
            return json.loads(b), e.code
        except Exception:
            return {"_raw": b}, e.code


call("/api/auth/login", {"email": EMAIL, "password": "Northwind!2026pass"})

# submit refuses until the "About your organisation" step is complete
_f, _c = call("/api/submission/firmographics",
              {"industry": "Retail & Consumer Goods", "fte_band": "250-999",
               "hq_region": "North West", "ownership_type": "Private (UK-owned)"}, method="PUT")
print("firmographics -> %s" % _c)

# the basis set, straight from the bank — is_required, as completion_basis_questions does
db = sqlite3.connect("file:%s/ai_lumi.db?mode=ro" % SP, uri=True)
db.row_factory = sqlite3.Row
rows = db.execute("SELECT id AS question_id, text AS display_title, type AS answer_type, "
                  "options_json FROM questions WHERE is_required=1 "
                  "AND (status IS NULL OR status='' OR status='active')").fetchall()
print("basis questions (is_required): %d" % len(rows))

ok = bad = 0
errs = {}
for r in rows:
    opts = json.loads(r["options_json"] or "[]")
    at = (r["answer_type"] or "").lower()
    if opts:
        first = opts[0]
        val = first.get("code") or first.get("value") or first.get("label") if isinstance(first, dict) else first
        if at in ("multi_select", "multiselect"):
            val = [val]
    elif at in ("number", "numeric", "integer", "percent", "currency"):
        val = 10
    else:
        val = "Yes"
    _, c = call("/api/submission/draft",
                {"question_id": r["question_id"], "value": val}, method="PUT")
    if c == 200:
        ok += 1
    else:
        bad += 1
        errs[c] = errs.get(c, 0) + 1
print("answers accepted: %d | refused: %d %s" % (ok, bad, errs or ""))

_, c = call("/api/submission/submit", {})
print("submit -> %s" % c)

al, c = call("/api/strategy/alignment")
ds = al.get("data_state") or {}
print("\n=== THE NEW ORG'S DOCUMENT ===")
print("  unlocked=%s  core_pct=%s  answered=%s/%s  positioned=%s"
      % (ds.get("unlocked"), ds.get("core_pct"), ds.get("answered"), ds.get("basis_total"),
         ds.get("positioned")))
print("  areas=%d  commitments=%d  signals=%d  plan=%s  priced=%s"
      % (len(al.get("domain_blocks") or []), len(al.get("commitments") or []),
         sum((b.get("signal_count") or 0) for b in (al.get("domain_blocks") or [])),
         bool(al.get("plan")), (al.get("money") or {}).get("priced")))

pl, c = call("/api/strategy/plan", {})
print("  build the plan -> %s source=%s" % (c, (pl.get("plan") or {}).get("source")))

# capture the five payloads the harness stubs, for THIS org
out = {}
for k, path, body in (("me", "/api/me", None), ("strategy", "/api/strategy", None),
                      ("alignment", "/api/strategy/alignment", None),
                      ("commentary", "/api/strategy/commentary", {}),
                      ("diagnosis", "/api/strategy-diagnosis", {}),
                      ("statement", "/api/strategy/statement", {})):
    v, c = call(path, body)
    out[k] = v
    if c != 200:
        print("  ! %s -> %s" % (path, c))
json.dump(out, open(SP + "/canned.json", "w"))
print("\ncanned.json now carries the NEW org — ready to render")
