"""Tests for qbo_mcp.config.Settings."""

from __future__ import annotations

import pytest

from qbo_mcp.config import (
    QBO_PRODUCTION_API_HOST,
    QBO_SANDBOX_API_HOST,
    Settings,
)


def _baseline(monkeypatch):
    monkeypatch.setenv("QBO_CLIENT_ID", "cid")
    monkeypatch.setenv("QBO_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("QBO_REFRESH_TOKEN", "rtoken")
    monkeypatch.setenv("QBO_REALM_ID", "9999999999990001")


def test_settings_from_env_happy_path(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("QBO_MINOR_VERSION", "70")
    monkeypatch.setenv("QBO_HTTP_TIMEOUT", "45")
    monkeypatch.setenv("QBO_MAX_RETRIES", "5")

    s = Settings.from_env()
    assert s.client_id == "cid"
    assert s.client_secret == "csecret"
    assert s.refresh_token == "rtoken"
    assert s.realm_id == "9999999999990001"
    assert s.environment == "sandbox"
    assert s.api_host == QBO_SANDBOX_API_HOST
    assert s.minor_version == 70
    assert s.http_timeout == 45
    assert s.max_retries == 5


def test_settings_defaults_to_production(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.delenv("QBO_ENVIRONMENT", raising=False)

    s = Settings.from_env()
    assert s.environment == "production"
    assert s.api_host == QBO_PRODUCTION_API_HOST


def test_settings_environment_is_normalized(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_ENVIRONMENT", "  Sandbox  ")
    s = Settings.from_env()
    assert s.environment == "sandbox"


def test_settings_environment_invalid(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_ENVIRONMENT", "staging")
    with pytest.raises(ValueError, match="QBO_ENVIRONMENT"):
        Settings.from_env()


def test_settings_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("QBO_CLIENT_ID", raising=False)
    monkeypatch.delenv("QBO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("QBO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("QBO_REALM_ID", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        Settings.from_env()


def test_settings_missing_one_credential(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.delenv("QBO_REALM_ID", raising=False)
    with pytest.raises(RuntimeError, match="QBO_REALM_ID"):
        Settings.from_env()


def test_settings_minor_version_blank(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_MINOR_VERSION", "")
    s = Settings.from_env()
    assert s.minor_version is None


def test_settings_minor_version_invalid(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_MINOR_VERSION", "newest")
    with pytest.raises(ValueError, match="QBO_MINOR_VERSION"):
        Settings.from_env()


def test_settings_invalid_int(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.setenv("QBO_HTTP_TIMEOUT", "not-a-number")
    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env()


def test_settings_default_timeout_and_retries(monkeypatch):
    _baseline(monkeypatch)
    monkeypatch.delenv("QBO_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("QBO_MAX_RETRIES", raising=False)

    s = Settings.from_env()
    assert s.http_timeout == 60
    assert s.max_retries == 3
