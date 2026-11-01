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

// Urutan menu = urutan di navigasi. `phone` = tampil di tab bawah HP (maks 5 termasuk Lainnya).
export const NAV = [
  { key: 'dashboard', to: '/', name: 'home', label: 'Beranda', icon: 'home', phone: true },
  { key: 'calendar', to: '/calendar', name: 'calendar', label: 'Kalender', icon: 'calendar', phone: true },
  { key: 'bookings', to: '/bookings', name: 'bookings', label: 'Booking', icon: 'list', phone: true },
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
      installPrompt: null
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
    navItems() {
      return NAV.filter((n) => this.can(n.key))
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
        if (this.prefs.property && !boot.properties.some((p) => p.property_id === this.prefs.property)) {
          this.setPref('property', '')
        }
      } catch (e) {
        // offline → pakai bootstrap terakhir; izin ditolak → tampilkan pesan
        if (!this.boot || (e.status && e.status !== 0 && e.status < 500)) this.bootError = e.message
      } finally {
        this.loaded = true
      }
    },
    setPref(key, value) {
      this.prefs = { ...this.prefs, [key]: value }
      writeJSON(LS_PREF, this.prefs)
      if (key === 'theme') this.applyTheme()
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
    }
  }
})
