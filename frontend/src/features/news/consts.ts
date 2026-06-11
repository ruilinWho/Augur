import type { InfoSection, NewsPrimary } from './store'

// 一级分类（rail）。资讯=按天看世界信息（二级=日期，三级=总结/新闻/推特），也是落地页；
// 个股=逐股叙事。（原「总览」与「资讯/今天/总结」内容重复，已合并掉。）
export const PRIMARIES: { id: NewsPrimary; label: string }[] = [
  { id: 'info', label: '资讯' },
  { id: 'stocks', label: '个股' },
]

export type SourceLaneId =
  | 'news'
  | 'blogs'
  | 'twitter'
  | 'reddit'
  | 'xiaohongshu'
  | 'threads'

// 资讯第三层：分三组（导航里用细线分隔）——① 总结（综合日报+今日机会，决策已并入）；
// ② 原始信源 lane（新闻+各社媒）；③ 博客（长文阅读卡，独立一类）。
export const INFO_SECTIONS: { id: InfoSection; label: string; group: string }[] = [
  { id: 'summary', label: '总结', group: 'digest' },
  { id: 'sectors', label: '分区', group: 'digest' },
  { id: 'news', label: '新闻', group: 'sources' },
  { id: 'twitter', label: '推特', group: 'sources' },
  { id: 'reddit', label: 'Reddit', group: 'sources' },
  { id: 'xiaohongshu', label: '小红书', group: 'sources' },
  { id: 'threads', label: 'Threads', group: 'sources' },
  { id: 'blogs', label: '博客', group: 'blog' },
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

export const FORUM_CATS: { key: string; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'forum', label: '论坛' },
  { key: 'ai', label: '大模型' },
  { key: 'chips', label: '芯片' },
  { key: 'markets', label: '行情' },
  { key: 'tech', label: '科技' },
]

export const SOURCE_LANES: Record<
  SourceLaneId,
  {
    label: string
    sourcePrefix?: string
    filters: { key: string; label: string }[]
    filterBy: 'theme' | 'category'
    live: boolean
  }
> = {
  news: { label: '新闻', filters: THEMES, filterBy: 'theme', live: true },
  blogs: { label: '博客', sourcePrefix: '博客·', filters: THEMES, filterBy: 'theme', live: true },
  twitter: { label: '推特', sourcePrefix: 'X·', filters: TW_CATS, filterBy: 'category', live: true },
  reddit: { label: 'Reddit', sourcePrefix: 'Reddit·', filters: FORUM_CATS, filterBy: 'category', live: true },
  xiaohongshu: { label: '小红书', sourcePrefix: '小红书·', filters: FORUM_CATS, filterBy: 'category', live: true },
  threads: { label: 'Threads', sourcePrefix: 'Threads·', filters: FORUM_CATS, filterBy: 'category', live: true },
}
