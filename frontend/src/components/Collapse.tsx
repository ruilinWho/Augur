import { type ReactNode } from 'react'

// 可折叠容器：grid-template-rows 0fr↔1fr 纯 CSS 过渡。
// ⚠️ 类名用 `.collapsible` 而非 `.collapse` —— Tailwind v4 内置 `.collapse` 工具类会设
// visibility:collapse 把内容隐藏掉（坑过一次）。也刻意不用 motion 的高度动画：在本项目
// motion + React 19 下 AnimatePresence 的 exit / animate 到 height:0 都不生效。grid 方案最稳。
export default function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div className="collapsible" data-open={String(open)}>
      <div className="collapsible-inner">{children}</div>
    </div>
  )
}
