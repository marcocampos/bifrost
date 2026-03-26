"""Track play state machine and scrobble eligibility logic."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto


class ActionType(Enum):
    NOW_PLAYING = auto()
    SCROBBLE = auto()


@dataclass
class TrackInfo:
    title: str
    artist: str
    album: str | None = None
    album_art_url: str | None = None
    duration_seconds: int = 0
    uri: str = ""
    service: str | None = None

    def is_same_track(self, other: TrackInfo | None) -> bool:
        if other is None:
            return False
        if self.uri and other.uri:
            return self.uri == other.uri
        return self.title == other.title and self.artist == other.artist


@dataclass
class PlayState:
    track: TrackInfo
    started_at: float
    accumulated_seconds: float = 0.0
    is_playing: bool = True
    scrobbled: bool = False
    now_playing_sent: bool = False


@dataclass
class Action:
    type: ActionType
    speaker_id: str
    track: TrackInfo
    timestamp: int = field(default_factory=lambda: int(time.time()))


class TrackStateManager:
    def __init__(self, clock: callable = None) -> None:
        self._states: dict[str, PlayState] = {}
        self._clock = clock or time.monotonic

    def handle_event(
        self,
        speaker_id: str,
        transport_state: str,
        track_info: TrackInfo | None,
    ) -> list[Action]:
        actions: list[Action] = []
        current = self._states.get(speaker_id)
        now = self._clock()

        if transport_state == "PLAYING":
            if track_info and (not track_info.artist or not track_info.title):
                return actions

            if current is None or not track_info or not track_info.is_same_track(current.track):
                # New track or first track
                if current and current.is_playing:
                    actions.extend(self._finalize(speaker_id, current, now))

                if track_info:
                    state = PlayState(track=track_info, started_at=now)
                    self._states[speaker_id] = state
                    actions.append(Action(
                        type=ActionType.NOW_PLAYING,
                        speaker_id=speaker_id,
                        track=track_info,
                    ))
                    state.now_playing_sent = True
            else:
                # Same track resumed from pause
                if not current.is_playing:
                    current.started_at = now
                    current.is_playing = True

        elif transport_state == "PAUSED_PLAYBACK":
            if current and current.is_playing:
                current.accumulated_seconds += now - current.started_at
                current.is_playing = False

        elif transport_state in ("STOPPED", "NO_MEDIA_PRESENT"):
            if current:
                actions.extend(self._finalize(speaker_id, current, now))
                del self._states[speaker_id]

        # TRANSITIONING is a no-op — wait for the next PLAYING event

        return actions

    def tick(self) -> list[Action]:
        """Check all active states for mid-song scrobble eligibility."""
        actions: list[Action] = []
        now = self._clock()
        for speaker_id, state in self._states.items():
            if not state.scrobbled and self._is_scrobble_eligible(state, now):
                state.scrobbled = True
                actions.append(Action(
                    type=ActionType.SCROBBLE,
                    speaker_id=speaker_id,
                    track=state.track,
                ))
        return actions

    def get_current_tracks(self) -> dict[str, PlayState]:
        return dict(self._states)

    def remove_speaker(self, speaker_id: str) -> None:
        self._states.pop(speaker_id, None)

    def _finalize(self, speaker_id: str, state: PlayState, now: float) -> list[Action]:
        """Check scrobble eligibility for a track that's ending."""
        actions: list[Action] = []
        if state.is_playing:
            state.accumulated_seconds += now - state.started_at
            state.is_playing = False
        if not state.scrobbled and self._is_scrobble_eligible(state, now):
            state.scrobbled = True
            actions.append(Action(
                type=ActionType.SCROBBLE,
                speaker_id=speaker_id,
                track=state.track,
            ))
        return actions

    def _is_scrobble_eligible(self, state: PlayState, now: float) -> bool:
        play_time = state.accumulated_seconds
        if state.is_playing:
            play_time += now - state.started_at

        if state.track.duration_seconds > 0:
            threshold = min(state.track.duration_seconds * 0.5, 240)
        else:
            # Streams with unknown duration: require 4 minutes
            threshold = 240

        return play_time >= threshold
