import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../../store'
import {
  streamReport,
  useClusters,
  useGenerateClusters,
  useGenerateNarrative,
  useNarrative,
  useNewsFeed,
  useNewsReport,
  useQuote,
  useRefreshDirected,
  useStockNews,
  type ClusterParams,
  type NewsCluster,
} from '../../api'
import Collapse from '../../components/Collapse'
import { useNews } from './store'
import { TW_CATS, themeLabel } from './consts'
import { Digest, FeedGroups } from './shared'
import OpportunitiesPanel from './OpportunitiesPanel'
import StockSourcesPanel from './StockSourcesPanel'

const EASE = [0.22, 1, 0.36, 1] as const
const fmtDate = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}

// ── 日报块（某天 digest + 生成/重生成）；总览与「日报」视图共用 ──
function DigestBlock({ date, showGenerate = true }: { date: string | null; showGenerate?: boolean }) {
  const report = useNewsReport(date)
  const qc = useQueryClient()
  const [gen, setGen] = useState('')
  const [genState, setGenState] = useState<'idle' | 'loading' | 'error'>('idle')

  const run = async () => {
    setGen('')
    setGenState('loading')
    try {
      await streamReport(date, (d) => setGen((p) => p + d))
      setGenState('idle')
      setGen('')
      qc.invalidateQueries({ queryKey: ['news-report'] })
      qc.invalidateQueries({ queryKey: ['news-reports'] })
    } catch (e) {
      setGen((e as Error).message)
      setGenState('error')
    }
  }

  const data = report.data
  const streaming = genState === 'loading'
  return (
    <>
      <div className="know-head">
        <h2>{data ? `${fmtDate(data.report_date)} · 趋势日报` : '趋势日报'}</h2>
        {showGenerate && (
          <button className="btn btn-primary jsm" disabled={streaming} onClick={run}>
            {streaming ? '生成中…' : data ? '重新生成' : '✨ 生成今日日报'}
          </button>
        )}
      </div>
      {streaming || genState === 'error' ? (
        <div className={`report-card ${genState === 'error' ? 'err' : ''}`}>
          {genState === 'error' ? <p>{gen}</p> : <Digest body={gen || '…'} />}
        </div>
      ) : data ? (
        <div className="report-card">
          <Digest body={data.body} />
          <div className="report-foot faint">非投资建议</div>
        </div>
      ) : report.isLoading ? (
        <div className="report-card faint">加载日报…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有这天的日报</div>
        </div>
      )}
    </>
  )
}

// ── 晨读 · 今日要事（Top3）：复用 news@1d 要点的前 3 条，scheduler 每日预生成 ──
// date 给定（某天快照）→ 取/生成那一天的要点；省略＝今天。
function MorningBrief({ date, heading = '晨读 · 今日要事' }: { date?: string; heading?: string }) {
  const params = { days: 1, date }
  const clusters = useClusters(params)
  const gen = useGenerateClusters()
  const top = (clusters.data?.clusters ?? []).slice(0, 3)
  return (
    <section className="brief">
      <div className="sec-head">
        <h3>{heading}</h3>
        <button className="btn btn-primary jsm" disabled={gen.isPending} onClick={() => gen.mutate(params)}>
          {gen.isPending ? '生成中…' : top.length ? '刷新' : '✨ 生成晨读'}
        </button>
      </div>
      {gen.isPending ? (
        <div className="opp-empty faint">正在挑出今天最要紧的几件事…</div>
      ) : top.length ? (
        <ol className="brief-list">
          {top.map((c, i) => {
            const imp = IMP[c.importance] ?? IMP.med
            return (
              <li className="brief-item" key={i}>
                <span className="brief-n">{i + 1}</span>
                <div className="brief-body">
                  <div className="brief-line">
                    <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
                    <span className="brief-head">{c.headline}</span>
                  </div>
                  {c.why && <div className="brief-why">{c.why}</div>}
                </div>
              </li>
            )
          })}
        </ol>
      ) : clusters.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="opp-empty faint">点「生成晨读」，从今日新闻里挑出最要紧的 3 件事。</div>
      )}
    </section>
  )
}

// ── 自上次以来：自打卡基准以来发布的新条目（确定性、零成本）──
function SinceLast() {
  const lastSeen = useUI((s) => s.lastSeenNewsAt)
  const markSeen = useUI((s) => s.markNewsSeen)
  const feed = useNewsFeed(150, { days: 7 })
  const [open, setOpen] = useState(true)
  const fresh = useMemo(() => {
    if (!lastSeen) return []
    const lo = new Date(lastSeen).getTime()
    return (feed.data ?? []).filter((it) => {
      const t = new Date(it.published_at ?? '').getTime()
      return !Number.isNaN(t) && t > lo
    })
  }, [feed.data, lastSeen])

  if (!lastSeen)
    return (
      <section className="since">
        <div className="since-bar">
          <span className="faint">想追踪「自上次以来」的新增？先设个基准。</span>
          <button className="btn jsm" onClick={markSeen}>
            标记此刻为已读
          </button>
        </div>
      </section>
    )
  if (!fresh.length) return null // 无新增 → 不占位
  return (
    <section className="since">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>
          自上次以来 <span className="since-n">{fresh.length}</span>
        </h3>
        <button
          className="btn jsm"
          onClick={(e) => {
            e.stopPropagation()
            markSeen()
          }}
        >
          标记已读
        </button>
      </div>
      <Collapse open={open}>
        <FeedGroups items={fresh} />
      </Collapse>
    </section>
  )
}

// ── 总览：晨读 Top3 + 自上次以来 + 机会 + 日报 + 今日要闻 ──
function OverviewView() {
  const feed = useNewsFeed(80)
  return (
    <div className="know">
      <MorningBrief />
      <SinceLast />
      <OpportunitiesPanel />
      <DigestBlock date={null} />
      <section className="feed">
        <div className="sec-head">
          <h3>今日要闻</h3>
          <span className="feed-count">{feed.data?.length ?? 0} 条</span>
        </div>
        <FeedGroups items={feed.data ?? []} empty="还没有新闻，先「↻ 刷新信源」" />
      </section>
    </div>
  )
}

// ── 每日 · 某天快照：那一天的 日报 + 要事 Top3 + 机会 + 要闻（统一时间轴）──
function dayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function DaySnapshotView() {
  const secondary = useNews((s) => s.secondary)
  const date = secondary ?? dayStr() // 默认今天
  const isToday = date === dayStr()
  const feed = useNewsFeed(120, { day: date })
  return (
    <div className="know">
      <DigestBlock date={date} />
      <MorningBrief date={date} heading={isToday ? '今日要事' : '当日要事'} />
      <OpportunitiesPanel date={date} />
      <section className="feed">
        <div className="sec-head">
          <h3>当日要闻</h3>
          <span className="feed-count">{feed.data?.length ?? 0} 条</span>
        </div>
        <FeedGroups items={feed.data ?? []} empty={feed.isLoading ? '加载…' : '这一天还没有抓到要闻'} />
      </section>
    </div>
  )
}

// ── 新闻 / 推特：时间线 ↔ 要点（去重聚类+重要性排序）+ 时间范围 ──
const IMP: Record<string, { label: string; cls: string }> = {
  critical: { label: '非常重要', cls: 'imp-critical' },
  high: { label: '重要', cls: 'imp-high' },
  med: { label: '一般', cls: 'imp-med' },
  low: { label: '次要', cls: 'imp-low' },
}
const RANGES = [
  { d: 1, label: '今天' },
  { d: 7, label: '近7天' },
  { d: 30, label: '近30天' },
]

function ClusterCard({ c }: { c: NewsCluster }) {
  const [open, setOpen] = useState(false)
  const imp = IMP[c.importance] ?? IMP.med
  return (
    <article className="cl-card">
      <header className="cl-head" onClick={() => setOpen((v) => !v)} role="button">
        <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
        <span className="cl-headline">{c.headline}</span>
        {c.members.length > 1 && <span className="cl-n">{c.members.length}</span>}
      </header>
      {c.why && <div className="cl-why">{c.why}</div>}
      <Collapse open={open}>
        <div className="cl-members">
          {c.members.map((m, i) => (
            <a key={i} className="cl-member" href={m.url} target="_blank" rel="noreferrer">
              <span className="cl-msrc">{m.source}</span>
              <span className="cl-mtitle">{m.title}</span>
            </a>
          ))}
        </div>
      </Collapse>
    </article>
  )
}

function ClusterList({ params }: { params: ClusterParams }) {
  const clusters = useClusters(params)
  const gen = useGenerateClusters()
  const [showLow, setShowLow] = useState(false)
  const data = clusters.data
  const all = data?.clusters ?? []
  const list = all.filter((c) => showLow || c.importance !== 'low')
  const lowN = all.filter((c) => c.importance === 'low').length

  return (
    <div className="clusters">
      <div className="cl-bar">
        <button
          className="btn btn-primary jsm"
          disabled={gen.isPending}
          onClick={() => gen.mutate(params)}
        >
          {gen.isPending ? '聚类中…' : data ? '重新生成' : '✨ 生成要点'}
        </button>
      </div>
      {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}
      {gen.isPending ? (
        <div className="opp-empty faint">正在按事件去重合并、按重要性排序…</div>
      ) : data ? (
        <>
          {list.map((c, i) => (
            <ClusterCard key={i} c={c} />
          ))}
          {lowN > 0 && !showLow && (
            <button className="cl-morelow" onClick={() => setShowLow(true)}>
              显示 {lowN} 条次要
            </button>
          )}
        </>
      ) : clusters.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有要点</div>
        </div>
      )}
    </div>
  )
}

// 时间线/要点 + 时间范围 的通用视图（新闻、推特共用）
function ScopedNews({
  title,
  theme,
  sourcePrefix,
  categoryFilter,
  category,
}: {
  title: string
  theme?: string
  sourcePrefix?: string
  categoryFilter?: string // 推特时间线：客户端按账号分类过滤
  category?: string // 推特要点：分类（后端过滤）
}) {
  const [mode, setMode] = useState<'time' | 'key'>('time')
  const [days, setDays] = useState(1)
  const feed = useNewsFeed(days >= 7 ? 400 : 150, { theme, sourcePrefix, days })
  const items = (feed.data ?? []).filter((i) => !categoryFilter || i.category === categoryFilter)
  return (
    <div className="know">
      <div className="know-head">
        <h2>{title}</h2>
        <div className="know-segs">
          <div className="seg range-seg">
            {RANGES.map((r) => (
              <button key={r.d} aria-pressed={days === r.d} onClick={() => setDays(r.d)}>
                {r.label}
              </button>
            ))}
          </div>
          <div className="seg feed-seg">
            <button aria-pressed={mode === 'time'} onClick={() => setMode('time')}>
              时间线
            </button>
            <button aria-pressed={mode === 'key'} onClick={() => setMode('key')}>
              要点
            </button>
          </div>
        </div>
      </div>
      {mode === 'time' ? (
        <FeedGroups items={items} empty={feed.isLoading ? '加载…' : '该范围暂无内容'} />
      ) : (
        <ClusterList params={{ theme, sourcePrefix, category, days }} />
      )}
    </div>
  )
}

function FeedView() {
  const theme = useNews((s) => s.secondary) || ''
  return <ScopedNews title={themeLabel(theme)} theme={theme || undefined} />
}

function TwitterView() {
  const cat = useNews((s) => s.secondary) || ''
  const label = TW_CATS.find((c) => c.key === cat)?.label ?? '全部'
  return (
    <ScopedNews
      title={`推特 · ${label}`}
      sourcePrefix="X·"
      categoryFilter={cat || undefined}
      category={cat || undefined}
    />
  )
}

// ── 个股：标的叙事时间线（融合定向抓取 + 申报）──
function StockNarrative({ symbol }: { symbol: string }) {
  const nar = useNarrative(symbol)
  const gen = useGenerateNarrative()
  const fetchD = useRefreshDirected()
  const news = useStockNews(symbol, 0)
  const q = useQuote(symbol)
  const [mkt, code] = symbol.split(':')
  const data = nar.data
  return (
    <div className="know">
      <div className="know-head">
        <h2>
          {q.data?.name || code} <span className="narr-sub">{code} · {mkt}</span>
        </h2>
        <div className="narr-actions">
          <button className="btn jsm" disabled={fetchD.isPending} onClick={() => fetchD.mutate(symbol)}>
            {fetchD.isPending ? '抓取中…' : '↻ 抓取最新'}
          </button>
          <button
            className="btn btn-primary jsm"
            disabled={gen.isPending}
            onClick={() => gen.mutate(symbol)}
          >
            {gen.isPending ? '融合中…' : data ? '重新生成' : '✨ 生成叙事'}
          </button>
        </div>
      </div>
      {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}

      {gen.isPending ? (
        <div className="report-card faint">正在融合该股近况、提炼主线与时间线…</div>
      ) : data ? (
        <>
          {data.summary && <div className="narr-summary">{data.summary}</div>}
          <div className="narr-timeline">
            {data.timeline.map((ev, i) => {
              const imp = IMP[ev.importance] ?? IMP.med
              return (
                <div className="narr-ev" key={i}>
                  <div className="narr-ev-head">
                    <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
                    {ev.date && <span className="narr-date">{ev.date}</span>}
                    <span className="narr-ev-title">{ev.title}</span>
                  </div>
                  {ev.refs.length > 0 && (
                    <div className="narr-refs">
                      {ev.refs.map((r, j) => (
                        <a key={j} className="narr-ref" href={r.url} target="_blank" rel="noreferrer">
                          <span className="narr-ref-src">{r.source}</span>
                          <span className="narr-ref-title">{r.title}</span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="report-foot faint">融合 {data.item_count} 条资讯 · 非投资建议</div>
        </>
      ) : nar.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有这只股的叙事</div>
          <div className="faint">点「✨ 生成叙事」让 LLM 融合最近的资讯成主线与时间线</div>
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <StockSourcesPanel symbol={symbol} />
      </div>

      <section className="feed" style={{ marginTop: 18 }}>
        <div className="sec-head">
          <h3>资讯流</h3>
          <span className="feed-count">{news.data?.length ?? 0} 条</span>
        </div>
        <FeedGroups
          items={news.data ?? []}
          empty={news.isLoading ? '加载…' : '点「↻ 抓取最新」按 ticker 直取该股新闻'}
        />
      </section>
    </div>
  )
}

function StockNarrativeView() {
  const symbol = useNews((s) => s.secondary)
  if (!symbol)
    return (
      <div className="know">
        <div className="know-empty">
          <div className="ke-title">从左侧选择一支自选股</div>
          <div className="faint">看它最近在发生什么——LLM 融合的主线与时间线</div>
        </div>
      </div>
    )
  return <StockNarrative key={symbol} symbol={symbol} />
}

// ── 机会 ──
function OppsView() {
  return (
    <div className="know">
      <OpportunitiesPanel />
    </div>
  )
}

export default function KnowView() {
  const primary = useNews((s) => s.primary)
  const secondary = useNews((s) => s.secondary)
  return (
    <motion.div
      key={`${primary}/${secondary ?? ''}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: EASE }}
      style={{ minHeight: '100%' }}
    >
      {primary === 'overview' && <OverviewView />}
      {primary === 'stocks' && <StockNarrativeView />}
      {primary === 'digest' && <DaySnapshotView />}
      {primary === 'news' && <FeedView />}
      {primary === 'twitter' && <TwitterView />}
      {primary === 'opps' && <OppsView />}
    </motion.div>
  )
}
