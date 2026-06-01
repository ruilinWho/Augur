import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'

// ───────────────────────── HTTP 助手（开发期经 Vite 代理到 :8788）─────────────────────────
async function getJSON(url: string): Promise<unknown> {
  const r = await fetch(url)
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new Error(d.detail ?? `HTTP ${r.status}`)
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
    throw new Error(d.detail ?? `HTTP ${r.status}`)
  }
  return r.status === 204 ? null : r.json()
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

export function useFinancials(symbol: string | null) {
  return useQuery({
    enabled: !!symbol,
    queryKey: ['financials', symbol],
    queryFn: async () =>
      financialsSchema.parse(
        await getJSON(`/market/financials?symbol=${encodeURIComponent(symbol!)}`),
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
  if (!r.ok || !r.body) {
    const d = (await r.json().catch(() => ({}))) as { detail?: string }
    throw new Error(d.detail ?? `HTTP ${r.status}`)
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
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
      try {
        const obj = JSON.parse(payload) as { delta?: string; error?: string }
        if (obj.error) throw new Error(obj.error)
        if (obj.delta) onDelta(obj.delta)
      } catch {
        /* 半行/非 JSON，忽略 */
      }
    }
  }
}

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: async () => z.array(roleSchema).parse(await getJSON('/llm/roles')),
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
  })
}

export function useAddItem() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: ({ sectionId, symbol }: { sectionId: number; symbol: string }) =>
      send(`/watchlist/sections/${sectionId}/items`, 'POST', { symbol }),
    onSuccess: invalidate,
  })
}

export function useDeleteSection() {
  const invalidate = useInvalidateSections()
  return useMutation({
    mutationFn: (id: number) => send(`/watchlist/sections/${id}`, 'DELETE'),
    onSuccess: invalidate,
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
