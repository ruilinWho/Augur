import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { motion } from 'motion/react'
import Collapse from '../../components/Collapse'
import {
  useCreateJournal,
  useDeleteJournal,
  useGenerateReflectionTimeline,
  useJournal,
  useReflectionTimeline,
  useRefreshDirected,
  useStockDisclosures,
  useStockNewsBrief,
  useStockSocialHeat,
  useStockSources,
  useUpdateJournal,
  type CitedPoint,
  type ReflectionAssessment,
  type ReflectionEvent,
} from '../../api'
import { EASE } from '../../theme/motion'
import { IMP } from './NarrativeTimeline'
import { CitedList } from './shared'

const _autoReflection = new Set<string>()

const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function agoLabel(dateStr: string): string {
  const then = new Date(dateStr + 'T00:00:00')
  const now = new Date(todayISO() + 'T00:00:00')
  const days = Math.round((now.getTime() - then.getTime()) / 86400000)
  if (Number.isNaN(days)) return ''
  if (days <= 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 30) return `${days} 天前`
  if (days < 365) return `${Math.round(days / 30)} 个月前`
  return `${(days / 365).toFixed(1)} 年前`
}

function Editor({
  initialDate,
  initialBody,
  onCancel,
  onSave,
}: {
  initialDate: string
  initialBody: string
  onCancel: () => void
  onSave: (date: string, body: string) => void
}) {
  const [date, setDate] = useState(initialDate)
  const [body, setBody] = useState(initialBody)
  return (
    <div className="jeditor cog-editor">
      <div className="jeditor-top">
        <label className="jdate-lbl">日期</label>
        <input type="date" className="input jdate-input" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <textarea
        className="input jtext"
        autoFocus
        rows={4}
        value={body}
        placeholder="写下今天对这只股票的判断、触发条件、反证条件"
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && body.trim()) onSave(date, body.trim())
          else if (e.key === 'Escape') onCancel()
        }}
      />
      <div className="jeditor-actions">
        <button className="btn btn-ghost jsm" onClick={onCancel}>
          取消
        </button>
        <button className="btn btn-primary jsm" disabled={!body.trim()} onClick={() => onSave(date, body.trim())}>
          保存
        </button>
      </div>
    </div>
  )
}

function verdictClass(a: ReflectionAssessment | null) {
  const v = a?.verdict ?? ''
  if (v === '印证') return 'good'
  if (v === '证伪') return 'bad'
  if (v === '混合') return 'mixed'
  return 'pending'
}

function AssessmentBox({ data }: { data: ReflectionAssessment }) {
  return (
    <div className={`cog-assess ${verdictClass(data)}`}>
      <div className="cog-assess-head">
        <span>{data.verdict}</span>
        <i>{data.confidence === 'high' ? '高置信' : data.confidence === 'med' ? '中置信' : '低置信'}</i>
      </div>
      {data.text && <p>{data.text}</p>}
      {data.price && <div className="cog-price">{data.price}</div>}
      {data.refs.length > 0 && (
        <div className="cog-refs">
          {data.refs.map((r, i) => (
            <a key={`${r.url}-${i}`} href={r.url || undefined} target="_blank" rel="noreferrer">
              <span>{r.source || '来源'}</span>
              <b>{r.title}</b>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function EventRefs({ refs }: { refs: ReflectionEvent['refs'] }) {
  const [open, setOpen] = useState(false)
  if (!refs.length) return null
  return (
    <div className="cog-src">
      <button className="cog-src-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? '收起来源' : `${refs.length} 条来源`}
      </button>
      <Collapse open={open}>
        <div className="narr-refs cog-news-refs">
          {refs.map((r, j) => (
            <a key={j} className="narr-ref" href={r.url} target="_blank" rel="noreferrer">
              <span className="narr-ref-src">{r.source}</span>
              <span className="narr-ref-title">{r.title}</span>
            </a>
          ))}
        </div>
      </Collapse>
    </div>
  )
}

function TimelineEventCard({
  event,
  onEdit,
  onDelete,
}: {
  event: ReflectionEvent
  onEdit: () => void
  onDelete: () => void
}) {
  const imp = IMP[event.importance] ?? IMP.med
  const isJournal = event.kind === 'journal'
  const isDisclosure = event.kind === 'disclosure'
  const label = isJournal ? '判断' : isDisclosure ? '披露' : '事件'
  return (
    <motion.article
      className={`cog-event ${isJournal ? 'is-judgment' : isDisclosure ? 'is-disclosure' : 'is-news'}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: EASE }}
    >
      <header className="cog-event-head">
        <span className={`cog-kind ${isJournal ? 'judgment' : isDisclosure ? 'disclosure' : 'news'}`}>
          {label}
        </span>
        {!isJournal && <span className={`cl-imp ${imp.cls}`}>{imp.label}</span>}
        <time className="mono">{event.date}</time>
        {isJournal && <span className="faint">{agoLabel(event.date)}</span>}
        {isJournal && (
          <span className="cog-actions">
            <button className="jbtn" title="修改" onClick={onEdit}>
              ✎
            </button>
            <button className="jbtn jdel" title="删除" onClick={onDelete}>
              ×
            </button>
          </span>
        )}
      </header>
      <div className="cog-title">{event.title}</div>
      {isJournal && event.body && <div className="cog-body">{event.body}</div>}
      {!isJournal && event.body && <div className="cog-body disclosure-body">{event.body}</div>}
      {!isJournal && <EventRefs refs={event.refs} />}
      {event.assessment && <AssessmentBox data={event.assessment} />}
    </motion.article>
  )
}

function SocialCol({ label, tone, items }: { label: string; tone: string; items: CitedPoint[] }) {
  if (!items.length) return null
  return (
    <div className={`srn-sc srn-sc-${tone}`}>
      <span className="srn-sc-l">{label}</span>
      <CitedList items={items} />
    </div>
  )
}

export default function StockNews({ symbol }: { symbol: string }) {
  const brief = useStockNewsBrief(symbol)
  const social = useStockSocialHeat(symbol)
  const timeline = useReflectionTimeline(symbol)
  const genTimeline = useGenerateReflectionTimeline()
  const refresh = useRefreshDirected()
  const sources = useStockSources(symbol)
  const disclosures = useStockDisclosures(symbol)
  const journal = useJournal(symbol)
  const create = useCreateJournal()
  const update = useUpdateJournal(symbol)
  const del = useDeleteJournal(symbol)
  const [open, setOpen] = useState(true)
  const [adding, setAdding] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)

  const data = brief.data
  const heat = social.data
  const reflection = timeline.data
  const n = data?.source_count ?? reflection?.news_count ?? 0
  const disclosureCount = disclosures.data?.events.filter((e) => e.kind !== 'financial_period').length ?? 0
  const enabledSources = (sources.data ?? []).filter((s) => s.enabled).length
  const heatTone = heat?.heat === '高' ? 'high' : heat?.heat === '中' ? 'mid' : 'low'
  const hasBrief = Boolean(data?.summary || data?.points.length || data?.risks.length)
  const hasSocial = Boolean(
    heat?.summary || heat?.bull_points.length || heat?.bear_points.length || heat?.watch.length,
  )
  const busy = refresh.isPending || genTimeline.isPending

  const genRef = useRef(genTimeline.mutate)
  genRef.current = genTimeline.mutate
  useEffect(() => {
    if (timeline.isLoading || genTimeline.isPending) return
    if (!reflection && !_autoReflection.has(symbol)) {
      _autoReflection.add(symbol)
      genRef.current(symbol)
    }
  }, [symbol, reflection, timeline.isLoading, genTimeline.isPending])

  const regenerate = () => {
    _autoReflection.add(symbol)
    genTimeline.mutate(symbol)
  }

  const runRefresh = async (e: MouseEvent) => {
    e.stopPropagation()
    _autoReflection.add(symbol)
    await refresh.mutateAsync(symbol)
    await genTimeline.mutateAsync(symbol)
  }

  const afterJournalChange = () => genTimeline.mutate(symbol)
  const events = reflection?.events ?? []

  return (
    <section className="stock-news cog">
      <div className="sec-head cog-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>综合认知</h3>
        <div className="cog-head-right">
          <div className="cog-metrics" aria-label="综合认知计数">
            {n > 0 && <span className="cog-count">{n} 事件</span>}
            {disclosureCount > 0 && <span className="cog-count hot">披露 {disclosureCount}</span>}
            {enabledSources > 0 && <span className="cog-count hot">专属 {enabledSources}</span>}
          </div>
          <div className="cog-head-actions">
            <button
              className="btn btn-primary jsm"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(true)
                setAdding(true)
              }}
            >
              ＋ 写判断
            </button>
            <button className="btn btn-ghost jsm stock-news-refresh" onClick={runRefresh} disabled={busy}>
              {busy ? '更新中…' : '刷新并评价'}
            </button>
          </div>
        </div>
      </div>

      <Collapse open={open}>
        <div className="cog-wrap">
          {adding && (
            <Editor
              initialDate={todayISO()}
              initialBody=""
              onCancel={() => setAdding(false)}
              onSave={(entry_date, body) => {
                create.mutate({ symbol, entry_date, body }, { onSuccess: afterJournalChange })
                setAdding(false)
              }}
            />
          )}

          {(hasBrief || hasSocial || reflection?.summary) && (
            <div className="cog-context">
              {reflection?.summary && (
                <div className="cog-overview">
                  <div className="cog-card-head">
                    <span className="cog-card-title">总览</span>
                  </div>
                  <p>{reflection.summary}</p>
                </div>
              )}
              {hasBrief && (
                <div className="cog-now">
                  <div className="cog-card-head">
                    <span className="cog-card-title">近况</span>
                  </div>
                  {data?.summary && <p>{data.summary}</p>}
                  {data?.points.length ? <CitedList items={data.points.slice(0, 3)} /> : null}
                </div>
              )}
              {hasSocial && (
                <div className="cog-social">
                  <div className="cog-card-head">
                    <span className="cog-card-title">社媒热度</span>
                    <i className={`social-pill heat-${heatTone}`}>{heat?.heat ?? '低'}</i>
                    <i className="social-pill">{heat?.sentiment ?? '不明'}</i>
                  </div>
                  {heat?.summary && <p>{heat.summary}</p>}
                  <div className="srn-social-cols compact">
                    <SocialCol label="偏多" tone="bull" items={(heat?.bull_points ?? []).slice(0, 2)} />
                    <SocialCol label="反方" tone="bear" items={(heat?.bear_points ?? []).slice(0, 2)} />
                    <SocialCol label="观察" tone="watch" items={(heat?.watch ?? []).slice(0, 2)} />
                  </div>
                </div>
              )}
            </div>
          )}

          {timeline.isLoading || genTimeline.isPending ? (
            <div className="fin-empty">融合判断、公司披露、新闻和事实反馈…</div>
          ) : events.length > 0 ? (
            <div className="cog-line">
              {events.map((event) =>
                event.journal_id != null && editId === event.journal_id ? (
                  <Editor
                    key={event.id}
                    initialDate={event.date}
                    initialBody={event.body}
                    onCancel={() => setEditId(null)}
                    onSave={(entry_date, body) => {
                      if (event.journal_id != null) {
                        update.mutate(
                          { id: event.journal_id, entry_date, body },
                          { onSuccess: afterJournalChange },
                        )
                      }
                      setEditId(null)
                    }}
                  />
                ) : (
                  <TimelineEventCard
                    key={event.id}
                    event={event}
                    onEdit={() => setEditId(event.journal_id)}
                    onDelete={() => {
                      if (event.journal_id != null) {
                        del.mutate(event.journal_id, { onSuccess: afterJournalChange })
                      }
                    }}
                  />
                ),
              )}
            </div>
          ) : journal.data?.length ? (
            <div className="journal-empty">
              已有判断，但还没有生成事实反馈。
              <button className="btn btn-ghost jsm inline-action" onClick={regenerate}>
                生成评价
              </button>
            </div>
          ) : (
            <div className="journal-empty">暂无判断；写下一条判断后，后续披露、新闻和价格会成为复盘材料。</div>
          )}
        </div>
      </Collapse>
    </section>
  )
}
