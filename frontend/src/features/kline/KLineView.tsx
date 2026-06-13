import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'motion/react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts'
import { useUI } from '../../store'
import { useFinancials, useFundamentals, useJournal, useOhlcv, useQuote, useStockDisclosures } from '../../api'
import { fmtMoney, fmtPctPlain } from '../../format'
import { EASE } from '../../theme/motion'
import AddToWatchlist from '../watchlist/AddToWatchlist'
import CopyPromptButton from '../research/CopyPromptButton'

// 与 index.css 的 token 镜像（图表是 canvas，直接取色避免读 CSS 变量的时序问题）
const PALETTE = {
  light: { green: '#7fa189', red: '#c68c7c', surface: '#fbfaf5', border: '#e4e0d3', faint: '#9a9483', accent: '#d97757', disclosure: '#8a7f6b' },
  dark: { green: '#8fb096', red: '#d49b8b', surface: '#282622', border: '#39352f', faint: '#766f63', accent: '#e08a6a', disclosure: '#a89e8c' },
}

const TF = [
  { label: '1月', interval: '1d', range: '1m' },
  { label: '3月', interval: '1d', range: '3m' },
  { label: '6月', interval: '1d', range: '6m' },
  { label: '1年', interval: '1d', range: '1y' },
]

const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
// hex + alpha → 8 位 hex。蜡笔纸感（§9 硬指标）：实体半透明（让纸透出）、描边/影线略实以保规整直角矩形。
const hexA = (hex: string, a: number) => hex + Math.round(a * 255).toString(16).padStart(2, '0')
// 确定性骨架柱高（无随机，避免每次不同）
const SKEL_BARS = Array.from({ length: 28 }, (_, i) => 30 + Math.round(28 * (1 + Math.sin(i / 2.3)) + 14 * (1 + Math.cos(i / 1.5))))

function quarterEnd(label: string): string | null {
  const m = /^(\d{4})Q([1-4])$/.exec(label)
  if (!m) return null
  const y = m[1]
  const q = Number(m[2])
  if (q === 1) return `${y}-03-31`
  if (q === 2) return `${y}-06-30`
  if (q === 3) return `${y}-09-30`
  return `${y}-12-31`
}

export default function KLineView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const theme = useUI((s) => s.theme)
  const conv = useUI((s) => s.convention)
  const [tf, setTf] = useState(TF[3]) // 默认 1 年

  const ohlcv = useOhlcv(symbol, tf.interval, tf.range)
  const quote = useQuote(symbol)
  const fund = useFundamentals(symbol)
  const financials = useFinancials(symbol, 'quarter')
  const disclosures = useStockDisclosures(symbol)
  // 始终取 1 年用于「52 周位置」（与 tf=1年 同 queryKey 时复用、不重复请求；后端走同一 parquet 缓存）
  const year = useOhlcv(symbol, '1d', '1y')
  const journal = useJournal(symbol)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, { autoSize: true })
    const series = chart.addSeries(CandlestickSeries, {})
    markersRef.current = createSeriesMarkers(series, [])
    chartRef.current = chart
    seriesRef.current = series
    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const series = seriesRef.current
    if (!chart || !series) return
    const p = PALETTE[theme]
    const up = conv === 'cn' ? p.red : p.green
    const down = conv === 'cn' ? p.green : p.red
    chart.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: p.surface },
        textColor: p.faint,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: p.border } },
      rightPriceScale: { borderColor: p.border },
      timeScale: { borderColor: p.border },
      crosshair: {
        mode: 1,
        vertLine: { color: p.accent, width: 1, style: 3, labelBackgroundColor: p.accent },
        horzLine: { color: p.accent, labelBackgroundColor: p.accent },
      },
    })
    // 蜡笔纸感：实体半透明（让象牙纸透出，不像交易终端的鲜艳实心），描边/影线略实保规整直角
    series.applyOptions({
      upColor: hexA(up, 0.5),
      downColor: hexA(down, 0.5),
      borderUpColor: hexA(up, 0.9),
      borderDownColor: hexA(down, 0.9),
      wickUpColor: hexA(up, 0.68),
      wickDownColor: hexA(down, 0.68),
      borderVisible: true,
    })
  }, [theme, conv])

  useEffect(() => {
    const series = seriesRef.current
    if (!series || !ohlcv.data) return
    series.setData(
      ohlcv.data.candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    chartRef.current?.timeScale().fitContent()
  }, [ohlcv.data])

  // 综合认知 marker：个人判断（判）+ 公司披露（财/会）。三类统一钉在价格轴底部一条事件带上，
  // 不遮挡蜡烛实体；同一财报周期内相近的多份申报/电话会合并，避免挤成一团分不清。
  // 优先用真实披露日；没有 SEC 披露事件时，财报 marker 才回退到季度期末近似。
  useEffect(() => {
    const plugin = markersRef.current
    if (!plugin) return
    const candles = ohlcv.data?.candles ?? []
    const entries = journal.data ?? []
    const fins = financials.data?.periods ?? []
    const disclosureEvents = disclosures.data?.events ?? []
    if (!candles.length) {
      plugin.setMarkers([])
      return
    }
    const times = candles.map((c) => c.time)
    const lo = times[0]
    // 底部锚价：所有事件 marker 钉在数据最低价那条水平线上 → 横向对齐成一条带；
    // createSeriesMarkers 的 autoScale 默认 true，会自动下扩价格轴让这条带完整可见。
    const priceFloor = Math.min(...candles.map((c) => c.low))
    const accent = PALETTE[theme].accent
    const disclosure = PALETTE[theme].disclosure
    const snap = (d: string) => {
      if (d < lo) return null // 早于当前区间，不显示
      // 吸附到 <= 该日期的最近一根（非交易日落到前一交易日）
      let t = ''
      for (const ct of times) {
        if (ct <= d) t = ct
        else break
      }
      return t || null
    }
    // 相近事件合并：间隔不足 MIN_GAP 个交易日的，只留最早一个（同一财报周期的 10-Q + 8-K 等会并成一条）
    const idxOf = new Map<string, number>()
    times.forEach((t, i) => idxOf.set(t, i))
    const MIN_GAP = 8
    const dedupeNear = (sorted: string[]) => {
      const out: string[] = []
      let last = -Infinity
      for (const t of sorted) {
        const i = idxOf.get(t) ?? 0
        if (i - last >= MIN_GAP) {
          out.push(t)
          last = i
        }
      }
      return out
    }
    // 统一造一个钉在底部带、小圆点 + 单字的 marker（judgment/disclosure 只差颜色与文字）
    const atFloor = (text: string, color: string) => (t: string) => ({
      time: t as Time,
      position: 'atPriceBottom' as const,
      price: priceFloor,
      color,
      shape: 'circle' as const,
      text,
    })
    const seenJournal = new Set<string>()
    const journalMarkers = entries
      .map((e) => snap(e.entry_date))
      .filter((t): t is string => !!t && !seenJournal.has(t) && (seenJournal.add(t), true))
      .sort()
      .map(atFloor('判', accent))
    const seenFinancial = new Set<string>()
    const disclosureFinancialDates = disclosureEvents
      .filter((ev) => {
        const form = ev.form.toUpperCase()
        return (
          ev.kind === 'filing' &&
          (form.startsWith('10-Q') ||
            form.startsWith('10-K') ||
            ev.title.includes('财报') ||
            ev.title.includes('经营成果'))
        )
      })
      .map((ev) => ev.date)
      .filter(Boolean)
    const fallbackFinancialDates = disclosureFinancialDates.length
      ? []
      : fins.map((p) => quarterEnd(p.period)).filter((d): d is string => Boolean(d))
    const financialMarkers = dedupeNear(
      [...disclosureFinancialDates, ...fallbackFinancialDates]
        .map((d) => snap(d))
        .filter((t): t is string => !!t && !seenFinancial.has(t) && (seenFinancial.add(t), true))
        .sort(),
    ).map(atFloor('财', disclosure))
    const seenCalls = new Set<string>()
    const callMarkers = dedupeNear(
      disclosureEvents
        .filter((ev) => ev.kind === 'transcript' && ev.date)
        .map((ev) => snap(ev.date))
        .filter((t): t is string => !!t && !seenCalls.has(t) && (seenCalls.add(t), true))
        .sort(),
    ).map(atFloor('会', disclosure))
    const markers = [...financialMarkers, ...callMarkers, ...journalMarkers].sort((a, b) =>
      String(a.time).localeCompare(String(b.time)),
    )
    plugin.setMarkers(markers)
  }, [disclosures.data, financials.data, journal.data, ohlcv.data, theme])

  // 52 周位置（始终用 1 年数据）：当前价在一年区间的分位，比当日涨跌更能传达"贵不贵"。
  const wk52 = useMemo(() => {
    const cs = year.data?.candles
    if (!cs || cs.length < 2) return null
    const hi = Math.max(...cs.map((c) => c.high))
    const lo = Math.min(...cs.map((c) => c.low))
    const cur = cs[cs.length - 1].close
    if (hi <= lo) return null
    return { hi, lo, pct: ((cur - lo) / (hi - lo)) * 100 }
  }, [year.data])

  const q = quote.data
  // 平盘（change===0：停牌/盘前无变动）单列出来——不再当作"涨"显绿色▲
  const dir = q ? (q.change > 0 ? 'up' : q.change < 0 ? 'down' : 'flat') : 'up'
  const [mkt, code] = symbol ? symbol.split(':') : ['', '']
  const candleCount = ohlcv.data?.candles.length ?? 0
  // 新股：可选区间内只有极少 K 线（如刚 IPO 仅 1 个交易日）——平静标注，避免看似坏掉（§11）
  const thin = !!symbol && !!ohlcv.data && candleCount > 0 && candleCount <= 3
  const showSkeleton = !!symbol && ohlcv.isLoading && !ohlcv.data
  const fundData = fund.data
  const keyStats = [
    wk52 && { label: '52周位置', value: `${Math.round(wk52.pct)}%` },
    fundData?.market_cap != null && {
      label: '市值',
      value: fmtMoney(fundData.market_cap, fundData.currency),
    },
    fundData?.pe != null && { label: '市盈率', value: fundData.pe.toFixed(1) },
    fundData?.net_margin != null && { label: '净利率', value: fmtPctPlain(fundData.net_margin) },
    q?.time && { label: '更新', value: q.time, quiet: true },
  ].filter(Boolean) as { label: string; value: string; quiet?: boolean }[]

  return (
    <>
      {symbol && (
        <motion.div
          className="stock-head"
          key={symbol}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: EASE }}
        >
          <div>
            <h2>
              {q?.name || code} <span className="sub">{code} · {mkt}</span>
              <AddToWatchlist symbol={symbol} />
            </h2>
            <div className="stock-price-row">
              <span className="px">{q ? fmt(q.price) : '—'}</span>
              {q && (
                <span className={`pill ${dir}`}>
                  {dir === 'up' ? '▲' : dir === 'down' ? '▼' : '–'} {Math.abs(q.change).toFixed(2)} (
                  {Math.abs(q.change_pct).toFixed(2)}%)
                </span>
              )}
              {thin && <span className="ipo-note">新股 · 仅 {candleCount} 个交易日</span>}
            </div>
            {keyStats.length > 0 && (
              <div className="stock-keyline">
                {keyStats.map((s) => (
                  <span key={s.label} className={`key-stat ${s.quiet ? 'quiet' : ''}`}>
                    <i>{s.label}</i>
                    <b>{s.value}</b>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="stock-head-actions">
            <CopyPromptButton symbol={symbol} name={q?.name} />
            <div className="tf">
              {TF.map((t) => (
                <button
                  key={t.label}
                  className={`chip ${tf.label === t.label ? 'active' : ''}`}
                  aria-pressed={tf.label === t.label}
                  onClick={() => setTf(t)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {symbol && fund.error && (
        <div className="faint" style={{ fontSize: '.74rem', marginTop: 6 }}>
          基本面暂不可用
        </div>
      )}

      <motion.div
        className="chart-wrap"
        style={{ position: 'relative' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, ease: EASE }}
      >
        <div
          ref={containerRef}
          style={{ width: '100%', height: '100%', visibility: symbol && !showSkeleton ? 'visible' : 'hidden' }}
        />
        {!symbol && (
          <div className="empty" style={{ position: 'absolute', inset: 0 }}>
            <div style={{ fontSize: '1.15rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
              选择标的
            </div>
          </div>
        )}
        {showSkeleton && (
          <div className="chart-skeleton">
            {SKEL_BARS.map((h, i) => (
              <div key={i} className="bar skeleton" style={{ height: `${h}%` }} />
            ))}
          </div>
        )}
      </motion.div>

      {ohlcv.error && (
        <div className="faint" style={{ marginTop: 10, color: 'var(--down)' }}>
          K线获取失败：{(ohlcv.error as Error).message}
        </div>
      )}
    </>
  )
}
