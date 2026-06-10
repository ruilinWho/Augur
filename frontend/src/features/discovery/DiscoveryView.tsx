import { motion } from 'motion/react'
import {
  useDiscovery,
  useRefreshDiscovery,
  useSetCandidateStatus,
  type Candidate,
} from '../../api'
import { useUI } from '../../store'
import AddToWatchlist from '../watchlist/AddToWatchlist'
import { EASE } from '../../theme/motion'

const MARKET_LABEL: Record<string, string> = { US: '美股', HK: '港股', CN: 'A股', KR: '韩股' }

function CandidateCard({ c }: { c: Candidate }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  const setStatus = useSetCandidateStatus()
  const code = c.symbol.includes(':') ? c.symbol.split(':')[1] : c.symbol
  return (
    <div className="cand-card">
      <div className="cand-head">
        <div className="cand-id">
          <h3>{c.name || code}</h3>
          <span className="cand-sym">{code} · {MARKET_LABEL[c.market] ?? c.market}</span>
        </div>
        <div className="cand-metrics">
          <span className="cand-metric">
            <b>{c.mention_count}</b> 次提及
          </span>
          <span className="cand-metric">
            <b>{c.day_span}</b> 天出现
          </span>
        </div>
      </div>

      {c.evidence.length > 0 && (
        <div className="cand-ev">
          {c.evidence.slice(0, 4).map((e) => (
            <a key={e.news_id} className="cand-ev-row" href={e.url} target="_blank" rel="noreferrer">
              {e.date && <span className="cand-ev-date">{e.date.slice(5)}</span>}
              <span className="cand-ev-src">{e.source}</span>
              <span className="cand-ev-title">{e.title}</span>
            </a>
          ))}
        </div>
      )}

      <div className="cand-actions">
        <AddToWatchlist symbol={c.symbol} />
        <button className="ncta" onClick={() => select(c.symbol)} title="在「看」里查看 K 线">
          看
        </button>
        <button className="ncta" onClick={() => research(c.symbol)} title="生成深度研究">
          研
        </button>
        <button
          className="btn btn-ghost jsm cand-dismiss"
          onClick={() => setStatus.mutate({ symbol: c.symbol, status: 'dismissed' })}
          title="忽略此候选（不再出现）"
        >
          忽略
        </button>
      </div>
    </div>
  )
}

export default function DiscoveryView() {
  const list = useDiscovery('new')
  const refresh = useRefreshDiscovery()
  const items = list.data ?? []
  return (
    <motion.div
      className="discovery"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="disc-head">
        <div className="disc-id">
          <h2>寻</h2>
          {items.length > 0 && <span className="disc-n">{items.length} 个候选</span>}
        </div>
        <button className="btn btn-primary jsm" disabled={refresh.isPending} onClick={() => refresh.mutate()}>
          {refresh.isPending ? '重算中…' : '重算'}
        </button>
      </div>

      {list.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : items.length === 0 ? (
        <div className="know-empty">
          <div className="ke-title">暂无候选</div>
        </div>
      ) : (
        <div className="cand-list">
          {items.map((c) => (
            <CandidateCard key={c.symbol} c={c} />
          ))}
        </div>
      )}
    </motion.div>
  )
}
