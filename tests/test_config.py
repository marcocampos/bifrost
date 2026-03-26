"""Tests for configuration loading."""

import pytest

from sonos_lastfm.config import load_config


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    """Prevent load_dotenv from loading .env files during tests."""
    monkeypatch.setattr("sonos_lastfm.config.load_dotenv", lambda: None)


@pytest.fixture
def base_env(monkeypatch):
    """Set minimal required environment variables."""
    monkeypatch.setenv("LASTFM_API_KEY", "test-key")
    monkeypatch.setenv("LASTFM_API_SECRET", "test-secret")
    monkeypatch.setenv("LASTFM_SESSION_KEY", "test-session")
    monkeypatch.delenv("SONOS_SPEAKERS", raising=False)
    monkeypatch.delenv("WEB_PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LASTFM_USERNAME", raising=False)
    monkeypatch.delenv("LASTFM_PASSWORD_HASH", raising=False)


def test_load_config_with_session_key(base_env):
    config = load_config()
    assert config.lastfm_api_key == "test-key"
    assert config.lastfm_api_secret == "test-secret"
    assert config.lastfm_session_key == "test-session"
    assert config.sonos_speakers == []
    assert config.web_port == 8080
    assert config.log_level == "INFO"


def test_load_config_with_username_password(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setenv("LASTFM_API_SECRET", "secret")
    monkeypatch.setenv("LASTFM_USERNAME", "user")
    monkeypatch.setenv("LASTFM_PASSWORD_HASH", "hash")
    monkeypatch.delenv("LASTFM_SESSION_KEY", raising=False)

    config = load_config()
    assert config.lastfm_username == "user"
    assert config.lastfm_password_hash == "hash"


def test_load_config_parses_speakers(base_env, monkeypatch):
    monkeypatch.setenv("SONOS_SPEAKERS", "Living Room, Kitchen , Bedroom")
    config = load_config()
    assert config.sonos_speakers == ["Living Room", "Kitchen", "Bedroom"]


def test_load_config_empty_speakers(base_env):
    config = load_config()
    assert config.sonos_speakers == []


def test_load_config_custom_port(base_env, monkeypatch):
    monkeypatch.setenv("WEB_PORT", "9090")
    config = load_config()
    assert config.web_port == 9090


def test_load_config_missing_api_key(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.delenv("LASTFM_API_SECRET", raising=False)
    monkeypatch.setenv("LASTFM_SESSION_KEY", "session")
    with pytest.raises(SystemExit):
        load_config()


def test_load_config_missing_auth(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setenv("LASTFM_API_SECRET", "secret")
    monkeypatch.delenv("LASTFM_SESSION_KEY", raising=False)
    monkeypatch.delenv("LASTFM_USERNAME", raising=False)
    monkeypatch.delenv("LASTFM_PASSWORD_HASH", raising=False)
    with pytest.raises(SystemExit):
        load_config()


def test_load_config_partial_auth_missing_password(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setenv("LASTFM_API_SECRET", "secret")
    monkeypatch.setenv("LASTFM_USERNAME", "user")
    monkeypatch.delenv("LASTFM_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("LASTFM_SESSION_KEY", raising=False)
    with pytest.raises(SystemExit):
        load_config()
