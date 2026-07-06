# Security Policy

## Supported versions

SpecOps is at `0.x`. Security fixes are released only against the latest
published version.

| Version | Supported |
|---------|-----------|
| latest `0.1.x` | ✅ |
| older | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately through one of these channels:

- **GitHub**: use [Private vulnerability reporting](https://github.com/paulo2nd/specops/security/advisories/new)
  (Security → Report a vulnerability).
- **Email**: paulosegundo@gmail.com

Please include:

- a description of the vulnerability and its impact,
- steps to reproduce (a minimal repository or command sequence is ideal),
- the SpecOps version (`specops --version`) and your OS / Python version.

## What to expect

- Acknowledgement within **5 business days**.
- An assessment and, if confirmed, a remediation plan with a target timeline.
- Credit in the release notes once a fix ships, unless you prefer to remain
  anonymous.

## Scope notes

SpecOps performs no network I/O after install and only reads/writes files inside
the target repository. Reports most relevant to SpecOps include: unsafe file
writes outside the repository, injection into prompt files that escapes the
marker-delimited blocks, or evidence/ledger tampering that bypasses the
`reconcile` / `consistency` gates.
