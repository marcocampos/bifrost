"""Entry point for sonos-lastfm."""

from __future__ import annotations

import logging
import signal
import sys
import threading

import uvicorn

from sonos_lastfm.config import load_config
from sonos_lastfm.scrobbler import Scrobbler
from sonos_lastfm.sonos_listener import SonosListener
from sonos_lastfm.track_state import TrackStateManager
from sonos_lastfm.web.app import WebApp


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        from sonos_lastfm.auth import run_auth

        run_auth()
        return

    config = load_config()

    from sonos_lastfm.logging_config import setup_logging
    setup_logging(config.log_level)

    scrobbler = Scrobbler(config)
    state_manager = TrackStateManager()
    web_app = WebApp(scrobbler=scrobbler)

    listener = SonosListener(
        config=config,
        scrobbler=scrobbler,
        state_manager=state_manager,
        on_state_change=web_app.broadcast,
    )

    # Run the Sonos listener in a background thread
    listener_thread = threading.Thread(target=listener.run, daemon=True)
    listener_thread.start()

    # Handle graceful shutdown
    def shutdown(signum, frame):
        logging.getLogger(__name__).info("Shutting down...")
        listener.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start the web server (blocks until stopped)
    uvicorn.run(
        web_app.app,
        host="0.0.0.0",
        port=config.web_port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
