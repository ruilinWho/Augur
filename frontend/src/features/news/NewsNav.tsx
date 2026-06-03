import { motion } from 'motion/react'
import { useNewsReports, useRefreshNews } from '../../api'
import { useNews } from './store'
import { PRIMARIES, THEMES, TW_CATS } from './consts'

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

const SUB_TITLE: Record<string, string> = { digest: '按天', news: '主题', twitter: '账号' }

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
          {primary === 'digest' && <DigestSub />}
          {primary === 'news' && <KeySub opts={THEMES} />}
          {primary === 'twitter' && <KeySub opts={TW_CATS} />}
        </aside>
      )}
    </>
  )
}
