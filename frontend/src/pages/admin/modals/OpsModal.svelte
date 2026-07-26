<script>
  import { untrack } from 'svelte'
  import { api } from '../../../lib/api.js'
  import { createRequest } from '../../../lib/request.svelte.js'
  import Modal from '../../../lib/ui/Modal.svelte'
  import Pager from '../../../lib/ui/Pager.svelte'

  let { open = false, onclose, onerror } = $props()

  let items = $state([])
  // 不能叫 actions —— 会被下方 {#snippet actions()} 的同名绑定遮蔽
  let actionTypes = $state([])
  let action = $state('all')
  let page = $state(1)
  let totalPages = $state(0)
  let total = $state(0)
  const req = createRequest()

  // untrack 必须有：load() 会读 action，不隔离的话本 effect 就依赖了 action，
  // 于是每次切换筛选都会被这里重置回 'all'。
  $effect(() => {
    const isOpen = open
    untrack(() => {
      if (isOpen) {
        action = 'all'
        load(1)
      }
    })
  })

  async function load(p = 1) {
    const data = await req.run((signal) => api.ops({ page: p, action }, { signal }))
    if (!data) {
      if (req.error) onerror?.(req.error)
      return
    }
    items = data.items || []
    actionTypes = data.actions || []
    page = data.page
    totalPages = data.total_pages
    total = data.total
  }
</script>

<Modal {open} title="系统操作记录" width="680px" {onclose}>
  <div class="filter-row">
    <label class="lbl" for="ops-action">操作类型</label>
    <select id="ops-action" class="field field-compact" bind:value={action} onchange={() => load(1)}>
      <option value="all">全部</option>
      {#each actionTypes as a (a)}
        <option value={a}>{a}</option>
      {/each}
    </select>
    <span class="faint nums count">{total} 条</span>
  </div>

  <div class="scroll ops-list">
    {#each items as o (o.id)}
      <div class="ops-row">
        <span class="nums faint">{o.created_at}</span>
        <span class="action">{o.action}</span>
        <span class="truncate muted">{o.target}</span>
        <span class="truncate faint">{o.detail}</span>
      </div>
    {:else}
      <p class="empty muted">
        {req.loading ? '加载中…' : action === 'all' ? '暂无操作日志记录' : `没有 ${action} 类型的记录`}
      </p>
    {/each}
  </div>

  <Pager {page} {totalPages} loading={req.loading} compact onchange={load} />

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>关闭</button>
  {/snippet}
</Modal>

<style>
  .filter-row {
    display: flex; align-items: center; gap: 0.6rem;
  }
  .filter-row select { width: 190px; appearance: auto; }
  .count { margin-left: auto; font-size: 0.82rem; }
  .ops-list {
    max-height: 360px;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
  }
  .ops-row {
    display: grid; grid-template-columns: 1.1fr 0.8fr 1fr 1.1fr; gap: 0.6rem;
    padding: 0.5rem 0.2rem; font-size: 0.84rem;
    border-bottom: 1px solid color-mix(in srgb, var(--stone) 50%, transparent);
  }
  .action { font-weight: 500; }
  .empty { padding: 2rem; text-align: center; margin: 0; }
</style>
