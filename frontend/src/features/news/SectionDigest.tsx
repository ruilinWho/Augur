import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUI } from '../../store'
import {
  useGenerateSectionReports,
  useQuote,
  useRefreshDirected,
  useRefreshNews,
  useSectionReports,
  type SectionBoard,
  type SectionMover,
} from '../../api'
import { CitedList } from './shared'

const fmtDate = (d: string) => {
  const [, m, day] = d.split('-')
  return `${Number(m)}月${Number(day)}日`
}
function dayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 重要性 → 徽章（与全局日报 / 后端 _IMP_ORDER 对齐）
const IMPORTANCE: Record<string, { label: string; cls: string }> = {
  critical: { label: '非常重要', cls: 'imp-critical' },
  high: { label: '重要', cls: 'imp-high' },
  med: { label: '留意', cls: 'imp-med' },
  low: { label: '次要', cls: 'imp-low' },
}
const MKT_BADGE: Record<string, string> = { US: '美', HK: '港', CN: 'A', KR: '韩' }

// 逐股异动：重要性徽章 · 名字→看 · 市场/二级板块 · 今日涨跌（仅今天）· 研 · 一句话发生了什么 · 分点。
function Mover({ m, isToday }: { m: SectionMover; isToday: boolean }) {
  const select = useUI((s) => s.select)
  const research = useUI((s) => s.research)
  // 历史日不取实时报价（报价只反映"现在"，挂到过去某天会误导）——传 null 即禁用查询
  const q = useQuote(isToday ? m.symbol : null)
  const imp = IMPORTANCE[m.importance] ?? IMPORTANCE.med
  const chg = q.data
  const dir = chg ? (chg.change > 0 ? 'up' : chg.change < 0 ? 'down' : 'flat') : 'flat'
  return (
    <article className="smover">
      <div className="smover-head">
        <span className={`rsec-imp ${imp.cls}`}>{imp.label}</span>
        <button className="smover-name" onClick={() => select(m.symbol)} title="在「看」里查看 K 线">
          <span className="wdot" />
          {m.name}
        </button>
        {m.market && <span className="smover-mkt">{MKT_BADGE[m.market] ?? m.market}</span>}
        {m.sub && <span className="smover-sub">{m.sub}</span>}
        {isToday && chg && (
          <span className={`smover-chg ${dir}`}>
            {chg.change_pct >= 0 ? '+' : ''}
            {chg.change_pct.toFixed(2)}%
          </span>
        )}
        <button className="smover-go" onClick={() => research(m.symbol)} title="深度研究这只股">
          研
        </button>
      </div>
      {m.headline && <p className="smover-headline">{m.headline}</p>}
      {m.points.length > 0 && <CitedList items={m.points} />}
    </article>
  )
}

// 一个一级分区的板块卡：分区名 + 异动数 + 板块脉搏 + 逐股异动 + 其余安静的票。
function BoardCard({ b, isToday }: { b: SectionBoard; isToday: boolean }) {
  return (
    <section className="sboard">
      <div className="sboard-head">
        <h3 className="sboard-name">{b.section_name}</h3>
        <span className="sboard-n">{b.movers.length} 异动</span>
      </div>
      {b.pulse && <p className="sboard-pulse">{b.pulse}</p>}
      <div className="sboard-movers">
        {b.movers.map((m) => (
          <Mover key={m.symbol} m={m} isToday={isToday} />
        ))}
      </div>
      {b.quiet.length > 0 && (
        <div className="sboard-quiet">
          <span className="sboard-quiet-l">其余安静</span>
          {b.quiet.join(' · ')}
        </div>
      )}
    </section>
  )
}

type GenStep = 'idle' | 'run' | 'done' | 'err'
const stepDot = (s: GenStep) => (s === 'done' ? '✓' : s === 'err' ? '✗' : '·')

// 资讯 · 某天「分区」：自选分区级日报。每个一级分区一张板块卡（按重要性排序），其余安静的分区收进页脚。
// 一键「刷新并生成」与「总结」同源（先刷新所有信源 + 自选定向，再每个分区并行蒸馏）。
function SectionReportsView({ date }: { date: string }) {
  const isToday = date === dayStr()
  const reports = useSectionReports(date)
  const gen = useGenerateSectionReports()
  const qc = useQueryClient()
  const refreshNews = useRefreshNews()
  const refreshDirected = useRefreshDirected()
  const [fetch, setFetch] = useState<GenStep>('idle')
  const [build, setBuild] = useState<GenStep>('idle')
  const running = [fetch, build].includes('run') || gen.isPending

  const run = async () => {
    setFetch('idle')
    setBuild('run')
    if (isToday) {
      setFetch('run')
      const r = await Promise.allSettled([
        refreshNews.mutateAsync(),
        refreshDirected.mutateAsync(undefined),
      ])
      setFetch(r.every((x) => x.status === 'rejected') ? 'err' : 'done')
      qc.invalidateQueries({ queryKey: ['news-feed'] })
    }
    try {
      await gen.mutateAsync(date)
      setBuild('done')
    } catch {
      setBuild('err')
    }
  }

  const boards = reports.data?.boards ?? []
  const active = boards.filter((b) => b.movers.length > 0)
  const quiet = boards.filter((b) => b.movers.length === 0)
  const hasAny = boards.length > 0

  return (
    <div className="know">
      <div className="sum-head">
        <div className="sum-title-line">
          <h2 className="sum-title">{isToday ? '今天' : fmtDate(date)} · 分区</h2>
        </div>
        <div className="sum-gen">
          {(running || build !== 'idle') && (
            <span className="sum-steps faint">
              {isToday && <>抓取 {stepDot(fetch)} · </>}分区日报 {stepDot(build)}
            </span>
          )}
          <button className="btn btn-primary jsm" disabled={running} onClick={run}>
            {running ? '生成中…' : isToday ? '刷新并生成分区日报' : '生成分区日报'}
          </button>
        </div>
      </div>

      {gen.isError && <div className="opp-err">{(gen.error as Error).message}</div>}

      {running && !hasAny ? (
        <div className="report-card faint">正在按分区蒸馏…（每个分区一次调用，约 30–60 秒）</div>
      ) : active.length > 0 ? (
        <>
          <div className="sboards">
            {active.map((b) => (
              <BoardCard key={b.section_id} b={b} isToday={isToday} />
            ))}
          </div>
          {quiet.length > 0 && (
            <div className="squiet">
              <span className="squiet-l">今日安静</span>
              <span className="squiet-items">{quiet.map((b) => b.section_name).join(' · ')}</span>
            </div>
          )}
        </>
      ) : hasAny ? (
        <div className="know-empty">
          <div className="ke-title">今天自选分区暂无明显动静</div>
          <div className="faint">{quiet.map((b) => b.section_name).join(' · ')}</div>
        </div>
      ) : reports.isLoading ? (
        <div className="report-card faint">加载…</div>
      ) : (
        <div className="know-empty">
          <div className="ke-title">暂无分区日报</div>
        </div>
      )}
    </div>
  )
}

export default SectionReportsView
