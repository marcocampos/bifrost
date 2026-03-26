"""FastAPI web application with WebSocket for real-time playback updates."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bifrost.scrobbler import Scrobbler

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class WebApp:
    def __init__(self, scrobbler: Scrobbler | None = None) -> None:
        self.app = FastAPI(title="bifrost")
        self._connections: list[WebSocket] = []
        self._current_state: dict = {}
        self._scrobbler = scrobbler
        self._speaker_count: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/")
        async def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

        @self.app.get("/sw.js")
        async def service_worker() -> FileResponse:
            return FileResponse(
                STATIC_DIR / "sw.js",
                media_type="application/javascript",
                headers={
                    "Service-Worker-Allowed": "/",
                    "Cache-Control": "no-cache",
                },
            )

        @self.app.get("/api/health")
        async def health() -> dict:
            lastfm_ok = False
            if self._scrobbler:
                lastfm_ok = self._scrobbler.verify_credentials()
            return {
                "status": "ok" if lastfm_ok else "degraded",
                "lastfm": lastfm_ok,
                "speakers": self._speaker_count,
            }

        @self.app.get("/api/status")
        async def status() -> dict:
            return self._current_state

        @self.app.get("/api/history")
        async def history(limit: int = 20) -> list[dict]:
            if not self._scrobbler:
                return []
            return self._scrobbler.get_recent_tracks(limit=min(limit, 50))

        @self.app.get("/api/stats")
        async def stats(period: str = "7day", limit: int = 10) -> dict:
            if not self._scrobbler:
                return {
                    "period": period,
                    "total_scrobbles": 0,
                    "top_artists": [],
                    "top_albums": [],
                    "top_tracks": [],
                }
            return self._scrobbler.get_stats(period=period, limit=min(limit, 50))

        @self.app.post("/api/love")
        async def love_track(artist: str, title: str) -> dict:
            if not self._scrobbler:
                return {"ok": False}
            ok = self._scrobbler.love_track(artist, title)
            return {"ok": ok}

        @self.app.post("/api/unlove")
        async def unlove_track(artist: str, title: str) -> dict:
            if not self._scrobbler:
                return {"ok": False}
            ok = self._scrobbler.unlove_track(artist, title)
            return {"ok": ok}

        @self.app.get("/api/loved")
        async def is_loved(artist: str, title: str) -> dict:
            if not self._scrobbler:
                return {"loved": False}
            loved = self._scrobbler.is_track_loved(artist, title)
            return {"loved": loved}

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket) -> None:
            if self._loop is None:
                self._loop = asyncio.get_running_loop()
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

    def update_speaker_count(self, count: int) -> None:
        """Update the number of discovered speakers."""
        self._speaker_count = count

    def broadcast(self, state: dict) -> None:
        """Called from the listener thread to push state updates."""
        self._current_state = state
        if self._loop is None:
            return
        payload = json.dumps(state)
        self._loop.call_soon_threadsafe(self._send_to_all, payload)

    def _send_to_all(self, payload: str) -> None:
        """Send payload to all connected WebSockets (runs on the event loop thread)."""
        for ws in list(self._connections):
            asyncio.ensure_future(self._safe_send(ws, payload))

    async def _safe_send(self, ws: WebSocket, payload: str) -> None:
        """Send to a single WebSocket, removing it on failure."""
        try:
            await ws.send_text(payload)
        except Exception:
            if ws in self._connections:
                self._connections.remove(ws)
