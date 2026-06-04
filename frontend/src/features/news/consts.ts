import type { InfoSection, NewsPrimary } from './store'

// 一级分类（rail）。资讯=按天看世界信息（二级=日期，三级=总结/新闻/推特），也是落地页；
// 个股=逐股叙事。（原「总览」与「资讯/今天/总结」内容重复，已合并掉。）
export const PRIMARIES: { id: NewsPrimary; label: string }[] = [
  { id: 'info', label: '资讯' },
  { id: 'stocks', label: '个股' },
]

// 资讯第三层：某天的「总结」+ 构成它的原始信源。未来在此加 reddit/雪球…
export const INFO_SECTIONS: { id: InfoSection; label: string }[] = [
  { id: 'summary', label: '总结' },
  { id: 'news', label: '新闻' },
  { id: 'twitter', label: '推特' },
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
