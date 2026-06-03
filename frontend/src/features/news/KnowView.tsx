import { useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { streamReport, useNewsFeed, useNewsReport } from '../../api'
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

// ── 新闻（按主题）──
function FeedView() {
  const theme = useNews((s) => s.secondary)
  const feed = useNewsFeed(200, { theme: theme || undefined })
  return (
    <div className="know">
      <div className="know-head">
        <h2>{themeLabel(theme || '')} · 要闻</h2>
        <span className="feed-count">{feed.data?.length ?? 0} 条</span>
      </div>
      <FeedGroups items={feed.data ?? []} empty="该主题暂无要闻" />
    </div>
  )
}

// ── 推特（按账号分类）──
function TwitterView() {
  const cat = useNews((s) => s.secondary)
  const feed = useNewsFeed(250, { sourcePrefix: 'X·' })
  const items = (feed.data ?? []).filter((i) => !cat || i.category === cat)
  const label = TW_CATS.find((c) => c.key === (cat || ''))?.label ?? '全部'
  return (
    <div className="know">
      <div className="know-head">
        <h2>推特 · {label}</h2>
        <span className="feed-count">{items.length} 条</span>
      </div>
      <FeedGroups
        items={items}
        empty={feed.isLoading ? '加载…' : '还没有推文（需配 twtapi key 并刷新信源）'}
      />
    </div>
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
