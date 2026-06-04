import { useRef, useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { streamResearch, useQuote, useResearchReport } from '../../api'
import { useUI } from '../../store'
import Markdown from '../../components/Markdown'
import { EASE } from '../../theme/motion'
import ImportedReports from './ImportedReports'

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
          {genState === 'error' ? (
            <p>{gen}</p>
          ) : (
            <Markdown body={gen || '正在汇集行情 · 财务 · 新闻 · 申报…'} />
          )}
        </div>
      ) : data ? (
        <div className="report-card">
          <Markdown body={data.body} sources={data.sources} />
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

      {/* 常驻静态免责（§11 不可妥协）：无论模型是否自觉输出、无论生成/错误/导入态，护栏恒在 */}
      <div className="disclaimer">
        本页为 AI / 他人研究综合，可能滞后或有误，仅供研究参考、不构成投资建议。
      </div>
    </motion.div>
  )
}
