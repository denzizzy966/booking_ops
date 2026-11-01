<script setup>
import { useRoute } from 'vue-router'
import AppBar from '../components/AppBar.vue'
import BookingDetail from '../components/BookingDetail.vue'

const route = useRoute()
</script>

<template>
  <AppBar :title="`Booking #${route.params.id}`" back />
  <div class="content">
    <div class="wrap narrow">
      <BookingDetail :id="String(route.params.id)" />
    </div>
  </div>
</template>
