import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3010,
    proxy: {
      '/ws': {
        target: 'ws://localhost:8010',
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8010',
      },
    },
  },
  build: {
    outDir: '../server/static',
    emptyOutDir: true,
  },
})
