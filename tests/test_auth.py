"""Tests for the authentication helper."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pylast
import pytest

from sonos_lastfm.auth import run_auth


@patch("sonos_lastfm.auth.getpass.getpass", return_value="mypassword")
@patch("builtins.input", side_effect=["api-key", "api-secret", "username"])
@patch("sonos_lastfm.auth.pylast.LastFMNetwork")
def test_successful_auth(mock_network_cls, mock_input, mock_getpass, capsys):
    mock_network = MagicMock()
    mock_network.session_key = "session-123"
    mock_network_cls.return_value = mock_network

    run_auth()

    mock_network_cls.assert_called_once_with(
        api_key="api-key",
        api_secret="api-secret",
        username="username",
        password_hash=hashlib.md5(b"mypassword").hexdigest(),
    )

    output = capsys.readouterr().out
    assert "LASTFM_API_KEY=api-key" in output
    assert "LASTFM_API_SECRET=api-secret" in output
    assert "LASTFM_USERNAME=username" in output
    assert "LASTFM_PASSWORD_HASH=" in output
    assert "LASTFM_SESSION_KEY=session-123" in output


@patch("sonos_lastfm.auth.getpass.getpass", return_value="mypassword")
@patch("builtins.input", side_effect=["api-key", "api-secret", "username"])
@patch("sonos_lastfm.auth.pylast.LastFMNetwork")
def test_auth_network_error(mock_network_cls, mock_input, mock_getpass):
    mock_network_cls.side_effect = pylast.NetworkError(None, "timeout")
    with pytest.raises(SystemExit):
        run_auth()


@patch("sonos_lastfm.auth.getpass.getpass", return_value="mypassword")
@patch("builtins.input", side_effect=["", "api-secret", "username"])
def test_auth_missing_api_key(mock_input, mock_getpass):
    with pytest.raises(SystemExit):
        run_auth()


@patch("sonos_lastfm.auth.getpass.getpass", return_value="")
@patch("builtins.input", side_effect=["api-key", "api-secret", "username"])
def test_auth_missing_password(mock_input, mock_getpass):
    with pytest.raises(SystemExit):
        run_auth()


@patch("sonos_lastfm.auth.getpass.getpass", return_value="pass")
@patch("builtins.input", side_effect=["api-key", "api-secret", ""])
def test_auth_missing_username(mock_input, mock_getpass):
    with pytest.raises(SystemExit):
        run_auth()
