"""Last.fm scrobbler wrapper using pylast."""

from __future__ import annotations

import logging
import time

import pylast

from sonos_lastfm.config import Config

logger = logging.getLogger(__name__)


class Scrobbler:
    def __init__(self, config: Config) -> None:
        self.network = pylast.LastFMNetwork(
            api_key=config.lastfm_api_key,
            api_secret=config.lastfm_api_secret,
            username=config.lastfm_username or None,
            password_hash=config.lastfm_password_hash or None,
            session_key=config.lastfm_session_key or None,
        )
        logger.info("Connected to Last.fm as %s", config.lastfm_username or "(session key)")

    def update_now_playing(
        self,
        artist: str,
        title: str,
        album: str | None = None,
        duration: int | None = None,
    ) -> None:
        try:
            self.network.update_now_playing(
                artist=artist,
                title=title,
                album=album,
                duration=duration,
            )
            logger.debug("Now playing: %s - %s", artist, title)
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to update now playing: %s", e)

    def scrobble(
        self,
        artist: str,
        title: str,
        timestamp: int | None = None,
        album: str | None = None,
        duration: int | None = None,
    ) -> None:
        if timestamp is None:
            timestamp = int(time.time())
        try:
            self.network.scrobble(
                artist=artist,
                title=title,
                timestamp=timestamp,
                album=album,
                duration=duration,
            )
            logger.info("Scrobbled: %s - %s", artist, title)
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to scrobble %s - %s: %s", artist, title, e)

    def get_session_key(self) -> str:
        return self.network.session_key
