<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

// Dropdown yang bisa dicari — dipakai untuk SEMUA pilihan di aplikasi (bukan <select> bawaan).
// options: string[] atau { value, label, hint? }[].
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '—' },
  disabled: { type: Boolean, default: false },
  clearable: { type: Boolean, default: false },
  searchPlaceholder: { type: String, default: 'Cari…' },
  emptyText: { type: String, default: 'Tidak ditemukan' },
  compact: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const q = ref('')
const root = ref(null)
const searchEl = ref(null)

const norm = computed(() => props.options.map((o) => (typeof o === 'object' ? o : { value: o, label: String(o) })))
const selected = computed(() => norm.value.find((o) => String(o.value) === String(props.modelValue)))
const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return norm.value
  return norm.value.filter((o) => `${o.label} ${o.hint || ''}`.toLowerCase().includes(s))
})

function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    q.value = ''
    nextTick(() => searchEl.value && searchEl.value.focus())
  }
}
function pick(v) {
  emit('update:modelValue', v)
  open.value = false
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))
</script>

<template>
  <div class="ss" :class="{ compact }" ref="root">
    <button type="button" class="ss-control" :disabled="disabled" @click="toggle">
      <span class="ss-value" :class="{ ph: !selected }">{{ selected ? selected.label : placeholder }}</span>
      <span class="ss-caret">▾</span>
    </button>
    <div v-if="open" class="ss-panel">
      <input v-if="norm.length > 6" ref="searchEl" v-model="q" class="ss-search" type="text" :placeholder="searchPlaceholder" @keydown.esc.prevent="open = false" />
      <div class="ss-list">
        <button v-if="clearable && !q" type="button" class="ss-opt muted" :class="{ active: !modelValue }" @click="pick('')">—</button>
        <button v-for="o in filtered" :key="o.value" type="button" class="ss-opt" :class="{ active: String(o.value) === String(modelValue) }" @click="pick(o.value)">
          {{ o.label }}<span v-if="o.hint" class="ss-hint">{{ o.hint }}</span>
        </button>
        <div v-if="!filtered.length" class="ss-empty">{{ emptyText }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ss { position: relative; }
.ss-control {
  width: 100%; display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); background: var(--input-bg);
  color: var(--ink); border-radius: 12px; padding: 12px 14px; font-size: 16px; text-align: left;
}
.ss-control:disabled { opacity: .6; }
.ss-value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ss-value.ph { color: var(--muted); }
.ss-caret { color: var(--muted); font-size: 12px; }
.ss-panel { position: absolute; z-index: 60; top: calc(100% + 4px); left: 0; right: 0; min-width: 220px; background: var(--card); border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow); padding: 6px; }
.ss-search { width: 100%; border: 1px solid var(--line); background: var(--input-bg); border-radius: 10px; padding: 10px 12px; font-size: 15px; margin-bottom: 6px; }
.ss-list { max-height: 260px; overflow-y: auto; }
.ss-opt { display: flex; flex-direction: column; width: 100%; text-align: left; border: 0; background: transparent; color: var(--ink); padding: 10px; border-radius: 8px; font-size: 15px; }
.ss-opt.active { background: var(--brand); color: var(--brand-ink); font-weight: 600; }
.ss-opt.muted { color: var(--muted); }
.ss-hint { font-size: 12px; opacity: .7; }
.ss-empty { padding: 12px; color: var(--muted); text-align: center; font-size: 14px; }
.compact .ss-control { padding: 7px 10px; font-size: 13px; font-weight: 700; border-radius: 10px; background: rgba(255,255,255,.16); color: var(--appbar-ink); border-color: transparent; }
.compact .ss-caret { color: inherit; }
.compact .ss-panel { left: auto; right: 0; }
</style>
