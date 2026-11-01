# Booking Ops

PWA (HP & tablet) untuk mengelola booking **Beds24** dari ERPNext v16. Setiap booking otomatis
dibuatkan **Sales Order** di ERPNext.

```
Beds24 (OTA: Booking.com, Airbnb, Agoda, …)
   │  webhook (instan)  +  tarik berkala tiap 5 menit (cadangan)
   ▼
Beds24 Booking (ERPNext)  ──►  Sales Order (+ Customer tamu / OTA)
   ▲
   │  buat / ubah / batalkan  (POST /bookings, cek ketersediaan)
PWA /booking_ops  ── check-in / check-out / no-show (dicatat di ERPNext + flag di kalender Beds24)
```

Beds24 tetap jadi sumber kebenaran untuk booking dan ketersediaan. ERPNext menyimpan salinan
booking, status inap (check-in/out tidak ada di Beds24), dan Sales Order.

## Fitur PWA (`/booking_ops`)

| Menu | Kunci role | Isi |
|---|---|---|
| Beranda | `dashboard` | Kedatangan / keberangkatan / menginap per tanggal, okupansi, pendapatan bulan ini, check-in/out sekali ketuk |
| Kalender | `calendar` | Timeline unit × tanggal (14 hari di HP, 21 di tablet); ketuk sel kosong → booking baru |
| Booking | `bookings` | Cari & filter (akan datang, menginap, selesai, batal, perlu perhatian); tablet: daftar + detail berdampingan |
| Booking Baru | `new_booking` | Tanggal → cek ketersediaan & harga Beds24 → pilih kamar/unit → data tamu → simpan ke Beds24 |
| (Detail) Ubah / Batalkan | `edit_booking` | Ubah tanggal, kamar, tamu, harga; batalkan dengan alasan |
| (Detail) Check-in/out | `front_desk` | Check-in, check-out, tidak datang (manajer bisa membatalkan status) |
| Ketersediaan | `availability` | Sisa unit & harga per malam dari kalender Beds24 |
| (Detail) Sales Order | `sales_order` | Ringkasan SO: status, total, % ditagih |
| Sinkronisasi | `sync` | Status koneksi, sinkron sekarang, booking bermasalah, log |
| Laporan | `reports` | Pendapatan, okupansi, ADR, per channel, per tipe kamar, ringkasan SO |

Navigasi menyesuaikan layar: tab bawah di HP, rail ikon di tablet (≥768 px), dan rail berlabel
di layar ≥1100 px. Data terakhir disimpan di perangkat, jadi layar tetap bisa dibaca saat
offline. Membuat atau mengubah booking butuh koneksi karena ketersediaan dicek langsung ke Beds24.

## Hak akses per menu

Role bawaan:
- **Booking Ops User**: membuka semua menu yang *tidak* punya baris di tabel akses.
- **Booking Ops Manager** (dan System Manager): selalu bisa semua menu.

Tabel **Booking Ops Settings → Akses Menu per Role**: kalau sebuah menu punya baris, hanya role
yang tercantum yang bisa membukanya. Contoh:

| Menu | Role |
|---|---|
| `front_desk` | Front Desk |
| `new_booking` | Reservasi |
| `edit_booking` | Reservasi |
| `reply_message` | Front Desk, Reservasi |
| `reports` | Booking Ops Manager |

Aturan ini juga ditegakkan di server pada setiap endpoint, tidak hanya menyembunyikan tombol.

## Pesan tamu

Pesan dari tamu (Airbnb, Booking.com, VRBO, dll.) diambil lewat Beds24 API
`GET/POST /bookings/messages`. Pesan disimpan di DocType **Beds24 Message**.

- **Menu Pesan:**
  - Daftar percakapan per booking, dengan badge jumlah pesan belum dibaca di tab bawah dan
    peringatan di Beranda.
  - Bisa dicari menurut nama, nomor booking, atau isi pesan.
- **Percakapan:**
  - Balas tamu; balasan diteruskan Beds24 ke channel-nya.
  - Lampirkan foto atau PDF, maksimal 5 MB. Foto besar diperkecil otomatis.
  - Tulis **catatan internal** yang tidak terkirim ke tamu.
  - Membuka percakapan menandai pesan tamu sudah dibaca, juga di Beds24.
- **Masuknya pesan:**
  - Ditarik berkala bersama sinkron 5 menit (setelan *Ambil Pesan Tamu*, *N hari terakhir*).
  - Ikut tersimpan bila payload webhook membawa `messages`.
  - Tombol ⟳ di menu Pesan menarik 30 hari terakhir.
  - Percakapan yang sedang terbuka dimuat ulang tiap 30 detik.
- **Hak akses:**
  - `messages`: melihat pesan.
  - `reply_message`: membalas dan menulis catatan.

  Membalas ditolak di server bila role tidak punya akses.

Catatan: webhook Beds24 terpicu oleh perubahan booking, bukan oleh pesan baru. Karena itu
pesan baru muncul paling lambat saat sinkron berkala berikutnya, dan itu butuh scheduler aktif.

## Mode Sandbox (coba tanpa akun Beds24)

Beds24 tidak menyediakan sandbox resmi, jadi app ini membawa **Beds24 tiruan** sendiri. Saat
**Booking Ops Settings → Mode Sandbox** dicentang, semua panggilan API dilayani di dalam server
(tanpa menghubungi beds24.com), dengan bentuk data yang sama seperti API v2 asli.

- Isinya 2 properti contoh, 4 tipe kamar, 11 unit, dan ±16 booking di sekitar tanggal hari ini.
  Datanya disimpan di `sites/<site>/private/booking_ops_sandbox.json`.
- Semua fitur berjalan sungguhan: kalender, booking baru/ubah/batal, check-in, laporan, dan
  **Sales Order ERPNext**.
- Tombol **Simulasi Booking Baru / Pembatalan dari OTA** (di Settings, dan di menu Sinkronisasi
  PWA) meniru booking dari Booking.com, Airbnb, dll. yang masuk lewat webhook.
- **Reset Data Sandbox** mengembalikan data contoh. Dokumen ERPNext yang sudah dibuat tidak
  dihapus.
- **Simulasi Pesan dari Tamu** meniru pesan masuk ke booking OTA yang aktif. Data contoh juga
  sudah berisi beberapa percakapan.
- PWA menampilkan label kuning **Sandbox** selama mode ini aktif.

Siapkan semuanya dengan satu perintah. Perintah ini mengisi setelan yang kosong, membuat Item
jasa `KAMAR-SANDBOX` bila perlu, mengimpor properti, lalu menarik booking:

```bash
bench --site <site> execute booking_ops.sandbox.setup_demo
# atau pilih company:  --kwargs "{'company': 'PT Contoh'}"
```

Sebelum memakai akun Beds24 asli, matikan Mode Sandbox, lalu hubungkan dengan invite code.
Booking dan properti contoh (ID 1001/1002, booking 50001 dst.) boleh dihapus.

## Setup

1. **Pasang app** (bundle PWA sudah ikut di repo, jadi server tidak perlu Node):
   ```bash
   bench get-app https://github.com/denzizzy966/booking_ops --branch main
   bench --site <site> install-app booking_ops
   bench --site <site> migrate   # membuat kunci webhook & custom field
   ```
2. **Beds24 → Settings → Apps & Integrations → API → Generate invite code**. Centang scope
   `bookings`, `bookings-personal`, `bookings-financial`, `inventory`, `properties`.
3. **ERPNext → Booking Ops Settings**:
   - Tempel invite code, lalu klik **Hubungkan ke Beds24**. Refresh token akan tersimpan
     terenkripsi, dan invite code dihapus karena hanya bisa dipakai sekali.
   - Klik **Ambil Properti & Kamar**. Setelah itu, di **Beds24 Room**, petakan tiap tipe kamar ke
     sebuah Item jasa (non-stok).
   - Isi bagian **Sales Order**:
     - Company, Item Kamar Default, Customer Default.
     - Opsional: Template Pajak, Price List, dan *Customer per Channel* (mis. `booking` →
       Customer "Booking.com" bila OTA yang membayar).
   - Klik **Sinkron Sekarang**. Tarikan pertama mengambil booking yang kedatangannya sejak N hari
     lalu.
4. **Webhook** (opsional tapi disarankan): salin *URL Webhook* dari Settings ke
   **Beds24 → Settings → Properties → Access → Booking Webhook**, versi *2 – with personal data*.
5. Berikan role ke user, lalu buka `/booking_ops` di HP atau tablet dan pasang ke layar utama.

## Aturan Sales Order

- Status **confirmed / new** (dan **request** bila dicentang) → SO dibuat:
  - Customer: per channel, lalu tamu (dicocokkan lewat email/HP, kalau tidak ada dibuat baru),
    lalu Customer Default.
  - Baris SO: satu baris kamar (qty = malam × kamar, rate = total / qty), atau rincian invoice
    Beds24.
  - Tanggal kirim = tanggal kedatangan. `po_no` = referensi channel.
- Booking **berubah**:
  - SO draft diperbarui di tempat.
  - SO submitted yang belum ditagih di-cancel lalu di-amend.
  - SO yang sudah ditagih atau dibayar → booking ditandai **Needs Review** dan tidak diubah
    otomatis.
- Booking **batal / diblokir / inquiry**:
  - SO draft dihapus.
  - SO submitted yang belum ditagih dibatalkan.
  - SO yang sudah ditagih → Needs Review.
- Gagal (mis. item belum dipetakan) → booking berstatus **Error** dengan pesannya. Perbaiki
  setelannya, lalu tekan **Sinkron / Coba lagi** di aplikasi.
- Perubahan dideteksi lewat sidik (hash) data SO, jadi sinkron ulang tidak membuat SO ganda.

## Pengembangan

```bash
cd frontend && npm install
npm run dev            # http://localhost:5174, proksi ke bench (FRAPPE_URL, FRAPPE_API_KEY/SECRET di .env)
npm run build:frappe   # → booking_ops/public/booking_ops + booking_ops/www/booking_ops/index.html
```

Bangun ulang dan commit bundle setiap kali frontend berubah.
