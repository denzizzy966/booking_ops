<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import AppBar from '../components/AppBar.vue'
import InstallBanner from '../components/InstallBanner.vue'

const app = useApp()
const router = useRouter()
// Menu yang tidak muat di tab bawah HP.
const extra = computed(() => app.moreNav)
const desc = {
  availability: 'Sisa kamar & harga per malam',
  reports: 'Pendapatan, okupansi, channel',
  sync: 'Status Beds24, log, coba ulang',
  new_booking: 'Buat booking langsung ke Beds24',
  messages: 'Pesan tamu dari OTA',
  calendar: 'Kamar × tanggal',
  bookings: 'Cari & kelola booking'
}

const logo = import.meta.env.BASE_URL + 'rmi-logo.png'
const logout = () => app.logout()
async function refresh() {
  await app.load()
  app.notify('Data master diperbarui', 'success')
}
</script>

<template>
  <AppBar title="Lainnya" />
  <div class="content">
    <div class="wrap narrow">
      <div class="card row">
        <span class="lead-icon me"><Icon name="user" /></span>
        <div class="grow">
          <b>{{ app.user.full_name }}</b>
          <div class="small muted truncate">{{ app.user.email }}</div>
          <div class="tiny muted">{{ app.user.is_manager ? 'Manajer' : 'Pengguna' }} · {{ app.properties.length }} properti · {{ app.rooms.length }} tipe kamar</div>
        </div>
      </div>

      <template v-if="extra.length">
        <div class="section-title">Menu</div>
        <button v-for="n in extra" :key="n.key" class="list-item menu" @click="router.push(n.to)">
          <span class="lead-icon brandbg"><Icon :name="n.icon" /></span>
          <div class="grow"><b>{{ n.label }}</b><div class="tiny muted">{{ desc[n.key] }}</div></div>
          <Icon name="right" class="muted" />
        </button>
      </template>

      <div class="section-title">Tampilan</div>
      <div class="card">
        <div class="seg">
          <button :class="{ active: app.prefs.theme === 'system' }" @click="app.setPref('theme', 'system')"><Icon name="desktop" /> Otomatis</button>
          <button :class="{ active: app.prefs.theme === 'light' }" @click="app.setPref('theme', 'light')"><Icon name="sun" /> Terang</button>
          <button :class="{ active: app.prefs.theme === 'dark' }" @click="app.setPref('theme', 'dark')"><Icon name="moon" /> Gelap</button>
        </div>
      </div>

      <div class="section-title">Aplikasi</div>
      <button class="list-item menu" @click="refresh"><span class="lead-icon graybg"><Icon name="sync" /></span><div class="grow"><b>Muat ulang data master</b><div class="tiny muted">Properti, kamar, hak akses menu</div></div></button>
      <InstallBanner force class="mb10" />
      <template v-if="app.user.is_manager">
        <a class="list-item menu" href="/app/booking-ops-settings" target="_blank"><span class="lead-icon graybg"><Icon name="settings" /></span><div class="grow"><b>Pengaturan Beds24 & role</b><div class="tiny muted">Booking Ops Settings (ERPNext)</div></div><Icon name="external" class="muted" /></a>
        <a class="list-item menu" href="/app/beds24-room" target="_blank"><span class="lead-icon graybg"><Icon name="bed" /></span><div class="grow"><b>Pemetaan kamar → item</b><div class="tiny muted">Beds24 Room</div></div><Icon name="external" class="muted" /></a>
      </template>
      <button class="list-item menu" @click="logout"><span class="lead-icon redbg"><Icon name="logout" /></span><div class="grow"><b>Keluar</b></div></button>
      <div class="brand-foot">
        <img :src="logo" alt="Real Magick Indonesia" />
        <p class="tiny muted center">Booking Ops 0.1 · Beds24 API v2 → ERPNext Sales Order</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.me { background: var(--brand); }
.menu { width: 100%; border: 0; text-align: left; color: var(--ink); cursor: pointer; }
.brandbg { background: var(--brand); } .graybg { background: #64748b; } .redbg { background: var(--danger); }
.center { text-align: center; }
.mb10 { margin-bottom: 10px; }
.brand-foot { margin-top: 22px; text-align: center; }
.brand-foot img { width: 84px; height: 84px; opacity: .9; }
:root[data-theme='dark'] .brand-foot img { opacity: .75; }
</style>
