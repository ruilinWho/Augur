import { useState } from 'react'
import {
  useAddStockSource,
  useDeleteStockSource,
  useDiscoverSources,
  useStockSources,
  useToggleStockSource,
  type StockSource,
} from '../../api'

// 信源类别：展示名 + 顺序
const KINDS: { key: string; label: string }[] = [
  { key: 'official', label: '官网' },
  { key: 'ir', label: 'IR' },
  { key: 'official_x', label: '官方X' },
  { key: 'influencer_x', label: '大V' },
  { key: 'reddit', label: 'Reddit' },
  { key: 'forum', label: '论坛' },
  { key: 'fin_site', label: '财经站' },
]
const kindLabel = (k: string) => KINDS.find((x) => x.key === k)?.label ?? k

// ref → 可点 href（URL 原样；@handle→x.com；r/sub→reddit）
function href(ref: string): string | null {
  const r = ref.trim()
  if (!r) return null
  if (/^https?:\/\//i.test(r)) return r
  if (r.startsWith('@')) return `https://x.com/${r.slice(1)}`
  if (/^r\//i.test(r)) return `https://reddit.com/${r}`
  return null
}

function SourceRow({ s }: { s: StockSource }) {
  const toggle = useToggleStockSource()
  const del = useDeleteStockSource()
  const url = href(s.ref)
  return (
    <div className={`ssrc-row ${s.enabled ? 'on' : ''}`}>
      <button
        className={`ssrc-toggle ${s.enabled ? 'on' : ''}`}
        title={s.enabled ? '已启用 · 点击停用' : '待确认 · 点击启用'}
        onClick={() => toggle.mutate({ id: s.id, symbol: s.symbol, enabled: !s.enabled })}
      >
        <span className="ssrc-knob" />
      </button>
      <span className="ssrc-kind">{kindLabel(s.kind)}</span>
      <div className="ssrc-main">
        <div className="ssrc-name">{s.name || s.ref}</div>
        {s.note && <div className="ssrc-note">{s.note}</div>}
      </div>
      {url ? (
        <a className="ssrc-ref" href={url} target="_blank" rel="noreferrer" title={s.ref}>
          {s.ref}
        </a>
      ) : (
        s.ref && <span className="ssrc-ref plain">{s.ref}</span>
      )}
      <button
        className="ssrc-del"
        title="删除"
        onClick={() => del.mutate({ id: s.id, symbol: s.symbol })}
      >
        ×
      </button>
    </div>
  )
}

function AddRow({ symbol, onDone }: { symbol: string; onDone: () => void }) {
  const add = useAddStockSource()
  const [kind, setKind] = useState('influencer_x')
  const [name, setName] = useState('')
  const [ref, setRef] = useState('')
  const submit = () => {
    if (!name.trim() && !ref.trim()) return
    add.mutate({ symbol, kind, name: name.trim(), ref: ref.trim() })
    onDone()
  }
  return (
    <div className="ssrc-add">
      <select className="ssrc-sel" value={kind} onChange={(e) => setKind(e.target.value)}>
        {KINDS.map((k) => (
          <option key={k.key} value={k.key}>
            {k.label}
          </option>
        ))}
      </select>
      <input
        className="input ssrc-in"
        placeholder="名称"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="input ssrc-in"
        placeholder="URL / @句柄 / r/子版"
        value={ref}
        onChange={(e) => setRef(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <button className="btn jsm" onClick={submit}>
        加
      </button>
    </div>
  )
}

export default function StockSourcesPanel({ symbol }: { symbol: string }) {
  const sources = useStockSources(symbol)
  const discover = useDiscoverSources()
  const [adding, setAdding] = useState(false)
  const list = sources.data ?? []
  const onN = list.filter((s) => s.enabled).length

  return (
    <section className="ssrc">
      <div className="sec-head">
        <h3>
          专属信源 {onN > 0 && <span className="ssrc-on-n">{onN} 启用</span>}
        </h3>
        <div className="ssrc-acts">
          <button className="btn jsm" onClick={() => setAdding((v) => !v)}>
            ＋ 手动
          </button>
          <button
            className="btn btn-primary jsm"
            disabled={discover.isPending}
            onClick={() => discover.mutate(symbol)}
          >
            {discover.isPending ? '调研中…' : list.length ? '重新调研' : '调研信源'}
          </button>
        </div>
      </div>
      {discover.isError && <div className="opp-err">{(discover.error as Error).message}</div>}
      {adding && <AddRow symbol={symbol} onDone={() => setAdding(false)} />}
      {discover.isPending ? (
        <div className="opp-empty faint">正在调研这只股该看哪些官网/大V/论坛/财经源…</div>
      ) : list.length ? (
        <div className="ssrc-list">
          {list.map((s) => (
            <SourceRow key={s.id} s={s} />
          ))}
        </div>
      ) : (
        <div className="opp-empty faint">
          点「调研信源」让 LLM 找出这只股专属的官网/IR/官方X/大V/Reddit/雪球/财经站，再由你勾选启用。
        </div>
      )}
    </section>
  )
}
