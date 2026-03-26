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


def test_get_recent_tracks(scrobbler):
    played1 = MagicMock()
    played1.track.artist = "Artist1"
    played1.track.title = "Title1"
    played1.album = "Album1"
    played1.timestamp = "1700000000"
    played1.track.get_cover_image.return_value = "https://img.com/1.jpg"

    played2 = MagicMock()
    played2.track.artist = "Artist2"
    played2.track.title = "Title2"
    played2.album = None
    played2.timestamp = "1700001000"
    played2.track.get_cover_image.return_value = None

    mock_user = MagicMock()
    mock_user.get_recent_tracks.return_value = [played1, played2]
    scrobbler.network.get_authenticated_user.return_value = mock_user

    result = scrobbler.get_recent_tracks(limit=10)

    assert len(result) == 2
    assert result[0]["artist"] == "Artist1"
    assert result[0]["title"] == "Title1"
    assert result[0]["album"] == "Album1"
    assert result[0]["timestamp"] == 1700000000
    assert result[0]["album_art_url"] == "https://img.com/1.jpg"
    assert result[1]["album"] is None


def test_get_recent_tracks_network_error(scrobbler):
    scrobbler.network.get_authenticated_user.side_effect = pylast.NetworkError(
        None, "timeout"
    )
    result = scrobbler.get_recent_tracks()
    assert result == []


def test_get_session_key(scrobbler):
    scrobbler.network.session_key = "abc123"
    assert scrobbler.get_session_key() == "abc123"
