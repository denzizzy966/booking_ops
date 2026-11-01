<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useApp } from '../stores/app'

// HP: tab bawah (maks 4 menu + Lainnya). Tablet: rail samping berisi semua menu.
const app = useApp()
const route = useRoute()
const icon = import.meta.env.BASE_URL + 'icon-192.png'
const items = computed(() => app.navItems)
const phoneItems = computed(() => app.phoneNav)
const badge = (n) => (n.key === 'messages' && app.unread ? (app.unread > 99 ? '99+' : String(app.unread)) : '')
const current = computed(() => route.meta.nav || route.name)
const isActive = (n) => current.value === n.name || (n.name === 'bookings' && current.value === 'booking')
const moreActive = computed(() => (current.value === 'more' || app.moreNav.some(isActive)) && !phoneItems.value.some(isActive))
</script>

<template>
  <nav class="rail">
    <div class="rail-brand">
      <img :src="icon" alt="" />
      <span>Booking Ops</span>
    </div>
    <router-link v-for="n in items" :key="n.key" :to="n.to" class="rail-item" :class="{ active: isActive(n) }">
      <span class="ic"><Icon :name="n.icon" /><i v-if="badge(n)" class="nbadge">{{ badge(n) }}</i></span><span>{{ n.label }}</span>
    </router-link>
    <div class="grow"></div>
    <router-link to="/more" class="rail-item" :class="{ active: current === 'more' }">
      <Icon name="settings" /><span>Lainnya</span>
    </router-link>
  </nav>

  <nav class="tabbar">
    <router-link v-for="n in phoneItems" :key="n.key" :to="n.to" :class="{ active: isActive(n) }">
      <span class="ic"><Icon :name="n.icon" /><i v-if="badge(n)" class="nbadge">{{ badge(n) }}</i></span><span class="lbl">{{ n.short || n.label }}</span>
    </router-link>
    <router-link to="/more" :class="{ active: moreActive }">
      <span class="ic"><Icon name="more" /></span><span class="lbl">Lainnya</span>
    </router-link>
  </nav>
</template>
