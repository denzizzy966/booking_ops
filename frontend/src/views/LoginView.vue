<script setup>
import { ref } from 'vue'
import InstallBanner from '../components/InstallBanner.vue'

// Login ERPNext langsung dari PWA (tanpa pindah ke /login desk). Sukses → muat ulang /booking_ops
// supaya halaman membawa sesi + CSRF token user yang baru.
const logo = import.meta.env.BASE_URL + 'rmi-logo.png'
const usr = ref('')
const pwd = ref('')
const show = ref(false)
const busy = ref(false)
const err = ref('')

async function login() {
  if (!usr.value.trim() || !pwd.value) {
    err.value = 'Isi email/username dan password.'
    return
  }
  busy.value = true
  err.value = ''
  try {
    const res = await fetch('/api/method/login', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ usr: usr.value.trim(), pwd: pwd.value }),
      credentials: 'same-origin'
    })
    const j = await res.json().catch(() => ({}))
    if (res.ok && j.verification) {
      // Akun dengan verifikasi 2 langkah → pakai halaman login ERPNext yang mendukung OTP.
      window.location.href = '/login?redirect-to=/booking_ops'
      return
    }
    if (res.ok) {
      localStorage.removeItem('bookingops.bootstrap')
      // Muat ulang penuh (bukan sekadar ganti #hash, yang tidak me-reload) → sesi + CSRF baru, buka Beranda.
      window.history.replaceState(null, '', '/booking_ops')
      window.location.reload()
      return
    }
    err.value =
      res.status === 401 ? 'Email/username atau password salah.'
      : res.status === 429 ? 'Terlalu banyak percobaan. Coba lagi beberapa menit lagi.'
      : (typeof j.message === 'string' && j.message) || `Gagal masuk (HTTP ${res.status}).`
  } catch {
    err.value = 'Tidak ada koneksi ke server.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login-inner">
      <img class="logo" :src="logo" alt="Real Magick Indonesia" />
      <h1>Booking Ops</h1>
      <p class="sub">Booking Beds24 &amp; Sales Order ERPNext</p>

      <form class="login-card" @submit.prevent="login">
        <div class="field">
          <label for="usr">Email / username</label>
          <input id="usr" v-model="usr" type="text" autocomplete="username" autocapitalize="off" spellcheck="false" inputmode="email" placeholder="nama@perusahaan.com" />
        </div>
        <div class="field">
          <label for="pwd">Password</label>
          <div class="pw">
            <input id="pwd" v-model="pwd" :type="show ? 'text' : 'password'" autocomplete="current-password" placeholder="••••••••" />
            <button type="button" class="eye" :aria-label="show ? 'Sembunyikan password' : 'Tampilkan password'" @click="show = !show"><Icon :name="show ? 'eyeoff' : 'eye'" /></button>
          </div>
        </div>
        <div v-if="err" class="err" role="alert"><Icon name="warn" /> {{ err }}</div>
        <button class="btn brand block" type="submit" :disabled="busy">
          <Icon v-if="busy" name="sync" spin /> {{ busy ? 'Masuk…' : 'Masuk' }}
        </button>
        <a class="forgot tiny" href="/login#forgot">Lupa password?</a>
      </form>

      <InstallBanner class="mt12" dark />
      <p class="foot">© Real Magick Indonesia · ERPNext</p>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 100%; overflow-y: auto; display: flex; justify-content: center; align-items: center; padding: calc(var(--safe-top) + 28px) 20px calc(var(--safe-bottom) + 24px); background: linear-gradient(160deg, #2e251b, #1a140e); color: #e9dfd2; }
.login-inner { width: 100%; max-width: 400px; }
.logo { width: 132px; height: 132px; display: block; margin: 0 auto 6px; }
h1 { text-align: center; margin: 0; font-size: 22px; letter-spacing: .3em; padding-left: .3em; text-transform: uppercase; color: #a4896c; font-weight: 600; }
.sub { text-align: center; margin: 6px 0 22px; font-size: 13px; opacity: .75; }
.login-card { background: var(--card); color: var(--ink); border-radius: 20px; padding: 22px; box-shadow: 0 12px 40px rgba(0,0,0,.35); }
.field label { display: block; font-size: 13px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.field input { width: 100%; border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; font: inherit; font-size: 16px; background: var(--bg); color: var(--ink); }
.field input:focus { outline: 2px solid var(--brand); outline-offset: 0; border-color: transparent; }
.pw { position: relative; }
.pw input { padding-right: 48px; }
.eye { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); border: 0; background: none; color: var(--muted); width: 40px; height: 40px; font-size: 17px; }
.err { background: color-mix(in srgb, var(--danger) 12%, var(--card)); color: var(--danger); border-radius: 10px; padding: 10px 12px; font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.block { width: 100%; height: 48px; font-size: 16px; }
.forgot { display: block; text-align: center; margin-top: 14px; color: var(--muted); }
.foot { text-align: center; font-size: 11px; opacity: .5; margin: 18px 0 0; letter-spacing: .05em; }
</style>
