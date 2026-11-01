<script setup>
import { ref, computed } from 'vue'
import { useApp } from '../stores/app'

// Ajakan pasang PWA ke layar utama. Android/Chrome/Edge: tombol (beforeinstallprompt).
// iPhone/iPad (Safari tidak punya tombol pasang): tampilkan langkah manual.
const props = defineProps({
  force: { type: Boolean, default: false }, // tetap tampil walau pernah ditutup (halaman Lainnya)
  dark: { type: Boolean, default: false } // di atas latar gelap (layar login)
})
const app = useApp()
const steps = ref(false)
const icon = import.meta.env.BASE_URL + 'icon-192.png'
const visible = computed(() => !app.isStandalone && (app.installPrompt || app.isIOS) && (props.force || !app.prefs.installDismissed))

async function install() {
  if (app.installPrompt) await app.promptInstall()
  else steps.value = !steps.value
}
</script>

<template>
  <div v-if="visible" class="install" :class="{ dark }">
    <div class="row">
      <img :src="icon" alt="" class="ic" />
      <div class="grow">
        <b>Pasang aplikasi</b>
        <div class="tiny">Buka langsung dari layar utama, layar penuh seperti aplikasi.</div>
      </div>
      <button class="btn sm brand" @click="install">{{ app.installPrompt ? 'Pasang' : 'Caranya' }}</button>
      <button v-if="!force" class="x" aria-label="Tutup" @click="app.setPref('installDismissed', 1)"><Icon name="close" /></button>
    </div>
    <ol v-if="steps" class="steps small">
      <li>Buka halaman ini di <b>Safari</b>.</li>
      <li>Ketuk tombol <b>Bagikan</b> (kotak dengan panah ke atas).</li>
      <li>Pilih <b>Tambah ke Layar Utama</b>, lalu <b>Tambah</b>.</li>
    </ol>
  </div>
</template>

<style scoped>
.install { background: var(--card); color: var(--ink); border-radius: 16px; padding: 12px; box-shadow: var(--shadow); border: 1px solid color-mix(in srgb, var(--brand) 35%, transparent); }
.install.dark { background: rgba(255,255,255,.06); color: #e9dfd2; border-color: rgba(164,137,108,.35); box-shadow: none; }
.install .tiny { opacity: .75; }
.ic { width: 42px; height: 42px; border-radius: 10px; flex: none; }
.x { border: 0; background: none; color: inherit; opacity: .6; width: 32px; height: 32px; flex: none; }
.steps { margin: 10px 0 2px; padding-left: 20px; line-height: 1.6; }
</style>
