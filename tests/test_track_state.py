"""Tests for track state machine and scrobble eligibility."""

from bifrost.track_state import (
    ActionType,
    TrackInfo,
    TrackStateManager,
)


def make_track(title="Song", artist="Artist", duration=200, uri="x-sonos:track1"):
    return TrackInfo(
        title=title,
        artist=artist,
        album="Album",
        duration_seconds=duration,
        uri=uri,
    )


class TestTrackInfo:
    def test_same_track_by_uri(self):
        a = make_track(uri="uri1")
        b = make_track(uri="uri1")
        assert a.is_same_track(b)

    def test_different_track_by_uri(self):
        a = make_track(uri="uri1")
        b = make_track(uri="uri2")
        assert not a.is_same_track(b)

    def test_same_track_no_uri(self):
        a = TrackInfo(title="Song", artist="Artist", uri="")
        b = TrackInfo(title="Song", artist="Artist", uri="")
        assert a.is_same_track(b)

    def test_different_track_no_uri(self):
        a = TrackInfo(title="Song", artist="Artist", uri="")
        b = TrackInfo(title="Other", artist="Artist", uri="")
        assert not a.is_same_track(b)

    def test_not_same_as_none(self):
        a = make_track()
        assert not a.is_same_track(None)


class TestTrackStateManager:
    def setup_method(self):
        self.time = 0.0
        self.manager = TrackStateManager(clock=lambda: self.time)

    def advance(self, seconds: float):
        self.time += seconds

    def test_new_track_playing_sends_now_playing(self):
        track = make_track()
        actions = self.manager.handle_event("spk1", "PLAYING", track)
        assert len(actions) == 1
        assert actions[0].type == ActionType.NOW_PLAYING
        assert actions[0].track == track

    def test_pause_and_resume_no_duplicate_now_playing(self):
        track = make_track()
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(50)
        self.manager.handle_event("spk1", "PAUSED_PLAYBACK", track)

        self.advance(30)
        actions = self.manager.handle_event("spk1", "PLAYING", track)
        # Resume should not send now_playing again
        assert len(actions) == 0

    def test_scrobble_at_50_percent(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(100)  # 50% of 200s
        actions = self.manager.tick()
        assert len(actions) == 1
        assert actions[0].type == ActionType.SCROBBLE

    def test_no_scrobble_before_50_percent(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(99)
        actions = self.manager.tick()
        assert len(actions) == 0

    def test_scrobble_capped_at_4_minutes(self):
        # Long track: 10 minutes. 50% = 300s, but cap is 240s
        track = make_track(duration=600)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(240)
        actions = self.manager.tick()
        assert len(actions) == 1
        assert actions[0].type == ActionType.SCROBBLE

    def test_no_double_scrobble(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(100)
        actions1 = self.manager.tick()
        assert len(actions1) == 1

        self.advance(50)
        actions2 = self.manager.tick()
        assert len(actions2) == 0

    def test_scrobble_on_track_change(self):
        track1 = make_track(title="Song 1", uri="uri1", duration=200)
        track2 = make_track(title="Song 2", uri="uri2", duration=200)

        self.manager.handle_event("spk1", "PLAYING", track1)
        self.advance(110)

        actions = self.manager.handle_event("spk1", "PLAYING", track2)
        types = [a.type for a in actions]
        assert ActionType.SCROBBLE in types
        assert ActionType.NOW_PLAYING in types

    def test_no_scrobble_on_skip(self):
        track1 = make_track(title="Song 1", uri="uri1", duration=200)
        track2 = make_track(title="Song 2", uri="uri2", duration=200)

        self.manager.handle_event("spk1", "PLAYING", track1)
        self.advance(30)  # Only 15% played

        actions = self.manager.handle_event("spk1", "PLAYING", track2)
        types = [a.type for a in actions]
        assert ActionType.SCROBBLE not in types
        assert ActionType.NOW_PLAYING in types

    def test_scrobble_on_stop_if_eligible(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(110)
        actions = self.manager.handle_event("spk1", "STOPPED", None)
        assert len(actions) == 1
        assert actions[0].type == ActionType.SCROBBLE

    def test_no_scrobble_on_stop_if_not_eligible(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(30)
        actions = self.manager.handle_event("spk1", "STOPPED", None)
        assert len(actions) == 0

    def test_pause_accumulates_time(self):
        track = make_track(duration=200)
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(60)
        self.manager.handle_event("spk1", "PAUSED_PLAYBACK", track)

        self.advance(1000)  # Long pause — shouldn't count

        self.manager.handle_event("spk1", "PLAYING", track)
        self.advance(40)  # Total: 60 + 40 = 100s = 50%

        actions = self.manager.tick()
        assert len(actions) == 1
        assert actions[0].type == ActionType.SCROBBLE

    def test_stream_scrobble_at_4_minutes(self):
        track = make_track(duration=0)  # Stream, unknown duration
        self.manager.handle_event("spk1", "PLAYING", track)

        self.advance(239)
        assert len(self.manager.tick()) == 0

        self.advance(1)
        actions = self.manager.tick()
        assert len(actions) == 1
        assert actions[0].type == ActionType.SCROBBLE

    def test_transitioning_is_noop(self):
        track = make_track()
        self.manager.handle_event("spk1", "PLAYING", track)
        actions = self.manager.handle_event("spk1", "TRANSITIONING", None)
        assert len(actions) == 0
        # State should still exist
        assert "spk1" in self.manager.get_current_tracks()

    def test_skip_track_without_metadata(self):
        track = TrackInfo(title="", artist="", uri="")
        actions = self.manager.handle_event("spk1", "PLAYING", track)
        assert len(actions) == 0

    def test_multiple_speakers_independent(self):
        track1 = make_track(title="Song A", uri="a")
        track2 = make_track(title="Song B", uri="b")

        self.manager.handle_event("spk1", "PLAYING", track1)
        self.manager.handle_event("spk2", "PLAYING", track2)

        current = self.manager.get_current_tracks()
        assert "spk1" in current
        assert "spk2" in current
        assert current["spk1"].track.title == "Song A"
        assert current["spk2"].track.title == "Song B"

    def test_remove_speaker(self):
        track = make_track()
        self.manager.handle_event("spk1", "PLAYING", track)
        self.manager.remove_speaker("spk1")
        assert "spk1" not in self.manager.get_current_tracks()

    def test_remove_nonexistent_speaker(self):
        self.manager.remove_speaker("nonexistent")  # Should not raise
