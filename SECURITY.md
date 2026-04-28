# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in `qbo-mcp`, please report it
responsibly. Do **not** open a public GitHub issue for security concerns.

**Contact:** open a private security advisory on the GitHub repository (path
TBD post-launch), or email the maintainer directly. We aim to respond to
reports within 72 hours.

## Scope

In scope:

- The MCP server entry point (`qbo_mcp/server.py`)
- The QBO HTTP client (`qbo_mcp/client.py`), including OAuth refresh-token
  handling
- Configuration and credential handling (`qbo_mcp/config.py`)
- Packaged dependencies and their pinned versions

Out of scope:

- The upstream Intuit / QuickBooks Online API itself (report directly to
  Intuit Security)
- The MCP protocol specification or the official MCP Python SDK
- Bugs that require an attacker to already control the host running the
  server

## Credential handling

This project never logs QBO `client_secret`, `refresh_token`, or
`access_token` values, never persists them outside the process, and reads
the long-lived secrets only from environment variables.

QBO refresh tokens **rotate on every refresh**. The client exposes an
`on_refresh_token_rotated` callback so your deployment can persist the new
token to durable storage. Failing to do this means a process restart can
lose the only valid refresh token, a denial-of-service for your own
integration, but not a data leak. If you find a code path where rotated
tokens are dropped silently or written to logs, report it as a security
issue.

## OAuth scope

This server only calls **read** endpoints (`GET /v3/company/.../query` and
`GET /v3/company/.../<entity>/<id>`). Even so, defense in depth means you
should:

- Use the **Accounting** scope on the Intuit Developer app, not the
  Payments or Payroll scopes, unless you genuinely need them.
- If you connect a multi-realm production app, scope the refresh token to
  one realm at a time.

## Disclosure timeline

Our default policy is coordinated disclosure: we will work with the
reporter to ship a fix and credit the discovery on a timeline that gives
users time to upgrade. The default embargo is 30 days from confirmed
reproduction.
