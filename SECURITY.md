# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report them privately to **[info@huskai.dev](mailto:info@huskai.dev)**. Include:

- a description of the issue and its impact,
- steps to reproduce (a proof of concept if you have one),
- any affected version or component.

We'll acknowledge your report, investigate, and keep you updated on a fix. Please
give us a reasonable window to address the issue before any public disclosure.

## Scope

Husk is **local-first**: the backend runs on your machine, data is stored locally
in `~/.husk/`, and there is no cloud component or telemetry. The areas most
relevant to security reports are:

- the local backend API on `127.0.0.1:7654` (`packages/husk-studio-backend`),
- the OpenTelemetry trace ingest endpoint (`/v1/traces`),
- the Cursor and VS Code bridges that relay agent activity to the local backend.

Thanks for helping keep Husk and its users safe.
