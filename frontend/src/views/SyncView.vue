<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { call } from '../lib/api'
import { fmtDateTime, fmtDate } from '../lib/util'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const router = useRouter()
const data = ref(null)
const busy = ref('')
const onlyErrors = ref(false)

async function load() {
  try {
    data.value = await call('sync_status', { limit: 80, only_errors: onlyErrors.value ? 1 : 0 })
  } catch (e) {
    app.notify(e.message, 'error')
  }
}
onMounted(load)

async function simulate(kind) {
  busy.value = kind
  try {
    const r = await call('sandbox_simulate', { kind }, { post: true })
    if (kind === 'message') {
      app.notify(`Pesan dari ${r.guest_name}: “${r.message}”`, 'success')
      app.refreshUnread()
      return router.push(`/messages/${r.booking_id}`)
    }
    app.notify(`${kind === 'new' ? 'Booking baru' : 'Dibatalkan'}: ${r.guest_name} · #${r.booking_id}${r.sales_order ? ' · ' + r.sales_order : ''}`, 'success')
    await load()
    if (kind === 'new') router.push(`/booking/${r.booking_id}`)
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}

async function run(full) {
  busy.value = full ? 'full' : 'now'
  try {
    const r = await call('sync_now', { full: full ? 1 : 0 }, { post: true })
    if (r.queued) app.notify('Tarik ulang semua dijadwalkan di latar', 'success')
    else if (r.skipped) app.notify(r.message, 'warn')
    else app.notify(`${r.fetched} diambil · ${r.created} baru · ${r.updated} berubah · ${r.errors} gagal`, r.errors ? 'warn' : 'success')
    await load()
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <AppBar title="Sinkronisasi" back />
  <div class="content">
    <div class="wrap narrow">
      <div class="card">
        <div class="row between">
          <div>
            <div class="small muted">Beds24</div>
            <div class="conn" :class="data && data.connected ? 'ok' : 'bad'">
              <Icon :name="data && data.connected ? 'ok' : 'warn'" /> {{ data ? (data.connected ? data.connection_status || 'Terhubung' : 'Belum terhubung') : '…' }}
            </div>
          </div>
          <span class="badge-status" :class="data && data.enable_sync ? 's-confirmed' : 's-expected'">{{ data && data.enable_sync ? 'Otomatis tiap 5 menit' : 'Otomatis mati' }}</span>
        </div>
        <dl class="kv mt12">
          <dt>Sinkron terakhir</dt><dd>{{ data ? fmtDateTime(data.last_pull) : '—' }}</dd>
          <dt>Hasil</dt><dd>{{ (data && data.last_pull_result) || '—' }}</dd>
        </dl>
        <div class="row mt12">
          <button class="btn brand grow" :disabled="!!busy || !app.online" @click="run(false)"><Icon name="sync" :spin="busy === 'now'" /> Sinkron sekarang</button>
          <button v-if="app.user.is_manager" class="btn" :disabled="!!busy || !app.online" @click="run(true)">Tarik ulang semua</button>
        </div>
      </div>

      <div v-if="data && data.sandbox" class="card sandbox mt12">
        <div class="row" style="gap: 8px"><Icon name="flask" /><b>Mode Sandbox</b></div>
        <p class="small muted" style="margin: 6px 0 10px">Data contoh, bukan Beds24 asli. Coba seolah-olah ada booking atau pesan tamu masuk dari OTA (Booking.com, Airbnb, dll.).</p>
        <div class="row">
          <button class="btn ok grow" :disabled="!!busy || !app.online" @click="simulate('new')"><Icon :name="busy === 'new' ? 'sync' : 'newcal'" :spin="busy === 'new'" /> Booking OTA baru</button>
          <button class="btn grow" :disabled="!!busy || !app.online" @click="simulate('cancel')"><Icon :name="busy === 'cancel' ? 'sync' : 'cancel'" :spin="busy === 'cancel'" /> OTA batal</button>
        </div>
        <button v-if="app.can('messages')" class="btn block mt8" :disabled="!!busy || !app.online" @click="simulate('message')"><Icon :name="busy === 'message' ? 'sync' : 'messages'" :spin="busy === 'message'" /> Pesan dari tamu</button>
      </div>

      <template v-if="data && data.attention.length">
        <div class="section-title">Perlu perhatian · {{ data.attention.length }}</div>
        <button v-for="a in data.attention" :key="a.booking_id" class="list-item att" @click="router.push(`/booking/${a.booking_id}`)">
          <span class="lead-icon warnbg"><Icon name="warn" /></span>
          <div class="grow">
            <div class="row between"><b class="truncate">{{ a.guest_name }}</b><span class="tiny muted">#{{ a.booking_id }}</span></div>
            <div class="tiny muted">{{ fmtDate(a.arrival) }} · {{ a.sync_state === 'Error' ? 'Gagal' : 'Tinjau' }}</div>
            <div class="small errtxt">{{ a.sync_error }}</div>
          </div>
        </button>
      </template>

      <div class="row between section-title">
        <span>Log</span>
        <label class="row small" style="gap: 6px; text-transform: none; letter-spacing: 0">
          Hanya error <span class="switch"><input type="checkbox" v-model="onlyErrors" @change="load" /><span class="slider"></span></span>
        </label>
      </div>
      <div class="card">
        <div v-if="data && !data.log.length" class="small muted">Belum ada log.</div>
        <div v-for="(l, i) in data ? data.log : []" :key="i" class="log-row">
          <span class="dot" :class="l.status === 'Error' ? 'err' : l.status === 'Dilewati' ? 'skip' : ''"></span>
          <div class="grow">
            <div class="small"><b>{{ l.event }}</b> <span class="muted">· {{ l.direction }}</span><span v-if="l.booking_id" class="muted"> · #{{ l.booking_id }}</span></div>
            <div class="tiny muted">{{ fmtDateTime(l.creation) }} · {{ l.user }}</div>
            <div v-if="l.message" class="tiny" :class="{ errtxt: l.status === 'Error' }">{{ l.message }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conn { font-weight: 800; font-size: 17px; display: flex; gap: 6px; align-items: center; }
.conn.ok { color: var(--ok); } .conn.bad { color: var(--danger); }
.kv { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; margin: 0; font-size: 14px; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; text-align: right; }
.att { width: 100%; border: 0; text-align: left; color: var(--ink); }
.sandbox { border: 1px dashed #d97706; }
.sandbox .ico { color: #d97706; }
.warnbg { background: var(--warn); }
.errtxt { color: var(--danger); }
.log-row { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.log-row:last-child { border-bottom: 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); margin-top: 6px; flex: none; }
.dot.err { background: var(--danger); } .dot.skip { background: var(--muted); }
</style>
