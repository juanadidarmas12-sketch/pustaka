/* Pustaka service worker.
   Strategi:
   - Kode aplikasi + data katalog (HTML/JS/CSS/manifest/index.json/authors.json) = NETWORK-FIRST
     → saat online selalu dapat versi terbaru; cache hanya cadangan offline. Ini mencegah
       "app nyangkut di versi lama" pada PWA terinstal.
   - Isi buku (books/<id>.json), ikon, foto Wikimedia, audio = CACHE-FIRST (konten stabil/besar). */
const CACHE = 'pustaka-v20';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './globe.js',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './books/index.json',
  './books/authors.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// izinkan halaman memaksa SW baru aktif segera
self.addEventListener('message', (e) => {
  if (e.data === 'skipWaiting') self.skipWaiting();
});

function isNetworkFirst(url, req) {
  if (req.mode === 'navigate') return true;
  if (url.origin !== location.origin) return false;
  const p = url.pathname;
  return (
    p.endsWith('/') ||
    p.endsWith('/index.html') ||
    p.endsWith('/app.js') ||
    p.endsWith('/globe.js') ||
    p.endsWith('/styles.css') ||
    p.endsWith('/manifest.webmanifest') ||
    p.endsWith('/sw.js') ||
    p.endsWith('/books/index.json') ||
    p.endsWith('/books/authors.json')
  );
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req, { cache: 'no-store' });
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req);
    if (hit) return hit;
    // fallback terakhir untuk navigasi → shell
    if (req.mode === 'navigate') {
      const shell = await cache.match('./index.html');
      if (shell) return shell;
    }
    throw err;
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  const url = new URL(req.url);
  if (res && res.ok && (url.origin === location.origin || res.type === 'basic' || res.type === 'cors')) {
    cache.put(req, res.clone());
  }
  return res;
}

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (isNetworkFirst(url, e.request)) {
    e.respondWith(networkFirst(e.request));
  } else {
    e.respondWith(cacheFirst(e.request));
  }
});
