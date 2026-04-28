"""Tests for the QBO HTTP client.

All tests use a mocked `requests.Session`, no live HTTP, no real
credentials. Synthetic fixtures defined in tests/fixtures.py.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from qbo_mcp.client import (
    QBOClient,
    QBOError,
    _balance_clause,
    _escape_qbo_string,
)
from qbo_mcp.config import QBO_TOKEN_URL
from tests.fixtures import (
    SAMPLE_ACCOUNTS_QUERY_PAGE,
    SAMPLE_BILL_QUERY_PAGE,
    SAMPLE_CUSTOMER_GET,
    SAMPLE_CUSTOMER_QUERY_PAGE,
    SAMPLE_INVOICE_GET,
    SAMPLE_INVOICE_QUERY_PAGE_1,
    SAMPLE_INVOICE_QUERY_PAGE_2,
    SAMPLE_TOKEN_RESPONSE,
    SAMPLE_VENDOR_GET,
    SAMPLE_VENDOR_QUERY_PAGE,
    SANDBOX_REALM_ID,
)


def _ok_response(json_body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    resp.json.return_value = json_body
    return resp


def _err_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = False
    resp.json.return_value = {}
    return resp


def _token_post_responder(url, data=None, json=None, headers=None, timeout=None):
    if url == QBO_TOKEN_URL:
        return _ok_response(SAMPLE_TOKEN_RESPONSE)
    raise AssertionError(f"Unexpected POST: {url}")


def _make_client(session: MagicMock, **overrides) -> QBOClient:
    kwargs = dict(
        client_id="cid",
        client_secret="csecret",
        refresh_token="initial-refresh-token",
        realm_id=SANDBOX_REALM_ID,
        api_host="https://sandbox-quickbooks.api.intuit.com",
        token_url=QBO_TOKEN_URL,
        timeout=5,
        max_retries=3,
        session=session,
    )
    kwargs.update(overrides)
    return QBOClient(**kwargs)


# ---- token / auth ------------------------------------------------------


def test_token_acquired_on_first_request():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )

    client = _make_client(session)
    client.search_customers(query="acme")

    # Token POST happened exactly once
    assert session.post.call_count == 1
    # Subsequent call reuses the cached access token
    client.search_customers(query="acme")
    assert session.post.call_count == 1


def test_token_post_uses_basic_auth_header():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )
    client = _make_client(session)
    client.search_customers(query="x")
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["Authorization"].startswith("Basic ")
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == "initial-refresh-token"


def test_token_failure_raises_qbo_error():
    session = MagicMock()
    session.post.return_value = _err_response(401)
    client = _make_client(session)
    with pytest.raises(QBOError, match="Failed to refresh QBO access token"):
        client.search_customers(query="x")


def test_token_response_missing_access_token():
    session = MagicMock()
    session.post.return_value = _ok_response({"expires_in": 3600})
    client = _make_client(session)
    with pytest.raises(QBOError, match="missing 'access_token'"):
        client.search_customers(query="x")


def test_token_endpoint_connection_error_raises():
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("boom")
    client = _make_client(session)
    with pytest.raises(QBOError, match="Failed to reach QBO token endpoint"):
        client.search_customers(query="x")


def test_refresh_token_rotation_invokes_callback():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )
    captured: list[str] = []
    client = _make_client(session, on_refresh_token_rotated=captured.append)
    client.search_customers(query="x")
    assert captured == [SAMPLE_TOKEN_RESPONSE["refresh_token"]]
    assert client.refresh_token == SAMPLE_TOKEN_RESPONSE["refresh_token"]


def test_refresh_token_callback_exception_does_not_break_client(monkeypatch):
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )

    def bad_callback(_token):
        raise RuntimeError("disk full")

    client = _make_client(session, on_refresh_token_rotated=bad_callback)
    # Should not raise, callback exceptions are swallowed and logged.
    client.search_customers(query="x")


def test_401_during_request_refreshes_token_and_retries():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _err_response(401),
        _ok_response(SAMPLE_CUSTOMER_QUERY_PAGE),
    ]
    client = _make_client(session)
    result = client.search_customers(query="acme")
    assert len(result) == 2
    # Initial token + refresh = 2 POSTs
    assert session.post.call_count == 2
    assert session.request.call_count == 2


# ---- error / retry handling -------------------------------------------


def test_500_response_retries_then_raises():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(500)
    client = _make_client(session)
    with pytest.raises(QBOError, match="Transient QBO error"):
        client.search_customers(query="x")
    assert session.request.call_count == 3  # max_retries


def test_429_response_retries():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _err_response(429),
        _ok_response(SAMPLE_CUSTOMER_QUERY_PAGE),
    ]
    client = _make_client(session)
    result = client.search_customers(query="acme")
    assert len(result) == 2


def test_connection_error_retries():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        requests.ConnectionError("boom"),
        _ok_response(SAMPLE_CUSTOMER_QUERY_PAGE),
    ]
    client = _make_client(session)
    result = client.search_customers(query="acme")
    assert len(result) == 2


def test_404_does_not_retry():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    with pytest.raises(QBOError) as exc_info:
        client.search_customers(query="x")
    assert exc_info.value.status_code == 404
    assert session.request.call_count == 1


# ---- customers --------------------------------------------------------


def test_search_customers_passes_query_param():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_CUSTOMER_QUERY_PAGE)
    client = _make_client(session)

    client.search_customers(query="acme", limit=10)

    args, kwargs = session.request.call_args
    assert args[0] == "GET"
    assert args[1].endswith(f"/v3/company/{SANDBOX_REALM_ID}/query")
    statement = kwargs["params"]["query"]
    assert "FROM Customer" in statement
    assert "DisplayName LIKE '%acme%'" in statement
    assert "MAXRESULTS 10" in statement


def test_search_customers_rejects_blank():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="non-empty"):
        client.search_customers(query="   ")


def test_search_customers_escapes_apostrophe():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )
    client = _make_client(session)
    client.search_customers(query="O'Brien")
    statement = session.request.call_args.kwargs["params"]["query"]
    assert "O\\'Brien" in statement


def test_get_customer_returns_record():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_CUSTOMER_GET)
    client = _make_client(session)
    result = client.get_customer("1001")
    assert result is not None
    assert result["Id"] == "1001"
    assert result["DisplayName"] == "Acme Corp"


def test_get_customer_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_customer("99999999") is None


def test_get_customer_blank_id():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="non-empty"):
        client.get_customer("  ")


# ---- vendors ----------------------------------------------------------


def test_search_vendors_returns_records():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_VENDOR_QUERY_PAGE)
    client = _make_client(session)
    out = client.search_vendors(query="widget")
    assert len(out) == 2
    assert out[0]["DisplayName"] == "WidgetCo"


def test_get_vendor_returns_record():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_VENDOR_GET)
    client = _make_client(session)
    result = client.get_vendor("2001")
    assert result is not None
    assert result["Id"] == "2001"


def test_get_vendor_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_vendor("99999999") is None


# ---- invoices ---------------------------------------------------------


def test_search_invoices_returns_records():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVOICE_QUERY_PAGE_1)
    client = _make_client(session)
    out = list(
        client.search_invoices(
            date_from=date(2026, 4, 25),
            date_to=date(2026, 4, 26),
            limit=10,
        )
    )
    assert len(out) == 2
    assert {inv["Id"] for inv in out} == {"5001", "5002"}


def test_paginate_query_walks_full_pages():
    """Cover the STARTPOSITION pagination path directly.

    Page 1 returns exactly `page_size` rows (signals "keep paging"); page 2
    returns fewer than `page_size` (natural terminator). The default
    `_paginate_query` page_size is 100, so we override here to make the
    fixtures meaningful.
    """
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _ok_response(SAMPLE_INVOICE_QUERY_PAGE_1),  # 2 items
        _ok_response(SAMPLE_INVOICE_QUERY_PAGE_2),  # 1 item, terminator
    ]
    client = _make_client(session)

    out = list(
        client._paginate_query(
            select_clause="SELECT * FROM Invoice",
            entity="Invoice",
            where="TxnDate >= '2026-04-25'",
            limit=10,
            page_size=2,
        )
    )
    assert len(out) == 3
    assert {inv["Id"] for inv in out} == {"5001", "5002", "5003"}
    assert session.request.call_count == 2

    # First page used STARTPOSITION 1, second page used STARTPOSITION 3.
    first_stmt = session.request.call_args_list[0].kwargs["params"]["query"]
    second_stmt = session.request.call_args_list[1].kwargs["params"]["query"]
    assert "STARTPOSITION 1" in first_stmt
    assert "STARTPOSITION 3" in second_stmt


def test_paginate_query_respects_limit_mid_page():
    """A `limit` smaller than the page size stops iteration cleanly."""
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVOICE_QUERY_PAGE_1)
    client = _make_client(session)

    out = list(
        client._paginate_query(
            select_clause="SELECT * FROM Invoice",
            entity="Invoice",
            limit=1,
            page_size=10,
        )
    )
    assert len(out) == 1


def test_paginate_query_zero_limit_yields_nothing():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    out = list(
        client._paginate_query(
            select_clause="SELECT * FROM Invoice",
            entity="Invoice",
            limit=0,
        )
    )
    assert out == []
    # No HTTP calls at all.
    assert session.request.call_count == 0


def test_search_invoices_status_open_adds_clause():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVOICE_QUERY_PAGE_2)
    client = _make_client(session)
    list(
        client.search_invoices(
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 26),
            status="open",
        )
    )
    statement = session.request.call_args.kwargs["params"]["query"]
    assert "Balance > '0'" in statement


def test_search_invoices_status_paid_adds_clause():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVOICE_QUERY_PAGE_2)
    client = _make_client(session)
    list(
        client.search_invoices(
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 26),
            status="paid",
        )
    )
    statement = session.request.call_args.kwargs["params"]["query"]
    assert "Balance = '0'" in statement


def test_search_invoices_status_invalid():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="status must be"):
        list(
            client.search_invoices(
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 26),
                status="overdue",
            )
        )


def test_search_invoices_rejects_inverted_range():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="date_from must be <= date_to"):
        list(
            client.search_invoices(
                date_from=date(2026, 4, 26),
                date_to=date(2026, 4, 25),
            )
        )


def test_get_invoice_returns_detail():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_INVOICE_GET)
    client = _make_client(session)
    result = client.get_invoice("5001")
    assert result is not None
    assert result["Id"] == "5001"
    assert len(result["Line"]) == 1


def test_get_invoice_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_invoice("99999999") is None


# ---- bills ------------------------------------------------------------


def test_search_bills_returns_records():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_BILL_QUERY_PAGE)
    client = _make_client(session)
    out = list(
        client.search_bills(
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 26),
        )
    )
    assert len(out) == 2
    assert out[0]["Id"] == "6001"


def test_search_bills_uses_txn_date_window():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_BILL_QUERY_PAGE)
    client = _make_client(session)
    list(
        client.search_bills(
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 26),
        )
    )
    statement = session.request.call_args.kwargs["params"]["query"]
    assert "TxnDate >= '2026-04-01'" in statement
    assert "TxnDate <= '2026-04-26'" in statement


def test_search_bills_rejects_inverted_range():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="date_from must be <= date_to"):
        list(
            client.search_bills(
                date_from=date(2026, 4, 26),
                date_to=date(2026, 4, 25),
            )
        )


# ---- chart of accounts ------------------------------------------------


def test_get_chart_of_accounts_returns_active_accounts():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_ACCOUNTS_QUERY_PAGE)
    client = _make_client(session)
    out = client.get_chart_of_accounts()
    assert len(out) == 3
    assert {a["AccountType"] for a in out} == {
        "Bank",
        "Other Current Asset",
        "Income",
    }
    statement = session.request.call_args.kwargs["params"]["query"]
    assert "Active = true" in statement


# ---- minor version --------------------------------------------------


def test_minor_version_added_to_params():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )
    client = _make_client(session, minor_version=70)
    client.search_customers(query="x")
    params = session.request.call_args.kwargs["params"]
    assert params["minorversion"] == 70


# ---- helpers --------------------------------------------------------


def test_escape_qbo_string_handles_metacharacters():
    assert _escape_qbo_string("O'Brien") == "O\\'Brien"
    assert _escape_qbo_string("a_b") == "a\\_b"
    assert _escape_qbo_string("c\\d") == "c\\\\d"


def test_balance_clause_branches():
    assert _balance_clause(None) is None
    assert _balance_clause("") is None
    assert _balance_clause("open") == "Balance > '0'"
    assert _balance_clause("PAID") == "Balance = '0'"
    with pytest.raises(ValueError):
        _balance_clause("partially-paid")


def test_max_retries_clamped_to_minimum_one():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"QueryResponse": {"Customer": []}}
    )
    client = _make_client(session, max_retries=0)
    # Should still execute once
    client.search_customers(query="x")
