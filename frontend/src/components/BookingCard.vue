<script setup>
import { computed } from 'vue'
import { useApp } from '../stores/app'
import { STATUS, STAY, fmtDate, money, channelLabel } from '../lib/util'

const props = defineProps({
  b: { type: Object, required: true },
  active: { type: Boolean, default: false },
  hint: { type: String, default: '' } // mis. "Datang" / "Pergi" di beranda
})
const app = useApp()
const st = computed(() => (props.b.status === 'cancelled' ? STATUS.cancelled : STAY[props.b.stay_status] || STAY.Expected))
const warn = computed(() => ['Error', 'Needs Review'].includes(props.b.sync_state))
</script>

<template>
  <div class="list-item bcard" :class="{ active }">
    <div class="avatar" :class="st.cls">{{ (b.guest_name || '?').trim().charAt(0).toUpperCase() }}</div>
    <div class="grow">
      <div class="row between">
        <div class="truncate name">{{ b.guest_name }}</div>
        <span class="badge-status" :class="st.cls">{{ st.label }}</span>
      </div>
      <div class="small muted truncate">
        <Icon name="bed" /> {{ app.roomName(b.room) }}<template v-if="b.unit_name"> · {{ b.unit_name }}</template>
      </div>
      <div class="row between small">
        <span class="muted truncate">{{ fmtDate(b.arrival, { day: false }) }} → {{ fmtDate(b.departure, { day: false }) }} · {{ b.nights }} mlm</span>
        <span class="price">{{ money(b.price, b.currency || app.currency) }}</span>
      </div>
      <div class="row tiny muted meta">
        <span class="chan">{{ channelLabel(b.channel) }}</span>
        <span>#{{ b.booking_id }}</span>
        <span v-if="b.status !== 'confirmed' && b.status !== 'cancelled'" class="badge-status" :class="STATUS[b.status]?.cls">{{ STATUS[b.status]?.label }}</span>
        <span v-if="hint" class="hint">{{ hint }}</span>
        <span v-if="warn" class="warn-tag"><Icon name="warn" /> SO</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bcard { cursor: pointer; align-items: flex-start; }
.bcard.active { outline: 2px solid var(--brand); }
.name { font-weight: 700; }
.price { font-weight: 700; white-space: nowrap; }
.meta { gap: 8px; margin-top: 2px; flex-wrap: wrap; }
.chan { font-weight: 700; color: var(--brand); }
.avatar { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; font-weight: 800; font-size: 17px; flex: none; }
.warn-tag { color: var(--warn); font-weight: 700; }
.hint { font-weight: 700; color: var(--ink); }
</style>
