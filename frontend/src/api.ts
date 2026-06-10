import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { toastError } from './components/Toast'

// 变更失败统一弹 toast（自选重命名撞名 409、加股已存在 422…不再静默回滚，§11 暴露不确定性）
const onMutErr = (e: unknown) => toastError((e as Error).message)

// ───────────────────────── HTTP 助手（开发期经 Vite 代理到 :8788）─────────────────────────
// 携带 HTTP 状态码的错误：让「404=暂无（空态）vs 其它=真错误」靠 status 判定，而非脆弱的中文
// detail 子串匹配（后端改文案就会让空态突然报红）。
export class HttpError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}

async function getJSON(url: string): Promise<unknown> {
  const r = await fetch(url)
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new HttpError(d.detail ?? `HTTP ${r.status}`, r.status)
  }
  return r.json()
}

async function send(url: string, method: string, body?: unknown): Promise<unknown> {
  const r = await fetch(url, {
    method,
    headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new HttpError(d.detail ?? `HTTP ${r.status}`, r.status)
  }
  return r.status === 204 ? null : r.json()
}

// 消费一个 SSE 流：逐 `data:` 帧解析 {delta|error}；delta→onDelta、[DONE]→结束、error→抛出
// （三处流式复用，单一真相）。关键修复：error 检测移出 JSON.parse 的 try/catch——此前 throw 被同
// 块 catch 当「非 JSON」吞掉，导致后端推送的错误帧静默丢失、前端永不进 error 态（违 §11）。
async function consumeSSE(r: Response, onDelta: (text: string) => void): Promise<void> {
  if (!r.body) throw new Error('无响应流')
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() ?? ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (payload === '[DONE]') return
        let obj: { delta?: string; error?: string }
        try {
          obj = JSON.parse(payload)
        } catch {
          continue // 半行/非 JSON，忽略
        }
        if (obj.error) throw new Error(obj.error) // 真正冒泡到调用方的 catch → 进 error 态
        if (obj.delta) onDelta(obj.delta)
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* 已被 cancel/锁释放 */
    }
  }
}

// ───────────────────────── schemas ─────────────────────────
const candleSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
})
const ohlcvSchema = z.object({
  symbol: z.string(),
  interval: z.string(),
  source: z.string(),
  cached: z.boolean(),
  candles: z.array(candleSchema),
})
const quoteSchema = z.object({
  symbol: z.string(),
  name: z.string().default(''),
  price: z.number(),
  change: z.number(),
  change_pct: z.number(),
  time: z.string(),
  source: z.string(),
})
const itemSchema = z.object({
  id: z.number(),
  symbol: z.string(),
  note: z.string(),
  sort_order: z.number(),
})
export type Item = z.infer<typeof itemSchema>
export type Section = {
  id: number
  name: string
  parent_id: number | null
  sort_order: number
  items: Item[]
  children: Section[]
}
const sectionSchema: z.ZodType<Section> = z.lazy(() =>
  z.object({
    id: z.number(),
    name: z.string(),
    parent_id: z.number().nullable(),
    sort_order: z.number(),
    items: z.array(itemSchema),
    children: z.array(sectionSchema),
  }),
)
const roleSchema = z.object({
  role: z.string(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  configured: z.boolean(),
})
const searchHitSchema = z.object({
  symbol: z.string(),
  market: z.string(),
  code: z.string(),
  name: z.string(),
  sub: z.string(),
})
const searchRespSchema = z.object({
  query: z.string(),
  indexing: z.boolean(),
  results: z.array(searchHitSchema),
})

const journalSchema = z.object({
  id: z.number(),
  symbol: z.string(),
  entry_date: z.string(),
  body: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
})
const fundamentalsSchema = z.object({
  symbol: z.string(),
  market_cap: z.number().nullable(),
  pe: z.number().nullable(),
  revenue: z.number().nullable(),
  net_income: z.number().nullable(),
  net_margin: z.number().nullable(),
  eps: z.number().nullable(),
  currency: z.string(),
})
const finPeriodSchema = z.object({
  period: z.string(),
  revenue: z.number().nullable(),
  revenue_growth: z.number().nullable(),
  net_income: z.number().nullable(),
  net_margin: z.number().nullable(),
  eps: z.number().nullable(),
  eps_growth: z.number().nullable(),
  fcf: z.number().nullable(),
})
const financialsSchema = z.object({
  symbol: z.string(),
  period: z.string().default('quarter'), // 'quarter' | 'annual'
  currency: z.string(),
  periods: z.array(finPeriodSchema),
  links: z.array(z.object({ label: z.string(), url: z.string() })),
})

export type Candle = z.infer<typeof candleSchema>
export type Ohlcv = z.infer<typeof ohlcvSchema>
export type Quote = z.infer<typeof quoteSchema>
export type RoleStatus = z.infer<typeof roleSchema>
export type SearchHit = z.infer<typeof searchHitSchema>
export type SearchResp = z.infer<typeof searchRespSchema>
export type JournalEntry = z.infer<typeof journalSchema>
export type Fundamentals = z.infer<typeof fundamentalsSchema>
export type FinancialsTable = z.infer<typeof financialsSchema>
export type FinPeriod = z.infer<typeof finPeriodSchema>

// ───────────────────────── 查询钩子 ─────────────────────────
export function useSections(market: string) {
  return useQuery({
    queryKey: ['sections', market],
    queryFn: async () => z.array(sectionSchema).parse(await getJSON(`/watchlist/sections?market=${market}`)),
  })
}

export function useOhlcv(symbol: string | null, interval: string, range: string) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['ohlcv', symbol, interval, range],
    queryFn: async () =>
      ohlcvSchema.parse(
        await getJSON(
          `/market/ohlcv?symbol=${encodeURIComponent(symbol!)}&interval=${interval}&range=${range}`,
        ),
      ),
    retry: 1,
  })
}

export function useQuote(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['quote', symbol],
    queryFn: async () => quoteSchema.parse(await getJSON(`/market/quote?symbol=${encodeURIComponent(symbol!)}`)),
    retry: 1,
  })
}

export function useFundamentals(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['fundamentals', symbol],
    queryFn: async () =>
      fundamentalsSchema.parse(
        await getJSON(`/market/fundamentals?symbol=${encodeURIComponent(symbol!)}`),
      ),
    staleTime: 30 * 60_000,
    retry: 1,
  })
}

export function useFinancials(symbol: string | null, period: 'quarter' | 'annual' = 'quarter') {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['financials', symbol, period],
    queryFn: async () =>
      financialsSchema.parse(
        await getJSON(
          `/market/financials?symbol=${encodeURIComponent(symbol!)}&period=${period}`,
        ),
      ),
    staleTime: 30 * 60_000,
    retry: 1,
  })
}

// 流式对话（SSE）：把 /llm/chat 的 data: {delta} 增量回调出去。失败/中断抛错。
export async function streamChat(
  messages: { role: string; content: string }[],
  role: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch('/llm/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ messages, role }),
    signal,
  })
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new Error(d.detail ?? `HTTP ${r.status}`)
  }
  await consumeSSE(r, onDelta)
}

// ───────────────────────── 设置 · API 配置（LLM 连接 + 数据信源）─────────────────────────
const connectionSchema = z.object({
  id: z.string(),
  name: z.string().default(''),
  base_url: z.string().default(''),
  model: z.string().default(''),
  key_configured: z.boolean(),
  key_hint: z.string().default(''),
  api_key: z.string().default(''), // 明文（仅本地单用户 UI 回显）
  web_search: z.boolean().default(false), // 联网检索（Qwen enable_search 等）
})
const roleTargetSchema = z.object({
  role: z.string(),
  connection_id: z.string().nullable().default(null),
  connection_name: z.string().nullable().default(null),
  configured: z.boolean(),
})
// 信源可配置项（账户/关键词…）。value 元素：accounts=对象 {screen_name,category}；tags=字符串
const sourceConfigFieldSchema = z.object({
  field: z.string(),
  type: z.string(),
  label: z.string(),
  value: z.array(z.any()).default([]),
})
const sourceStatusSchema = z.object({
  id: z.string(),
  name: z.string(),
  group: z.string().default('news'),
  access: z.string(),
  key_env: z.string().nullable().default(null),
  cred: z.string().default(''),
  key_url: z.string().default(''),
  docs_url: z.string().default(''),
  official_url: z.string().default(''),
  secret_label: z.string().default(''),
  secret_placeholder: z.string().default(''),
  secret_help: z.string().default(''),
  setup: z.string().default(''),
  best_use: z.string().default(''),
  boundary: z.string().default(''),
  note: z.string().default(''),
  payment: z.string().default(''),
  configured: z.boolean(),
  status: z.string(),
  hint: z.string().default(''),
  key_value: z.string().default(''), // 明文 key（仅本地单用户 UI 回显）
  config: z.array(sourceConfigFieldSchema).default([]),
})
export type SourceConfigField = z.infer<typeof sourceConfigFieldSchema>
export type TwAccount = { screen_name: string; category: string }
const sourceGroupSchema = z.object({
  id: z.string(),
  label: z.string(),
  blurb: z.string().default(''),
})
const settingsConfigSchema = z.object({
  llm: z.object({
    connections: z.array(connectionSchema),
    roles: z.array(roleTargetSchema),
  }),
  sources: z.array(sourceStatusSchema),
  source_groups: z.array(sourceGroupSchema).default([]),
})
export type Connection = z.infer<typeof connectionSchema>
export type RoleTarget = z.infer<typeof roleTargetSchema>
export type SourceStatus = z.infer<typeof sourceStatusSchema>
export type SourceGroup = z.infer<typeof sourceGroupSchema>
export type TestResult = { ok: boolean; latency_ms?: number; reply?: string; error?: string }

export function useSettingsConfig() {
  return useQuery({
    queryKey: ['settings-config'],
    queryFn: async () => settingsConfigSchema.parse(await getJSON('/settings/config')),
    staleTime: 30_000,
  })
}

// 自动刷新调度（白天每小时「全部生成」）：{enabled, start_hour, end_hour}
const scheduleSchema = z.object({
  enabled: z.boolean().default(true),
  start_hour: z.number().default(11),
  end_hour: z.number().default(23),
  cluster_input_max: z.number().default(1000), // 要事/机会喂 LLM 的当日条数上限（0=不限）
  brief_top_n: z.number().default(5), // 今日要事显示条数
})
export type Schedule = z.infer<typeof scheduleSchema>

export function useSchedule() {
  return useQuery({
    queryKey: ['settings-schedule'],
    queryFn: async () => scheduleSchema.parse(await getJSON('/settings/schedule')),
    staleTime: 30_000,
  })
}

export function useSetSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch: Partial<Schedule>) =>
      scheduleSchema.parse(await send('/settings/schedule', 'POST', patch)),
    onSuccess: (data) => qc.setQueryData(['settings-schedule'], data),
  })
}

// LLM token 用量（§6 看成本）：按角色/模型聚合最近 days 天
const usageRowSchema = z.object({
  role: z.string().default(''),
  model: z.string().default(''),
  calls: z.number().default(0),
  prompt_tokens: z.number().nullable().default(0),
  completion_tokens: z.number().nullable().default(0),
  cost_usd: z.number().nullable().default(0),
})
const usageSchema = z.object({
  days: z.number().default(30),
  total: z
    .object({
      calls: z.number().nullable().default(0),
      prompt_tokens: z.number().nullable().default(0),
      completion_tokens: z.number().nullable().default(0),
      cost_usd: z.number().nullable().default(0),
    })
    .default({}),
  by_role_model: z.array(usageRowSchema).default([]),
})
export type LlmUsage = z.infer<typeof usageSchema>
export function useLlmUsage(days = 30) {
  return useQuery({
    queryKey: ['llm-usage', days],
    queryFn: async () => usageSchema.parse(await getJSON(`/llm/usage?days=${days}`)),
    staleTime: 60_000,
  })
}

function useInvalidateSettings() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: ['settings-config'] })
}

export function useUpsertConnection() {
  const invalidate = useInvalidateSettings()
  return useMutation({
    mutationFn: (v: {
      id?: string
      name: string
      base_url: string
      api_key?: string | null
      model: string
      web_search?: boolean
    }) => send('/settings/llm/connection', 'POST', v),
    onSuccess: invalidate,
  })
}

export function useDeleteConnection() {
  const invalidate = useInvalidateSettings()
  return useMutation({
    mutationFn: (id: string) => send(`/settings/llm/connection/${id}`, 'DELETE'),
    onSuccess: invalidate,
  })
}

type SettingsConfig = z.infer<typeof settingsConfigSchema>

// 拖拽重排连接：乐观更新 settings-config 缓存（避免松手时卡片回弹闪烁），出错回滚
export function useReorderConnections() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (orderedIds: string[]) =>
      send('/settings/llm/connections/reorder', 'POST', { ordered_ids: orderedIds }),
    onMutate: async (orderedIds: string[]) => {
      await qc.cancelQueries({ queryKey: ['settings-config'] })
      const prev = qc.getQueryData<SettingsConfig>(['settings-config'])
      if (prev) {
        const byId = new Map(prev.llm.connections.map((c) => [c.id, c]))
        const conns = orderedIds.map((id) => byId.get(id)).filter((c): c is Connection => !!c)
        for (const c of prev.llm.connections) if (!orderedIds.includes(c.id)) conns.push(c)
        qc.setQueryData<SettingsConfig>(['settings-config'], {
          ...prev,
          llm: { ...prev.llm, connections: conns },
        })
      }
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(['settings-config'], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['settings-config'] }),
  })
}

export function useSetSourceConfig() {
  const invalidate = useInvalidateSettings()
  return useMutation({
    mutationFn: (v: { id: string; field: string; value: unknown[] }) =>
      send('/settings/source/config', 'POST', v),
    onSuccess: invalidate,
  })
}

export function useSetRoleTarget() {
  const invalidate = useInvalidateSettings()
  return useMutation({
    mutationFn: (v: { role: string; connection_id: string | null }) =>
      send('/settings/llm/role', 'POST', v),
    onSuccess: invalidate,
  })
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (v: {
      connection_id?: string
      base_url?: string
      api_key?: string
      model?: string
    }) => (await send('/settings/llm/test', 'POST', v)) as TestResult,
  })
}

// 测试全部连接（后端并发探活），返回 {连接id: 结果}
export function useTestAllConnections() {
  return useMutation({
    mutationFn: async () =>
      (await send('/settings/llm/test-all', 'POST')) as Record<string, TestResult>,
  })
}

export function useSetSecret() {
  const invalidate = useInvalidateSettings()
  return useMutation({
    mutationFn: (v: { name: string; value: string | null }) => send('/settings/secret', 'POST', v),
    onSuccess: invalidate,
  })
}

export function useSearch(query: string, market: string) {
  const q = query.trim()
  return useQuery({
    enabled: q.length > 0,
    queryKey: ['search', q, market],
    queryFn: async () =>
      searchRespSchema.parse(
        await getJSON(`/market/search?q=${encodeURIComponent(q)}&market=${market}&limit=20`),
      ),
    placeholderData: (prev) => prev, // 输入时保留上次结果，避免闪烁
    staleTime: 60_000,
  })
}

// ───────────────────────── 变更钩子 ─────────────────────────
function useInvalidateSections() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: ['sections'] })
}

export function useCreateSection() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: (body: { name: string; parent_id?: number | null }) =>
      send('/watchlist/sections', 'POST', body),
    onSuccess: invalidate,
    onError: onMutErr,
  })
}

export function useAddItem() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: ({ sectionId, symbol }: { sectionId: number; symbol: string }) =>
      send(`/watchlist/sections/${sectionId}/items`, 'POST', { symbol }),
    onSuccess: invalidate,
    onError: onMutErr,
  })
}

export function useDeleteSection() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: (id: number) => send(`/watchlist/sections/${id}`, 'DELETE'),
    onSuccess: invalidate,
  })
}

// 重命名按 section id（市场无关，后端单实体 UPDATE）；onSuccess 失效**所有市场**的 sections
// 查询（useInvalidateSections 按 ['sections'] 前缀）→ 切到别的市场也即时一致，避免"分叉"。
export function useRenameSection() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      send(`/watchlist/sections/${id}`, 'PATCH', { name }),
    onSuccess: invalidate,
    onError: onMutErr,
  })
}

export function useDeleteItem() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: (id: number) => send(`/watchlist/items/${id}`, 'DELETE'),
    onSuccess: invalidate,
  })
}

export function useMoveItem() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: ({ itemId, sectionId }: { itemId: number; sectionId: number }) =>
      send(`/watchlist/items/${itemId}`, 'PATCH', { section_id: sectionId }),
    onSuccess: invalidate,
    onError: onMutErr,
  })
}

export function useReorder() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: ({ kind, orderedIds }: { kind: 'section' | 'item'; orderedIds: number[] }) =>
      send('/watchlist/reorder', 'POST', { kind, ordered_ids: orderedIds }),
    onSuccess: invalidate,
  })
}

// ───────────────────────── 判断日记 ─────────────────────────
export function useJournal(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['journal', symbol],
    queryFn: async () =>
      z
        .array(journalSchema)
        .parse(await getJSON(`/journal/entries?symbol=${encodeURIComponent(symbol!)}`)),
  })
}

function useInvalidateJournal() {
  const qc = useQueryClient()
  return (symbol: string) => qc.invalidateQueries({ queryKey: ['journal', symbol] })
}

export function useCreateJournal() {
  const invalidate = useInvalidateJournal()
  return useMutation({
    mutationFn: (body: { symbol: string; entry_date: string; body: string }) =>
      send('/journal/entries', 'POST', body),
    onSuccess: (_d, v) => invalidate(v.symbol),
  })
}

export function useUpdateJournal(symbol: string) {
  const invalidate = useInvalidateJournal()
  return useMutation({
    mutationFn: ({ id, entry_date, body }: { id: number; entry_date?: string; body?: string }) =>
      send(`/journal/entries/${id}`, 'PATCH', { entry_date, body }),
    onSuccess: () => invalidate(symbol),
  })
}

export function useDeleteJournal(symbol: string) {
  const invalidate = useInvalidateJournal()
  return useMutation({
    mutationFn: (id: number) => send(`/journal/entries/${id}`, 'DELETE'),
    onSuccess: () => invalidate(symbol),
  })
}

// ───────────────────────── 新闻 · 趋势日报（「知」）─────────────────────────
const newsItemSchema = z.object({
  id: z.number(),
  source: z.string(),
  title: z.string(),
  url: z.string(),
  summary: z.string().default(''),
  lang: z.string().default(''),
  category: z.string().default(''),
  published_at: z.string().nullable().default(null),
  theme: z.string().default(''),
  topics: z.array(z.string()).default([]),
  title_zh: z.string().nullable().default(null),
  symbols: z
    .array(
      z.object({
        symbol: z.string(),
        name: z.string().default(''),
        in_watchlist: z.boolean().default(false),
      }),
    )
    .default([]),
})
const newsReportSchema = z.object({
  report_date: z.string(),
  body: z.string(),
  model: z.string().default(''),
  item_count: z.number().default(0),
  created_at: z.string().nullable().default(null),
})
const reportMetaSchema = z.object({
  report_date: z.string(),
  item_count: z.number().default(0),
  model: z.string().default(''),
  created_at: z.string().nullable().default(null),
  preview: z.string().default(''),
})
const refreshResultSchema = z.object({
  fetched: z.number(),
  inserted: z.number(),
  sources_ok: z.number(),
  sources_failed: z.number(),
  failures: z.array(z.string()).default([]),
})
const filingSchema = z.object({
  form: z.string(),
  title: z.string(),
  url: z.string(),
  summary: z.string().default(''),
  filed_at: z.string().nullable().default(null),
})
export type NewsItem = z.infer<typeof newsItemSchema>
export type NewsReport = z.infer<typeof newsReportSchema>
export type ReportMeta = z.infer<typeof reportMetaSchema>
export type RefreshResult = z.infer<typeof refreshResultSchema>
export type Filing = z.infer<typeof filingSchema>

export function useNewsFeed(
  limit = 60,
  opts?: { theme?: string; sourcePrefix?: string; category?: string; days?: number; day?: string },
) {
  const theme = opts?.theme
  const sp = opts?.sourcePrefix
  const category = opts?.category
  const days = opts?.days
  const day = opts?.day
  return useQuery({
    queryKey: ['news-feed', limit, theme ?? 'all', sp ?? '', category ?? '', days ?? 0, day ?? ''],
    queryFn: async () => {
      const q = new URLSearchParams({ limit: String(limit) })
      if (theme) q.set('theme', theme)
      if (sp) q.set('source_prefix', sp)
      if (category) q.set('category', category)
      if (days) q.set('days', String(days))
      if (day) q.set('day', day)
      return z.array(newsItemSchema).parse(await getJSON(`/news/feed?${q.toString()}`))
    },
    staleTime: 5 * 60_000,
  })
}

export function useNewsForSymbol(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['news-for', symbol],
    queryFn: async () =>
      z
        .array(newsItemSchema)
        .parse(await getJSON(`/news/for?symbol=${encodeURIComponent(symbol!)}&limit=20`)),
    staleTime: 5 * 60_000,
  })
}

const stockNewsBriefSchema = z.object({
  symbol: z.string(),
  summary: z.string().default(''),
  points: z.array(z.string()).default([]),
  risks: z.array(z.string()).default([]),
  source_count: z.number().default(0),
  generated_at: z.string().nullable().default(null),
})
export type StockNewsBrief = z.infer<typeof stockNewsBriefSchema>

const stockSocialHeatSchema = z.object({
  symbol: z.string(),
  configured: z.boolean().default(false),
  status: z.string().default(''),
  summary: z.string().default(''),
  sentiment: z.string().default('不明'),
  heat: z.string().default('低'),
  bull_points: z.array(z.string()).default([]),
  bear_points: z.array(z.string()).default([]),
  watch: z.array(z.string()).default([]),
  source_count: z.number().default(0),
  platforms: z.record(z.string(), z.number()).default({}),
  generated_at: z.string().nullable().default(null),
})
export type StockSocialHeat = z.infer<typeof stockSocialHeatSchema>

export function useStockNewsBrief(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['stock-news-brief', symbol],
    queryFn: async () =>
      stockNewsBriefSchema.parse(
        await getJSON(`/news/for/brief?symbol=${encodeURIComponent(symbol!)}&limit=32`),
      ),
    staleTime: 30 * 60_000,
    retry: 1,
  })
}

export function useStockSocialHeat(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['stock-social-heat', symbol],
    queryFn: async () =>
      stockSocialHeatSchema.parse(
        await getJSON(`/news/social-heat?symbol=${encodeURIComponent(symbol!)}`),
      ),
    staleTime: 30 * 60_000,
    retry: 1,
  })
}

// 个股官方一手文件（美股 SEC EDGAR 申报）。仅美股启用；其他市场后端返回空表。
export function useStockOfficial(symbol: string | null) {
  return useQuery({
    enabled: !!symbol && symbol.startsWith('US:'),
    queryKey: ['news-official', symbol],
    queryFn: async () =>
      z
        .array(filingSchema)
        .parse(await getJSON(`/news/official?symbol=${encodeURIComponent(symbol!)}&limit=15`)),
    staleTime: 30 * 60_000,
  })
}

export function useNewsReports() {
  return useQuery({
    queryKey: ['news-reports'],
    queryFn: async () => z.array(reportMetaSchema).parse(await getJSON('/news/reports')),
  })
}

export function useNewsReport(date: string | null) {
  return useQuery({
    queryKey: ['news-report', date ?? 'latest'],
    // 最新一份用 ?date 省略；某天用具体日期。404（暂无日报）→ 返回 null 而非抛错。
    queryFn: async () => {
      try {
        return newsReportSchema.parse(
          await getJSON(`/news/report${date ? `?date=${date}` : ''}`),
        )
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) return null
        throw e
      }
    },
  })
}

export function useRefreshNews() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => refreshResultSchema.parse(await send('/news/refresh', 'POST')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['news-feed'] }),
  })
}

// ── 今日投资机会 ──
const relatedSchema = z.object({
  symbol: z.string().nullable().default(null),
  name: z.string(),
  market: z.string().default(''),
  resolved: z.boolean().default(false),
  in_watchlist: z.boolean().default(false),
  sections: z.array(z.string()).default([]),
})
const evidenceSchema = z.object({
  news_id: z.number().nullable().default(null),
  title: z.string(),
  source: z.string(),
  url: z.string().nullable().default(null),
})
const opportunitySchema = z.object({
  title: z.string(),
  thesis: z.string().default(''),
  theme: z.string().default(''),
  confidence: z.string().default('low'),
  caveats: z.string().default(''),
  related: z.array(relatedSchema).default([]),
  evidence: z.array(evidenceSchema).default([]),
})
const opportunitiesSchema = z.object({
  report_date: z.string(),
  model: z.string().default(''),
  item_count: z.number().default(0),
  created_at: z.string().nullable().default(null),
  disclaimer: z.string().default(''),
  opportunities: z.array(opportunitySchema).default([]),
})
export type RelatedSymbol = z.infer<typeof relatedSchema>
export type Opportunity = z.infer<typeof opportunitySchema>
export type OpportunitiesResp = z.infer<typeof opportunitiesSchema>

export function useOpportunities(date: string | null) {
  return useQuery({
    queryKey: ['news-opps', date ?? 'today'],
    queryFn: async () => {
      try {
        return opportunitiesSchema.parse(
          await getJSON(`/news/opportunities${date ? `?date=${date}` : ''}`),
        )
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) return null // 未生成 → null（非错误）
        throw e
      }
    },
  })
}

export function useGenerateOpportunities() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (date?: string | null) =>
      opportunitiesSchema.parse(
        await send(`/news/opportunities/generate${date ? `?date=${date}` : ''}`, 'POST'),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['news-opps'] }),
  })
}

// ── 新闻「要点」：去重聚类 + 按投资重要性排序 ──
const clusterMemberSchema = z.object({
  source: z.string().default(''),
  title: z.string().default(''),
  url: z.string().default(''),
})
const newsClusterSchema = z.object({
  headline: z.string(),
  importance: z.string().default('med'),
  why: z.string().default(''),
  members: z.array(clusterMemberSchema).default([]),
})
const clustersSchema = z.object({
  report_date: z.string(),
  scope: z.string().default(''),
  days: z.number().default(1),
  model: z.string().default(''),
  item_count: z.number().default(0),
  created_at: z.string().nullable().default(null),
  clusters: z.array(newsClusterSchema).default([]),
})
export type NewsCluster = z.infer<typeof newsClusterSchema>
// 聚类范围：新闻按 theme，推特按 sourcePrefix='X·' + category；都带时间窗 days
export type ClusterParams = {
  theme?: string
  sourcePrefix?: string
  category?: string
  days?: number
  date?: string // 某天快照：取/生成那一天的要点
}
function clusterQS(p: ClusterParams): string {
  const q = new URLSearchParams()
  if (p.theme) q.set('theme', p.theme)
  if (p.sourcePrefix) q.set('source_prefix', p.sourcePrefix)
  if (p.category) q.set('category', p.category)
  q.set('days', String(p.days ?? 1))
  if (p.date) q.set('date', p.date)
  return q.toString()
}

export function useClusters(p: ClusterParams) {
  const qs = clusterQS(p)
  return useQuery({
    queryKey: ['news-clusters', qs],
    queryFn: async () => {
      try {
        return clustersSchema.parse(await getJSON(`/news/clusters?${qs}`))
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) return null
        throw e
      }
    },
  })
}

export function useGenerateClusters() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (p: ClusterParams) =>
      clustersSchema.parse(await send(`/news/clusters/generate?${clusterQS(p)}`, 'POST')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['news-clusters'] }),
  })
}

// ── 个股：定向抓取 lane + 标的叙事时间线（知·个股）──
const narrativeRefSchema = z.object({
  source: z.string().default(''),
  title: z.string().default(''),
  url: z.string().default(''),
})
const narrativeEventSchema = z.object({
  date: z.string().default(''),
  title: z.string().default(''),
  importance: z.string().default('med'),
  refs: z.array(narrativeRefSchema).default([]),
})
const narrativeSchema = z.object({
  symbol: z.string(),
  name: z.string().default(''),
  summary: z.string().default(''),
  timeline: z.array(narrativeEventSchema).default([]),
  model: z.string().default(''),
  item_count: z.number().default(0),
  created_at: z.string().nullable().default(null),
})
export type StockNarrative = z.infer<typeof narrativeSchema>
export type NarrativeEvent = z.infer<typeof narrativeEventSchema>

export function useNarrative(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['narrative', symbol],
    queryFn: async () => {
      try {
        return narrativeSchema.parse(
          await getJSON(`/news/narrative?symbol=${encodeURIComponent(symbol!)}`),
        )
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) return null // 未生成 → null（非错误）
        throw e
      }
    },
  })
}

export function useGenerateNarrative() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (symbol: string) =>
      narrativeSchema.parse(
        await send(`/news/narrative/generate?symbol=${encodeURIComponent(symbol)}`, 'POST'),
      ),
    onSuccess: (_d, symbol) => {
      qc.invalidateQueries({ queryKey: ['narrative', symbol] })
      qc.invalidateQueries({ queryKey: ['stock-news', symbol] })
    },
  })
}

export function useRefreshDirected() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (symbol?: string) =>
      send(`/news/directed/refresh${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ''}`, 'POST'),
    onSuccess: (_d, symbol) => {
      // 指定股 → 只失效那只；全量刷新（一键里以 undefined 调）→ 失效整个 stock-news 前缀
      qc.invalidateQueries({ queryKey: symbol ? ['stock-news', symbol] : ['stock-news'] })
      qc.invalidateQueries({ queryKey: symbol ? ['stock-news-brief', symbol] : ['stock-news-brief'] })
      qc.invalidateQueries({ queryKey: symbol ? ['stock-social-heat', symbol] : ['stock-social-heat'] })
      qc.invalidateQueries({ queryKey: symbol ? ['news-for', symbol] : ['news-for'] })
    },
  })
}

// ── 每股专属信源画像（组件化信源：LLM 调研 + 作者策展）──
const stockSourceSchema = z.object({
  id: z.number(),
  symbol: z.string(),
  kind: z.string(),
  name: z.string().default(''),
  ref: z.string().default(''),
  note: z.string().default(''),
  enabled: z.boolean().default(false),
  verified: z.boolean().default(false),
  added_by: z.string().default('llm'),
})
export type StockSource = z.infer<typeof stockSourceSchema>

export function useStockSources(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['stock-sources', symbol],
    queryFn: async () =>
      z
        .array(stockSourceSchema)
        .parse(await getJSON(`/news/sources?symbol=${encodeURIComponent(symbol!)}`)),
  })
}

export function useDiscoverSources() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (symbol: string) =>
      send(`/news/sources/discover?symbol=${encodeURIComponent(symbol)}`, 'POST'),
    onSuccess: (_d, symbol) => qc.invalidateQueries({ queryKey: ['stock-sources', symbol] }),
  })
}

export function useAddStockSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { symbol: string; kind: string; name: string; ref: string; note?: string }) =>
      send(`/news/sources?symbol=${encodeURIComponent(v.symbol)}`, 'POST', {
        kind: v.kind,
        name: v.name,
        ref: v.ref,
        note: v.note ?? '',
      }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['stock-sources', v.symbol] }),
  })
}

export function useToggleStockSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; symbol: string; enabled: boolean }) =>
      send(`/news/sources/${v.id}`, 'PATCH', { enabled: v.enabled }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['stock-sources', v.symbol] }),
  })
}

export function useDeleteStockSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; symbol: string }) =>
      send(`/news/sources/${v.id}`, 'DELETE'),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['stock-sources', v.symbol] }),
  })
}

export function useStockNews(symbol: string | null, days = 0) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['stock-news', symbol, days],
    queryFn: async () =>
      z
        .array(newsItemSchema)
        .parse(
          await getJSON(
            `/news/stock?symbol=${encodeURIComponent(symbol!)}&days=${days}&limit=80`,
          ),
        ),
    staleTime: 5 * 60_000,
  })
}

// 生成趋势日报（SSE 流式）；onDelta 增量回调。完成/中断由调用方处理。
export async function streamReport(
  date: string | null,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`/news/report/generate${date ? `?date=${date}` : ''}`, {
    method: 'POST',
    signal,
  })
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new Error(d.detail ?? `HTTP ${r.status}`)
  }
  await consumeSSE(r, onDelta)
}

// ───────────────────────── 研 · 单股深度研究 ─────────────────────────
const researchSourceSchema = z.object({
  n: z.number(),
  title: z.string().default(''),
  source: z.string().default(''),
  url: z.string().nullable().default(null),
})
const researchReportSchema = z.object({
  symbol: z.string(),
  name: z.string().default(''),
  body: z.string(),
  sources: z.array(researchSourceSchema).default([]),
  model: z.string().default(''),
  created_at: z.string().nullable().default(null),
})
export type ResearchSource = z.infer<typeof researchSourceSchema>
export type ResearchReport = z.infer<typeof researchReportSchema>

// 已生成的深度研究报告。404（暂无）→ null 而非抛错。
export function useResearchReport(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['research', symbol],
    queryFn: async () => {
      try {
        return researchReportSchema.parse(
          await getJSON(`/research/stock?symbol=${encodeURIComponent(symbol!)}`),
        )
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) return null
        throw e
      }
    },
  })
}

// 生成单股深度研究（SSE 流式）；onDelta 增量回调。完成/中断由调用方处理。
export async function streamResearch(
  symbol: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`/research/stock/generate?symbol=${encodeURIComponent(symbol)}`, {
    method: 'POST',
    signal,
  })
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new Error(d.detail ?? `HTTP ${r.status}`)
  }
  await consumeSSE(r, onDelta)
}

// ───────────────────────── 研 · 导入研报（他人写的 markdown，一股可多份）─────────────────────────
const importedReportSchema = z.object({
  id: z.number(),
  symbol: z.string(),
  title: z.string().default(''),
  body: z.string().default(''),
  comment: z.string().default(''),
  engine: z.string().default(''), // 回流来源：chatgpt/claude/gemini/other
  source_url: z.string().default(''),
  sort_order: z.number().default(0),
  created_at: z.string().nullable().default(null),
})
export type ImportedReport = z.infer<typeof importedReportSchema>

export function useImportedReports(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['imported', symbol],
    queryFn: async () =>
      z
        .array(importedReportSchema)
        .parse(await getJSON(`/research/imported?symbol=${encodeURIComponent(symbol!)}`)),
  })
}

export function useAddImported() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: {
      symbol: string
      title: string
      body: string
      engine?: string
      source_url?: string
    }) => send('/research/imported', 'POST', v),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['imported', v.symbol] }),
    onError: onMutErr,
  })
}

export function useUpdateImported() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: {
      id: number
      symbol: string
      title?: string
      body?: string
      comment?: string
      engine?: string
      source_url?: string
    }) =>
      send(`/research/imported/${v.id}`, 'PATCH', {
        title: v.title,
        body: v.body,
        comment: v.comment,
        engine: v.engine,
        source_url: v.source_url,
      }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['imported', v.symbol] }),
  })
}

export function useDeleteImported() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; symbol: string }) =>
      send(`/research/imported/${v.id}`, 'DELETE'),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['imported', v.symbol] }),
  })
}

export function useReorderImported() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { symbol: string; orderedIds: number[] }) =>
      send('/research/imported/reorder', 'POST', { ordered_ids: v.orderedIds }),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ['imported', v.symbol] }),
  })
}

// ───────────────────────── 「记」· 笔记（第 4 支柱）─────────────────────────
const noteMetaSchema = z.object({
  id: z.number(),
  title: z.string().default(''),
  preview: z.string().default(''),
  pinned: z.boolean().default(false),
  created_at: z.string().nullable().default(null),
  updated_at: z.string().nullable().default(null),
})
const noteSchema = z.object({
  id: z.number(),
  title: z.string().default(''),
  body: z.string().default(''),
  pinned: z.boolean().default(false),
  created_at: z.string().nullable().default(null),
  updated_at: z.string().nullable().default(null),
})
export type NoteMeta = z.infer<typeof noteMetaSchema>
export type Note = z.infer<typeof noteSchema>

export function useNotes() {
  return useQuery({
    queryKey: ['notes'],
    queryFn: async () => z.array(noteMetaSchema).parse(await getJSON('/notes')),
  })
}

export function useNote(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: ['note', id],
    queryFn: async () => noteSchema.parse(await getJSON(`/notes/${id}`)),
  })
}

export function useCreateNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { title?: string; body?: string }) =>
      noteSchema.parse(await send('/notes', 'POST', { title: v.title ?? '', body: v.body ?? '' })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  })
}

export function useUpdateNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; title?: string; body?: string; pinned?: boolean }) =>
      noteSchema.parse(
        await send(`/notes/${v.id}`, 'PATCH', { title: v.title, body: v.body, pinned: v.pinned }),
      ),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['notes'] })
      qc.setQueryData(['note', data.id], data)
    },
  })
}

export function useDeleteNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => send(`/notes/${id}`, 'DELETE'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  })
}

// ───────────────────────── Prompt 模板（「研」一键复制 Deep Research 提示词）─────────────────────────
const templateSchema = z.object({
  id: z.number(),
  name: z.string().default(''),
  body: z.string().default(''),
  sort_order: z.number().default(0),
  created_at: z.string().nullable().default(null),
  updated_at: z.string().nullable().default(null),
})
export type PromptTemplate = z.infer<typeof templateSchema>

// 占位符填充：{STOCK} 代码 · {NAME} 名称 · {MARKET} 市场 · {SYMBOL} 市场:代码。
// 纯前端渲染——模板用于复制到外部网页 Deep Research，不进本地 LLM 调用链。
const MARKET_LABEL: Record<string, string> = { US: '美股', HK: '港股', CN: 'A股', KR: '韩股' }
export function fillTemplate(body: string, symbol: string, name?: string | null): string {
  const i = symbol.indexOf(':')
  const market = i > 0 ? symbol.slice(0, i) : ''
  const code = i > 0 ? symbol.slice(i + 1) : symbol
  return body
    .replaceAll('{SYMBOL}', symbol)
    .replaceAll('{STOCK}', code)
    .replaceAll('{MARKET}', MARKET_LABEL[market] ?? market)
    .replaceAll('{NAME}', name || code)
}

export function useTemplates() {
  return useQuery({
    queryKey: ['templates'],
    queryFn: async () => z.array(templateSchema).parse(await getJSON('/templates')),
  })
}

export function useCreateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { name?: string; body?: string }) =>
      templateSchema.parse(
        await send('/templates', 'POST', { name: v.name ?? '', body: v.body ?? '' }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
    onError: onMutErr,
  })
}

export function useUpdateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: { id: number; name?: string; body?: string }) =>
      templateSchema.parse(
        await send(`/templates/${v.id}`, 'PATCH', { name: v.name, body: v.body }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
    onError: onMutErr,
  })
}

export function useDeleteTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => send(`/templates/${id}`, 'DELETE'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
    onError: onMutErr,
  })
}

// ───────────────────────── 「寻」· 发现候选标的（第 4 支柱）─────────────────────────
const discoveryEvidenceSchema = z.object({
  news_id: z.number(),
  title: z.string().default(''),
  source: z.string().default(''),
  url: z.string().default(''),
  date: z.string().default(''),
})
const candidateSchema = z.object({
  symbol: z.string(),
  name: z.string().default(''),
  market: z.string().default(''),
  mention_count: z.number().default(0),
  day_span: z.number().default(0),
  first_seen_at: z.string().nullable().default(null),
  last_seen_at: z.string().nullable().default(null),
  evidence: z.array(discoveryEvidenceSchema).default([]),
  status: z.string().default('new'),
})
export type Candidate = z.infer<typeof candidateSchema>

export function useDiscovery(status = 'new') {
  return useQuery({
    queryKey: ['discovery', status],
    queryFn: async () =>
      z.array(candidateSchema).parse(await getJSON(`/discovery?status=${status}`)),
  })
}

export function useRefreshDiscovery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => send('/discovery/refresh', 'POST'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discovery'] }),
    onError: onMutErr,
  })
}

export function useSetCandidateStatus() {
  const qc = useQueryClient()
  return useMutation({
    // symbol=MARKET:CODE 拆成路径段避免冒号转义
    mutationFn: async (v: { symbol: string; status: string }) => {
      const [market, code] = v.symbol.split(':')
      return send(`/discovery/${market}/${code}`, 'PATCH', { status: v.status })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discovery'] }),
    onError: onMutErr,
  })
}

// ── 数据信源「测试」（轻量真实探活）──
export type SourceTestResult = {
  ok: boolean
  latency_ms?: number
  count?: number
  note?: string
  error?: string
}
export function useTestSource() {
  return useMutation({
    mutationFn: async (id: string) =>
      (await send(`/settings/source/test?id=${encodeURIComponent(id)}`, 'POST')) as SourceTestResult,
  })
}

const auditResultSchema = z
  .object({
    ok: z.boolean(),
    latency_ms: z.number().optional(),
    count: z.number().optional(),
    note: z.string().optional(),
    reply: z.string().optional(),
    error: z.string().optional(),
  })
  .passthrough()
const auditItemSchema = z.object({
  id: z.string(),
  kind: z.string(),
  name: z.string(),
  group: z.string().default(''),
  configured: z.boolean(),
  status: z.string(),
  state: z.string(),
  key_env: z.string().default(''),
  cred: z.string().default(''),
  key_url: z.string().default(''),
  docs_url: z.string().default(''),
  official_url: z.string().default(''),
  setup: z.string().default(''),
  best_use: z.string().default(''),
  boundary: z.string().default(''),
  base_url: z.string().default(''),
  model: z.string().default(''),
  result: auditResultSchema.nullable().default(null),
})
const sourceHealthSchema = z.object({
  source: z.string(),
  ok_count: z.number().default(0),
  fail_count: z.number().default(0),
  last_count: z.number().default(0),
  last_ok_at: z.string().nullable().default(null),
  last_fail_at: z.string().nullable().default(null),
  last_error: z.string().default(''),
  updated_at: z.string().default(''),
})
const settingsAuditSchema = z.object({
  llm: z.array(auditItemSchema).default([]),
  sources: z.array(auditItemSchema).default([]),
  health: z.array(sourceHealthSchema).default([]),
  summary: z
    .object({
      total: z.number().default(0),
      ok: z.number().default(0),
      missing_key: z.number().default(0),
      quota: z.number().default(0),
      permission: z.number().default(0),
      not_integrated: z.number().default(0),
      failed: z.number().default(0),
      health_sources: z.number().default(0),
      health_failed: z.number().default(0),
    })
    .default({}),
})
export type ApiAuditItem = z.infer<typeof auditItemSchema>
export type SourceHealthRow = z.infer<typeof sourceHealthSchema>
export type SettingsAudit = z.infer<typeof settingsAuditSchema>

export function useRunSettingsAudit() {
  return useMutation({
    mutationFn: async () => settingsAuditSchema.parse(await send('/settings/test-all', 'POST')),
  })
}

export function useSourceHealth() {
  return useQuery({
    queryKey: ['source-health'],
    queryFn: async () => z.array(sourceHealthSchema).parse(await getJSON('/news/source-health')),
    staleTime: 30_000,
  })
}
