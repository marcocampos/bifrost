const CACHE_NAME = "sonos-lastfm-v1";
const SHELL_ASSETS = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/manifest.json",
    "/static/icon-192.svg",
    "/static/icon-512.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // API calls and WebSocket: always go to network
    if (url.pathname.startsWith("/api/") || url.pathname === "/ws") {
        return;
    }

    // App shell: cache first, fallback to network
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return fetch(event.request).then((response) => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                }
                return response;
            });
        })
    );
});
