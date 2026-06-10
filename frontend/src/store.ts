import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type View = 'kan' | 'yan' | 'zhi' | 'ji' | 'set'
export type Market = 'ALL' | 'US' | 'HK' | 'CN' | 'KR'
export type Theme = 'light' | 'dark'
export type DisplayFont = 'serif' | 'sans'
export type Convention = 'us' | 'cn' // us: 绿涨红跌；cn: 红涨绿跌
export type SettingsPage = 'all' | 'appearance' | 'models' | 'sources' | 'templates' | 'schedule'

export const PANEL_MIN = 208
export const PANEL_MAX = 520
export const NEWS_SUB_MIN = 140
export const NEWS_SUB_MAX = 360
export const SRC_NAV_MIN = 120
export const SRC_NAV_MAX = 320
export const KAN_COL_MIN = 96
export const KAN_COL_MAX = 420
export const DEFAULT_PANEL_W = 268
export const DEFAULT_NEWS_SUB_W = 196
export const DEFAULT_SRC_NAV_W = 184
export const DEFAULT_KAN_COL_W: [number, number, number] = [156, 150, 248]
export const DEFAULT_KAN_COL_CLOSED: [boolean, boolean, boolean] = [false, false, false]
export const KAN_MODULES = ['financials', 'news', 'journal'] as const
export type KanModuleId = (typeof KAN_MODULES)[number]
export const DEFAULT_KAN_MODULE_OPEN: Record<KanModuleId, boolean> = {
  financials: true,
  news: true,
  journal: true,
}

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
  kanColW: [number, number, number] // 「看」自选三列宽度 [一级,二级,标的]，可拖拽
  kanColClosed: [boolean, boolean, boolean] // 「看」三列是否收起
  kanOrder: string[] // 「看」页 K 线下方模块顺序（可拖拽），持久化
  kanModuleOpen: Record<KanModuleId, boolean> // 「看」页下方模块展开状态，换股不重置
  settingsPage: SettingsPage // 「设置」当前页（左栏导航选择，瞬时不持久化）
  lastSeenNewsAt: string | null // 「知」上次查看时间（ISO，持久化）——用于「自上次以来」增量

  setView: (v: View) => void
  select: (s: string) => void
  research: (s: string) => void // 选标的并直接进「研」（机会卡直通研）
  pickInView: (s: string) => void // 选标的但**留在当前视图**（看/研）——左栏点股不再弹回看
  setMarket: (m: Market) => void
  setTheme: (t: Theme) => void
  setTextBase: (n: number) => void
  setLeading: (n: number) => void
  setDisplayFont: (f: DisplayFont) => void
  setConvention: (c: Convention) => void
  setPanelW: (n: number) => void
  setNewsSubW: (n: number) => void
  setSrcNavW: (n: number) => void
  setKanColW: (i: 0 | 1 | 2, n: number) => void
  toggleKanCol: (i: 0 | 1 | 2) => void
  setKanOrder: (o: string[]) => void
  setKanModuleOpen: (id: KanModuleId, open: boolean) => void
  resetLayout: () => void
  setSettingsPage: (p: SettingsPage) => void
  markNewsSeen: () => void // 把「自上次以来」基准推到此刻
}

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
      panelW: DEFAULT_PANEL_W,
      newsSubW: DEFAULT_NEWS_SUB_W,
      srcNavW: DEFAULT_SRC_NAV_W,
      kanColW: [...DEFAULT_KAN_COL_W],
      kanColClosed: [...DEFAULT_KAN_COL_CLOSED],
      kanOrder: [...KAN_MODULES],
      kanModuleOpen: { ...DEFAULT_KAN_MODULE_OPEN },
      settingsPage: 'all',
      lastSeenNewsAt: null,

      setView: (view) => set({ view }),
      select: (selectedSymbol) => set({ selectedSymbol, view: 'kan' }),
      research: (selectedSymbol) => set({ selectedSymbol, view: 'yan' }),
      pickInView: (selectedSymbol) =>
        set((s) => ({ selectedSymbol, view: s.view === 'yan' ? 'yan' : 'kan' })),
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
      setKanColW: (i, n) =>
        set((s) => {
          const w = [...s.kanColW] as [number, number, number]
          w[i] = Math.max(KAN_COL_MIN, Math.min(KAN_COL_MAX, Math.round(n)))
          return { kanColW: w }
        }),
      toggleKanCol: (i) =>
        set((s) => {
          const c = [...s.kanColClosed] as [boolean, boolean, boolean]
          c[i] = !c[i]
          return { kanColClosed: c }
        }),
      setKanOrder: (kanOrder) => set({ kanOrder }),
      setKanModuleOpen: (id, open) =>
        set((s) => ({ kanModuleOpen: { ...s.kanModuleOpen, [id]: open } })),
      resetLayout: () =>
        set({
          panelW: DEFAULT_PANEL_W,
          newsSubW: DEFAULT_NEWS_SUB_W,
          srcNavW: DEFAULT_SRC_NAV_W,
          kanColW: [...DEFAULT_KAN_COL_W],
          kanColClosed: [...DEFAULT_KAN_COL_CLOSED],
          kanOrder: [...KAN_MODULES],
          kanModuleOpen: { ...DEFAULT_KAN_MODULE_OPEN },
        }),
      setSettingsPage: (settingsPage) => set({ settingsPage }),
      markNewsSeen: () => set({ lastSeenNewsAt: new Date().toISOString() }),
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
        kanColW: s.kanColW,
        kanColClosed: s.kanColClosed,
        kanOrder: s.kanOrder,
        kanModuleOpen: s.kanModuleOpen,
        lastSeenNewsAt: s.lastSeenNewsAt,
      }),
    },
  ),
)
