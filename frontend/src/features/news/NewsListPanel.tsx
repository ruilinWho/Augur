import { motion } from 'motion/react'
import { useNewsReports, useRefreshNews } from '../../api'
import { useNews } from './store'

const EASE = [0.22, 1, 0.36, 1] as const
const fmtDate = (d: string) => {
  const [y, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日 ${y}`
}

export default function NewsListPanel() {
  const reports = useNewsReports()
  const refresh = useRefreshNews()
  const selectedDate = useNews((s) => s.selectedDate)
  const setSelectedDate = useNews((s) => s.setSelectedDate)
  const list = reports.data ?? []

  return (
    <aside className="panel">
      <div className="lbl">
        趋势日报
        <span className="act" onClick={() => refresh.mutate()}>
          {refresh.isPending ? '刷新中…' : '↻ 刷新信源'}
        </span>
      </div>
      {refresh.data && (
        <div className="refresh-note faint">
          +{refresh.data.inserted} 条新闻 · {refresh.data.sources_ok} 源就绪
          {refresh.data.sources_failed > 0 && ` · ${refresh.data.sources_failed} 源失败`}
        </div>
      )}

      <div className="report-list">
        {list.map((r, i) => {
          const active = selectedDate === r.report_date || (selectedDate === null && i === 0)
          return (
            <motion.div
              key={r.report_date}
              className={`report-row ${active ? 'active' : ''}`}
              onClick={() => setSelectedDate(i === 0 ? null : r.report_date)}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: Math.min(i * 0.04, 0.2), ease: EASE }}
            >
              <div className="rr-top">
                <span className="rr-date">{fmtDate(r.report_date)}</span>
                <span className="rr-count">{r.item_count} 条</span>
              </div>
              <div className="rr-preview">{r.preview.replace(/^#+\s*/, '').replace(/[#*]/g, '')}</div>
            </motion.div>
          )
        })}
        {reports.isLoading && <div className="report-row faint">加载日报…</div>}
        {!reports.isLoading && list.length === 0 && (
          <div className="faint" style={{ padding: '10px 2px', fontSize: '.82rem', lineHeight: 1.7 }}>
            还没有日报。先「↻ 刷新信源」抓取新闻，再到右侧「生成今日日报」。
          </div>
        )}
      </div>
    </aside>
  )
}
