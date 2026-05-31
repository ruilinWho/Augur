import { useUI } from '../../store'
import { useRoles } from '../../api'

export default function SettingsView() {
  const {
    theme,
    textBase,
    leading,
    displayFont,
    convention,
    setTheme,
    setTextBase,
    setLeading,
    setDisplayFont,
    setConvention,
  } = useUI()
  const roles = useRoles()

  return (
    <div>
      <div className="eyebrow">设置 · 排版</div>
      <h2 style={{ marginTop: 8, marginBottom: 14 }}>排版（字号 / 行距 / 字体）</h2>
      <div className="set-group">
        <div className="set-row">
          <div>
            <div className="k">正文字号</div>
            <div className="d">全局基准字号，整页实时生效</div>
          </div>
          <div className="ctl">
            <input type="range" min={14} max={19} step={1} value={textBase} onChange={(e) => setTextBase(+e.target.value)} />
            <span className="val">{textBase}px</span>
          </div>
        </div>
        <div className="set-row">
          <div>
            <div className="k">行距</div>
            <div className="d">行与行的呼吸感</div>
          </div>
          <div className="ctl">
            <input type="range" min={1.4} max={1.9} step={0.02} value={leading} onChange={(e) => setLeading(+e.target.value)} />
            <span className="val">{leading.toFixed(2)}</span>
          </div>
        </div>
        <div className="set-row">
          <div>
            <div className="k">英文标题字体</div>
            <div className="d">默认 Source Serif 4 衬线（中文恒为苹方）</div>
          </div>
          <div className="ctl">
            <div className="seg">
              <button aria-pressed={displayFont === 'serif'} onClick={() => setDisplayFont('serif')}>衬线</button>
              <button aria-pressed={displayFont === 'sans'} onClick={() => setDisplayFont('sans')}>无衬线</button>
            </div>
          </div>
        </div>
      </div>

      <div className="eyebrow">设置 · 主题与色彩</div>
      <div className="set-group" style={{ marginTop: 12 }}>
        <div className="set-row">
          <div>
            <div className="k">主题</div>
            <div className="d">默认亮色，明暗皆暖</div>
          </div>
          <div className="ctl">
            <div className="seg">
              <button aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>☀ 亮</button>
              <button aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>☾ 暗</button>
            </div>
          </div>
        </div>
        <div className="set-row">
          <div>
            <div className="k">涨跌色习惯</div>
            <div className="d">蜡笔纸感色，按市场习惯切换</div>
          </div>
          <div className="ctl">
            <div className="seg">
              <button aria-pressed={convention === 'us'} onClick={() => setConvention('us')}>绿涨红跌</button>
              <button aria-pressed={convention === 'cn'} onClick={() => setConvention('cn')}>红涨绿跌</button>
            </div>
          </div>
        </div>
      </div>

      <div className="eyebrow">设置 · LLM 厂商</div>
      <div className="set-group" style={{ marginTop: 12 }}>
        {roles.data?.map((r) => (
          <div className="set-row" key={r.role}>
            <div>
              <div className="k">{r.role}</div>
              <div className="d">{r.provider ? `${r.provider} · ${r.model}` : '未配置角色'}</div>
            </div>
            <div className="ctl">
              <span className="badge" style={{ color: r.configured ? 'var(--up)' : 'var(--text-faint)' }}>
                {r.configured ? '已配置' : '未配置'}
              </span>
            </div>
          </div>
        ))}
        <div className="hedge">
          在 <span className="mono">backend/.env</span> 配置厂商 key / base_url 与 <span className="mono">AUGUR_ROLE_*</span> 角色路由（见 .env.example），重启后端生效。
        </div>
      </div>
    </div>
  )
}
