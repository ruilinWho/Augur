import { useMemo } from 'react'
import { motion } from 'motion/react'
import { useNewsReports, useQuote, useRefreshNews, useSections, type Section } from '../../api'
import { useNews } from './store'
import { INFO_SECTIONS, PRIMARIES } from './consts'

const fmtDay = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}
function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 自选分区树 → 去重 symbol 列表（保持分区顺序）
function flattenSymbols(sections: Section[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  const walk = (s: Section) => {
    for (const it of s.items) if (!seen.has(it.symbol)) (seen.add(it.symbol), out.push(it.symbol))
    s.children.forEach(walk)
  }
  sections.forEach(walk)
  return out
}
const MKT_BADGE: Record<string, string> = { US: '美', HK: '港', CN: 'A', KR: '韩' }

// ── 个股二级：自选股列表 ──
function StockSubRow({ symbol, active, onClick }: { symbol: string; active: boolean; onClick: () => void }) {
  const q = useQuote(symbol)
  const [mkt, code] = symbol.split(':')
  return (
    <button className={`nsub-row ${active ? 'active' : ''}`} onClick={onClick}>
      <span className="nsub-main">{q.data?.name || code}</span>
      <span className="nsub-badge">{MKT_BADGE[mkt] ?? mkt}</span>
    </button>
  )
}

function StocksSub() {
  const sections = useSections('ALL')
  const stockSym = useNews((s) => s.stockSym)
  const setStockSym = useNews((s) => s.setStockSym)
  const syms = useMemo(() => flattenSymbols(sections.data ?? []), [sections.data])
  if (sections.isLoading) return <div className="nsub-row faint">加载…</div>
  if (!syms.length) return <div className="nsub-empty faint">暂无自选</div>
  return (
    <div className="nsub-list">
      {syms.map((sym) => (
        <StockSubRow key={sym} symbol={sym} active={stockSym === sym} onClick={() => setStockSym(sym)} />
      ))}
    </div>
  )
}

// ── 资讯二级：日期（今天置顶，再按已存日报的天）──
function DatesSub() {
  const reports = useNewsReports()
  const infoDate = useNews((s) => s.infoDate)
  const setInfoDate = useNews((s) => s.setInfoDate)
  const td = todayStr()
  const list = reports.data ?? []
  const days = list.some((r) => r.report_date === td)
    ? list.map((r) => ({ date: r.report_date, n: r.item_count }))
    : [{ date: td, n: 0 }, ...list.map((r) => ({ date: r.report_date, n: r.item_count }))]
  const cur = infoDate ?? td
  return (
    <div className="nsub-list">
      {days.map((r) => (
        <button
          key={r.date}
          className={`nsub-row ${cur === r.date ? 'active' : ''}`}
          onClick={() => setInfoDate(r.date === td ? null : r.date)}
        >
          <span className="nsub-main">{r.date === td ? '今天' : fmtDay(r.date)}</span>
          {r.n > 0 && <span className="nsub-n">{r.n}</span>}
        </button>
      ))}
      {reports.isLoading && <div className="nsub-row faint">加载…</div>}
    </div>
  )
}

// ── 资讯三级：总结 / 决策 / 各信源 lane ──
function SectionsSub() {
  const infoSection = useNews((s) => s.infoSection)
  const setInfoSection = useNews((s) => s.setInfoSection)
  return (
    <div className="nsub-list">
      {INFO_SECTIONS.map((sec) => (
        <button
          key={sec.id}
          className={`nsub-row ${infoSection === sec.id ? 'active' : ''}`}
          onClick={() => setInfoSection(sec.id)}
        >
          <span className="nsub-main">{sec.label}</span>
        </button>
      ))}
    </div>
  )
}

export default function NewsNav() {
  const primary = useNews((s) => s.primary)
  const setPrimary = useNews((s) => s.setPrimary)
  const navCollapsed = useNews((s) => s.navCollapsed)
  const toggleNav = useNews((s) => s.toggleNav)
  const refresh = useRefreshNews()

  return (
    <>
      <aside className="panel news-rail">
        <div className="nrail-items">
          {PRIMARIES.map((p) => (
            <button
              key={p.id}
              className={`nrail-item ${primary === p.id ? 'active' : ''}`}
              onClick={() => setPrimary(p.id)}
            >
              {primary === p.id && (
                <motion.span layoutId="nrailpill" className="nrail-pill" transition={{ type: 'spring', stiffness: 380, damping: 30 }} />
              )}
              <span className="nrail-label">{p.label}</span>
            </button>
          ))}
        </div>
        <button
          className="nrail-collapse"
          onClick={toggleNav}
          title={navCollapsed ? '展开 日期 / 板块' : '收起 日期 / 板块'}
        >
          {navCollapsed ? '›' : '‹'}
        </button>
        <button className="nrail-refresh" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          {refresh.isPending ? '刷新中…' : '↻ 刷新'}
        </button>
        {refresh.data && (
          <div className="nrail-note faint">
            +{refresh.data.inserted} · {refresh.data.sources_ok} 源
          </div>
        )}
      </aside>

      {!navCollapsed && primary === 'stocks' && (
        <aside className="panel news-sub">
          <div className="lbl">标的</div>
          <StocksSub />
        </aside>
      )}
      {!navCollapsed && primary === 'info' && (
        <>
          <aside className="panel news-sub">
            <div className="lbl">日期</div>
            <DatesSub />
          </aside>
          <aside className="panel news-sub news-sub3">
            <div className="lbl">板块</div>
            <SectionsSub />
          </aside>
        </>
      )}
    </>
  )
}
