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
store.bindNetwork()

// Bootstrap (menu per role, properti, kamar) dulu → router guard tahu menu mana yang boleh.
store.load().finally(() => {
  app.use(router)
  app.mount('#app')
})

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  store.installPrompt = e
})

// Service worker hanya saat disajikan bench (scope tanpa slash akhir, sama seperti Stock Ops).
const servedByBench = !!window.bookingops_user && !String(window.bookingops_user).includes('{{')
if (servedByBench && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/booking_ops_sw.js', { scope: '/booking_ops' }).catch(() => {})
}
