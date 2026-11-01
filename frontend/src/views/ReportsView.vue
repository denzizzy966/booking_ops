<script setup>
import { ref, computed, watch } from 'vue'
import { useApp } from '../stores/app'
import { cached } from '../lib/api'
import { fmtMonth, money, compact, channelLabel, today, iso, parse, pct } from '../lib/util'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const month = ref(today().slice(0, 7) + '-01')
const data = ref(null)
const stale = ref(false)
const loading = ref(false)

function shift(n) {
  const d = parse(month.value)
  d.setMonth(d.getMonth() + n)
  month.value = iso(d)
}
async function load() {
  loading.value = true
  try {
    const r = await cached(`report.${app.property}.${month.value}`, 'report', { month: month.value, property: app.property })
    data.value = r.data
    stale.value = r.stale
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}
watch(() => [month.value, app.property], load, { immediate: true })
const t = computed(() => (data.value && data.value.totals) || {})
const maxRev = computed(() => Math.max(1, ...((data.value && data.value.by_channel) || []).map((c) => c.revenue)))
</script>

<template>
  <AppBar title="Laporan" back property-picker />
  <div class="content">
    <div class="wrap">
      <div class="row tools">
        <button class="btn sm" @click="shift(-1)"><Icon name="left" /></button>
        <b class="grow center">{{ fmtMonth(month) }}</b>
        <button class="btn sm" @click="shift(1)"><Icon name="right" /></button>
      </div>
      <div v-if="stale" class="banner-offline mb8"><Icon name="warn" /> Offline — data terakhir</div>

      <div class="tiles" :class="{ loading }">
        <div class="tile"><div class="tl">Pendapatan</div><div class="tv">{{ compact(t.revenue) }}</div><div class="ts">{{ money(t.revenue, app.currency) }}</div></div>
        <div class="tile"><div class="tl">Okupansi</div><div class="tv">{{ pct(t.occupancy) }}</div><div class="ts">{{ t.units || 0 }} unit × {{ data ? data.days : 0 }} hari</div></div>
        <div class="tile"><div class="tl">Malam terjual</div><div class="tv">{{ t.nights || 0 }}</div><div class="ts">ADR {{ money(t.adr, app.currency) }}</div></div>
        <div class="tile"><div class="tl">Booking masuk</div><div class="tv">{{ t.bookings || 0 }}</div><div class="ts">{{ t.cancelled || 0 }} batal</div></div>
      </div>

      <div class="cols">
        <div class="card mt12">
          <div class="card-title">Per channel</div>
          <div v-if="data && !data.by_channel.length" class="small muted">Belum ada data.</div>
          <div v-for="c in data ? data.by_channel : []" :key="c.channel" class="bar-row">
            <div class="row between small"><b>{{ channelLabel(c.channel) }}</b><span>{{ money(c.revenue, app.currency) }}</span></div>
            <div class="hbar"><i :style="{ width: (c.revenue * 100) / maxRev + '%' }"></i></div>
            <div class="tiny muted">{{ c.bookings }} booking · {{ c.nights }} malam</div>
          </div>
        </div>
        <div class="card mt12">
          <div class="card-title">Okupansi per tipe kamar</div>
          <div v-if="data && !data.by_room.length" class="small muted">Belum ada data.</div>
          <div v-for="r in data ? data.by_room : []" :key="r.room" class="bar-row">
            <div class="row between small"><b class="truncate">{{ r.room_name }}</b><span>{{ pct(r.occupancy) }}</span></div>
            <div class="hbar alt"><i :style="{ width: Math.min(r.occupancy, 100) + '%' }"></i></div>
            <div class="tiny muted">{{ r.nights }} malam · {{ money(r.revenue, app.currency) }}</div>
          </div>
        </div>
      </div>

      <div v-if="data && app.can('sales_order')" class="card mt12">
        <div class="card-title">Sales Order ERPNext (booking bulan ini)</div>
        <div class="so">
          <div><b>{{ data.sales_orders.draft }}</b><span>Draft</span></div>
          <div><b>{{ data.sales_orders.submitted }}</b><span>Submitted</span></div>
          <div><b>{{ data.sales_orders.billed }}</b><span>Lunas ditagih</span></div>
          <div><b>{{ compact(data.sales_orders.total) }}</b><span>Total SO</span></div>
        </div>
      </div>
      <p class="tiny muted mt8">Pendapatan dihitung per malam yang jatuh di bulan ini (booking lintas bulan dibagi proporsional).</p>
    </div>
  </div>
</template>

<style scoped>
.tools { margin-bottom: 10px; }
.center { text-align: center; font-size: 17px; }
.mb8 { margin-bottom: 8px; }
.tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.tiles.loading { opacity: .6; }
.tile { background: var(--card); border-radius: 16px; box-shadow: var(--shadow); padding: 12px; }
.tl { font-size: 12px; color: var(--muted); font-weight: 700; }
.tv { font-size: 26px; font-weight: 800; line-height: 1.15; }
.ts { font-size: 11px; color: var(--muted); }
.card-title { font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; margin-bottom: 10px; }
.bar-row + .bar-row { margin-top: 12px; }
.hbar { height: 8px; background: var(--line); border-radius: 99px; overflow: hidden; margin: 5px 0 3px; }
.hbar i { display: block; height: 100%; background: var(--brand); border-radius: 99px; }
.hbar.alt i { background: #2563eb; }
.so { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; text-align: center; }
.so b { display: block; font-size: 20px; }
.so span { font-size: 11px; color: var(--muted); }
@media (min-width: 768px) {
  .tiles { grid-template-columns: repeat(4, 1fr); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .cols .card + .card { margin-top: 12px; }
}
</style>
