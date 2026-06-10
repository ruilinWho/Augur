// ==UserScript==
// @name         Augur 回流 · 网页 Deep Research → 剪贴板
// @namespace    augur.local
// @version      0.1.0
// @description  在 ChatGPT / Claude 网页版一键把当前对话（含 Deep Research 报告）读成干净 Markdown 复制到剪贴板，再粘进 Augur「研·导入研报」。读取走站点同源内部 API（你自己的登录态、你自己的内容），不做自动化驱动会话。
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://claude.ai/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/*
 * 用途与边界（重要）
 * ─────────────────────────────────────────────────────────────
 * Augur 是本地单用户投研工作台。ChatGPT Pro / Claude Max 的网页版 Deep Research 没有 API，
 * 本脚本只做一件事：你点按钮时，读取「你自己登录态下、你自己的那条对话」的同源内部 JSON，
 * 转成 Markdown 写入剪贴板。然后你切到 Augur 的「研 → 导入研报 → ＋导入」粘贴、选来源引擎、
 * 贴上本页链接即可。
 *
 * 它【不】驱动会话、不自动提交、不抓别人的内容、不向任何服务器发数据（连 Augur 后端都不发，
 * 只写剪贴板）。这与「人工导出自己的内容」同级，区别于被各家 ToS 禁止的「程序化驱动会话」。
 * 安装：Tampermonkey/Violentmonkey 新建脚本，粘贴本文件保存即可。
 */

;(function () {
  'use strict'

  const HOST = location.hostname
  const IS_CHATGPT = HOST.includes('chatgpt.com') || HOST.includes('chat.openai.com')
  const IS_CLAUDE = HOST.includes('claude.ai')
  if (!IS_CHATGPT && !IS_CLAUDE) return

  // ── 轻量 toast ──
  function toast(msg, ok = true) {
    const el = document.createElement('div')
    el.textContent = msg
    Object.assign(el.style, {
      position: 'fixed', right: '18px', bottom: '74px', zIndex: 999999,
      padding: '10px 14px', borderRadius: '10px', font: '13px/1.4 system-ui, sans-serif',
      color: '#fff', background: ok ? '#7a8a5f' : '#b4533a', boxShadow: '0 4px 16px rgba(0,0,0,.18)',
      maxWidth: '320px',
    })
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 3200)
  }

  // ── ChatGPT：同源内部 API（/api/auth/session 取 token → /backend-api/conversation/{id}）──
  async function captureChatGPT() {
    const m = location.pathname.match(/\/(?:c|g\/[^/]+\/c)\/([0-9a-f-]{36})/)
    if (!m) throw new Error('请先打开一条具体对话（URL 含 /c/<id>）')
    const convId = m[1]
    const sess = await fetch('/api/auth/session', { credentials: 'include' }).then((r) => r.json())
    const token = sess && sess.accessToken
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    const conv = await fetch(`/backend-api/conversation/${convId}`, {
      credentials: 'include',
      headers,
    }).then((r) => {
      if (!r.ok) throw new Error(`读取对话失败 HTTP ${r.status}`)
      return r.json()
    })
    // 从 current_node 沿 parent 回溯到根，得到线性消息序列
    const map = conv.mapping || {}
    const lines = []
    let node = map[conv.current_node]
    const chain = []
    while (node) {
      chain.push(node)
      node = node.parent ? map[node.parent] : null
    }
    chain.reverse()
    for (const n of chain) {
      const msg = n && n.message
      if (!msg || !msg.author) continue
      const role = msg.author.role
      if (role !== 'user' && role !== 'assistant') continue
      const c = msg.content || {}
      let text = ''
      if (Array.isArray(c.parts)) {
        text = c.parts.filter((p) => typeof p === 'string').join('\n\n')
      } else if (typeof c.text === 'string') {
        text = c.text
      }
      text = (text || '').trim()
      if (!text) continue
      lines.push(role === 'user' ? `> **我：** ${text}\n` : text)
    }
    const title = conv.title || document.title.replace(/\s*[-|].*$/, '')
    return { title, body: lines.join('\n\n---\n\n') }
  }

  // ── Claude：同源内部 API（/api/organizations → /api/organizations/{org}/chat_conversations/{id}）──
  async function captureClaude() {
    const m = location.pathname.match(/\/chat\/([0-9a-f-]{36})/)
    if (!m) throw new Error('请先打开一条具体对话（URL 含 /chat/<id>）')
    const convId = m[1]
    const orgs = await fetch('/api/organizations', { credentials: 'include' }).then((r) => r.json())
    const org = Array.isArray(orgs) && orgs.length ? orgs[0].uuid : null
    if (!org) throw new Error('未找到组织（org）')
    const conv = await fetch(
      `/api/organizations/${org}/chat_conversations/${convId}?tree=True&rendering_mode=raw`,
      { credentials: 'include' },
    ).then((r) => {
      if (!r.ok) throw new Error(`读取对话失败 HTTP ${r.status}`)
      return r.json()
    })
    const msgs = conv.chat_messages || []
    const lines = []
    for (const msg of msgs) {
      const sender = msg.sender // 'human' | 'assistant'
      let text = ''
      if (Array.isArray(msg.content)) {
        text = msg.content
          .map((b) => (b && (b.text || (b.input && JSON.stringify(b.input)))) || '')
          .filter(Boolean)
          .join('\n\n')
      }
      text = (text || msg.text || '').trim()
      if (!text) continue
      lines.push(sender === 'human' ? `> **我：** ${text}\n` : text)
    }
    const title = conv.name || document.title.replace(/\s*[-|].*$/, '')
    return { title, body: lines.join('\n\n---\n\n') }
  }

  async function run() {
    try {
      const { title, body } = IS_CHATGPT ? await captureChatGPT() : await captureClaude()
      if (!body) throw new Error('没读到正文')
      const header = `<!-- ${title} · ${location.href} -->\n\n`
      await navigator.clipboard.writeText(header + body)
      toast(`已复制「${title.slice(0, 24)}」→ 去 Augur 研·导入研报 粘贴`)
    } catch (e) {
      toast('复制失败：' + (e && e.message ? e.message : e), false)
      // 兜底：手动全选复制页面（结构会差些）
      console.error('[Augur capture]', e)
    }
  }

  // ── 悬浮按钮 ──
  const btn = document.createElement('button')
  btn.textContent = '📋 复制到 Augur'
  Object.assign(btn.style, {
    position: 'fixed', right: '18px', bottom: '18px', zIndex: 999999,
    padding: '10px 14px', borderRadius: '999px', border: 'none', cursor: 'pointer',
    font: '13px/1 system-ui, sans-serif', color: '#fff', background: '#c96442',
    boxShadow: '0 4px 16px rgba(0,0,0,.2)',
  })
  btn.addEventListener('click', run)
  document.body.appendChild(btn)
})()
