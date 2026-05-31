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
      <div className="eyebrow">设置</div>
      <h1 className="set-page-title" style={{ marginTop: 8 }}>偏好</h1>

      <div className="set-card-h">排版 · 字号 / 行距 / 字体（整页实时生效）</div>
      <div className="set-card">
        <div className="set-row">
          <div>
            <div className="k">正文字号</div>
            <div className="d">全局基准字号</div>
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

      <div className="set-card-h">主题与色彩</div>
      <div className="set-card">
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

      <div className="set-card-h">LLM 厂商 · 角色路由</div>
      <div className="set-card">
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
      </div>
      <div className="hedge" style={{ maxWidth: 680 }}>
        在 <span className="mono">backend/.env</span> 配置厂商 key / base_url 与 <span className="mono">AUGUR_ROLE_*</span> 角色路由（见 .env.example），重启后端生效。
      </div>
    </div>
  )
}
