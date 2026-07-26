<script>
  import { onMount } from 'svelte'
  import { api } from '../../lib/api.js'
  import { flash } from '../../lib/stores/toast.svelte.js'
  import { registerKeys } from '../../lib/stores/keymap.js'
  import { modals } from '../../lib/stores/modals.svelte.js'
  import EmptyState from '../../lib/ui/EmptyState.svelte'
  import ConfirmDialog from '../../lib/ui/ConfirmDialog.svelte'
  import AdminHeader from './AdminHeader.svelte'
  import AccountSidebar from './AccountSidebar.svelte'
  import MailPane from './MailPane.svelte'
  import BulkBar from './BulkBar.svelte'
  import AccountFormModal from './modals/AccountFormModal.svelte'
  import ImportModal from './modals/ImportModal.svelte'
  import OpsModal from './modals/OpsModal.svelte'
  import SettingsModal from './modals/SettingsModal.svelte'
  import ApiKeysModal from './modals/ApiKeysModal.svelte'

  let { navigate, onLogout } = $props()

  let stats = $state({ total: 0, ok: 0, error: 0, unknown: 0, aliases: 0 })
  let sys = $state({
    probe_enabled: true,
    probe_interval_minutes: 10,
    probe_batch_size: 40,
    probe_workers: 6,
    probe_stale_hours: 24,
    scheduler: {},
  })

  let sidebarOpen = $state(true)
  let selectedId = $state(null)
  let selectedEmail = $state('')
  let selected = $state(new Set())
  let error = $state('')
  let busy = $state(false)

  let showAdd = $state(false)
  let showEdit = $state(false)
  let showImport = $state(false)
  let showOps = $state(false)
  let showSettings = $state(false)
  let showApiKeys = $state(false)

  const EMPTY_FORM = { raw: '', email: '', password: '', client_id: '', refresh_token: '', note: '' }
  let form = $state({ ...EMPTY_FORM })
  let editSecrets = $state(null)

  let sidebar = $state(null)
  let mailPane = $state(null)
  let pendingDelete = $state(null)

  // 由 Modal 自行登记，新增弹窗无需改这里（此前手动枚举漏掉了全部 ConfirmDialog）
  let modalOpen = $derived(modals.open > 0)

  onMount(() => {
    if (window.innerWidth < 900) sidebarOpen = false
    refreshAll()
    loadSettings()

    const poll = setInterval(() => {
      if (showSettings) loadSettings(true)
    }, 15000)

    const offKeys = registerKeys(
      {
        '/': () => sidebar?.focusSearch(),
        j: () => sidebar?.step(1),
        k: () => sidebar?.step(-1),
        r: () => { sidebar?.reload(); mailPane?.loadMessages(1) },
        Escape: () => {
          if (modalOpen) return false // 交给 Modal 自己处理
          if (selected.size) { selected = new Set(); return true }
          return false
        },
      },
      { enabled: () => !modalOpen },
    )

    return () => {
      clearInterval(poll)
      offKeys()
    }
  })

  async function refreshAll() {
    await Promise.all([loadStats(), sidebar?.reload()])
  }

  async function loadStats() {
    try { stats = await api.stats() } catch (e) { error = e.message }
  }

  async function loadSettings(silent = false) {
    try {
      const next = await api.systemSettings()
      if (silent && showSettings) {
        // 弹窗开着时是 15 秒一次的后台轮询，只能更新调度器状态。
        // 整体替换会把用户正在输入、尚未保存的配置直接冲掉。
        sys.scheduler = next.scheduler
      } else {
        sys = next
      }
    } catch (e) {
      if (!silent) error = e.message
    }
  }

  function selectAccount(a) {
    selectedId = a.id
    selectedEmail = a.email
    if (window.innerWidth < 900) sidebarOpen = false
  }

  async function probeSelected() {
    if (!selectedId) return
    busy = true
    try {
      const r = await api.probe(selectedId)
      flash(r.ok ? '连接正常' : '连接异常')
      await refreshAll()
    } catch (e) { error = e.message } finally { busy = false }
  }

  async function probeBatch() {
    busy = true
    try {
      const r = await api.probeBatch(sys.probe_batch_size || 40, false)
      flash(`已探测 ${r.probed}（正常 ${r.ok ?? '-'}）`)
      await refreshAll()
      await loadSettings(true)
    } catch (e) { error = e.message } finally { busy = false }
  }

  function openAdd() {
    form = { ...EMPTY_FORM }
    showAdd = true
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
      form = { ...EMPTY_FORM }
      flash('已添加')
      await refreshAll()
    } catch (e) { error = e.message } finally { busy = false }
  }

  async function openEdit(id) {
    busy = true
    try {
      editSecrets = await api.accountSecrets(id)
      showEdit = true
    } catch (e) { error = e.message } finally { busy = false }
  }

  function closeEdit() {
    showEdit = false
    editSecrets = null // 不留明文凭据在组件状态里
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
      if (selectedId === editSecrets.id) selectedEmail = editSecrets.email
      closeEdit()
      flash('已保存')
      await refreshAll()
    } catch (e) { error = e.message } finally { busy = false }
  }

  async function removeAccount() {
    const a = pendingDelete
    if (!a) return
    busy = true
    try {
      await api.deleteAccount(a.id)
      if (selectedId === a.id) {
        selectedId = null
        selectedEmail = ''
      }
      pendingDelete = null
      flash('已删除')
      await refreshAll()
    } catch (e) { error = e.message } finally { busy = false }
  }

  async function afterBulk(deletedIds) {
    // 当前查看的账号若在批量删除范围内，清空右侧面板
    if (deletedIds?.includes(selectedId)) {
      selectedId = null
      selectedEmail = ''
    }
    await refreshAll()
  }
</script>

<div class="shell" class:sidebar-collapsed={!sidebarOpen}>
  <AdminHeader
    {stats}
    {sys}
    {busy}
    ontoggleSidebar={() => (sidebarOpen = !sidebarOpen)}
    onnavigate={() => navigate('/')}
    onops={() => (showOps = true)}
    onimport={() => (showImport = true)}
    onsettings={() => { showSettings = true; loadSettings() }}
    onapikeys={() => (showApiKeys = true)}
    onprobe={probeBatch}
    onadd={openAdd}
    onlogout={onLogout}
  />

  {#if error}
    <div class="banner" role="alert">
      <span>{error}</span>
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => (error = '')}>关闭</button>
    </div>
  {/if}

  <div class="body">
    <AccountSidebar
      bind:this={sidebar}
      bind:selected
      open={sidebarOpen}
      {selectedId}
      onselect={selectAccount}
      onedit={openEdit}
      ondelete={(a) => (pendingDelete = a)}
      onerror={(m) => (error = m)}
    />

    {#if sidebarOpen}
      <button class="scrim" type="button" aria-label="关闭侧栏" onclick={() => (sidebarOpen = false)}></button>
    {/if}

    <main class="main">
      {#if !selectedId}
        <EmptyState
          wide
          title="从左侧选择 Outlook 账号"
          hint="独立收取信件、自动衍生别名与提取验证码"
        />
      {:else}
        <MailPane
          bind:this={mailPane}
          accountId={selectedId}
          accountEmail={selectedEmail}
          probing={busy}
          onprobe={probeSelected}
          onerror={(m) => (error = m)}
        />
      {/if}
    </main>

    <BulkBar bind:selected ondone={afterBulk} onerror={(m) => (error = m)} />
  </div>
</div>

<AccountFormModal
  open={showAdd}
  mode="create"
  bind:data={form}
  {busy}
  onsave={saveAccount}
  onclose={() => (showAdd = false)}
/>

<AccountFormModal
  open={showEdit && !!editSecrets}
  mode="edit"
  bind:data={editSecrets}
  {busy}
  onsave={saveEdit}
  onclose={closeEdit}
/>

<ImportModal
  open={showImport}
  onclose={() => (showImport = false)}
  ondone={refreshAll}
  onerror={(m) => (error = m)}
/>

<OpsModal open={showOps} onclose={() => (showOps = false)} onerror={(m) => (error = m)} />

<ApiKeysModal
  open={showApiKeys}
  onclose={() => (showApiKeys = false)}
  onerror={(m) => (error = m)}
/>

<ConfirmDialog
  open={!!pendingDelete}
  title="删除账号"
  message="删除 {pendingDelete?.email ?? ''}？"
  detail="该账号的凭据与全部别名会一并删除，无法撤销。"
  confirmLabel="删除"
  danger
  {busy}
  onconfirm={removeAccount}
  oncancel={() => (pendingDelete = null)}
/>

<SettingsModal
  open={showSettings}
  bind:sys
  {busy}
  onclose={() => (showSettings = false)}
  onsaved={() => { refreshAll(); loadSettings(true) }}
  onerror={(m) => (error = m)}
/>

<style>
  .shell {
    height: 100%;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    background: var(--paper);
  }

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
  .shell.sidebar-collapsed .body { grid-template-columns: 0 minmax(0, 1fr); }
  .shell.sidebar-collapsed :global(.sidebar) {
    width: 0; border: 0; overflow: hidden; padding: 0; opacity: 0; pointer-events: none;
  }

  .main {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: color-mix(in srgb, white 80%, var(--paper));
  }

  .scrim { display: none; }

  @media (max-width: 900px) {
    .body { grid-template-columns: minmax(0, 1fr); }
    .shell.sidebar-collapsed .body { grid-template-columns: minmax(0, 1fr); }
    .shell :global(.sidebar) {
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
    .shell :global(.sidebar.open) {
      opacity: 1;
      pointer-events: auto;
      transform: translateX(0);
    }
    .shell.sidebar-collapsed :global(.sidebar.open) {
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
