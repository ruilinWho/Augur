import { create } from 'zustand'

// 「知」导航（非持久、随会话）。三层 Miller：
//   一级 primary：总览 / 个股 / 资讯
//   · 个股 → 二级 stockSym（选中的标的）
//   · 资讯 → 二级 infoDate（日期，null=今天）+ 三级 infoSection（总结/决策/各信源 lane…）
//   · 总览 → 无二级
export type NewsPrimary = 'info' | 'stocks'
// 资讯第三层：日的「总结」（综合日报+今日机会）+「分区」（自选分区级日报）+ 原始信源 lane
export type InfoSection =
  | 'summary'
  | 'sectors'
  | 'radar'
  | 'news'
  | 'blogs'
  | 'twitter'
  | 'reddit'
  | 'xiaohongshu'
  | 'threads'

interface NewsState {
  primary: NewsPrimary
  stockSym: string | null // 个股：选中标的
  infoDate: string | null // 资讯：选中日期（null=今天）
  infoSection: InfoSection // 资讯：第三层
  navCollapsed: boolean // 收起 日期/板块/标的 选择栏，让主内容延展
  setPrimary: (p: NewsPrimary) => void
  setStockSym: (s: string) => void
  setInfoDate: (d: string | null) => void
  setInfoSection: (s: InfoSection) => void
  toggleNav: () => void
}

export const useNews = create<NewsState>((set) => ({
  primary: 'info',
  stockSym: null,
  infoDate: null,
  infoSection: 'summary',
  navCollapsed: false,
  setPrimary: (primary) => set({ primary }),
  setStockSym: (stockSym) => set({ stockSym }),
  setInfoDate: (infoDate) => set({ infoDate }),
  setInfoSection: (infoSection) => set({ infoSection }),
  toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),
}))
