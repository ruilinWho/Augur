import { useMemo, type ReactNode } from 'react'

// 共享轻量 Markdown 渲染（无依赖）：## 标题 / # 标题 / > 引用 / - 列表 / |表格| / --- 分隔 /
// 段落，行内支持 **加粗** · 裸链接 · [n] 引用上标（给了 sources 且该 n 有 url 则可点跳来源）。
// 研报（带编号引用）、导入研报、「记」长文笔记共用——单一真相，避免多份手写解析漂移。
export type CiteSource = { n: number; url?: string | null }

function inline(text: string, srcUrl: (n: number) => string | null): ReactNode[] {
  // 先按 **加粗** / 裸 URL / [n] 切分，逐段渲染
  const parts = text.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s)]+|\[\d+\])/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) return <strong key={i}>{p.slice(2, -2)}</strong>
    if (/^https?:\/\//.test(p))
      return (
        <a key={i} className="cite-link" href={p} target="_blank" rel="noreferrer">
          原文
        </a>
      )
    const m = p.match(/^\[(\d+)\]$/)
    if (m) {
      const n = Number(m[1])
      const url = srcUrl(n)
      const chip = <sup className="cite">[{n}]</sup>
      return url ? (
        <a key={i} href={url} target="_blank" rel="noreferrer" className="cite-a" title="查看来源">
          {chip}
        </a>
      ) : (
        <span key={i}>{chip}</span>
      )
    }
    return <span key={i}>{p}</span>
  })
}

export default function Markdown({
  body,
  sources = [],
  className = '',
}: {
  body: string
  sources?: CiteSource[]
  className?: string
}) {
  const srcUrl = useMemo(() => {
    const map = new Map<number, string>()
    for (const s of sources) if (s.url) map.set(s.n, s.url)
    return (n: number) => map.get(n) ?? null
  }, [sources])

  const blocks: ReactNode[] = []
  let list: string[] = []
  let quote: string[] = []
  let table: string[] = []

  const flushList = () => {
    if (!list.length) return
    const items = list
    blocks.push(
      <ul key={`u${blocks.length}`}>
        {items.map((t, i) => (
          <li key={i}>{inline(t, srcUrl)}</li>
        ))}
      </ul>,
    )
    list = []
  }
  const flushQuote = () => {
    if (!quote.length) return
    const items = quote
    blocks.push(
      <blockquote key={`q${blocks.length}`}>
        {items.map((t, i) => (
          <p key={i}>{inline(t, srcUrl)}</p>
        ))}
      </blockquote>,
    )
    quote = []
  }
  const flushTable = () => {
    if (!table.length) return
    const rows = table
      .map((r) =>
        r
          .trim()
          .replace(/^\||\|$/g, '')
          .split('|')
          .map((c) => c.trim()),
      )
      // 分隔行（---|---）丢弃
      .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c) || c === ''))
    const [head, ...rest] = rows
    blocks.push(
      <div key={`tb${blocks.length}`} className="rep-table-wrap">
        <table className="rep-table">
          {head && (
            <thead>
              <tr>
                {head.map((c, i) => (
                  <th key={i}>{inline(c, srcUrl)}</th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rest.map((cells, r) => (
              <tr key={r}>
                {cells.map((c, i) => (
                  <td key={i}>{inline(c, srcUrl)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
    table = []
  }
  const flushAll = () => {
    flushList()
    flushQuote()
    flushTable()
  }

  body.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (!line) return flushAll()
    if (line.startsWith('|') && line.includes('|', 1)) {
      flushList()
      flushQuote()
      table.push(line)
      return
    }
    flushTable()
    if (line === '---' || line === '***') {
      flushAll()
      blocks.push(<hr key={`h${i}`} />)
    } else if (line.startsWith('> ') || line === '>') {
      flushList()
      quote.push(line.replace(/^>\s?/, ''))
    } else if (line.startsWith('## ')) {
      flushAll()
      blocks.push(<h4 key={`t${i}`}>{line.replace(/^##\s+/, '')}</h4>)
    } else if (line.startsWith('# ')) {
      flushAll()
      blocks.push(<h3 key={`t${i}`}>{line.replace(/^#\s+/, '')}</h3>)
    } else if (/^[-*]\s+/.test(line)) {
      flushQuote()
      list.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flushAll()
      blocks.push(<p key={`p${i}`}>{inline(line, srcUrl)}</p>)
    }
  })
  flushAll()
  return <div className={`digest report ${className}`}>{blocks}</div>
}
