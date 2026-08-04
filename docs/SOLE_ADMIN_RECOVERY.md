# Runbook: sole-admin recovery

The stranded-Admin case: an organisation's only Admin left, lost access, or must be
replaced. Carried since 2026-06-11 as "a manual lumi-side process, deliberately unbuilt";
specified 2026-08-04 (PH-PROV-2b §4) — the mechanism is PH-PROV-1g's scope choice made
useful: "active Admin" means `disabled_at IS NULL`, so deactivate-then-reissue is a
working route to a fresh founding Admin. All through the console; no database surgery.

## The procedure

1. **Deactivate the stranded Admin** — org page → Members table → Deactivate.
   Soft-deactivate GATES ACCESS AND DELETES NOTHING: their sessions die instantly and
   sign-in refuses, but every artifact they created and every terms acceptance they
   recorded survives, because the record of what the organisation agreed to is the
   organisation's, not the departed individual's.
2. **Issue a founding invite to the replacement** — same page → Invite a member →
   role Admin → Create invite. The active-Admin refusal no longer applies (no *active*
   Admin remains). Copy the link and deliver it out-of-band.
3. **The replacement activates** — sets their own password and accepts the platform
   terms AS THEIR OWN ACT, never inherited from the departed Admin. From there they
   manage their team by promotion, the normal rule.

## Why this leaves a proper trail

Both platform-admin actions are audited (`user.deactivate`, `org.invite` — the latter
recording any superseded invite as a sha256[:12] digest, never the bearer). The recovery
is therefore reconstructible from the audit trail alone: who acted, when, on which org,
and what credential was retired.

Notes: if the departed Admin should return, Reactivate restores them exactly (nothing was
deleted). If an unaccepted admin invite is also floating, issuing the new one supersedes
it automatically (PH-PROV-1g) — the old link stops working the moment you reissue.
