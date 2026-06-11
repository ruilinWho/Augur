import type { NewsReport, ReportSection } from '../../api'
import { CitedList, RelatedChip } from './shared'

// 重要性 → 徽章（陶土系，非常重要最重，向下递减）。与后端 _IMP_ORDER（critical/high/med/low）对齐。
const IMPORTANCE: Record<string, { label: string; cls: string }> = {
  critical: { label: '非常重要', cls: 'imp-critical' },
  high: { label: '重要', cls: 'imp-high' },
  med: { label: '留意', cls: 'imp-med' },
  low: { label: '次要', cls: 'imp-low' },
}

// 一个主题卡：重要性徽章 + 加粗下划线小标题 + 为什么重要 + 分点（可点引用）+ 关联标的「看/研」。
function SectionCard({ s }: { s: ReportSection }) {
  const imp = IMPORTANCE[s.importance] ?? IMPORTANCE.med
  return (
    <article className="rsec">
      <div className="rsec-head">
        <span className={`rsec-imp ${imp.cls}`}>{imp.label}</span>
        <h4 className="rsec-headline">{s.headline}</h4>
      </div>
      {s.why && <p className="rsec-why">{s.why}</p>}
      {s.points.length > 0 && <CitedList items={s.points} />}
      {s.related.length > 0 && (
        <div className="rsec-syms">
          {s.related.map((r, i) => (
            <RelatedChip key={i} r={r} />
          ))}
        </div>
      )}
    </article>
  )
}

// 结构化综合日报：总判断 + 主题卡 + 风险/反证 + 明天继续看。分层分点、个股可点——取代旧的长文。
export default function DigestReport({ data }: { data: NewsReport }) {
  return (
    <div className="rreport">
      {data.verdict && (
        <div className="rverdict">
          <span className="rverdict-l">总判断</span>
          <p>{data.verdict}</p>
        </div>
      )}
      {data.sections.map((s, i) => (
        <SectionCard key={s.headline || `s${i}`} s={s} />
      ))}
      {data.risks.length > 0 && (
        <div className="rblock rblock-risk">
          <h4 className="rblock-l">风险 / 反证</h4>
          <CitedList items={data.risks} />
        </div>
      )}
      {data.watch.length > 0 && (
        <div className="rblock rblock-watch">
          <h4 className="rblock-l">明天继续看</h4>
          <CitedList items={data.watch} />
        </div>
      )}
    </div>
  )
}
