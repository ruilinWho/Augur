import { useMemo, useRef, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import {
  streamResearch,
  useQuote,
  useResearchReport,
  type ResearchSource,
} from '../../api'
import { useUI } from '../../store'
import ImportedReports from './ImportedReports'

const EASE = [0.22, 1, 0.36, 1] as const

// ── 内联：**加粗** · 裸链接 · [n] 引用上标（有源 url 则可点）──
function inline(text: string, srcUrl: (n: number) => string | null): ReactNode[] {
  // 先按 **加粗** / 裸 URL / [n] 切分，逐段渲染
  const parts = text.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s)]+|\[\d+\])/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i}>{p.slice(2, -2)}</strong>
    if (/^https?:\/\//.test(p))
      return (
        <a key={i} className="cite-link" href={p} target="_blank" rel="noreferrer">
          原文
        </a>
      )
    const m = p.match(/^\[(\d+)\]$/)
    if (m) {
      const n = Number(m[1])
      const url = srcUrl(n)
      const chip = <sup className="cite">[{n}]</sup>
      return url ? (
        <a key={i} href={url} target="_blank" rel="noreferrer" className="cite-a" title="查看来源">
          {chip}
        </a>
      ) : (
        <span key={i}>{chip}</span>
      )
    }
    return <span key={i}>{p}</span>
  })
}

// 轻量 Markdown：## 标题 / > 引用 / - 列表 / |表格| / 段落（含引用上标）
function Report({ body, sources }: { body: string; sources: ResearchSource[] }) {
  const srcUrl = useMemo(() => {
    const m = new Map<number, string>()
    for (const s of sources) if (s.url) m.set(s.n, s.url)
    return (n: number) => m.get(n) ?? null
  }, [sources])

  const blocks: ReactNode[] = []
  let list: string[] = []
  let quote: string[] = []
  let table: string[] = []
  const flushList = () => {
    if (!list.length) return
    const items = list
    blocks.push(
      <ul key={`u${blocks.length}`}>
        {items.map((t, i) => (
          <li key={i}>{inline(t, srcUrl)}</li>
        ))}
      </ul>,
    )
    list = []
  }
  const flushQuote = () => {
    if (!quote.length) return
    const items = quote
    blocks.push(
      <blockquote key={`q${blocks.length}`}>
        {items.map((t, i) => (
          <p key={i}>{inline(t, srcUrl)}</p>
        ))}
      </blockquote>,
    )
    quote = []
  }
  const flushTable = () => {
    if (!table.length) return
    const rows = table
      .map((r) => r.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()))
      // 分隔行（---|---）丢弃
      .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c) || c === ''))
    const [head, ...rest] = rows
    blocks.push(
      <div key={`tb${blocks.length}`} className="rep-table-wrap">
        <table className="rep-table">
          {head && (
            <thead>
              <tr>
                {head.map((c, i) => (
                  <th key={i}>{inline(c, srcUrl)}</th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rest.map((cells, r) => (
              <tr key={r}>
                {cells.map((c, i) => (
                  <td key={i}>{inline(c, srcUrl)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
    table = []
  }
  const flushAll = () => {
    flushList()
    flushQuote()
    flushTable()
  }

  body.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (!line) return flushAll()
    if (line.startsWith('|') && line.includes('|', 1)) {
      flushList()
      flushQuote()
      table.push(line)
      return
    }
    flushTable()
    if (line === '---' || line === '***') {
      flushAll()
      blocks.push(<hr key={`h${i}`} />)
    } else if (line.startsWith('> ') || line === '>') {
      flushList()
      quote.push(line.replace(/^>\s?/, ''))
    } else if (line.startsWith('## ')) {
      flushAll()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^##\s+/, '')}</h4>)
    } else if (line.startsWith('# ')) {
      flushAll()
      blocks.push(<h3 key={`t${i}`}>{line.replace(/^#\s+/, '')}</h3>)
    } else if (/^[-*]\s+/.test(line)) {
      flushQuote()
      list.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flushAll()
      blocks.push(<p key={`p${i}`}>{inline(line, srcUrl)}</p>)
    }
  })
  flushAll()
  return <div className="digest report">{blocks}</div>
}

function fmtWhen(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes(),
  ).padStart(2, '0')}`
}

export default function ResearchView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const quote = useQuote(symbol)
  const report = useResearchReport(symbol)
  const qc = useQueryClient()

  const [gen, setGen] = useState('')
  const [genState, setGenState] = useState<'idle' | 'loading' | 'error'>('idle')
  const abortRef = useRef<AbortController | null>(null)

  const name = report.data?.name || quote.data?.name || ''

  const runGenerate = async () => {
    if (!symbol) return
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setGen('')
    setGenState('loading')
    try {
      await streamResearch(symbol, (d) => setGen((p) => p + d), ac.signal)
      setGenState('idle')
      setGen('')
      qc.invalidateQueries({ queryKey: ['research', symbol] })
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setGen((e as Error).message)
      setGenState('error')
    }
  }

  if (!symbol) {
    return (
      <div className="research empty-stage">
        <div className="es-title">深度研究</div>
        <div className="es-sub faint">从左侧自选选一支标的，生成它的深度研究报告</div>
      </div>
    )
  }

  const streaming = genState === 'loading'
  const data = report.data

  return (
    <motion.div
      className="research"
      key={symbol}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="research-head">
        <div className="rh-id">
          <h2>{name || symbol}</h2>
          <span className="rh-sym">{symbol}</span>
          {data?.created_at && !streaming && (
            <span className="rh-when faint">{fmtWhen(data.created_at)} 生成</span>
          )}
        </div>
        <button className="btn btn-primary jsm" disabled={streaming} onClick={runGenerate}>
          {streaming ? '研究中…' : data ? '重新生成' : '生成深度研究'}
        </button>
      </div>

      {streaming || genState === 'error' ? (
        <div className={`report-card ${genState === 'error' ? 'err' : ''}`}>
          {genState === 'error' ? <p>{gen}</p> : <Report body={gen || '正在汇集行情 · 财务 · 新闻 · 申报…'} sources={[]} />}
        </div>
      ) : data ? (
        <div className="report-card">
          <Report body={data.body} sources={data.sources} />
        </div>
      ) : report.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">还没有 {name || symbol} 的研究报告</div>
          <div className="faint" style={{ marginTop: 6 }}>
            汇集行情、基本面、财务趋势、近期新闻与 SEC 申报，由长上下文模型综合
          </div>
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <ImportedReports symbol={symbol} />
      </div>
    </motion.div>
  )
}
