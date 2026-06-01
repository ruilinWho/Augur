import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useUI, type Market } from '../../store'
import {
  useAddItem,
  useCreateSection,
  useDeleteSection,
  useDeleteItem,
  useMoveItem,
  useQuote,
  useReorder,
  useSearch,
  useSections,
  type Item,
  type Section,
} from '../../api'

const MARKETS: { v: Market; label: string }[] = [
  { v: 'ALL', label: '全部' },
  { v: 'US', label: '美股' },
  { v: 'HK', label: '港股' },
  { v: 'CN', label: 'A股' },
  { v: 'KR', label: '韩股' },
]
const MKT_LABEL: Record<string, string> = { US: '美', HK: '港', CN: 'A', KR: '韩' }
// 各市场「裸代码」直输模式（点了某市场就只敲代码即可加入）
const CODE_RE: Record<string, RegExp> = {
  US: /^[A-Za-z][A-Za-z.]{0,5}$/,
  HK: /^\d{1,5}$/,
  CN: /^\d{6}$/,
  KR: /^\d{6}$/,
}

const EASE = [0.22, 1, 0.36, 1] as const
const fmtPrice = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
const countSymbols = (s: Section) => s.items.length + s.children.reduce((a, c) => a + c.items.length, 0)

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

// ───────────────────────── 检索式添加：点哪个市场就搜哪个；ALL=全市场 ─────────────────────────
function StockSearch({ sectionId, onDone }: { sectionId: number; onDone: () => void }) {
  const market = useUI((s) => s.market)
  const select = useUI((s) => s.select)
  const addItem = useAddItem()
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 170)
  const { data, isFetching } = useSearch(dq, market)
  const [hi, setHi] = useState(0)

  // 选了具体市场且输入像代码 → 提供「直接添加」入口（无需出现在目录里）
  const direct = useMemo(() => {
    const t = q.trim()
    if (market === 'ALL' || !t || !CODE_RE[market]?.test(t)) return null
    const code = market === 'US' ? t.toUpperCase() : market === 'HK' ? t.padStart(5, '0') : t
    return { symbol: `${market}:${code}`, market, code, name: '直接添加', sub: '' }
  }, [q, market])

  const results = data?.results ?? []
  const options = direct
    ? [direct, ...results.filter((r) => r.symbol !== direct.symbol)]
    : results
  const indexing = data?.indexing ?? false

  useEffect(() => setHi(0), [dq, market])

  const add = (symbol: string) => {
    addItem.mutate({ sectionId, symbol })
    select(symbol) // 立即选中 → 主舞台马上加载它的 K 线（不等 POST 回执）
    onDone()
  }

  return (
    <div className="adder">
      <input
        className="input"
        autoFocus
        value={q}
        placeholder={
          market === 'ALL' ? '搜代码 / 名称 / 拼音（全市场）…' : `在${MARKETS.find((m) => m.v === market)?.label}内搜代码或名称…`
        }
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onDone()
          else if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHi((h) => Math.min(h + 1, options.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHi((h) => Math.max(h - 1, 0))
          } else if (e.key === 'Enter' && options[hi]) {
            add(options[hi].symbol)
          }
        }}
        onBlur={() => setTimeout(onDone, 140)}
      />
      {q.trim() && (
        <div className="sresults">
          {options.map((o, i) => (
            <div
              key={o.symbol}
              className={`sopt ${i === hi ? 'hi' : ''}`}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                add(o.symbol)
              }}
            >
              <span className={`mbadge m-${o.market.toLowerCase()}`}>{MKT_LABEL[o.market] ?? o.market}</span>
              <span className="scode mono">{o.code}</span>
              <span className="sname">{o.name}</span>
              {o.sub && <span className="ssub">{o.sub}</span>}
            </div>
          ))}
          {!options.length &&
            (indexing ? (
              <div className="shint">正在建立标的索引，请稍候…</div>
            ) : isFetching ? (
              <div className="shint">搜索中…</div>
            ) : (
              <div className="shint">无匹配。试试「全部」市场，或输入精确代码。</div>
            ))}
        </div>
      )}
    </div>
  )
}

function InlineAdd({ placeholder, onSubmit, onCancel }: { placeholder: string; onSubmit: (v: string) => void; onCancel: () => void }) {
  const [v, setV] = useState('')
  return (
    <input
      className="input"
      autoFocus
      placeholder={placeholder}
      value={v}
      style={{ margin: '4px 6px', width: 'calc(100% - 12px)' }}
      onChange={(e) => setV(e.target.value)}
      onBlur={onCancel}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && v.trim()) onSubmit(v.trim())
        else if (e.key === 'Escape') onCancel()
      }}
    />
  )
}

// ───────────────────────── 标的行（可拖拽换区 / 排序）─────────────────────────
function RowBody({ item }: { item: Item }) {
  const [market, code] = item.symbol.split(':')
  const q = useQuote(item.symbol)
  const up = q.data ? q.data.change >= 0 : true
  return (
    <>
      <span className="tk">{q.data?.name || code}</span>
      <span className="v">{q.data ? fmtPrice(q.data.price) : '—'}</span>
      <span className="cn">
        {code} · {market}
      </span>
      <span className={`d ${up ? 'up' : 'down'}`}>
        {q.data ? `${up ? '▲' : '▼'} ${Math.abs(q.data.change_pct).toFixed(2)}%` : ''}
      </span>
    </>
  )
}

function StockRow({ item }: { item: Item }) {
  const selected = useUI((s) => s.selectedSymbol)
  const select = useUI((s) => s.select)
  const delItem = useDeleteItem()
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `item:${item.id}`,
  })
  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
    opacity: isDragging ? 0.35 : 1,
  }
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`stk ${selected === item.symbol ? 'active' : ''}`}
      onClick={() => select(item.symbol)}
      {...attributes}
      {...listeners}
    >
      <RowBody item={item} />
      <button
        className="stk-del"
        title="移出自选"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          delItem.mutate(item.id)
        }}
      >
        ×
      </button>
    </div>
  )
}

// 折叠动画容器
function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: EASE }}
          style={{ overflow: 'hidden' }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// 板块标题行：整行点击折叠；右侧操作按钮 stopPropagation；本身是拖拽落点
function SectionHeader({
  section,
  level,
  open,
  count,
  onToggle,
  onAddStock,
  onAddSub,
  onDelete,
}: {
  section: Section
  level: 1 | 2
  open: boolean
  count: number
  onToggle: () => void
  onAddStock: () => void
  onAddSub?: () => void
  onDelete: () => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `sec:${section.id}` })
  const stop = (fn: () => void) => (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    fn()
  }
  return (
    <div
      ref={setNodeRef}
      className={`row${level} ${isOver ? 'drop-into' : ''}`}
      onClick={onToggle}
      role="button"
    >
      <span className="chev">{open ? '▾' : '▸'}</span>
      <span className="nm">{section.name}</span>
      <span className="ct">{count}</span>
      {onAddSub && (
        <span className="add" title="加子板块" onClick={stop(onAddSub)}>
          ⊞
        </span>
      )}
      <span className="add" title="加标的" onClick={stop(onAddStock)}>
        ＋
      </span>
      <span className="del" title="删板块" onClick={stop(onDelete)}>
        ×
      </span>
    </div>
  )
}

type Adding = 'top' | { id: number; kind: 'stock' | 'sub' } | null

export default function WatchlistPanel() {
  const market = useUI((s) => s.market)
  const setMarket = useUI((s) => s.setMarket)
  const { data: sections, isLoading, error } = useSections(market)
  const createSection = useCreateSection()
  const delSection = useDeleteSection()
  const moveItem = useMoveItem()
  const reorder = useReorder()

  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())
  const [adding, setAdding] = useState<Adding>(null)

  // ── 拖拽：本地乐观态（order: 区→标的id序；holder: 标的id→所在区）──
  const [order, setOrder] = useState<Record<number, number[]>>({})
  const [holder, setHolder] = useState<Record<number, number>>({})
  const [itemData, setItemData] = useState<Record<number, Item>>({})
  const [activeId, setActiveId] = useState<number | null>(null)
  const dragging = useRef(false)
  const startSec = useRef<number | null>(null)

  const resync = useMemo(
    () => () => {
      if (!sections) return
      const ord: Record<number, number[]> = {}
      const hold: Record<number, number> = {}
      const data: Record<number, Item> = {}
      const walk = (s: Section) => {
        ord[s.id] = s.items.map((i) => i.id)
        s.items.forEach((i) => {
          hold[i.id] = s.id
          data[i.id] = i
        })
        s.children.forEach(walk)
      }
      sections.forEach(walk)
      setOrder(ord)
      setHolder(hold)
      setItemData(data)
    },
    [sections],
  )

  useEffect(() => {
    if (!dragging.current) resync()
  }, [resync])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const containerOf = (id: string): number | null => {
    if (id.startsWith('sec:')) return Number(id.slice(4))
    return holder[Number(id.slice(5))] ?? null
  }

  const onDragStart = (e: DragStartEvent) => {
    const id = Number(String(e.active.id).slice(5))
    dragging.current = true
    startSec.current = holder[id] ?? null
    setActiveId(id)
  }

  const onDragOver = (e: DragOverEvent) => {
    const { active, over } = e
    if (!over) return
    const id = Number(String(active.id).slice(5))
    const from = holder[id]
    const to = containerOf(String(over.id))
    if (from == null || to == null || from === to) return
    setHolder((h) => ({ ...h, [id]: to }))
    setOrder((o) => {
      const fromIds = (o[from] ?? []).filter((x) => x !== id)
      const toIds = [...(o[to] ?? [])]
      let idx = toIds.length
      if (String(over.id).startsWith('item:')) {
        const p = toIds.indexOf(Number(String(over.id).slice(5)))
        if (p >= 0) idx = p
      }
      toIds.splice(idx, 0, id)
      return { ...o, [from]: fromIds, [to]: toIds }
    })
  }

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    dragging.current = false
    setActiveId(null)
    if (!over) return resync()
    const id = Number(String(active.id).slice(5))
    const to = containerOf(String(over.id))
    if (to == null) return resync()

    // 重算目标区顺序：移除拖拽项后，按落点（在某标的上→其位；在标题上→末尾）精确插回
    const without = (order[to] ?? []).filter((x) => x !== id)
    let insertAt = without.length
    if (String(over.id).startsWith('item:')) {
      const p = without.indexOf(Number(String(over.id).slice(5)))
      if (p >= 0) insertAt = p
    }
    const toIds = [...without.slice(0, insertAt), id, ...without.slice(insertAt)]
    setOrder((o) => ({ ...o, [to]: toIds }))

    const orig = startSec.current
    startSec.current = null
    const persist = async () => {
      if (orig != null && orig !== to) await moveItem.mutateAsync({ itemId: id, sectionId: to })
      await reorder.mutateAsync({ kind: 'item', orderedIds: toIds })
    }
    persist().catch(() => resync())
  }

  const toggle = (id: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const itemsOf = (s: Section): Item[] => {
    const ids = order[s.id]
    if (!ids) return s.items
    return ids.map((id) => itemData[id]).filter(Boolean)
  }

  const stockAdder = (id: number) =>
    adding && adding !== 'top' && adding.id === id && adding.kind === 'stock' ? (
      <StockSearch sectionId={id} onDone={() => setAdding(null)} />
    ) : null

  const renderItems = (s: Section) => {
    const items = itemsOf(s)
    return (
      <SortableContext items={items.map((i) => `item:${i.id}`)} strategy={verticalListSortingStrategy}>
        {items.map((it) => (
          <StockRow key={it.id} item={it} />
        ))}
      </SortableContext>
    )
  }

  const renderL2 = (s: Section) => {
    const open = !collapsed.has(s.id)
    return (
      <div className="l2grp" key={s.id}>
        <SectionHeader
          section={s}
          level={2}
          open={open}
          count={itemsOf(s).length}
          onToggle={() => toggle(s.id)}
          onAddStock={() => setAdding({ id: s.id, kind: 'stock' })}
          onDelete={() => delSection.mutate(s.id)}
        />
        <Collapse open={open}>
          {renderItems(s)}
          {stockAdder(s.id)}
        </Collapse>
      </div>
    )
  }

  const renderL1 = (s: Section, idx: number) => {
    const open = !collapsed.has(s.id)
    return (
      <motion.div
        className="l1grp"
        key={s.id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, delay: Math.min(idx * 0.04, 0.2), ease: EASE }}
      >
        <SectionHeader
          section={s}
          level={1}
          open={open}
          count={countSymbols(s)}
          onToggle={() => toggle(s.id)}
          onAddStock={() => setAdding({ id: s.id, kind: 'stock' })}
          onAddSub={() => setAdding({ id: s.id, kind: 'sub' })}
          onDelete={() => delSection.mutate(s.id)}
        />
        <Collapse open={open}>
          {renderItems(s)}
          {stockAdder(s.id)}
          {s.children.map(renderL2)}
          {adding && adding !== 'top' && adding.id === s.id && adding.kind === 'sub' && (
            <InlineAdd
              placeholder="子板块名…"
              onSubmit={(v) => {
                createSection.mutate({ name: v, parent_id: s.id })
                setAdding(null)
              }}
              onCancel={() => setAdding(null)}
            />
          )}
        </Collapse>
      </motion.div>
    )
  }

  const activeItem = activeId != null ? itemData[activeId] : null

  return (
    <aside className="panel">
      <div className="lbl">市场</div>
      <div className="mkt">
        {MARKETS.map((m) => (
          <button key={m.v} aria-pressed={market === m.v} onClick={() => setMarket(m.v)}>
            {m.label}
          </button>
        ))}
      </div>

      <div className="lbl">
        自选分区
        <span className="act" onClick={() => setAdding('top')}>
          ＋ 板块
        </span>
      </div>
      {adding === 'top' && (
        <InlineAdd
          placeholder="新一级板块名…"
          onSubmit={(v) => {
            createSection.mutate({ name: v })
            setAdding(null)
          }}
          onCancel={() => setAdding(null)}
        />
      )}

      {isLoading && (
        <div className="wl-skel">
          <div className="line skeleton" />
          <div className="line short skeleton" />
          <div className="line skeleton" />
          <div className="line short skeleton" />
        </div>
      )}
      {error && (
        <div className="faint" style={{ padding: 10, fontSize: '.82rem', color: 'var(--down)' }}>
          {(error as Error).message}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          dragging.current = false
          setActiveId(null)
          resync()
        }}
      >
        <div className="tree">{sections?.map(renderL1)}</div>
        <DragOverlay dropAnimation={null}>
          {activeItem ? (
            <div className="stk drag-ghost">
              <RowBody item={activeItem} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {sections && sections.length === 0 && (
        <div className="faint" style={{ padding: 10, fontSize: '.82rem' }}>
          还没有板块。点上方「＋ 板块」新建。
        </div>
      )}
    </aside>
  )
}
