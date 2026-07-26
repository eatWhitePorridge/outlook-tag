<script>
  import { api } from '../../lib/api.js'
  import { createRequest } from '../../lib/request.svelte.js'
  import Pager from '../../lib/ui/Pager.svelte'
  import Skeleton from '../../lib/ui/Skeleton.svelte'
  import AccountRow from './AccountRow.svelte'

  let {
    open = true,
    selectedId = null,
    selected = $bindable(new Set()),
    onselect,
    onedit,
    ondelete,
    onerror,
  } = $props()

  let accounts = $state([])
  let total = $state(0)
  let page = $state(1)
  let totalPages = $state(0)
  let perPage = $state(50)
  let q = $state('')
  let status = $state('all')
  let menuId = $state(null)
  let searchInput = $state(null)
  let searchTimer

  const req = createRequest()

  export async function reload(p = page) {
    // 翻页后原选中项已不在视野内，留着会导致"批量删除看不见的行"
    if (p !== page) resetSelection()
    const data = await req.run((signal) =>
      api.accounts({ q, status, page: p, per_page: perPage }, { signal }),
    )
    if (!data) {
      if (req.error) onerror?.(req.error)
      return
    }
    accounts = data.items || []
    total = data.total
    page = data.page
    totalPages = data.total_pages
  }

  export function focusSearch() {
    searchInput?.focus()
    searchInput?.select()
  }

  /** j/k 在当前页内上下移动选中账号 */
  export function step(delta) {
    if (!accounts.length) return
    const i = accounts.findIndex((a) => a.id === selectedId)
    const next = i < 0 ? 0 : Math.min(accounts.length - 1, Math.max(0, i + delta))
    onselect?.(accounts[next])
  }

  export function currentPageIds() {
    return accounts.map((a) => a.id)
  }

  /** 条件变了就清空选择，避免误删看不见的行 */
  function resetSelection() {
    if (selected.size) selected = new Set()
  }

  function onSearch() {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      resetSelection()
      reload(1)
    }, 300)
  }

  function onFilter() {
    resetSelection()
    reload(1)
  }

  function toggle(a) {
    const next = new Set(selected)
    next.has(a.id) ? next.delete(a.id) : next.add(a.id)
    selected = next
  }

  function toggleAll() {
    const ids = currentPageIds()
    const allPicked = ids.length > 0 && ids.every((id) => selected.has(id))
    selected = allPicked ? new Set() : new Set(ids)
  }

  let selectMode = $derived(selected.size > 0)
  let allPicked = $derived(
    accounts.length > 0 && accounts.every((a) => selected.has(a.id)),
  )

  $effect(() => {
    const onDoc = () => { menuId = null }
    document.addEventListener('click', onDoc)
    return () => {
      document.removeEventListener('click', onDoc)
      clearTimeout(searchTimer) // 否则组件卸载后防抖仍会打一次请求
    }
  })
</script>

<aside class="sidebar" class:open aria-label="账号列表">
  <div class="side-head">
    <h2 class="serif">账号阵列</h2>
    <span class="nums faint">{total}</span>
  </div>

  <div class="filters">
    <input
      class="field field-compact"
      placeholder="搜索邮箱 / 备注…"
      aria-label="搜索账号"
      bind:this={searchInput}
      bind:value={q}
      oninput={onSearch}
      onkeydown={(e) => e.key === 'Escape' && searchInput?.blur()}
    />
    <select class="field field-compact select" aria-label="按状态筛选" bind:value={status} onchange={onFilter}>
      <option value="all">全部</option>
      <option value="ok">正常</option>
      <option value="error">异常</option>
      <option value="unknown">未测</option>
    </select>
  </div>

  <div class="bulk-head">
    <label class="pick-all">
      <input
        type="checkbox"
        checked={allPicked}
        indeterminate={selectMode && !allPicked}
        aria-label="全选本页账号"
        onchange={toggleAll}
      />
      <span class="faint">{selectMode ? `已选 ${selected.size}` : '全选本页'}</span>
    </label>
    <select class="field field-compact per-page" aria-label="每页条数" bind:value={perPage} onchange={() => reload(1)}>
      <option value={50}>50/页</option>
      <option value={100}>100/页</option>
      <option value={200}>200/页</option>
    </select>
  </div>

  <div class="scroll list">
    {#if req.loading && !accounts.length}
      <Skeleton count={3} />
    {:else if !accounts.length}
      <div class="none"><p class="muted serif">暂无匹配账号</p></div>
    {:else}
      {#each accounts as a (a.id)}
        <AccountRow
          account={a}
          active={selectedId === a.id}
          selected={selected.has(a.id)}
          {selectMode}
          menuOpen={menuId === a.id}
          {onselect}
          ontoggle={toggle}
          onmenu={(id) => (menuId = id)}
          onedit={(id) => { menuId = null; onedit?.(id) }}
          ondelete={(acc) => { menuId = null; ondelete?.(acc) }}
        />
      {/each}
    {/if}
  </div>

  <Pager
    {page}
    {totalPages}
    loading={req.loading}
    compact
    prevLabel="上页"
    nextLabel="下页"
    onchange={reload}
  />
</aside>

<style>
  .sidebar {
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-rows: auto auto auto minmax(0, 1fr) auto;
    border-right: 1px solid color-mix(in srgb, var(--stone) 80%, transparent);
    background: color-mix(in srgb, white 70%, var(--paper));
    backdrop-filter: blur(12px);
    transition: opacity 180ms var(--ease);
  }
  .side-head {
    display: flex; align-items: baseline; justify-content: space-between;
    padding: 0.95rem 1.1rem 0.45rem;
  }
  .side-head h2 { margin: 0; font-size: 1.05rem; font-weight: 600; }

  .filters {
    display: grid;
    grid-template-columns: 1fr 84px;
    gap: 0.45rem;
    padding: 0 0.9rem 0.6rem;
  }
  .select { appearance: auto; }

  .bulk-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 0.5rem;
    padding: 0 0.9rem 0.6rem;
    font-size: 0.78rem;
  }
  .pick-all { display: inline-flex; align-items: center; gap: 0.4rem; }
  .pick-all input { width: 15px; height: 15px; }
  .per-page { width: 88px; appearance: auto; }

  .list { min-height: 0; }
  .none { padding: 2.5rem 1rem; text-align: center; }
  .none p { margin: 0; }
</style>
