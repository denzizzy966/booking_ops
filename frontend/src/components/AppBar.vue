<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import SearchSelect from './SearchSelect.vue'

const props = defineProps({
  title: { type: String, default: '' },
  back: { type: Boolean, default: false },
  propertyPicker: { type: Boolean, default: false }
})
const router = useRouter()
const app = useApp()
const propOptions = computed(() => [
  { value: '', label: 'Semua properti' },
  ...app.properties.map((p) => ({ value: p.property_id, label: p.property_name }))
])
const showPicker = computed(() => props.propertyPicker && app.properties.length > 1)

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<template>
  <header class="appbar">
    <button v-if="back" class="back" @click="goBack" aria-label="Kembali"><Icon name="left" /></button>
    <div class="title truncate">{{ title }}</div>
    <div v-if="showPicker" class="prop-pick">
      <SearchSelect
        :model-value="app.property"
        :options="propOptions"
        compact
        search-placeholder="Cari properti…"
        @update:model-value="(v) => app.setPref('property', v)"
      />
    </div>
    <slot name="actions" />
    <span v-if="app.settings.sandbox" class="net-pill sandbox" title="Data contoh, bukan Beds24 asli"><Icon name="flask" />Sandbox</span>
    <span v-if="!app.online" class="net-pill off"><span class="dot"></span>Offline</span>
  </header>
</template>
