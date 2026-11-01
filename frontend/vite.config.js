import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Build untuk bench: BOOKINGOPS_OUTDIR = apps/booking_ops/booking_ops/public/booking_ops.
const frappeOut = process.env.BOOKINGOPS_OUTDIR || ''

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Dev: proksi ke bench lokal; token API disuntik di sisi Node (tak pernah ke browser).
  const url = new URL(env.FRAPPE_URL || 'http://erp.localhost:8000')
  const target = `${url.protocol}//127.0.0.1:${url.port || 80}`
  const auth = env.FRAPPE_API_KEY && env.FRAPPE_API_SECRET ? `token ${env.FRAPPE_API_KEY}:${env.FRAPPE_API_SECRET}` : ''
  const configure = (server) =>
    server.on('proxyReq', (req) => {
      req.setHeader('Host', url.host)
      if (auth) req.setHeader('Authorization', auth)
    })
  const proxy = {}
  for (const p of ['/api', '/assets', '/files']) proxy[p] = { target, changeOrigin: false, configure }

  return {
    base: frappeOut ? '/assets/booking_ops/booking_ops/' : '/',
    build: frappeOut ? { outDir: frappeOut, emptyOutDir: true, target: 'es2018' } : {},
    plugins: [vue()],
    server: { port: 5174, proxy }
  }
})
