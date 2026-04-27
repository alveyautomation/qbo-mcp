"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from qbo_mcp.client import QBOClient
from qbo_mcp.config import QBO_TOKEN_URL
from tests.fixtures import SAMPLE_TOKEN_RESPONSE, SANDBOX_REALM_ID


@pytest.fixture(autouse=True)
def _reset_server_singletons():
    """Each test starts with a fresh server-module singleton state.

    The MCP server lazily caches a Settings + QBOClient instance. Reset
    between tests so env-var changes take effect and one test's mock
    client doesn't leak into the next.
    """
    from qbo_mcp import server as srv

    srv._settings = None
    srv._client = None
    yield
    srv._settings = None
    srv._client = None


@pytest.fixture(autouse=True)
def _patch_sleep(monkeypatch):
    """Make retry backoff instant in unit tests."""
    import qbo_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)


@pytest.fixture
def env_credentials(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("QBO_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("QBO_CLIENT_SECRET", "sandbox-client-secret")
    monkeypatch.setenv("QBO_REFRESH_TOKEN", "sandbox-refresh-token")
    monkeypatch.setenv("QBO_REALM_ID", SANDBOX_REALM_ID)
    monkeypatch.setenv("QBO_ENVIRONMENT", "sandbox")
    yield


@pytest.fixture
def mock_session() -> MagicMock:
    """A mocked `requests.Session` that returns canned token + JSON bodies."""
    session = MagicMock()

    def post(url, data=None, json=None, headers=None, timeout=None):
        if url == QBO_TOKEN_URL:
            resp = MagicMock()
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = SAMPLE_TOKEN_RESPONSE
            return resp
        raise AssertionError(f"Unexpected POST: {url}")

    session.post.side_effect = post
    return session


@pytest.fixture
def client(mock_session) -> QBOClient:
    return QBOClient(
        client_id="sandbox-client-id",
        client_secret="sandbox-client-secret",
        refresh_token="sandbox-refresh-token",
        realm_id=SANDBOX_REALM_ID,
        api_host="https://sandbox-quickbooks.api.intuit.com",
        token_url=QBO_TOKEN_URL,
        timeout=10,
        max_retries=2,
        session=mock_session,
    )


def _integration_enabled() -> bool:
    return os.environ.get("QBO_INTEGRATION_TESTS") == "1"


integration_only = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Integration tests require QBO_INTEGRATION_TESTS=1 + valid creds",
)
