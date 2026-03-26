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

    played2 = MagicMock()
    played2.track.artist = "Artist2"
    played2.track.title = "Title2"
    played2.album = None
    played2.timestamp = "1700001000"

    mock_user = MagicMock()
    mock_user.get_recent_tracks.return_value = [played1, played2]
    scrobbler.network.get_authenticated_user.return_value = mock_user

    result = scrobbler.get_recent_tracks(limit=10)

    assert len(result) == 2
    assert result[0]["artist"] == "Artist1"
    assert result[0]["title"] == "Title1"
    assert result[0]["album"] == "Album1"
    assert result[0]["timestamp"] == 1700000000
    assert result[1]["album"] is None


def test_get_recent_tracks_network_error(scrobbler):
    scrobbler.network.get_authenticated_user.side_effect = pylast.NetworkError(
        None, "timeout"
    )
    result = scrobbler.get_recent_tracks()
    assert result == []


def test_get_stats(scrobbler):
    mock_user = MagicMock()

    artist_item = MagicMock()
    artist_item.__str__ = lambda self: "Radiohead"
    mock_user.get_top_artists.return_value = [MagicMock(item=artist_item, weight=42)]

    album_item = MagicMock()
    album_item.title = "OK Computer"
    album_item.artist = "Radiohead"
    mock_user.get_top_albums.return_value = [MagicMock(item=album_item, weight=15)]

    track_item = MagicMock()
    track_item.title = "Paranoid Android"
    track_item.artist = "Radiohead"
    mock_user.get_top_tracks.return_value = [MagicMock(item=track_item, weight=8)]

    mock_user.get_playcount.return_value = 12345
    scrobbler.network.get_authenticated_user.return_value = mock_user

    result = scrobbler.get_stats(period="7day", limit=10)

    assert result["period"] == "7day"
    assert result["total_scrobbles"] == 12345
    assert len(result["top_artists"]) == 1
    assert result["top_artists"][0]["name"] == "Radiohead"
    assert result["top_artists"][0]["plays"] == 42
    assert result["top_albums"][0]["name"] == "OK Computer"
    assert result["top_tracks"][0]["name"] == "Paranoid Android"


def test_get_stats_invalid_period(scrobbler):
    mock_user = MagicMock()
    mock_user.get_top_artists.return_value = []
    mock_user.get_top_albums.return_value = []
    mock_user.get_top_tracks.return_value = []
    mock_user.get_playcount.return_value = 0
    scrobbler.network.get_authenticated_user.return_value = mock_user

    result = scrobbler.get_stats(period="invalid")
    assert result["period"] == "7day"


def test_get_stats_network_error(scrobbler):
    scrobbler.network.get_authenticated_user.side_effect = pylast.NetworkError(
        None, "timeout"
    )
    result = scrobbler.get_stats()
    assert result["total_scrobbles"] == 0
    assert result["top_artists"] == []


def test_get_session_key(scrobbler):
    scrobbler.network.session_key = "abc123"
    assert scrobbler.get_session_key() == "abc123"
