async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }
  if (options.publicToken) {
    headers['X-Public-Token'] = options.publicToken
    delete options.publicToken
  }
  const res = await fetch(path, {
    credentials: 'include',
    ...options,
    headers,
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || res.statusText || '请求失败'
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  health: () => request('/api/health'),
  login: (password) => request('/api/auth/login', { method: 'POST', body: { password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  stats: () => request('/api/accounts/stats'),
  accounts: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, v)
    })
    return request(`/api/accounts?${q}`)
  },
  account: (id) => request(`/api/accounts/${id}`),
  accountSecrets: (id) => request(`/api/accounts/${id}/secrets`),
  createAccount: (body) => request('/api/accounts', { method: 'POST', body }),
  updateAccount: (id, body) => request(`/api/accounts/${id}`, { method: 'PUT', body }),
  deleteAccount: (id) => request(`/api/accounts/${id}`, { method: 'DELETE' }),
  batchImport: (lines) => request('/api/accounts/batch', { method: 'POST', body: { lines } }),
  probe: (id) => request(`/api/accounts/${id}/probe`, { method: 'POST' }),
  probeBatch: (limit = 20, only_unknown = true) =>
    request(`/api/accounts/probe-batch?limit=${limit}&only_unknown=${only_unknown}`, { method: 'POST' }),
  aliases: (id) => request(`/api/accounts/${id}/aliases`),
  createAlias: (id, tag = '') => request(`/api/accounts/${id}/aliases`, { method: 'POST', body: { tag } }),
  deleteAlias: (aliasId) => request(`/api/accounts/aliases/${aliasId}`, { method: 'DELETE' }),
  messages: (id, params = {}, publicToken) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '' && v !== false) q.set(k, v)
    })
    return request(`/api/accounts/${id}/messages?${q}`, { publicToken })
  },
  message: (id, uid, publicToken) =>
    request(`/api/accounts/${id}/messages/${uid}`, { publicToken }),
  lookup: (email) => request('/api/lookup', { method: 'POST', body: { email } }),
  ops: (page = 1) => request(`/api/ops?page=${page}&per_page=50`),
  systemSettings: () => request('/api/settings/system'),
  updateSystemSettings: (body) => request('/api/settings/system', { method: 'PUT', body }),
  probeRunNow: () => request('/api/settings/probe/run-now', { method: 'POST' }),
}

export function relativeTime(iso) {
  if (!iso) return '未检测'
  const t = Date.parse(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(t)) return iso
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  const d = Math.floor(h / 24)
  return `${d} 天前`
}

/**
 * 复制到剪贴板。
 * navigator.clipboard 仅在安全上下文（HTTPS / localhost）可用；
 * 公网 HTTP 会失败，因此提供 execCommand 回退。
 */
export async function copyText(text) {
  const value = text == null ? '' : String(text)
  if (!value) throw new Error('empty')

  // 优先现代 API（HTTPS / localhost）
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch {
      // fall through
    }
  }

  // 回退：临时 textarea + execCommand（兼容 HTTP IP 访问）
  const ta = document.createElement('textarea')
  ta.value = value
  ta.setAttribute('readonly', '')
  ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;opacity:0;'
  document.body.appendChild(ta)
  ta.focus()
  ta.select()
  ta.setSelectionRange(0, value.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } finally {
    document.body.removeChild(ta)
  }
  if (!ok) throw new Error('copy failed')
}
