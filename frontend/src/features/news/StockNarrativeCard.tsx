import { useState, type MouseEvent } from 'react'
import Collapse from '../../components/Collapse'
import { useGenerateNarrative, useNarrative } from '../../api'
import { NarrativeBody } from './NarrativeTimeline'

// 「看·个股」叙事时间线：复用「知」已生成的叙事（当前主线 + 带引用时间线），
// 没有则可就地生成——让「看」页自给自足，不必跳「知」。
export default function StockNarrativeCard({ symbol }: { symbol: string }) {
  const nar = useNarrative(symbol)
  const gen = useGenerateNarrative()
  const [open, setOpen] = useState(true)
  const data = nar.data
  const runGen = (e: MouseEvent) => {
    e.stopPropagation()
    gen.mutate(symbol)
  }
  return (
    <section className="stock-news">
      <div className="sec-head" onClick={() => setOpen((o) => !o)} role="button">
        <h3>叙事时间线</h3>
        {data?.item_count ? <span className="feed-count">{data.item_count} 条</span> : null}
        <button className="btn btn-ghost jsm stock-news-refresh" onClick={runGen} disabled={gen.isPending}>
          {gen.isPending ? '融合中…' : data ? '重新生成' : '生成叙事'}
        </button>
      </div>
      <Collapse open={open}>
        {gen.isError ? (
          <div className="stock-brief-empty">{(gen.error as Error).message}</div>
        ) : gen.isPending ? (
          <div className="fin-empty">融合中…</div>
        ) : data ? (
          <NarrativeBody data={data} />
        ) : nar.isLoading ? (
          <div className="fin-empty">加载…</div>
        ) : (
          <div className="stock-brief-empty">暂无叙事</div>
        )}
      </Collapse>
    </section>
  )
}
