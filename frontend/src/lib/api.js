// Akses API Frappe. Di-serve bench: same-origin + cookie sesi + CSRF (POST).
// Dev (vite): diproksikan; token disuntik proxy Node.
const PREFIX = 'booking_ops.api.'

function csrf() {
  const t = window.csrf_token || ''
  return t && !t.includes('{{') ? t : ''
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

function serverMessage(json) {
  try {
    const msgs = json._server_messages ? JSON.parse(json._server_messages) : []
    const txt = msgs.map((m) => (typeof m === 'string' ? JSON.parse(m).message : m.message)).join(' · ')
    // pesan Frappe bisa ber-HTML (mis. <b>) → teks polos
    return txt.replace(/<[^>]+>/g, '')
  } catch {
    return ''
  }
}

export async function call(method, params = {}, { post = false } = {}) {
  const full = method.includes('.') ? method : PREFIX + method
  let url = `/api/method/${full}`
  const opts = { method: post ? 'POST' : 'GET', headers: { Accept: 'application/json' }, credentials: 'same-origin' }
  if (post) {
    opts.headers['Content-Type'] = 'application/json'
    if (csrf()) opts.headers['X-Frappe-CSRF-Token'] = csrf()
    opts.body = JSON.stringify(params)
  } else {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, typeof v === 'object' ? JSON.stringify(v) : v)
    }
    if (qs.toString()) url += `?${qs}`
  }
  let res
  try {
    res = await fetch(url, opts)
  } catch {
    throw new ApiError('Tidak ada koneksi ke server.', 0)
  }
  const text = await res.text()
  let json = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    let msg = (json && (serverMessage(json) || json.message)) || `HTTP ${res.status}`
    if (res.status === 403 && !serverMessage(json || {})) msg = 'Sesi habis atau akses ditolak. Silakan login ulang.'
    throw new ApiError(typeof msg === 'string' ? msg : 'Permintaan gagal', res.status)
  }
  return json ? json.message : null
}

// GET dengan salinan terakhir di localStorage: offline / server error → tampilkan data terakhir.
export async function cached(key, method, params = {}) {
  const k = `bookingops.cache.${key}`
  try {
    const data = await call(method, params)
    try {
      localStorage.setItem(k, JSON.stringify({ at: Date.now(), data }))
    } catch {
      /* kuota penuh — abaikan */
    }
    return { data, stale: false }
  } catch (e) {
    if (e.status && e.status < 500) throw e // izin/validasi: jangan disembunyikan
    let hit = null
    try {
      hit = JSON.parse(localStorage.getItem(k) || 'null')
    } catch {
      hit = null
    }
    if (!hit) throw e
    return { data: hit.data, stale: true, at: hit.at }
  }
}
