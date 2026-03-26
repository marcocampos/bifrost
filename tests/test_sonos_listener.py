"""Tests for Sonos listener utilities and event parsing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sonos_lastfm.config import Config
from sonos_lastfm.sonos_listener import (
    SonosListener,
    get_album_art_url,
    parse_duration,
)
from sonos_lastfm.track_state import TrackStateManager


class TestParseDuration:
    def test_standard_format(self):
        assert parse_duration("0:03:45") == 225

    def test_hours(self):
        assert parse_duration("1:00:00") == 3600

    def test_minutes_seconds(self):
        assert parse_duration("03:45") == 225

    def test_seconds_only(self):
        assert parse_duration("45") == 45

    def test_empty(self):
        assert parse_duration("") == 0

    def test_not_implemented(self):
        assert parse_duration("NOT_IMPLEMENTED") == 0

    def test_invalid(self):
        assert parse_duration("invalid") == 0

    def test_none(self):
        assert parse_duration(None) == 0


class TestGetAlbumArtUrl:
    def test_absolute_url(self):
        speaker = MagicMock()
        meta = SimpleNamespace(album_art_uri="https://example.com/art.jpg")
        assert get_album_art_url(speaker, meta) == "https://example.com/art.jpg"

    def test_relative_url(self):
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.100"
        meta = SimpleNamespace(album_art_uri="/getaa?s=1&u=some-uri")
        assert get_album_art_url(speaker, meta) == "http://192.168.1.100:1400/getaa?s=1&u=some-uri"

    def test_no_art(self):
        speaker = MagicMock()
        meta = SimpleNamespace(album_art_uri="")
        assert get_album_art_url(speaker, meta) is None

    def test_no_meta(self):
        speaker = MagicMock()
        assert get_album_art_url(speaker, None) is None

    def test_no_attribute(self):
        speaker = MagicMock()
        meta = SimpleNamespace()
        assert get_album_art_url(speaker, meta) is None


class TestParseEvent:
    @pytest.fixture
    def listener(self):
        config = Config(
            lastfm_api_key="key",
            lastfm_api_secret="secret",
            lastfm_session_key="session",
        )
        scrobbler = MagicMock()
        state_manager = TrackStateManager()
        listener = SonosListener(config, scrobbler, state_manager)
        # Simulate a known speaker
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"
        speaker.player_name = "Living Room"
        listener._speakers["192.168.1.10"] = speaker
        return listener

    def test_parse_playing_event(self, listener):
        resource = SimpleNamespace(uri="x-sonos://track1")
        meta = SimpleNamespace(
            title="Song Title",
            creator="Artist Name",
            album="Album Name",
            album_art_uri="/getaa?s=1",
            resources=[resource],
        )
        event = MagicMock()
        event.variables = {
            "transport_state": "PLAYING",
            "current_track_meta_data": meta,
            "current_track_duration": "0:03:30",
        }
        state, track = listener._parse_event("192.168.1.10", event)
        assert state == "PLAYING"
        assert track is not None
        assert track.title == "Song Title"
        assert track.artist == "Artist Name"
        assert track.album == "Album Name"
        assert track.duration_seconds == 210
        assert track.uri == "x-sonos://track1"
        assert "192.168.1.10" in track.album_art_url

    def test_parse_event_string_metadata(self, listener):
        event = MagicMock()
        event.variables = {
            "transport_state": "STOPPED",
            "current_track_meta_data": "",
        }
        state, track = listener._parse_event("192.168.1.10", event)
        assert state == "STOPPED"
        assert track is None

    def test_parse_event_no_metadata(self, listener):
        event = MagicMock()
        event.variables = {
            "transport_state": "PAUSED_PLAYBACK",
        }
        state, track = listener._parse_event("192.168.1.10", event)
        assert state == "PAUSED_PLAYBACK"
        assert track is None


class TestDiscoverSpeakers:
    def test_filters_to_coordinators(self):
        config = Config(
            lastfm_api_key="key",
            lastfm_api_secret="secret",
            lastfm_session_key="session",
        )

        coordinator = MagicMock()
        coordinator.ip_address = "192.168.1.10"
        coordinator.player_name = "Living Room"
        coordinator.group.coordinator.ip_address = "192.168.1.10"

        member = MagicMock()
        member.ip_address = "192.168.1.11"
        member.player_name = "Kitchen"
        member.group.coordinator.ip_address = "192.168.1.10"

        with patch("soco.discover", return_value={coordinator, member}):
            listener = SonosListener(config, MagicMock(), TrackStateManager())
            speakers = listener.discover_speakers()
            ips = [s.ip_address for s in speakers]
            assert "192.168.1.10" in ips
            assert "192.168.1.11" not in ips

    def test_filters_by_name(self):
        config = Config(
            lastfm_api_key="key",
            lastfm_api_secret="secret",
            lastfm_session_key="session",
            sonos_speakers=["Kitchen"],
        )

        living = MagicMock()
        living.ip_address = "192.168.1.10"
        living.player_name = "Living Room"
        living.group.coordinator.ip_address = "192.168.1.10"

        kitchen = MagicMock()
        kitchen.ip_address = "192.168.1.11"
        kitchen.player_name = "Kitchen"
        kitchen.group.coordinator.ip_address = "192.168.1.11"

        with patch("soco.discover", return_value={living, kitchen}):
            listener = SonosListener(config, MagicMock(), TrackStateManager())
            speakers = listener.discover_speakers()
            assert len(speakers) == 1
            assert speakers[0].player_name == "Kitchen"

    def test_no_speakers_found(self):
        config = Config(
            lastfm_api_key="key",
            lastfm_api_secret="secret",
            lastfm_session_key="session",
        )
        with patch("soco.discover", return_value=None):
            listener = SonosListener(config, MagicMock(), TrackStateManager())
            assert listener.discover_speakers() == []
