<script>
  import { api } from '../../../lib/api.js'
  import { createRequest } from '../../../lib/request.svelte.js'
  import Modal from '../../../lib/ui/Modal.svelte'
  import Pager from '../../../lib/ui/Pager.svelte'

  let { open = false, onclose, onerror } = $props()

  let items = $state([])
  let page = $state(1)
  let totalPages = $state(0)
  const req = createRequest()

  $effect(() => {
    if (open) load(1)
  })

  async function load(p = 1) {
    const data = await req.run((signal) => api.ops({ page: p }, { signal }))
    if (!data) {
      if (req.error) onerror?.(req.error)
      return
    }
    items = data.items || []
    page = data.page
    totalPages = data.total_pages
  }
</script>

<Modal {open} title="系统操作记录" width="680px" {onclose}>
  <div class="scroll ops-list">
    {#each items as o (o.id)}
      <div class="ops-row">
        <span class="nums faint">{o.created_at}</span>
        <span class="action">{o.action}</span>
        <span class="truncate muted">{o.target}</span>
        <span class="truncate faint">{o.detail}</span>
      </div>
    {:else}
      <p class="empty muted">{req.loading ? '加载中…' : '暂无操作日志记录'}</p>
    {/each}
  </div>

  <Pager {page} {totalPages} loading={req.loading} compact onchange={load} />

  {#snippet actions()}
    <button class="btn" type="button" onclick={onclose}>关闭</button>
  {/snippet}
</Modal>

<style>
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
