<script>
  /**
   * 分页条。加载中禁用两侧按钮，避免连点导致的请求叠加。
   * hasMore 用于后端无法给出总页数的场景（如 codes_only 滚动扫描）。
   */
  let {
    page = 1,
    totalPages = 0,
    hasMore = null,
    loading = false,
    compact = false,
    prevLabel = '上一页',
    nextLabel = '下一页',
    onchange,
  } = $props()

  let unknownTotal = $derived(hasMore !== null)
  let atStart = $derived(page <= 1)
  let atEnd = $derived(unknownTotal ? !hasMore : page >= totalPages || totalPages === 0)
</script>

<div class="pager nums" class:compact>
  <button
    class="btn btn-sm btn-ghost"
    type="button"
    disabled={atStart || loading}
    onclick={() => onchange?.(page - 1)}
  >{prevLabel}</button>
  <span class="faint">
    {#if unknownTotal}
      第 {page} 页
    {:else}
      {page}/{Math.max(totalPages, 1)}
    {/if}
  </span>
  <button
    class="btn btn-sm btn-ghost"
    type="button"
    disabled={atEnd || loading}
    onclick={() => onchange?.(page + 1)}
  >{nextLabel}</button>
</div>

<style>
  .pager {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.5rem;
    border-top: 1px solid color-mix(in srgb, var(--stone) 70%, transparent);
    background: color-mix(in srgb, var(--paper) 40%, white);
  }
  .pager.compact { padding: 0.45rem 0.85rem; }
</style>
