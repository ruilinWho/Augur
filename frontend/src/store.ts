import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type View = 'kan' | 'yan' | 'zhi' | 'set'
export type Market = 'ALL' | 'US' | 'HK' | 'CN' | 'KR'
export type Theme = 'light' | 'dark'
export type DisplayFont = 'serif' | 'sans'
export type Convention = 'us' | 'cn' // us: 绿涨红跌；cn: 红涨绿跌
export type SettingsPage = 'appearance' | 'models' | 'sources'

export const PANEL_MIN = 208
export const PANEL_MAX = 520
export const NEWS_SUB_MIN = 140
export const NEWS_SUB_MAX = 360
export const SRC_NAV_MIN = 120
export const SRC_NAV_MAX = 320

interface UIState {
  view: View
  selectedSymbol: string | null
  market: Market
  // ── Meta 设置（持久化）──
  theme: Theme
  textBase: number
  leading: number
  displayFont: DisplayFont
  convention: Convention
  panelW: number // 左栏宽度（px），可拖拽调整
  newsSubW: number // 「知」二级卡宽度（px），可拖拽调整
  srcNavW: number // 「设置·数据/信源」二级菜单宽度（px），可拖拽调整
  kanOrder: string[] // 「看」页 K 线下方模块顺序（可拖拽），持久化
  settingsPage: SettingsPage // 「设置」当前页（左栏导航选择，瞬时不持久化）

  setView: (v: View) => void
  select: (s: string) => void
  setMarket: (m: Market) => void
  setTheme: (t: Theme) => void
  setTextBase: (n: number) => void
  setLeading: (n: number) => void
  setDisplayFont: (f: DisplayFont) => void
  setConvention: (c: Convention) => void
  setPanelW: (n: number) => void
  setNewsSubW: (n: number) => void
  setSrcNavW: (n: number) => void
  setKanOrder: (o: string[]) => void
  setSettingsPage: (p: SettingsPage) => void
}

export const KAN_MODULES = ['financials', 'news', 'journal'] as const

export const useUI = create<UIState>()(
  persist(
    (set) => ({
      view: 'kan',
      selectedSymbol: null,
      market: 'ALL',
      theme: 'light',
      textBase: 16,
      leading: 1.62,
      displayFont: 'serif',
      convention: 'us',
      panelW: 268,
      newsSubW: 196,
      srcNavW: 184,
      kanOrder: [...KAN_MODULES],
      settingsPage: 'appearance',

      setView: (view) => set({ view }),
      select: (selectedSymbol) => set({ selectedSymbol, view: 'kan' }),
      setMarket: (market) => set({ market }),
      setTheme: (theme) => set({ theme }),
      setTextBase: (textBase) => set({ textBase }),
      setLeading: (leading) => set({ leading }),
      setDisplayFont: (displayFont) => set({ displayFont }),
      setConvention: (convention) => set({ convention }),
      setPanelW: (panelW) =>
        set({ panelW: Math.max(PANEL_MIN, Math.min(PANEL_MAX, Math.round(panelW))) }),
      setNewsSubW: (newsSubW) =>
        set({ newsSubW: Math.max(NEWS_SUB_MIN, Math.min(NEWS_SUB_MAX, Math.round(newsSubW))) }),
      setSrcNavW: (srcNavW) =>
        set({ srcNavW: Math.max(SRC_NAV_MIN, Math.min(SRC_NAV_MAX, Math.round(srcNavW))) }),
      setKanOrder: (kanOrder) => set({ kanOrder }),
      setSettingsPage: (settingsPage) => set({ settingsPage }),
    }),
    {
      name: 'augur-ui',
      partialize: (s) => ({
        theme: s.theme,
        textBase: s.textBase,
        leading: s.leading,
        displayFont: s.displayFont,
        convention: s.convention,
        market: s.market,
        panelW: s.panelW,
        newsSubW: s.newsSubW,
        srcNavW: s.srcNavW,
        kanOrder: s.kanOrder,
      }),
    },
  ),
)
