import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { useUI } from '../../store'
import { useOhlcv, useQuote } from '../../api'

// 与 index.css 的 token 镜像（图表用 canvas，直接取色避免读 CSS 变量的时序问题）
const PALETTE = {
  light: { green: '#7fa189', red: '#c68c7c', surface: '#fbfaf5', border: '#e4e0d3', faint: '#9a9483', accent: '#d97757' },
  dark: { green: '#8fb096', red: '#d49b8b', surface: '#282622', border: '#39352f', faint: '#766f63', accent: '#e08a6a' },
}

const TF = [
  { label: '1月', interval: '1d', range: '1m' },
  { label: '6月', interval: '1d', range: '6m' },
  { label: '1年', interval: '1d', range: '1y' },
  { label: '5年', interval: '1w', range: '5y' },
]

const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })

export default function KLineView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const theme = useUI((s) => s.theme)
  const conv = useUI((s) => s.convention)
  const [tf, setTf] = useState(TF[2])

  const ohlcv = useOhlcv(symbol, tf.interval, tf.range)
  const quote = useQuote(symbol)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  // 建图（仅一次）
  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, { autoSize: true })
    const series = chart.addSeries(CandlestickSeries, {})
    chartRef.current = chart
    seriesRef.current = series
    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  // 主题化（蜡笔纸感）
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
    series.applyOptions({
      upColor: up,
      downColor: down,
      borderUpColor: up,
      borderDownColor: down,
      wickUpColor: up,
      wickDownColor: down,
      borderVisible: true,
    })
  }, [theme, conv])

  // 数据
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

  const q = quote.data
  const up = q ? q.change >= 0 : true
  const [mkt, code] = symbol ? symbol.split(':') : ['', '']

  return (
    <>
      {symbol && (
        <div className="stock-head">
          <div>
            <h2>
              {code} <span className="sub">{symbol} · {mkt}</span>
            </h2>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 8 }}>
              <span className="px">{q ? fmt(q.price) : '—'}</span>
              {q && (
                <span className={`pill ${up ? 'up' : 'down'}`} style={{ fontSize: '1rem' }}>
                  {up ? '▲' : '▼'} {Math.abs(q.change).toFixed(2)} ({Math.abs(q.change_pct).toFixed(2)}%)
                </span>
              )}
            </div>
          </div>
          <div className="tf">
            {TF.map((t) => (
              <span
                key={t.label}
                className={`chip ${tf.label === t.label ? 'active' : ''}`}
                onClick={() => setTf(t)}
              >
                {t.label}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="chart-wrap" style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          style={{ width: '100%', height: '100%', visibility: symbol ? 'visible' : 'hidden' }}
        />
        {!symbol && (
          <div className="empty" style={{ position: 'absolute', inset: 0 }}>
            <div style={{ fontSize: '1.1rem', color: 'var(--text-muted)' }}>从左侧选择一支标的</div>
            <div className="faint">美 / 港 / A / 韩 · 蜡笔纸感 K 线</div>
          </div>
        )}
      </div>

      {ohlcv.error && (
        <div className="faint" style={{ marginTop: 10, color: 'var(--down)' }}>
          K线获取失败：{(ohlcv.error as Error).message}
        </div>
      )}
      {ohlcv.data && (
        <div className="faint" style={{ marginTop: 8, fontSize: '.74rem' }}>
          数据源 {ohlcv.data.source} · {ohlcv.data.candles.length} 根 · {tf.interval}
          {ohlcv.data.cached ? ' · 缓存' : ''} · 免费源可能延迟/有误，仅供研究
        </div>
      )}
    </>
  )
}
