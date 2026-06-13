import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import './index.css'
import '@fontsource/source-serif-4/400.css'
import '@fontsource/source-serif-4/500.css'
import '@fontsource/source-serif-4/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } },
})

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// 桌面外壳（Tauri）：标记到 <html>，让 CSS 给原生红绿灯（Overlay 标题栏）让位。
if (typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window) {
  document.documentElement.classList.add('tauri')
}

// 后端就绪 gate：打包（Tauri）后外壳刚 spawn 后端、预热要几秒；轮询 /health 通过前显示加载态，
// 避免首屏一堆请求闪错。开发期后端已在跑 → 几乎瞬间通过。
function BackendGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`)
        if (r.ok) {
          if (alive) setReady(true)
          return
        }
      } catch {
        /* 后端还没起，继续轮询 */
      }
      if (alive) window.setTimeout(poll, 600)
    }
    poll()
    return () => {
      alive = false
    }
  }, [])
  if (!ready)
    return (
      <div className="backend-gate">
        <div className="bg-seed">🌱</div>
        <div className="bg-text">启动中…</div>
      </div>
    )
  return <>{children}</>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={qc}>
        <BackendGate>
          <App />
        </BackendGate>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
