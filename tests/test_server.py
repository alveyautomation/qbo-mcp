"""Tests for the MCP server tool layer.

We exercise the tool functions directly (their underlying Python callable)
to avoid spinning up a real MCP transport in unit tests. The functions
return JSON-encoded envelopes; we decode and assert on shape.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from qbo_mcp import server as srv
from tests.fixtures import (
    SAMPLE_ACCOUNTS,
    SAMPLE_BILL,
    SAMPLE_CUSTOMER,
    SAMPLE_INVOICE,
    SAMPLE_VENDOR,
)


def _call(tool, **kwargs):
    """Invoke a FastMCP-registered tool's underlying Python function."""
    func = getattr(tool, "fn", None) or tool
    return func(**kwargs)


def _decode(envelope: str) -> dict:
    return json.loads(envelope)


def _install_fake_client(monkeypatch, **methods):
    """Replace the lazy-instantiated client with a MagicMock."""
    fake = MagicMock()
    for name, value in methods.items():
        if callable(value) and not isinstance(value, MagicMock):
            getattr(fake, name).side_effect = value
        else:
            getattr(fake, name).return_value = value
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    return fake


# ---- search_customers --------------------------------------------------


def test_search_customers_happy(monkeypatch):
    _install_fake_client(monkeypatch, search_customers=[SAMPLE_CUSTOMER])
    out = _decode(_call(srv.qbo_search_customers, query="acme"))
    assert out["ok"] is True
    assert out["data"]["count"] == 1
    assert out["data"]["customers"][0]["DisplayName"] == "Acme Corp"


def test_search_customers_rejects_blank_query(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.qbo_search_customers, query="   "))
    assert out["ok"] is False
    assert "query is required" in out["error"]


def test_search_customers_clamps_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_customers=[])
    _call(srv.qbo_search_customers, query="x", limit=99999)
    assert fake.search_customers.call_args.kwargs["limit"] == 1000


def test_search_customers_propagates_client_error(monkeypatch):
    from qbo_mcp.client import QBOError

    fake = MagicMock()
    fake.search_customers.side_effect = QBOError("boom", status_code=500)
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    out = _decode(_call(srv.qbo_search_customers, query="x"))
    assert out["ok"] is False
    assert "boom" in out["error"]


# ---- get_customer ------------------------------------------------------


def test_get_customer_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_customer=SAMPLE_CUSTOMER)
    out = _decode(_call(srv.qbo_get_customer, customer_id="1001"))
    assert out["ok"] is True
    assert out["data"]["Id"] == "1001"


def test_get_customer_missing_returns_null(monkeypatch):
    _install_fake_client(monkeypatch, get_customer=None)
    out = _decode(_call(srv.qbo_get_customer, customer_id="9999"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_customer_blank_id(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.qbo_get_customer, customer_id="  "))
    assert out["ok"] is False


# ---- search_vendors ----------------------------------------------------


def test_search_vendors_happy(monkeypatch):
    _install_fake_client(monkeypatch, search_vendors=[SAMPLE_VENDOR])
    out = _decode(_call(srv.qbo_search_vendors, query="widget"))
    assert out["ok"] is True
    assert out["data"]["count"] == 1
    assert out["data"]["vendors"][0]["DisplayName"] == "WidgetCo"


def test_search_vendors_blank(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.qbo_search_vendors, query=""))
    assert out["ok"] is False


# ---- get_vendor --------------------------------------------------------


def test_get_vendor_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_vendor=SAMPLE_VENDOR)
    out = _decode(_call(srv.qbo_get_vendor, vendor_id="2001"))
    assert out["ok"] is True
    assert out["data"]["Id"] == "2001"


def test_get_vendor_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_vendor=None)
    out = _decode(_call(srv.qbo_get_vendor, vendor_id="9999"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_vendor_blank(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.qbo_get_vendor, vendor_id=""))
    assert out["ok"] is False


# ---- search_invoices ---------------------------------------------------


def test_search_invoices_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_invoices.return_value = iter(
        [SAMPLE_INVOICE, {"Id": "5002", "TotalAmt": 50.00, "Balance": 0.00}]
    )
    out = _decode(
        _call(
            srv.qbo_search_invoices,
            date_from="2026-04-25",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 2
    assert out["data"]["invoices"][0]["Id"] == "5001"
    assert out["data"]["status"] is None


def test_search_invoices_passes_status(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_invoices.return_value = iter([])
    _decode(
        _call(
            srv.qbo_search_invoices,
            date_from="2026-04-01",
            date_to="2026-04-26",
            status="open",
        )
    )
    assert fake.search_invoices.call_args.kwargs["status"] == "open"


def test_search_invoices_rejects_bad_date(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(
            srv.qbo_search_invoices,
            date_from="not-a-date",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is False
    assert "ISO date" in out["error"]


def test_search_invoices_respects_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_invoices.return_value = iter(
        [SAMPLE_INVOICE, {"Id": "5002"}, {"Id": "5003"}]
    )
    out = _decode(
        _call(
            srv.qbo_search_invoices,
            date_from="2026-04-25",
            date_to="2026-04-26",
            limit=2,
        )
    )
    assert out["data"]["count"] == 2
    assert out["data"]["limit_reached"] is True


# ---- get_invoice -------------------------------------------------------


def test_get_invoice_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_invoice=SAMPLE_INVOICE)
    out = _decode(_call(srv.qbo_get_invoice, invoice_id="5001"))
    assert out["ok"] is True
    assert out["data"]["Id"] == "5001"


def test_get_invoice_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_invoice=None)
    out = _decode(_call(srv.qbo_get_invoice, invoice_id="9999"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_invoice_blank(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.qbo_get_invoice, invoice_id=""))
    assert out["ok"] is False


# ---- search_bills ------------------------------------------------------


def test_search_bills_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_bills.return_value = iter([SAMPLE_BILL])
    out = _decode(
        _call(
            srv.qbo_search_bills,
            date_from="2026-04-01",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 1
    assert out["data"]["bills"][0]["Id"] == "6001"


def test_search_bills_status_paid(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_bills.return_value = iter([])
    _decode(
        _call(
            srv.qbo_search_bills,
            date_from="2026-04-01",
            date_to="2026-04-26",
            status="paid",
        )
    )
    assert fake.search_bills.call_args.kwargs["status"] == "paid"


def test_search_bills_bad_date(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(
            srv.qbo_search_bills,
            date_from="2026-04-01",
            date_to="garbage",
        )
    )
    assert out["ok"] is False


# ---- get_chart_of_accounts --------------------------------------------


def test_get_chart_of_accounts_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_chart_of_accounts=SAMPLE_ACCOUNTS)
    out = _decode(_call(srv.qbo_get_chart_of_accounts))
    assert out["ok"] is True
    assert out["data"]["count"] == 3
    assert out["data"]["accounts"][0]["AccountType"] == "Bank"


def test_get_chart_of_accounts_propagates_error(monkeypatch):
    from qbo_mcp.client import QBOError

    fake = MagicMock()
    fake.get_chart_of_accounts.side_effect = QBOError("token expired", status_code=401)
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    out = _decode(_call(srv.qbo_get_chart_of_accounts))
    assert out["ok"] is False
    assert "token expired" in out["error"]


# ---- env-driven init --------------------------------------------------


def test_get_client_initializes_settings_and_client(env_credentials, monkeypatch):
    """End-to-end lazy init: Settings reads env, QBOClient is constructed."""
    # Don't actually let it make HTTP calls, just verify init wiring.
    out = srv._get_client()
    assert out is not None
    assert srv._settings is not None
    assert srv._settings.environment == "sandbox"
    assert out.realm_id == srv._settings.realm_id
