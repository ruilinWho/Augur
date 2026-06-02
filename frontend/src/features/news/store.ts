import { create } from 'zustand'

// 「知」视图的轻量本地状态：当前选中的日报日期（null = 最新一份）。
// 不进全局 useUI（非持久、随会话即可）。
interface NewsState {
  selectedDate: string | null
  setSelectedDate: (d: string | null) => void
}

export const useNews = create<NewsState>((set) => ({
  selectedDate: null,
  setSelectedDate: (selectedDate) => set({ selectedDate }),
}))
