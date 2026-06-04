import { useEffect, useMemo, useRef, useState } from 'react'
import { useAddItem, useCreateSection, useSections, type Section } from '../../api'

type Target = { id: number; label: string; depth: number }

function flatten(sections: Section[]): Target[] {
  const out: Target[] = []
  for (const s of sections) {
    out.push({ id: s.id, label: s.name, depth: 0 })
    for (const c of s.children) out.push({ id: c.id, label: c.name, depth: 1 })
  }
  return out
}

function inTree(sections: Section[], symbol: string): boolean {
  const walk = (s: Section): boolean =>
    s.items.some((it) => it.symbol === symbol) || s.children.some(walk)
  return sections.some(walk)
}

// 「看」头部：当前标的若不在自选里 → 显示「＋ 自选」，点开选分区（含新建）加入。
export default function AddToWatchlist({ symbol }: { symbol: string }) {
  const { data: sections } = useSections('ALL')
  const addItem = useAddItem()
  const createSection = useCreateSection()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const ref = useRef<HTMLSpanElement | null>(null)

  const tree = sections ?? []
  const inWl = useMemo(() => inTree(tree, symbol), [tree, symbol])
  const targets = useMemo(() => flatten(tree), [tree])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setCreating(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  if (inWl) return null // 已自选 → 不显示

  const addTo = (sectionId: number) => {
    addItem.mutate({ sectionId, symbol })
    setOpen(false)
  }
  const createAndAdd = async () => {
    const name = newName.trim()
    if (!name) return
    const sec = (await createSection.mutateAsync({ name })) as Section
    addItem.mutate({ sectionId: sec.id, symbol })
    setNewName('')
    setCreating(false)
    setOpen(false)
  }

  return (
    <span className="addwl" ref={ref}>
      <button className="addwl-btn" onClick={() => setOpen((v) => !v)} title="加入自选分区">
        ＋ 自选
      </button>
      {open && (
        <div className="addwl-menu">
          <div className="addwl-menu-h">加入哪个分区</div>
          {targets.map((t) => (
            <button
              key={t.id}
              className={`addwl-opt ${t.depth ? 'sub' : ''}`}
              onClick={() => addTo(t.id)}
            >
              {t.depth ? '└ ' : ''}
              {t.label}
            </button>
          ))}
          {!targets.length && <div className="addwl-empty faint">暂无分区</div>}
          {creating ? (
            <div className="addwl-new">
              <input
                className="input"
                autoFocus
                placeholder="新分区名…"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') createAndAdd()
                  else if (e.key === 'Escape') setCreating(false)
                }}
              />
              <button className="btn jsm" onClick={createAndAdd}>
                加
              </button>
            </div>
          ) : (
            <button className="addwl-opt new" onClick={() => setCreating(true)}>
              ＋ 新建分区…
            </button>
          )}
        </div>
      )}
    </span>
  )
}
