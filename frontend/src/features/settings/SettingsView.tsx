import {
  useEffect,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useUI } from '../../store'
import GripDots from '../../components/GripDots'
import {
  useDeleteConnection,
  useLlmUsage,
  useReorderConnections,
  useSchedule,
  useSetRoleTarget,
  useSetSchedule,
  useSetSecret,
  useSetSourceConfig,
  useSettingsConfig,
  useTestAllConnections,
  useTestConnection,
  useTestSource,
  useUpsertConnection,
  type Connection,
  type RoleTarget,
  type Schedule,
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
function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="set2-sec">
      <div className="set2-sec-head">
        <h2 className="set2-sec-h">{title}</h2>
        {action}
      </div>
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
    panelW,
    newsSubW,
    srcNavW,
    kanColW,
    setTheme,
    setTextBase,
    setLeading,
    setDisplayFont,
    setConvention,
    resetLayout,
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
        <Row label="英文标题字体">
          <Seg
            value={displayFont}
            onChange={setDisplayFont}
            options={[{ v: 'serif', label: '衬线' }, { v: 'sans', label: '无衬线' }]}
          />
        </Row>
      </Section>
      <Section title="布局">
        <Row label="栏宽">
          <span className="layout-sizes mono">
            {panelW} · {newsSubW} · {srcNavW} · {kanColW.join('/')}
          </span>
          <button className="btn jsm" onClick={resetLayout}>
            恢复默认
          </button>
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

// ───────────────────────── 自动（白天每小时「全部生成」）─────────────────────────
function SchedulePage() {
  const q = useSchedule()
  const set = useSetSchedule()
  const cur = q.data
  const HOURS = Array.from({ length: 24 }, (_, i) => i)
  if (q.isLoading && !cur) return <div className="report-card faint">加载…</div>
  if (!cur)
    return (
      <div className="report-card err">
        加载失败
        <button className="btn jsm" style={{ marginLeft: 10 }} onClick={() => q.refetch()}>
          重试
        </button>
      </div>
    )
  return (
    <>
      <Section title="白天自动 · 全部生成">
        <Row label="自动刷新并生成">
          <Seg
            value={cur.enabled ? 'on' : 'off'}
            onChange={(v) => set.mutate({ enabled: v === 'on' })}
            options={[{ v: 'on', label: '开' }, { v: 'off', label: '关' }]}
          />
        </Row>
        <Row label="时间窗">
          <div className="sched-window">
            <select
              className="cfg-input"
              value={cur.start_hour}
              disabled={!cur.enabled}
              onChange={(e) => set.mutate({ start_hour: +e.target.value })}
            >
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, '0')}:00
                </option>
              ))}
            </select>
            <span className="faint">至</span>
            <select
              className="cfg-input"
              value={cur.end_hour}
              disabled={!cur.enabled}
              onChange={(e) => set.mutate({ end_hour: +e.target.value })}
            >
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, '0')}:00
                </option>
              ))}
            </select>
          </div>
        </Row>
        <Row label="固定任务">
          <span className="faint mono">07:30 · 23:30</span>
        </Row>
      </Section>
      <GenDepthSection cur={cur} set={set} />
    </>
  )
}

const CAP_PRESETS = [200, 500, 1000, 2000, 3000, 5000]
const BRIEF_PRESETS = [3, 5, 8, 10, 15]

// 蒸馏深度：要事/机会喂 LLM 的当日条数上限（日报不受限）。同属「知·生成」配置，放「自动」页。
function GenDepthSection({ cur, set }: { cur: Schedule; set: ReturnType<typeof useSetSchedule> }) {
  const cap = cur.cluster_input_max
  const list = cap > 0 && !CAP_PRESETS.includes(cap) ? [...CAP_PRESETS, cap].sort((a, b) => a - b) : CAP_PRESETS
  const briefList = BRIEF_PRESETS.includes(cur.brief_top_n)
    ? BRIEF_PRESETS
    : [...BRIEF_PRESETS, cur.brief_top_n].sort((a, b) => a - b)
  return (
    <Section title="生成 · 蒸馏深度">
      <Row label="要事 / 机会 输入上限">
        <select
          className="cfg-input"
          value={cap}
          onChange={(e) => set.mutate({ cluster_input_max: +e.target.value })}
        >
          {list.map((n) => (
            <option key={n} value={n}>
              {n} 条
            </option>
          ))}
          <option value={0}>不限</option>
        </select>
      </Row>
      <Row label="今日要事 条数">
        <select
          className="cfg-input"
          value={cur.brief_top_n}
          onChange={(e) => set.mutate({ brief_top_n: +e.target.value })}
        >
          {briefList.map((n) => (
            <option key={n} value={n}>
              {n} 条
            </option>
          ))}
        </select>
      </Row>
    </Section>
  )
}

// ───────────────────────── 模型 ─────────────────────────
function ConnectionCard({
  conn,
  onDone,
  injected,
}: {
  conn: Connection | null
  onDone?: () => void
  injected?: TestResult | null // 「测试全部」注入的结果（本卡自测会覆盖它）
}) {
  const upsert = useUpsertConnection()
  const del = useDeleteConnection()
  const test = useTestConnection()
  const [name, setName] = useState(conn?.name ?? '')
  const [base, setBase] = useState(conn?.base_url ?? '')
  const [model, setModel] = useState(conn?.model ?? '')
  const [key, setKey] = useState(conn?.api_key ?? '') // 明文预填（仅本地）
  const [open, setOpen] = useState(!conn)
  const [result, setResult] = useState<TestResult | null>(null)
  const shown = result ?? injected ?? null
  // 保存后刷新会带回已存明文 key → 回灌输入框，保证**长期明文可见**（作者要求）。
  // 依赖 conn.api_key：仅它真正变化（即保存成功后）才同步，不会覆盖正在输入的内容。
  useEffect(() => {
    setName(conn?.name ?? '')
    setBase(conn?.base_url ?? '')
    setModel(conn?.model ?? '')
    setKey(conn?.api_key ?? '')
    setOpen(!conn)
  }, [conn?.id, conn?.name, conn?.base_url, conn?.model, conn?.api_key])
  const isNew = !conn
  const canTest = !!base && !!model && (!isNew || !!key)
  const host = base.replace(/^https?:\/\//, '').replace(/\/$/, '') || 'base_url'

  // web_search 不再在此 UI 暴露（作者：先去掉联网检索按钮）；省略该字段＝后端保留已存值不动。
  const save = async () => {
    // 不清空 key：卡片按 id keyed 不重挂载，清空会让明文 key「看起来消失」（数据其实已存）
    await upsert.mutateAsync({ id: conn?.id, name, base_url: base, model, api_key: key || null })
    onDone?.()
  }
  const copy = async () => {
    // 不带 id ＝ 后端新建一条；名字加 (copy)，连 key 一并复制，方便快速加模型
    await upsert.mutateAsync({ name: `${name} (copy)`, base_url: base, model, api_key: key || null })
  }
  const runTest = async () => {
    setResult(null)
    const payload =
      conn && !key ? { connection_id: conn.id, base_url: base, model } : { base_url: base, api_key: key, model }
    setResult(await test.mutateAsync(payload))
  }

  return (
    <div className={`conn-card ${isNew ? 'is-new' : ''} ${open ? 'is-open' : 'is-collapsed'}`}>
      <div className="conn-head">
        <div className="conn-summary">
          <div className="conn-summary-name">{name || '未命名连接'}</div>
          <div className="conn-summary-meta">
            <span className="mono">{model || 'model'}</span>
            <span>{host}</span>
          </div>
        </div>
        {shown && (
          <span
            className={`conn-test ${shown.ok ? 'ok' : 'err'}`}
            title={shown.ok ? shown.reply || 'ok' : shown.error}
          >
            {shown.ok ? `✓ ${shown.latency_ms}ms` : `✗ ${shown.error}`}
          </span>
        )}
        <button className="btn btn-ghost jsm" onClick={runTest} disabled={test.isPending || !canTest}>
          {test.isPending ? '测试中…' : '测试'}
        </button>
        {!isNew && (
          <>
            <button className="btn btn-ghost jsm" onClick={() => setOpen((v) => !v)}>
              {open ? '收起' : '编辑'}
            </button>
            <button className="btn btn-ghost jsm" onClick={copy} disabled={upsert.isPending} title="复制为新连接">
              复制
            </button>
            <button className="btn btn-ghost jsm conn-del" onClick={() => del.mutate(conn.id)} title="删除">
              删除
            </button>
          </>
        )}
        {open && (
          <button
            className="btn btn-primary jsm"
            onClick={save}
            disabled={upsert.isPending || !name || !base || !model}
          >
            保存
          </button>
        )}
      </div>
      {open && (
        <div className="conn-fields">
          <input
            className="cfg-input conn-name"
            placeholder="连接名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="cfg-input mono conn-f-base"
            placeholder="base_url"
            value={base}
            onChange={(e) => setBase(e.target.value)}
          />
          <input
            className="cfg-input mono conn-f-model"
            placeholder="model id"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <input
            className="cfg-input mono conn-f-key"
            type="text"
            autoComplete="off"
            spellCheck={false}
            placeholder="API key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </div>
      )}
    </div>
  )
}

// 可拖拽排序的连接卡：grip 在左侧 gutter，hover 浮现；只 grip 可拖，卡内输入不受影响
function SortableConnCard({ conn, injected }: { conn: Connection; injected?: TestResult | null }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: conn.id,
  })
  return (
    <div
      ref={setNodeRef}
      className={`conn-sortable ${isDragging ? 'dragging' : ''}`}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.7 : 1 }}
    >
      <button className="conn-grip" {...attributes} {...listeners} title="拖动排序" aria-label="拖动排序">
        <GripDots />
      </button>
      <ConnectionCard conn={conn} injected={injected} />
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

function fmtTok(n: number | null | undefined): string {
  const v = n ?? 0
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}k`
  return String(v)
}

// 用量（§6 看成本）：近 30 天 token 按 角色/模型 聚合。成本多半算不出（中转/国产模型不在价表），
// 但 token 始终有——作者据此知道每天烧了多少。
function UsageSection() {
  const usage = useLlmUsage(30)
  const d = usage.data
  const t = d?.total
  const empty = !d || (t?.calls ?? 0) === 0
  return (
    <Section title="用量 · 近 30 天">
      {empty ? (
        <div className="usage-empty faint">暂无用量</div>
      ) : (
        <div className="usage">
          <div className="usage-total">
            <span>
              <i>调用</i>
              <b>{t!.calls}</b>
            </span>
            <span>
              <i>输入 tokens</i>
              <b>{fmtTok(t!.prompt_tokens)}</b>
            </span>
            <span>
              <i>输出 tokens</i>
              <b>{fmtTok(t!.completion_tokens)}</b>
            </span>
            {(t!.cost_usd ?? 0) > 0 && (
              <span>
                <i>估算成本</i>
                <b>${(t!.cost_usd ?? 0).toFixed(3)}</b>
              </span>
            )}
          </div>
          <div className="usage-rows">
            {d!.by_role_model.map((r, i) => (
              <div className="usage-row" key={`${r.role}-${r.model}-${i}`}>
                <span className="usage-role">{r.role}</span>
                <span className="usage-model">{r.model || '—'}</span>
                <span className="usage-tok">
                  {fmtTok((r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0))} tok · {r.calls} 次
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Section>
  )
}

function ModelsPage({ conns, roles }: { conns: Connection[]; roles: RoleTarget[] }) {
  const [adding, setAdding] = useState(false)
  const reorder = useReorderConnections()
  const testAll = useTestAllConnections()
  const [allResults, setAllResults] = useState<Record<string, TestResult>>({})
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const ids = conns.map((c) => c.id)
    const from = ids.indexOf(String(active.id))
    const to = ids.indexOf(String(over.id))
    if (from < 0 || to < 0) return
    reorder.mutate(arrayMove(ids, from, to))
  }
  const runTestAll = async () => {
    setAllResults({})
    setAllResults(await testAll.mutateAsync())
  }
  const okN = Object.values(allResults).filter((r) => r.ok).length
  const doneN = Object.keys(allResults).length
  return (
    <>
      <Section
        title="LLM 连接"
        action={
          conns.length > 0 && (
            <div className="sec-act">
              {doneN > 0 && !testAll.isPending && (
                <span className="sec-act-note faint">
                  {okN}/{doneN} 连通
                </span>
              )}
              <button className="btn btn-ghost jsm" onClick={runTestAll} disabled={testAll.isPending}>
                {testAll.isPending ? '测试中…' : '测试全部'}
              </button>
            </div>
          )
        }
      >
        <div className="conn-list">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={conns.map((c) => c.id)} strategy={verticalListSortingStrategy}>
              {conns.map((c) => (
                <SortableConnCard key={c.id} conn={c} injected={allResults[c.id]} />
              ))}
            </SortableContext>
          </DndContext>
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
      <UsageSection />
    </>
  )
}

// ───────────────────────── 数据 / 信源 ─────────────────────────
// 信源详情子页：只放名称 + 状态 + 可操作项（key / 账户 / 关键词）。不写任何说明性文案。
function SourceDetail({ s }: { s: SourceStatus }) {
  const setSecret = useSetSecret()
  const test = useTestSource()
  const [key, setKey] = useState(s.key_value ?? '') // 明文预填（仅本地）
  const [tres, setTres] = useState<Awaited<ReturnType<typeof test.mutateAsync>> | null>(null)
  // 保存后刷新带回已存明文 key → 回灌输入框，保证长期明文可见（作者要求）。
  useEffect(() => setKey(s.key_value ?? ''), [s.key_value])
  const isToken = s.cred === 'token'
  const hasNothing = !s.key_env && s.config.length === 0
  const runTest = async () => {
    setTres(null)
    setTres(await test.mutateAsync(s.id))
  }
  return (
    <div className="src2-page">
      <div className="src2-phead">
        <h2>{s.name}</h2>
        <span className={`badge ${s.configured ? 'on' : ''}`}>{s.status}</span>
        <button className="btn jsm src2-test" disabled={test.isPending} onClick={runTest}>
          {test.isPending ? '测试中…' : '测试'}
        </button>
      </div>
      {tres && (
        <div className={`conn-test ${tres.ok ? 'ok' : 'err'} src2-tres`}>
          {tres.ok
            ? `✓ 可用 · ${tres.latency_ms}ms${tres.count != null ? ` · ${tres.count} 条` : ''}${tres.note ? ` · ${tres.note}` : ''}`
            : `✗ ${tres.error}`}
        </div>
      )}

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
              onClick={() => setSecret.mutate({ name: s.key_env!, value: key.trim() })}
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
  { v: 'investor', l: '投资人' },
  { v: 'macro', l: '宏观' },
  { v: 'other', l: '其他' },
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
  // 外观/自动页不依赖 /settings/config（各自本地或独立查询）；模型/信源页需 config，缺数据时给明确反馈
  const needsCfg = page === 'models' || page === 'sources'
  return (
    <div className="set2-body">
      {page === 'appearance' && <AppearancePage />}
      {page === 'schedule' && <SchedulePage />}
      {needsCfg && cfg.isLoading && !cfg.data ? (
        <div className="report-card faint">加载配置…</div>
      ) : needsCfg && cfg.isError ? (
        <div className="report-card err">
          配置加载失败：{(cfg.error as Error).message}
          <button className="btn jsm" style={{ marginLeft: 10 }} onClick={() => cfg.refetch()}>
            重试
          </button>
        </div>
      ) : (
        <>
          {page === 'models' && (
            <ModelsPage
              conns={cfg.data?.llm.connections ?? []}
              roles={cfg.data?.llm.roles ?? []}
            />
          )}
          {page === 'sources' && (
            <SourcesPage sources={cfg.data?.sources ?? []} groups={cfg.data?.source_groups ?? []} />
          )}
        </>
      )}
    </div>
  )
}
