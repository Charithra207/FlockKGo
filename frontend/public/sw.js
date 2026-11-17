/* FlockGo service worker: installable app + offline fallback.
 * - Pages: network first, fall back to the cached app shell when offline.
 * - Built assets (/assets/*): cache first (file names change every build).
 * - Spot / profile / meta API reads: network first, cached copy when offline,
 *   so places you've opened still work in the hills with no signal.
 * - Map tiles you've already seen: cache first, capped.
 */
const VERSION = 'v1'
const SHELL = `flockgo-shell-${VERSION}`
const ASSETS = `flockgo-assets-${VERSION}`
const DATA = `flockgo-data-${VERSION}`
const TILES = `flockgo-tiles-${VERSION}`
const MAX_TILES = 600
const MAX_DATA = 300

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/', '/manifest.webmanifest', '/icon-192.png'])).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  const keep = [SHELL, ASSETS, DATA, TILES]
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('flockgo-') && !keep.includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName)
  const keys = await cache.keys()
  for (let i = 0; i < keys.length - max; i++) await cache.delete(keys[i])
}

async function networkFirst(request, cacheName, max) {
  const cache = await caches.open(cacheName)
  try {
    const res = await fetch(request)
    if (res.ok) {
      cache.put(request, res.clone())
      if (max) trim(cacheName, max)
    }
    return res
  } catch (err) {
    const hit = await cache.match(request)
    if (hit) return hit
    throw err
  }
}

async function cacheFirst(request, cacheName, max) {
  const cache = await caches.open(cacheName)
  const hit = await cache.match(request)
  if (hit) return hit
  const res = await fetch(request)
  if (res.ok || res.type === 'opaque') {
    cache.put(request, res.clone())
    if (max) trim(cacheName, max)
  }
  return res
}

const DATA_PATHS = [/\/v1\/spots\/meta$/, /\/v1\/spots\/[0-9a-f-]{36}$/, /\/v1\/users\/[^/]+$/, /\/v1\/places\/destinations$/, /\/v1\/photos\//]

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then((res) => {
        caches.open(SHELL).then((c) => c.put('/', res.clone()))
        return res
      }).catch(() => caches.match('/')),
    )
    return
  }
  if (url.origin === self.location.origin && url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(req, ASSETS))
    return
  }
  if (/(^|\.)tile\.openstreetmap\.org$/.test(url.hostname)) {
    event.respondWith(cacheFirst(req, TILES, MAX_TILES))
    return
  }
  if (DATA_PATHS.some((re) => re.test(url.pathname))) {
    event.respondWith(networkFirst(req, DATA, MAX_DATA))
  }
})
