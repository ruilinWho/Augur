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
  useOpportunities,
  useQuote,
  useRefreshDirected,
  useRefreshNews,
  useSchedule,
  useStockNews,
  type ClusterParams,
  type NewsCluster,
  type NewsItem,
} from '../../api'
import Collapse from '../../components/Collapse'
import { useNews } from './store'
import { SOURCE_LANES, type SourceLaneId } from './consts'
import { Digest, FeedGroups } from './shared'
import OpportunitiesPanel from './OpportunitiesPanel'
import StockSourcesPanel from './StockSourcesPanel'
import { EASE } from '../../theme/motion'

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
          <div className="ke-title">暂无日报</div>
        </div>
      )}
    </section>
  )
}

// ── 晨读 · 今日要事：复用 news@1d 要点的前 N 条（N 可配，设置「自动·生成」），每日预生成 ──
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
  const topN = useSchedule().data?.brief_top_n ?? 5
  const top = (clusters.data?.clusters ?? []).slice(0, topN)
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
        <div className="opp-empty faint">生成中…</div>
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
        <div className="opp-empty faint">暂无要事</div>
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
  const [open, setOpen] = useState(false) // 默认收起（可能很多；点标题展开）
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
          <button className="btn jsm" onClick={markSeen}>
            设置已读基准
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
  const refreshNews = useRefreshNews()
  const refreshDirected = useRefreshDirected()
  const genClusters = useGenerateClusters()
  const genOpps = useGenerateOpportunities()
  const [fetch, setFetch] = useState<GenStep>('idle')
  const [digest, setDigest] = useState<GenStep>('idle')
  const [clusters, setClusters] = useState<GenStep>('idle')
  const [tw, setTw] = useState<GenStep>('idle')
  const [opps, setOpps] = useState<GenStep>('idle')
  const running = [fetch, digest, clusters, tw, opps].includes('run')

  // 一键刷新并生成：先刷新信源（新闻+推特+自选定向），再并行蒸馏 日报/要事/推特要点/机会。
  // 先刷新后生成——否则蒸馏的是旧数据。仅今天可刷新（历史日不再抓新源）。
  const run = async () => {
    setFetch('idle')
    setDigest('run')
    setClusters('run')
    setTw('run')
    setOpps('run')
    if (isToday) {
      setFetch('run')
      // 刷新（含相关性/标股流水线）+ 自选定向；任一失败不挡生成（用已有数据兜底）。
      // allSettled 永不 reject → 只有两者都失败才记 ✗（部分成功仍算抓取完成，诚实标注）。
      const r = await Promise.allSettled([
        refreshNews.mutateAsync(),
        refreshDirected.mutateAsync(undefined),
      ])
      setFetch(r.every((x) => x.status === 'rejected') ? 'err' : 'done')
      qc.invalidateQueries({ queryKey: ['news-feed'] })
    }
    await Promise.allSettled([
      streamReport(date, () => {})
        .then(() => {
          setDigest('done')
          qc.invalidateQueries({ queryKey: ['news-report'] })
          qc.invalidateQueries({ queryKey: ['news-reports'] })
        })
        .catch(() => setDigest('err')),
      genClusters
        .mutateAsync({ days: 1, date }) // 要事＝新闻「全部」要点（同 scope）
        .then(() => setClusters('done'))
        .catch(() => setClusters('err')),
      genClusters
        .mutateAsync({ sourcePrefix: 'X·', days: 1, date }) // 推特要点
        .then(() => setTw('done'))
        .catch(() => setTw('err')),
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
            {isToday && <>抓取 {stepDot(fetch)} · </>}日报 {stepDot(digest)} · 要事{' '}
            {stepDot(clusters)} · 推特 {stepDot(tw)} · 机会 {stepDot(opps)}
          </span>
        )}
        <button className="btn btn-primary jsm" disabled={running} onClick={run}>
          {running ? '生成中…' : isToday ? '一键刷新并生成' : '一键生成'}
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

// ── 决策工作台：把「机会 / 风险反证 / 催化 / 关联标的」集中到一屏 ──
function DecisionView({ date }: { date: string }) {
  const clusters = useClusters({ days: 1, date })
  const opps = useOpportunities(date)
  const feed = useNewsFeed(400, { day: date })
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)

  const allClusters = clusters.data?.clusters ?? []
  const keyClusters = allClusters.filter((c) => c.importance === 'critical' || c.importance === 'high')
  const risks = keyClusters.filter((c) =>
    /风险|反证|监管|调查|通胀|利率|短缺|泡沫|亏损|下调|禁令|关税|压力|risk|probe|inflation|ban/i.test(
      `${c.headline} ${c.why}`,
    ),
  )
  const catalysts = keyClusters.filter((c) => !risks.includes(c))
  const opportunities = opps.data?.opportunities ?? []
  const highOpps = opportunities.filter((o) => o.confidence === 'high' || o.confidence === 'med')
  const symbolMap = new Map<string, { symbol: string; name: string; n: number; watched: boolean }>()
  ;(feed.data ?? []).forEach((it: NewsItem) => {
    it.symbols.forEach((s) => {
      const prev = symbolMap.get(s.symbol)
      symbolMap.set(s.symbol, {
        symbol: s.symbol,
        name: s.name || s.symbol.split(':')[1],
        n: (prev?.n ?? 0) + 1,
        watched: Boolean(prev?.watched || s.in_watchlist),
      })
    })
  })
  const symbols = [...symbolMap.values()].sort((a, b) => b.n - a.n).slice(0, 18)
  const loading = clusters.isLoading || opps.isLoading || feed.isLoading

  return (
    <div className="know decision">
      <div className="know-head">
        <h2>
          决策 <span className="faint">· {fmtDate(date)}</span>
        </h2>
        <div className="decision-score">
          <span>
            <b>{keyClusters.length}</b>
            要事
          </span>
          <span>
            <b>{highOpps.length}</b>
            机会
          </span>
          <span>
            <b>{symbols.length}</b>
            标的
          </span>
        </div>
      </div>
      {loading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="decision-grid">
          <section className="decision-panel accent">
            <div className="sec-head">
              <h3>主动机会</h3>
              <span className="feed-count">{highOpps.length}</span>
            </div>
            {highOpps.length ? (
              <div className="decision-list">
                {highOpps.slice(0, 6).map((o, i) => (
                  <article className="decision-item" key={`${o.title}-${i}`}>
                    <div className="di-title">{o.title}</div>
                    {o.thesis && <div className="di-body">{o.thesis}</div>}
                    {o.related.length > 0 && (
                      <div className="di-chips">
                        {o.related
                          .filter((r) => r.resolved && r.symbol)
                          .slice(0, 6)
                          .map((r) => (
                            <span className={`di-chip ${r.in_watchlist ? 'watched' : ''}`} key={r.symbol}>
                              <button onClick={() => select(r.symbol!)}>{r.name}</button>
                              <button onClick={() => research(r.symbol!)}>研</button>
                            </span>
                          ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="opp-empty faint">暂无机会</div>
            )}
          </section>

          <section className="decision-panel">
            <div className="sec-head">
              <h3>风险 / 反证</h3>
              <span className="feed-count">{risks.length}</span>
            </div>
            {risks.length ? (
              <div className="decision-list compact">
                {risks.slice(0, 7).map((c) => (
                  <ClusterCard key={c.headline} c={c} />
                ))}
              </div>
            ) : (
              <div className="opp-empty faint">暂无反证</div>
            )}
          </section>

          <section className="decision-panel">
            <div className="sec-head">
              <h3>催化</h3>
              <span className="feed-count">{catalysts.length}</span>
            </div>
            {catalysts.length ? (
              <div className="decision-list compact">
                {catalysts.slice(0, 7).map((c) => (
                  <ClusterCard key={c.headline} c={c} />
                ))}
              </div>
            ) : (
              <div className="opp-empty faint">暂无催化</div>
            )}
          </section>

          <section className="decision-panel">
            <div className="sec-head">
              <h3>关联标的</h3>
              <span className="feed-count">{symbols.length}</span>
            </div>
            {symbols.length ? (
              <div className="decision-symbols">
                {symbols.map((s) => (
                  <span className={`dsym ${s.watched ? 'watched' : ''}`} key={s.symbol}>
                    <button onClick={() => select(s.symbol)}>{s.name}</button>
                    <i>{s.n}</i>
                    <button onClick={() => research(s.symbol)}>研</button>
                  </span>
                ))}
              </div>
            ) : (
              <div className="opp-empty faint">暂无标的</div>
            )}
          </section>
        </div>
      )}
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
        <div className="opp-empty faint">聚类中…</div>
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
          <div className="ke-title">暂无要点</div>
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

// 资讯 · 某天的某个 source lane：主题/账号/社区分类过滤 + 时间线/要点切换
function DayScopedNews({ date, kind }: { date: string; kind: SourceLaneId }) {
  // 默认「要点」（作者：去重聚类更易读）——但仅今天：历史日要点不会自动生成，默认时间线才有内容
  const [mode, setMode] = useState<'time' | 'key'>(date === dayStr() ? 'key' : 'time')
  const [filter, setFilter] = useState('') // theme key（新闻）/ category key（社交 lane）；''=全部
  const [mkt, setMkt] = useState('') // 市场前缀；''=全部
  const [onlyWatch, setOnlyWatch] = useState(false) // 仅自选（挂钩了自选股的条目）
  const lane = SOURCE_LANES[kind]
  const opts = lane.filters
  const theme = kind === 'news' && filter ? filter : undefined
  const sourcePrefix = lane.sourcePrefix
  const category = kind !== 'news' && filter ? filter : undefined
  const feed = useNewsFeed(250, { theme, sourcePrefix, day: date })
  const items = (feed.data ?? []).filter((i) => {
    if (kind !== 'news' && filter && i.category !== filter) return false
    if (onlyWatch && i.symbols.length === 0) return false
    if (mkt && !i.symbols.some((s) => s.symbol.startsWith(`${mkt}:`))) return false
    return true
  })
  const clusterParams: ClusterParams = { theme, sourcePrefix, category, days: 1, date }
  return (
    <div className="know">
      <div className="know-head">
        <h3>
          {lane.label} <span className="faint">· {fmtDate(date)}</span>
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
        <FeedGroups items={items} empty={feed.isLoading ? '加载…' : '暂无内容'} />
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
        <div className="report-card faint">融合中…</div>
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
          <div className="ke-title">暂无叙事</div>
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
          empty={news.isLoading ? '加载…' : '暂无资讯'}
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
          <div className="ke-title">个股叙事</div>
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
  if (infoSection === 'decision') return <DecisionView key={`d${date}`} date={date} />
  if (infoSection in SOURCE_LANES) {
    return <DayScopedNews key={`${infoSection}${date}`} date={date} kind={infoSection as SourceLaneId} />
  }
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
