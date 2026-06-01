// 数字格式化（基本面/财报共用）。金额为本币原值 → 亿/万亿 + 币种符号。

const CUR: Record<string, string> = { USD: '$', HKD: 'HK$', CNY: '¥', KRW: '₩' }

export function fmtMoney(v: number | null | undefined, cur: string): string {
  if (v == null) return '—'
  const s = CUR[cur] ?? ''
  const neg = v < 0 ? '-' : ''
  const a = Math.abs(v)
  if (a >= 1e12) return `${neg}${s}${(a / 1e12).toFixed(2)}万亿`
  if (a >= 1e8) return `${neg}${s}${(a / 1e8).toFixed(a / 1e8 >= 100 ? 0 : 1)}亿`
  if (a >= 1e4) return `${neg}${s}${(a / 1e4).toFixed(1)}万`
  return `${neg}${s}${a.toFixed(0)}`
}

// 带符号（用于增长率：+/- 有意义）
export function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`
}

// 不带符号（用于比率：净利率等）
export function fmtPctPlain(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null) return '—'
  return v.toFixed(digits)
}
