import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useFinancials, useFundamentals, type FinPeriod } from '../../api'
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
  { key: 'revenue_growth', label: '营收同比', kind: 'pct', growth: true },
  { key: 'net_income', label: '净利润', kind: 'money' },
  { key: 'net_margin', label: '净利润率', kind: 'pct' },
  { key: 'eps', label: '每股收益', kind: 'num', extra: true },
  { key: 'eps_growth', label: 'EPS 同比', kind: 'pct', growth: true, extra: true },
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
  const [period, setPeriod] = useState<'quarter' | 'annual'>('quarter')
  const fin = useFinancials(symbol, period)
  const fund = useFundamentals(symbol)
  const [open, setOpen] = useState(true)
  const [showExtra, setShowExtra] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const cur = fin.data?.currency || fund.data?.currency || ''
  // 后端最新在前；翻转 → 最新在右（最近一期贴右边缘）。
  const cols = [...(fin.data?.periods ?? [])].reverse()
  const rows = showExtra ? ROWS : ROWS.filter((r) => !r.extra)

  // 数据/周期变化后，默认滚到最右（露出最新几期）。
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollLeft = el.scrollWidth
  }, [cols.length, period])

  return (
    <section className="financials">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <span className="chev">{open ? '▾' : '▸'}</span>
        <h3>财报分析</h3>
        <div className="fin-toggle" onClick={(e) => e.stopPropagation()}>
          <button className={period === 'quarter' ? 'on' : ''} onClick={() => setPeriod('quarter')}>
            季度
          </button>
          <button className={period === 'annual' ? 'on' : ''} onClick={() => setPeriod('annual')}>
            年度
          </button>
        </div>
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
        {cols.length > 0 ? (
          <>
            <div className="fin-table-wrap" ref={scrollRef}>
              <table className="fin-table">
                <thead>
                  <tr>
                    <th className="rlabel" />
                    {cols.map((p) => (
                      <th key={p.period}>{p.period}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key}>
                      <td className="rlabel">{row.label}</td>
                      {cols.map((p) => {
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
            </div>
          </>
        ) : (
          <div className="fin-empty">{fin.isLoading ? '加载财报…' : '暂无财报数据'}</div>
        )}
      </Collapse>
    </section>
  )
}
