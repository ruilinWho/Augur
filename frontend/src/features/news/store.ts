import { create } from 'zustand'

// 「知」两级导航状态（非持久、随会话）。
//   primary：一级分类（列1）。secondary：二级选项（列2），语义随 primary 变：
//     digest  → 日期串（null=最新）   news → theme（null=全部）   twitter → 账号分类（null=全部）
//     overview / opps → 无二级（secondary 恒 null）
export type NewsPrimary = 'overview' | 'digest' | 'news' | 'twitter' | 'opps'

interface NewsState {
  primary: NewsPrimary
  secondary: string | null
  setPrimary: (p: NewsPrimary) => void
  setSecondary: (s: string | null) => void
}

export const useNews = create<NewsState>((set) => ({
  primary: 'overview',
  secondary: null,
  // 切一级时把二级重置为该级默认（null＝最新/全部）
  setPrimary: (primary) => set({ primary, secondary: null }),
  setSecondary: (secondary) => set({ secondary }),
}))
