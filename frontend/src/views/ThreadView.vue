<script setup>
import { useRoute } from 'vue-router'
import AppBar from '../components/AppBar.vue'
import ThreadPanel from '../components/ThreadPanel.vue'

const route = useRoute()
</script>

<template>
  <AppBar title="Pesan" back />
  <div class="thread-host">
    <ThreadPanel :id="String(route.params.id)" />
  </div>
</template>

<style scoped>
/* Isi setinggi layar: daftar pesan menggulir, kotak balas tetap di bawah (di atas tab bar HP). */
.thread-host { flex: 1; min-height: 0; display: flex; flex-direction: column; padding-bottom: calc(var(--tabbar-h) + var(--safe-bottom)); }
@media (min-width: 768px) {
  .thread-host { padding: 16px 20px; max-width: 900px; width: 100%; margin: 0 auto; }
  .thread-host :deep(.thread) { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
}
</style>
