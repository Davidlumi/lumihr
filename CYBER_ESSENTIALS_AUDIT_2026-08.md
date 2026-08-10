# Cyber Essentials v3.3 — Gap Analysis for lumi

**Date:** 2026-08-10 · **Question set:** Danzell 2026 (v16.3) · **Requirements:** IT Infrastructure v3.3

## Read this first (scope reality)

Cyber Essentials certifies your **whole IT estate** — staff laptops/phones, the
cloud accounts your company uses (Google Workspace / Microsoft 365, AWS console,
GitHub, etc.), your network boundary, device patching and malware protection.
**Most of CE is organisational and lives in your operations, not in the lumi
codebase.** I can only fix the parts of CE that live in the application/stack; the
rest is a checklist for you (and whoever manages the hosting).

The lumi web app appears in CE in two ways:
- **A5.4–A5.7** — "an external service you host that serves confidential data over the internet" → its authentication + brute-force protection. **Code — now compliant.**
- **A7.14–A7.17** — "a cloud service your organisation uses" → **MFA. This is an *automatic fail* and lumi currently has no MFA. Needs a build decision (below).**

**Legend:** ✅ fixed in code · 🔧 hosting config (you/devops) · 👤 organisational (you) · ⛔ **gap — decision needed**

---

## 1. Firewalls (A4.x) — 👤 / 🔧 organisational

None of this is in the repo. Actions:
- **A4.1/A4.1.1** Enable the software firewall on **every** staff laptop/desktop/server (Windows Defender Firewall / macOS firewall / ufw). 🔧👤
- **A4.2/A4.3** Change default admin passwords on your office router/firewall; set the admin auth to option **B** (min-8 + common-password blocking) or **C** (min-12). 👤
- **A4.5–A4.8** Document your inbound rules with a business case; block unauthenticated inbound by default. On your **hosting** (AWS security group / cloud firewall): only 443 (HTTPS) inbound to the app; SSH restricted to an IP allow-list or via SSM, never open to the internet. 🔧
- **A4.9–A4.11** Firewall/router admin interface must not be reachable from the internet unless MFA-protected or IP-allow-listed. 🔧
- **A4.6** Review firewall rules at least every 12 months. 👤

## 2. Secure Configuration (A5.x)

| Q | Requirement | Status |
|---|---|---|
| A5.1 | Remove unnecessary software/services | 🔧👤 laptops + server; **code:** API docs already disabled (`docs_url=None`) ✅ |
| A5.2 | Only necessary user accounts | ✅ **code:** demo accounts no longer auto-seed in production (gated behind `LUMI_SEED_DEMO`, default off) + 👤 laptop accounts |
| A5.3 | Change default/guessable passwords | ✅ **code:** demo + super-admin known-password defaults removed (`seed_staff_admin.py` now env/random) — **👤 ACTION: change the live `david@lumihr.co.uk` password** (it currently holds the old known value) + 👤 laptop/router passwords |
| A5.4/A5.5 | External service auth quality | ✅ **code:** lumi = **option B** — min-8, **no maximum length**, common-password deny-list |
| A5.6 | Password change on compromise | ✅ **code:** self-service reset (revokes sessions) + 👤 documented process |
| A5.7 | Brute-force protection (no MFA) | ✅ **code:** option **A** — throttling (5 attempts / 5 min per email+IP; ≤10/5min ✓) |
| A5.8 | Disable auto-run of downloaded files | 👤 device policy |
| A5.9/A5.10 | Device locking (PIN/biometric ≥6) | 👤 laptops/phones |

## 3. Security Update Management (A6.x)

| Q | Requirement | Status |
|---|---|---|
| A6.1 | Supported OS + firmware | 🔧👤 — ensure the **hosting server OS** is a supported LTS; all laptops on supported OS versions |
| A6.2/A6.3 | Supported + licensed software | ✅ **code:** `requirements.txt` now pins the runtime deps — all current/supported (FastAPI 0.128.8, Starlette 0.49.3, uvicorn 0.39.0, bcrypt 5.0.0, pydantic 2.13.4, anthropic 0.109.2). Open-source, licensed. |
| A6.4/A6.5 | **14-day** patching of high/critical (CVSS≥7) | 🔧👤 **process** — enable OS auto-updates on all devices; for the app stack, watch `pip` advisories / GitHub Dependabot and bump `requirements.txt` within 14 days. **A6.4/A6.5 are automatic-fail questions if you can't attest to this.** |
| A6.6/A6.7 | Remove unsupported software | ✅ **code:** no unsupported deps + 👤 devices |

**Recommendation:** turn on GitHub Dependabot (or `pip-audit` in CI) so dependency CVEs are surfaced and the 14-day clock is easy to meet.

## 4. User Access Control (A7.x)

| Q | Requirement | Status |
|---|---|---|
| A7.1 | Account creation process | 👤 document it (who approves a new lumi/laptop/cloud account) |
| A7.2 | Unique credentials, no shared accounts | ✅ **code:** unique email+password per user; no shared logins |
| A7.3 | Remove leavers' accounts | ✅ **code:** deactivate/remove supported + 👤 offboarding checklist |
| A7.4 | Least privilege | ✅ **code:** RBAC (admin/contributor/viewer) + separate platform-staff tier |
| A7.5–A7.9 | Admin process / separation / tracking / review | ✅ **code:** platform-admin is a separate tier from org roles + 👤 keep a list of who has admin, review regularly, use separate admin accounts (no email/web-browsing on them) |
| A7.10/A7.11 | Brute-force + password quality | ✅ **code:** throttling + deny-list + min-8 |
| A7.12/A7.13 | Encourage strong passwords / compromise process | ✅ **code:** live strength meter + reset flow + 👤 staff education |
| **A7.14** | MFA **available** on all cloud services | ✅ **code:** email one-time-code MFA built into the lumi app · 👤 confirm MFA is enabled on Google/MS365/AWS/GitHub too |
| **A7.16** | **MFA applied to all admins** of cloud services — **AUTO FAIL** | ✅ **code:** enforced for every account (incl. platform-admin) when `LUMI_MFA=on` · 🔧 **set `LUMI_MFA=on` + SMTP in production** |
| **A7.17** | **MFA applied to all users** of cloud services — **AUTO FAIL** | ✅ **code:** enforced for all users when `LUMI_MFA=on` · 🔧 **production activation below** |

## 5. Malware Protection (A8.x) — 👤 organisational

Not in the repo. Actions:
- **A8.1/A8.2/A8.3** Anti-malware active on all laptops (Windows Defender is fine), set to update automatically, block malware execution and malicious sites. 👤
- **A8.4/A8.5** Phones/tablets: app-store-only installs (default) or MDM allow-listing. 👤

---

## ✅ MFA — built (email one-time code, enforced for all users)

A7.16/A7.17 (MFA on cloud-service admins **and** users) are automatic fails, and
the lumi app now satisfies them. On a correct password the app mints a short-lived
challenge and emails a 6-digit code; the session is created only after the code is
verified. Codes are stored hashed, expire in 10 minutes, are single-use, capped at
5 attempts, and the endpoint is rate-limited. Verified end-to-end on a throwaway
(login→code→session; wrong code; resend invalidates the old; reuse rejected).

**Production activation (🔧 you/devops):**
1. **Set `LUMI_MFA=on`** on the production server — this enforces the code step for
   every login. (Off by default so dev/QA/gates run password-only; they can't read
   an emailed code.)
2. **Configure SMTP** (`LUMI_SMTP_HOST`, etc.) — email OTP is useless until real
   email delivery is live. Until then codes are only written to the server log.
   This is the one hard dependency of the email-code choice.

If you later want stronger MFA (authenticator-app TOTP), it slots into the same
challenge/verify flow — email code can stay as a fallback.

Everything else in the stack is done or is on the organisational checklist above.

## What I changed in code (committed)
- Password hashing pre-hashes with SHA-256 → **no maximum length** (A5.5) and no bcrypt truncation; legacy logins still work.
- Demo accounts no longer auto-seed in production; super-admin seed no longer uses a known default password (A5.2/A5.3).
- Security-headers middleware: HSTS (https), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP.
- `requirements.txt` pinning supported dependency versions (A6).

## Your immediate action list
1. **Change the live `david@lumihr.co.uk` password** off the old known value (and never reuse `lumi-demo-2026` in production).
2. Decide MFA scope so I can build it (blocks certification).
3. Confirm MFA is on for Google/MS365/AWS/GitHub and every other cloud account.
4. Software firewall on every device; hosting firewall = 443-only inbound, SSH locked down.
5. Anti-malware active + auto-updating on every device; OS auto-updates on.
6. Turn on Dependabot/pip-audit for the 14-day patch rule.
7. Write down: account creation/approval, leaver offboarding, admin list + review, compromise-response — CE asks for these as described processes.
