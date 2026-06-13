import { useState, type ReactNode } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  useCreateFolder,
  useCreateNote,
  useDeleteFolder,
  useFolders,
  useMoveNote,
  useNotes,
  useRenameFolder,
  type Folder,
  type NoteMeta,
} from '../../api'
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

// 一条笔记行：整行可拖到文件夹（distance 约束区分点击 / 拖拽，未达阈值则正常 onClick 选中）。
function NoteRow({
  note,
  active,
  onSelect,
}: {
  note: NoteMeta
  active: boolean
  onSelect: (id: number) => void
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `note:${note.id}` })
  return (
    <button
      type="button"
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={`note-row ${active ? 'active' : ''} ${isDragging ? 'dragging' : ''}`}
      onClick={() => onSelect(note.id)}
    >
      <div className="note-row-top">
        {note.pinned && (
          <span className="note-pin" title="置顶">
            ●
          </span>
        )}
        <span className="note-row-title">{note.title || '无标题'}</span>
      </div>
      {note.preview && <div className="note-row-prev">{note.preview}</div>}
      <div className="note-row-when">{relDay(note.updated_at)}</div>
    </button>
  )
}

// 文件夹标题：双击名字重命名（对齐自选分区习惯）+ 笔记数 + hover 显「＋ 新建到此 / × 删除」。
function FolderHead({
  folder,
  onNewHere,
}: {
  folder: Folder
  onNewHere: (id: number) => void
}) {
  const rename = useRenameFolder()
  const del = useDeleteFolder()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(folder.name)

  const commit = () => {
    setEditing(false)
    const t = name.trim()
    if (t && t !== folder.name) rename.mutate({ id: folder.id, name: t })
    else setName(folder.name)
  }
  const onDelete = () => {
    if (!confirm(`删除文件夹「${folder.name}」？里面的笔记会回到「未归类」，不会被删除。`)) return
    del.mutate(folder.id)
  }

  return (
    <div className="note-folder-head">
      {editing ? (
        <input
          className="note-folder-rename"
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            else if (e.key === 'Escape') {
              setName(folder.name)
              setEditing(false)
            }
          }}
        />
      ) : (
        <span
          className="note-folder-name"
          onDoubleClick={() => {
            setName(folder.name)
            setEditing(true)
          }}
          title="双击重命名"
        >
          {folder.name}
        </span>
      )}
      <span className="note-folder-count">{folder.note_count}</span>
      <span className="note-folder-acts">
        <button className="nf-act" onClick={() => onNewHere(folder.id)} title="在此文件夹新建笔记">
          ＋
        </button>
        <button className="nf-act danger" onClick={onDelete} title="删除文件夹">
          ×
        </button>
      </span>
    </div>
  )
}

// 一个可放置区（文件夹 / 未归类）。空区不可见，仅作拖放目标；drop-over 时高亮。
function Zone({ dropId, children }: { dropId: string; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: dropId })
  return (
    <div ref={setNodeRef} className={`note-folder ${isOver ? 'drop-over' : ''}`}>
      {children}
    </div>
  )
}

export default function NotesNav() {
  const list = useNotes()
  const folders = useFolders()
  const createNote = useCreateNote()
  const createFolder = useCreateFolder()
  const move = useMoveNote()
  const selectedId = useNotesUI((s) => s.selectedId)
  const select = useNotesUI((s) => s.select)
  const [dragTitle, setDragTitle] = useState<string | null>(null)

  const notes = list.data ?? []
  const folderList = folders.data ?? []
  const hasFolders = folderList.length > 0
  const inFolder = (fid: number | null) => notes.filter((n) => (n.folder_id ?? null) === fid)
  const unfiled = inFolder(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const onDragStart = (e: DragStartEvent) => {
    const id = Number(String(e.active.id).replace('note:', ''))
    setDragTitle(notes.find((n) => n.id === id)?.title || '无标题')
  }
  const onDragEnd = (e: DragEndEvent) => {
    setDragTitle(null)
    const { active, over } = e
    if (!over) return
    const noteId = Number(String(active.id).replace('note:', ''))
    const fid = Number(String(over.id).replace('folder:', '')) || null // 'folder:0' → 未归类
    const note = notes.find((n) => n.id === noteId)
    if (!note || (note.folder_id ?? null) === fid) return
    move.mutate({ id: noteId, folderId: fid })
  }

  const newNote = async (folderId: number | null) => {
    const n = await createNote.mutateAsync({ folderId })
    select(n.id)
  }
  const newFolder = () => createFolder.mutate({ name: '新文件夹' })

  return (
    <aside className="panel notes-nav">
      <div className="notes-nav-head">
        <button
          className="notes-new"
          onClick={() => newNote(null)}
          disabled={createNote.isPending}
          title="新建笔记"
        >
          ＋ 笔记
        </button>
        <button
          className="notes-new ghost"
          onClick={newFolder}
          disabled={createFolder.isPending}
          title="新建文件夹"
        >
          ＋ 文件夹
        </button>
      </div>

      {list.isLoading ? (
        <div className="nsub-row faint">加载…</div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
        >
          <div className="notes-tree">
            {folderList.map((f) => (
              <Zone key={f.id} dropId={`folder:${f.id}`}>
                <FolderHead folder={f} onNewHere={newNote} />
                {inFolder(f.id).map((n) => (
                  <NoteRow key={n.id} note={n} active={selectedId === n.id} onSelect={select} />
                ))}
              </Zone>
            ))}

            {/* 未归类：有文件夹时给标题作拖回目标；无文件夹时退化为纯列表（视觉等同旧版）。 */}
            <Zone dropId="folder:0">
              {hasFolders && unfiled.length > 0 && (
                <div className="note-folder-head unfiled">
                  <span className="note-folder-name">未归类</span>
                  <span className="note-folder-count">{unfiled.length}</span>
                </div>
              )}
              {unfiled.map((n) => (
                <NoteRow key={n.id} note={n} active={selectedId === n.id} onSelect={select} />
              ))}
            </Zone>
          </div>

          <DragOverlay>
            {dragTitle != null ? <div className="note-row drag-ghost">{dragTitle || '无标题'}</div> : null}
          </DragOverlay>
        </DndContext>
      )}
    </aside>
  )
}
