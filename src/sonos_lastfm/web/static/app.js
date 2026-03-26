(() => {
    const playersEl = document.getElementById("players");
    const emptyState = document.getElementById("empty-state");
    const statusEl = document.getElementById("status-indicator");
    const statusText = statusEl.querySelector(".status-text");
    const bgGlow = document.getElementById("bg-glow");
    let ws;
    let reconnectTimer;
    let currentArtUrl = null;

    function connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${location.host}/ws`);

        ws.onopen = () => {
            statusText.textContent = "Connected";
            statusEl.className = "status connected";
            clearTimeout(reconnectTimer);
        };

        ws.onclose = () => {
            statusText.textContent = "Disconnected";
            statusEl.className = "status disconnected";
            reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = () => ws.close();

        ws.onmessage = (event) => {
            const state = JSON.parse(event.data);
            const hadScrobble = checkForNewScrobble(state);
            render(state);
            if (hadScrobble) fetchHistory();
        };
    }

    function formatDuration(seconds) {
        if (!seconds) return "";
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, "0")}`;
    }

    // ── Scrobble detection ──

    let prevScrobbleState = {};

    function checkForNewScrobble(state) {
        let newScrobble = false;
        for (const [id, info] of Object.entries(state)) {
            if (info.scrobbled && !prevScrobbleState[id]) {
                newScrobble = true;
            }
            prevScrobbleState[id] = info.scrobbled;
        }
        return newScrobble;
    }

    // ── Album art background glow ──

    function updateBackground(artUrl) {
        if (!artUrl) {
            bgGlow.style.opacity = "0";
            currentArtUrl = null;
            return;
        }

        if (artUrl === currentArtUrl) return;
        currentArtUrl = artUrl;

        bgGlow.style.backgroundImage = `url(${artUrl})`;
        bgGlow.style.opacity = "1";
    }

    // ── Last.fm links ──

    function lastfmArtistUrl(artist) {
        return `https://www.last.fm/music/${encodeURIComponent(artist)}`;
    }

    function lastfmTrackUrl(artist, title) {
        return `https://www.last.fm/music/${encodeURIComponent(artist)}/_/${encodeURIComponent(title)}`;
    }

    function lastfmAlbumUrl(artist, album) {
        return `https://www.last.fm/music/${encodeURIComponent(artist)}/${encodeURIComponent(album)}`;
    }

    function lastfmLink(url, text, className) {
        return `<a href="${escapeAttr(url)}" class="${className}" target="_blank" rel="noopener">${escapeHtml(text)}</a>`;
    }

    // ── Icons ──

    const musicIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`;

    const speakerIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"></rect><circle cx="12" cy="14" r="4"></circle><line x1="12" y1="6" x2="12.01" y2="6"></line></svg>`;

    // ── Render ──

    function render(state) {
        const entries = Object.entries(state);

        if (entries.length === 0) {
            emptyState.style.display = "";
            playersEl.querySelectorAll(".player-card").forEach(el => {
                el.style.opacity = "0";
                el.style.transform = "translateY(8px)";
                setTimeout(() => el.remove(), 250);
            });
            updateBackground(null);
            return;
        }

        emptyState.style.display = "none";
        const activeSpeakers = new Set();

        // Use the first playing speaker's art for the background
        let bgArtUrl = null;

        for (const [speakerId, info] of entries) {
            activeSpeakers.add(speakerId);

            if (info.album_art_url && (info.is_playing || !bgArtUrl)) {
                bgArtUrl = info.album_art_url;
            }

            let card = playersEl.querySelector(`[data-speaker-id="${speakerId}"]`);
            const isNew = !card;

            if (isNew) {
                card = document.createElement("div");
                card.className = "player-card";
                card.dataset.speakerId = speakerId;
                playersEl.appendChild(card);
            }

            card.className = `player-card${info.is_playing ? " playing" : ""}`;

            const artHtml = info.album_art_url
                ? `<img class="album-art" src="${escapeAttr(info.album_art_url)}" alt="" loading="lazy" onerror="this.onerror=null;this.style.display='none';this.parentElement.querySelector('.art-fallback').style.display='flex'"><div class="album-art-placeholder art-fallback" style="display:none">${musicIcon}</div>`
                : `<div class="album-art-placeholder">${musicIcon}</div>`;

            const scrobbleClass = info.scrobbled ? "scrobbled" : "pending";
            const scrobbleLabel = info.scrobbled ? "Scrobbled" : "Listening";

            const durationBadge = info.duration
                ? `<span class="badge badge-duration">${formatDuration(info.duration)}</span>`
                : "";

            const pausedBadge = !info.is_playing
                ? `<span class="badge badge-paused">Paused</span>`
                : "";

            const eqBars = `<div class="eq-bars"><span></span><span></span><span></span><span></span></div>`;

            card.innerHTML = `
                <div class="art-wrap">${artHtml}</div>
                <div class="track-details">
                    <div class="speaker-name">${speakerIcon} ${escapeHtml(info.speaker_name)}</div>
                    <div class="track-title">${info.artist ? lastfmLink(lastfmTrackUrl(info.artist, info.title), info.title, "lastfm-link") : escapeHtml(info.title)}</div>
                    <div class="track-artist">${lastfmLink(lastfmArtistUrl(info.artist), info.artist, "lastfm-link")}</div>
                    ${info.album && info.artist ? `<div class="track-album">${lastfmLink(lastfmAlbumUrl(info.artist, info.album), info.album, "lastfm-link")}</div>` : ""}
                    <div class="track-footer">
                        <span class="badge ${scrobbleClass}"><span class="badge-dot"></span>${scrobbleLabel}</span>
                        ${durationBadge}
                        ${pausedBadge}
                        ${eqBars}
                    </div>
                </div>
            `;
        }

        playersEl.querySelectorAll(".player-card").forEach(el => {
            if (!activeSpeakers.has(el.dataset.speakerId)) {
                el.style.opacity = "0";
                el.style.transform = "translateY(8px)";
                setTimeout(() => el.remove(), 250);
            }
        });

        updateBackground(bgArtUrl);
    }

    function escapeHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ── History ──

    const historySection = document.getElementById("history-section");
    const historyList = document.getElementById("history-list");
    let historyTimer;

    function fetchHistory() {
        fetch("/api/history?limit=20")
            .then(r => r.json())
            .then(renderHistory)
            .catch(() => {});
    }

    function renderHistory(tracks) {
        if (!tracks || tracks.length === 0) {
            historySection.style.display = "none";
            return;
        }

        historySection.style.display = "";

        historyList.innerHTML = tracks.map(t => {
            const artHtml = t.album_art_url
                ? `<img class="history-art" src="${escapeAttr(t.album_art_url)}" alt="" loading="lazy" onerror="this.onerror=null;this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="history-art-placeholder" style="display:none">${musicIcon}</div>`
                : `<div class="history-art-placeholder">${musicIcon}</div>`;

            const titleLink = t.artist
                ? lastfmLink(lastfmTrackUrl(t.artist, t.title), t.title, "lastfm-link")
                : escapeHtml(t.title);

            const artistLink = t.artist
                ? lastfmLink(lastfmArtistUrl(t.artist), t.artist, "lastfm-link")
                : "";

            const albumHtml = t.album && t.artist
                ? `<div class="history-album">${lastfmLink(lastfmAlbumUrl(t.artist, t.album), t.album, "lastfm-link")}</div>`
                : "";

            const timeStr = t.timestamp ? formatTimeAgo(t.timestamp) : "";

            return `
                <div class="history-item">
                    ${artHtml}
                    <div class="history-info">
                        <div class="history-track">${titleLink}</div>
                        <div class="history-artist">${artistLink}</div>
                        ${albumHtml}
                    </div>
                    ${timeStr ? `<span class="history-time">${escapeHtml(timeStr)}</span>` : ""}
                </div>
            `;
        }).join("");
    }

    function formatTimeAgo(timestamp) {
        const now = Math.floor(Date.now() / 1000);
        const diff = now - timestamp;
        if (diff < 60) return "just now";
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    // Fetch history on load and periodically
    fetchHistory();
    historyTimer = setInterval(fetchHistory, 30000);

    connect();
})();
