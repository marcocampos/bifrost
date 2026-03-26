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
            render(JSON.parse(event.data));
        };
    }

    function formatDuration(seconds) {
        if (!seconds) return "";
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, "0")}`;
    }

    const musicIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;

    const speakerIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="12" cy="14" r="4"/><line x1="12" y1="6" x2="12.01" y2="6"/></svg>`;

    function render(state) {
        const entries = Object.entries(state);

        if (entries.length === 0) {
            emptyState.style.display = "";
            playersEl.querySelectorAll(".player-card").forEach(el => {
                el.style.opacity = "0";
                el.style.transform = "translateY(8px)";
                setTimeout(() => el.remove(), 250);
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
                ? `<img class="album-art" src="${escapeAttr(info.album_art_url)}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'album-art-placeholder\\'>${musicIcon}</div>'">`
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
                    <div class="track-title">${escapeHtml(info.title)}</div>
                    <div class="track-artist">${escapeHtml(info.artist)}</div>
                    ${info.album ? `<div class="track-album">${escapeHtml(info.album)}</div>` : ""}
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
