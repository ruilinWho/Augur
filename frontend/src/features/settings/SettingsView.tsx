import { useState, type ReactNode } from 'react'
import { useUI } from '../../store'
import {
  useDeleteConnection,
  useSetRoleTarget,
  useSetSecret,
  useSettingsConfig,
  useTestConnection,
  useUpsertConnection,
  type Connection,
  type RoleTarget,
  type SourceStatus,
  type TestResult,
} from '../../api'

// ── 通用：Anthropic 风格的「左标题+说明 / 右控件 + 分隔线」行 ──
function Row({ label, desc, children }: { label: ReactNode; desc?: ReactNode; children: ReactNode }) {
  return (
    <div className="set2-row">
      <div className="set2-row-l">
        <div className="set2-row-lbl">{label}</div>
        {desc != null && <div className="set2-row-desc">{desc}</div>}
      </div>
      <div className="set2-row-ctl">{children}</div>
    </div>
  )
}
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="set2-sec">
      <h2 className="set2-sec-h">{title}</h2>
      <div className="set2-rows">{children}</div>
    </section>
  )
}
function Seg<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { v: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.v} aria-pressed={value === o.v} onClick={() => onChange(o.v)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ───────────────────────── 外观 ─────────────────────────
function AppearancePage() {
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
  return (
    <>
      <h1 className="set2-title">外观</h1>
      <Section title="排版">
        <Row label="正文字号">
          <input type="range" min={14} max={19} step={1} value={textBase} onChange={(e) => setTextBase(+e.target.value)} />
          <span className="val">{textBase}px</span>
        </Row>
        <Row label="行距">
          <input type="range" min={1.4} max={1.9} step={0.02} value={leading} onChange={(e) => setLeading(+e.target.value)} />
          <span className="val">{leading.toFixed(2)}</span>
        </Row>
        <Row label="英文标题字体" desc="中文恒为苹方">
          <Seg
            value={displayFont}
            onChange={setDisplayFont}
            options={[{ v: 'serif', label: '衬线' }, { v: 'sans', label: '无衬线' }]}
          />
        </Row>
      </Section>
      <Section title="主题与色彩">
        <Row label="主题">
          <Seg value={theme} onChange={setTheme} options={[{ v: 'light', label: '☀ 亮' }, { v: 'dark', label: '☾ 暗' }]} />
        </Row>
        <Row label="涨跌色习惯">
          <Seg
            value={convention}
            onChange={setConvention}
            options={[{ v: 'us', label: '绿涨红跌' }, { v: 'cn', label: '红涨绿跌' }]}
          />
        </Row>
      </Section>
    </>
  )
}

// ───────────────────────── 模型 ─────────────────────────
function ConnectionCard({ conn, onDone }: { conn: Connection | null; onDone?: () => void }) {
  const upsert = useUpsertConnection()
  const del = useDeleteConnection()
  const test = useTestConnection()
  const [name, setName] = useState(conn?.name ?? '')
  const [base, setBase] = useState(conn?.base_url ?? '')
  const [model, setModel] = useState(conn?.model ?? '')
  const [key, setKey] = useState('')
  const [result, setResult] = useState<TestResult | null>(null)
  const isNew = !conn
  const canTest = !!base && !!model && (!isNew || !!key)

  const save = async () => {
    await upsert.mutateAsync({ id: conn?.id, name, base_url: base, model, api_key: key || null })
    setKey('')
    onDone?.()
  }
  const runTest = async () => {
    setResult(null)
    const payload =
      conn && !key ? { connection_id: conn.id, base_url: base, model } : { base_url: base, api_key: key, model }
    setResult(await test.mutateAsync(payload))
  }

  return (
    <div className={`conn-card ${isNew ? 'is-new' : ''}`}>
      <input className="cfg-input conn-name" placeholder="连接名称（如 DeepSeek / OhMyGPT 中转）" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="conn-grid">
        <input className="cfg-input mono" placeholder="base_url（如 https://api.deepseek.com）" value={base} onChange={(e) => setBase(e.target.value)} />
        <input className="cfg-input mono" placeholder="model id（如 deepseek-chat）" value={model} onChange={(e) => setModel(e.target.value)} />
      </div>
      <input
        className="cfg-input"
        type="password"
        autoComplete="off"
        placeholder={conn?.key_configured ? `API key（已配 ${conn.key_hint}，留空＝不改）` : '粘贴 API key'}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <div className="conn-actions">
        {result && (
          <span className={`conn-test ${result.ok ? 'ok' : 'err'}`}>
            {result.ok ? `✓ 连通 · ${result.latency_ms}ms · ${result.reply || 'ok'}` : `✗ ${result.error}`}
          </span>
        )}
        <span className="conn-actions-sp" />
        {!isNew && (
          <button className="btn btn-ghost jsm" onClick={() => del.mutate(conn.id)}>
            删除
          </button>
        )}
        <button className="btn jsm" onClick={runTest} disabled={test.isPending || !canTest}>
          {test.isPending ? '测试中…' : '测试连接'}
        </button>
        <button className="btn btn-primary jsm" onClick={save} disabled={upsert.isPending || !name || !base || !model}>
          保存
        </button>
      </div>
    </div>
  )
}

const ROLE_LABEL: Record<string, string> = {
  chat: '对话',
  deep_research: '深度研究',
  summarize: '摘要 / 日报',
  cheap: '便宜（翻译 / 筛选）',
}
function RoleRow({ role, conns }: { role: RoleTarget; conns: Connection[] }) {
  const setRole = useSetRoleTarget()
  return (
    <Row label={ROLE_LABEL[role.role] ?? role.role}>
      <span className={`role-dot ${role.configured ? 'ok' : ''}`} title={role.configured ? '就绪' : '未配'} />
      <select
        className="cfg-input set2-select"
        value={role.connection_id ?? ''}
        onChange={(e) => setRole.mutate({ role: role.role, connection_id: e.target.value || null })}
      >
        <option value="">— 未指定 —</option>
        {conns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </Row>
  )
}

function ModelsPage({ conns, roles }: { conns: Connection[]; roles: RoleTarget[] }) {
  const [adding, setAdding] = useState(false)
  return (
    <>
      <h1 className="set2-title">模型</h1>
      <Section title="LLM 连接">
        <div className="conn-list">
          {conns.map((c) => (
            <ConnectionCard key={c.id} conn={c} />
          ))}
          {adding ? (
            <ConnectionCard conn={null} onDone={() => setAdding(false)} />
          ) : (
            <button className="btn set2-add" onClick={() => setAdding(true)}>
              ＋ 添加连接
            </button>
          )}
        </div>
      </Section>
      <Section title="角色路由">
        {roles.map((r) => (
          <RoleRow key={r.role} role={r} conns={conns} />
        ))}
      </Section>
    </>
  )
}

// ───────────────────────── 数据 / 信源 ─────────────────────────
const ACCESS_TONE: Record<string, string> = {
  free_rss: 'var(--up)',
  free_api: 'var(--accent)',
  paid_api: 'var(--text-muted)',
}

function SourceRow({ s }: { s: SourceStatus }) {
  const setSecret = useSetSecret()
  const [key, setKey] = useState('')
  const tone = s.configured ? 'var(--up)' : ACCESS_TONE[s.access] ?? 'var(--text-faint)'
  return (
    <div className="src-block">
      <div className="src-head2">
        <div className="src-name">
          {s.name} <span className="src-cat">{s.category}</span>
        </div>
        <div className="src-badges">
          {s.payment && <span className="pay-badge">{s.payment}</span>}
          <span className="badge" style={{ color: tone }}>
            {s.status}
            {s.hint ? ` · ${s.hint}` : ''}
          </span>
        </div>
      </div>
      <div className="src-note2">{s.note}</div>
      {s.key_env && (
        <div className="src-keyrow">
          <input
            className="cfg-input"
            type="password"
            autoComplete="off"
            placeholder={s.configured ? 'key（留空＝不改）' : '粘贴 API key'}
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          {s.configured && (
            <button className="btn btn-ghost jsm" onClick={() => setSecret.mutate({ name: s.key_env!, value: null })}>
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

function SourcesPage({ sources }: { sources: SourceStatus[] }) {
  return (
    <>
      <h1 className="set2-title">数据 / 信源 API</h1>
      <Section title="信源">
        {sources.map((s) => (
          <SourceRow key={s.id} s={s} />
        ))}
      </Section>
    </>
  )
}

// 页面由左栏导航（App.tsx）经 store.settingsPage 选择；本组件只渲染选中页的内容。
export default function SettingsView() {
  const page = useUI((s) => s.settingsPage)
  const cfg = useSettingsConfig()
  return (
    <div className="set2-body">
      {page === 'appearance' && <AppearancePage />}
      {page === 'models' && (
        <ModelsPage conns={cfg.data?.llm.connections ?? []} roles={cfg.data?.llm.roles ?? []} />
      )}
      {page === 'sources' && <SourcesPage sources={cfg.data?.sources ?? []} />}
    </div>
  )
}
