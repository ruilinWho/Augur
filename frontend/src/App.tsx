import {
  useEffect,
  useMemo,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { motion } from 'motion/react'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { KAN_MODULES, useUI, type View } from './store'
import WatchlistPanel from './features/watchlist/WatchlistPanel'
import KLineView from './features/kline/KLineView'
import FinancialsPanel from './features/analysis/FinancialsPanel'
import JournalPanel from './features/journal/JournalPanel'
import SettingsView from './features/settings/SettingsView'
import NewsListPanel from './features/news/NewsListPanel'
import KnowView from './features/news/KnowView'
import StockNews from './features/news/StockNews'
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

// 左栏宽度拖拽手柄：拖动更新 --panel-w（panel 左缘在视口 x=0，故宽度=指针 clientX）
function ResizeHandle() {
  const setPanelW = useUI((s) => s.setPanelW)
  const onPointerDown = (e: ReactPointerEvent) => {
    e.preventDefault()
    const move = (ev: globalThis.PointerEvent) => setPanelW(ev.clientX)
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.classList.remove('resizing')
    }
    document.body.classList.add('resizing')
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  return <div className="resize-handle" onPointerDown={onPointerDown} title="拖动调整栏宽" />
}

// 看·K线下方模块：拖动手柄重排（持久化）。仅手柄可拖，模块内部交互不受影响。
const KAN_RENDER: Record<string, (symbol: string) => ReactNode> = {
  financials: (s) => <FinancialsPanel symbol={s} />,
  news: (s) => <StockNews symbol={s} />,
  journal: (s) => <JournalPanel symbol={s} />,
}

function GripDots() {
  // 竖向 2×3 点阵，适合放在模块标题左侧的把手
  return (
    <svg width="8" height="16" viewBox="0 0 8 16" aria-hidden="true">
      {[2.5, 5.5].flatMap((cx) =>
        [3, 8, 13].map((cy) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.05" fill="currentColor" />
        )),
      )}
    </svg>
  )
}

function SortableModule({ id, symbol }: { id: string; symbol: string }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <div
      ref={setNodeRef}
      className={`kan-mod ${isDragging ? 'dragging' : ''}`}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.75 : 1,
        zIndex: isDragging ? 5 : undefined,
      }}
    >
      <button className="kan-grip" {...attributes} {...listeners} aria-label="拖动排序" title="拖动调整顺序">
        <GripDots />
      </button>
      {KAN_RENDER[id]?.(symbol)}
    </div>
  )
}

function KanStack({ symbol }: { symbol: string }) {
  const stored = useUI((s) => s.kanOrder)
  const setKanOrder = useUI((s) => s.setKanOrder)
  // 与已知模块对账（持久化里可能残留旧 id，如已移除的 SEC）
  const order = useMemo(() => {
    const known = stored.filter((x) => (KAN_MODULES as readonly string[]).includes(x))
    const missing = KAN_MODULES.filter((x) => !known.includes(x))
    return [...known, ...missing]
  }, [stored])
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const oldI = order.indexOf(String(active.id))
    const newI = order.indexOf(String(over.id))
    if (oldI >= 0 && newI >= 0) setKanOrder(arrayMove(order, oldI, newI))
  }
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={order} strategy={verticalListSortingStrategy}>
        {order.map((id) => (
          <SortableModule key={id} id={id} symbol={symbol} />
        ))}
      </SortableContext>
    </DndContext>
  )
}

export default function App() {
  const view = useUI((s) => s.view)
  const setView = useUI((s) => s.setView)
  const selectedSymbol = useUI((s) => s.selectedSymbol)
  const { theme, textBase, leading, displayFont, convention, panelW } = useUI()

  useEffect(() => {
    const el = document.documentElement
    el.dataset.theme = theme
    el.style.setProperty('--text-base', `${textBase}px`)
    el.style.setProperty('--leading', String(leading))
    el.style.setProperty('--font-display', displayFont === 'serif' ? 'var(--font-serif)' : 'var(--font-sans)')
    el.style.setProperty('--up', convention === 'cn' ? 'var(--crayon-red)' : 'var(--crayon-green)')
    el.style.setProperty('--down', convention === 'cn' ? 'var(--crayon-green)' : 'var(--crayon-red)')
    el.style.setProperty('--panel-w', `${panelW}px`)
  }, [theme, textBase, leading, displayFont, convention, panelW])

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
          <NewsListPanel />
        ) : (
          <SimplePanel label="设置">
            {['排版', '主题与色彩', 'LLM 厂商', '数据 / 信源 API'].map((c) => (
              <div key={c} className="navrow">
                {c}
              </div>
            ))}
          </SimplePanel>
        )}

        <ResizeHandle />

        <main className="stage">
          {/* 视图切换：keyed motion.div 只做进场动画。刻意不用 AnimatePresence——
              本项目 motion+React19 下其 exit 不触发，mode="wait" 会卡住旧视图、新视图永不挂载
              （见 docs/memory/frontend-gotchas.md）。换 key 即重挂载 + 进场淡入，干净可靠。 */}
          <motion.div
            key={view}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: EASE }}
            style={{ minHeight: '100%' }}
          >
            {view === 'kan' && (
              <>
                <KLineView />
                {selectedSymbol && <KanStack symbol={selectedSymbol} />}
              </>
            )}
            {view === 'yan' && <Placeholder pillar="研" />}
            {view === 'zhi' && <KnowView />}
            {view === 'set' && <SettingsView />}
          </motion.div>
        </main>
      </div>
    </div>
  )
}
