import { useEffect, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useUI, type View } from './store'
import WatchlistPanel from './features/watchlist/WatchlistPanel'
import KLineView from './features/kline/KLineView'
import SettingsView from './features/settings/SettingsView'
import Placeholder from './features/misc/Placeholder'

const TABS: { v: View; label: string }[] = [
  { v: 'kan', label: '看' },
  { v: 'yan', label: '研' },
  { v: 'zhi', label: '知' },
]

const EASE = [0.22, 1, 0.36, 1] as const // easeOutExpo——柔和"落定"

function SimplePanel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <aside className="panel">
      <div className="lbl">{label}</div>
      {children}
    </aside>
  )
}

export default function App() {
  const view = useUI((s) => s.view)
  const setView = useUI((s) => s.setView)
  const { theme, textBase, leading, displayFont, convention } = useUI()

  useEffect(() => {
    const el = document.documentElement
    el.dataset.theme = theme
    el.style.setProperty('--text-base', `${textBase}px`)
    el.style.setProperty('--leading', String(leading))
    el.style.setProperty('--font-display', displayFont === 'serif' ? 'var(--font-serif)' : 'var(--font-sans)')
    el.style.setProperty('--up', convention === 'cn' ? 'var(--crayon-red)' : 'var(--crayon-green)')
    el.style.setProperty('--down', convention === 'cn' ? 'var(--crayon-green)' : 'var(--crayon-red)')
  }, [theme, textBase, leading, displayFont, convention])

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="wordmark">
          <span className="dot" /> Augur
        </span>
        <nav className="fn-tabs">
          {TABS.map((t) => (
            <button
              key={t.v}
              className={`t ${view === t.v ? 'active' : ''}`}
              onClick={() => setView(t.v)}
            >
              {view === t.v && (
                <motion.span
                  layoutId="tabpill"
                  className="tabpill"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              <span className="tab-label">{t.label}</span>
            </button>
          ))}
        </nav>
        <button className="app-search" onClick={() => setView('kan')} title="搜索（即将上线）">
          <span>⌕ 搜索标的、板块</span>
          <kbd className="kbd">⌘K</kbd>
        </button>
        <button
          className={`gear ${view === 'set' ? 'active' : ''}`}
          title="设置"
          onClick={() => setView('set')}
        >
          <svg viewBox="0 0 18 18">
            <line x1="2.5" y1="6" x2="15.5" y2="6" />
            <circle cx="11.5" cy="6" r="2.3" fill="var(--surface)" />
            <line x1="2.5" y1="12.5" x2="15.5" y2="12.5" />
            <circle cx="6" cy="12.5" r="2.3" fill="var(--surface)" />
          </svg>
        </button>
      </header>

      <div className="layout">
        {view === 'kan' || view === 'yan' ? (
          <WatchlistPanel />
        ) : view === 'zhi' ? (
          <SimplePanel label="趋势日报">
            <div className="navrow" style={{ opacity: 0.6 }}>日报列表（M3 接入）</div>
          </SimplePanel>
        ) : (
          <SimplePanel label="设置">
            {['排版', '主题与色彩', '数据与市场', 'LLM 厂商'].map((c) => (
              <div key={c} className="navrow">
                {c}
              </div>
            ))}
          </SimplePanel>
        )}

        <main className="stage">
          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: EASE }}
              style={{ height: '100%' }}
            >
              {view === 'kan' && <KLineView />}
              {view === 'yan' && <Placeholder pillar="研" />}
              {view === 'zhi' && <Placeholder pillar="知" />}
              {view === 'set' && <SettingsView />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
