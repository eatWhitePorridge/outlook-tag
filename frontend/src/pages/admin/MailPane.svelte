<script>
  import { untrack } from 'svelte'
  import { api } from '../../lib/api.js'
  import { createRequest } from '../../lib/request.svelte.js'
  import MessageList from '../../lib/mail/MessageList.svelte'
  import Pager from '../../lib/ui/Pager.svelte'
  import AliasBar from './AliasBar.svelte'
  import MailDetailPane from './MailDetailPane.svelte'

  let { accountId, accountEmail = '', onerror, onprobe, probing = false } = $props()

  let aliases = $state([])
  let filterTo = $state(null)
  let messages = $state([])
  let page = $state(1)
  let totalPages = $state(0)
  let hasMore = $state(null)
  let total = $state(0)
  let codesOnly = $state(false)
  let autoRefresh = $state(false)
  let search = $state('')
  let searchField = $state('subject')
  let view = $state('list')
  let detail = $state(null)
  let selectedUid = $state(null)
  let searchTimer

  const listReq = createRequest()
  const detailReq = createRequest()
  // 别名必须用独立实例：createRequest 会中止同一实例上的前一个请求，
  // 而 loadAliases() 与 loadMessages() 是连着发的，共用会让别名列表永远加载不出来。
  const aliasReq = createRequest()

  let index = $derived(messages.findIndex((m) => m.uid === selectedUid))
  let hasPrev = $derived(index > 0)
  let hasNext = $derived(index >= 0 && index < messages.length - 1)

  // 切换账号：全量复位。
  // 必须 untrack —— 否则 loadMessages 里读到的 codesOnly / search / filterTo
  // 会成为本 effect 的依赖，勾一下「仅验证码」就会把整个面板重置一遍。
  $effect(() => {
    const id = accountId
    untrack(() => {
      filterTo = null
      search = ''
      view = 'list'
      detail = null
      selectedUid = null
      messages = []
      page = 1
      // 这三个不重置会让新账号短暂显示上一个账号的条数与翻页状态
      total = 0
      totalPages = 0
      hasMore = null
      if (id) {
        loadAliases()
        loadMessages(1)
      }
    })
  })

  $effect(() => () => clearTimeout(searchTimer))

  // 自动刷新：标签页隐藏时暂停，回到前台立即补一次
  $effect(() => {
    if (!autoRefresh || !accountId || view !== 'list') return
    let timer = setInterval(tick, 30000)
    function tick() {
      if (document.visibilityState === 'visible') loadMessages(page)
    }
    function onVisible() {
      if (document.visibilityState === 'visible') loadMessages(page)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  })

  async function loadAliases() {
    if (!accountId) return
    const data = await aliasReq.run((signal) => api.aliases(accountId, { signal }))
    if (data) aliases = data
    else if (aliasReq.error) onerror?.(aliasReq.error)
  }

  export async function loadMessages(p = 1) {
    if (!accountId) return
    const data = await listReq.run((signal) =>
      api.messages(
        accountId,
        {
          page: p,
          per_page: 20,
          filter_to: filterTo || undefined,
          codes_only: codesOnly,
          search: search.trim() || undefined,
          search_field: search.trim() ? searchField : undefined,
        },
        undefined,
        { signal },
      ),
    )
    if (!data) {
      if (listReq.error) {
        messages = []
        onerror?.(listReq.error)
      }
      return
    }
    messages = data.messages || []
    page = data.page
    totalPages = data.total_pages ?? 0
    hasMore = data.has_more ?? null
    total = data.total
  }

  async function openMessage(m) {
    selectedUid = m.uid
    view = 'detail'
    detail = null
    const data = await detailReq.run((signal) => api.message(accountId, m.uid, undefined, { signal }))
    if (data) detail = data
    else if (detailReq.error) detail = { error: detailReq.error }
  }

  function stepMessage(delta) {
    const next = messages[index + delta]
    if (next) openMessage(next)
  }

  function backToList() {
    view = 'list'
    selectedUid = null
    detail = null
  }

  function onSearchInput() {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => loadMessages(1), 300)
  }

  function applyFilter(alias) {
    filterTo = alias
    backToList()
    loadMessages(1)
  }

  function onAliasChanged(deletedAlias) {
    if (deletedAlias && filterTo === deletedAlias) filterTo = null
    loadAliases()
    loadMessages(1)
  }
</script>

{#if view === 'detail'}
  <MailDetailPane
    {detail}
    loading={detailReq.loading}
    {accountId}
    {accountEmail}
    {hasPrev}
    {hasNext}
    onback={backToList}
    onprev={() => stepMessage(-1)}
    onnext={() => stepMessage(1)}
  />
{:else}
  <div class="list-view">
    <div class="main-bar">
      <div class="main-title">
        <h2 class="serif truncate" title={filterTo || accountEmail}>{filterTo || accountEmail}</h2>
        <span class="nums faint">{total} 封</span>
      </div>
      <div class="mail-tools">
        <div class="search-group">
          <select class="field field-compact scope" aria-label="搜索范围" bind:value={searchField} onchange={() => search.trim() && loadMessages(1)}>
            <option value="subject">主题</option>
            <option value="from">发件人</option>
            <option value="text">全文</option>
          </select>
          <input
            class="field field-compact mail-search"
            placeholder="搜索邮件…"
            aria-label="搜索邮件"
            bind:value={search}
            oninput={onSearchInput}
            onkeydown={(e) => e.key === 'Escape' && (search = '', loadMessages(1))}
          />
        </div>
        <label class="check"><input type="checkbox" bind:checked={codesOnly} onchange={() => loadMessages(1)} /> 验证码</label>
        <label class="check"><input type="checkbox" bind:checked={autoRefresh} /> 自动</label>
        <button class="btn btn-sm" type="button" disabled={listReq.loading} onclick={() => loadMessages(page)}>
          {listReq.loading ? '…' : '刷新'}
        </button>
        <button class="btn btn-sm" type="button" disabled={probing} onclick={onprobe}>探测</button>
      </div>
    </div>

    <AliasBar
      {accountId}
      {aliases}
      {filterTo}
      onfilter={applyFilter}
      onchanged={onAliasChanged}
      {onerror}
    />

    <MessageList
      {messages}
      {selectedUid}
      loading={listReq.loading}
      variant="compact"
      emptyIcon={false}
      emptyTitle={search.trim() ? '没有匹配的邮件' : '没有邮件'}
      emptyHint={search.trim() ? '换个关键词或搜索范围试试' : ''}
      onopen={openMessage}
    />

    <Pager
      {page}
      {totalPages}
      {hasMore}
      loading={listReq.loading}
      compact
      onchange={loadMessages}
    />
  </div>
{/if}

<style>
  .list-view {
    min-height: 0;
    flex: 1;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr) auto;
  }
  .main-bar {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
    gap: 0.75rem;
    padding: 0.95rem 1.35rem 0.75rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 65%, transparent);
  }
  .main-title { display: flex; align-items: baseline; gap: 0.75rem; min-width: 0; }
  .main-title h2 { margin: 0; font-size: 1.2rem; font-weight: 600; min-width: 0; }
  .mail-tools { display: flex; flex-wrap: wrap; gap: 0.45rem 0.65rem; align-items: center; }
  .search-group { display: flex; gap: 0.3rem; }
  .scope { width: 78px; appearance: auto; }
  .mail-search { width: 150px; }
  .check { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.82rem; }
</style>
