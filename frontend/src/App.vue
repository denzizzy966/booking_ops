<script setup>
import { onMounted, onBeforeUnmount } from 'vue'
import { useApp } from './stores/app'
import NavBar from './components/NavBar.vue'

const app = useApp()
// Badge pesan belum dibaca: cek tiap menit (dilewati saat tab tersembunyi / offline).
let timer = null
const onVisible = () => !document.hidden && app.refreshUnread()
onMounted(() => {
  timer = setInterval(() => app.refreshUnread(), 60000)
  document.addEventListener('visibilitychange', onVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisible)
})
const icon = import.meta.env.BASE_URL + 'icon-192.png'
</script>

<template>
  <div v-if="app.bootError" class="fatal">
    <img :src="icon" alt="" class="fatal-logo" />
    <h2>Booking Ops</h2>
    <p>{{ app.bootError }}</p>
    <div class="row" style="justify-content: center">
      <button class="btn brand" @click="app.load()"><Icon name="sync" /> Coba lagi</button>
      <a class="btn" href="/login?redirect-to=/booking_ops">Login</a>
    </div>
  </div>
  <div v-else class="layout">
    <NavBar />
    <main class="main">
      <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="['booking', 'thread'].includes(route.name) ? route.fullPath : route.name" />
      </router-view>
    </main>
    <transition name="fade">
      <div v-if="app.toast" class="toast" :class="app.toast.kind" @click="app.toast = null">{{ app.toast.message }}</div>
    </transition>
  </div>
</template>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fatal { min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 28px; gap: 8px; }
.fatal-logo { width: 72px; height: 72px; border-radius: 18px; }
.fatal p { color: var(--muted); max-width: 360px; }
</style>
