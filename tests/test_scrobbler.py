"""Tests for Last.fm scrobbler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pylast
import pytest

from sonos_lastfm.config import Config
from sonos_lastfm.scrobbler import Scrobbler


@pytest.fixture
def config():
    return Config(
        lastfm_api_key="test-key",
        lastfm_api_secret="test-secret",
        lastfm_session_key="test-session",
    )


@pytest.fixture
def scrobbler(config):
    with patch.object(pylast, "LastFMNetwork") as mock_network_cls:
        mock_network = MagicMock()
        mock_network_cls.return_value = mock_network
        s = Scrobbler(config)
        s.network = mock_network
        yield s


def test_update_now_playing(scrobbler):
    scrobbler.update_now_playing("Artist", "Title", album="Album", duration=200)
    scrobbler.network.update_now_playing.assert_called_once_with(
        artist="Artist",
        title="Title",
        album="Album",
        duration=200,
    )


def test_update_now_playing_network_error(scrobbler):
    scrobbler.network.update_now_playing.side_effect = pylast.NetworkError(
        None, "timeout"
    )
    # Should not raise
    scrobbler.update_now_playing("Artist", "Title")


def test_update_now_playing_ws_error(scrobbler):
    scrobbler.network.update_now_playing.side_effect = pylast.WSError(
        None, "invalid", "details"
    )
    scrobbler.update_now_playing("Artist", "Title")


def test_scrobble(scrobbler):
    scrobbler.scrobble("Artist", "Title", timestamp=1000, album="Album", duration=200)
    scrobbler.network.scrobble.assert_called_once_with(
        artist="Artist",
        title="Title",
        timestamp=1000,
        album="Album",
        duration=200,
    )


def test_scrobble_default_timestamp(scrobbler):
    scrobbler.scrobble("Artist", "Title")
    call_args = scrobbler.network.scrobble.call_args
    assert call_args.kwargs["timestamp"] is not None
    assert isinstance(call_args.kwargs["timestamp"], int)


def test_scrobble_network_error(scrobbler):
    scrobbler.network.scrobble.side_effect = pylast.NetworkError(None, "timeout")
    scrobbler.scrobble("Artist", "Title", timestamp=1000)


def test_scrobble_ws_error(scrobbler):
    scrobbler.network.scrobble.side_effect = pylast.WSError(None, "invalid", "details")
    scrobbler.scrobble("Artist", "Title", timestamp=1000)


def test_get_session_key(scrobbler):
    scrobbler.network.session_key = "abc123"
    assert scrobbler.get_session_key() == "abc123"
