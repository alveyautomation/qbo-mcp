# Changelog

All notable changes to `qbo-mcp` are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]. 2026-04-26

Initial public release.

### Added

- MCP server entry point (`qbo_mcp/server.py`) using the official `mcp` Python SDK with `FastMCP`.
- Eight read-only tools:
  - `qbo_search_customers`
  - `qbo_get_customer`
  - `qbo_search_vendors`
  - `qbo_get_vendor`
  - `qbo_search_invoices`
  - `qbo_get_invoice`
  - `qbo_search_bills`
  - `qbo_get_chart_of_accounts`
- HTTP client (`qbo_mcp/client.py`):
  - OAuth 2.0 refresh-token flow against `oauth.platform.intuit.com`.
  - Access token caching with a 2-minute refresh margin to avoid mid-page expiry.
  - Refresh-token rotation hook (`on_refresh_token_rotated`) so deployments can persist the rotated value.
  - Automatic access-token refresh on `401`.
  - Exponential backoff retry on transient `429` / `5xx` and connection errors.
  - Transparent `STARTPOSITION` / `MAXRESULTS` pagination for the `query` endpoint.
  - QBO query string escaping (`'`, `\`, `_`).
- Sandbox vs. production environment switch (`QBO_ENVIRONMENT`).
- Optional `QBO_MINOR_VERSION` to pin Intuit API behavior.
- Configuration via environment variables (`qbo_mcp/config.py`).
- Pytest suite with mocked HTTP responses (50+ tests, all synthetic fixtures).
- Pre-commit configuration: gitleaks, trufflehog, ruff, ruff-format, tenant-fingerprint scrubber.
- MIT license, security policy, contributing guidance in README.

### Notes

- v0.1 is read-only by design. Write endpoints (create invoice, create bill, journal-entry post) are planned for v0.2.
- Integration tests against a live QBO sandbox realm are gated by `QBO_INTEGRATION_TESTS=1` and are not exercised by default.
