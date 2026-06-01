import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  streamChat,
  useFinancials,
  useFundamentals,
  useQuote,
  type FinPeriod,
} from '../../api'
import { fmtMoney, fmtNum, fmtPct, fmtPctPlain } from '../../format'

const EASE = [0.22, 1, 0.36, 1] as const

type RowDef = {
  key: Exclude<keyof FinPeriod, 'period'> // 仅数值列
  label: string
  kind: 'money' | 'pct' | 'num'
  growth?: boolean // 按正负着色
  extra?: boolean // 默认折叠
}
const ROWS: RowDef[] = [
  { key: 'revenue', label: '营业收入', kind: 'money' },
  { key: 'revenue_growth', label: '营收增长', kind: 'pct', growth: true },
  { key: 'net_income', label: '净利润', kind: 'money' },
  { key: 'net_margin', label: '净利润率', kind: 'pct' },
  { key: 'eps', label: '每股收益', kind: 'num', extra: true },
  { key: 'eps_growth', label: 'EPS 增长', kind: 'pct', growth: true, extra: true },
  { key: 'fcf', label: '自由现金流', kind: 'money', extra: true },
]

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

function cellText(p: FinPeriod, row: RowDef, cur: string): string {
  const v = p[row.key]
  if (row.kind === 'money') return fmtMoney(v, cur)
  if (row.kind === 'pct') return row.growth ? fmtPct(v) : fmtPctPlain(v) // 增长率带符号，比率不带
  return fmtNum(v)
}

export default function FinancialsPanel({ symbol }: { symbol: string }) {
  const fin = useFinancials(symbol)
  const fund = useFundamentals(symbol)
  const quote = useQuote(symbol)
  const [open, setOpen] = useState(true)
  const [showExtra, setShowExtra] = useState(false)
  const [ai, setAi] = useState('')
  const [aiState, setAiState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')

  useEffect(() => {
    setAi('')
    setAiState('idle')
  }, [symbol])

  const cur = fin.data?.currency || fund.data?.currency || ''
  const periods = fin.data?.periods ?? []
  const rows = showExtra ? ROWS : ROWS.filter((r) => !r.extra)

  const runAI = async () => {
    setAi('')
    setAiState('loading')
    const name = quote.data?.name || symbol
    const trend = periods
      .slice(0, 5)
      .map(
        (p) =>
          `${p.period} 营收${fmtMoney(p.revenue, cur)}(同比${fmtPct(p.revenue_growth)}) ` +
          `净利${fmtMoney(p.net_income, cur)} 净利率${fmtPct(p.net_margin)}`,
      )
      .join('；')
    const prompt =
      `你是严谨、克制的投研助手。基于 ${name}（${symbol}）近几年财报趋势：\n${trend || '（暂无）'}\n` +
      `当前市值 ${fmtMoney(fund.data?.market_cap, cur)}、市盈率 ${fund.data?.pe != null ? fund.data.pe.toFixed(1) : '—'}。\n` +
      `分别用 1-2 句点出：营收/利润趋势、盈利能力变化、估值水平、主要风险。暴露不确定性，不构成投资建议。` +
      `纯文本中文，不要 markdown 符号，180 字内。`
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
        {fin.data?.links?.length ? (
          <span className="fin-links">
            {fin.data.links.map((l) => (
              <a
                key={l.url}
                href={l.url}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                {l.label} ↗
              </a>
            ))}
          </span>
        ) : null}
      </div>
      <Collapse open={open}>
        {periods.length > 0 ? (
          <>
            <div className="fin-table-wrap">
              <table className="fin-table">
                <thead>
                  <tr>
                    <th className="rlabel" />
                    {periods.map((p) => (
                      <th key={p.period}>{p.period}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key}>
                      <td className="rlabel">{row.label}</td>
                      {periods.map((p) => {
                        const cls = row.growth && p[row.key] != null ? (p[row.key]! >= 0 ? 'up' : 'down') : ''
                        return (
                          <td key={p.period} className={`mono ${cls}`}>
                            {cellText(p, row, cur)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="fin-actions">
              <button className="btn-ghost more-btn" onClick={() => setShowExtra((s) => !s)}>
                {showExtra ? '收起 ▴' : '更多指标 ▾'}
              </button>
              <button
                className="btn ai-btn"
                disabled={aiState === 'loading'}
                onClick={runAI}
              >
                {aiState === 'loading' ? '解读中…' : '✨ AI 解读'}
              </button>
            </div>
          </>
        ) : (
          <div className="fin-empty">{fin.isLoading ? '加载财报…' : '暂无财报数据'}</div>
        )}
        {ai && <div className={`ai-out ${aiState === 'error' ? 'err' : ''}`}>{ai}</div>}
      </Collapse>
    </section>
  )
}
