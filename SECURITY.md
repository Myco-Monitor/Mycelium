# Security Policy

**Mycelium** is the local monitoring and control platform for the
[Myco-Monitor](https://myco-monitor.com) ecosystem. It is self-hosted and
runs entirely on the operator's own machine or LAN — there is no Myco-Monitor
cloud service that processes your data. This policy covers the **Mycelium**
application in this repository. The **Spore** and **Hyphae** device firmware are
maintained separately.

## Supported Versions

Security fixes are applied to the latest released `2.x` line. Older versions are
not maintained — please upgrade before reporting.

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security reports.** Use a private
channel so the issue can be fixed before it is disclosed:

1. **Preferred — GitHub private advisory:** go to the repository's **Security**
   tab and choose **"Report a vulnerability"** to open a private security
   advisory.
2. **Email fallback:** <greg@myco-monitor.com>.

To help us triage quickly, please include where practical:

- A description of the issue and its impact.
- The Mycelium version (see `version.py`) and how you run it
  (loopback only, `--host 0.0.0.0` on the LAN, Raspberry Pi, etc.).
- Steps to reproduce, a proof of concept, or affected file/endpoint.
- Any suggested remediation.

### What to expect

This is a small project, so timelines are best-effort:

- **Acknowledgement** within ~5 business days.
- An initial assessment and a planned fix or mitigation once the report is
  confirmed.
- **Coordinated disclosure:** we will agree on a disclosure timeline with you
  and credit you in the advisory unless you prefer to remain anonymous. Please
  give us a reasonable window to ship a fix before any public disclosure.

## Scope

In scope: the Mycelium application — the web UI, REST API, device clients,
authentication, data storage, and TLS/secret handling.

Examples of valid reports include authentication or authorization bypass,
remote code execution, SQL injection, secret exposure, TLS/certificate
weaknesses, and stored/reflected XSS in the web UI.

Out of scope:

- Issues that require an attacker to already have privileged access to the host
  running Mycelium (the data directory and secrets are protected by filesystem
  permissions — see below).
- Spore/Hyphae firmware vulnerabilities (reported via their own repositories).
- Findings against deployments that ignore the documented hardening guidance
  (for example, binding to `0.0.0.0` with `--http` instead of the default HTTPS).

## Security Model (summary)

Mycelium is designed to run locally and keep all data on the operator's machine:

- **HTTPS for the web UI on by default** (opt out with `--http`) using a
  per-install local CA you import once (mkcert-style), or a certificate you supply.
- **HTTPS-only device communication** using CSP-provisioned device certificates
  (`config/ca_root.pem`).
- **Secrets encrypted at rest** — device PINs, the SMTP password, and the
  OpenWeatherMap API key are encrypted with a per-install key; the
  session-signing key is generated automatically. These live in the gitignored
  `data/` directory with owner-only (`0600`) permissions.
- **Passwords** are stored as PBKDF2-HMAC-SHA256 hashes with a per-user salt.
- **Local-first** — no cloud dependency; your data does not leave your network.

For the full security model, TLS setup, and host hardening, see the
[Security section of the README](README.md#security) and
[docs/deployment.md](docs/deployment.md).
