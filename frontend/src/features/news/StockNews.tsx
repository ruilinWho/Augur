import { useState, type MouseEvent } from 'react'
import Collapse from '../../components/Collapse'
import { useRefreshDirected, useStockNewsBrief, useStockSocialHeat, useStockSources } from '../../api'

// 个股「相关资讯」：只呈现 AI 筛选后的摘要，不铺直接新闻列表。
export default function StockNews({ symbol }: { symbol: string }) {
  const brief = useStockNewsBrief(symbol)
  const social = useStockSocialHeat(symbol)
  const refresh = useRefreshDirected()
  const sources = useStockSources(symbol)
  const [open, setOpen] = useState(true)
  const data = brief.data
  const heat = social.data
  const n = data?.source_count ?? 0
  const enabledSources = (sources.data ?? []).filter((s) => s.enabled).length
  const hasBody = Boolean(data?.summary || data?.points.length || data?.risks.length)
  const platformEntries = Object.entries(heat?.platforms ?? {})
  const heatTone = heat?.heat === '高' ? 'high' : heat?.heat === '中' ? 'mid' : 'low'
  const hasSocialBody = Boolean(
    heat?.summary || heat?.bull_points.length || heat?.bear_points.length || heat?.watch.length,
  )
  const runRefresh = (e: MouseEvent) => {
    e.stopPropagation()
    refresh.mutate(symbol)
  }

  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>相关资讯</h3>
        {n > 0 && <span className="feed-count">{n} 源</span>}
        {enabledSources > 0 && <span className="feed-count stock-src-n">专属 {enabledSources}</span>}
        <button className="btn btn-ghost jsm stock-news-refresh" onClick={runRefresh} disabled={refresh.isPending}>
          {refresh.isPending ? '刷新中…' : '刷新'}
        </button>
      </div>
      <Collapse open={open}>
        <div className="stock-news-stack">
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
          <div className="social-heat">
            <div className="social-heat-top">
              <h4>社媒热度</h4>
              {heat?.source_count ? <span className="social-heat-count">{heat.source_count} 条</span> : null}
              <span className={`social-pill heat-${heatTone}`}>{heat?.heat ?? '低'}</span>
              <span className="social-pill">{heat?.sentiment ?? '不明'}</span>
            </div>
            {social.isLoading ? (
              <p className="social-heat-empty">加载…</p>
            ) : social.isError ? (
              <p className="social-heat-empty">暂不可用</p>
            ) : hasSocialBody ? (
              <>
                {heat?.summary && <p className="social-heat-summary">{heat.summary}</p>}
                {platformEntries.length ? (
                  <div className="social-platforms">
                    {platformEntries.map(([name, count]) => (
                      <span key={name}>
                        {name} {count}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className="social-heat-grid">
                  <SocialColumn title="偏多" items={heat?.bull_points ?? []} />
                  <SocialColumn title="反证" items={heat?.bear_points ?? []} />
                  <SocialColumn title="观察" items={heat?.watch ?? []} />
                </div>
              </>
            ) : (
              <p className="social-heat-empty">{heat?.status || '暂无社媒信号'}</p>
            )}
          </div>
        </div>
      </Collapse>
    </section>
  )
}

function SocialColumn({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div className="social-heat-col">
      <span>{title}</span>
      {items.map((item, idx) => (
        <p key={`${title}-${idx}`}>{item}</p>
      ))}
    </div>
  )
}
