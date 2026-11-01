const pad = (n) => String(n).padStart(2, '0')

export function iso(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
export function parse(s) {
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}
export function addDays(s, n) {
  const d = parse(s)
  d.setDate(d.getDate() + n)
  return iso(d)
}
export function today() {
  return iso(new Date())
}
export function diffDays(a, b) {
  return Math.round((parse(b) - parse(a)) / 86400000)
}

const DAY = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab']
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
const MONTH = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

export function fmtDate(s, { day = true, year = false } = {}) {
  if (!s) return '—'
  const d = parse(s)
  const head = day ? `${DAY[d.getDay()]}, ` : ''
  return `${head}${d.getDate()} ${MON[d.getMonth()]}${year ? ' ' + d.getFullYear() : ''}`
}
export function fmtMonth(s) {
  const d = parse(s)
  return `${MONTH[d.getMonth()]} ${d.getFullYear()}`
}
export function dayName(s) {
  return DAY[parse(s).getDay()]
}
export function fmtDateTime(s) {
  if (!s) return '—'
  const [d, t] = String(s).split(' ')
  return `${fmtDate(d, { day: false })} ${(t || '').slice(0, 5)}`
}
export function relDay(s) {
  const n = diffDays(today(), s)
  if (n === 0) return 'Hari ini'
  if (n === 1) return 'Besok'
  if (n === -1) return 'Kemarin'
  return fmtDate(s)
}

export function money(v, currency = 'IDR') {
  const n = Number(v || 0)
  try {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency,
      maximumFractionDigits: currency === 'IDR' ? 0 : 2
    }).format(n)
  } catch {
    return `${currency} ${n.toLocaleString('id-ID')}`
  }
}
export function compact(v) {
  const n = Number(v || 0)
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1).replace('.', ',') + ' M'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1).replace('.', ',') + ' jt'
  if (Math.abs(n) >= 1e3) return Math.round(n / 1e3) + ' rb'
  return String(Math.round(n))
}

export const STATUS = {
  confirmed: { label: 'Confirmed', cls: 's-confirmed' },
  new: { label: 'Baru', cls: 's-new' },
  request: { label: 'Request', cls: 's-request' },
  inquiry: { label: 'Inquiry', cls: 's-inquiry' },
  black: { label: 'Diblokir', cls: 's-black' },
  cancelled: { label: 'Batal', cls: 's-cancelled' }
}
export const STAY = {
  Expected: { label: 'Belum datang', cls: 's-expected' },
  'Checked In': { label: 'Menginap', cls: 's-in' },
  'Checked Out': { label: 'Sudah keluar', cls: 's-out' },
  'No Show': { label: 'Tidak datang', cls: 's-noshow' }
}
const CHANNEL = {
  booking: 'Booking.com',
  airbnb: 'Airbnb',
  expedia: 'Expedia',
  agoda: 'Agoda',
  traveloka: 'Traveloka',
  tiket: 'tiket.com',
  trip: 'Trip.com',
  direct: 'Langsung',
  bookingpage: 'Website',
  hostelworld: 'Hostelworld',
  vrbo: 'Vrbo'
}
export function channelLabel(c) {
  if (!c) return 'Langsung'
  return CHANNEL[String(c).toLowerCase()] || c
}
export function waLink(phone) {
  let d = String(phone || '').replace(/\D/g, '')
  if (d.startsWith('0')) d = '62' + d.slice(1)
  return d ? `https://wa.me/${d}` : ''
}
export function guests(b) {
  const a = Number(b.num_adult || 0)
  const c = Number(b.num_child || 0)
  return `${a} dewasa${c ? ` · ${c} anak` : ''}`
}
export function pct(v) {
  return `${String(Number(v || 0)).replace('.', ',')}%`
}
// Waktu pesan di daftar: jam (hari ini), "Kemarin", atau tanggal.
export function fmtMsgTime(s) {
  if (!s) return ''
  const d = String(s).slice(0, 10)
  const n = diffDays(d, today())
  if (n === 0) return String(s).slice(11, 16)
  if (n === 1) return 'Kemarin'
  return fmtDate(d, { day: false })
}
