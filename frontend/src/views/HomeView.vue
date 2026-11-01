<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { cached, call } from '../lib/api'
import { addDays, today, fmtDate, relDay, compact, pct } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import BookingCard from '../components/BookingCard.vue'
import InstallBanner from '../components/InstallBanner.vue'

const app = useApp()
const router = useRouter()
const date = ref(today())
const data = ref(null)
const stale = ref(false)
const loading = ref(false)
const tab = ref('arrivals')
const busy = ref('')

async function load() {
  loading.value = true
  try {
    const r = await cached(`dash.${app.property}.${date.value}`, 'dashboard', { date: date.value, property: app.property })
    data.value = r.data
    stale.value = r.stale
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}
watch(() => [date.value, app.property], load, { immediate: true })

const s = computed(() => (data.value && data.value.stats) || {})
const lists = computed(() => ({
  arrivals: (data.value && data.value.arrivals) || [],
  departures: (data.value && data.value.departures) || [],
  in_house: (data.value && data.value.in_house) || []
}))
const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 11 ? 'Selamat pagi' : h < 15 ? 'Selamat siang' : h < 18 ? 'Selamat sore' : 'Selamat malam'
})
const isToday = computed(() => date.value === today())

// Aksi cepat di kartu (check-in / check-out) tanpa membuka detail.
function quick(b, list) {
  if (!app.can('front_desk') || !isToday.value) return null
  if (list === 'arrivals' && b.stay_status === 'Expected') return { key: 'check_in', label: 'Check-in', icon: 'checkin', cls: 'ok' }
  if (list === 'departures' && b.stay_status === 'Checked In') return { key: 'check_out', label: 'Check-out', icon: 'checkout', cls: 'brand' }
  return null
}
async function run(b, action) {
  busy.value = b.booking_id
  try {
    await call('set_stay_status', { booking_id: b.booking_id, action: action.key }, { post: true })
    app.notify(`${action.label}: ${b.guest_name}`, 'success')
    await load()
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}
const open = (b) => router.push(`/booking/${b.booking_id}`)
</script>

<template>
  <AppBar title="Beranda" property-picker />
  <div class="content">
    <div class="wrap">
      <div class="hero">
        <div class="row between">
          <div>
            <div class="small" style="opacity: .85">{{ greeting }}, {{ (app.user.full_name || '').split(' ')[0] }}</div>
            <div class="hero-date">{{ relDay(date) }}</div>
            <div class="small" style="opacity: .85">{{ fmtDate(date, { year: true }) }}</div>
          </div>
          <div class="datenav">
            <button @click="date = addDays(date, -1)" aria-label="Sebelumnya"><Icon name="left" /></button>
            <button v-if="!isToday" class="today" @click="date = today()">Hari ini</button>
            <button @click="date = addDays(date, 1)" aria-label="Berikutnya"><Icon name="right" /></button>
          </div>
        </div>
        <div class="occ mt12">
          <div class="row between small"><span>Okupansi</span><b>{{ pct(s.occupancy) }} · {{ s.occupied || 0 }}/{{ s.units || 0 }} unit</b></div>
          <div class="occ-bar"><i :style="{ width: Math.min(s.occupancy || 0, 100) + '%' }"></i></div>
        </div>
      </div>

      <InstallBanner class="mt12" />
      <div v-if="stale" class="banner-offline mt12"><Icon name="warn" /> Offline — menampilkan data terakhir</div>
      <button v-if="s.attention && app.can('sync')" class="alert-row mt12" @click="router.push('/sync')">
        <Icon name="warn" /><span class="grow">{{ s.attention }} booking perlu perhatian (Sales Order)</span><Icon name="right" />
      </button>
      <button v-if="app.unread && app.can('messages')" class="alert-row msg mt12" @click="router.push({ path: '/messages', query: { unread: '1' } })">
        <Icon name="messages" /><span class="grow">{{ app.unread }} pesan tamu belum dibaca</span><Icon name="right" />
      </button>

      <div class="kpis mt12">
        <button class="kpi" :class="{ on: tab === 'arrivals' }" @click="tab = 'arrivals'">
          <Icon name="checkin" class="k-ic in" /><div class="k-num">{{ s.arrivals || 0 }}</div><div class="k-lbl">Kedatangan</div>
          <div class="k-sub">{{ s.arrivals_done || 0 }} sudah check-in</div>
        </button>
        <button class="kpi" :class="{ on: tab === 'departures' }" @click="tab = 'departures'">
          <Icon name="checkout" class="k-ic out" /><div class="k-num">{{ s.departures || 0 }}</div><div class="k-lbl">Keberangkatan</div>
          <div class="k-sub">{{ s.departures_done || 0 }} sudah check-out</div>
        </button>
        <button class="kpi" :class="{ on: tab === 'in_house' }" @click="tab = 'in_house'">
          <Icon name="bed" class="k-ic house" /><div class="k-num">{{ s.in_house || 0 }}</div><div class="k-lbl">Menginap</div>
          <div class="k-sub">{{ s.checked_in || 0 }} sudah check-in</div>
        </button>
        <div class="kpi static">
          <Icon name="money" class="k-ic rev" /><div class="k-num">{{ compact(s.revenue_month) }}</div><div class="k-lbl">Pendapatan bulan ini</div>
          <div class="k-sub">{{ s.new_24h || 0 }} booking baru 24 jam</div>
        </div>
      </div>

      <div class="lists">
        <section v-for="key in ['arrivals', 'departures', 'in_house']" :key="key" class="list-col" :class="{ show: tab === key }">
          <div class="section-title">{{ { arrivals: 'Kedatangan', departures: 'Keberangkatan', in_house: 'Sedang menginap' }[key] }} · {{ lists[key].length }}</div>
          <div v-if="loading && !data" class="card"><div class="skel skel-line" v-for="i in 3" :key="i"></div></div>
          <div v-else-if="!lists[key].length" class="empty small">Tidak ada.</div>
          <div v-for="b in lists[key]" :key="b.booking_id" class="qwrap">
            <BookingCard :b="b" @click="open(b)" />
            <button v-if="quick(b, key)" class="btn sm qbtn" :class="quick(b, key).cls" :disabled="busy === b.booking_id || !app.online" @click.stop="run(b, quick(b, key))">
              <Icon :name="busy === b.booking_id ? 'sync' : quick(b, key).icon" :spin="busy === b.booking_id" /> {{ quick(b, key).label }}
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero-date { font-size: 28px; font-weight: 800; line-height: 1.1; margin-top: 2px; }
.datenav { display: flex; gap: 6px; }
.datenav button { border: 0; background: rgba(255,255,255,.2); color: #fff; border-radius: 10px; height: 36px; min-width: 36px; font-weight: 700; padding: 0 10px; }
.occ-bar { height: 8px; background: rgba(255,255,255,.25); border-radius: 99px; margin-top: 6px; overflow: hidden; }
.occ-bar i { display: block; height: 100%; background: #fff; border-radius: 99px; transition: width .3s; }
.alert-row { width: 100%; display: flex; gap: 10px; align-items: center; border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent); background: color-mix(in srgb, var(--warn) 12%, var(--card)); color: var(--ink); border-radius: 14px; padding: 12px 14px; font-weight: 600; text-align: left; }
.alert-row .ico:first-child { color: var(--warn); }
.alert-row.msg { border-color: color-mix(in srgb, var(--brand) 40%, transparent); background: color-mix(in srgb, var(--brand) 10%, var(--card)); }
.alert-row.msg .ico:first-child { color: var(--brand); }
.kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kpi { text-align: left; border: 2px solid transparent; background: var(--card); border-radius: 16px; box-shadow: var(--shadow); padding: 12px; color: var(--ink); position: relative; }
.kpi.on { border-color: var(--brand); }
.kpi.static { cursor: default; }
.k-ic { position: absolute; top: 12px; right: 12px; font-size: 18px; }
.k-ic.in { color: var(--ok); } .k-ic.out { color: var(--brand); } .k-ic.house { color: #2563eb; } .k-ic.rev { color: var(--warn); }
.k-num { font-size: 26px; font-weight: 800; line-height: 1.1; }
.k-lbl { font-size: 13px; font-weight: 700; }
.k-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.list-col { display: none; }
.list-col.show { display: block; }
.qwrap { position: relative; }
.qwrap + .qwrap { margin-top: 10px; }
.qwrap :deep(.list-item) { margin: 0; }
/* tombol aksi cepat di baris sendiri di bawah isi kartu (tidak menutupi harga) */
.qbtn { position: absolute; left: 66px; right: 14px; bottom: 10px; }
.qwrap:has(.qbtn) :deep(.list-item) { padding-bottom: 58px; }
@media (min-width: 768px) {
  .kpis { grid-template-columns: repeat(4, 1fr); }
}
@media (min-width: 1100px) {
  .lists { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; align-items: start; }
  .list-col { display: block; }
  .kpi { cursor: default; }
  .kpi.on { border-color: transparent; }
}
</style>
