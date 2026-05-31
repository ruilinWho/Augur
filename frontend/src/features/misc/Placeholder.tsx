import { useUI } from '../../store'

export default function Placeholder({ pillar }: { pillar: '研' | '知' }) {
  const symbol = useUI((s) => s.selectedSymbol)
  const isResearch = pillar === '研'
  return (
    <div className="placeholder">
      <div className="eyebrow">{pillar} · {isResearch ? 'Deep Research' : 'Daily Briefing'}</div>
      <h1 style={{ marginTop: 10 }}>{isResearch ? '深度研究' : '趋势日报'}</h1>
      <p className="lead">
        {isResearch
          ? '选中一支标的，用 LLM + Deep Research 生成结构化、带引用、暴露不确定性的深度分析。'
          : '每天聚合全球顶级信源，由 LLM 去重、聚类、蒸馏成趋势日报，让你在天级别与世界信息流同步。'}
      </p>

      {isResearch && (
        <div className="research-cta">
          <div className="muted" style={{ fontSize: '.82rem' }}>当前标的</div>
          <div className="mono" style={{ fontSize: '1.1rem', marginTop: 3, color: 'var(--text)' }}>
            {symbol ?? '— 未选标的 —'}
          </div>
          <button className="btn btn-primary" style={{ marginTop: 14 }} disabled>
            开始深度研究
          </button>
        </div>
      )}

      <div className="hedge">
        M1 先打通「看」。{isResearch ? '深度研究' : '趋势日报'}将在 {isResearch ? 'M2' : 'M3'} 接入已就绪的 LLM 网关。
      </div>
    </div>
  )
}
