import { createRouter, createWebHashHistory } from 'vue-router'
import { useApp } from '../stores/app'

// meta.menu = kunci menu di Booking Ops Settings → Akses Menu per Role.
const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue'), meta: { menu: 'dashboard' } },
  { path: '/calendar', name: 'calendar', component: () => import('../views/CalendarView.vue'), meta: { menu: 'calendar' } },
  { path: '/bookings', name: 'bookings', component: () => import('../views/BookingsView.vue'), meta: { menu: 'bookings' } },
  { path: '/booking/:id', name: 'booking', component: () => import('../views/BookingDetailView.vue'), meta: { menu: 'bookings', nav: 'bookings' } },
  { path: '/booking/:id/edit', name: 'edit', component: () => import('../views/BookingFormView.vue'), meta: { menu: 'edit_booking', nav: 'bookings' } },
  { path: '/messages', name: 'messages', component: () => import('../views/MessagesView.vue'), meta: { menu: 'messages' } },
  { path: '/messages/:id', name: 'thread', component: () => import('../views/ThreadView.vue'), meta: { menu: 'messages', nav: 'messages' } },
  { path: '/new', name: 'new', component: () => import('../views/BookingFormView.vue'), meta: { menu: 'new_booking' } },
  { path: '/rates', name: 'rates', component: () => import('../views/RatesView.vue'), meta: { menu: 'availability' } },
  { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue'), meta: { menu: 'reports' } },
  { path: '/sync', name: 'sync', component: () => import('../views/SyncView.vue'), meta: { menu: 'sync' } },
  { path: '/more', name: 'more', component: () => import('../views/MoreView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const app = useApp()
  const menu = to.meta.menu
  if (menu && !app.can(menu)) {
    const first = app.firstRoute
    return first === to.path ? { name: 'more' } : first
  }
})

export default router
