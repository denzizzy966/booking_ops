import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import { useApp } from './stores/app'
import Icon from './components/Icon.vue'

const app = createApp(App)
app.use(createPinia())
app.component('Icon', Icon)

const store = useApp()
store.applyTheme()
store.applyRail()
store.bindNetwork()

// Splash (index.html) dilepas setelah app tampil.
function hideSplash() {
  const s = document.getElementById('splash')
  if (!s) return
  s.classList.add('hide')
  setTimeout(() => s.remove(), 400)
}

// Belum login (halaman disajikan bench untuk Guest) → langsung layar login PWA.
// Sudah login → bootstrap (menu per role, properti, kamar) dulu supaya router guard tahu menu mana yang boleh.
const servedByBench = !!window.bookingops_user && !String(window.bookingops_user).includes('{{')
const start = servedByBench && window.bookingops_user === 'Guest' ? Promise.resolve((store.needLogin = true)) : store.load()
start.finally(() => {
  app.use(router)
  app.mount('#app')
  requestAnimationFrame(hideSplash)
})

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  store.installPrompt = e
})
window.addEventListener('appinstalled', () => {
  store.installPrompt = null
  store.isStandalone = true
})

// Service worker hanya saat disajikan bench (scope tanpa slash akhir, sama seperti Stock Ops).
if (servedByBench && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/booking_ops_sw.js', { scope: '/booking_ops' }).catch(() => {})
}
