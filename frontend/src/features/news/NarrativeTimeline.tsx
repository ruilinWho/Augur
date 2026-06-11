import type { StockNarrative } from '../../api'

// 重要度标签（叙事时间线 + 要点聚类共用，单一真相）
export const IMP: Record<string, { label: string; cls: string }> = {
  critical: { label: '非常重要', cls: 'imp-critical' },
  high: { label: '重要', cls: 'imp-high' },
  med: { label: '一般', cls: 'imp-med' },
  low: { label: '次要', cls: 'imp-low' },
}

// 只读叙事正文（当前主线 + 带引用的时间线）——「知·个股」与「看·个股」复用。
// hideSummary：在「看·相关资讯」里 近况 子卡片已有摘要，时间线只留事件，避免两段摘要重复。
export function NarrativeBody({
  data,
  hideSummary = false,
  hideRefs = false,
}: {
  data: StockNarrative
  hideSummary?: boolean
  hideRefs?: boolean
}) {
  return (
    <>
      {!hideSummary && data.summary && <div className="narr-summary">{data.summary}</div>}
      <div className="narr-timeline">
        {data.timeline.map((ev, i) => {
          const imp = IMP[ev.importance] ?? IMP.med
          return (
            <div className="narr-ev" key={`ev-${i}`}>
              <div className="narr-ev-head">
                <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>
                {ev.date && <span className="narr-date">{ev.date}</span>}
                <span className="narr-ev-title">{ev.title}</span>
              </div>
              {!hideRefs && ev.refs.length > 0 && (
                <div className="narr-refs">
                  {ev.refs.map((r, j) => (
                    <a key={j} className="narr-ref" href={r.url} target="_blank" rel="noreferrer">
                      <span className="narr-ref-src">{r.source}</span>
                      <span className="narr-ref-title">{r.title}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
