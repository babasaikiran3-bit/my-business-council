import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// Parse BACKEND_PORT from root .env
let backendPort = process.env.VITE_BACKEND_PORT || '8001'
try {
  const envFile = readFileSync(resolve(__dirname, '../.env'), 'utf-8')
  const match = envFile.match(/^\s*BACKEND_PORT\s*=\s*(\S+)/m)
  if (match) backendPort = match[1]
} catch {}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    proxy: {
      '/api': `http://localhost:${backendPort}`,
    },
  },
})
