import { useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useUI, type Market } from '../../store'
import {
  useAddItem,
  useCreateSection,
  useDeleteSection,
  useQuote,
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

const EASE = [0.22, 1, 0.36, 1] as const
const fmtPrice = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
const countSymbols = (s: Section) => s.items.length + s.children.reduce((a, c) => a + c.items.length, 0)

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

function StockRow({ item }: { item: Item }) {
  const selected = useUI((s) => s.selectedSymbol)
  const select = useUI((s) => s.select)
  const [market, code] = item.symbol.split(':')
  const q = useQuote(item.symbol)
  const up = q.data ? q.data.change >= 0 : true
  return (
    <div className={`stk ${selected === item.symbol ? 'active' : ''}`} onClick={() => select(item.symbol)}>
      <span className="tk">{code}</span>
      <span className="v">{q.data ? fmtPrice(q.data.price) : '—'}</span>
      <span className="cn">{market}</span>
      <span className={`d ${up ? 'up' : 'down'}`}>
        {q.data ? `${up ? '▲' : '▼'} ${Math.abs(q.data.change_pct).toFixed(2)}%` : ''}
      </span>
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

export default function WatchlistPanel() {
  const market = useUI((s) => s.market)
  const setMarket = useUI((s) => s.setMarket)
  const { data: sections, isLoading, error } = useSections(market)
  const createSection = useCreateSection()
  const addItem = useAddItem()
  const delSection = useDeleteSection()

  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())
  const [adding, setAdding] = useState<'top' | { id: number; kind: 'stock' | 'sub' } | null>(null)

  const toggle = (id: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const stockAdder = (id: number) =>
    adding && adding !== 'top' && adding.id === id && adding.kind === 'stock' ? (
      <InlineAdd
        placeholder="代码，如 US:AAPL"
        onSubmit={(v) => {
          addItem.mutate({ sectionId: id, symbol: v })
          setAdding(null)
        }}
        onCancel={() => setAdding(null)}
      />
    ) : null

  const renderL2 = (s: Section) => {
    const open = !collapsed.has(s.id)
    return (
      <div className="l2grp" key={s.id}>
        <div className="row2">
          <span className="chev" onClick={() => toggle(s.id)}>{open ? '▾' : '▸'}</span>
          <span className="nm" onClick={() => toggle(s.id)}>{s.name}</span>
          <span className="ct">{s.items.length}</span>
          <span className="add" title="加标的" onClick={() => setAdding({ id: s.id, kind: 'stock' })}>＋</span>
          <span className="del" title="删板块" onClick={() => delSection.mutate(s.id)}>×</span>
        </div>
        <Collapse open={open}>
          {s.items.map((it) => (
            <StockRow key={it.id} item={it} />
          ))}
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
        <div className="row1">
          <span className="chev" onClick={() => toggle(s.id)}>{open ? '▾' : '▸'}</span>
          <span className="nm" onClick={() => toggle(s.id)}>{s.name}</span>
          <span className="ct">{countSymbols(s)}</span>
          <span className="add" title="加子板块" onClick={() => setAdding({ id: s.id, kind: 'sub' })}>⊞</span>
          <span className="add" title="加标的" onClick={() => setAdding({ id: s.id, kind: 'stock' })}>＋</span>
          <span className="del" title="删板块" onClick={() => delSection.mutate(s.id)}>×</span>
        </div>
        <Collapse open={open}>
          {s.items.map((it) => (
            <StockRow key={it.id} item={it} />
          ))}
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
        <span className="act" onClick={() => setAdding('top')}>＋ 板块</span>
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
      <div className="tree">{sections?.map(renderL1)}</div>
      {sections && sections.length === 0 && (
        <div className="faint" style={{ padding: 10, fontSize: '.82rem' }}>
          还没有板块。点上方「＋ 板块」新建。
        </div>
      )}
    </aside>
  )
}
