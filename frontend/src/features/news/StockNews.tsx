import { useState } from 'react'
import Collapse from '../../components/Collapse'
import { useNewsForSymbol } from '../../api'
import { ago } from './shared'

// 个股「相关资讯」：从「知」聚合的新闻里筛出提到该公司的条目，链接到原文。
export default function StockNews({ symbol }: { symbol: string }) {
  const news = useNewsForSymbol(symbol)
  const [open, setOpen] = useState(true)
  const items = news.data ?? []

  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>相关资讯</h3>
        <span className="feed-count">{items.length} 条</span>
      </div>
      <Collapse open={open}>
        {items.length > 0 ? (
          <div className="hl-list">
            {items.map((it) => (
              <a key={it.id} className="hl" href={it.url} target="_blank" rel="noreferrer">
                <span className="hl-src">{it.source}</span>
                <span className="hl-title">{it.title_zh || it.title}</span>
                {ago(it.published_at) && <span className="hl-ago">{ago(it.published_at)}</span>}
              </a>
            ))}
          </div>
        ) : (
          <div className="fin-empty">
            {news.isLoading ? '加载相关资讯…' : '暂无相关资讯'}
          </div>
        )}
      </Collapse>
    </section>
  )
}
