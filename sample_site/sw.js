self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open('fox-store').then((cache) => cache.addAll([
            '/',
            // '/index.html',
            // '/new.html',
        ])),
    );
});

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);

    if (!(url.searchParams.get('share-target'))) {
        return
    }

    e.respondWith(Response.redirect('/new.html'));

    e.waitUntil(async function () {
        const data = await e.request.formData();
        const client = await self.clients.get(e.resultingClientId);
        const files = data.getAll('files');
        client.postMessage({ files });
    }());
});

