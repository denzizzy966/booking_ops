<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { call, cached } from '../lib/api'
import { STATUS, STAY, fmtDate, fmtDateTime, money, channelLabel, waLink, guests, today } from '../lib/util'
import Sheet from './Sheet.vue'

const props = defineProps({ id: { type: String, required: true }, pane: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const app = useApp()
const router = useRouter()

const b = ref(null)
const stale = ref(false)
const loading = ref(true)
const busy = ref('')
const error = ref('')
const cancelOpen = ref(false)
const reason = ref('')
const armed = ref('') // aksi berisiko (Tidak datang) perlu ketukan kedua

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await cached(`booking.${props.id}`, 'get_booking', { booking_id: props.id })
    b.value = r.data
    stale.value = r.stale
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
watch(() => props.id, load, { immediate: true })

const cur = computed(() => (b.value && b.value.currency) || app.currency)
const balance = computed(() => (b.value ? Math.max(Number(b.value.price || 0) - Number(b.value.paid || 0), 0) : 0))
const active = computed(() => b.value && ['confirmed', 'new', 'request'].includes(b.value.status))
const arrived = computed(() => b.value && b.value.arrival <= today())
const stay = computed(() => (b.value && STAY[b.value.stay_status]) || STAY.Expected)
const phone = computed(() => b.value && (b.value.mobile || b.value.phone))
const so = computed(() => b.value && b.value.sales_order_info)
const charges = computed(() => (b.value ? (b.value.invoice_items || []).filter((i) => i.type === 'charge') : []))
const payments = computed(() => (b.value ? (b.value.invoice_items || []).filter((i) => i.type === 'payment') : []))
const lineTotal = (i) => (i.lineTotal != null ? Number(i.lineTotal) : Number(i.qty || 1) * Number(i.amount || 0))

const actions = computed(() => {
  if (!b.value || !active.value) return []
  const out = []
  const fd = app.can('front_desk')
  const s = b.value.stay_status
  if (fd && s === 'Expected' && arrived.value) out.push({ key: 'check_in', label: 'Check-in', icon: 'checkin', cls: 'ok' })
  if (fd && s === 'Checked In') out.push({ key: 'check_out', label: 'Check-out', icon: 'checkout', cls: 'brand' })
  if (fd && s === 'Expected' && arrived.value) out.push({ key: 'no_show', label: 'Tidak datang', icon: 'noshow', cls: '' })
  if (fd && s !== 'Expected' && app.user.is_manager) out.push({ key: 'undo', label: 'Batalkan status', icon: 'undo', cls: '' })
  return out
})

async function stayAction(key) {
  if (key === 'no_show' && armed.value !== key) {
    armed.value = key
    setTimeout(() => (armed.value = ''), 4000)
    return
  }
  armed.value = ''
  busy.value = key
  try {
    b.value = await call('set_stay_status', { booking_id: props.id, action: key }, { post: true })
    app.notify({ check_in: 'Check-in tercatat', check_out: 'Check-out tercatat', no_show: 'Ditandai tidak datang', undo: 'Status inap dikembalikan' }[key], 'success')
    emit('changed', b.value)
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}

async function doCancel() {
  busy.value = 'cancel'
  try {
    b.value = await call('cancel_booking', { booking_id: props.id, reason: reason.value }, { post: true })
    cancelOpen.value = false
    app.notify('Booking dibatalkan di Beds24', 'success')
    emit('changed', b.value)
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}

async function resync() {
  busy.value = 'sync'
  try {
    b.value = await call('resync_booking', { booking_id: props.id }, { post: true })
    app.notify('Data booking & Sales Order diperbarui', 'success')
    emit('changed', b.value)
  } catch (e) {
    app.notify(e.message, 'error')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <div class="bd">
    <div v-if="loading && !b" class="card"><div class="skel skel-line" v-for="i in 6" :key="i"></div></div>
    <div v-else-if="error" class="empty"><div class="big"><Icon name="warn" /></div>{{ error }}</div>
    <template v-else-if="b">
      <div v-if="stale" class="banner-offline mb12"><Icon name="warn" /> Data terakhir tersimpan (offline)</div>

      <!-- Kepala -->
      <div class="card head">
        <div class="row between">
          <div class="grow">
            <div class="guest">{{ b.guest_name }}</div>
            <div class="small muted">#{{ b.booking_id }} · {{ channelLabel(b.channel) }}<template v-if="b.api_reference"> · {{ b.api_reference }}</template></div>
          </div>
          <div class="badges">
            <span class="badge-status" :class="STATUS[b.status]?.cls">{{ STATUS[b.status]?.label || b.status }}</span>
            <span v-if="b.status !== 'cancelled'" class="badge-status" :class="stay.cls">{{ stay.label }}</span>
          </div>
        </div>
        <div class="contact mt12">
          <a v-if="phone" class="btn sm" :href="`tel:${phone}`"><Icon name="phone" /> Telepon</a>
          <a v-if="phone" class="btn sm" :href="waLink(phone)" target="_blank" rel="noopener"><Icon name="chat" /> WhatsApp</a>
          <a v-if="b.email" class="btn sm" :href="`mailto:${b.email}`"><Icon name="mail" /> Email</a>
          <router-link v-if="app.can('messages') && (b.message_count || app.can('reply_message'))" class="btn sm msg-btn" :to="`/messages/${b.booking_id}`">
            <Icon name="messages" /> Pesan<template v-if="b.message_count"> · {{ b.message_count }}</template>
            <i v-if="b.unread_messages" class="nbadge inline">{{ b.unread_messages }}</i>
          </router-link>
        </div>
      </div>

      <!-- Aksi front desk -->
      <div v-if="actions.length" class="actions mt12">
        <button v-for="a in actions" :key="a.key" class="btn" :class="a.cls" :disabled="!!busy || !app.online" @click="stayAction(a.key)">
          <Icon :name="busy === a.key ? 'sync' : a.icon" :spin="busy === a.key" /> {{ armed === a.key ? 'Ketuk lagi untuk yakin' : a.label }}
        </button>
      </div>

      <div v-if="b.sync_state === 'Error' || b.sync_state === 'Needs Review'" class="alert mt12">
        <Icon name="warn" />
        <div class="grow">
          <b>{{ b.sync_state === 'Error' ? 'Sales Order gagal dibuat' : 'Perlu ditinjau' }}</b>
          <div class="small">{{ b.sync_error }}</div>
        </div>
        <button class="btn sm" :disabled="!!busy || !app.online" @click="resync"><Icon name="sync" :spin="busy === 'sync'" /> Coba lagi</button>
      </div>

      <div class="grid2 mt12">
        <!-- Menginap -->
        <div class="card">
          <div class="card-title"><Icon name="bed" /> Menginap</div>
          <div class="stay-dates">
            <div>
              <div class="tiny muted">Kedatangan</div>
              <div class="big-date">{{ fmtDate(b.arrival) }}</div>
              <div class="tiny muted">{{ b.arrival_time ? 'Jam ' + b.arrival_time : '' }}</div>
            </div>
            <div class="nights">{{ b.nights }} <span>malam</span></div>
            <div class="right">
              <div class="tiny muted">Keberangkatan</div>
              <div class="big-date">{{ fmtDate(b.departure) }}</div>
            </div>
          </div>
          <dl class="kv">
            <dt>Kamar</dt><dd>{{ b.room_name || '—' }}<template v-if="b.unit_name"> · {{ b.unit_name }}</template><template v-if="b.room_qty > 1"> × {{ b.room_qty }}</template></dd>
            <dt>Tamu</dt><dd>{{ guests(b) }}</dd>
            <dt v-if="app.properties.length > 1">Properti</dt><dd v-if="app.properties.length > 1">{{ b.property_name }}</dd>
            <dt v-if="b.checked_in_at">Check-in</dt><dd v-if="b.checked_in_at">{{ fmtDateTime(b.checked_in_at) }}</dd>
            <dt v-if="b.checked_out_at">Check-out</dt><dd v-if="b.checked_out_at">{{ fmtDateTime(b.checked_out_at) }}</dd>
          </dl>
        </div>

        <!-- Harga -->
        <div class="card">
          <div class="card-title"><Icon name="money" /> Pembayaran</div>
          <dl class="kv">
            <dt>Total</dt><dd class="strong">{{ money(b.price, cur) }}</dd>
            <dt>Sudah dibayar</dt><dd>{{ money(b.paid, cur) }}</dd>
            <dt>Sisa</dt><dd :class="{ due: balance > 0 }">{{ money(balance, cur) }}</dd>
            <dt v-if="b.deposit">Deposit</dt><dd v-if="b.deposit">{{ money(b.deposit, cur) }}</dd>
            <dt v-if="b.commission">Komisi channel</dt><dd v-if="b.commission">{{ money(b.commission, cur) }}</dd>
          </dl>
          <div v-if="charges.length || payments.length" class="inv mt8">
            <div v-for="(i, n) in charges" :key="'c' + n" class="inv-row"><span class="grow truncate">{{ i.description }} <span class="muted">× {{ i.qty }}</span></span><span>{{ money(lineTotal(i), cur) }}</span></div>
            <div v-for="(i, n) in payments" :key="'p' + n" class="inv-row pay"><span class="grow truncate">{{ i.description || 'Pembayaran' }}</span><span>− {{ money(Math.abs(lineTotal(i)), cur) }}</span></div>
          </div>
        </div>

        <!-- Kontak -->
        <div class="card">
          <div class="card-title"><Icon name="user" /> Tamu</div>
          <dl class="kv">
            <dt>Nama</dt><dd>{{ [b.title, b.first_name, b.last_name].filter(Boolean).join(' ') || b.guest_name }}</dd>
            <dt v-if="b.company_name">Perusahaan</dt><dd v-if="b.company_name">{{ b.company_name }}</dd>
            <dt>HP</dt><dd>{{ phone || '—' }}</dd>
            <dt>Email</dt><dd class="truncate">{{ b.email || '—' }}</dd>
            <dt v-if="b.country">Negara</dt><dd v-if="b.country">{{ b.country }}</dd>
          </dl>
          <div v-if="b.comments" class="note mt8"><div class="tiny muted">Catatan tamu</div>{{ b.comments }}</div>
          <div v-if="b.notes" class="note mt8"><div class="tiny muted">Catatan internal</div>{{ b.notes }}</div>
        </div>

        <!-- Sales Order -->
        <div v-if="app.can('sales_order')" class="card">
          <div class="card-title"><Icon name="invoice" /> Sales Order ERPNext</div>
          <template v-if="so">
            <div class="row between">
              <b>{{ so.name }}</b>
              <span class="badge-status" :class="so.docstatus === 1 ? 's-confirmed' : so.docstatus === 2 ? 's-cancelled' : 's-request'">{{ so.status }}</span>
            </div>
            <dl class="kv mt8">
              <dt>Customer</dt><dd>{{ so.customer_name }}</dd>
              <dt>Subtotal</dt><dd>{{ money(so.net_total, so.currency) }}</dd>
              <dt v-if="so.total_taxes">Pajak</dt><dd v-if="so.total_taxes">{{ money(so.total_taxes, so.currency) }}</dd>
              <dt>Grand total</dt><dd class="strong">{{ money(so.grand_total, so.currency) }}</dd>
              <dt>Ditagih</dt><dd>{{ Math.round(so.per_billed || 0) }}%</dd>
            </dl>
            <a v-if="app.user.is_manager" class="btn sm ghost mt8" :href="so.desk_url" target="_blank"><Icon name="external" /> Buka di ERPNext</a>
          </template>
          <div v-else class="small muted">{{ b.sync_state === 'Skipped' ? 'Status booking ini tidak dibuatkan Sales Order.' : 'Belum ada Sales Order.' }}</div>
        </div>
      </div>

      <!-- Riwayat -->
      <div v-if="b.log && b.log.length" class="card mt12">
        <div class="card-title"><Icon name="clock" /> Riwayat</div>
        <div v-for="(l, i) in b.log" :key="i" class="log-row">
          <span class="dot" :class="l.status === 'Error' ? 'err' : ''"></span>
          <div class="grow">
            <div class="small"><b>{{ l.event }}</b> <span class="muted">· {{ l.direction }}</span></div>
            <div class="tiny muted">{{ fmtDateTime(l.creation) }}<template v-if="l.message"> · {{ l.message }}</template></div>
          </div>
        </div>
      </div>

      <!-- Ubah / batal -->
      <div v-if="active && (app.can('edit_booking') || app.can('bookings'))" class="row mt12 foot">
        <button v-if="app.can('edit_booking')" class="btn" :disabled="!app.online" @click="router.push(`/booking/${b.booking_id}/edit`)"><Icon name="edit" /> Ubah</button>
        <button class="btn" :disabled="!!busy || !app.online" @click="resync"><Icon name="sync" :spin="busy === 'sync'" /> Sinkron</button>
        <div class="grow"></div>
        <button v-if="app.can('edit_booking')" class="btn danger" :disabled="!app.online" @click="cancelOpen = true"><Icon name="cancel" /> Batalkan</button>
      </div>
    </template>

    <Sheet v-if="cancelOpen" title="Batalkan booking" @close="cancelOpen = false">
      <p class="small">Booking <b>#{{ b.booking_id }} · {{ b.guest_name }}</b> akan dibatalkan di Beds24. Sales Order yang belum ditagih ikut dibatalkan.</p>
      <div class="field">
        <label>Alasan (masuk ke catatan Beds24)</label>
        <textarea v-model="reason" rows="3" placeholder="Mis. tamu membatalkan via telepon"></textarea>
      </div>
      <button class="btn danger block" :disabled="busy === 'cancel'" @click="doCancel"><Icon name="cancel" /> Ya, batalkan booking</button>
    </Sheet>
  </div>
</template>

<style scoped>
.head .guest { font-size: 20px; font-weight: 800; line-height: 1.2; }
.badges { display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }
.contact { display: flex; gap: 8px; flex-wrap: wrap; }
.msg-btn { position: relative; }
.nbadge.inline { position: static; margin-left: 2px; box-shadow: none; }
.actions { display: flex; gap: 8px; }
.actions .btn { flex: 1; }
.alert { display: flex; gap: 10px; align-items: center; padding: 12px; border-radius: 14px; background: color-mix(in srgb, var(--warn) 14%, var(--card)); color: var(--ink); border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent); }
.alert > .ico { color: var(--warn); font-size: 18px; }
.card-title { font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; margin-bottom: 10px; display: flex; gap: 6px; align-items: center; }
.stay-dates { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.stay-dates > div:first-child, .stay-dates .right { flex: 1; }
.stay-dates .right { text-align: right; }
.big-date { font-weight: 800; font-size: 16px; }
.nights { background: var(--brand-soft); color: var(--brand); border-radius: 12px; padding: 6px 10px; font-weight: 800; text-align: center; }
.nights span { font-size: 11px; font-weight: 600; display: block; }
.kv { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; margin: 0; font-size: 14px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; text-align: right; min-width: 0; }
.kv .strong { font-weight: 800; }
.kv .due { color: var(--danger); font-weight: 700; }
.inv { border-top: 1px dashed var(--line); padding-top: 8px; }
.inv-row { display: flex; gap: 8px; font-size: 13px; padding: 3px 0; }
.inv-row.pay { color: var(--ok); }
.note { background: var(--bg); border-radius: 10px; padding: 8px 10px; font-size: 14px; white-space: pre-wrap; }
.log-row { display: flex; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--line); }
.log-row:last-child { border-bottom: 0; }
.log-row .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); margin-top: 6px; flex: none; }
.log-row .dot.err { background: var(--danger); }
.foot { flex-wrap: wrap; }
.mb12 { margin-bottom: 12px; }
</style>
