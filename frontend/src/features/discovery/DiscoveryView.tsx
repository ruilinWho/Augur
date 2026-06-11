import { useState } from 'react'
import { motion } from 'motion/react'
import {
  useDiscovery,
  useDiscoveryMarkets,
  useDiscoverySignals,
  useDiscoveryThemes,
  useMuteMarket,
  useMuteTheme,
  useRefreshDiscovery,
  useSetCandidateStatus,
  type Candidate,
  type DiscoverySignal,
} from '../../api'
import { useUI } from '../../store'
import AddToWatchlist from '../watchlist/AddToWatchlist'
import { EASE } from '../../theme/motion'

const MARKET_LABEL: Record<string, string> = { US: '美股', HK: '港股', CN: 'A股', KR: '韩股' }
const THEME_LABEL: Record<string, string> = {
  ai: '大模型',
  chips: '芯片',
  robotics: '机器人',
  space: '航天',
  macro: '宏观',
  markets: '行情',
  tech: '科技',
  world: '国际',
  crypto: '加密',
}
const themeLabel = (t: string) => THEME_LABEL[t] ?? t

function CandidateCard({ c, signal }: { c: Candidate; signal?: DiscoverySignal }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  const setStatus = useSetCandidateStatus()
  const mute = useMuteTheme()
  const dismissed = c.status === 'dismissed'
  const code = c.symbol.includes(':') ? c.symbol.split(':')[1] : c.symbol
  return (
    <div className="cand-card">
      <div className="cand-top">
        <div className="cand-id">
          <h3>{c.name || code}</h3>
          <span className="cand-sym">{code}</span>
          <span className="cand-mkt">{MARKET_LABEL[c.market] ?? c.market}</span>
          {c.theme && <span className="cand-theme">{themeLabel(c.theme)}</span>}
        </div>
        <div className="cand-metrics">
          {signal && (
            <span className="cand-hot" title="近月明显上涨且放量，可能是关键信号">
              近月 ↑{signal.ret_pct}% · 放量 {signal.vol_ratio}×
            </span>
          )}
          <span className="cand-metric">
            <b>{c.mention_count}</b> 次
          </span>
          <span className="cand-metric">
            <b>{c.day_span}</b> 天
          </span>
        </div>
      </div>

      {c.reason && <p className="cand-reason">{c.reason}</p>}

      {c.evidence.length > 0 && (
        <div className="cand-ev">
          {c.evidence.map((e) => (
            <a key={e.news_id} className="cand-ev-row" href={e.url} target="_blank" rel="noreferrer">
              <span className="cand-ev-date">{e.date ? e.date.slice(5) : '—'}</span>
              <span className="cand-ev-src">{e.source}</span>
              <span className="cand-ev-title">{e.title}</span>
            </a>
          ))}
        </div>
      )}

      <div className="cand-actions">
        {dismissed ? (
          <button className="cand-btn" onClick={() => setStatus.mutate({ symbol: c.symbol, status: 'new' })}>
            恢复
          </button>
        ) : (
          <>
            <AddToWatchlist symbol={c.symbol} />
            <button className="cand-btn" onClick={() => select(c.symbol)} title="在「看」里查看 K 线">
              看
            </button>
            <button className="cand-btn" onClick={() => research(c.symbol)} title="生成深度研究">
              研
            </button>
            <div className="cand-actions-r">
              {c.theme && (
                <button
                  className="cand-btn ghost"
                  onClick={() => mute.mutate({ theme: c.theme, muted: true })}
                  title={`不再看「${themeLabel(c.theme)}」这类`}
                >
                  屏蔽「{themeLabel(c.theme)}」
                </button>
              )}
              <button
                className="cand-btn ghost"
                onClick={() => setStatus.mutate({ symbol: c.symbol, status: 'dismissed' })}
                title="忽略此候选（移到已忽略，可恢复）"
              >
                忽略
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// 「偏好」面板：屏蔽不想看的市场/主题——整类不再出现，可随时恢复。
function PrefsPanel({ onClose }: { onClose: () => void }) {
  const themes = useDiscoveryThemes()
  const markets = useDiscoveryMarkets()
  const muteTheme = useMuteTheme()
  const muteMarket = useMuteMarket()
  const themeItems = themes.data ?? []
  const marketItems = markets.data ?? []
  return (
    <div className="disc-prefs">
      <div className="disc-prefs-head">
        <span>偏好 · 点亮=在看，灰=已屏蔽</span>
        <button className="cand-btn ghost" onClick={onClose}>
          收起
        </button>
      </div>
      <div className="disc-prefs-grp">
        <span className="disc-prefs-lbl">市场</span>
        <div className="disc-prefs-chips">
          {marketItems.map((m) => (
            <button
              key={m.market}
              className={`disc-theme-chip ${m.muted ? 'muted' : ''}`}
              onClick={() => muteMarket.mutate({ market: m.market, muted: !m.muted })}
              title={m.muted ? '点击恢复' : `不再看「${m.label || m.market}」`}
            >
              {m.label || m.market}
              {m.count > 0 && <i>{m.count}</i>}
            </button>
          ))}
        </div>
      </div>
      <div className="disc-prefs-grp">
        <span className="disc-prefs-lbl">主题</span>
        {themeItems.length === 0 ? (
          <div className="disc-prefs-empty faint">暂无主题</div>
        ) : (
          <div className="disc-prefs-chips">
            {themeItems.map((t) => (
              <button
                key={t.theme}
                className={`disc-theme-chip ${t.muted ? 'muted' : ''}`}
                onClick={() => muteTheme.mutate({ theme: t.theme, muted: !t.muted })}
                title={t.muted ? '点击恢复' : '点击屏蔽这一类'}
              >
                {themeLabel(t.theme)}
                {t.count > 0 && <i>{t.count}</i>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function DiscoveryView() {
  const [tab, setTab] = useState<'new' | 'dismissed'>('new')
  const [prefsOpen, setPrefsOpen] = useState(false)
  const list = useDiscovery(tab)
  const signals = useDiscoverySignals()
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
        <h2>寻</h2>
        <div className="seg disc-seg">
          <button aria-pressed={tab === 'new'} onClick={() => setTab('new')}>
            关注中
          </button>
          <button aria-pressed={tab === 'dismissed'} onClick={() => setTab('dismissed')}>
            已忽略
          </button>
        </div>
        <button
          className={`cand-btn ghost ${prefsOpen ? 'on' : ''}`}
          onClick={() => setPrefsOpen((v) => !v)}
        >
          偏好
        </button>
        <button className="btn btn-primary jsm disc-refresh" disabled={refresh.isPending} onClick={() => refresh.mutate()}>
          {refresh.isPending ? '重算中…' : '重算'}
        </button>
      </div>

      {prefsOpen && <PrefsPanel onClose={() => setPrefsOpen(false)} />}

      {list.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : items.length === 0 ? (
        <div className="know-empty">
          <div className="ke-title">{tab === 'new' ? '暂无候选' : '没有已忽略的'}</div>
        </div>
      ) : (
        <div className="cand-list">
          {items.map((c) => (
            <CandidateCard key={c.symbol} c={c} signal={signals.data?.[c.symbol]} />
          ))}
        </div>
      )}
    </motion.div>
  )
}
