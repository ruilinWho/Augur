import { useState, type MouseEvent } from 'react'
import Collapse from '../../components/Collapse'
import {
  useGenerateNarrative,
  useNarrative,
  useRefreshDirected,
  useStockNewsBrief,
  useStockSocialHeat,
  useStockSources,
  type CitedPoint,
} from '../../api'
import { NarrativeBody } from './NarrativeTimeline'

// 一条要点背后的原始链接（像新闻一样可点回看）
function SourceChips({ refs }: { refs: CitedPoint['refs'] }) {
  if (!refs.length) return null
  return (
    <span className="cited-srcs">
      {refs.map((r, i) => (
        <a key={i} className="cited-src" href={r.url} target="_blank" rel="noreferrer" title={r.source}>
          {r.source || '来源'} ↗
        </a>
      ))}
    </span>
  )
}

function CitedList({ items }: { items: CitedPoint[] }) {
  return (
    <div className="cited-list">
      {items.map((p, i) => (
        <div className="cited-row" key={i}>
          <p>
            {p.text}
            <SourceChips refs={p.refs} />
          </p>
        </div>
      ))}
    </div>
  )
}

// 「看·相关资讯」：一个板块一眼看全——现状一句话 + 要点（带来源）+ 时间线 + 社媒热度。
export default function StockNews({ symbol }: { symbol: string }) {
  const brief = useStockNewsBrief(symbol)
  const social = useStockSocialHeat(symbol)
  const nar = useNarrative(symbol)
  const genNar = useGenerateNarrative()
  const refresh = useRefreshDirected()
  const sources = useStockSources(symbol)
  const [open, setOpen] = useState(true)

  const data = brief.data
  const heat = social.data
  const narr = nar.data
  const n = data?.source_count ?? 0
  const enabledSources = (sources.data ?? []).filter((s) => s.enabled).length
  const hasBrief = Boolean(data?.summary || data?.points.length || data?.risks.length)
  const heatTone = heat?.heat === '高' ? 'high' : heat?.heat === '中' ? 'mid' : 'low'
  const platformEntries = Object.entries(heat?.platforms ?? {})
  const hasSocial = Boolean(
    heat?.summary || heat?.bull_points.length || heat?.bear_points.length || heat?.watch.length,
  )

  const runRefresh = (e: MouseEvent) => {
    e.stopPropagation()
    refresh.mutate(symbol)
  }
  const runGenNar = (e: MouseEvent) => {
    e.stopPropagation()
    genNar.mutate(symbol)
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
        <div className="srn">
          {/* 现状 + 要点 */}
          {brief.isLoading ? (
            <div className="fin-empty">加载…</div>
          ) : brief.isError ? (
            <div className="srn-empty">暂无摘要</div>
          ) : hasBrief ? (
            <div className="srn-block">
              {data?.summary && <p className="srn-summary">{data.summary}</p>}
              {data?.points.length ? <CitedList items={data.points} /> : null}
              {data?.risks.length ? (
                <div className="srn-risks">
                  <span className="srn-sub">值得担心</span>
                  <CitedList items={data.risks} />
                </div>
              ) : null}
            </div>
          ) : (
            <div className="srn-empty">暂无摘要</div>
          )}

          {/* 时间线 */}
          <div className="srn-block">
            <div className="srn-head">
              <span className="srn-sub">时间线</span>
              {narr?.item_count ? <span className="srn-n">{narr.item_count} 条</span> : null}
              <button className="srn-link" onClick={runGenNar} disabled={genNar.isPending}>
                {genNar.isPending ? '融合中…' : narr ? '重新生成' : '生成时间线'}
              </button>
            </div>
            {genNar.isError ? (
              <div className="srn-empty">{(genNar.error as Error).message}</div>
            ) : narr ? (
              <NarrativeBody data={narr} />
            ) : genNar.isPending ? (
              <div className="fin-empty">融合中…</div>
            ) : (
              <div className="srn-empty faint">点「生成时间线」把近况捋成带日期的主线</div>
            )}
          </div>

          {/* 社媒热度 */}
          <div className="srn-block">
            <div className="srn-head">
              <span className="srn-sub">社媒热度</span>
              {heat?.source_count ? <span className="srn-n">{heat.source_count} 条</span> : null}
              <span className={`social-pill heat-${heatTone}`}>{heat?.heat ?? '低'}</span>
              <span className="social-pill">{heat?.sentiment ?? '不明'}</span>
            </div>
            {social.isLoading ? (
              <div className="fin-empty">加载…</div>
            ) : hasSocial ? (
              <>
                {heat?.summary && <p className="srn-summary">{heat.summary}</p>}
                {platformEntries.length ? (
                  <div className="social-platforms">
                    {platformEntries.map(([name, count]) => (
                      <span key={name}>
                        {name} {count}
                      </span>
                    ))}
                  </div>
                ) : null}
                <SocialGroup label="偏多" items={heat?.bull_points ?? []} />
                <SocialGroup label="反方" items={heat?.bear_points ?? []} />
                <SocialGroup label="观察" items={heat?.watch ?? []} />
              </>
            ) : (
              <div className="srn-empty faint">{heat?.status || '暂无社媒信号'}</div>
            )}
          </div>
        </div>
      </Collapse>
    </section>
  )
}

function SocialGroup({ label, items }: { label: string; items: CitedPoint[] }) {
  if (!items.length) return null
  return (
    <div className="srn-sg">
      <span className="srn-sg-l">{label}</span>
      <CitedList items={items} />
    </div>
  )
}
