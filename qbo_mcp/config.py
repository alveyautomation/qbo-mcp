"""Configuration for the QuickBooks Online MCP server.

All settings come from environment variables. Nothing is persisted to disk
and nothing is logged. See `.env.example` for the full list of supported
variables.

QBO OAuth 2.0 requires four pieces of state:
  - `client_id` and `client_secret` from the Intuit Developer app registration
  - a long-lived `refresh_token` obtained once via the OAuth authorize flow
  - a `realm_id` (a.k.a. CompanyID) that scopes every API call to one company

The server uses the refresh token to mint short-lived access tokens at runtime;
the refresh token itself rotates on every refresh, but the rotation is a
deployment concern, not a server concern. See README for the one-time setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


_VALID_ENVIRONMENTS = frozenset({"production", "sandbox"})


def _environment(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value not in _VALID_ENVIRONMENTS:
        raise ValueError(
            f"Environment variable {name} must be one of "
            f"{sorted(_VALID_ENVIRONMENTS)}; got {raw!r}"
        )
    return value


# Intuit's published API hosts. The OAuth token endpoint is environment-
# independent; only the API host changes between sandbox and production.
QBO_PRODUCTION_API_HOST = "https://quickbooks.api.intuit.com"
QBO_SANDBOX_API_HOST = "https://sandbox-quickbooks.api.intuit.com"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the MCP server."""

    client_id: str
    client_secret: str
    refresh_token: str
    realm_id: str
    environment: str
    minor_version: int | None
    http_timeout: int
    max_retries: int

    @property
    def api_host(self) -> str:
        """Base URL for QBO Accounting API calls (no trailing slash)."""
        return (
            QBO_PRODUCTION_API_HOST
            if self.environment == "production"
            else QBO_SANDBOX_API_HOST
        )

    @classmethod
    def from_env(cls) -> Settings:
        client_id = _str("QBO_CLIENT_ID")
        client_secret = _str("QBO_CLIENT_SECRET")
        refresh_token = _str("QBO_REFRESH_TOKEN")
        realm_id = _str("QBO_REALM_ID")

        missing = [
            name
            for name, value in [
                ("QBO_CLIENT_ID", client_id),
                ("QBO_CLIENT_SECRET", client_secret),
                ("QBO_REFRESH_TOKEN", refresh_token),
                ("QBO_REALM_ID", realm_id),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". See .env.example for the full list."
            )

        environment = _environment("QBO_ENVIRONMENT", "production")

        minor_version_raw = os.environ.get("QBO_MINOR_VERSION")
        if minor_version_raw is None or minor_version_raw.strip() == "":
            minor_version: int | None = None
        else:
            try:
                minor_version = int(minor_version_raw)
            except ValueError as exc:
                raise ValueError(
                    "Environment variable QBO_MINOR_VERSION must be an integer"
                ) from exc

        return cls(
            client_id=client_id,  # type: ignore[arg-type]
            client_secret=client_secret,  # type: ignore[arg-type]
            refresh_token=refresh_token,  # type: ignore[arg-type]
            realm_id=realm_id,  # type: ignore[arg-type]
            environment=environment,
            minor_version=minor_version,
            http_timeout=_int("QBO_HTTP_TIMEOUT", 60),
            max_retries=_int("QBO_MAX_RETRIES", 3),
        )
