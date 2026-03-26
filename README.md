# Bifrost

Bridge your Sonos speakers to Last.fm. Bifrost automatically scrobbles songs playing on your Sonos system, with a real-time web UI showing what's playing, your listening history, and stats.

## Features

- **Automatic scrobbling** from all Sonos speakers on your network
- **Real-time web UI** with album art, now playing, and WebSocket updates
- **Listening stats** with top artists, albums, and tracks by period
- **Recent scrobbles** fetched from your Last.fm profile
- **Love tracks** directly from the web UI
- **Last.fm links** on all track, artist, and album names
- **Speaker filtering** to scrobble from specific speakers only
- **Group handling** so grouped speakers only scrobble once
- **Light/dark theme** with system preference detection
- **PWA support** for installation on mobile devices
- **Structured JSON logging** for easy monitoring
- **Health check endpoint** at `/api/health`

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- Sonos speakers on the same network
- [Last.fm API account](https://www.last.fm/api/account/create)

### Install and Run

```bash
# Clone the repo
git clone https://github.com/marcocampos/sonos-lastfm.git
cd sonos-lastfm

# Install dependencies
uv sync

# Authenticate with Last.fm (interactive)
uv run bifrost auth

# Copy the output to your .env file
cp .env.example .env
# Edit .env with your credentials

# Run
uv run bifrost
```

Open http://localhost:8080 in your browser.

### Docker

```bash
# Build and run
docker compose up -d

# Or build manually
docker build -t bifrost .
docker run --network=host --env-file .env bifrost
```

> **Note:** `--network=host` (or `network_mode: host` in Compose) is required for Sonos UPnP/SSDP multicast discovery.

### Docker Compose

```yaml
services:
  bifrost:
    build: .
    network_mode: host
    env_file: .env
    restart: unless-stopped
```

## Configuration

All configuration is via environment variables (`.env` file supported):

| Variable | Required | Description |
|----------|----------|-------------|
| `LASTFM_API_KEY` | Yes | Last.fm API key |
| `LASTFM_API_SECRET` | Yes | Last.fm API secret |
| `LASTFM_SESSION_KEY` | * | Last.fm session key |
| `LASTFM_USERNAME` | * | Last.fm username |
| `LASTFM_PASSWORD_HASH` | * | MD5 hash of Last.fm password |
| `SONOS_SPEAKERS` | No | Comma-separated speaker names to filter |
| `WEB_PORT` | No | Web UI port (default: 8080) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

\* Provide either `LASTFM_SESSION_KEY` or both `LASTFM_USERNAME` + `LASTFM_PASSWORD_HASH`.

Run `bifrost auth` for an interactive setup that generates these values.

## Homelab Setup

Bifrost is designed to run as a long-lived service on your homelab:

### systemd Service

```ini
[Unit]
Description=Bifrost - Sonos to Last.fm scrobbler
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/bifrost
EnvironmentFile=/opt/bifrost/.env
ExecStart=/opt/bifrost/.venv/bin/bifrost
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker on a Raspberry Pi / NAS

```bash
docker compose up -d
```

The container uses host networking for Sonos discovery and restarts automatically. No external database or services needed beyond your local network and a Last.fm account.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/ws` | WS | Real-time playback updates |
| `/api/status` | GET | Current playback state |
| `/api/health` | GET | Health check (Last.fm + speakers) |
| `/api/history` | GET | Recent scrobbles |
| `/api/stats` | GET | Listening stats by period |
| `/api/love` | POST | Love a track |
| `/api/unlove` | POST | Unlove a track |
| `/api/loved` | GET | Check if track is loved |

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=bifrost --cov-report=term-missing

# Run the app
uv run bifrost
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Open a pull request against `main`

Direct pushes to `main` are not allowed. All changes must go through pull requests.

## License

MIT
