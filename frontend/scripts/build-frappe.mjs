// Build PWA langsung ke modul app: `cd frontend && npm install && npm run build:frappe`
// Lalu index.html hasil build → www/booking_ops/index.html (template Jinja: csrf + user sesi).
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join } from 'node:path'
import { readFileSync, writeFileSync, copyFileSync, readdirSync } from 'node:fs'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = resolve(here, '..')
const outDir = resolve(frontend, '../booking_ops/public/booking_ops')
const wwwFile = resolve(frontend, '../booking_ops/www/booking_ops/index.html')
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx'

console.log('Building →', outDir)
const r = spawnSync(npx, ['vite', 'build'], { cwd: frontend, env: { ...process.env, BOOKINGOPS_OUTDIR: outDir }, stdio: 'inherit', shell: process.platform === 'win32' })
if (r.status !== 0) process.exit(r.status || 1)

const inject =
  '\n  <link rel="manifest" href="/booking_ops/manifest.json">\n' +
  '  <link rel="apple-touch-icon" href="/assets/booking_ops/booking_ops/apple-touch-icon.png">\n' +
  '  <link rel="icon" type="image/png" sizes="64x64" href="/assets/booking_ops/booking_ops/favicon-64.png">\n' +
  '  <link rel="icon" type="image/png" sizes="192x192" href="/assets/booking_ops/booking_ops/icon-192.png">\n' +
  '  <script>\n' +
  '    window.csrf_token = "{{ csrf_token }}";\n' +
  '    window.bookingops_user = "{{ bookingops_user }}";\n' +
  '  </script>\n'
const html = readFileSync(join(outDir, 'index.html'), 'utf8').replace(/<head>/i, '<head>' + inject)
writeFileSync(wwwFile, html)
console.log('Wrote', wwwFile)
