<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { cached } from '../lib/api'
import { addDays, today, diffDays, dayName, parse, fmtDate, fmtMonth, channelLabel } from '../lib/util'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const router = useRouter()
const wide = ref(window.innerWidth >= 768)
const onResize = () => (wide.value = window.innerWidth >= 768)
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

const days = computed(() => (wide.value ? 21 : 14))
const start = ref(addDays(today(), -1))
const data = ref(null)
const stale = ref(false)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await cached(`cal.${app.property}.${start.value}.${days.value}`, 'calendar', { start: start.value, days: days.value, property: app.property })
    data.value = r.data
    stale.value = r.stale
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}
watch(() => [start.value, days.value, app.property], load, { immediate: true })

const dates = computed(() => Array.from({ length: days.value }, (_, i) => addDays(start.value, i)))

// Satu baris per unit. Booking tanpa unit ditempatkan ke baris pertama yang kosong (greedy);
// sisa yang tak muat → baris "Belum ditempatkan".
const groups = computed(() => {
  if (!data.value) return []
  const byRoom = {}
  for (const b of data.value.bookings) (byRoom[b.room] = byRoom[b.room] || []).push(b)
  return data.value.rooms.map((r) => {
    const units = r.units && r.units.length ? r.units : Array.from({ length: Math.max(r.qty || 1, 1) }, (_, i) => ({ id: null, name: `#${i + 1}` }))
    const lines = units.map((u) => ({ key: `${r.room_id}:${u.id ?? u.name}`, unitId: u.id != null ? String(u.id) : '', label: u.name, bars: [] }))
    const overlaps = (line, b) => line.bars.some((x) => x.arrival < b.departure && b.arrival < x.departure)
    const list = (byRoom[r.room_id] || []).slice().sort((a, b) => (a.arrival < b.arrival ? -1 : 1))
    const pending = []
    for (const b of list) {
      const line = b.unit_id && lines.find((l) => l.unitId === String(b.unit_id))
      if (line) line.bars.push(b)
      else pending.push(b)
    }
    let extra = null
    for (const b of pending) {
      const free = lines.find((l) => !overlaps(l, b))
      if (free) free.bars.push(b)
      else {
        extra = extra || { key: `${r.room_id}:extra`, unitId: '', label: 'Tanpa unit', bars: [], extra: true }
        extra.bars.push(b)
      }
    }
    if (extra) lines.push(extra)
    return { room: r, lines }
  })
})

function bar(b) {
  const x0 = Math.max(diffDays(start.value, b.arrival) + 0.5, 0)
  const x1 = Math.min(diffDays(start.value, b.departure) + 0.5, days.value)
  return { left: `calc(var(--cell) * ${x0})`, width: `calc(var(--cell) * ${Math.max(x1 - x0, 0.3)} - 3px)` }
}
function barCls(b) {
  if (b.status === 'black') return 'k-black'
  if (b.stay_status === 'Checked In') return 'k-in'
  if (b.stay_status === 'Checked Out') return 'k-out'
  if (b.stay_status === 'No Show') return 'k-noshow'
  return `k-${b.status}`
}
function cellClick(room, line, d) {
  if (!app.can('new_booking') || d < today()) return
  const q = { room: room.room_id, arrival: d, departure: addDays(d, 1) }
  if (line.unitId) q.unit = line.unitId
  router.push({ path: '/new', query: q })
}
const isWeekend = (d) => [0, 6].includes(parse(d).getDay())
const monthLabel = computed(() => {
  const a = fmtMonth(start.value)
  const b = fmtMonth(addDays(start.value, days.value - 1))
  return a === b ? a : `${a.split(' ')[0]} – ${b}`
})
</script>

<template>
  <AppBar title="Kalender" property-picker />
  <div class="content cal-content">
    <div class="cal-tools">
      <button class="btn sm" @click="start = addDays(start, -7)" aria-label="Minggu sebelumnya"><Icon name="left" /></button>
      <button class="btn sm" @click="start = addDays(today(), -1)">Hari ini</button>
      <button class="btn sm" @click="start = addDays(start, 7)" aria-label="Minggu berikutnya"><Icon name="right" /></button>
      <div class="grow month">{{ monthLabel }}</div>
      <input type="date" class="jump" :value="start" @change="(e) => e.target.value && (start = e.target.value)" aria-label="Lompat ke tanggal" />
    </div>
    <div v-if="stale" class="banner-offline mb8"><Icon name="warn" /> Offline — data terakhir</div>

    <div class="legend tiny">
      <span><i class="k-confirmed"></i>Confirmed</span><span><i class="k-new"></i>Baru</span><span><i class="k-request"></i>Request</span>
      <span><i class="k-in"></i>Menginap</span><span><i class="k-out"></i>Keluar</span><span><i class="k-black"></i>Blokir</span>
    </div>

    <div class="cal" :class="{ loading }">
      <div class="cal-head">
        <div class="lbl-col head-corner">Kamar</div>
        <div v-for="d in dates" :key="d" class="dcell" :class="{ today: d === today(), we: isWeekend(d) }">
          <span>{{ dayName(d) }}</span><b>{{ parse(d).getDate() }}</b>
        </div>
      </div>
      <template v-for="g in groups" :key="g.room.room_id">
        <div class="grp">
          <div class="lbl-col grp-lbl truncate"><Icon name="bed" /> {{ g.room.room_name }}</div>
        </div>
        <div v-for="line in g.lines" :key="line.key" class="line" :class="{ extra: line.extra }">
          <div class="lbl-col truncate">{{ line.label }}</div>
          <div class="cells">
            <div v-for="d in dates" :key="d" class="cell" :class="{ today: d === today(), we: isWeekend(d), past: d < today() }" @click="cellClick(g.room, line, d)"></div>
            <button
              v-for="b in line.bars"
              :key="b.booking_id"
              class="bar"
              :class="barCls(b)"
              :style="bar(b)"
              :title="`${b.guest_name} · ${fmtDate(b.arrival)} → ${fmtDate(b.departure)}`"
              @click.stop="b.status !== 'black' && router.push(`/booking/${b.booking_id}`)"
            >
              <span class="truncate">{{ b.status === 'black' ? 'Diblokir' : b.guest_name }}</span>
              <small v-if="wide && b.status !== 'black'" class="truncate">{{ channelLabel(b.channel) }}</small>
            </button>
          </div>
        </div>
      </template>
      <div v-if="data && !groups.length" class="empty">Belum ada kamar. Minta admin klik “Ambil Properti & Kamar” di Booking Ops Settings.</div>
    </div>
    <p v-if="app.can('new_booking')" class="tiny muted mt8">Ketuk sel kosong untuk membuat booking di kamar & tanggal itu.</p>
  </div>
</template>

<style scoped>
.cal-content { --cell: 46px; --lbl: 96px; padding-left: 10px; padding-right: 10px; }
@media (min-width: 768px) { .cal-content { --cell: 54px; --lbl: 160px; } }
.cal-tools { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.month { font-weight: 800; text-align: center; }
@media (max-width: 767px) {
  .month { order: -1; flex-basis: 100%; text-align: left; font-size: 17px; }
  .jump { margin-left: auto; }
}
.jump { border: 1px solid var(--line); border-radius: 10px; padding: 6px 8px; font-size: 13px; width: 132px; }
.legend { display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); margin-bottom: 8px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
.cal { overflow: auto; background: var(--card); border-radius: 14px; box-shadow: var(--shadow); max-height: calc(100vh - 230px); position: relative; }
.cal.loading { opacity: .6; }
.cal-head { display: flex; position: sticky; top: 0; z-index: 4; background: var(--card); border-bottom: 1px solid var(--line); width: max-content; }
.lbl-col { width: var(--lbl); flex: none; position: sticky; left: 0; z-index: 3; background: var(--card); padding: 0 8px; font-size: 12px; display: flex; align-items: center; border-right: 1px solid var(--line); }
.head-corner { font-weight: 700; color: var(--muted); z-index: 5; }
.dcell { width: var(--cell); flex: none; text-align: center; padding: 6px 0; font-size: 11px; color: var(--muted); display: flex; flex-direction: column; line-height: 1.2; }
.dcell b { font-size: 15px; color: var(--ink); }
.dcell.we { background: color-mix(in srgb, var(--brand-soft) 60%, transparent); }
.dcell.today { background: var(--brand); color: var(--brand-ink); border-radius: 8px; }
.dcell.today b { color: var(--brand-ink); }
.grp { display: flex; width: max-content; min-width: 100%; background: var(--bg); border-bottom: 1px solid var(--line); }
.grp-lbl { background: var(--bg); font-weight: 800; height: 28px; width: auto; min-width: var(--lbl); gap: 6px; border-right: 0; }
.line { display: flex; width: max-content; border-bottom: 1px solid var(--line); height: 40px; }
.line.extra .lbl-col { color: var(--warn); font-weight: 700; }
.cells { display: flex; position: relative; }
.cell { width: var(--cell); flex: none; border-right: 1px solid color-mix(in srgb, var(--line) 60%, transparent); cursor: pointer; }
.cell.we { background: color-mix(in srgb, var(--brand-soft) 45%, transparent); }
.cell.today { background: color-mix(in srgb, var(--brand) 10%, transparent); }
.cell.past { cursor: default; }
.bar { position: absolute; top: 5px; height: 30px; border: 0; border-radius: 8px; padding: 0 6px; color: #fff; font-size: 12px; font-weight: 700; text-align: left; display: flex; flex-direction: column; justify-content: center; overflow: hidden; line-height: 1.1; z-index: 2; box-shadow: 0 1px 2px rgba(0,0,0,.2); }
.bar small { font-size: 10px; font-weight: 600; opacity: .85; }
.k-confirmed { background: #8a6f4e; } .k-new { background: #2563eb; } .k-request { background: #d97706; } .k-inquiry { background: #7c3aed; }
.k-in { background: #16a34a; } .k-out { background: #64748b; } .k-noshow { background: #dc2626; }
.k-black { background: repeating-linear-gradient(45deg, #475569, #475569 6px, #64748b 6px, #64748b 12px); }
.mb8 { margin-bottom: 8px; }
</style>
