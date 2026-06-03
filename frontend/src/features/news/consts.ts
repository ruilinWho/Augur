import type { NewsPrimary } from './store'

// 一级分类（列1）。hasSub=是否有二级卡片（列2）。
export const PRIMARIES: { id: NewsPrimary; label: string; hasSub: boolean }[] = [
  { id: 'overview', label: '总览', hasSub: false },
  { id: 'stocks', label: '个股', hasSub: true },
  { id: 'digest', label: '每日', hasSub: true },
  { id: 'news', label: '新闻', hasSub: true },
  { id: 'twitter', label: '推特', hasSub: true },
]

// 新闻二级：主题。key='' = 全部。与后端 classify 主题键一致。
export const THEMES: { key: string; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'ai', label: '大模型' },
  { key: 'chips', label: '芯片' },
  { key: 'robotics', label: '机器人' },
  { key: 'space', label: '航天' },
  { key: 'macro', label: '宏观' },
  { key: 'markets', label: '行情' },
  { key: 'tech', label: '科技' },
  { key: 'world', label: '国际' },
]

// 推特二级：账号分类（与 resources/sources/x_accounts.yaml 的 category 一致）。key=''=全部。
export const TW_CATS: { key: string; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'ai', label: '大模型' },
  { key: 'chips', label: '芯片' },
  { key: 'space', label: '航天' },
  { key: 'robotics', label: '机器人' },
]

export const themeLabel = (k: string) => THEMES.find((t) => t.key === k)?.label ?? k
