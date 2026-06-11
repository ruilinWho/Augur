import { useState } from 'react'
import Collapse from '../../components/Collapse'
import { useGenerateOpportunities, useOpportunities, type Opportunity } from '../../api'
import { RelatedChip } from './shared'

const CONF: Record<string, { label: string; cls: string }> = {
  high: { label: '高把握', cls: 'cf-high' },
  med: { label: '中', cls: 'cf-med' },
  low: { label: '低', cls: 'cf-low' },
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
            <RelatedChip key={i} r={r} />
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

export default function OpportunitiesPanel({
  date = null,
  showGenerate = true,
}: {
  date?: string | null
  showGenerate?: boolean
}) {
  const opps = useOpportunities(date)
  const gen = useGenerateOpportunities()
  const [open, setOpen] = useState(true)
  const list = opps.data?.opportunities ?? []

  return (
    <section className="opps">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>今日机会</h3>
        {showGenerate && (
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
        )}
      </div>
      <Collapse open={open}>
        {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}
        {gen.isPending ? (
          <div className="opp-empty faint">识别中…</div>
        ) : list.length ? (
          <>
            <div className="opp-list">
              {list.map((o, i) => (
                <OppCard key={o.title || `o${i}`} o={o} />
              ))}
            </div>
          </>
        ) : (
          <div className="opp-empty">
            <div className="oe-title">暂无机会</div>
          </div>
        )}
      </Collapse>
    </section>
  )
}
