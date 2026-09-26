const CACHE = 'bot-v3';
const OFFLINE = '/offline';

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE)
            .then(c => c.add(OFFLINE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(
                keys.filter(k => k !== CACHE).map(k => caches.delete(k))
            ))
            .then(() => self.clients.claim())
    );
});

// Only page navigations are handled, and only a network failure shows the
// offline page -- server responses (404, 500, redirects) pass through as-is.
self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET' || e.request.mode !== 'navigate') return;
    e.respondWith(
        fetch(e.request).catch(() =>
            caches.match(OFFLINE).then(r => r || Response.error())
        )
    );
});
