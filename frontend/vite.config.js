import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/model': 'http://127.0.0.1:8000',
      '/risk': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
    },
  },
})
