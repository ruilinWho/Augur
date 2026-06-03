import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useUI, type Market } from '../../store'
import {
  useAddItem,
  useCreateSection,
  useDeleteItem,
  useDeleteSection,
  useMoveItem,
  useQuote,
  useRenameSection,
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
const CODE_RE: Record<string, RegExp> = {
  US: /^[A-Za-z][A-Za-z.]{0,5}$/,
  HK: /^\d{1,5}$/,
  CN: /^\d{6}$/,
  KR: /^\d{6}$/,
}
const fmtPrice = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
const countSymbols = (s: Section) =>
  s.items.length + s.children.reduce((a, c) => a + c.items.length, 0)
const DIRECT = -1 // col2 里「直属标的」伪条目的 id

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

// ───────── 检索式加股（点哪个市场搜哪个；ALL=全市场）─────────
function StockSearch({ sectionId, onDone }: { sectionId: number; onDone: () => void }) {
  const market = useUI((s) => s.market)
  const select = useUI((s) => s.select)
  const addItem = useAddItem()
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 170)
  const { data, isFetching } = useSearch(dq, market)
  const [hi, setHi] = useState(0)

  const direct = useMemo(() => {
    const t = q.trim()
    if (market === 'ALL' || !t || !CODE_RE[market]?.test(t)) return null
    const code = market === 'US' ? t.toUpperCase() : market === 'HK' ? t.padStart(5, '0') : t
    return { symbol: `${market}:${code}`, market, code, name: '直接添加', sub: '' }
  }, [q, market])

  const results = data?.results ?? []
  const options = direct ? [direct, ...results.filter((r) => r.symbol !== direct.symbol)] : results
  const indexing = data?.indexing ?? false
  useEffect(() => setHi(0), [dq, market])

  const add = (symbol: string) => {
    addItem.mutate({ sectionId, symbol })
    select(symbol)
    onDone()
  }

  return (
    <div className="adder">
      <input
        className="input"
        autoFocus
        value={q}
        placeholder={market === 'ALL' ? '搜代码 / 名称 / 拼音…' : '搜代码或名称…'}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onDone()
          else if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHi((h) => Math.min(h + 1, options.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHi((h) => Math.max(h - 1, 0))
          } else if (e.key === 'Enter' && options[hi]) add(options[hi].symbol)
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
              <span className={`mbadge m-${o.market.toLowerCase()}`}>
                {MKT_LABEL[o.market] ?? o.market}
              </span>
              <span className="scode mono">{o.code}</span>
              <span className="sname">{o.name}</span>
              {o.sub && <span className="ssub">{o.sub}</span>}
            </div>
          ))}
          {!options.length &&
            (indexing ? (
              <div className="shint">正在建立索引…</div>
            ) : isFetching ? (
              <div className="shint">搜索中…</div>
            ) : (
              <div className="shint">无匹配。试「全部」或输入精确代码。</div>
            ))}
        </div>
      )}
    </div>
  )
}

function InlineAdd({
  placeholder,
  onSubmit,
  onCancel,
}: {
  placeholder: string
  onSubmit: (v: string) => void
  onCancel: () => void
}) {
  const [v, setV] = useState('')
  return (
    <input
      className="input kc-inlineadd"
      autoFocus
      placeholder={placeholder}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={onCancel}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && v.trim()) onSubmit(v.trim())
        else if (e.key === 'Escape') onCancel()
      }}
    />
  )
}

// ───────── 标的行（col3，可拖拽排序/换区）─────────
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
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition, opacity: isDragging ? 0.35 : 1 }}
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

// ───────── 板块行（col1/col2，可选中、双击重命名、拖股票落入即换区）─────────
function SecRow({
  section,
  active,
  count,
  onSelect,
  onAddSub,
  onDelete,
}: {
  section: Section
  active: boolean
  count: number
  onSelect: () => void
  onAddSub?: () => void
  onDelete: () => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `sec:${section.id}` })
  const rename = useRenameSection()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(section.name)
  const clickT = useRef<number | null>(null)
  const stop = (fn: () => void) => (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    fn()
  }
  const handleClick = () => {
    if (editing) return
    if (clickT.current) window.clearTimeout(clickT.current)
    clickT.current = window.setTimeout(() => {
      clickT.current = null
      onSelect()
    }, 190)
  }
  const startEdit = () => {
    if (clickT.current) {
      window.clearTimeout(clickT.current)
      clickT.current = null
    }
    setDraft(section.name)
    setEditing(true)
  }
  const commit = () => {
    setEditing(false)
    const v = draft.trim()
    if (v && v !== section.name) rename.mutate({ id: section.id, name: v })
  }
  useEffect(
    () => () => {
      if (clickT.current != null) window.clearTimeout(clickT.current)
    },
    [],
  )
  return (
    <div
      ref={setNodeRef}
      className={`secrow ${active ? 'active' : ''} ${isOver ? 'drop-into' : ''}`}
      onClick={handleClick}
      role="button"
    >
      {editing ? (
        <input
          className="nm-edit"
          autoFocus
          value={draft}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            e.stopPropagation()
            if (e.key === 'Enter') commit()
            else if (e.key === 'Escape') {
              setEditing(false)
              setDraft(section.name)
            }
          }}
        />
      ) : (
        <>
          <span className="secname" title="双击重命名" onDoubleClick={stop(startEdit)}>
            {section.name}
          </span>
          <span className="seccount">{count}</span>
          {onAddSub && (
            <span className="secact" title="加子板块" onClick={stop(onAddSub)}>
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2.5" y="2.5" width="9" height="9" rx="2.2" />
                <path d="M7 5v4M5 7h4" />
              </svg>
            </span>
          )}
          <span className="secact del" title="删板块" onClick={stop(onDelete)}>
            ×
          </span>
        </>
      )}
    </div>
  )
}

// ───────── 可拖宽 / 可收起的列容器 ─────────
function Column({
  i,
  title,
  action,
  children,
}: {
  i: 0 | 1 | 2
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  const w = useUI((s) => s.kanColW[i])
  const closed = useUI((s) => s.kanColClosed[i])
  const setW = useUI((s) => s.setKanColW)
  const toggle = useUI((s) => s.toggleKanCol)

  if (closed) {
    return (
      <button className="kcol-closed" onClick={() => toggle(i)} title="展开">
        <span className="kcol-closed-t">{title}</span>
      </button>
    )
  }
  const onResize = (e: React.PointerEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = w
    const move = (ev: PointerEvent) => setW(i, startW + (ev.clientX - startX))
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.classList.remove('resizing')
    }
    document.body.classList.add('resizing')
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  return (
    <div className="kcol" style={{ width: w }}>
      <div className="kcol-head">
        <span className="kcol-title">{title}</span>
        <span className="kcol-act">{action}</span>
        <button className="kcol-fold" onClick={() => toggle(i)} title="收起">
          ‹
        </button>
      </div>
      <div className="kcol-body">{children}</div>
      <div className="kcol-resize" onPointerDown={onResize} title="拖动调整列宽" />
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
  const delSectionFn = delSection.mutate
  const moveItem = useMoveItem()
  const reorder = useReorder()

  const [selL1, setSelL1] = useState<number | null>(null)
  const [selSec, setSelSec] = useState<number | null>(null) // col3 显示哪个 section 的标的
  const [adding, setAdding] = useState<Adding>(null)

  // col3 的标的顺序乐观态
  const [ord, setOrd] = useState<number[]>([])
  const [itemData, setItemData] = useState<Record<number, Item>>({})
  const [activeId, setActiveId] = useState<number | null>(null)
  const dragging = useRef(false)

  const l1 = useMemo(() => sections?.find((s) => s.id === selL1) ?? null, [sections, selL1])
  // col3 的 section（一级直属 = l1 自身；否则某二级）
  const col3 = useMemo(() => {
    if (!l1) return null
    if (selSec === l1.id || selSec == null) return l1
    return l1.children.find((c) => c.id === selSec) ?? l1
  }, [l1, selSec])

  // 无子板块时不显中列（避免只有一个「直属」的冗余卡）；建子板块或正在建时才分出中列
  const isAddingSub =
    adding !== null && adding !== 'top' && adding.kind === 'sub' && !!l1 && adding.id === l1.id
  const showCol2 = !!l1 && (l1.children.length > 0 || isAddingSub)
  const col3Title = !col3
    ? '标的'
    : !showCol2
      ? col3.name
      : col3.id === l1?.id
        ? `${l1?.name} · 直属`
        : col3.name

  // 选择合法化：sections 变化时保证 selL1/selSec 有效
  useEffect(() => {
    if (!sections || !sections.length) return
    if (!sections.some((s) => s.id === selL1)) {
      setSelL1(sections[0].id)
      setSelSec(sections[0].id)
    }
  }, [sections, selL1])

  // 同步 col3 标的顺序（非拖拽时）
  useEffect(() => {
    if (dragging.current || !col3) return
    setOrd(col3.items.map((i) => i.id))
    setItemData(Object.fromEntries(col3.items.map((i) => [i.id, i])))
  }, [col3])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const onDragStart = (e: DragStartEvent) => {
    dragging.current = true
    setActiveId(Number(String(e.active.id).slice(5)))
  }
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    dragging.current = false
    setActiveId(null)
    if (!over) return
    const id = Number(String(active.id).slice(5))
    const overId = String(over.id)
    if (overId.startsWith('sec:')) {
      const to = Number(overId.slice(4))
      if (col3 && to !== col3.id) {
        setOrd((o) => o.filter((x) => x !== id)) // 乐观移出 col3
        moveItem.mutate({ itemId: id, sectionId: to })
      }
      return
    }
    // 列内重排
    const overItem = Number(overId.slice(5))
    const from = ord.indexOf(id)
    const to = ord.indexOf(overItem)
    if (from < 0 || to < 0 || from === to) return
    const next = arrayMove(ord, from, to)
    setOrd(next)
    reorder.mutate({ kind: 'item', orderedIds: next })
  }

  const col3Items = ord.map((id) => itemData[id]).filter(Boolean)
  const activeItem = activeId != null ? itemData[activeId] : null

  const selectL1 = (id: number) => {
    setSelL1(id)
    setSelSec(id)
    setAdding(null)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={() => {
        dragging.current = false
        setActiveId(null)
      }}
    >
      <div className="kan-nav">
        {/* ── 列1：市场过滤 + 一级板块 ── */}
        <Column
          i={0}
          title="分区"
          action={
            <button className="kc-add" title="新建一级板块" onClick={() => setAdding('top')}>
              ＋
            </button>
          }
        >
          <div className="mkt kc-mkt">
            {MARKETS.map((m) => (
              <button key={m.v} aria-pressed={market === m.v} onClick={() => setMarket(m.v)}>
                {m.label}
              </button>
            ))}
          </div>
          {adding === 'top' && (
            <InlineAdd
              placeholder="一级板块名…"
              onSubmit={async (v) => {
                const sec = (await createSection.mutateAsync({ name: v })) as Section
                setAdding(null)
                // 空板块现在在任何市场都可见（后端 §8 细化）→ 就地选中，不切换市场
                setSelL1(sec.id)
                setSelSec(sec.id)
              }}
              onCancel={() => setAdding(null)}
            />
          )}
          {isLoading && <div className="kc-skel skeleton" />}
          {error && <div className="faint kc-msg">{(error as Error).message}</div>}
          {sections?.map((s) => (
            <SecRow
              key={s.id}
              section={s}
              active={selL1 === s.id}
              count={countSymbols(s)}
              onSelect={() => selectL1(s.id)}
              onAddSub={() => {
                setSelL1(s.id)
                setAdding({ id: s.id, kind: 'sub' })
              }}
              onDelete={() => delSectionFn(s.id)}
            />
          ))}
          {sections && sections.length === 0 && (
            <div className="faint kc-msg">还没有板块，点上方 ＋ 新建。</div>
          )}
        </Column>

        {/* ── 列2：选中一级板块的 二级板块 + 直属（仅当有子板块/正在建子板块时显示）── */}
        {showCol2 && l1 && (
          <Column i={1} title={l1.name}>
            <>
              <div
                className={`secrow ${selSec === l1.id ? 'active' : ''}`}
                onClick={() => setSelSec(l1.id)}
                role="button"
              >
                <span className="secname">直属</span>
                <span className="seccount">{l1.items.length}</span>
              </div>
              {l1.children.map((c) => (
                <SecRow
                  key={c.id}
                  section={c}
                  active={selSec === c.id}
                  count={c.items.length}
                  onSelect={() => setSelSec(c.id)}
                  onDelete={() => {
                    delSectionFn(c.id)
                    if (selSec === c.id) setSelSec(l1.id)
                  }}
                />
              ))}
              {adding && adding !== 'top' && adding.id === l1.id && adding.kind === 'sub' && (
                <InlineAdd
                  placeholder="子板块名…"
                  onSubmit={async (v) => {
                    const sub = (await createSection.mutateAsync({
                      name: v,
                      parent_id: l1.id,
                    })) as Section
                    setAdding(null)
                    setSelL1(l1.id)
                    setSelSec(sub.id)
                  }}
                  onCancel={() => setAdding(null)}
                />
              )}
              <button className="kc-addsub" onClick={() => setAdding({ id: l1.id, kind: 'sub' })}>
                ＋ 子板块
              </button>
            </>
          </Column>
        )}

        {/* ── 列3：标的（可拖拽排序/换区）── */}
        <Column
          i={2}
          title={col3Title}
          action={
            col3 && (
              <button
                className="kc-add"
                title="加标的"
                onClick={() =>
                  setAdding(
                    adding && adding !== 'top' && adding.id === col3.id && adding.kind === 'stock'
                      ? null
                      : { id: col3.id, kind: 'stock' },
                  )
                }
              >
                ＋
              </button>
            )
          }
        >
          {col3 ? (
            <>
              {adding && adding !== 'top' && adding.id === col3.id && adding.kind === 'stock' && (
                <StockSearch sectionId={col3.id} onDone={() => setAdding(null)} />
              )}
              <SortableContext
                items={col3Items.map((i) => `item:${i.id}`)}
                strategy={verticalListSortingStrategy}
              >
                {col3Items.map((it) => (
                  <StockRow key={it.id} item={it} />
                ))}
              </SortableContext>
              {!col3Items.length && <div className="faint kc-msg">该板块暂无标的，点 ＋ 添加。</div>}
            </>
          ) : (
            <div className="faint kc-msg">选板块看标的</div>
          )}
        </Column>
      </div>

      <DragOverlay dropAnimation={null}>
        {activeItem ? (
          <div className="stk drag-ghost">
            <RowBody item={activeItem} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
