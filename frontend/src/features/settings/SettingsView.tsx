import {
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { useUI } from '../../store'
import {
  useDeleteConnection,
  useSetRoleTarget,
  useSetSecret,
  useSetSourceConfig,
  useSettingsConfig,
  useTestConnection,
  useUpsertConnection,
  type Connection,
  type RoleTarget,
  type SourceGroup,
  type SourceStatus,
  type TestResult,
  type TwAccount,
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
  const [key, setKey] = useState(conn?.api_key ?? '') // 明文预填（仅本地）
  const [websearch, setWebsearch] = useState(conn?.web_search ?? false)
  const [result, setResult] = useState<TestResult | null>(null)
  const isNew = !conn
  const canTest = !!base && !!model && (!isNew || !!key)

  const save = async () => {
    // 不清空 key：卡片按 id keyed 不重挂载，清空会让明文 key「看起来消失」（数据其实已存）
    await upsert.mutateAsync({
      id: conn?.id,
      name,
      base_url: base,
      model,
      api_key: key || null,
      web_search: websearch,
    })
    onDone?.()
  }
  const copy = async () => {
    // 不带 id ＝ 后端新建一条；名字加 (copy)，连 key 一并复制，方便快速加模型
    await upsert.mutateAsync({
      name: `${name} (copy)`,
      base_url: base,
      model,
      api_key: key || null,
      web_search: websearch,
    })
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
        className="cfg-input mono"
        type="text"
        autoComplete="off"
        spellCheck={false}
        placeholder="API key"
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <label className="conn-ws">
        <button
          type="button"
          className={`ssrc-toggle ${websearch ? 'on' : ''}`}
          onClick={() => setWebsearch((v) => !v)}
        >
          <span className="ssrc-knob" />
        </button>
        <span>
          联网检索
          <span className="faint"> · Qwen/百炼 enable_search，供「研」「信源调研」</span>
        </span>
      </label>
      <div className="conn-actions">
        {result && (
          <span className={`conn-test ${result.ok ? 'ok' : 'err'}`}>
            {result.ok ? `✓ 连通 · ${result.latency_ms}ms · ${result.reply || 'ok'}` : `✗ ${result.error}`}
          </span>
        )}
        <span className="conn-actions-sp" />
        {!isNew && (
          <>
            <button className="btn btn-ghost jsm" onClick={copy} disabled={upsert.isPending}>
              复制
            </button>
            <button className="btn btn-ghost jsm" onClick={() => del.mutate(conn.id)}>
              删除
            </button>
          </>
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
// 信源详情子页：只放名称 + 状态 + 可操作项（key / 账户 / 关键词）。不写任何说明性文案。
function SourceDetail({ s }: { s: SourceStatus }) {
  const setSecret = useSetSecret()
  const [key, setKey] = useState(s.key_value ?? '') // 明文预填（仅本地）
  const isToken = s.cred === 'token'
  const hasNothing = !s.key_env && s.config.length === 0
  return (
    <div className="src2-page">
      <div className="src2-phead">
        <h2>{s.name}</h2>
        <span className={`badge ${s.configured ? 'on' : ''}`}>{s.status}</span>
      </div>

      {s.key_env && (
        <div className="src2-field">
          <div className="src2-flabel">{isToken ? '登录 token' : 'API key'}</div>
          <div className="src-keyrow">
            <input
              className="cfg-input mono"
              type="text"
              autoComplete="off"
              spellCheck={false}
              placeholder={isToken ? 'token' : 'API key'}
              value={key}
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
        </div>
      )}

      {s.config.map((f) => (
        <div key={f.field} className="src2-field">
          <div className="src2-flabel">{f.label}</div>
          {f.type === 'accounts' ? (
            <AccountsEditor id={s.id} field={f.field} value={f.value as TwAccount[]} />
          ) : (
            <TagsEditor id={s.id} field={f.field} value={f.value as string[]} />
          )}
        </div>
      ))}

      {hasNothing && <div className="src2-none faint">无需配置</div>}
    </div>
  )
}

// 账户分类（与 x_accounts.yaml / TW_CATS 对齐）
const ACCT_CATS = [
  { v: 'ai', l: '大模型' },
  { v: 'chips', l: '芯片' },
  { v: 'space', l: '航天' },
  { v: 'robotics', l: '机器人' },
  { v: 'tech', l: '科技' },
]
const catLabel = (v: string) => ACCT_CATS.find((c) => c.v === v)?.l ?? v

// 关键词标签编辑器（tags 类型）
function TagsEditor({ id, field, value }: { id: string; field: string; value: string[] }) {
  const set = useSetSourceConfig()
  const [draft, setDraft] = useState('')
  const commit = (next: string[]) => set.mutate({ id, field, value: next })
  const add = () => {
    const v = draft.trim()
    if (v && !value.includes(v)) commit([...value, v])
    setDraft('')
  }
  return (
    <div className="cfg-tags">
      {value.map((k, i) => (
        <span key={i} className="cfg-tag">
          {k}
          <button onClick={() => commit(value.filter((_, j) => j !== i))} aria-label="删除">
            ×
          </button>
        </span>
      ))}
      <input
        className="cfg-tag-input"
        placeholder="加关键词 ↵"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') add()
        }}
      />
    </div>
  )
}

// 账户编辑器（accounts 类型：screen_name + 分类）
function AccountsEditor({ id, field, value }: { id: string; field: string; value: TwAccount[] }) {
  const set = useSetSourceConfig()
  const [sn, setSn] = useState('')
  const [cat, setCat] = useState('ai')
  const commit = (next: TwAccount[]) => set.mutate({ id, field, value: next })
  const add = () => {
    const v = sn.trim().replace(/^@/, '')
    if (v && !value.some((a) => a.screen_name.toLowerCase() === v.toLowerCase()))
      commit([...value, { screen_name: v, category: cat }])
    setSn('')
  }
  return (
    <div className="cfg-accts">
      <div className="cfg-acct-list">
        {value.map((a, i) => (
          <div key={i} className="cfg-acct">
            <span className="cfg-acct-sn">@{a.screen_name}</span>
            <span className="cfg-acct-cat">{catLabel(a.category)}</span>
            <button
              className="cfg-acct-del"
              onClick={() => commit(value.filter((_, j) => j !== i))}
              aria-label="删除"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="cfg-acct-add">
        <span className="cfg-at">@</span>
        <input
          className="cfg-input"
          placeholder="账号（不含 @）"
          value={sn}
          onChange={(e) => setSn(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') add()
          }}
        />
        <select className="cfg-sel" value={cat} onChange={(e) => setCat(e.target.value)}>
          {ACCT_CATS.map((c) => (
            <option key={c.v} value={c.v}>
              {c.l}
            </option>
          ))}
        </select>
        <button className="btn jsm" onClick={add} disabled={!sn.trim()}>
          添加
        </button>
      </div>
    </div>
  )
}

const GROUP_FALLBACK: SourceGroup[] = [
  { id: 'finance', label: '财经', blurb: '' },
  { id: 'news', label: '新闻', blurb: '' },
  { id: 'forum', label: '论坛', blurb: '' },
]

// 二级菜单：左侧按 财经/新闻/论坛 分组列出信源，右侧是选中源的子页面；中缝可拖拽调宽
function SourcesPage({ sources, groups }: { sources: SourceStatus[]; groups: SourceGroup[] }) {
  const order = groups.length ? groups : GROUP_FALLBACK
  const [selId, setSelId] = useState<string>('')
  const sel = sources.find((s) => s.id === selId) ?? sources[0]
  const srcNavW = useUI((s) => s.srcNavW)
  const setSrcNavW = useUI((s) => s.setSrcNavW)

  const onResize = (e: ReactPointerEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = srcNavW
    const move = (ev: globalThis.PointerEvent) => setSrcNavW(startW + (ev.clientX - startX))
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.classList.remove('resizing')
    }
    document.body.classList.add('resizing')
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  return (
    <div className="src2" style={{ '--src-nav-w': `${srcNavW}px` } as CSSProperties}>
      <nav className="src2-nav">
        {order.map((g) => {
          const items = sources.filter((s) => s.group === g.id)
          if (!items.length) return null
          return (
            <div key={g.id} className="src2-group">
              <div className="src2-glabel">{g.label}</div>
              {items.map((s) => (
                <button
                  key={s.id}
                  className={`src2-item ${sel?.id === s.id ? 'active' : ''}`}
                  onClick={() => setSelId(s.id)}
                >
                  <span className="src2-iname">{s.name}</span>
                  <span className={`src2-dot ${s.configured ? 'on' : ''}`} />
                </button>
              ))}
            </div>
          )
        })}
      </nav>
      <div className="src2-resize" onPointerDown={onResize} title="拖动调整宽度" />
      <div className="src2-detail">{sel && <SourceDetail key={sel.id} s={sel} />}</div>
    </div>
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
      {page === 'sources' && (
        <SourcesPage sources={cfg.data?.sources ?? []} groups={cfg.data?.source_groups ?? []} />
      )}
    </div>
  )
}
