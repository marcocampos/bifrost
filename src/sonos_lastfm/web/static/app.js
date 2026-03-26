(() => {
    const playersEl = document.getElementById("players");
    const emptyState = document.getElementById("empty-state");
    const statusEl = document.getElementById("status-indicator");
    let ws;
    let reconnectTimer;

    function connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${location.host}/ws`);

        ws.onopen = () => {
            statusEl.textContent = "connected";
            statusEl.className = "connected";
            clearTimeout(reconnectTimer);
        };

        ws.onclose = () => {
            statusEl.textContent = "disconnected";
            statusEl.className = "disconnected";
            reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = () => ws.close();

        ws.onmessage = (event) => {
            const state = JSON.parse(event.data);
            render(state);
        };
    }

    function formatDuration(seconds) {
        if (!seconds) return "";
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, "0")}`;
    }

    function render(state) {
        const entries = Object.entries(state);

        if (entries.length === 0) {
            emptyState.style.display = "";
            // Remove player cards but keep empty state
            Array.from(playersEl.querySelectorAll(".player-card")).forEach(el => el.remove());
            return;
        }

        emptyState.style.display = "none";

        // Track existing cards
        const existingCards = new Set();
        playersEl.querySelectorAll(".player-card").forEach(el => {
            existingCards.add(el.dataset.speakerId);
        });

        const activeSpeakers = new Set();

        for (const [speakerId, info] of entries) {
            activeSpeakers.add(speakerId);
            let card = playersEl.querySelector(`[data-speaker-id="${speakerId}"]`);

            if (!card) {
                card = document.createElement("div");
                card.className = "player-card";
                card.dataset.speakerId = speakerId;
                playersEl.appendChild(card);
            }

            card.className = `player-card${info.is_playing ? " playing" : ""}`;

            const artHtml = info.album_art_url
                ? `<img class="album-art" src="${info.album_art_url}" alt="Album art" onerror="this.outerHTML='<div class=\\'album-art-placeholder\\'>♪</div>'">`
                : `<div class="album-art-placeholder">♪</div>`;

            const durationHtml = info.duration
                ? `<span class="duration">${formatDuration(info.duration)}</span>`
                : "";

            const scrobbleClass = info.scrobbled ? "scrobbled" : "pending";
            const scrobbleText = info.scrobbled ? "scrobbled" : "pending";

            const pausedHtml = !info.is_playing ? `<span class="paused-indicator">paused</span>` : "";

            card.innerHTML = `
                ${artHtml}
                <div class="track-info">
                    <div class="track-title">${escapeHtml(info.title)}</div>
                    <div class="track-artist">${escapeHtml(info.artist)}</div>
                    ${info.album ? `<div class="track-album">${escapeHtml(info.album)}</div>` : ""}
                    <div class="track-meta">
                        <span class="speaker-name">${escapeHtml(info.speaker_name)}</span>
                        <span class="scrobble-badge ${scrobbleClass}">${scrobbleText}</span>
                        ${durationHtml}
                        ${pausedHtml}
                    </div>
                </div>
            `;
        }

        // Remove cards for speakers no longer playing
        playersEl.querySelectorAll(".player-card").forEach(el => {
            if (!activeSpeakers.has(el.dataset.speakerId)) {
                el.remove();
            }
        });
    }

    function escapeHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    connect();
})();
