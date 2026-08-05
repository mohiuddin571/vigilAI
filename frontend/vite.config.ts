import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/cameras': 'http://localhost:8000',
      '/streams': 'http://localhost:8000',
      '/recordings': 'http://localhost:8000',
      '/analytics': 'http://localhost:8000',
      '/zones': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
