import { useState } from 'react'
import Collapse from '../../components/Collapse'
import { useStockNewsBrief } from '../../api'

// 个股「相关资讯」：只呈现 AI 筛选后的摘要，不铺直接新闻列表。
export default function StockNews({ symbol }: { symbol: string }) {
  const brief = useStockNewsBrief(symbol)
  const [open, setOpen] = useState(true)
  const data = brief.data
  const n = data?.source_count ?? 0
  const hasBody = Boolean(data?.summary || data?.points.length || data?.risks.length)

  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>相关资讯</h3>
        {n > 0 && <span className="feed-count">{n} 源</span>}
      </div>
      <Collapse open={open}>
        {brief.isLoading ? (
          <div className="fin-empty">加载…</div>
        ) : brief.isError ? (
          <div className="stock-brief-empty">暂无摘要</div>
        ) : hasBody ? (
          <div className="stock-brief">
            {data?.summary && <p className="stock-brief-summary">{data.summary}</p>}
            {data?.points.length ? (
              <div className="stock-brief-list">
                {data.points.map((p, i) => (
                  <div className="stock-brief-row" key={`${p}-${i}`}>
                    <span>{i + 1}</span>
                    <p>{p}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {data?.risks.length ? (
              <div className="stock-brief-risk">
                {data.risks.map((r, i) => (
                  <p key={`${r}-${i}`}>{r}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="stock-brief-empty">暂无摘要</div>
        )}
      </Collapse>
    </section>
  )
}
