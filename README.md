# qbo-mcp

> The Model Context Protocol server for QuickBooks Online. Plug Claude into your books â€” customers, vendors, invoices, bills, and the chart of accounts â€” read-only, in five minutes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io)

## Why this exists

Roughly seven million businesses keep their books in QuickBooks Online. Intuit publishes a capable REST API but no official MCP server, so every team that wants Claude (or any MCP-aware AI assistant) to *see* their books ends up writing the same OAuth-and-pagination glue from scratch.

If you use Claude to operate finance day-to-day â€” chasing AR, sanity-checking AP, prepping for a board update â€” that gap is the difference between *"how much did Acme owe us at the end of March?"* working out of the box and *"how much did Acme owe us at the end of March?"* requiring a custom integration.

`qbo-mcp` closes that gap. It's a tiny, well-tested, MIT-licensed MCP server that exposes eight read-only QBO endpoints to any MCP client. Built from years of running production QBO automation against real money flow â€” every edge that surfaced in production (token rotation, 429 backoff, mid-page expiry, query-string escaping) is handled in `client.py` so you don't have to learn it the hard way.

## What you can do with it

Wire this server into Claude Code, Claude Desktop, or any MCP host, then ask things like:

- *"Find every customer matching 'Acme' and show me their balances."*
- *"How much do we owe WidgetCo right now? List the open bills."*
- *"Pull all unpaid invoices created this month and group them by customer."*
- *"What does our chart of accounts look like? List every Bank and Other Current Asset account with its current balance."*
- *"Compare last week's bill volume to the same week last month."*

Claude reads your books directly. No copy-paste, no spreadsheets, no custom pipelines.

## Tools (v0.1, all read-only)

| Tool                          | What it does                                             |
| ----------------------------- | -------------------------------------------------------- |
| `qbo_search_customers`        | Find customers by display name (substring, case-insens). |
| `qbo_get_customer`            | Fetch one customer by Id.                                |
| `qbo_search_vendors`          | Find vendors by display name.                            |
| `qbo_get_vendor`              | Fetch one vendor by Id.                                  |
| `qbo_search_invoices`         | List invoices in a date window, optionally open/paid.    |
| `qbo_get_invoice`             | Fetch one invoice by Id, including line items.           |
| `qbo_search_bills`            | List bills in a date window, optionally open/paid.       |
| `qbo_get_chart_of_accounts`   | Return the active chart of accounts with balances.       |

Write endpoints (create invoice, create bill, post journal entry) are intentionally **not** in v0.1. They are planned for v0.2 once read-only ergonomics settle. We will not ship a write tool that reaches into your books until the read surface has been beaten on for a release cycle.

## Install

```bash
pip install qbo-mcp
```

> v0.1 ships from this repository. PyPI publication is pending â€” for now, install with `pip install git+https://github.com/alveyautomation/qbo-mcp` or clone and run `pip install -e .` locally.

## One-time OAuth setup

QBO uses OAuth 2.0 with rotating refresh tokens. You only do this dance **once**, then `qbo-mcp` keeps itself authenticated forever (as long as it runs at least once every 100 days). Total time: about 60 seconds.

1. **Create an app** at <https://developer.intuit.com/>. Pick the **Accounting** scope. Copy the `client_id` and `client_secret`.
2. **Visit the OAuth Playground** at <https://developer.intuit.com/app/developer/playground>. Select your app, pick the environment (Sandbox or Production), and click *Get Authorization Code*. Sign in to the QuickBooks company you want to expose.
3. **Exchange the code** for tokens â€” the Playground does this for you. Copy:
   - `refresh_token` (long string, lasts 100 days of inactivity)
   - `realmId` (numeric, identifies your QBO company)
4. **Save them** to `.env`:

```bash
QBO_CLIENT_ID=ABxxxxxxxxxxxxxx
QBO_CLIENT_SECRET=xxxxxxxxxxxxxxxx
QBO_REFRESH_TOKEN=ABxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
QBO_REALM_ID=1234567890123456
QBO_ENVIRONMENT=production       # or "sandbox"
```

That's it. The first tool call exchanges the refresh token for an access token; subsequent calls reuse the cached access token until it expires (~55 minutes), at which point the client refreshes silently.

> **Refresh-token rotation:** Intuit issues a *new* refresh token on every refresh and immediately invalidates the old one. If your deployment runs in a single long-lived process, this is invisible. If your deployment restarts often (containers, serverless), persist the rotated token. Subscribe to `QBOClient(on_refresh_token_rotated=â€¦)` to capture every rotation. See [SECURITY.md](SECURITY.md) for the full story.

## Wire into Claude Code

Add to `~/.claude/claude_code_config.json` (or your project's MCP config):

```json
{
  "mcpServers": {
    "qbo": {
      "command": "qbo-mcp",
      "env": {
        "QBO_CLIENT_ID": "ABxxxxxxxxxxxxxx",
        "QBO_CLIENT_SECRET": "xxxxxxxxxxxxxxxx",
        "QBO_REFRESH_TOKEN": "ABxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "QBO_REALM_ID": "1234567890123456",
        "QBO_ENVIRONMENT": "production"
      }
    }
  }
}
```

Restart Claude Code. The eight `qbo_*` tools will appear in any new session.

## Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the same `mcpServers` block as above. Restart the desktop app.

## Tool reference

Every tool returns a JSON envelope:

```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "error": "human-readable message" }
```

### `qbo_search_customers`

```python
qbo_search_customers(query: str, limit: int = 50)
```

Substring match against `Customer.DisplayName`. The query is escaped before embedding into QBO's query language, so apostrophes (`O'Brien`) and underscores (`acme_test`) are safe.

Example response:

```json
{
  "ok": true,
  "data": {
    "customers": [
      { "Id": "1001", "DisplayName": "Acme Corp", "Balance": 1250.00 }
    ],
    "count": 1,
    "query": "acme",
    "limit": 50
  }
}
```

### `qbo_get_customer`

```python
qbo_get_customer(customer_id: str)
```

Fetches the full customer record by `Id`. Returns `data: null` when the Id does not exist (404).

### `qbo_search_vendors` / `qbo_get_vendor`

Symmetric to the customer pair, but against the `Vendor` entity.

### `qbo_search_invoices`

```python
qbo_search_invoices(
    date_from: str,                     # ISO date "YYYY-MM-DD"
    date_to: str,                       # ISO date "YYYY-MM-DD"
    status: str | None = None,          # "open" | "paid" | None
    limit: int = 200,                   # max 2000
)
```

Window is inclusive on `Invoice.TxnDate`. The `status` filter is a convenience over QBO's `Balance` field â€” `"open"` returns invoices with `Balance > 0`, `"paid"` returns invoices with `Balance = 0`.

Pagination is handled transparently: QBO's query endpoint requires explicit `STARTPOSITION` / `MAXRESULTS` clauses, and the client walks pages until either `limit` is reached or the upstream returns a short page. The response includes `limit_reached: true` when `limit` was the stopping condition.

### `qbo_get_invoice`

```python
qbo_get_invoice(invoice_id: str)
```

Returns the full invoice record (with `Line[]`), or `data: null` for a 404.

### `qbo_search_bills` / `qbo_get_invoice` parity

`qbo_search_bills` mirrors `qbo_search_invoices` but against the `Bill` entity (vendor-side). Same date semantics, same status filter.

### `qbo_get_chart_of_accounts`

```python
qbo_get_chart_of_accounts()
```

Returns every active account in the realm. Each record includes `Id`, `Name`, `AccountType`, `AccountSubType`, `Classification`, and `CurrentBalance` among other QBO fields. Useful for grounding any "where did this transaction post?" question.

## Local development

```bash
git clone https://github.com/alveyautomation/qbo-mcp
cd qbo-mcp
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                # 50+ tests, ~3s
```

Pre-commit hooks (gitleaks, trufflehog, ruff, formatter, tenant-fingerprint scrubber):

```bash
pip install pre-commit
pre-commit install
```

Integration tests against a real QBO sandbox realm are gated behind `QBO_INTEGRATION_TESTS=1`. They are not required for normal contribution.

## Troubleshooting

**`Failed to refresh QBO access token`** â€” refresh token has been rotated out from under you, or the app's `client_id` / `client_secret` is wrong. Refresh tokens are invalidated as soon as a new one is issued, so if two processes share a refresh token, whichever one refreshes first wins. Solution: persist rotated tokens (see `on_refresh_token_rotated`) or run only one server per refresh-token credential.

**`Missing required environment variables`** â€” the server tried to start before its `.env` was loaded. Either export the vars in the parent shell, or ensure your MCP host config includes them in the `env` block.

**Empty results despite known data** â€” confirm `QBO_ENVIRONMENT` matches the credential. A sandbox refresh token against the production API host (or vice versa) will authenticate but return an empty company.

**Slow large date windows** â€” QBO's query endpoint paginates at a hard cap of 1000 rows per page. The client walks pages transparently, but a 5-year invoice scan still means many round-trips. Consider tightening `date_from` / `date_to` or filtering by `status`.

**`Transient QBO error: HTTP 429`** â€” Intuit's rate limiter kicked in. The client retries automatically with exponential backoff; if you see this surface in tool output, you've exceeded the configured `QBO_MAX_RETRIES`. Bump it or slow down your queries.

## Contributing

Issues and pull requests welcome. Please:

- Run `pytest` before opening a PR (`pip install -e ".[dev]"`).
- Run `pre-commit run --all-files`.
- Keep additions to v0.1 scope read-only. Write endpoints land in v0.2.
- Synthetic data only in tests â€” no real customer names, vendor names, or realm IDs.

## License

MIT â€” see [LICENSE](LICENSE).

## Disclaimer

`qbo-mcp` is an unofficial, third-party integration. It is **not endorsed by, affiliated with, or supported by Intuit Inc.** "QuickBooks" and "QuickBooks Online" are trademarks of Intuit Inc. Use at your own risk; verify behavior against your realm before depending on it for production decisions.

