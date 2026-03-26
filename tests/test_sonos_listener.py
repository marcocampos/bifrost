"""Tests for Sonos listener utilities and event parsing."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bifrost.config import Config
from bifrost.sonos_listener import (
    SonosListener,
    get_album_art_url,
    parse_duration,
)
from bifrost.track_state import Action, ActionType, TrackInfo, TrackStateManager


def _make_config(**kwargs):
    defaults = dict(lastfm_api_key="key", lastfm_api_secret="secret", lastfm_session_key="session")
    defaults.update(kwargs)
    return Config(**defaults)


def _make_listener(**kwargs):
    config = kwargs.pop("config", _make_config())
    scrobbler = kwargs.pop("scrobbler", MagicMock())
    state_manager = kwargs.pop("state_manager", TrackStateManager())
    return SonosListener(config, scrobbler, state_manager, **kwargs)


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


class TestSubscribe:
    def test_subscribe_success(self):
        listener = _make_listener()
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"
        speaker.player_name = "Living Room"
        mock_sub = MagicMock()
        speaker.avTransport.subscribe.return_value = mock_sub

        result = listener.subscribe(speaker)
        assert result is mock_sub
        assert "192.168.1.10" in listener._subscriptions
        assert "192.168.1.10" in listener._speakers

    def test_subscribe_already_subscribed(self):
        listener = _make_listener()
        existing_sub = MagicMock()
        listener._subscriptions["192.168.1.10"] = existing_sub

        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"

        result = listener.subscribe(speaker)
        assert result is existing_sub
        speaker.avTransport.subscribe.assert_not_called()

    def test_subscribe_failure(self):
        listener = _make_listener()
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"
        speaker.player_name = "Living Room"
        speaker.avTransport.subscribe.side_effect = Exception("network error")

        result = listener.subscribe(speaker)
        assert result is None
        assert "192.168.1.10" not in listener._subscriptions


class TestUnsubscribeAll:
    def test_unsubscribe_all_cleans_up(self):
        listener = _make_listener()
        sub1 = MagicMock()
        sub2 = MagicMock()
        listener._subscriptions = {"10": sub1, "11": sub2}
        listener._speakers = {"10": MagicMock(), "11": MagicMock()}

        listener._unsubscribe_all()

        sub1.unsubscribe.assert_called_once()
        sub2.unsubscribe.assert_called_once()
        assert len(listener._subscriptions) == 0
        assert len(listener._speakers) == 0

    def test_unsubscribe_all_handles_errors(self):
        listener = _make_listener()
        sub = MagicMock()
        sub.unsubscribe.side_effect = Exception("fail")
        listener._subscriptions = {"10": sub}
        listener._speakers = {"10": MagicMock()}

        listener._unsubscribe_all()  # Should not raise
        assert len(listener._subscriptions) == 0


class TestProcessActions:
    def test_now_playing_action(self):
        scrobbler = MagicMock()
        listener = _make_listener(scrobbler=scrobbler)
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration_seconds=200)
        actions = [Action(type=ActionType.NOW_PLAYING, speaker_id="spk1", track=track)]

        listener._process_actions(actions)

        scrobbler.update_now_playing.assert_called_once_with(
            artist="Artist",
            title="Song",
            album="Album",
            duration=200,
        )

    def test_scrobble_action(self):
        scrobbler = MagicMock()
        listener = _make_listener(scrobbler=scrobbler)
        track = TrackInfo(title="Song", artist="Artist", album="Album", duration_seconds=200)
        actions = [Action(type=ActionType.SCROBBLE, speaker_id="spk1", track=track, timestamp=1000)]

        listener._process_actions(actions)

        scrobbler.scrobble.assert_called_once_with(
            artist="Artist",
            title="Song",
            timestamp=1000,
            album="Album",
            duration=200,
        )

    def test_process_actions_calls_state_change(self):
        callback = MagicMock()
        listener = _make_listener(on_state_change=callback)
        track = TrackInfo(title="Song", artist="Artist")
        actions = [Action(type=ActionType.NOW_PLAYING, speaker_id="spk1", track=track)]

        listener._process_actions(actions)
        callback.assert_called_once()

    def test_process_actions_no_callback_on_empty(self):
        callback = MagicMock()
        listener = _make_listener(on_state_change=callback)

        listener._process_actions([])
        callback.assert_not_called()

    def test_duration_zero_passed_as_none(self):
        scrobbler = MagicMock()
        listener = _make_listener(scrobbler=scrobbler)
        track = TrackInfo(title="Song", artist="Artist", duration_seconds=0)
        actions = [Action(type=ActionType.NOW_PLAYING, speaker_id="spk1", track=track)]

        listener._process_actions(actions)
        scrobbler.update_now_playing.assert_called_once_with(
            artist="Artist",
            title="Song",
            album=None,
            duration=None,
        )


class TestBroadcastState:
    def test_broadcast_formats_state(self):
        callback = MagicMock()
        state_manager = TrackStateManager()
        listener = _make_listener(state_manager=state_manager, on_state_change=callback)

        speaker = MagicMock()
        speaker.player_name = "Kitchen"
        listener._speakers["192.168.1.10"] = speaker

        track = TrackInfo(
            title="Song",
            artist="Artist",
            album="Album",
            album_art_url="http://art.jpg",
            duration_seconds=200,
        )
        state_manager.handle_event("192.168.1.10", "PLAYING", track)

        listener._broadcast_state()

        callback.assert_called_once()
        state = callback.call_args[0][0]
        assert "192.168.1.10" in state
        assert state["192.168.1.10"]["speaker_name"] == "Kitchen"
        assert state["192.168.1.10"]["title"] == "Song"
        assert state["192.168.1.10"]["is_playing"] is True

    def test_broadcast_no_callback(self):
        listener = _make_listener(on_state_change=None)
        listener._broadcast_state()  # Should not raise

    def test_broadcast_unknown_speaker_uses_id(self):
        callback = MagicMock()
        state_manager = TrackStateManager()
        listener = _make_listener(state_manager=state_manager, on_state_change=callback)

        track = TrackInfo(title="Song", artist="Artist")
        state_manager.handle_event("unknown-ip", "PLAYING", track)

        listener._broadcast_state()

        state = callback.call_args[0][0]
        assert state["unknown-ip"]["speaker_name"] == "unknown-ip"


class TestRefreshSpeakers:
    def test_removes_old_and_adds_new(self):
        listener = _make_listener()

        old_sub = MagicMock()
        listener._subscriptions["192.168.1.10"] = old_sub
        listener._speakers["192.168.1.10"] = MagicMock()

        new_speaker = MagicMock()
        new_speaker.ip_address = "192.168.1.20"
        new_speaker.player_name = "Bedroom"
        new_speaker.avTransport.subscribe.return_value = MagicMock()

        with patch.object(listener, "discover_speakers", return_value=[new_speaker]):
            listener._refresh_speakers()

        old_sub.unsubscribe.assert_called_once()
        assert "192.168.1.10" not in listener._subscriptions
        assert "192.168.1.20" in listener._subscriptions

    def test_keeps_existing_speakers(self):
        listener = _make_listener()

        existing_sub = MagicMock()
        listener._subscriptions["192.168.1.10"] = existing_sub
        listener._speakers["192.168.1.10"] = MagicMock()

        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"

        with patch.object(listener, "discover_speakers", return_value=[speaker]):
            listener._refresh_speakers()

        existing_sub.unsubscribe.assert_not_called()
        assert "192.168.1.10" in listener._subscriptions

    def test_handles_unsubscribe_error(self):
        listener = _make_listener()

        old_sub = MagicMock()
        old_sub.unsubscribe.side_effect = Exception("fail")
        listener._subscriptions["192.168.1.10"] = old_sub
        listener._speakers["192.168.1.10"] = MagicMock()

        with patch.object(listener, "discover_speakers", return_value=[]):
            listener._refresh_speakers()  # Should not raise

        assert "192.168.1.10" not in listener._subscriptions


class TestStop:
    def test_stop_sets_running_false_and_cleans_up(self):
        listener = _make_listener()
        listener._running = True
        sub = MagicMock()
        listener._subscriptions["10"] = sub
        listener._speakers["10"] = MagicMock()

        listener.stop()

        assert listener._running is False
        sub.unsubscribe.assert_called_once()
        assert len(listener._subscriptions) == 0


class TestParseEventFallbackUri:
    def test_falls_back_to_current_track_uri(self):
        listener = _make_listener()
        speaker = MagicMock()
        speaker.ip_address = "192.168.1.10"
        speaker.player_name = "Test"
        listener._speakers["192.168.1.10"] = speaker

        # Meta with resources that lack a uri attribute
        meta = SimpleNamespace(
            title="Song",
            creator="Artist",
            album="Album",
            album_art_uri="",
            resources=[SimpleNamespace()],  # no .uri
        )
        event = MagicMock()
        event.variables = {
            "transport_state": "PLAYING",
            "current_track_meta_data": meta,
            "current_track_duration": "0:03:00",
            "current_track_uri": "x-fallback://uri",
        }

        state, track = listener._parse_event("192.168.1.10", event)
        assert track.uri == "x-fallback://uri"
