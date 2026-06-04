// 共享动效常量（与 index.css 的 cubic-bezier(0.22,1,0.36,1) 对齐）。
// easeOutExpo——柔和"落定"，不弹跳。各 motion.div 进场统一引用，别再各处重复声明。
export const EASE = [0.22, 1, 0.36, 1] as const
