# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues by emailing the maintainer directly. Include:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if any)

You will receive a response within 48 hours. If confirmed, a patch release will be
prepared and a CVE will be requested if appropriate. Credit will be given in the
release notes unless you prefer to remain anonymous.

## Scope

This package handles sensitive payment data. Security-relevant areas include:

- Credential handling in gateway configs (never logged)
- PII data (card numbers, phone numbers, emails — never logged by GatewayManager)
- Callback verification logic (ensures bank responses are validated before success)
- SOAP/HTTP transport (httpx is used; TLS verification is on by default)

## Out of Scope

- Vulnerabilities in upstream dependencies (report to them directly)
- Bank-side API security issues (report to the respective bank)
