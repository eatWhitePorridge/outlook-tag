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

function qs(params = {}) {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== false) q.set(k, v)
  })
  return q.toString()
}

/**
 * 所有可能被快速连续触发的读取型方法都接受 `{ signal }`，
 * 配合 lib/request.svelte.js 的 createRequest() 取消上一次在途请求。
 */
export const api = {
  health: () => request('/api/health'),
  login: (password) => request('/api/auth/login', { method: 'POST', body: { password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),

  stats: (opts = {}) => request('/api/accounts/stats', opts),
  accounts: (params = {}, opts = {}) => request(`/api/accounts?${qs(params)}`, opts),
  account: (id) => request(`/api/accounts/${id}`),
  accountSecrets: (id) => request(`/api/accounts/${id}/secrets`),
  createAccount: (body) => request('/api/accounts', { method: 'POST', body }),
  updateAccount: (id, body) => request(`/api/accounts/${id}`, { method: 'PUT', body }),
  deleteAccount: (id) => request(`/api/accounts/${id}`, { method: 'DELETE' }),
  batchImport: (lines) => request('/api/accounts/batch', { method: 'POST', body: { lines } }),
  probe: (id) => request(`/api/accounts/${id}/probe`, { method: 'POST' }),
  probeBatch: (limit = 20, only_unknown = true) =>
    request(`/api/accounts/probe-batch?limit=${limit}&only_unknown=${only_unknown}`, { method: 'POST' }),

  aliases: (id, opts = {}) => request(`/api/accounts/${id}/aliases`, opts),
  createAlias: (id, tag = '') => request(`/api/accounts/${id}/aliases`, { method: 'POST', body: { tag } }),
  deleteAlias: (aliasId) => request(`/api/accounts/aliases/${aliasId}`, { method: 'DELETE' }),

  messages: (id, params = {}, publicToken, opts = {}) =>
    request(`/api/accounts/${id}/messages?${qs(params)}`, { ...opts, publicToken }),
  message: (id, uid, publicToken, opts = {}) =>
    request(`/api/accounts/${id}/messages/${uid}`, { ...opts, publicToken }),
  lookup: (email) => request('/api/lookup', { method: 'POST', body: { email } }),

  ops: (params = {}, opts = {}) => request(`/api/ops?${qs({ per_page: 50, ...params })}`, opts),
  systemSettings: (opts = {}) => request('/api/settings/system', opts),
  updateSystemSettings: (body) => request('/api/settings/system', { method: 'PUT', body }),
  probeRunNow: () => request('/api/settings/probe/run-now', { method: 'POST' }),
}
