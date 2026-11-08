import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), {
    name: 'pyglide-runtime-assets',
    apply: 'build',
    generateBundle() {
      for (const fileName of ['pyworker.js', 'sw.js']) {
        this.emitFile({
          type: 'asset',
          fileName,
          source: readFileSync(new URL(`./${fileName}`, import.meta.url), 'utf8')
        })
      }
    }
  }],
  server: {
    port: 3000,
    open: true
  }
})
