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
  useSocialPulse,
  useStockNews,
  type ClusterParams,
  type NewsCluster,
  type NewsItem,
  type SocialPulseItem,
} from '../../api'
import Collapse from '../../components/Collapse'
import { useNews } from './store'
import { SOURCE_LANES, type SourceLaneId } from './consts'
import { Digest, FeedGroups } from './shared'
import OpportunitiesPanel from './OpportunitiesPanel'
import StockSourcesPanel from './StockSourcesPanel'
import { IMP, NarrativeBody } from './NarrativeTimeline'
import { EASE } from '../../theme/motion'

const fmtDate = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}
const stripRefs = (s: string) => s.replace(/(?:\s*\[\d{1,5}\])+/g, '').trim()
const normUrl = (u: string) => (u || '').split('?')[0].replace(/\/+$/, '').toLowerCase()
type ClusterSym = { symbol: string; name: string; watched: boolean }

// ── 日报块（某天 digest + 生成/重生成）；总览与「日报」视图共用 ──
function DigestBlock({ date, showGenerate = true }: { date: string | null; showGenerate?: boolean }) {
  const report = useNewsReport(date)
  const qc = useQueryClient()
  const [gen, setGen] = useState('')
  const [genState, setGenState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [open, setOpen] = useState(true)

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
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>{data ? `${fmtDate(data.report_date)} · 趋势日报` : '趋势日报'}</h3>
        {showGenerate && (
          <button
            className="btn btn-primary jsm sec-gen"
            disabled={streaming}
            onClick={(e) => {
              e.stopPropagation()
              setOpen(true)
              run()
            }}
          >
            {streaming ? '生成中…' : data ? '重新生成' : '生成今日日报'}
          </button>
        )}
      </div>
      <Collapse open={open}>
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
      </Collapse>
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
  const [open, setOpen] = useState(true)
  return (
    <section className="brief">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>{heading}</h3>
        {top.length > 0 && <span className="feed-count">{top.length}</span>}
        {showGenerate && (
          <button
            className="btn btn-primary jsm sec-gen"
            disabled={gen.isPending}
            onClick={(e) => {
              e.stopPropagation()
              setOpen(true)
              gen.mutate(params)
            }}
          >
            {gen.isPending ? '生成中…' : top.length ? '刷新' : '生成晨读'}
          </button>
        )}
      </div>
      <Collapse open={open}>
        {gen.isPending ? (
          <div className="opp-empty faint">生成中…</div>
        ) : top.length ? (
          <ol className="brief-list">
            {top.map((c, i) => (
              <BriefCard key={`${c.headline}-${i}`} cluster={c} rank={i + 1} />
            ))}
          </ol>
        ) : clusters.isLoading ? (
          <div className="report-card faint">加载…</div>
        ) : (
          <div className="opp-empty faint">暂无要事</div>
        )}
      </Collapse>
    </section>
  )
}

function BriefCard({ cluster, rank }: { cluster: NewsCluster; rank: number }) {
  const [open, setOpen] = useState(false)
  const imp = IMP[cluster.importance] ?? IMP.med
  const sources = cluster.members.filter((m) => m.source || m.title || m.url)
  return (
    <li className={`brief-item ${open ? 'open' : ''}`}>
      <button className="brief-card-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="brief-n">{rank}</span>
        <span className="brief-body">
          <span className="brief-line">
            <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
            <span className="brief-head">{stripRefs(cluster.headline)}</span>
            {sources.length > 0 && <span className="brief-src-n">{sources.length} 源</span>}
          </span>
          {cluster.why && <span className="brief-why">{stripRefs(cluster.why)}</span>}
        </span>
      </button>
      <Collapse open={open}>
        <div className="brief-members">
          {sources.length ? (
            sources.map((m, i) => {
              const content = (
                <>
                  <span className="brief-msrc">{m.source || '来源'}</span>
                  <span className="brief-mtitle">{stripRefs(m.title)}</span>
                </>
              )
              return m.url ? (
                <a
                  key={`${m.url}-${i}`}
                  className="brief-member"
                  href={m.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {content}
                </a>
              ) : (
                <div key={`${m.title}-${i}`} className="brief-member">
                  {content}
                </div>
              )
            })
          ) : (
            <div className="brief-empty-src">暂无来源明细</div>
          )}
        </div>
      </Collapse>
    </li>
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
  const [social, setSocial] = useState<GenStep>('idle')
  const [opps, setOpps] = useState<GenStep>('idle')
  const running = [fetch, digest, clusters, tw, social, opps].includes('run')

  // 一键刷新并生成：先刷新信源（新闻+推特+自选定向），再并行蒸馏 日报/要事/推特要点/机会。
  // 先刷新后生成——否则蒸馏的是旧数据。仅今天可刷新（历史日不再抓新源）。
  const run = async () => {
    setFetch('idle')
    setDigest('run')
    setClusters('run')
    setTw('run')
    setSocial('run')
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
        .mutateAsync({ sourcePrefix: 'X·', days: 1, date }) // 推特要点（TikHub）
        .then(() => setTw('done'))
        .catch(() => setTw('err')),
      // 其余社媒各 lane 要点（小红书/Reddit/Threads）——合并成一个步骤；无数据的 lane
      // 会失败（无条目），只要有一个成功就算 done，全失败才 err。
      Promise.allSettled(
        ['小红书·', 'Reddit·', 'Threads·'].map((sp) =>
          genClusters.mutateAsync({ sourcePrefix: sp, days: 1, date }),
        ),
      ).then((r) => setSocial(r.some((x) => x.status === 'fulfilled') ? 'done' : 'err')),
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
            {stepDot(clusters)} · 推特 {stepDot(tw)} · 社媒 {stepDot(social)} · 机会{' '}
            {stepDot(opps)}
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
      <SocialPulse date={date} variant="section" />
    </div>
  )
}

// ── 社媒脉搏：把各 lane 已生成的要点聚合到「总结 / 决策」，让综合视图接入所有信源 ──
const IMP_ORDER: Record<string, number> = { critical: 0, high: 1, med: 2, low: 3 }

function PulseRow({ it, mode }: { it: SocialPulseItem; mode: 'merged' | 'grouped' }) {
  const imp = IMP[it.importance] ?? IMP.med
  const inner = (
    <>
      {mode === 'merged' ? (
        <span className="sp-plat-tag">{it.platform}</span>
      ) : (
        <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
      )}
      <span className="sp-body">
        <span className="sp-head">{stripRefs(it.headline)}</span>
        {mode === 'merged' && it.why && <span className="sp-why">{stripRefs(it.why)}</span>}
      </span>
    </>
  )
  return it.url ? (
    <a className="sp-row" href={it.url} target="_blank" rel="noreferrer">
      {inner}
    </a>
  ) : (
    <div className="sp-row">{inner}</div>
  )
}

// variant='panel'：决策——合并全平台、按重要性排序的「社媒信号」面板；
// variant='section'：总结——按平台分组的「社媒热度」一览。读已生成要点，无则不占位。
function SocialPulse({ date, variant }: { date: string; variant: 'panel' | 'section' }) {
  const pulse = useSocialPulse(date)
  const lanes = pulse.data?.lanes ?? []
  const [open, setOpen] = useState(true)
  if (!lanes.length) return null

  if (variant === 'panel') {
    const merged = lanes
      .flatMap((l) => l.items)
      .sort((a, b) => (IMP_ORDER[a.importance] ?? 2) - (IMP_ORDER[b.importance] ?? 2))
      .slice(0, 8)
    return (
      <section className="decision-panel social-pulse">
        <div className="sec-head">
          <h3>社媒信号</h3>
          <span className="feed-count">{lanes.length} 平台</span>
        </div>
        <div className="sp-list">
          {merged.map((it, i) => (
            <PulseRow key={i} it={it} mode="merged" />
          ))}
        </div>
      </section>
    )
  }
  return (
    <section className="ovsec social-pulse-sec">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>社媒热度</h3>
        <span className="feed-count">{lanes.length} 平台</span>
      </div>
      <Collapse open={open}>
        <div className="sp-lanes">
          {lanes.map((l) => (
            <div key={l.platform} className="sp-lane">
              <div className="sp-lane-h">
                <span className="sp-plat-tag">{l.platform}</span>
                <span className="srn-n">{l.total}</span>
              </div>
              {l.items.map((it, i) => (
                <PulseRow key={i} it={it} mode="grouped" />
              ))}
            </div>
          ))}
        </div>
      </Collapse>
    </section>
  )
}

// ── 决策工作台：把「机会 / 风险反证 / 催化 / 关联标的 / 社媒信号」集中到一屏 ──
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
  // 关联标的不再单列：建 url→挂钩自选股 映射，把标的就近挂到每条要事/反证/催化下面
  const urlSyms = useMemo(() => {
    const m = new Map<string, ClusterSym[]>()
    ;(feed.data ?? []).forEach((it: NewsItem) => {
      if (!it.url) return
      m.set(
        normUrl(it.url),
        it.symbols.map((s) => ({
          symbol: s.symbol,
          name: s.name || s.symbol.split(':')[1],
          watched: Boolean(s.in_watchlist),
        })),
      )
    })
    return m
  }, [feed.data])
  const clusterSyms = (c: NewsCluster): ClusterSym[] => {
    const seen = new Set<string>()
    const out: ClusterSym[] = []
    for (const m of c.members) {
      for (const s of urlSyms.get(normUrl(m.url)) ?? []) {
        if (!seen.has(s.symbol)) {
          seen.add(s.symbol)
          out.push(s)
        }
      }
    }
    return out.slice(0, 6)
  }
  const loading = clusters.isLoading || opps.isLoading || feed.isLoading

  return (
    <div className="know decision">
      <div className="know-head">
        <h2>
          决策 <span className="faint">· {fmtDate(date)}</span>
        </h2>
      </div>
      {loading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <>
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
                  <ClusterCard key={c.headline} c={c} related={clusterSyms(c)} />
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
                  <ClusterCard key={c.headline} c={c} related={clusterSyms(c)} />
                ))}
              </div>
            ) : (
              <div className="opp-empty faint">暂无催化</div>
            )}
          </section>

        </div>
        <SocialPulse date={date} variant="panel" />
        </>
      )}
    </div>
  )
}

// ── 新闻 / 推特：时间线 ↔ 要点（去重聚类+重要性排序）+ 时间范围 ──
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
  const theme = kind === 'news' && filter ? filter : undefined
  const sourcePrefix = lane.sourcePrefix
  const category = kind !== 'news' && filter ? filter : undefined
  const feed = useNewsFeed(250, { theme, sourcePrefix, category, day: date })
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
