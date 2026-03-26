"""FastAPI web application with WebSocket for real-time playback updates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from sonos_lastfm.scrobbler import Scrobbler

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class WebApp:
    def __init__(self, scrobbler: Scrobbler | None = None) -> None:
        self.app = FastAPI(title="sonos-lastfm")
        self._connections: list[WebSocket] = []
        self._current_state: dict = {}
        self._scrobbler = scrobbler
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/")
        async def index():
            return FileResponse(STATIC_DIR / "index.html")

        @self.app.get("/api/status")
        async def status():
            return self._current_state

        @self.app.get("/api/history")
        async def history(limit: int = 20):
            if not self._scrobbler:
                return []
            return self._scrobbler.get_recent_tracks(limit=min(limit, 50))

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._connections.append(ws)
            try:
                # Send current state on connect
                await ws.send_text(json.dumps(self._current_state))
                while True:
                    await ws.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                if ws in self._connections:
                    self._connections.remove(ws)

        self.app.mount(
            "/static",
            StaticFiles(directory=str(STATIC_DIR)),
            name="static",
        )

    def broadcast(self, state: dict) -> None:
        """Called from the listener thread to push state updates."""
        self._current_state = state
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                # Use the event loop from the async context
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        ws.send_text(json.dumps(state)), loop
                    )
                else:
                    loop.run_until_complete(ws.send_text(json.dumps(state)))
            except Exception:
                stale.append(ws)
        for ws in stale:
            if ws in self._connections:
                self._connections.remove(ws)
