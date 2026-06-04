import { useEffect } from 'react'
import { motion } from 'motion/react'
import { create } from 'zustand'

// 轻量全局 toast：给静默失败的变更（自选重命名撞名 409、加股已存在 422…）一个温和反馈，
// 而非无声回滚（§11 暴露不确定性）。克制：右下角、几秒淡出、陶土/警示色。
type Kind = 'info' | 'error'
interface ToastItem {
  id: number
  msg: string
  kind: Kind
}
interface ToastState {
  items: ToastItem[]
  push: (msg: string, kind?: Kind) => void
  dismiss: (id: number) => void
}

let _seq = 1
export const useToast = create<ToastState>((set) => ({
  items: [],
  push: (msg, kind = 'info') =>
    set((s) => ({ items: [...s.items, { id: _seq++, msg, kind }].slice(-4) })),
  dismiss: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
}))

// 便捷：在非组件处（如 api 钩子 onError）直接报错
export const toastError = (msg: string) => useToast.getState().push(msg, 'error')

function Row({ t }: { t: ToastItem }) {
  const dismiss = useToast((s) => s.dismiss)
  useEffect(() => {
    const id = window.setTimeout(() => dismiss(t.id), 4200)
    return () => window.clearTimeout(id)
  }, [t.id, dismiss])
  return (
    <motion.div
      className={`toast ${t.kind}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      onClick={() => dismiss(t.id)}
      role="status"
    >
      {t.msg}
    </motion.div>
  )
}

// 不用 AnimatePresence/exit（本项目 motion+React19 下 exit 不触发，见 frontend-gotchas）；
// 进场淡入 + 到点直接移除即可。
export default function Toaster() {
  const items = useToast((s) => s.items)
  return (
    <div className="toaster">
      {items.map((t) => (
        <Row key={t.id} t={t} />
      ))}
    </div>
  )
}
