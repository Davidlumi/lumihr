# Secure Configuration / Device Standards

| | |
|---|---|
| **Owner** | [Name — e.g. David Whitfield, Director] |
| **Applies to** | Every device (company-owned or personal/BYOD) used for lumi work, and the network/services they use |
| **Version** | 1.0 |
| **Effective** | [date] |
| **Review** | At least annually |

> The known-good baseline every device and service must meet. Supports Cyber
> Essentials **Firewalls** (A4.1.1), **Secure Configuration** (A5.1, A5.2, A5.3, A5.8,
> A5.9, A5.10) and **Malware Protection** (A8.x). Mapping table at the end.

## 1. Baseline for every device (laptop, desktop, phone)

Before a device is used for lumi work, and kept true thereafter, it must have:

1. **A supported operating system** receiving security updates (see *Patch
   Management*). No end-of-life OS.
2. **Disk encryption on** — FileVault (macOS) / BitLocker (Windows) / device
   encryption (mobile).
3. **A software firewall on** — the OS built-in firewall (macOS firewall / Windows
   Defender Firewall / `ufw` on Linux), enabled at all times, even behind an office
   firewall (A4.1.1).
4. **Automatic updates on** for the OS and apps (see *Patch Management*).
5. **A screen lock** that engages automatically after **[5] minutes** and requires a
   password, PIN (≥6) or biometric to unlock (A5.9, A5.10).
6. **Anti-malware active and auto-updating** (A8.1–A8.3) — e.g. Microsoft Defender on
   Windows; built-in protections + [product] on macOS. Configured to prevent malware
   running and to warn on malicious sites.
7. **Auto-run/auto-play disabled** so files don't execute without the user choosing to
   (A5.8).

## 2. Laptops and desktops

- Only **necessary software** is installed; unused applications, utilities and
  network services are removed or disabled (A5.1).
- Only **necessary local accounts** exist; guest and unused admin accounts are removed
  or disabled (A5.2). Day-to-day work is done as a **standard user**, not an admin
  (see *Account Management* §6).
- Any **default or vendor-set passwords** (on the device, or the office router/
  firewall) are changed to strong, unique ones (A5.3, A4.2).

## 3. Mobile phones and tablets

- Kept on a **supported OS version**.
- Apps installed **only from the official app store**; the device is not
  jailbroken/rooted, so unsigned apps cannot run (A8.4, A8.5).
- Screen lock + encryption on (as §1).
- Used for lumi work only via approved apps/services with MFA.

## 4. Network / boundary

- Office network sits behind a **firewall/router** with inbound blocked by default;
  its **admin password is changed** from default and its **admin interface is not
  reachable from the internet** (or is MFA/IP-allow-list protected) (A4.x).
- On untrusted networks (public wifi), the **device software firewall** is the
  boundary — hence §1.3 applies everywhere.
- **Hosting:** the lumi server's cloud firewall/security group allows **only 443
  (HTTPS) inbound**; administrative access (SSH) is restricted (IP allow-list / bastion
  / SSM), never open to the internet.

## 5. Authentication from the device

- Access to every cloud service **and** the lumi app uses **MFA** (see *Account
  Management* §4). The lumi app enforces this with `LUMI_MFA=on` in production.
- Users authenticate before reaching any organisational data or service (A5.4) — no
  unauthenticated access to confidential data.

## 6. The lumi application (secure hosting)

- Served over **HTTPS**; the session cookie is `Secure`; **HSTS** and a baseline
  **Content-Security-Policy** and related security headers are set (in the app).
- API documentation endpoints are disabled in production.
- Runtime dependencies are pinned and supported (see *Patch Management*).

## 7. New-device setup checklist

Tick each before the device is used for work; record completion in the asset
inventory.

- [ ] Supported OS, up to date, auto-updates on
- [ ] Disk encryption on
- [ ] Software firewall on
- [ ] Anti-malware active + auto-updating; malicious-site warnings on
- [ ] Screen lock auto-engages (≤[5] min), PIN/biometric set
- [ ] Auto-run/auto-play disabled
- [ ] Unnecessary software/accounts removed; standard (non-admin) daily account
- [ ] Default passwords changed
- [ ] MFA set up for every work account (incl. the lumi app)
- [ ] Device added to the asset inventory

## Cyber Essentials mapping

| CE question | Covered by |
|---|---|
| A4.1.1 software firewall on devices | §1.3, §4 |
| A4.2 change router/firewall default password | §2, §4 |
| A5.1 remove unnecessary software/services | §2 |
| A5.2 only necessary accounts | §2 |
| A5.3 change default/guessable passwords | §2 |
| A5.4 authenticate before data access | §5, §6 |
| A5.8 disable auto-run | §1.7 |
| A5.9 / A5.10 device locking | §1.5 |
| A8.1–A8.3 anti-malware | §1.6 |
| A8.4 / A8.5 app allow-listing (mobile) | §3 |
