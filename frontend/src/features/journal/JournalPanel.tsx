import { useState } from 'react'
import { motion } from 'motion/react'
import Collapse from '../../components/Collapse'
import {
  useCreateJournal,
  useDeleteJournal,
  useJournal,
  useUpdateJournal,
  type JournalEntry,
} from '../../api'
import { EASE } from '../../theme/motion'

const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 距今天数（复盘语境：「32 天前的判断」）
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
    <div className="jeditor">
      <div className="jeditor-top">
        <label className="jdate-lbl">日期</label>
        <input type="date" className="input jdate-input" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <textarea
        className="input jtext"
        autoFocus
        rows={4}
        value={body}
        placeholder="判断"
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

function EntryCard({
  entry,
  collapsed,
  onToggle,
  onEdit,
  onDelete,
}: {
  entry: JournalEntry
  collapsed: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const stop = (fn: () => void) => (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    fn()
  }
  return (
    <motion.article
      className="jentry"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: EASE }}
    >
      <header className="jentry-head" onClick={onToggle}>
        <time className="jdate mono">{entry.entry_date}</time>
        <span className="jago faint">{agoLabel(entry.entry_date)}</span>
        <span className="jactions">
          <button className="jbtn" title="修改" onClick={stop(onEdit)}>
            ✎
          </button>
          <button className="jbtn jdel" title="删除" onClick={stop(onDelete)}>
            ×
          </button>
        </span>
      </header>
      <Collapse open={!collapsed}>
        <div className="jbody">{entry.body || <span className="faint">（空）</span>}</div>
      </Collapse>
    </motion.article>
  )
}

export default function JournalPanel({ symbol }: { symbol: string }) {
  const { data: entries, isLoading } = useJournal(symbol)
  const create = useCreateJournal()
  const update = useUpdateJournal(symbol)
  const del = useDeleteJournal(symbol)
  const [adding, setAdding] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [open, setOpen] = useState(true)
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  const toggle = (id: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <section className="journal">
      <div className="journal-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>判断日记</h3>
        {!adding && (
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
        )}
      </div>

      <Collapse open={open}>
        {adding && (
          <Editor
            initialDate={todayISO()}
            initialBody=""
            onCancel={() => setAdding(false)}
            onSave={(entry_date, body) => {
              create.mutate({ symbol, entry_date, body })
              setAdding(false)
            }}
          />
        )}

        {!isLoading && entries && entries.length === 0 && !adding && (
          <div className="journal-empty">暂无判断</div>
        )}

        <div className="journal-list">
          {entries?.map((e) =>
            editId === e.id ? (
              <Editor
                key={e.id}
                initialDate={e.entry_date}
                initialBody={e.body}
                onCancel={() => setEditId(null)}
                onSave={(entry_date, body) => {
                  update.mutate({ id: e.id, entry_date, body })
                  setEditId(null)
                }}
              />
            ) : (
              <EntryCard
                key={e.id}
                entry={e}
                collapsed={collapsed.has(e.id)}
                onToggle={() => toggle(e.id)}
                onEdit={() => setEditId(e.id)}
                onDelete={() => del.mutate(e.id)}
              />
            ),
          )}
        </div>
      </Collapse>
    </section>
  )
}
