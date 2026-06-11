import { useMemo, useState } from 'react'
import { useUI } from '../../store'
import {
  useCreateThesis,
  useDeleteThesis,
  useDraftThesis,
  useScanTheses,
  useSections,
  useTheses,
  useUpdateThesis,
  type Section,
  type Thesis,
  type ThesisAlert,
} from '../../api'
import { CitedText } from './shared'

const STANCE: Record<string, { label: string; cls: string }> = {
  bull: { label: '看多', cls: 'st-bull' },
  bear: { label: '看空', cls: 'st-bear' },
  watch: { label: '观望', cls: 'st-watch' },
}
const STANCES = ['bull', 'bear', 'watch'] as const
const MKT_BADGE: Record<string, string> = { US: '美', HK: '港', CN: 'A', KR: '韩' }

// 自选分区树 → 去重 symbol 列表（保持分区顺序），供立论的标的选择
function flattenSymbols(sections: Section[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  const walk = (s: Section) => {
    for (const it of s.items) if (!seen.has(it.symbol)) (seen.add(it.symbol), out.push(it.symbol))
    s.children.forEach(walk)
  }
  sections.forEach(walk)
  return out
}

// 一条告警：反证（用户「下跌色」警示）/ 印证（「上涨色」）。summary 即可点链接（回原文核对）。
function AlertRow({ a }: { a: ThesisAlert }) {
  const refute = a.polarity === 'refute'
  return (
    <div className={`talert ${refute ? 'refute' : 'support'}`}>
      <span className="talert-tag">{refute ? '反证' : '印证'}</span>
      <CitedText p={{ text: a.summary, refs: a.refs }} />
    </div>
  )
}

// 一条证伪条件 + 挂在它下面的告警
function ConditionRow({ text, n, alerts }: { text: string; n: number; alerts: ThesisAlert[] }) {
  return (
    <li className="tcond">
      <span className="tcond-text">
        <span className="tcond-n">{n}</span>
        {text}
      </span>
      {alerts.map((a, i) => (
        <AlertRow key={i} a={a} />
      ))}
    </li>
  )
}

// 一条立论卡：立场徽章 + 标的（看/研）+ 一句话立论 + 证伪条件（含反证/印证告警）。
function ThesisCard({ t, onEdit }: { t: Thesis; onEdit: () => void }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  const del = useDeleteThesis()
  const st = STANCE[t.stance] ?? STANCE.watch
  const refuteN = t.alerts.filter((a) => a.polarity === 'refute').length
  return (
    <article className={`thesis ${refuteN ? 'challenged' : ''}`}>
      <div className="thesis-head">
        <span className={`tstance ${st.cls}`}>{st.label}</span>
        <button className="thesis-name" onClick={() => select(t.symbol)} title="在「看」里查看 K 线">
          <span className="wdot" />
          {t.name}
        </button>
        {t.market && <span className="thesis-mkt">{MKT_BADGE[t.market] ?? t.market}</span>}
        {refuteN > 0 && <span className="thesis-flag">⚡ {refuteN} 反证</span>}
        <span className="thesis-actions">
          <button className="tbtn" onClick={() => research(t.symbol)} title="深度研究这只股">
            研
          </button>
          <button className="tbtn" onClick={onEdit} title="编辑立论 / 证伪条件">
            ✎
          </button>
          <button className="tbtn tdel" onClick={() => del.mutate(t.id)} title="删除立论">
            ×
          </button>
        </span>
      </div>
      {t.thesis && <p className="thesis-line">{t.thesis}</p>}
      {t.conditions.length > 0 ? (
        <ul className="tconds">
          {t.conditions.map((c, i) => (
            <ConditionRow
              key={c.id}
              text={c.text}
              n={i + 1}
              alerts={t.alerts.filter((a) => a.condition_id === c.id)}
            />
          ))}
        </ul>
      ) : (
        <p className="faint tcond-empty">未设证伪条件 · 点 ✎ 补充</p>
      )}
    </article>
  )
}

// 立论编辑器：新建（带标的选择）或编辑既有。可 AI 起草（从该股近况草拟立场/立论/证伪条件）。
function ThesisEditor({
  stocks,
  initial,
  onCancel,
  onSaved,
}: {
  stocks: string[]
  initial: Thesis | null
  onCancel: () => void
  onSaved: () => void
}) {
  const create = useCreateThesis()
  const update = useUpdateThesis()
  const draft = useDraftThesis()
  const editing = initial != null
  const [symbol, setSymbol] = useState(initial?.symbol ?? stocks[0] ?? '')
  const [stance, setStance] = useState(initial?.stance ?? 'bull')
  const [thesis, setThesis] = useState(initial?.thesis ?? '')
  const [conds, setConds] = useState((initial?.conditions ?? []).map((c) => c.text).join('\n'))

  const runDraft = async () => {
    if (!symbol) return
    const d = await draft.mutateAsync(symbol)
    setStance(d.stance)
    if (d.thesis) setThesis(d.thesis)
    if (d.conditions.length) setConds(d.conditions.join('\n'))
  }
  const save = () => {
    const conditions = conds
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    if (editing) update.mutate({ id: initial.id, stance, thesis, conditions }, { onSuccess: onSaved })
    else create.mutate({ symbol, stance, thesis, conditions }, { onSuccess: onSaved })
  }
  const busy = create.isPending || update.isPending

  return (
    <div className="teditor">
      <div className="teditor-row">
        {editing ? (
          <span className="teditor-sym">
            <span className="wdot" />
            {initial.name}
          </span>
        ) : (
          <select className="input teditor-pick" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {stocks.map((s) => (
              <option key={s} value={s}>
                {s.split(':')[1]} · {MKT_BADGE[s.split(':')[0]] ?? s.split(':')[0]}
              </option>
            ))}
          </select>
        )}
        <div className="seg tstance-seg">
          {STANCES.map((s) => (
            <button key={s} aria-pressed={stance === s} onClick={() => setStance(s)}>
              {STANCE[s].label}
            </button>
          ))}
        </div>
        <button className="btn btn-ghost jsm teditor-draft" disabled={!symbol || draft.isPending} onClick={runDraft}>
          {draft.isPending ? '起草中…' : '✨ AI 起草'}
        </button>
      </div>
      <input
        className="input"
        value={thesis}
        placeholder="一句话立论：为什么看多 / 看空这只票"
        onChange={(e) => setThesis(e.target.value)}
      />
      <textarea
        className="input tconds-input"
        rows={4}
        value={conds}
        placeholder="证伪条件，每行一条：什么事实出现，就说明这个判断错了"
        onChange={(e) => setConds(e.target.value)}
      />
      {draft.isError && <div className="opp-err">{(draft.error as Error).message}</div>}
      <div className="teditor-actions">
        <button className="btn btn-ghost jsm" onClick={onCancel}>
          取消
        </button>
        <button
          className="btn btn-primary jsm"
          disabled={!symbol || busy || (!thesis.trim() && !conds.trim())}
          onClick={save}
        >
          {busy ? '保存中…' : '保存'}
        </button>
      </div>
    </div>
  )
}

// 资讯 · 雷达：反证雷达。给持有观点的票记下证伪条件，系统按每天挂钩新闻盯反证/印证。
export default function RadarView() {
  const theses = useTheses()
  const scan = useScanTheses()
  const sectionsQ = useSections('ALL')
  const stocks = useMemo(() => flattenSymbols(sectionsQ.data ?? []), [sectionsQ.data])
  const [adding, setAdding] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const list = theses.data ?? []
  const refuteTotal = list.reduce(
    (n, t) => n + t.alerts.filter((a) => a.polarity === 'refute').length,
    0,
  )

  return (
    <div className="know">
      <div className="sum-head">
        <div className="sum-title-line">
          <h2 className="sum-title">反证雷达</h2>
          {refuteTotal > 0 && <span className="since-pill hot">{refuteTotal} 反证</span>}
        </div>
        <div className="sum-gen">
          {list.length > 0 && (
            <button className="btn jsm" disabled={scan.isPending} onClick={() => scan.mutate()}>
              {scan.isPending ? '扫描中…' : '↻ 扫描'}
            </button>
          )}
          {!adding && (
            <button
              className="btn btn-primary jsm"
              onClick={() => {
                setAdding(true)
                setEditId(null)
              }}
            >
              ＋ 立论
            </button>
          )}
        </div>
      </div>

      {adding && (
        <ThesisEditor
          stocks={stocks}
          initial={null}
          onCancel={() => setAdding(false)}
          onSaved={() => setAdding(false)}
        />
      )}
      {scan.isError && <div className="opp-err">{(scan.error as Error).message}</div>}

      {list.length > 0 ? (
        <div className="theses">
          {list.map((t) =>
            editId === t.id ? (
              <ThesisEditor
                key={t.id}
                stocks={stocks}
                initial={t}
                onCancel={() => setEditId(null)}
                onSaved={() => setEditId(null)}
              />
            ) : (
              <ThesisCard key={t.id} t={t} onEdit={() => (setEditId(t.id), setAdding(false))} />
            ),
          )}
        </div>
      ) : theses.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : !adding ? (
        <div className="know-empty">
          <div className="ke-title">还没有立论</div>
        </div>
      ) : null}
    </div>
  )
}
