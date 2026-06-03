import { useEffect, useState } from 'react'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  useAddImported,
  useDeleteImported,
  useImportedReports,
  useReorderImported,
  useUpdateImported,
  type ImportedReport,
} from '../../api'
import { Digest } from '../news/shared'

function fmtWhen(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function GripDots() {
  return (
    <svg width="8" height="16" viewBox="0 0 8 16" aria-hidden="true">
      {[2.5, 5.5].flatMap((cx) =>
        [3, 8, 13].map((cy) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.05" fill="currentColor" />),
      )}
    </svg>
  )
}

function ImpCard({ r }: { r: ImportedReport }) {
  const upd = useUpdateImported()
  const del = useDeleteImported()
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: r.id,
  })
  const [editBody, setEditBody] = useState(false)
  const [title, setTitle] = useState(r.title)
  const [body, setBody] = useState(r.body)
  const [comment, setComment] = useState(r.comment)
  // 保存/刷新后让本地态跟上服务器（不在编辑正文时才同步，避免覆盖输入中的内容）
  useEffect(() => setTitle(r.title), [r.title])
  useEffect(() => setComment(r.comment), [r.comment])
  useEffect(() => {
    if (!editBody) setBody(r.body)
  }, [r.body]) // eslint-disable-line react-hooks/exhaustive-deps

  const saveTitle = () => {
    if (title.trim() !== r.title) upd.mutate({ id: r.id, symbol: r.symbol, title: title.trim() })
  }
  const saveBody = () => {
    setEditBody(false)
    if (body !== r.body) upd.mutate({ id: r.id, symbol: r.symbol, body })
  }
  const saveComment = () => {
    if (comment !== r.comment) upd.mutate({ id: r.id, symbol: r.symbol, comment })
  }

  return (
    <div
      ref={setNodeRef}
      className={`imp-card ${isDragging ? 'dragging' : ''}`}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.7 : 1 }}
    >
      <div className="imp-head">
        <button className="imp-grip" {...attributes} {...listeners} title="拖动排序" aria-label="拖动排序">
          <GripDots />
        </button>
        <input
          className="imp-title"
          placeholder="标题"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={saveTitle}
        />
        {r.created_at && <span className="imp-when">{fmtWhen(r.created_at)}</span>}
        <button className="imp-edit" onClick={() => (editBody ? saveBody() : setEditBody(true))}>
          {editBody ? '完成' : '编辑'}
        </button>
        <button
          className="imp-del"
          title="删除研报"
          onClick={() => del.mutate({ id: r.id, symbol: r.symbol })}
        >
          ×
        </button>
      </div>
      {editBody ? (
        <textarea
          className="imp-body-edit"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="正文（markdown）"
          autoFocus
        />
      ) : body.trim() ? (
        <div className="imp-body">
          <Digest body={body} />
        </div>
      ) : (
        <div className="imp-body faint">空正文</div>
      )}
      <div className="imp-comment">
        <span className="imp-comment-lbl">我的评论</span>
        <textarea
          className="imp-comment-in"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          onBlur={saveComment}
          placeholder="写点你的看法…"
        />
      </div>
    </div>
  )
}

function AddForm({ symbol, onDone }: { symbol: string; onDone: () => void }) {
  const add = useAddImported()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const submit = () => {
    if (!title.trim() && !body.trim()) return
    add.mutate({ symbol, title: title.trim(), body })
    onDone()
  }
  return (
    <div className="imp-add">
      <input
        className="imp-title"
        placeholder="标题"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        autoFocus
      />
      <textarea
        className="imp-body-edit"
        placeholder="正文（markdown）"
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="imp-add-actions">
        <button className="btn btn-ghost jsm" onClick={onDone}>
          取消
        </button>
        <button className="btn btn-primary jsm" disabled={add.isPending} onClick={submit}>
          保存
        </button>
      </div>
    </div>
  )
}

export default function ImportedReports({ symbol }: { symbol: string }) {
  const list = useImportedReports(symbol)
  const reorder = useReorderImported()
  const [adding, setAdding] = useState(false)
  const items = list.data ?? []
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const ids = items.map((r) => r.id)
    const from = ids.indexOf(Number(active.id))
    const to = ids.indexOf(Number(over.id))
    if (from < 0 || to < 0) return
    reorder.mutate({ symbol, orderedIds: arrayMove(ids, from, to) })
  }

  return (
    <section className="imp">
      <div className="sec-head">
        <h3>
          导入研报 {items.length > 0 && <span className="imp-n">{items.length}</span>}
        </h3>
        <button className="btn btn-primary jsm sec-gen" onClick={() => setAdding((v) => !v)}>
          ＋ 导入
        </button>
      </div>
      {adding && <AddForm symbol={symbol} onDone={() => setAdding(false)} />}
      {items.length > 0 ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={items.map((r) => r.id)} strategy={verticalListSortingStrategy}>
            <div className="imp-list">
              {items.map((r) => (
                <ImpCard key={r.id} r={r} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : null}
    </section>
  )
}
