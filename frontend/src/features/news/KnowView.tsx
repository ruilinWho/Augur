import { useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import Collapse from '../../components/Collapse'
import { streamReport, useNewsFeed, useNewsReport, type NewsItem } from '../../api'
import { useNews } from './store'

const EASE = [0.22, 1, 0.36, 1] as const

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

const CAT_LABEL: Record<string, string> = { markets: '行情', tech: '科技', world: '国际' }

function Headline({ item }: { item: NewsItem }) {
  return (
    <a className="hl" href={item.url} target="_blank" rel="noreferrer">
      <span className="hl-src">{item.source}</span>
      <span className="hl-title">{item.title}</span>
      <span className="hl-meta">
        {item.category && <span className={`hl-cat c-${item.category}`}>{CAT_LABEL[item.category] ?? item.category}</span>}
        {ago(item.published_at) && <span className="hl-ago">{ago(item.published_at)}</span>}
      </span>
    </a>
  )
}

export default function KnowView() {
  const selectedDate = useNews((s) => s.selectedDate)
  const setSelectedDate = useNews((s) => s.setSelectedDate)
  const report = useNewsReport(selectedDate)
  const feed = useNewsFeed(40)
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

  return (
    <motion.div
      className="know"
      key={selectedDate ?? 'latest'}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="know-head">
        <div>
          <h2>{data ? `${fmtDate(data.report_date)} · 趋势日报` : '趋势日报'}</h2>
          {data && (
            <div className="know-sub faint">
              蒸馏自 {data.item_count} 条新闻 · {data.model}
            </div>
          )}
        </div>
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
          <div className="report-foot faint">
            研究辅助，非投资建议 · 蒸馏自所列信源标题，可能有误，请回看原文核实。
          </div>
        </div>
      ) : report.isLoading ? (
        <div className="report-card faint">加载日报…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有今日日报</div>
          <div className="faint">点右上「生成今日日报」，由 LLM 蒸馏当下全球要闻为一份趋势速览。</div>
        </div>
      )}

      <section className="feed">
        <div className="sec-head" onClick={() => setFeedOpen((o) => !o)} role="button">
          <h3>今日要闻</h3>
          <span className="feed-count">{feed.data?.length ?? 0} 条</span>
        </div>
        <Collapse open={feedOpen}>
          <div className="hl-list">
            {feed.data?.map((it) => (
              <Headline key={it.id} item={it} />
            ))}
            {feed.data && feed.data.length === 0 && (
              <div className="faint" style={{ padding: '12px 2px' }}>
                还没有新闻。左侧「刷新信源」抓取最新内容。
              </div>
            )}
          </div>
        </Collapse>
      </section>
    </motion.div>
  )
}
