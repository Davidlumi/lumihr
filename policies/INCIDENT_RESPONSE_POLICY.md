# Security Incident Response Policy

| | |
|---|---|
| **Owner / Incident Lead** | [Name — e.g. David Whitfield, Director] |
| **Deputy** | [Name, or "none — sole responder"] |
| **Applies to** | All staff, contractors and volunteers |
| **Version** | 1.0 |
| **Effective** | [date] |
| **Review** | At least annually, and after every incident |

> Written to support Cyber Essentials (the compromise-response processes behind
> A5.6, A7.13, A4.4) and to meet UK GDPR breach-notification duties. lumi holds
> **confidential reward/pay data and personal data** (user names and emails), so a
> breach can be reportable to the ICO. Mapping table at the end.

## 1. What is a security incident?

Anything that may compromise the confidentiality, integrity or availability of lumi
systems or data, including:

- a **compromised or suspected-compromised account or password**;
- a **lost or stolen device** (laptop/phone);
- **malware / ransomware** on a device;
- a **phishing** click or credential entry;
- **unauthorised access** to, or exposure of, customer or personal data;
- a vendor/supplier breach affecting our data.

**If in doubt, treat it as an incident and report it.**

## 2. Roles and contacts

- **Incident Lead:** [Name] — [phone] / [email]. Coordinates the response and makes
  the notification decisions.
- **Everyone:** report a suspected incident to the Incident Lead **immediately** —
  by [phone/Slack/email] — even out of hours. Do not wait to be sure.
- **Key external contacts** (fill in):
  - Hosting provider support: [ ]
  - ICO (personal-data breaches): ico.org.uk/make-a-complaint / 0303 123 1113
  - IASME (CE breach feedback, if opted in at A1.13): security@iasme.co.uk
  - NCSC reporting / Action Fraud: ncsc.gov.uk/report
  - Cyber insurer (if CE cyber insurance taken): [ ]

## 3. Response steps

**1. Report & record.** Whoever notices it tells the Incident Lead immediately. The
Lead opens an entry in the **incident log** (§6) — time, what was seen, systems/data
possibly involved.

**2. Contain.** Stop it spreading:
- **Compromised account:** change the password immediately; in the lumi admin
  console **force sign-out** and, if needed, **deactivate** the account (both revoke
  live sessions). Revoke any API tokens/keys.
- **Lost/stolen device:** remotely lock/wipe it if possible; disable that person's
  cloud sessions and change any passwords stored on it.
- **Malware:** disconnect the device from the network; do not use it until cleaned or
  rebuilt.
- **Data exposure:** take the exposed resource offline / revoke the share link.

**3. Assess.** What was accessed? Whose data? Was **personal data** involved? This
decides notification (§4).

**4. Eradicate & recover.** Remove the cause (rebuild the device, rotate all
credentials that may be exposed, patch the exploited vulnerability). Restore service
from a known-good backup if needed. Confirm the attacker no longer has access.

**5. Notify** — see §4.

**6. Review** — see §5.

## 4. Notification & reporting

- **Affected customers:** notify per our contractual/DPA commitments, without undue
  delay, where their data was or may have been affected.
- **ICO (UK GDPR):** if the incident is a **personal-data breach likely to risk
  people's rights and freedoms**, report to the ICO **within 72 hours** of becoming
  aware. lumi accounts hold names/emails and the data is confidential pay data, so
  assess this on every incident. If unsure, the Lead documents the reasoning.
- **Affected individuals:** if the breach is **high risk** to them, inform them too.
- **IASME:** if we opted in at assessment (A1.13), email security@iasme.co.uk.
- **Insurer / NCSC / Action Fraud:** notify as appropriate.

## 5. Post-incident review

Within **[1–2 weeks]** of closing an incident, the Lead runs a short review:
what happened, how it was handled, what to change (a control, a process, training).
Actions are recorded and tracked to completion; this policy and the Account/Patch
policies are updated if needed.

## 6. Records

- **Incident log** — date/time, reporter, description, systems/data involved,
  actions taken, notifications made, root cause, follow-up actions, closure date.
  [Location: e.g. a restricted-access sheet.]

## 7. Preparedness (do these now, not during an incident)

- Confirm you can **force-logout / deactivate** a user in the lumi console and
  **reset any password** quickly.
- Confirm **backups** exist and can be restored (databases + configuration).
- Ensure everyone knows **who to call** and that reporting is blame-free.

## Cyber Essentials mapping

| CE question | Covered by |
|---|---|
| A4.4 change firewall password on compromise | §3 (contain) |
| A5.6 change service passwords on compromise | §3 (contain) |
| A7.13 process for compromised passwords/accounts | §1–§3, §7 |
| A1.13 IASME breach-feedback contact | §2, §4 |
