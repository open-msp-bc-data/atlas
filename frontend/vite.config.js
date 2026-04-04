import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/atlas/',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
  server: {
    proxy: {
      '/physicians': 'http://localhost:8000',
      '/aggregations': 'http://localhost:8000',
      '/trends': 'http://localhost:8000',
      '/heatmap': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
