# Account Management Policy

| | |
|---|---|
| **Owner** | [Name — e.g. David Whitfield, Director] |
| **Applies to** | All staff, contractors and volunteers with access to lumi organisational data or services |
| **Version** | 1.0 |
| **Effective** | [date] |
| **Review** | At least annually, and after any account-related incident |

> Fill in every `[bracketed]` field before adopting. This document is written to
> answer the Cyber Essentials **User Access Control** questions (A7.x) and the
> account parts of Secure Configuration (A5.2, A5.3, A5.6). A mapping table is at the end.

## 1. Purpose & scope

This policy governs how user accounts are created, controlled and removed across
**every system that holds or accesses lumi data or services**, namely:

- **End-user devices** — staff laptops, desktops and phones.
- **The lumi application** — the reward-benchmarking web app (org roles: Admin,
  Contributor, Viewer; and the internal platform-staff/console tier).
- **Cloud services we use** — [Google Workspace / Microsoft 365], [AWS / hosting
  console], [GitHub], the domain registrar, [SMTP/email provider], and any other
  account that stores or processes company data. **Cloud services cannot be
  excluded** (CE requirement).

Only authorised individuals get accounts, and only the access their role needs.

## 2. Creating and approving accounts (A7.1, A7.5)

1. An account is requested by [the person's manager / the joiner's sponsor].
2. It is **approved by [a Director / the person with leadership authority]** before
   it is created. Approval is recorded (email or the account register in §9).
3. The account is created with the **least privilege** needed for the role
   (§5) — never "admin by default".
4. Cloud-service accounts are created under the person's own named identity — never
   a shared or generic login.

## 3. Unique credentials, no sharing (A7.2)

Every device, application and cloud service is accessed with **unique, individual
credentials**. Accounts and passwords are **never shared** between people. Generic
or role mailboxes (e.g. hello@) that require sign-in use individually-delegated
access, not a shared password.

## 4. Passwords, MFA and authentication (A5.3, A7.10–A7.17)

**Password quality (A7.11, A7.12).** For every account we control, passwords must:
- be **at least 12 characters**, OR **at least 8 characters** where the system
  automatically blocks common passwords with a deny-list (the lumi app enforces
  min-8 + a common-password deny-list technically);
- **not** be a common password, a reused password, or anything guessable (pet/
  company name, keyboard runs);
- have **no forced expiry** and **no complexity mandates** (per NCSC guidance).

We encourage staff to use the **[password manager — e.g. 1Password/Bitwarden]** to
generate and store unique passwords, and to build memorable ones from **three
random words**.

**Brute-force protection (A7.10).** Systems must throttle or lock after repeated
failures. The lumi app throttles login attempts (no more than a few tries before a
temporary block) and applies MFA (below).

**Multi-factor authentication (A7.14–A7.17).** MFA is **mandatory on every cloud
service**, for **all users and all administrators**:
- **The lumi app** — MFA is enforced by setting `LUMI_MFA=on` in production (email
  one-time code on every sign-in; requires SMTP configured). **[Confirm this is ON
  in production.]**
- **[Google Workspace / M365 / AWS / GitHub / registrar / SMTP]** — MFA enabled for
  every account, using an authenticator app where possible (SMS only if nothing
  else is available). **[Confirm enabled for all.]**

**Device unlocking (A5.9).** Every laptop and phone has a screen lock (password,
PIN of at least 6, or biometric) that engages automatically.

## 5. Least privilege and access reviews (A7.4, A7.9)

- Access is granted strictly on a **need-to-do-the-job** basis.
- When someone **changes role**, their access is adjusted the same week — access no
  longer needed is removed.
- **[Quarterly]**, [the Owner] reviews who has access to each system and confirms it
  is still appropriate. The review is recorded (date + reviewer) in the account
  register.

## 6. Administrative accounts (A7.5–A7.8)

Administrative (privileged) accounts get special care:

- Admin access is **granted only with Director approval** (A7.5) and only to those
  who need it.
- Administrators use a **separate account for admin tasks** — never the account used
  for email or web browsing (A7.6, A7.7). Day-to-day work is done as a standard user.
- In the lumi app, cross-tenant staff powers live in a **separate platform-admin
  tier**, restricted to an explicit allowlist ([david@lumihr.co.uk]); org Admins
  cannot reach it.
- We keep an **admin register** listing everyone with administrative access to each
  system (A7.8), and **[the Owner]** reviews it **[quarterly]** (A7.9). Access no
  longer needed is removed.

## 7. Removing access — leavers and role changes (A7.3)

When someone leaves, or no longer needs access:

1. **On their last day (or immediately on suspicion of a problem)**, [the Owner]
   disables or deletes their accounts on **every** system — laptop, the lumi app,
   and every cloud service.
2. In the lumi app, use the admin console to **deactivate the user** (this also
   revokes their live sessions) and/or **force sign-out**.
3. Recover or wipe any company device; revoke shared-mailbox delegation and any
   API tokens/keys they held.
4. The offboarding is recorded (date + who actioned it) in the account register.

## 8. Compromised or suspected-compromised accounts (A5.6, A7.13, A4.4)

If a password or account is known or suspected to be compromised:

1. **Change the password immediately** and, in the lumi app, **force sign-out**
   (revokes all sessions) — self-service reset also revokes existing sessions.
2. For firewalls/routers, change the admin password promptly (A4.4).
3. Follow the **Incident Response Policy** for containment, notification and review.

There is an established route to do this quickly at any time — see Incident Response.

## 9. Records

- **Account register** — who has an account on which systems, role/access level,
  approver, date created, date reviewed, date removed. [Location: e.g. a shared
  sheet in Google Workspace.]
- **Admin register** — who holds administrative access to each system.
- Approvals and offboarding actions are recorded against these registers.

## Cyber Essentials mapping

| CE question | Covered by |
|---|---|
| A5.2 only necessary accounts | §2, §5, §7 |
| A5.3 change default/guessable passwords | §4 |
| A5.6 change passwords on compromise | §8 |
| A5.9 device locking | §4 |
| A7.1 account creation/approval process | §2 |
| A7.2 unique credentials | §3 |
| A7.3 remove leavers | §7 |
| A7.4 least privilege | §5 |
| A7.5 admin-access process | §6 |
| A7.6 / A7.7 separate admin accounts | §6 |
| A7.8 track admin accounts | §6, §9 |
| A7.9 review admin access | §6 |
| A7.10 brute-force protection | §4 |
| A7.11 password quality | §4 |
| A7.12 encourage unique passwords | §4 |
| A7.13 compromise process | §8 |
| A7.14–A7.17 MFA on cloud services | §4 |
