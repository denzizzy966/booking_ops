<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApp } from '../stores/app'
import { cached, call } from '../lib/api'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import BookingCard from '../components/BookingCard.vue'
import BookingDetail from '../components/BookingDetail.vue'

const PAGE = 30
const SCOPES = [
  { key: 'upcoming', label: 'Akan datang' },
  { key: 'inhouse', label: 'Menginap' },
  { key: 'past', label: 'Selesai' },
  { key: 'cancelled', label: 'Batal' },
  { key: 'attention', label: 'Perlu perhatian' },
  { key: 'all', label: 'Semua' }
]
const app = useApp()
const router = useRouter()
const route = useRoute()
const scope = ref(route.query.scope || 'upcoming')
const txt = ref('')
const rows = ref([])
const more = ref(false)
const loading = ref(false)
const stale = ref(false)
const selected = ref('')
const twoPane = ref(window.innerWidth >= 1000)
const onResize = () => (twoPane.value = window.innerWidth >= 1000)
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

let seq = 0
let timer = null
async function load(append = false) {
  const my = ++seq
  loading.value = true
  const params = { scope: scope.value, txt: txt.value.trim(), property: app.property, start: append ? rows.value.length : 0, limit: PAGE }
  try {
    let data
    if (append || params.txt) {
      data = await call('list_bookings', params)
    } else {
      const r = await cached(`list.${scope.value}.${app.property}`, 'list_bookings', params)
      data = r.data
      stale.value = r.stale
    }
    if (my !== seq) return // respons basi (filter sudah berubah)
    rows.value = append ? rows.value.concat(data) : data
    more.value = data.length === PAGE
    if (twoPane.value && !selected.value && rows.value.length) selected.value = rows.value[0].booking_id
  } catch (e) {
    if (my === seq) app.notify(e.message, 'error')
  } finally {
    if (my === seq) loading.value = false
  }
}
watch(() => [scope.value, app.property], () => load(), { immediate: true })
watch(txt, () => {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 300)
})

function open(b) {
  if (twoPane.value) selected.value = b.booking_id
  else router.push(`/booking/${b.booking_id}`)
}
function onChanged(doc) {
  const i = rows.value.findIndex((r) => r.booking_id === doc.booking_id)
  if (i >= 0) rows.value[i] = { ...rows.value[i], ...doc }
}
</script>

<template>
  <AppBar title="Booking" property-picker />
  <div class="content" :class="{ split: twoPane }">
    <div class="list-pane">
      <div class="toolbar">
        <SearchInput v-model="txt" placeholder="Cari nama, no. booking, HP, email…" />
        <div class="chips mt8" :class="{ dim: txt.trim() }">
          <button v-for="s in SCOPES" :key="s.key" class="chip" :class="{ active: scope === s.key }" @click="scope = s.key">{{ s.label }}</button>
        </div>
        <div v-if="txt.trim()" class="tiny muted">Mencari di semua booking</div>
      </div>
      <div v-if="stale" class="banner-offline mb8"><Icon name="warn" /> Offline — data terakhir</div>
      <div v-if="loading && !rows.length" class="card"><div class="skel skel-line" v-for="i in 5" :key="i"></div></div>
      <div v-else-if="!rows.length" class="empty"><div class="big"><Icon name="list" /></div>Tidak ada booking.</div>
      <BookingCard v-for="b in rows" :key="b.booking_id" :b="b" :active="twoPane && selected === b.booking_id" @click="open(b)" />
      <button v-if="more" class="btn block mt12" :disabled="loading" @click="load(true)">{{ loading ? 'Memuat…' : 'Muat lagi' }}</button>
    </div>
    <div v-if="twoPane" class="detail-pane">
      <BookingDetail v-if="selected" :id="selected" pane @changed="onChanged" />
      <div v-else class="empty">Pilih booking di kiri.</div>
    </div>
    <router-link v-if="app.can('new_booking')" to="/new" class="fab" aria-label="Booking baru"><Icon name="plus" /></router-link>
  </div>
</template>

<style scoped>
.mb8 { margin-bottom: 8px; }
.chips.dim { opacity: .45; }
.split { display: grid; grid-template-columns: minmax(340px, 400px) 1fr; gap: 16px; align-items: start; }
.split .list-pane { position: sticky; top: 0; max-height: calc(100vh - var(--header-h) - 28px); overflow-y: auto; padding-right: 4px; }
.split .toolbar { top: 0; margin-top: 0; }
.detail-pane { min-width: 0; }
</style>
