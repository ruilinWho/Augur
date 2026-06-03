import { useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import {
  streamReport,
  useClusters,
  useGenerateClusters,
  useNewsFeed,
  useNewsReport,
  type ClusterParams,
  type NewsCluster,
} from '../../api'
import Collapse from '../../components/Collapse'
import { useNews } from './store'
import { TW_CATS, themeLabel } from './consts'
import { Digest, FeedGroups } from './shared'
import OpportunitiesPanel from './OpportunitiesPanel'

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

// ── 总览：日报 + 今日机会 + 今日要闻 ──
function OverviewView() {
  const feed = useNewsFeed(80)
  return (
    <div className="know">
      <DigestBlock date={null} />
      <OpportunitiesPanel />
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

// ── 日报（按天）──
function DigestView() {
  const date = useNews((s) => s.secondary)
  return (
    <div className="know">
      <DigestBlock date={date} />
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
      {primary === 'digest' && <DigestView />}
      {primary === 'news' && <FeedView />}
      {primary === 'twitter' && <TwitterView />}
      {primary === 'opps' && <OppsView />}
    </motion.div>
  )
}
