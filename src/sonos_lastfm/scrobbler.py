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
        self._username = config.lastfm_username or "(session key)"
        logger.info("Connected to Last.fm", extra={"username": self._username})

    def verify_credentials(self) -> bool:
        """Verify Last.fm credentials are valid by fetching the authenticated user."""
        try:
            user = self.network.get_authenticated_user()
            name = str(user)
            logger.info("Last.fm credentials verified", extra={"username": name})
            return True
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Last.fm credential verification failed", extra={"error": str(e)})
            return False

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
            logger.debug("Now playing updated", extra={"artist": artist, "title": title})
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to update now playing", extra={"artist": artist, "title": title, "error": str(e)})

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
            logger.info("Scrobbled", extra={"artist": artist, "title": title})
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to scrobble", extra={"artist": artist, "title": title, "error": str(e)})

    def get_recent_tracks(self, limit: int = 20) -> list[dict]:
        """Fetch the user's recent scrobbles from Last.fm."""
        try:
            user = self.network.get_authenticated_user()
            tracks = user.get_recent_tracks(limit=limit)
            result = []
            for played in tracks:
                track = played.track
                album = played.album
                result.append({
                    "artist": str(track.artist),
                    "title": str(track.title),
                    "album": str(album) if album else None,
                    "timestamp": int(played.timestamp) if played.timestamp else None,
                })
            return result
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to fetch recent tracks", extra={"error": str(e)})
            return []

    def get_stats(self, period: str = "7day", limit: int = 10) -> dict:
        """Fetch listening stats from Last.fm for the given period."""
        valid_periods = {"7day", "1month", "3month", "6month", "12month", "overall"}
        if period not in valid_periods:
            period = "7day"

        try:
            user = self.network.get_authenticated_user()

            top_artists = [
                {"name": str(a.item), "plays": int(a.weight)}
                for a in user.get_top_artists(period=period, limit=limit)
            ]

            top_albums = [
                {
                    "name": str(a.item.title),
                    "artist": str(a.item.artist),
                    "plays": int(a.weight),
                }
                for a in user.get_top_albums(period=period, limit=limit)
            ]

            top_tracks = [
                {
                    "name": str(t.item.title),
                    "artist": str(t.item.artist),
                    "plays": int(t.weight),
                }
                for t in user.get_top_tracks(period=period, limit=limit)
            ]

            playcount = int(user.get_playcount())

            return {
                "period": period,
                "total_scrobbles": playcount,
                "top_artists": top_artists,
                "top_albums": top_albums,
                "top_tracks": top_tracks,
            }
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to fetch stats", extra={"error": str(e)})
            return {
                "period": period,
                "total_scrobbles": 0,
                "top_artists": [],
                "top_albums": [],
                "top_tracks": [],
            }

    def love_track(self, artist: str, title: str) -> bool:
        """Love a track on Last.fm. Returns True on success."""
        try:
            track = self.network.get_track(artist, title)
            track.love()
            logger.info("Loved track", extra={"artist": artist, "title": title})
            return True
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to love track", extra={"artist": artist, "title": title, "error": str(e)})
            return False

    def unlove_track(self, artist: str, title: str) -> bool:
        """Unlove a track on Last.fm. Returns True on success."""
        try:
            track = self.network.get_track(artist, title)
            track.unlove()
            logger.info("Unloved track", extra={"artist": artist, "title": title})
            return True
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to unlove track", extra={"artist": artist, "title": title, "error": str(e)})
            return False

    def is_track_loved(self, artist: str, title: str) -> bool:
        """Check if a track is loved on Last.fm."""
        try:
            track = self.network.get_track(artist, title)
            user = self.network.get_authenticated_user()
            return bool(track.get_userloved(user))
        except (pylast.NetworkError, pylast.WSError) as e:
            logger.error("Failed to check loved status", extra={"error": str(e)})
            return False

    def get_session_key(self) -> str:
        return self.network.session_key
