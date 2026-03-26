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

    const heartOutline = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"></path></svg>`;

    const heartFilled = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"></path></svg>`;

    // ── Love/Unlove ──

    const lovedTracks = {};  // key: "artist|title" -> boolean

    function loveKey(artist, title) {
        return `${artist}|${title}`;
    }

    function checkLoved(artist, title) {
        const key = loveKey(artist, title);
        if (key in lovedTracks) return;
        lovedTracks[key] = null; // loading
        fetch(`/api/loved?artist=${encodeURIComponent(artist)}&title=${encodeURIComponent(title)}`)
            .then(r => r.json())
            .then(data => {
                lovedTracks[key] = data.loved;
                updateHeartButtons();
            })
            .catch(() => {});
    }

    function toggleLove(artist, title) {
        const key = loveKey(artist, title);
        const isLoved = lovedTracks[key];
        const endpoint = isLoved ? "/api/unlove" : "/api/love";

        // Optimistic update
        lovedTracks[key] = !isLoved;
        updateHeartButtons();

        fetch(`${endpoint}?artist=${encodeURIComponent(artist)}&title=${encodeURIComponent(title)}`, { method: "POST" })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    lovedTracks[key] = isLoved; // revert
                    updateHeartButtons();
                }
            })
            .catch(() => {
                lovedTracks[key] = isLoved; // revert
                updateHeartButtons();
            });
    }

    function updateHeartButtons() {
        document.querySelectorAll(".heart-btn").forEach(btn => {
            const key = loveKey(btn.dataset.artist, btn.dataset.title);
            const loved = lovedTracks[key];
            btn.innerHTML = loved ? heartFilled : heartOutline;
            btn.classList.toggle("loved", !!loved);
        });
    }

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

            const heartKey = loveKey(info.artist, info.title);
            const isLoved = lovedTracks[heartKey];
            const heartHtml = info.artist ? `<button class="heart-btn${isLoved ? " loved" : ""}" data-artist="${escapeAttr(info.artist)}" data-title="${escapeAttr(info.title)}">${isLoved ? heartFilled : heartOutline}</button>` : "";

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
                        ${heartHtml}
                        ${eqBars}
                    </div>
                </div>
            `;

            // Check loved status for new tracks
            if (info.artist) checkLoved(info.artist, info.title);
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

    const spinner = `<div class="loading"><div class="loading-spinner"></div><span>Loading...</span></div>`;
    let historyFirstLoad = true;

    function fetchHistory() {
        if (historyFirstLoad) {
            historySection.style.display = "";
            historyList.innerHTML = spinner;
        }
        fetch("/api/history?limit=5")
            .then(r => r.json())
            .then(data => { historyFirstLoad = false; renderHistory(data); })
            .catch(() => { historyFirstLoad = false; });
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

    // Heart button click delegation
    playersEl.addEventListener("click", (e) => {
        const btn = e.target.closest(".heart-btn");
        if (btn) {
            e.preventDefault();
            toggleLove(btn.dataset.artist, btn.dataset.title);
        }
    });

    // Fetch history on load and periodically
    fetchHistory();
    historyTimer = setInterval(fetchHistory, 30000);

    // ── Tabs ──

    const tabs = document.querySelectorAll(".tab");
    const tabContents = document.querySelectorAll(".tab-content");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;

            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            tabContents.forEach(tc => tc.classList.remove("active"));
            document.getElementById(`tab-${target}`).classList.add("active");

            if (target === "stats" && !statsLoaded) {
                fetchStats();
            }
        });
    });

    // ── Stats ──

    const statsArtists = document.getElementById("stats-artists");
    const statsAlbums = document.getElementById("stats-albums");
    const statsTracks = document.getElementById("stats-tracks");
    const statsTotalCount = document.getElementById("stats-total-count");
    const periodBtns = document.querySelectorAll(".period-btn");
    let currentPeriod = "7day";
    let statsLoaded = false;

    periodBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            periodBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentPeriod = btn.dataset.period;
            fetchStats();
        });
    });

    function fetchStats() {
        statsArtists.innerHTML = spinner;
        statsAlbums.innerHTML = "";
        statsTracks.innerHTML = "";
        statsTotalCount.textContent = "--";

        fetch(`/api/stats?period=${currentPeriod}&limit=10`)
            .then(r => r.json())
            .then(renderStats)
            .catch(() => {
                statsArtists.innerHTML = `<div class="stats-empty">Failed to load stats</div>`;
            });
    }

    function renderStats(data) {
        statsLoaded = true;

        statsTotalCount.textContent = data.total_scrobbles.toLocaleString();

        statsArtists.innerHTML = renderStatsList(data.top_artists, item =>
            lastfmLink(lastfmArtistUrl(item.name), item.name, "lastfm-link stats-row-name")
        );

        statsAlbums.innerHTML = renderStatsList(data.top_albums, item => `
            <span class="stats-row-name">${lastfmLink(lastfmAlbumUrl(item.artist, item.name), item.name, "lastfm-link")}</span>
            <span class="stats-row-sub">${lastfmLink(lastfmArtistUrl(item.artist), item.artist, "lastfm-link")}</span>
        `);

        statsTracks.innerHTML = renderStatsList(data.top_tracks, item => `
            <span class="stats-row-name">${lastfmLink(lastfmTrackUrl(item.artist, item.name), item.name, "lastfm-link")}</span>
            <span class="stats-row-sub">${lastfmLink(lastfmArtistUrl(item.artist), item.artist, "lastfm-link")}</span>
        `);
    }

    function renderStatsList(items, renderName) {
        if (!items || items.length === 0) {
            return `<div class="stats-empty">No data for this period</div>`;
        }

        const maxPlays = items[0].plays;

        return items.map((item, i) => {
            const pct = maxPlays > 0 ? (item.plays / maxPlays) * 100 : 0;
            return `
                <div class="stats-row">
                    <span class="stats-rank">${i + 1}</span>
                    <div class="stats-bar-wrap">
                        <div class="stats-row-info">
                            <div class="stats-row-name-wrap">${renderName(item)}</div>
                            <span class="stats-row-plays">${item.plays} plays</span>
                        </div>
                        <div class="stats-bar">
                            <div class="stats-bar-fill" style="width:${pct}%"></div>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    // ── Theme Toggle ──

    const themeToggle = document.getElementById("theme-toggle");
    const iconDark = document.getElementById("theme-icon-dark");
    const iconLight = document.getElementById("theme-icon-light");

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
        iconDark.style.display = theme === "dark" ? "" : "none";
        iconLight.style.display = theme === "light" ? "" : "none";
    }

    // Load saved theme or respect system preference
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
        setTheme(savedTheme);
    } else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
        setTheme("light");
    }

    themeToggle.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        setTheme(current === "dark" ? "light" : "dark");
    });

    // ── Service Worker ──

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/sw.js").catch(() => {});
    }

    connect();
})();
