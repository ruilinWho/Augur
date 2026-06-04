import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { useDeleteNote, useNote, useUpdateNote } from '../../api'
import Markdown from '../../components/Markdown'
import { useNotesUI } from './store'

const EASE = [0.22, 1, 0.36, 1] as const

function fmtWhen(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 单篇编辑器：标题 + 正文（编辑/预览切换）+ 置顶/删除。防抖自动保存（长文不丢，§9 平静）。
function NoteEditor({ id }: { id: number }) {
  const note = useNote(id)
  const upd = useUpdateNote()
  const del = useDeleteNote()
  const select = useNotesUI((s) => s.select)

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [preview, setPreview] = useState(false)
  const [status, setStatus] = useState<'saved' | 'dirty' | 'saving'>('saved')
  const timer = useRef<number | undefined>(undefined)
  const loadedId = useRef<number | null>(null)

  // 切到另一篇 / 首次加载时，用服务器值填充本地态（不覆盖正在编辑的内容）
  useEffect(() => {
    if (note.data && loadedId.current !== note.data.id) {
      loadedId.current = note.data.id
      setTitle(note.data.title)
      setBody(note.data.body)
      setStatus('saved')
    }
  }, [note.data])

  const scheduleSave = (next: { title?: string; body?: string }) => {
    setStatus('dirty')
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      setStatus('saving')
      upd
        .mutateAsync({ id, ...next })
        .then(() => setStatus('saved'))
        .catch(() => setStatus('dirty'))
    }, 700)
  }

  // 卸载时清掉计时器（避免向已卸载组件 setState）
  useEffect(() => () => window.clearTimeout(timer.current), [])

  if (note.isLoading && !note.data) return <div className="report-card faint">加载…</div>
  if (!note.data) return <div className="know-empty">笔记不存在</div>

  const togglePin = () => upd.mutate({ id, pinned: !note.data!.pinned })
  const onDelete = () => {
    if (!confirm('删除这篇笔记？')) return
    del.mutate(id, { onSuccess: () => select(null) })
  }

  const statusText =
    status === 'saving' ? '保存中…' : status === 'dirty' ? '未保存' : '已保存'

  return (
    <motion.div
      className="note-edit"
      key={id}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: EASE }}
    >
      <div className="note-head">
        <input
          className="note-title-in"
          placeholder="无标题"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            scheduleSave({ title: e.target.value })
          }}
        />
        <div className="note-actions">
          <span className="note-status faint">{statusText}</span>
          <button
            className={`note-act ${note.data.pinned ? 'on' : ''}`}
            onClick={togglePin}
            title={note.data.pinned ? '取消置顶' : '置顶'}
          >
            {note.data.pinned ? '已置顶' : '置顶'}
          </button>
          <div className="seg note-seg">
            <button aria-pressed={!preview} onClick={() => setPreview(false)}>
              编辑
            </button>
            <button aria-pressed={preview} onClick={() => setPreview(true)}>
              预览
            </button>
          </div>
          <button className="note-act danger" onClick={onDelete} title="删除">
            删除
          </button>
        </div>
      </div>

      {preview ? (
        body.trim() ? (
          <div className="report-card note-preview">
            <Markdown body={body} />
          </div>
        ) : (
          <div className="know-empty">
            <div className="ke-title">空正文</div>
          </div>
        )
      ) : (
        <textarea
          className="note-body-in"
          placeholder="写下与个股无关的长文——市场随想、方法论、复盘思考…（支持 Markdown）"
          value={body}
          onChange={(e) => {
            setBody(e.target.value)
            scheduleSave({ body: e.target.value })
          }}
        />
      )}

      {note.data.updated_at && (
        <div className="note-foot faint">最后更新 {fmtWhen(note.data.updated_at)}</div>
      )}
    </motion.div>
  )
}

export default function NotesView() {
  const selectedId = useNotesUI((s) => s.selectedId)
  if (selectedId == null)
    return (
      <div className="note-edit">
        <div className="know-empty">
          <div className="ke-title">「记」· 自由长文</div>
          <div className="faint">从左侧选一篇，或「＋ 新建」——记录与个股无关的市场思考与方法论</div>
        </div>
      </div>
    )
  return <NoteEditor key={selectedId} id={selectedId} />
}
