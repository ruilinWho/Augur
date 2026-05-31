import { useUI } from '../../store'

export default function Placeholder({ pillar }: { pillar: '研' | '知' }) {
  const symbol = useUI((s) => s.selectedSymbol)
  const isResearch = pillar === '研'
  const title = isResearch ? '深度研究' : '趋势日报'
  const desc = isResearch
    ? '选中一支标的后，这里用 LLM + Deep Research 生成结构化、带引用、暴露不确定性的深度分析。'
    : '每天聚合全球顶级信源，由 LLM 去重、聚类、蒸馏成趋势日报，让你在天级别与世界信息流同步。'
  return (
    <div className="placeholder">
      <div className="eyebrow">{pillar} · {title}</div>
      <h2 style={{ marginTop: 8 }}>{title}</h2>
      <p className="lead">{desc}</p>
      {isResearch && <p className="faint">当前选中：{symbol ?? '（未选标的）'}</p>}
      <div className="hedge">
        M1 先打通「看」。{title}将在 {isResearch ? 'M2' : 'M3'} 接入已就绪的 LLM 网关。
      </div>
    </div>
  )
}
