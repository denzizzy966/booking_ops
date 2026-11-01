<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useApp } from '../stores/app'
import { cached, call } from '../lib/api'
import { channelLabel, fmtMsgTime } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import SearchInput from '../components/SearchInput.vue'
import ThreadPanel from '../components/ThreadPanel.vue'

const PAGE = 30
const app = useApp()
const router = useRouter()
const route = useRoute()
const onlyUnread = ref(route.query.unread === '1')
const txt = ref('')
const rows = ref([])
const more = ref(false)
const loading = ref(false)
const fetching = ref(false)
const stale = ref(false)
const selected = ref('')
const twoPane = ref(window.innerWidth >= 1000)
const onResize = () => (twoPane.value = window.innerWidth >= 1000)
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

let seq = 0
let timer = null
async function load(append = false, quiet = false) {
  const my = ++seq
  if (!quiet) loading.value = true
  const params = { txt: txt.value.trim(), only_unread: onlyUnread.value ? 1 : 0, property: app.property, start: append ? rows.value.length : 0, limit: PAGE }
  try {
    let data
    if (append || params.txt) data = await call('inbox', params)
    else {
      const r = await cached(`inbox.${params.only_unread}.${app.property}`, 'inbox', params)
      data = r.data
      stale.value = r.stale
    }
    if (my !== seq) return
    rows.value = append ? rows.value.concat(data) : data
    more.value = data.length === PAGE
    if (twoPane.value && !selected.value && rows.value.length) selected.value = rows.value[0].booking_id
  } catch (e) {
    if (my === seq && !quiet) app.notify(e.message, 'error')
  } finally {
    if (my === seq) loading.value = false
  }
}
watch(() => [onlyUnread.value, app.property], () => load(), { immediate: true })
watch(txt, () => {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 300)
})
// Badge berubah (pesan baru masuk / dibaca di perangkat lain) → segarkan daftar diam-diam.
watch(() => app.unread, () => load(false, true))

async function fetchNow() {
  fetching.value = true
  try {
    const r = await call('fetch_messages', {}, { post: true })
    app.notify(r.skipped ? r.message : `${r.created} pesan baru dari Beds24`, r.errors ? 'warn' : 'success')
    await load()
    app.refreshUnread()
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    fetching.value = false
  }
}

function open(r) {
  if (twoPane.value) selected.value = r.booking_id
  else router.push(`/messages/${r.booking_id}`)
}
function onChanged(ch) {
  const i = rows.value.findIndex((r) => r.booking_id === ch.booking_id)
  if (i < 0) return
  const row = { ...rows.value[i], unread: ch.unread ?? rows.value[i].unread }
  if (ch.last) Object.assign(row, { last: ch.last, last_time: ch.last_time })
  rows.value[i] = row
  if (ch.last && i > 0) rows.value.unshift(...rows.value.splice(i, 1))
}
const preview = (r) => {
  const m = r.last || {}
  const head = m.source === 'host' ? 'Anda: ' : m.source === 'internalNote' ? 'Catatan: ' : ''
  return head + (m.message || (m.attachment_name ? `Lampiran: ${m.attachment_name}` : ''))
}
</script>

<template>
  <AppBar title="Pesan" property-picker>
    <template #actions>
      <button class="bar-btn" :disabled="fetching || !app.online" aria-label="Ambil pesan dari Beds24" title="Ambil pesan dari Beds24" @click="fetchNow"><Icon name="sync" :spin="fetching" /></button>
    </template>
  </AppBar>
  <div class="content" :class="{ split: twoPane }">
    <div class="list-pane">
      <div class="toolbar">
        <SearchInput v-model="txt" placeholder="Cari nama tamu, no. booking, isi pesan…" />
        <div class="chips mt8">
          <button class="chip" :class="{ active: !onlyUnread }" @click="onlyUnread = false">Semua</button>
          <button class="chip" :class="{ active: onlyUnread }" @click="onlyUnread = true">Belum dibaca<template v-if="app.unread"> · {{ app.unread }}</template></button>
        </div>
      </div>
      <div v-if="stale" class="banner-offline mb8"><Icon name="warn" /> Offline — data terakhir</div>
      <div v-if="loading && !rows.length" class="card"><div class="skel skel-line" v-for="i in 5" :key="i"></div></div>
      <div v-else-if="!rows.length" class="empty">
        <div class="big"><Icon name="messages" /></div>
        {{ onlyUnread ? 'Semua pesan sudah dibaca.' : 'Belum ada pesan tamu.' }}
        <div v-if="!onlyUnread" class="tiny mt8">Pesan dari Airbnb, Booking.com, dll. masuk otomatis. Ketuk <Icon name="sync" /> di atas untuk mengambil sekarang.</div>
      </div>
      <button v-for="r in rows" :key="r.booking_id" class="list-item conv" :class="{ unread: r.unread, active: twoPane && selected === r.booking_id }" @click="open(r)">
        <div class="avatar">{{ (r.guest_name || '?').trim().charAt(0).toUpperCase() }}</div>
        <div class="grow">
          <div class="row between">
            <b class="truncate">{{ r.guest_name }}</b>
            <span class="tiny when">{{ fmtMsgTime(r.last_time) }}</span>
          </div>
          <div class="row between">
            <span class="small truncate prev">{{ preview(r) }}</span>
            <i v-if="r.unread" class="count">{{ r.unread }}</i>
          </div>
          <div class="tiny muted truncate">{{ channelLabel(r.channel) }} · #{{ r.booking_id }}<template v-if="r.room"> · {{ app.roomName(r.room) }}</template></div>
        </div>
      </button>
      <button v-if="more" class="btn block mt12" :disabled="loading" @click="load(true)">{{ loading ? 'Memuat…' : 'Muat lagi' }}</button>
    </div>
    <div v-if="twoPane" class="thread-pane">
      <ThreadPanel v-if="selected" :id="selected" :key="selected" pane @changed="onChanged" />
      <div v-else class="empty card">Pilih percakapan di kiri.</div>
    </div>
  </div>
</template>

<style scoped>
.mb8 { margin-bottom: 8px; }
.conv { width: 100%; border: 0; text-align: left; color: var(--ink); align-items: flex-start; }
.conv + .conv { margin-top: 8px; }
.conv.active { outline: 2px solid var(--brand); }
.avatar { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; background: var(--brand-soft); color: var(--brand); font-weight: 800; flex: none; font-size: 18px; }
.when { color: var(--muted); flex: none; }
.prev { color: var(--muted); }
.unread .prev { color: var(--ink); font-weight: 700; }
.unread .when { color: var(--brand); font-weight: 800; }
.count { flex: none; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 99px; background: var(--brand); color: var(--brand-ink); font-size: 11px; font-weight: 800; font-style: normal; line-height: 20px; text-align: center; }
.bar-btn { border: 0; background: rgba(255,255,255,.18); color: var(--appbar-ink); border-radius: 10px; height: 36px; min-width: 36px; display: grid; place-items: center; }
.split { display: grid; grid-template-columns: minmax(320px, 380px) 1fr; gap: 16px; align-items: start; }
.split .list-pane { position: sticky; top: 0; max-height: calc(100vh - var(--header-h) - 36px); overflow-y: auto; padding-right: 4px; }
.split .toolbar { top: 0; margin-top: 0; }
.thread-pane { position: sticky; top: 0; height: calc(100vh - var(--header-h) - 36px); min-width: 0; }
</style>
