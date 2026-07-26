<script>
  import { api } from '../../lib/api.js'
  import { flash } from '../../lib/stores/toast.svelte.js'
  import ConfirmDialog from '../../lib/ui/ConfirmDialog.svelte'

  let { selected = $bindable(new Set()), ondone, onerror } = $props()

  let busy = $state(false)
  let confirmDelete = $state(false)

  let ids = $derived([...selected])
  let count = $derived(ids.length)

  async function probe() {
    busy = true
    try {
      const r = await api.batchProbe(ids)
      flash(`已探测 ${r.probed}（正常 ${r.ok}）`)
      ondone?.()
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  async function remove() {
    busy = true
    const removed = ids
    try {
      const r = await api.batchDelete(removed)
      flash(`已删除 ${r.deleted} 个账号`)
      selected = new Set()
      confirmDelete = false
      ondone?.(removed)
    } catch (e) {
      onerror?.(e.message)
    } finally {
      busy = false
    }
  }

  /**
   * 导出会把明文密码与 refresh_token 落到下载目录。
   * 后端要求 confirm=1 且会写 ops_log，这里直接用浏览器导航触发下载。
   */
  function exportCsv() {
    if (!confirm(`导出 ${count} 个账号的明文凭据（含 refresh_token）到本地文件？此操作会记入操作日志。`)) return
    window.location.href = `/api/accounts/export?confirm=1&ids=${ids.join(',')}`
    flash('已开始导出')
  }
</script>

{#if count > 0}
  <div class="bulk" role="region" aria-label="批量操作">
    <span class="count nums">已选 {count} 个账号</span>
    <div class="acts">
      <button class="btn btn-sm" type="button" disabled={busy} onclick={probe}>批量探测</button>
      <button class="btn btn-sm" type="button" disabled={busy} onclick={exportCsv}>导出凭据</button>
      <button class="btn btn-sm btn-danger" type="button" disabled={busy} onclick={() => (confirmDelete = true)}>批量删除</button>
      <button class="btn btn-sm btn-ghost" type="button" onclick={() => (selected = new Set())}>取消选择</button>
    </div>
  </div>
{/if}

<ConfirmDialog
  open={confirmDelete}
  title="批量删除账号"
  message="将删除 {count} 个账号及其全部别名，无法撤销。"
  detail="删除后这些账号的凭据不再保存，需要重新导入。"
  confirmLabel="确认删除"
  danger
  requireText={String(count)}
  {busy}
  onconfirm={remove}
  oncancel={() => (confirmDelete = false)}
/>

<style>
  .bulk {
    position: absolute;
    left: 50%;
    bottom: 1.5rem;
    transform: translateX(-50%);
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 0.85rem 0.6rem 1.15rem;
    border-radius: 12px;
    background: rgba(255, 254, 250, 0.96);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.9);
    outline: 1px solid color-mix(in srgb, var(--stone) 85%, transparent);
    box-shadow: var(--shadow-lg);
    animation: fadeIn 180ms var(--ease-out);
  }
  .count { font-size: 0.86rem; font-weight: 600; white-space: nowrap; }
  .acts { display: flex; flex-wrap: wrap; gap: 0.35rem; }
</style>
