"""Demo-org resolution (P3).

The reward store loses `orgs.name` and `orgs.normalized_name` at step 5, so the
demo org can no longer be found there. The NAME lives identity-side; the
CLASSIFICATION stays reward-side. This module is the single place that joins the
two — the shape app.py took at the C7 startup-wiring commit.

NO SILENT SKIP. Every resolver here raises on a miss. A gate whose demo org
vanished must fail, not quietly stop asserting: `qa_metric_data` demonstrated the
failure mode this rule exists to prevent, where `demo_id = ... if demo else None`
turned an unresolvable org into a skipped required-question check that a reader
could not distinguish from a passing one.

Callers that genuinely cannot exit non-zero (reports, not gates) catch
DemoOrgUnresolved and record it as a CRITICAL finding in their own output.
"""
import identity


class DemoOrgUnresolved(RuntimeError):
    """The demo org could not be resolved from the identity store, or its reward-side
    row is missing/unclassified. Always fatal unless a caller deliberately downgrades it."""


def demo_row(conn):
    """The demo org's full reward-side row. Raises DemoOrgUnresolved on any miss."""
    ident = identity.org_lookup_by_normalized(identity.DEMO_ORG_NORMALIZED)
    if ident is None:
        raise DemoOrgUnresolved(
            "identity.org_register has no org with normalized_name=%r — the demo org "
            "cannot be resolved. (identity.db missing, empty, or pointed elsewhere?)"
            % identity.DEMO_ORG_NORMALIZED)
    r = conn.execute("SELECT * FROM orgs WHERE org_id=? AND classified=1",
                     (ident["org_id"],)).fetchone()
    if r is None:
        raise DemoOrgUnresolved(
            "identity resolved the demo org to org_id=%s, but the reward store has no "
            "classified org with that id — the two stores disagree." % ident["org_id"])
    return r


def demo_id(conn):
    """The demo org's org_id. Raises DemoOrgUnresolved on any miss."""
    return demo_row(conn)["org_id"]


def any_classified_row(conn):
    """Shape B: any classified, submission-complete org — the demo org is incidental
    to these callers. ORDER BY is mandatory, not decorative: an unordered LIMIT 1 is
    the unordered-iteration hazard this project has ruled against, and a gate that
    silently changes which org it tests between runs is not a gate."""
    r = conn.execute("SELECT * FROM orgs WHERE classified=1 AND submission_complete=1 "
                     "ORDER BY org_id LIMIT 1").fetchone()
    if r is None:
        raise DemoOrgUnresolved("no classified, submission-complete org exists in the reward store")
    return r
