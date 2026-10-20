# Security policy

## Supported versions

Soundline is in its specification phase and has no release yet. Once released, security fixes target the latest minor version.

## Reporting a vulnerability

**Please do not open a public issue for a vulnerability.**

Use GitHub's [private vulnerability reporting](https://github.com/yamsdmc/soundline/security/advisories/new) for this repository. You will receive an acknowledgment within 7 days.

Please include:

- the affected version or commit;
- a description of the issue and its impact;
- steps to reproduce, or a proof of concept;
- any suggested fix.

## Contact

Private reports, including code of conduct reports, go through the private reporting channel above.

## Scope

Of particular interest, given Soundline's threat model ([spec chapter 10](docs/spec/10-operations.md)):

- prompt injection through ingested documents that bypasses citation verification or alters system behavior;
- cross-corpus or cross-tenant data leakage;
- path traversal, SSRF or resource exhaustion during ingestion;
- leakage of secrets in logs, traces or error messages.
