# -*- coding: utf-8 -*-
"""Share-capital form from an org's ownership_type — the one place two scripts share.

`verify_diff7.py` and `diff7_reseed.py` each carried an AST-identical `form()`. Both
classified from `orgs.ownership_type` and, when it was absent, fell back to a regex on
the org's TRADING NAME (`plc|ltd|limited`). That fallback is removed here.

WHY THE FALLBACK IS GONE, measured not asserted:
  * where the structured field gives us truth, the regex ventures an opinion on 137 of
    160 orgs and is WRONG on 13 of them. 8 of those 13 are nonshare->share — the
    direction that triggers a write in diff7_reseed (`set_change(qid, o, "Neither")`).
  * a trading-name suffix describes legal form; ownership_type describes ownership.
    They are not the same field, and the 8 disagreements are where that shows.
  * the population it was asked to judge is exactly the 63 orgs with classified=0 —
    the set defined by having no structured firmographics at all. It was applying the
    weakest evidence precisely where the strongest was missing.
  * it costs nothing to remove: `flip` (the diff7_reseed write count) is 0 with the
    fallback and 0 without, and verify_diff7's F1 count is 0 either way.
  * the codebase already said so — diff7_reseed's sharefix block keys off
    ownership_type directly, noting form()'s fallback is "flagged for removal".

THE VOCABULARY IS HARDCODED, AND THAT IS THE FINDING. There is no canonical constant
to import: `server/app.py:3773 OWNERSHIP` is the member-facing signup list (8 values)
and shares only 3 with the seed estate, so keying off it would misclassify most of it.
The eleven below are the live distinct set. `assert_vocabulary_current(conn)` is what
stops this going stale the way the thing it replaces did — it is BIDIRECTIONAL, so it
fires both when a value is added to the data and when one disappears from it.
"""

# The eleven live values of orgs.ownership_type, classified by whether the ownership
# form implies share capital. Grounds are per-value; see assert_vocabulary_current.
_SHARE = {
    "Public Listed (PLC)",          # listed company — share capital by definition
    "Private (UK-owned)",           # UK private company — limited by shares
    "Private (Founder/Family)",     # privately held company — shares, closely held
    "Founder-led (Private)",        # as above; founder control is not a form difference
    "VC-backed (Private)",          # venture equity IS shareholding
    "PE-backed",                    # private-equity ownership is shareholding
    "Subsidiary of Global Group",   # subsidiary held via shares by its parent
}
_NONSHARE = {
    "Public Sector Body",           # statutory body — no share capital
    "Charity / Non-profit",         # charitable company/trust — limited by guarantee
    "Mutual / Co-operative",        # member-owned; member shares are not equity capital
    "Partnership / LLP",            # partners, not shareholders
}

VOCABULARY = _SHARE | _NONSHARE


def assert_vocabulary_current(conn):
    """Fail loudly if the live vocabulary has drifted from the one classified above.

    BIDIRECTIONAL by design:
      * a value appearing in orgs.ownership_type that is not classified here raises —
        it would otherwise silently become "unknown", which is how the previous
        version's regex fallback came to be doing the work.
      * a value classified here that no longer appears in the data raises too — a set
        that keeps values the estate has dropped is a set nobody is maintaining, and
        it is the state this function exists to prevent.
    Returns the live distinct set on success.
    """
    live = {r[0] for r in conn.execute(
        "SELECT DISTINCT ownership_type FROM orgs "
        "WHERE ownership_type IS NOT NULL AND TRIM(ownership_type) <> ''")}
    missing = sorted(live - VOCABULARY)      # in the data, unclassified here
    extra = sorted(VOCABULARY - live)        # classified here, gone from the data
    if missing or extra:
        raise AssertionError(
            "org_form vocabulary is stale.\n"
            "  in orgs.ownership_type but NOT classified: %s\n"
            "  classified but NO LONGER in the data     : %s\n"
            "  Update _SHARE / _NONSHARE in org_form.py deliberately — do not widen a\n"
            "  fallback to absorb it, which is what this replaced." % (missing, extra))
    return live


def form(org_row):
    """'share' | 'nonshare' | 'unknown' for one org row (anything dict-subscriptable).

    'unknown' means the ownership_type is absent — 63 orgs, exactly the classified=0
    population. It is an honest answer, and already a value both call sites handle.
    """
    ot = (org_row.get("ownership_type") or "").strip()
    if ot in _SHARE:
        return "share"
    if ot in _NONSHARE:
        return "nonshare"
    return "unknown"
