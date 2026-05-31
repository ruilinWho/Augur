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

export type Candle = z.infer<typeof candleSchema>
export type Ohlcv = z.infer<typeof ohlcvSchema>
export type Quote = z.infer<typeof quoteSchema>
export type RoleStatus = z.infer<typeof roleSchema>

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

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: async () => z.array(roleSchema).parse(await getJSON('/llm/roles')),
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
