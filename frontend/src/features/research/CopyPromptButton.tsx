import { useEffect, useRef, useState } from 'react'
import {
  fillTemplate,
  renderSkill,
  useSkills,
  useTemplates,
  type PromptTemplate,
  type SkillMeta,
} from '../../api'
import { useToast } from '../../components/Toast'

// 「复制 Prompt」：技能（启用的 surface=yan）+ 用户模板，按当前标的填充占位符进剪贴板。
// 看/研两处复用。无任何技能/模板时不显示。className 让调用方控制按钮样式（研页 btn / 看页 chip）。
export default function CopyPromptButton({
  symbol,
  name,
  className = 'btn jsm',
}: {
  symbol: string
  name?: string | null
  className?: string
}) {
  const templates = useTemplates()
  const tpls = templates.data ?? []
  const skills = useSkills('yan', true)
  const sks = skills.data ?? []
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)
  const toast = useToast((s) => s.push)

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('pointerdown', onDown)
    return () => window.removeEventListener('pointerdown', onDown)
  }, [open])

  const copyTpl = async (t: PromptTemplate) => {
    setOpen(false)
    try {
      await navigator.clipboard.writeText(fillTemplate(t.body, symbol, name))
      toast('已复制 Prompt')
    } catch {
      toast('复制失败', 'error')
    }
  }
  const copySkill = async (sk: SkillMeta) => {
    setOpen(false)
    try {
      await navigator.clipboard.writeText(await renderSkill(sk.slug, symbol))
      toast(`已复制技能 · ${sk.name}`)
    } catch {
      toast('复制失败', 'error')
    }
  }

  const total = tpls.length + sks.length
  if (total === 0) return null
  const onlyOne = total === 1
  const copyOnly = () => (sks.length === 1 ? copySkill(sks[0]) : copyTpl(tpls[0]))

  return (
    <div className="tpl-copy" ref={ref}>
      <button className={className} onClick={() => (onlyOne ? copyOnly() : setOpen((v) => !v))}>
        复制 Prompt
      </button>
      {open && !onlyOne && (
        <div className="tpl-pop">
          {sks.length > 0 && <div className="tpl-pop-h">技能</div>}
          {sks.map((sk) => (
            <button key={sk.slug} onClick={() => copySkill(sk)}>
              {sk.name}
            </button>
          ))}
          {tpls.length > 0 && sks.length > 0 && <div className="tpl-pop-h">模板</div>}
          {tpls.map((t) => (
            <button key={t.id} onClick={() => copyTpl(t)}>
              {t.name || `模板 ${t.id}`}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
