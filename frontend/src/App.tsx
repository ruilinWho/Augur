import {
  useEffect,
  useMemo,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { motion, MotionConfig } from 'motion/react'
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
import { KAN_MODULES, useUI, type SettingsPage, type View } from './store'
import WatchlistPanel from './features/watchlist/WatchlistPanel'
import KLineView from './features/kline/KLineView'
import FinancialsPanel from './features/analysis/FinancialsPanel'
import JournalPanel from './features/journal/JournalPanel'
import SettingsView from './features/settings/SettingsView'
import NewsNav from './features/news/NewsNav'
import KnowView from './features/news/KnowView'
import NotesNav from './features/notes/NotesNav'
import NotesView from './features/notes/NotesView'
import { useNews } from './features/news/store'
import StockNews from './features/news/StockNews'
import ResearchView from './features/research/ResearchView'

const TABS: { v: View; label: string }[] = [
  { v: 'kan', label: '看' },
  { v: 'yan', label: '研' },
  { v: 'zhi', label: '知' },
  { v: 'ji', label: '记' },
]

const EASE = [0.22, 1, 0.36, 1] as const // easeOutExpo——柔和"落定"

const SETTINGS_NAV: { id: SettingsPage; label: string; icon: ReactNode }[] = [
  {
    id: 'appearance',
    label: '外观',
    icon: (
      <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6">
        <line x1="4" y1="6" x2="16" y2="6" />
        <circle cx="12" cy="6" r="2" fill="var(--surface)" />
        <line x1="4" y1="14" x2="16" y2="14" />
        <circle cx="7" cy="14" r="2" fill="var(--surface)" />
      </svg>
    ),
  },
  {
    id: 'models',
    label: '模型',
    icon: (
      <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="6" y="6" width="8" height="8" rx="1.5" />
        <path d="M8 6V3.5M12 6V3.5M8 14v2.5M12 14v2.5M6 8H3.5M6 12H3.5M14 8h2.5M14 12h2.5" />
      </svg>
    ),
  },
  {
    id: 'sources',
    label: '数据 / 信源',
    icon: (
      <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="10" cy="10" r="7" />
        <path d="M3 10h14M10 3c2 2.2 2 11.8 0 14M10 3c-2 2.2-2 11.8 0 14" />
      </svg>
    ),
  },
]

// 「设置」左栏导航（取代旧的装饰性 navrow，主人反馈"那栏没用上"）
function SettingsNav() {
  const page = useUI((s) => s.settingsPage)
  const setPage = useUI((s) => s.setSettingsPage)
  return (
    <aside className="panel set-nav">
      <div className="lbl">设置</div>
      {SETTINGS_NAV.map((n) => (
        <button
          key={n.id}
          className={`set-navitem ${page === n.id ? 'active' : ''}`}
          onClick={() => setPage(n.id)}
        >
          <span className="set-navicon">{n.icon}</span>
          {n.label}
        </button>
      ))}
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

// 「知」二级卡宽度拖拽：rail 固定 92px，故二级宽 = 指针 clientX − 92
const NEWS_RAIL_W = 92
function NewsResizeHandle() {
  const setNewsSubW = useUI((s) => s.setNewsSubW)
  const onPointerDown = (e: ReactPointerEvent) => {
    e.preventDefault()
    const move = (ev: globalThis.PointerEvent) => setNewsSubW(ev.clientX - NEWS_RAIL_W)
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.classList.remove('resizing')
    }
    document.body.classList.add('resizing')
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  return <div className="resize-handle news-resize" onPointerDown={onPointerDown} title="拖动调整二级栏宽" />
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
  const newsPrimary = useNews((s) => s.primary)
  // 细粒度订阅（非整 store）——否则拖动栏宽时 setPanelW/setNewsSubW 每帧触发整 App 树重渲染，卡顿
  const theme = useUI((s) => s.theme)
  const textBase = useUI((s) => s.textBase)
  const leading = useUI((s) => s.leading)
  const displayFont = useUI((s) => s.displayFont)
  const convention = useUI((s) => s.convention)
  const panelW = useUI((s) => s.panelW)
  const newsSubW = useUI((s) => s.newsSubW)

  // 「知」三层 Miller：资讯=4 列（rail+日期+板块+舞台）、个股=3 列（rail+标的+舞台）
  const newsCols = newsPrimary === 'info' ? 4 : 3
  const layoutClass =
    view === 'zhi'
      ? `layout know-${newsCols}`
      : view === 'kan' || view === 'yan'
        ? 'layout kan'
        : 'layout'

  useEffect(() => {
    const el = document.documentElement
    el.dataset.theme = theme
    el.style.setProperty('--text-base', `${textBase}px`)
    el.style.setProperty('--leading', String(leading))
    el.style.setProperty('--font-display', displayFont === 'serif' ? 'var(--font-serif)' : 'var(--font-sans)')
    el.style.setProperty('--up', convention === 'cn' ? 'var(--crayon-red)' : 'var(--crayon-green)')
    el.style.setProperty('--down', convention === 'cn' ? 'var(--crayon-green)' : 'var(--crayon-red)')
    el.style.setProperty('--panel-w', `${panelW}px`)
    el.style.setProperty('--news-sub-w', `${newsSubW}px`)
  }, [theme, textBase, leading, displayFont, convention, panelW, newsSubW])

  return (
    // reducedMotion="user"：尊重系统「减少动效」偏好——motion.dev 的 y 位移/spring 是 JS 动画，
    // 不受 index.css 的 @media(prefers-reduced-motion) 约束，靠这里统一降级为纯透明度（§5/§10）。
    <MotionConfig reducedMotion="user">
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

        <div className={layoutClass}>
          {view === 'kan' || view === 'yan' ? (
            <WatchlistPanel />
          ) : view === 'zhi' ? (
            <>
              <NewsNav />
              {newsCols >= 3 && <NewsResizeHandle />}
            </>
          ) : view === 'ji' ? (
            <>
              <NotesNav />
              <ResizeHandle />
            </>
          ) : (
            <>
              <SettingsNav />
              <ResizeHandle />
            </>
          )}

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
              {view === 'yan' && <ResearchView />}
              {view === 'zhi' && <KnowView />}
              {view === 'ji' && <NotesView />}
              {view === 'set' && <SettingsView />}
            </motion.div>
          </main>
        </div>
      </div>
    </MotionConfig>
  )
}
