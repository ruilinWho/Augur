import { useState } from 'react'
import { useUI } from '../../store'
import {
  useSettingsConfig,
  useSetRole,
  useSetSecret,
  type ProviderStatus,
  type SourceStatus,
} from '../../api'

// LLM 角色路由行：provider:model 文本框 + 保存（空=回退 .env）
function RoleRow({
  role,
  spec,
  configured,
  desc,
}: {
  role: string
  spec: string
  configured: boolean
  desc: string
}) {
  const setRole = useSetRole()
  const [val, setVal] = useState(spec)
  const dirty = val.trim() !== spec
  return (
    <div className="set-row row-top">
      <div>
        <div className="k">{role}</div>
        <div className="d">{configured ? desc : '未配置'}</div>
      </div>
      <div className="ctl ctl-col">
        <input
          className="cfg-input mono"
          value={val}
          placeholder="provider:model（如 deepseek:deepseek-chat）"
          onChange={(e) => setVal(e.target.value)}
        />
        <div className="cfg-actions">
          <button
            className="btn jsm"
            disabled={!dirty || setRole.isPending}
            onClick={() => setRole.mutate({ role, spec: val.trim() })}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

// LLM 厂商行：API key（密文，留空不改）+ base_url（中转站）+ 保存/清除
function ProviderRow({ p }: { p: ProviderStatus }) {
  const setSecret = useSetSecret()
  const [key, setKey] = useState('')
  const [base, setBase] = useState(p.base_url)
  const baseDirty = base.trim() !== p.base_url
  const save = () => {
    if (key.trim()) setSecret.mutate({ name: p.key_env, value: key.trim() })
    if (baseDirty) setSecret.mutate({ name: p.base_env, value: base.trim() || null })
    setKey('')
  }
  return (
    <div className="set-row row-top">
      <div>
        <div className="k">{p.id}</div>
        <div className="d">{p.key_configured ? `key ${p.key_hint}` : '未配置 key'}</div>
      </div>
      <div className="ctl ctl-col">
        <input
          className="cfg-input"
          type="password"
          autoComplete="off"
          value={key}
          placeholder={p.key_configured ? 'API key（留空＝不改）' : '粘贴 API key'}
          onChange={(e) => setKey(e.target.value)}
        />
        <input
          className="cfg-input mono"
          value={base}
          placeholder="base_url（可选，自配中转站）"
          onChange={(e) => setBase(e.target.value)}
        />
        <div className="cfg-actions">
          {p.key_configured && (
            <button
              className="btn btn-ghost jsm"
              onClick={() => setSecret.mutate({ name: p.key_env, value: null })}
            >
              清除 key
            </button>
          )}
          <button
            className="btn jsm"
            disabled={setSecret.isPending || (!key.trim() && !baseDirty)}
            onClick={save}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

const TONE: Record<string, string> = {
  free_rss: 'var(--up)',
  free_api: 'var(--accent)',
  paid_api: 'var(--text-muted)',
  paid_terminal: 'var(--text-faint)',
  unavailable: 'var(--text-faint)',
}

// 数据/新闻信源行：状态徽标 +（付费源）API key 输入
function SourceRow({ s }: { s: SourceStatus }) {
  const setSecret = useSetSecret()
  const [key, setKey] = useState('')
  const tone = s.configured ? 'var(--up)' : TONE[s.access] ?? 'var(--text-faint)'
  return (
    <div className="set-row row-top">
      <div style={{ maxWidth: 380 }}>
        <div className="k">
          {s.name} <span className="src-cat">{s.category}</span>
        </div>
        <div className="d">{s.note}</div>
      </div>
      <div className="ctl ctl-col">
        <span className="badge" style={{ color: tone }}>
          {s.status}
          {s.hint ? ` · ${s.hint}` : ''}
        </span>
        {s.key_env && (
          <>
            <input
              className="cfg-input"
              type="password"
              autoComplete="off"
              value={key}
              placeholder={s.configured ? 'key（留空＝不改）' : '粘贴 API key'}
              onChange={(e) => setKey(e.target.value)}
            />
            <div className="cfg-actions">
              {s.configured && (
                <button
                  className="btn btn-ghost jsm"
                  onClick={() => setSecret.mutate({ name: s.key_env!, value: null })}
                >
                  清除
                </button>
              )}
              <button
                className="btn jsm"
                disabled={!key.trim() || setSecret.isPending}
                onClick={() => {
                  setSecret.mutate({ name: s.key_env!, value: key.trim() })
                  setKey('')
                }}
              >
                保存
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

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
  const cfg = useSettingsConfig()

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

      <div className="set-card-h">LLM 厂商 · 角色路由（改后即时生效，无需重启）</div>
      <div className="set-card">
        {cfg.data?.llm.roles.map((r) => (
          <RoleRow
            key={r.role}
            role={r.role}
            spec={r.spec}
            configured={r.configured}
            desc={r.provider ? `${r.provider} · ${r.model}` : ''}
          />
        ))}
        <div className="cfg-sub">厂商 key / base_url</div>
        {cfg.data?.llm.providers.map((p) => (
          <ProviderRow key={p.id} p={p} />
        ))}
      </div>

      <div className="set-card-h">数据 / 新闻信源 · API（按需配 key，逐步「一条龙」）</div>
      <div className="set-card">
        {cfg.data?.sources.map((s) => (
          <SourceRow key={s.id} s={s} />
        ))}
        {!cfg.data && <div className="d">加载信源配置…</div>}
      </div>

      <div className="hedge" style={{ maxWidth: 680 }}>
        密钥仅存于本机 <span className="mono">data/config.local.json</span>（不入库、不外传、界面只显末位），
        改动即时注入运行环境。也可继续用 <span className="mono">backend/.env</span>（见 .env.example）。
      </div>
    </div>
  )
}
