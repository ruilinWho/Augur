import { create } from 'zustand'

// 「记」导航状态（非持久、随会话）：当前选中的笔记 id（null=未选/空态）。
interface NotesState {
  selectedId: number | null
  select: (id: number | null) => void
}

export const useNotesUI = create<NotesState>((set) => ({
  selectedId: null,
  select: (selectedId) => set({ selectedId }),
}))
