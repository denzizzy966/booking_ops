// Service worker Booking Ops — app-shell + aset ter-cache supaya app bisa dibuka offline.
// Disajikan dari root (/booking_ops_sw.js) agar scope "/booking_ops" (tanpa slash akhir) diizinkan.
// Data (/api) tidak di-cache di sini; app menyimpan salinan terakhir sendiri (localStorage).

const CACHE = 'bookingops-v2'
const APP_SHELL = '/booking_ops'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k.startsWith('bookingops-') && k !== CACHE).map((k) => caches.delete(k)))
      await self.clients.claim()
    })()
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  if (req.mode === 'navigate' && url.pathname.startsWith(APP_SHELL)) {
    e.respondWith(
      (async () => {
        try {
          const fresh = await fetch(req)
          const c = await caches.open(CACHE)
          c.put(APP_SHELL, fresh.clone())
          return fresh
        } catch {
          return (await caches.match(APP_SHELL)) || Response.error()
        }
      })()
    )
    return
  }

  if (url.pathname.startsWith('/assets/booking_ops/')) {
    e.respondWith(
      (async () => {
        const c = await caches.open(CACHE)
        const cached = await c.match(req)
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) c.put(req, res.clone())
            return res
          })
          .catch(() => null)
        return cached || (await network) || Response.error()
      })()
    )
  }
})
