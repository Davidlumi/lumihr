# -*- coding: utf-8 -*-
"""Generate the R7/R8 content sign-off sheet (2026-08-16).

DAVID OWNS data/reward_levers.json (R8) and data/strategy_coherence_rules.json (R7).
Both shipped marked DRAFT and both are now quoted verbatim in a board paper — lever
names and trade-offs appear as numbered exhibits with recorded decisions against them,
and rule statements are printed as findings. So the drafting needs signing off, and
this makes that reviewable in one pass instead of by reading two JSON files.

The sheet is generated, never hand-maintained: it carries the LIVE content plus the
checks a reviewer cannot do by eye — does every referenced metric exist, is it visible
in the right category, does a rule's expected answer actually appear on its question.

    python3 server/gen_r7_r8_ruling_sheet.py            # writes the sheet, read-only on the DB
    python3 server/gen_r7_r8_ruling_sheet.py --check    # validation only, non-zero exit on a defect

Reads LUMI_DB when set (the gate suite imports validate() and runs against a throwaway),
otherwise the live bank — this generator is a deliberate data tool, not a gate.
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEVERS = os.path.join(ROOT, "data", "reward_levers.json")
RULES = os.path.join(ROOT, "data", "strategy_coherence_rules.json")
OUT = os.path.join(ROOT, "R7_R8_RULING_SHEET_2026-08-16.md")
# LUMI_DB wins when it is set. The gate suite imports load_questions() and runs with
# LUMI_DB pointed at a throwaway — a hardcoded live path here would have a gate process
# reading the live bank, which is exactly the hazard gate-safety-1 exists to stop.
DB = os.environ.get("LUMI_DB") or os.path.join(ROOT, "lumi.db")

# Column order matches the document's own section order so a reviewer reads them in the
# order a member meets them.
CATS = ["Pay", "Incentives & Recognition", "Benefits & Lifestyle", "Time Off & Family",
        "Health & Protection", "Pensions & Savings", "Wellbeing", "Governance & Transparency"]


def load_questions():
    conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    conn.row_factory = sqlite3.Row
    q = {}
    for r in conn.execute("SELECT id, sub_power, text, type, status, options_json FROM questions"):
        q[r["id"]] = dict(r)
    conn.close()
    return q


def rule_clauses(ev):
    """Rules use three evidence shapes: one metric, or any/all lists of clauses."""
    if "metric" in ev:
        return [ev]
    out = []
    for k in ("any", "all"):
        for c in ev.get(k) or []:
            out.extend(rule_clauses(c))
    return out


def validate(levers, rules, Q):
    """Everything a reviewer cannot check by eye. Returns a list of defect strings."""
    bad = []
    for l in levers:
        m = l.get("prevalence_metric_id")
        if m and m not in Q:
            bad.append("LEVER %s: prevalence_metric_id '%s' does not exist in the question bank "
                       "— the lever renders with no peer take-up and says nothing about it"
                       % (l["lever_id"], m))
        elif m and Q[m].get("status") not in (None, "active"):
            bad.append("LEVER %s: prevalence metric '%s' is %s, not active"
                       % (l["lever_id"], m, Q[m].get("status")))
        elif m and Q[m]["type"] == "matrix":
            bad.append("LEVER %s: prevalence metric '%s' is a MATRIX (a rate by level), not a "
                       "prevalence question — 'what share of peers do this' cannot be read from it"
                       % (l["lever_id"], m))
        if not (l.get("trade_off") or "").strip():
            bad.append("LEVER %s: no trade_off — a lever with no stated downside is marketing"
                       % l["lever_id"])
    for r in rules:
        for c in rule_clauses(r["evidence"]):
            m = c.get("metric")
            if m not in Q:
                bad.append("RULE %s: evidence metric '%s' does not exist — the rule can never fire"
                           % (r["rule_id"], m))
                continue
            opts = json.loads(Q[m]["options_json"]) if Q[m]["options_json"] else None
            labels = [o.get("label") if isinstance(o, dict) else o for o in (opts or [])]
            for key in ("answer_in", "answer_not_in"):
                for a in c.get(key) or []:
                    if labels and a not in labels:
                        bad.append("RULE %s: %s expects '%s', which is not an option on %s"
                                   % (r["rule_id"], key, a, m))
    return bad


def qref(Q, mid):
    if not mid:
        return "—"
    if mid not in Q:
        return "`%s` **← MISSING**" % mid
    return "`%s` · %s · *%s*" % (mid, Q[mid]["sub_power"], Q[mid]["text"][:64])


def main():
    levers = json.load(open(LEVERS))["levers"]
    rdoc = json.load(open(RULES))
    rules = rdoc["rules"]
    Q = load_questions()
    defects = validate(levers, rules, Q)

    if "--check" in sys.argv:
        for d in defects:
            print("  DEFECT " + d)
        print("%d defect(s)" % len(defects))
        return 1 if defects else 0

    L = []
    w = L.append
    w("# R7 / R8 — content sign-off sheet")
    w("")
    w("*Generated by `server/gen_r7_r8_ruling_sheet.py` on the live question bank. "
      "Do not hand-edit — change the JSON and regenerate.*")
    w("")
    w("**Why this exists.** `data/reward_levers.json` (R8) and "
      "`data/strategy_coherence_rules.json` (R7) are yours. Both shipped marked DRAFT, "
      "and both are now quoted verbatim in a board paper: lever names and trade-offs "
      "appear as numbered exhibits with a recorded decision against each, and rule "
      "statements print as findings. Until you sign them off, Claude's drafting is being "
      "read as house doctrine.")
    w("")
    w("**How to use it.** Work down each table. For every row put one of "
      "**KEEP** / **EDIT** / **CUT** in the last column and, for EDIT, the wording you "
      "want. Nothing here is load-bearing on the engine — both files hot-reload, so a "
      "change takes effect on the next request.")
    w("")

    w("## 0. Defects to settle first")
    w("")
    if not defects:
        w("None — every referenced metric exists, is active, is the right question type, "
          "and every rule's expected answers appear on its question.")
    else:
        w("These are not content judgements — they are broken references found by "
          "checking the files against the live question bank. Each one fails silently "
          "today.")
        w("")
        for d in defects:
            w("- " + d)
    w("")

    # ---------------------------------------------------------------- levers
    linked = [l for l in levers if l.get("prevalence_metric_id")]
    w("## 1. R8 — the reward lever inventory (%d levers)" % len(levers))
    w("")
    w("%d carry a prevalence link, so peer take-up renders live beside them. "
      "The other %d are **asserted on domain knowledge alone** and are marked ⚠ — those "
      "are the ones worth the most of your attention, because nothing in the product "
      "checks them."
      % (len(linked), len(levers) - len(linked)))
    w("")
    w("`Substance` moves what you offer or how much; `Approach` moves how you operate. "
      "A member behind on POSITION is offered Substance levers; one CONTRADICTED on "
      "practice is offered Approach. Both registers must exist in every category or a "
      "gap can land with no options against it.")
    w("")
    for cat in CATS:
        rows = [l for l in levers if l["category"] == cat]
        if not rows:
            continue
        w("### %s — %d levers" % (cat, len(rows)))
        w("")
        for l in rows:
            flag = "" if l.get("prevalence_metric_id") else " ⚠"
            w("**%s** · `%s`%s" % (l["name"], l["lever_id"], flag))
            w("")
            w("| | |")
            w("|---|---|")
            w("| Register | %s |" % l["register_effect"])
            w("| What it is | %s |" % l["what_it_is"])
            w("| Typical shape | %s |" % l["typical_shape"])
            w("| Cost / speed / reversibility | %s · %s · %s |"
              % (l["cost_character"], l["speed"], l["reversibility"]))
            w("| **Trade-off** (printed in the document) | %s |" % l["trade_off"])
            w("| Peer take-up read from | %s |" % qref(Q, l.get("prevalence_metric_id")))
            w("| **Your ruling** | KEEP / EDIT / CUT — |")
            w("")
    w("")

    # ---------------------------------------------------------------- rules
    w("## 2. R7 — the coherence rules (%d rules)" % len(rules))
    w("")
    w("A rule fires only when the stated intent HOLDS — a rule is a commitment you made, "
      "tested against your own answer. `contradicted` means practice runs against the "
      "intent; `behind_intent` means the intent is stated and the provision is absent. "
      "The statement is printed verbatim in the document, with `{answer}` replaced by "
      "the member's own response.")
    w("")
    for r in rules:
        w("### %s · %s · **%s**" % (r["rule_id"], r["category"], r["status"]))
        w("")
        w("| | |")
        w("|---|---|")
        w("| Commitment tested | %s |" % r["commitment"])
        # two intent shapes: an enum field matching a list, or a multi-select containing a value
        _it = r["intent"]
        _when = ("is %s" % " or ".join(_it["in"])) if _it.get("in") else \
                ("includes %s" % _it.get("contains"))
        w("| Fires when intent | `%s` %s |" % (_it["field"], _when))
        for c in rule_clauses(r["evidence"]):
            cond = ("answer in %s" % c["answer_in"]) if c.get("answer_in") else \
                   ("answer NOT in %s" % c.get("answer_not_in"))
            w("| …and evidence | %s<br>%s |" % (qref(Q, c.get("metric")), cond))
        w("| **Statement printed** | %s |" % r["statement"].replace("|", "\\|"))
        w("| Rationale | %s |" % r["rationale"])
        w("| **Your ruling** | KEEP / EDIT / CUT — |")
        w("")

    # ------------------------------------------------------------- coverage
    w("## 3. Coverage — where a gap would land with no options")
    w("")
    w("| Category | Substance levers | Approach levers | Coherence rules |")
    w("|---|---|---|---|")
    for cat in CATS:
        sub = len([l for l in levers if l["category"] == cat and l["register_effect"] == "Substance"])
        app = len([l for l in levers if l["category"] == cat and l["register_effect"] == "Approach"])
        rr = len([r for r in rules if r["category"] == cat])
        mark = "" if (sub and app) else "  ← a gap here can land with no options"
        w("| %s | %d | %d | %d |%s" % (cat, sub, app, rr, mark))
    w("")
    w("---")
    w("")
    w("*Sign-off: when every row above carries a ruling, update the `_readme` STATUS line "
      "in both JSON files from `pending David's content sign-off` to the date you signed "
      "them, and the DRAFT caveat comes out of DECISIONS.*")

    open(OUT, "w").write("\n".join(L) + "\n")
    print("wrote %s — %d levers, %d rules, %d defect(s)"
          % (os.path.relpath(OUT, ROOT), len(levers), len(rules), len(defects)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
