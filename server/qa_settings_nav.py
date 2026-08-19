# -*- coding: utf-8 -*-
"""SETTINGS NAV GATE (2026-08-19).

The Settings page keeps THREE lists that must stay the same sequence:

  the rail        railItem("<id>", …)  — what the user clicks
  the stack       card("<id>", …)      — the sections themselves, in DOM order
  the scroll-spy  SEC_IDS              — what the IntersectionObserver walks, and whose
                                         LAST entry the end-of-page pin selects

Nothing in the code makes them agree. Adding the Team card broke two of the three at once:
the rail item sat under one heading while its card sat three groups lower, and the id was
missing from SEC_IDS entirely, so that rail entry could never highlight at any scroll
position. It parsed, it rendered, and every other gate passed.

Also checks the ADMIN GATING matches per id: a card rendered only for admins whose rail
item is not gated the same way leaves a viewer clicking a link to a section that is not
on their page.

Static read of web/js/commercial.js. No DB, no HTTP. Exit != 0 on any failure.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# an explicit path makes each check demonstrable RED against a mutated copy without
# touching the working tree (red-first admission rule)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "web", "js", "commercial.js")

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILS.append((name, detail))


src = open(SRC, encoding="utf-8").read()
start = src.index("window.SettingsPage")
end = src.index("${aiDoc &&", start)
body = src[start:end]

rail = re.findall(r'railItem\("([a-z0-9-]+)"', body)
cards = re.findall(r'card\("([a-z0-9-]+)"', body)
_sec_src = body[body.index("const SEC_IDS"):]
_sec_src = _sec_src[:_sec_src.index(";")]
sec = [x for x in re.findall(r'"([a-z0-9-]+)"', _sec_src)]

print("  rail : %s" % rail)
print("  cards: %s" % cards)
print("  spy  : %s" % sec)

check("1. every rail item has a card", all(r in cards for r in rail),
      "rail ids with no section: %s" % [r for r in rail if r not in cards])
check("2. every card has a rail item", all(c in rail for c in cards),
      "sections unreachable from the rail: %s" % [c for c in cards if c not in rail])
check("3. rail order == card (DOM) order", rail == cards,
      "rail %s vs cards %s — a rail click lands in a different place from where it reads" % (rail, cards))
check("4. every card is in SEC_IDS", all(c in sec for c in cards),
      "sections the scroll-spy never observes, so their rail item can never highlight: %s"
      % [c for c in cards if c not in sec])
check("5. SEC_IDS order == card (DOM) order", sec == cards,
      "SEC_IDS %s vs cards %s — the observer walks a different sequence, and SEC_IDS[-1] "
      "is what the end-of-page pin selects" % (sec, cards))


def gated(kind, cid):
    """Is this id's railItem/card rendered behind isAdmin on its own line?"""
    for line in body.split("\n"):
        if ('%s("%s"' % (kind, cid)) in line:
            return "isAdmin" in line
    return False


mismatch = [c for c in cards if gated("card", c) != gated("railItem", c)]
check("6. admin gating matches between rail item and card", not mismatch,
      "ids gated on one side only — a viewer sees a rail item for a section that is not "
      "rendered for them (or vice versa): %s" % mismatch)

print("\nNOTE: static gate — reads web/js/commercial.js only. No DB, no HTTP, nothing to clean.")
print("\nRESULTS: %d failures" % len(FAILS))
for n, d in FAILS:
    print("  FAIL:", n, d)
sys.exit(1 if FAILS else 0)
