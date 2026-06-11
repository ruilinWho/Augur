import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'
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

// 已尝试过自动生成时间线的标的（本会话内，避免每次挂载重复触发 / 失败死循环）
const _autoNar = new Set<string>()

// 要点：文字本身就是可点链接（hover 出下划线），不把 url 写出来；多来源时附极小上标。
function CitedText({ p }: { p: CitedPoint }) {
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
        <a key={i} className="cited-sup" href={r.url} target="_blank" rel="noreferrer" title={r.source}>
          {i + 2}
        </a>
      ))}
    </span>
  )
}

function CitedList({ items }: { items: CitedPoint[] }) {
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

// 子卡片：标题行点击折叠（无三角，靠 hover+点击发现）。每个子模块独立卡片、独立折叠。
function SubCard({
  title,
  right,
  children,
  defaultOpen = true,
}: {
  title: string
  right?: ReactNode
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`srn-card ${open ? 'open' : ''}`}>
      <div className="srn-card-head" role="button" onClick={() => setOpen((o) => !o)}>
        <span className="srn-card-title">{title}</span>
        {right}
      </div>
      <Collapse open={open}>
        <div className="srn-card-body">{children}</div>
      </Collapse>
    </div>
  )
}

// 「看·相关资讯」：一张卡片，内含 近况 / 社媒热度 / 时间线 三个独立可折叠子卡片。
// 傻瓜式：全部自动加载/生成，只有一个「刷新」重抓+重生成。
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
  const hasTimeline = Boolean(narr && narr.timeline.length > 0)

  // 傻瓜式：时间线没生成过就自动生成一次（本会话每只股只试一次，cached 后直接读库）
  const genRef = useRef(genNar.mutate)
  genRef.current = genNar.mutate
  useEffect(() => {
    if (nar.isLoading || genNar.isPending) return
    if (!narr && !_autoNar.has(symbol)) {
      _autoNar.add(symbol)
      genRef.current(symbol)
    }
  }, [symbol, narr, nar.isLoading, genNar.isPending])

  const runRefresh = (e: MouseEvent) => {
    e.stopPropagation()
    _autoNar.add(symbol) // 手动刷新即重生成，关掉自动那次
    refresh.mutate(symbol)
    genNar.mutate(symbol)
  }
  const busy = refresh.isPending || genNar.isPending

  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>相关资讯</h3>
        {n > 0 && <span className="feed-count">{n} 源</span>}
        {enabledSources > 0 && <span className="feed-count stock-src-n">专属 {enabledSources}</span>}
        <button className="btn btn-ghost jsm stock-news-refresh" onClick={runRefresh} disabled={busy}>
          {busy ? '更新中…' : '刷新'}
        </button>
      </div>

      <Collapse open={open}>
        <div className="srn">
          {/* 近况 */}
          <SubCard title="近况">
            {brief.isLoading ? (
              <div className="fin-empty">加载…</div>
            ) : hasBrief ? (
              <>
                {data?.summary && <p className="srn-summary">{data.summary}</p>}
                {data?.points.length ? <CitedList items={data.points} /> : null}
                {data?.risks.length ? (
                  <div className="srn-risks">
                    <span className="srn-risks-l">值得担心</span>
                    <CitedList items={data.risks} />
                  </div>
                ) : null}
              </>
            ) : (
              <div className="srn-empty faint">暂无摘要</div>
            )}
          </SubCard>

          {/* 社媒热度 */}
          <SubCard
            title="社媒热度"
            right={
              <span className="srn-card-meta">
                <span className={`social-pill heat-${heatTone}`}>{heat?.heat ?? '低'}</span>
                <span className="social-pill">{heat?.sentiment ?? '不明'}</span>
                {heat?.source_count ? <span className="srn-n">{heat.source_count} 条</span> : null}
              </span>
            }
          >
            {social.isLoading ? (
              <div className="fin-empty">加载…</div>
            ) : hasSocial ? (
              <>
                {heat?.summary && <p className="srn-social-sum">{heat.summary}</p>}
                <div className="srn-social-cols">
                  <SocialCol label="偏多" tone="bull" items={heat?.bull_points ?? []} />
                  <SocialCol label="反方" tone="bear" items={heat?.bear_points ?? []} />
                  <SocialCol label="观察" tone="watch" items={heat?.watch ?? []} />
                </div>
                {platformEntries.length ? (
                  <div className="srn-social-plat">
                    {platformEntries.map(([name, count]) => (
                      <span key={name}>
                        {name} <b>{count}</b>
                      </span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <div className="srn-empty faint">{heat?.status || '暂无社媒信号'}</div>
            )}
          </SubCard>

          {/* 时间线（自动生成）——放在社媒热度下面，默认收起（点标题展开），避免又长又乱 */}
          {(hasTimeline || (!narr && genNar.isPending)) && (
            <SubCard
              title="时间线"
              defaultOpen={false}
              right={narr?.item_count ? <span className="srn-n">{narr.item_count} 条</span> : undefined}
            >
              {hasTimeline ? (
                <NarrativeBody data={narr!} hideSummary />
              ) : (
                <div className="fin-empty">融合中…</div>
              )}
            </SubCard>
          )}
        </div>
      </Collapse>
    </section>
  )
}

function SocialCol({ label, tone, items }: { label: string; tone: string; items: CitedPoint[] }) {
  if (!items.length) return null
  return (
    <div className={`srn-sc srn-sc-${tone}`}>
      <span className="srn-sc-l">{label}</span>
      <ul className="cited-list">
        {items.map((p, i) => (
          <li key={i}>
            <CitedText p={p} />
          </li>
        ))}
      </ul>
    </div>
  )
}
