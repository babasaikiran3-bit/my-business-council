import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Enable source maps for debugging
  build: {
    sourcemap: true,
  },
  // Better error overlay in development
  server: {
    hmr: {
      overlay: true,
    },
  },
  // Enable source maps in dev mode
  css: {
    devSourcemap: true,
  },
})
