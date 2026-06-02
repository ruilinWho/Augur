import { useState } from 'react'
import Collapse from '../../components/Collapse'
import { useNewsForSymbol, useStockOfficial } from '../../api'

function ago(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 60) return `${Math.max(mins, 1)}分钟前`
  const h = Math.round(mins / 60)
  if (h < 24) return `${h}小时前`
  return `${Math.round(h / 24)}天前`
}

// 申报日期：YYYY-MM-DD → 今年只显 M月D日，往年带年份
function filed(iso: string | null): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  if (!y || !m || !d) return iso
  const thisYear = String(new Date().getFullYear())
  return y === thisYear ? `${Number(m)}月${Number(d)}日` : `${y}.${Number(m)}.${Number(d)}`
}

// 官方一手文件：美股 SEC EDGAR 申报（8-K/10-Q/10-K/DEF 14A…），中文标签 + 直链原文。
function OfficialFilings({ symbol }: { symbol: string }) {
  const q = useStockOfficial(symbol)
  const [open, setOpen] = useState(true)
  const items = q.data ?? []
  // 非美股 / 查得为空：整段隐藏（避免空噪音）；加载中先显骨架文案
  if (!q.isLoading && items.length === 0) return null

  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>官方文件 · SEC</h3>
        <span className="feed-count">{items.length} 份</span>
      </div>
      <Collapse open={open}>
        {items.length > 0 ? (
          <div className="hl-list">
            {items.map((f, i) => (
              <a key={i} className="hl" href={f.url} target="_blank" rel="noreferrer">
                <span className="filing-form">{f.form}</span>
                <span className="hl-title">{f.title}</span>
                {f.filed_at && <span className="hl-ago">{filed(f.filed_at)}</span>}
              </a>
            ))}
          </div>
        ) : (
          <div className="fin-empty">加载官方文件…</div>
        )}
      </Collapse>
    </section>
  )
}

// 个股「相关资讯」：从「知」聚合的新闻里筛出提到该公司的条目，链接到原文。
function RelatedNews({ symbol }: { symbol: string }) {
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
            {news.isLoading ? '加载相关资讯…' : '暂无相关资讯（到「知」刷新信源后再看）'}
          </div>
        )}
      </Collapse>
    </section>
  )
}

// 个股一条龙信源：官方一手文件（SEC）置顶，其下为聚合相关资讯。
export default function StockNews({ symbol }: { symbol: string }) {
  return (
    <>
      <OfficialFilings symbol={symbol} />
      <RelatedNews symbol={symbol} />
    </>
  )
}
