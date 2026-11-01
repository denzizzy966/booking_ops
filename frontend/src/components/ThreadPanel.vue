<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useApp } from '../stores/app'
import { call } from '../lib/api'
import { fmtDate, channelLabel, today, parse, iso } from '../lib/util'

// Percakapan satu booking: dipakai halaman /messages/:id (HP) dan panel kanan di tablet.
const props = defineProps({ id: { type: String, required: true }, pane: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const app = useApp()
const data = ref(null)
const loading = ref(true)
const text = ref('')
const internal = ref(false)
const file = ref(null) // { name, type, b64, size, preview }
const sending = ref(false)
const listEl = ref(null)
const fileEl = ref(null)
const wide = window.matchMedia('(min-width: 768px)').matches
const MAX = 5 * 1024 * 1024

const b = computed(() => (data.value && data.value.booking) || {})
const msgs = computed(() => (data.value && data.value.messages) || [])
// Kelompokkan per tanggal untuk pemisah "Hari ini" / "Kemarin" / tanggal.
const groups = computed(() => {
  const out = []
  for (const m of msgs.value) {
    const d = String(m.time || '').slice(0, 10)
    if (!out.length || out[out.length - 1].date !== d) out.push({ date: d, items: [] })
    out[out.length - 1].items.push(m)
  }
  return out
})
const dayLabel = (d) => {
  if (d === today()) return 'Hari ini'
  const y = parse(today())
  y.setDate(y.getDate() - 1)
  return d === iso(y) ? 'Kemarin' : fmtDate(d, { year: true })
}
const clock = (t) => String(t || '').slice(11, 16)
const isImage = (m) => /\.(jpe?g|png|gif|webp)$/i.test(m.attachment_name || m.attachment || '')
const who = (m) => (m.sent_by ? m.sent_by.split('@')[0] : '')

async function scrollEnd() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function load(refresh = 1, quiet = false) {
  if (!quiet) loading.value = true
  try {
    const before = msgs.value.length
    const r = await call('thread', { booking_id: props.id, refresh })
    data.value = r
    if (r.warning && !quiet) app.notify(r.warning, 'warn')
    if (!quiet || r.messages.length !== before) scrollEnd()
    markRead()
  } catch (e) {
    if (!quiet) app.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function markRead() {
  const unread = msgs.value.filter((m) => m.source === 'guest' && !m.read)
  if (!unread.length || !app.online) return
  unread.forEach((m) => (m.read = 1))
  try {
    await call('mark_read', { booking_id: props.id }, { post: true })
  } catch {
    /* lokal sudah ditandai; coba lagi saat dibuka berikutnya */
  }
  emit('changed', { booking_id: props.id, unread: 0 })
  app.refreshUnread()
}

// Foto dari HP bisa > 5 MB → perkecil ke sisi terpanjang 1600 px (JPEG 80%).
function shrink(f) {
  return new Promise((resolve) => {
    if (!/^image\/(jpeg|png)$/.test(f.type)) return resolve(null)
    const img = new Image()
    img.onload = () => {
      const k = Math.min(1, 1600 / Math.max(img.width, img.height))
      const c = document.createElement('canvas')
      c.width = Math.round(img.width * k)
      c.height = Math.round(img.height * k)
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height)
      URL.revokeObjectURL(img.src)
      resolve(c.toDataURL('image/jpeg', 0.8))
    }
    img.onerror = () => resolve(null)
    img.src = URL.createObjectURL(f)
  })
}
const readAsDataURL = (f) =>
  new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = reject
    r.readAsDataURL(f)
  })

async function pick(e) {
  const f = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!f) return
  if (!['image/jpeg', 'image/png', 'image/gif', 'application/pdf'].includes(f.type)) return app.notify('Lampiran harus foto (JPG/PNG/GIF) atau PDF', 'error')
  let url = f.size > 1024 * 1024 ? await shrink(f) : null
  let type = url ? 'image/jpeg' : f.type
  let name = url ? f.name.replace(/\.\w+$/, '') + '.jpg' : f.name
  url = url || (await readAsDataURL(f))
  const b64 = url.split(',')[1]
  if (b64.length * 0.75 > MAX) return app.notify('Lampiran maksimal 5 MB', 'error')
  file.value = { name, type, b64, size: Math.round(b64.length * 0.75), preview: type.startsWith('image/') ? url : '' }
}

async function send() {
  const msg = text.value.trim()
  if ((!msg && !file.value) || sending.value) return
  sending.value = true
  try {
    const params = { booking_id: props.id, message: msg, internal: internal.value ? 1 : 0 }
    if (file.value) Object.assign(params, { attachment: file.value.b64, attachment_name: file.value.name, attachment_type: file.value.type })
    data.value = await call('send_message', params, { post: true })
    text.value = ''
    file.value = null
    internal.value = false
    const last = msgs.value[msgs.value.length - 1]
    emit('changed', { booking_id: props.id, unread: 0, last, last_time: last && last.time })
    scrollEnd()
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    sending.value = false
  }
}
function onEnter(e) {
  // Tablet/desktop: Enter kirim, Shift+Enter baris baru. HP: Enter = baris baru.
  if (wide && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

let timer = null
onMounted(() => {
  load(1)
  timer = setInterval(() => app.online && !document.hidden && !sending.value && load(1, true), 30000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="thread" :class="{ pane }">
    <div class="thead">
      <div class="avatar">{{ (b.guest_name || '?').trim().charAt(0).toUpperCase() }}</div>
      <div class="grow">
        <div class="truncate name">{{ b.guest_name || '…' }}</div>
        <div class="tiny muted truncate">
          {{ channelLabel(b.channel) }} · #{{ id }}<template v-if="b.arrival"> · {{ fmtDate(b.arrival, { day: false }) }} → {{ fmtDate(b.departure, { day: false }) }}</template><template v-if="data && data.booking.room_name"> · {{ data.booking.room_name }}</template>
        </div>
      </div>
      <button class="btn sm icon-only" :disabled="loading || !app.online" aria-label="Muat ulang" @click="load(1)"><Icon name="sync" :spin="loading" /></button>
      <router-link v-if="app.can('bookings')" class="btn sm" :to="`/booking/${id}`"><Icon name="info" /><span class="hide-xs"> Booking</span></router-link>
    </div>

    <div ref="listEl" class="msgs">
      <div v-if="loading && !data" class="card"><div class="skel skel-line" v-for="i in 4" :key="i"></div></div>
      <div v-else-if="!msgs.length" class="empty small">Belum ada pesan untuk booking ini.</div>
      <template v-for="g in groups" :key="g.date">
        <div class="day"><span>{{ dayLabel(g.date) }}</span></div>
        <div v-for="m in g.items" :key="m.name" class="msg" :class="m.source">
          <div v-if="m.source === 'system'" class="sys"><Icon name="info" /> {{ m.message }} <span class="t">{{ clock(m.time) }}</span></div>
          <div v-else class="bubble">
            <div v-if="m.source === 'internalNote'" class="note-tag"><Icon name="note" /> Catatan internal · tidak terlihat tamu</div>
            <a v-if="m.attachment && isImage(m)" :href="m.attachment" target="_blank" rel="noopener" class="att-img"><img :src="m.attachment" :alt="m.attachment_name || 'lampiran'" loading="lazy" /></a>
            <a v-else-if="m.attachment" :href="m.attachment" target="_blank" rel="noopener" class="att-file"><Icon name="attach" /> {{ m.attachment_name || 'Lampiran' }}</a>
            <div v-if="m.message" class="txt">{{ m.message }}</div>
            <div class="t">
              <template v-if="who(m)">{{ who(m) }} · </template>{{ clock(m.time) }}
              <Icon v-if="m.source === 'host'" name="check" />
            </div>
          </div>
        </div>
      </template>
    </div>

    <div v-if="data && data.can_reply" class="composer" :class="{ internal }">
      <div v-if="file" class="file-chip">
        <img v-if="file.preview" :src="file.preview" alt="" />
        <Icon v-else name="attach" />
        <span class="grow truncate small">{{ file.name }} · {{ Math.max(1, Math.round(file.size / 1024)) }} KB</span>
        <button class="btn sm icon-only" aria-label="Hapus lampiran" @click="file = null"><Icon name="close" /></button>
      </div>
      <div class="row crow">
        <button class="btn icon-only" :class="{ on: internal }" :aria-pressed="internal" title="Catatan internal (tidak terkirim ke tamu)" @click="internal = !internal"><Icon name="note" /></button>
        <button v-if="!internal" class="btn icon-only" aria-label="Lampirkan foto/PDF" @click="fileEl.click()"><Icon name="attach" /></button>
        <input ref="fileEl" type="file" accept="image/jpeg,image/png,image/gif,application/pdf" hidden @change="pick" />
        <textarea
          v-model="text"
          rows="1"
          class="grow"
          :placeholder="internal ? 'Catatan internal untuk staf…' : `Balas ${b.guest_name || 'tamu'} via ${channelLabel(b.channel)}…`"
          @keydown.enter="onEnter"
        ></textarea>
        <button class="btn brand icon-only send" :disabled="sending || !app.online || (!text.trim() && !file)" aria-label="Kirim" @click="send">
          <Icon :name="sending ? 'sync' : 'send'" :spin="sending" />
        </button>
      </div>
      <div v-if="!app.online" class="tiny muted">Offline — pesan bisa dikirim setelah tersambung.</div>
    </div>
    <div v-else-if="data" class="readonly tiny muted"><Icon name="info" /> Anda hanya bisa membaca pesan.</div>
  </div>
</template>

<style scoped>
.thread { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.thread.pane { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
.thead { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--card); border-bottom: 1px solid var(--line); }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; background: var(--brand-soft); color: var(--brand); font-weight: 800; flex: none; }
.name { font-weight: 800; }
.icon-only { padding-left: 10px; padding-right: 10px; }
.msgs { flex: 1; min-height: 0; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; background: var(--bg); }
.day { text-align: center; margin: 8px 0 4px; }
.day span { font-size: 11px; font-weight: 700; color: var(--muted); background: var(--card); padding: 3px 10px; border-radius: 99px; box-shadow: var(--shadow); }
.msg { display: flex; }
.msg.host, .msg.internalNote { justify-content: flex-end; }
.msg.system { justify-content: center; }
.bubble { max-width: min(78%, 520px); padding: 8px 12px 6px; border-radius: 16px; background: var(--card); box-shadow: 0 1px 1px rgba(0,0,0,.08); border-bottom-left-radius: 4px; }
.host .bubble { background: var(--brand); color: var(--brand-ink); border-bottom-left-radius: 16px; border-bottom-right-radius: 4px; }
.internalNote .bubble { background: color-mix(in srgb, #fbbf24 22%, var(--card)); border: 1px dashed #d97706; border-bottom-left-radius: 16px; border-bottom-right-radius: 4px; }
.note-tag { font-size: 11px; font-weight: 700; color: #b45309; margin-bottom: 2px; }
.txt { white-space: pre-wrap; word-break: break-word; font-size: 15px; line-height: 1.35; }
.t { font-size: 10px; opacity: .7; text-align: right; margin-top: 2px; }
.sys { font-size: 12px; color: var(--muted); background: var(--card); border-radius: 10px; padding: 5px 10px; max-width: 90%; text-align: center; }
.sys .t { display: inline; margin-left: 4px; }
.att-img img { display: block; max-width: 100%; max-height: 240px; border-radius: 10px; margin-bottom: 4px; }
.att-file { display: inline-flex; gap: 6px; align-items: center; font-weight: 700; text-decoration: underline; color: inherit; margin-bottom: 4px; }
.composer { padding: 8px 10px; background: var(--card); border-top: 1px solid var(--line); }
.composer.internal { background: color-mix(in srgb, #fbbf24 14%, var(--card)); }
.crow { gap: 6px; align-items: flex-end; }
.composer textarea { border: 1px solid var(--line); border-radius: 18px; padding: 9px 14px; font: inherit; font-size: 15px; resize: none; max-height: 120px; min-height: 40px; background: var(--bg); color: var(--ink); field-sizing: content; }
.btn.on { background: #fbbf24; color: #3b2a12; }
.send { border-radius: 50%; width: 42px; height: 42px; padding: 0; }
.file-chip { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; padding: 6px 8px; border-radius: 12px; background: var(--bg); }
.file-chip img { width: 40px; height: 40px; object-fit: cover; border-radius: 8px; }
.readonly { padding: 10px 14px; background: var(--card); border-top: 1px solid var(--line); }
@media (max-width: 420px) { .hide-xs { display: none; } }
</style>
