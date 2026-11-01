<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { call } from '../lib/api'
import { addDays, today, diffDays, fmtDate, money } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import SearchSelect from '../components/SearchSelect.vue'

const app = useApp()
const route = useRoute()
const router = useRouter()
const editId = computed(() => (route.name === 'edit' ? String(route.params.id) : ''))

const f = reactive({
  property: app.property || (app.properties.length === 1 ? app.properties[0].property_id : ''),
  arrival: route.query.arrival || today(),
  departure: route.query.departure || addDays(route.query.arrival || today(), 1),
  num_adult: 2,
  num_child: 0,
  room: route.query.room || '',
  unit_id: route.query.unit || '',
  title: '',
  first_name: '',
  last_name: '',
  mobile: '',
  email: '',
  country: '',
  company_name: '',
  arrival_time: '',
  price: '',
  deposit: '',
  status: 'confirmed',
  comments: '',
  notes: '',
  notify_guest: false
})
const original = ref(null)
const avail = ref(null)
const checking = ref(false)
const saving = ref(false)
const errors = ref('')
const priceTouched = ref(false)

const nights = computed(() => Math.max(diffDays(f.arrival, f.departure), 0))
const cur = computed(() => app.currencyFor(f.property || (avail.value && avail.value.rooms[0] && avail.value.rooms[0].property)))
const propOptions = computed(() => app.properties.map((p) => ({ value: p.property_id, label: p.property_name })))
const roomsList = computed(() => (avail.value ? avail.value.rooms : app.roomsFor(f.property).map((r) => ({ ...r, units_available: null, price: null, free_units: r.units }))))
const chosen = computed(() => roomsList.value.find((r) => r.room_id === f.room))
const unitOptions = computed(() => {
  const r = chosen.value
  if (!r) return []
  const list = (r.free_units || []).map((u) => ({ value: String(u.id), label: u.name }))
  if (f.unit_id && !list.some((u) => u.value === String(f.unit_id))) {
    const u = (app.rooms.find((x) => x.room_id === r.room_id)?.units || []).find((x) => String(x.id) === String(f.unit_id))
    if (u) list.unshift({ value: String(u.id), label: `${u.name} (terisi?)` })
  }
  return [{ value: '', label: 'Otomatis (Beds24 memilih)' }, ...list]
})
const roomFull = (r) => r.units_available === 0 && !(original.value && original.value.room === r.room_id)
const guestsTooMany = (r) => r.max_people && Number(f.num_adult) + Number(f.num_child) > r.max_people

onMounted(async () => {
  if (!editId.value) return
  try {
    const b = await call('get_booking', { booking_id: editId.value })
    original.value = b
    for (const k of Object.keys(f)) if (k in b && b[k] != null) f[k] = typeof f[k] === 'number' ? Number(b[k]) : String(b[k])
    f.num_adult = Number(b.num_adult || 1)
    f.num_child = Number(b.num_child || 0)
    f.notify_guest = false
    priceTouched.value = true
  } catch (e) {
    app.notify(e.message, 'error')
  }
})

let timer = null
watch(() => [f.arrival, f.departure, f.num_adult, f.num_child, f.property], () => {
  if (f.departure <= f.arrival) f.departure = addDays(f.arrival, 1)
  clearTimeout(timer)
  timer = setTimeout(check, 400)
}, { immediate: true })

async function check() {
  if (nights.value < 1 || !app.online) return
  checking.value = true
  try {
    avail.value = await call('availability', {
      arrival: f.arrival, departure: f.departure, property: f.property, num_adult: f.num_adult, num_child: f.num_child, exclude: editId.value
    })
    applyPrice()
  } catch (e) {
    avail.value = null
    app.notify(e.message, 'error')
  } finally {
    checking.value = false
  }
}
function applyPrice() {
  const r = chosen.value
  if (r && r.price != null && !priceTouched.value) f.price = String(r.price)
}
function pickRoom(r) {
  if (roomFull(r)) return
  f.room = r.room_id
  f.unit_id = ''
  if (!f.property) f.property = r.property
  applyPrice()
}
const step = (k, d, min) => (f[k] = Math.max(min, Number(f[k] || 0) + d))

function validate() {
  if (nights.value < 1) return 'Keberangkatan harus setelah kedatangan.'
  if (!f.room) return 'Pilih tipe kamar.'
  if (!f.first_name.trim() && !f.last_name.trim()) return 'Isi nama tamu.'
  if (f.email && !/^\S+@\S+\.\S+$/.test(f.email)) return 'Format email tidak valid.'
  return ''
}
async function save() {
  errors.value = validate()
  if (errors.value) return
  saving.value = true
  const data = { ...f, price: Number(f.price || 0), deposit: Number(f.deposit || 0), notify_guest: f.notify_guest ? 1 : 0 }
  delete data.property
  try {
    let b
    if (editId.value) {
      // kirim hanya yang berubah
      const diff = {}
      for (const k of Object.keys(data)) if (String(data[k] ?? '') !== String(original.value[k] ?? '')) diff[k] = data[k]
      delete diff.notify_guest
      b = await call('update_booking', { booking_id: editId.value, data: diff }, { post: true })
      app.notify('Perubahan tersimpan di Beds24', 'success')
    } else {
      b = await call('create_booking', { data }, { post: true })
      app.notify(`Booking #${b.booking_id} dibuat`, 'success')
    }
    router.replace(`/booking/${b.booking_id}`)
  } catch (e) {
    errors.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AppBar :title="editId ? `Ubah #${editId}` : 'Booking Baru'" back />
  <div class="content">
    <div v-if="!app.online" class="banner-offline mb12"><Icon name="warn" /> Butuh koneksi: ketersediaan dicek langsung ke Beds24.</div>
    <div class="form-grid">
      <div class="col">
        <div class="card">
          <div class="card-title"><Icon name="calendar" /> Tanggal & tamu</div>
          <div v-if="app.properties.length > 1" class="field">
            <label>Properti</label>
            <SearchSelect v-model="f.property" :options="propOptions" placeholder="Semua properti" clearable />
          </div>
          <div class="two">
            <div class="field"><label>Kedatangan</label><input type="date" v-model="f.arrival" :min="editId ? undefined : today()" /></div>
            <div class="field"><label>Keberangkatan</label><input type="date" v-model="f.departure" :min="addDays(f.arrival, 1)" /></div>
          </div>
          <div class="row between small muted nights-line">
            <span>{{ fmtDate(f.arrival) }} → {{ fmtDate(f.departure) }}</span><b class="nchip">{{ nights }} malam</b>
          </div>
          <div class="two mt12">
            <div class="field"><label>Dewasa</label>
              <div class="stepper"><button @click="step('num_adult', -1, 1)">−</button><span>{{ f.num_adult }}</span><button @click="step('num_adult', 1, 1)">+</button></div>
            </div>
            <div class="field"><label>Anak</label>
              <div class="stepper"><button @click="step('num_child', -1, 0)">−</button><span>{{ f.num_child }}</span><button @click="step('num_child', 1, 0)">+</button></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="row between card-title"><span><Icon name="bed" /> Pilih kamar</span>
            <button class="btn sm ghost" :disabled="checking || !app.online" @click="check"><Icon name="sync" :spin="checking" /> Cek</button>
          </div>
          <div v-if="avail && avail.warning" class="tiny warn-txt mb8"><Icon name="warn" /> Harga Beds24 tidak tersedia: {{ avail.warning }}</div>
          <div v-if="!roomsList.length" class="small muted">Belum ada kamar. Impor properti di Booking Ops Settings.</div>
          <button v-for="r in roomsList" :key="r.room_id" class="room" :class="{ on: f.room === r.room_id, full: roomFull(r) }" @click="pickRoom(r)">
            <div class="grow">
              <div class="rname">{{ r.room_name }}</div>
              <div class="tiny muted">
                Maks {{ r.max_people || '?' }} tamu
                <template v-if="app.properties.length > 1 && !f.property"> · {{ app.propertyName(r.property) }}</template>
                <span v-if="guestsTooMany(r)" class="warn-txt"> · melebihi kapasitas</span>
              </div>
            </div>
            <div class="rside">
              <span v-if="checking" class="tiny muted">…</span>
              <template v-else>
                <span class="badge-status" :class="roomFull(r) ? 's-cancelled' : r.units_available == null ? 's-expected' : 's-confirmed'">
                  {{ roomFull(r) ? 'Penuh' : r.units_available == null ? 'Belum dicek' : `${r.units_available} tersedia` }}
                </span>
                <div v-if="r.price != null" class="rprice">{{ money(r.price, cur) }}</div>
                <div v-if="r.price != null && nights" class="tiny muted">{{ money(r.price / nights, cur) }}/mlm</div>
              </template>
            </div>
          </button>
          <div v-if="chosen && unitOptions.length > 1" class="field mt12">
            <label>Unit / nomor kamar</label>
            <SearchSelect v-model="f.unit_id" :options="unitOptions" placeholder="Otomatis" />
          </div>
        </div>
      </div>

      <div class="col">
        <div class="card">
          <div class="card-title"><Icon name="user" /> Data tamu</div>
          <div class="two">
            <div class="field"><label>Nama depan *</label><input v-model="f.first_name" autocomplete="off" /></div>
            <div class="field"><label>Nama belakang</label><input v-model="f.last_name" autocomplete="off" /></div>
          </div>
          <div class="two">
            <div class="field"><label>No. HP / WhatsApp</label><input v-model="f.mobile" type="tel" inputmode="tel" placeholder="08…" /></div>
            <div class="field"><label>Email</label><input v-model="f.email" type="email" inputmode="email" /></div>
          </div>
          <div class="two">
            <div class="field"><label>Negara (kode 2 huruf)</label><input v-model="f.country" maxlength="2" placeholder="ID" style="text-transform: uppercase" /></div>
            <div class="field"><label>Perkiraan jam tiba</label><input v-model="f.arrival_time" type="time" /></div>
          </div>
          <div class="field"><label>Perusahaan</label><input v-model="f.company_name" /></div>
        </div>

        <div class="card">
          <div class="card-title"><Icon name="money" /> Harga & status</div>
          <div class="two">
            <div class="field"><label>Harga total ({{ cur }})</label><input v-model="f.price" type="number" inputmode="decimal" min="0" @input="priceTouched = true" /></div>
            <div class="field"><label>Deposit</label><input v-model="f.deposit" type="number" inputmode="decimal" min="0" /></div>
          </div>
          <div v-if="chosen && chosen.price != null && priceTouched && Number(f.price) !== chosen.price" class="tiny muted mb8">
            Harga Beds24: {{ money(chosen.price, cur) }} <button class="linkbtn" @click="priceTouched = false; applyPrice()">pakai</button>
          </div>
          <div class="field">
            <label>Status</label>
            <div class="seg">
              <button :class="{ active: f.status === 'confirmed' }" @click="f.status = 'confirmed'">Confirmed</button>
              <button :class="{ active: f.status === 'request' }" @click="f.status = 'request'">Request</button>
            </div>
          </div>
          <div class="field"><label>Catatan tamu</label><textarea v-model="f.comments" rows="2"></textarea></div>
          <div class="field"><label>Catatan internal</label><textarea v-model="f.notes" rows="2"></textarea></div>
          <label v-if="!editId" class="row between toggle">
            <span>Kirim email konfirmasi ke tamu</span>
            <span class="switch"><input type="checkbox" v-model="f.notify_guest" /><span class="slider"></span></span>
          </label>
        </div>

        <div v-if="errors" class="err-box"><Icon name="warn" /> {{ errors }}</div>
        <button class="btn brand block save" :disabled="saving || !app.online" @click="save">
          <Icon :name="saving ? 'sync' : 'check'" :spin="saving" /> {{ saving ? 'Menyimpan ke Beds24…' : editId ? 'Simpan perubahan' : 'Buat booking' }}
        </button>
        <p class="tiny muted mt8">Booking disimpan langsung di Beds24, lalu Sales Order ERPNext dibuat/diperbarui otomatis.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-title { font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; margin-bottom: 12px; display: flex; gap: 6px; align-items: center; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.two .field { margin-bottom: 10px; }
.nights-line { margin-top: -2px; }
.nchip { background: var(--brand-soft); color: var(--brand); padding: 3px 10px; border-radius: 99px; }
.stepper { display: flex; align-items: center; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--input-bg); }
.stepper button { width: 46px; height: 46px; border: 0; background: var(--brand-soft); color: var(--brand); font-size: 22px; font-weight: 700; }
.stepper span { flex: 1; text-align: center; font-weight: 800; font-size: 17px; }
.room { width: 100%; display: flex; gap: 10px; align-items: center; text-align: left; border: 2px solid var(--line); background: var(--card); color: var(--ink); border-radius: 14px; padding: 12px; }
.room + .room { margin-top: 8px; }
.room.on { border-color: var(--brand); background: var(--brand-soft); }
.room.full { opacity: .55; }
.rname { font-weight: 700; }
.rside { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.rprice { font-weight: 800; }
.warn-txt { color: var(--warn); }
.linkbtn { border: 0; background: none; color: var(--brand); font-weight: 700; padding: 0; }
.toggle { padding: 4px 0; font-size: 14px; font-weight: 600; }
.err-box { background: color-mix(in srgb, var(--danger) 12%, var(--card)); color: var(--danger); border-radius: 12px; padding: 10px 12px; font-weight: 600; margin-bottom: 12px; font-size: 14px; }
.save { padding: 15px; font-size: 16px; }
.mb8 { margin-bottom: 8px; } .mb12 { margin-bottom: 12px; }
.form-grid .col > .card + .card { margin-top: 12px; }
.form-grid .col + .col { margin-top: 12px; }
@media (min-width: 900px) {
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; max-width: 1100px; margin: 0 auto; }
  .form-grid .col + .col { margin-top: 0; }
}
</style>
