<script setup>
import { ref, computed, watch } from 'vue'
import { useApp } from '../stores/app'
import { cached } from '../lib/api'
import { addDays, today, dayName, parse, fmtMonth, compact } from '../lib/util'
import AppBar from '../components/AppBar.vue'

// Sisa kamar & harga per malam langsung dari kalender Beds24.
const app = useApp()
const start = ref(today())
const days = 14
const data = ref(null)
const stale = ref(false)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await cached(`rates.${app.property}.${start.value}`, 'rates', { start: start.value, days, property: app.property })
    data.value = r.data
    stale.value = r.stale
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}
watch(() => [start.value, app.property], load, { immediate: true })
const dates = computed(() => Array.from({ length: days }, (_, i) => addDays(start.value, i)))
const cell = (r, d) => (data.value && data.value.grid[r.room_id] && data.value.grid[r.room_id][d]) || {}
const level = (c, r) => (c.avail == null ? '' : c.avail <= 0 ? 'none' : c.avail / Math.max(r.qty || 1, 1) <= 0.3 ? 'low' : 'ok')
</script>

<template>
  <AppBar title="Ketersediaan & Harga" back property-picker />
  <div class="content">
    <div class="row tools">
      <button class="btn sm" @click="start = addDays(start, -14)" :disabled="start <= today()"><Icon name="left" /></button>
      <button class="btn sm" @click="start = today()">Hari ini</button>
      <button class="btn sm" @click="start = addDays(start, 14)"><Icon name="right" /></button>
      <b class="grow center">{{ fmtMonth(start) }}</b>
    </div>
    <div v-if="stale" class="banner-offline mb8"><Icon name="warn" /> Offline — data terakhir</div>
    <div class="grid-wrap" :class="{ loading }">
      <table class="rates">
        <thead>
          <tr>
            <th class="rh">Tipe kamar</th>
            <th v-for="d in dates" :key="d" :class="{ today: d === today() }"><span>{{ dayName(d) }}</span><b>{{ parse(d).getDate() }}</b></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in data ? data.rooms : []" :key="r.room_id">
            <th class="rh"><div class="truncate">{{ r.room_name }}</div><small class="muted">{{ r.qty }} unit</small></th>
            <td v-for="d in dates" :key="d" :class="level(cell(r, d), r)">
              <b>{{ cell(r, d).avail ?? '–' }}</b>
              <small v-if="cell(r, d).price">{{ compact(cell(r, d).price) }}</small>
              <i v-if="cell(r, d).min_stay > 1" class="ms">min {{ cell(r, d).min_stay }}</i>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="tiny muted mt8">Angka besar = sisa unit; angka kecil = harga per malam (tarif 1). Ubah harga & stok di Beds24.</p>
  </div>
</template>

<style scoped>
.tools { margin-bottom: 10px; gap: 6px; }
.center { text-align: center; }
.mb8 { margin-bottom: 8px; }
.grid-wrap { overflow: auto; background: var(--card); border-radius: 14px; box-shadow: var(--shadow); }
.grid-wrap.loading { opacity: .6; }
.rates { border-collapse: collapse; font-size: 12px; min-width: 100%; }
.rates th, .rates td { border-bottom: 1px solid var(--line); text-align: center; padding: 6px 4px; min-width: 50px; }
.rates thead th { position: sticky; top: 0; background: var(--card); font-weight: 600; color: var(--muted); }
.rates thead th b { display: block; font-size: 14px; color: var(--ink); }
.rates thead th.today { color: var(--brand); }
.rates .rh { position: sticky; left: 0; background: var(--card); text-align: left; min-width: 110px; max-width: 150px; z-index: 1; padding-left: 10px; }
.rates td b { display: block; font-size: 14px; }
.rates td small { color: var(--muted); }
.rates td.ok b { color: var(--ok); }
.rates td.low { background: color-mix(in srgb, var(--warn) 12%, transparent); }
.rates td.low b { color: var(--warn); }
.rates td.none { background: color-mix(in srgb, var(--danger) 10%, transparent); }
.rates td.none b { color: var(--danger); }
.ms { display: block; font-size: 9px; font-style: normal; color: var(--muted); }
</style>
