import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 后端 FastAPI 在 :8788。开发期把这些路径代理过去，免跨域。
const backend = 'http://127.0.0.1:8788'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/market': backend,
      '/watchlist': backend,
      '/llm': backend,
      '/journal': backend,
      '/news': backend,
      '/research': backend,
      '/notes': backend,
      '/templates': backend,
      '/discovery': backend,
      '/settings': backend,
      '/health': backend,
    },
  },
})
