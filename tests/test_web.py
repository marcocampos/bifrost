"""Tests for the web application."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from sonos_lastfm.web.app import WebApp


@pytest.fixture
def web_app():
    return WebApp()


@pytest.fixture
def client(web_app):
    return TestClient(web_app.app)


def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "sonos-lastfm" in response.text


def test_status_empty_initially(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == {}


def test_status_after_broadcast(web_app, client):
    state = {
        "192.168.1.10": {
            "speaker_name": "Living Room",
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "album_art_url": None,
            "duration": 200,
            "is_playing": True,
            "scrobbled": False,
        }
    }
    web_app._current_state = state
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "192.168.1.10" in data
    assert data["192.168.1.10"]["title"] == "Song"


def test_static_css(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_static_js(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_websocket_receives_current_state(web_app):
    web_app._current_state = {"test": "data"}
    client = TestClient(web_app.app)
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert data == {"test": "data"}


def test_broadcast_updates_state(web_app):
    state = {"spk1": {"title": "Song"}}
    web_app.broadcast(state)
    assert web_app._current_state == state


def test_broadcast_with_no_connections(web_app):
    web_app.broadcast({"test": "data"})  # Should not raise
    assert web_app._current_state == {"test": "data"}


def test_broadcast_removes_stale_connections(web_app):
    stale_ws = MagicMock()
    stale_ws.send_text = MagicMock(side_effect=Exception("closed"))
    web_app._connections.append(stale_ws)

    web_app.broadcast({"test": "data"})

    assert stale_ws not in web_app._connections
    assert web_app._current_state == {"test": "data"}
