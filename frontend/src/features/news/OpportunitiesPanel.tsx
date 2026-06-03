import { useState } from 'react'
import Collapse from '../../components/Collapse'
import { useUI } from '../../store'
import {
  useGenerateOpportunities,
  useOpportunities,
  type Opportunity,
  type RelatedSymbol,
} from '../../api'

const CONF: Record<string, { label: string; cls: string }> = {
  high: { label: '高把握', cls: 'cf-high' },
  med: { label: '中', cls: 'cf-med' },
  low: { label: '低', cls: 'cf-low' },
}

// 关联标的 chip：已解析→拆分胶囊「名字→看 · 研→深度研究」；已关注→陶土描边+圆点；未解析→灰
function Chip({ r }: { r: RelatedSymbol }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  if (!r.resolved || !r.symbol) {
    return (
      <span className="opp-chip unresolved" title="未能解析到具体上市公司代码">
        {r.name}
      </span>
    )
  }
  const sym = r.symbol
  return (
    <span
      className={`opp-chip2 ${r.in_watchlist ? 'watched' : ''}`}
      title={r.in_watchlist ? `已关注 · ${r.sections.join(' / ')}` : sym}
    >
      <button className="oc-nm" onClick={() => select(sym)} title="在「看」里查看 K 线">
        {r.in_watchlist && <span className="wdot" />}
        {r.name}
      </button>
      <button className="oc-go" onClick={() => research(sym)} title="深度研究这只股">
        研
      </button>
    </span>
  )
}

function OppCard({ o }: { o: Opportunity }) {
  const [open, setOpen] = useState(false)
  const conf = CONF[o.confidence] ?? CONF.low
  return (
    <article className="opp-card">
      <header className="opp-head" onClick={() => setOpen((v) => !v)} role="button">
        <span className="opp-title">{o.title}</span>
        {o.theme && <span className="opp-theme">{o.theme}</span>}
        <span className={`opp-conf ${conf.cls}`}>{conf.label}</span>
      </header>
      {o.related.length > 0 && (
        <div className="opp-related">
          {o.related.map((r, i) => (
            <Chip key={i} r={r} />
          ))}
        </div>
      )}
      <Collapse open={open}>
        <div className="opp-body">
          <p className="opp-thesis">{o.thesis}</p>
          {o.caveats && <p className="opp-caveats">不确定性：{o.caveats}</p>}
          {o.evidence.length > 0 && (
            <div className="opp-ev">
              <span className="opp-ev-lbl">依据</span>
              {o.evidence.map((e, i) =>
                e.url ? (
                  <a key={i} className="opp-ev-item" href={e.url} target="_blank" rel="noreferrer">
                    {e.source} · {e.title}
                  </a>
                ) : (
                  <span key={i} className="opp-ev-item">
                    {e.source} · {e.title}
                  </span>
                ),
              )}
            </div>
          )}
        </div>
      </Collapse>
    </article>
  )
}

export default function OpportunitiesPanel({ date = null }: { date?: string | null }) {
  const opps = useOpportunities(date)
  const gen = useGenerateOpportunities()
  const [open, setOpen] = useState(true)
  const list = opps.data?.opportunities ?? []

  return (
    <section className="opps">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>今日机会</h3>
        <button
          className="btn btn-primary jsm sec-gen"
          disabled={gen.isPending}
          onClick={(e) => {
            e.stopPropagation()
            setOpen(true)
            gen.mutate(date)
          }}
        >
          {gen.isPending ? '识别中…' : list.length ? '重新识别' : '识别机会'}
        </button>
      </div>
      <Collapse open={open}>
        {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}
        {gen.isPending ? (
          <div className="opp-empty faint">正在从今日新闻中识别可研究的方向…（约 20–40 秒）</div>
        ) : list.length ? (
          <>
            <div className="opp-list">
              {list.map((o, i) => (
                <OppCard key={i} o={o} />
              ))}
            </div>
          </>
        ) : (
          <div className="opp-empty">
            <div className="oe-title">还没有今日机会</div>
          </div>
        )}
      </Collapse>
    </section>
  )
}
