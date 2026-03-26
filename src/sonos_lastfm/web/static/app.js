(() => {
    const playersEl = document.getElementById("players");
    const emptyState = document.getElementById("empty-state");
    const statusEl = document.getElementById("status-indicator");
    const statusText = statusEl.querySelector(".status-text");
    let ws;
    let reconnectTimer;

    function connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${location.host}/ws`);

        ws.onopen = () => {
            statusText.textContent = "live";
            statusEl.className = "status connected";
            clearTimeout(reconnectTimer);
        };

        ws.onclose = () => {
            statusText.textContent = "disconnected";
            statusEl.className = "status disconnected";
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

    const speakerIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><circle cx="12" cy="14" r="4"/><line x1="12" y1="6" x2="12.01" y2="6"/></svg>`;

    const placeholderSvg = `<svg viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="24" stroke="currentColor" stroke-width="1.5"/><circle cx="32" cy="32" r="14" stroke="currentColor" stroke-width="1"/><circle cx="32" cy="32" r="3" fill="currentColor"/></svg>`;

    function render(state) {
        const entries = Object.entries(state);

        if (entries.length === 0) {
            emptyState.style.display = "";
            Array.from(playersEl.querySelectorAll(".player-card")).forEach(el => {
                el.style.opacity = "0";
                el.style.transform = "translateY(8px)";
                setTimeout(() => el.remove(), 300);
            });
            return;
        }

        emptyState.style.display = "none";

        const activeSpeakers = new Set();

        for (const [speakerId, info] of entries) {
            activeSpeakers.add(speakerId);
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
                ? `<img class="album-art" src="${escapeAttr(info.album_art_url)}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'album-art-placeholder\\'>${placeholderSvg}</div><div class=\\'art-glow\\'></div>'">`
                : `<div class="album-art-placeholder">${placeholderSvg}</div>`;

            const durationHtml = info.duration
                ? `<span class="duration-label">${formatDuration(info.duration)}</span>`
                : "";

            const scrobbleClass = info.scrobbled ? "scrobbled" : "pending";
            const scrobbleText = info.scrobbled ? "scrobbled" : "listening";

            const barsHtml = `<div class="now-playing-bars"><span></span><span></span><span></span><span></span></div>`;

            const pausedHtml = !info.is_playing
                ? `<span class="paused-label">paused</span>`
                : "";

            card.innerHTML = `
                <div class="art-container">
                    ${artHtml}
                    <div class="art-glow"></div>
                </div>
                <div class="track-info">
                    <div class="track-title">${escapeHtml(info.title)}</div>
                    <div class="track-artist">${escapeHtml(info.artist)}</div>
                    ${info.album ? `<div class="track-album">${escapeHtml(info.album)}</div>` : ""}
                    <div class="track-meta">
                        <span class="speaker-label">${speakerIcon} ${escapeHtml(info.speaker_name)}</span>
                        <span class="scrobble-badge ${scrobbleClass}"><span class="scrobble-dot"></span>${scrobbleText}</span>
                        ${barsHtml}
                        ${durationHtml}
                        ${pausedHtml}
                    </div>
                </div>
            `;
        }

        // Remove cards for speakers no longer playing
        playersEl.querySelectorAll(".player-card").forEach(el => {
            if (!activeSpeakers.has(el.dataset.speakerId)) {
                el.style.opacity = "0";
                el.style.transform = "translateY(8px)";
                setTimeout(() => el.remove(), 300);
            }
        });
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

    connect();
})();
