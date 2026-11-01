<script setup>
defineProps({ title: String })
const emit = defineEmits(['close'])
</script>

<template>
  <div class="sheet-mask" @click.self="emit('close')">
    <div class="sheet">
      <div class="grab"></div>
      <div class="sheet-head">
        <div class="title">{{ title }}</div>
        <button class="btn sm" @click="emit('close')">Tutup</button>
      </div>
      <div class="sheet-body"><slot /></div>
    </div>
  </div>
</template>
