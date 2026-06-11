import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../../store'
import {
  useClusters,
  useGenerateClusters,
  useGenerateNarrative,
  useGenerateOpportunities,
  useGenerateReport,
  useNarrative,
  useNewsFeed,
  useNewsReadState,
  useNewsReport,
  useQuote,
  useRefreshDirected,
  useRefreshNews,
  useStockNews,
  type ClusterParams,
  type NewsCluster,
} from '../../api'
import Collapse from '../../components/Collapse'
import { useNews } from './store'
import { SOURCE_LANES, type SourceLaneId } from './consts'
import { BlogList, FeedGroups } from './shared'
import Markdown from '../../components/Markdown'
import DigestReport from './DigestReport'
import SectionReportsView from './SectionDigest'
import OpportunitiesPanel from './OpportunitiesPanel'
import StockSourcesPanel from './StockSourcesPanel'
import { IMP, NarrativeBody } from './NarrativeTimeline'
import { EASE } from '../../theme/motion'

const fmtDate = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}
const stripRefs = (s: string) => s.replace(/(?:\s*\[\d{1,5}\])+/g, '').trim()
type ClusterSym = { symbol: string; name: string; watched: boolean }

// ── 日报块（某天 digest + 生成/重生成）；总览与「日报」视图共用 ──
function DigestBlock({ date, showGenerate = true }: { date: string | null; showGenerate?: boolean }) {
  const report = useNewsReport(date)
  const genReport = useGenerateReport()
  const [open, setOpen] = useState(true)
  const data = report.data
  const generating = genReport.isPending
  const structured = Boolean(data && (data.verdict || data.sections.length > 0))
  const hasAny = Boolean(structured || data?.markdown)
  return (
    <section className="ovsec">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>{data ? `${fmtDate(data.report_date)} · 综合日报` : '综合日报'}</h3>
        {showGenerate && (
          <button
            className="btn btn-primary jsm sec-gen"
            disabled={generating}
            onClick={(e) => {
              e.stopPropagation()
              setOpen(true)
              genReport.mutate(date)
            }}
          >
            {generating ? '生成中…' : hasAny ? '重新生成' : '生成综合日报'}
          </button>
        )}
      </div>
      <Collapse open={open}>
        {generating ? (
          <div className="report-card faint">正在分层蒸馏综合日报…（约 20–40 秒）</div>
        ) : genReport.isError ? (
          <div className="report-card err">
            <p>{(genReport.error as Error).message}</p>
          </div>
        ) : structured ? (
          <DigestReport data={data!} />
        ) : data?.markdown ? (
          <div className="report-card">
            <Markdown body={data.markdown} />
          </div>
        ) : report.isLoading ? (
          <div className="report-card faint">加载日报…</div>
        ) : (
          <div className="know-empty">
            <div className="ke-title">暂无综合日报</div>
          </div>
        )}
      </Collapse>
    </section>
  )
}

// ── 每日 · 某天快照：总结 / 决策共用单张综合日报 ──
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
  const genReport = useGenerateReport()
  const genOpps = useGenerateOpportunities()
  const readState = useNewsReadState()
  const [fetch, setFetch] = useState<GenStep>('idle')
  const [digest, setDigest] = useState<GenStep>('idle')
  const running = [fetch, digest].includes('run')
  const freshCount = readState.data?.fresh_count ?? 0

  // 一键刷新并生成：先刷新所有信源，再并行生成「综合日报 + 今日机会」。总结页以这张卡片为单一入口。
  const run = async () => {
    setFetch('idle')
    setDigest('run')
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
    // 机会与日报同源、彼此独立 → 刷新后**并行**生成：一键即得「结构化日报 + 今日机会」。
    // 两个 mutation 各自 onSuccess 失效相关查询；机会失败不连累日报状态（§11 优雅降级）。
    const oppsP = genOpps.mutateAsync(date).catch(() => {})
    try {
      await genReport.mutateAsync(date)
      setDigest('done')
    } catch {
      setDigest('err')
    }
    await oppsP
  }

  return (
    <div className="sum-head">
      <div className="sum-title-line">
        <h2 className="sum-title">{isToday ? '今天' : fmtDate(date)}</h2>
        {isToday && (
          <span className={`since-pill ${freshCount > 0 ? 'hot' : ''}`}>
            自上次以来 {freshCount}
          </span>
        )}
      </div>
      <div className="sum-gen">
        {(running || digest !== 'idle') && (
          <span className="sum-steps faint">
            {isToday && <>抓取 {stepDot(fetch)} · </>}综合日报 {stepDot(digest)}
          </span>
        )}
        <button className="btn btn-primary jsm" disabled={running} onClick={run}>
          {running ? '生成中…' : isToday ? '刷新并生成综合日报' : '生成综合日报'}
        </button>
      </div>
    </div>
  )
}

// 资讯 · 某天「总结」：综合日报（整合新闻/博客/社媒弱信号）+ 今日机会（含相关标的「看/研」引导）。
// 原「决策」页已并入此处——机会卡与其关联标的引导回到日报正文下方。
function DaySummaryView({ date }: { date: string }) {
  const isToday = date === dayStr()
  return (
    <div className="know">
      <DaySummaryHead date={date} isToday={isToday} />
      <DigestBlock date={date} showGenerate={false} />
      <OpportunitiesPanel date={date} showGenerate={false} />
    </div>
  )
}

// ── 新闻 / 博客 / 社媒：时间线 ↔ 要点（去重聚类+重要性排序）+ 时间范围 ──
// related：决策页把挂钩自选股就近挂到这条要事下面（其它处不传 → 不显示）。
function ClusterCard({ c, related = [] }: { c: NewsCluster; related?: ClusterSym[] }) {
  const [open, setOpen] = useState(false)
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  const imp = IMP[c.importance] ?? IMP.med
  return (
    <article className="cl-card">
      <header className="cl-head" onClick={() => setOpen((v) => !v)} role="button">
        <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
        <span className="cl-headline">{stripRefs(c.headline)}</span>
        {c.members.length > 1 && <span className="cl-n">{c.members.length}</span>}
      </header>
      {c.why && <div className="cl-why">{stripRefs(c.why)}</div>}
      {related.length > 0 && (
        <div className="cl-syms">
          {related.map((s) => (
            <span className={`dsym ${s.watched ? 'watched' : ''}`} key={s.symbol}>
              <button onClick={() => select(s.symbol)}>{s.name}</button>
              <button onClick={() => research(s.symbol)}>研</button>
            </span>
          ))}
        </div>
      )}
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
  const theme = lane.filterBy === 'theme' && filter ? filter : undefined
  const sourcePrefix = lane.sourcePrefix
  const category = lane.filterBy === 'category' && filter ? filter : undefined
  const feed = useNewsFeed(250, { theme, sourcePrefix, category, day: date })
  const items = (feed.data ?? []).filter((i) => {
    if (lane.filterBy === 'category' && filter && i.category !== filter) return false
    if (lane.filterBy === 'theme' && filter && i.theme !== filter) return false
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
      {!lane.live ? (
        <div className="lane-empty">
          <div className="ke-title">待接入</div>
        </div>
      ) : (
        <>
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
        </>
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
          <NarrativeBody data={data} />
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

// 资讯 · 博客：长文阅读清单。博客是低频长文 → 不按单日切片（几乎永远空），而是滚动近一月聚合；
// 也不做要点聚类（逐篇读才是博客的用法）。纯阅读卡，与新闻/社媒的标题行/要点明确区别开。
function BlogLaneView() {
  const feed = useNewsFeed(120, { sourcePrefix: SOURCE_LANES.blogs.sourcePrefix, days: 30 })
  const items = feed.data ?? []
  return (
    <div className="know">
      <div className="know-head">
        <h3>
          博客 <span className="faint">· 近一月长读</span>
        </h3>
        {items.length > 0 && <span className="feed-count">{items.length} 篇</span>}
      </div>
      <BlogList items={items} empty={feed.isLoading ? '加载…' : '近一月暂无博客长文'} />
    </div>
  )
}

// 资讯：某天（infoDate）+ 三级板块（总结/新闻/博客/社媒…）
function InfoView() {
  const infoDate = useNews((s) => s.infoDate)
  const infoSection = useNews((s) => s.infoSection)
  const date = infoDate ?? dayStr()
  if (infoSection === 'sectors') return <SectionReportsView key={`sectors${date}`} date={date} />
  if (infoSection === 'blogs') return <BlogLaneView key="blogs" />
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
