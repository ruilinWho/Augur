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
            <Markdown body={gen || '生成中…'} />
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
          <div className="ke-title">暂无研究报告</div>
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <ImportedReports symbol={symbol} />
      </div>

      {/* 常驻静态边界：决策级研究，但不执行交易；关键事实仍需回看来源。 */}
      <div className="disclaimer">
        决策级研究输出 · 可能滞后或有误 · 关键事实请回看来源核验 · Augur 不执行交易
      </div>
    </motion.div>
  )
}
