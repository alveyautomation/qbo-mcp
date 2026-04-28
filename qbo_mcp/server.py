"""MCP server entry point.

Exposes eight read-only tools that wrap the QuickBooks Online Accounting API.
The server uses stdio transport, which is the standard MCP transport for
desktop Claude clients (Claude Code, Claude Desktop, IDE extensions).

Run via `python -m qbo_mcp` or the `qbo-mcp` CLI command.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import QBOClient, QBOError
from .config import QBO_TOKEN_URL, Settings

logger = logging.getLogger(__name__)

mcp = FastMCP("qbo-mcp")

# Lazy singletons. We don't want to require credentials at import time, # the MCP host may launch the server with a degenerate environment for
# capability discovery.
_settings: Settings | None = None
_client: QBOClient | None = None


def _get_client() -> QBOClient:
    global _settings, _client
    if _client is None:
        _settings = Settings.from_env()
        _client = QBOClient(
            client_id=_settings.client_id,
            client_secret=_settings.client_secret,
            refresh_token=_settings.refresh_token,
            realm_id=_settings.realm_id,
            api_host=_settings.api_host,
            token_url=QBO_TOKEN_URL,
            minor_version=_settings.minor_version,
            timeout=_settings.http_timeout,
            max_retries=_settings.max_retries,
        )
    return _client


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=_json_default, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO date (YYYY-MM-DD); got {value!r}"
        ) from exc


# ---- tools -------------------------------------------------------------


@mcp.tool()
def qbo_search_customers(query: str, limit: int = 50) -> str:
    """Search customers by display name (substring, case-insensitive).

    Args:
        query: Free-text fragment matched against Customer.DisplayName
            via QBO's `LIKE '%query%'` operator.
        limit: Cap on returned customers (1-1000, default 50).

    Returns:
        JSON envelope: {"ok": true, "data": {"customers": [...], "count": N}}.
    """
    if not query or not query.strip():
        return _err("query is required and must be non-empty")
    try:
        capped = max(1, min(limit, 1000))
        customers = _get_client().search_customers(query=query.strip(), limit=capped)
        return _ok(
            {
                "customers": customers,
                "count": len(customers),
                "query": query.strip(),
                "limit": capped,
            }
        )
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_get_customer(customer_id: str) -> str:
    """Fetch the full record for a single customer.

    Args:
        customer_id: QBO Customer.Id (string-encoded integer per Intuit's API).

    Returns:
        JSON envelope. `data` is the customer record, or null on 404.
    """
    if not customer_id or not str(customer_id).strip():
        return _err("customer_id is required and must be non-empty")
    try:
        customer = _get_client().get_customer(str(customer_id).strip())
        return _ok(customer)
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_search_vendors(query: str, limit: int = 50) -> str:
    """Search vendors by display name (substring, case-insensitive).

    Args:
        query: Free-text fragment matched against Vendor.DisplayName.
        limit: Cap on returned vendors (1-1000, default 50).

    Returns:
        JSON envelope: {"ok": true, "data": {"vendors": [...], "count": N}}.
    """
    if not query or not query.strip():
        return _err("query is required and must be non-empty")
    try:
        capped = max(1, min(limit, 1000))
        vendors = _get_client().search_vendors(query=query.strip(), limit=capped)
        return _ok(
            {
                "vendors": vendors,
                "count": len(vendors),
                "query": query.strip(),
                "limit": capped,
            }
        )
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_get_vendor(vendor_id: str) -> str:
    """Fetch the full record for a single vendor.

    Args:
        vendor_id: QBO Vendor.Id.

    Returns:
        JSON envelope. `data` is the vendor record, or null on 404.
    """
    if not vendor_id or not str(vendor_id).strip():
        return _err("vendor_id is required and must be non-empty")
    try:
        vendor = _get_client().get_vendor(str(vendor_id).strip())
        return _ok(vendor)
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_search_invoices(
    date_from: str,
    date_to: str,
    status: str | None = None,
    limit: int = 200,
) -> str:
    """Search invoices created in [date_from, date_to] inclusive.

    Args:
        date_from: ISO date (YYYY-MM-DD), start of TxnDate window.
        date_to: ISO date (YYYY-MM-DD), end of TxnDate window.
        status: Optional balance filter. "open" returns invoices with a
            non-zero balance; "paid" returns invoices with Balance == 0.
            Omit (null) for both.
        limit: Cap on yielded invoices (1-2000, default 200).

    Returns:
        JSON envelope. `data.invoices` is the list of invoice records.
    """
    try:
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")
        capped = max(1, min(limit, 2000))
        client = _get_client()
        out: list[dict] = []
        for inv in client.search_invoices(
            date_from=df,
            date_to=dt,
            status=status,
            limit=capped,
        ):
            out.append(inv)
            if len(out) >= capped:
                break
        return _ok(
            {
                "invoices": out,
                "count": len(out),
                "date_from": df.isoformat(),
                "date_to": dt.isoformat(),
                "status": status,
                "limit_reached": len(out) >= capped,
            }
        )
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_get_invoice(invoice_id: str) -> str:
    """Fetch full invoice detail including line items.

    Args:
        invoice_id: QBO Invoice.Id.

    Returns:
        JSON envelope. `data` is the invoice record, or null on 404.
    """
    if not invoice_id or not str(invoice_id).strip():
        return _err("invoice_id is required and must be non-empty")
    try:
        invoice = _get_client().get_invoice(str(invoice_id).strip())
        return _ok(invoice)
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_search_bills(
    date_from: str,
    date_to: str,
    status: str | None = None,
    limit: int = 200,
) -> str:
    """Search vendor bills with TxnDate in [date_from, date_to] inclusive.

    Args:
        date_from: ISO date (YYYY-MM-DD), start of TxnDate window.
        date_to: ISO date (YYYY-MM-DD), end of TxnDate window.
        status: Optional balance filter. "open" returns bills with a
            non-zero balance; "paid" returns bills with Balance == 0.
            Omit (null) for both.
        limit: Cap on yielded bills (1-2000, default 200).

    Returns:
        JSON envelope. `data.bills` is the list of bill records.
    """
    try:
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")
        capped = max(1, min(limit, 2000))
        client = _get_client()
        out: list[dict] = []
        for bill in client.search_bills(
            date_from=df,
            date_to=dt,
            status=status,
            limit=capped,
        ):
            out.append(bill)
            if len(out) >= capped:
                break
        return _ok(
            {
                "bills": out,
                "count": len(out),
                "date_from": df.isoformat(),
                "date_to": dt.isoformat(),
                "status": status,
                "limit_reached": len(out) >= capped,
            }
        )
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def qbo_get_chart_of_accounts() -> str:
    """Return the full chart of accounts (active only).

    Returns:
        JSON envelope. `data.accounts` is the list of account records,
        each carrying `Id`, `Name`, `AccountType`, `AccountSubType`,
        `Classification`, and `CurrentBalance` among other QBO fields.
    """
    try:
        accounts = _get_client().get_chart_of_accounts()
        return _ok({"accounts": accounts, "count": len(accounts)})
    except (ValueError, QBOError, RuntimeError) as exc:
        return _err(str(exc))


def main() -> None:
    """CLI entry point, runs the MCP server over stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
