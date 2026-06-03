import { useMemo } from 'react'
import { motion } from 'motion/react'
import { useNewsReports, useQuote, useRefreshNews, useSections, type Section } from '../../api'
import { useNews } from './store'
import { PRIMARIES, THEMES, TW_CATS } from './consts'

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

const fmtDay = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}

// 列2 · 日报按天
function DigestSub() {
  const reports = useNewsReports()
  const secondary = useNews((s) => s.secondary)
  const setSecondary = useNews((s) => s.setSecondary)
  const list = reports.data ?? []
  return (
    <div className="nsub-list">
      {list.map((r, i) => {
        const active = secondary === r.report_date || (secondary === null && i === 0)
        return (
          <button
            key={r.report_date}
            className={`nsub-row ${active ? 'active' : ''}`}
            onClick={() => setSecondary(i === 0 ? null : r.report_date)}
          >
            <span className="nsub-main">{fmtDay(r.report_date)}</span>
            <span className="nsub-n">{r.item_count}</span>
          </button>
        )
      })}
      {reports.isLoading && <div className="nsub-row faint">加载…</div>}
      {!reports.isLoading && !list.length && <div className="nsub-empty faint">还没有日报</div>}
    </div>
  )
}

// 列2 · 简单 key 列表（新闻主题 / 推特账号分类）
function KeySub({ opts }: { opts: { key: string; label: string }[] }) {
  const secondary = useNews((s) => s.secondary)
  const setSecondary = useNews((s) => s.setSecondary)
  const cur = secondary ?? ''
  return (
    <div className="nsub-list">
      {opts.map((o) => (
        <button
          key={o.key}
          className={`nsub-row ${cur === o.key ? 'active' : ''}`}
          onClick={() => setSecondary(o.key || null)}
        >
          <span className="nsub-main">{o.label}</span>
        </button>
      ))}
    </div>
  )
}

// 列2 · 个股（自选股列表，选中→主舞台看叙事）
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
  const secondary = useNews((s) => s.secondary)
  const setSecondary = useNews((s) => s.setSecondary)
  const syms = useMemo(() => flattenSymbols(sections.data ?? []), [sections.data])
  if (sections.isLoading) return <div className="nsub-row faint">加载…</div>
  if (!syms.length) return <div className="nsub-empty faint">先在「看」里自选标的</div>
  return (
    <div className="nsub-list">
      {syms.map((sym) => (
        <StockSubRow
          key={sym}
          symbol={sym}
          active={secondary === sym}
          onClick={() => setSecondary(sym)}
        />
      ))}
    </div>
  )
}

const SUB_TITLE: Record<string, string> = {
  stocks: '标的',
  digest: '按天',
  news: '主题',
  twitter: '账号',
}

export default function NewsNav() {
  const primary = useNews((s) => s.primary)
  const setPrimary = useNews((s) => s.setPrimary)
  const refresh = useRefreshNews()
  const cfg = PRIMARIES.find((p) => p.id === primary)
  const hasSub = cfg?.hasSub ?? false

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
        <button className="nrail-refresh" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          {refresh.isPending ? '刷新中…' : '↻ 刷新'}
        </button>
        {refresh.data && (
          <div className="nrail-note faint">
            +{refresh.data.inserted} · {refresh.data.sources_ok} 源
          </div>
        )}
      </aside>

      {hasSub && (
        <aside className="panel news-sub">
          <div className="lbl">{SUB_TITLE[primary] ?? ''}</div>
          {primary === 'stocks' && <StocksSub />}
          {primary === 'digest' && <DigestSub />}
          {primary === 'news' && <KeySub opts={THEMES} />}
          {primary === 'twitter' && <KeySub opts={TW_CATS} />}
        </aside>
      )}
    </>
  )
}
