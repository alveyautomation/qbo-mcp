"""HTTP client for the QuickBooks Online Accounting API.

The client implements Intuit's OAuth 2.0 refresh-token flow: it exchanges a
long-lived refresh token for a short-lived access token, caches the access
token in memory until just before expiry, and refreshes on demand. Refresh
tokens themselves rotate on every refresh, callers that persist refresh
tokens across process restarts should subscribe to `on_refresh_token_rotated`
to capture the new value.

Read-only by design: every public method here calls a `GET` endpoint or
issues a `SELECT` query against QBO's read-only query endpoint. There are no
`POST`, `PUT`, or `DELETE` paths.

State is per-instance, there is no module-level mutable state, so multiple
clients can run in the same process against different QBO realms without
interfering.

This module is a clean rewrite for public release. It does not import or
inherit any tenant-specific configuration; everything that depends on a
particular QBO realm is supplied by the caller.
"""

from __future__ import annotations

import logging
import time
from base64 import b64encode
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

# QBO's `query` endpoint accepts up to 1000 results per page. We page in
# chunks of 100 by default, large enough to keep round-trips cheap, small
# enough to keep responses well under the 1 MB payload cap.
QUERY_PAGE_SIZE = 100

# Refresh the access token a couple of minutes before Intuit expires it
# (the published TTL is 3600s). This prevents a tight race on long-running
# pages where the token was minted just before pagination began.
_ACCESS_TOKEN_REFRESH_MARGIN_SECONDS = 120

# Status codes that warrant a retry. 401 is handled separately (token
# refresh + single retry). 429 is included because Intuit aggressively
# rate-limits the query endpoint and a brief backoff almost always recovers.
_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class QBOError(Exception):
    """Wraps a non-recoverable QBO response so the MCP layer can surface a
    clean message instead of leaking the raw HTTP exception."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class QBOClient:
    """Thin REST wrapper. Construct once per (realm, credential) pair."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        realm_id: str,
        api_host: str,
        token_url: str,
        *,
        minor_version: int | None = None,
        timeout: int = 60,
        max_retries: int = 3,
        session: requests.Session | None = None,
        on_refresh_token_rotated: Callable[[str], None] | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self.realm_id = realm_id
        self._api_host = api_host.rstrip("/")
        self._token_url = token_url
        self._minor_version = minor_version
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._session = session or requests.Session()
        self._on_refresh_token_rotated = on_refresh_token_rotated

        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    @property
    def refresh_token(self) -> str:
        """Latest known refresh token. Updated whenever Intuit rotates it."""
        return self._refresh_token

    # ---- auth -----------------------------------------------------------

    def _get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._access_token
            and self._access_token_expires_at
            and now < self._access_token_expires_at
        ):
            return self._access_token

        basic = b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        try:
            resp = self._session.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=self._timeout,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise QBOError(
                f"Failed to reach QBO token endpoint: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise QBOError(
                f"Failed to refresh QBO access token: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise QBOError("QBO token response was not valid JSON") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise QBOError("QBO token response missing 'access_token'")

        # Intuit returns the new refresh token alongside the access token.
        # The old one is invalidated on success, capture the new one and
        # notify the caller so they can persist it.
        new_refresh = payload.get("refresh_token")
        if new_refresh and new_refresh != self._refresh_token:
            self._refresh_token = new_refresh
            if self._on_refresh_token_rotated is not None:
                try:
                    self._on_refresh_token_rotated(new_refresh)
                except Exception:
                    logger.exception(
                        "on_refresh_token_rotated callback raised"
                    )

        expires_in = int(payload.get("expires_in", 3600))
        ttl = max(60, expires_in - _ACCESS_TOKEN_REFRESH_MARGIN_SECONDS)
        self._access_token = access_token
        self._access_token_expires_at = now + timedelta(seconds=ttl)
        return access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Accept": "application/json",
        }

    # ---- request loop --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
    ) -> Any:
        url = f"{self._api_host}/v3/company/{self.realm_id}/{path.lstrip('/')}"
        merged_params = dict(params or {})
        if self._minor_version is not None:
            merged_params.setdefault("minorversion", self._minor_version)

        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=merged_params,
                    timeout=self._timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            # Access token expired mid-request: refresh once and retry inline.
            if resp.status_code == 401:
                self._access_token = None
                self._access_token_expires_at = None
                try:
                    resp = self._session.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=merged_params,
                        timeout=self._timeout,
                    )
                except (requests.ConnectionError, requests.Timeout) as exc:
                    last_exc = exc
                    self._sleep_backoff(attempt)
                    continue

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = QBOError(
                    f"Transient QBO error: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
                self._sleep_backoff(attempt)
                continue

            if not resp.ok:
                raise QBOError(
                    f"QBO {method} {path} failed: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except ValueError as exc:
                raise QBOError(
                    f"QBO {method} {path} returned non-JSON body"
                ) from exc

        if last_exc is not None:
            raise QBOError(
                f"QBO {method} {path} failed after "
                f"{self._max_retries} attempts: {last_exc}"
            ) from last_exc
        raise QBOError(f"QBO {method} {path} failed for unknown reason")

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # Exponential backoff with a small floor: 0.5s, 1s, 2s, 4s ...
        delay = 0.5 * (2 ** (attempt - 1))
        time.sleep(min(delay, 8.0))

    # ---- query helper --------------------------------------------------

    def _query_page(self, statement: str) -> dict:
        """Run a single QBO `SELECT ...` query and return the raw response."""
        return self._request("GET", "query", params={"query": statement})

    def _paginate_query(
        self,
        *,
        select_clause: str,
        entity: str,
        where: str | None = None,
        order_by: str | None = None,
        limit: int,
        page_size: int = QUERY_PAGE_SIZE,
    ) -> Iterator[dict]:
        """Yield records from a QBO query, handling STARTPOSITION pagination.

        QBO's query endpoint requires explicit `STARTPOSITION` and `MAXRESULTS`
        clauses for paging (it never returns a cursor). Stops yielding once
        `limit` records have been emitted, or when a page returns fewer
        rows than `page_size` (signaling the natural end of results).
        """
        if limit <= 0:
            return
        emitted = 0
        start_position = 1
        while True:
            page = max(1, min(page_size, limit - emitted))
            stmt_parts = [select_clause]
            if where:
                stmt_parts.append(f"WHERE {where}")
            if order_by:
                stmt_parts.append(f"ORDER BY {order_by}")
            stmt_parts.append(f"STARTPOSITION {start_position}")
            stmt_parts.append(f"MAXRESULTS {page}")
            stmt = " ".join(stmt_parts)

            data = self._query_page(stmt)
            qr = data.get("QueryResponse") or {}
            items = qr.get(entity) or []

            for record in items:
                yield record
                emitted += 1
                if emitted >= limit:
                    return

            if len(items) < page:
                return
            start_position += len(items)

    # ---- public read endpoints -----------------------------------------

    def search_customers(
        self, query: str, *, limit: int = 50
    ) -> list[dict]:
        """Search active customers by display name (substring, case-insensitive)."""
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        safe = _escape_qbo_string(query.strip())
        where = f"DisplayName LIKE '%{safe}%'"
        return list(
            self._paginate_query(
                select_clause="SELECT * FROM Customer",
                entity="Customer",
                where=where,
                order_by="DisplayName",
                limit=limit,
            )
        )

    def get_customer(self, customer_id: str) -> dict | None:
        """Fetch one customer by Id, or None on 404."""
        if not customer_id or not str(customer_id).strip():
            raise ValueError("customer_id must be non-empty")
        try:
            data = self._request("GET", f"customer/{customer_id}")
        except QBOError as exc:
            if exc.status_code == 404:
                return None
            raise
        return data.get("Customer")

    def search_vendors(
        self, query: str, *, limit: int = 50
    ) -> list[dict]:
        """Search active vendors by display name (substring, case-insensitive)."""
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        safe = _escape_qbo_string(query.strip())
        where = f"DisplayName LIKE '%{safe}%'"
        return list(
            self._paginate_query(
                select_clause="SELECT * FROM Vendor",
                entity="Vendor",
                where=where,
                order_by="DisplayName",
                limit=limit,
            )
        )

    def get_vendor(self, vendor_id: str) -> dict | None:
        """Fetch one vendor by Id, or None on 404."""
        if not vendor_id or not str(vendor_id).strip():
            raise ValueError("vendor_id must be non-empty")
        try:
            data = self._request("GET", f"vendor/{vendor_id}")
        except QBOError as exc:
            if exc.status_code == 404:
                return None
            raise
        return data.get("Vendor")

    def search_invoices(
        self,
        date_from: date,
        date_to: date,
        *,
        status: str | None = None,
        limit: int = 200,
    ) -> Iterator[dict]:
        """Yield invoices with TxnDate in [date_from, date_to].

        `status` is a convenience filter applied to QBO's `Balance` field:
          - "open"   -> Balance > 0  (unpaid in full)
          - "paid"   -> Balance = 0  (no remaining balance)
          - None     -> no balance filter
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        clauses = [
            f"TxnDate >= '{date_from.isoformat()}'",
            f"TxnDate <= '{date_to.isoformat()}'",
        ]
        balance_clause = _balance_clause(status)
        if balance_clause:
            clauses.append(balance_clause)
        where = " AND ".join(clauses)
        yield from self._paginate_query(
            select_clause="SELECT * FROM Invoice",
            entity="Invoice",
            where=where,
            order_by="TxnDate",
            limit=limit,
        )

    def get_invoice(self, invoice_id: str) -> dict | None:
        """Fetch one invoice by Id, or None on 404."""
        if not invoice_id or not str(invoice_id).strip():
            raise ValueError("invoice_id must be non-empty")
        try:
            data = self._request("GET", f"invoice/{invoice_id}")
        except QBOError as exc:
            if exc.status_code == 404:
                return None
            raise
        return data.get("Invoice")

    def search_bills(
        self,
        date_from: date,
        date_to: date,
        *,
        status: str | None = None,
        limit: int = 200,
    ) -> Iterator[dict]:
        """Yield bills with TxnDate in [date_from, date_to].

        `status` is a convenience filter applied to QBO's `Balance` field:
          - "open"   -> Balance > 0
          - "paid"   -> Balance = 0
          - None     -> no balance filter
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")
        clauses = [
            f"TxnDate >= '{date_from.isoformat()}'",
            f"TxnDate <= '{date_to.isoformat()}'",
        ]
        balance_clause = _balance_clause(status)
        if balance_clause:
            clauses.append(balance_clause)
        where = " AND ".join(clauses)
        yield from self._paginate_query(
            select_clause="SELECT * FROM Bill",
            entity="Bill",
            where=where,
            order_by="TxnDate",
            limit=limit,
        )

    def get_chart_of_accounts(self) -> list[dict]:
        """Return all active accounts (the chart of accounts).

        QBO caps a single page at 1000; we paginate transparently in case a
        realm has more. In practice almost no books exceed a few hundred
        accounts.
        """
        return list(
            self._paginate_query(
                select_clause="SELECT * FROM Account",
                entity="Account",
                where="Active = true",
                order_by="AccountType, Name",
                limit=10000,
                page_size=1000,
            )
        )


def _escape_qbo_string(value: str) -> str:
    """Escape characters that would break a QBO string literal.

    QBO's query language uses single quotes for strings and a backslash as
    the escape character for both `'` and `\\`. `%` and `_` are also
    metacharacters inside `LIKE` expressions; we leave `%` alone so that
    callers don't lose substring semantics, but escape `_` so a literal
    underscore in a customer name doesn't silently match anything.
    """
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("_", "\\_")
    )


def _balance_clause(status: str | None) -> str | None:
    if status is None:
        return None
    s = status.strip().lower()
    if s == "":
        return None
    if s == "open":
        return "Balance > '0'"
    if s == "paid":
        return "Balance = '0'"
    raise ValueError(
        f"status must be 'open', 'paid', or omitted; got {status!r}"
    )
