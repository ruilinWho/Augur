import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../../store'
import {
  streamReport,
  useClusters,
  useGenerateClusters,
  useGenerateOpportunities,
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
import { THEMES, TW_CATS } from './consts'
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
    <section className="ovsec">
      <div className="sec-head">
        <h3>{data ? `${fmtDate(data.report_date)} · 趋势日报` : '趋势日报'}</h3>
        {showGenerate && (
          <button className="btn btn-primary jsm sec-gen" disabled={streaming} onClick={run}>
            {streaming ? '生成中…' : data ? '重新生成' : '生成今日日报'}
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
        </div>
      ) : report.isLoading ? (
        <div className="report-card faint">加载日报…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有这天的日报</div>
        </div>
      )}
    </section>
  )
}

// ── 晨读 · 今日要事（Top3）：复用 news@1d 要点的前 3 条，scheduler 每日预生成 ──
// date 给定（某天快照）→ 取/生成那一天的要点；省略＝今天。
function MorningBrief({
  date,
  heading = '晨读 · 今日要事',
  showGenerate = true,
}: {
  date?: string
  heading?: string
  showGenerate?: boolean
}) {
  const params = { days: 1, date }
  const clusters = useClusters(params)
  const gen = useGenerateClusters()
  const top = (clusters.data?.clusters ?? []).slice(0, 3)
  return (
    <section className="brief">
      <div className="sec-head">
        <h3>{heading}</h3>
        {showGenerate && (
          <button
            className="btn btn-primary jsm sec-gen"
            disabled={gen.isPending}
            onClick={() => gen.mutate(params)}
          >
            {gen.isPending ? '生成中…' : top.length ? '刷新' : '生成晨读'}
          </button>
        )}
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
        <div className="opp-empty faint">还没有今日要事</div>
      )}
    </section>
  )
}

// ── 自上次以来：自打卡基准以来发布的新条目（确定性、零成本）──
function SinceLast() {
  const lastSeen = useUI((s) => s.lastSeenNewsAt)
  const markSeen = useUI((s) => s.markNewsSeen)
  // 窗口随「距上次」自适应（久未点也能看全，封顶 30 天）；上限放宽到 500（修原 150 封顶）
  const days = lastSeen
    ? Math.min(30, Math.max(1, Math.ceil((Date.now() - new Date(lastSeen).getTime()) / 86400000) + 1))
    : 7
  const feed = useNewsFeed(500, { days })
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

// ── 每日 · 某天快照：那一天的 日报 + 要事 Top3 + 机会 + 要闻（统一时间轴）──
function dayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 一键生成：把那天的 日报 + 要事 + 机会 三样并行生成；各步独立成败、带状态点。
type GenStep = 'idle' | 'run' | 'done' | 'err'
const stepDot = (s: GenStep) => (s === 'done' ? '✓' : s === 'err' ? '✗' : s === 'run' ? '·' : '·')

function DaySummaryHead({ date, isToday }: { date: string; isToday: boolean }) {
  const qc = useQueryClient()
  const genClusters = useGenerateClusters()
  const genOpps = useGenerateOpportunities()
  const [digest, setDigest] = useState<GenStep>('idle')
  const [clusters, setClusters] = useState<GenStep>('idle')
  const [opps, setOpps] = useState<GenStep>('idle')
  const running = [digest, clusters, opps].includes('run')

  const run = async () => {
    setDigest('run')
    setClusters('run')
    setOpps('run')
    await Promise.allSettled([
      streamReport(date, () => {})
        .then(() => {
          setDigest('done')
          qc.invalidateQueries({ queryKey: ['news-report'] })
          qc.invalidateQueries({ queryKey: ['news-reports'] })
        })
        .catch(() => setDigest('err')),
      genClusters
        .mutateAsync({ days: 1, date })
        .then(() => setClusters('done'))
        .catch(() => setClusters('err')),
      genOpps
        .mutateAsync(date)
        .then(() => setOpps('done'))
        .catch(() => setOpps('err')),
    ])
  }

  return (
    <div className="sum-head">
      <h2 className="sum-title">{isToday ? '今天' : fmtDate(date)}</h2>
      <div className="sum-gen">
        {(running || digest !== 'idle') && (
          <span className="sum-steps faint">
            日报 {stepDot(digest)} · 要事 {stepDot(clusters)} · 机会 {stepDot(opps)}
          </span>
        )}
        <button className="btn btn-primary jsm" disabled={running} onClick={run}>
          {running ? '生成中…' : '一键生成'}
        </button>
      </div>
    </div>
  )
}

// 资讯 · 某天「总结」：那天蒸馏出的结论 = 趋势日报 + 要事 Top3 + 机会（原始新闻/推特在同级别另两个板块）。
// 看今天时，顶部加「自上次以来」增量（跨天的「上次查看后新增」，原总览独有，合并到此）。
function DaySummaryView({ date }: { date: string }) {
  const isToday = date === dayStr()
  return (
    <div className="know">
      {/* 一键生成统管 日报+要事+机会；各块隐藏独立生成按钮，一屏只一个主操作（§9 克制） */}
      <DaySummaryHead date={date} isToday={isToday} />
      {isToday && <SinceLast />}
      <DigestBlock date={date} showGenerate={false} />
      <MorningBrief date={date} heading={isToday ? '今日要事' : '当日要事'} showGenerate={false} />
      <OpportunitiesPanel date={date} showGenerate={false} />
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
          {gen.isPending ? '聚类中…' : data ? '重新生成' : '生成要点'}
        </button>
      </div>
      {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}
      {gen.isPending ? (
        <div className="opp-empty faint">正在按事件去重合并、按重要性排序…</div>
      ) : data ? (
        <>
          {list.map((c, i) => (
            <ClusterCard key={c.headline || `c${i}`} c={c} />
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

// 市场过滤：按条目挂钩的自选股 symbol 前缀（linker 只挂自选股 → symbols 即"我关注的票"）
const MKTS: { key: string; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'US', label: '美' },
  { key: 'HK', label: '港' },
  { key: 'CN', label: 'A' },
  { key: 'KR', label: '韩' },
]

// 资讯 · 某天的「新闻」或「推特」：固定那一天，主题/账号分类做**舞台内过滤** + 时间线/要点切换
function DayScopedNews({ date, kind }: { date: string; kind: 'news' | 'twitter' }) {
  const [mode, setMode] = useState<'time' | 'key'>('time')
  const [filter, setFilter] = useState('') // theme key（新闻）/ category key（推特）；''=全部
  const [mkt, setMkt] = useState('') // 市场前缀；''=全部
  const [onlyWatch, setOnlyWatch] = useState(false) // 仅自选（挂钩了自选股的条目）
  const opts = kind === 'news' ? THEMES : TW_CATS
  const theme = kind === 'news' && filter ? filter : undefined
  const sourcePrefix = kind === 'twitter' ? 'X·' : undefined
  const category = kind === 'twitter' && filter ? filter : undefined
  const feed = useNewsFeed(250, { theme, sourcePrefix, day: date })
  const items = (feed.data ?? []).filter((i) => {
    if (kind === 'twitter' && filter && i.category !== filter) return false
    if (onlyWatch && i.symbols.length === 0) return false
    if (mkt && !i.symbols.some((s) => s.symbol.startsWith(`${mkt}:`))) return false
    return true
  })
  const clusterParams: ClusterParams = { theme, sourcePrefix, category, days: 1, date }
  return (
    <div className="know">
      <div className="know-head">
        <h3>
          {kind === 'news' ? '新闻' : '推特'} <span className="faint">· {fmtDate(date)}</span>
        </h3>
        <div className="seg feed-seg">
          <button aria-pressed={mode === 'time'} onClick={() => setMode('time')}>
            时间线
          </button>
          <button aria-pressed={mode === 'key'} onClick={() => setMode('key')}>
            要点
          </button>
        </div>
      </div>
      <div className="tfilter">
        {opts.map((o) => (
          <button
            key={o.key}
            className={`tfilter-chip ${filter === o.key ? 'active' : ''}`}
            onClick={() => setFilter(o.key)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {/* 市场 + 仅自选（挂钩自选股的条目）——"我关注的盘子今天发生了什么" */}
      <div className="tfilter tfilter-mkt">
        {MKTS.map((o) => (
          <button
            key={o.key}
            className={`tfilter-chip ${mkt === o.key ? 'active' : ''}`}
            onClick={() => setMkt(o.key)}
          >
            {o.label}
          </button>
        ))}
        <button
          className={`tfilter-chip ow ${onlyWatch ? 'active' : ''}`}
          onClick={() => setOnlyWatch((v) => !v)}
          title="只看挂钩了自选股的资讯"
        >
          仅自选
        </button>
      </div>
      {mode === 'time' ? (
        <FeedGroups items={items} empty={feed.isLoading ? '加载…' : '这一天暂无内容'} />
      ) : (
        <ClusterList params={clusterParams} />
      )}
    </div>
  )
}

// ── 个股：标的叙事时间线（融合定向抓取 + 申报）──
function StockNarrative({ symbol }: { symbol: string }) {
  const nar = useNarrative(symbol)
  const gen = useGenerateNarrative()
  const fetchD = useRefreshDirected()
  const news = useStockNews(symbol, 0)
  const q = useQuote(symbol)
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  const [mkt, code] = symbol.split(':')
  const data = nar.data
  // 自生成叙事以来新增的资讯条数（确定性、零 LLM）——提示是否值得重生成（§11 暴露新鲜度）
  const freshCount = useMemo(() => {
    if (!data?.created_at) return 0
    const lo = new Date(data.created_at.replace(' ', 'T') + 'Z').getTime()
    return (news.data ?? []).filter((it) => {
      const t = new Date(it.published_at ?? '').getTime()
      return !Number.isNaN(t) && t > lo
    }).length
  }, [news.data, data?.created_at])
  return (
    <div className="know">
      <div className="know-head">
        <h2>
          {q.data?.name || code} <span className="narr-sub">{code} · {mkt}</span>
        </h2>
        <div className="narr-actions">
          <button className="ncta" onClick={() => select(symbol)} title="在「看」里查看 K 线">
            看
          </button>
          <button className="ncta" onClick={() => research(symbol)} title="生成深度研究">
            研
          </button>
          <button className="btn jsm" disabled={fetchD.isPending} onClick={() => fetchD.mutate(symbol)}>
            {fetchD.isPending ? '抓取中…' : '↻ 抓取最新'}
          </button>
          <button
            className="btn btn-primary jsm"
            disabled={gen.isPending}
            onClick={() => gen.mutate(symbol)}
          >
            {gen.isPending ? '融合中…' : data ? '重新生成' : '生成叙事'}
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
                <div className="narr-ev" key={`ev-${i}`}>
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
          <div className="report-foot faint">
            融合 {data.item_count} 条资讯
            {data.created_at && ` · 生成于 ${data.created_at.slice(0, 10)}`}
            {freshCount > 0 && (
              <span className="narr-fresh"> · 自生成后新增 {freshCount} 条（可重生成）</span>
            )}
          </div>
        </>
      ) : nar.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有这只股的叙事</div>
          <div className="faint">点「生成叙事」让 LLM 融合最近的资讯成主线与时间线</div>
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
  const symbol = useNews((s) => s.stockSym)
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

// 资讯：某天（infoDate）+ 三级板块（总结/新闻/推特）
function InfoView() {
  const infoDate = useNews((s) => s.infoDate)
  const infoSection = useNews((s) => s.infoSection)
  const date = infoDate ?? dayStr()
  if (infoSection === 'news') return <DayScopedNews key={`n${date}`} date={date} kind="news" />
  if (infoSection === 'twitter') return <DayScopedNews key={`t${date}`} date={date} kind="twitter" />
  return <DaySummaryView date={date} />
}

export default function KnowView() {
  const primary = useNews((s) => s.primary)
  const stockSym = useNews((s) => s.stockSym)
  const infoDate = useNews((s) => s.infoDate)
  const infoSection = useNews((s) => s.infoSection)
  return (
    <motion.div
      key={`${primary}/${stockSym ?? ''}/${infoDate ?? ''}/${infoSection}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: EASE }}
      style={{ minHeight: '100%' }}
    >
      {primary === 'info' && <InfoView />}
      {primary === 'stocks' && <StockNarrativeView />}
    </motion.div>
  )
}
