"""Sonos speaker discovery, UPnP event subscriptions, and main event loop."""

from __future__ import annotations

import logging
import time
from queue import Empty
from typing import TYPE_CHECKING, Callable

import soco
from soco.events import Subscription

from sonos_lastfm.track_state import Action, ActionType, TrackInfo, TrackStateManager

if TYPE_CHECKING:
    from sonos_lastfm.config import Config
    from sonos_lastfm.scrobbler import Scrobbler

logger = logging.getLogger(__name__)


def parse_duration(duration_str: str) -> int:
    """Parse a Sonos duration string like '0:03:45' to seconds."""
    if not duration_str or duration_str == "NOT_IMPLEMENTED":
        return 0
    try:
        parts = duration_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except (ValueError, IndexError):
        return 0


def get_album_art_url(speaker: soco.SoCo, meta) -> str | None:
    """Extract album art URL from track metadata."""
    if meta and hasattr(meta, "album_art_uri") and meta.album_art_uri:
        uri = meta.album_art_uri
        if uri.startswith(("http://", "https://")):
            return uri
        return f"http://{speaker.ip_address}:1400{uri}"
    return None


class SonosListener:
    def __init__(
        self,
        config: Config,
        scrobbler: Scrobbler,
        state_manager: TrackStateManager,
        on_state_change: Callable[[dict], None] | None = None,
    ) -> None:
        self.config = config
        self.scrobbler = scrobbler
        self.state_manager = state_manager
        self.on_state_change = on_state_change
        self._subscriptions: dict[str, Subscription] = {}
        self._speakers: dict[str, soco.SoCo] = {}
        self._running = False

    def discover_speakers(self) -> list[soco.SoCo]:
        """Discover Sonos speakers, filtering to group coordinators."""
        discovered = soco.discover(timeout=5)
        if not discovered:
            logger.warning("No Sonos speakers found on the network")
            return []

        # Filter to group coordinators only
        coordinators = [
            s for s in discovered
            if s.group and s.group.coordinator.ip_address == s.ip_address
        ]

        # Filter by configured speaker names
        if self.config.sonos_speakers:
            allowed = {name.lower() for name in self.config.sonos_speakers}
            coordinators = [
                s for s in coordinators
                if s.player_name.lower() in allowed
            ]

        for s in coordinators:
            logger.info("Found speaker", extra={"speaker": s.player_name, "ip": s.ip_address})

        return coordinators

    def subscribe(self, speaker: soco.SoCo) -> Subscription | None:
        """Subscribe to AVTransport events for a speaker."""
        key = speaker.ip_address
        if key in self._subscriptions:
            return self._subscriptions[key]
        try:
            sub = speaker.avTransport.subscribe(auto_renew=True)
            self._subscriptions[key] = sub
            self._speakers[key] = speaker
            logger.info("Subscribed to events", extra={"speaker": speaker.player_name})
            return sub
        except Exception:
            logger.exception("Failed to subscribe", extra={"speaker": speaker.player_name})
            return None

    def _unsubscribe_all(self) -> None:
        """Clean up all event subscriptions."""
        for key, sub in self._subscriptions.items():
            try:
                sub.unsubscribe()
                logger.debug("Unsubscribed from %s", key)
            except Exception:
                logger.debug("Failed to unsubscribe from %s", key, exc_info=True)
        self._subscriptions.clear()
        self._speakers.clear()

    def _parse_event(self, speaker_ip: str, event) -> tuple[str, TrackInfo | None]:
        """Parse an AVTransport event into transport state and track info."""
        variables = event.variables

        transport_state = variables.get("transport_state", "")

        meta = variables.get("current_track_meta_data")
        if not meta or isinstance(meta, str):
            return transport_state, None

        title = getattr(meta, "title", "") or ""
        artist = getattr(meta, "creator", "") or ""
        album = getattr(meta, "album", "") or ""

        duration_str = variables.get("current_track_duration", "")
        duration = parse_duration(duration_str)

        speaker = self._speakers.get(speaker_ip)
        album_art_url = get_album_art_url(speaker, meta) if speaker else None

        uri = getattr(meta, "resources", [{}])
        if uri and hasattr(uri[0], "uri"):
            uri = uri[0].uri
        else:
            uri = variables.get("current_track_uri", "")

        track = TrackInfo(
            title=title,
            artist=artist,
            album=album or None,
            album_art_url=album_art_url,
            duration_seconds=duration,
            uri=uri,
        )
        return transport_state, track

    def _process_actions(self, actions: list[Action]) -> None:
        """Execute scrobble/now-playing actions and notify UI."""
        for action in actions:
            if action.type == ActionType.NOW_PLAYING:
                self.scrobbler.update_now_playing(
                    artist=action.track.artist,
                    title=action.track.title,
                    album=action.track.album,
                    duration=action.track.duration_seconds or None,
                )
            elif action.type == ActionType.SCROBBLE:
                self.scrobbler.scrobble(
                    artist=action.track.artist,
                    title=action.track.title,
                    timestamp=action.timestamp,
                    album=action.track.album,
                    duration=action.track.duration_seconds or None,
                )

        if actions and self.on_state_change:
            self._broadcast_state()

    def _broadcast_state(self) -> None:
        """Send current state to the web UI."""
        if not self.on_state_change:
            return
        tracks = self.state_manager.get_current_tracks()
        state = {}
        for speaker_id, play_state in tracks.items():
            speaker = self._speakers.get(speaker_id)
            speaker_name = speaker.player_name if speaker else speaker_id
            state[speaker_id] = {
                "speaker_name": speaker_name,
                "title": play_state.track.title,
                "artist": play_state.track.artist,
                "album": play_state.track.album,
                "album_art_url": play_state.track.album_art_url,
                "duration": play_state.track.duration_seconds,
                "is_playing": play_state.is_playing,
                "scrobbled": play_state.scrobbled,
            }
        self.on_state_change(state)

    def _refresh_speakers(self) -> None:
        """Re-discover speakers and update subscriptions for group changes."""
        new_coordinators = self.discover_speakers()
        new_ips = {s.ip_address for s in new_coordinators}
        current_ips = set(self._subscriptions.keys())

        # Unsubscribe from speakers no longer coordinating
        for ip in current_ips - new_ips:
            sub = self._subscriptions.pop(ip, None)
            self._speakers.pop(ip, None)
            self.state_manager.remove_speaker(ip)
            if sub:
                try:
                    sub.unsubscribe()
                except Exception:
                    pass
            logger.info("Removed speaker (no longer coordinator)", extra={"ip": ip})

        # Subscribe to new coordinators
        for speaker in new_coordinators:
            if speaker.ip_address not in current_ips:
                self.subscribe(speaker)

    def run(self) -> None:
        """Main event loop: discover, subscribe, poll events."""
        self._running = True
        logger.info("Starting Sonos listener...")

        speakers = self.discover_speakers()
        if not speakers:
            logger.error("No speakers found. Will retry on next refresh cycle.")

        for speaker in speakers:
            self.subscribe(speaker)

        last_refresh = time.monotonic()
        last_tick = time.monotonic()

        while self._running:
            now = time.monotonic()

            # Poll each subscription for events
            for ip, sub in list(self._subscriptions.items()):
                try:
                    event = sub.events.get(timeout=0.2)
                    transport_state, track_info = self._parse_event(ip, event)
                    if transport_state:
                        actions = self.state_manager.handle_event(
                            ip, transport_state, track_info
                        )
                        self._process_actions(actions)
                except Empty:
                    pass
                except Exception:
                    logger.exception("Error processing event from %s", ip)

            # Periodic tick for mid-song scrobble checks
            if now - last_tick >= 5:
                actions = self.state_manager.tick()
                self._process_actions(actions)
                last_tick = now

            # Periodic speaker refresh
            if now - last_refresh >= 30:
                try:
                    self._refresh_speakers()
                except Exception:
                    logger.exception("Error refreshing speakers")
                last_refresh = now

    def stop(self) -> None:
        """Signal the main loop to stop and clean up."""
        self._running = False
        self._unsubscribe_all()
        logger.info("Sonos listener stopped")
