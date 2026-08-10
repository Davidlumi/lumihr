# Information Security Policy

| | |
|---|---|
| **Owner** | [Name — e.g. David Whitfield, Director] |
| **Applies to** | All staff, contractors and volunteers, and all lumi systems and data |
| **Version** | 1.0 |
| **Effective** | [date] |
| **Approved by** | [Director / board member — signature + date] |
| **Review** | At least annually, and after any significant change or incident |

> This is the umbrella policy. It states our commitment and points to the detailed
> policies that implement it. It supports Cyber Essentials across all five controls;
> mapping table at the end.

## 1. Purpose and commitment

lumi provides reward-benchmarking software and, in doing so, holds **confidential
customer pay data and personal data**. Protecting that information — its
confidentiality, integrity and availability — is fundamental to our business and to
our customers' trust. [Management / the Director] is committed to maintaining
appropriate security controls, meeting our legal obligations (including UK GDPR), and
maintaining **Cyber Essentials** certification.

## 2. Scope

This policy applies to **all** of the IT lumi uses to run the business:
- end-user devices (laptops, desktops, phones — company-owned and any personal
  devices used for work);
- the **lumi application** and its hosting;
- all **cloud services** we use ([Google Workspace / M365], [AWS/hosting], [GitHub],
  the domain registrar, [email/SMTP], etc.) — none can be out of scope;
- all business data, wherever it is stored.

## 3. Roles and responsibilities

- **[Owner / Director]** owns information security overall: sets policy, approves
  exceptions, and makes breach-notification decisions.
- **Everyone** is responsible for following these policies: using strong unique
  passwords and MFA, keeping devices updated and locked, not installing untrusted
  software, being alert to phishing, and **reporting anything suspicious immediately**.
- **Third parties / suppliers** who handle our data must meet equivalent standards
  (§8).

## 4. Our approach — the five controls

We implement the Cyber Essentials technical controls; each has a detailed policy or
standard:

1. **Firewalls** — a firewall protects every device and our network boundary;
   inbound access is blocked by default. → *Secure Configuration / Device Standards*.
2. **Secure configuration** — devices and services are set up to a known-good
   standard; defaults and unnecessary software/accounts are removed. →
   *[Secure Configuration / Device Standards](SECURE_CONFIGURATION_STANDARD.md)*.
3. **Security update management** — supported software only, patched within 14 days
   of high/critical fixes. → *[Patch Management](PATCH_MANAGEMENT_POLICY.md)*.
4. **User access control** — least-privilege, unique credentials, MFA everywhere,
   prompt removal of access. → *[Account Management](ACCOUNT_MANAGEMENT_POLICY.md)*.
5. **Malware protection** — active anti-malware / approved-apps-only on every device.
   → *Secure Configuration / Device Standards*.

## 5. Data protection and confidentiality

- We handle personal data under **UK GDPR**: collect only what we need, keep it only
  as long as needed, and protect it.
- Customer reward/pay data is **confidential**; access is on a need-to-know basis and
  governed by our customer terms and Data Sharing Agreement (DPA).
- Benchmark outputs are **anonymised/aggregated** and subject to a minimum-count
  suppression floor so no individual organisation is identifiable.
- Personal-data breaches are handled per the
  *[Incident Response Policy](INCIDENT_RESPONSE_POLICY.md)* (including the 72-hour ICO
  assessment).

## 6. Acceptable use (staff essentials)

Staff must:
- use a unique, strong password (via the [password manager]) and MFA on every account;
- keep devices updated, encrypted and screen-locked;
- only install software from official stores / the approved list;
- not use company accounts or data for anything unauthorised;
- be cautious with links and attachments, and **report suspected phishing or any
  incident to [Owner] immediately**.

## 7. Training and awareness

All staff are briefed on this policy at induction and **[annually]**, covering
passwords/MFA, phishing, safe device use, and how to report an incident. New joiners
complete it before being given access.

## 8. Suppliers and third parties

- Cloud providers operate a **shared-responsibility model**; we confirm they provide
  the controls we rely on (via their security/trust documentation) and we configure
  our side securely.
- Any supplier or MSP account that can access our data or systems is in scope of our
  access-control and offboarding processes (*Account Management*).

## 9. Backups and resilience

We keep **regular backups** of critical data (the application database + key
configuration), stored securely and separately, and we **periodically test that a
restore works**. [Owner] owns backups. [State cadence — e.g. daily automated
backups, restore test [quarterly].]

## 10. Governance, exceptions and review

- This policy and its sub-policies are **reviewed at least annually** and after any
  significant change or incident.
- Exceptions require [Owner] approval and are recorded with a rationale and an expiry.
- Breaches of this policy may lead to disciplinary action.

## 11. Related documents

- [Account Management Policy](ACCOUNT_MANAGEMENT_POLICY.md)
- [Patch & Security Update Management Policy](PATCH_MANAGEMENT_POLICY.md)
- [Incident Response Policy](INCIDENT_RESPONSE_POLICY.md)
- [Secure Configuration / Device Standards](SECURE_CONFIGURATION_STANDARD.md)
- `CYBER_ESSENTIALS_AUDIT_2026-08.md` (control-by-control status)

## Cyber Essentials mapping

| CE area | Covered by |
|---|---|
| Overall management commitment & scope | §1, §2 |
| Firewalls (control 1) | §4, Secure Config standard |
| Secure Configuration (control 2) | §4, Secure Config standard |
| Security Update Management (control 3) | §4, Patch Management |
| User Access Control (control 4) | §4, Account Management |
| Malware Protection (control 5) | §4, Secure Config standard |
| Data protection / breach duties | §5, Incident Response |
| Backups (recommended) | §9 |
| Attestation / board sign-off | Approved-by header, §10 |
