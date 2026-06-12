import { useMemo } from 'react'
import type { CitedPoint, NewsItem, RelatedSymbol } from '../../api'
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

// ── 带原始链接的要点：文字本身即可点链接（hover 出下划线），多来源附极小上标。资讯/日报/个股共用。──
export function CitedText({ p }: { p: CitedPoint }) {
  const primary = p.refs[0]?.url
  const extra = p.refs.slice(1)
  return (
    <span className="cited-text">
      {primary ? (
        <a className="cited-link" href={primary} target="_blank" rel="noreferrer">
          {p.text}
        </a>
      ) : (
        <span>{p.text}</span>
      )}
      {extra.map((r, i) => (
        <a
          key={i}
          className="cited-sup"
          href={r.url}
          target="_blank"
          rel="noreferrer"
          title={r.source}
        >
          {i + 2}
        </a>
      ))}
    </span>
  )
}

export function CitedList({ items }: { items: CitedPoint[] }) {
  return (
    <ul className="cited-list">
      {items.map((p, i) => (
        <li key={i}>
          <CitedText p={p} />
        </li>
      ))}
    </ul>
  )
}

// ── 关联标的 chip：已解析→「名字→看 K 线 · 研→深度研究」；已关注→陶土描边+圆点；未解析→灰。──
// 机会卡、日报主题卡共用（作者：个股挂钩按钮是提高 UI/UX 的重要工具，单一真相避免漂移）。
export function RelatedChip({ r }: { r: RelatedSymbol }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  if (!r.resolved || !r.symbol) {
    return (
      <span className="opp-chip unresolved" title="未能解析到具体上市公司代码">
        {r.name}
      </span>
    )
  }
  const sym = r.symbol
  return (
    <span
      className={`opp-chip2 ${r.in_watchlist ? 'watched' : ''}`}
      title={r.in_watchlist ? `已关注 · ${r.sections.join(' / ')}` : sym}
    >
      <button className="oc-nm" onClick={() => select(sym)} title="在「看」里查看 K 线">
        {r.in_watchlist && <span className="wdot" />}
        {r.name}
      </button>
      <button className="oc-go" onClick={() => research(sym)} title="深度研究这只股">
        研
      </button>
    </span>
  )
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
        {empty ?? '暂无内容'}
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

// ── 博客阅读卡：博客是长文（公众号深度分析等），不套新闻的标题行，而是给署名 + 标题 + 摘要节选，
//    像一份"待读清单"。标题里的 `[公众号名]` 前缀抽成署名，正文摘要节选 3 行。──
export function BlogList({ items, empty }: { items: NewsItem[]; empty?: string }) {
  const select = useUI((s) => s.select)
  if (!items.length) {
    return (
      <div className="faint" style={{ padding: '14px 2px' }}>
        {empty ?? '暂无博客'}
      </div>
    )
  }
  return (
    <div className="blog-list">
      {items.map((it) => {
        const raw = it.title_zh || it.title
        const m = raw.match(/^\[([^\]]+)\]\s*(.*)$/)
        const byline = m ? m[1] : it.source.replace(/^博客·/, '')
        const title = m ? m[2] : raw
        return (
          <article key={it.id} className="blog-card">
            <div className="blog-card-top">
              <span className="blog-src">{byline}</span>
              {ago(it.published_at) && <span className="blog-ago">{ago(it.published_at)}</span>}
            </div>
            <a className="blog-title" href={it.url} target="_blank" rel="noreferrer">
              {title}
            </a>
            {it.symbols.length > 0 && (
              <div className="blog-syms">
                {it.symbols.map((s) => (
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
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}
