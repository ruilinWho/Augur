import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { streamChat, useFundamentals, useQuote } from '../../api'

const EASE = [0.22, 1, 0.36, 1] as const
const CUR: Record<string, string> = { USD: '$', HKD: 'HK$', CNY: '¥', KRW: '₩' }

// 本币原值 → 亿/万亿（带币种符号；缺失为「—」）
function fmtMoney(v: number | null | undefined, cur: string): string {
  if (v == null) return '—'
  const s = CUR[cur] ?? ''
  const neg = v < 0 ? '-' : ''
  const a = Math.abs(v)
  if (a >= 1e12) return `${neg}${s}${(a / 1e12).toFixed(2)} 万亿`
  if (a >= 1e8) return `${neg}${s}${(a / 1e8).toFixed(a / 1e8 >= 100 ? 0 : 1)} 亿`
  if (a >= 1e4) return `${neg}${s}${(a / 1e4).toFixed(1)} 万`
  return `${neg}${s}${a.toFixed(0)}`
}

function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: EASE }}
          style={{ overflow: 'hidden' }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="m-label">{label}</div>
      <div className="m-value mono">{value}</div>
    </div>
  )
}

export default function FinancialsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading } = useFundamentals(symbol)
  const quote = useQuote(symbol)
  const [open, setOpen] = useState(true)
  const [ai, setAi] = useState('')
  const [aiState, setAiState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')

  // 切标的时清空上一只的 AI 解读
  useEffect(() => {
    setAi('')
    setAiState('idle')
  }, [symbol])

  const cur = data?.currency ?? ''

  const runAI = async () => {
    setAi('')
    setAiState('loading')
    const name = quote.data?.name || symbol
    const prompt =
      `你是严谨、克制的投研助手。基于下列数据，简要分析 ${name}（${symbol}）的财务与估值。\n` +
      `市值 ${fmtMoney(data?.market_cap, cur)}；营收(TTM) ${fmtMoney(data?.revenue, cur)}；` +
      `净利润 ${fmtMoney(data?.net_income, cur)}；市盈率 ${data?.pe != null ? data.pe.toFixed(1) : '—'}；` +
      `最新价 ${quote.data?.price ?? '—'}。\n` +
      `分别用 1-2 句点出：盈利能力、估值高低、增长与主要风险。暴露不确定性，不构成投资建议。` +
      `用纯文本中文，不要 markdown 符号（如 ** 或 #），180 字内。`
    try {
      await streamChat([{ role: 'user', content: prompt }], 'deep_research', (d) =>
        setAi((p) => p + d),
      )
      setAiState('done')
    } catch (e) {
      setAi((e as Error).message)
      setAiState('error')
    }
  }

  return (
    <section className="financials">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <span className="chev">{open ? '▾' : '▸'}</span>
        <h3>财报分析</h3>
      </div>
      <Collapse open={open}>
        <div className="metrics">
          <Metric label="市值" value={isLoading ? '…' : fmtMoney(data?.market_cap, cur)} />
          <Metric label="营收 TTM" value={isLoading ? '…' : fmtMoney(data?.revenue, cur)} />
          <Metric label="净利润" value={isLoading ? '…' : fmtMoney(data?.net_income, cur)} />
          <Metric
            label="市盈率 P/E"
            value={isLoading ? '…' : data?.pe != null ? data.pe.toFixed(1) : '—'}
          />
        </div>
        <div className="ai-block">
          <button className="btn ai-btn" disabled={aiState === 'loading' || isLoading} onClick={runAI}>
            {aiState === 'loading' ? '解读中…' : '✨ AI 解读'}
          </button>
          {ai && <div className={`ai-out ${aiState === 'error' ? 'err' : ''}`}>{ai}</div>}
        </div>
      </Collapse>
    </section>
  )
}
