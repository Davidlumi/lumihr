# lumi security policies (Cyber Essentials)

These are the written processes Cyber Essentials asks you to **describe** in the
assessment. They're drafted to be adopted as-is once you fill in the `[bracketed]`
fields (owner name, dates, cadences, provider names) and confirm the "[Confirm …]"
items are actually true in production.

| Policy | Answers CE questions | Key `[fill-in]` / confirm |
|---|---|---|
| [Account Management](ACCOUNT_MANAGEMENT_POLICY.md) | A5.2, A5.3, A5.6, A5.9, A7.1–A7.17 | owner; MFA ON everywhere (incl. `LUMI_MFA=on`); account + admin registers |
| [Patch Management](PATCH_MANAGEMENT_POLICY.md) | A4.6, A6.1–A6.7 | Dependabot/pip-audit on; server OS supported; auto-updates on |
| [Incident Response](INCIDENT_RESPONSE_POLICY.md) | A4.4, A5.6, A7.13, A1.13 | incident lead + contacts; backups restorable |

## How to use them
1. Fill every `[bracketed]` field and resolve each "[Confirm …]".
2. Adopt them (a director signs/dates them).
3. Keep the small **records** each one names (account register, admin register,
   software inventory/patch log, incident log) — an assessor will expect these to be
   real, not just described.
4. Review at the stated cadence.

## What these do NOT cover (still on you / your IT setup)
These are policies. Cyber Essentials also needs the **technical controls actually in
place** on your estate — see `CYBER_ESSENTIALS_AUDIT_2026-08.md` for the full list.
The big organisational items:
- Software firewall on every device; hosting firewall = 443-only inbound, SSH locked down.
- Anti-malware active + auto-updating on every device (A8.x).
- MFA genuinely enabled on Google/M365/AWS/GitHub and the lumi app in production.
- The one lumi-side action still outstanding: **change the live `david@lumihr.co.uk`
  password** off the old known value.

## Not drafted (offer)
Optional supporting documents that some assessors like but CE doesn't strictly
require as separate files:
- an overarching **Information Security Policy** (umbrella), and
- a **Secure Configuration / Device Standards** note (firewall on, malware, screen
  lock, auto-run off, MFA) covering A4.1.1 / A5.8 / A5.9 / A8.x from a policy angle.

Ask if you'd like these too.
