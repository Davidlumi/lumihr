# DOES A 200 FROM PUT /api/submission/draft MEAN THE VALUE WAS STORED?
# 72 drafts returned 200 and 3 became answers. Either the endpoint accepts values it
# cannot store and says so anyway, or the loss is later. This asks the drafts table
# directly, one question at a time, with values read from that question's own bank row.
import json, sqlite3, sys, urllib.error, urllib.request, http.cookiejar

SP = "/private/tmp/claude-501/-Applications-Lumi-Project/eab138a8-46d2-40c2-9324-b262e4a7efba/scratchpad"
B = "http://localhost:8071"
st = json.load(open(SP + "/newuser.json"))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(path, body=None, method=None):
    d = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=d, method=method or ("POST" if body is not None else "GET"),
                               headers={"Content-Type": "application/json"})
    try:
        return json.loads(op.open(r, timeout=300).read() or b"{}"), 200
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode()[:300]), e.code
        except Exception:
            return {}, e.code


call("/api/auth/login", {"email": st["email"], "password": "Northwind!2026pass"})
ORG = st["org_id"]

db = sqlite3.connect("file:%s/ai_lumi.db?mode=ro" % SP, uri=True)
db.row_factory = sqlite3.Row
rows = db.execute("SELECT id, text, type, options_json FROM questions "
                  "WHERE is_required=1 AND options_json IS NOT NULL AND options_json != '[]' "
                  "LIMIT 6").fetchall()


def drafts_now():
    d2 = sqlite3.connect("file:%s/ai_lumi.db?mode=ro" % SP, uri=True)
    n = d2.execute("SELECT COUNT(*) FROM drafts WHERE org_id=? AND value IS NOT NULL AND value != ''",
                   (ORG,)).fetchone()[0]
    d2.close()
    return n


print("%-24s %-9s %-30s %-6s %s" % ("question", "type", "value sent", "HTTP", "stored?"))
print("-" * 92)
for r in rows:
    opts = json.loads(r["options_json"] or "[]")
    first = opts[0]
    label = first.get("label") if isinstance(first, dict) else str(first)
    code = (first.get("code") or first.get("value")) if isinstance(first, dict) else None
    for what, val in (("its own option LABEL", label), ("its own option CODE", code),
                      ("a value it never offers", "ZZ_NOT_AN_OPTION")):
        if val is None:
            continue
        before = drafts_now()
        _, c = call("/api/submission/draft", {"question_id": r["id"], "value": val}, method="PUT")
        after = drafts_now()
        print("%-24s %-9s %-30s %-6s %s" % (r["id"][:24], (r["type"] or "")[:9],
                                            str(val)[:30], c,
                                            "YES" if after > before else "no change"))
    print()
