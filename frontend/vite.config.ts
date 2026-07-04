import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  base: '/ui/',
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8501' },
  },
  build: {
    outDir: fileURLToPath(new URL('../src/interfaces/api/static', import.meta.url)),
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
