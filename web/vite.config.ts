import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API calls to the backend during development so the browser makes
// same-origin requests (no CORS setup needed on the FastAPI side).
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': API_TARGET,
      '/links': API_TARGET,
    },
  },
})
