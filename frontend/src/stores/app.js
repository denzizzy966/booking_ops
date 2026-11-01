import { defineStore } from 'pinia'
import { call } from '../lib/api'

const LS_BOOT = 'bookingops.bootstrap'
const LS_PREF = 'bookingops.prefs'

function readJSON(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null') || fallback
  } catch {
    return fallback
  }
}
function writeJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* abaikan */
  }
}

// Urutan menu = urutan di navigasi. `phone` = kandidat tab bawah HP; 4 pertama yang boleh diakses
// tampil di tab (+ Lainnya), sisanya pindah ke halaman Lainnya.
export const NAV = [
  { key: 'dashboard', to: '/', name: 'home', label: 'Beranda', icon: 'home', phone: true },
  { key: 'calendar', to: '/calendar', name: 'calendar', label: 'Kalender', icon: 'calendar', phone: true },
  { key: 'bookings', to: '/bookings', name: 'bookings', label: 'Booking', icon: 'list', phone: true },
  { key: 'messages', to: '/messages', name: 'messages', label: 'Pesan', icon: 'messages', phone: true },
  { key: 'new_booking', to: '/new', name: 'new', label: 'Booking Baru', short: 'Baru', icon: 'plus', phone: true },
  { key: 'availability', to: '/rates', name: 'rates', label: 'Ketersediaan', icon: 'tags' },
  { key: 'reports', to: '/reports', name: 'reports', label: 'Laporan', icon: 'chart' },
  { key: 'sync', to: '/sync', name: 'sync', label: 'Sinkronisasi', icon: 'sync' }
]

export const useApp = defineStore('app', {
  state: () => {
    const boot = readJSON(LS_BOOT, null)
    const prefs = readJSON(LS_PREF, { theme: 'system', property: '' })
    return {
      boot,
      loaded: false,
      bootError: '',
      prefs,
      online: navigator.onLine,
      toast: null,
      installPrompt: null,
      unread: (boot && boot.unread_messages) || 0,
      needLogin: false,
      // PWA: sudah dibuka dari layar utama? iPhone/iPad (tanpa tombol pasang otomatis)?
      isStandalone: window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true,
      isIOS: /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1),
      winWide: window.innerWidth >= 1100
    }
  },
  getters: {
    user: (s) => (s.boot && s.boot.user) || {},
    menus: (s) => (s.boot && s.boot.menus) || {},
    can: (s) => (key) => !!(s.boot && s.boot.menus && s.boot.menus[key]),
    properties: (s) => (s.boot && s.boot.properties) || [],
    rooms: (s) => (s.boot && s.boot.rooms) || [],
    settings: (s) => (s.boot && s.boot.settings) || {},
    currency: (s) => (s.boot && s.boot.settings && s.boot.settings.currency) || 'IDR',
    property: (s) => s.prefs.property || '',
    // Sidebar tablet/desktop: lebar (ikon + label) atau ringkas (ikon saja). Pilihan pengguna
    // (prefs.rail) menang; tanpa pilihan → otomatis menurut lebar layar (≥1100 px lebar).
    railWide: (s) => s.prefs.rail === 'wide' || (s.prefs.rail !== 'compact' && s.winWide),
    navItems() {
      return NAV.filter((n) => this.can(n.key))
    },
    phoneNav() {
      return this.navItems.filter((n) => n.phone).slice(0, 4)
    },
    // Menu yang tidak muat di tab bawah HP → halaman Lainnya.
    moreNav() {
      const shown = new Set(this.phoneNav.map((n) => n.key))
      return this.navItems.filter((n) => !shown.has(n.key))
    },
    firstRoute() {
      const n = this.navItems[0]
      return n ? n.to : '/more'
    },
    roomsFor() {
      return (property) => this.rooms.filter((r) => !property || r.property === property)
    },
    roomName() {
      return (id) => (this.rooms.find((r) => r.room_id === id) || {}).room_name || id || '—'
    },
    propertyName() {
      return (id) => (this.properties.find((p) => p.property_id === id) || {}).property_name || id || ''
    },
    currencyFor() {
      return (property) => (this.properties.find((p) => p.property_id === property) || {}).currency || this.currency
    }
  },
  actions: {
    async load() {
      try {
        const boot = await call('get_bootstrap')
        this.boot = boot
        this.bootError = ''
        writeJSON(LS_BOOT, boot)
        this.unread = boot.unread_messages || 0
        if (this.prefs.property && !boot.properties.some((p) => p.property_id === this.prefs.property)) {
          this.setPref('property', '')
        }
      } catch (e) {
        // Sesi habis / belum login → layar login. Offline → bootstrap terakhir. Izin ditolak → pesan.
        if (e.status === 401 || (e.status === 403 && /login/i.test(e.message))) {
          this.needLogin = true
          this.boot = null
        } else if (!this.boot || (e.status && e.status !== 0 && e.status < 500)) this.bootError = e.message
      } finally {
        this.loaded = true
      }
    },
    async promptInstall() {
      const p = this.installPrompt
      if (!p) return false
      p.prompt()
      const { outcome } = await p.userChoice
      this.installPrompt = null
      return outcome === 'accepted'
    },
    async logout() {
      try {
        await call('frappe.handler.logout', {}, { post: true })
      } catch {
        /* tetap keluar */
      }
      localStorage.removeItem(LS_BOOT)
      window.location.replace('/booking_ops')
    },
    // Badge menu Pesan: dipanggil berkala (App.vue) dan setelah membaca/membalas.
    async refreshUnread() {
      if (!this.can('messages') || !this.online || document.hidden) return
      try {
        this.unread = (await call('unread_count')) || 0
      } catch {
        /* abaikan: badge saja */
      }
    },
    setPref(key, value) {
      this.prefs = { ...this.prefs, [key]: value }
      writeJSON(LS_PREF, this.prefs)
      if (key === 'theme') this.applyTheme()
    },
    applyRail() {
      // Tanpa pilihan → atribut kosong, CSS media query yang menentukan (seperti sebelumnya).
      const r = this.prefs.rail
      if (r === 'wide' || r === 'compact') document.documentElement.dataset.rail = r
      else delete document.documentElement.dataset.rail
    },
    toggleRail() {
      this.setPref('rail', this.railWide ? 'compact' : 'wide')
      this.applyRail()
    },
    applyTheme() {
      const t = this.prefs.theme || 'system'
      const dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    },
    notify(message, kind = 'info') {
      this.toast = { message, kind, id: Date.now() }
      const id = this.toast.id
      setTimeout(() => {
        if (this.toast && this.toast.id === id) this.toast = null
      }, kind === 'error' ? 5000 : 2600)
    },
    bindNetwork() {
      window.addEventListener('online', () => (this.online = true))
      window.addEventListener('offline', () => (this.online = false))
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => this.applyTheme())
      window.addEventListener('resize', () => {
        const w = window.innerWidth >= 1100
        if (w !== this.winWide) {
          this.winWide = w
          this.applyRail()
        }
      })
    }
  }
})
