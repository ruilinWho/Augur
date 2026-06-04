import { useMemo, type ReactNode } from 'react'
import type { NewsItem } from '../../api'
import { useUI } from '../../store'

// ── 今日要闻按天归类的日期标签 ──
export function dayLabel(iso: string | null): string {
  if (!iso) return '更早'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '更早'
  const a = new Date()
  a.setHours(0, 0, 0, 0)
  const b = new Date(d)
  b.setHours(0, 0, 0, 0)
  const diff = Math.round((a.getTime() - b.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff} 天前`
  return `${b.getMonth() + 1}月${b.getDate()}日`
}

export function ago(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const h = Math.round(mins / 60)
  if (h < 24) return `${h}小时前`
  return `${Math.round(h / 24)}天前`
}

// ── 极简内联：**加粗** → <strong> ──
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    ),
  )
}

// ## 小标题 / - 列表 / > 引用 / --- 分隔 / 段落 —— 轻量 Markdown 渲染（无依赖）
export function Digest({ body }: { body: string }) {
  const blocks: ReactNode[] = []
  let list: string[] = []
  let quote: string[] = []
  const flushList = () => {
    if (list.length) {
      const items = list
      blocks.push(
        <ul key={`u${blocks.length}`}>
          {items.map((t, i) => (
            <li key={i}>{inline(t)}</li>
          ))}
        </ul>,
      )
      list = []
    }
  }
  const flushQuote = () => {
    if (quote.length) {
      const items = quote
      blocks.push(
        <blockquote key={`q${blocks.length}`}>
          {items.map((t, i) => (
            <p key={i}>{inline(t)}</p>
          ))}
        </blockquote>,
      )
      quote = []
    }
  }
  const flush = () => {
    flushList()
    flushQuote()
  }
  body.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (!line) return flush()
    if (line === '---' || line === '***') {
      flush()
      blocks.push(<hr key={`h${i}`} />)
    } else if (line.startsWith('## ')) {
      flush()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^##\s+/, '')}</h4>)
    } else if (line.startsWith('# ')) {
      flush()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^#\s+/, '')}</h4>)
    } else if (line.startsWith('> ') || line === '>') {
      flushList()
      quote.push(line.replace(/^>\s?/, ''))
    } else if (/^[-*]\s+/.test(line)) {
      flushQuote()
      list.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flush()
      blocks.push(<p key={`p${i}`}>{inline(line)}</p>)
    }
  })
  flush()
  return <div className="digest">{blocks}</div>
}

// ── 单条要闻（含挂钩的自选股 ticker chip，点击跳「看」）──
export function Headline({ item }: { item: NewsItem }) {
  const select = useUI((s) => s.select)
  return (
    <div className="hl">
      <a className="hl-main" href={item.url} target="_blank" rel="noreferrer">
        <span className="hl-src">{item.source}</span>
        <span className="hl-title">{item.title_zh || item.title}</span>
      </a>
      {item.symbols.length > 0 && (
        <span className="hl-syms">
          {item.symbols.map((s) => (
            <button
              key={s.symbol}
              className={`hl-sym ${s.in_watchlist ? 'watched' : ''}`}
              title={s.in_watchlist ? `${s.symbol} · 已自选` : `${s.symbol} · 看 K 线`}
              onClick={() => select(s.symbol)}
            >
              {s.in_watchlist && <span className="wdot" />}
              {s.name || s.symbol.split(':')[1]}
            </button>
          ))}
        </span>
      )}
      {ago(item.published_at) && <span className="hl-ago">{ago(item.published_at)}</span>}
    </div>
  )
}

// ── 按天分组的要闻流（总览/新闻/推特复用）──
export function FeedGroups({ items, empty }: { items: NewsItem[]; empty?: string }) {
  const byDay = useMemo(() => {
    const order: string[] = []
    const m: Record<string, NewsItem[]> = {}
    for (const it of items) {
      const d = dayLabel(it.published_at)
      if (!m[d]) {
        m[d] = []
        order.push(d)
      }
      m[d].push(it)
    }
    return order.map((d) => [d, m[d]] as const)
  }, [items])

  if (!items.length) {
    return (
      <div className="faint" style={{ padding: '14px 2px' }}>
        {empty ?? '还没有内容'}
      </div>
    )
  }
  return (
    <div className="feed-groups">
      {byDay.map(([day, list]) => (
        <div key={day} className="feed-group">
          <div className="fg-head">
            <span className="fg-theme">{day}</span>
            <span className="fg-n">{list.length}</span>
          </div>
          <div className="hl-list">
            {list.map((it) => (
              <Headline key={it.id} item={it} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
