"""Entry point for sonos-lastfm."""

from __future__ import annotations

import logging
import signal
import threading

import uvicorn

from sonos_lastfm.config import load_config
from sonos_lastfm.scrobbler import Scrobbler
from sonos_lastfm.sonos_listener import SonosListener
from sonos_lastfm.track_state import TrackStateManager
from sonos_lastfm.web.app import WebApp


def main() -> None:
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    scrobbler = Scrobbler(config)
    state_manager = TrackStateManager()
    web_app = WebApp()

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
