"""Configuration loading from environment variables."""

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    lastfm_api_key: str
    lastfm_api_secret: str
    lastfm_username: str = ""
    lastfm_password_hash: str = ""
    lastfm_session_key: str = ""
    sonos_speakers: list[str] = field(default_factory=list)
    web_port: int = 8080
    log_level: str = "INFO"


def load_config() -> Config:
    """Load configuration from environment variables (.env supported)."""
    load_dotenv()

    speakers_raw = os.environ.get("SONOS_SPEAKERS", "")
    speakers = [s.strip() for s in speakers_raw.split(",") if s.strip()]

    config = Config(
        lastfm_api_key=os.environ.get("LASTFM_API_KEY", ""),
        lastfm_api_secret=os.environ.get("LASTFM_API_SECRET", ""),
        lastfm_username=os.environ.get("LASTFM_USERNAME", ""),
        lastfm_password_hash=os.environ.get("LASTFM_PASSWORD_HASH", ""),
        lastfm_session_key=os.environ.get("LASTFM_SESSION_KEY", ""),
        sonos_speakers=speakers,
        web_port=int(os.environ.get("WEB_PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )

    if not config.lastfm_api_key or not config.lastfm_api_secret:
        print(
            "Error: LASTFM_API_KEY and LASTFM_API_SECRET are required.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not config.lastfm_session_key and not (
        config.lastfm_username and config.lastfm_password_hash
    ):
        print(
            "Error: Provide LASTFM_SESSION_KEY or both LASTFM_USERNAME and LASTFM_PASSWORD_HASH.",
            file=sys.stderr,
        )
        sys.exit(1)

    return config
