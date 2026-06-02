import { useMemo, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import Collapse from '../../components/Collapse'
import { streamReport, useNewsFeed, useNewsReport, type NewsItem } from '../../api'
import { useNews } from './store'
import OpportunitiesPanel from './OpportunitiesPanel'

const EASE = [0.22, 1, 0.36, 1] as const

// 今日要闻按天归类的日期标签
function dayLabel(iso: string | null): string {
  if (!iso) return '更早'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '更早'
  const a = new Date()
  a.setHours(0, 0, 0, 0)
  const b = new Date(d)
  b.setHours(0, 0, 0, 0)
  const diff = Math.round((a.getTime() - b.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff} 天前`
  return `${b.getMonth() + 1}月${b.getDate()}日`
}

// ── 极简内联：**加粗** → <strong> ──
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>,
  )
}

// ## 小标题 / - 列表 / --- 分隔 / 段落 —— 轻量 Markdown 渲染（无需依赖）
function Digest({ body }: { body: string }) {
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) {
      const items = list
      blocks.push(
        <ul key={`u${blocks.length}`}>
          {items.map((t, i) => (
            <li key={i}>{inline(t)}</li>
          ))}
        </ul>,
      )
      list = []
    }
  }
  body.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (!line) return flush()
    if (line === '---' || line === '***') {
      flush()
      blocks.push(<hr key={`h${i}`} />)
    } else if (line.startsWith('## ')) {
      flush()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^##\s+/, '')}</h4>)
    } else if (line.startsWith('# ')) {
      flush()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^#\s+/, '')}</h4>)
    } else if (/^[-*]\s+/.test(line)) {
      list.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flush()
      blocks.push(<p key={`p${i}`}>{inline(line)}</p>)
    }
  })
  flush()
  return <div className="digest">{blocks}</div>
}

const fmtDate = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}

function ago(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const h = Math.round(mins / 60)
  if (h < 24) return `${h}小时前`
  return `${Math.round(h / 24)}天前`
}

function Headline({ item }: { item: NewsItem }) {
  return (
    <a className="hl" href={item.url} target="_blank" rel="noreferrer">
      <span className="hl-src">{item.source}</span>
      <span className="hl-title">{item.title_zh || item.title}</span>
      {ago(item.published_at) && <span className="hl-ago">{ago(item.published_at)}</span>}
    </a>
  )
}

export default function KnowView() {
  const selectedDate = useNews((s) => s.selectedDate)
  const setSelectedDate = useNews((s) => s.setSelectedDate)
  const report = useNewsReport(selectedDate)
  const feed = useNewsFeed(150)
  const qc = useQueryClient()

  const [gen, setGen] = useState('')
  const [genState, setGenState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [feedOpen, setFeedOpen] = useState(true)

  const runGenerate = async () => {
    setGen('')
    setGenState('loading')
    try {
      await streamReport(null, (d) => setGen((p) => p + d)) // null = 今天
      setGenState('idle')
      setGen('')
      setSelectedDate(null) // 跳到最新（今天）
      qc.invalidateQueries({ queryKey: ['news-report'] })
      qc.invalidateQueries({ queryKey: ['news-reports'] })
    } catch (e) {
      setGen((e as Error).message)
      setGenState('error')
    }
  }

  const data = report.data
  const streaming = genState === 'loading'

  // 今日要闻按天归类（feed 已按时间倒序，故天的出现顺序即新→旧）
  const byDay = useMemo(() => {
    const order: string[] = []
    const m: Record<string, NewsItem[]> = {}
    for (const it of feed.data ?? []) {
      const d = dayLabel(it.published_at)
      if (!m[d]) {
        m[d] = []
        order.push(d)
      }
      m[d].push(it)
    }
    return order.map((d) => [d, m[d]] as const)
  }, [feed.data])

  return (
    <motion.div
      className="know"
      key={selectedDate ?? 'latest'}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="know-head">
        <h2>{data ? `${fmtDate(data.report_date)} · 趋势日报` : '趋势日报'}</h2>
        <button className="btn btn-primary jsm" disabled={streaming} onClick={runGenerate}>
          {streaming ? '生成中…' : data ? '重新生成' : '✨ 生成今日日报'}
        </button>
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
          <div className="ke-title">还没有今日日报</div>
        </div>
      )}

      <OpportunitiesPanel />

      <section className="feed">
        <div className="sec-head" onClick={() => setFeedOpen((o) => !o)} role="button">
          <h3>今日要闻</h3>
          <span className="feed-count">{feed.data?.length ?? 0} 条</span>
        </div>
        <Collapse open={feedOpen}>
          <div className="feed-groups">
            {byDay.map(([day, items]) => (
              <div key={day} className="feed-group">
                <div className="fg-head">
                  <span className="fg-theme">{day}</span>
                  <span className="fg-n">{items.length}</span>
                </div>
                <div className="hl-list">
                  {items.map((it) => (
                    <Headline key={it.id} item={it} />
                  ))}
                </div>
              </div>
            ))}
            {feed.data && feed.data.length === 0 && (
              <div className="faint" style={{ padding: '12px 2px' }}>
                还没有新闻
              </div>
            )}
          </div>
        </Collapse>
      </section>
    </motion.div>
  )
}
