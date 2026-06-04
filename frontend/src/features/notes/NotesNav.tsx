import { useNotes, useCreateNote } from '../../api'
import { useNotesUI } from './store'

function relDay(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return ''
  const a = new Date()
  a.setHours(0, 0, 0, 0)
  const b = new Date(d)
  b.setHours(0, 0, 0, 0)
  const diff = Math.round((a.getTime() - b.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff} 天前`
  return `${b.getMonth() + 1}月${b.getDate()}日`
}

export default function NotesNav() {
  const list = useNotes()
  const create = useCreateNote()
  const selectedId = useNotesUI((s) => s.selectedId)
  const select = useNotesUI((s) => s.select)
  const items = list.data ?? []

  const onNew = async () => {
    const n = await create.mutateAsync({ title: '', body: '' })
    select(n.id)
  }

  return (
    <aside className="panel notes-nav">
      <div className="notes-nav-head">
        <div className="lbl">记</div>
        <button className="notes-new" onClick={onNew} disabled={create.isPending} title="新建笔记">
          ＋ 新建
        </button>
      </div>
      {list.isLoading ? (
        <div className="nsub-row faint">加载…</div>
      ) : items.length === 0 ? (
        <div className="nsub-empty faint">还没有笔记，点「＋ 新建」开始记录</div>
      ) : (
        <div className="notes-list">
          {items.map((n) => (
            <button
              key={n.id}
              className={`note-row ${selectedId === n.id ? 'active' : ''}`}
              onClick={() => select(n.id)}
            >
              <div className="note-row-top">
                {n.pinned && <span className="note-pin" title="置顶">●</span>}
                <span className="note-row-title">{n.title || '无标题'}</span>
              </div>
              {n.preview && <div className="note-row-prev">{n.preview}</div>}
              <div className="note-row-when">{relDay(n.updated_at)}</div>
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}
