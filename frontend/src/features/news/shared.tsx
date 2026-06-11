import { useMemo } from 'react'
import type { NewsItem } from '../../api'
import { useUI } from '../../store'
import Markdown from '../../components/Markdown'

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

// 综合日报正文：复用 components/Markdown 这份**单一真相**渲染器（#–#### 标题/有序无序列表/
// 表格/斜体/代码/裸链接全支持）。此前这里另有一份简化解析，不认 ###/有序列表 → 日报偶发
// "没渲染出 markdown"；现统一掉。日报正文不带 [n] 编号引用（prompt 用圆括号标来源），故不传 sources。
export function Digest({ body }: { body: string }) {
  return <Markdown body={body} />
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
            {it.summary && <p className="blog-excerpt">{it.summary}</p>}
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
