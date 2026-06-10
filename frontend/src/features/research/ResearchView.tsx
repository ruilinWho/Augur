import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import {
  fillTemplate,
  renderSkill,
  streamResearch,
  useQuote,
  useResearchReport,
  useSkills,
  useTemplates,
  type PromptTemplate,
  type SkillMeta,
} from '../../api'
import { useUI } from '../../store'
import Markdown from '../../components/Markdown'
import { useToast } from '../../components/Toast'
import { EASE } from '../../theme/motion'
import ImportedReports from './ImportedReports'

function fmtWhen(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes(),
  ).padStart(2, '0')}`
}

export default function ResearchView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const quote = useQuote(symbol)
  const report = useResearchReport(symbol)
  const qc = useQueryClient()

  const [gen, setGen] = useState('')
  const [genState, setGenState] = useState<'idle' | 'loading' | 'error'>('idle')
  const abortRef = useRef<AbortController | null>(null)

  const name = report.data?.name || quote.data?.name || ''

  // 「复制 Prompt」：模板/技能按当前标的填充占位符后进剪贴板（粘到外部网页 Deep Research）
  const templates = useTemplates()
  const tpls = templates.data ?? []
  const skills = useSkills('yan', true) // 只取启用的「研」技能
  const sks = skills.data ?? []
  const hasAny = tpls.length + sks.length > 0
  const [tplOpen, setTplOpen] = useState(false)
  const tplRef = useRef<HTMLDivElement | null>(null)
  const toast = useToast((s) => s.push)
  useEffect(() => {
    if (!tplOpen) return
    const onDown = (e: PointerEvent) => {
      if (tplRef.current && !tplRef.current.contains(e.target as Node)) setTplOpen(false)
    }
    window.addEventListener('pointerdown', onDown)
    return () => window.removeEventListener('pointerdown', onDown)
  }, [tplOpen])
  const copyTpl = async (t: PromptTemplate) => {
    if (!symbol) return
    setTplOpen(false)
    try {
      await navigator.clipboard.writeText(fillTemplate(t.body, symbol, name))
      toast('已复制 Prompt')
    } catch {
      toast('复制失败', 'error')
    }
  }
  const copySkill = async (sk: SkillMeta) => {
    if (!symbol) return
    setTplOpen(false)
    try {
      const prompt = await renderSkill(sk.slug, symbol)
      await navigator.clipboard.writeText(prompt)
      toast(`已复制技能 · ${sk.name}`)
    } catch {
      toast('复制失败', 'error')
    }
  }
  // 单个来源时直接复制；多个时下拉选
  const onlyOne = tpls.length + sks.length === 1
  const copyTheOnlyOne = () => {
    if (sks.length === 1) copySkill(sks[0])
    else if (tpls.length === 1) copyTpl(tpls[0])
  }

  const runGenerate = async () => {
    if (!symbol) return
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setGen('')
    setGenState('loading')
    try {
      await streamResearch(symbol, (d) => setGen((p) => p + d), ac.signal)
      setGenState('idle')
      setGen('')
      qc.invalidateQueries({ queryKey: ['research', symbol] })
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setGen((e as Error).message)
      setGenState('error')
    }
  }

  if (!symbol) {
    return (
      <div className="research empty-stage">
        <div className="es-title">深度研究</div>
      </div>
    )
  }

  const streaming = genState === 'loading'
  const data = report.data

  return (
    <motion.div
      className="research"
      key={symbol}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="research-head">
        <div className="rh-id">
          <h2>{name || symbol}</h2>
          <span className="rh-sym">{symbol}</span>
          {data?.created_at && !streaming && (
            <span className="rh-when faint">{fmtWhen(data.created_at)} 生成</span>
          )}
        </div>
        <div className="rh-actions">
          {hasAny && (
            <div className="tpl-copy" ref={tplRef}>
              <button
                className="btn jsm"
                onClick={() => (onlyOne ? copyTheOnlyOne() : setTplOpen((v) => !v))}
              >
                复制 Prompt
              </button>
              {tplOpen && !onlyOne && (
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
          )}
          <button className="btn btn-primary jsm" disabled={streaming} onClick={runGenerate}>
            {streaming ? '研究中…' : data ? '重新生成' : '生成深度研究'}
          </button>
        </div>
      </div>

      {streaming || genState === 'error' ? (
        <div className={`report-card ${genState === 'error' ? 'err' : ''}`}>
          {genState === 'error' ? (
            <p>{gen}</p>
          ) : (
            <Markdown body={gen || '生成中…'} />
          )}
        </div>
      ) : data ? (
        <div className="report-card">
          <Markdown body={data.body} sources={data.sources} />
        </div>
      ) : report.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">暂无研究报告</div>
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <ImportedReports symbol={symbol} />
      </div>
    </motion.div>
  )
}
