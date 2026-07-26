<script>
  import { onMount } from 'svelte'
  import { api, copyText, relativeTime } from '../lib/api.js'
  import MailBody from '../lib/MailBody.svelte'

  let { navigate, onLogout } = $props()

  let stats = $state({ total: 0, ok: 0, error: 0, unknown: 0, aliases: 0 })
  let accounts = $state([])
  let total = $state(0)
  let page = $state(1)
  let totalPages = $state(0)
  let q = $state('')
  let status = $state('all')
  let loadingList = $state(false)
  let sidebarOpen = $state(true)

  let selectedId = $state(null)
  let selectedEmail = $state('')
  let aliases = $state([])
  let filterTo = $state(null)
  let messages = $state([])
  let mailPage = $state(1)
  let mailTotalPages = $state(0)
  let mailTotal = $state(0)
  let mailLoading = $state(false)
  let codesOnly = $state(false)
  let autoRefresh = $state(false)
  let detail = $state(null)
  let detailLoading = $state(false)
  let selectedUid = $state(null)
  let view = $state('list') // list | detail
  let error = $state('')
  let toast = $state('')
  let aliasTag = $state('')

  let showAdd = $state(false)
  let showImport = $state(false)
  let showOps = $state(false)
  let showSettings = $state(false)
  let showEdit = $state(false)
  let editSecrets = $state(null)
  let menuId = $state(null)

  let form = $state({ raw: '', email: '', password: '', client_id: '', refresh_token: '', note: '' })
  let importText = $state('')
  let importResult = $state(null)
  let ops = $state([])
  let busy = $state(false)

  let sys = $state({
    probe_enabled: true,
    probe_interval_minutes: 10,
    probe_batch_size: 40,
    probe_workers: 6,
    probe_stale_hours: 24,
    scheduler: {},
  })

  let timer
  let toastTimer
  let searchTimer

  onMount(() => {
    if (window.innerWidth < 900) sidebarOpen = false
    refreshAll()
    loadSettings()
    const onDoc = () => { menuId = null }
    document.addEventListener('click', onDoc)
    const poll = setInterval(() => {
      if (showSettings) loadSettings(true)
    }, 15000)
    return () => {
      clearInterval(timer)
      clearTimeout(toastTimer)
      clearInterval(poll)
      document.removeEventListener('click', onDoc)
    }
  })

  $effect(() => {
    clearInterval(timer)
    if (autoRefresh && selectedId && view === 'list') {
      timer = setInterval(() => loadMessages(mailPage), 30000)
    }
  })

  function flash(msg) {
    toast = msg
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast = '' }, 1600)
  }

  async function copy(text, label = '已复制') {
    try {
      await copyText(text)
      flash(label)
    } catch {
      flash('复制失败')
    }
  }

  async function refreshAll() {
    await Promise.all([loadStats(), loadAccounts()])
  }

  async function loadStats() {
    try { stats = await api.stats() } catch (e) { error = e.message }
  }

  async function loadAccounts(p = page) {
    loadingList = true
    try {
      const data = await api.accounts({ q, status, page: p, per_page: 50 })
      accounts = data.items || []
      total = data.total
      page = data.page
      totalPages = data.total_pages
    } catch (e) {
      error = e.message
    } finally {
      loadingList = false
    }
  }

  async function selectAccount(a) {
    selectedId = a.id
    selectedEmail = a.email
    filterTo = null
    mailPage = 1
    detail = null
    selectedUid = null
    messages = []
    view = 'list'
    menuId = null
    if (window.innerWidth < 900) sidebarOpen = false
    await Promise.all([loadAliases(), loadMessages(1)])
  }

  async function loadAliases() {
    if (!selectedId) return
    try { aliases = await api.aliases(selectedId) } catch (e) { error = e.message }
  }

  async function loadMessages(p = 1) {
    if (!selectedId) return
    mailLoading = true
    error = ''
    try {
      const data = await api.messages(selectedId, {
        page: p,
        per_page: 20,
        filter_to: filterTo || undefined,
        codes_only: codesOnly,
      })
      messages = data.messages || []
      mailPage = data.page
      mailTotalPages = data.total_pages
      mailTotal = data.total
    } catch (e) {
      messages = []
      error = e.message
    } finally {
      mailLoading = false
    }
  }

  async function openMessage(m) {
    selectedUid = m.uid
    view = 'detail'
    detailLoading = true
    detail = null
    try {
      detail = await api.message(selectedId, m.uid)
    } catch (e) {
      detail = { error: e.message }
    } finally {
      detailLoading = false
    }
  }

  function backToList() {
    view = 'list'
    selectedUid = null
    detail = null
  }

  async function createAlias() {
    if (!selectedId) return
    busy = true
    try {
      const row = await api.createAlias(selectedId, aliasTag.trim())
      aliasTag = ''
      await loadAliases()
      flash(`别名 ${row.alias}`)
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function removeAlias(id, alias) {
    if (!confirm(`删除别名 ${alias}？`)) return
    await api.deleteAlias(id)
    if (filterTo === alias) filterTo = null
    await loadAliases()
    await loadMessages(1)
  }

  async function probeSelected() {
    if (!selectedId) return
    busy = true
    try {
      const r = await api.probe(selectedId)
      flash(r.ok ? '连接正常' : '连接异常')
      await refreshAll()
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function probeBatch() {
    busy = true
    try {
      const r = await api.probeBatch(sys.probe_batch_size || 40, false)
      flash(`已探测 ${r.probed}（正常 ${r.ok ?? '-'}）`)
      await refreshAll()
      await loadSettings(true)
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function loadSettings(silent = false) {
    try {
      const data = await api.systemSettings()
      sys = data
    } catch (e) {
      if (!silent) error = e.message
    }
  }

  async function openSettings() {
    showSettings = true
    await loadSettings()
  }

  async function saveSettings() {
    busy = true
    try {
      sys = await api.updateSystemSettings({
        probe_enabled: !!sys.probe_enabled,
        probe_interval_minutes: Number(sys.probe_interval_minutes) || 10,
        probe_batch_size: Number(sys.probe_batch_size) || 40,
        probe_workers: Number(sys.probe_workers) || 6,
        probe_stale_hours: Number(sys.probe_stale_hours) || 24,
      })
      flash('配置已保存')
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function runProbeNow() {
    busy = true
    try {
      const r = await api.probeRunNow()
      if (r.busy) flash('探测进行中…')
      else flash(`立即探测 ${r.probed}（正常 ${r.ok ?? 0}）`)
      await refreshAll()
      await loadSettings(true)
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  function formatEta(sec) {
    if (sec == null) return '—'
    const s = Math.max(0, Math.floor(sec))
    if (s < 60) return `${s}s`
    const m = Math.floor(s / 60)
    const r = s % 60
    return r ? `${m}m${r}s` : `${m}m`
  }

  async function saveAccount() {
    busy = true
    try {
      const body = form.raw.trim()
        ? { raw: form.raw, note: form.note }
        : {
            email: form.email,
            password: form.password,
            client_id: form.client_id,
            refresh_token: form.refresh_token,
            note: form.note,
          }
      await api.createAccount(body)
      showAdd = false
      form = { raw: '', email: '', password: '', client_id: '', refresh_token: '', note: '' }
      flash('已添加')
      await refreshAll()
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function openEdit(id) {
    menuId = null
    busy = true
    try {
      editSecrets = await api.accountSecrets(id)
      showEdit = true
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function saveEdit() {
    if (!editSecrets) return
    busy = true
    try {
      await api.updateAccount(editSecrets.id, {
        email: editSecrets.email,
        password: editSecrets.password,
        client_id: editSecrets.client_id,
        refresh_token: editSecrets.refresh_token,
        note: editSecrets.note,
      })
      showEdit = false
      if (selectedId === editSecrets.id) selectedEmail = editSecrets.email
      editSecrets = null
      flash('已保存')
      await refreshAll()
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function removeAccount(id, email) {
    menuId = null
    if (!confirm(`删除 ${email}？`)) return
    await api.deleteAccount(id)
    if (selectedId === id) {
      selectedId = null
      selectedEmail = ''
      messages = []
      detail = null
      aliases = []
      view = 'list'
    }
    flash('已删除')
    await refreshAll()
  }

  async function doImport() {
    busy = true
    importResult = null
    try {
      importResult = await api.batchImport(importText)
      flash(`导入 ${importResult.ok}/${importResult.total}`)
      await refreshAll()
    } catch (e) { error = e.message }
    finally { busy = false }
  }

  async function openOps() {
    showOps = true
    try {
      const data = await api.ops(1)
      ops = data.items || []
    } catch (e) { error = e.message }
  }

  function statusLabel(s) {
    if (s === 'ok') return '正常'
    if (s === 'error') return '异常'
    return '未测'
  }

  function filterAlias(alias) {
    filterTo = alias
    selectedUid = null
    detail = null
    view = 'list'
    loadMessages(1)
  }

  function showAllMail() {
    filterTo = null
    selectedUid = null
    detail = null
    view = 'list'
    loadMessages(1)
  }

  function onSearch() {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => { page = 1; loadAccounts(1) }, 220)
  }

  function shortDate(d) {
    if (!d) return ''
    return d.replace(/ \+0000.*/, '').replace(/ \(.*\)/, '')
  }
</script>

<div class="shell" class:sidebar-collapsed={!sidebarOpen}>
  <header class="top">
    <div class="brand">
      <button class="icon-btn rail-toggle" type="button" aria-label="切换侧栏" onclick={() => (sidebarOpen = !sidebarOpen)}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
      </button>
      <div class="seal-logo-sm">信</div>
      <div class="brand-text">
        <h1 class="serif">信笺 · 管理控制台</h1>
        <p class="nums faint">
          <span>巡检周期: {sys.probe_enabled ? `${sys.probe_interval_minutes}m` : '禁用'}</span>
          <span class="dot">·</span>
          <span>按批: {sys.probe_batch_size}</span>
        </p>
      </div>
    </div>

    <div class="metrics-row nums">
      <div class="metric-chip">
        <span class="label">全部账号</span>
        <span class="val">{stats.total}</span>
      </div>
      <div class="metric-chip ok">
        <span class="label">正常连接</span>
        <span class="val">{stats.ok}</span>
      </div>
      <div class="metric-chip err">
        <span class="label">异常状态</span>
        <span class="val">{stats.error}</span>
      </div>
      <div class="metric-chip">
        <span class="label">Tag 别名</span>
        <span class="val">{stats.aliases}</span>
      </div>
    </div>

    <nav class="top-actions">
      <button class="btn btn-sm" type="button" onclick={() => navigate('/')}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        公开页
      </button>
      <button class="btn btn-sm" type="button" onclick={openOps}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
        日志
      </button>
      <button class="btn btn-sm" type="button" onclick={() => { showImport = true; importResult = null }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
        批量导入
      </button>
      <button class="btn btn-sm" type="button" onclick={openSettings}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"></path></svg>
        配置
      </button>
      <button class="btn btn-sm" type="button" onclick={probeBatch} disabled={busy}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
        探测
      </button>
      <button class="btn btn-sm btn-primary" type="button" onclick={() => (showAdd = true)}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        添加
      </button>
      <button class="btn btn-sm btn-ghost" type="button" onclick={onLogout}>退出</button>
    </nav>
  </header>

  {#if error}
    <div class="banner" role="alert">
      <span>{error}</span>
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => (error = '')}>关闭</button>
    </div>
  {/if}

  <div class="body">
    <!-- sidebar: accounts only -->
    <aside class="sidebar" class:open={sidebarOpen} aria-label="账号列表">
      <div class="side-head">
        <h2 class="serif">账号阵列</h2>
        <span class="nums faint">{total}</span>
      </div>
      <div class="filters">
        <input class="field field-compact" placeholder="搜索邮箱 / 备注..." bind:value={q} oninput={onSearch} />
        <select class="field field-compact select" bind:value={status} onchange={() => { page = 1; loadAccounts(1) }}>
          <option value="all">全部</option>
          <option value="ok">正常</option>
          <option value="error">异常</option>
          <option value="unknown">未测</option>
        </select>
      </div>
      <div class="scroll list">
        {#if loadingList && !accounts.length}
          <div class="skeleton-list">
            <div class="skeleton sk-item"></div>
            <div class="skeleton sk-item"></div>
          </div>
        {:else if !accounts.length}
          <div class="empty-state">
            <p class="muted font-serif">暂无匹配账号</p>
          </div>
        {:else}
          {#each accounts as a (a.id)}
            <div class="acc" class:active={selectedId === a.id}>
              <button type="button" class="acc-main" onclick={() => selectAccount(a)}>
                <span class="status-dot status-{a.status || 'unknown'}" title={statusLabel(a.status)}></span>
                <div class="acc-text">
                  <div class="email truncate" title={a.email}>{a.email}</div>
                  <div class="meta faint">
                    <span>{statusLabel(a.status)}</span>
                    <span class="sep">·</span>
                    <span class="nums">{relativeTime(a.last_checked_at)}</span>
                    {#if a.note}<span class="sep">·</span><span class="truncate note">{a.note}</span>{/if}
                  </div>
                </div>
              </button>
              <div class="acc-more">
                <button
                  type="button"
                  class="icon-btn"
                  aria-label="更多操作"
                  onclick={(e) => { e.stopPropagation(); menuId = menuId === a.id ? null : a.id }}
                >⋯</button>
                {#if menuId === a.id}
                  <div class="menu" role="menu">
                    <button type="button" onclick={() => openEdit(a.id)}>编辑凭据</button>
                    <button type="button" onclick={() => copy(a.email, '邮箱已复制')}>复制邮箱</button>
                    <button type="button" style="color: var(--vermilion);" onclick={() => removeAccount(a.id, a.email)}>删除账号</button>
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>
      <div class="pager nums">
        <button class="btn btn-sm btn-ghost" type="button" disabled={page <= 1} onclick={() => loadAccounts(page - 1)}>上页</button>
        <span class="faint">{page}/{Math.max(totalPages, 1)}</span>
        <button class="btn btn-sm btn-ghost" type="button" disabled={page >= totalPages || totalPages === 0} onclick={() => loadAccounts(page + 1)}>下页</button>
      </div>
    </aside>

    {#if sidebarOpen}
      <button class="scrim" type="button" aria-label="关闭侧栏" onclick={() => (sidebarOpen = false)}></button>
    {/if}

    <!-- main: list OR detail (not both side by side) -->
    <main class="main">
      {#if !selectedId}
        <div class="empty-state wide">
          <svg class="enso-icon" viewBox="0 0 100 100" fill="none" stroke="currentColor">
            <circle cx="50" cy="50" r="38" stroke-width="1.8" stroke-dasharray="210 30" stroke-linecap="round" opacity="0.3" />
          </svg>
          <p class="serif" style="font-size: 1.3rem; margin-top: 0.5rem;">从左侧选择 Outlook 账号</p>
          <p class="muted" style="font-size: 0.9rem;">独立收取信件、自动衍生别名与提取验证码</p>
        </div>
      {:else if view === 'detail'}
        <div class="detail-view">
          <div class="detail-toolbar">
            <button class="btn btn-sm" type="button" onclick={backToList}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              返回收件箱
            </button>
            <span class="faint truncate current-mail">{selectedEmail}</span>
          </div>
          {#if detailLoading}
            <div class="empty-state"><p class="muted">加载邮件正文中...</p></div>
          {:else if detail?.error}
            <div class="empty-state"><p class="err">{detail.error}</p></div>
          {:else if detail}
            <div class="detail-scroll scroll">
              <header class="detail-head">
                <h2 class="serif">{detail.subject || '(无主题)'}</h2>
                <p class="meta-line muted">{detail.from}</p>
                <p class="meta-line faint">→ {detail.to}</p>
                <p class="meta-line faint nums">{detail.date}</p>
                {#if detail.codes?.length}
                  <div class="codes codes-lg">
                    {#each detail.codes as c}
                      <button type="button" class="code-chip lg" onclick={() => copy(c, `已复制 ${c}`)}>
                        <span>{c}</span>
                        <span class="copy-hint">复制</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </header>
              <div class="detail-body">
                <MailBody {detail} />
              </div>
            </div>
          {/if}
        </div>
      {:else}
        <div class="list-view">
          <div class="main-bar">
            <div class="main-title">
              <h2 class="serif truncate" title={filterTo || selectedEmail}>{filterTo || selectedEmail}</h2>
              <span class="nums faint">{mailTotal} 封</span>
            </div>
            <div class="mail-tools">
              <label class="check"><input type="checkbox" bind:checked={codesOnly} onchange={() => loadMessages(1)} /> 验证码</label>
              <label class="check"><input type="checkbox" bind:checked={autoRefresh} /> 自动</label>
              <button class="btn btn-sm" type="button" disabled={mailLoading} onclick={() => loadMessages(mailPage)}>
                {mailLoading ? '…' : '刷新'}
              </button>
              <button class="btn btn-sm" type="button" disabled={busy} onclick={probeSelected}>探测</button>
            </div>
          </div>

          <div class="alias-row">
            <div class="alias-chips">
              <button type="button" class="chip" class:on={!filterTo} onclick={showAllMail}>全部</button>
              {#each aliases as al (al.id)}
                <div class="alias-item" class:on={filterTo === al.alias}>
                  <button type="button" class="chip" class:on={filterTo === al.alias} onclick={() => filterAlias(al.alias)} title={al.alias}>+{al.tag}</button>
                  <button type="button" class="mini" title="复制" onclick={() => copy(al.alias, '别名已复制')}>复制</button>
                  <button type="button" class="mini danger" title="删除" onclick={() => removeAlias(al.id, al.alias)}>删</button>
                </div>
              {/each}
            </div>
            <div class="alias-add">
              <input class="field field-compact tag-input" placeholder="tag" bind:value={aliasTag} onkeydown={(e) => e.key === 'Enter' && createAlias()} />
              <button class="btn btn-sm" type="button" disabled={busy} onclick={createAlias}>+ 别名</button>
            </div>
          </div>

          <div class="scroll mail-list">
            {#if mailLoading && !messages.length}
              <p class="empty muted">拉取邮件中…</p>
            {:else if !messages.length}
              <p class="empty muted">没有邮件</p>
            {:else}
              {#each messages as m (m.uid)}
                <div
                  class="mail"
                  class:active={selectedUid === m.uid}
                  role="button"
                  tabindex="0"
                  onclick={() => openMessage(m)}
                  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && openMessage(m)}
                >
                  <div class="mail-main">
                    <div class="mail-line">
                      <span class="subject truncate">{m.subject || '(无主题)'}</span>
                      {#if m.codes?.length}<span class="otp-mark">码</span>{/if}
                    </div>
                    <div class="mail-sub faint">
                      <span class="truncate from">{m.from}</span>
                      <span class="nums date">{shortDate(m.date)}</span>
                    </div>
                    {#if m.body_preview}
                      <p class="preview faint truncate">{m.body_preview}</p>
                    {/if}
                  </div>
                  {#if m.codes?.length}
                    <div class="codes">
                      {#each m.codes as c}
                        <button
                          type="button"
                          class="code-chip"
                          onclick={(e) => { e.stopPropagation(); copy(c, `已复制 ${c}`) }}
                        >{c}</button>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            {/if}
          </div>

          <div class="pager nums">
            <button class="btn btn-sm btn-ghost" type="button" disabled={mailPage <= 1} onclick={() => loadMessages(mailPage - 1)}>上一页</button>
            <span class="faint">{mailPage}/{Math.max(mailTotalPages, 1)}</span>
            <button class="btn btn-sm btn-ghost" type="button" disabled={mailPage >= mailTotalPages || mailTotalPages === 0} onclick={() => loadMessages(mailPage + 1)}>下一页</button>
          </div>
        </div>
      {/if}
    </main>
  </div>
</div>

{#if toast}
  <div class="toast fade-in" role="status">{toast}</div>
{/if}

{#if showAdd}
  <div class="modal-backdrop" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && (showAdd = false)} onkeydown={(e) => e.key === 'Escape' && (showAdd = false)}>
    <div class="modal-card">
      <div style="padding: 1.25rem 1.4rem; display: grid; gap: 0.75rem; overflow: auto;">
        <h3 class="serif" style="margin: 0; font-size: 1.2rem;">添加账号</h3>
        <div>
          <label class="lbl" for="raw-input">快速导入（邮箱----密码----client_id----refresh_token）</label>
          <textarea id="raw-input" class="field" rows="3" bind:value={form.raw} placeholder="粘贴完整凭据，一键解析…"></textarea>
        </div>
        <p class="faint center" style="margin: 0.2rem 0;">— 或手动分段填写 —</p>
        <input class="field" placeholder="邮箱地址" bind:value={form.email} />
        <input class="field" placeholder="密码（可选）" bind:value={form.password} />
        <input class="field" placeholder="Client ID" bind:value={form.client_id} />
        <textarea class="field" rows="2" placeholder="Refresh Token" bind:value={form.refresh_token}></textarea>
        <input class="field" placeholder="备注信息（可选）" bind:value={form.note} />
        <div class="modal-actions" style="margin-top: 0.5rem;">
          <button class="btn" type="button" onclick={() => (showAdd = false)}>取消</button>
          <button class="btn btn-primary" type="button" disabled={busy} onclick={saveAccount}>保存账号</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showEdit && editSecrets}
  <div class="modal-backdrop" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && (showEdit = false)} onkeydown={(e) => e.key === 'Escape' && (showEdit = false)}>
    <div class="modal-card">
      <div style="padding: 1.25rem 1.4rem; display: grid; gap: 0.75rem; overflow: auto;">
        <h3 class="serif" style="margin: 0; font-size: 1.2rem;">编辑账号凭据</h3>
        <input class="field" placeholder="邮箱地址" bind:value={editSecrets.email} />
        <input class="field" placeholder="密码" bind:value={editSecrets.password} />
        <input class="field" placeholder="Client ID" bind:value={editSecrets.client_id} />
        <textarea class="field" rows="2" placeholder="Refresh Token" bind:value={editSecrets.refresh_token}></textarea>
        <input class="field" placeholder="备注信息" bind:value={editSecrets.note} />
        <div class="modal-actions" style="margin-top: 0.5rem;">
          <button class="btn" type="button" onclick={() => (showEdit = false)}>取消</button>
          <button class="btn btn-primary" type="button" disabled={busy} onclick={saveEdit}>保存修改</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showImport}
  <div class="modal-backdrop" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && (showImport = false)} onkeydown={(e) => e.key === 'Escape' && (showImport = false)}>
    <div class="modal-card" style="width: min(100%, 640px);">
      <div style="padding: 1.25rem 1.4rem; display: grid; gap: 0.75rem; overflow: auto;">
        <h3 class="serif" style="margin: 0; font-size: 1.2rem;">批量导入账号</h3>
        <p class="muted" style="margin: 0; font-size: 0.88rem;">每行一条格式：`邮箱----密码----client_id----refresh_token`</p>
        <textarea class="field" rows="8" placeholder="每行粘贴一个账号…" bind:value={importText}></textarea>
        {#if importResult}
          <p class="nums" style="margin: 0.2rem 0; font-weight: 500;">导入结果：成功 {importResult.ok} / 共 {importResult.total}</p>
          <div class="scroll import-list">
            {#each importResult.results as r}
              <div class="import-row">
                <span class="truncate">{r.email}</span>
                <span class:err={!r.ok}>{r.ok ? 'OK' : r.error}</span>
              </div>
            {/each}
          </div>
        {/if}
        <div class="modal-actions" style="margin-top: 0.5rem;">
          <button class="btn" type="button" onclick={() => (showImport = false)}>关闭</button>
          <button class="btn btn-primary" type="button" disabled={busy || !importText.trim()} onclick={doImport}>开始导入</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showOps}
  <div class="modal-backdrop" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && (showOps = false)} onkeydown={(e) => e.key === 'Escape' && (showOps = false)}>
    <div class="modal-card" style="width: min(100%, 640px);">
      <div style="padding: 1.25rem 1.4rem; display: grid; gap: 0.75rem; overflow: auto;">
        <h3 class="serif" style="margin: 0; font-size: 1.2rem;">系统操作记录</h3>
        <div class="scroll import-list" style="max-height: 360px;">
          {#each ops as o}
            <div class="ops-row">
              <span class="nums faint">{o.created_at}</span>
              <span style="font-weight: 500;">{o.action}</span>
              <span class="truncate muted">{o.target}</span>
              <span class="truncate faint">{o.detail}</span>
            </div>
          {:else}
            <p class="empty muted">暂无操作日志记录</p>
          {/each}
        </div>
        <div class="modal-actions">
          <button class="btn" type="button" onclick={() => (showOps = false)}>关闭</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showSettings}
  <div class="modal-backdrop" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && (showSettings = false)} onkeydown={(e) => e.key === 'Escape' && (showSettings = false)}>
    <div class="modal-card" style="width: min(100%, 580px);">
      <div style="padding: 1.25rem 1.4rem; display: grid; gap: 0.85rem; overflow: auto;">
        <h3 class="serif" style="margin: 0; font-size: 1.2rem;">系统参数 · 自动化连接探测</h3>
        <p class="muted" style="margin: 0; font-size: 0.88rem;">后台定时巡检账号可用性，优先探测未检测、异常及最久未检的账号。</p>

        <div class="settings-grid">
          <label class="set-row">
            <span>启用后台自动探测</span>
            <input type="checkbox" bind:checked={sys.probe_enabled} />
          </label>
          <label class="set-row">
            <span>轮询间隔（分钟）</span>
            <input class="field field-compact" type="number" min="1" max="1440" bind:value={sys.probe_interval_minutes} />
          </label>
          <label class="set-row">
            <span>每批探测账号数量</span>
            <input class="field field-compact" type="number" min="1" max="200" bind:value={sys.probe_batch_size} />
          </label>
          <label class="set-row">
            <span>并发线程池数量</span>
            <input class="field field-compact" type="number" min="1" max="16" bind:value={sys.probe_workers} />
          </label>
          <label class="set-row">
            <span>陈旧检测阈值（小时）</span>
            <input class="field field-compact" type="number" min="1" max="168" bind:value={sys.probe_stale_hours} />
          </label>
        </div>

        <div class="sched-status nums">
          <div><span class="faint">调度器:</span> {sys.scheduler?.thread_alive ? '运行中' : '未启动'}</div>
          <div><span class="faint">上次执行:</span> {sys.scheduler?.last_run_at || '—'}</div>
          <div><span class="faint">下次约:</span> {formatEta(sys.scheduler?.next_run_in_sec)}</div>
          <div>
            <span class="faint">最近结果:</span>
            {#if sys.scheduler?.last_result}
              探测 {sys.scheduler.last_result.probed} · 正常 {sys.scheduler.last_result.ok} · 异常 {sys.scheduler.last_result.error}
            {:else}
              —
            {/if}
          </div>
          <div><span class="faint">已完成轮次:</span> {sys.scheduler?.cycle ?? 0}</div>
        </div>

        <div class="modal-actions" style="margin-top: 0.5rem;">
          <button class="btn" type="button" onclick={() => (showSettings = false)}>关闭</button>
          <button class="btn" type="button" disabled={busy} onclick={runProbeNow}>立即跑一批</button>
          <button class="btn btn-primary" type="button" disabled={busy} onclick={saveSettings}>保存配置</button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .shell {
    height: 100%;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    background: var(--paper);
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 75%, transparent);
    background: color-mix(in srgb, white 75%, var(--paper));
    backdrop-filter: blur(12px);
    z-index: 3;
  }
  .brand { display: flex; align-items: center; gap: 0.65rem; min-width: 0; }
  .seal-logo-sm {
    width: 32px; height: 32px; border-radius: 8px;
    display: grid; place-items: center; flex-shrink: 0;
    background: var(--vermilion); color: #ffffff;
    font-family: "Shippori Mincho", serif; font-size: 1rem; font-weight: 700;
    box-shadow: 0 2px 8px var(--vermilion-glow);
  }
  .brand-text h1 { margin: 0; font-size: 1.15rem; font-weight: 600; line-height: 1.2; }
  .brand-text p {
    margin: 0.1rem 0 0; font-size: 0.75rem;
    display: flex; flex-wrap: wrap; gap: 0.3rem;
  }
  .dot { opacity: 0.4; }

  .metrics-row {
    display: flex;
    gap: 0.6rem;
    align-items: center;
  }
  .metric-chip {
    display: flex;
    flex-direction: column;
    padding: 0.35rem 0.85rem;
    border-radius: 8px;
    background: color-mix(in srgb, var(--paper-glass) 80%, white);
    border: 1px solid color-mix(in srgb, var(--stone) 75%, transparent);
    min-width: 80px;
  }
  .metric-chip .label { font-size: 9.5px; opacity: 0.75; }
  .metric-chip .val { font-size: 1.15rem; font-weight: 700; line-height: 1.15; margin-top: 0.1rem; }
  .metric-chip.ok .val { color: var(--moss); }
  .metric-chip.err .val { color: var(--vermilion); }

  .top-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; justify-content: flex-end; }

  .banner {
    display: flex; justify-content: space-between; align-items: center; gap: 1rem;
    padding: 0.6rem 1.2rem;
    border-bottom: 1px solid color-mix(in srgb, var(--vermilion) 30%, var(--stone));
    background: var(--vermilion-bg);
    color: var(--vermilion); font-size: 0.88rem;
  }

  .body {
    min-height: 0;
    display: grid;
    grid-template-columns: 290px minmax(0, 1fr);
    position: relative;
  }
  .shell.sidebar-collapsed .body {
    grid-template-columns: 0 minmax(0, 1fr);
  }
  .shell.sidebar-collapsed .sidebar {
    width: 0; border: 0; overflow: hidden; padding: 0; opacity: 0; pointer-events: none;
  }

  .sidebar {
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr) auto;
    border-right: 1px solid color-mix(in srgb, var(--stone) 80%, transparent);
    background: color-mix(in srgb, white 70%, var(--paper));
    backdrop-filter: blur(12px);
    transition: opacity 180ms var(--ease);
  }
  .side-head {
    display: flex; align-items: baseline; justify-content: space-between;
    padding: 0.95rem 1.1rem 0.45rem;
  }
  .side-head h2 {
    margin: 0; font-size: 1.05rem; font-weight: 600;
  }
  .filters {
    display: grid;
    grid-template-columns: 1fr 84px;
    gap: 0.45rem;
    padding: 0 0.9rem 0.75rem;
  }
  .field-compact {
    min-height: 34px;
    padding: 0.35rem 0.6rem;
    font-size: 0.84rem;
    border-radius: 7px;
  }
  .select { appearance: auto; }

  .main {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, white 80%, var(--paper));
  }

  .list-view, .detail-view {
    min-height: 0;
    flex: 1;
    display: grid;
  }
  .list-view {
    grid-template-rows: auto auto minmax(0, 1fr) auto;
  }
  .detail-view {
    grid-template-rows: auto minmax(0, 1fr);
  }

  .main-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.95rem 1.35rem 0.75rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 65%, transparent);
  }
  .main-title {
    display: flex; align-items: baseline; gap: 0.75rem; min-width: 0;
  }
  .main-title h2 {
    margin: 0; font-size: 1.2rem; font-weight: 600; min-width: 0;
  }
  .mail-tools {
    display: flex; flex-wrap: wrap; gap: 0.45rem 0.65rem; align-items: center;
  }

  .alias-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    justify-content: space-between;
    padding: 0.65rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 55%, transparent);
    background: color-mix(in srgb, var(--paper) 55%, white);
  }
  .alias-chips {
    display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
    min-width: 0; flex: 1;
  }
  .alias-item { display: inline-flex; align-items: center; gap: 0.2rem; }
  .chip {
    border: 1px solid color-mix(in srgb, var(--stone) 85%, var(--ink));
    background: white;
    border-radius: 999px;
    padding: 0.22rem 0.65rem;
    font-size: 0.78rem;
    transition: all 150ms var(--ease);
  }
  .chip.on {
    background: var(--ink);
    color: var(--paper);
    border-color: var(--ink);
  }
  .mini {
    border: 0; background: transparent;
    font-size: 0.72rem;
    color: var(--ink-faint);
    padding: 0.1rem 0.25rem;
  }
  .mini:hover { color: var(--ink); }
  .mini.danger:hover { color: var(--vermilion); }
  .alias-add { display: flex; gap: 0.35rem; flex-shrink: 0; }
  .tag-input { width: 95px; }

  .mail-list { min-height: 0; }
  .mail {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.85rem;
    align-items: start;
    padding: 0.95rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
    cursor: pointer;
    transition: background 150ms var(--ease);
  }
  .mail:hover { background: color-mix(in srgb, var(--ink) 2.5%, transparent); }
  .mail.active {
    background: color-mix(in srgb, var(--wood) 18%, transparent);
    box-shadow: inset 3px 0 0 var(--indigo);
  }
  .mail-main { min-width: 0; display: grid; gap: 0.25rem; }
  .mail-line { display: flex; gap: 0.5rem; align-items: center; min-width: 0; }
  .subject { flex: 1; min-width: 0; font-weight: 500; font-size: 0.95rem; }
  .mail-sub {
    display: flex; justify-content: space-between; gap: 0.85rem;
    font-size: 0.78rem;
  }
  .from { min-width: 0; flex: 1; }
  .date { flex-shrink: 0; }
  .preview { margin: 0.15rem 0 0; font-size: 0.82rem; max-width: 100%; color: var(--ink-muted); }
  .codes { display: flex; flex-wrap: wrap; gap: 0.35rem; justify-content: flex-end; }
  .codes-lg { margin-top: 0.75rem; gap: 0.45rem; justify-content: flex-start; }
  .code-chip.lg {
    padding: 0.45rem 0.85rem;
    font-size: 1.05rem;
    gap: 0.6rem;
  }

  .list { min-height: 0; }
  .acc {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 30px;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 55%, transparent);
    position: relative;
    transition: background 150ms var(--ease);
  }
  .acc.active {
    background: color-mix(in srgb, var(--wood) 20%, transparent);
    box-shadow: inset 3px 0 0 var(--indigo);
  }
  .acc-main {
    display: flex; gap: 0.65rem; align-items: flex-start;
    text-align: left; background: transparent; border: 0;
    padding: 0.75rem 0.4rem 0.75rem 0.9rem;
    min-width: 0; width: 100%;
  }
  .acc-main:hover { background: color-mix(in srgb, var(--ink) 2.5%, transparent); }
  .acc-text { min-width: 0; flex: 1; }
  .email { font-size: 0.86rem; font-weight: 500; line-height: 1.35; }
  .meta {
    display: flex; flex-wrap: wrap; gap: 0.15rem 0.3rem;
    font-size: 0.74rem; margin-top: 0.22rem; align-items: center;
  }
  .meta .note { max-width: 7.5rem; }
  .sep { opacity: 0.45; }
  .acc-more { position: relative; display: flex; align-items: flex-start; padding-top: 0.5rem; }
  .icon-btn {
    width: 28px; height: 28px; border: 0; border-radius: 6px;
    background: transparent; color: var(--ink-faint);
    font-size: 1rem; line-height: 1; display: grid; place-items: center;
    transition: all 150ms var(--ease);
  }
  .icon-btn:hover { background: color-mix(in srgb, var(--ink) 6%, transparent); color: var(--ink); }
  .rail-toggle { flex-shrink: 0; }
  
  .menu {
    position: absolute; right: 0.35rem; top: 2.2rem; z-index: 20;
    min-width: 112px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(16px);
    border: 1px solid color-mix(in srgb, var(--stone) 80%, transparent);
    border-radius: 10px;
    box-shadow: var(--shadow-lg);
    padding: 0.3rem;
    display: grid;
    gap: 0.15rem;
    animation: fadeIn 150ms var(--ease-out);
  }
  .menu button {
    border: 0; background: transparent; text-align: left;
    padding: 0.45rem 0.75rem; border-radius: 6px; font-size: 0.84rem;
    font-weight: 500; transition: background 120ms var(--ease);
  }
  .menu button:hover { background: color-mix(in srgb, var(--ink) 5%, transparent); }

  .pager {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.45rem 0.85rem;
    border-top: 1px solid color-mix(in srgb, var(--stone) 65%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }

  .detail-toolbar {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.75rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 65%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }
  .current-mail { font-size: 0.85rem; min-width: 0; }
  .detail-scroll {
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .detail-head {
    padding: 1.25rem 1.5rem 1.1rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 60%, transparent);
  }
  .detail-head h2 {
    margin: 0 0 0.6rem;
    font-size: 1.4rem; font-weight: 600; line-height: 1.35;
  }
  .meta-line { margin: 0.15rem 0; font-size: 0.88rem; }
  .detail-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .empty { padding: 3rem 1rem; text-align: center; }
  .empty-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    text-align: center;
    padding: 2rem;
  }
  .empty-state.wide { min-height: 50vh; }
  .enso-icon { width: 56px; height: 56px; color: var(--ink); }
  
  .skeleton-list { padding: 1rem 0.9rem; display: grid; gap: 0.75rem; }
  .sk-item { height: 56px; }

  .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .err { color: var(--vermilion); margin: 0; }
  .scrim { display: none; }

  .toast {
    position: fixed; left: 50%; bottom: 1.75rem; transform: translateX(-50%);
    z-index: 200;
    padding: 0.65rem 1.35rem;
    border-radius: 999px;
    background: var(--ink); color: var(--paper);
    font-size: 0.88rem; font-weight: 500;
    box-shadow: var(--shadow-lg);
  }

  .lbl { font-size: 0.85rem; font-weight: 500; color: var(--ink-muted); }
  .center { text-align: center; margin: 0.15rem 0; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 0.55rem; margin-top: 0.5rem; }
  .import-list {
    max-height: 280px;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .import-row, .ops-row {
    display: grid; gap: 0.6rem;
    padding: 0.5rem 0.2rem; font-size: 0.84rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
  }
  .import-row { grid-template-columns: 1.4fr 1fr; }
  .ops-row { grid-template-columns: 1.1fr 0.8fr 1fr 1.1fr; }
  .settings-grid {
    display: grid;
    gap: 0.75rem;
    margin: 0.5rem 0 0.85rem;
  }
  .set-row {
    display: grid;
    grid-template-columns: 1fr 120px;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.9rem;
  }
  .set-row input[type="checkbox"] { width: 18px; height: 18px; justify-self: end; }
  .sched-status {
    display: grid;
    gap: 0.4rem;
    padding: 0.85rem 1rem;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 50%, white);
    font-size: 0.84rem;
  }

  @media (max-width: 990px) {
    .metrics-row { display: none; }
  }

  @media (max-width: 900px) {
    .body { grid-template-columns: minmax(0, 1fr); }
    .shell.sidebar-collapsed .body { grid-template-columns: minmax(0, 1fr); }
    .sidebar {
      position: absolute;
      inset: 0 auto 0 0;
      width: min(86vw, 300px);
      z-index: 8;
      box-shadow: 8px 0 28px rgba(0, 0, 0, 0.12);
      opacity: 0;
      pointer-events: none;
      transform: translateX(-100%);
      transition: transform 180ms var(--ease), opacity 180ms var(--ease);
    }
    .sidebar.open {
      opacity: 1;
      pointer-events: auto;
      transform: translateX(0);
    }
    .shell.sidebar-collapsed .sidebar.open {
      width: min(86vw, 300px);
      opacity: 1;
      pointer-events: auto;
    }
    .scrim {
      display: block;
      position: absolute;
      inset: 0;
      z-index: 7;
      border: 0;
      background: rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(2px);
    }
    .shell.sidebar-collapsed .scrim { display: none; }
    .shell:not(.sidebar-collapsed) .scrim { display: block; }
  }
</style>
