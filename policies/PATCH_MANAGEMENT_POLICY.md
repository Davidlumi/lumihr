# Patch & Security Update Management Policy

| | |
|---|---|
| **Owner** | [Name — e.g. David Whitfield, Director] |
| **Applies to** | All in-scope devices, servers, network equipment, applications and the lumi application stack |
| **Version** | 1.0 |
| **Effective** | [date] |
| **Review** | At least annually |

> Written to answer Cyber Essentials **Security Update Management** (A6.x) and the
> firewall-firmware/review parts of A4. **A6.4 and A6.5 are automatic-fail questions** —
> the 14-day rule below is mandatory. Mapping table at the end.

## 1. Purpose & scope

Keep all software free of known, fixable vulnerabilities. This covers:

- **Operating systems** — staff laptops/phones, and the **hosting server OS**.
- **Firmware** — office router/firewall (treated as an operating system).
- **Applications** — browsers, email, office suite, and any other installed software.
- **The lumi application stack** — its Python dependencies (`requirements.txt`) and
  the runtime.

## 2. Only supported, licensed software (A6.1, A6.2, A6.3, A6.6, A6.7)

- Every OS and application in use must be **currently supported by its vendor** and
  receiving security updates. **No end-of-life software** (e.g. an unsupported
  Windows/macOS version, EOL Python) is used on any internet-connected device.
- All software is **licensed** (open-source is fine where licence terms are met).
- When something becomes unsupported it is **removed**, or the device is moved out
  of scope onto a segregated network with no internet access. We do **not** keep
  unsupported, internet-connected software.
- The lumi runtime dependencies are pinned in **`requirements.txt`** and are all
  currently-supported versions; the hosting server runs a supported OS/LTS.

## 3. The 14-day rule for high/critical fixes (A6.4, A6.5) — mandatory

Any update that fixes a vulnerability the vendor rates **"critical" or "high risk"**,
or that carries a **CVSS v3 base score of 7.0+** (or where no severity is stated),
is **applied within 14 days of release**, on every in-scope device, server, firewall
firmware and application — including the lumi dependency stack.

This is an absolute requirement; missing it fails Cyber Essentials.

## 4. Automatic updates (A6.4.1, A6.5.1)

Automatic updates are **enabled wherever possible**:

- **Laptops/phones** — OS auto-updates ON; app stores set to auto-update.
- **Browsers** — auto-update ON.
- Confirm the setting on each device as part of onboarding.

## 5. Where auto-updates are not used (A6.4.2, A6.5.2)

For systems we manage directly (the **hosting server**, the **office firewall/router
firmware**, and the **lumi application stack**), where auto-update isn't appropriate:

- **[Owner]** checks for new high/critical updates **[at least weekly]** and applies
  them **within the 14-day window**.
- **Hosting server OS:** [`unattended-upgrades` enabled for security updates / manual
  `apt`/`yum` patch on the weekly check].
- **Firewall/router firmware:** checked **[monthly and on vendor notification]** and
  updated within 14 days of a high/critical release.

## 6. The lumi application dependency stack

- Dependencies are pinned in **`requirements.txt`** so the exact versions in
  production are known and auditable.
- **[Enable GitHub Dependabot alerts and/or run `pip-audit` in CI]** so dependency
  CVEs are surfaced automatically. **[Confirm enabled.]**
- When an alert reports a high/critical (CVSS ≥ 7) issue in a dependency, bump the
  pin in `requirements.txt`, test, and **redeploy within 14 days**. Record the bump
  in `DECISIONS.md`.
- Application changes are deployed via [your deploy process — e.g. git push + restart].

## 7. Firewall rules review (A4.6)

Firewall/router inbound rules are **reviewed at least every 12 months** by [Owner]:
any rule no longer needed is removed. Each rule has a documented business need.

## 8. Software inventory (supports all of the above)

We keep a **software/asset inventory** — the OS + version on each device, the
firewall model + firmware, key applications, and the cloud services in use — so we
know what needs patching and can spot anything that has gone end-of-life.
[Location: e.g. a shared sheet.]

## 9. Records

- **Patch log / inventory** — devices, software, versions, and when high/critical
  updates were applied.
- Dependency bumps recorded in `DECISIONS.md`.

## Cyber Essentials mapping

| CE question | Covered by |
|---|---|
| A4.6 firewall rule review | §7 |
| A6.1 supported OS/firmware | §2 |
| A6.2 / A6.2.x supported software | §2, §8 |
| A6.3 licensed/supported | §2 |
| A6.4 14-day OS/firmware patching (auto-fail) | §3 |
| A6.4.1 auto-updates for OS | §4 |
| A6.4.2 non-auto-update process | §5 |
| A6.5 14-day software patching (auto-fail) | §3, §6 |
| A6.5.1 auto-updates for apps | §4 |
| A6.5.2 non-auto-update process | §5, §6 |
| A6.6 / A6.7 remove unsupported software | §2 |
