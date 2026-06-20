import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Output dir is `build/` to match the feature spec's Output Files (§5).
// `index.html` lives at the frontend root (Vite convention) — see spec.md §4.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'build',
    sourcemap: false,
  },
  server: {
    port: 5173,
    open: false,
  },
})
