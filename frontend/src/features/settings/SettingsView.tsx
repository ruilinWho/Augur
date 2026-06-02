import { useState } from 'react'
import { useUI } from '../../store'
import {
  useSettingsConfig,
  useSetRole,
  useSetSecret,
  type ProviderStatus,
  type SourceStatus,
} from '../../api'

// LLM 角色路由卡：provider:model 文本框 + 保存（空=回退 .env）
function RoleCard({
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
    <div className="scard">
      <div className="scard-h">
        <span className="scard-name">{role}</span>
        <span className="badge" style={{ color: configured ? 'var(--up)' : 'var(--text-faint)' }}>
          {configured ? '已配置' : '未配置'}
        </span>
      </div>
      <div className="scard-d">{configured ? desc : '把该角色指到某厂商:模型'}</div>
      <div className="scard-field">
        <input
          className="cfg-input mono"
          value={val}
          placeholder="provider:model"
          onChange={(e) => setVal(e.target.value)}
        />
        <button
          className="btn jsm"
          disabled={!dirty || setRole.isPending}
          onClick={() => setRole.mutate({ role, spec: val.trim() })}
        >
          保存
        </button>
      </div>
    </div>
  )
}

// LLM 厂商卡：API key（密文）+ base_url（中转站）+ 保存/清除
function ProviderCard({ p }: { p: ProviderStatus }) {
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
    <div className="scard">
      <div className="scard-h">
        <span className="scard-name">{p.id}</span>
        <span style={{ color: p.key_configured ? 'var(--up)' : 'var(--text-faint)' }} className="badge">
          {p.key_configured ? `key ${p.key_hint}` : '未配置 key'}
        </span>
      </div>
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
      <div className="scard-actions">
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
  )
}

const TONE: Record<string, string> = {
  free_rss: 'var(--up)',
  free_api: 'var(--accent)',
  paid_api: 'var(--text-muted)',
}

// 数据/新闻信源卡：状态徽标 +（付费源）API key
function SourceCard({ s }: { s: SourceStatus }) {
  const setSecret = useSetSecret()
  const [key, setKey] = useState('')
  const tone = s.configured ? 'var(--up)' : TONE[s.access] ?? 'var(--text-faint)'
  return (
    <div className="scard">
      <div className="scard-h">
        <span className="scard-name">
          {s.name} <span className="src-cat">{s.category}</span>
        </span>
        <span className="badge" style={{ color: tone }}>
          {s.status}
          {s.hint ? ` · ${s.hint}` : ''}
        </span>
      </div>
      <div className="scard-d">{s.note}</div>
      {s.key_env && (
        <div className="scard-field">
          <input
            className="cfg-input"
            type="password"
            autoComplete="off"
            value={key}
            placeholder={s.configured ? 'key（留空＝不改）' : '粘贴 API key'}
            onChange={(e) => setKey(e.target.value)}
          />
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
      )}
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
    <div className="set-wrap">
      <div className="eyebrow">设置</div>
      <h1 className="set-page-title" style={{ marginTop: 8 }}>偏好</h1>

      <div className="set-card-h">排版 · 字号 / 行距 / 字体（整页实时生效）</div>
      <div className="set-grid">
        <div className="scard">
          <div className="scard-h">
            <span className="scard-name">正文字号</span>
            <span className="val">{textBase}px</span>
          </div>
          <div className="scard-d">全局基准字号</div>
          <input type="range" min={14} max={19} step={1} value={textBase} onChange={(e) => setTextBase(+e.target.value)} />
        </div>
        <div className="scard">
          <div className="scard-h">
            <span className="scard-name">行距</span>
            <span className="val">{leading.toFixed(2)}</span>
          </div>
          <div className="scard-d">行与行的呼吸感</div>
          <input type="range" min={1.4} max={1.9} step={0.02} value={leading} onChange={(e) => setLeading(+e.target.value)} />
        </div>
        <div className="scard">
          <div className="scard-h">
            <span className="scard-name">英文标题字体</span>
          </div>
          <div className="scard-d">默认 Source Serif 4 衬线（中文恒为苹方）</div>
          <div className="seg">
            <button aria-pressed={displayFont === 'serif'} onClick={() => setDisplayFont('serif')}>衬线</button>
            <button aria-pressed={displayFont === 'sans'} onClick={() => setDisplayFont('sans')}>无衬线</button>
          </div>
        </div>
      </div>

      <div className="set-card-h">主题与色彩</div>
      <div className="set-grid">
        <div className="scard">
          <div className="scard-h">
            <span className="scard-name">主题</span>
          </div>
          <div className="scard-d">默认亮色，明暗皆暖</div>
          <div className="seg">
            <button aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>☀ 亮</button>
            <button aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>☾ 暗</button>
          </div>
        </div>
        <div className="scard">
          <div className="scard-h">
            <span className="scard-name">涨跌色习惯</span>
          </div>
          <div className="scard-d">蜡笔纸感色，按市场习惯切换</div>
          <div className="seg">
            <button aria-pressed={convention === 'us'} onClick={() => setConvention('us')}>绿涨红跌</button>
            <button aria-pressed={convention === 'cn'} onClick={() => setConvention('cn')}>红涨绿跌</button>
          </div>
        </div>
      </div>

      <div className="set-card-h">LLM 角色路由（改后即时生效，无需重启）</div>
      <div className="set-grid">
        {cfg.data?.llm.roles.map((r) => (
          <RoleCard
            key={r.role}
            role={r.role}
            spec={r.spec}
            configured={r.configured}
            desc={r.provider ? `${r.provider} · ${r.model}` : ''}
          />
        ))}
      </div>

      <div className="set-card-h">LLM 厂商 · key / base_url</div>
      <div className="set-grid">
        {cfg.data?.llm.providers.map((p) => (
          <ProviderCard key={p.id} p={p} />
        ))}
      </div>

      <div className="set-card-h">数据 / 新闻信源 · API（按需配 key，逐步「一条龙」）</div>
      <div className="set-grid">
        {cfg.data?.sources.map((s) => (
          <SourceCard key={s.id} s={s} />
        ))}
        {!cfg.data && <div className="scard-d">加载信源配置…</div>}
      </div>

      <div className="hedge">
        密钥仅存于本机 <span className="mono">data/config.local.json</span>（不入库、不外传、界面只显末位），
        改动即时注入运行环境。也可继续用 <span className="mono">backend/.env</span>（见 .env.example）。
      </div>
    </div>
  )
}
