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
import { useFundamentals, useJournal, useOhlcv, useQuote } from '../../api'
import { fmtMoney, fmtPctPlain } from '../../format'
import { EASE } from '../../theme/motion'
import AddToWatchlist from '../watchlist/AddToWatchlist'

// 与 index.css 的 token 镜像（图表是 canvas，直接取色避免读 CSS 变量的时序问题）
const PALETTE = {
  light: { green: '#7fa189', red: '#c68c7c', surface: '#fbfaf5', border: '#e4e0d3', faint: '#9a9483', accent: '#d97757' },
  dark: { green: '#8fb096', red: '#d49b8b', surface: '#282622', border: '#39352f', faint: '#766f63', accent: '#e08a6a' },
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

export default function KLineView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const theme = useUI((s) => s.theme)
  const conv = useUI((s) => s.convention)
  const [tf, setTf] = useState(TF[3]) // 默认 1 年

  const ohlcv = useOhlcv(symbol, tf.interval, tf.range)
  const quote = useQuote(symbol)
  const fund = useFundamentals(symbol)
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

  // 判断日记 marker：把写下判断那天的日期落到 K 线上（研究上下文与价格不再脱节）。
  // 非交易日的笔记吸附到当日或之前最近的一根；只在当前区间内显示。
  useEffect(() => {
    const plugin = markersRef.current
    if (!plugin) return
    const candles = ohlcv.data?.candles ?? []
    const entries = journal.data ?? []
    if (!candles.length || !entries.length) {
      plugin.setMarkers([])
      return
    }
    const times = candles.map((c) => c.time)
    const lo = times[0]
    const accent = PALETTE[theme].accent
    const seen = new Set<string>()
    const markers = entries
      .map((e) => {
        const d = e.entry_date
        if (d < lo) return null // 早于当前区间，不显示
        // 吸附到 <= 该日期的最近一根（非交易日落到前一交易日）
        let t = ''
        for (const ct of times) {
          if (ct <= d) t = ct
          else break
        }
        return t || null
      })
      .filter((t): t is string => !!t && !seen.has(t) && (seen.add(t), true))
      .sort()
      .map((t) => ({
        time: t as Time,
        position: 'belowBar' as const,
        color: accent,
        shape: 'circle' as const,
        text: '记',
      }))
    plugin.setMarkers(markers)
  }, [journal.data, ohlcv.data, theme])

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
  const last = ohlcv.data?.candles.at(-1)
  const candleCount = ohlcv.data?.candles.length ?? 0
  // 新股：可选区间内只有极少 K 线（如刚 IPO 仅 1 个交易日）——平静标注，避免看似坏掉（§11）
  const thin = !!symbol && !!ohlcv.data && candleCount > 0 && candleCount <= 3
  const showSkeleton = !!symbol && ohlcv.isLoading && !ohlcv.data

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
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              <span className="px">{q ? fmt(q.price) : '—'}</span>
              {q && (
                <span className={`pill ${dir}`} style={{ fontSize: '1rem' }}>
                  {dir === 'up' ? '▲' : dir === 'down' ? '▼' : '–'} {Math.abs(q.change).toFixed(2)} (
                  {Math.abs(q.change_pct).toFixed(2)}%)
                </span>
              )}
              {last && (
                <span className="faint mono" style={{ fontSize: '.74rem', marginLeft: 4 }}>
                  高 {fmt(last.high)} · 低 {fmt(last.low)}
                </span>
              )}
              {thin && <span className="ipo-note">新股 · 仅 {candleCount} 个交易日</span>}
              {q?.time && (
                <span className="faint" style={{ fontSize: '.7rem' }}>
                  截至 {q.time} · {q.source}
                </span>
              )}
            </div>
            {wk52 && (
              <div className="faint mono wk52">
                52周 {fmt(wk52.lo)} — {fmt(wk52.hi)} · 当前
                <span className="wk52-bar" aria-hidden="true">
                  <span className="wk52-fill" style={{ width: `${Math.round(wk52.pct)}%` }} />
                </span>
                {Math.round(wk52.pct)}% 分位
              </div>
            )}
          </div>
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
        </motion.div>
      )}

      {symbol &&
        fund.data &&
        (fund.data.market_cap != null || fund.data.pe != null || fund.data.net_margin != null) && (
          <div className="snapshot">
            <span>
              <i>市值</i>
              {fmtMoney(fund.data.market_cap, fund.data.currency)}
            </span>
            <span>
              <i>市盈率</i>
              {fund.data.pe != null ? fund.data.pe.toFixed(1) : '—'}
            </span>
            <span>
              <i>净利率</i>
              {fmtPctPlain(fund.data.net_margin)}
            </span>
          </div>
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
